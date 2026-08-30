"""The axis nomenclature the user reads must not change by accident.

Rotor/propeller axis names are produced today by several independent
tables (`api._COLUMN_SYMBOL`, `viz/plots._SUMMARY_KEY_LABELS`,
`studies._SIMBOLO_DE_VARIAVEL`, `gui/widgets.CONDITION_UNITS`) that are
being unified into `zbemt/nomenclature.py`. A unification is only a
unification if the strings come out the same afterwards -- and "the same" is
only checkable against a record of what they are.

`tests/data/nomenclature_snapshot.json` is that record, produced by
`tools/nomenclature_snapshot.py`. This test compares it against the live
output, surface by surface, so a failure names the exact table that moved
instead of reporting "some label is different somewhere".

Changing a label on purpose is done by regenerating the file:

    python tools/nomenclature_snapshot.py

which puts the change in the commit diff, where it can be read.
"""
import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "nomenclature_snapshot.json"


def _snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


class TestSnapshotIsPresent(unittest.TestCase):
    def test_snapshot_file_exists(self):
        self.assertTrue(
            SNAPSHOT_PATH.is_file(),
            f"{SNAPSHOT_PATH} is missing -- run `python tools/nomenclature_snapshot.py`",
        )

    def test_every_surface_is_recorded(self):
        """A new surface added to the generator without regenerating the file
        would leave that surface unchecked -- which is the one failure mode a
        snapshot test cannot detect on its own."""
        from tools import nomenclature_snapshot

        recorded = set(_snapshot())
        generated = set(nomenclature_snapshot.collect())
        if not nomenclature_snapshot.has_qt():
            # No Qt on this machine (the engine and CLI run without it on
            # purpose): the GUI surfaces are not produced, so they are not
            # checked either. The file still records them, for the machines
            # that do have it.
            recorded -= set(nomenclature_snapshot.GUI_SURFACES)
        self.assertEqual(sorted(recorded), sorted(generated))


class TestSurfacesMatchSnapshot(unittest.TestCase):
    """One test per surface: the failure message names the table that moved."""

    @classmethod
    def setUpClass(cls):
        from tools import nomenclature_snapshot

        cls.expected = _snapshot()
        cls.current = nomenclature_snapshot.collect()

    def _compare(self, surface: str):
        if surface not in self.current:
            self.skipTest(f"'{surface}' is a GUI surface and Qt is not available")
        self.assertEqual(
            self.expected[surface], self.current[surface],
            f"'{surface}' changed. If deliberate, regenerate with "
            f"`python tools/nomenclature_snapshot.py` and review the diff.",
        )

    def test_summary_symbols(self):
        self._compare("summary_symbols")

    def test_summary_units(self):
        self._compare("summary_units")

    def test_primary_columns(self):
        self._compare("primary_columns")

    def test_suppressed_columns(self):
        self._compare("suppressed_columns")

    def test_axis_labels(self):
        self._compare("axis_labels")

    def test_condition_labels(self):
        self._compare("condition_labels")

    def test_factorial_slots(self):
        self._compare("factorial_slots")

    def test_condition_units(self):
        self._compare("condition_units")

    def test_default_unit(self):
        self._compare("default_unit")

    def test_slot_labels(self):
        self._compare("slot_labels")


if __name__ == "__main__":
    unittest.main()
