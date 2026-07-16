import csv
import json
import math
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models.analysis import AnalysisInfo

router = APIRouter()


class ProteinEntriesRequest(BaseModel):
    analysis_id: str
    row_numbers: list[int]


class GlycanSitesRequest(BaseModel):
    accession: str
    analysis_id: str
    pvalue_threshold: float = 0.05
    ref_condition: str | None = None
    comp_condition: str | None = None


class GlycopeptideTableRequest(BaseModel):
    analysis_id: str
    ref_condition: str
    comp_condition: str


class ProteinProportionRequest(BaseModel):
    analysis_id: str
    identifier: str
    plot_condition: str


async def _find_results_csv(analysis_id: str, db: AsyncSession) -> Path:
    """Locate the results CSV file for a given analysis_id via DB lookup."""
    try:
        aid = int(analysis_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid analysis_id format")
    stmt = select(AnalysisInfo).where(AnalysisInfo.id == aid)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Analysis not found for id={analysis_id}"
        )
    results_path = Path(record.url)
    if not results_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Results CSV not found at {results_path}"
        )
    return results_path


def _read_csv_rows(csv_path: Path) -> tuple[list[str], list[list[str]]]:
    """Read all rows from a CSV file, returning (header, data_rows)."""
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None:
            raise HTTPException(status_code=500, detail="Results CSV is empty")
        rows = list(reader)
    return header, rows


@router.post("/protein-entries")
async def get_protein_entries(
    params: ProteinEntriesRequest, db: AsyncSession = Depends(get_db)
):
    """Get glycan entries for a specific protein."""
    csv_path = await _find_results_csv(params.analysis_id, db)
    header, all_rows = _read_csv_rows(csv_path)

    entries = []
    for row_num in params.row_numbers:
        if 0 <= row_num < len(all_rows):
            row = all_rows[row_num]
            entry = dict(zip(header, row))
            entry["_row_number"] = row_num
            entries.append(entry)

    return {"entries": entries, "total": len(entries)}


@router.post("/sites")
async def get_glycan_sites(
    params: GlycanSitesRequest, db: AsyncSession = Depends(get_db)
):
    """Get glycan sites for a protein accession.

    Returns { glycan_to_rows, site_list, max_site_pos, glycan_to_pvalue }
    matching the legacy data shape used by the interact page.
    """
    csv_path = await _find_results_csv(params.analysis_id, db)
    header, all_rows = _read_csv_rows(csv_path)

    # Find the relevant column indices
    try:
        idx_accession = header.index("Protein Accessions")
    except ValueError:
        raise HTTPException(
            status_code=500, detail="'Protein Accessions' column not found"
        )

    idx_site_info = (
        header.index("Protein---Position---Gene")
        if "Protein---Position---Gene" in header
        else None
    )
    idx_glycan_name = (
        header.index("Converted Glycan Names")
        if "Converted Glycan Names" in header
        else None
    )
    idx_glycan_comp = (
        header.index("Glycan Composition") if "Glycan Composition" in header else None
    )
    idx_position = (
        header.index("Position in Protein") if "Position in Protein" in header else None
    )

    # Find the p-value column if conditions are provided
    idx_pvalue = None
    if params.ref_condition and params.comp_condition:
        pvalue_col = f"p-value:{params.ref_condition}_to_{params.comp_condition}"
        alt_pvalue_col = f"p-value:{params.comp_condition}_to_{params.ref_condition}"
        if pvalue_col in header:
            idx_pvalue = header.index(pvalue_col)
        elif alt_pvalue_col in header:
            idx_pvalue = header.index(alt_pvalue_col)

    # Build glycan_to_rows, site_list, glycan_to_pvalue
    # site_list entries: "Accession---Position---Gene:::GlycanName:::GlycanComp"
    glycan_to_rows: dict[str, list[int]] = {}
    glycan_to_pvalue: dict[str, list[float]] = {}
    site_list: list[str] = []
    max_site_pos = 0

    site_idx = 0
    for row_num, row in enumerate(all_rows):
        if row[idx_accession] != params.accession:
            continue

        # Parse p-value and apply threshold
        pvalue = None
        if idx_pvalue is not None:
            try:
                pv_str = row[idx_pvalue]
                if pv_str and pv_str != "nan":
                    pvalue = float(pv_str)
            except (ValueError, IndexError):
                pass

        if pvalue is not None and pvalue > params.pvalue_threshold:
            continue

        site_info = row[idx_site_info] if idx_site_info is not None else ""
        glycan_name = row[idx_glycan_name] if idx_glycan_name is not None else ""
        glycan_comp = row[idx_glycan_comp] if idx_glycan_comp is not None else ""

        if not site_info or not glycan_name:
            continue

        # Build site_list entry matching legacy format
        site_entry = f"{site_info}:::{glycan_name}:::{glycan_comp}"
        site_list.append(site_entry)

        # Key for glycan_to_rows: "SiteInfo---GlycanName"
        key = f"{site_info}---{glycan_name}"
        if key not in glycan_to_rows:
            glycan_to_rows[key] = []
        glycan_to_rows[key].append(site_idx)

        # P-value mapping
        if pvalue is not None and pvalue > 0:
            log10_pv = -math.log10(pvalue)
            if key not in glycan_to_pvalue:
                glycan_to_pvalue[key] = []
            glycan_to_pvalue[key].append(log10_pv)

        # Track max position for protein length scaling
        if idx_position is not None and row[idx_position]:
            try:
                pos = int(float(row[idx_position]))
                max_site_pos = max(max_site_pos, pos)
            except (ValueError, TypeError):
                pass
        else:
            # Try to extract from site_info (e.g. "P28665---N313---Mug1" → 313)
            parts = site_info.split("---")
            if len(parts) >= 2:
                import re

                m = re.search(r"(\d+)", parts[1])
                if m:
                    max_site_pos = max(max_site_pos, int(m.group(1)))

        site_idx += 1

    return {
        "glycan_to_rows": glycan_to_rows,
        "site_list": site_list,
        "max_site_pos": max_site_pos,
        "glycan_to_pvalue": glycan_to_pvalue,
    }


