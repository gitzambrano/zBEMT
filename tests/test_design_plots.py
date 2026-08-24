"""Verify the design-tools plots against synthetic Results objects.

The geometry comparison groups results by ``geometry_label``, and the
optimization convergence reads the evaluation record of a study. The
tests build tiny summary-only Results objects, so no engine run happens
here. Assertions cover saved files, returned axes, series counts, and
the fallbacks for missing fields.
"""

import tempfile
import unittest
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes

from zbemt.models import Results
from zbemt.viz import plots


def _labeled_lines(panel):
    """Data lines of a panel, with the unlabeled guide lines excluded."""
    return [line for line in panel.get_lines()
            if line.get_label() and not line.get_label().startswith("_")]


def _panels(axes_out):
    """The axes behind a return value, a single axis or an array alike."""
    if isinstance(axes_out, np.ndarray):
        return list(axes_out.ravel())
    return [axes_out]


def _geometry_result(label, mu_x, condition_name, scale=1.0):
    """One synthetic result whose summary carries the four default fields."""
    summary = {
        "geometry_label": label,
        "mu_x": mu_x,
        "CT": scale * (0.0050 + 0.0100 * mu_x),
        "FM": scale * (0.7000 + 0.0500 * mu_x),
        "CP": scale * (0.0020 + 0.0010 * mu_x),
        "eta_prop": min(0.99, scale * (0.600 + 0.100 * mu_x)),
    }
    return Results(summary=summary, maps={}, condition_name=condition_name)


def _two_variant_results(mu_x_values=(0.1, 0.2)):
    """Variant-major list of two geometries over the same two conditions."""
    results = []
    for label, scale in (("Baseline", 1.0), ("Tapered", 1.15)):
        for mu_x in mu_x_values:
            results.append(_geometry_result(label, mu_x,
                                            f"case {mu_x:g}", scale))
    return results


class TestPlotGeometryComparison(unittest.TestCase):

    def test_fname_writes_non_empty_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "comparison.png"
            plots.plot_geometry_comparison(_two_variant_results(),
                                           fname=str(path))
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)

    def test_ax_returns_one_panel_per_field_and_one_series_per_label(self):
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_comparison(_two_variant_results(), ax=ax)
            self.assertIsInstance(out, np.ndarray)
            panels = _panels(out)
            self.assertEqual(len(panels), 4)
            for panel in panels:
                self.assertEqual(len(_labeled_lines(panel)), 2,
                                 "expected one series per geometry label")
                self.assertIn("mu", panel.get_xlabel())
            legend = panels[0].get_legend()
            self.assertIsNotNone(legend, "the shared legend is missing")
            self.assertEqual(legend.get_title().get_text(), "Geometry")
            titles = [t.get_text() for t in fig.texts]
            self.assertTrue(any("Geometry comparison" in t for t in titles))
            self.assertTrue(any("2 variants" in t for t in titles))
            self.assertTrue(any("2 conditions" in t for t in titles))
        finally:
            plt.close(fig)

    def test_colors_match_across_panels_for_the_same_label(self):
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_comparison(_two_variant_results(), ax=ax)
            panels = _panels(out)

            def color_of(panel, label):
                for line in _labeled_lines(panel):
                    if line.get_label() == label:
                        return line.get_color()
                self.fail(f"missing series {label!r}")

            self.assertEqual(color_of(panels[0], "Baseline"),
                             color_of(panels[1], "Baseline"))
            self.assertEqual(color_of(panels[0], "Tapered"),
                             color_of(panels[-1], "Tapered"))
        finally:
            plt.close(fig)

    def test_constant_mu_x_switches_to_case_index(self):
        """With a single distinct ``mu_x`` value there is nothing to sweep,
        so the curves sit against the case index and each tick names its
        condition. Long tick names rotate by 30 degrees."""
        results = []
        for label in ("Baseline", "Tapered"):
            for name in ("hover", "fast forward flight"):
                results.append(Results(
                    summary={"geometry_label": label, "mu_x": 0.0,
                             "CT": 0.01},
                    maps={}, condition_name=name))
        fig, ax = plt.subplots()
        try:
            # Only CT exists in these summaries, so a single panel results
            # and the single axis itself comes back.
            out = plots.plot_geometry_comparison(results, ax=ax)
            self.assertIsInstance(out, Axes)
            self.assertNotIn("mu", out.get_xlabel())
            self.assertIn("hover", [t.get_text() for t in out.get_xticklabels()])
            self.assertIn("fast forward flight",
                          [t.get_text() for t in out.get_xticklabels()])
            rotations = {t.get_rotation() for t in out.get_xticklabels()}
            self.assertEqual(rotations, {30.0})
        finally:
            plt.close(fig)

    def test_only_present_default_fields_become_panels(self):
        """A quantity absent from every summary must not leave an empty
        panel behind."""
        results = []
        for label in ("A", "B"):
            for mu_x in (0.1, 0.2):
                results.append(Results(
                    summary={"geometry_label": label, "mu_x": mu_x,
                             "CP": 0.003 + 0.001 * mu_x},
                    maps={}, condition_name=f"c{mu_x:g}"))
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_comparison(results, ax=ax)
            self.assertIsInstance(out, Axes)
            self.assertIn("C_P", out.get_ylabel())
            self.assertEqual(len(_labeled_lines(out)), 2)
        finally:
            plt.close(fig)

    def test_no_default_field_falls_back_to_ct_panel(self):
        """Without any default quantity the figure still produces its CT
        panel, and an unusable panel states why it is empty instead of
        staying blank."""
        results = []
        for label in ("A", "B"):
            results.append(Results(
                summary={"geometry_label": label, "Thrust": 12.0},
                maps={}, condition_name="hover"))
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_comparison(results, ax=ax)
            self.assertIsInstance(out, Axes)
            self.assertIn("C_T", out.get_ylabel())
            self.assertFalse(_labeled_lines(out))
            self.assertTrue(out.texts,
                            "an empty panel must explain itself")
        finally:
            plt.close(fig)


