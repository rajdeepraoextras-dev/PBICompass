"""Metadata shared across the non-technical document types (audit, executive,
user guide). Deliberately independent from :class:`~pbicompass.schemas.document.
DocumentMetadata` — that dataclass belongs to the technical document and stays
untouched for backward compatibility. This is a small, separate contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DocMetadataCore:
    report_name: str
    document_type: str
    owner: Optional[str] = None
    refresh_schedule: Optional[str] = None
    target_audience: Optional[str] = None
    source_format: Optional[str] = None
    generated_at: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    score_trend: Optional[str] = None
    overridden_fields: list[str] = field(default_factory=list)
    # Day 3: the same human intake fields ``schemas.document.DocumentMetadata``
    # (the technical document) already carries — extended here so the audit,
    # executive, and user guide documents can receive and render them too,
    # instead of only the technical document ever seeing them.
    author: Optional[str] = None
    reviewer: Optional[str] = None
    classification: Optional[str] = None
    business_decision: Optional[str] = None
    requirements: Optional[str] = None
    security_notes: Optional[str] = None
    refresh_notes: Optional[str] = None
    deployment_notes: Optional[str] = None
    access_notes: Optional[str] = None
    glossary: Optional[str] = None
    assumptions: Optional[str] = None
    support_notes: Optional[str] = None
