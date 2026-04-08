"""Single source of truth for glycan name lookups and motif classification.

Ported from the legacy ``Glycans`` class that was duplicated across
``glycan_converter.py`` and ``mass_converter.py``.  All callers should import
from this module instead of re-implementing the lookup logic.
"""

from __future__ import annotations

from typing import NamedTuple

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class GlycanComposition(NamedTuple):
    """Monosaccharide composition of a single N-glycan structure."""

    hexnac: int
    hex: int
    fuc: int
    neuac: int
    neugc: int


# ---------------------------------------------------------------------------
# Canonical glycan table
# ---------------------------------------------------------------------------
# Each row: (short_name, HexNAc, Hex, Fuc, NeuAc, NeuGc)

GLYCAN_TABLE: list[tuple[str, int, int, int, int, int]] = [
    ("M3F", 2, 3, 1, 0, 0),
    ("M4F", 2, 4, 1, 0, 0),
    ("M5F", 2, 5, 1, 0, 0),
    ("A1G0", 3, 3, 0, 0, 0),
    ("A1G0F", 3, 3, 1, 0, 0),
    ("A2G0", 4, 3, 0, 0, 0),
    ("A2G0F", 4, 3, 1, 0, 0),
    ("A2G0F2", 4, 3, 2, 0, 0),
    ("A1G1", 3, 4, 0, 0, 0),
    ("A1G1F", 3, 4, 1, 0, 0),
    ("A2G1", 4, 4, 0, 0, 0),
    ("A2G1F", 4, 4, 1, 0, 0),
    ("A2G2", 4, 5, 0, 0, 0),
    ("A2G2F", 4, 5, 1, 0, 0),
    ("A2G3", 4, 6, 0, 0, 0),
    ("A2G3F", 4, 6, 1, 0, 0),
    ("A2G4", 4, 7, 0, 0, 0),
    ("A2G4F", 4, 7, 1, 0, 0),
    ("A3G0", 5, 3, 0, 0, 0),
    ("A3G0F", 5, 3, 1, 0, 0),
    ("A3G1", 5, 4, 0, 0, 0),
    ("A3G1F", 5, 4, 1, 0, 0),
    ("A3G2", 5, 5, 0, 0, 0),
    ("A3G2F", 5, 5, 1, 0, 0),
    ("A3G3", 5, 6, 0, 0, 0),
    ("A3G3F", 5, 6, 1, 0, 0),
    ("A3G4", 5, 7, 0, 0, 0),
    ("A3G4F", 5, 7, 1, 0, 0),
    ("A3G5", 5, 8, 0, 0, 0),
    ("A3G5F", 5, 8, 1, 0, 0),
    ("A3G6", 5, 9, 0, 0, 0),
    ("A3G6F", 5, 9, 1, 0, 0),
    ("A4G3", 6, 6, 0, 0, 0),
    ("A4G3F", 6, 6, 1, 0, 0),
    ("A4G4", 6, 7, 0, 0, 0),
    ("A4G4F", 6, 7, 1, 0, 0),
    ("A4G5", 6, 8, 0, 0, 0),
    ("A4G5F", 6, 8, 1, 0, 0),
    ("A4G6", 6, 9, 0, 0, 0),
    ("A4G6F", 6, 9, 1, 0, 0),
    ("A4G7", 6, 10, 0, 0, 0),
    ("A4G7F", 6, 10, 1, 0, 0),
    ("A4G8", 6, 11, 0, 0, 0),
    ("A4G8F", 6, 11, 1, 0, 0),
    ("A2G2F2 (LeX)", 4, 5, 2, 0, 0),
    ("A2G3F2 (LeX)", 4, 6, 2, 0, 0),
    ("A3G3F2 (LeX)", 5, 6, 2, 0, 0),
    ("A3G4F2 (LeX)", 5, 7, 2, 0, 0),
    ("A3G5F2 (LeX)", 5, 8, 2, 0, 0),
    ("A3G4F3 (LeX)", 5, 7, 3, 0, 0),
    ("A1S1G1", 3, 4, 0, 1, 0),
    ("A1Sg1G1", 3, 4, 0, 0, 1),
    ("A1S1G1F", 3, 4, 1, 1, 0),
    ("A1Sg1G1F", 3, 4, 1, 0, 1),
    ("A2S1G1", 4, 4, 0, 1, 0),
    ("A2Sg1G1", 4, 4, 0, 0, 1),
    ("A2S1G1F", 4, 4, 1, 1, 0),
    ("A2S1G2", 4, 5, 0, 1, 0),
    ("A2Sg1G2", 4, 5, 0, 0, 1),
    ("A2S2G2", 4, 5, 0, 2, 0),
    ("A2Sg2G2", 4, 5, 0, 0, 2),
    ("A2S1G2F", 4, 5, 1, 1, 0),
    ("A2S1G3", 4, 6, 0, 1, 0),
    ("A2S1G3F", 4, 6, 1, 1, 0),
    ("A2S2G2F", 4, 5, 1, 2, 0),
    ("A3S1G2", 5, 5, 0, 1, 0),
    ("A3Sg1G2", 5, 5, 0, 0, 1),
    ("A2Sg1G1F", 4, 4, 1, 0, 1),
    ("A2Sg1G2F", 4, 5, 1, 0, 1),
    ("A2Sg1G3", 4, 6, 0, 0, 1),
    ("A2Sg1G3F", 4, 6, 1, 0, 1),
    ("A2Sg2G2F", 4, 5, 1, 0, 2),
    ("A2S1Sg1G2", 4, 5, 0, 1, 1),
    ("A2S1Sg1G2F", 4, 5, 1, 1, 1),
    ("A3Sg1G2F", 5, 5, 1, 0, 1),
    ("A3S1G2F", 5, 5, 1, 1, 0),
    ("A3Sg1G3", 5, 6, 0, 0, 1),
    ("A3Sg1G3F", 5, 6, 1, 0, 1),
    ("A3S1G3", 5, 6, 0, 1, 0),
    ("A3S1G3F", 5, 6, 1, 1, 0),
    ("A3Sg1G4", 5, 7, 0, 0, 1),
    ("A3Sg1G4F", 5, 7, 1, 0, 1),
    ("A3S1G4", 5, 7, 0, 1, 0),
    ("A3S1G4F", 5, 7, 1, 1, 0),
    ("A3Sg1G5", 5, 8, 0, 0, 1),
    ("A3Sg1G5F", 5, 8, 1, 0, 1),
    ("A3S1G5", 5, 8, 0, 1, 0),
    ("A3S1G5F", 5, 8, 1, 1, 0),
    ("A3Sg2G3", 5, 6, 0, 0, 2),
    ("A3Sg2G3F", 5, 6, 1, 0, 2),
    ("A3S2G3", 5, 6, 0, 2, 0),
    ("A3S2G3F", 5, 6, 1, 2, 0),
    ("A3Sg2G4", 5, 7, 0, 0, 2),
    ("A3Sg2G4F", 5, 7, 1, 0, 2),
    ("A3S2G4", 5, 7, 0, 2, 0),
    ("A3S2G4F", 5, 7, 1, 2, 0),
    ("A3Sg3G3", 5, 6, 0, 0, 3),
    ("A3Sg3G3F", 5, 6, 1, 0, 3),
    ("A3S3G3", 5, 6, 0, 3, 0),
    ("A3S3G3F", 5, 6, 1, 3, 0),
    ("A2Sg1G2F2 (LeX)", 4, 5, 2, 0, 1),
    ("A2S1G2F2 (LeX)", 4, 5, 2, 1, 0),
    ("A3Sg1G3F2 (LeX)", 5, 6, 2, 0, 1),
    ("A3S1G3F2 (LeX)", 5, 6, 2, 1, 0),
    ("A3Sg1G4F2 (LeX)", 5, 7, 2, 0, 1),
    ("A3S1G4F2 (LeX)", 5, 7, 2, 1, 0),
    ("A3Sg2G3F2 (LeX)", 5, 6, 2, 0, 2),
    ("A3S2G3F2 (LeX)", 5, 6, 2, 2, 0),
    ("A1G0M4", 3, 4, 0, 0, 0),
    ("A1G1M4", 3, 5, 0, 0, 0),
    ("A1G0M4F", 3, 4, 1, 0, 0),
    ("A1G1M4F", 3, 5, 1, 0, 0),
    ("A1G0M5", 3, 5, 0, 0, 0),
    ("A1G1M5", 3, 6, 0, 0, 0),
    ("A1G0M5F", 3, 5, 1, 0, 0),
    ("A1G1M5F", 3, 6, 1, 0, 0),
    ("A1G1M6", 3, 7, 0, 0, 0),
    ("A1G2M4F", 3, 6, 0, 0, 0),
    ("A1G2M5", 3, 7, 0, 0, 0),
    ("A1G2M4", 3, 6, 0, 0, 0),
    ("A1G2M4F", 3, 6, 1, 0, 0),
    ("A1G2M5F", 3, 7, 1, 0, 0),
    ("A2G1M5", 4, 6, 0, 0, 0),
    ("A2G1M5F", 4, 6, 1, 0, 0),
    ("A2G2M5", 4, 7, 0, 0, 0),
    ("A2G2M5F", 4, 7, 1, 0, 0),
    ("A2G3M5", 4, 8, 0, 0, 0),
    ("A2G3M5F", 4, 8, 1, 0, 0),
    ("A1S1G1M4", 3, 5, 0, 1, 0),
    ("A1S1G1M4F", 3, 5, 1, 1, 0),
    ("A1Sg1G1M4", 3, 5, 0, 0, 1),
    ("A1Sg1G1M4F", 3, 5, 1, 0, 1),
    ("A1S1G1M5", 3, 6, 0, 1, 0),
    ("A1Sg1G1M5", 3, 6, 0, 0, 1),
    ("A1S1G1M5F", 3, 6, 1, 1, 0),
    ("A1Sg1G1M5F", 3, 6, 1, 0, 1),
    ("M3", 2, 3, 0, 0, 0),
    ("M4", 2, 4, 0, 0, 0),
    ("M5", 2, 5, 0, 0, 0),
    ("M6", 2, 6, 0, 0, 0),
    ("M7", 2, 7, 0, 0, 0),
    ("M8", 2, 8, 0, 0, 0),
    ("M9", 2, 9, 0, 0, 0),
    ("Hex(1)", 0, 1, 0, 0, 0),
    ("Hex(2)", 0, 2, 0, 0, 0),
    ("Hex(3)", 0, 3, 0, 0, 0),
    ("Hex(4)", 0, 4, 0, 0, 0),
    ("Hex(5)", 0, 5, 0, 0, 0),
    ("Hex(6)", 0, 6, 0, 0, 0),
    ("Hex(7)", 0, 7, 0, 0, 0),
    ("Hex(8)", 0, 8, 0, 0, 0),
    ("Hex(9)", 0, 9, 0, 0, 0),
    ("Hex(10)", 0, 10, 0, 0, 0),
]