class TestPlotGeometryDelta(unittest.TestCase):
    """Percent change of every variant against one base geometry."""

    @staticmethod
    def _result(label, name, mu_x, FM):
        return Results(summary={"geometry_label": label, "mu_x": mu_x,
                                  "FM": FM},
                       maps={}, condition_name=name)

    def _bar_results(self):
        """Variant-major list with one constant mu_x, known percents.

        A sits 10% above base at both conditions, B 10% below."""
        values = {"base": (0.50, 0.60), "A": (0.55, 0.66),
                  "B": (0.45, 0.54)}
        results = []
        for label, fms in values.items():
            for name, fm in zip(("hover", "cruise"), fms):
                results.append(self._result(label, name, 0.0, fm))
        return results

    def test_fname_writes_non_empty_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delta.png"
            plots.plot_geometry_delta(self._bar_results(), "FM",
                                      fname=str(path))
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)

    def test_known_percents_and_base_excluded(self):
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_delta(self._bar_results(), "FM",
                                            ax=ax)
            heights = sorted(p.get_height() for p in out.patches)
            np.testing.assert_allclose(heights,
                                       [-10.0, -10.0, 10.0, 10.0])
            labels = [line.get_label() for line in _labeled_lines(out)]
            self.assertNotIn("base", labels)
            titles = [t.get_text() for t in out.figure.texts]
            suptitle = next(t for t in titles if t)
            self.assertIn("$FM$", suptitle)
            self.assertIn("relative to base", suptitle)
            self.assertIn("2 conditions", suptitle)
            self.assertIn("vs base [%]", out.get_ylabel())
        finally:
            plt.close(fig)

    def test_zero_base_falls_back_to_absolute_differences(self):
        results = []
        for label, fms in (("base", (0.0, 0.0)), ("A", (0.05, -0.02))):
            for name, fm in zip(("hover", "cruise"), fms):
                results.append(self._result(label, name, 0.0, fm))
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_delta(results, "FM", ax=ax)
            heights = sorted(p.get_height() for p in out.patches)
            np.testing.assert_allclose(heights, [-0.02, 0.05])
            self.assertIn("(absolute)", out.get_ylabel())
            texts = [t.get_text() for t in out.figure.texts]
            self.assertTrue(any("(absolute)" in t for t in texts))
        finally:
            plt.close(fig)

    def test_mu_x_sweep_draws_one_line_per_variant(self):
        results = []
        for label, fms in (("base", (0.50, 0.50)),
                            ("A", (0.55, 0.60)),
                            ("B", (0.40, 0.60))):
            for mu_x, fm in zip((0.1, 0.2), fms):
                results.append(self._result(label, f"c{mu_x:g}", mu_x, fm))
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_delta(results, "FM", ax=ax)
            lines = _labeled_lines(out)
            self.assertEqual([line.get_label() for line in lines],
                             ["A", "B"])
            series_a = next(line for line in lines
                            if line.get_label() == "A")
            np.testing.assert_allclose(series_a.get_xdata(), [0.1, 0.2])
            np.testing.assert_allclose(series_a.get_ydata(), [10.0, 20.0])
            self.assertIn("mu", out.get_xlabel())
            zero_lines = [line for line in out.get_lines()
                          if abs(line.get_ydata()[0]) < 1e-12]
            self.assertTrue(zero_lines, "the zero reference is missing")
        finally:
            plt.close(fig)

    def test_long_case_names_rotate_like_the_comparison_plot(self):
        results = []
        for name, fm_base, fm_a in (("hover", 0.50, 0.55),
                                     ("fast forward flight", 0.60, 0.66)):
            results.append(self._result("base", name, 0.0, fm_base))
            results.append(self._result("A", name, 0.0, fm_a))
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_delta(results, "FM", ax=ax)
            rotations = {t.get_rotation() for t in out.get_xticklabels()}
            self.assertEqual(rotations, {30.0})
        finally:
            plt.close(fig)

    def test_empty_input_draws_an_explanation(self):
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_delta([], "FM", ax=ax)
            self.assertIs(out, ax)
            self.assertEqual(_labeled_lines(out), [])
            self.assertTrue(out.texts, "an empty input must explain itself")
        finally:
            plt.close(fig)

    def test_missing_base_variant_draws_an_explanation(self):
        results = [self._result("A", "hover", 0.0, 0.55)]
        fig, ax = plt.subplots()
        try:
            out = plots.plot_geometry_delta(results, "FM", ax=ax,
                                            base_label="base")
            message = " ".join(t.get_text() for t in out.texts)
            self.assertIn("base", message)
            self.assertEqual(_labeled_lines(out), [])
        finally:
            plt.close(fig)


