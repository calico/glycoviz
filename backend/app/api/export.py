import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.config import settings

router = APIRouter()


def _find_file(analysis_id: str, suffix: str) -> Path:
    """Locate a file matching the analysis_id and suffix pattern."""
    upload_dir = Path(settings.upload_dir)
    candidates = list(upload_dir.glob(f"*{analysis_id}*{suffix}"))
    if not candidates:
        raise HTTPException(
            status_code=404, detail=f"File not found: *{analysis_id}*{suffix}"
        )
    return candidates[0]


@router.get("/{analysis_id}/results")
async def export_results(analysis_id: str):
    """Export analysis results as CSV."""
    csv_path = _find_file(analysis_id, "_results.csv")
    return FileResponse(
        path=str(csv_path),
        media_type="text/csv",
        filename=csv_path.name,
    )


@router.get("/{analysis_id}/zip")
async def export_zip(analysis_id: str):
    """Export all analysis files as ZIP."""
    upload_dir = Path(settings.upload_dir)

    # Collect all files that belong to this analysis
    files_to_bundle: list[Path] = []

    # Results CSV
    results_candidates = list(upload_dir.glob(f"*{analysis_id}*_results.csv"))
    files_to_bundle.extend(results_candidates)

    # QC CSV
    qc_candidates = list(upload_dir.glob(f"*{analysis_id}*_qc.csv"))
    files_to_bundle.extend(qc_candidates)

    # Global JSON
    global_candidates = list(upload_dir.glob(f"*{analysis_id}*_global.json"))
    files_to_bundle.extend(global_candidates)

    if not files_to_bundle:
        raise HTTPException(status_code=404, detail="No analysis files found to export")

    # Create ZIP in memory
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in files_to_bundle:
            zf.write(file_path, arcname=file_path.name)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=analysis_{analysis_id}.zip"
        },
    )
