"""
test_golden_results.py
======================

The engine's OUTPUT had no regression net. A handful of tests lock a
hand-written value; everything else was covered only by "it ran without
raising", which a solver can do while returning numbers that are five
percent wrong in every case.

Two things happen here, both driven by one solve of every saved case of
every project under `projects/`:

  * `TestValuesMatch` compares the run against
    `tests/data/golden_results.json`, written by
    `tools/golden_snapshot.py`. A deliberate change to the physics is made
    visible by regenerating that file and reading its diff; an accidental
    one fails here, naming the project, the case and the quantity that
    moved.
  * `TestResultsArePhysicallyPlausible` asks the questions the golden
    file cannot: a recorded number is "correct" by construction, even if it
    is a NaN or a figure of merit of 4. These checks are independent of the
    record and would have caught a bad snapshot at the moment it was taken.

The two are deliberately not merged. The first says "this changed"; the
second says "this is wrong". A change that trips both is a regression; a
change that trips only the first is a decision to review.
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import golden_snapshot

GOLDEN_PATH = ROOT / "tests" / "data" / "golden_results.json"

#: Relative tolerance of the comparison. The snapshot keeps six decimals, so
#: this is loose enough to absorb a different BLAS or a different platform's
#: last-bit reduction order, and far tighter than any change to a model, a
#: mesh rule or an integration scheme.
RELATIVE_TOLERANCE = 1e-6

#: Below this the relative comparison is meaningless -- a coefficient that is
#: zero by symmetry oscillates in the last digits around zero -- so an
#: absolute floor takes over.
ABSOLUTE_FLOOR = 1e-9


class _SingleRun(unittest.TestCase):
    """Both suites need the same solve of every project, and that solve is
    the expensive part. Running it once in the `setUpClass` of a shared base
    keeps the file at about twenty seconds instead of forty."""

    @classmethod
    def setUpClass(cls):
        cls.current = golden_snapshot.collect()
        cls.expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


class TestValuesMatch(_SingleRun):

    def test_the_reference_file_exists(self):
        self.assertTrue(
            GOLDEN_PATH.is_file(),
            f"{GOLDEN_PATH} is missing -- run `python tools/golden_snapshot.py`")

    def test_every_project_and_every_case_is_registered(self):
        """A new example project, or a new saved case inside one, has to
        enter the record. Otherwise it is exercised by the run and checked
        by nothing -- the one failure mode a snapshot cannot detect on its
        own."""
        missing = []
        for project, cases in self.current.items():
            if project not in self.expected:
                missing.append(project)
                continue
            for case in cases:
                if case not in self.expected[project]:
                    missing.append(f"{project}/{case}")
        self.assertEqual(
            missing, [],
            "not in the golden record (run `python tools/golden_snapshot.py`): "
            + str(missing))

    def test_no_project_left_the_record(self):
        """The converse: a project deleted from `projects/` but left in the
        record would keep passing forever without ever running."""
        extra = [p for p in self.expected if p not in self.current]
        self.assertEqual(
            extra, [],
            "in the golden record but no longer on disk: " + str(extra))

    def test_the_numbers_did_not_change(self):
        deviations = []
        for project, cases in sorted(self.expected.items()):
            if project not in self.current:
                continue
            for case, values in sorted(cases.items()):
                if case not in self.current[project]:
                    continue
                got = self.current[project][case]
                for key, reference in sorted(values.items()):
                    with self.subTest(project=project, case=case, key=key):
                        self.assertIn(
                            key, got,
                            f"{project}/{case}: '{key}' is no longer produced")
                        now = got[key]
                        if isinstance(reference, str) or isinstance(now, str):
                            self.assertEqual(reference, now)
                            continue
                        scale = max(abs(reference), ABSOLUTE_FLOOR)
                        if abs(now - reference) > RELATIVE_TOLERANCE * scale:
                            deviations.append(
                                f"{project}/{case}/{key}: {reference} -> {now}")
        self.assertEqual(
            deviations, [],
            "the engine's numbers changed. If deliberate, regenerate with "
            "`python tools/golden_snapshot.py` and review the diff:\n  "
            + "\n  ".join(deviations))


class TestResultsArePhysicallyPlausible(_SingleRun):
    """Checks that hold whatever the numbers happen to be. Each one
    corresponds to a way a solve can fail while still returning a result."""

    def test_no_value_is_nan_or_infinite(self):
        """A NaN in the summary reaches the results table, the report and
        the CSV as an empty cell, and reads as "this column does not apply
        here" rather than as a failure."""
        bad = []
        for project, cases in sorted(self.current.items()):
            for case, values in sorted(cases.items()):
                for key, value in sorted(values.items()):
                    if value == "nan" or (isinstance(value, float)
                                          and not math.isfinite(value)):
                        bad.append(f"{project}/{case}/{key}")
        self.assertEqual(bad, [], "non-finite value in the summary: " + str(bad))

    #: Convergence floor. Hover reaches 100%; forward flight does not, and
    #: is not expected to: a few elements per solve sit in the reverse-flow
    #: region or at the root, where the inflow equation is close to
    #: singular and the fixed point stalls at the tolerance. Those elements
    #: carry almost no area weight. Measured worst case across the example
    #: projects today is 99.91%, so the floor is set well below that and
    #: still catches a solve that has genuinely fallen apart.
    MIN_CONVERGENCE_PCT = 99.0

    def test_every_solution_converges_almost_completely(self):
        """`convergence_pct` is the fraction of mesh elements that reached
        their fixed point. A case well below the floor means the leftover
        error is spread over enough of the disk to contaminate every
        integrated quantity, and an example project is a reference: it must
        not ship in that state."""
        bad = []
        for project, cases in sorted(self.current.items()):
            for case, values in sorted(cases.items()):
                pct = values.get("convergence_pct")
                if pct is not None and pct < self.MIN_CONVERGENCE_PCT:
                    bad.append(f"{project}/{case}: {pct}%")
        self.assertEqual(
            bad, [],
            f"case converged below {self.MIN_CONVERGENCE_PCT}%: " + str(bad))

    def test_total_power_is_the_sum_of_its_parts(self):
        """Induced plus profile is the whole of the shaft power. If the
        identity breaks, one of the two integrations is being done over a
        different mesh, or with a different weighting, than the total."""
        for project, cases in sorted(self.current.items()):
            for case, v in sorted(cases.items()):
                if not {"Power", "Power_i", "Power_p"} <= set(v):
                    continue
                with self.subTest(project=project, case=case):
                    self.assertAlmostEqual(
                        v["Power"], v["Power_i"] + v["Power_p"],
                        delta=1e-6 * max(abs(v["Power"]), 1.0),
                        msg=f"{project}/{case}: P is not P_i + P_p")

    #: The one case that autorotates, and why it is allowed to.
    #:
    #: `transition_evtol/cruise` is stated at mu_x = 0.35 with 8 deg of
    #: collective. At that advance ratio and that pitch the local inflow
    #: angle is negative over much of the advancing side, so
    #: `Ft_i = L*sin(phi)` is negative there and those sections DRIVE the
    #: shaft. The engine reports it correctly: the total shaft power of
    #: the case is negative too. It is the CASE that is not a powered
    #: cruise, not the solve that is wrong.
    #:
    #: This surfaced only when the Oye separation function was fixed.
    #: Before that, `f_st` returned "fully attached" for the reverse-flow
    #: region and `Cl_sep` reached 16603, which inflated this case's
    #: thrust from 2996 N to 10260 N and its induced power from -18 kW to
    #: +42 kW -- a defect that happened to hide the autorotation behind a
    #: plausible-looking positive number.
    AUTOROTATING = {("transition_evtol", "cruise", "Power_i")}

    def test_power_parts_are_not_negative(self):
        """Induced and profile power are both dissipative. Negative means
        either that the sign of a force was flipped somewhere, or that a
        section is driving the shaft -- which a POWERED rotor must not
        produce. A case that autorotates is neither, and the ones that do
        are named in `AUTOROTATING` with the reason."""
        bad = []
        for project, cases in sorted(self.current.items()):
            for case, v in sorted(cases.items()):
                for key in ("Power_i", "Power_p"):
                    if (project, case, key) in self.AUTOROTATING:
                        continue
                    if v.get(key, 0.0) < 0.0:
                        bad.append(f"{project}/{case}/{key} = {v[key]}")
        self.assertEqual(bad, [], "negative power component: " + str(bad))

    def test_every_named_autorotating_case_really_autorotates(self):
        """The exception above is not a mute button.

        A case may only sit on that list while its TOTAL shaft power is
        negative, which is what "the rotor is being driven" means. If a
        future change makes the case powered again, the entry has to go,
        and this is what says so."""
        for project, case, _key in sorted(self.AUTOROTATING):
            v = self.current.get(project, {}).get(case)
            with self.subTest(project=project, case=case):
                self.assertIsNotNone(
                    v, f"{project}/{case} is named as autorotating but no "
                       f"longer exists")
                self.assertLess(
                    v.get("Power", 0.0), 0.0,
                    f"{project}/{case} no longer autorotates (shaft power "
                    f"{v.get('Power')}), so it must not be excused from the "
                    f"negative-power check")

    def test_propulsive_efficiency_stays_below_one(self):
        """The propulsive efficiency is thrust power over shaft power. Above
        1 the propeller would be returning more than it is given."""
        bad = []
        for project, cases in sorted(self.current.items()):
            for case, v in sorted(cases.items()):
                eta = v.get("eta_prop")
                if eta is not None and eta > 1.0:
                    bad.append(f"{project}/{case}: eta = {eta}")
        self.assertEqual(bad, [], "propulsive efficiency above 1: " + str(bad))

    def test_torque_follows_the_sign_of_power(self):
        """Shaft power is torque times angular speed, and the angular speed
        is positive by convention. The two must therefore carry the same
        sign; opposite signs mean one of them was integrated with a flipped
        moment arm."""
        bad = []
        for project, cases in sorted(self.current.items()):
            for case, v in sorted(cases.items()):
                if "Torque" not in v or "Power" not in v:
                    continue
                if v["Torque"] * v["Power"] < 0.0:
                    bad.append(f"{project}/{case}: Q={v['Torque']}, P={v['Power']}")
        self.assertEqual(bad, [], "torque and power disagree in sign: " + str(bad))


if __name__ == "__main__":
    unittest.main()
