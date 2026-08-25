"""Implement the Transient Simulation window (SC-12).

The window prescribes a trajectory of flight conditions in time, samples
it onto a uniform grid and marches the unsteady Pitt-Peters inflow
through ``api.run_maneuver``. Page 1 edits the trajectory; page 2 runs
the march and shows the time history. The march itself runs off the main
thread through `ManeuverWorker` (PR-11).
"""

from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QPushButton,
    QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QTextEdit, QTabWidget, QProgressBar,
    QMessageBox, QHeaderView, QInputDialog, QFileDialog,
)

from ..common import AppState, CanvasHost, show_error
from ..workers import ManeuverWorker, launch_worker
from ... import api
from ...models import ManeuverDefinition, ManeuverPoint
from ...viz import plots


def _save_dialog(parent, default_name: str, kind: str = "csv") -> str:
    if kind == "html":
        path, _f = QFileDialog.getSaveFileName(
            parent, "Save report", default_name,
            "HTML report (*.html)")
    else:
        path, _f = QFileDialog.getSaveFileName(
            parent, "Save CSV", default_name,
            "Comma-separated (*.csv)")
    return path


class TransientWindow(QWidget):
    """Two-page tool: Trajectory, then Run and results."""

    _POINT_COLUMNS = ["t [s]", "mu", "V [m/s]",
                      "Collective [deg]", "Cyclic c [deg]",
                      "Cyclic s [deg]", "RPM"]
    #: Engine key per editable column of the point table.
    _POINT_FIELDS = ["t_s", "mu_x", "Vz", "collective_deg",
                      "cyclic_c_deg", "cyclic_s_deg", "rpm"]

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("Transient Simulation")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(1150, 760)

        self._worker = None
        self._thread = None
        self._run_started_at = None
        self._history = None
        self._maps_list = None

        tabs = QTabWidget(self)
        tabs.addTab(self._build_trajectory_page(), "Trajectory")
        tabs.addTab(self._build_run_page(), "Run and results")
        outer = QVBoxLayout(self)
        outer.addWidget(tabs)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(400)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self.state.project_changed.connect(self._refresh_from_project)
        self.state.geometry_changed.connect(self._refresh_gating)
        self.state.airfoil_changed.connect(self._refresh_gating)
        self._refresh_from_project()

    # ------------------------------------------------------------------
    # Page 1: Trajectory
    # ------------------------------------------------------------------
    def _build_trajectory_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        left = QVBoxLayout()
        list_box = QGroupBox("Maneuvers stored in this project")
        list_form = QFormLayout(list_box)
        self.maneuver_combo = QComboBox()
        self.maneuver_combo.setToolTip(
            '"maneuver" — the maneuvers persisted with this project in '
            'inputs/maneuvers.bemt. Selecting one loads its trajectory '
            'into the editor.')
        self.maneuver_combo.currentIndexChanged.connect(
            self._on_maneuver_selected)
        list_form.addRow(self.maneuver_combo)
        btn_row = QHBoxLayout()
        for text, handler in (("New", self._new_maneuver),
                              ("Duplicate", self._duplicate_maneuver),
                              ("Rename", self._rename_maneuver),
                              ("Delete", self._delete_maneuver)):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            btn_row.addWidget(btn)
        btn_row.addStretch(1)
        list_form.addRow(btn_row)
        left.addWidget(list_box)

        points_box = QGroupBox("Trajectory points")
        points_layout = QVBoxLayout(points_box)
        self.points_table = QTableWidget(0, len(self._POINT_COLUMNS))
        self.points_table.setHorizontalHeaderLabels(self._POINT_COLUMNS)
        self.points_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.points_table.itemChanged.connect(self._on_point_edited)
        points_layout.addWidget(self.points_table)
        pts_btns = QHBoxLayout()
        btn_add = QPushButton("Add point")
        btn_add.setToolTip("Appends a point one interval after the last one.")
        btn_add.clicked.connect(self._add_point)
        pts_btns.addWidget(btn_add)
        btn_rm = QPushButton("Remove selected")
        btn_rm.clicked.connect(self._remove_selected_point)
        pts_btns.addWidget(btn_rm)
        pts_btns.addStretch(1)
        points_layout.addLayout(pts_btns)

        build_box = QGroupBox("Build from two saved cases")
        build_form = QFormLayout(build_box)
        self.build_case_a = QComboBox()
        self.build_case_b = QComboBox()
        for combo, tip in ((self.build_case_a,
                            "Start condition of the ramp."),
                           (self.build_case_b,
                            "End condition of the ramp.")):
            combo.setToolTip(tip)
        self.build_duration = QDoubleSpinBox()
        self.build_duration.setRange(0.1, 60.0)
        self.build_duration.setValue(4.0)
        self.build_duration.setSingleStep(0.5)
        self.build_duration.setToolTip(
            '"build_duration" — seconds of transition between the two '
            "saved cases. A short hold at each end keeps the boundary "
            "conditions visible in the results.")
        build_form.addRow("From case:", self.build_case_a)
        build_form.addRow("To case:", self.build_case_b)
        build_form.addRow("Duration [s]:", self.build_duration)
        btn_build = QPushButton("Build ramp")
        btn_build.setToolTip(
            "Fills the trajectory with a hold - ramp - hold between the "
            "two saved cases.")
        btn_build.clicked.connect(self._build_ramp)
        build_form.addRow(btn_build)
        left.addWidget(points_box)
        left.addWidget(build_box)
        layout.addLayout(left, 0)

        right = QVBoxLayout()
        settings_box = QGroupBox("Sampling and march")
        form = QFormLayout(settings_box)
        self.interpolation_combo = QComboBox()
        self.interpolation_combo.addItem("Linear", "linear")
        self.interpolation_combo.addItem("Hold", "hold")
        self.interpolation_combo.setToolTip(
            '"interpolation" — how sample values follow the trajectory '
            "between points: linear blend or zero-order hold.")
        form.addRow("Interpolation:", self.interpolation_combo)
        self.dt_spin = QDoubleSpinBox()
        self.dt_spin.setRange(0.001, 5.0)
        self.dt_spin.setDecimals(3)
        self.dt_spin.setValue(0.05)
        self.dt_spin.setSingleStep(0.01)
        self.dt_spin.setToolTip(
            '"dt_s" — output sample interval in seconds. Every sample is '
            "one row of the time history.")
        form.addRow("Sample interval [s]:", self.dt_spin)
        self.substeps_spin = QSpinBox()
        self.substeps_spin.setRange(1, 200)
        self.substeps_spin.setValue(8)
        self.substeps_spin.setToolTip(
            '"substeps_per_step" — inflow sub-steps inside one sample. '
            "More sub-steps refine the march without extra table rows.")
        form.addRow("Sub-steps per sample:", self.substeps_spin)
        self.initial_state_combo = QComboBox()
        self.initial_state_combo.addItem("Equilibrium", "equilibrium")
        self.initial_state_combo.addItem("Zero", "zero")
        self.initial_state_combo.setToolTip(
            '"initial_state" — Equilibrium solves the steady inflow at the '
            "first sample, so no start-up transient appears. Zero starts "
            "the states from zero and shows the transient decay.")
        form.addRow("Initial state:", self.initial_state_combo)
        self.march_stall_check = QCheckBox("March dynamic stall")
        self.march_stall_check.setToolTip(
            '"march_dynamic_stall" — threads the Øye separation state from '
            "sample to sample instead of restarting it. Needs dynamic "
            "stall enabled on the Airfoil tab.")
        form.addRow(self.march_stall_check)
        self.march_flap_check = QCheckBox("March flapping (quasi-steady)")
        self.march_flap_check.setToolTip(
            '"march_flapping" — solves the periodic flap response at every '
            "sample and feeds it into the loads. Quasi-steady inside each "
            "sample: not a flap transient.")
        form.addRow(self.march_flap_check)
        right.addWidget(settings_box)

        cost_box = QGroupBox("Cost estimate")
        cost_layout = QVBoxLayout(cost_box)
        self.cost_label = QLabel("-")
        self.cost_label.setWordWrap(True)
        self.cost_label.setToolTip(
            "Solver-call count stated as numbers: samples times sub-steps "
            "per sample.")
        cost_layout.addWidget(self.cost_label)
        right.addWidget(cost_box)

        valid_box = QGroupBox("Validation")
        valid_layout = QVBoxLayout(valid_box)
        self.validation_panel = QTextEdit()
        self.validation_panel.setReadOnly(True)
        self.validation_panel.setToolTip(
            "Static findings for the current trajectory, in the same style "
            "as the Config tab.")
        valid_layout.addWidget(self.validation_panel)
        right.addWidget(valid_box, 1)

        preview_box = QGroupBox("Trajectory preview")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_canvas = CanvasHost()
        preview_layout.addWidget(self.preview_canvas)
        right.addWidget(preview_box, 1)
        layout.addLayout(right, 1)

        # wiring
        for w in (self.interpolation_combo, self.initial_state_combo):
            w.currentIndexChanged.connect(self._apply_settings)
        for w in (self.dt_spin, self.substeps_spin):
            w.valueChanged.connect(self._apply_settings)
        self.march_stall_check.toggled.connect(self._apply_settings)
        self.march_flap_check.toggled.connect(self._apply_settings)
        return page

    # ------------------------------------------------------------------
    # Page 2: Run and results
    # ------------------------------------------------------------------
    def _build_run_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        run_row = QHBoxLayout()
        self.btn_run = QPushButton("Run maneuver")
        self.btn_run.clicked.connect(self._run)
        run_row.addWidget(self.btn_run)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel)
        run_row.addWidget(self.btn_cancel)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        run_row.addWidget(self.progress, 1)
        self.elapsed_label = QLabel("")
        run_row.addWidget(self.elapsed_label)
        layout.addLayout(run_row)

        history_box = QGroupBox("Time history")
        hist_layout = QVBoxLayout(history_box)
        self.history_table = QTableWidget(0, 0)
        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setToolTip(
            "One row per sample: time, loads, the three inflow states and "
            "how much time the march actually integrated.")
        hist_layout.addWidget(self.history_table)
        layout.addWidget(history_box, 2)

        plots_row = QHBoxLayout()
        self.plot_canvas = CanvasHost()
        plots_row.addWidget(self.plot_canvas, 2)
        disk_box = QGroupBox("Disk map at sample")
        disk_layout = QVBoxLayout(disk_box)
        self.disk_slider = QSpinBox()
        self.disk_slider.setRange(0, 0)
        self.disk_slider.setToolTip("Sample index whose disk map is drawn.")
        self.disk_slider.valueChanged.connect(self._refresh_disk_map)
        disk_layout.addWidget(self.disk_slider)
        self.disk_canvas = CanvasHost()
        disk_layout.addWidget(self.disk_canvas, 1)
        plots_row.addWidget(disk_box, 1)
        layout.addLayout(plots_row, 3)

        export_row = QHBoxLayout()
        btn_csv = QPushButton("Export CSV")
        btn_csv.setToolTip("Writes the time-history table to a CSV file.")
        btn_csv.clicked.connect(self._export_csv)
        export_row.addWidget(btn_csv)
        btn_report = QPushButton("Export report")
        btn_report.setToolTip(
            "Writes the self-contained HTML report of this maneuver "
            "(RP-1: same implementation as the CLI).")
        btn_report.clicked.connect(self._export_report)
        export_row.addWidget(btn_report)
        export_row.addStretch(1)
        layout.addLayout(export_row)
        return page

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------
    def _refresh_from_project(self):
        self.maneuver_combo.blockSignals(True)
        self.maneuver_combo.clear()
        project = self.state.project
        if project:
            for m in project.maneuvers:
                self.maneuver_combo.addItem(m.name)
        self.maneuver_combo.blockSignals(False)
        self._refresh_saved_cases()
        self._load_selected_definition()
        self._refresh_gating()

    def _refresh_saved_cases(self):
        for combo in (self.build_case_a, self.build_case_b):
            combo.blockSignals(True)
            combo.clear()
            project = self.state.project
            if project:
                for case in project.saved_cases:
                    combo.addItem(case.name)
            combo.blockSignals(False)

    def _refresh_gating(self):
        project = self.state.project
        airfoil = getattr(project, "airfoil", None)
        stall_ok = bool(getattr(airfoil, "use_dynamic_stall", False))
        self.march_stall_check.setEnabled(stall_ok)
        if not stall_ok:
            self.march_stall_check.setChecked(False)
        dynamics = getattr(getattr(project, "geometry", None), "dynamics",
                            None)
        flap_ok = bool(dynamics and dynamics.flap_model != "rigid")
        self.march_flap_check.setEnabled(flap_ok)
        if not flap_ok:
            self.march_flap_check.setChecked(False)

    def _current_definition(self) -> ManeuverDefinition:
        """Builds the definition FROM THE FORM, so validation and the
        preview always reflect what is on screen."""

        def _num(row: int, field: str) -> float:
            item = self.points_table.item(row,
                                           self._POINT_FIELDS.index(field))
            try:
                value = float(item.text()) if item else float("nan")
            except (TypeError, ValueError):
                value = float("nan")
            if field == "rpm" and value <= 0.0:
                return None
            return value

        points = []
        for row in range(self.points_table.rowCount()):
            values = {f: _num(row, f) for f in self._POINT_FIELDS}
            if any(v != v for v in values.values()):
                continue   # skip half-typed rows
            points.append(ManeuverPoint(**values))
        return ManeuverDefinition(
            name=(self.maneuver_combo.currentText()
                  or "maneuver 1"),
            points=points,
            interpolation=self.interpolation_combo.currentData(),
            dt_s=self.dt_spin.value(),
            substeps_per_step=self.substeps_spin.value(),
            initial_state=self.initial_state_combo.currentData(),
            march_dynamic_stall=self.march_stall_check.isChecked(),
            march_flapping=self.march_flap_check.isChecked(),
        )

    def _fill_editor(self, definition: ManeuverDefinition):
        self.points_table.blockSignals(True)
        self.points_table.setRowCount(len(definition.points))
        for r, point in enumerate(definition.points):
            for c, field in enumerate(self._POINT_FIELDS):
                value = getattr(point, field)
                text = "" if value is None else f"{float(value):g}"
                self.points_table.setItem(r, c, QTableWidgetItem(text))
        self.points_table.blockSignals(False)
        self.interpolation_combo.setCurrentIndex(
            self.interpolation_combo.findData(definition.interpolation))
        self.dt_spin.setValue(float(definition.dt_s))
        self.substeps_spin.setValue(int(definition.substeps_per_step))
        self.initial_state_combo.setCurrentIndex(
            self.initial_state_combo.findData(definition.initial_state))
        self.march_stall_check.setChecked(bool(definition.march_dynamic_stall))
        self.march_flap_check.setChecked(bool(definition.march_flapping))
        self._on_points_changed()

    def _store_into_project(self, definition: ManeuverDefinition):
        """Writes the edited definition back into the project's list and
        marks the project unsaved (TB-3); nothing touches disk here."""
        project = self.state.project
        if project is None:
            return
        idx = self.maneuver_combo.currentIndex()
        while len(project.maneuvers) <= idx:
            project.maneuvers.append(ManeuverDefinition())
        project.maneuvers[idx] = definition
        self.state.notify_geometry()   # marks dependent tabs stale

    # ------------------------------------------------------------------
    # Maneuver list handlers
    # ------------------------------------------------------------------
    def _on_maneuver_selected(self, _index: int):
        definition = self._selected_persisted()
        if definition is not None:
            self._fill_editor(definition)

    def _selected_persisted(self):
        project = self.state.project
        idx = self.maneuver_combo.currentIndex()
        if project is None or idx < 0 or idx >= len(project.maneuvers):
            return None
        return project.maneuvers[idx]

    def _new_maneuver(self):
        project = self.state.project
        if project is None:
            return
        name, ok = QInputDialog.getText(self, "New maneuver",
                                         "Name:")
        if not ok or not name.strip():
            return
        definition = ManeuverDefinition(name=name.strip(), points=[
            ManeuverPoint(t_s=0.0, mu_x=0.0, Vz=0.0, collective_deg=8.0,
                           rpm=self._first_saved_rpm() or 600.0),
            ManeuverPoint(t_s=2.0, mu_x=0.1, Vz=0.0, collective_deg=8.0,
                           rpm=self._first_saved_rpm() or 600.0),
        ])
        project.maneuvers.append(definition)
        self.maneuver_combo.blockSignals(True)
        self.maneuver_combo.addItem(definition.name)
        self.maneuver_combo.setCurrentIndex(
            self.maneuver_combo.count() - 1)
        self.maneuver_combo.blockSignals(False)
        self._fill_editor(definition)
        self.state.notify_geometry()

    def _duplicate_maneuver(self):
        source = self._current_definition()
        new_name, ok = QInputDialog.getText(self, "Duplicate maneuver",
                                             "Name:", text=source.name + " copy")
        if not ok or not new_name.strip():
            return
        project = self.state.project
        if project is None:
            return
        copy = ManeuverDefinition(name=new_name.strip(),
                                   points=list(source.points),
                                   interpolation=source.interpolation,
                                   dt_s=source.dt_s,
                                   substeps_per_step=source.substeps_per_step,
                                   initial_state=source.initial_state,
                                   march_dynamic_stall=source.march_dynamic_stall,
                                   march_flapping=source.march_flapping)
        project.maneuvers.append(copy)
        self.maneuver_combo.blockSignals(True)
        self.maneuver_combo.addItem(copy.name)
        self.maneuver_combo.setCurrentIndex(self.maneuver_combo.count() - 1)
        self.maneuver_combo.blockSignals(False)
        self.state.notify_geometry()

    def _rename_maneuver(self):
        old = self._selected_persisted()
        if old is None:
            return
        new_name, ok = QInputDialog.getText(self, "Rename maneuver",
                                             "Name:", text=old.name)
        if not ok or not new_name.strip():
            return
        old.name = new_name.strip()
        idx = self.maneuver_combo.currentIndex()
        self.maneuver_combo.setItemText(idx, old.name)
        self.state.notify_geometry()

    def _delete_maneuver(self):
        project = self.state.project
        idx = self.maneuver_combo.currentIndex()
        if project is None or idx < 0 or idx >= len(project.maneuvers):
            return
        confirm = QMessageBox.question(
            self, "Delete maneuver",
            f"Delete maneuver {project.maneuvers[idx].name!r} from this "
            "project?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        del project.maneuvers[idx]
        self.maneuver_combo.blockSignals(True)
        self.maneuver_combo.removeItem(idx)
        self.maneuver_combo.blockSignals(False)
        self.state.notify_geometry()
        self._load_selected_definition()

    # ------------------------------------------------------------------
    # Point-table handlers
    # ------------------------------------------------------------------
    def _load_selected_definition(self):
        definition = self._selected_persisted()
        if definition is None:
            self.points_table.setRowCount(0)
            self._on_points_changed()
            return
        self._fill_editor(definition)

    def _add_point(self):
        row = self.points_table.rowCount()
        last_t = 0.0
        if row:
            try:
                last_t = float(self.points_table.item(row - 1, 0).text())
            except (TypeError, ValueError, AttributeError):
                last_t = 0.0
        self.points_table.insertRow(row)
        defaults = [f"{last_t + 0.5:g}", "0.0", "0.0", "8.0", "0.0",
                    "0.0", self._first_saved_rpm() or "600"]
        for c, text in enumerate(defaults):
            self.points_table.setItem(row, c, QTableWidgetItem(text))

    def _remove_selected_point(self):
        rows = sorted({i.row() for i in self.points_table.selectedIndexes()},
                       reverse=True)
        for r in rows:
            self.points_table.removeRow(r)
        self._on_points_changed()

    def _on_point_edited(self, *_args):
        self.state_notify()
        self._schedule_preview_refresh()

    def state_notify(self):
        """Stores the on-screen trajectory into the project (TB-3)."""
        project = self.state.project
        if project is None:
            return
        idx = self.maneuver_combo.currentIndex()
        if idx < 0 or idx >= len(project.maneuvers):
            return
        project.maneuvers[idx] = self._current_definition()

    def _apply_settings(self, *_args):
        self.state_notify()
        self._schedule_preview_refresh()
        self._update_cost_estimate()

    def _first_saved_rpm(self):
        project = self.state.project
        if project and project.saved_cases and project.saved_cases[0].rpm:
            return f"{float(project.saved_cases[0].rpm):g}"
        return None

    # ------------------------------------------------------------------
    # Ramp builder
    # ------------------------------------------------------------------
    def _build_ramp(self):
        project = self.state.project
        if project is None or not project.saved_cases:
            QMessageBox.information(
                self, "No saved cases",
                "Save at least two cases on the Run Case tab first.")
            return
        i_a = max(self.build_case_a.currentIndex(), 0)
        i_b = max(self.build_case_b.currentIndex(), 0)
        if i_a == i_b:
            QMessageBox.information(
                self, "Same case",
                "Pick two different saved cases to build a ramp.")
            return
        ca = project.saved_cases[i_a]
        cb = project.saved_cases[i_b]
        duration = self.build_duration.value()
        hold = min(0.5, duration / 4.0)
        rpm_a = ca.rpm if ca.rpm is not None else cb.rpm
        points = [
            ManeuverPoint(t_s=0.0, mu_x=ca.mu_x, Vz=ca.Vz,
                           collective_deg=ca.collective_deg,
                           cyclic_c_deg=getattr(ca, "cyclic_c_deg", 0.0),
                           cyclic_s_deg=getattr(ca, "cyclic_s_deg", 0.0),
                           rpm=rpm_a),
            ManeuverPoint(t_s=duration + hold, mu_x=cb.mu_x, Vz=cb.Vz,
                           collective_deg=cb.collective_deg,
                           cyclic_c_deg=getattr(cb, "cyclic_c_deg", 0.0),
                           cyclic_s_deg=getattr(cb, "cyclic_s_deg", 0.0),
                           rpm=cb.rpm if cb.rpm is not None else rpm_a),
        ]
        self._fill_editor(ManeuverDefinition(name="ramp", points=points,
                                              dt_s=self.dt_spin.value()))

    # ------------------------------------------------------------------
    # Preview / cost / validation
    # ------------------------------------------------------------------
    def _schedule_preview_refresh(self, *_args):
        self._preview_timer.start()

    def _on_points_changed(self):
        self.state_notify()
        self._schedule_preview_refresh()
        self._update_cost_estimate()
        self._update_validation_panel()

    def _update_cost_estimate(self):
        definition = self._current_definition()
        try:
            from zbemt.studies import _maneuver_samples
            n_samples = len(_maneuver_samples(definition))
        except Exception:
            n_samples = 0
        substeps = max(int(definition.substeps_per_step), 1)
        calls = n_samples * substeps
        self.cost_label.setText(
            f"{n_samples} samples x {substeps} sub-steps = "
            f"{calls} solver calls.")

    def _update_validation_panel(self):
        from zbemt.validation import validate_maneuver
        definition = self._current_definition()
        cfg = dict(self.state.project.config) if self.state.project else {}
        issues = validate_maneuver(definition, cfg)
        self.validation_panel.setPlainText(
            "\n".join(str(i) for i in issues) if issues
            else "No findings.")

    def _refresh_preview(self):
        from zbemt.studies import _maneuver_samples
        try:
            definition = self._current_definition()
            samples = _maneuver_samples(definition)
        except Exception as exc:
            self.preview_canvas.show_message(f"Cannot sample: {exc}")
            return
        if not samples:
            self.preview_canvas.show_message("Add at least two points.")
            return
        t = [s.t_s for s in samples]
        canvas = self.preview_canvas.use_simple()
        canvas.clear()
        ax = canvas.ax
        ax.plot(t, [s.mu_x for s in samples], label="mu (in-plane)",
                 color="tab:blue")
        ax.plot(t, [s.Vz for s in samples], label="V axial [m/s]",
                 color="tab:cyan")
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Flow components")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, loc="best")
        ax2 = ax.twiny()
        ax2.set_visible(False)
        canvas.draw()

    # ------------------------------------------------------------------
    # Run page
    # ------------------------------------------------------------------
    def _run(self):
        project = self.state.project
        if project is None:
            return
        definition = self._current_definition()
        self.btn_run.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._run_started_at = time.time()
        self._worker = ManeuverWorker(project, definition)
        self._thread = launch_worker(self._worker)
        self._worker.sample_finished.connect(self._on_sample_finished)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(lambda msg: show_error(
            self, "Error running maneuver", ValueError(msg)))

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    def _on_sample_finished(self, done: int, total: int, _row):
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        elapsed = time.time() - (self._run_started_at or time.time())
        self.elapsed_label.setText(f"{elapsed:.1f}s - {done}/{total}")

    def _on_finished(self, payload):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.progress.setVisible(False)
        if payload is None:      # cancelled
            return
        history, maps_list = payload
        self._history = history
        self._maps_list = maps_list
        columns = ["t", "CT", "CQ", "CP", "nu0", "nu_s", "nu_c",
                    "collective_deg", "marched_interval_s", "substeps"]
        columns = [c for c in columns if c in history.columns]
        self.history_table.setColumnCount(len(columns))
        self.history_table.setHorizontalHeaderLabels(columns)
        self.history_table.setRowCount(len(history))
        for r in range(len(history)):
            for c, col in enumerate(columns):
                value = history.iloc[r][col]
                self.history_table.setItem(
                    r, c, QTableWidgetItem(f"{float(value):.6g}"))
        self.disk_slider.setRange(0, max(len(maps_list) - 1, 0))
        self.disk_slider.setValue(0)
        self._refresh_overview_plot()

    def _refresh_overview_plot(self):
        if self._history is None:
            return
        fig = plots.plot_maneuver_history(self._history)
        if fig is not None:
            self.plot_canvas.show_figure(fig)

    def _refresh_disk_map(self, index: int):
        if not self._maps_list or not (0 <= index < len(self._maps_list)):
            return
        maps = self._maps_list[index]
        canvas = self.disk_canvas.use_simple()
        canvas.clear()
        try:
            plots.plot_disk_map(maps, field="lambda_i", ax=canvas.ax,
                                 compact=True)
        except Exception as exc:
            canvas.ax.text(0.5, 0.5, f"Cannot draw: {exc}",
                            ha="center", va="center",
                            transform=canvas.ax.transAxes)
        canvas.draw()

    def _export_csv(self):
        if self._history is None:
            QMessageBox.information(self, "Nothing to export",
                                     "Run the maneuver first.")
            return
        path, _filter = _save_dialog(self, "maneuver_history.csv")
        if not path:
            return
        api.export_maneuver_csv(self._history, path)
        QMessageBox.information(self, "Exported", f"File written:\n{path}")

    def _export_report(self):
        if self._history is None or not self._maps_list:
            QMessageBox.information(self, "Nothing to export",
                                     "Run the maneuver first.")
            return
        path, _filter = _save_dialog(self, "maneuver_report.html", "html")
        if not path:
            return
        from zbemt.models import Results
        results = [Results(summary=row.to_dict(), maps=mp,
                            condition_name=f"t={row['t']:.2f}s")
                   for (_, row), mp in zip(self._history.iterrows(),
                                            self._maps_list)]
        api.generate_report(results, path, project=self.state.project)
        QMessageBox.information(self, "Exported", f"Report written:\n{path}")
