"""Shared helpers used by every document generator."""

from __future__ import annotations

import json
import random
import time
from typing import TYPE_CHECKING, Any, Callable, Optional

from ...schemas.model import SemanticModel
from ...schemas.shared import DocMetadataCore
from ..io import AGENT_EFFORT
from ..llm import LLMClient

Warn = Callable[[str], None]


from ..cache import LLMResponseCache

if TYPE_CHECKING:
    from ..context import JobAIContext


def _resolve_effort(name: str, effort: Optional[str]) -> Optional[str]:
    """An explicit ``effort=`` always wins; otherwise fall back to the
    agent's tier in ``io.AGENT_EFFORT`` (Phase 0); an agent absent from that
    map keeps the client's own default (``None``)."""
    return effort if effort is not None else AGENT_EFFORT.get(name)


def _record_usage(ai_context: Optional["JobAIContext"], client: LLMClient, name: str) -> None:
    """Content-free spend telemetry: token counts only, read opportunistically
    off whatever the client stashed after its last real (non-cached) call."""
    if ai_context is None:
        return
    usage = getattr(client, "last_usage", None) or {}
    ai_context.record(
        name,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )


def _schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_json_schema(value: Any, schema: dict, path: str = "$") -> list[str]:
    """Small dependency-free validator for the JSON-schema subset our agents use.

    Provider-side structured output is still the first line of defense. This
    local check is the final gate before caching/rendering, especially for
    provider fallbacks that can only ask for JSON in plain text.
    """
    errors: list[str] = []
    if not isinstance(schema, dict):
        return errors

    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if not any(_schema_type_matches(value, t) for t in expected_type):
            return [f"{path}: expected one of {expected_type}, got {type(value).__name__}"]
    elif isinstance(expected_type, str) and not _schema_type_matches(value, expected_type):
        return [f"{path}: expected {expected_type}, got {type(value).__name__}"]

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} is not in enum {schema['enum']!r}")

    if expected_type == "object" and isinstance(value, dict):
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: missing required property")
        properties = schema.get("properties") or {}
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key}: additional property not allowed")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(validate_json_schema(value[key], child_schema, f"{path}.{key}"))

    if expected_type == "array" and isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                errors.extend(validate_json_schema(item, item_schema, f"{path}[{i}]"))

    return errors


def _validate_response(response: dict, schema: dict) -> dict:
    errors = validate_json_schema(response, schema)
    if errors:
        preview = "; ".join(errors[:5])
        if len(errors) > 5:
            preview += f"; +{len(errors) - 5} more"
        raise ValueError(f"LLM response did not match schema: {preview}")
    return response


def call_llm(client: LLMClient, system: str, payload: dict, schema: dict,
             warn: Warn, name: str, *,
             ai_context: Optional["JobAIContext"] = None,
             effort: Optional[str] = None) -> Optional[dict]:
    """Call ``client.complete_json``; on any failure, warn and return ``None``
    so the caller can fall back to its deterministic path.

    ``ai_context`` (Phase 0), when given, supplies the job-scoped cache path
    (falling back to the client-wide default when absent) and collects
    content-free call/token telemetry under ``name``. ``effort`` overrides
    ``io.AGENT_EFFORT``'s tier for ``name``.
    """
    model_id = getattr(client, "model", "unknown")
    effort = _resolve_effort(name, effort)
    cache_path = ai_context.cache_path if ai_context is not None else None
    cache = LLMResponseCache(cache_path)
    try:
        cached = cache.get(system, payload, schema, model_id, effort)
        if cached is not None:
            try:
                return _validate_response(cached, schema)
            except ValueError as exc:
                warn(f"{name}: ignored invalid cached LLM response ({exc})")
        res = client.complete_json(system, json.dumps(payload, ensure_ascii=False), schema, effort=effort)
        if res is not None:
            res = _validate_response(res, schema)
            cache.set(system, payload, schema, model_id, res, effort)
            _record_usage(ai_context, client, name)
        return res
    except Exception as exc:  # any failure -> deterministic fallback
        warn(f"{name}: LLM call failed, using deterministic fallback ({exc})")
        return None
    finally:
        cache.close()