# ---------------------------------------------------------------------------
# Derived lookup: composition → list of short names
# ---------------------------------------------------------------------------


def _build_comp_to_name_dict() -> dict[GlycanComposition, list[str]]:
    """Build a mapping from monosaccharide composition to all known short names.

    Multiple short names may share the same composition (e.g. hybrid
    structures with identical monosaccharide counts).
    """
    mapping: dict[GlycanComposition, list[str]] = {}
    for name, hexnac, hex_, fuc, neuac, neugc in GLYCAN_TABLE:
        comp = GlycanComposition(hexnac, hex_, fuc, neuac, neugc)
        mapping.setdefault(comp, []).append(name)
    return mapping


COMP_TO_NAME_DICT: dict[GlycanComposition, list[str]] = _build_comp_to_name_dict()

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_glycan_composition_list(composition_name: str) -> GlycanComposition:
    """Parse a Byonic-format composition string into a :class:`GlycanComposition`.

    Parameters
    ----------
    composition_name:
        A string such as ``"HexNAc(4)Hex(5)Fuc(1)NeuAc(1)NeuGc(1)"``.
        Components may appear in any order and any subset may be omitted.

    Returns
    -------
    GlycanComposition
        Named tuple with counts for each monosaccharide.  Fields that are
        absent in the input default to ``0``.

    Examples
    --------
    >>> get_glycan_composition_list("HexNAc(4)Hex(5)Fuc(1)")
    GlycanComposition(hexnac=4, hex=5, fuc=1, neuac=0, neugc=0)
    >>> get_glycan_composition_list("")
    GlycanComposition(hexnac=0, hex=0, fuc=0, neuac=0, neugc=0)
    """
    if not composition_name:
        return GlycanComposition(0, 0, 0, 0, 0)

    hexnac = 0
    hex_ = 0
    fuc = 0
    neuac = 0
    neugc = 0

    parts = composition_name.split(")")
    for part in parts:
        if not part:
            continue
        tokens = part.split("(")
        glycan, count = tokens[0], int(tokens[1])
        if glycan == "HexNAc":
            hexnac = count
        elif glycan == "Hex":
            hex_ = count
        elif glycan == "Fuc":
            fuc = count
        elif glycan == "NeuAc":
            neuac = count
        elif glycan == "NeuGc":
            neugc = count
        else:
            # Unknown monosaccharide type – return zeroed composition.
            return GlycanComposition(0, 0, 0, 0, 0)

    return GlycanComposition(hexnac, hex_, fuc, neuac, neugc)


