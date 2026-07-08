from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..schemas.model import SemanticModel

from ._shared import anchor_slug, html_e
from ..agents.usage import measure_usage
from ..agents.report_facts import find_referenced_tables, data_source_summaries

# v4 design (2026-07-08) — "similar design" to the page wireframe (same
# session, user-supplied wireframe-v4-light.html, Option A): a white card
# per node with a colored *left* accent bar (top bar is the wireframe's own
# convention; left distinguishes a lineage node from a wireframe visual at
# a glance) instead of a plain filled rect, a tinted icon badge per layer,
# and the same hover-lift .wf-node treatment. Lineage has no data/slicer/
# nav/decorative categories — it has four *layers* — so the same four v4
# accent colors are reassigned: source=purple, table=blue, measure=amber,
# page=green.
_INK = "#1f2433"
_MUTED = "#8a93a8"
_EDGE = "#e7eaf3"
_SURFACE = "#ffffff"
_LAYER_STYLE = [
    ("source", "#8b5cf6", "#f3eefe", "Source"),
    ("table", "#4f6ef7", "#eef1fe", "Table"),
    ("measure", "#f59e0b", "#fef4e4", "Measure"),
    ("page", "#10b981", "#e7f8f1", "Page"),
]
_LAYER_ICON = {
    "source": '<ellipse cx="12" cy="5" rx="8" ry="3" fill="none" stroke-width="1.8"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" fill="none" stroke-width="1.8"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke-width="1.8"/><path d="M3 10h18M9 10v10" fill="none" stroke-width="1.8"/>',
    "measure": '<path d="M4 19V5M4 19h16M8 15l3-4 3 3 4-6" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "page": '<rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke-width="1.8"/><path d="M3 9h18" fill="none" stroke-width="1.8"/>',
}

_LEGEND = (
    '<div class="legend legend--upper wf-legend">'
    '<span class="wf-chip"><i class="wf-chip-dot wf-chip-dot--source"></i>Source</span>'
    '<span class="wf-chip"><i class="wf-chip-dot wf-chip-dot--table"></i>Table</span>'
    '<span class="wf-chip"><i class="wf-chip-dot wf-chip-dot--measure"></i>Measure</span>'
    '<span class="wf-chip"><i class="wf-chip-dot wf-chip-dot--page"></i>Page</span>'
    "</div>"
)


def get_source_label(ds) -> str:
    target = ds.server or ds.detail or ""
    if ds.database:
        target = f"{target}/{ds.database}" if target else ds.database
    return f"{ds.type or 'Source'}: {target}".rstrip(": ")

