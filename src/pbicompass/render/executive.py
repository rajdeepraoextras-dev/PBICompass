"""Render an :class:`ExecutiveDocument` to Markdown, HTML, and DOCX.

Six sections (G.1), concise and non-technical by design: no DAX, no table/
column inventories, no relationship diagrams, no raw file paths, and no
model/report statistics tables — those live in the technical document and
the audit report. Reads in under ten minutes and prints to no more than two
pages. Reuses the same low-level primitives as the other renderers
(``_shared``, ``_html_shell``, ``_docx_writer``).
"""

from __future__ import annotations

from pathlib import Path

from ..schemas.executive_document import ExecutiveDocument, ExecutiveRisk
from ._docx_writer import _Docx
from ._html_shell import page_shell
from ._shared import format_timestamp as _fmt_ts
from ._shared import html_e as _e
from ._shared import md_table as _table

_SECTION_TITLES = [
    "1. Purpose & Value",
    "2. Key KPIs",
    "3. Top Risks & Recommended Actions",
    "4. Data & Refresh at a Glance",
    "5. Ownership & Accountability",
    "6. What's Next",
]


def _risk_line(r: ExecutiveRisk) -> str:
    return f"[{r.severity}] {r.consequence} — **Ask:** {r.ask}"


# -- Markdown -------------------------------------------------------------------
def render_markdown(doc: ExecutiveDocument) -> str:
    md = doc.metadata
    out: list[str] = [f"# {md.report_name} — Executive Summary\n"]
    out.append(f"_{md.target_audience or ''} · generated {_fmt_ts(md.generated_at)}_\n")

    out.append(f"\n## {_SECTION_TITLES[0]}\n")
    out.append(doc.purpose + "\n")
    out.append(doc.business_value + "\n")

    out.append(f"\n## {_SECTION_TITLES[1]}\n")
    if doc.key_kpis:
        for kpi in doc.key_kpis:
            out.append(f"- {kpi}")
    else:
        out.append("_No KPIs identified._")
    out.append("")

    out.append(f"\n## {_SECTION_TITLES[2]}\n")
    if doc.top_risks:
        for r in doc.top_risks:
            out.append(f"- {_risk_line(r)}")
    else:
        out.append("_No known risks — the latest audit found nothing to act on._")
    out.append("")

    out.append(f"\n## {_SECTION_TITLES[3]}\n")
    if doc.data_source_types:
        out.append("**Data sources:** " + ", ".join(doc.data_source_types) + "\n")
    else:
        out.append("**Data sources:** _None detected._\n")
    out.append(f"**Refresh schedule:** {doc.refresh_schedule or '_Not documented._'}\n")
    out.append(doc.maintenance_note + "\n")

    out.append(f"\n## {_SECTION_TITLES[4]}\n")
    ownership_rows = [["Owner", md.owner or "not specified"]]
    if doc.steward:
        ownership_rows.append(["Steward", doc.steward])
    if doc.classification:
        ownership_rows.append(["Classification", doc.classification])
    out.append(_table(["Field", "Value"], ownership_rows))

    out.append(f"\n## {_SECTION_TITLES[5]}\n")
    if doc.next_steps:
        for s in doc.next_steps:
            out.append(f"- {s}")
    else:
        out.append("_Nothing outstanding._")
    out.append("")

    return "\n".join(out).rstrip() + "\n"


# -- HTML -------------------------------------------------------------------------
def _risk_href(rule_id: str, audit_href: str | None) -> str:
    """Deep-link a risk to its exact audit finding (I5) when the audit doc
    is a sibling in this job — the finding's recommendation card is
    anchored by rule_id (see render/audit.py). Falls back to the section
    anchor when no rule_id is available (e.g. the "unused assets" risk),
    and to no link at all when audit wasn't generated in this job (2.7)."""
    if not audit_href:
        return ""
    anchor = f"rec-{rule_id}" if rule_id else "sec8"
    return f' — <a href="{_e(audit_href)}#{_e(anchor)}">full detail</a>'


