"""API endpoints for persisting user settings (column header sets, etc.)."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter

from app.schemas.analysis import (
    ColumnHeaderSet,
    BYONIC_HEADER_SET,
    MSFRAGGER_HEADER_SET,
)

logger = logging.getLogger(__name__)
router = APIRouter()

SETTINGS_DIR = Path(__file__).resolve().parent.parent.parent / "settings"
HEADER_SETS_FILE = SETTINGS_DIR / "column_header_sets.json"

# Customized set defaults to Byonic values
_CUSTOM_HEADER_SET = ColumnHeaderSet(
    **{**BYONIC_HEADER_SET.model_dump(), "name": "Customized"}
)

_DEFAULTS: list[ColumnHeaderSet] = [
    _CUSTOM_HEADER_SET,
    BYONIC_HEADER_SET,
    MSFRAGGER_HEADER_SET,
]


def _read_header_sets() -> list[ColumnHeaderSet]:
    """Load header sets from the JSON file, falling back to defaults."""
    if HEADER_SETS_FILE.is_file():
        try:
            raw = json.loads(HEADER_SETS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list) and len(raw) >= 2:
                defaults_by_name = {d.name: d for d in _DEFAULTS}
                result: list[ColumnHeaderSet] = []
                for item in raw:
                    name = item.get("name", "")
                    base = defaults_by_name.get(name, ColumnHeaderSet())
                    merged = {**base.model_dump(), **item}
                    result.append(ColumnHeaderSet(**merged))
                return result
        except Exception as exc:
            logger.warning("Failed to read header sets file: %s", exc)
    return [hs.model_copy() for hs in _DEFAULTS]


def _write_header_sets(header_sets: list[ColumnHeaderSet]) -> None:
    """Save header sets to the JSON file."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    data = [hs.model_dump() for hs in header_sets]
    HEADER_SETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@router.get("/header-sets", response_model=list[ColumnHeaderSet])
async def get_header_sets():
    """Return the current column header sets."""
    return _read_header_sets()


@router.put("/header-sets", response_model=list[ColumnHeaderSet])
async def save_header_sets(header_sets: list[ColumnHeaderSet]):
    """Persist column header sets to disk and return the saved values."""
    _write_header_sets(header_sets)
    return header_sets