class TestPlotOptimizationConvergence(unittest.TestCase):

    def _history(self):
        return [{"eval": 1, "FM": 0.50},
                {"eval": 2, "FM": 0.72},
                {"eval": 3, "FM": 0.61},
                {"eval": 4, "FM": 0.80}]

    def test_fname_writes_non_empty_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "convergence.png"
            plots.plot_optimization_convergence(self._history(), "FM",
                                                fname=str(path))
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)

    def test_ax_is_returned_and_carries_points_and_running_best(self):
        fig, ax = plt.subplots()
        try:
            out = plots.plot_optimization_convergence(self._history(), "FM",
                                                      ax=ax)
            self.assertIs(out, ax)
            self.assertEqual(len(ax.get_lines()), 2)
            raw = next(line for line in ax.get_lines()
                       if line.get_label() == "evaluation")
            np.testing.assert_allclose(raw.get_xdata(), [1.0, 2.0, 3.0, 4.0])
            best = next(line for line in ax.get_lines()
                        if line.get_label() == "best so far (minimize)")
            np.testing.assert_allclose(best.get_ydata(),
                                       [0.50, 0.50, 0.50, 0.50])
            self.assertIn("$FM$", ax.get_ylabel())
            self.assertEqual(ax.get_xlabel(), "Evaluation")
            self.assertEqual(ax.get_title(), "Optimization convergence")
            self.assertTrue(ax.get_xgridlines())
            self.assertAlmostEqual(ax.get_xgridlines()[0].get_alpha(), 0.3)
        finally:
            plt.close(fig)

    def test_maximize_follows_the_cumulative_maximum(self):
        fig, ax = plt.subplots()
        try:
            plots.plot_optimization_convergence(self._history(), "FM",
                                                ax=ax, mode="maximize")
            best = next(line for line in ax.get_lines()
                        if line.get_label() == "best so far (maximize)")
            np.testing.assert_allclose(best.get_ydata(),
                                       [0.50, 0.72, 0.72, 0.80])
        finally:
            plt.close(fig)

    def test_rows_without_a_finite_objective_are_skipped(self):
        """Rows without the objective key, and rows with a non-finite
        value, are absent from a real record. They must not erase the
        good evaluations nor break the drawing."""
        history = [{"eval": 1, "FM": 0.50},
                   {"eval": 2},
                   {"eval": 3, "FM": float("nan")},
                   {"eval": 4, "FM": 0.60}]
        fig, ax = plt.subplots()
        try:
            plots.plot_optimization_convergence(history, "FM", ax=ax)
            raw = next(line for line in ax.get_lines()
                       if line.get_label() == "evaluation")
            np.testing.assert_allclose(raw.get_xdata(), [1.0, 4.0])
            np.testing.assert_allclose(raw.get_ydata(), [0.50, 0.60])
        finally:
            plt.close(fig)

    def test_unknown_objective_falls_back_to_the_key_itself(self):
        fig, ax = plt.subplots()
        try:
            plots.plot_optimization_convergence(
                [{"eval": 1, "custom_metric": 1.0}], "custom_metric", ax=ax)
            self.assertEqual(ax.get_ylabel(), "custom_metric")
        finally:
            plt.close(fig)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            plots.plot_optimization_convergence(self._history(), "FM",
                                                mode="maximise")

    def test_empty_history_still_draws_an_explanation(self):
        fig, ax = plt.subplots()
        try:
            out = plots.plot_optimization_convergence([], "FM", ax=ax)
            self.assertIs(out, ax)
            self.assertEqual(ax.get_lines(), [])
            self.assertTrue(ax.texts, "an empty record must explain itself")
        finally:
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
