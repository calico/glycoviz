import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.config import settings
from app.core.excel_reader import (
    build_header_remap,
    normalize_to_csv,
    read_abundance_columns,
    read_all_headers,
)
from app.api.settings import _read_header_sets
from app.schemas.analysis import UploadResponse

router = APIRouter()


def _match_header_set(all_headers: list[str]):
    """Match raw headers against saved header sets.

    Returns ``(header_remap, matched_hs)`` on success, or ``(None, None)``
    when no header set matches.

    The returned *header_remap* is a unified dict that maps **every** column
    needing renaming to its canonical name — including structural columns
    (``Protein ID → Protein Accessions``) and abundance columns
    (``Sample1 Intensity → Abundances (Grouped): Sample1``).

    Columns that should be **removed** (stale ``"Abundances (Grouped): "``
    columns that don't belong to the matched header set) are mapped to
    ``None``.
    """
    try:
        header_sets = _read_header_sets()
    except Exception:
        return None, None

    raw_set = set(all_headers)
    for hs in header_sets:
        fields = [
            hs.glycan_composition,
            hs.protein_accessions,
            hs.position_in_protein,
            hs.master_protein_descriptions,
            hs.sequence,
            hs.modifications,
            hs.fdr_prefix,
        ]
        required = {f for f in fields if f}
        if required and required.issubset(raw_set):
            header_remap = build_header_remap(hs)

            # Build abundance column mappings from wildcard pattern
            abundance_pattern = hs.abundance_columns or ""
            if abundance_pattern:
                canonical = "Abundances (Grouped): "

                # Parse wildcard pattern
                if "*" not in abundance_pattern:
                    # Exact match: "Intensity"
                    match_mode = "exact"
                    match_value = abundance_pattern
                elif abundance_pattern.startswith("*"):
                    # Suffix match: "* Intensity" → endswith(" Intensity")
                    match_mode = "suffix"
                    match_value = abundance_pattern.lstrip("*").lstrip()
                else:
                    # Prefix match: "Abundances (Grouped)*" → startswith(...)
                    match_mode = "prefix"
                    match_value = abundance_pattern.rstrip("*").rstrip()

                source_is_canonical = match_value == "Abundances (Grouped)"

                for name in all_headers:
                    # Already canonical and headerset matches — no remap needed
                    if source_is_canonical and name.startswith(canonical):
                        continue

                    is_abundance = False
                    sample_name = name

                    if match_mode == "prefix" and name.startswith(match_value):
                        rest = name[len(match_value) :]
                        stripped = rest.lstrip(": ")
                        is_abundance = True
                        sample_name = stripped if stripped else name
                    elif match_mode == "suffix" and name.endswith(match_value):
                        sample_name = name[: -len(match_value)].rstrip()
                        is_abundance = bool(sample_name)
                    elif match_mode == "exact" and name == match_value:
                        is_abundance = True
                        sample_name = name

                    if is_abundance:
                        new_name = f"{canonical}{sample_name}"
                        if name != new_name:
                            header_remap[name] = new_name

                # Corner case: mark stale canonical columns for removal
                if not source_is_canonical:
                    for name in all_headers:
                        if name.startswith(canonical) and name not in header_remap:
                            header_remap[name] = None  # sentinel: remove column

            return header_remap, hs
    return None, None


