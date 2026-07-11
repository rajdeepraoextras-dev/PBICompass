"""The ``executive_document.json`` contract — a concise, non-technical
summary readable in under ten minutes (G.1: 6 sections, printing to no more
than 2 pages).

Audience: managers, executives, project owners. No implementation details:
no DAX, no table/column inventories, no relationship diagrams, no raw file
paths, and no model/report statistics tables — those live in the technical
document and the audit report; this document gets only the 4-KPI header
strip. Most fields are assembled deterministically from facts already
computed elsewhere in the pipeline (data sources, modeling risks, audit
findings); only the narrative prose fields optionally go through an LLM,
with a deterministic fallback so the document is always complete offline.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .shared import DocMetadataCore


@dataclass
class ExecutiveRisk:
    """One risk phrased for executives (G.1): a consequence if left
    unaddressed, plus a specific ask — never raw audit/DAX terminology.
    ``rule_id``, when set, deep-links to the exact audit finding behind this
    risk (I5) instead of a generic section-level link."""
    severity: str
    consequence: str
    ask: str
    rule_id: str = ""


@dataclass
class ExecutiveDocument:
    """Top-level ``executive_document.json`` object."""
    metadata: DocMetadataCore
    purpose: str = ""
    business_value: str = ""
    key_kpis: list[str] = field(default_factory=list)
    top_risks: list[ExecutiveRisk] = field(default_factory=list)
    # Source *types* only (e.g. "3 Excel workbook(s)") — never a path,
    # server, or database name (G.1).
    data_source_types: list[str] = field(default_factory=list)
    refresh_schedule: Optional[str] = None
    # Day 3: gateway/latency detail from the intake form's "Gateway, Latency
    # & Refresh Details" field — the "Data & Refresh at a Glance" section's
    # only source for anything beyond the bare schedule string.
    refresh_notes: Optional[str] = None
    maintenance_note: str = ""
    # Owner comes from ``metadata.owner`` (shared across doc types); steward
    # has no source yet — will be sourced from the enrichment file (5.1)
    # once it's wired in — always "not specified" until then.
    steward: Optional[str] = None
    classification: Optional[str] = None
    next_steps: list[str] = field(default_factory=list)
    # Day 4: "7/9"-style Requirements Traceability coverage stat (empty
    # when no requirements were supplied) — see agents.traceability.
    requirements_coverage: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
