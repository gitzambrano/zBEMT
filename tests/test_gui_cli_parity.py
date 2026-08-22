"""
test_gui_cli_parity.py
=======================

T7 (production-plan.md): `tests/test_cli_parity.py` only compares the CLI
against `api.open_project` -- never against what the GUI actually produces.
The "GUI/`.bemt`/CLI parity" principle in CLAUDE.md had no test to back it.

Here we build the SAME project by two independent paths --
(A) via the GUI's real widgets (same pattern as tests/test_gui_smoke.py:
instantiate the real tabs, set the widgets, fire the real "Apply to project"
slots) and (B) via `zbemt.cli` with equivalent flags -- and compare the
resulting `.bemt` files field by field.

We only cover fields that HAVE an equivalent CLI flag (see production-plan.md
S3: Ne/Npsi, cl_alpha/alpha0_deg/cd0/k and several other BEMTConfig/AirfoilDef
fields have no flag today -- that's not a bug in this suite, it's the
documented parity gap; can't compare what the CLI can't set)."""

import contextlib
import io
import os
import tempfile
import unittest

from tests import helpers
import unittest.mock

try:
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except Exception:  # pragma: no cover - ambiente sem PyQt6
    _HAS_QT = False

from zbemt import api
from zbemt import cli as main_batch


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestGuiCliParity(unittest.TestCase):
    """Build the same project via the GUI (path A) and CLI (path B),
    then compare the resulting `.bemt` files (via `api.open_project`
    in each folder)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    # custom geometry shared by the two paths
    _R = [0.15, 0.5, 1.0]
    _C = [0.09, 0.06, 0.03]
    _T = [12.0, 6.0, 0.0]
    _N_BLADES = 3
    _RADIUS_M = 1.35

    def _build_via_gui(self, project_dir: str):
        gui = self.gui
        state = gui.AppState()
        project = api.new_project(project_dir, name="parity_gui")
        state.set_project(project)

        # --- Geometry: global constants + custom table ---
        geom_tab = gui.GeometryTab(state)
        geom_tab.n_blades.setValue(self._N_BLADES)
        geom_tab.radius_m.setValue(self._RADIUS_M)
        geom_tab.table.blockSignals(True)
        geom_tab.table.setRowCount(len(self._R))
        from PyQt6.QtWidgets import QTableWidgetItem
        for i, (r, c, t) in enumerate(zip(self._R, self._C, self._T)):
            geom_tab.table.setItem(i, 0, QTableWidgetItem(str(r)))
            geom_tab.table.setItem(i, 1, QTableWidgetItem(str(c)))
            geom_tab.table.setItem(i, 2, QTableWidgetItem(str(t)))
        geom_tab.table.blockSignals(False)
        geom_tab._apply_table_edits()

        # --- Airfoil: analytical source, stall_model + dynamic stall ---
        airfoil_tab = gui.AirfoilTab(state)
        airfoil_tab.source_combo.setCurrentText("analytical")
        airfoil_tab.stall_model_combo.setCurrentText("clip")
        airfoil_tab.use_dynamic_stall.setChecked(True)
        with helpers.patch_message_box_everywhere("QMessageBox"):
            airfoil_tab._apply_to_project()

        # --- Config/Engine: inflow, prandtl, solver, augmentations ---
        config_tab = gui.ConfigMotorTab(state)
        config_tab.cfg_inflow_family.setCurrentText("coleman")
        idx = config_tab.cfg_prandtl_loss_mode.findData("tip")
        config_tab.cfg_prandtl_loss_mode.setCurrentIndex(idx)
        config_tab.cfg_solver.setCurrentText("newton")
        config_tab.cfg_use_rotational_augmentation.setChecked(True)
        config_tab.cfg_use_radial_flow_correction.setChecked(True)
        with helpers.patch_message_box_everywhere("QMessageBox"):
            config_tab._apply_config_to_project()

        api.save_project(state.project)

    def _build_via_cli(self, project_dir: str):
        points = ",".join(f"{r}:{c}:{t}" for r, c, t in zip(self._R, self._C, self._T))
        with contextlib.redirect_stdout(io.StringIO()):
            main_batch.main([
                "--new", project_dir, "--rpm", "600",
                "--geom-preset", "custom", "--geom-custom-points", points,
                "--geom-n-blades", str(self._N_BLADES), "--geom-radius", str(self._RADIUS_M),
                "--airfoil-source", "analytical", "--airfoil-stall-model", "clip",
                "--dynamic-stall",
                "--inflow", "coleman_local", "--prandtl-loss-mode", "tip",
                "--solver", "newton",
                "--rotational-augmentation", "--radial-flow-correction",
                "--save-as", project_dir,
            ])

    def test_gui_and_cli_produce_the_same_project(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            path_gui = os.path.join(d1, "proj_gui")
            path_cli = os.path.join(d2, "proj_cli")
            self._build_via_gui(path_gui)
            self._build_via_cli(path_cli)

            proj_gui = api.open_project(path_gui)
            proj_cli = api.open_project(path_cli)

            # --- geometry ---
            self.assertEqual(proj_gui.geometry.r_norm, proj_cli.geometry.r_norm)
            self.assertEqual(proj_gui.geometry.chord_norm, proj_cli.geometry.chord_norm)
            self.assertEqual(proj_gui.geometry.twist_deg, proj_cli.geometry.twist_deg)
            self.assertEqual(proj_gui.geometry.n_blades, proj_cli.geometry.n_blades)
            self.assertEqual(proj_gui.geometry.radius_m, proj_cli.geometry.radius_m)

            # --- airfoil ---
            self.assertEqual(proj_gui.airfoil.source, proj_cli.airfoil.source)
            self.assertEqual(proj_gui.airfoil.stall_model, proj_cli.airfoil.stall_model)
            self.assertEqual(proj_gui.airfoil.use_dynamic_stall, proj_cli.airfoil.use_dynamic_stall)

            # --- config ---
            self.assertEqual(proj_gui.config["inflow_field_model"], proj_cli.config["inflow_field_model"])
            self.assertEqual(proj_gui.config["prandtl_loss_mode"], proj_cli.config["prandtl_loss_mode"])
            self.assertEqual(proj_gui.config["solver"], proj_cli.config["solver"])
            self.assertEqual(proj_gui.config["use_rotational_augmentation"],
                              proj_cli.config["use_rotational_augmentation"])
            self.assertEqual(proj_gui.config["use_radial_flow_correction"],
                              proj_cli.config["use_radial_flow_correction"])


if __name__ == "__main__":
    unittest.main()
