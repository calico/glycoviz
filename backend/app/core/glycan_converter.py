"""Main glycan analysis engine.

Python 3.11+ port of the legacy monolithic ``glycan_converter.py``.  The
original ~700-line ``main()`` function has been decomposed into small, testable
helpers orchestrated by :func:`run_analysis`.

Key changes from the legacy code
---------------------------------
* ``openpyxl`` replaces ``xlrd`` (which dropped ``.xlsx`` support in v2).
* All I/O uses ``pathlib.Path`` for clarity and safety.
* ``collections.defaultdict`` usage is preserved where it simplifies
  aggregation; plain dicts with explicit initialisation are used everywhere
  else so that the data flow is easier to trace.
* Every public symbol carries full type annotations and a docstring.
"""

from __future__ import annotations

import csv
import json
import math
import logging
import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openpyxl

from app.core.glycan_lookup import (
    COMP_TO_NAME_DICT,
    GlycanComposition,
    get_glycan_composition_list,
    get_glycan_motif,
    glycan_name_old_to_new,
)
from app.core.statistics import (
    anova_pvalue,
    cv,
    mean,
    pvalue_from_ttest,
    std,
    std_error,
)
from app.core.glycan_validator import validate_glycans as _run_glycan_validator
from app.schemas.analysis import ColumnHeaderSet, BYONIC_HEADER_SET

__all__ = [
    "AnalysisFilters",
    "AnalysisResult",
    "run_analysis",
]

from app.core.glycan_lookup import composition_to_mass

from app.core.glycan_validator import clean_sequence, get_peplength_from_sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column-name constants (must match the Byonic / PD export conventions)
# ---------------------------------------------------------------------------

_GLYCAN_COL = "Glycan Composition"
_PROTEIN_COL = "Protein Accessions"
_MOD_POS_COL = "Position in Protein"
_MOD_IN_PEP_COL_PREFERRED = "Modifications (all possible sites)"
_MOD_IN_PEP_COL_FALLBACK = "Modifications"
_DESCRIPTION_COL = "Master Protein Descriptions"
_FDR_COL_PREFIX = "FDR 2D (by Search Engine)"
_BYONIC_COL_PREFIX = "Byonic Score ("
_PPM_COL_PREFIX = "DeltaM [ppm] "
_PEP_COL = "Sequence"

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AnalysisFilters:
    """User-supplied thresholds and options that govern which rows survive
    the QC filter pass and how results are exported."""

    fdr2d_threshold: float
    byonic_threshold: float
    ppm_threshold: float
    peplength_threshold: int
    export_filter: str  # "all" or "glycan"
    mincount_threshold: int
    abundance_type: str  # e.g. "Abundances (Grouped)"
    fdr_is_probability: bool = False
    w_depth: float = 0.4
    w_conflict: float = 0.4
    w_byonic: float = 0.2
    column_header_sets: list[ColumnHeaderSet] | None = None


@dataclass
class AnalysisResult:
    """Compact summary returned by :func:`run_analysis`."""

    output_file: str
    site_to_rows: dict[str, list[int]]
    statistics: dict[str, int]
    qc_output_file: str


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


