"""Turn an uploaded artifact into a parsed :class:`SemanticModel`.

Accepted uploads:
- ``.pbix``  — parsed directly.
- ``.zip``   — a zipped ``.pbip`` project; extracted (with a zip-slip guard)
               into the sandbox, then the project root is located and parsed.
- ``.pbip``  — only useful if its sibling folders are present (rare for an
               upload); otherwise the user should zip the project.
"""

from __future__ import annotations

import os
import stat
import zipfile
from pathlib import Path

from ..parsers import detect_and_parse
from ..schemas.model import SemanticModel


def _max_extracted_bytes() -> int:
    return int(os.environ.get("PBICOMPASS_MAX_EXTRACTED_MB", "512")) * 1024 * 1024


def _max_archive_entries() -> int:
    return int(os.environ.get("PBICOMPASS_MAX_ARCHIVE_ENTRIES", "20000"))


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract a PBIP archive without path traversal or decompression bombs."""
    dest = dest.resolve()
    members = zf.infolist()
    if len(members) > _max_archive_entries():
        raise ValueError("Archive contains too many files.")

    declared_total = sum(max(0, member.file_size) for member in members)
    cap = _max_extracted_bytes()
    if declared_total > cap:
        raise ValueError("Archive expands beyond the extraction size limit.")

    extracted = 0
    for member in members:
        target = (dest / member.filename).resolve()
        if dest != target and dest not in target.parents:
            raise ValueError("Refusing to extract zip entry outside the sandbox (zip-slip).")
        if member.flag_bits & 0x1:
            raise ValueError("Encrypted archive entries are not supported.")

        mode = member.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError("Archive contains an unsupported special file.")

        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member, "r") as source, open(target, "wb") as output:
            while chunk := source.read(1 << 20):
                extracted += len(chunk)
                if extracted > cap:
                    raise ValueError("Archive expands beyond the extraction size limit.")
                output.write(chunk)


def _find_project(root: Path) -> Path | None:
    """Locate a .pbip project root: a dir containing a ``*.SemanticModel`` folder."""
    candidates = [root, *(p for p in root.rglob("*") if p.is_dir())]
    for d in candidates:
        try:
            if any(c.is_dir() and c.name.endswith(".SemanticModel") for c in d.iterdir()):
                return d
        except OSError:
            continue
    pbips = list(root.rglob("*.pbip"))
    return pbips[0] if pbips else None


def ingest_to_model(upload_path: Path, sandbox_dir: Path) -> SemanticModel:
    suffix = upload_path.suffix.lower()
    if suffix == ".pbix":
        return detect_and_parse(upload_path)
    if suffix == ".pbip":
        return detect_and_parse(upload_path)
    if suffix == ".zip":
        extracted = sandbox_dir / "extracted"
        extracted.mkdir(exist_ok=True)
        with zipfile.ZipFile(upload_path) as zf:
            _safe_extract(zf, extracted)
        project = _find_project(extracted)
        if project is None:
            raise ValueError(
                "No Power BI project found in the zip "
                "(expected a '*.SemanticModel' folder or a '.pbip' file)."
            )
        return detect_and_parse(project)
    raise ValueError(f"Unsupported upload type '{suffix}'. Upload a .pbix or a .zip of a .pbip project.")
