"""
test_results_tab.py
===================

Regression tests for the Results tab (``zbemt/gui/tabs/results.py``):

* **independent height and color in the 3D view** -- there used to be ONE
  field selector plus a checkbox "raise the disc by the field value", so
  the height was forced to be the same quantity as the color (or none).
  ``visualization.build_disk_grid`` always accepted separate
  ``field=``/``z_field=``; it was only the GUI that tied the two together;
* **every export starts from the project's ``outputs/`` folder** -- the
  dialogs used to open wherever the process happened to be (the working
  directory, or the last one visited), scattering figures outside the
  project;
* **the reverse-flow mask belongs to the Results tab** -- it is a DISPLAY
  choice (it does not change forces or the CSV) and now lives here,
  writing to the project's ``config`` so it does not lose GUI/``.bemt``/CLI
  parity.

Each test switches to the Results tab before any assertion: on a tab
that is not selected ``isVisible()`` is always False, and the assertions
would pass without testing anything.
"""

import os
import unittest
import unittest.mock
from pathlib import Path

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    _HAS_QT = True
except Exception:  # pragma: no cover - environment without PyQt6
    _HAS_QT = False

import numpy as np

from zbemt import geometry
from zbemt.models import Project, AirfoilDef, Results


def _make_project(path: str = "") -> Project:
    geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                      twist_root_deg=14.0, twist_tip_deg=2.0,
                                      root_cutout_norm=0.15, radius_m=1.0, n_stations=10)
    airfoil = AirfoilDef(source="analytical", stall_model="clip",
                          alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
    cfg = dict(Ne=6, Npsi=8, solver="fixed_point", max_iter=80)
    return Project(name="test_results", path=path, geometry=geom, airfoil=airfoil,
                    config=cfg)


def _make_disk_result() -> Results:
    """``Results`` with ``maps`` sufficient for the 3D disk -- and with two
    fields of DIFFERENT SHAPE (``Fn`` grows with radius, ``Mach`` varies
    with azimuth), so that coloring by one and raising by the other
    produces a surface distinct from either "same field" combination."""
    Ne, Npsi = 6, 8
    r = np.linspace(0.2, 1.0, Ne)
    psi = np.linspace(0, 2 * np.pi * (1 - 1 / Npsi), Npsi)
    R_NORM, PSI = np.meshgrid(r, psi, indexing="ij")
    ones = np.ones_like(R_NORM)
    maps = dict(R_NORM=R_NORM, R_DIM=R_NORM * 1.0, PSI=PSI,
                lambda_i=0.05 + 0.02 * np.sin(PSI) * R_NORM,
                Ut=ones * 5.0, Fn=R_NORM ** 2, Ft=ones * 0.1,
                Cl=ones * 0.5, Cd=ones * 0.02, Up=ones * 0.5, W=ones * 5.0,
                alpha_eff=ones * 0.05, phi=ones * 0.02, lambda_total=ones * 0.06,
                Mach=0.3 + 0.25 * np.sin(PSI))
    return Results(summary={"mu_x": 0.2}, maps=maps, condition_name="c1")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class ResultsTabBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def _window_on_results_tab(self, project=None):
        """A real `MainWindow`, already WITH the Results tab selected.

        Switching tabs is mandatory: on a tab that is not selected,
        widgets have `isVisible()` False and any visibility assertion
        passes without testing anything at all."""
        win = self.gui.MainWindow()
        win.state.set_project(project if project is not None else _make_project())
        index = win.tabs.count() - 1
        tab = win.tabs.widget(index)
        self.assertEqual(type(tab).__name__, "ResultsTab")
        # `show()` in addition to `setCurrentIndex`: without the window
        # shown, EVERY `isVisible()` is False and the visibility
        # assertions would pass without testing anything.
        win.resize(1500, 1000)
        win.show()
        win.tabs.setCurrentIndex(index)
        self.app.processEvents()
        self.addCleanup(win.deleteLater)
        return win, tab

    def _with_result(self, project=None):
        win, tab = self._window_on_results_tab(project)
        win.state.add_history_entry(kind="case", label="c1", results=_make_disk_result())
        self.app.processEvents()
        return win, tab


class Test3DViewHeightAndColorIndependent(ResultsTabBase):
    """Item 7: one selector for HEIGHT and another for COLOR."""

    def test_two_selectors_exist_and_height_allows_flat_disk(self):
        _, tab = self._with_result()
        tab.mode_list.setCurrentRow(tab._MODES.index("3D"))
        self.app.processEvents()

        self.assertTrue(tab.field_combo.isVisible())
        self.assertTrue(tab.z_field_combo.isVisible(),
                         "the Results tab needs a HEIGHT selector besides the color one")
        labels = [tab.z_field_combo.itemText(i) for i in range(tab.z_field_combo.count())]
        self.assertIn(tab._FLAT_DISC_LABEL, labels)
        # Default: the same quantity as the color (anyone who already used
        # the tab keeps seeing the relief of the chosen field).
        self.assertEqual(tab.z_field_combo.currentText(), tab.field_combo.currentText())

    def test_height_and_color_can_be_different_fields(self):
        _, tab = self._with_result()
        tab.field_combo.setCurrentText("Fn (thrust)")
        tab.z_field_combo.setCurrentText("Mach")
        self.assertEqual(tab._selected_3d_field(), "Fn")
        self.assertEqual(tab._3d_field_height(), "Mach")

        tab.z_field_combo.setCurrentText(tab._FLAT_DISC_LABEL)
        self.assertIsNone(tab._3d_field_height())

    def test_redraw_requests_mesh_with_different_field_and_z_field(self):
        """Where the regression actually bites: with color=Fn and
        height=Mach, the mesh must be requested with
        ``field="Fn", z_field="Mach"``. Before, ``z_field`` could only be
        the SAME field as the color (or ``None``)."""
        from zbemt.viz import visualization
        _, tab = self._with_result()
        tab.mode_list.setCurrentRow(tab._MODES.index("3D"))
        tab.field_combo.setCurrentText("Fn (thrust)")
        tab.z_field_combo.setCurrentText("Mach")
        # Touching the combos already drew and CACHED the figure
        # (`_CachedCanvas`); without discarding the cache, the redraw
        # below would not build any mesh and the spy would never be
        # called.
        tab.canvas_host.clear_cache()

        with unittest.mock.patch.object(
                visualization, "build_disk_grid",
                wraps=visualization.build_disk_grid) as spy:
            tab._refresh_3d_preview()
        self.assertTrue(spy.called, "the 3D view did not build any mesh")
        kwargs = spy.call_args.kwargs
        self.assertEqual(kwargs.get("field"), "Fn")
        self.assertEqual(kwargs.get("z_field"), "Mach")

        # And the (color, height) pair reaches the figure: with DIFFERENT
        # quantities the title names both, by their SYMBOLS (see
        # `Test3DViewLabels`).
        fig = tab._figure_3d_matplotlib(_make_disk_result().maps, "Fn", "Mach")
        title_text = fig.axes[0].get_title()
        self.assertIn(r"$F_n$", title_text)
        self.assertIn(r"$M$", title_text)

    def test_color_bar_and_z_axis_identify_their_quantity(self):
        _, tab = self._with_result()
        maps = _make_disk_result().maps
        fig = tab._figure_3d_matplotlib(maps, "Fn", "Mach")
        ax = fig.axes[0]
        self.assertIn(r"$M$", ax.get_zlabel())
        self.assertEqual(ax.zaxis.labelpad, -8)
        bar_labels = [a.get_ylabel() for a in fig.axes[1:]]
        self.assertTrue(any(r"$F_n$" in r for r in bar_labels),
                         f"colorbar does not name the field: {bar_labels}")

    def test_3d_mode_redraws_without_error_with_color_and_height_different(self):
        _, tab = self._with_result()
        tab.mode_list.setCurrentRow(tab._MODES.index("3D"))
        tab.field_combo.setCurrentText("lambda_i")
        tab.z_field_combo.setCurrentText("Cd")
        tab._refresh_3d_preview()      # must not raise
        tab.z_field_combo.setCurrentText(tab._FLAT_DISC_LABEL)
        tab._refresh_3d_preview()      # same, flat disk

    def test_table_paints_condition_label_with_subscript(self):
        _, tab = self._with_result()
        tab._refresh_table()
        header = tab.table_widget.verticalHeaderItem(0)
        self.assertIsNotNone(header)
        from zbemt.gui.tabs.results import _HTML_ROLE
        self.assertIn("&mu;<sub>x</sub>", header.data(_HTML_ROLE))


class TestExportsStartFromProjectFolder(ResultsTabBase):
    """Item 8: EVERY export dialog opens in ``<project>/outputs``."""

    def _project_on_disk(self) -> Project:
        import shutil
        import tempfile
        root = tempfile.mkdtemp(prefix="zbemt_results_tab_")
        self.addCleanup(shutil.rmtree, root, True)
        return _make_project(path=root)

    def test_helper_resolves_and_creates_project_outputs_dir(self):
        from zbemt import api
        proj = self._project_on_disk()
        _, tab = self._window_on_results_tab(proj)
        dest = tab._default_output_dir()
        self.assertEqual(dest, Path(api.default_project_paths(proj.path)["outputs"]))
        self.assertTrue(dest.is_dir(), "the output folder should be created if it does not exist")

    def test_without_project_falls_back_to_global_outputs(self):
        from zbemt import paths
        win, tab = self._window_on_results_tab()
        win.state.project = None
        self.assertEqual(tab._default_output_dir(create=False), paths.outputs_dir())

    def test_report_opens_in_project_outputs(self):
        from tests.helpers import patch_message_box_everywhere
        proj = self._project_on_disk()
        _, tab = self._with_result(proj)
        expected = str(Path(proj.path) / "outputs")
        with patch_message_box_everywhere("QMessageBox"):
            with unittest.mock.patch(
                    "zbemt.gui.tabs.results.QFileDialog") as dlg:
                dlg.getSaveFileName.return_value = ("", "")
                tab._generate_report()
        default_path = dlg.getSaveFileName.call_args.args[2]
        self.assertTrue(default_path.startswith(expected),
                         f"report does not start from {expected}: {default_path}")

    def test_3d_export_opens_in_project_outputs(self):
        from tests.helpers import patch_message_box_everywhere
        proj = self._project_on_disk()
        _, tab = self._with_result(proj)
        expected = str(Path(proj.path) / "outputs")
        with patch_message_box_everywhere("QMessageBox"):
            with unittest.mock.patch(
                    "zbemt.gui.tabs.results.require_optional_package",
                    return_value=True):
                with unittest.mock.patch(
                        "zbemt.gui.tabs.results.QFileDialog") as dlg:
                    dlg.getExistingDirectory.return_value = ""
                    tab._export_3d("rotor_3d")
        self.assertEqual(dlg.getExistingDirectory.call_args.args[2], expected)

    def test_disk_maps_dialog_starts_at_project_outputs(self):
        """The "Destination folder" field starts filled in with the
        project's folder, even without a project saved to disk (in that
        case, the global outputs)."""
        from tests.helpers import patch_message_box_everywhere
        proj = self._project_on_disk()
        _, tab = self._with_result(proj)
        expected = str(Path(proj.path) / "outputs")
        captured = {}

        def _fake_exec(self_dlg):
            # Walks the built dialog and reads the destination QLineEdit.
            from PyQt6.QtWidgets import QLineEdit, QDialog
            edits = self_dlg.findChildren(QLineEdit)
            captured["text"] = edits[0].text() if edits else None
            return QDialog.DialogCode.Rejected

        with patch_message_box_everywhere("QMessageBox"):
            with unittest.mock.patch(
                    "zbemt.gui.tabs.results.QDialog.exec", _fake_exec):
                tab._export_selected_disk_maps()
        self.assertEqual(captured.get("text"), expected)


class TestExportButtons(ResultsTabBase):
    """Export/Copy export and copy WHATEVER IS ON SCREEN.

    Before, there was a fixed "Export disk maps…" in any mode: in 3D, in
    Azimuth/Radius, or in the table, the single export button offered
    the plot the user was not even looking at -- and "Copy table" copied
    the table even with a plot in front."""

    def _set_mode(self, tab, mode: str):
        tab.mode_list.setCurrentRow(tab._MODES.index(mode))
        tab._update_export_buttons()

    def test_label_names_mode_output(self):
        _, tab = self._with_result()
        for mode, expected_export, expected_copy in (
                ("Disk map", "Export plots…", "Copy figure"),
                ("Table", "Export table…", "Copy table"),
                ("Azimuth / Radius", "Export plots…", "Copy figure"),
                ("3D", "Export plots…", "Copy figure")):
            with self.subTest(mode=mode):
                self._set_mode(tab, mode)
                self.assertEqual(tab.btn_export.text(), expected_export)
                self.assertEqual(tab.btn_copy.text(), expected_copy)

    def test_label_never_says_selection(self):
        """Item 9, preserved: the button only exists when there is a
        selection, and the dialog already says how many cases go out."""
        _, tab = self._with_result()
        for mode in tab._MODES:
            with self.subTest(mode=mode):
                self._set_mode(tab, mode)
                self.assertNotIn("selection", tab.btn_export.text().lower())

    def test_every_mode_has_label_and_tooltip_on_both_buttons(self):
        """A mode with no entry would fall back to a mute button -- no
        label saying what goes out and no tooltip saying the scope."""
        _, tab = self._with_result()
        for mode in tab._MODES:
            with self.subTest(mode=mode):
                self.assertIn(mode, tab._EXPORT_BY_MODE)
                self._set_mode(tab, mode)
                self.assertTrue(tab.btn_export.toolTip().strip())
                self.assertTrue(tab.btn_copy.toolTip().strip())

    def test_three_bottom_buttons_share_same_width(self):
        """And the width must fit the longest label of ANY mode: if
        measured only on the current one, the button would change size
        on every switch."""
        _, tab = self._with_result()
        tab.show()
        tab._update_export_buttons()
        widths = {b.minimumWidth() for b in tab._export_buttons}
        self.assertEqual(len(widths), 1, widths)
        tab.hide()

    def test_copy_in_plot_mode_does_not_copy_table(self):
        """The inversion test: with a plot on screen, "Copy" puts an
        IMAGE on the clipboard, not the table's TSV."""
        from PyQt6.QtWidgets import QApplication
        from tests.helpers import patch_message_box_everywhere
        _, tab = self._with_result()
        self._set_mode(tab, "Disk map")
        tab._refresh_current()
        QApplication.clipboard().clear()
        QApplication.clipboard().setText("sentinela")
        with patch_message_box_everywhere("QMessageBox"):
            tab._copy_from_screen()
        # either it copied the image (clearing the text), or it warned
        # that it could not -- in neither case does the table's TSV end
        # up there
        self.assertNotIn("condition_name", QApplication.clipboard().text())


class Test3DViewLabels(ResultsTabBase):
    """The 3D view used to show the RAW key name.

    User screenshot: the color bar said "colour: lambda_i" and the z
    axis "height: lambda_i" -- the same quantity that the selector just
    above, the 2D maps and the table already show as λᵢ. And, with both
    pointing to the SAME field, the pair still appeared a third time in
    the title."""

    def test_label_is_symbol_not_key(self):
        _, tab = self._with_result()
        for field, expected in (("lambda_i", r"$\lambda_i$"),
                                 ("Fn", r"$F_n$ [N/m]"),
                                 ("alpha_eff", r"$\alpha$ [deg]")):
            with self.subTest(field=field):
                self.assertEqual(tab._label_of_3d_field(field), expected)
                # and what appears is mathtext, not the raw name followed
                # by the unit -- which was the old format ("lambda_i [-]")
                self.assertTrue(tab._label_of_3d_field(field).startswith("$"))

    def test_symbol_comes_from_same_source_as_2d_maps(self):
        """No second list: `plots._DISK_FIELD_META` is the source, and
        every field offered in the 3D selector must be in it."""
        from zbemt.viz import plots
        _, tab = self._with_result()
        for field in tab._DISK_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, plots._DISK_FIELD_META)
                self.assertEqual(tab._label_of_3d_field(field).split(" [")[0],
                                  plots.disk_field_label(field))

    def test_plotly_receives_plain_text_not_mathtext(self):
        """Plotly does not render matplotlib mathtext: it would print
        `$\\lambda_i$` raw on the color bar."""
        _, tab = self._with_result()
        label = tab._label_of_3d_field("lambda_i", False)
        self.assertNotIn("$", label)
        self.assertNotIn("\\", label)
        self.assertIn("λ", label)          # a real λ

    def test_no_colour_or_height_words_in_labels(self):
        """Each symbol stays right next to what it describes -- the color
        bar and the z axis --, so the word adds nothing."""
        _, tab = self._with_result()
        for drawn in (True, False):
            with self.subTest(drawn=drawn):
                label = tab._label_of_3d_field("Fn", drawn)
                self.assertNotIn("colour", label.lower())
                self.assertNotIn("height", label.lower())

    def test_title_repeats_pair_only_when_color_and_height_differ(self):
        """With both on the same field (the screenshot's case), the title
        line was the THIRD repetition of the same quantity."""
        _, tab = self._with_result()
        self.assertEqual(tab._pair_3d_legend("lambda_i", "lambda_i"), "")
        self.assertEqual(tab._pair_3d_legend("Fn", None), "")
        legend = tab._pair_3d_legend("Fn", "Mach")
        self.assertIn("color", legend)
        self.assertIn("height", legend)
        self.assertIn(r"$F_n$", legend)
        self.assertIn(r"$M$", legend)

    def test_3d_figure_carries_symbols(self):
        """End to end: the real figure, not just the formatter."""
        _, tab = self._with_result()
        result = tab._resolve_single_result()
        if result is None:                     # pragma: no cover
            self.skipTest("no single result in the selection")
        fig = tab._figure_3d_matplotlib(result.maps, "lambda_i", "lambda_i")
        axis = fig.axes[0]
        self.assertEqual(axis.get_zlabel(), r"$\lambda_i$")
        # and the title does not carry the third repetition
        self.assertNotIn("height", axis.get_title())