def run_analysis(
    filepath: str,
    filters: AnalysisFilters,
    conditions: list[str],
) -> AnalysisResult:
    """Run the full glycan nomenclature-conversion and statistical analysis.

    This is the main orchestrator that replaces the legacy monolithic
    ``main()`` function.  It reads the input workbook, applies QC filters,
    converts glycan nomenclature, computes per-condition statistics, and
    writes several output artefacts (results CSV, site-table JSON, global-
    stats JSON, proportions CSV, conditions-map CSV, QC CSV).

    Parameters
    ----------
    filepath:
        Path to the input ``.xlsx`` (or ``.csv`` when the special
        ``single_protein`` workflow applies).
    filters:
        Threshold / export settings supplied by the user.
    conditions:
        Ordered list of condition labels — one per abundance column in the
        file.  Duplicates indicate biological replicates.

    Returns
    -------
    AnalysisResult
        Paths to the generated files together with summary statistics.
    """
    # single_protein CSV no longer needs xlsx conversion — CSV is now native
    print(f"[DEBUG] run_analysis called with filepath={filepath}")
    print(f"[DEBUG] filters={filters}")
    print(f"[DEBUG] conditions={conditions}")

    # ---- derive output paths from the input path --------------------------
    stem = Path(filepath).with_suffix("")
    output_file = str(stem) + "_results.csv"
    qc_output_file = str(stem) + "_qc.csv"
    site_table_meta_file = str(stem) + ".sites_table.json"
    meta_file_global = str(stem) + "_global.json"

    # File-id is the filename without extension (the upload UUID)
    file_id = Path(filepath).stem
    proportion_file = f"uploads/proportions_table_{file_id}.csv"
    condition_map_file = "uploads/conditions_biological_replicates_map.csv"

    # ---- open the input file ------------------------------------------------
    _input_fh = open(filepath, newline="", encoding="utf-8")
    _csv_reader = csv.reader(_input_fh)

    try:
        header_row = [str(cell) if cell else "" for cell in next(_csv_reader)]
        print(f"[DEBUG] header_row has {len(header_row)} columns")
        print(f"[DEBUG] first 10 headers: {header_row[:10]}")

        col_idx, matched_set = _resolve_with_header_sets(
            header_row,
            filters.abundance_type,
            filters.column_header_sets,
        )
        print(f"[DEBUG] matched header set: {matched_set.name}")
        rt_column_name = matched_set.retention_time
        print(
            f"[DEBUG] resolved column indices: glycan={col_idx.glycan}, protein={col_idx.protein}, "
            f"fdr2d={col_idx.fdr2d}, byonic={col_idx.byonic}, ppm={col_idx.ppm}, "
            f"peptide={col_idx.peptide}, abundance_indices={col_idx.abundance_indices}"
        )

        # ---- build extended header for the results CSV --------------------
        result_fields = list(header_row)
        result_fields += ["Protein---Position---Gene", "Converted Glycan Names"]
        result_fields += ["HexNAc", "Hex", "Fuc", "NeuAc", "NeuGc"]

        unique_conditions, condition_to_col_indices, idx_to_condition = _map_conditions(
            conditions, col_idx.abundance_indices
        )

        # Per-condition header groups
        for cond in unique_conditions:
            result_fields.append(f"{cond}: Valid Data Points")
        for cond in unique_conditions:
            result_fields.append(f"{cond}: Abundance")
        for cond in unique_conditions:
            result_fields.append(f"{cond}: std")
        for cond in unique_conditions:
            result_fields.append(f"{cond}: std_error")
        for cond in unique_conditions:
            result_fields.append(f"{cond}: cv")

        # Pairwise t-test headers
        for i in range(len(unique_conditions)):
            for j in range(i + 1, len(unique_conditions)):
                result_fields.append(
                    f"p-value:{unique_conditions[i]}_to_{unique_conditions[j]}"
                )

        # ANOVA headers (>2 conditions)
        if len(unique_conditions) > 2:
            result_fields.append("ANOVA_F-statistic")
            result_fields.append("ANOVA_P-value")

        # ---- initialise accumulators --------------------------------------
        rows: list[list[Any]] = []
        site_to_rows: dict[str, list[int]] = defaultdict(list)
        glycan_cache: dict[str, str] = {}

        n_abd_cols = len(col_idx.abundance_indices)
        abd_col_names = [header_row[i] for i in col_idx.abundance_indices]

        glycan_to_abd_replicates: dict[str, list[float]] = defaultdict(
            lambda: [0.0] * n_abd_cols
        )
        glycan_to_abd_conditions: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        motif_to_abd_replicates: dict[str, list[float]] = defaultdict(
            lambda: [0.0] * n_abd_cols
        )
        motif_to_abd_conditions: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        glycan_to_cnt_replicates: dict[str, list[int]] = defaultdict(
            lambda: [0] * n_abd_cols
        )
        glycan_to_cnt_conditions: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        motif_to_cnt_replicates: dict[str, list[int]] = defaultdict(
            lambda: [0] * n_abd_cols
        )
        motif_to_cnt_conditions: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        glycopep_to_abd_replicates: dict[str, list[float]] = defaultdict(
            lambda: [0.0] * n_abd_cols
        )
        condition_mean_and_stderr: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        result_row_number = 0
        result_glycopeptide_count = 0
        is_single_protein = "single_protein" in filepath

        total_rows_scanned = 0
        rows_skipped_peplength = 0
        rows_skipped_fdr = 0
        rows_skipped_byonic = 0
        rows_skipped_ppm = 0
        rows_skipped_mincount = 0
        rows_skipped_parse_error = 0

        # ---- iterate over data rows ---------------------------------------
        for row in _csv_reader:
            row_values = list(row)
            total_rows_scanned += 1

            # --- clean sequence in-place (strip modifications and flanking residues)
            if col_idx.peptide < len(row_values):
                row_values[col_idx.peptide] = clean_sequence(
                    str(row_values[col_idx.peptide])
                )

            # --- clean protein accession (keep first token, strip leading ">")
            if col_idx.protein < len(row_values):
                acc = str(row_values[col_idx.protein] or "").lstrip(">")
                if " " in acc:
                    acc = acc.split()[0]
                row_values[col_idx.protein] = acc

            # --- apply QC filters ------------------------------------------
            try:
                peplength_val = len(row_values[col_idx.peptide])
                fdr2d_val = float(row_values[col_idx.fdr2d])
                if filters.fdr_is_probability:
                    fdr2d_val = 1.0 - fdr2d_val
                byonic_val = float(row_values[col_idx.byonic])
                ppm_val = float(row_values[col_idx.ppm])
            except (TypeError, ValueError, IndexError):
                rows_skipped_parse_error += 1
                continue

            if peplength_val < filters.peplength_threshold:
                rows_skipped_peplength += 1
                continue
            if fdr2d_val > filters.fdr2d_threshold:
                rows_skipped_fdr += 1
                continue
            if byonic_val < filters.byonic_threshold:
                rows_skipped_byonic += 1
                continue
            if abs(ppm_val) > filters.ppm_threshold:
                rows_skipped_ppm += 1
                continue

            # Min-count filter: how many abundance columns have a positive value?
            count_of_peaks = 0
            for c in col_idx.abundance_indices:
                abd_str = str(row_values[c]) if c < len(row_values) and row_values[c] else ""
                if abd_str and float(abd_str) > 0:
                    count_of_peaks += 1
            if count_of_peaks < filters.mincount_threshold:
                rows_skipped_mincount += 1
                continue

            # --- per-condition abundance aggregation -----------------------
            condition_to_abd_list: dict[str, list[float]] = defaultdict(list)
            for cond in unique_conditions:
                for idx in condition_to_col_indices[cond]:
                    abd = row_values[idx]
                    if not abd:
                        continue
                    condition_to_abd_list[cond].append(float(abd))

            # --- glycan conversion -----------------------------------------
            glycan_names = str(row_values[col_idx.glycan] or "")
            new_name = ""
            best_glycan_name = ""
            site = ""

            if glycan_names:
                result_glycopeptide_count += 1
                glycan_names = glycan_names.replace(" ", "")  # remove spaces
                # this allows us to handle both "HexNAc(4)Hex(5); Fuc(1)" and "HexNAc(4)Hex(3)Fuc(1) % 1444.5339; HexNAc(4)Hex(3) % 1444.5339"
                delimiters = r"[;,]"
                mods = re.split(delimiters, glycan_names)
                # mods = glycan_names.split("; ")
                name_parts: list[str] = []
                for mod in mods:
                    # handle the case where the glycan name is followed by " % mass" (e.g. "HexNAc(4)Hex(3) % 1444.5339")
                    # find last index of ) and take substring up to that. if there is no ), continue with next loop
                    if ")" not in mod:
                        continue
                    mod = mod[: mod.rfind(")") + 1]
                    if mod not in glycan_cache:
                        glycan_cache[mod] = glycan_name_old_to_new(mod)
                    converted = glycan_cache[mod]
                    if converted != mod and not best_glycan_name:
                        best_glycan_name = mod
                    name_parts.append(converted)
                new_name = ";".join(name_parts)

                if not best_glycan_name:
                    best_glycan_name = name_parts[0] if name_parts else ""

                # --- extract gene name and compute site --------------------
                description = str(row_values[col_idx.description] or "")
                gene_name = _extract_gene_name(description)

                peptide_start = int(float(row_values[col_idx.mod_position]))
                mod_in_pep = str(row_values[col_idx.mod_in_peptide] or "")
                mod_site = _parse_modification_site(
                    mod_in_pep, glycan_names, peptide_start
                )

                protein_accession = str(row_values[col_idx.protein] or "")
                site = f"{protein_accession}---{mod_site}---{gene_name}"
                site_to_rows[site].append(result_row_number + 1)

                site_with_glycan = f"{new_name}---{site}"

                # Ensure replicate vectors are initialised (the defaultdict
                # factory handles this, but we touch the keys explicitly so
                # that the initialisation is deterministic for the first row).
                _ = glycan_to_abd_replicates[new_name]
                _ = glycan_to_cnt_replicates[new_name]
                _ = glycopep_to_abd_replicates[site_with_glycan]

                motifs = get_glycan_motif(glycan_names, new_name)

                for k, abd_col_idx in enumerate(col_idx.abundance_indices):
                    abd = row_values[abd_col_idx]
                    curr_condition = idx_to_condition[abd_col_idx]
                    abd_float = float(abd) if abd else 0.0

                    glycan_to_abd_replicates[new_name][k] += abd_float
                    glycan_to_abd_conditions[new_name][curr_condition] += abd_float
                    glycopep_to_abd_replicates[site_with_glycan][k] += abd_float

                    for motif in motifs:
                        _ = motif_to_abd_replicates[motif]
                        _ = motif_to_cnt_replicates[motif]
                        motif_to_abd_replicates[motif][k] += abd_float
                        motif_to_abd_conditions[motif][curr_condition] += abd_float
                        if abd_float > 0:
                            motif_to_cnt_replicates[motif][k] += 1
                            motif_to_cnt_conditions[motif][curr_condition] += 1

                    if abd_float > 0:
                        glycan_to_cnt_replicates[new_name][k] += 1
                        glycan_to_cnt_conditions[new_name][curr_condition] += 1

            # --- per-row statistics ----------------------------------------
            stats_suffix = _compute_row_statistics(
                unique_conditions, condition_to_abd_list
            )

            # Single-protein mean/stderr bookkeeping
            if is_single_protein:
                for cond in unique_conditions:
                    condition_mean_and_stderr[new_name][cond].append(
                        mean(condition_to_abd_list[cond])
                    )
                    condition_mean_and_stderr[new_name][cond].append(
                        std_error(condition_to_abd_list[cond])
                    )

            # --- glycan composition tuple for the CSV ----------------------
            comp = get_glycan_composition_list(best_glycan_name)
            comp_list: list[int] = list(comp)

            # --- assemble and (optionally) emit result row -----------------
            candidate_row = row_values + [site, new_name] + comp_list + stats_suffix
            if filters.export_filter == "all":
                rows.append(candidate_row)
                result_row_number += 1
            elif filters.export_filter == "glycan" and glycan_names:
                rows.append(candidate_row)
                result_row_number += 1

    finally:
        _input_fh.close()

    print(f"[DEBUG] === Row processing summary ===")
    print(f"[DEBUG] Total rows scanned: {total_rows_scanned}")
    print(f"[DEBUG] Skipped (parse error): {rows_skipped_parse_error}")
    print(
        f"[DEBUG] Skipped (peplength < {filters.peplength_threshold}): {rows_skipped_peplength}"
    )
    print(f"[DEBUG] Skipped (fdr2d > {filters.fdr2d_threshold}): {rows_skipped_fdr}")
    print(
        f"[DEBUG] Skipped (byonic < {filters.byonic_threshold}): {rows_skipped_byonic}"
    )
    print(f"[DEBUG] Skipped (ppm > {filters.ppm_threshold}): {rows_skipped_ppm}")
    print(
        f"[DEBUG] Skipped (mincount < {filters.mincount_threshold}): {rows_skipped_mincount}"
    )
    print(f"[DEBUG] Result rows emitted: {result_row_number}")
    print(f"[DEBUG] Glycopeptide count: {result_glycopeptide_count}")
    print(f"[DEBUG] Unique sites: {len(site_to_rows)}")
    print(f"[DEBUG] Unique glycans: {len(glycan_to_abd_replicates)}")
    print(f"[DEBUG] Output file: {output_file}")

    # ---- write output artefacts -------------------------------------------
    _write_csv(output_file, result_fields, rows)

    # Site-table JSON
    with open(site_table_meta_file, "w", encoding="utf-8") as fp:
        json.dump(dict(site_to_rows), fp)

    # Global glycan stats JSON
    global_glycan_stats: dict[str, Any] = {
        "condition_names": unique_conditions,
        "col_names": abd_col_names,
        "glycan_to_abd_replicates": dict(glycan_to_abd_replicates),
        "glycan_to_abd_conditions": {
            k: dict(v) for k, v in glycan_to_abd_conditions.items()
        },
        "motif_to_abd_replicates": dict(motif_to_abd_replicates),
        "motif_to_abd_conditions": {
            k: dict(v) for k, v in motif_to_abd_conditions.items()
        },
        "glycan_to_cnt_replicates": dict(glycan_to_cnt_replicates),
        "glycan_to_cnt_conditions": {
            k: dict(v) for k, v in glycan_to_cnt_conditions.items()
        },
        "motif_to_cnt_replicates": dict(motif_to_cnt_replicates),
        "motif_to_cnt_conditions": {
            k: dict(v) for k, v in motif_to_cnt_conditions.items()
        },
        "condition_mean_and_stderr": {
            k: dict(v) for k, v in condition_mean_and_stderr.items()
        },
    }
    with open(meta_file_global, "w", encoding="utf-8") as fp:
        json.dump(global_glycan_stats, fp, sort_keys=False)

    # Conditions-map CSV (4 rows × n_replicate columns)
    conditions_rep_rows: list[list[Any]] = [[], [], [], []]
    for i, col_name in enumerate(abd_col_names):
        conditions_rep_rows[0].append(i + 1)
        conditions_rep_rows[1].append(unique_conditions.index(conditions[i]) + 1)
        conditions_rep_rows[2].append("MAP1")
        conditions_rep_rows[3].append(conditions[i])
    with open(condition_map_file, "w", newline="", encoding="utf-8") as csvfile:
        csv.writer(csvfile).writerows(conditions_rep_rows)

    # Proportions CSV
    prop_fields = ["Gene", "Protein"]
    for i in range(n_abd_cols):
        prop_fields.append(f"Est_Prop{i + 1}")

    prop_rows: list[list[Any]] = [
        abd_col_names,
        conditions,
        unique_conditions,
        conditions_rep_rows[1],
    ]
    for key, replicates in glycopep_to_abd_replicates.items():
        tmp_gene = key.split("---")[-1]
        if not tmp_gene:
            tmp_gene = "NA"
        total = sum(replicates)
        prop_row: list[Any] = []
        for v in replicates:
            if v == 0 or total == 0:
                prop_row.append("")
            else:
                prop_row.append(v / total)
        prop_rows.append([key, key] + prop_row)
    _write_csv(proportion_file, prop_fields, prop_rows)

    # QC statistics
    protein_set: set[str] = set()
    for key in site_to_rows:
        protein_set.add(key.split("---")[0])

    statistics: dict[str, int] = OrderedDict(
        total_proteins=len(protein_set),
        total_peptides=result_row_number,
        total_glycopeptides=result_glycopeptide_count,
        unique_glycans=len(glycan_to_abd_replicates),
        total_sites=len(site_to_rows),
    )

    qc_fields = list(statistics.keys())
    _write_csv(qc_output_file, qc_fields, [list(statistics.values())])

    # Run glycan validator to append depth, predicted RT, conflict, and
    # composite validation score columns to the results CSV.
    try:
        _run_glycan_validator(
            output_file,
            output_file,
            w_depth=filters.w_depth,
            w_conflict=filters.w_conflict,
            w_byonic=filters.w_byonic,
            rt_column=rt_column_name,
        )
    except Exception as exc:
        logger.warning("glycan_validator failed (non-fatal): %s", exc)

    return AnalysisResult(
        output_file=output_file,
        site_to_rows=dict(site_to_rows),
        statistics=dict(statistics),
        qc_output_file=qc_output_file,
    )


