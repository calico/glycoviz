import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.api import analysis, export, fasta, foldchange, glycan, heatmap, upload
from app.api import settings as settings_api

EXAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "example_data"

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
    app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
    app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
    app.include_router(glycan.router, prefix="/api/glycan", tags=["glycan"])
    app.include_router(foldchange.router, prefix="/api/foldchange", tags=["foldchange"])
    app.include_router(heatmap.router, prefix="/api/heatmap", tags=["heatmap"])
    app.include_router(fasta.router, prefix="/api/fasta", tags=["fasta"])
    app.include_router(export.router, prefix="/api/export", tags=["export"])

    @app.on_event("startup")
    async def startup():
        try:
            from app.db.session import _get_engine
            from app.models.analysis import Base

            engine = _get_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as exc:
            logger.warning("Database not available at startup: %s", exc)
            logger.warning(
                "DB-dependent endpoints will fail until the database is reachable."
            )

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/example-data/{filename}")
    async def download_example(filename: str):
        filepath = EXAMPLE_DATA_DIR / filename
        if not filepath.is_file() or not filepath.resolve().is_relative_to(
            EXAMPLE_DATA_DIR.resolve()
        ):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(
            filepath, filename=filename, media_type="application/octet-stream"
        )

    return app


app = create_app()
