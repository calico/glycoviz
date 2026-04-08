"""Statistical helper functions for glycan analysis.

Ported from the legacy ``glycan_converter.py`` (Python 2) to Python 3.11+
with proper type annotations and improved return types.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------


def mean(values: list[float]) -> float:
    """Return the arithmetic mean of *values*.

    Returns ``0.0`` for an empty sequence.
    """
    if len(values) == 0:
        return 0.0
    return sum(values) / len(values)


def std(values: list[float]) -> float:
    """Return the sample standard deviation of *values* (Bessel-corrected).

    Uses ``n − 1`` in the denominator (sample std-dev).
    Returns ``0.0`` when the sequence has fewer than two elements.
    """
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    total = sum((x - m) ** 2 for x in values)
    return math.sqrt(total / (len(values) - 1))


def std_error(values: list[float]) -> float:
    """Return the standard error of the mean for *values*.

    Returns ``0.0`` when the sequence has fewer than two elements.
    """
    if len(values) <= 1:
        return 0.0
    return std(values) / math.sqrt(len(values))


def cv(values: list[float]) -> float:
    """Return the coefficient of variation (std / mean) for *values*.

    Returns ``0.0`` when the mean is zero to avoid division-by-zero.
    """
    m = mean(values)
    if m == 0:
        return 0.0
    return std(values) / m


# ---------------------------------------------------------------------------
# Hypothesis tests
# ---------------------------------------------------------------------------


def _filter_zeros(values: list[float]) -> list[float]:
    """Return a copy of *values* with exact zeros removed."""
    return [x for x in values if x != 0]


def pvalue_from_ttest(values_a: list[float], values_b: list[float]) -> float:
    """Return the p-value from Welch's two-sample t-test.

    Exact zeros are removed from each group before testing (legacy
    behaviour).  Returns ``float("nan")`` when either group is empty
    after filtering.

    Parameters
    ----------
    values_a:
        First sample of observations.
    values_b:
        Second sample of observations.

    Returns
    -------
    float
        The two-tailed p-value, or ``NaN`` if the test cannot be performed.
    """
    a = _filter_zeros(values_a)
    b = _filter_zeros(values_b)
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    result = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
    return float(result.pvalue)


def anova_pvalue(groups: list[list[float]]) -> tuple[float, float]:
    """Return the F-statistic and p-value from a one-way ANOVA.

    Exact zeros in each group are replaced with ``NaN`` so that
    ``scipy.stats.f_oneway`` can handle them via its *nan_policy*
    parameter, consistent with the zero-filtering convention used
    elsewhere in this module.

    Parameters
    ----------
    groups:
        Two or more sequences of observations, one per treatment group.

    Returns
    -------
    tuple[float, float]
        ``(f_statistic, p_value)``.  Both values are ``NaN`` when the
        test cannot be performed (e.g. fewer than two non-empty groups).

    Raises
    ------
    ValueError
        If fewer than two groups are supplied.
    """
    if len(groups) < 2:
        raise ValueError("ANOVA requires at least two groups")

    # Replace zeros with NaN (mirrors the legacy zero-filtering approach).
    cleaned: list[np.ndarray] = []
    for group in groups:
        arr = np.array(group, dtype=np.float64)
        arr[arr == 0] = np.nan
        cleaned.append(arr)

    # Drop groups that are entirely NaN / empty.
    non_empty = [g for g in cleaned if np.any(~np.isnan(g))]
    if len(non_empty) < 2:
        return (float("nan"), float("nan"))

    result = stats.f_oneway(*non_empty, nan_policy="omit")
    return (float(result.statistic), float(result.pvalue))
