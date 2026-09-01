"""Tests for `viz/plots_interactive.py` -- the GUI's Plotly charts.

No matplotlib and no PyQt6 here: this only tests the returned `go.Figure`
(data, axes), in the same spirit as `test_plots.py`, but without depending
on `ax`. The widget that hosts the figure (`gui.common.PlotlyCanvasHost`)
has its own test in `test_gui_smoke.py`, skipped under
`QT_QPA_PLATFORM=offscreen` (see that class's docstring -- `QWebEngineView`
hangs in that mode).
"""
import os
import tempfile
import unittest

try:
    import plotly
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False

from zbemt import api
from zbemt.models import FlightCondition
from tests.helpers import make_api_fast_project


@unittest.skipUnless(_HAS_PLOTLY, "'interactive' extra not installed")
class TestCoefficientsVsAxis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = make_api_fast_project(os.path.join(self.tmp, "proj"))
        conds = [FlightCondition(name=f"c{i}", mu_x=0.05 * i, collective_deg=8.0, rpm=600.0)
                 for i in range(1, 4)]
        self.results = [api.run_case(self.project, c) for c in conds]

    def test_devolve_go_figure_com_11_paineis(self):
        from zbemt.viz import plots_interactive as pi
        fig = pi.coefficients_vs_axis(self.results, axis="mu_x")
        self.assertEqual(len(fig.data), 11, "one trace per coefficient")

    def test_eixo_x_e_o_que_variou(self):
        """Same guarantee as `plots.plot_coefficients_vs_axis`: the axis
        chosen by the user is what appears, not always mu_x."""
        conds = [FlightCondition(name=f"c{i}", mu_x=0.2, collective_deg=float(4 + 2 * i),
                                  rpm=600.0) for i in range(3)]
        results = [api.run_case(self.project, c) for c in conds]
        from zbemt.viz import plots_interactive as pi
        fig = pi.coefficients_vs_axis(results, axis="collective_deg")
        self.assertIn("collective", fig.layout.title.text)

    def test_labels_are_plain_text_not_mathtext(self):
        """Plotly does not interpret `$C_T$` (matplotlib syntax) without
        MathJax -- which we deliberately do not load (offline). A
        label with `$` would appear literally on the screen."""
        from zbemt.viz import plots_interactive as pi
        fig = pi.coefficients_vs_axis(self.results, axis="mu_x")
        for ann in fig.layout.annotations:
            self.assertNotIn("$", ann.text, f"panel title with raw mathtext: {ann.text}")

    def test_factorial_batch_with_two_axes_groups_by_secondary(self):
        """Regression: factorials with 2+ axes should auto-group by
        secondary variables (same behavior as matplotlib). Previously,
        Plotly always combined everything into a single curve."""
        # Factorial with mu_x and rpm varying: 3x2 = 6 combinations
        conds_mu_rpm = [
            FlightCondition(name="mu_x=0.05_rpm=600", mu_x=0.05, collective_deg=8.0, rpm=600.0),
            FlightCondition(name="mu_x=0.05_rpm=800", mu_x=0.05, collective_deg=8.0, rpm=800.0),
            FlightCondition(name="mu_x=0.10_rpm=600", mu_x=0.10, collective_deg=8.0, rpm=600.0),
            FlightCondition(name="mu_x=0.10_rpm=800", mu_x=0.10, collective_deg=8.0, rpm=800.0),
            FlightCondition(name="mu_x=0.15_rpm=600", mu_x=0.15, collective_deg=8.0, rpm=600.0),
            FlightCondition(name="mu_x=0.15_rpm=800", mu_x=0.15, collective_deg=8.0, rpm=800.0),
        ]
        results_mu_rpm = [api.run_case(self.project, c) for c in conds_mu_rpm]
        from zbemt.viz import plots_interactive as pi
        fig = pi.coefficients_vs_axis(results_mu_rpm, axis="mu_x")
        # With auto-grouping by rpm, we expect 2 series (rpm=600, rpm=800).
        # Each panel (CT, CQ, etc.) will have 2 traces (one per series).
        # Total: 11 panels × 2 traces per panel = 22 traces
        self.assertEqual(len(fig.data), 22, f"expected 22 traces (11 panels x 2 rpm), got {len(fig.data)}")

    def test_floating_point_noise_in_alpha_does_not_split_the_series(self):
        """Regression for reported bug: a factorial mu_x x alpha_deg solves
        each combination as Vz=tan(alpha)*V and reconstructs alpha_rotor_deg
        via atan2 -- the round-trip leaves noise of ~1e-4 (e.g. 2.99994
        instead of 3.0). Since `coefficients_vs_axis` (unlike the matplotlib
        version) does not have special exclusion of `alpha_deg`, it
        groups by `alpha_rotor_deg` normally -- but exact equality comparison
        was slicing EACH nominal alpha into a series per mu_x point (seen on
        screen: 7 nominal alphas becoming ~20 quasi-duplicate curves in
        the legend)."""
        from zbemt.models import Results
        results = []
        for i, mu_x in enumerate((0.05, 0.10, 0.15, 0.20)):
            for nominal in (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0):
                # DIFFERENT noise per mu_x point (the real case: each
                # combination goes through its own atan2/tan) -- noise
                # identical across all mu_x would not exercise the bug.
                noisy = nominal + (1e-4 if i % 2 == 0 else -1e-4) * (i + 1)
                s = dict(mu_x=mu_x, alpha_rotor_deg=noisy, collective_deg=8.0, rpm=600.0,
                          CT=0.01, CQ=0.001, FM=0.7, CY=0.0, CMx=0.0, CMy=0.0,
                          CH=0.0, CHp=0.0, CHi=0.0, CPp=0.0005, CPi=0.0005)
                results.append(Results(summary=s, maps={}, condition_name=f"mu_x={mu_x},a={nominal}"))
        from zbemt.viz import plots_interactive as pi
        fig = pi.coefficients_vs_axis(results, axis="mu_x")
        # 11 panels x 7 nominal alphas = 77 traces, no more (nor less)
        self.assertEqual(len(fig.data), 77,
                          f"expected 77 traces (11 panels x 7 alphas), got {len(fig.data)}")

    def test_overlay_mode_uses_series_labels(self):
        """Overlay mode with explicit series_labels works."""
        labels = ["selection A", "selection B", "selection A"]
        from zbemt.viz import plots_interactive as pi
        fig = pi.coefficients_vs_axis(self.results, axis="mu_x", series_labels=labels)
        # 2 distinct labels × 11 panels = 22 traces
        self.assertEqual(len(fig.data), 22, f"expected 22 traces (11 panels x 2 labels), got {len(fig.data)}")