# ---------------------------------------------------------------------------
# Modification-site parsing
# ---------------------------------------------------------------------------


def _parse_modification_site(
    mod_string: str,
    glycan_names: str,
    peptide_start: int,
) -> str:
    """Extract the absolute protein position from a modification-site string.

    The *mod_string* value comes from the ``"Modifications (all possible
    sites)"`` column.  Its format is something like::

        2xCarbamidomethyl [C7; C24]; 1xHexNAc(5)Hex(6)NeuAc(1) [N10]

    The function locates the glycan composition token inside the string,
    extracts the first residue + offset (e.g. ``N10``), then computes the
    absolute position as ``peptide_start + residue_offset - 1``.

    Parameters
    ----------
    mod_string:
        Raw value of the modifications column for this row.
    glycan_names:
        The glycan composition(s) for this row (semicolon-separated).
    peptide_start:
        1-based starting position of the peptide in the protein sequence.

    Returns
    -------
    str
        A residue + absolute-position string (e.g. ``"N142"``), or the bare
        *peptide_start* as a string if parsing fails.
    """
    default = str(peptide_start)

    # Split on the first glycan composition token to isolate the site bracket.
    first_glycan = glycan_names.split(";")[0]

    # Defensive check: if the glycan name isn't found in the mod string, we can't parse the site.
    if first_glycan not in mod_string:
        mass = composition_to_mass(first_glycan)
        first_glycan = str(math.floor(mass * 100) / 100)

    # handle multiple modifications separated by either ";" or ","
    all_mods = mod_string.replace(",", ";").split(";")
    for one_mod in all_mods:
        if first_glycan in one_mod:
            mod_string = one_mod
            break

    # now mod_string should be a single mod or glycan, extract location from it
    parts = mod_string.split(first_glycan)
    if len(parts) <= 1:
        return default

    residue_loc_str = ""
    residue = ""
    for part in parts:
        # Match residue + integer: "N10", "S23", "T5", or reversed "10N", "23S"
        m = re.search(r"([NST])(\d+)", part)
        if not m:
            m = re.search(r"(\d+)([NST])", part)
        if m:
            groups = m.groups()
            if groups[0].isdigit():
                residue_loc_str = groups[0]
                residue = groups[1]
            else:
                residue = groups[0]
                residue_loc_str = groups[1]
            break

    if not residue_loc_str:
        return default

    try:
        absolute_pos = int(residue_loc_str) + peptide_start - 1
    except ValueError:
        return default

    return f"{residue}{absolute_pos}"