def build_lineage_data(model: SemanticModel) -> tuple[list[dict[str, str]], str]:
    """Build all lineage edges and render the layered left-to-right SVG lineage graph."""
    raw_edges: list[dict[str, str]] = []
    
    # 1. Source to Table
    sources_map = {get_source_label(ds): ds for ds in model.data_sources}
    for t in model.tables:
        for p in t.partitions:
            if p.expression:
                for src_label, ds in sources_map.items():
                    if (
                        (ds.server and ds.server in p.expression) or
                        (ds.detail and ds.detail in p.expression) or
                        (ds.database and ds.database in p.expression) or
                        (ds.type and ds.type in p.expression)
                    ):
                        raw_edges.append({"from": src_label, "to": t.name, "type": "Source to Table"})
    
    # 2. Table to Measure
    measures = model.all_measures()
    for m in measures:
        if m.table:
            raw_edges.append({"from": m.table, "to": m.name, "type": "Table to Measure"})
        ref_tables = find_referenced_tables(m.expression)
        for ref_t in ref_tables:
            # check if ref_t exists in the model tables
            if any(tbl.name == ref_t for tbl in model.tables) and ref_t != m.table:
                raw_edges.append({"from": ref_t, "to": m.name, "type": "Table to Measure"})
                
    # 3. Measure to Page
    usage = measure_usage(model)
    for m_name, pages in usage.items():
        for page_name in pages:
            raw_edges.append({"from": m_name, "to": page_name, "type": "Measure to Page"})

    # De-duplicate edges
    seen_edges = set()
    edges: list[dict[str, str]] = []
    for edge in raw_edges:
        edge_key = (edge["from"], edge["to"], edge["type"])
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append(edge)
            
    # Compute layers
    layer_0_all = sorted(list({e["from"] for e in edges if e["type"] == "Source to Table"}))
    layer_1_all = sorted(list(
        {e["to"] for e in edges if e["type"] == "Source to Table"} |
        {e["from"] for e in edges if e["type"] == "Table to Measure"}
    ))
    layer_2_all = sorted(list(
        {e["to"] for e in edges if e["type"] == "Table to Measure"} |
        {e["from"] for e in edges if e["type"] == "Measure to Page"}
    ))
    layer_3_all = sorted(list({e["to"] for e in edges if e["type"] == "Measure to Page"}))
    
    # Cap nodes in each layer at 8
    max_cap = 8
    
    def cap_layer(layer_nodes: list[str], layer_index: int) -> tuple[list[str], dict[str, str], int]:
        # Count connections for sorting
        conn_counts = {}
        for n in layer_nodes:
            count = 0
            for e in edges:
                if e["from"] == n or e["to"] == n:
                    count += 1
            conn_counts[n] = count
            
        sorted_nodes = sorted(layer_nodes, key=lambda n: conn_counts.get(n, 0), reverse=True)
        if len(sorted_nodes) <= max_cap:
            return sorted_nodes, {}, 0
            
        keep_count = max_cap - 1
        keep_nodes = sorted_nodes[:keep_count]
        overflow_nodes = sorted_nodes[keep_count:]
        
        overflow_label = f"+{len(overflow_nodes)} more " + ["sources", "tables", "measures", "pages"][layer_index]
        mapping = {n: overflow_label for n in overflow_nodes}
        return keep_nodes + [overflow_label], mapping, len(overflow_nodes)

    l0, map0, count0 = cap_layer(layer_0_all, 0)
    l1, map1, count1 = cap_layer(layer_1_all, 1)
    l2, map2, count2 = cap_layer(layer_2_all, 2)
    l3, map3, count3 = cap_layer(layer_3_all, 3)
    
    # Map edges to capped labels
    mapped_raw_edges = []
    for e in edges:
        f = e["from"]
        t = e["to"]
        
        if e["type"] == "Source to Table":
            f = map0.get(f, f)
            t = map1.get(t, t)
        elif e["type"] == "Table to Measure":
            f = map1.get(f, f)
            t = map2.get(t, t)
        elif e["type"] == "Measure to Page":
            f = map2.get(f, f)
            t = map3.get(t, t)
            
        mapped_raw_edges.append({"from": f, "to": t, "type": e["type"]})
        
    # Dedup mapped edges
    seen_mapped = set()
    mapped_edges: list[dict[str, str]] = []
    for me in mapped_raw_edges:
        key = (me["from"], me["to"], me["type"])
        if key not in seen_mapped:
            seen_mapped.add(key)
            mapped_edges.append(me)

    # Layout geometry
    layers = [l0, l1, l2, l3]
    max_len = max(len(lay) for lay in layers) if layers else 0
    H = max(400, max_len * 50 + 40)
    W = 960
    
    col_x = [60, 320, 580, 840]
    box_w = 190
    box_h = 38

    node_coords: dict[str, tuple[float, float]] = {}

    svg = [
        f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-labelledby="lineage-diagram-title">\n<style>text {{ font-family: "Poppins", sans-serif !important; text-transform: uppercase; }}</style>'
    ]
    svg.append('<title id="lineage-diagram-title">Data lineage graph: sources to pages</title>')
    svg.append(f'''<defs>
<pattern id="wf-dotbg-lineage" width="7" height="7" patternUnits="userSpaceOnUse">
  <rect width="7" height="7" fill="#ffffff"/><circle cx="1" cy="1" r="0.55" fill="#dfe4f0"/>
</pattern>
<symbol id="wf-i-lin-source" viewBox="0 0 24 24">{_LAYER_ICON["source"]}</symbol>
<symbol id="wf-i-lin-table" viewBox="0 0 24 24">{_LAYER_ICON["table"]}</symbol>
<symbol id="wf-i-lin-measure" viewBox="0 0 24 24">{_LAYER_ICON["measure"]}</symbol>
<symbol id="wf-i-lin-page" viewBox="0 0 24 24">{_LAYER_ICON["page"]}</symbol>
</defs>''')
    svg.append(
        f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#wf-dotbg-lineage)" rx="10" stroke="{_EDGE}" stroke-width="1"/>'
    )

    # Pass 1: pure geometry -- compute every node's (x, y) up front, so
    # edges can be drawn *before* (underneath) the node cards in pass 3.
    for col_idx, nodes in enumerate(layers):
        n_count = len(nodes)
        if n_count == 0:
            continue
        y_start = (H - (n_count * box_h + (n_count - 1) * 15)) / 2
        for i, name in enumerate(nodes):
            node_coords[name] = (col_x[col_idx], y_start + i * (box_h + 15))

    # Pass 2: edges, so node cards paint on top of the curves feeding
    # into/out of them.
    for me in mapped_edges:
        p1 = node_coords.get(me["from"])
        p2 = node_coords.get(me["to"])
        if not p1 or not p2:
            continue

        x1 = p1[0] + box_w
        y1 = p1[1] + box_h / 2
        x2 = p2[0]
        y2 = p2[1] + box_h / 2

        dx = (x2 - x1) / 2
        svg.append(
            f'  <path d="M {x1:.1f} {y1:.1f} C {x1 + dx:.1f} {y1:.1f}, {x1 + dx:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}" '
            f'fill="none" stroke="#c7ccdb" stroke-width="1.3" stroke-linecap="round"/>'
        )

    # Pass 3: node cards -- each a v4-style card: white surface, a colored
    # *left* accent bar, a tinted icon badge, title + layer sub-label. (I3:
    # no per-node <a> link yet -- this is a visual redesign, not a new
    # interactivity feature.)
    for col_idx, nodes in enumerate(layers):
        if not nodes:
            continue
        layer_key, accent, soft, layer_label = _LAYER_STYLE[col_idx]

        for name in nodes:
            cx, cy = node_coords[name]
            is_overflow = name.startswith("+")

            display_name = name
            if len(display_name) > 24:
                display_name = display_name[:22] + "…"

            svg.append(f'  <g class="wf-node cat-{layer_key}">')
            svg.append(
                f'    <rect x="{cx:.1f}" y="{cy:.1f}" width="{box_w}" height="{box_h}" rx="8" '
                f'class="wf-card-bg" fill="{_SURFACE}" stroke="{_EDGE}" '
                f'stroke-width="1" stroke-dasharray="{"3,2" if is_overflow else "0"}"/>'
            )
            if not is_overflow:
                svg.append(
                    f'    <rect x="{cx:.1f}" y="{cy + 0.6:.1f}" width="1.6" height="{box_h - 1.2:.1f}" fill="{accent}"/>'
                )
                svg.append(
                    f'    <rect x="{cx + 8:.1f}" y="{cy + 8:.1f}" width="16" height="16" rx="4" fill="{soft}"/>'
                    f'    <use href="#wf-i-lin-{layer_key}" x="{cx + 12:.1f}" y="{cy + 12:.1f}" width="8" height="8" '
                    f'fill="none" stroke="{accent}"/>'
                )
                svg.append(
                    f'    <text x="{cx + 32:.1f}" y="{cy + 16:.1f}" font-size="8.5" font-weight="600" '
                    f'fill="{_INK}">{html_e(display_name)}</text>'
                    f'    <text x="{cx + 32:.1f}" y="{cy + 27:.1f}" font-size="6" letter-spacing="0.16em" '
                    f'fill="{_MUTED}">{html_e(layer_label)}</text>'
                )
            else:
                svg.append(
                    f'    <text x="{cx + box_w / 2:.1f}" y="{cy + box_h / 2 + 3:.1f}" font-size="8" '
                    f'text-anchor="middle" fill="{_MUTED}" font-style="italic">{html_e(display_name)}</text>'
                )
            svg.append(f'  </g>')

    svg.append('</svg>')

    svg_str = f'<div class="diagram">{"".join(svg)}{_LEGEND}</div>'
    return edges, svg_str

