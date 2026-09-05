"""Verify plot preparation, labels, ranges, and visual data selection.

The tests supply synthetic geometry, polar, convergence, disk-map, and result data;
assertions inspect generated figures, labels, masks, selections, and robust range
handling. Plot generation is isolated from file persistence and solver execution.
"""

import tempfile
import unittest
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from zbemt import geometry
from zbemt.viz import plots


def _visible_labels_outside_figure(fig):
    """Returns visible tick labels that would clip in an embedded canvas."""
    width, height = plots.figure_minimum_pixels(fig)
    fig.set_dpi(100)
    fig.set_size_inches(width / 100, height / 100, forward=True)
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    outside = []
    for axis in fig.axes:
        if not axis.axison:
            continue
        for label in axis.get_xticklabels() + axis.get_yticklabels():
            if not label.get_visible() or not label.get_text():
                continue
            box = label.get_window_extent(renderer)
            if box.x0 < 0 or box.y0 < 0 or box.x1 > width or box.y1 > height:
                outside.append((axis.get_title(), label.get_text()))
    return outside


class TestPlotPlanformReflectsNBlades(unittest.TestCase):
    """plot_planform draws the CONTOUR (leading edge + trailing edge
    + root/tip closures) of each blade -- 4 lines per blade -- so the
    number of lines on the axis should scale linearly with geom.n_blades
    (plus the root/tip circles, which do not depend on n_blades)."""

    def _n_blade_lines(self, geom):
        fig, ax = plt.subplots()
        try:
            plots.plot_planform(geom, ax=ax)
            return len(ax.get_lines())
        finally:
            plt.close(fig)

    def test_two_blades(self):
        geom = geometry.generate_tapered(n_blades=2)
        # 4 lines/blade (LE, TE, root closure, tip closure) * 2 blades + 2 circles (root, tip)
        self.assertEqual(self._n_blade_lines(geom), 4 * 2 + 2)

    def test_four_blades_has_more_lines_than_two(self):
        geom2 = geometry.generate_tapered(n_blades=2)
        geom4 = geometry.generate_tapered(n_blades=4)
        self.assertEqual(self._n_blade_lines(geom4), 4 * 4 + 2)
        self.assertGreater(self._n_blade_lines(geom4), self._n_blade_lines(geom2))

    def test_title_mentions_blade_count(self):
        fig, ax = plt.subplots()
        try:
            geom = geometry.generate_tapered(n_blades=3)
            plots.plot_planform(geom, ax=ax)
            self.assertIn("3", ax.get_title())
        finally:
            plt.close(fig)

    def test_single_blade_edge_case(self):
        geom = geometry.generate_tapered(n_blades=1)
        self.assertEqual(self._n_blade_lines(geom), 4 * 1 + 2)

    def test_contours_at_different_azimuths_for_multiple_blades(self):
        # with 2 blades, the root points of blade 0 and blade 1 should be
        # opposite (180 degrees apart) -- direct geometric check, not just
        # line count.
        import numpy as np
        geom = geometry.generate_tapered(n_blades=2, root_cutout_norm=0.2)
        fig, ax = plt.subplots()
        try:
            plots.plot_planform(geom, ax=ax)
            lines = ax.get_lines()
            # line 0 = LE of blade 0, line 4 = LE of blade 1 (4 lines per blade)
            le0_root = (lines[0].get_xdata()[0], lines[0].get_ydata()[0])
            le1_root = (lines[4].get_xdata()[0], lines[4].get_ydata()[0])
            self.assertTrue(np.allclose(le0_root, tuple(-c for c in le1_root), atol=1e-6))
        finally:
            plt.close(fig)


class TestPlotPlanformSaveToFile(unittest.TestCase):
    def test_fname_writes_png(self):
        geom = geometry.generate_tapered(n_blades=3)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "planform.png"
            plots.plot_planform(geom, fname=str(path))
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)

    def test_hub_circle_omitted_when_no_root_cutout(self):
        geom = geometry.generate_custom(r_norm=[0.0, 0.5, 1.0], chord_norm=[0.05, 0.05, 0.02],
                                         twist_deg=[10.0, 5.0, 0.0])
        fig, ax = plt.subplots()
        try:
            plots.plot_planform(geom, ax=ax, show_hub=True)
            # no root cutout (r_norm starts at 0), only the tip circle should appear
            self.assertEqual(len(ax.get_lines()), 4 * 2 + 1)
        finally:
            plt.close(fig)


class TestPlotPolar(unittest.TestCase):
    """docs/plano_v3.md Part 5: plot_polar now draws both Cl AND Cd
    (previously only drew Cl, `cd` was ignored)."""

    def test_draws_cl_and_cd_lines(self):
        fig, ax = plt.subplots()
        try:
            plots.plot_polar([-5, 0, 5], [0.0, 0.5, 1.0], [0.02, 0.015, 0.02], ax=ax, label="test")
            lines = ax.get_lines()
            self.assertEqual(len(lines), 2)
            import numpy as np
            np.testing.assert_allclose(lines[0].get_ydata(), [0.0, 0.5, 1.0])
            np.testing.assert_allclose(lines[1].get_ydata(), [0.02, 0.015, 0.02])
        finally:
            plt.close(fig)

    def test_fname_writes_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "polar.png"
            plots.plot_polar([-5, 0, 5], [0.0, 0.5, 1.0], [0.02, 0.015, 0.02], fname=str(path))
            self.assertTrue(path.exists())

    def test_neuralfoil_legend_keeps_reynolds_and_mach(self):
        fig, ax = plt.subplots()
        try:
            plots.plot_polar([0, 5], [0, .5], [.01, .02], ax=ax,
                             label="NeuralFoil", reynolds=2.5e5, mach=.18)
            labels = [line.get_label() for line in ax.get_lines()]
            self.assertIn("Re=2.5e+05, M=0.18", labels[0])
            self.assertIn("Re=2.5e+05, M=0.18", labels[1])
        finally:
            plt.close(fig)