@unittest.skipUnless(_HAS_PLOTLY, "'interactive' extra not installed")
class TestXYPlot(unittest.TestCase):
    """`plots_interactive.xy_plot` -- interactive twin of `plots.plot_xy`."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = make_api_fast_project(os.path.join(self.tmp, "proj"))
        conds = [FlightCondition(name=f"c{i}", mu_x=0.05 * i, collective_deg=float(4 + 2 * i),
                                  rpm=600.0) for i in range(1, 4)]
        self.results = [api.run_case(self.project, c) for c in conds]

    def test_any_key_x_vs_any_key_y_produces_a_figure(self):
        from zbemt.viz import plots_interactive as pi
        fig = pi.xy_plot(self.results, x_key="mu_x", y_key="CT")
        self.assertGreaterEqual(len(fig.data), 1)

    def test_group_by_produces_one_curve_per_distinct_value(self):
        from zbemt.viz import plots_interactive as pi
        fig = pi.xy_plot(self.results, x_key="mu_x", y_key="CT", group_by="collective_deg")
        # 3 distinct values of collective_deg -> 3 traces
        self.assertEqual(len(fig.data), 3)

    def test_missing_or_nan_keys_do_not_crash(self):
        from zbemt.viz import plots_interactive as pi
        fig = pi.xy_plot(self.results, x_key="mu_x", y_key="does_not_exist")
        self.assertIsNotNone(fig)

    def test_labels_are_plain_text_not_mathtext(self):
        """Without `$...$`: Plotly would try to render as mathtext (LaTeX),
        which fails/looks out of place with the rest of the page. The x-axis
        shows "mu_x" with real unicode subscript (μₓ), not the raw engine
        key -- see `widgets.CONDITION_UNITS` for the same convention
        in dropdowns."""
        from zbemt.viz import plots_interactive as pi
        fig = pi.xy_plot(self.results, x_key="mu_x", y_key="CT")
        self.assertNotIn("$", fig.layout.xaxis.title.text)
        self.assertNotIn("$", fig.layout.yaxis.title.text)
        self.assertIn("μₓ", fig.layout.xaxis.title.text)
        self.assertIn("CT", fig.layout.yaxis.title.text)


if __name__ == "__main__":
    unittest.main()
