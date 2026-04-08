import csv
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.foldchange import compute_foldchange as core_compute_foldchange
from app.db.session import get_db
from app.models.analysis import AnalysisInfo
from app.schemas.foldchange import FcAvgRequest, FoldChangeRequest, FoldChangeResult

router = APIRouter()


async def _find_results_csv(analysis_id: str, db: AsyncSession) -> str:
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
    return str(results_path)


@router.post("/compute", response_model=FoldChangeResult)
async def compute_foldchange(
    params: FoldChangeRequest, db: AsyncSession = Depends(get_db)
):
    """Compute fold change between two conditions."""
    file_path = await _find_results_csv(params.analysis_id, db)

    try:
        result = core_compute_foldchange(
            file_path=file_path,
            reference_condition=params.reference_condition,
            comparison_condition=params.comparison_condition,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Results file not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return FoldChangeResult(
        glycan_list=result.glycan_list,
        fc=result.fc,
        p_value=result.p_value,
        anova=result.anova,
    )


@router.post("/fc-avg")
async def get_fc_avg(params: FcAvgRequest, db: AsyncSession = Depends(get_db)):
    """Get fold change with protein-level overlay for the 2-subplot plot.

    Returns glycan-level FC, protein-level FC (from companion CSV), and
    normalized FC (glycan FC minus protein FC) for each glycosite.
    """
    file_path = await _find_results_csv(params.analysis_id, db)

    try:
        glycan_result = core_compute_foldchange(
            file_path=file_path,
            reference_condition=params.reference_condition,
            comparison_condition=params.comparison_condition,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Results file not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Look for companion protein FC CSV (uploaded separately via compMS)
    # Naming convention: {stem}---{comparison}_to_{reference}.csv
    results_path = Path(file_path)
    stem = str(results_path).replace("_results.csv", "")
    ref = params.reference_condition
    cmp = params.comparison_condition

    protein_fc_path = Path(f"{stem}---{cmp}_to_{ref}.csv")
    accession_to_fc: dict[str, float] = {}

    if protein_fc_path.exists():
        with open(protein_fc_path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header:
                idx_protein = -1
                idx_fc = -1
                for i, col in enumerate(header):
                    if col == "Protein":
                        idx_protein = i
                    elif col.startswith("Est_Fc"):
                        idx_fc = i
                if idx_protein >= 0 and idx_fc >= 0:
                    for row in reader:
                        acc = row[idx_protein].replace("-", "_")
                        try:
                            accession_to_fc[acc] = float(row[idx_fc])
                        except (ValueError, IndexError):
                            pass
                        # Also store by middle part for "tr|X|Y" or "sp|X|Y" format
                        if acc.startswith("tr|") or acc.startswith("sp|"):
                            parts = acc.split("|")
                            if len(parts) >= 2:
                                accession_to_fc[parts[1]] = float(row[idx_fc])

    # Build protein_mean and mean_norm arrays aligned with glycan_list
    protein_mean: list[float] = []
    mean_norm: list[float] = []
    for i, gl_entry in enumerate(glycan_result.glycan_list):
        parts = gl_entry.split("---")
        acc = parts[1] if len(parts) >= 2 else ""
        pfc = accession_to_fc.get(acc, 0.0)
        protein_mean.append(pfc)
        mean_norm.append(glycan_result.fc[i] - pfc)

    return {
        "glycan_list": glycan_result.glycan_list,
        "mean": glycan_result.fc,
        "p_value": glycan_result.p_value,
        "protein_mean": protein_mean,
        "mean_norm": mean_norm,
        "anova": glycan_result.anova,
        "has_protein_data": bool(accession_to_fc),
    }