# ---------------------------------------------------------------------------
# Gene-name extraction
# ---------------------------------------------------------------------------


def _extract_gene_name(description: str) -> str:
    """Extract the gene name from a protein description string.

    The FASTA description convention used by UniProt includes a ``GN=``
    tag, for example::

        sp|P00750|TPA_HUMAN ... GN=PLAT PE=1 SV=1

    This function returns the word immediately following ``" GN="``, or an
    empty string if no such tag is found.

    Parameters
    ----------
    description:
        The ``Master Protein Descriptions`` field value.

    Returns
    -------
    str
        Gene name, or ``""`` if not found.
    """
    idx = description.find(" GN=")
    if idx < 0:
        return ""
    return description[idx + 4 :].split(" ")[0]


# ---------------------------------------------------------------------------
# CSV helper
# ---------------------------------------------------------------------------


def _write_csv(
    filepath: str,
    fields: list[str],
    rows: list[list[Any]],
) -> None:
    """Write a simple CSV file with a header row and data rows.

    Parameters
    ----------
    filepath:
        Destination path.  Parent directories must already exist.
    fields:
        Column headers.
    rows:
        Data rows (each a list whose length should match *fields*).
    """
    print(
        f"[DEBUG] Writing CSV to {filepath} with {len(rows)} rows and {len(fields)} columns"
    )
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(fields)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _ColumnIndices:
    """Resolved integer column positions for every field we need."""

    glycan: int
    protein: int
    mod_position: int
    mod_in_peptide: int
    description: int
    fdr2d: int
    byonic: int
    ppm: int
    peptide: int
    abundance_indices: list[int] = field(default_factory=list)


