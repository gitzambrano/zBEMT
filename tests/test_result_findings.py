"""`EN-9`. What a converged-looking result still has to admit.

The other validators answer "may this run?" and they run before the
engine does. This one answers a different question -- "may this number
be believed?" -- and it can only be asked afterwards, because the two
things it catches both produce a perfectly converged field:

  * a time-marched separation state whose last revolutions are still
    moving, so the answer is a transient being read as a periodic one;
  * a flap response past the angle where the small-angle flap equation
    stops being a small correction.

Neither is an error. The numbers are real; what is wrong is reading them
without knowing which assumption they left behind. So both are warnings,
and the Run Case tab shows them above the table they qualify.
"""
import unittest

from zbemt import api
from zbemt.validation import (FLAP_SMALL_ANGLE_LIMIT_DEG,
                              PERIODIC_RESIDUAL_TOLERANCE, validate_results)


class TestNothingToSay(unittest.TestCase):

    def test_an_empty_summary_is_silent(self):
        self.assertEqual(validate_results({}), [])

    def test_an_ordinary_rigid_run_is_silent(self):
        self.assertEqual(validate_results({"CT": 0.008, "CQ": 0.0006}), [])

    def test_a_settled_march_is_silent(self):
        self.assertEqual(validate_results({
            "dynamic_stall_periodic_residual": 0.1 * PERIODIC_RESIDUAL_TOLERANCE
        }), [])

    def test_a_small_flap_response_is_silent(self):
        self.assertEqual(validate_results({
            "beta_0_deg": 2.0, "beta_1c_deg": -1.5, "beta_1s_deg": 0.4}), [])


class TestTheMarchMustHaveSettled(unittest.TestCase):

    def test_a_moving_separation_state_is_reported(self):
        issues = validate_results({"dynamic_stall_periodic_residual": 0.02})
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].level, "warning")
        self.assertIn("periodic", issues[0].message)
        self.assertIn("EN-9", issues[0].message)

    def test_the_message_states_the_number_and_the_threshold(self):
        issues = validate_results({"dynamic_stall_periodic_residual": 0.02})
        self.assertIn("0.02", issues[0].message)
        self.assertIn(f"{PERIODIC_RESIDUAL_TOLERANCE:g}", issues[0].message)

    def test_the_threshold_itself_does_not_warn(self):
        """Exactly at the tolerance is settled, not unsettled."""
        self.assertEqual(validate_results({
            "dynamic_stall_periodic_residual": PERIODIC_RESIDUAL_TOLERANCE}), [])


class TestTheFlapMustStaySmall(unittest.TestCase):
    """The bound is the SUM of the harmonic amplitudes, which is the
    furthest the response can reach -- not the coning alone, and not the
    first harmonic alone. A blade coning at 14 deg and flapping 14 deg
    once per revolution reaches 28, and it is 28 that leaves the range."""

    def test_a_large_response_is_reported(self):
        issues = validate_results({"beta_0_deg": 14.2, "beta_1c_deg": -13.9,
                                    "beta_1s_deg": -2.9})
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].level, "warning")
        self.assertIn("small-angle", issues[0].message)

    def test_the_bound_adds_the_harmonics_to_the_coning(self):
        issues = validate_results({"beta_0_deg": 6.0, "beta_1c_deg": 8.0,
                                    "beta_1s_deg": 0.0})
        self.assertTrue(issues, "6 + 8 = 14 deg is past the limit")
        self.assertIn("14.0", issues[0].message)

    def test_coning_alone_below_the_limit_is_silent(self):
        self.assertEqual(validate_results({"beta_0_deg": 9.0}), [])

    def test_higher_harmonics_count_too(self):
        base = {"beta_0_deg": 4.0, "beta_1c_deg": 4.0, "beta_1s_deg": 0.0}
        self.assertEqual(validate_results(dict(base)), [])
        with_second = dict(base, beta_2c_deg=3.0, beta_2s_deg=0.0)
        self.assertTrue(validate_results(with_second),
                        "the second harmonic must count toward the bound")

    def test_a_rigid_run_reports_nothing_about_flapping(self):
        """A rigid blade has no `beta_0_deg` at all, and must not be
        given a flap warning by default."""
        self.assertEqual(validate_results({"CT": 0.01}), [])

    def test_the_limit_is_the_documented_one(self):
        self.assertEqual(FLAP_SMALL_ANGLE_LIMIT_DEG, 10.0)


class TestBothAtOnce(unittest.TestCase):

    def test_two_findings_are_both_reported(self):
        issues = validate_results({
            "dynamic_stall_periodic_residual": 0.05,
            "beta_0_deg": 15.0, "beta_1c_deg": 10.0, "beta_1s_deg": 0.0})
        self.assertEqual(len(issues), 2)


class TestTheApiExposesIt(unittest.TestCase):
    """`api` is the only path the GUI and the CLI may take."""

    def test_api_forwards_to_the_validator(self):
        summary = {"dynamic_stall_periodic_residual": 0.02}
        self.assertEqual([str(i) for i in api.validate_results(summary)],
                          [str(i) for i in validate_results(summary)])

    def test_the_findings_are_issues_with_a_level(self):
        for issue in api.validate_results({"beta_0_deg": 30.0}):
            self.assertIn(issue.level, ("error", "warning", "info"))
            self.assertTrue(str(issue).startswith("["))


if __name__ == "__main__":
    unittest.main()