@router.post("/data-file", response_model=UploadResponse)
async def upload_data_file(
    file: UploadFile = File(...),
    abundance_prefixes: str | None = Form(None),
):
    """Upload a tabular data file, normalize headers, and return column info.

    Supported formats: ``.xlsx``, ``.xls``, ``.tsv``, ``.csv``, ``.txt``.

    The upload pipeline:

    1. Save the raw file and read its original headers (for frontend matching).
    2. Match headers against saved header sets to build a remap dict.
    3. Normalize to CSV with canonical Byonic column names and
       ``"Abundances (Grouped): "`` prefixed abundance columns.
    4. Return the abundance column list and the original raw headers.
    """
    os.makedirs(settings.upload_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    suffix = Path(file.filename or "upload").suffix.lower()
    dest = Path(settings.upload_dir) / f"{file_id}{suffix}"

    content = await file.read()
    dest.write_bytes(content)

    # 1) Read raw headers before any conversion (for frontend header matching)
    all_headers = read_all_headers(str(dest))

    # 2) Match against header sets to get unified remap dict
    header_remap, matched_hs = _match_header_set(all_headers)

    # 3) Normalize: remap headers + convert to csv
    csv_dest = dest.with_suffix(".csv")
    needs_conversion = suffix != ".csv" or header_remap

    try:
        if needs_conversion or header_remap:
            did_change = normalize_to_csv(
                str(dest),
                str(csv_dest),
                header_remap=header_remap,
            )
            if needs_conversion:
                dest.unlink(missing_ok=True)
                dest = csv_dest
            elif did_change:
                dest.unlink(missing_ok=True)
                csv_dest.rename(dest)
            else:
                csv_dest.unlink(missing_ok=True)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        csv_dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to normalize file: {exc}",
        )

    # 3b) Validate: at least one of Glycan Composition or Modifications must exist
    # Note: ensure_glycan_composition and ensure_placeholder_columns are
    # deferred to analysis time (run_analysis) to keep uploads fast.
    final_headers = read_all_headers(str(dest))
    final_set = set(final_headers)
    has_glycan = "Glycan Composition" in final_set
    has_mods = "Modifications (all possible sites)" in final_set
    if not has_glycan and not has_mods:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail='File must contain at least one of "Glycan Composition" or "Modifications" columns.',
        )

    # 4) Read abundance columns from the (possibly converted) file
    prefixes: list[str] | None = None
    if abundance_prefixes:
        try:
            parsed = json.loads(abundance_prefixes)
            if isinstance(parsed, list):
                prefixes = [f"{p}: " if not p.endswith(": ") else p for p in parsed]
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        columns = read_abundance_columns(str(dest), abundance_prefixes=prefixes)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to read columns: {exc}")

    return UploadResponse(file_id=file_id, columns=columns, all_headers=all_headers)


@router.post("/protein-fc")
async def upload_protein_fc(
    analysis_id: str = Query(...),
    ref_condition: str = Query(...),
    comp_condition: str = Query(...),
    fc_file: UploadFile = File(...),
    pbio_file: UploadFile = File(None),
    info_file: UploadFile = File(None),
):
    """Upload protein fold-change CSV files."""
    os.makedirs(settings.upload_dir, exist_ok=True)

    tag = f"{ref_condition}_vs_{comp_condition}"

    fc_dest = Path(settings.upload_dir) / f"{analysis_id}_{tag}_protein_fc.csv"
    fc_content = await fc_file.read()
    fc_dest.write_bytes(fc_content)

    saved = [str(fc_dest)]

    if pbio_file is not None:
        pbio_dest = Path(settings.upload_dir) / f"{analysis_id}_{tag}_pbio.csv"
        pbio_dest.write_bytes(await pbio_file.read())
        saved.append(str(pbio_dest))

    if info_file is not None:
        info_dest = Path(settings.upload_dir) / f"{analysis_id}_{tag}_proteininfo.json"
        info_dest.write_bytes(await info_file.read())
        saved.append(str(info_dest))

    return {"status": "ok", "files": saved}


@router.get("/protein-fc-status")
async def protein_fc_status(
    analysis_id: str,
    ref_condition: str,
    comp_condition: str,
):
    """Check processing status of protein FC file."""
    tag = f"{ref_condition}_vs_{comp_condition}"
    fc_path = Path(settings.upload_dir) / f"{analysis_id}_{tag}_protein_fc.csv"

    return {
        "exists": fc_path.exists(),
        "analysis_id": analysis_id,
        "ref_condition": ref_condition,
        "comp_condition": comp_condition,
    }