class TestPlotConvergence(unittest.TestCase):
    """The convergence figure is: iteration disk by element (WHERE the
    solver struggled) + sweep history + range of cards with header
    numbers. Each piece appears if and only if the data exists --
    that is what the two percentage bars did not do (drew
    "98.5%" and "7 iterations" as if they were comparable)."""

    def _complete_result(self):
        from zbemt.models import Results
        import numpy as np
        Ne, Npsi = 5, 8
        r_norm = np.linspace(0.2, 1.0, Ne)
        psi = np.linspace(0, 2 * np.pi * (1 - 1 / Npsi), Npsi)
        R_NORM, PSI = np.meshgrid(r_norm, psi, indexing="ij")
        n_iter = np.full((Ne, Npsi), 4)
        n_iter[0, 0] = 9
        converged = np.ones((Ne, Npsi), dtype=bool)
        converged[0, 0] = False
        return Results(
            summary={"convergence_pct": 97.5, "mean_iter": 4.1, "solver": "newton",
                      "elapsed_s": 0.42},
            maps=dict(R_NORM=R_NORM, PSI=PSI, Ut=np.abs(np.cos(PSI)) + 0.1,
                       n_iter=n_iter, converged=converged, total_iterations=9,
                       frac_converged_history=[0.2, 0.8, 0.975],
                       residual_history=[1e-1, 1e-3, 1e-6], mu_x=0.3))

    def _texts(self, fig):
        axes_list = list(fig.axes)
        for ax in list(axes_list):
            axes_list.extend(ax.child_axes)
        return [t.get_text() for ax in axes_list for t in ax.texts]

    def test_summary_without_iteration_history_is_plotable(self):
        """Without history AND without maps, only the summary remains: a
        range of cards with numbers, never again two bars with different
        scales side by side."""
        from zbemt.models import Results
        result = Results(summary={"convergence_pct": 98.5, "mean_iter": 7.0}, maps={})
        fig, ax = plt.subplots()
        try:
            out_fig = plots.plot_convergence(result, ax=ax)
            texts = self._texts(out_fig)
            self.assertIn("98.5%", texts)
            self.assertIn("7.0", texts)
            self.assertTrue(any("collect_history" in t for t in texts),
                            f"does not explain the absence of the history: {texts}")
            # no bars: `ax.bar` produces Rectangle in `ax.patches`
            bars = [p for axis in out_fig.axes for p in axis.patches
                    if type(p).__name__ == "Rectangle"]
            self.assertEqual(bars, [])
        finally:
            plt.close(fig)

    def test_iteration_disk_marks_non_converged_elements(self):
        result = self._complete_result()
        fig = plots.plot_convergence(result)
        iteration_axes = [a for a in fig.axes if a.get_title().startswith("Iterations")]
        self.assertEqual(len(iteration_axes), 1, "missing the per-element iteration map")
        labels = [l.get_label() for l in iteration_axes[0].get_lines()]
        self.assertIn("not converged", labels)

    def test_header_numbers_appear_as_cards(self):
        fig = plots.plot_convergence(self._complete_result())
        texts = self._texts(fig)
        self.assertIn("97.5%", texts)          # convergence fraction
        self.assertIn("1/40", texts)           # elements that failed
        self.assertIn("9", texts)              # iterations in worst element
        self.assertIn("420 ms", texts)         # solver time

    def test_nested_convergence_layout_has_a_readable_floor(self):
        """The disk, history, and cards must not collapse below their usable size."""
        fig = plots.plot_convergence(self._complete_result())
        width, height = plots.figure_minimum_pixels(fig)
        self.assertGreaterEqual(width, 960)
        self.assertGreaterEqual(height, 384)

    def test_convergence_labels_stay_inside_the_figure_at_its_floor(self):
        """The nested layout must preserve its visible scale labels."""
        fig = plots.plot_convergence(self._complete_result())
        self.assertEqual(_visible_labels_outside_figure(fig), [])

    def test_disk_map_does_not_repeat_panel_title(self):
        import numpy as np
        maps = dict(R_NORM=np.ones((2, 4)), PSI=np.tile(np.linspace(0, 5, 4), (2, 1)),
                    Ut=np.ones((2, 4)), Up=np.ones((2, 4)),
                    lambda_i=np.ones((2, 4)), mu_x=.2)
        fig = plots.plot_disk_map_grid(maps, fields=["lambda_i"])
        try:
            self.assertEqual(len(fig.axes[0].texts), 4)
            self.assertFalse(any("lambda" in text.get_text().lower()
                                 for text in fig.axes[0].texts))
        finally:
            plt.close(fig)