def _read_header_row(ws: Any) -> list[str]:
    """Return the first row of *ws* as a list of strings."""
    first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    return [str(cell) if cell is not None else "" for cell in first_row]


def _resolve_column_indices(
    header: list[str],
    abundance_type: str,
    header_set: ColumnHeaderSet | None = None,
) -> _ColumnIndices:
    """Map well-known column names to their 0-based positions in *header*.

    When *header_set* is provided, its field values override the module-level
    defaults.  Raises :class:`ValueError` when a required column cannot be
    found.
    """
    hs = header_set or BYONIC_HEADER_SET

    def _exact(name: str) -> int:
        try:
            return header.index(name)
        except ValueError:
            raise ValueError(f"Required column '{name}' not found in header") from None

    def _startswith(prefix: str) -> int:
        for i, h in enumerate(header):
            if h.startswith(prefix):
                return i
        raise ValueError(f"No column starting with '{prefix}' found in header")

    def _all_startswith(prefix: str) -> list[int]:
        return [i for i, h in enumerate(header) if h.startswith(prefix)]

    # Modification column: prefer the primary variant, fall back
    # to the fallback column (MSFragger compatibility).
    mod_primary = hs.modifications
    mod_fallback = hs.modifications_fallback
    if mod_primary and mod_primary in header:
        mod_in_pep_idx = header.index(mod_primary)
    elif mod_fallback and mod_fallback in header:
        mod_in_pep_idx = header.index(mod_fallback)
    else:
        raise ValueError(
            f"Neither '{mod_primary}' nor " f"'{mod_fallback}' found in header"
        )

    abundance_prefix = f"{abundance_type}: "

    return _ColumnIndices(
        glycan=_exact(hs.glycan_composition),
        protein=_exact(hs.protein_accessions),
        mod_position=_exact(hs.position_in_protein),
        mod_in_peptide=mod_in_pep_idx,
        description=_exact(hs.master_protein_descriptions),
        fdr2d=_startswith(hs.fdr_prefix),
        byonic=_startswith(hs.engine_score_prefix),
        ppm=_startswith(hs.ppm_prefix),
        peptide=_exact(hs.sequence),
        abundance_indices=_all_startswith(abundance_prefix),
    )


