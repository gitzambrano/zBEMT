"""Exercise every Engineering Tool and capture its populated result state.

This complements ``gui_qa_screenshots.py``.  The general matrix proves every
page renders in empty/loaded states at several viewport sizes; this script
presses the run path of each Tool and records what an engineer sees after the
work completes.  Geometry Designer, Stability Derivatives and Transient
Simulation use the real BEMT/studies engine.  Design Optimization uses the real
optimizer and real BEMT evaluations on a deliberately tiny search.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tools.gui_qa_screenshots import (
    Recorder,
    _configure_application,
    _make_fast_rotor_project,
    _settle,
    _wait_for_worker,
)


def _grab_result_pages(rec: Recorder, tool, key: str, pages: list[int]) -> None:
    for index in pages:
        tool.pages.setCurrentIndex(index)
        _settle(rec.app)
        title = tool.pages.tabText(index) or f"step-{index + 1}"
        for size_name, width, height in (
            ("desktop", 1500, 1000),
            ("laptop", 1366, 700),
        ):
            rec.grab(
                tool,
                f"{key}/{size_name}/{index + 1:02d}-used.png",
                requested=(width, height),
                strict_fit=size_name == "laptop",
                state="used-results",
                screen=f"{key} / {title} / used",
            )


def _designer(rec: Recorder, window, project) -> None:
    from tests import helpers

    window.state.set_project(project)
    tool = window.geometry_designer
    tool._refresh_from_project()
    tool.vsweep_param_combo.setCurrentText("tip_chord_norm")
    tool.vsweep_values_edit.setText("0.065")
    tool.btn_build_sweep.click()
    if tool.variants_table.rowCount() != 2:
        raise RuntimeError(
            f"Geometry Designer expected base + one variant, got "
            f"{tool.variants_table.rowCount()} rows")
    tool.radio_single.setChecked(True)
    tool.mu_x_spin.setValue(0.10)
    tool.collective_spin.setValue(8.0)
    tool.vz_spin.setValue(0.0)
    tool.rpm_spin.setValue(600.0)
    tool.workers_spin.setValue(1)
    with helpers.patch_message_box_everywhere("QMessageBox"):
        tool._run_comparison()
        worker = tool._compare_worker
        if worker is None:
            raise RuntimeError("Geometry Designer did not launch its comparison worker")
        _wait_for_worker(worker)
    if len(tool._comparison_results) != 2:
        raise RuntimeError(
            f"Geometry Designer expected two real solves, got "
            f"{len(tool._comparison_results)}")
    if tool.verdict_strip.count() != 2:
        raise RuntimeError("Geometry Designer result verdict did not populate")
    rec.engineering_checks["geometry_designer_solves"] = len(
        tool._comparison_results)
    _grab_result_pages(rec, tool, "geometry-designer", [0, 2])
    tool.hide()


def _optimizer(rec: Recorder, window, project) -> None:
    from tests import helpers
    from zbemt.models import (
        ConstraintDef,
        DesignVariable,
        FlightCondition,
        ObjectiveDef,
        OptimizationDefinition,
    )

    condition = FlightCondition(
        name="qa optimization", mu_x=0.10, collective_deg=8.0, rpm=600.0)
    project.saved_cases = [condition]
    project.optimizations = [OptimizationDefinition(
        name="QA tiny real optimization",
        objectives=[ObjectiveDef(key="CT", kind="maximize"),
                    ObjectiveDef(key="FM", kind="maximize")],
        constraints=[ConstraintDef(key="CT", operator=">=", value=0.0)],
        variables=[DesignVariable(param="root_chord_norm", lower=0.085,
                                  upper=0.115),
                   DesignVariable(param="tip_chord_norm", lower=0.040,
                                  upper=0.070)],
        algorithm="nsga2",
        population=8,
        generations=1,
        seed=200809,
        condition=condition,
    )]
    window.state.set_project(project)
    tool = window.optimizer_window
    tool._refresh_from_project()
    with helpers.patch_message_box_everywhere("QMessageBox"):
        tool._run()
        worker = tool._worker
        if worker is None:
            raise RuntimeError("Design Optimization did not launch its worker")
        _wait_for_worker(worker, timeout_ms=180000)
    outcome = tool._outcome
    if outcome is None or not outcome.front_params:
        raise RuntimeError("Design Optimization completed without a Pareto front")
    if tool.front_table.rowCount() < 1:
        raise RuntimeError("Design Optimization result table did not populate")
    rec.engineering_checks["optimizer_front_members"] = len(outcome.front_params)
    rec.engineering_checks["optimizer_evaluations"] = len(outcome.all_evaluations)
    _grab_result_pages(rec, tool, "optimizer", [0, 1])
    tool.hide()


def _stability(rec: Recorder, window, project) -> None:
    from tests import helpers
    from zbemt.models import DerivativeRequest, FlightCondition

    condition = FlightCondition(
        name="qa derivatives", mu_x=0.0, collective_deg=8.0, rpm=600.0)
    project.saved_cases = [condition]
    project.geometry.dynamics.flap_model = "offset"
    project.geometry.dynamics.hinge_offset_norm = 0.08
    project.derivatives = [DerivativeRequest(
        name="QA real derivatives",
        condition=condition,
        trim="none",
        states=["w"],
        controls=["theta_0"],
        outputs=["Thrust"],
        richardson_check=False,
        parallel_workers=1,
    )]
    window.state.set_project(project)
    tool = window.stability_window
    tool._refresh_from_project()
    with helpers.patch_message_box_everywhere("QMessageBox"):
        tool._run()
        worker = tool._worker
        if worker is None:
            raise RuntimeError("Stability Derivatives did not launch its worker")
        _wait_for_worker(worker, timeout_ms=180000)
    outcome = tool._outcome
    if outcome is None or not outcome.matrix:
        raise RuntimeError("Stability Derivatives completed without a matrix")
    if tool.matrix_table.rowCount() < 1:
        raise RuntimeError("Stability Derivatives matrix table did not populate")
    rec.engineering_checks["stability_matrix_terms"] = len(outcome.matrix)
    _grab_result_pages(rec, tool, "stability", [0, 2])
    tool.hide()


def _transient(rec: Recorder, window, project) -> None:
    from tests import helpers
    from zbemt.models import FlightCondition, ManeuverDefinition, ManeuverPoint

    # The maneuver path explicitly requires unsteady Pitt-Peters inflow.
    project.config["inflow_field_model"] = "pitt_peters_unsteady"
    project.config["max_iter"] = 60
    project.saved_cases = [
        FlightCondition(name="start", mu_x=0.02, collective_deg=8.0,
                        rpm=600.0),
        FlightCondition(name="end", mu_x=0.05, collective_deg=8.5,
                        rpm=600.0),
    ]
    project.maneuvers = [ManeuverDefinition(
        name="QA short ramp",
        points=[
            ManeuverPoint(t_s=0.0, mu_x=0.02, Vz=0.0,
                          collective_deg=8.0, rpm=600.0),
            ManeuverPoint(t_s=0.10, mu_x=0.05, Vz=0.0,
                          collective_deg=8.5, rpm=600.0),
        ],
        dt_s=0.05,
        substeps_per_step=1,
    )]
    window.state.set_project(project)
    tool = window.transient_window
    tool._refresh_from_project()
    with helpers.patch_message_box_everywhere("QMessageBox"):
        tool._run()
        worker = tool._worker
        if worker is None:
            raise RuntimeError("Transient Simulation did not launch its worker")
        _wait_for_worker(worker, timeout_ms=180000)
    history = tool._history
    if history is None or len(history) < 2:
        raise RuntimeError("Transient Simulation completed without history")
    if tool.history_table.rowCount() != len(history):
        raise RuntimeError("Transient Simulation history table did not populate")
    rec.engineering_checks["transient_samples"] = len(history)
    _grab_result_pages(rec, tool, "transient", [0, 1])
    tool.hide()


def _fresh_project(tmp: str, name: str):
    root = Path(tmp) / name
    root.mkdir(parents=True, exist_ok=True)
    return _make_fast_rotor_project(str(root))


def generate(destination: Path) -> Path:
    app = _configure_application()
    from zbemt.gui.app import MainWindow

    destination.mkdir(parents=True, exist_ok=True)
    rec = Recorder(destination, app)
    window = MainWindow()
    window.show()
    _settle(app)

    with tempfile.TemporaryDirectory(prefix="zbemt_tools_qa_") as tmp:
        # Fresh on-disk roots keep each Tool's persistence and state isolated.
        _designer(rec, window, _fresh_project(tmp, "designer"))
        _optimizer(rec, window, _fresh_project(tmp, "optimizer"))
        _stability(rec, window, _fresh_project(tmp, "stability"))
        _transient(rec, window, _fresh_project(tmp, "transient"))

    window.hide()
    _settle(app)
    path = destination / "manifest.json"
    path.write_text(json.dumps({
        "screenshot_count": len(rec.records),
        "engineering_checks": rec.engineering_checks,
        "screenshots": rec.records,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\n{len(rec.records)} used-state Tool screenshots written to {destination}")
    print(json.dumps(rec.engineering_checks, indent=2, sort_keys=True))
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "artifacts" / "gui-qa" / "tools-used")
    args = parser.parse_args(argv)
    generate(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