class TestDiskMapVisualReading(unittest.TestCase):
    """Three invariants of READING the disk map, all seen on the screen
    before they became tests:

    * the color bar had the height of the subplot CELL, not the disk --
      it was much taller than the drawing and wasted height;
    * the r/R guide circles existed in the code but were drawn
      BELOW the filled contour, i.e., never appeared;
    * the reverse flow region needs to be a light gray distinct from
      the white background ("no valid data here"), never white or a
      saturated color that reads as data.

    None of them measure pixel/inch: they measure height ratio, guide
    radius, and the color used.
    """

    def _maps(self, with_reverse=True):
        import numpy as np
        Ne, Npsi = 8, 16
        r_norm = np.linspace(0.2, 1.0, Ne)
        psi = np.linspace(0, 2 * np.pi * (1 - 1 / Npsi), Npsi)
        R_NORM, PSI = np.meshgrid(r_norm, psi, indexing="ij")
        Ut = (np.cos(PSI) if with_reverse else np.abs(np.cos(PSI)) + 0.5)
        return dict(R_NORM=R_NORM, PSI=PSI, Ut=Ut,
                    Fn=1000.0 * R_NORM * (1 + 0.3 * np.sin(PSI)), mu_x=0.3)

    def _guide_radii(self, ax):
        """Radius of each CLOSED and dashed axis line (the guides) --
        identified by geometry, not by creation order."""
        import numpy as np
        radii = []
        for line in ax.get_lines():
            x, y = np.asarray(line.get_xdata()), np.asarray(line.get_ydata())
            if x.size < 50:            # reference cross has 2 points
                continue
            r = np.hypot(x, y)
            if np.ptp(r) < 1e-6:       # circle: constant radius
                radii.append(round(float(r[0]), 3))
        return sorted(radii)

    def test_colorbar_has_the_height_of_the_disk(self):
        import numpy as np
        from matplotlib.figure import Figure
        for compact in (False, True):
            with self.subTest(compact=compact):
                fig = Figure(figsize=(5.5, 5.5))
                ax = fig.add_subplot(111)
                plots.plot_disk_map(self._maps(), field="Fn", ax=ax, compact=compact)
                fig.canvas.draw()
                self.assertTrue(ax.child_axes, "colorbar was not created")
                bar_height = ax.child_axes[0].get_window_extent().height
                (_, y_bottom), (_, y_top) = ax.transData.transform([(0, -1.0), (0, 1.0)])
                disk_height = y_top - y_bottom
                self.assertAlmostEqual(bar_height / disk_height, 1.0, delta=0.03)

    def test_radius_guides_on_every_disk_and_above_the_field(self):
        import numpy as np
        from matplotlib.figure import Figure
        fig = Figure(figsize=(5.5, 5.5))
        ax = fig.add_subplot(111)
        plots.plot_disk_map(self._maps(), field="Fn", ax=ax)
        self.assertEqual(self._guide_radii(ax), [0.25, 0.5, 0.75])
        guides = [l for l in ax.get_lines() if len(l.get_xdata()) >= 50]
        field_z = max(c.get_zorder() for c in ax.collections)
        for guide in guides:
            self.assertGreater(guide.get_zorder(), field_z,
                               "guide drawn BELOW the contour -- it becomes invisible")
            self.assertNotEqual(guide.get_linestyle(), "-", "guide must be dashed")

    def test_radius_guides_also_in_each_grid_panel(self):
        fig = plots.plot_disk_map_grid(self._maps(), fields=["Fn", "Fn"])
        panels = [a for a in fig.axes if a.collections]
        self.assertEqual(len(panels), 2)
        for panel in panels:
            self.assertEqual(self._guide_radii(panel), [0.25, 0.5, 0.75])

    def test_reverse_flow_painted_light_gray(self):
        from matplotlib.colors import to_rgb
        from matplotlib.figure import Figure
        r, g, b = to_rgb(plots._REVERSE_MASK_COLOR)
        self.assertEqual((r, g), (g, b))                    # pure gray
        self.assertTrue(0.70 <= r <= 0.93,
                        "the mask needs to be a LIGHT gray, distinct from white")
        fig = Figure(figsize=(5, 5))
        ax = fig.add_subplot(111)
        plots.plot_disk_map(self._maps(with_reverse=True), field="Fn", ax=ax,
                             mask_reverse=True)
        colors = [tuple(collection.get_cmap()(0.0)[:3]) for collection in ax.collections]
        self.assertIn((r, g, b), colors,
                      "no collection paints the masked region with the mask gray")


class TestPlotGeometryStillWorks(unittest.TestCase):
    """Regression: plot_planform should not have broken plot_geometry
    (curves of chord/twist vs r/R, which continue to not depend on n_blades)."""

    def test_plot_geometry_line_count_independent_of_n_blades(self):
        geom2 = geometry.generate_tapered(n_blades=2)
        geom6 = geometry.generate_tapered(n_blades=6)
        fig, ax = plt.subplots()
        try:
            plots.plot_geometry(geom2, ax=ax)
            n_lines_2 = len(ax.get_lines()) + len(ax.figure.axes[-1].get_lines())
        finally:
            plt.close(fig)
        fig, ax = plt.subplots()
        try:
            plots.plot_geometry(geom6, ax=ax)
            n_lines_6 = len(ax.get_lines()) + len(ax.figure.axes[-1].get_lines())
        finally:
            plt.close(fig)
        self.assertEqual(n_lines_2, n_lines_6)


