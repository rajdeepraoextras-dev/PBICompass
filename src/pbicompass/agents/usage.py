"""Report-usage analysis: which measures/columns actually appear on a page.

Originally lived inline in ``orchestrator.py``. Promoted to its own module
because the audit generator's unused-assets check needs the same usage
closure the technical generator's orphaned-measure audit already computes —
sharing one implementation instead of two. Pure functions, no LLM involved.
"""

from __future__ import annotations

import re

from ..schemas.model import SemanticModel


def used_measure_names(model: SemanticModel) -> set[str]:
    """Measure names that appear on a report page — directly or transitively.

    Power BI references a measure as ``HomeTable.MeasureName`` in visuals, so we
    match the trailing segment of each field token against measure names, then
    pull in measures referenced by those (a used measure's dependencies count).
    """
    measure_names = {m.name for m in model.all_measures()}
    leaves: set[str] = set()
    for p in model.pages:
        for v in p.visuals:
            for f in v.fields:
                leaves.add(f)
                leaves.add(f.split(".")[-1])
    used = {n for n in measure_names if n in leaves}
    expr = {m.name: (m.expression or "") for m in model.all_measures()}
    # Worklist over newly-added measures only — each measure's expression is
    # scanned exactly once, instead of re-scanning the whole (growing) `used`
    # set every round, which goes O(n^2) on models with many chained measures.
    queue = list(used)
    while queue:
        um = queue.pop()
        for ref in re.findall(r"\[([^\]]+)\]", expr.get(um, "")):
            if ref in measure_names and ref not in used:
                used.add(ref)
                queue.append(ref)
    return used


def measure_usage(model: SemanticModel) -> dict[str, list[str]]:
    """Measure name -> list of page names it is shown on."""
    measure_names = {m.name for m in model.all_measures()}
    usage: dict[str, list[str]] = {}
    for p in model.pages:
        for v in p.visuals:
            for f in v.fields:
                leaf = f.split(".")[-1]
                if leaf in measure_names and p.display_name not in usage.setdefault(leaf, []):
                    usage[leaf].append(p.display_name)
    return usage


def measure_dependencies(expression: str, measure_names: set[str]) -> list[str]:
    """The measures and ``Table[Column]`` references a DAX expression depends
    on, in order of first appearance — the "Dependencies" line of a measure's
    documentation. Bare ``[Name]`` references are kept only when they match a
    known measure (anything else is a column in a row context we can't
    attribute to a table)."""
    from .deterministic import _column_refs, _measure_refs  # local import: avoids cycle at module load

    expr = expression or ""
    deps: list[str] = []
    for ref in _measure_refs(expr):
        if ref in measure_names and ref not in deps:
            deps.append(ref)
    for ref in _column_refs(expr):
        if ref not in deps:
            deps.append(ref)
    return deps


def used_column_names(model: SemanticModel) -> set[str]:
    """Non-measure column names referenced anywhere in report visuals.

    Same leaf-matching approach as :func:`used_measure_names`, restricted to
    field tokens that are *not* a measure name — used by the audit's
    unused-columns check.
    """
    measure_names = {m.name for m in model.all_measures()}
    used: set[str] = set()
    for p in model.pages:
        for v in p.visuals:
            for f in v.fields:
                leaf = f.split(".")[-1]
                if leaf and leaf not in measure_names:
                    used.add(leaf)
    return used