def _resolve_with_header_sets(
    header: list[str],
    abundance_type: str,
    header_sets: list[ColumnHeaderSet] | None,
) -> tuple[_ColumnIndices, ColumnHeaderSet]:
    """Try each header set in order and return the first match.

    Returns a tuple of (resolved indices, matched header set).
    Raises :class:`ValueError` with a summary if none match.
    """
    if not header_sets:
        return _resolve_column_indices(header, abundance_type), BYONIC_HEADER_SET

    # Filter out empty/blank header sets (all fields empty)
    active_sets = [
        hs
        for hs in header_sets
        if any(getattr(hs, f) for f in hs.model_fields if f != "name")
    ]
    if not active_sets:
        return _resolve_column_indices(header, abundance_type), BYONIC_HEADER_SET

    errors: list[str] = []
    for hs in active_sets:
        try:
            # Override abundance_type from the header set's abundance_columns
            abt = (
                hs.abundance_columns.rstrip("*").rstrip()
                if hs.abundance_columns
                else abundance_type
            )
            col_idx = _resolve_column_indices(header, abt, hs)
            return col_idx, hs
        except ValueError as exc:
            errors.append(f"  [{hs.name or 'unnamed'}]: {exc}")

    # Fallback: try canonical Byonic-pd headers (files are remapped to
    # canonical names at upload time, so the original header set may not match)
    try:
        return _resolve_column_indices(header, abundance_type), BYONIC_HEADER_SET
    except ValueError:
        pass

    raise ValueError(
        "No column header set matched the file headers.\n" + "\n".join(errors)
    )