class TestPlotChordTwistDistribution(unittest.TestCase):
    """docs/plano_v3.md Part 6.1: new function dedicated to embedded
    Geometry canvas -- 2 Y axes, N points = len(geom.r_norm), and ``fname``
    writes PNG (same pattern as _resolve_ax/_finish of other functions)."""

    def test_two_y_axes_and_point_count_match_geometry(self):
        geom = geometry.generate_tapered(n_stations=12)
        fig, ax = plt.subplots()
        try:
            plots.plot_chord_twist_distribution(geom, ax=ax)
            self.assertEqual(len(ax.figure.axes), 2)
            chord_line = ax.get_lines()[0]
            self.assertEqual(len(chord_line.get_xdata()), len(geom.r_norm))
            twist_line = ax.figure.axes[-1].get_lines()[0]
            self.assertEqual(len(twist_line.get_xdata()), len(geom.r_norm))
        finally:
            plt.close(fig)

    def test_fname_writes_png(self):
        geom = geometry.generate_tapered()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "chord_twist.png"
            plots.plot_chord_twist_distribution(geom, fname=str(out))
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)


class TestDiskMapReverseFlowMasking(unittest.TestCase):
    """plot_disk_map/plot_disk_map_grid: mask_reverse (default True) should
    run without error both with and without reverse flow region in
    `maps`, and should not modify input data (only the drawing)."""

    def _fake_maps(self, with_reverse: bool):
        import numpy as np
        Ne, Npsi = 6, 12
        r_norm = np.linspace(0.2, 1.0, Ne)
        psi = np.linspace(0, 2 * np.pi * (1 - 1 / Npsi), Npsi)
        R_NORM, PSI = np.meshgrid(r_norm, psi, indexing="ij")
        Ut = np.cos(PSI) * R_NORM  # negative in half the disk
        if not with_reverse:
            Ut = np.abs(Ut) + 0.1  # never reverse
        return dict(R_NORM=R_NORM, PSI=PSI, Ut=Ut, Up=0.1 * np.ones_like(Ut),
                    lambda_i=0.05 * np.ones_like(Ut), mu_x=0.3)

    def test_plot_disk_map_masked_runs_with_reverse_flow(self):
        maps = self._fake_maps(with_reverse=True)
        fig, ax = plt.subplots()
        try:
            plots.plot_disk_map(maps, field="lambda_i", ax=ax, mask_reverse=True)
        finally:
            plt.close(fig)
        # original data preserved (masking is only in the drawing)
        self.assertTrue((maps["Ut"] < 0).any())

    def test_plot_disk_map_unmasked_runs_with_reverse_flow(self):
        maps = self._fake_maps(with_reverse=True)
        fig, ax = plt.subplots()
        try:
            plots.plot_disk_map(maps, field="lambda_i", ax=ax, mask_reverse=False)
        finally:
            plt.close(fig)

    def test_plot_disk_map_runs_without_reverse_flow(self):
        maps = self._fake_maps(with_reverse=False)
        fig, ax = plt.subplots()
        try:
            plots.plot_disk_map(maps, field="lambda_i", ax=ax, mask_reverse=True)
        finally:
            plt.close(fig)

    def test_plot_disk_map_grid_saves_file_and_forwards_mask(self):
        maps = self._fake_maps(with_reverse=True)
        with tempfile.TemporaryDirectory() as tmp:
            fname = str(Path(tmp) / "grid.png")
            plots.plot_disk_map_grid(maps, fields=["lambda_i", "Up"], fname=fname, mask_reverse=True)
            self.assertTrue(Path(fname).exists())


class TestDiskMapAdditionalFields(unittest.TestCase):
    """Ft_i/Ft_p (induced/profile tangential force), Mach and dynamic
    pressure q -- already computed by element_state()/solve_bemt() and
    present in a real `maps`, but not previously reachable from the disk
    map plots (missing from _DISK_FIELD_META/_DISK_GRID_FIELDS)."""

    def _fake_maps(self):
        import numpy as np
        Ne, Npsi = 6, 12
        r_norm = np.linspace(0.2, 1.0, Ne)
        psi = np.linspace(0, 2 * np.pi * (1 - 1 / Npsi), Npsi)
        R_NORM, PSI = np.meshgrid(r_norm, psi, indexing="ij")
        W = 50.0 * np.ones_like(R_NORM)
        return dict(R_NORM=R_NORM, PSI=PSI, Ut=np.abs(np.cos(PSI)) + 0.1,
                    Up=0.1 * np.ones_like(R_NORM), W=W, rho=1.225,
                    Ft_i=0.2 * np.ones_like(R_NORM), Ft_p=0.05 * np.ones_like(R_NORM),
                    Mach=W / 340.0, mu_x=0.3)

    def test_new_fields_are_registered_in_grid(self):
        for field in ("Ft_i", "Ft_p", "Mach", "q"):
            self.assertIn(field, plots._DISK_GRID_FIELDS)
            self.assertIn(field, plots._DISK_FIELD_META)

    def test_dynamic_pressure_computed_correctly(self):
        maps = self._fake_maps()
        q = plots._disk_field_array(maps, "q")
        expected = 0.5 * maps["rho"] * maps["W"] ** 2
        self.assertTrue((q == expected).all())

    def test_new_fields_plot_without_error(self):
        maps = self._fake_maps()
        for field in ("Ft_i", "Ft_p", "Mach", "q"):
            fig, ax = plt.subplots()
            try:
                plots.plot_disk_map(maps, field=field, ax=ax, mask_reverse=True)
            finally:
                plt.close(fig)


