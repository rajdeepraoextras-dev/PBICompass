"""LLM client layer.

``LLMClient`` is the minimal contract the orchestrator depends on:
``complete_json(system, user, schema) -> dict``. Four concrete
implementations: :class:`AnthropicClient` (Claude, native structured
outputs), :class:`GeminiClient`, :class:`CohereClient`, and
:class:`MeshAPIClient` — the last routes through https://developers.meshapi.ai,
a single API key giving access to 1000+ models across providers via an
OpenAI-compatible endpoint, for BYOK users who'd rather not manage a
separate key per provider.

Every provider SDK import is lazy — the rest of ``pbicompass`` (and the
deterministic pipeline) works without any of them installed.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from typing import Any, Optional, Protocol


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema: dict, *, effort: Optional[str] = None) -> dict:
        """Return a JSON object conforming to ``schema``.

        ``effort`` (Phase 0) is a per-call override of the client's own
        thinking-depth default (see ``EFFORT_LEVELS`` below) — ``None`` keeps
        the client's own default. Every provider maps it to its own native
        reasoning knob where the configured model supports one (§4.0);
        where it doesn't (e.g. Cohere's non-reasoning models, MeshAPI models
        outside the o-series/gpt-5 families), it's accepted for protocol
        compatibility and silently ignored rather than risk a rejected call.
        """
        ...


# Thinking-depth / token-spend levels for output_config.effort, low to high.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


# Hard ceiling on a single LLM call. Without this, a slow/huge prompt or a
# network hiccup on the host can block the calling thread indefinitely — the
# job then sits in "processing" forever since nothing else marks it failed.
# ``call_llm`` (agents/generators/base.py) catches the resulting timeout
# exception and falls back to the deterministic engine for that agent.
#
# 180s is deliberately generous and should not be trimmed to "fail faster":
# it is a per-attempt ceiling on the slowest *legitimate* call, not a target.
# Measured mean is ~33s/call, but that is a mean over 25 calls spanning
# effort tiers — the xhigh whole-bundle passes (Report Intelligence, Senior
# Reviewer) are far slower than the low-effort Critic. Cutting this to near
# the mean would time out exactly the calls the output quality leans on, and
# each false timeout costs a retry *and* degrades that agent to
# deterministic.
_DEFAULT_TIMEOUT_SECONDS = 180.0

# Retries belong to ``_call_with_retries`` below and to nothing else.
#
# Every provider SDK here ships its own retry loop (anthropic and openai both
# default to max_retries=2, i.e. 3 attempts). Left at the default, that loop
# nests *underneath* ours and the two multiply: 3 of ours x 3 of the SDK's =
# 9 HTTP attempts for one agent call, each bounded only by the 180s timeout
# above. A single slow-but-healthy provider could therefore burn ~27 minutes
# inside one ``complete_json`` and still return None to the deterministic
# fallback — with the job's own watchdog force-failing the whole bundle long
# before that resolved. Pinning the SDKs to a single attempt makes the retry
# budget exactly what ``PBICOMPASS_LLM_MAX_RETRIES`` says it is.
#
# The trade-off, stated plainly: the SDK loops honour a 429's ``Retry-After``
# header and ours does not (it uses bounded exponential backoff with jitter).
# One predictable retry layer is worth more here than a smarter one whose
# real budget nobody can see.
_SDK_MAX_RETRIES = 0


def _resolve_error_class(module: Any, *dotted_paths: str, default: type = Exception) -> type:
    """Look up one of several dotted attribute paths on ``module`` (e.g. an
    SDK's ``BadRequestError`` living either at the package root or under a
    version-specific ``errors`` submodule) and return the first that
    resolves, else ``default``. Used so the reasoning-fallback retry below
    can catch "this model/param combination was rejected" without hard-
    coding an exact SDK layout that might shift between versions."""
    for path in dotted_paths:
        obj = module
        for part in path.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                break
        if isinstance(obj, type) and issubclass(obj, BaseException):
            return obj
    return default


# --- Transient-error retry (§4.0 robustness) ------------------------------
#
# HTTP statuses worth retrying: transient rate-limit / server / network
# conditions that a short wait plausibly clears. Explicitly NOT retried:
# 400 (bad request), 401 (auth), 402 (spend limit / insufficient balance),
# 403, 404 — these never fix themselves on a retry and would only add latency
# in front of the deterministic fallback ``call_llm`` already provides. A real
# 2026 finding drove this: a live MeshAPI bundle hit repeated 402s mid-run and
# silently half-degraded to deterministic; the same code path meant a routine
# 429 rate-limit on any provider would do the same. 402 stays non-retryable
# (correct — it won't clear); 429/5xx/network now get a bounded retry first.
_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
# Matched by class name (not isinstance) so it survives SDK version/layout
# shifts and works uniformly across the anthropic/openai/cohere/genai SDKs,
# which all expose these same names for connection/timeout/5xx conditions.
_RETRYABLE_EXC_NAMES = frozenset({
    "APIConnectionError", "APITimeoutError", "APIConnectionTimeoutError",
    "InternalServerError", "RateLimitError", "ServiceUnavailableError",
    "ServerError",
})


def _llm_retry_attempts() -> int:
    """Total attempts per SDK call (>=1). Override with ``PBICOMPASS_LLM_MAX_RETRIES``
    (the number of *retries*; total attempts = retries + 1). ``0`` disables
    retrying entirely, preserving the old fail-fast-to-deterministic behavior."""
    try:
        retries = int(os.environ.get("PBICOMPASS_LLM_MAX_RETRIES", "2"))
    except ValueError:
        retries = 2
    return max(1, retries + 1)


def _is_retryable_llm_error(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        return status in _RETRYABLE_STATUS
    # No HTTP status attached (connection reset, read timeout, DNS failure) —
    # fall back to matching the exception class name.
    return type(exc).__name__ in _RETRYABLE_EXC_NAMES


def _call_with_retries(fn, *, base_delay: float = 1.0, max_delay: float = 8.0):
    """Call ``fn`` and retry on transient LLM API errors (429 / 5xx / network)
    with bounded exponential backoff plus jitter. Non-retryable errors
    (400/401/402/403/404 and anything not recognised as transient) propagate
    immediately so the caller's deterministic fallback kicks in without wasted
    latency. After the final attempt the last exception is re-raised unchanged,
    so the existing per-provider BadRequest degradation ladders still see it."""
    attempts = _llm_retry_attempts()
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - re-raised below
            if attempt == attempts - 1 or not _is_retryable_llm_error(exc):
                raise
            delay = min(max_delay, base_delay * (2 ** attempt))
            time.sleep(delay * (0.5 + random.random()))  # 50–150% jitter


class _UsageTracker:
    """Gives a client a per-thread ``last_usage`` attribute.

    Clients stash the token counts of their most recent call so
    ``generators/base.py::_record_usage`` can read them back immediately
    afterwards and attribute them to the calling agent. One job now issues
    several agent calls concurrently through the *same* client instance
    (``agents/parallel.py``), so a single shared attribute would be
    overwritten by whichever call finished last and the counts would land on
    the wrong agent. Scoping the value to the calling thread keeps the
    existing ``getattr(client, "last_usage", None)`` contract — including its
    ``None`` default before the first call — exactly as it was.
    """

    _usage_local: threading.local

    def _init_usage(self) -> None:
        self._usage_local = threading.local()

    @property
    def last_usage(self) -> Optional[dict]:
        return getattr(self._usage_local, "value", None)

    @last_usage.setter
    def last_usage(self, value: dict) -> None:
        self._usage_local.value = value


def _loose_json_parse(text: str) -> dict:
    """``json.loads``, tolerant of a stray ```json ... ``` fence — used for
    MeshAPI's unstructured JSON fallback (:class:`MeshAPIClient`), where a
    model is asked in plain text to reply with JSON rather than constrained
    via ``response_format`` and occasionally wraps it in a fence anyway."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        stripped = re.sub(r"\n?```$", "", stripped)
    return json.loads(stripped)


class AnthropicClient(_UsageTracker):
    """Claude-backed client using structured outputs.

    Defaults to Claude Opus 4.8 with adaptive thinking at ``high`` effort — the
    recommended floor for intelligence-sensitive prose (Business Analyst, DAX
    Translator, Data Modeler agents). Pass ``effort="xhigh"`` or ``"max"`` for
    deeper reasoning at the cost of latency. Reads the API key from
    ``ANTHROPIC_API_KEY`` (BYOK) unless one is passed explicitly.
    """

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        *,
        api_key: Optional[str] = None,
        effort: str = "high",
        max_tokens: int = 16000,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if effort not in EFFORT_LEVELS:
            raise ValueError(f"Unknown effort level {effort!r}. Choose from {EFFORT_LEVELS}.")
        try:
            import anthropic  # noqa: PLC0415 (intentional lazy import)
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "The 'anthropic' package is required for the Claude provider. "
                "Install it with: pip install -e \".[agents]\""
            ) from exc
        self._init_usage()
        self._anthropic = anthropic
        self._client = (
            anthropic.Anthropic(api_key=api_key, timeout=timeout,
                                max_retries=_SDK_MAX_RETRIES)
            if api_key else anthropic.Anthropic(timeout=timeout,
                                                max_retries=_SDK_MAX_RETRIES)
        )
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.timeout = timeout

    def complete_json(self, system: str, user: str, schema: dict, *, effort: Optional[str] = None) -> dict:
        resolved_effort = effort or self.effort

        def _call(include_effort: bool):
            output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
            if include_effort:
                output_config["effort"] = resolved_effort
            return _call_with_retries(lambda: self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                thinking={"type": "adaptive"},
                output_config=output_config,
                messages=[{"role": "user", "content": user}],
            ))

        # Graceful degradation (§4.0): if this model/account rejects the
        # effort tier, retry once without it rather than failing the whole
        # agent call — ``call_llm`` would otherwise fall back to the
        # deterministic engine for a problem that a plain retry fixes.
        bad_request = _resolve_error_class(self._anthropic, "BadRequestError")
        try:
            response = _call(True)
        except bad_request:
            response = _call(False)
        if response.stop_reason == "refusal":
            raise RuntimeError("Claude declined the request (stop_reason=refusal).")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise RuntimeError("Claude returned no text content.")
        # Content-free spend telemetry (Phase 0): token counts only, never the
        # prompt/response text itself. Read opportunistically by callers
        # (``agents/generators/base.py::call_llm``) via ``getattr``.
        usage = getattr(response, "usage", None)
        self.last_usage = {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        }
        return json.loads(text)


def _gemini_schema(schema: dict) -> dict:
    """Strip keys Gemini's ``response_schema`` doesn't accept (additionalProperties)."""
    def clean(node):
        if isinstance(node, dict):
            return {k: clean(v) for k, v in node.items() if k != "additionalProperties"}
        if isinstance(node, list):
            return [clean(x) for x in node]
        return node
    return clean(schema)


# effort -> Gemini ``thinking_budget`` (tokens the model may spend
# thinking before answering). ``-1`` is Gemini's own convention for
# "dynamic" thinking — the model sizes its own budget per request, which is
# the closest fit for "max" now that token cost is not a constraint (§4.0).
# (Some Gemini 3.x models additionally expose a coarser ``thinking_level``
# knob; not wired here — ``thinking_budget`` is the stable, model-agnostic
# knob and is sufficient for every effort tier below.)
_GEMINI_THINKING_BUDGET = {
    "low": 1024,
    "medium": 4096,
    "high": 8192,
    "xhigh": 24576,
    "max": -1,
}


class GeminiClient:
    """Google Gemini-backed client using JSON structured output.

    Defaults to Gemini 3.5 Flash. Reads the API key from ``GEMINI_API_KEY`` (or
    ``GOOGLE_API_KEY``) — never hardcode it. Lazy-imports ``google-genai`` so the
    rest of ``pbicompass`` works without the dependency.
    """

    def __init__(self, model: str = "gemini-3.5-flash", *, api_key: Optional[str] = None,
                 effort: Optional[str] = None, max_output_tokens: int = 16000,
                 timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> None:
        if effort is not None and effort not in EFFORT_LEVELS:
            raise ValueError(f"Unknown effort level {effort!r}. Choose from {EFFORT_LEVELS}.")
        try:
            from google import genai  # noqa: PLC0415 (intentional lazy import)
            from google.genai import types  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "The 'google-genai' package is required for the Gemini provider. "
                "Install it with: pip install -e \".[agents]\""
            ) from exc
        self._genai = genai
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        # HttpOptions.timeout is milliseconds.
        http_options = types.HttpOptions(timeout=int(timeout * 1000))
        self._client = (
            genai.Client(api_key=key, http_options=http_options)
            if key else genai.Client(http_options=http_options)
        )
        self.model = model
        self.effort = effort
        self.max_output_tokens = max_output_tokens

    def complete_json(self, system: str, user: str, schema: dict, *, effort: Optional[str] = None) -> dict:
        from google.genai import types  # noqa: PLC0415

        resolved_effort = effort if effort is not None else self.effort
        budget = _GEMINI_THINKING_BUDGET.get(resolved_effort)

        def _config(include_thinking: bool):
            kwargs: dict = dict(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=_gemini_schema(schema),
                max_output_tokens=self.max_output_tokens,
            )
            if include_thinking and budget is not None:
                kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)
            return types.GenerateContentConfig(**kwargs)

        # Graceful degradation (§4.0): a model with no thinking support
        # rejects ``thinking_config`` — retry once without it rather than
        # failing the agent call outright.
        from google.genai import errors as genai_errors  # noqa: PLC0415
        client_error = _resolve_error_class(genai_errors, "ClientError")
        try:
            response = _call_with_retries(lambda: self._client.models.generate_content(
                model=self.model, contents=user, config=_config(True),
            ))
        except client_error:
            if budget is None:
                raise
            response = _call_with_retries(lambda: self._client.models.generate_content(
                model=self.model, contents=user, config=_config(False),
            ))
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini returned no text content.")
        return json.loads(text)


# effort -> Cohere reasoning ``token_budget``. Only sent when the configured
# model actually supports reasoning (``command-a-reasoning`` and similar) —
# see ``_cohere_reasoning_capable`` below.
_COHERE_THINKING_BUDGET = {
    "low": 1024,
    "medium": 4096,
    "high": 8192,
    "xhigh": 16000,
    "max": 16000,
}


def _cohere_reasoning_capable(model: str) -> bool:
    return "reasoning" in model.lower()


class CohereClient:
    """Cohere-backed client using JSON structured output.

    Defaults to Command A (``command-a-03-2025``), Cohere's text-only flagship —
    it returns a plain answer without the reasoning/thinking token spend of the
    ``command-a-plus``/``command-a-reasoning`` models, so it's markedly faster and
    cheaper for schema-constrained JSON. (Reasoning models still work: their
    content list leads with a ``thinking`` item, and ``complete_json`` skips past
    it to the ``text`` item.) Reads the API key from ``COHERE_API_KEY`` (or
    ``CO_API_KEY``) — never hardcode it. Lazy-imports ``cohere`` so the rest of
    ``pbicompass`` works without the dependency. Uses the v2 chat API with
    ``response_format={"type": "json_object", "schema": ...}``; Cohere accepts
    ``additionalProperties``, so the schemas pass through unmodified.
    """

    # Command A models cap output at 8192 tokens; sending more 400s the request.
    def __init__(self, model: str = "command-a-03-2025", *, api_key: Optional[str] = None,
                 effort: Optional[str] = None, max_tokens: int = 8192,
                 timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> None:
        if effort is not None and effort not in EFFORT_LEVELS:
            raise ValueError(f"Unknown effort level {effort!r}. Choose from {EFFORT_LEVELS}.")
        try:
            import cohere  # noqa: PLC0415 (intentional lazy import)
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "The 'cohere' package is required for the Cohere provider. "
                "Install it with: pip install -e \".[agents]\""
            ) from exc
        self._cohere = cohere
        key = api_key or os.environ.get("COHERE_API_KEY") or os.environ.get("CO_API_KEY")
        # ClientV2 timeout is in seconds.
        self._client = cohere.ClientV2(api_key=key, timeout=timeout)
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.timeout = timeout

    def complete_json(self, system: str, user: str, schema: dict, *, effort: Optional[str] = None) -> dict:
        # The reasoning knob only exists on Cohere's reasoning models
        # (command-a-reasoning and similar) — the default command-a-03-2025
        # has none, so effort is accepted-and-ignored there; pass --model to
        # opt into a reasoning model.
        resolved_effort = effort if effort is not None else self.effort
        budget = (
            _COHERE_THINKING_BUDGET.get(resolved_effort)
            if _cohere_reasoning_capable(self.model) else None
        )

        def _call(include_thinking: bool):
            kwargs: dict = dict(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    # Cohere's json_object mode wants the request to
                    # explicitly ask for JSON, on top of the enforced schema.
                    {"role": "user", "content": f"{user}\n\nRespond with a single JSON object."},
                ],
                response_format={"type": "json_object", "schema": schema},
            )
            if include_thinking and budget is not None:
                kwargs["thinking"] = {"type": "enabled", "token_budget": budget}
            return _call_with_retries(lambda: self._client.chat(**kwargs))

        # Graceful degradation (§4.0): retry once without the thinking param
        # if this model/account rejects it, rather than failing the call.
        bad_request = _resolve_error_class(self._cohere, "BadRequestError", "errors.BadRequestError")
        try:
            response = _call(True)
        except bad_request:
            if budget is None:
                raise
            response = _call(False)
        # message.content is a list of typed items; reasoning models lead with a
        # 'thinking' item, so pick the 'text' one (mirrors the Anthropic client)
        # rather than blindly taking content[0].
        content = getattr(response.message, "content", None) or []
        text = next(
            (item.text for item in content
             if getattr(item, "type", None) == "text" and getattr(item, "text", None)),
            None,
        )
        if not text:
            raise RuntimeError("Cohere returned no text content.")
        return json.loads(text)


# Model-name pattern for reasoning-capable model families routed through
# MeshAPI (``provider/model-name`` ids — matched against the part after the
# slash): OpenAI's o-series (o1, o3, o4-mini, ...) and gpt-5, plus DeepSeek's
# reasoning/"Thinking"-tagged models — V4 Flash/Pro (MeshAPI's catalog
# documents ``reasoning_effort`` support for these) and the always-on-
# thinking R1 family (R1, R1-0528, R1-Distill-*) and V3.2 Speciale.
# Everything else (gpt-4o, gpt-4.1, DeepSeek's *hybrid* thinking/non-thinking
# V3/V3.1/V3.2/V3.2-Exp models — which MeshAPI toggles via a separate
# ``reasoning.enabled`` boolean this client doesn't send — third-party
# models, ...) is treated as non-reasoning.
# ``gpt-5`` is followed by ``.`` as well as ``-`` or end-of-id: MeshAPI's catalog
# carries dot-separated point releases (gpt-5.2/5.4/5.5/5.6-luna, ...) alongside
# the bare ``gpt-5``. The original ``gpt-5(-|$)`` matched none of the dotted ones,
# so an expensive gpt-5.5 run silently never received ``reasoning_effort`` — paying
# premium rates for no reasoning at all. Sending it to a model that rejects it is
# safe: ``complete_json``'s ladder retries without the param on a 400.
_MESHAPI_REASONING_MODEL_RE = re.compile(
    r"^(o[1-9](-mini|-preview|-pro)?|gpt-5)([-.]|$)"
    r"|^deepseek-(v3\.2-speciale|v4-(flash|pro)|r1(-\d+)?|r1-distill-.+)$",
    re.IGNORECASE,
)

# OpenAI's ``reasoning_effort`` only accepts a handful of values
# ("minimal"/"low"/"medium"/"high" depending on model family) — our finer
# 5-tier scale collapses onto it, with xhigh/max clamped to its ceiling.
_MESHAPI_REASONING_EFFORT = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "high",
    "max": "high",
}


def _meshapi_reasoning_capable(model: str) -> bool:
    """Whether the model *accepts* the ``reasoning_effort`` param (a capability
    fact about the routed model id). Distinct from whether we should *send* it
    — see ``_meshapi_send_reasoning``."""
    name = model.rsplit("/", 1)[-1]
    return bool(_MESHAPI_REASONING_MODEL_RE.match(name))


# Reasoning-capable models where sending ``reasoning_effort`` empirically HURTS
# output quality instead of helping — so it is withheld despite the model
# accepting the param. This is a measured quality decision, not a capability
# one, hence separate from ``_meshapi_reasoning_capable``.
#
# deepseek-v4-flash (the default): a controlled cold A/B on the Corporate Spend
# full bundle (2026-07-18) scored 44/61 *with* reasoning vs 50–56/61 *without*,
# and reasoning uniquely introduced a factual contradiction against the audit
# verdict (benchmark T4). Withholding it restores the better output while the
# combo-cache still trims the wasted structured-output attempt. The effort
# machinery remains fully active for any genuinely reasoning-benefiting model a
# caller selects (o-series, gpt-5, ...). Revisit per-model as data accrues.
_MESHAPI_REASONING_WITHHELD = frozenset({"deepseek-v4-flash"})


def _meshapi_send_reasoning(model: str) -> bool:
    name = model.rsplit("/", 1)[-1]
    return _meshapi_reasoning_capable(model) and name.lower() not in _MESHAPI_REASONING_WITHHELD


class MeshAPIClient(_UsageTracker):
    """MeshAPI-backed client (https://developers.meshapi.ai) — a single
    ``rsk_...`` API key routes to 1000+ models across providers through one
    OpenAI-compatible endpoint, so BYOK users no longer need a separate
    ``ANTHROPIC_API_KEY``/``GEMINI_API_KEY``/``COHERE_API_KEY`` per provider.

    Model ids are ``provider/model-name`` (e.g. ``"openai/gpt-4o"``,
    ``"anthropic/claude-opus-4.8"``) — see MeshAPI's model catalog for the
    full list. Note MeshAPI's own catalog uses dot-separated point releases
    for Claude models (``claude-opus-4.8``), unlike Anthropic's native API
    model ids, which use hyphens (``claude-opus-4-8``, as
    :class:`AnthropicClient` expects) — the two are not interchangeable.

    Defaults to ``openai/gpt-4o`` (2026-07-18, switched from
    ``deepseek/deepseek-v4-flash``). The reason is a measured live failure:
    v4-flash scored well in offline scoring but a real full-bundle run ran
    ~15 minutes and then errored — the deepseek reasoning family is slow and
    flaky through MeshAPI's routing under load — whereas a live run on gpt-4o
    completed cleanly with first-class output. gpt-4o is a non-reasoning model,
    so ``complete_json`` correctly never sends it ``reasoning_effort`` (see
    ``_meshapi_send_reasoning``), and OpenAI ids have first-class
    structured-output support on MeshAPI. A Claude default remains off the table:
    MeshAPI routes at least some Anthropic model ids
    through AWS Bedrock's Converse API, which doesn't support the
    structured-output parameter MeshAPI's translation layer attaches for
    them (every ``complete_json`` call fails with a Bedrock
    ``ValidationException`` on ``output_config.format`` for those ids).

    The default can be overridden without a code change via the
    ``MESHAPI_MODEL`` env var (a ``provider/model-name`` id), or per-client
    with an explicit ``model=``. ``complete_json`` below still degrades
    gracefully to a prompt-only JSON instruction if a chosen model rejects
    ``response_format`` outright.

    Implemented with the official ``openai`` SDK pointed at MeshAPI's base
    URL, exactly as MeshAPI's own quickstart recommends ("replace the Base
    URL of any OpenAI-compatible SDK with https://api.meshapi.ai"), rather
    than a bespoke ``meshapi`` package integration. Lazy-imports ``openai``
    so the rest of ``pbicompass`` works without the dependency. Reads the
    API key from ``MESHAPI_API_KEY`` (BYOK) unless passed explicitly.
    """

    _BASE_URL = "https://api.meshapi.ai/v1"
    # The default engine has to reliably complete a full bundle and pass this
    # tool's own output gate. History on the Corporate Spend fixture:
    #   inclusionai/ling-2.6-flash  2/2 runs BLOCKED by the gate (T4: user-guide
    #                               prose contradicting the audit's verdict) ->
    #                               error, zero documents.
    #   deepseek/deepseek-v4-flash  scored well in offline scoring, but a live
    #                               full-bundle run (2026-07-18) ran ~15 minutes
    #                               and then FAILED — the reasoning family is slow
    #                               and flaky through MeshAPI's routing under load.
    #   openai/gpt-4o (now default)  a live full run completed cleanly with
    #                               first-class output. A non-reasoning model, so
    #                               the reasoning-effort machinery correctly never
    #                               sends `reasoning_effort` to it, and OpenAI ids
    #                               have first-class structured-output support on
    #                               MeshAPI (no Bedrock/Converse rejection path).
    # A default that finishes and produces good documents beats a cheaper one that
    # burns 15 minutes and errors. Override per-deploy with MESHAPI_MODEL.
    _FALLBACK_MODEL = "openai/gpt-4o"

    def __init__(
        self,
        model: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        effort: Optional[str] = None,
        max_tokens: int = 16000,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import openai  # noqa: PLC0415 (intentional lazy import)
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "The 'openai' package is required for the MeshAPI provider (MeshAPI "
                "exposes an OpenAI-compatible API). Install it with: pip install -e \".[agents]\""
            ) from exc
        self._init_usage()
        key = api_key or os.environ.get("MESHAPI_API_KEY")
        self._client = openai.OpenAI(base_url=self._BASE_URL, api_key=key, timeout=timeout,
                                     max_retries=_SDK_MAX_RETRIES)
        self._openai = openai
        # Model resolution: explicit arg > MESHAPI_MODEL env (deploy-time
        # override, no code change to switch models) > hard fallback. The env
        # value must be a full "provider/model-name" id; anything without a
        # slash can't be a MeshAPI id, so it's ignored rather than sent.
        env_model = (os.environ.get("MESHAPI_MODEL") or "").strip()
        if not model:
            model = env_model if "/" in env_model else self._FALLBACK_MODEL
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.timeout = timeout
        # Discovered-once cache of the (include_reasoning, structured) parameter
        # combination this model actually accepts. MeshAPI fronts 1000+ models
        # of wildly varying support and exposes no per-model capability signal,
        # so ``complete_json`` learns it by trying — but only once. Without this
        # the degradation ladder re-pays the discovery cost on *every* call: a
        # live deepseek-v4-flash bundle (2026-07-18) 422'd twice per agent call
        # before its third attempt succeeded — 2 wasted round-trips × ~25 calls
        # — because the model rejects ``response_format: json_schema``. Guarded
        # by a lock since one client instance is shared across the parallel
        # agent fan-out; the value converges (same model => same answer), the
        # lock just keeps the read/write clean.
        self._working_combo: Optional[tuple[bool, bool]] = None
        self._combo_lock = threading.Lock()

    def complete_json(self, system: str, user: str, schema: dict, *, effort: Optional[str] = None) -> dict:
        # MeshAPI documents `reasoning_effort` as a unified-schema field, but
        # doesn't drop it gracefully for models that don't recognize it — it
        # 400s ("Unrecognized request argument supplied: reasoning_effort")
        # instead, confirmed against openai/gpt-4o (a non-reasoning model),
        # failing every single agent call. MeshAPI fronts 1000+ models of
        # wildly varying reasoning-effort support with no per-model signal
        # exposed here, so it's only ever sent when the routed model id
        # itself looks reasoning-capable (o-series/gpt-5 and the deepseek
        # reasoning families, which the default ``deepseek/deepseek-v4-flash``
        # belongs to); every other model never receives it.
        resolved_effort = effort if effort is not None else self.effort
        reasoning_effort = (
            _MESHAPI_REASONING_EFFORT.get(resolved_effort)
            if _meshapi_send_reasoning(self.model) else None
        )

        # MeshAPI fronts 1000+ models of wildly varying structured-output
        # support with no per-model signal exposed here either, so a
        # rejected ``response_format`` also degrades gracefully: the schema
        # is restated as a plain-text instruction instead and the response
        # is parsed loosely (stripping a stray ```json fence some models add
        # despite the instruction). The default deepseek-v4-flash *does* hit
        # this path — it rejects ``response_format: json_schema`` and lands on
        # the reasoning-kept/text-schema rung below.
        def _call(*, include_reasoning: bool, structured: bool):
            sys_prompt = system if structured else (
                system + "\n\nRespond with only a single valid JSON object (no markdown "
                "code fences, no commentary) that matches exactly this JSON schema:\n"
                + json.dumps(schema, ensure_ascii=False)
            )
            kwargs: dict = dict(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user},
                ],
            )
            if structured:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "response", "schema": schema, "strict": True},
                }
            if include_reasoning and reasoning_effort is not None:
                kwargs["reasoning_effort"] = reasoning_effort
            return _call_with_retries(lambda: self._client.chat.completions.create(**kwargs))

        # Graceful degradation ladder (§4.0), most-capable first. Reasoning is
        # preserved *before* structured output is given up, because reasoning is
        # the quality lever and structured output is only a parse-reliability
        # convenience (``_loose_json_parse`` + the caller's own schema
        # validation in generators/base.py already backstop an unstructured
        # reply). The old ladder dropped reasoning first and so never tried
        # "reasoning without json_schema" — which is exactly what
        # deepseek-v4-flash needs, since it accepts ``reasoning_effort`` but
        # rejects ``response_format: json_schema``. The result was that the
        # default model silently ran with reasoning OFF on every call (measured
        # live 2026-07-18), defeating the whole reason it was chosen over ling.
        #
        #   (reasoning, structured)
        #   (True,  True)   both — an o-series/gpt-5 / fully-capable model
        #   (True,  False)  reasoning kept, schema restated as text — v4-flash
        #   (False, True)   reasoning rejected but json_schema fine
        #   (False, False)  neither — the universal floor
        want_reasoning = reasoning_effort is not None
        full_ladder: list[tuple[bool, bool]] = []
        if want_reasoning:
            full_ladder.append((True, True))
            full_ladder.append((True, False))
        full_ladder.append((False, True))
        full_ladder.append((False, False))

        # Try the combo this model already proved it accepts first, so calls
        # 2..N are a single round-trip instead of re-walking the ladder. The
        # rest stays as fallback in case a cached combo goes stale.
        with self._combo_lock:
            cached = self._working_combo
        if cached is not None and cached in full_ladder:
            attempts = [cached] + [c for c in full_ladder if c != cached]
        else:
            attempts = full_ladder

        # Catch both 400 and 422: MeshAPI's telemetry labels a rejected
        # ``response_format``/``reasoning_effort`` as "unprocessable_entity",
        # and depending on the routed upstream it can surface as either status.
        # Only catching BadRequestError (400) would let a 422 escape the ladder
        # straight to the deterministic fallback — degrading a whole agent for a
        # param the very next rung would have dropped.
        param_rejected = (
            _resolve_error_class(self._openai, "BadRequestError"),
            _resolve_error_class(self._openai, "UnprocessableEntityError"),
        )
        response = None
        last_exc: Exception | None = None
        for include_reasoning, structured in attempts:
            try:
                response = _call(include_reasoning=include_reasoning, structured=structured)
                with self._combo_lock:
                    self._working_combo = (include_reasoning, structured)
                break
            except param_rejected as exc:
                last_exc = exc
        if response is None:
            raise last_exc
        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "content_filter":
            raise RuntimeError("MeshAPI declined the request (finish_reason=content_filter).")
        text = choice.message.content
        if not text:
            raise RuntimeError("MeshAPI returned no text content.")
        usage = getattr(response, "usage", None)
        self.last_usage = {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        }
        return _loose_json_parse(text)


