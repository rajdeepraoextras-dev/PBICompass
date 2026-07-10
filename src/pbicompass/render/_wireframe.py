"""Page wireframe SVG — a scaled layout of a report page's visuals (3.1).

v5 "Blueprint" (2026-07-10, user-selected from three proposed directions):
each visual is a dashed region outline tinted in its category color with a
solid rounded pill label (icon + title) pinned top-left and the friendly
type in small caps beneath it — read like an annotated design spec laid over
a faint grid "sheet". Replaces the v4 card/ghost-content skin (white cards
with schematic bars/lines/KPI/map glyphs) and the interim window-frame
version. Rendered larger and at real per-visual x/y/width/height positions,
in real-case Poppins (no global text-transform), so titles stay legible and
recognizably Poppins instead of a tiny shouted line.

Same four categories (data/slicer/nav/decorative), same real positions, same
tiny-object / decorative-overflow collapse, and the same
hover-via-CSS-class / I3 link-resolution logic — only the visual language
changed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..schemas.model import Page, Visual

from ..agents.report_facts import friendly_visual_type, visual_label
from ._shared import anchor_slug, html_e

# Non-data layout elements — quieter styling, never linked to a
# data-dictionary row (I3).
_DECORATIVE_TYPES = {"image", "shape", "basicShape", "textbox"}
_NAV_TYPES = {"actionButton", "button", "navBar", "bookmarkNavigator"}
_SLICER_TYPES = {"slicer", "advancedSlicerVisual"}

_INK = "#1f2433"
_MUTED = "#8a93a8"
_FAINT = "#b6bdcf"
_EDGE = "#e7eaf3"
_SURFACE = "#ffffff"

# category -> accent. The blueprint region, its pill label, and the type
# caption all take this one color; the pill's icon is knocked out in white.
_STYLE = {
    "data": "#4f6ef7",
    "slicer": "#f59e0b",
    "nav": "#10b981",
    "decorative": "#8b5cf6",
}

# visualType -> glyph id (feather-style stroke icons, drawn white inside the
# category-colored pill).
_GLYPH_BY_TYPE = {
    "clusteredColumnChart": "bars", "columnChart": "bars",
    "hundredPercentStackedColumnChart": "bars", "stackedColumnChart": "bars",
    "clusteredBarChart": "bars", "barChart": "bars",
    "hundredPercentStackedBarChart": "bars", "stackedBarChart": "bars",
    "lineChart": "line",
    "lineStackedColumnComboChart": "combo", "lineClusteredColumnComboChart": "combo",
    "areaChart": "area", "stackedAreaChart": "area",
    "map": "pin", "filledMap": "pin", "shapeMap": "pin",
    "tableEx": "matrix", "table": "matrix", "pivotTable": "matrix", "matrix": "matrix",
    "card": "card123", "multiRowCard": "card123", "kpi": "card123",
    "decompositionTreeVisual": "tree", "decompositionTree": "tree",
    "slicer": "funnel", "advancedSlicerVisual": "funnel",
    "actionButton": "button", "button": "button", "navBar": "button", "bookmarkNavigator": "button",
    "image": "image", "textbox": "textbox", "shape": "shape", "basicShape": "shape",
}


def _defs(suffix: str) -> str:
    """The glyph ``<symbol>`` defs + the faint blueprint grid pattern,
    namespaced by ``suffix`` — each wireframe is a self-contained SVG
    embedded independently (one per page), so without a per-instance suffix a
    document with more than one page would define the same ``id`` twice. All
    icons are stroke-style paths (``fill="none"``, no local ``stroke``), so
    color is set by the referencing ``<use>``."""
    return f"""<defs>
<pattern id="wf-grid-{suffix}" width="24" height="24" patternUnits="userSpaceOnUse">
  <rect width="24" height="24" fill="#f8fafc"/><path d="M24 0H0V24" fill="none" stroke="#e7ecf5" stroke-width="1"/>