# =============================================================================
# docs/plano_v3.md Part 4 -- Results hub: flatten_selection and
# plot_coefficients_vs_axis (generalization of plot_coefficients_vs_mu).
# =============================================================================

def _fake_result(mu_x=0.0, alpha_rotor_deg=0.0, collective_deg=8.0, rpm=600.0,
                  CT=0.01, condition_name="c"):
    from zbemt.models import Results
    summary = dict(mu_x=mu_x, alpha_rotor_deg=alpha_rotor_deg, collective_deg=collective_deg,
                   rpm=rpm, CT=CT, CQ=0.001, FM=0.7, CY=0.0, CMx=0.0, CMy=0.0,
                   CH=0.0, CHp=0.0, CHi=0.0, CPp=0.0005, CPi=0.0005)
    return Results(summary=summary, maps={}, condition_name=condition_name)


def _fake_entry(entry_id, label, kind, results):
    from zbemt.models import ResultEntry
    return ResultEntry(id=entry_id, label=label, kind=kind, results=results, timestamp="00:00:00")


class TestFlattenSelection(unittest.TestCase):
    """flatten_selection finds a heterogeneous selection (cases + batches) of
    ResultEntry in a flat list of Results, preserving order."""

    def test_case_plus_case(self):
        r1, r2 = _fake_result(mu_x=0.1), _fake_result(mu_x=0.2)
        entries = [_fake_entry("1", "caso 1", "case", r1),
                   _fake_entry("2", "caso 2", "case", r2)]
        flat = plots.flatten_selection(entries)
        self.assertEqual(flat, [r1, r2])

    def test_case_plus_batch(self):
        r1 = _fake_result(mu_x=0.1)
        batch_results = [_fake_result(mu_x=0.2), _fake_result(mu_x=0.3)]
        entries = [_fake_entry("1", "caso 1", "case", r1),
                   _fake_entry("2", "batch 1", "batch", batch_results)]
        flat = plots.flatten_selection(entries)
        self.assertEqual(flat, [r1] + batch_results)

    def test_batch_plus_batch(self):
        b1 = [_fake_result(mu_x=0.1), _fake_result(mu_x=0.2)]
        b2 = [_fake_result(mu_x=0.3)]
        entries = [_fake_entry("1", "batch 1", "batch", b1),
                   _fake_entry("2", "batch 2", "batch", b2)]
        flat = plots.flatten_selection(entries)
        self.assertEqual(flat, b1 + b2)

    def test_empty_selection_is_empty_list(self):
        self.assertEqual(plots.flatten_selection([]), [])


