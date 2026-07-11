"""The ``audit_document.json`` contract — an evaluation of the model, not a
description of it. Populated entirely by deterministic rules
(:mod:`pbicompass.agents.audit_rules`), except ``narrative_overview`` which
optionally goes through an LLM with a deterministic fallback.

Audience: BI architects, technical leads, governance teams, managers.

Two things are explicitly out of scope and intentionally absent, rather than
faked, because today's ``model.json`` genuinely lacks the data:
hierarchies/calculation groups (never populated by the parsers) are omitted
from :class:`UnusedAssets`, and every :class:`PerformanceRisk` is a
metadata-only heuristic (no row-level data is ever extracted) — its
``detail`` text says so explicitly.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .shared import DocMetadataCore

Severity = str  # "Critical" | "High" | "Medium" | "Low"


@dataclass
class HealthScore:
    overall: int  # 0-100
    band: str  # "Excellent" | "Good" | "Fair" | "Poor"
    component_scores: dict[str, int] = field(default_factory=dict)  # modeling, dax, governance, performance, unused_assets
    # one-sentence explanation per component score, keyed like component_scores
    component_notes: dict[str, str] = field(default_factory=dict)


@dataclass
class ComplexityAssessment:
    level: str  # "Low" | "Medium" | "High"
    table_count: int
    measure_count: int
    relationship_count: int
    calculated_column_count: int
    max_relationship_depth: int
    rationale: str = ""


@dataclass
class DaxFinding:
    measure: str
    table: Optional[str]
    kind: str  # duplicate_logic | very_long_expression | missing_description | naming_issue | repeated_pattern
    detail: str
    severity: Severity = "Medium"
    rule_id: str = ""


@dataclass
class BestPracticeCheck:
    id: str
    name: str
    passed: bool
    detail: str
    category: str = "modeling"  # schema | naming | documentation | modeling
    rule_id: str = ""


@dataclass
class PerformanceRisk:
    kind: str  # large_calc_column | high_cardinality_signal | large_text_column | heavy_dax
               # | visual_density | slow_slicer_signal | cross_filter_complexity
    object_name: str
    table: Optional[str]
    detail: str
    severity: Severity = "Medium"
    rule_id: str = ""


@dataclass
class GovernanceFinding:
    area: str  # rls | descriptions | ownership | sensitive_columns | data_source_consistency
    detail: str
    severity: Severity = "Medium"
    rule_id: str = ""


@dataclass
class UnusedAssets:
    measures: list[str] = field(default_factory=list)
    columns: list[dict[str, str]] = field(default_factory=list)  # {table, column}
    tables: list[str] = field(default_factory=list)
    calculated_columns: list[dict[str, str]] = field(default_factory=list)  # {table, column}
    report_pages: list[str] = field(default_factory=list)
    # Otherwise-unused columns/calculated columns/tables belonging to
    # Power BI's auto-generated Auto Date/Time hidden tables — excluded
    # from the lists above (Day 2) and counted here instead, since they
    # are the PBIC-PERF-007 finding's own category, not a maintenance gap.
    auto_datetime_excluded: int = 0


@dataclass
class Recommendation:
    priority: str  # Critical | High | Medium | Low
    issue: str
    why_it_matters: str
    suggested_fix: str
    expected_benefit: str
    effort: str = "Medium"  # estimated implementation effort: Low | Medium | High
    category: str = "modeling"  # dax | modeling | performance | governance | unused_assets
    rule_id: str = ""


@dataclass
class FindingCluster:
    """One root-cause group of otherwise-isolated findings (AI-Native Phase 4
    / Day 7 Audit Synthesizer) — e.g. Auto Date/Time being enabled explains a
    performance-risk finding, a failed star-schema check (its hidden local
    tables miscounted as extra facts), and a batch of unused hidden
    calculated columns, all of which would clear together if the one root
    cause were fixed. Populated only when an LLM client is supplied; absent
    (``clusters == []``) is a fully valid, complete document — the
    per-finding list is unaffected either way."""
    root_cause: str
    rule_ids: list[str] = field(default_factory=list)
    narrative: str = ""
    confidence: str = "Medium"  # High | Medium | Low


@dataclass
class AuditDocument:
    """Top-level ``audit_document.json`` object."""
    metadata: DocMetadataCore
    health: HealthScore
    complexity: ComplexityAssessment
    dax_findings: list[DaxFinding] = field(default_factory=list)
    best_practices: list[BestPracticeCheck] = field(default_factory=list)
    performance_risks: list[PerformanceRisk] = field(default_factory=list)
    governance: list[GovernanceFinding] = field(default_factory=list)
    unused_assets: UnusedAssets = field(default_factory=UnusedAssets)
    recommendations: list[Recommendation] = field(default_factory=list)
    narrative_overview: str = ""
    suppressed_rules: list[str] = field(default_factory=list)
    changelog: Optional[str] = None
    # AI-Native Phase 4 / Day 7: root-cause clusters + the overall remediation
    # story across them. Deterministic fallback (no client, or the call
    # fails) = both stay empty and the Root-Cause Analysis section is simply
    # omitted by the renderers (Day 8) — never a placeholder or an error.
    clusters: list[FindingCluster] = field(default_factory=list)
    strategic_narrative: str = ""
    # Rule-engine ledger (4.1 / J.A.1): counts over the full stable-ID rule
    # registry (agents.audit_rules.FINDING_RULES), not just the findings that
    # happened to fire — "checks run" must include rules that passed silently.
    checks_run: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    checks_suppressed: int = 0
    # {category: {"run": n, "passed": n, "failed": n, "suppressed": n}}
    checks_by_category: dict[str, dict[str, int]] = field(default_factory=dict)
    # Day 3: human-stated facts (the intake form) that contradict what the
    # model actually contains — {field, human_claim, model_finding,
    # explanation}, from agents.consistency.find_human_claim_discrepancies.
    # Never silently resolved one way or the other; always surfaced.
    discrepancies: list[dict[str, str]] = field(default_factory=list)
    # Day 4: Requirements Traceability rows whose status is "Gap" — a
    # stated business requirement with nothing in the report satisfying it,
    # each {text, priority, status, rationale}. Empty when every
    # requirement is at least Partially covered, or none were supplied.
    requirements_gaps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
