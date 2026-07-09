"""Excel/TSV file reader for extracting abundance columns and converting formats.

This is a Python 3.11+ port of the legacy ``read_excel_header.py``.  It reads
Excel (.xlsx / .xls) and delimited-text (.tsv / .csv) data files and exposes
helpers for normalization:

* ``read_abundance_columns`` – return the list of abundance column names found
  in the first row of a file.
* ``normalize_to_xlsx`` – universal file normalizer (all formats → .xlsx with
  canonical headers).
* ``ensure_placeholder_columns`` – add missing placeholder columns generically.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import TYPE_CHECKING

import openpyxl

if TYPE_CHECKING:
    pass  # reserved for future type-only imports

__all__ = [
    "read_abundance_columns",
    "read_all_headers",
    "build_header_remap",
    "normalize_to_csv",
    "normalize_to_xlsx",
    "ensure_glycan_composition",
    "ensure_placeholder_columns",
]

# ---------------------------------------------------------------------------
# Column-name constants (mirrored from the legacy script)
# ---------------------------------------------------------------------------

# Byonic-style abundance prefix
_ABUNDANCE_PREFIX = "Abundances (Grouped): "

# Canonical Byonic column names (the "target" names after remapping).
_CANONICAL_NAMES: dict[str, str] = {
    "protein_accessions": "Protein Accessions",
    "master_protein_descriptions": "Master Protein Descriptions",
    "fdr_prefix": "FDR 2D (by Search Engine)",
    "glycan_composition": "Glycan Composition",
    "position_in_protein": "Position in Protein",
    "sequence": "Sequence",
    "modifications": "Modifications (all possible sites)",
    "modifications_fallback": "Modifications",
    "retention_time": "Top Apex RT [min]",
    "engine_score_prefix": "Byonic Score (",
}


def build_header_remap(header_set: "ColumnHeaderSet") -> dict[str, str]:
    """Build a header remap dict from a :class:`ColumnHeaderSet`.

    For each field in ``_CANONICAL_NAMES``, if the header set's value differs
    from the canonical name (and is non-empty), add a mapping from the header
    set's value to the canonical name.
    """
    from app.schemas.analysis import ColumnHeaderSet  # noqa: F811 – deferred import

    remap: dict[str, str] = {}
    for field, canonical in _CANONICAL_NAMES.items():
        value = getattr(header_set, field, "")
        if value and value != canonical:
            remap[value] = canonical
    return remap


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_abundance_columns(
    filepath: str,
    abundance_prefixes: list[str] | None = None,
) -> list[str]:
    """Return the abundance column names found in the first header row of *filepath*.

    Supported formats:

    * **.xlsx** – columns whose name starts with one of *abundance_prefixes*
      (default ``["Abundances (Grouped): "]``).
    * **.xls** – same logic, read via *xlrd* (which still supports the legacy
      BIFF format).
    * **.tsv** – columns whose name ends with ``" Intensity"`` (MSFragger
      convention).
    * **.csv** – same as TSV but comma-delimited.

    Parameters
    ----------
    filepath:
        Path to the data file.
    abundance_prefixes:
        Optional list of prefixes to try when detecting abundance columns.
        Each prefix is tried in order; the first one that finds at least one
        column wins.  Defaults to ``["Abundances (Grouped): "]``.

    Returns
    -------
    list[str]
        Ordered list of matching column names (may be empty if none match).

    Raises
    ------
    ValueError
        If the file extension is not one of the supported types.
    FileNotFoundError
        If *filepath* does not exist.
    """
    ext = Path(filepath).suffix.lower()
    prefixes = abundance_prefixes or [_ABUNDANCE_PREFIX]

    if ext == ".xlsx":
        return _read_abundance_from_xlsx(filepath, prefixes)
    if ext == ".xls":
        return _read_abundance_from_xls(filepath, prefixes)
    if ext in {".tsv", ".csv"}:
        delimiter = "\t" if ext == ".tsv" else ","
        return _read_abundance_from_delimited(filepath, delimiter=delimiter, prefixes=prefixes)

    raise ValueError(
        f"Unsupported file type '{ext}'. Expected one of: .xlsx, .xls, .tsv, .csv"
    )


def read_all_headers(filepath: str) -> list[str]:
    """Return every column header from the first row of *filepath*."""
    ext = Path(filepath).suffix.lower()

    if ext == ".xlsx":
        from python_calamine import CalamineWorkbook
        wb = CalamineWorkbook.from_path(filepath)
        sheet = wb.get_sheet_by_index(0)
        data = sheet.to_python(skip_empty_area=False)
        if not data:
            return []
        return [str(cell) if cell is not None else "" for cell in data[0]]

    if ext == ".xls":
        import xlrd  # type: ignore[import-untyped]

        book = xlrd.open_workbook(filepath)
        sheet = book.sheet_by_index(0)
        return [str(sheet.cell_value(0, c)) for c in range(sheet.ncols)]

    if ext in {".tsv", ".csv"}:
        delimiter = "\t" if ext == ".tsv" else ","
        with open(filepath, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter=delimiter, quotechar='"')
            row = next(reader, None)
        return list(row) if row else []

    return []


def normalize_to_xlsx(
    src_path: str,
    dest_path: str,
    header_remap: dict[str, str | None] | None = None,
) -> bool:
    """Read any tabular file, apply header remapping, and write as ``.xlsx``.

    This is the universal file normalizer.  It handles ``.xlsx``, ``.xls``,
    ``.tsv``, ``.csv``, and ``.txt`` files.  After normalization, every file
    has canonical Byonic header names.

    Parameters
    ----------
    src_path:
        Path to the source file (any supported tabular format).
    dest_path:
        Destination ``.xlsx`` path.
    header_remap:
        Unified mapping from source column names to canonical names.
        Entries mapped to ``None`` cause the column to be **removed**.

    Returns
    -------
    bool
        ``True`` if any header was changed or columns removed,
        ``False`` otherwise.
    """
    remap = header_remap or {}
    ext = Path(src_path).suffix.lower()

    # --- read rows ----------------------------------------------------------
    rows: list[list[object]] = []

    if ext == ".xlsx":
        from python_calamine import CalamineWorkbook
        wb = CalamineWorkbook.from_path(src_path)
        sheet = wb.get_sheet_by_index(0)
        for row in sheet.to_python(skip_empty_area=False):
            rows.append([cell if cell is not None else "" for cell in row])

    elif ext == ".xls":
        import xlrd  # type: ignore[import-untyped]

        wb_xls = xlrd.open_workbook(src_path)
        sheet = wb_xls.sheet_by_index(0)
        for r in range(sheet.nrows):
            rows.append(sheet.row_values(r))

    elif ext in {".tsv", ".csv", ".txt"}:
        delimiter = "\t" if ext in {".tsv", ".txt"} else ","
        with open(src_path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter=delimiter, quotechar='"')
            for raw_row in reader:
                rows.append(list(raw_row))
    else:
        raise ValueError(f"Unsupported file type '{ext}'")

    if not rows:
        return False

    # --- remap headers ------------------------------------------------------
    raw_headers = [str(h) for h in rows[0]]
    mapped_headers = list(raw_headers)
    changed = False

    # Identify columns to remove (mapped to None) and columns to rename
    indices_to_remove: list[int] = []
    for i, name in enumerate(raw_headers):
        if name in remap:
            target = remap[name]
            if target is None:
                indices_to_remove.append(i)
                changed = True
            else:
                mapped_headers[i] = target
                changed = True

    # Remove columns marked for deletion (reverse order to preserve indices)
    if indices_to_remove:
        for row in rows:
            for idx in reversed(indices_to_remove):
                if idx < len(row):
                    row.pop(idx)
        for idx in reversed(indices_to_remove):
            if idx < len(mapped_headers):
                mapped_headers.pop(idx)

    if not changed and ext == ".xlsx":
        # No changes needed and already xlsx — skip rewriting
        return False

    # --- write xlsx ---------------------------------------------------------
    rows[0] = mapped_headers
    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    assert ws_out is not None
    ws_out.title = "Sheet1"

    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row, start=1):
            ws_out.cell(row=r_idx, column=c_idx, value=val)

    wb_out.save(dest_path)
    return True


def normalize_to_csv(
    src_path: str,
    dest_path: str,
    header_remap: dict[str, str | None] | None = None,
) -> bool:
    """Read any tabular file, apply header remapping, and write as ``.csv``.

    This is the universal file normalizer.  It handles ``.xlsx``, ``.xls``,
    ``.tsv``, ``.csv``, and ``.txt`` files.  After normalization, every file
    has canonical Byonic header names in CSV format.

    Parameters
    ----------
    src_path:
        Path to the source file (any supported tabular format).
    dest_path:
        Destination ``.csv`` path.
    header_remap:
        Unified mapping from source column names to canonical names.
        Entries mapped to ``None`` cause the column to be **removed**.

    Returns
    -------
    bool
        ``True`` if any header was changed or columns removed,
        ``False`` otherwise.
    """
    remap = header_remap or {}
    ext = Path(src_path).suffix.lower()

    # --- read rows ----------------------------------------------------------
    rows: list[list[object]] = []

    if ext == ".xlsx":
        from python_calamine import CalamineWorkbook
        wb = CalamineWorkbook.from_path(src_path)
        sheet = wb.get_sheet_by_index(0)
        for row in sheet.to_python(skip_empty_area=False):
            rows.append([cell if cell is not None else "" for cell in row])

    elif ext == ".xls":
        import xlrd  # type: ignore[import-untyped]

        wb_xls = xlrd.open_workbook(src_path)
        sheet = wb_xls.sheet_by_index(0)
        for r in range(sheet.nrows):
            rows.append(sheet.row_values(r))

    elif ext in {".tsv", ".csv", ".txt"}:
        delimiter = "\t" if ext in {".tsv", ".txt"} else ","
        with open(src_path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter=delimiter, quotechar='"')
            for raw_row in reader:
                rows.append(list(raw_row))
    else:
        raise ValueError(f"Unsupported file type '{ext}'")

    if not rows:
        return False

    # --- remap headers ------------------------------------------------------
    raw_headers = [str(h) for h in rows[0]]
    mapped_headers = list(raw_headers)
    changed = False

    # Identify columns to remove (mapped to None) and columns to rename
    indices_to_remove: list[int] = []
    for i, name in enumerate(raw_headers):
        if name in remap:
            target = remap[name]
            if target is None:
                indices_to_remove.append(i)
                changed = True
            else:
                mapped_headers[i] = target
                changed = True

    # Remove columns marked for deletion (reverse order to preserve indices)
    if indices_to_remove:
        for row in rows:
            for idx in reversed(indices_to_remove):
                if idx < len(row):
                    row.pop(idx)
        for idx in reversed(indices_to_remove):
            if idx < len(mapped_headers):
                mapped_headers.pop(idx)

    if not changed and ext == ".csv":
        # No changes needed and already csv — skip rewriting
        return False

    # --- write csv ----------------------------------------------------------
    rows[0] = mapped_headers
    with open(dest_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)
    return True


def ensure_glycan_composition(filepath: str) -> bool:
    """Add a ``Glycan Composition`` column if the file lacks one.

    Reads the CSV at *filepath*.  If the header row already contains
    ``"Glycan Composition"`` the file is left untouched and ``False`` is
    returned.

    Otherwise the function looks for an ``"Assigned Modifications"`` column,
    runs each value through :pymethod:`MassConverter.get_glycan_comp` to
    synthesize glycan composition strings, appends the new column, and
    overwrites the file in-place.

    Returns ``True`` when a column was added, ``False`` otherwise.
    """
    from app.core.mass_converter import MassConverter  # type: ignore[import-untyped]

    headers = read_all_headers(filepath)

    if "Glycan Composition" in headers:
        return False

    # Find the modifications column (may have been remapped)
    mods_col_name: str | None = None
    for candidate in ("Assigned Modifications", "Modifications (all possible sites)"):
        if candidate in headers:
            mods_col_name = candidate
            break

    if mods_col_name is None:
        return False

    idx_mods = headers.index(mods_col_name)

    mass_file = str(
        Path(__file__).resolve().parent.parent.parent
        / "example_data"
        / "glycan_masses.csv"
    )
    mass_converter = MassConverter(mass_file)

    # Read all rows, append new column, write back
    rows: list[list[str]] = []
    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header_row = next(reader)
        header_row.append("Glycan Composition")
        rows.append(header_row)
        for row in reader:
            glycan_comp = ""
            try:
                mods_val = row[idx_mods] if idx_mods < len(row) else ""
                if mods_val:
                    glycan_comp = mass_converter.get_glycan_comp(mods_val)
            except Exception:
                glycan_comp = ""
            row.append(glycan_comp)
            rows.append(row)

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)
    return True


# Placeholder columns: (canonical_header_name, default_value)
_PLACEHOLDER_COLUMNS: list[tuple[str, object]] = [
    ("DeltaM [ppm] ", 0),
    ("Position in Protein", 1),
    ("Modifications (all possible sites)", ""),
    ("Byonic Score (", 1000),
    ("Master Protein Descriptions", ""),
    ("FDR 2D (by Search Engine)", 0),
]


def ensure_placeholder_columns(filepath: str) -> bool:
    """Add missing placeholder columns to the CSV at *filepath*.

    For each entry in ``_PLACEHOLDER_COLUMNS``, if the header is not already
    present (exact match or prefix match), a new column is appended with the
    given default value for every data row.

    Returns ``True`` when at least one column was added, ``False`` otherwise.
    """
    headers = read_all_headers(filepath)

    to_add: list[tuple[str, object]] = []
    for col_name, default_val in _PLACEHOLDER_COLUMNS:
        # Check exact match or prefix match (for columns like "DeltaM [ppm] ...")
        found = any(h == col_name or h.startswith(col_name) for h in headers)
        if not found:
            to_add.append((col_name, default_val))

    if not to_add:
        return False

    # Read all rows, append new columns, write back
    rows: list[list[str]] = []
    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header_row = next(reader)
        for col_name, _ in to_add:
            header_row.append(col_name)
        rows.append(header_row)
        for row in reader:
            for _, default_val in to_add:
                row.append(str(default_val))
            rows.append(row)

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)
    return True


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _read_abundance_from_xlsx(filepath: str, prefixes: list[str]) -> list[str]:
    """Extract abundance columns from an ``.xlsx`` file."""
    headers = read_all_headers(filepath)
    for prefix in prefixes:
        cols = [name for name in headers if name.startswith(prefix)]
        if cols:
            return cols
    return []


def _read_abundance_from_xls(filepath: str, prefixes: list[str]) -> list[str]:
    """Extract abundance columns from a legacy ``.xls`` (BIFF) file using *xlrd*."""
    import xlrd  # xlrd 2.x still supports .xls (BIFF) format

    wb = xlrd.open_workbook(filepath)
    sheet = wb.sheet_by_index(0)
    for prefix in prefixes:
        cols = [
            str(cell) for cell in sheet.row_values(0) if str(cell).startswith(prefix)
        ]
        if cols:
            return cols
    return []


def _read_abundance_from_delimited(
    filepath: str, *, delimiter: str, prefixes: list[str] | None = None,
) -> list[str]:
    """Extract abundance columns from a TSV or CSV file."""
    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=delimiter, quotechar='"')
        headers = next(reader, None)

    if headers is None:
        return []

    # Try prefix matching first (works for all formats including converted xlsx)
    for prefix in (prefixes or [_ABUNDANCE_PREFIX]):
        cols = [name for name in headers if name.startswith(prefix)]
        if cols:
            return cols

    # Fall back to suffix matching (MSFragger convention)
    return [name for name in headers if name.endswith(" Intensity")]
