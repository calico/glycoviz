from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Glycan Analysis API"
    debug: bool = False

    # Database — defaults to local SQLite for development.
    # Override with GLYCAN_DATABASE_URL for PostgreSQL in production.
    database_url: str = "sqlite+aiosqlite:///./glycan_analysis.db"

    # File storage
    upload_dir: str = "uploads"
    fasta_dir: str = "fasta"
    max_upload_size_mb: int = 500

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_prefix": "GLYCAN_", "env_file": ".env"}


settings = Settings()
