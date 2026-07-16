#!/usr/bin/env python
"""Validate the parsers against REAL Power BI TMDL exports.

Why this exists: the unit suite tests parsing against *synthetic* fixtures, which
encode our own understanding of TMDL syntax. If that understanding is wrong, the
fixture is wrong the same way and the tests pass while real models silently lose
data. That is not hypothetical — it is exactly how the `cultureInfo` bug was
found (the parser dispatched on `culture`; real exports write `cultureInfo`, so
cultures parsed as 0 on every real model while the synthetic tests stayed green).

Method: for each model, raw-grep `definition/**/*.tmdl` for each feature's
declaration keyword (ground truth that the feature IS in the source), then
compare against what the parser actually produced. Source > 0 while parsed == 0
is a silent-loss bug; any mismatch is worth a look.

Only `definition/` is scanned — a `.SemanticModel` may also contain scratch
folders (e.g. `TMDLScripts/`) that are NOT part of the model definition and
would otherwise inflate the ground truth.

Privacy: prints only counts and pass/fail — never table names, DAX, or business
content. Runs fully locally; nothing is transmitted.

Usage:
    python scripts/validate_real_models.py <path.pbip | path.SemanticModel> [...]

Exit code is the number of mismatches, so it can gate CI if you ever add a
corpus of real models.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pbicompass.parsers import detect_and_parse  # noqa: E402

# feature -> regex matching its TMDL *declaration* (not a mere mention)
FEATURE_RX = {
    "calculationItem": re.compile(r"^\s*calculationItem\s", re.M),
    "hierarchy": re.compile(r"^\s*hierarchy\s", re.M),
    "cultureInfo": re.compile(r"^\s*cultureInfo\s", re.M),
    "kpi": re.compile(r"^\s*kpi\b", re.M),
    "refreshPolicy": re.compile(r"^\s*refreshPolicy\b", re.M),
    "perspective": re.compile(r"^\s*perspective\s", re.M),
    "formatStringDefinition": re.compile(r"^\s*formatStringDefinition\b", re.M),
}


def validate_pbit(path: Path) -> int:
    """Validate the TMSL parser against a real ``.pbit``.

    A .pbit carries its model as ``DataModelSchema`` — real, Power-BI-emitted
    TMSL, readable with nothing but zipfile+json. That makes it the only way to
    check the TMSL path against genuine output rather than dicts we wrote
    ourselves from our own reading of the format, which is exactly the
    circularity that let the ``cultureInfo`` bug survive.

    Compares the parse against the raw JSON's own counts. Prints counts only.
    """
    import json
    import zipfile

    from pbicompass.parsers.tmsl import parse_semantic_model_tmsl

    print(f"\n=== {path.name} (.pbit / TMSL) ===")
    try:
        zf = zipfile.ZipFile(path)
        entry = next((n for n in zf.namelist() if "DataModelSchema" in n), None)
        if entry is None:
            print("  SKIP — no DataModelSchema in this .pbit")
            return 0
        raw = zf.read(entry)
        # Power BI writes DataModelSchema as UTF-16LE.
        text = (raw.decode("utf-16-le", errors="replace") if raw[:2] == b"{\x00"
                else raw.decode("utf-8-sig", errors="replace"))
        bim = json.loads(text)
    except Exception as exc:
        print(f"  READ FAILED: {type(exc).__name__}: {str(exc)[:120]}")
        return 1

    warnings: list[str] = []
    agg = parse_semantic_model_tmsl(bim, warnings)
    model = bim.get("model", bim)
    expected = {
        "tables": len(model.get("tables", [])),
        "measures": sum(len(t.get("measures", [])) for t in model.get("tables", [])),
        "relationships": len(model.get("relationships", [])),
        "roles": len(model.get("roles", [])),
    }
    got = {
        "tables": len(agg["tables"]),
        "measures": sum(len(t.measures) for t in agg["tables"]),
        "relationships": len(agg["relationships"]),
        "roles": len(agg["roles"]),
    }
    mismatches = 0
    for key, want in expected.items():
        if want == got[key]:
            print(f"  PASS  {key}: source {want} -> parsed {got[key]}")
        else:
            print(f"  FAIL  {key}: source {want} -> parsed {got[key]}   <-- LOSS")
            mismatches += 1
    print(f"  parse warnings: {len(warnings)}")
    return mismatches


def _semantic_model_dir(path: Path) -> Path | None:
    if path.is_dir() and path.name.endswith(".SemanticModel"):
        return path
    base = path.parent if path.is_file() else path
    return next((p for p in base.glob("*.SemanticModel")), None)


def _raw_counts(sm: Path) -> dict[str, int]:
    out = {k: 0 for k in FEATURE_RX}
    definition = sm / "definition"
    if not definition.is_dir():
        return out
    for f in definition.rglob("*.tmdl"):
        try:
            text = f.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        for k, rx in FEATURE_RX.items():
            out[k] += len(rx.findall(text))
    return out


def _parsed_counts(model) -> dict[str, int]:
    return {
        "calculationItem": sum(len(t.calculation_items) for t in model.tables),
        "hierarchy": sum(len(t.hierarchies) for t in model.tables),
        "cultureInfo": len(model.cultures),
        "kpi": sum(1 for m in model.all_measures() if m.kpi),
        "refreshPolicy": sum(1 for t in model.tables if t.refresh_policy),
        "perspective": len(model.perspectives),
        "formatStringDefinition": (
            sum(1 for m in model.all_measures() if m.format_string_expression)
            + sum(1 for t in model.tables for ci in t.calculation_items
                  if ci.format_string_expression)),
    }


def validate(path: Path) -> int:
    print(f"\n=== {path.name} ===")
    sm = _semantic_model_dir(path)
    if sm is None:
        print("  SKIP — no .SemanticModel folder found (a .pbix has no TMDL to check)")
        return 0
    # detect_and_parse wants the .pbip file or the *project* directory; handed a
    # bare `<name>.SemanticModel` folder it finds no project and parses nothing.
    target = path if path.is_file() else (
        path.parent if path.name.endswith(".SemanticModel") else path)
    try:
        model = detect_and_parse(target)
    except Exception as exc:
        print(f"  PARSE FAILED: {type(exc).__name__}: {str(exc)[:140]}")
        return 1

    c = model.meta.counts
    print(f"  parsed: {c.get('tables', 0)} tables, {c.get('columns', 0)} columns, "
          f"{c.get('measures', 0)} measures, {c.get('relationships', 0)} relationships, "
          f"{c.get('pages', 0)} pages · {len(model.meta.warnings)} warning(s)")

    raw, got, mismatches = _raw_counts(sm), _parsed_counts(model), 0
    for k in FEATURE_RX:
        if not raw[k] and not got[k]:
            continue
        if raw[k] == got[k]:
            print(f"  PASS  {k}: source {raw[k]} -> parsed {got[k]}")
        else:
            kind = "SILENT LOSS" if raw[k] and not got[k] else "MISMATCH"
            print(f"  FAIL  {k}: source {raw[k]} -> parsed {got[k]}   <-- {kind}")
            mismatches += 1
    absent = [k for k in FEATURE_RX if not raw[k]]
    if absent:
        print(f"  (not present in this model, so unverified here: {', '.join(absent)})")
    return mismatches


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    total = sum(
        (validate_pbit(Path(a)) if Path(a).suffix.lower() == ".pbit" else validate(Path(a)))
        for a in argv
    )
    print(f"\n{'=' * 60}\nTOTAL MISMATCHES: {total}")
    return total


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
