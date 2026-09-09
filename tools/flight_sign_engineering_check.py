"""Exercise flight-condition signs through GUI, CLI-style API, and .bemt I/O.

The checks are deliberately physical rather than structural. They construct the
conditions an engineer enters, run the engine, and compare the reported angle
with the requested wind side.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from zbemt import api, nomenclature
from zbemt.gui.common import AppState
from zbemt.gui.tabs.run_case import RunCaseTab
from zbemt.gui.tabs.run_batch import RunBatchTab
from tests.helpers import make_studies_project


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS  {message}")


def run() -> None:
    app = QApplication.instance() or QApplication([])

    # Canonical mathematical contract.
    check(nomenclature.alpha_rotor_axial_velocity(5.0, 40.0) < 0.0,
          "alpha_rotor + => rotor Vz - (wind from below)")
    check(nomenclature.alpha_rotor_axial_velocity(-5.0, 40.0) > 0.0,
          "alpha_rotor - => rotor Vz + (wind from above)")
    check(nomenclature.alpha_disk_cross_velocity(5.0, 60.0) < 0.0,
          "alpha_disk + => propeller display Vz - (wind from below)")
    check(nomenclature.alpha_disk_cross_velocity(-5.0, 60.0) > 0.0,
          "alpha_disk - => propeller display Vz + (wind from above)")

    # Rotor GUI -> canonical FlightCondition -> engine.
    rotor = make_studies_project()
    rotor.config["is_propeller"] = False
    state = AppState(); state.project = rotor
    tab = RunCaseTab(state); tab.show(); app.processEvents()
    tab.rpm_spin.setValue(600.0)
    tab.advance.unit_combo.setCurrentText("Vₓ [m/s]")
    tab.advance.spin.setValue(40.0)
    tab.axial.unit_combo.setCurrentText("αᵣₒₜₒᵣ [deg]")
    tab.axial.spin.setValue(5.0)
    c = tab._current_condition()
    check(c.Vz < 0.0, "Run Case rotor alpha_rotor + builds negative internal/display Vz")
    r = api.run_case(rotor, c)
    check(abs(r.summary["alpha_rotor_deg"] - 5.0) < 1e-3,
          "Run Case rotor angle survives engine round trip")
    tab.grab().save("rotor_sign_gui.png")
    tab.close(); tab.deleteLater()

    # Propeller GUI -> canonical FlightCondition -> engine.
    prop = make_studies_project()
    prop.config["is_propeller"] = True
    state = AppState(); state.project = prop
    tab = RunCaseTab(state); tab.show(); app.processEvents()
    tab.rpm_spin.setValue(1200.0)
    tab.axial.unit_combo.setCurrentText("Vₓ [m/s]")
    tab.axial.spin.setValue(60.0)
    tab.advance.unit_combo.setCurrentText("α_dᵢₛₖ [deg]")
    tab.advance.spin.setValue(5.0)
    c = tab._current_condition()
    check(c.Vz > 0.0, "Run Case propeller axial Vx reaches positive internal shaft component")
    check(c.mu_x < 0.0, "Run Case propeller alpha_disk + builds negative display Vz cross-flow")
    r = api.run_case(prop, c)
    check(abs(r.summary["alpha_disk_deg"] - 5.0) < 1e-3,
          "Run Case propeller angle survives engine round trip")

    # Unit switching must preserve the same physical vector.
    tab.advance.unit_combo.setCurrentText("V_z [m/s]")
    cross_before = tab.advance.spin.value()
    check(cross_before < 0.0, "alpha_disk + displays negative Vz after unit switch")
    c2 = tab._current_condition()
    check(abs(c2.mu_x - c.mu_x) < 2e-5 and abs(c2.Vz - c.Vz) < 1e-9,
          "GUI alpha_disk <-> Vz switch preserves the physical condition")
    tab.advance.spin.setValue(6.0)
    c3 = tab._current_condition()
    check(c3.mu_x > 0.0, "positive propeller Vz input remains positive at engine boundary")
    r3 = api.run_case(prop, c3)
    check(r3.summary["alpha_disk_deg"] < 0.0,
          "positive propeller Vz reports negative alpha_disk (wind from above)")
    tab.grab().save("propeller_sign_gui.png")
    tab.close(); tab.deleteLater()

    # Run Batch case-by-case path uses the same GUI widgets and condition builder.
    state = AppState(); state.project = prop
    batch = RunBatchTab(state); batch.show(); app.processEvents()
    batch.rpm_spin.setValue(1200.0)
    batch.add_row_axial.unit_combo.setCurrentText("Vₓ [m/s]")
    batch.add_row_axial.spin.setValue(60.0)
    batch.add_row_advance.unit_combo.setCurrentText("α_dᵢₛₖ [deg]")
    batch.add_row_advance.spin.setValue(5.0)
    bc = batch._standalone_condition()
    check(bc.mu_x < 0.0 and bc.Vz > 0.0,
          "Run Batch case-by-case alpha_disk + builds correct engine condition")
    batch.grab().save("propeller_sign_batch_gui.png")
    batch.close(); batch.deleteLater()

    # API alias path is the path used by a .bemt file that contains an angle.
    alias_project = make_studies_project()
    alias_project.config["is_propeller"] = True
    from zbemt.models import FlightCondition
    alias_project.saved_cases = [FlightCondition(
        name="angle_alias", mu_x=0.0, Vz=60.0, rpm=1200.0,
        collective_deg=8.0)]
    setattr(alias_project.saved_cases[0], "_alpha_alias",
            ("alpha_disk_deg", 5.0))
    api.resolve_alpha_aliases(alias_project)
    ac = alias_project.saved_cases[0]
    check(ac.mu_x < 0.0 and ac.Vz > 0.0,
          ".bemt alpha_disk alias resolves to negative propeller display Vz")
    ar = api.run_case(alias_project, ac)
    check(abs(ar.summary["alpha_disk_deg"] - 5.0) < 1e-3,
          ".bemt alpha_disk alias runs as the requested angle")

    # Persistence boundary: display Vz sign must survive save/load unchanged.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "sign_project"
        prop.saved_cases = [c3]
        api.save_project(prop, str(root))
        loaded = api.load_project(str(root))
        lc = loaded.saved_cases[0]
        check(lc.mu_x > 0.0 and lc.Vz > 0.0,
              ".bemt round trip preserves positive propeller display Vz and axial Vx")
        lr = api.run_case(loaded, lc)
        check(lr.summary["alpha_disk_deg"] < 0.0,
              ".bemt positive propeller Vz still means wind from above after reload")

    # Reverse shaft flow must not change the side convention.
    reverse_cross = nomenclature.alpha_disk_cross_velocity(5.0, -60.0)
    check(reverse_cross < 0.0,
          "reverse propeller axial flow does not flip alpha_disk cross-flow side")
    check(abs(nomenclature.alpha_disk_from_components(reverse_cross, -60.0) - 5.0) < 1e-9,
          "reverse propeller axial flow round-trips alpha_disk")

    print("\nEngineering sign-convention check complete.")


if __name__ == "__main__":
    run()
