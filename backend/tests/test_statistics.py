"""Tests for app.core.statistics."""

import math

import pytest

from app.core.statistics import mean, std, std_error, cv, pvalue_from_ttest, anova_pvalue


# ── mean ────────────────────────────────────────────────────────────────────

class TestMean:
    def test_basic(self):
        assert mean([1.0, 2.0, 3.0]) == 2.0

    def test_single(self):
        assert mean([5.0]) == 5.0

    def test_empty(self):
        assert mean([]) == 0.0


# ── std ─────────────────────────────────────────────────────────────────────

class TestStd:
    def test_basic(self):
        # Sample std of [2, 4, 4, 4, 5, 5, 7, 9] ≈ 2.1381
        result = std([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        assert abs(result - 2.13809) < 0.001

    def test_single_element(self):
        assert std([42.0]) == 0.0

    def test_empty(self):
        assert std([]) == 0.0

    def test_identical_values(self):
        assert std([3.0, 3.0, 3.0]) == 0.0


# ── std_error ───────────────────────────────────────────────────────────────

class TestStdError:
    def test_basic(self):
        vals = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        expected = std(vals) / math.sqrt(len(vals))
        assert abs(std_error(vals) - expected) < 1e-10

    def test_single(self):
        assert std_error([1.0]) == 0.0


# ── cv ──────────────────────────────────────────────────────────────────────

class TestCv:
    def test_basic(self):
        vals = [10.0, 10.0, 10.0]
        assert cv(vals) == 0.0

    def test_zero_mean(self):
        assert cv([0.0, 0.0]) == 0.0

    def test_positive(self):
        result = cv([1.0, 2.0, 3.0])
        assert result > 0


# ── pvalue_from_ttest ───────────────────────────────────────────────────────

class TestPvalueFromTtest:
    def test_identical_groups(self):
        p = pvalue_from_ttest([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
        assert math.isnan(p) or p == 1.0  # identical → no difference

    def test_different_groups(self):
        p = pvalue_from_ttest([1.0, 2.0, 3.0], [10.0, 11.0, 12.0])
        assert p < 0.05

    def test_empty_after_zero_filter(self):
        # All zeros get filtered out → NaN
        p = pvalue_from_ttest([0.0, 0.0], [1.0, 2.0, 3.0])
        assert math.isnan(p)

    def test_both_empty(self):
        assert math.isnan(pvalue_from_ttest([], []))


# ── anova_pvalue ────────────────────────────────────────────────────────────

class TestAnovaPvalue:
    def test_different_groups(self):
        f_stat, p_val = anova_pvalue([[1, 2, 3], [10, 11, 12], [20, 21, 22]])
        assert p_val < 0.05
        assert f_stat > 0

    def test_identical_groups(self):
        _, p_val = anova_pvalue([[5, 5, 5], [5, 5, 5]])
        assert math.isnan(p_val) or p_val > 0.99

    def test_fewer_than_two_groups(self):
        with pytest.raises(ValueError, match="at least two groups"):
            anova_pvalue([[1, 2, 3]])

    def test_all_zeros(self):
        # All zeros → NaN after filtering
        f_stat, p_val = anova_pvalue([[0, 0, 0], [0, 0, 0]])
        assert math.isnan(f_stat)
        assert math.isnan(p_val)
