"""Version-diff engine (C2): compare two ``model.json`` snapshots and produce a
change summary with **impact analysis**, not just a flat list of deltas.

Two public surfaces:

* :func:`compute_model_diff` — the structured delta. Returns a dict that keeps
  the original back-compatible keys (``added_tables``/``changed_measures``/…)
  the enrichment round-trip and CLI already depend on, and adds broader coverage
  (RLS roles, pages, modified relationships, calculation items, KPIs, refresh
  policies, hierarchies, perspectives, cultures) plus a classified ``entries``
  list where every change carries a severity and a plain-language impact note.
* :func:`generate_change_log_markdown` — renders that delta as a reviewer-ready
  change log grouped by severity, safe to embed via the docs' mini-markdown
  renderer and rich enough to stand alone from ``pbicompass diff``.

Pure functions over plain dicts (``SemanticModel.to_dict()`` output) — no LLM,
no model objects required, so it works on any two saved snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Severity vocabulary, most to least serious. "Critical" is reserved for changes
# that can silently break or falsify a live report (a removed object a visual
# still binds to, a security-filter change); "Info" for additive metadata.
SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Info"]
_SEV_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}


@dataclass
class ChangeEntry:
    category: str          # "Measure", "Relationship", "RLS role", ...
    name: str              # the object the change is about
    kind: str              # "added" | "removed" | "modified"
    severity: str          # one of SEVERITY_ORDER
    detail: str            # what changed
    impact: str = ""       # downstream consequence, if any

    def to_dict(self) -> dict:
        return {"category": self.category, "name": self.name, "kind": self.kind,
                "severity": self.severity, "detail": self.detail, "impact": self.impact}


# --- helpers ----------------------------------------------------------------
def _measures(model: dict) -> dict[str, dict]:
    out = {}
    for t in model.get("tables", []):
        for m in t.get("measures", []):
            out[m["name"]] = {**m, "_table": t.get("name", "")}
    return out


def _columns(table: dict) -> dict[str, dict]:
    return {c["name"]: c for c in table.get("columns", [])}


def _rel_key(r: dict) -> str:
    return (f"{r.get('from_table')}[{r.get('from_column')}] -> "
            f"{r.get('to_table')}[{r.get('to_column')}]")


def _roles(model: dict) -> dict[str, dict]:
    return {r["name"]: r for r in model.get("roles", [])}


def _role_filters(role: dict) -> dict[str, str]:
    return {tp.get("table", ""): tp.get("filter_expression", "")
            for tp in role.get("table_permissions", [])}


def _build_usage_index(model: dict) -> dict[str, list[str]]:
    """Map a lowercased object name (measure or column) to the list of report
    pages whose visuals reference it. Basis for the impact analysis: if a
    removed/changed object appears here, the change touches a live visual."""
    usage: dict[str, set[str]] = {}
    for p in model.get("pages", []):
        page = p.get("display_name") or p.get("id") or "?"
        for v in p.get("visuals", []):
            for f in v.get("fields", []) or []:
                # A field ref is "Table.Field" / "Table[Field]"; index the bare
                # field token so a measure or column name matches regardless of
                # which qualifier form the layout used.
                token = f.replace("[", ".").replace("]", "").split(".")[-1].strip().lower()
                if token:
                    usage.setdefault(token, set()).add(page)
    return {k: sorted(v) for k, v in usage.items()}


def _impact(name: str, usage: dict[str, list[str]]) -> tuple[str, bool]:
    pages = usage.get(name.strip().lower(), [])
    if not pages:
        return "", False
    shown = ", ".join(pages[:4]) + (f" +{len(pages) - 4} more" if len(pages) > 4 else "")
    noun = "page" if len(pages) == 1 else "pages"
    return f"Referenced by visuals on {len(pages)} {noun}: {shown}.", True


# --- the diff ---------------------------------------------------------------
def compute_model_diff(old: dict, new: dict) -> dict:
    """Structural + semantic delta between two ``model.json`` dicts.

    Keeps the original keys (``added_tables``, ``removed_tables``,
    ``changed_tables``, ``added_measures``, ``removed_measures``,
    ``changed_measures``, ``added_relationships``, ``removed_relationships``) and
    adds ``changed_relationships``, role/page/feature deltas, a classified
    ``entries`` list, and a ``summary`` count map."""
    diff: dict[str, Any] = {
        "added_tables": [], "removed_tables": [], "changed_tables": {},
        "added_measures": [], "removed_measures": [], "changed_measures": {},
        "added_relationships": [], "removed_relationships": [], "changed_relationships": [],
        "added_roles": [], "removed_roles": [], "changed_roles": {},
        "added_pages": [], "removed_pages": [],
    }
    entries: list[ChangeEntry] = []
    new_usage = _build_usage_index(new)
    old_usage = _build_usage_index(old)

    old_tables = {t["name"]: t for t in old.get("tables", [])}
    new_tables = {t["name"]: t for t in new.get("tables", [])}

    # --- tables + columns ---
    for name, new_t in new_tables.items():
        if name not in old_tables:
            diff["added_tables"].append(name)
            entries.append(ChangeEntry("Table", name, "added", "Info",
                                       "New table added to the model."))
            continue
        old_c, new_c = _columns(old_tables[name]), _columns(new_t)
        added_c = [c for c in new_c if c not in old_c]
        removed_c = [c for c in old_c if c not in new_c]
        changed_c = [
            cn for cn, ncol in new_c.items()
            if cn in old_c and (
                old_c[cn].get("expression") != ncol.get("expression")
                or old_c[cn].get("is_calculated") != ncol.get("is_calculated")
                or old_c[cn].get("data_type") != ncol.get("data_type"))
        ]
        if added_c or removed_c or changed_c:
            diff["changed_tables"][name] = {"added_columns": added_c,
                                            "removed_columns": removed_c,
                                            "changed_columns": changed_c}
        for cn in removed_c:
            note, used = _impact(cn, old_usage)
            entries.append(ChangeEntry("Column", f"{name}[{cn}]", "removed",
                                       "Critical" if used else "Medium",
                                       "Column removed.", note))
        for cn in changed_c:
            note, used = _impact(cn, new_usage)
            entries.append(ChangeEntry("Column", f"{name}[{cn}]", "modified",
                                       "High" if used else "Low",
                                       "Column type or calculation changed.", note))
        for cn in added_c:
            entries.append(ChangeEntry("Column", f"{name}[{cn}]", "added", "Info",
                                       "New column added."))

    for name in old_tables:
        if name not in new_tables:
            diff["removed_tables"].append(name)
            entries.append(ChangeEntry("Table", name, "removed", "High",
                                       "Table removed from the model.",
                                       "Any visual, measure, or relationship bound to it will break."))

    # --- measures ---
    old_m, new_m = _measures(old), _measures(new)
    for name, nm in new_m.items():
        if name not in old_m:
            diff["added_measures"].append(name)
            entries.append(ChangeEntry("Measure", name, "added", "Info",
                                       "New measure added."))
            continue
        om = old_m[name]
        if om.get("expression") != nm.get("expression"):
            diff["changed_measures"][name] = {"old_expression": om.get("expression"),
                                              "new_expression": nm.get("expression")}
            note, used = _impact(name, new_usage)
            entries.append(ChangeEntry(
                "Measure", name, "modified", "High" if used else "Medium",
                "DAX logic changed — results may differ.", note))
        elif om.get("format_string") != nm.get("format_string"):
            entries.append(ChangeEntry("Measure", name, "modified", "Low",
                                       "Display format changed."))
    for name in old_m:
        if name not in new_m:
            diff["removed_measures"].append(name)
            note, used = _impact(name, old_usage)
            entries.append(ChangeEntry("Measure", name, "removed",
                                       "Critical" if used else "Medium",
                                       "Measure removed.",
                                       note or "No visual referenced it."))

    # --- relationships (add / remove / modified props) ---
    old_rels = {_rel_key(r): r for r in old.get("relationships", [])}
    new_rels = {_rel_key(r): r for r in new.get("relationships", [])}
    diff["added_relationships"] = sorted(set(new_rels) - set(old_rels))
    diff["removed_relationships"] = sorted(set(old_rels) - set(new_rels))
    for k in diff["added_relationships"]:
        entries.append(ChangeEntry("Relationship", k, "added", "Medium",
                                   "New relationship — changes how filters propagate."))
    for k in diff["removed_relationships"]:
        entries.append(ChangeEntry("Relationship", k, "removed", "High",
                                   "Relationship removed — tables it joined no longer filter each other."))
    for k in set(old_rels) & set(new_rels):
        o, n = old_rels[k], new_rels[k]
        changed = [p for p in ("from_cardinality", "to_cardinality", "cross_filter", "is_active")
                   if o.get(p) != n.get(p)]
        if changed:
            diff["changed_relationships"].append(k)
            entries.append(ChangeEntry(
                "Relationship", k, "modified", "High",
                "Changed: " + ", ".join(changed) + ".",
                "Cardinality/cross-filter/active changes can silently alter every number that crosses this join."))

    # --- RLS roles (security-sensitive) ---
    old_roles, new_roles = _roles(old), _roles(new)
    for name in new_roles:
        if name not in old_roles:
            diff["added_roles"].append(name)
            entries.append(ChangeEntry("RLS role", name, "added", "High",
                                       "New row-level-security role — changes who sees which rows."))
    for name in old_roles:
        if name not in new_roles:
            diff["removed_roles"].append(name)
            entries.append(ChangeEntry("RLS role", name, "removed", "High",
                                       "RLS role removed — users under it may now see more data."))
    for name in set(old_roles) & set(new_roles):
        of, nf = _role_filters(old_roles[name]), _role_filters(new_roles[name])
        touched = sorted({t for t in set(of) | set(nf) if of.get(t) != nf.get(t)})
        if touched:
            diff["changed_roles"][name] = touched
            entries.append(ChangeEntry(
                "RLS role", name, "modified", "High",
                "Row filter changed on: " + ", ".join(touched) + ".",
                "Security-sensitive — re-validate who can see what."))

    # --- pages ---
    old_pages = {p.get("display_name") or p.get("id") for p in old.get("pages", [])}
    new_pages = {p.get("display_name") or p.get("id") for p in new.get("pages", [])}
    diff["added_pages"] = sorted(x for x in new_pages - old_pages if x)
    diff["removed_pages"] = sorted(x for x in old_pages - new_pages if x)
    for p in diff["added_pages"]:
        entries.append(ChangeEntry("Page", p, "added", "Info", "New report page."))
    for p in diff["removed_pages"]:
        entries.append(ChangeEntry("Page", p, "removed", "Medium",
                                   "Report page removed — bookmarks or drill-throughs to it will break."))

    # --- model-feature deltas (calc items, KPIs, refresh, hierarchies, ...) ---
    _diff_feature(entries, old_tables, new_tables)
    _diff_model_level(entries, old, new)

    entries.sort(key=lambda e: (_SEV_RANK.get(e.severity, 99), e.category, e.name))
    diff["entries"] = [e.to_dict() for e in entries]
    summary = {s: 0 for s in SEVERITY_ORDER}
    for e in entries:
        summary[e.severity] += 1
    diff["summary"] = summary
    return diff


def _diff_feature(entries: list[ChangeEntry], old_tables: dict, new_tables: dict) -> None:
    """Table-scoped feature deltas: calc items, KPIs, refresh policy, hierarchies."""
    for name in set(old_tables) & set(new_tables):
        ot, nt = old_tables[name], new_tables[name]
        # calculation items
        oi = {c["name"]: c.get("expression") for c in ot.get("calculation_items", [])}
        ni = {c["name"]: c.get("expression") for c in nt.get("calculation_items", [])}
        for cn in set(ni) - set(oi):
            entries.append(ChangeEntry("Calculation item", f"{name}[{cn}]", "added", "Low", "Added."))
        for cn in set(oi) - set(ni):
            entries.append(ChangeEntry("Calculation item", f"{name}[{cn}]", "removed", "Medium", "Removed."))
        for cn in set(oi) & set(ni):
            if oi[cn] != ni[cn]:
                entries.append(ChangeEntry("Calculation item", f"{name}[{cn}]", "modified", "Medium",
                                           "DAX changed."))
        # hierarchies
        oh = {h["name"] for h in ot.get("hierarchies", [])}
        nh = {h["name"] for h in nt.get("hierarchies", [])}
        for hn in nh - oh:
            entries.append(ChangeEntry("Hierarchy", f"{name}[{hn}]", "added", "Info", "Added."))
        for hn in oh - nh:
            entries.append(ChangeEntry("Hierarchy", f"{name}[{hn}]", "removed", "Low", "Removed."))
        # refresh policy
        orp, nrp = ot.get("refresh_policy"), nt.get("refresh_policy")
        if bool(orp) != bool(nrp):
            entries.append(ChangeEntry("Refresh policy", name,
                                       "added" if nrp else "removed",
                                       "Medium", "Incremental-refresh policy "
                                       + ("added." if nrp else "removed.")))
        elif orp and nrp and orp != nrp:
            entries.append(ChangeEntry("Refresh policy", name, "modified", "Medium",
                                       "Incremental-refresh window changed."))
        # KPIs (per measure)
        om = {m["name"]: m.get("kpi") for m in ot.get("measures", [])}
        nm = {m["name"]: m.get("kpi") for m in nt.get("measures", [])}
        for mn in set(om) & set(nm):
            if bool(om[mn]) != bool(nm[mn]):
                entries.append(ChangeEntry("Measure KPI", mn, "added" if nm[mn] else "removed",
                                           "Low", "KPI target " + ("added." if nm[mn] else "removed.")))
            elif om[mn] and nm[mn] and om[mn] != nm[mn]:
                entries.append(ChangeEntry("Measure KPI", mn, "modified", "Low", "KPI target changed."))


def _diff_model_level(entries: list[ChangeEntry], old: dict, new: dict) -> None:
    """Model-level feature deltas: perspectives, translation cultures."""
    op = {p["name"] for p in old.get("perspectives", [])}
    np_ = {p["name"] for p in new.get("perspectives", [])}
    for x in np_ - op:
        entries.append(ChangeEntry("Perspective", x, "added", "Info", "Added."))
    for x in op - np_:
        entries.append(ChangeEntry("Perspective", x, "removed", "Low", "Removed."))
    oc = {c["name"] for c in old.get("cultures", [])}
    nc = {c["name"] for c in new.get("cultures", [])}
    for x in nc - oc:
        entries.append(ChangeEntry("Translation", x, "added", "Info", "New language added."))
    for x in oc - nc:
        entries.append(ChangeEntry("Translation", x, "removed", "Low", "Language removed."))


# --- markdown ----------------------------------------------------------------
_NO_CHANGES = "No structural or logic changes detected since the last documentation run."


def generate_change_log_markdown(diff: dict) -> str:
    """Render a change log grouped by severity, with impact notes. Uses bold
    section labels + bullet lists (no headings), so it renders correctly both
    standalone (``pbicompass diff``) and embedded in the technical/audit docs."""
    entries = diff.get("entries")
    if entries is None:  # a diff dict from a caller that predates entries
        entries = []
    if not entries:
        return _NO_CHANGES

    summary = diff.get("summary", {})
    counts = [f"{summary[s]} {s.lower()}" for s in SEVERITY_ORDER if summary.get(s)]
    parts = [f"**{len(entries)} change(s) since the last version** — " + ", ".join(counts) + "."]

    for sev in SEVERITY_ORDER:
        group = [e for e in entries if e["severity"] == sev]
        if not group:
            continue
        lines = [f"**{sev}**"]
        for e in group:
            line = f"- **{e['category']}** `{e['name']}` — {e['kind']}: {e['detail']}"
            if e.get("impact"):
                line += f" _Impact: {e['impact']}_"
            lines.append(line)
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


# --- standalone HTML ---------------------------------------------------------
_SEV_COLOR = {"Critical": "#b3261e", "High": "#c8641b", "Medium": "#8a6d00",
              "Low": "#4a6a2f", "Info": "#5a5a5a"}


def render_change_summary_html(diff: dict, *, title: str = "What Changed") -> str:
    """A self-contained, styled HTML page for ``pbicompass diff --format html``.
    No external assets — safe to open or hand off directly."""
    from html import escape as _e

    entries = diff.get("entries", []) or []
    summary = diff.get("summary", {})
    chips = "".join(
        f'<span class="chip" style="border-color:{_SEV_COLOR[s]};color:{_SEV_COLOR[s]}">'
        f'{summary.get(s, 0)} {s}</span>'
        for s in SEVERITY_ORDER if summary.get(s)
    ) or '<span class="chip">No changes</span>'

    body = []
    for sev in SEVERITY_ORDER:
        group = [e for e in entries if e["severity"] == sev]
        if not group:
            continue
        body.append(f'<h2 style="color:{_SEV_COLOR[sev]}">{sev} ({len(group)})</h2><ul>')
        for e in group:
            impact = (f' <span class="impact">Impact: {_e(e["impact"])}</span>'
                      if e.get("impact") else "")
            body.append(
                f'<li><strong>{_e(e["category"])}</strong> '
                f'<code>{_e(e["name"])}</code> — {_e(e["kind"])}: {_e(e["detail"])}{impact}</li>')
        body.append("</ul>")
    if not entries:
        body.append(f"<p>{_e(_NO_CHANGES)}</p>")

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title><style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;
margin:2rem auto;padding:0 1rem;color:#1a1a1a;line-height:1.5}}
h1{{font-size:1.6rem;margin-bottom:.25rem}}
.chip{{display:inline-block;border:1px solid #999;border-radius:999px;padding:.1rem .6rem;
margin:.15rem .3rem .15rem 0;font-size:.8rem;font-weight:600}}
h2{{font-size:1.15rem;margin:1.4rem 0 .4rem;border-bottom:1px solid #eee;padding-bottom:.2rem}}
ul{{padding-left:1.2rem}} li{{margin:.35rem 0}}
code{{background:#f4f4f4;padding:.05rem .3rem;border-radius:4px;font-size:.9em}}
.impact{{color:#555;font-style:italic;font-size:.9em}}
@media(prefers-color-scheme:dark){{body{{background:#141414;color:#e6e6e6}}
code{{background:#2a2a2a}} h2{{border-color:#333}} .impact{{color:#aaa}}}}
</style></head><body>
<h1>{_e(title)}</h1><div>{chips}</div>
{''.join(body)}
</body></html>"""
