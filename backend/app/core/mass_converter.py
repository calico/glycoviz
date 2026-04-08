"""Convert glycan masses to Byonic-format composition strings.

Ported from the legacy ``Mass_converter`` class in
``glycan_nomenclature_converter/mass_converter.py``.  Key changes from the
original implementation:

* PEP 8 class naming (``MassConverter``).
* The glycan-mass CSV path is injected via the constructor instead of being
  hard-coded.
* The ``Glycans`` helper class is replaced by the canonical
  :data:`~app.core.glycan_lookup.COMP_TO_NAME_DICT` mapping – no data
  duplication.
* Full type annotations (Python 3.11+).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from app.core.glycan_lookup import COMP_TO_NAME_DICT

# The mass-matching tolerance used by the legacy code (in Daltons).
_MASS_TOLERANCE_DA: float = 0.02

# If a candidate mass exceeds the query mass by more than this value the
# search can be terminated early (the list is assumed to be sorted).
_EARLY_EXIT_DA: float = 1.0


class MassConverter:
    """Look up glycan composition strings by observed mass.

    The converter loads a two-column CSV file (mass, composition) at
    construction time and keeps the data in memory for fast repeated lookups.

    Parameters
    ----------
    mass_file_path:
        Path to a CSV file whose first column is a monoisotopic mass
        (``float``) and whose second column is the corresponding Byonic-format
        composition string.  The first row is treated as a header and skipped.
    """

    def __init__(self, mass_file_path: str) -> None:
        self.glycan_masses: list[float] = []
        self.glycan_comps: list[str] = []

        with Path(mass_file_path).open(newline="") as csvfile:
            reader = csv.reader(csvfile, delimiter=",")
            for row_idx, row in enumerate(reader):
                if row_idx == 0:
                    # Skip the header row.
                    continue
                self.glycan_masses.append(float(row[0]))
                self.glycan_comps.append(row[1])

        # Re-use the single canonical lookup table from glycan_lookup instead
        # of duplicating the Glycans class.
        self.comp_to_name_dict = COMP_TO_NAME_DICT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_glycan_comp(self, mass_string: str) -> str:
        """Convert a semicolon- or comma-separated mass string to compositions.

        Each numeric value in *mass_string* is matched against the pre-loaded
        mass table.  A match is accepted when the absolute difference is less
        than **0.02 Da**.  Because the mass table is sorted in ascending order,
        the search exits early once the candidate mass exceeds the query mass
        by more than **1 Da**.

        Parameters
        ----------
        mass_string:
            One or more observed masses separated by ``;`` or ``,``.
            Example: ``"1234.56; 2345.67"`` or ``"1234.56,2345.67"``.
            or format of "9N(1079.4017)" or "6C(57.0215),2N(162.0528)"
            OR
            other format like: 1xHexNAc(5)Hex(6)Fuc(1)NeuAc(2)NeuGc(1) [N1]; 1xHexNAc(2)Fuc(1) [N4]

        Returns
        -------
        str
            A ``"; "``-joined string of the matched Byonic-format compositions,
            or an empty string if *mass_string* is empty or no masses matched.

        Examples
        --------
        >>> mc = MassConverter("example_data/glycan_masses.csv")
        >>> mc.get_glycan_comp("1234.56; 2345.67")  # doctest: +SKIP
        'HexNAc(4)Hex(5)Fuc(1); HexNAc(5)Hex(6)NeuGc(2)'
        """
        # Normalise the delimiter: the legacy code accepted both "," and ";".
        mass_string = mass_string.replace(",", ";").replace(" ", "")

        if not mass_string.strip():
            return ""

        # if the field is using glycan_compositio redirect, no need to convert
        glycan_symbols = [
            "HexNAc(",
            "Hex(",
            "Fuc(",
            "NeuAc(",
            "NeuGc(",
            "GalNAc",
            "Gal",
            "GlcNAc",
            "Fuc",
            "Sia",
            "Man",
            "Glc",
            "Xyl",
        ]
        if any(symbol in mass_string for symbol in glycan_symbols):
            has_glycan_comp = True
            names = mass_string.split(";")
            matched_comps: list[str] = []
            for name in names:
                # find any glycan_symbol at the earlies position in the name
                symbol_positions = [
                    name.find(symbol) for symbol in glycan_symbols if symbol in name
                ]
                if len(symbol_positions) == 0:
                    continue
                earliest_symbol_pos = min(symbol_positions)
                # fine the last ) in the name
                last_paren_pos = name.rfind(")")
                if last_paren_pos > earliest_symbol_pos:
                    matched_comps.append(name[earliest_symbol_pos : last_paren_pos + 1])
            return "; ".join(matched_comps)

        # if not compostion, must have float number based glycan mass
        nums = mass_string.split(";")

        matched_comps: list[str] = []

        for num in nums:
            num = num.strip()

            # find the first float number in the string with decimal point, which is the mass value
            m = re.search(r"-?\d+\.\d+", num)
            if m:
                num = m.group()
            if not num:
                continue

            target = float(num)
            for i, candidate_mass in enumerate(self.glycan_masses):
                if abs(candidate_mass - target) < _MASS_TOLERANCE_DA:
                    matched_comps.append(self.glycan_comps[i])
                    break
                # Assume the mass list is sorted – stop early if we have
                # overshot the target by more than 1 Da.
                if candidate_mass - target > _EARLY_EXIT_DA:
                    break

        return "; ".join(matched_comps)