def render_html(
    doc: ExecutiveDocument, *,
    doc_links: list[tuple[str, str]] | None = None,
    sibling_hrefs: dict[str, str] | None = None,
) -> str:
    md = doc.metadata
    audit_href = (sibling_hrefs or {}).get("audit")

    toc = [(f"sec{i+1}", title.split(". ", 1)[1]) for i, title in enumerate(_SECTION_TITLES)]
    kpis = [
        ("Key KPIs", len(doc.key_kpis)),
        ("Top Risks", len(doc.top_risks)),
        ("Data Sources", len(doc.data_source_types)),
        ("Next Steps", len(doc.next_steps)),
    ]

    o: list[str] = []
    o.append(f'<h2 id="sec1">{_e(_SECTION_TITLES[0])}</h2>')
    o.append(f"<p>{_e(doc.purpose)}</p>")
    o.append(f"<p>{_e(doc.business_value)}</p>")

    kpi_ids = [f"kpi-{i}" for i in range(len(doc.key_kpis))]
    o.append(f'<h2 id="sec2">{_e(_SECTION_TITLES[1])}</h2>')
    if doc.key_kpis:
        o.append("<ul>" + "".join(f'<li id="{_e(kid)}">{_e(k)}</li>' for k, kid in zip(doc.key_kpis, kpi_ids))
                 + "</ul>")
    else:
        o.append('<p class="muted">No KPIs identified.</p>')

    risk_ids = [f"risk-{i}" for i in range(len(doc.top_risks))]
    o.append(f'<h2 id="sec3">{_e(_SECTION_TITLES[2])}</h2>')
    if doc.top_risks:
        for r, rid in zip(doc.top_risks, risk_ids):
            suffix = _risk_href(r.rule_id, audit_href)
            o.append(f'<div class="card-section" id="{_e(rid)}">')
            o.append(f'<p><span class="pill {_e(r.severity.lower())}">{_e(r.severity)}</span> {_e(r.consequence)}</p>')
            o.append(f'<p><strong>Ask:</strong> {_e(r.ask)}{suffix}</p>')
            o.append("</div>")
    else:
        o.append('<p class="muted">No known risks — the latest audit found nothing to act on.</p>')

    o.append(f'<h2 id="sec4">{_e(_SECTION_TITLES[3])}</h2>')
    if doc.data_source_types:
        o.append(f'<p><strong>Data sources:</strong> {_e(", ".join(doc.data_source_types))}</p>')
    else:
        o.append('<p><strong>Data sources:</strong> <span class="muted">None detected.</span></p>')
    refresh_html = _e(doc.refresh_schedule) if doc.refresh_schedule else '<span class="muted">not documented</span>'
    o.append(f'<p><strong>Refresh schedule:</strong> {refresh_html}</p>')
    o.append(f"<p>{_e(doc.maintenance_note)}</p>")

    _not_specified = '<span class="muted">not specified</span>'
    owner_html = _e(md.owner) if md.owner else _not_specified
    ownership_items = [f"<li><strong>Owner:</strong> {owner_html}</li>"]
    if doc.steward:
        ownership_items.append(f"<li><strong>Steward:</strong> {_e(doc.steward)}</li>")
    if doc.classification:
        ownership_items.append(f"<li><strong>Classification:</strong> {_e(doc.classification)}</li>")
    o.append(f'<h2 id="sec5">{_e(_SECTION_TITLES[4])}</h2>')
    o.append("<ul>" + "".join(ownership_items) + "</ul>")

    o.append(f'<h2 id="sec6">{_e(_SECTION_TITLES[5])}</h2>')
    if doc.next_steps:
        o.append("<ul>" + "".join(f"<li>{_e(s)}</li>" for s in doc.next_steps) + "</ul>")
    else:
        o.append('<p class="muted">Nothing outstanding.</p>')

    search_index = [{"title": sec_title, "type": "section", "anchor": sec_id} for sec_id, sec_title in toc]
    search_index += [
        {"title": kpi.split(" — ", 1)[0], "type": "KPI", "anchor": kid}
        for kpi, kid in zip(doc.key_kpis, kpi_ids)
    ]
    search_index += [
        {"title": r.consequence, "type": "risk", "anchor": rid}
        for r, rid in zip(doc.top_risks, risk_ids)
    ]

    return page_shell(
        title=f"{md.report_name} — Executive Summary",
        subtitle=f"{md.target_audience or ''} · generated {_fmt_ts(md.generated_at)}",
        toc=toc, kpis=kpis, body_html="\n".join(o), doc_links=doc_links, search_index=search_index,
        owner=md.owner, version=md.version, status=md.status, classification=doc.classification,
    )


# -- DOCX -------------------------------------------------------------------------
def render_docx(doc: ExecutiveDocument, out_path) -> Path:
    """Write ``doc`` to a ``.docx`` at ``out_path`` and return the path."""
    out_path = Path(out_path)
    d = _Docx()
    md = doc.metadata

    d.heading(0, f"{md.report_name} — Executive Summary")
    d.para([d._run(f"{md.target_audience or ''} · generated {_fmt_ts(md.generated_at)}", italic=True)])

    def _bullets_or_none(items: list[str], empty: str) -> None:
        if items:
            for item in items:
                d.bullet(item)
        else:
            d.para([d._run(empty, italic=True)])

    d.heading(1, _SECTION_TITLES[0])
    d.para(doc.purpose)
    d.para(doc.business_value)

    d.heading(1, _SECTION_TITLES[1])
    _bullets_or_none(doc.key_kpis, "No KPIs identified.")

    d.heading(1, _SECTION_TITLES[2])
    if doc.top_risks:
        for r in doc.top_risks:
            d.bullet(_risk_line(r))
    else:
        d.para([d._run("No known risks — the latest audit found nothing to act on.", italic=True)])

    d.heading(1, _SECTION_TITLES[3])
    d.para([d._run("Data sources: ", bold=True),
           d._run(", ".join(doc.data_source_types) if doc.data_source_types else "None detected.")])
    d.para([d._run("Refresh schedule: ", bold=True), d._run(doc.refresh_schedule or "Not documented.")])
    d.para(doc.maintenance_note)

    d.heading(1, _SECTION_TITLES[4])
    ownership_rows = [["Owner", md.owner or "not specified"]]
    if doc.steward:
        ownership_rows.append(["Steward", doc.steward])
    if doc.classification:
        ownership_rows.append(["Classification", doc.classification])
    d.table(["Field", "Value"], ownership_rows)

    d.heading(1, _SECTION_TITLES[5])
    _bullets_or_none(doc.next_steps, "Nothing outstanding.")

    d.save(out_path)
    return out_path
