import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clustering import ClusterParams, cluster_data
from app.db.session import get_db
from app.models.analysis import AnalysisInfo
from app.schemas.heatmap import ClusterRequest, ClusterResult

router = APIRouter()


async def _get_analysis_file_stem(analysis_id: int, db: AsyncSession) -> str:
    """Look up the upload file UUID from the DB analysis record."""
    record = await db.get(AnalysisInfo, analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    # record.url is like "uploads/<uuid>_results.csv"
    url_path = Path(record.url)
    stem = url_path.stem  # e.g. "<uuid>_results"
    # Remove the "_results" suffix to get just the UUID
    file_id = stem.replace("_results", "")
    return file_id


def _find_proportions_csv(file_id: str) -> Path:
    """Locate the proportions CSV for the given file_id (UUID)."""
    upload_dir = Path(settings.upload_dir)
    # Direct path: proportions_table_{file_id}.csv
    direct = upload_dir / f"proportions_table_{file_id}.csv"
    if direct.exists():
        return direct
    # Fallback: check subdirectory (old bug created this path)
    fallback_dir = upload_dir / f"proportions_table_uploads"
    if fallback_dir.is_dir():
        candidate = fallback_dir / f"{file_id}.csv"
        if candidate.exists():
            return candidate
    raise HTTPException(
        status_code=404, detail=f"Proportions CSV not found for file_id={file_id}"
    )


def _parse_proportions_csv(
    csv_path: Path,
) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    """Read the proportions CSV, extracting metadata rows and data.

    Returns:
        (data_df, sample_names, conditions, unique_conditions)
        where data_df has Gene/Protein as first two columns and Est_Prop columns.
    """
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 6:
        raise HTTPException(status_code=400, detail="Proportions CSV has too few rows")

    header = rows[0]  # Gene, Protein, Est_Prop1, ..., Est_PropN
    sample_names = rows[1]  # sample name per Est column
    conditions = rows[2]  # condition label per Est column
    unique_conditions = rows[3]  # unique condition names
    # rows[4] = condition-to-replicate mapping
    data_rows = rows[5:]  # actual data

    # Build DataFrame from data rows
    df = pd.DataFrame(data_rows, columns=header)

    # Convert Est_Prop columns to numeric
    est_cols = [c for c in df.columns if c.startswith("Est_Prop")]
    for col in est_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df, sample_names, conditions, unique_conditions


@router.post("/cluster", response_model=ClusterResult)
async def cluster_for_heatmap(
    params: ClusterRequest, db: AsyncSession = Depends(get_db)
):
    """Run clustering and return heatmap data."""
    file_id = await _get_analysis_file_stem(params.analysis_id, db)
    prop_path = _find_proportions_csv(file_id)

    df, sample_names, conditions, unique_conditions = _parse_proportions_csv(prop_path)

    # Extract only Est_Prop columns for clustering
    est_cols = [c for c in df.columns if c.startswith("Est_Prop")]
    if not est_cols:
        raise HTTPException(
            status_code=400, detail="No Est_Prop columns found in proportions CSV"
        )

    if "Protein" in df.columns:
        row_labels = [str(v) for v in df["Protein"].fillna("unknown")]
    else:
        row_labels = [str(i) for i in range(len(df))]

    numeric_df = df[est_cols].copy()
    total_quantified = len(numeric_df)

    # Filter: keep only rows with complete data across ALL Est columns (like R complete.cases)
    complete_mask = numeric_df.notna().all(axis=1)
    numeric_df = numeric_df[complete_mask]
    row_labels = [
        row_labels[i] for i in range(len(complete_mask)) if complete_mask.iloc[i]
    ]

    if numeric_df.empty:
        raise HTTPException(
            status_code=400, detail="No complete data rows for clustering"
        )

    # Build column labels from condition names and sample names
    col_labels = []
    for i, col in enumerate(est_cols):
        if i < len(conditions) and conditions[i]:
            label = conditions[i]
            if i < len(sample_names) and sample_names[i]:
                label = f"{conditions[i]}_{sample_names[i]}"
        elif i < len(sample_names) and sample_names[i]:
            label = sample_names[i]
        else:
            label = col
        col_labels.append(label)

    # Set column labels on the dataframe
    numeric_df.columns = col_labels
    numeric_df.index = row_labels

    # Order by condition if requested (and not clustering columns)
    if params.order_by_condition and not params.cluster_by_column:
        # Sort columns by their condition label
        sorted_cols = sorted(numeric_df.columns, key=lambda c: c)
        numeric_df = numeric_df[sorted_cols]

    # Build ClusterParams from the request
    cluster_params = ClusterParams(
        distance_metric=params.distance_metric,
        linkage_method=params.linkage_method,
        use_kmeans=params.use_kmeans,
        k_clusters=params.k_clusters,
        clr_transform=params.clr_transform,
        zscore_transform=params.zscore_transform,
        meaningful_change_cutoff=params.meaningful_change_cutoff,
    )

    # Determine colorbar title and zmid based on transforms (match legacy JS)
    if params.clr_transform and params.zscore_transform:
        colorbar_title = "Centered Log Ratio Z Score"
        zmid: float | None = 0.0
    elif params.clr_transform:
        colorbar_title = "Centered Log Ratio Intensity"
        zmid = 0.0
    elif params.zscore_transform:
        colorbar_title = "Z Score"
        zmid = 0.0
    else:
        colorbar_title = "Proportion"
        zmid = None

    # If user doesn't want to cluster rows or columns, handle manually
    if (
        not params.cluster_by_row
        and not params.cluster_by_column
        and not params.use_kmeans
    ):
        # No clustering at all — just return the data as-is with transforms applied
        matrix = numeric_df.to_numpy(dtype=np.float64)
        row_labels_nc = list(numeric_df.index)
        if params.clr_transform:
            from app.core.clustering import clr_transform as _clr

            matrix = _clr(matrix)
        if params.meaningful_change_cutoff > 0:
            threshold = np.log(params.meaningful_change_cutoff)
            keep_mask = np.nanmax(np.abs(matrix), axis=1) > threshold
            if not np.any(keep_mask):
                raise HTTPException(
                    status_code=400, detail="Filtering for fold change left no rows."
                )
            matrix = matrix[keep_mask]
            row_labels_nc = [row_labels_nc[i] for i, k in enumerate(keep_mask) if k]
        if params.zscore_transform:
            from app.core.clustering import zscore_normalize

            matrix = zscore_normalize(matrix)
        from app.core.clustering import _signif

        matrix = _signif(matrix, 4)
        return ClusterResult(
            heatmap_data=matrix.tolist(),
            row_labels=row_labels_nc,
            col_labels=list(numeric_df.columns),
            row_dendrogram=None,
            col_dendrogram=None,
            total_quantified=total_quantified,
            heatmap_count=len(row_labels_nc),
            zmid=zmid,
            colorbar_title=colorbar_title,
        )

    try:
        result = cluster_data(numeric_df, cluster_params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # If only clustering one axis, null out the other dendrogram
    row_dendro = result.row_dendrogram if params.cluster_by_row else None
    col_dendro = result.col_dendrogram if params.cluster_by_column else None

    return ClusterResult(
        heatmap_data=result.heatmap_data.tolist(),
        row_labels=result.row_labels,
        col_labels=result.col_labels,
        row_dendrogram=row_dendro,
        col_dendrogram=col_dendro,
        total_quantified=total_quantified,
        heatmap_count=len(result.row_labels),
        zmid=zmid,
        colorbar_title=colorbar_title,
    )