class TestReverseFlowMaskLivesInResults(ResultsTabBase):
    """Item 10: the mask is a DISPLAY choice and lives only in this tab."""

    def test_checkbox_exists_and_visible_in_disk_mode(self):
        _, tab = self._with_result()
        tab.mode_list.setCurrentRow(tab._MODES.index("Disk map"))
        self.app.processEvents()
        self.assertTrue(tab.disk_mask_check.isVisible())
        self.assertIn("mask_reverse_flow_plots", tab.disk_mask_check.toolTip())

    def test_checkbox_reflects_project_config_on_open(self):
        proj = _make_project()
        proj.config["mask_reverse_flow_plots"] = False
        _, tab = self._window_on_results_tab(proj)
        self.assertFalse(tab.disk_mask_check.isChecked())

    def test_toggling_checkbox_writes_project_config(self):
        win, tab = self._with_result()
        self.assertTrue(tab.disk_mask_check.isChecked())
        tab.disk_mask_check.setChecked(False)
        self.assertIs(win.state.project.config["mask_reverse_flow_plots"], False)
        tab.disk_mask_check.setChecked(True)
        self.assertIs(win.state.project.config["mask_reverse_flow_plots"], True)

    def test_opening_project_does_not_mark_unsaved_work(self):
        proj = _make_project()
        proj.config["mask_reverse_flow_plots"] = False
        win, _ = self._window_on_results_tab(proj)
        self.assertFalse(win.state.unsaved,
                          "syncing the checkbox with the project must not dirty it")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestEnableHistoryButton(ResultsTabBase):
    """The "Enable convergence history" button was hidden in BOTH branches
    of `_refresh_convergence`, so a project saved with collect_history=false
    could never reach the affordance its own constructor docstring promises.
    PR-2: a real control that still has something to offer stays visible."""

    _CONVERGENCE_ROW = 5   # `_MODES` puts Convergence last on purpose

    def _open_convergence_with_result(self, cfg_collect_history=None):
        project = _make_project()
        if cfg_collect_history is not None:
            project.config["collect_history"] = cfg_collect_history
        win, tab = self._with_result(project)
        # Through the widget, so currentRow AND the options stack move
        # together exactly as on a real click.
        tab.mode_list.setCurrentRow(self._CONVERGENCE_ROW)
        tab._refresh_current()
        self.app.processEvents()
        return win, tab

    def test_button_visible_when_project_does_not_collect_history(self):
        win, tab = self._open_convergence_with_result(cfg_collect_history=False)
        self.assertTrue(tab.btn_enable_history.isVisible(),
                        "without history the user needs the affordance")

    def test_button_hidden_when_result_recorded_history(self):
        win, tab = self._open_convergence_with_result(cfg_collect_history=True)
        entry = win.state.results_history[-1]
        entry.results.summary["cfg_collect_history"] = True
        tab._refresh_current()
        self.app.processEvents()
        self.assertFalse(tab.btn_enable_history.isVisible())

    def test_click_writes_config_and_hides_the_button(self):
        win, tab = self._open_convergence_with_result(cfg_collect_history=False)
        with unittest.mock.patch("zbemt.gui.tabs.results.QMessageBox") as box:
            box.information.return_value = None
            tab._habilitar_historico_de_convergencia()
        self.assertTrue(win.state.project.config.get("collect_history"))
        self.assertFalse(tab.btn_enable_history.isVisible())


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestAxisCombosFollowPr2(ResultsTabBase):
    """The X/Y quantity dropdowns are empty until a result exists.
    PR-2: empty means DISABLED, not enabled-but-useless."""

    def test_xy_combos_disabled_without_results(self):
        win, tab = self._window_on_results_tab()
        tab._populate_xy_combos()
        self.app.processEvents()
        self.assertEqual(tab.xy_x_combo.count(), 0)
        self.assertFalse(tab.xy_x_combo.isEnabled())
        self.assertFalse(tab.xy_y_combo.isEnabled())
        # group-by always carries "(none)": something to choose, stays on
        self.assertTrue(tab.xy_group_combo.isEnabled())

    def test_xy_combos_enabled_once_results_exist(self):
        win, tab = self._with_result()
        tab._populate_xy_combos()
        self.app.processEvents()
        self.assertGreater(tab.xy_x_combo.count(), 0)
        self.assertTrue(tab.xy_x_combo.isEnabled())
        self.assertTrue(tab.xy_y_combo.isEnabled())


if __name__ == "__main__":   # pragma: no cover
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    unittest.main()