@router.post("/glycopeptide-table")
async def get_glycopeptide_table(
    params: GlycopeptideTableRequest, db: AsyncSession = Depends(get_db)
):
    """Get glycopeptide-level table data."""
    csv_path = await _find_results_csv(params.analysis_id, db)
    header, all_rows = _read_csv_rows(csv_path)

    # Find abundance columns for the two conditions
    ref_abd_col = f"{params.ref_condition}: Abundance"
    comp_abd_col = f"{params.comp_condition}: Abundance"

    idx_ref = header.index(ref_abd_col) if ref_abd_col in header else None
    idx_comp = header.index(comp_abd_col) if comp_abd_col in header else None

    # Find p-value column
    pvalue_col = f"p-value:{params.ref_condition}_to_{params.comp_condition}"
    alt_pvalue_col = f"p-value:{params.comp_condition}_to_{params.ref_condition}"
    idx_pvalue = None
    if pvalue_col in header:
        idx_pvalue = header.index(pvalue_col)
    elif alt_pvalue_col in header:
        idx_pvalue = header.index(alt_pvalue_col)

    idx_glycan = (
        header.index("Converted Glycan Names")
        if "Converted Glycan Names" in header
        else None
    )
    idx_site = (
        header.index("Protein---Position---Gene")
        if "Protein---Position---Gene" in header
        else None
    )

    table_rows: list[dict] = []
    for row in all_rows:
        ref_abd = float(row[idx_ref]) if idx_ref is not None and row[idx_ref] else 0.0
        comp_abd = (
            float(row[idx_comp]) if idx_comp is not None and row[idx_comp] else 0.0
        )

        log2fc = math.log2(comp_abd / ref_abd) if ref_abd > 0 and comp_abd > 0 else 0.0

        pvalue = None
        neg_log10_p = 0.0
        if idx_pvalue is not None:
            try:
                pvalue = float(row[idx_pvalue])
                if pvalue > 0:
                    neg_log10_p = -math.log10(pvalue)
            except (ValueError, IndexError):
                pass

        table_rows.append(
            {
                "glycan_name": row[idx_glycan] if idx_glycan is not None else "",
                "site_info": row[idx_site] if idx_site is not None else "",
                "ref_abundance": ref_abd,
                "comp_abundance": comp_abd,
                "log2fc": log2fc,
                "neg_log10_pvalue": neg_log10_p,
                "p_value": pvalue,
            }
        )

    return {
        "ref_condition": params.ref_condition,
        "comp_condition": params.comp_condition,
        "rows": table_rows,
    }


@router.post("/protein-proportion")
async def get_protein_proportion(
    params: ProteinProportionRequest, db: AsyncSession = Depends(get_db)
):
    """Get protein proportion data for violin/box plot."""
    upload_dir = Path(settings.upload_dir)

    # Find the proportion (pbio) CSV and protein info JSON
    pbio_candidates = list(upload_dir.glob(f"*{params.analysis_id}*_pbio.csv"))
    if not pbio_candidates:
        raise HTTPException(status_code=404, detail="Proportion (pbio) CSV not found")
    pbio_path = pbio_candidates[0]

    info_candidates = list(upload_dir.glob(f"*{params.analysis_id}*_proteininfo.json"))
    protein_info = {}
    if info_candidates:
        protein_info = json.loads(info_candidates[0].read_text(encoding="utf-8"))

    # Read the pbio CSV
    with open(pbio_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])

        # Filter columns by the requested condition
        cond_col_indices = [
            i for i, col in enumerate(header) if params.plot_condition in col
        ]

        proportion_data: list[dict] = []
        for row in reader:
            identifier_val = row[0] if row else ""
            if params.identifier and identifier_val != params.identifier:
                continue

            replicate_values = []
            for idx in cond_col_indices:
                try:
                    replicate_values.append(float(row[idx]))
                except (ValueError, IndexError):
                    replicate_values.append(0.0)

            proportion_data.append(
                {
                    "identifier": identifier_val,
                    "condition": params.plot_condition,
                    "replicates": replicate_values,
                    "columns": [header[i] for i in cond_col_indices],
                }
            )

    return {
        "data": proportion_data,
        "protein_info": protein_info,
    }
