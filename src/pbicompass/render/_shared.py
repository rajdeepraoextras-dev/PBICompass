"""Small rendering primitives shared by every document-type renderer.

Extracted from ``markdown.py``/``html.py``/``docx.py`` (which previously each
defined their own copy) so new renderers (audit, executive, user-guide) reuse
the same building blocks instead of duplicating them.
"""

from __future__ import annotations

import re
from html import escape as _escape


# Reader-facing names for the health-score components computed by
# ``agents.audit_rules.compute_health_score`` — shared by every renderer so
# the same component is never labelled two different ways.
HEALTH_COMPONENT_LABELS = {
    "modeling": "Model Design",
    "dax": "DAX Quality",
    "governance": "Governance & Security",
    "performance": "Performance",
    "unused_assets": "Maintainability",
}


def non_data_note(count: int) -> str:
    """The standard line for non-data page objects (buttons, images, shapes,
    text labels) — layout elements, not documented individually."""
    return (f"{count} non-data object(s) on this page — buttons, images, shapes, "
            "and text labels used for layout and navigation.")


def is_local_path(path_str: str) -> bool:
    return bool(re.search(r"^[A-Za-z]:[\\/]", path_str) or "Users/" in path_str or "Users\\" in path_str)


def md_todo(text: str) -> str:
    """Markdown ``To complete`` placeholder blockquote."""
    return f"> **✎ To complete:** {text}\n"


def md_table(headers: list[str], rows: list[list[str]], empty: str = "_None._") -> str:
    """Markdown table (or an ``empty`` fallback line if ``rows`` is empty)."""
    if not rows:
        return empty + "\n"
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |")
    return "\n".join(out) + "\n"


def html_e(v) -> str:
    return _escape("" if v is None else str(v))


def html_todo(text: str) -> str:
    """HTML ``To complete`` placeholder div. Escapes ``text`` itself."""
    return f'<div class="todo"><b>✎ To complete:</b> {html_e(text)}</div>'


def html_table(headers: list[str], rows: list[list[str]], empty: str = "None.") -> str:
    """HTML table. Headers/``empty`` are escaped here; row cells are inserted
    as-is since callers commonly pre-build cell HTML (e.g. ``<span>`` markup)."""
    if not rows:
        return f'<p class="muted">{html_e(empty)}</p>'
    head = "".join(f"<th>{html_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
