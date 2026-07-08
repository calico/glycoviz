"""Tests for app.core.foldchange."""

import math

import pytest

from app.core.foldchange import compute_foldchange


class TestComputeFoldchange:
    def test_basic_foldchange(self, tmp_csv):
        """Two-row CSV with clear fold change."""
        header = [
            "Converted Glycan Names",
            "Protein---Position---Gene",
            "Control: Abundance",
            "Treatment: Abundance",
            "p-value:Control_to_Treatment",
        ]
        rows = [
            ["A2G2F", "P12345---N100---GeneA", "100", "200", "0.01"],
            ["M5", "P12345---N200---GeneA", "50", "25", "0.05"],
        ]
        path = tmp_csv(header, rows)
        result = compute_foldchange(path, "Control", "Treatment")

        assert len(result.glycan_list) == 2
        assert len(result.fc) == 2
        assert len(result.p_value) == 2

        # A2G2F: 200/100 → log2 = 1.0
        idx = result.glycan_list.index("A2G2F---P12345---N100---GeneA")
        assert abs(result.fc[idx] - 1.0) < 1e-10

        # M5: 25/50 → log2 = -1.0
        idx = result.glycan_list.index("M5---P12345---N200---GeneA")
        assert abs(result.fc[idx] - (-1.0)) < 1e-10

    def test_zero_abundance_skipped(self, tmp_csv):
        """Rows with zero abundance should be skipped."""
        header = [
            "Converted Glycan Names",
            "Protein---Position---Gene",
            "A: Abundance",
            "B: Abundance",
            "p-value:A_to_B",
        ]
        rows = [
            ["A2G2F", "P1---N1---G1", "0", "200", "0.01"],
            ["M5", "P1---N2---G1", "100", "0", "0.01"],
        ]
        path = tmp_csv(header, rows)
        result = compute_foldchange(path, "A", "B")
        assert len(result.glycan_list) == 0

    def test_nan_pvalue_skipped(self, tmp_csv):
        """Rows with NaN p-value should be skipped."""
        header = [
            "Converted Glycan Names",
            "Protein---Position---Gene",
            "A: Abundance",
            "B: Abundance",
            "p-value:A_to_B",
        ]
        rows = [
            ["A2G2F", "P1---N1---G1", "100", "200", "nan"],
        ]
        path = tmp_csv(header, rows)
        result = compute_foldchange(path, "A", "B")
        assert len(result.glycan_list) == 0

    def test_dedup_keeps_most_significant(self, tmp_csv):
        """Duplicate glycan-site entries should keep the most significant p-value."""
        header = [
            "Converted Glycan Names",
            "Protein---Position---Gene",
            "A: Abundance",
            "B: Abundance",
            "p-value:A_to_B",
        ]
        rows = [
            ["A2G2F", "P1---N1---G1", "100", "200", "0.05"],
            ["A2G2F", "P1---N1---G1", "100", "400", "0.001"],  # more significant
        ]
        path = tmp_csv(header, rows)
        result = compute_foldchange(path, "A", "B")
        assert len(result.glycan_list) == 1
        # Should keep log2(400/100) = 2.0
        assert abs(result.fc[0] - 2.0) < 1e-10

    def test_alt_pvalue_column(self, tmp_csv):
        """Should find p-value column in reverse direction."""
        header = [
            "Converted Glycan Names",
            "Protein---Position---Gene",
            "A: Abundance",
            "B: Abundance",
            "p-value:B_to_A",
        ]
        rows = [
            ["M3", "P1---N1---G1", "100", "200", "0.01"],
        ]
        path = tmp_csv(header, rows)
        result = compute_foldchange(path, "A", "B")
        assert len(result.glycan_list) == 1

    def test_anova_column(self, tmp_csv):
        """ANOVA column should be included when present."""
        header = [
            "Converted Glycan Names",
            "Protein---Position---Gene",
            "A: Abundance",
            "B: Abundance",
            "p-value:A_to_B",
            "ANOVA_P-value",
        ]
        rows = [
            ["A2G2F", "P1---N1---G1", "100", "200", "0.01", "0.005"],
        ]
        path = tmp_csv(header, rows)
        result = compute_foldchange(path, "A", "B")
        assert result.anova is not None
        assert result.anova[0] == "0.005"

    def test_no_anova_column(self, tmp_csv):
        """ANOVA should be None when column is absent."""
        header = [
            "Converted Glycan Names",
            "Protein---Position---Gene",
            "A: Abundance",
            "B: Abundance",
            "p-value:A_to_B",
        ]
        rows = [
            ["A2G2F", "P1---N1---G1", "100", "200", "0.01"],
        ]
        path = tmp_csv(header, rows)
        result = compute_foldchange(path, "A", "B")
        assert result.anova is None

    def test_empty_csv_raises(self, tmp_path):
        """Empty file should raise ValueError."""
        fp = tmp_path / "empty.csv"
        fp.write_text("")
        with pytest.raises(ValueError, match="empty or has no header"):
            compute_foldchange(str(fp), "A", "B")