def glycan_name_old_to_new(composition_name: str) -> str:
    """Convert a Byonic-format composition string to its short glycan name(s).

    Looks up the parsed composition in :data:`COMP_TO_NAME_DICT`.  If several
    short names share the same composition they are joined with ``"/"``.

    Parameters
    ----------
    composition_name:
        A Byonic-format string, e.g. ``"HexNAc(4)Hex(5)Fuc(1)"``.

    Returns
    -------
    str
        The matching short name(s), or the original *composition_name* if no
        match is found.

    Examples
    --------
    >>> glycan_name_old_to_new("HexNAc(4)Hex(5)Fuc(1)")
    'A2G2F'
    """
    comp = get_glycan_composition_list(composition_name)
    names = COMP_TO_NAME_DICT.get(comp)
    if names is not None:
        return "/".join(names)
    return composition_name


def get_glycan_motif(composition_str: str, new_name: str) -> list[str]:
    """Classify a glycan into structural motif categories.

    The classification mirrors the legacy ``getGlycanMotif`` method exactly.

    Parameters
    ----------
    composition_str:
        Byonic-format composition, e.g. ``"HexNAc(4)Hex(5)Fuc(1)"``.
    new_name:
        The short glycan name produced by :func:`glycan_name_old_to_new`.

    Returns
    -------
    list[str]
        A list of motif labels that apply to this glycan.  Possible values:

        * ``"Fucosylation"`` or ``"Afucosylation"`` (mutually exclusive)
        * ``"High mannose"``
        * ``"Sialylation"``
        * ``"NANA"`` (N-acetylneuraminic acid / NeuAc)
        * ``"NGNA"`` (N-glycolylneuraminic acid / NeuGc)
        * ``"LewisX"``
        * ``"Galactosylation"``

    Examples
    --------
    >>> get_glycan_motif("HexNAc(4)Hex(5)Fuc(1)", "A2G2F")
    ['Fucosylation', 'Galactosylation']
    >>> get_glycan_motif("HexNAc(2)Hex(5)", "M5")
    ['Afucosylation', 'High mannose']
    """
    motifs: list[str] = []

    # 1. Fucosylation status (always exactly one of the two)
    if "Fuc(" in composition_str:
        motifs.append("Fucosylation")
    else:
        motifs.append("Afucosylation")

    # 2. High mannose
    if "M" in new_name:
        motifs.append("High mannose")

    # 3. Sialylation (either NeuAc or NeuGc present)
    if "NeuAc" in composition_str or "NeuGc" in composition_str:
        motifs.append("Sialylation")

    # 4. Specific sialic acid types
    if "NeuAc" in composition_str:
        motifs.append("NANA")

    if "NeuGc" in composition_str:
        motifs.append("NGNA")

    # 5. Lewis X antigen
    if "LeX" in new_name:
        motifs.append("LewisX")

    # 6. Galactosylation – any "G" that is not "G0" and not part of "Gc"
    if "G" in new_name and "G0" not in new_name and "Gc" not in new_name:
        motifs.append("Galactosylation")

    return motifs