</pattern>
<symbol id="wf-i-bars-{suffix}" viewBox="0 0 24 24"><path d="M3 21h18M6 21V10M11 21V4M16 21v-9M21 21V7" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
<symbol id="wf-i-line-{suffix}" viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-9" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
<symbol id="wf-i-combo-{suffix}" viewBox="0 0 24 24"><path d="M3 21h4v-7H3zM10 21h4v-11h-4zM17 21h4v-5h-4M4 11l5-4 4 3 6-6" fill="none" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
<symbol id="wf-i-area-{suffix}" viewBox="0 0 24 24"><path d="M3 20h18L16 8l-4 5-3-3z" fill="none" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
<symbol id="wf-i-pin-{suffix}" viewBox="0 0 24 24"><path d="M12 21s-7-6.2-7-11a7 7 0 1114 0c0 4.8-7 11-7 11z" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="10" r="2.5" fill="none" stroke-width="2"/></symbol>
<symbol id="wf-i-matrix-{suffix}" viewBox="0 0 24 24"><path d="M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z" fill="none" stroke-width="1.7" stroke-linejoin="round"/></symbol>
<symbol id="wf-i-card123-{suffix}" viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="2" fill="none" stroke-width="2"/><path d="M2 10h20" fill="none" stroke-width="2"/></symbol>
<symbol id="wf-i-tree-{suffix}" viewBox="0 0 24 24"><circle cx="12" cy="5" r="2" fill="none" stroke-width="2"/><circle cx="5" cy="19" r="2" fill="none" stroke-width="2"/><circle cx="19" cy="19" r="2" fill="none" stroke-width="2"/><path d="M12 7l-5.5 10M12 7l5.5 10" fill="none" stroke-width="1.7" stroke-linecap="round"/></symbol>
<symbol id="wf-i-funnel-{suffix}" viewBox="0 0 24 24"><path d="M22 3H2l8 9.5V19l4 2v-8.5z" fill="none" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
<symbol id="wf-i-button-{suffix}" viewBox="0 0 24 24"><rect x="3" y="8" width="18" height="8" rx="4" fill="none" stroke-width="1.7"/></symbol>
<symbol id="wf-i-image-{suffix}" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke-width="1.7"/><circle cx="8.5" cy="8.5" r="1.5" fill="none" stroke-width="1.7"/><path d="M21 15l-5-5L5 21" fill="none" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
<symbol id="wf-i-textbox-{suffix}" viewBox="0 0 24 24"><path d="M4 7V4h16v3M9 20h6M12 4v16" fill="none" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
<symbol id="wf-i-shape-{suffix}" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="3" fill="none" stroke-width="1.7"/></symbol>
</defs>"""


# Rounded-pill legend chips — one shared style, reused with the lineage graph.
_LEGEND = (
    '<div class="legend legend--upper wf-legend">'
    '<span class="wf-chip"><i class="wf-chip-dot wf-chip-dot--data"></i>Data visual</span>'
    '<span class="wf-chip"><i class="wf-chip-dot wf-chip-dot--slicer"></i>Slicer</span>'
    '<span class="wf-chip"><i class="wf-chip-dot wf-chip-dot--nav"></i>Navigation</span>'
    '<span class="wf-chip"><i class="wf-chip-dot wf-chip-dot--deco"></i>Decorative</span>'
    "</div>"
)


def _category(v: "Visual") -> str:
    if v.is_slicer or v.type in _SLICER_TYPES:
        return "slicer"
    if v.type in _NAV_TYPES:
        return "nav"
    if v.type in _DECORATIVE_TYPES:
        return "decorative"
    return "data"


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: max(1, limit - 1)].rstrip() + "…"


def render_wireframe(
    page: "Page", *,
    measure_names: frozenset[str] = frozenset(),
    field_param_tables: frozenset[str] = frozenset(),
    visual_anchor_map: dict[tuple, str] | None = None,
) -> str:
    """Render a scaled SVG "sheet" of the page's visuals, if layout
    coordinates exist (pbix-parsed models don't carry them — skip gracefully
    rather than render an empty diagram).

    ``measure_names``/``field_param_tables``, when given, let a data visual's
    link target be computed with the exact same ``report_facts.visual_label()``
    a caller used to build the matching table row — otherwise an untitled
    visual bound only to fields would get a *different* label here than in the
    table, producing a dead link (I3).

    ``visual_anchor_map``, when given (``report_pages()`` always supplies one),
    maps a visual's ``(title, friendly_type, frozenset(metrics),
    frozenset(dims))`` group key to its *resolved* table-row anchor slug — the
    id it actually gets after ``report_pages()`` groups 2+ identical visuals
    into one row and after ``dedupe_ids`` resolves any remaining slug
    collision. Without the map, a group's link would still point at the raw,
    un-relabeled/un-deduped slug — a guaranteed dead link for any page with
    two or more visuals identical in title/type/metrics/dims (I3). Callers
    that render standalone (tests, or any future caller with no matching
    table) fall back to the raw slug, same as before this map existed."""
    valid_visuals = [
        v for v in page.visuals
        if v.x is not None and v.y is not None and v.width is not None and v.height is not None
    ]
    if not valid_visuals:
        return ""

    page_w = page.width or 1280
    page_h = page.height or 720
    if page_w <= 0 or page_h <= 0:
        return ""
    page_area = page_w * page_h

    # Larger than the old 480 so real-case Poppins stays legible. The viewBox
    # is fitted to the union of the sheet and every visual, so a visual
    # dragged partly off the page can't be clipped by a hardcoded width (same
    # robustness fix the lineage rebuild got).
    base_w = 760
    margin = 16
    sheet_w = base_w - 2 * margin
    scale = sheet_w / page_w
    sheet_h = page_h * scale
    ox = oy = margin  # sheet origin

    right = ox + sheet_w
    bottom = oy + sheet_h
    for v in valid_visuals:
        right = max(right, ox + (v.x + v.width) * scale)
        bottom = max(bottom, oy + (v.y + v.height) * scale)
    target_w = right + margin
    target_h = bottom + margin

    page_title_slug = anchor_slug(page.display_name)
    # Same anchor formula html.py's Report Pages section and user_guide.py's
    # per-page card use — this SVG is computed once and embedded verbatim in
    # both documents, so it can't carry a document-specific deduped id.
    page_anchor = f"page-{page_title_slug}"
    glyph_suffix = anchor_slug(page.id)
    title_id = f"wireframe-title-{glyph_suffix}"

    svg = [
        f'<svg viewBox="0 0 {target_w:.0f} {target_h:.0f}" width="100%" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-labelledby="{title_id}">\n<style>text {{ font-family: "Poppins", sans-serif !important; }}</style>'
    ]
    svg.append(f'<title id="{title_id}">Wireframe layout for page {html_e(page.display_name)}</title>')
    svg.append(_defs(glyph_suffix))
    # The "sheet": the page area as a faint grid rectangle. Explicit light hex
    # (not shell CSS variables) so it stays light in dark mode, same rule as
    # the interactive model diagram.
    svg.append(
        f'<rect x="{ox}" y="{oy}" width="{sheet_w:.0f}" height="{sheet_h:.0f}" rx="12" '
        f'fill="url(#wf-grid-{glyph_suffix})" stroke="{_EDGE}" stroke-width="1"/>'
    )

    sorted_visuals = sorted(valid_visuals, key=lambda v: v.z or 0)

    decorative_shown = 0
    decorative_total = sum(1 for v in sorted_visuals if _category(v) == "decorative")
    decorative_overflow = 0

    for v in sorted_visuals:
        vx, vy = ox + v.x * scale, oy + v.y * scale
        vw, vh = v.width * scale, v.height * scale
        if vw <= 0 or vh <= 0:
            continue

        category = _category(v)

        # Tiny-object handling (J.C item 6): anything under 0.5% of the page
        # area renders as an unlabeled, unlinked dot — a full region would be
        # unreadable and misleading at that size regardless of type.
        if (v.width * v.height) < 0.005 * page_area:
            cx, cy = vx + vw / 2, vy + vh / 2
            svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="1.8" fill="{_FAINT}"/>')
            continue

        # Collapse decorative clutter (J.C item 6): once a page has 3+
        # decorative objects, show the first two individually and fold the
        # rest into one footer note instead of a wall of near-identical boxes.
        if category == "decorative" and decorative_total >= 3:
            decorative_shown += 1
            if decorative_shown > 2:
                decorative_overflow += 1
                continue

        accent = _STYLE[category]
        friendly = friendly_visual_type(v.type)
        label = v.title or friendly
        glyph = _GLYPH_BY_TYPE.get(v.type)

        # ---- the blueprint region ----
        card = [
            f'<rect x="{vx:.1f}" y="{vy:.1f}" width="{vw:.1f}" height="{vh:.1f}" rx="8" '
            f'class="wf-card-bg cat-{category}" fill="{accent}" fill-opacity="0.05" '
            f'stroke="{accent}" stroke-opacity="0.55" stroke-width="1.4" stroke-dasharray="5 4"/>'
        ]

        pad = 8
        big = vw >= 84 and vh >= 44
        compact = not big and vw >= 52 and vh >= 26

        if big:
            # A solid category pill — icon knocked out white + the visual's
            # own title (real case) — plus the friendly type in small caps
            # beneath it when a real title fills the pill.
            chip_h, icon = 22, 14
            has_icon = bool(glyph)
            text_room = vw - 2 * pad - (icon + 13 if has_icon else 12) - 8
            max_chars = max(2, int(text_room / 6.6)) if text_room > 0 else 0
            name = v.title or friendly
            name_txt = _truncate(name, max_chars) if max_chars else ""
            chip_w = min(vw - 2 * pad, 12 + (icon + 6 if has_icon else 0) + len(name_txt) * 6.6 + 8)
            cx, cy = vx + pad, vy + pad
            card.append(f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{chip_w:.1f}" height="{chip_h}" '
                        f'rx="{chip_h // 2}" fill="{accent}"/>')
            tx = cx + 11
            if has_icon:
                card.append(f'<use href="#wf-i-{glyph}-{glyph_suffix}" x="{cx + 8:.1f}" '
                            f'y="{cy + (chip_h - icon) / 2:.1f}" width="{icon}" height="{icon}" '
                            f'fill="none" stroke="#ffffff"/>')
                tx = cx + 8 + icon + 6
            if name_txt:
                card.append(f'<text x="{tx:.1f}" y="{cy + chip_h / 2 + 4:.1f}" font-size="12.5" '
                            f'font-weight="600" fill="#ffffff">{html_e(name_txt)}</text>')
            if v.title and vh >= chip_h + 24:
                card.append(f'<text x="{vx + pad + 2:.1f}" y="{cy + chip_h + 15:.1f}" font-size="9.5" '
                            f'font-weight="600" letter-spacing="0.07em" fill="{accent}" '
                            f'fill-opacity="0.85">{html_e(friendly.upper())}</text>')
        elif compact:
            # Too small for a filled pill: a small accent icon badge and the
            # title beside it in ink (full card width available for the text).
            tx = vx + 6
            if glyph:
                b = 16
                card.append(f'<rect x="{vx + 5:.1f}" y="{vy + 5:.1f}" width="{b}" height="{b}" rx="4" fill="{accent}"/>')
                card.append(f'<use href="#wf-i-{glyph}-{glyph_suffix}" x="{vx + 5 + (b - 10) / 2:.1f}" '
                            f'y="{vy + 5 + (b - 10) / 2:.1f}" width="10" height="10" fill="none" stroke="#ffffff"/>')
                tx = vx + 5 + b + 6
            max_chars = max(2, int((vx + vw - 6 - tx) / 6.3))
            name_txt = _truncate(v.title or friendly, max_chars)
            card.append(f'<text x="{tx:.1f}" y="{vy + 17:.1f}" font-size="11" font-weight="600" '
                        f'fill="{_INK}">{html_e(name_txt)}</text>')
        elif glyph:
            # No room for a label: a small white-on-accent icon badge only.
            b = 16
            card.append(f'<rect x="{vx + 4:.1f}" y="{vy + 4:.1f}" width="{b}" height="{b}" rx="4" fill="{accent}"/>')
            card.append(f'<use href="#wf-i-{glyph}-{glyph_suffix}" x="{vx + 4 + (b - 10) / 2:.1f}" '
                        f'y="{vy + 4 + (b - 10) / 2:.1f}" width="10" height="10" fill="none" stroke="#ffffff"/>')

        group = [f'<g class="wf-node cat-{category}">'] + card + ["</g>"]

        if category == "data":
            from ..agents.report_facts import is_field_selector

            metrics, dims = [], []
            for f in v.fields:
                if is_field_selector(f, field_param_tables):
                    continue
                leaf = f.split(".")[-1]
                (metrics if leaf in measure_names else dims).append(leaf)
            # Same label a caller's table row was built with (report_facts's
            # visual_label()) — not the simpler ``label`` used for the
            # on-canvas text above — so the link always resolves (I3).
            link_label = visual_label(v.title, v.type, metrics, dims)
            field_leaves = ", ".join(
                f.split(".")[-1] for f in v.fields if not is_field_selector(f, field_param_tables)
            ) or "no fields bound"
            tooltip = f"{label} — {friendly} ({field_leaves})"
            # report_pages()'s own group key for this exact visual — look up
            # its *resolved* (relabeled/deduped) row anchor; only a caller
            # with no map (no matching table) falls back to the raw slug.
            visual_key = (v.title, friendly, frozenset(metrics), frozenset(dims))
            visual_slug = (visual_anchor_map or {}).get(visual_key) or anchor_slug(link_label)
            svg.append(f'<a href="#visual-{page_title_slug}-{visual_slug}">')
            svg.append(f"<title>{html_e(tooltip)}</title>")
            svg.extend(group)
            svg.append("</a>")
        elif category == "slicer":
            svg.append(f'<a href="#{page_anchor}">')
            svg.append(f"<title>{html_e(label)} — filters this page</title>")
            svg.extend(group)
            svg.append("</a>")
        else:
            # Buttons/nav and decorative shapes/images/text: not linked —
            # there's no per-object row anywhere in the document for them
            # to resolve to (I3).
            svg.extend(group)

    svg.append("</svg>")

    footer = ""
    if decorative_overflow:
        footer = f'<p class="wf-footer">+{decorative_overflow} decorative shape(s)</p>'

    return f'<div class="diagram">{"".join(svg)}{footer}{_LEGEND}</div>'
