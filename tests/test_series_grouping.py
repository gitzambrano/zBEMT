"""Series grouping by TOLERANCE, text labels and condition names with
symbols -- the three defects seen on the same screen of the Results tab
(alpha sweep = -10, -5, 0, 5, 10 over mu_x = 0..0.4):

* the legend had ~18 curves ("alpha_rotor=-10.001", "-9.999",
  "-10.002"...) because `alpha_rotor_deg` is reconstructed by
  ``atan2(Vz, V)`` and floating-point noise passed through the rounding grid;
* the X/Y/grouping combos showed raw mathtext (``$\\mu_x$ [-]``);
* each case name was the RAW field name (``mu_x=0_alpha_deg=-10``).
"""
import unittest

import numpy as np

from zbemt import api, studies
from zbemt.models import Results
from zbemt.viz import plots


def _result(**summary) -> Results:
    """Minimal `Results` -- just the `summary`, which is all the plots read."""
    return Results(summary=dict(summary), maps={}, condition_name=summary.get("name", ""))


class TestGroupingMap(unittest.TestCase):

    def test_noise_below_the_tolerance_becomes_a_single_series(self):
        # exactly the values read on screen
        raw = [-10.002, -10.001, -10.0, -9.999, -9.997]
        mapping = plots.grouping_map(raw, 0.01)
        self.assertEqual(len(set(mapping.values())), 1)
        self.assertAlmostEqual(next(iter(set(mapping.values()))), -10.0, places=9)

    def test_legitimate_sweep_stays_separated(self):
        mapping = plots.grouping_map([-10.0, -5.0, 0.0, 5.0, 10.0], 0.01)
        self.assertEqual(len(set(mapping.values())), 5)

    def test_step_smaller_than_tolerance_is_merged_on_purpose(self):
        """The tolerance is the USER's: increased, it merges a fine sweep --
        that is what it means, not a defect."""
        mapping = plots.grouping_map([0.0, 0.05, 0.1, 0.15], 0.2)
        self.assertEqual(len(set(mapping.values())), 1)

    def test_zero_tolerance_falls_back_to_the_previous_behavior(self):
        mapping = plots.grouping_map([-10.001, -10.0, -9.999], 0.0)
        self.assertEqual(len(set(mapping.values())), 3)

    def test_negative_zero_does_not_become_its_own_series(self):
        mapping = plots.grouping_map([-0.0002, 0.0003], 0.01)
        keys = set(mapping.values())
        self.assertEqual(len(keys), 1)
        # "-0" and "0" format differently and would become two legends
        self.assertEqual(f"{next(iter(keys)):g}", "0")

    def test_non_numeric_values_are_keys_of_themselves(self):
        mapping = plots.grouping_map(["newton", "aitken", 1.0], 0.01)
        self.assertEqual(mapping["newton"], "newton")
        self.assertEqual(mapping["aitken"], "aitken")


class TestPlotXYGroupsWithTolerance(unittest.TestCase):
    """The path of truth: `plot_xy` with the alpha noise from the report."""

    def _results(self):
        alphas = [-10.002, -10.001, -10.0, -9.999, -9.997]
        return [_result(mu_x=0.05 * (i + 1), alpha_rotor_deg=a, CT=0.01 * (i + 1))
                for i, a in enumerate(alphas)]

    def _n_curves(self, tol):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        try:
            plots.plot_xy(self._results(), x_key="mu_x", y_key="CT",
                          group_by="alpha_rotor_deg", ax=ax, group_tol=tol)
            return len(ax.get_lines())
        finally:
            plt.close(fig)

    def test_one_curve_with_the_default_tolerance(self):
        # -1 for the horizontal reference line (`axhline`) that plot_xy draws
        self.assertEqual(self._n_curves(plots.DEFAULT_GROUP_TOLERANCE) - 1, 1)

    def test_five_curves_with_no_tolerance_at_all(self):
        """The reported defect, reproduced: without tolerance, one curve per
        noise point."""
        self.assertEqual(self._n_curves(0.0) - 1, 5)

    def test_legend_in_value_order(self):
        import matplotlib.pyplot as plt
        results = [_result(mu_x=0.1, alpha_rotor_deg=a, CT=0.01)
                   for a in (0.0, -10.0, -5.0, 10.0, 5.0)]
        fig, ax = plt.subplots()
        try:
            plots.plot_xy(results, x_key="mu_x", y_key="CT",
                          group_by="alpha_rotor_deg", ax=ax)
            labels = [t.get_text() for t in ax.get_legend().get_texts()]
        finally:
            plt.close(fig)
        values = [float(r.split("=")[1]) for r in labels]
        self.assertEqual(values, sorted(values))


