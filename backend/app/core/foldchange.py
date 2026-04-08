"""Fold-change computation for glycan abundance data.

Ported from the legacy ``get_foldchange_data.py`` (Python 2) to Python 3.11+
with proper type annotations and a structured return type.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class FoldChangeResult:
    """Output of a fold-change computation.

    Attributes
    ----------
    glycan_list:
        Identifiers of the form ``"<glycan>---<Protein---Position---Gene>"``.
    fc:
        Log₂ fold-change values (comparison / reference) for each entry.
    p_value:
        Negative log₁₀ p-values for each entry.
    anova:
        ANOVA p-value strings for each entry, or ``None`` when the input
        file does not contain an ANOVA column.
    """

    glycan_list: list[str]
    fc: list[float]
    p_value: list[float]
    anova: list[str] | None


# ---------------------------------------------------------------------------
# Column-name constants
# ---------------------------------------------------------------------------

_GLYCAN_COL = "Converted Glycan Names"
_SITE_INFO_COL = "Protein---Position---Gene"
_ABD_SUFFIX = ": Abundance"
_ANOVA_COL = "ANOVA_P-value"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def compute_foldchange(
    file_path: str,
    reference_condition: str,
    comparison_condition: str,
) -> FoldChangeResult:
    """Compute per-glycosite log₂ fold-changes and transformed p-values.

    Reads a CSV file produced by the upstream glycan-abundance pipeline,
    calculates ``log₂(comparison / reference)`` for each row, converts the
    pairwise p-value to ``-log₁₀(p)``, and deduplicates glycan–site
    combinations by keeping the entry with the most significant
    (highest ``-log₁₀``) p-value.

    Parameters
    ----------
    file_path:
        Path to the input CSV file.
    reference_condition:
        Name of the reference (denominator) condition.  Quotes are
        stripped automatically for backwards compatibility with the
        legacy command-line interface.
    comparison_condition:
        Name of the comparison (numerator) condition.  Quotes are
        stripped automatically.

    Returns
    -------
    FoldChangeResult
        A dataclass containing aligned lists of glycan identifiers,
        log₂ fold-changes, ``-log₁₀`` p-values, and (optionally) raw
        ANOVA p-value strings.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    ValueError
        If the CSV header is missing or a required column cannot be found.
    """
    # Sanitise condition names (legacy compat: strip embedded quotes).
    reference_condition = reference_condition.replace('"', "")
    comparison_condition = comparison_condition.replace('"', "")

    # ------------------------------------------------------------------
    # Read header & resolve column indices
    # ------------------------------------------------------------------
    with open(file_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"CSV file is empty or has no header: {file_path}")

        idx_glycan = header.index(_GLYCAN_COL)
        idx_site = header.index(_SITE_INFO_COL)
        idx_ref_abd = header.index(reference_condition + _ABD_SUFFIX)
        idx_cmp_abd = header.index(comparison_condition + _ABD_SUFFIX)

        # The p-value column may appear in either direction.
        pvalue_col = f"p-value:{reference_condition}_to_{comparison_condition}"
        alt_pvalue_col = f"p-value:{comparison_condition}_to_{reference_condition}"

        if pvalue_col in header:
            idx_pvalue = header.index(pvalue_col)
        elif alt_pvalue_col in header:
            idx_pvalue = header.index(alt_pvalue_col)
        else:
            raise ValueError(
                f"Neither '{pvalue_col}' nor '{alt_pvalue_col}' found in header"
            )

        idx_anova = header.index(_ANOVA_COL) if _ANOVA_COL in header else -1

        # ------------------------------------------------------------------
        # Accumulate per-glycosite results
        # ------------------------------------------------------------------
        # Key: "glycan---siteinfo"
        # Value: [log2_fc, neg_log10_pvalue(, anova_str)]
        best: dict[str, list[float | str]] = {}

        for line in reader:
            try:
                ref_abd = float(line[idx_ref_abd])
                cmp_abd = float(line[idx_cmp_abd])
            except (ValueError, IndexError):
                continue

            raw_pvalue = line[idx_pvalue]
            if not raw_pvalue or raw_pvalue == "nan":
                continue
            try:
                pvalue = float(raw_pvalue)
            except ValueError:
                continue
            if pvalue < 0:
                continue
            if ref_abd == 0 or cmp_abd == 0:
                continue

            key = line[idx_glycan] + "---" + line[idx_site]
            # Skip entries with empty glycan or site info
            if not line[idx_glycan] or not line[idx_site]:
                continue
            log2_fc = math.log2(cmp_abd / ref_abd)
            neg_log10_p = -math.log10(pvalue)

            # Keep the entry with the most significant p-value.
            prev = best.get(key)
            if prev is None or prev[1] < neg_log10_p:
                entry: list[float | str] = [log2_fc, neg_log10_p]
                if idx_anova != -1:
                    entry.append(line[idx_anova])
                best[key] = entry

    # ------------------------------------------------------------------
    # Unpack into parallel lists
    # ------------------------------------------------------------------
    glycan_list: list[str] = []
    fc_list: list[float] = []
    pvalue_list: list[float] = []
    anova_list: list[str] = [] if idx_anova != -1 else []

    for key, vals in best.items():
        glycan_list.append(key)
        fc_list.append(float(vals[0]))
        pvalue_list.append(float(vals[1]))
        if idx_anova != -1:
            anova_list.append(str(vals[2]))

    return FoldChangeResult(
        glycan_list=glycan_list,
        fc=fc_list,
        p_value=pvalue_list,
        anova=anova_list if idx_anova != -1 else None,
    )