def get_tables_fed(ds, model) -> list[str]:
    fed = []
    for t in model.tables:
        for p in t.partitions:
            if p.expression:
                if (
                    (ds.server and ds.server in p.expression) or
                    (ds.detail and ds.detail in p.expression) or
                    (ds.database and ds.database in p.expression) or
                    (ds.type and ds.type in p.expression)
                ):
                    fed.append(t.name)
                    break
    return fed

def get_storage_mode(ds, model) -> str:
    fed_tables = get_tables_fed(ds, model)
    modes = set()
    for t_name in fed_tables:
        t = next((tbl for tbl in model.tables if tbl.name == t_name), None)
        if t:
            for p in t.partitions:
                if p.mode:
                    modes.add(p.mode)
    if not modes:
        return "import"
    return ", ".join(sorted(modes))

def is_local_path(detail: str) -> bool:
    if not detail:
        return False
    if "://" in detail:
        return False
    return (
        detail.startswith("\\\\") or
        (len(detail) > 2 and detail[1] == ":" and detail[2] == "\\") or
        "/" in detail or
        "\\" in detail
    )

def build_data_sources_inventory(model: SemanticModel) -> list[dict]:
    import os
    inventory = []
    for ds in model.data_sources:
        location = ds.detail or ds.server or ""
        
        if is_local_path(location):
            display_location = os.path.basename(location.replace("\\", "/")) or location
            flag = "⚠️ Hardcoded local path"
        else:
            display_location = location
            flag = ""
            
        fed = get_tables_fed(ds, model)
        mode = get_storage_mode(ds, model)
        
        inventory.append({
            "type": ds.type or "Unknown",
            "location": location,
            "display_location": display_location,
            "tables_fed": fed,
            "storage_mode": mode,
            "auth": ds.authentication_status or "not specified",
            "flag": flag
        })
    return inventory