_DEFAULT_MODEL = {
    "anthropic": "claude-opus-4-8",
    "gemini": "gemini-3.5-flash",
    "cohere": "command-a-03-2025",
    # None: MeshAPIClient resolves its own default (MESHAPI_MODEL env var,
    # else deepseek/deepseek-v4-flash — never a Claude id; see its docstring:
    # MeshAPI routes at least some Anthropic ids through AWS Bedrock's
    # Converse API, which rejects the structured-output parameter every
    # agent here needs).
    "meshapi": None,
}


def get_client(provider: Optional[str], **kwargs: Any) -> Optional[LLMClient]:
    """Resolve a provider name to a client (or ``None`` for the offline engine).

    ``None`` / ``"none"`` / ``"offline"`` -> deterministic pipeline (no client).
    ``"anthropic"`` / ``"claude"``        -> :class:`AnthropicClient`.
    ``"gemini"`` / ``"google"``           -> :class:`GeminiClient`.
    ``"cohere"`` / ``"command"``          -> :class:`CohereClient`.
    ``"meshapi"`` / ``"mesh"``            -> :class:`MeshAPIClient` (one key, 1000+ models).
    """
    if provider in (None, "none", "offline", "deterministic"):
        return None
    model = kwargs.pop("model", None)
    if provider in ("anthropic", "claude"):
        if not model or "claude" not in model:
            model = _DEFAULT_MODEL["anthropic"]
        return AnthropicClient(model=model, **kwargs)
    if provider in ("gemini", "google"):
        if not model or "gemini" not in model:
            model = _DEFAULT_MODEL["gemini"]
        return GeminiClient(model=model, **kwargs)
    if provider in ("cohere", "command"):
        if not model or "command" not in model:
            model = _DEFAULT_MODEL["cohere"]
        return CohereClient(model=model, **kwargs)
    if provider in ("meshapi", "mesh"):
        # MeshAPI model ids are always "provider/model-name" — a bare model
        # id from another provider's default (e.g. the CLI's own
        # "claude-opus-4-8") isn't valid here, so fall back the same way:
        # None lets MeshAPIClient resolve MESHAPI_MODEL / its own default.
        if not model or "/" not in model:
            model = _DEFAULT_MODEL["meshapi"]
        return MeshAPIClient(model=model, **kwargs)
    raise ValueError(f"Unknown LLM provider: {provider!r}")