class TestPlotCoefficientsVsAxis(unittest.TestCase):
    """Generalization of plot_coefficients_vs_mu (Part 4.2) -- any
    of the 4 factorial variables, combine mode (1 curve) and overlay
    (1 curve per label)."""

    def _results(self):
        return [
            _fake_result(mu_x=0.30, alpha_rotor_deg=2.0, collective_deg=10.0, rpm=650.0, CT=0.015),
            _fake_result(mu_x=0.10, alpha_rotor_deg=0.0, collective_deg=8.0, rpm=600.0, CT=0.010),
            _fake_result(mu_x=0.20, alpha_rotor_deg=1.0, collective_deg=9.0, rpm=625.0, CT=0.012),
        ]

    def test_plot_coefficients_vs_mu_backward_compatible(self):
        results = self._results()
        with tempfile.TemporaryDirectory() as tmp:
            fname = str(Path(tmp) / "vs_mu.png")
            plots.plot_coefficients_vs_mu(results, fname=fname)
            self.assertTrue(Path(fname).exists())

    def test_each_factorial_axis_runs_and_saves(self):
        results = self._results()
        for axis in ("mu_x", "alpha_deg", "collective_deg", "rpm"):
            with tempfile.TemporaryDirectory() as tmp:
                fname = str(Path(tmp) / f"vs_{axis}.png")
                plots.plot_coefficients_vs_axis(results, axis=axis, fname=fname)
                self.assertTrue(Path(fname).exists(), f"axis={axis} did not generate a file")

    def test_small_force_panel_does_not_let_offset_invade_title(self):
        fig = plots.plot_coefficients_vs_axis(self._results(), axis="mu_x")
        panel = next(ax for ax in fig.axes
                      if ax.get_title() == "H-Force, profile component")
        self.assertEqual(panel.yaxis.get_offset_text().get_text(), "")

    def test_labels_stay_inside_the_figure_at_the_readable_floor(self):
        """A tick label outside the figure clips in the Results canvas."""
        fig = plots.plot_coefficients_vs_axis(self._results(), axis="mu_x")
        outside = _visible_labels_outside_figure(fig)
        self.assertEqual(outside, [], f"labels outside figure: {outside}")

    def test_derived_alpha_does_not_split_axial_sweep_into_series(self):
        """`alpha_rotor_deg` is DERIVED from the pair (mu_x, Vz), not an
        independent axis: in an axial sweep (propeller) it jumps from 0 at
        Vz=0 to 90 at axial flight, and automatic grouping was splitting the
        sweep into TWO series -- the V=0 point alone in one curve, the rest
        in another -- which reads as two distinct regimes when it is just
        one sweep."""
        from zbemt.models import Results
        res = []
        for vv in (0.0, 20.0, 40.0):
            s = dict(mu_x=0.0, Vz=vv, alpha_rotor_deg=(0.0 if vv == 0 else 90.0),
                     collective_deg=0.0, rpm=2500.0, CT=0.02, CQ=0.001, FM=0.7,
                     CY=0.0, CMx=0.0, CMy=0.0, CH=0.0, CHp=0.0, CHi=0.0,
                     CPp=0.0005, CPi=0.0005)
            res.append(Results(summary=s, maps={}, condition_name=f"V={vv:g}"))
        fig = plots.plot_coefficients_vs_axis(res, axis="Vz")
        # one curve only, with the THREE points
        lines = [l for l in fig.axes[0].get_lines() if len(l.get_xdata()) == 3]
        self.assertEqual(len(lines), 1,
                          "axial sweep split into spurious series by derived alpha")

    def test_two_real_axes_still_become_separate_series(self):
        """Counterweight to the test above: when a SECOND truly
        independent axis varies (rpm), grouping must continue
        to happen -- the fix cannot have killed the overlay."""
        res = [_fake_result(mu_x=m, alpha_rotor_deg=0.0, collective_deg=8.0, rpm=n, CT=0.01)
               for n in (500.0, 700.0) for m in (0.0, 0.1, 0.2)]
        fig = plots.plot_coefficients_vs_axis(res, axis="mu_x")
        lines = [l for l in fig.axes[0].get_lines() if len(l.get_xdata()) == 3]
        self.assertEqual(len(lines), 2, "expected one curve per rpm value")

    def test_mu_x_alpha_factorial_still_groups_by_alpha(self):
        """Real bug reported: the exclusion of `alpha_deg` (designed for the
        degenerate case of a PURELY axial sweep, mu_x=0 fixed) was
        too broad -- `mu_x` varies in ANY mu_x sweep (it's the X axis!),
        so it suppressed grouping by alpha even in a legitimate 2-axis
        factorial (mu_x x alpha_deg), collapsing the entire batch
        into one curve and hiding the alphas the user asked to
        compare. With `mu_x` genuinely varying (2+ non-zero values),
        alpha_rotor_deg is not degenerate and must continue grouping."""
        res = [_fake_result(mu_x=m, alpha_rotor_deg=a, collective_deg=8.0, rpm=600.0, CT=0.01)
               for a in (-2.0, 0.0, 2.0) for m in (0.1, 0.2, 0.3, 0.4)]
        fig = plots.plot_coefficients_vs_axis(res, axis="mu_x")
        lines = [l for l in fig.axes[0].get_lines() if len(l.get_xdata()) == 4]
        self.assertEqual(len(lines), 3, "expected one curve per alpha value")

    def test_propeller_mode_uses_the_propeller_panels(self):
        """A propeller is not a rotor with other names: the
        non-dimensionalization is different (rho*n^2*D^4) and the merit metric is
        eta_prop, not FM. Showing rotor panels filled the figure with
        meaningless plots there (FM, CMx/CMy/CY ~ 0 by symmetry in axial
        flight) and OMITTED CT_prop/CQ_prop/CP_prop/eta_prop."""
        from zbemt.models import Results
        s = dict(mu_x=0.0, Vz=40.0, alpha_rotor_deg=90.0, collective_deg=0.0, rpm=2500.0,
                 CT=0.02, CQ=0.001, CP=0.001, CPp=0.0005, CPi=0.0005,
                 CT_prop=0.2, CQ_prop=0.02, CP_prop=0.13, eta_prop=0.6, J_z=0.5,
                 cfg_is_propeller=True)
        res = [Results(summary=s, maps={}, condition_name="c")]
        self.assertIs(plots._sweep_panels(res), plots._PROP_SWEEP_PANELS)
        # and the rotor stays in the rotor set
        self.assertIs(plots._sweep_panels(self._results()),
                       plots._MU_SWEEP_PANELS)

    def test_combine_mode_sorts_by_axis_without_series_labels(self):
        # "combine" mode (default, series_labels=None): to test sorting
        # in a single curve with multiple points, other variables must be constant.
        results = [
            _fake_result(mu_x=0.30, alpha_rotor_deg=0.0, collective_deg=8.0, rpm=600.0, CT=0.015),
            _fake_result(mu_x=0.10, alpha_rotor_deg=0.0, collective_deg=8.0, rpm=600.0, CT=0.010),
            _fake_result(mu_x=0.20, alpha_rotor_deg=0.0, collective_deg=8.0, rpm=600.0, CT=0.012),
        ]
        fig = plots.plot_coefficients_vs_axis(results, axis="mu_x")
        ax0 = fig.axes[0]
        line = ax0.get_lines()[0]
        xs = list(line.get_xdata())
        self.assertEqual(xs, sorted(xs))
        self.assertEqual(len(xs), 3)
        plt.close(fig)

    def test_floating_point_noise_in_the_secondary_group_does_not_split_the_series(self):
        """`_grouping_key` rounds before comparing: a
        secondary variable derived from floating point math can
        carry noise of ~1e-4 (e.g. 8.00003 instead of exactly 8.0) --
        exact equality comparison was slicing EACH nominal value into
        a series per main axis point. Uses `collective_deg` (not
        `alpha_deg`, which has its own deliberate exclusion when
        `mu_x`/`Vz` vary -- see
        `test_derived_alpha_does_not_split_axial_sweep_into_series`) with
        deliberately SMALL magnitude: at large magnitude (hundreds),
        the `:g` label format (6 significant digits) already absorbs
        1e-4 noise by itself -- would not exercise the real bug."""
        res = []
        for i, mu_x in enumerate((0.1, 0.2, 0.3, 0.4)):
            # DIFFERENT noise per mu_x point (the real case: each
            # combination goes through its own floating point math)
            # -- identical noise repeated across all mu_x would not exercise the
            # bug, since exact equality would suffice for grouping.
            for nominal in (6.0, 8.0, 10.0):
                noisy = nominal + (1e-4 if i % 2 == 0 else -1e-4) * (i + 1)
                res.append(_fake_result(mu_x=mu_x, alpha_rotor_deg=0.0, collective_deg=noisy,
                                          rpm=600.0, CT=0.01))
        fig = plots.plot_coefficients_vs_axis(res, axis="mu_x")
        lines = [l for l in fig.axes[0].get_lines() if len(l.get_xdata()) == 4]
        self.assertEqual(len(lines), 3,
                          "floating-point noise in the secondary variable split the series "
                          f"into {len(lines)} curves instead of 3")
        plt.close(fig)

    def test_overlay_mode_draws_one_line_per_label(self):
        results = self._results()
        labels = ["selection A", "selection A", "selection B"]
        fig = plots.plot_coefficients_vs_axis(results, axis="mu_x", series_labels=labels)
        ax0 = fig.axes[0]
        self.assertEqual(len(ax0.get_lines()) - 1, 2)  # -1: axhline(0)
        plt.close(fig)


