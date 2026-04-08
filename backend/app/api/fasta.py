import json
import os
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings

router = APIRouter()


@router.get("/list")
async def list_fasta_files():
    """List available FASTA files."""
    fasta_dir = Path(settings.fasta_dir)
    if not fasta_dir.exists():
        return {"files": []}

    files = sorted(p.name for p in fasta_dir.glob("*.fasta"))
    return {"files": files}


@router.post("/upload")
async def upload_fasta(file: UploadFile = File(...)):
    """Upload a FASTA file."""
    os.makedirs(settings.fasta_dir, exist_ok=True)

    filename = file.filename or "unknown.fasta"
    dest = Path(settings.fasta_dir) / filename

    if dest.exists():
        raise HTTPException(
            status_code=409, detail=f"FASTA file '{filename}' already exists"
        )

    content = await file.read()
    dest.write_bytes(content)

    return {"status": "ok", "filename": filename}


@router.post("/remap")
async def get_remap_data(
    analysis_id: str, ref_condition: str, comp_condition: str, remap_fasta: str
):
    """Get FASTA remap data."""
    fasta_dir = Path(settings.fasta_dir)
    map_file = fasta_dir / f"{Path(remap_fasta).stem}.mapfasta.json"

    if not map_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Mapping file not found: {map_file.name}"
        )

    try:
        mapping_data = json.loads(map_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to parse mapping file: {exc}"
        )

    return {
        "analysis_id": analysis_id,
        "ref_condition": ref_condition,
        "comp_condition": comp_condition,
        "remap_fasta": remap_fasta,
        "mapping": mapping_data,
    }
