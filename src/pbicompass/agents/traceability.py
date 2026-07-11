"""Requirements Traceability Matrix (Day 4 of the post-launch hardening plan).

Business Requirements is currently a free-text field that just gets echoed
back verbatim in the technical document's §3 — useful as a record, but it
never tells a reader whether the report actually *satisfies* what's written
there. This module turns each requirement line into a RAG (Covered/Partial/
Gap) verdict against the report's real measures, columns, and pages, with
working anchor links back into the document — the signature "did the build
match the ask" deliverable a Big-4 handover pack always includes and no
competitor tool attempts, per the roadmap.

Two layers, the same shape as ``agents/consistency.py``:

- A deterministic keyword-overlap matcher (:func:`match_candidates`) ranks
  every measure/column/page against a requirement's own vocabulary — free,
  exact, and itself enough to produce a real (if coarse) verdict offline.
- An LLM pass (:func:`build_requirements_matrix`, when a client is given)
  judges the *already-matched* candidates rather than reasoning from
  scratch — it may only cite anchors that were actually offered as
  candidates for that requirement, never invent one, which is what makes
  every evidence link in the rendered matrix a real, working link.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from . import io

if TYPE_CHECKING:
    from .context import JobAIContext
    from .llm import LLMClient

Warn = Callable[[str], None]

STATUSES = ("Covered", "Partial", "Gap")


@dataclass
class RequirementEvidence:
    kind: str    # "measure" | "column" | "page"
    name: str    # display name, e.g. "Total Revenue" or "Sales[Region]"
    anchor: str  # e.g. "measure-total-revenue" — an id that exists in the rendered document


@dataclass
class RequirementCoverage:
    text: str
    priority: str = ""    # "Must" | "Should" | ""
    status: str = "Gap"   # "Covered" | "Partial" | "Gap"
    evidence: list[RequirementEvidence] = field(default_factory=list)
    rationale: str = ""


# -- Parsing --------------------------------------------------------------------

_PRIORITY_RE = re.compile(r"^\s*\[(Must|Should)\]\s*", re.IGNORECASE)


def parse_requirements(text: Optional[str]) -> list[tuple[str, str]]:
    """One requirement per line, with an optional leading ``[Must]``/
    ``[Should]`` priority tag. Returns ``(priority, requirement_text)``
    pairs in input order; blank lines are skipped."""
    out: list[tuple[str, str]] = []
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        m = _PRIORITY_RE.match(line)
        if m:
            priority = m.group(1).capitalize()
            line = line[m.end():].strip()
        else:
            priority = ""
        if line:
            out.append((priority, line))
    return out


# -- Deterministic candidate matching --------------------------------------------

_STOPWORDS = frozenset(
    "the a an is are was were this that these those and or but if of in on at for to with per by as "
    "show shows display displays must should need needs support supports allow allows report reports".split()
)


def _significant_words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text) if w.lower() not in _STOPWORDS}


def build_candidates(model, translations: Optional[dict] = None) -> list[dict]:
    """One candidate per measure/column/page — built directly from
    ``model`` (plus the job-shared DAX Translator result, when available)
    rather than any one generator's own assembled artifacts, so this runs
    the same way regardless of which document type asks for it first, with
    no ordering dependency on technical.py having already run. Uses
    ``report_facts.report_pages`` for the page/visual text — the same
    grounded facts every renderer already shows (Day 4: "grounded against
    report_facts"). ``{kind, name, anchor, text}`` per candidate."""
    from ..render._shared import anchor_slug
    from .report_facts import report_pages

    translations = translations or {}
    candidates: list[dict] = []
    for m in model.all_measures():
        translated = (translations.get(m.name) or {}).get("plain_english", "")
        text = f"{m.name} {m.description or ''} {translated}"
        candidates.append({
            "kind": "measure", "name": m.name,
            "anchor": f"measure-{anchor_slug(m.name)}", "text": text,
        })
    for t in model.tables:
        for c in t.columns:
            if c.is_hidden:
                continue
            candidates.append({
                "kind": "column", "name": f"{t.name}[{c.name}]",
                "anchor": f"column-{anchor_slug(t.name)}-{anchor_slug(c.name)}",
                "text": f"{t.name} {c.name} {c.description or ''}",
            })
    for page in report_pages(model):
        if page.get("hidden"):
            continue
        visuals = page.get("visuals", [])
        visual_text = " ".join(v.get("label", "") for v in visuals)
        metric_text = " ".join(x for v in visuals for x in v.get("metrics", []))
        dim_text = " ".join(x for v in visuals for x in v.get("dimensions", []))
        name = page.get("name", "")
        candidates.append({
            "kind": "page", "name": name,
            "anchor": f"page-{anchor_slug(name)}",
            "text": f"{name} {visual_text} {metric_text} {dim_text}",
        })
    return candidates


def match_candidates(requirement_text: str, candidates: list[dict], *, top_n: int = 5) -> list[dict]:
    """Rank ``candidates`` by shared significant words with
    ``requirement_text``; returns the top ``top_n`` with ``score > 0``,
    each candidate dict extended with its ``score``."""
    req_words = _significant_words(requirement_text)
    if not req_words:
        return []
    scored = []
    for c in candidates:
        score = len(req_words & _significant_words(c["text"]))
        if score > 0:
            scored.append({**c, "score": score})
    scored.sort(key=lambda c: -c["score"])
    return scored[:top_n]


def _deterministic_verdict(matched: list[dict]) -> tuple[str, list[dict]]:
    """Coarse offline verdict from match scores alone: no candidates at all
    is a Gap; a strong (>= 2 shared words) top match is Covered; anything
    weaker but present is Partial — a real, reproducible verdict without an
    LLM, upgraded by the LLM pass when a client is available."""
    if not matched:
        return "Gap", []
    top_score = matched[0]["score"]
    if top_score >= 2:
        return "Covered", [c for c in matched if c["score"] == top_score][:2]
    return "Partial", matched[:1]


# -- Orchestration ----------------------------------------------------------------

def build_requirements_matrix(
    model,
    requirements_text: Optional[str],
    client: Optional["LLMClient"] = None,
    warn: Optional[Warn] = None,
    ai_context: Optional["JobAIContext"] = None,
) -> list[RequirementCoverage]:
    """Parse ``requirements_text``, deterministically match each line
    against the report's own measures/columns/pages, then (when ``client``
    is given) ask the Requirements Traceability agent to judge the matched
    candidates. Returns ``[]`` when there are no requirements to check —
    never a placeholder row.

    Takes ``model`` directly (not any one generator's assembled artifacts)
    so this runs identically no matter which document type computes it
    first in a job — no ordering dependency the way ``audit_verdicts``
    (Day 2) has on the Audit document specifically. Reuses
    ``ai_context.translations`` (the job-shared DAX Translator result) for
    richer measure text when a job context is already available.

    Always at least the deterministic verdict: a failed/offline LLM pass
    degrades to the keyword-overlap result, never an empty matrix."""
    warn = warn or (lambda _msg: None)
    parsed = parse_requirements(requirements_text)
    if not parsed:
        return []

    translations = ai_context.translations if ai_context is not None else None
    candidates = build_candidates(model, translations)

    per_requirement_candidates: list[dict] = []
    results: list[RequirementCoverage] = []
    for priority, text in parsed:
        matched = match_candidates(text, candidates)
        per_requirement_candidates.append({"requirement": text, "candidates": matched})
        status, evidence = _deterministic_verdict(matched)
        results.append(RequirementCoverage(
            text=text, priority=priority, status=status,
            evidence=[RequirementEvidence(kind=e["kind"], name=e["name"], anchor=e["anchor"]) for e in evidence],
        ))

    if client is None:
        return results

    payload = [
        {
            "requirement": r["requirement"],
            "candidates": [{"anchor": c["anchor"], "kind": c["kind"], "name": c["name"]} for c in r["candidates"]],
        }
        for r in per_requirement_candidates
    ]
    try:
        from .generators.base import call_llm  # local import: see consistency.py's identical note
        data = call_llm(
            client, io.TRACEABILITY_SYSTEM, io.traceability_input(payload),
            io.TRACEABILITY_SCHEMA, warn, "Requirements Traceability", ai_context=ai_context,
        )
    except Exception as exc:  # pragma: no cover - defensive, mirrors call_llm's own contract
        warn(f"Requirements Traceability: LLM call failed, using deterministic verdicts only ({exc})")
        return results
    if not data:
        return results

    by_text = {r.text: r for r in results}
    candidate_by_anchor = {c["anchor"]: c for c in candidates}
    allowed_by_text = {r["requirement"]: {c["anchor"] for c in r["candidates"]} for r in per_requirement_candidates}

    for item in data.get("requirements", []):
        req_text = (item.get("requirement") or "").strip()
        target = by_text.get(req_text)
        if target is None:
            continue
        status = item.get("status")
        if status not in STATUSES:
            continue
        allowed = allowed_by_text.get(req_text, set())
        # Grounding: only anchors this requirement was actually offered as a
        # candidate may be cited as evidence — never trust an invented one.
        evidence_anchors = [a for a in item.get("evidence", []) if a in allowed]
        if status != "Gap" and not evidence_anchors:
            # A "Covered"/"Partial" verdict with no real evidence left after
            # grounding is worse than the deterministic fallback already in
            # place — keep it rather than show an unsupported claim.
            continue
        target.status = status
        target.evidence = [
            RequirementEvidence(kind=candidate_by_anchor[a]["kind"], name=candidate_by_anchor[a]["name"], anchor=a)
            for a in evidence_anchors
        ]
        target.rationale = (item.get("rationale") or "").strip()
    return results


def coverage_stat(matrix: list[RequirementCoverage]) -> str:
    """``"7/9"``-style one-line stat: requirements at least Partially
    covered out of the total — the executive doc's own summary line."""
    if not matrix:
        return ""
    covered = sum(1 for r in matrix if r.status in ("Covered", "Partial"))
    return f"{covered}/{len(matrix)}"
