"""Shared fixtures for the GlycoViz test suite."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_csv(tmp_path: Path):
    """Factory fixture: write rows to a temporary CSV and return its path."""

    def _write(header: list[str], rows: list[list[str]]) -> str:
        fp = tmp_path / "data.csv"
        with fp.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)
        return str(fp)

    return _write