# =============================================================================
# plot_xy -- free X-Y plot (any summary key), "Custom X-Y" Part
# =============================================================================

class TestPlotXY(unittest.TestCase):
    def _results(self):
        return [
            _fake_result(mu_x=0.30, collective_deg=10.0, CT=0.015),
            _fake_result(mu_x=0.10, collective_deg=8.0, CT=0.010),
            _fake_result(mu_x=0.20, collective_deg=9.0, CT=0.012),
            _fake_result(mu_x=0.05, collective_deg=8.0, CT=0.009),
        ]

    def test_any_key_x_vs_any_key_y_produces_a_figure(self):
        fig, ax = plt.subplots()
        try:
            plots.plot_xy(self._results(), x_key="mu_x", y_key="CT", ax=ax)
            # at least 1 data line besides axhline(0)
            self.assertGreaterEqual(len(ax.get_lines()), 2)
        finally:
            plt.close(fig)

    def test_group_by_draws_one_curve_per_distinct_value(self):
        fig, ax = plt.subplots()
        try:
            plots.plot_xy(self._results(), x_key="mu_x", y_key="CT",
                           group_by="collective_deg", ax=ax)
            # 3 distinct values of collective_deg (10, 8, 9) -> 3 curves + axhline(0)
            self.assertEqual(len(ax.get_lines()) - 1, 3)
        finally:
            plt.close(fig)

    def test_missing_or_nan_keys_do_not_crash(self):
        from zbemt.models import Results
        results = [
            _fake_result(mu_x=0.1, CT=0.01),
            Results(summary=dict(mu_x=float("nan"), CT=0.02), maps={}, condition_name="nan_mu"),
            Results(summary=dict(mu_x=0.2), maps={}, condition_name="no_CT"),
        ]
        fig, ax = plt.subplots()
        try:
            plots.plot_xy(results, x_key="mu_x", y_key="CT", ax=ax)  # should not raise
        finally:
            plt.close(fig)

    def test_all_points_missing_does_not_crash_and_shows_message(self):
        results = [_fake_result(mu_x=0.1)]  # "eta_prop" is not in fake summary
        fig, ax = plt.subplots()
        try:
            plots.plot_xy(results, x_key="mu_x", y_key="eta_prop", ax=ax)
        finally:
            plt.close(fig)

    def test_axis_labels_contain_expected_symbol(self):
        fig, ax = plt.subplots()
        try:
            plots.plot_xy(self._results(), x_key="mu_x", y_key="CT", ax=ax)
            self.assertIn(r"\mu_x", ax.get_xlabel())
            self.assertIn("C_T", ax.get_ylabel())
        finally:
            plt.close(fig)

    def test_save_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            fname = str(Path(tmp) / "xy.png")
            plots.plot_xy(self._results(), x_key="mu_x", y_key="CT", fname=fname)
            self.assertTrue(Path(fname).exists())


if __name__ == "__main__":
    unittest.main()


class TestRobustColorRange(unittest.TestCase):
    """Few singular elements cannot erase the entire map.

    Reproduced with real data: in a case with tip Mach > 1 on the
    advancing blade, the compressibility correction (division by
    sqrt(1-M^2)) explodes Cl in 2 out of 7776 elements -- maximum 599 vs
    99th percentile of 2.5. The color scale stretched by those two
    points painted four of the sixteen panels of the disk grid as a
    uniform purple rectangle.
    """

    def test_extreme_tail_clips_the_scale_and_marks_the_bar(self):
        import numpy as np
        from zbemt.viz.plots import _robust_color_range

        z = np.concatenate([np.linspace(0.0, 2.5, 5000), np.array([599.0, 86.0])])
        lo, hi, extend = _robust_color_range(z, float(z.min()), float(z.max()))
        self.assertLess(hi, 10.0, "scale still dominated by the tail")
        self.assertEqual(extend, "max",
                          "clipping without an arrow on the color bar would be silent")

    def test_well_behaved_field_passes_untouched(self):
        """Strong but continuous gradient (Ut, W) CANNOT be clipped --
        clipping is for the pathological case, not for all fields."""
        import numpy as np
        from zbemt.viz.plots import _robust_color_range

        z = np.linspace(0.0, 600.0, 5000)
        lo, hi, extend = _robust_color_range(z, float(z.min()), float(z.max()))
        self.assertEqual(extend, "")
        self.assertAlmostEqual(hi, 600.0)
        self.assertAlmostEqual(lo, 0.0)


