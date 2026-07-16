"""Integration test: upload an example file, run analysis, verify, and clean up.

Uses an in-memory SQLite database and a temporary upload directory so no
persistent state is left behind.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.analysis import Base

EXAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "example_data"
BYONIC_FILE = EXAMPLE_DIR / "example_input_byonic.xlsx"


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
async def test_app(tmp_path):
    """Create a FastAPI app backed by an in-memory DB and temp upload dir."""
    # Patch settings BEFORE importing modules that read them at import time
    import app.config as cfg
    import app.db.session as sess

    original_settings = cfg.settings
    original_engine = sess._engine
    original_session = sess._async_session

    # Override settings
    cfg.settings = cfg.Settings(
        database_url="sqlite+aiosqlite://",  # in-memory
        upload_dir=str(tmp_path / "uploads"),
        fasta_dir=str(tmp_path / "fasta"),
    )
    (tmp_path / "uploads").mkdir()
    (tmp_path / "fasta").mkdir()

    # Reset engine/session so they pick up the new DB URL
    sess._engine = None
    sess._async_session = None

    from app.main import create_app

    application = create_app()

    # Create tables in the in-memory DB
    engine = sess._get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield application, tmp_path

    # Teardown: restore original settings and clean up
    cfg.settings = original_settings
    sess._engine = original_engine
    sess._async_session = original_session


@pytest.fixture()
async def client(test_app):
    application, _ = test_app
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.anyio
@pytest.mark.skipif(not BYONIC_FILE.exists(), reason="Example data not found")
async def test_full_byonic_workflow(client, test_app):
    """Upload the Byonic example, run analysis, verify outputs, then delete."""
    _, tmp_path = test_app
    upload_dir = tmp_path / "uploads"

    # 1. Upload the example file
    with open(BYONIC_FILE, "rb") as f:
        resp = await client.post(
            "/api/upload/data-file",
            files={"file": ("example_input_byonic.xlsx", f, "application/octet-stream")},
        )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    upload_data = resp.json()
    file_id = upload_data["file_id"]
    columns = upload_data["columns"]
    assert len(columns) > 0, "No abundance columns detected"

    # 2. Assign conditions (split columns into two groups)
    half = len(columns) // 2
    conditions = {}
    for i, col in enumerate(columns):
        conditions[col] = "Control" if i < half else "Treatment"

    # 3. Run analysis
    resp = await client.post(
        "/api/analysis/run",
        json={
            "file_id": file_id,
            "name": "Integration Test",
            "conditions": conditions,
            "fdr_threshold": 0.01,
            "byonic_score": 10,
            "ppm_threshold": 10,
            "peptide_length": 7,
            "min_count": 1,
            "export_filter": "all",
            "w_depth": 0.4,
            "w_conflict": 0.4,
            "w_byonic": 0.2,
        },
    )
    assert resp.status_code == 200, f"Analysis failed: {resp.text}"
    result = resp.json()
    analysis_id = result["analysis_id"]
    assert analysis_id is not None

    # 4. Verify analysis is listed
    resp = await client.get("/api/analysis/list")
    assert resp.status_code == 200
    analyses = resp.json()
    assert any(a["id"] == analysis_id for a in analyses)

    # 5. Verify analysis detail
    resp = await client.get(f"/api/analysis/{analysis_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["name"] == "Integration Test"
    assert "qc_stats" in detail
    assert detail["qc_stats"]["total_proteins"] > 0

    # 6. Verify sites
    resp = await client.get(f"/api/analysis/{analysis_id}/sites")
    assert resp.status_code == 200
    sites = resp.json()
    assert len(sites) > 0

    # 7. Verify abundance data
    resp = await client.get(
        f"/api/analysis/{analysis_id}/abundance",
        params={"mode": "glycan", "metric": "abundance"},
    )
    assert resp.status_code == 200
    abd = resp.json()
    assert len(abd["data"]) > 0

    # 8. Verify per-protein abundance with custom weights
    first_site = sites[0]
    resp = await client.get(
        f"/api/analysis/{analysis_id}/protein/{first_site['accession']}/abundance",
        params={
            "mode": "glycan",
            "metric": "abundance",
            "site": first_site["site"],
            "w_depth": 0.5,
            "w_conflict": 0.0,
            "w_byonic": 0.5,
        },
    )
    assert resp.status_code == 200
    protein_abd = resp.json()
    assert len(protein_abd) > 0

    # 9. Verify fold change
    resp = await client.post(
        "/api/foldchange/compute",
        json={
            "analysis_id": str(analysis_id),
            "reference_condition": "Control",
            "comparison_condition": "Treatment",
        },
    )
    assert resp.status_code == 200
    fc = resp.json()
    assert "glycan_list" in fc
    assert "fc" in fc

    # 10. Clean up: delete the analysis
    resp = await client.delete(f"/api/analysis/{analysis_id}")
    assert resp.status_code == 204

    # Verify it's gone
    resp = await client.get("/api/analysis/list")
    assert resp.status_code == 200
    assert not any(a["id"] == analysis_id for a in resp.json())

    # Verify generated files are cleaned up
    result_files = list(upload_dir.glob("*_results*"))
    assert len(result_files) == 0, f"Leftover result files: {result_files}"
