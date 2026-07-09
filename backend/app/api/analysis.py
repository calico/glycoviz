import csv
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.glycan_converter import AnalysisFilters, run_analysis as core_run_analysis
from app.db.session import get_db
from app.models.analysis import AnalysisInfo
from app.schemas.analysis import AnalysisCreate, AnalysisResponse, AnalysisRunResult
from pydantic import BaseModel

router = APIRouter()


@router.post("/run", response_model=AnalysisRunResult)
async def run_analysis(params: AnalysisCreate, db: AsyncSession = Depends(get_db)):
    """Run the full glycan analysis pipeline."""
    print(f"[DEBUG API] /analysis/run called")
    print(f"[DEBUG API] file_id={params.file_id}")
    print(f"[DEBUG API] conditions={params.conditions}")
    print(
        f"[DEBUG API] filters: fdr={params.fdr_threshold}, byonic={params.byonic_score}, "
        f"ppm={params.ppm_threshold}, peptide_len={params.peptide_length}, "
        f"min_count={params.min_count}, export_filter={params.export_filter}, "
        f"abundance_type={params.abundance_type}"
    )

    # Resolve the uploaded file path from file_id
    upload_dir = Path(settings.upload_dir)
    candidates = list(upload_dir.glob(f"{params.file_id}.*"))
    print(f"[DEBUG API] upload_dir={upload_dir}, candidates={candidates}")
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"Uploaded file not found for file_id={params.file_id}",
        )
    filepath = str(candidates[0])
    print(f"[DEBUG API] using filepath={filepath}")

    # Build AnalysisFilters from the request body
    filters = AnalysisFilters(
        fdr2d_threshold=params.fdr_threshold,
        fdr_is_probability=params.fdr_is_probability,
        byonic_threshold=params.byonic_score,
        ppm_threshold=params.ppm_threshold,
        peplength_threshold=params.peptide_length,
        export_filter=params.export_filter,
        mincount_threshold=params.min_count,
        abundance_type=params.abundance_type,
        w_depth=params.w_depth,
        w_conflict=params.w_conflict,
        w_byonic=params.w_byonic,
        column_header_sets=params.column_header_sets,
    )

    # Build the conditions list from the conditions dict (column_name -> condition_label)
    conditions = list(params.conditions.values())

    # Ensure required columns exist before running analysis
    from app.core.excel_reader import ensure_glycan_composition, ensure_placeholder_columns
    try:
        ensure_glycan_composition(filepath)
    except Exception:
        pass
    try:
        ensure_placeholder_columns(filepath)
    except Exception:
        pass

    # Run the core analysis (CPU-bound, but kept simple for now)
    try:
        result = core_run_analysis(filepath, filters, conditions)
        print(f"[DEBUG API] Analysis complete: output_file={result.output_file}")
        print(f"[DEBUG API] statistics={result.statistics}")
    except Exception as exc:
        import traceback

        print(f"[DEBUG API] Analysis FAILED with exception:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    # Persist analysis info to DB (id auto-incremented)
    analysis_name = params.name.strip() if params.name.strip() else Path(filepath).stem
    record = AnalysisInfo(
        name=analysis_name,
        url=result.output_file,
        parameters=json.dumps(
            {
                "fdr_threshold": params.fdr_threshold,
                "byonic_score": params.byonic_score,
                "ppm_threshold": params.ppm_threshold,
                "peptide_length": params.peptide_length,
                "min_count": params.min_count,
                "export_filter": params.export_filter,
                "abundance_type": params.abundance_type,
                "conditions": params.conditions,
                "w_depth": params.w_depth,
                "w_conflict": params.w_conflict,
                "w_byonic": params.w_byonic,
            }
        ),
        conditions=json.dumps(params.conditions),
        study_code=params.study_code,
        quant_method=params.quant_method,
        note=params.note,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return AnalysisRunResult(
        analysis_id=record.id,
        output_file=result.output_file,
        site_to_rows=result.site_to_rows,
        statistics=result.statistics,
        qc_output_file=result.qc_output_file,
    )


@router.get("/list", response_model=list[AnalysisResponse])
async def list_analyses(db: AsyncSession = Depends(get_db)):
    """List all saved analyses."""
    stmt = select(AnalysisInfo).order_by(AnalysisInfo.created_at.desc())
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return rows


@router.delete("/{analysis_id}", status_code=204)
async def delete_analysis(analysis_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an analysis record and all associated files in uploads/."""
    stmt = select(AnalysisInfo).where(AnalysisInfo.id == analysis_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Derive file_id from the url field (e.g. "uploads/abc123_results.csv" -> "abc123")
    if record.url:
        results_path = Path(record.url)
        file_id = results_path.stem.replace("_results", "")
        uploads_dir = results_path.parent
        # Remove all files matching the file_id pattern
        for f in uploads_dir.glob(f"*{file_id}*"):
            try:
                f.unlink()
            except OSError:
                pass

    await db.delete(record)
    await db.commit()


@router.get("/{analysis_id}", response_model=None)
async def get_analysis(analysis_id: int, db: AsyncSession = Depends(get_db)):
    """Get details of a specific analysis, including QC stats and filter params."""
    stmt = select(AnalysisInfo).where(AnalysisInfo.id == analysis_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Base response fields
    resp: dict = {
        "id": str(record.id),
        "name": record.name,
        "study_code": record.study_code,
        "quant_method": record.quant_method,
        "note": record.note,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }

    # Parse stored conditions
    if record.conditions:
        try:
            resp["conditions"] = list(set(json.loads(record.conditions).values()))
        except Exception:
            resp["conditions"] = []

    # Parse stored filter params
    if record.parameters:
        try:
            resp["filter_params"] = json.loads(record.parameters)
        except Exception:
            resp["filter_params"] = None

    # Load QC stats from the _qc.csv file
    if record.url:
        results_path = Path(record.url)
        base_stem = results_path.stem.replace("_results", "")
        qc_file = results_path.parent / f"{base_stem}_qc.csv"
        if qc_file.exists():
            try:
                with open(qc_file, newline="", encoding="utf-8") as fh:
                    reader = csv.reader(fh)
                    header = next(reader, [])
                    values = next(reader, [])
                    if header and values:
                        qc = {}
                        for k, v in zip(header, values):
                            try:
                                qc[k] = int(v)
                            except ValueError:
                                qc[k] = v
                        resp["qc_stats"] = qc
            except Exception:
                resp["qc_stats"] = None

    return resp


@router.get("/{analysis_id}/sites")
async def get_analysis_sites(analysis_id: int, db: AsyncSession = Depends(get_db)):
    """Return the sites table for an analysis as a list of SiteRow objects."""
    base = await _get_analysis_file_stem(analysis_id, db)
    sites_file = Path(str(base) + ".sites_table.json")

    if not sites_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Sites table file not found: {sites_file}"
        )

    data = json.loads(sites_file.read_text(encoding="utf-8"))
    # data is { "accession---position---gene": [row_numbers, ...], ... }
    sites = []
    for key, row_numbers in data.items():
        parts = key.split("---")
        accession = parts[0] if len(parts) > 0 else ""
        site = parts[1] if len(parts) > 1 else ""
        gene = parts[2] if len(parts) > 2 else ""
        sites.append(
            {
                "gene": gene,
                "protein": accession,
                "accession": accession,
                "site": site,
                "count": len(row_numbers),
            }
        )
    return sites


async def _get_analysis_file_stem(analysis_id: int, db: AsyncSession) -> Path:
    """Look up an analysis record and return the base file stem (without _results)."""
    stmt = select(AnalysisInfo).where(AnalysisInfo.id == analysis_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    results_path = Path(record.url)
    base_stem = results_path.stem.replace("_results", "")
    return results_path.parent / base_stem


def _load_global_json(base: Path) -> dict:
    """Load the _global.json file for an analysis."""
    global_file = Path(str(base) + "_global.json")
    if not global_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Global stats file not found: {global_file}"
        )
    return json.loads(global_file.read_text(encoding="utf-8"))


@router.get("/{analysis_id}/abundance")
async def get_abundance_data(
    analysis_id: int,
    mode: str = "glycan",
    metric: str = "abundance",
    db: AsyncSession = Depends(get_db),
):
    """Return abundance or count data for bar charts.

    mode: "glycan" or "motif"
    metric: "abundance" or "count"
    """
    base = await _get_analysis_file_stem(analysis_id, db)
    global_data = _load_global_json(base)

    key = f"{mode}_to_{'abd' if metric == 'abundance' else 'cnt'}_replicates"
    data = global_data.get(key, {})

    return {
        "data": data,
        "condition_names": global_data.get("condition_names", []),
        "sample_names": global_data.get("col_names", []),
    }


@router.get("/{analysis_id}/protein/{accession}/abundance")
async def get_protein_abundance(
    analysis_id: int,
    accession: str,
    mode: str = "glycan",
    metric: str = "abundance",
    site: str | None = None,
    w_depth: float | None = None,
    w_conflict: float | None = None,
    w_byonic: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return per-protein abundance data filtered by accession and optionally by site.

    Reads the results CSV, filters rows matching the protein accession
    (and site position when provided), and aggregates abundance per glycan
    name across replicates.
    """
    base = await _get_analysis_file_stem(analysis_id, db)
    global_data = _load_global_json(base)
    condition_names = global_data.get("condition_names", [])
    sample_names = global_data.get("col_names", [])
    n_samples = len(sample_names)

    results_csv = Path(str(base) + "_results.csv")
    if not results_csv.exists():
        raise HTTPException(status_code=404, detail="Results CSV not found")

    from collections import defaultdict

    # Per-sequence breakdown
    seq_glycan_to_values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(lambda: [0.0] * n_samples)
    )
    seq_glycan_to_scores: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    # Combined across all sequences (pre-split logic)
    all_glycan_to_values: dict[str, list[float]] = defaultdict(
        lambda: [0.0] * n_samples
    )
    all_glycan_to_scores: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    with open(results_csv, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)

        # Find column indices
        try:
            idx_accession = header.index("Protein Accessions")
        except ValueError:
            raise HTTPException(
                status_code=500, detail="'Protein Accessions' column not found"
            )

        idx_glycan = (
            header.index("Converted Glycan Names")
            if "Converted Glycan Names" in header
            else None
        )
        idx_ppg = (
            header.index("Protein---Position---Gene")
            if "Protein---Position---Gene" in header
            else None
        )
        idx_sequence = header.index("Sequence") if "Sequence" in header else None

        # Score column indices (use percentile columns for individual metrics)
        idx_composite = (
            header.index("composite_validation_score")
            if "composite_validation_score" in header
            else None
        )
        idx_depth_pct = header.index("depth_pct") if "depth_pct" in header else None
        idx_rt_conflict_pct = (
            header.index("rt_conflict_pct") if "rt_conflict_pct" in header else None
        )
        idx_engine_score_pct = (
            header.index("engine_score_pct") if "engine_score_pct" in header else None
        )

        # Find abundance columns matching sample_names
        abd_indices = []
        for sn in sample_names:
            if sn in header:
                abd_indices.append(header.index(sn))
            else:
                abd_indices.append(-1)

        # Build site match prefix when filtering by site (e.g. "B2RXS4---N1005---")
        site_prefix = f"{accession}---{site}---" if site else None

        for row in reader:
            if len(row) <= idx_accession:
                continue
            if row[idx_accession] != accession:
                continue
            # Filter by site position when provided
            if site_prefix and idx_ppg is not None and idx_ppg < len(row):
                if not row[idx_ppg].startswith(site_prefix):
                    continue

            glycan_name = (
                row[idx_glycan]
                if idx_glycan is not None and len(row) > idx_glycan
                else ""
            )
            if not glycan_name:
                continue

            seq_key = (
                row[idx_sequence]
                if idx_sequence is not None and idx_sequence < len(row)
                else ""
            )

            for k, col_i in enumerate(abd_indices):
                if col_i < 0 or col_i >= len(row):
                    continue
                try:
                    val = float(row[col_i]) if row[col_i] else 0.0
                except ValueError:
                    val = 0.0
                seq_glycan_to_values[seq_key][glycan_name][k] += val
                all_glycan_to_values[glycan_name][k] += val

            # Collect score percentiles and composite per glycan
            for idx, key in [
                (idx_composite, "composite"),
                (idx_depth_pct, "depth"),
                (idx_rt_conflict_pct, "rt_conflict"),
                (idx_engine_score_pct, "engine_score"),
            ]:
                if idx is not None and idx < len(row) and row[idx]:
                    try:
                        score_val = float(row[idx])
                        seq_glycan_to_scores[seq_key][glycan_name][key].append(
                            score_val
                        )
                        all_glycan_to_scores[glycan_name][key].append(score_val)
                    except ValueError:
                        pass

    # Recompute composite scores in-memory when custom weights are provided
    recompute = w_depth is not None and w_conflict is not None and w_byonic is not None
    if recompute:
        w_sum = w_depth + w_conflict + w_byonic
        for scores_dict in [all_glycan_to_scores, *(seq_glycan_to_scores.values())]:
            for glycan_scores in scores_dict.values():
                d_list = glycan_scores.get("depth", [])
                c_list = glycan_scores.get("rt_conflict", [])
                e_list = glycan_scores.get("engine_score", [])
                n = max(len(d_list), len(c_list), len(e_list))
                if n == 0:
                    continue
                recomputed = []
                for i in range(n):
                    d = d_list[i] if i < len(d_list) else 0.5
                    c = c_list[i] if i < len(c_list) else 0.5
                    e = e_list[i] if i < len(e_list) else 0.5
                    raw = w_depth * d + w_conflict * c + w_byonic * e
                    recomputed.append(raw / w_sum if w_sum > 0 else 0.0)
                glycan_scores["composite"] = recomputed

    # Build per-sequence response sorted by number of glycans (most data first)
    ranked_keys = sorted(
        seq_glycan_to_values.keys(),
        key=lambda s: len(seq_glycan_to_scores[s]),
        reverse=True,
    )
    by_sequence: dict[str, dict] = {}
    for seq_key in ranked_keys:
        by_sequence[seq_key] = {
            "data": dict(seq_glycan_to_values[seq_key]),
            "condition_names": condition_names,
            "sample_names": sample_names,
            "composite_scores": {
                k: dict(v) for k, v in seq_glycan_to_scores[seq_key].items()
            },
        }

    # Append "All Sequences" combined entry when more than one sequence exists
    if len(by_sequence) > 1:
        by_sequence["All Sequences"] = {
            "data": dict(all_glycan_to_values),
            "condition_names": condition_names,
            "sample_names": sample_names,
            "composite_scores": {k: dict(v) for k, v in all_glycan_to_scores.items()},
        }

    return by_sequence


class SiteQuery(BaseModel):
    accession: str
    site: str


@router.post("/{analysis_id}/multi-site-abundance")
async def get_multi_site_abundance(
    analysis_id: int,
    body: dict,
    mode: str = "glycan",
    metric: str = "abundance",
    w_depth: float | None = None,
    w_conflict: float | None = None,
    w_byonic: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return aggregated abundance for multiple accession+site pairs."""
    sites: list[dict] = body.get("sites", [])
    if not sites:
        raise HTTPException(status_code=400, detail="No sites provided")

    base = await _get_analysis_file_stem(analysis_id, db)
    global_data = _load_global_json(base)
    condition_names = global_data.get("condition_names", [])
    sample_names = global_data.get("col_names", [])
    n_samples = len(sample_names)

    results_csv = Path(str(base) + "_results.csv")
    if not results_csv.exists():
        raise HTTPException(status_code=404, detail="Results CSV not found")

    # Build set of site prefixes to match
    site_prefixes = {f"{s['accession']}---{s['site']}---" for s in sites}

    from collections import defaultdict

    glycan_to_values: dict[str, list[float]] = defaultdict(lambda: [0.0] * n_samples)
    glycan_to_scores: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    with open(results_csv, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)

        try:
            idx_accession = header.index("Protein Accessions")
        except ValueError:
            raise HTTPException(
                status_code=500, detail="'Protein Accessions' column not found"
            )

        idx_glycan = (
            header.index("Converted Glycan Names")
            if "Converted Glycan Names" in header
            else None
        )
        idx_ppg = (
            header.index("Protein---Position---Gene")
            if "Protein---Position---Gene" in header
            else None
        )

        # Score column indices (use percentile columns for individual metrics)
        idx_composite = (
            header.index("composite_validation_score")
            if "composite_validation_score" in header
            else None
        )
        idx_depth_pct = header.index("depth_pct") if "depth_pct" in header else None
        idx_rt_conflict_pct = (
            header.index("rt_conflict_pct") if "rt_conflict_pct" in header else None
        )
        idx_engine_score_pct = (
            header.index("engine_score_pct") if "engine_score_pct" in header else None
        )

        abd_indices = []
        for sn in sample_names:
            if sn in header:
                abd_indices.append(header.index(sn))
            else:
                abd_indices.append(-1)

        for row in reader:
            if idx_ppg is None or idx_ppg >= len(row):
                continue
            ppg_val = row[idx_ppg]
            if not any(ppg_val.startswith(p) for p in site_prefixes):
                continue

            glycan_name = (
                row[idx_glycan]
                if idx_glycan is not None and len(row) > idx_glycan
                else ""
            )
            if not glycan_name:
                continue

            for k, col_i in enumerate(abd_indices):
                if col_i < 0 or col_i >= len(row):
                    continue
                try:
                    val = float(row[col_i]) if row[col_i] else 0.0
                except ValueError:
                    val = 0.0
                glycan_to_values[glycan_name][k] += val

            # Collect score percentiles and composite per glycan
            for idx, key in [
                (idx_composite, "composite"),
                (idx_depth_pct, "depth"),
                (idx_rt_conflict_pct, "rt_conflict"),
                (idx_engine_score_pct, "engine_score"),
            ]:
                if idx is not None and idx < len(row) and row[idx]:
                    try:
                        glycan_to_scores[glycan_name][key].append(float(row[idx]))
                    except ValueError:
                        pass

    # Recompute composite scores in-memory when custom weights are provided
    recompute = w_depth is not None and w_conflict is not None and w_byonic is not None
    if recompute:
        w_sum = w_depth + w_conflict + w_byonic
        for glycan_scores in glycan_to_scores.values():
            d_list = glycan_scores.get("depth", [])
            c_list = glycan_scores.get("rt_conflict", [])
            e_list = glycan_scores.get("engine_score", [])
            n = max(len(d_list), len(c_list), len(e_list))
            if n == 0:
                continue
            recomputed = []
            for i in range(n):
                d = d_list[i] if i < len(d_list) else 0.5
                c = c_list[i] if i < len(c_list) else 0.5
                e = e_list[i] if i < len(e_list) else 0.5
                raw = w_depth * d + w_conflict * c + w_byonic * e
                recomputed.append(raw / w_sum if w_sum > 0 else 0.0)
            glycan_scores["composite"] = recomputed

    return {
        "data": dict(glycan_to_values),
        "condition_names": condition_names,
        "sample_names": sample_names,
        "composite_scores": {k: dict(v) for k, v in glycan_to_scores.items()},
    }


@router.get("/{analysis_id}/params")
async def get_analysis_params(analysis_id: int, db: AsyncSession = Depends(get_db)):
    """Get saved parameters for an analysis."""
    stmt = select(AnalysisInfo).where(AnalysisInfo.id == analysis_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if record.parameters:
        return json.loads(record.parameters)
    return {}
