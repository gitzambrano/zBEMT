"""Headless, reproducible GUI QA matrix for zBEMT.

This is deliberately separate from ``tools/gui_screenshots.py``.  The latter
owns the compact screenshots embedded in the documentation; this script owns
merge-gate evidence.  It renders the real application theme, exercises real
rotor cases through the GUI worker path, and captures every main page and every
Engineering Tool workflow page at several viewport sizes.

Typical CI use::

    QT_QPA_PLATFORM=offscreen python tools/gui_qa_screenshots.py \
        --output artifacts/gui-qa

The output contains PNG files plus ``manifest.json`` with requested/actual
window sizes and basic engineering sanity checks.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

DEFAULT_OUTPUT = ROOT / "artifacts" / "gui-qa"
ROTOR_PROJECT = ROOT / "projects" / "starter_rotor"
PROPELLER_PROJECT = ROOT / "projects" / "starter_propeller"

MAIN_SIZES = (
    ("desktop", 1500, 1000),
    ("laptop", 1366, 700),
    ("minimum", 1024, 680),
)
TOOL_SIZES = (
    ("desktop", 1500, 1000),
    ("laptop", 1366, 700),
    # Intentionally tighter than the documented small-laptop gate.  It is
    # evidence, not a hard requirement: the manifest records if Qt clamps it.
    ("tight", 1100, 680),
)

FONT_DIRS = (
    r"C:\Windows\Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/System/Library/Fonts",
)


def _ensure_fonts() -> None:
    if os.environ.get("QT_QPA_FONTDIR"):
        return
    for path in FONT_DIRS:
        if Path(path).is_dir():
            os.environ["QT_QPA_FONTDIR"] = path
            return


def _settle(app, cycles: int = 20) -> None:
    for _ in range(cycles):
        app.processEvents()


def _slug(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return text or "page"


def _configure_application():
    """Build QApplication exactly like ``zbemt.gui.app.main`` does."""
    _ensure_fonts()
    from PyQt6.QtCore import QCoreApplication, Qt
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication([])
    if not QFontDatabase.families():
        raise RuntimeError("Qt has no fonts; visual QA screenshots would be invalid")

    from zbemt.gui import styles

    app.setStyle("Fusion")
    font = app.font()
    font.setPointSize(max(font.pointSize(), 10))
    app.setFont(font)
    app.setStyleSheet(styles.APP_QSS)
    return app


class Recorder:
    def __init__(self, root: Path, app):
        self.root = root
        self.app = app
        self.records: list[dict] = []
        self.engineering_checks: dict[str, object] = {}
        root.mkdir(parents=True, exist_ok=True)

    def grab(self, widget, relative: str, *, requested=None, strict_fit=False,
             state: str, screen: str) -> Path:
        if requested is not None:
            width, height = requested
            widget.resize(width, height)
        widget.show()
        _settle(self.app)

        actual = (widget.width(), widget.height())
        if requested is not None and strict_fit:
            if actual[0] > requested[0] or actual[1] > requested[1]:
                raise RuntimeError(
                    f"{screen} cannot fit requested {requested[0]}x{requested[1]}: "
                    f"Qt clamped it to {actual[0]}x{actual[1]}")

        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        pixmap = widget.grab()
        if pixmap.isNull() or not pixmap.save(str(target)):
            raise RuntimeError(f"failed to save screenshot {target}")
        if not target.exists() or target.stat().st_size == 0:
            raise RuntimeError(f"empty screenshot {target}")

        self.records.append({
            "file": str(target.relative_to(self.root)).replace("\\", "/"),
            "state": state,
            "screen": screen,
            "requested_size": list(requested) if requested else None,
            "actual_size": list(actual),
            "bytes": target.stat().st_size,
        })
        print(f"  {state:18} {screen:34} {actual[0]:4}x{actual[1]:4}  {target.name}")
        return target

    def write_manifest(self) -> Path:
        path = self.root / "manifest.json"
        payload = {
            "screenshot_count": len(self.records),
            "engineering_checks": self.engineering_checks,
            "screenshots": self.records,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path


def _capture_main_tabs(rec: Recorder, window, *, state_name: str, sizes,
                       strict_sizes: set[str] | None = None) -> None:
    strict_sizes = strict_sizes or set()
    for size_name, width, height in sizes:
        for index in range(window.tabs.count()):
            window.tabs.setCurrentIndex(index)
            _settle(rec.app)
            title = window.tabs.tabText(index).replace(" *", "")
            rec.grab(
                window,
                f"main/{state_name}/{size_name}/{index + 1:02d}-{_slug(title)}.png",
                requested=(width, height),
                strict_fit=size_name in strict_sizes,
                state=state_name,
                screen=f"Main / {title}",
            )


def _capture_launcher(rec: Recorder, window, state_name: str) -> None:
    launcher = window.flow_bar._tools_launcher
    rec.grab(
        launcher,
        f"tools/{state_name}/launcher.png",
        requested=(650, 560),
        strict_fit=True,
        state=state_name,
        screen="Engineering Tools launcher",
    )
    launcher.hide()


def _capture_tools(rec: Recorder, window, *, state_name: str, sizes) -> None:
    tools = (
        ("geometry-designer", "Geometry Designer", window.geometry_designer),
        ("transient", "Transient Simulation", window.transient_window),
        ("optimizer", "Design Optimization", window.optimizer_window),
        ("stability", "Stability Derivatives", window.stability_window),
    )
    for key, title, tool in tools:
        pages = tool.pages
        for size_name, width, height in sizes:
            for index in range(pages.count()):
                pages.setCurrentIndex(index)
                _settle(rec.app)
                page_title = pages.tabText(index) or f"step-{index + 1}"
                rec.grab(
                    tool,
                    f"tools/{state_name}/{key}/{size_name}/{index + 1:02d}-{_slug(page_title)}.png",
                    requested=(width, height),
                    strict_fit=size_name == "laptop",
                    state=state_name,
                    screen=f"{title} / {page_title}",
                )
        tool.hide()


def _wait_for_worker(worker, timeout_ms: int = 90000) -> None:
    from PyQt6.QtCore import QCoreApplication, QEventLoop, QThread, QTimer

    thread = worker.thread()
    loop = QEventLoop()
    finished = {"done": False, "error": None}

    def _done(*_args):
        finished["done"] = True
        loop.quit()

    def _failed(error):
        finished["done"] = True
        finished["error"] = str(error)
        loop.quit()

    worker.finished.connect(_done)
    worker.failed.connect(_failed)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    if not finished["done"]:
        raise RuntimeError("GUI worker did not finish before QA timeout")

    # ``worker.finished`` / ``worker.failed`` only schedules ``thread.quit()``
    # in ``launch_worker``.  The signal does not guarantee that the QThread's
    # event loop has actually stopped.  The QA process used to reach Python/Qt
    # teardown with a live worker thread and could segfault after writing every
    # screenshot.  Join the real thread before allowing teardown to continue.
    if isinstance(thread, QThread) and thread is not QThread.currentThread():
        if thread.isRunning():
            thread.quit()
        if not thread.wait(timeout_ms):
            raise RuntimeError("GUI worker QThread did not stop before QA timeout")
        QCoreApplication.processEvents()

    if finished["error"]:
        raise RuntimeError(f"GUI worker failed: {finished['error']}")


def _make_fast_rotor_project(tmp: str):
    """Small but physical rotor used by the GUI E2E suite as well."""
    from zbemt import api, geometry as geometry_mod
    from zbemt.models import AirfoilDef

    path = Path(tmp) / "qa_rotor"
    project = api.new_project(str(path), name="QA rotor")
    project.geometry = geometry_mod.generate_tapered(
        root_chord_norm=0.10,
        tip_chord_norm=0.05,
        twist_root_deg=14.0,
        twist_tip_deg=2.0,
        root_cutout_norm=0.15,
        radius_m=8.18,
        n_blades=4,
        n_stations=10,
        airfoil_name="qa-airfoil",
    )
    project.airfoil = AirfoilDef(
        source="analytical",
        stall_model="clip",
        alpha_stall_pos_deg=15.0,
        alpha_stall_neg_deg=-6.0,
    )
    project.config.update({
        "Ne": 8,
        "Npsi": 6,
        "solver": "fixed_point",
        "max_iter": 60,
        "reverse_flow_model": "simple_flip",
    })
    return project


def _exercise_real_engineering_flow(rec: Recorder, window) -> None:
    """Drive real Run Case + Run Batch workers and capture populated states."""
    from PyQt6.QtWidgets import QMessageBox
    from tests import helpers

    with tempfile.TemporaryDirectory(prefix="zbemt_gui_qa_") as tmp:
        project = _make_fast_rotor_project(tmp)
        window.state.set_project(project)
        window.state.notify_geometry()
        window.state.notify_airfoil()
        window.state.notify_config()

        with helpers.patch_message_box_everywhere("QMessageBox") as msgbox:
            msgbox.StandardButton = QMessageBox.StandardButton
            msgbox.question.return_value = QMessageBox.StandardButton.Yes

            case = window.tabs.widget(4)
            window.tabs.setCurrentIndex(4)
            case.advance.unit_combo.setCurrentText("mu_x")
            case.advance.set_mu(0.0)
            case.axial.unit_combo.setCurrentIndex(0)
            case.axial.spin.setValue(0.0)
            case.collective_spin.setValue(8.0)
            case.rpm_spin.setValue(600.0)
            case._run_case()
            _wait_for_worker(case._worker)
            hover_ct = float(window.state.last_results.summary["CT"])
            if not (0.0 < hover_ct < 0.5):
                raise RuntimeError(f"hover CT failed sanity check: {hover_ct}")
            rec.engineering_checks["hover_CT"] = hover_ct
            rec.grab(case, "used/run-case-hover.png", state="used-real-run",
                     screen="Run Case / hover result")

            case.advance.set_mu(0.25)
            case.axial.spin.setValue(-5.0)
            case._run_case()
            _wait_for_worker(case._worker)
            fwd = window.state.last_results.summary
            fwd_ct = float(fwd["CT"])
            fwd_cq = float(fwd["CQ"])
            if abs(fwd_ct) >= 0.5:
                raise RuntimeError(f"forward-flight CT failed sanity check: {fwd_ct}")
            rec.engineering_checks["forward_CT"] = fwd_ct
            rec.engineering_checks["forward_CQ"] = fwd_cq

            for size_name, width, height in MAIN_SIZES:
                rec.grab(
                    window,
                    f"used/run-case-forward-{size_name}.png",
                    requested=(width, height),
                    strict_fit=True,
                    state="used-real-run",
                    screen="Main / Run Case / forward-flight result",
                )

            results = window.tabs.widget(6)
            window.tabs.setCurrentIndex(6)
            for size_name, width, height in MAIN_SIZES:
                rec.grab(
                    window,
                    f"used/results-after-cases-{size_name}.png",
                    requested=(width, height),
                    strict_fit=True,
                    state="used-real-run",
                    screen="Main / Results / populated",
                )

            batch = window.tabs.widget(5)
            window.tabs.setCurrentIndex(5)
            slot1, unit1, values1 = batch.axis_rows[0]
            idx_advance = next(
                i for i, (_label, slot) in enumerate(batch._AXIS_SLOTS)
                if slot == "inplane")
            slot1.setCurrentIndex(idx_advance)
            unit1.setCurrentText("mu_x")
            values1.setText("0.0, 0.1")

            slot2, _unit2, values2 = batch.axis_rows[1]
            idx_collective = next(
                i for i, (_label, slot) in enumerate(batch._AXIS_SLOTS)
                if slot == "collective_deg")
            slot2.setCurrentIndex(idx_collective)
            values2.setText("6.0, 10.0")
            batch.fixed_rpm.setValue(600.0)
            batch._generate_cases()
            if batch.batch_table.rowCount() != 4:
                raise RuntimeError(
                    f"expected 4 generated batch cases, got {batch.batch_table.rowCount()}")
            rec.grab(
                window,
                "used/run-batch-queued-laptop.png",
                requested=(1366, 700),
                strict_fit=True,
                state="used-real-run",
                screen="Main / Run Batch / populated queue",
            )

            batch._run_batch()
            _wait_for_worker(batch._worker)
            completed = [
                batch.batch_table.item(i, batch._COL_STATUS).text()
                for i in range(batch.batch_table.rowCount())
            ]
            if not all(text.startswith("OK") for text in completed):
                raise RuntimeError(f"batch did not complete cleanly: {completed}")
            rec.engineering_checks["batch_cases_completed"] = len(completed)
            for size_name, width, height in MAIN_SIZES:
                rec.grab(
                    window,
                    f"used/run-batch-complete-{size_name}.png",
                    requested=(width, height),
                    strict_fit=True,
                    state="used-real-run",
                    screen="Main / Run Batch / completed",
                )

            window.tabs.setCurrentIndex(6)
            for size_name, width, height in MAIN_SIZES:
                rec.grab(
                    window,
                    f"used/results-after-batch-{size_name}.png",
                    requested=(width, height),
                    strict_fit=True,
                    state="used-real-run",
                    screen="Main / Results / case + batch history",
                )


def generate(destination: Path) -> Path:
    app = _configure_application()
    from zbemt import api
    from zbemt.gui.app import MainWindow

    rec = Recorder(destination, app)
    window = MainWindow()
    window.show()
    _settle(app)

    # Empty/unused state: every main page and every Tool page at the small
    # laptop viewport, plus the launcher itself.
    _capture_main_tabs(
        rec, window,
        state_name="empty",
        sizes=(("laptop", 1366, 700),),
        strict_sizes={"laptop"},
    )
    _capture_launcher(rec, window, "empty")
    _capture_tools(
        rec, window,
        state_name="empty",
        sizes=(("laptop", 1366, 700),),
    )

    # Loaded rotor: full main matrix and every internal Tool workflow page.
    window.state.set_project(api.open_project(str(ROTOR_PROJECT)))
    _capture_main_tabs(
        rec, window,
        state_name="rotor-loaded",
        sizes=MAIN_SIZES,
        strict_sizes={"desktop", "laptop", "minimum"},
    )
    _capture_launcher(rec, window, "rotor-loaded")
    _capture_tools(rec, window, state_name="rotor-loaded", sizes=TOOL_SIZES)

    # Loaded propeller: all seven main screens in the same viewport matrix.
    window.state.set_project(api.open_project(str(PROPELLER_PROJECT)))
    _capture_main_tabs(
        rec, window,
        state_name="propeller-loaded",
        sizes=MAIN_SIZES,
        strict_sizes={"desktop", "laptop", "minimum"},
    )

    # Populated states are not mocked results: these calls use the same real
    # GUI worker path as a user pressing Run Case / Run Batch.
    _exercise_real_engineering_flow(rec, window)

    window.hide()
    for tool in (
        window.geometry_designer,
        window.transient_window,
        window.optimizer_window,
        window.stability_window,
        window.flow_bar._tools_launcher,
    ):
        tool.hide()
    _settle(app)

    manifest = rec.write_manifest()
    print(f"\n{len(rec.records)} screenshots written to {destination}")
    print(f"manifest: {manifest}")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    generate(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