class TestDiskColorBarLabel(unittest.TestCase):
    """In the disk grid, the color bar label cannot be ABOVE
    it: any text there rises into the cell above and glues the
    variable name to the previous disk. In the grid it goes to the LEFT of the
    bar, high up, where the circular edge of the disk leaves the corner free.

    And the label is always "symbol [unit]" in one piece -- before the symbol
    and unit were two separate texts on different lines.
    """

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")

    def _maps(self):
        """Synthetic mesh -- this test measures LABEL POSITION, not
        physics; running the engine would only make the test slow and fragile."""
        import numpy as np
        Ne, Npsi = 6, 12
        r_norm = np.linspace(0.2, 1.0, Ne)
        psi = np.linspace(0, 2 * np.pi * (1 - 1 / Npsi), Npsi)
        R_NORM, PSI = np.meshgrid(r_norm, psi, indexing="ij")
        base = np.ones_like(R_NORM)
        return dict(R_NORM=R_NORM, PSI=PSI, Ut=np.abs(np.cos(PSI)) + 0.1,
                    Fn=1000.0 * R_NORM, Cl=0.5 * base, mu_x=0.0)

    def _colorbar_texts(self, fig):
        """(text, x, y, ha) of each label drawn on color bar axes.

        The color bar became an INSET axis of the disk axis itself (to
        have exactly the disk's height, see `plots._colorbar_axis`),
        and an inset does not appear in `fig.axes` -- it is in
        `ax.child_axes`. Scanning both is what keeps this test measuring
        label position, not layout implementation."""
        found = []
        axes_list = list(fig.axes)
        for ax in list(axes_list):
            axes_list.extend(ax.child_axes)
        for ax in axes_list:
            # colorbar axes have no data drawn by us, only texts
            for t in ax.texts:
                found.append((t.get_text(), t.get_position()[0],
                              t.get_position()[1], t.get_ha()))
        return found

    def test_in_the_grid_the_label_stays_above_the_bar_without_invading_the_disk(self):
        from zbemt.viz import plots
        fig = plots.plot_disk_map_grid(self._maps(), fields=["Fn", "Cl"])
        labels = [t for t in self._colorbar_texts(fig)
                  if t[0].startswith("$F_n$") or t[0].startswith("$C_L$")
                  or "F_n" in t[0] or "C_L" in t[0]]
        self.assertTrue(labels, "no colorbar label found")
        for text, x, y, ha in labels:
            self.assertGreaterEqual(x, 0.0,
                                    f"label {text!r} at x={x} -- invades the disk area")
            self.assertGreater(y, 1.0, f"label {text!r} is not above the bar")
            self.assertEqual(ha, "left")

    def test_label_carries_symbol_and_unit_together(self):
        from zbemt.viz import plots
        fig = plots.plot_disk_map_grid(self._maps(), fields=["Fn"])
        texts = [t[0] for t in self._colorbar_texts(fig)]
        with_unit = [t for t in texts if "[N/m]" in t]
        self.assertTrue(
            with_unit,
            f"no label in the 'symbol [unit]' format; texts={texts}")
        # and the unit does NOT appear alone in a second text
        self.assertNotIn("N/m", [t.strip() for t in texts],
                          "unit still drawn as a separate text")

    def test_dimensionless_field_gets_no_empty_bracket(self):
        from zbemt.viz import plots
        fig = plots.plot_disk_map_grid(self._maps(), fields=["Cl"])
        texts = [t[0] for t in self._colorbar_texts(fig)]
        self.assertFalse([t for t in texts if "[]" in t or "[-]" in t],
                          f"empty bracket/dash in a dimensionless field: {texts}")


class TestPlotParallelCoordinates(unittest.TestCase):
    """SC-13: one polyline per front member across normalized axes."""

    def test_draws_one_line_per_member_and_labels_every_axis(self):
        import matplotlib.pyplot as plt
        front = [{"root": 0.07, "tip": 0.02, "FM": 1.40, "CT": 0.006},
                  {"root": 0.11, "tip": 0.05, "FM": 1.20, "CT": 0.010},
                  {"root": 0.15, "tip": 0.09, "FM": 1.00, "CT": 0.014}]
        try:
            ax = plots.plot_parallel_coordinates(
                front, ["FM", "CT"], param_names=["root", "tip"])
            self.assertEqual(len(ax.lines), 3)
            labels = [t.get_text() for t in ax.get_xticklabels()]
            self.assertEqual(len(labels), 4)
        finally:
            plt.close("all")

    def test_no_finite_member_draws_the_placeholder(self):
        import matplotlib.pyplot as plt
        try:
            ax = plots.plot_parallel_coordinates(
                [{"FM": float("nan")}, {}], ["FM"], param_names=[])
            self.assertFalse(ax.lines)
        finally:
            plt.close("all")
