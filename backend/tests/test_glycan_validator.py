"""Tests for the composite validation score computation in app.core.glycan_validator."""

import pandas as pd
import pytest

from app.core.glycan_validator import compute_composite_validation_score


class TestCompositeValidationScore:
    def _make_df(self, depth, rt_conflics, byonic_scores):
        """Build a minimal DataFrame with the required columns."""
        return pd.DataFrame(
            {
                "depth": depth,
                "rt_conflics": rt_conflics,
                "Byonic Score (best)": byonic_scores,
            }
        )

    def test_basic_output_columns(self):
        df = self._make_df(["1", "2", "3"], ["0.1", "0.2", "0.3"], ["100", "200", "300"])
        result = compute_composite_validation_score(df)
        assert "depth_pct" in result.columns
        assert "rt_conflict_pct" in result.columns
        assert "engine_score_pct" in result.columns
        assert "composite_validation_score" in result.columns
        assert len(result) == 3

    def test_scores_in_unit_range(self):
        df = self._make_df(
            ["1", "2", "3", "4", "5"],
            ["0.1", "0.2", "0.3", "0.4", "0.5"],
            ["10", "20", "30", "40", "50"],
        )
        result = compute_composite_validation_score(df)
        for col in ["depth_pct", "rt_conflict_pct", "engine_score_pct", "composite_validation_score"]:
            vals = [float(v) for v in result[col] if v != ""]
            for v in vals:
                assert 0.0 <= v <= 1.0, f"{col} value {v} out of [0, 1]"

    def test_custom_weights(self):
        df = self._make_df(["1", "2"], ["0.1", "0.2"], ["100", "200"])
        # With all weight on depth only
        result = compute_composite_validation_score(df, w_depth=1.0, w_conflict=0.0, w_byonic=0.0)
        # Both rows should have valid scores
        scores = [float(v) for v in result["composite_validation_score"] if v != ""]
        assert len(scores) == 2
        # Composite should equal depth_pct when only depth has weight
        for i in range(2):
            if result["composite_validation_score"].iloc[i]:
                assert abs(
                    float(result["composite_validation_score"].iloc[i])
                    - float(result["depth_pct"].iloc[i])
                ) < 1e-4

    def test_normalization(self):
        """Weights that don't sum to 1 should still produce scores in [0, 1]."""
        df = self._make_df(["1", "2", "3"], ["0.1", "0.2", "0.3"], ["100", "200", "300"])
        result = compute_composite_validation_score(df, w_depth=0.5, w_conflict=0.0, w_byonic=0.2)
        scores = [float(v) for v in result["composite_validation_score"] if v != ""]
        for v in scores:
            assert 0.0 <= v <= 1.0

    def test_no_byonic_column(self):
        """When Byonic column is missing, should fall back to (depth + conflict) / 2."""
        df = pd.DataFrame({"depth": ["1", "2"], "rt_conflics": ["0.1", "0.2"]})
        result = compute_composite_validation_score(df, byonic_col_prefix="NonExistent")
        scores = [float(v) for v in result["composite_validation_score"] if v != ""]
        assert len(scores) == 2

    def test_empty_dataframe(self):
        df = self._make_df([], [], [])
        result = compute_composite_validation_score(df)
        assert len(result) == 0

    def test_na_values_handled(self):
        df = self._make_df(["1", "", "3"], ["0.1", "NA", "0.3"], ["100", "", "300"])
        result = compute_composite_validation_score(df)
        # Row with empty depth should have empty composite
        assert result["composite_validation_score"].iloc[1] == ""