class TestGridGroupsWithTolerance(unittest.TestCase):
    """Same defect in grid mode (auto-detection of secondary axes)."""

    def _results(self):
        out = []
        for i, alpha in enumerate([-10.002, -10.001, -10.0, -9.999]):
            out.append(_result(mu_x=0.1 * (i + 1), alpha_rotor_deg=alpha,
                               collective_deg=8.0, rpm=600.0, CT=0.01))
        return out

    def test_noisy_alpha_does_not_generate_a_series_per_point(self):
        import matplotlib.pyplot as plt
        fig = plots.plot_coefficients_vs_axis(self._results(), axis="mu_x")
        try:
            axis = fig.axes[0]
            # one curve + the horizontal reference line
            labels = [l.get_label() for l in axis.get_lines()
                      if not l.get_label().startswith("_")]
            self.assertLessEqual(len(labels), 1)
        finally:
            plt.close(fig)


class TestLabelAsText(unittest.TestCase):
    """Qt combos do not render LaTeX: the label must come out as text."""

    def test_mathtext_becomes_unicode(self):
        self.assertEqual(plots.summary_label_text("mu_x"), "μₓ [-]")
        self.assertEqual(plots.summary_label_text("Torque"), "Q [N·m]")

    def test_no_dollar_sign_or_backslash_left_over(self):
        for key in plots._SUMMARY_KEY_LABELS:
            text = plots.summary_label_text(key)
            with self.subTest(key=key):
                self.assertNotIn("$", text)
                self.assertNotIn("\\", text)
                self.assertNotIn("{", text)
                self.assertNotIn("}", text)

    def test_unknown_key_passes_intact(self):
        """`_summary_axis_label` falls back to the raw key name; its `_` is
        NOT subscripted ("cfg_solver", not "cfgₛolver")."""
        self.assertEqual(plots.summary_label_text("cfg_solver"), "cfg_solver")


class TestConditionNameWithSymbol(unittest.TestCase):

    def test_symbols_in_place_of_the_raw_field_name(self):
        name = studies.condition_name({"mu_x": 0.1, "alpha_deg": -10})
        self.assertEqual(name, "μ_x=0.1, α_rotor=-10°")

    def test_collective_and_rpm(self):
        self.assertEqual(studies.condition_name({"collective_deg": 8, "rpm": 600}),
                         "θ₀=8°, RPM=600")

    def test_unknown_variable_does_not_leave_the_condition_without_a_name(self):
        self.assertEqual(studies.condition_name({"xyz": 3}), "xyz=3")

    def test_factorial_names_with_symbol(self):
        from tests.helpers import make_studies_project
        project = make_studies_project()
        conditions = studies.build_factorial_conditions(
            project,
            [{"variable": "mu_x", "values": [0.0, 0.2]},
             {"variable": "alpha_deg", "values": [-5.0]}],
            {"collective_deg": 8.0, "rpm": 600.0})
        self.assertEqual([c.name for c in conditions],
                         ["μ_x=0, α_rotor=-5°", "μ_x=0.2, α_rotor=-5°"])

    def test_fixed_sideslip_reaches_every_generated_condition(self):
        """The batch offers sideslip as a fixed value only (never an axis),
        so every combination of the factorial carries the same psi_w."""
        from tests.helpers import make_studies_project
        project = make_studies_project()
        conditions = studies.build_factorial_conditions(
            project,
            [{"variable": "mu_x", "values": [0.0, 0.2]}],
            {"collective_deg": 8.0, "rpm": 600.0, "sideslip_deg": 12.5})
        self.assertEqual([c.sideslip_deg for c in conditions], [12.5, 12.5])

    def test_fixed_cyclic_reaches_every_generated_condition(self):
        """`SC-11`: the cyclic pair travels like sideslip -- a fixed value,
        never an axis, applied to every combination."""
        from tests.helpers import make_studies_project
        project = make_studies_project()
        conditions = studies.build_factorial_conditions(
            project,
            [{"variable": "mu_x", "values": [0.0, 0.2]}],
            {"collective_deg": 8.0, "rpm": 600.0,
             "cyclic_c_deg": -2.5, "cyclic_s_deg": 1.5})
        self.assertEqual([c.cyclic_c_deg for c in conditions], [-2.5, -2.5])
        self.assertEqual([c.cyclic_s_deg for c in conditions], [1.5, 1.5])

    def test_sideslip_defaults_to_zero_when_not_given(self):
        from tests.helpers import make_studies_project
        project = make_studies_project()
        conditions = studies.build_factorial_conditions(
            project,
            [{"variable": "mu_x", "values": [0.1]}],
            {"collective_deg": 8.0, "rpm": 600.0})
        self.assertEqual(conditions[0].sideslip_deg, 0.0)

    def test_file_name_falls_back_to_ascii(self):
        """The name is Unicode on screen; the FILE derived from it is not --
        it travels in zip and foreign file systems."""
        filename = api.sanitize_filename(studies.condition_name({"mu_x": 0.1, "alpha_deg": -10}))
        self.assertEqual(filename, "mu_x=0.1, alpha_rotor=-10deg")
        self.assertTrue(filename.isascii())

    def test_user_typed_accent_stays_untouched(self):
        """Only the symbols that the tool itself generates are transcribed."""
        self.assertEqual(api.sanitize_filename("Caso Padrão"), "Caso Padrão")


if __name__ == "__main__":
    unittest.main()