def call_llm_with_retry(
    client: LLMClient, system: str, payload: dict, schema: dict,
    *, retries: int = 1, backoff_range: tuple[float, float] = (2.0, 5.0),
    ai_context: Optional["JobAIContext"] = None,
    effort: Optional[str] = None,
    name: str = "LLM",
) -> Optional[dict]:
    """Like :func:`call_llm`, but retries once (after a jittered delay)
    before giving up, and never warns itself.

    Built for batched callers (a page batch, a page-guide batch): a lone
    failed/invalid batch response is often a transient blip (rate limit,
    network hiccup), so it's retried silently first. Only on the final
    failure does this return ``None`` — the caller knows exactly which
    objects (pages, measures, ...) that batch covered and can produce a far
    more specific warning than this function could, so it does that instead
    of warning here.

    ``name`` identifies the agent for the effort tier (``io.AGENT_EFFORT``)
    and telemetry (``ai_context``) — see :func:`call_llm`.
    """
    model_id = getattr(client, "model", "unknown")
    effort = _resolve_effort(name, effort)
    cache_path = ai_context.cache_path if ai_context is not None else None
    cache = LLMResponseCache(cache_path)
    try:
        cached = cache.get(system, payload, schema, model_id, effort)
        if cached is not None:
            try:
                return _validate_response(cached, schema)
            except ValueError:
                pass
        attempt = 0
        while True:
            try:
                res = client.complete_json(system, json.dumps(payload, ensure_ascii=False), schema, effort=effort)
                if res is not None:
                    res = _validate_response(res, schema)
                    cache.set(system, payload, schema, model_id, res, effort)
                    _record_usage(ai_context, client, name)
                return res
            except Exception:
                if attempt >= retries:
                    return None
                attempt += 1
                time.sleep(random.uniform(*backoff_range))
    finally:
        cache.close()


def build_core_metadata(
    model: SemanticModel,
    document_type: str,
    *,
    default_audience: str,
    owner: Optional[str] = None,
    audience: Optional[str] = None,
    refresh: Optional[str] = None,
    version: Optional[str] = None,
    status: Optional[str] = None,
    author: Optional[str] = None,
    reviewer: Optional[str] = None,
    classification: Optional[str] = None,
    business_decision: Optional[str] = None,
    requirements: Optional[str] = None,
    security_notes: Optional[str] = None,
    refresh_notes: Optional[str] = None,
    deployment_notes: Optional[str] = None,
    access_notes: Optional[str] = None,
    glossary: Optional[str] = None,
    assumptions: Optional[str] = None,
    support_notes: Optional[str] = None,
) -> DocMetadataCore:
    """Assemble the metadata contract shared by the non-technical document
    types (audit, executive, user guide) — Day 3: carries the full human
    intake field set the technical document's own ``_metadata()`` already
    does, so every document type can steer its prose and render these
    sections, not just the technical one."""
    overridden = getattr(model.meta, "overridden_fields", [])
    return DocMetadataCore(
        report_name=model.report_name,
        document_type=document_type,
        owner=owner,
        refresh_schedule=refresh,
        target_audience=audience or default_audience,
        source_format=model.meta.source_format,
        generated_at=model.meta.generated_at,
        version=version,
        status=status,
        overridden_fields=list(overridden),
        author=author,
        reviewer=reviewer,
        classification=classification,
        business_decision=business_decision,
        requirements=requirements,
        security_notes=security_notes,
        refresh_notes=refresh_notes,
        deployment_notes=deployment_notes,
        access_notes=access_notes,
        glossary=glossary,
        assumptions=assumptions,
        support_notes=support_notes,
    )
