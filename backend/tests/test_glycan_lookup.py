"""Tests for app.core.glycan_lookup."""

import pytest

from app.core.glycan_lookup import (
    GlycanComposition,
    COMP_TO_NAME_DICT,
    get_glycan_composition_list,
    glycan_name_old_to_new,
    get_glycan_motif,
    composition_to_mass,
)


# ── get_glycan_composition_list ─────────────────────────────────────────────

class TestGetGlycanCompositionList:
    def test_full_composition(self):
        result = get_glycan_composition_list("HexNAc(4)Hex(5)Fuc(1)NeuAc(1)NeuGc(1)")
        assert result == GlycanComposition(4, 5, 1, 1, 1)

    def test_partial_composition(self):
        result = get_glycan_composition_list("HexNAc(2)Hex(3)")
        assert result == GlycanComposition(2, 3, 0, 0, 0)

    def test_empty_string(self):
        result = get_glycan_composition_list("")
        assert result == GlycanComposition(0, 0, 0, 0, 0)

    def test_unknown_monosaccharide(self):
        result = get_glycan_composition_list("Unknown(5)")
        assert result == GlycanComposition(0, 0, 0, 0, 0)

    def test_single_component(self):
        result = get_glycan_composition_list("Fuc(3)")
        assert result == GlycanComposition(0, 0, 3, 0, 0)


# ── glycan_name_old_to_new ──────────────────────────────────────────────────

class TestGlycanNameOldToNew:
    def test_known_composition(self):
        # HexNAc(4)Hex(5)Fuc(1) → A2G2F
        assert glycan_name_old_to_new("HexNAc(4)Hex(5)Fuc(1)") == "A2G2F"

    def test_high_mannose(self):
        assert glycan_name_old_to_new("HexNAc(2)Hex(5)") == "M5"

    def test_unknown_returns_original(self):
        comp = "HexNAc(99)Hex(99)"
        assert glycan_name_old_to_new(comp) == comp

    def test_m3f(self):
        assert glycan_name_old_to_new("HexNAc(2)Hex(3)Fuc(1)") == "M3F"


# ── get_glycan_motif ────────────────────────────────────────────────────────

class TestGetGlycanMotif:
    def test_fucosylated_galactosylated(self):
        motifs = get_glycan_motif("HexNAc(4)Hex(5)Fuc(1)", "A2G2F")
        assert "Fucosylation" in motifs
        assert "Galactosylation" in motifs
        assert "Afucosylation" not in motifs

    def test_high_mannose(self):
        motifs = get_glycan_motif("HexNAc(2)Hex(5)", "M5")
        assert "Afucosylation" in motifs
        assert "High mannose" in motifs

    def test_sialylated_neuac(self):
        motifs = get_glycan_motif("HexNAc(4)Hex(5)NeuAc(1)", "A2S1G2")
        assert "Sialylation" in motifs
        assert "NANA" in motifs
        assert "NGNA" not in motifs

    def test_sialylated_neugc(self):
        motifs = get_glycan_motif("HexNAc(4)Hex(5)NeuGc(1)", "A2Sg1G2")
        assert "Sialylation" in motifs
        assert "NGNA" in motifs

    def test_lewis_x(self):
        motifs = get_glycan_motif("HexNAc(4)Hex(5)Fuc(2)", "A2G2F2 (LeX)")
        assert "LewisX" in motifs
        assert "Fucosylation" in motifs

    def test_afucosylated_no_galactose(self):
        motifs = get_glycan_motif("HexNAc(4)Hex(3)", "A2G0")
        assert "Afucosylation" in motifs
        assert "Galactosylation" not in motifs


# ── composition_to_mass ─────────────────────────────────────────────────────

class TestCompositionToMass:
    def test_known_mass(self):
        # HexNAc(3)Hex(3)Fuc(1) → 1241.4545
        mass = composition_to_mass("HexNAc(3)Hex(3)Fuc(1)")
        assert abs(mass - 1241.4545) < 0.01

    def test_empty(self):
        assert composition_to_mass("") == 0.0

    def test_single_hex(self):
        mass = composition_to_mass("Hex(1)")
        assert abs(mass - 162.05282) < 0.001

    def test_mass_positive(self):
        mass = composition_to_mass("HexNAc(2)Hex(5)")
        assert mass > 0


# ── COMP_TO_NAME_DICT ───────────────────────────────────────────────────────

class TestCompToNameDict:
    def test_not_empty(self):
        assert len(COMP_TO_NAME_DICT) > 0

    def test_m5_lookup(self):
        comp = GlycanComposition(2, 5, 0, 0, 0)
        assert "M5" in COMP_TO_NAME_DICT[comp]