def _map_conditions(
    conditions: list[str],
    abundance_indices: list[int],
) -> tuple[list[str], dict[str, list[int]], dict[int, str]]:
    """Build the condition-to-column-index mapping.

    Parameters
    ----------
    conditions:
        Ordered list of condition labels (same length as *abundance_indices*).
    abundance_indices:
        0-based column indices for the abundance columns.

    Returns
    -------
    tuple
        ``(unique_conditions, condition_to_col_indices, idx_to_condition)``
    """
    unique_conditions: list[str] = []
    condition_to_col_indices: dict[str, list[int]] = defaultdict(list)
    idx_to_condition: dict[int, str] = {}

    for pos, cond in enumerate(conditions):
        if cond not in unique_conditions:
            unique_conditions.append(cond)
        col_idx = abundance_indices[pos]
        condition_to_col_indices[cond].append(col_idx)
        idx_to_condition[col_idx] = cond

    return unique_conditions, dict(condition_to_col_indices), idx_to_condition


def _compute_row_statistics(
    unique_conditions: list[str],
    condition_to_abd_list: dict[str, list[float]],
) -> list[Any]:
    """Compute per-row statistics and return them as a flat list of values.

    The returned list contains, in order:
    1. Valid data-point count for each condition
    2. Mean abundance for each condition
    3. Standard deviation for each condition
    4. Standard error for each condition
    5. Coefficient of variation for each condition
    6. Pairwise t-test p-values (all unordered pairs)
    7. ANOVA F-statistic and p-value (when >2 conditions)
    """
    result: list[Any] = []

    # 1–5: descriptive statistics per condition
    for cond in unique_conditions:
        result.append(len(condition_to_abd_list[cond]))
    for cond in unique_conditions:
        result.append(mean(condition_to_abd_list[cond]))
    for cond in unique_conditions:
        result.append(std(condition_to_abd_list[cond]))
    for cond in unique_conditions:
        result.append(std_error(condition_to_abd_list[cond]))
    for cond in unique_conditions:
        result.append(cv(condition_to_abd_list[cond]))

    # 6: pairwise t-tests
    for i in range(len(unique_conditions)):
        for j in range(i + 1, len(unique_conditions)):
            result.append(
                pvalue_from_ttest(
                    condition_to_abd_list[unique_conditions[i]],
                    condition_to_abd_list[unique_conditions[j]],
                )
            )

    # 7: ANOVA (>2 conditions)
    if len(unique_conditions) > 2:
        groups = [condition_to_abd_list[c] for c in unique_conditions]
        f_stat, p_val = anova_pvalue(groups)
        result.append(f_stat)
        result.append(p_val)

    return result


def _maybe_convert_single_protein_csv(filepath: str) -> str:
    """If *filepath* is the special ``single_protein.csv``, convert it to
    ``.xlsx`` (using openpyxl) and return the new path.  Otherwise return
    *filepath* unchanged.

    The legacy code performed this conversion with ``xlsxwriter``; here we
    use ``openpyxl`` for consistency with the rest of the v2 codebase.
    """
    if "single_protein" not in filepath:
        return filepath

    p = Path(filepath)
    if p.suffix.lower() != ".csv":
        return filepath

    xlsx_path = p.with_suffix(".xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None

    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            ws.append(row)

    wb.save(str(xlsx_path))
    wb.close()
    logger.info("Converted single-protein CSV → XLSX: %s", xlsx_path)
    return str(xlsx_path)