# ---------------------------------------------------------------------------
# Mass calculation
# ---------------------------------------------------------------------------

# Monoisotopic residue masses (Da) — mass of monosaccharide minus H₂O.
_UNIT_MASS: dict[str, float] = {
    "HexNAc": 203.07937,
    "Hex": 162.05282,
    "Fuc": 146.05791,
    "NeuAc": 291.09542,
    "NeuGc": 307.09033,
}

_WATER_MASS: float = 18.01056


def composition_to_mass(composition_str: str) -> float:
    """Calculate the monoisotopic residue mass of a glycan from its composition.

    This returns the **residue mass** (without water), which matches the mass
    values used by search engines like MSFragger in modification annotations.

    Parameters
    ----------
    composition_str:
        A Byonic-format string such as ``"HexNAc(3)Hex(3)Fuc(1)"``.

    Returns
    -------
    float
        Residue mass in Daltons (sum of monosaccharide residue masses).
        Returns ``0.0`` for empty or unparseable input.

    Examples
    --------
    >>> round(composition_to_mass("HexNAc(3)Hex(3)Fuc(1)"), 4)
    1241.4545
    """
    comp = get_glycan_composition_list(composition_str)
    if comp == GlycanComposition(0, 0, 0, 0, 0):
        return 0.0

    mass = (
        comp.hexnac * _UNIT_MASS["HexNAc"]
        + comp.hex * _UNIT_MASS["Hex"]
        + comp.fuc * _UNIT_MASS["Fuc"]
        + comp.neuac * _UNIT_MASS["NeuAc"]
        + comp.neugc * _UNIT_MASS["NeuGc"]
    )
    return mass
