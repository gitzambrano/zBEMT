"""The Pitt-Peters validity warning must reach the user, in English.

QR-5 requires English on every user-facing surface, and the linear
finite-state inflow theory has a validity limit that only a warning can
show. The engine measured that limit but kept the warning inside the disk
maps, where no interface reads it (`REPO-PITT-WARNING`, `PP-LINEAR-LIMITATION`).
"""
from __future__ import annotations

import re
import unittest
from dataclasses import replace

import numpy as np

from zbemt import api, studies, validation
from zbemt.models import FlightCondition


#: Portuguese function words with no English meaning. The original warning
#: mixed three of them into an otherwise English sentence.
PORTUGUESE_WORDS = ("disco", "com", "para", "nao", "uma", "dos", "das")


def _reversed_inflow_case():
    """Return a case whose Pitt-Peters inflow reverses over part of the disk."""
    project = api.open_project("projects/starter_rotor")
    config = dict(project.config)
    config.update({
        "Ne": 24, "Npsi": 36, "use_compressibility": False,
        "inflow_field_model": "pitt_peters_steady",
    })
    return studies.run_single_case(
        replace(project, config=config),
        FlightCondition(name="reversed inflow", rpm=400.0, mu_x=0.15,
                        collective_deg=12.0),
    )


class TestPittPetersWarningIsExported(unittest.TestCase):
    """The summary must carry the reversed fraction and the warning."""

    @classmethod
    def setUpClass(cls):
        cls.case = _reversed_inflow_case()

    def test_the_summary_reports_the_reversed_fraction(self):
        fraction = self.case.summary["pitt_peters_frac_reversed"]
        measured = float(np.mean(
            np.asarray(self.case.maps["lambda_total"], dtype=float) < 0.0))
        self.assertAlmostEqual(float(fraction), measured, places=12)
        self.assertGreater(float(fraction), 0.02)

    def test_the_summary_carries_the_warning_text(self):
        self.assertIn("pitt_peters_warning", self.case.summary)
        self.assertIn("Pitt-Peters", self.case.summary["pitt_peters_warning"])

    def test_the_warning_holds_no_portuguese_word(self):
        warning = self.case.summary["pitt_peters_warning"].lower()
        for word in PORTUGUESE_WORDS:
            with self.subTest(word=word):
                self.assertIsNone(re.search(rf"\b{word}\b", warning))

    def test_the_warning_is_written_as_complete_sentences(self):
        warning = self.case.summary["pitt_peters_warning"]
        self.assertGreaterEqual(len(re.findall(r"[A-Z][^.]*\.", warning)), 2)

    def test_result_validation_reports_the_warning_to_the_user(self):
        issues = validation.validate_results(self.case.summary)
        messages = [issue.message for issue in issues if issue.level == "warning"]
        self.assertTrue(any("Pitt-Peters" in message for message in messages))

    def test_a_case_inside_the_linear_range_reports_no_warning(self):
        project = api.open_project("projects/starter_rotor")
        config = dict(project.config)
        config.update({
            "Ne": 24, "Npsi": 36, "use_compressibility": False,
            "inflow_field_model": "pitt_peters_steady",
        })
        case = studies.run_single_case(
            replace(project, config=config),
            FlightCondition(name="linear range", rpm=400.0, mu_x=0.0,
                            collective_deg=8.0),
        )
        self.assertEqual(float(case.summary["pitt_peters_frac_reversed"]), 0.0)
        self.assertNotIn("pitt_peters_warning", case.summary)


if __name__ == "__main__":
    unittest.main()
