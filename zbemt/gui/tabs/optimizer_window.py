"""Implement the Design Optimization window (SC-13).

The window edits a persisted optimization study
(``inputs/optimizations.bemt``) and runs it as an OUTER loop over the
engine: every evaluation regenerates the geometry and solves one flight
condition through ``api.optimize_design_multi``. Page 1 edits the study;
page 2 runs the search and shows the Pareto front. The search itself
runs off the main thread through `OptimizeMultiWorker` (PR-11). The
single-objective path stays on SC-8 (`optimize_design`, CLI/library);
this window is the multi-objective one.
"""

from __future__ import annotations

import time
from dataclasses import replace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QGroupBox,
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QTabWidget, QProgressBar, QMessageBox,
    QHeaderView, QInputDialog, QFileDialog,
)

from ..common import AppState, CanvasHost, show_error, show_all_options_in
from ..workers import OptimizeMultiWorker, launch_worker
from ... import api
from ...models import (
    ConstraintDef, DesignVariable, FlightCondition, ObjectiveDef,
    OptimizationDefinition,
)
from ...viz import plots

_GEOMETRY_PARAM_TIP = (
    "Planform parameters: root_chord_norm, tip_chord_norm, twist_root_deg, "
    "twist_tip_deg, max_chord_norm. Direct fields: n_blades, radius_m, "
    "root_cutout_norm.")

#: Seeds for the editable objective-key boxes. Any summary key types in;
#: these are the ones optimization studies usually drive.
_COMMON_OBJECTIVE_KEYS = ("FM", "CT", "CP", "CQ", "eta_prop", "CY",
                           "Power")


def _save_dialog(parent, default_name: str, kind: str = "csv") -> str:
    if kind == "html":
        path, _f = QFileDialog.getSaveFileName(
            parent, "Save report", default_name, "HTML report (*.html)")
    else:
        path, _f = QFileDialog.getSaveFileName(
            parent, "Save CSV", default_name, "Comma-separated (*.csv)")
    return path


class OptimizerWindow(QWidget):
    """Two-page tool: Study definition, then Run and results."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("Design Optimization")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(1100, 720)

        self._worker = None
        self._thread = None
        self._run_started_at = None
        self._outcome = None
        self._last_definition = None

        tabs = QTabWidget(self)
        tabs.addTab(self._build_definition_page(), "Study")
        tabs.addTab(self._build_run_page(), "Run and results")
        outer = QVBoxLayout(self)
        outer.addWidget(tabs)
        show_all_options_in(self)

        self.state.project_changed.connect(self._refresh_from_project)
        self.state.geometry_changed.connect(lambda: self.state_notify())
        self._refresh_from_project()

    # ------------------------------------------------------------------
    # Page 1: Study
    # ------------------------------------------------------------------
    def _build_definition_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        left = QVBoxLayout()
        list_box = QGroupBox("Optimization studies stored in this project")
        list_form = QFormLayout(list_box)
        self.study_combo = QComboBox()
        self.study_combo.setToolTip(
            '"optimization" — the studies persisted with this project in '
            'inputs/optimizations.bemt. Selecting one loads it into the '
            "editor.")
        self.study_combo.currentIndexChanged.connect(self._on_study_selected)
        list_form.addRow(self.study_combo)
        btn_row = QHBoxLayout()
        for text, handler in (("New", self._new_study),
                              ("Duplicate", self._duplicate_study),
                              ("Rename", self._rename_study),
                              ("Delete", self._delete_study)):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            btn_row.addWidget(btn)
        btn_row.addStretch(1)
        list_form.addRow(btn_row)
        left.addWidget(list_box)

        obj_box = QGroupBox("Objectives")
        obj_form = QFormLayout(obj_box)
        self.obj_keys = []
        self.obj_kinds = []
        for i in (1, 2):
            key_combo = QComboBox()
            key_combo.setEditable(True)
            for key in _COMMON_OBJECTIVE_KEYS:
                key_combo.addItem(key)
            kind_combo = QComboBox()
            kind_combo.addItem("Maximize", "maximize")
            kind_combo.addItem("Minimize", "minimize")
            tip = ('"objectives" — any quantity of the results summary '
                   "(for example FM, CT, CP). The box suggests the usual "
                   "ones; type any other summary key.")
            if i == 2:
                tip = ("Second objective. An EMPTY box runs a "
                       "single-objective study; a filled one switches to "
                       "the Pareto front.")
            key_combo.setToolTip(tip)
            kind_combo.setToolTip('"kind" — maximize or minimize.')
            row = QHBoxLayout()
            row.addWidget(key_combo, 2)
            row.addWidget(kind_combo, 1)
            wrap = QWidget()
            wrap.setLayout(row)
            obj_form.addRow(f"Objective {i}:", wrap)
            self.obj_keys.append(key_combo)
            self.obj_kinds.append(kind_combo)
        left.addWidget(obj_box)

        cons_box = QGroupBox("Constraints")
        cons_layout = QVBoxLayout(cons_box)
        self.cons_table = QTableWidget(0, 3)
        self.cons_table.setHorizontalHeaderLabels(["Summary key",
                                                    "Operator", "Value"])
        self.cons_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.cons_table.setToolTip(
            '"constraints" — the search discards designs that break them. '
            'Each row reads one summary key and requires >=, <= or == a '
            "value.")
        cons_layout.addWidget(self.cons_table)
        cons_btns = QHBoxLayout()
        btn_add_c = QPushButton("Add constraint")
        btn_add_c.clicked.connect(self._add_constraint)
        cons_btns.addWidget(btn_add_c)
        btn_rm_c = QPushButton("Remove selected")
        btn_rm_c.clicked.connect(self._remove_selected_constraint)
        cons_btns.addWidget(btn_rm_c)
        cons_btns.addStretch(1)
        cons_layout.addLayout(cons_btns)
        left.addWidget(cons_box, 1)
        layout.addLayout(left, 0)

        right = QVBoxLayout()
        var_box = QGroupBox("Design variables")
        var_layout = QVBoxLayout(var_box)
        self.var_table = QTableWidget(0, 3)
        self.var_table.setHorizontalHeaderLabels(["Parameter", "Lower",
                                                   "Upper"])
        self.var_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.var_table.setToolTip(_GEOMETRY_PARAM_TIP)
        var_layout.addWidget(self.var_table)
        var_btns = QHBoxLayout()
        btn_add_v = QPushButton("Add variable")
        btn_add_v.clicked.connect(self._add_variable)
        var_btns.addWidget(btn_add_v)
        btn_rm_v = QPushButton("Remove selected")
        btn_rm_v.clicked.connect(self._remove_selected_variable)
        var_btns.addWidget(btn_rm_v)
        var_btns.addStretch(1)
        var_layout.addLayout(var_btns)
        right.addWidget(var_box, 1)

        search_box = QGroupBox("Search settings")
        grid = QGridLayout(search_box)
        self.condition_combo = QComboBox()
        self.condition_combo.setToolTip(
            '"condition" — the saved case whose flight state every design '
            "is solved at. It must carry an RPM: the solver "
            "adimensionalizes by ΩR.")
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItem("NSGA-II (Pareto front)", "nsga2")
        self.algorithm_combo.addItem("Differential evolution (global)",
                                      "de")
        self.algorithm_combo.setToolTip(
            '"algorithm" — NSGA-II evolves the whole front; differential '
            "evolution drives the FIRST objective only (single-result "
            "search).")
        self.population_spin = QSpinBox()
        self.population_spin.setRange(4, 400)
        self.population_spin.setValue(40)
        self.population_spin.setToolTip(
            '"population" — designs alive per generation. Every generation '
            "costs this many solver calls.")
        self.generations_spin = QSpinBox()
        self.generations_spin.setRange(1, 500)
        self.generations_spin.setValue(25)
        self.generations_spin.setToolTip(
            '"generations" — how many rounds of selection and variation '
            "run after the first evaluation sweep.")
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(0)
        self.seed_spin.setToolTip(
            '"seed" — the same seed reproduces the same search '
            "deterministically.")
        self.crossover_spin = QDoubleSpinBox()
        self.crossover_spin.setRange(1.0, 40.0)
        self.crossover_spin.setDecimals(1)
        self.crossover_spin.setValue(15.0)
        self.crossover_spin.setToolTip(
            '"crossover_eta" — η_c, the SBX distribution index. Larger '
            "keeps children near their parents.")
        self.mutation_spin = QDoubleSpinBox()
        self.mutation_spin.setRange(1.0, 100.0)
        self.mutation_spin.setDecimals(1)
        self.mutation_spin.setValue(20.0)
        self.mutation_spin.setToolTip(
            '"mutation_eta" — η_m, the polynomial-mutation distribution '
            "index. Larger mutates less violently.")
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.0, 1.0)
        self.rate_spin.setDecimals(3)
        self.rate_spin.setSingleStep(0.05)
        self.rate_spin.setValue(0.0)
        self.rate_spin.setToolTip(
            '"mutation_rate" — 0 means ONE OVER THE VARIABLE COUNT (the '
            "NSGA-II default). Without it the population contracts into a "
            "corner.")
        rows = [
            ("Condition:", self.condition_combo),
            ("Algorithm:", self.algorithm_combo),
            ("Population:", self.population_spin),
            ("Generations:", self.generations_spin),
            ("Seed:", self.seed_spin),
            ("Crossover η_c:", self.crossover_spin),
            ("Mutation η_m:", self.mutation_spin),
            ("Mutation rate:", self.rate_spin),
        ]
        for r, (label, widget) in enumerate(rows):
            grid.addWidget(QLabel(label), r, 0)
            grid.addWidget(widget, r, 1)
        right.addWidget(search_box)

        cost_box = QGroupBox("Cost estimate")
        cost_layout = QVBoxLayout(cost_box)
        self.cost_label = QLabel("-")
        self.cost_label.setWordWrap(True)
        self.cost_label.setToolTip(
            "Solver-call count stated as numbers: one population sweep per "
            "generation, plus the initial one.")
        cost_layout.addWidget(self.cost_label)
        right.addWidget(cost_box)
        layout.addLayout(right, 1)

        for w in (self.population_spin, self.generations_spin,
                  self.seed_spin, self.crossover_spin, self.mutation_spin,
                  self.rate_spin):
            w.valueChanged.connect(self._apply_settings)
        self.algorithm_combo.currentIndexChanged.connect(
            self._apply_settings)
        self.condition_combo.currentIndexChanged.connect(
            self._apply_settings)
        return page

    # ------------------------------------------------------------------
    # Page 2: Run and results
    # ------------------------------------------------------------------
    def _build_run_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        run_row = QHBoxLayout()
        self.btn_run = QPushButton("Run optimization")
        self.btn_run.clicked.connect(self._run)
        run_row.addWidget(self.btn_run)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel)
        run_row.addWidget(self.btn_cancel)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)   # busy: a Pareto search has no total
        run_row.addWidget(self.progress, 1)
        self.elapsed_label = QLabel("")
        run_row.addWidget(self.elapsed_label)
        layout.addLayout(run_row)

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        front_box = QGroupBox("Pareto front")
        front_layout = QVBoxLayout(front_box)
        self.front_table = QTableWidget(0, 0)
        self.front_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.front_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.front_table.setToolTip(
            "One row per non-dominated design: its parameters and its raw "
            "objective values. No row dominates another.")
        front_layout.addWidget(self.front_table)
        layout.addWidget(front_box, 2)

        plot_box = QGroupBox("Trade-off plot")
        plot_layout = QVBoxLayout(plot_box)
        view_row = QHBoxLayout()
        self.view_combo = QComboBox()
        self.view_combo.addItem("Objectives (Pareto)", "pareto")
        self.view_combo.addItem("All quantities (parallel coordinates)",
                                 "parallel")
        self.view_combo.setToolTip(
            "The Pareto view plots the two objectives against each other; "
            "click a front marker to select that design in the table. The "
            "parallel view draws one polyline per front member across every "
            "variable and objective, normalized to each axis.")
        self.view_combo.currentIndexChanged.connect(self._refresh_plot)
        view_row.addWidget(self.view_combo)
        view_row.addStretch(1)
        plot_layout.addLayout(view_row)
        self.plot_canvas = CanvasHost()
        plot_layout.addWidget(self.plot_canvas)
        layout.addWidget(plot_box, 2)

        export_row = QHBoxLayout()
        btn_csv = QPushButton("Export CSV")
        btn_csv.setToolTip("Writes the front table to a CSV file.")
        btn_csv.clicked.connect(self._export_csv)
        export_row.addWidget(btn_csv)
        btn_report = QPushButton("Export report")
        btn_report.setToolTip(
            "Writes the self-contained HTML report: front table, trade-off "
            "plot and planforms of three spread members.")
        btn_report.clicked.connect(self._export_report)
        export_row.addWidget(btn_report)
        self.btn_send_to_designer = QPushButton("Send front to comparison")
        self.btn_send_to_designer.setEnabled(False)
        self.btn_send_to_designer.setToolTip(
            "Appends every Pareto member to the Geometry Designer's "
            "variant table, each labeled with the study name and its "
            "front index.")
        self.btn_send_to_designer.clicked.connect(self._send_front_to_designer)
        export_row.addWidget(self.btn_send_to_designer)
        export_row.addStretch(1)
        layout.addLayout(export_row)
        return page

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------
    def _refresh_from_project(self):
        self.study_combo.blockSignals(True)
        self.study_combo.clear()
        project = self.state.project
        if project:
            for o in project.optimizations:
                self.study_combo.addItem(o.name)
        self.study_combo.blockSignals(False)
        self._refresh_conditions()
        self._load_selected_study()
        self._refresh_gating()

    def _refresh_conditions(self):
        self.condition_combo.blockSignals(True)
        self.condition_combo.clear()
        project = self.state.project
        if project:
            for case in project.saved_cases:
                label = f"{case.name}"
                if case.rpm:
                    label += f" ({float(case.rpm):g} rpm)"
                self.condition_combo.addItem(label)
        self.condition_combo.blockSignals(False)

    def _refresh_gating(self):
        has_project = self.state.project is not None
        self.btn_run.setEnabled(has_project)
        for w in (self.study_combo, self.condition_combo):
            w.setEnabled(has_project)

    def _selected_persisted(self):
        project = self.state.project
        idx = self.study_combo.currentIndex()
        if project is None or idx < 0 or idx >= len(project.optimizations):
            return None
        return project.optimizations[idx]

    def _on_study_selected(self, _index: int):
        definition = self._selected_persisted()
        if definition is not None:
            self._fill_editor(definition)

    def _condition_by_index(self, index: int):
        project = self.state.project
        if project is None or not (0 <= index < len(project.saved_cases)):
            return None
        return replace(project.saved_cases[index])

    def _current_definition(self) -> OptimizationDefinition:
        """Builds the definition FROM THE FORM, so storage and the run
        always reflect what is on screen."""
        objectives = []
        for key_combo, kind_combo in zip(self.obj_keys, self.obj_kinds):
            key = key_combo.currentText().strip()
            if key:
                objectives.append(ObjectiveDef(
                    key=key, kind=kind_combo.currentData()))
        variables = []
        for r in range(self.var_table.rowCount()):
            name_item = self.var_table.item(r, 0)
            if name_item is None or not name_item.text().strip():
                continue   # skip half-typed rows
            lo = self._cell_float(self.var_table.item(r, 1), 0.0)
            hi = self._cell_float(self.var_table.item(r, 2), 1.0)
            variables.append(DesignVariable(param=name_item.text().strip(),
                                             lower=min(lo, hi),
                                             upper=max(lo, hi)))
        constraints = []
        for r in range(self.cons_table.rowCount()):
            key_item = self.cons_table.item(r, 0)
            if key_item is None or not key_item.text().strip():
                continue
            op_widget = self.cons_table.cellWidget(r, 1)
            op = op_widget.currentText() if op_widget else ">="
            constraints.append(ConstraintDef(
                key=key_item.text().strip(), operator=op,
                value=self._cell_float(self.cons_table.item(r, 2), 0.0)))
        algorithm = self.algorithm_combo.currentData() or "nsga2"
        condition = self._condition_by_index(
            max(self.condition_combo.currentIndex(), 0))
        return OptimizationDefinition(
            name=(self.study_combo.currentText() or "optimization 1"),
            objectives=objectives,
            variables=variables,
            constraints=constraints,
            algorithm="nsga2" if not objectives else algorithm,
            condition=condition,
            population=self.population_spin.value(),
            generations=self.generations_spin.value(),
            seed=self.seed_spin.value(),
            crossover_eta=self.crossover_spin.value(),
            mutation_eta=self.mutation_spin.value(),
            mutation_rate=self.rate_spin.value())

    @staticmethod
    def _cell_float(item, default: float) -> float:
        try:
            return float(item.text()) if item else default
        except (TypeError, ValueError):
            return default

    def _fill_editor(self, definition: OptimizationDefinition):
        objectives = list(definition.objectives)
        while len(objectives) < 2:
            objectives.append(ObjectiveDef(key="", kind="maximize"))
        for i, obj in enumerate(objectives[:2]):
            self.obj_keys[i].setCurrentText("" if obj.key == "" else str(obj.key))
            idx = self.obj_kinds[i].findData(obj.kind)
            self.obj_kinds[i].setCurrentIndex(max(idx, 0))
        self.var_table.setRowCount(0)
        for v in definition.variables:
            self._append_variable_row(v.param, v.lower, v.upper)
        self.cons_table.setRowCount(0)
        for c in definition.constraints:
            self._append_constraint_row(c.key, c.operator, c.value)
        self.algorithm_combo.setCurrentIndex(
            self.algorithm_combo.findData(
                definition.algorithm or "nsga2"))
        self.population_spin.setValue(int(definition.population))
        self.generations_spin.setValue(int(definition.generations))
        self.seed_spin.setValue(int(definition.seed))
        self.crossover_spin.setValue(float(definition.crossover_eta))
        self.mutation_spin.setValue(float(definition.mutation_eta))
        self.rate_spin.setValue(float(definition.mutation_rate))
        # condition: match by name against the project's saved cases
        cond_index = -1
        if definition.condition is not None:
            for i, case in enumerate((self.state.project.saved_cases
                                       if self.state.project else [])):
                if case.name == definition.condition.name:
                    cond_index = i
                    break
        if cond_index >= 0:
            self.condition_combo.setCurrentIndex(cond_index)
        self._update_cost_estimate()

    def state_notify(self):
        """Stores the on-screen study into the project (TB-3)."""
        project = self.state.project
        idx = self.study_combo.currentIndex()
        if project is None or idx < 0 or idx >= len(project.optimizations):
            return
        project.optimizations[idx] = self._current_definition()

    def _apply_settings(self, *_args):
        self.state_notify()
        self._update_cost_estimate()
        self._update_search_gating()

    def _update_search_gating(self):
        """PR-2: the SBX/mutation controls are real only under NSGA-II;
        under differential evolution they stay visible but disabled."""
        is_nsga2 = self.algorithm_combo.currentData() != "de"
        for w in (self.crossover_spin, self.mutation_spin, self.rate_spin):
            w.setEnabled(is_nsga2)

    def _update_cost_estimate(self):
        population = self.population_spin.value()
        generations = self.generations_spin.value()
        calls = population * (generations + 1)
        self.cost_label.setText(
            f"{population} designs x {generations + 1} sweeps = about "
            f"{calls} solver calls.")

    # ------------------------------------------------------------------
    # Study list handlers
    # ------------------------------------------------------------------
    def _new_study(self):
        project = self.state.project
        if project is None:
            return
        name, ok = QInputDialog.getText(self, "New optimization study",
                                         "Name:")
        if not ok or not name.strip():
            return
        definition = OptimizationDefinition(
            name=name.strip(),
            objectives=[ObjectiveDef(key="FM", kind="maximize")],
            variables=[DesignVariable(param="tip_chord_norm", lower=0.02,
                                       upper=0.15)],
            algorithm="nsga2",
            condition=self._condition_by_index(0))
        project.optimizations.append(definition)
        self.study_combo.blockSignals(True)
        self.study_combo.addItem(definition.name)
        self.study_combo.setCurrentIndex(self.study_combo.count() - 1)
        self.study_combo.blockSignals(False)
        self._fill_editor(definition)
        self.state.notify_geometry()

    def _duplicate_study(self):
        source = self._current_definition()
        new_name, ok = QInputDialog.getText(
            self, "Duplicate study", "Name:", text=source.name + " copy")
        if not ok or not new_name.strip():
            return
        project = self.state.project
        if project is None:
            return
        copy = replace(source, name=new_name.strip())
        project.optimizations.append(copy)
        self.study_combo.blockSignals(True)
        self.study_combo.addItem(copy.name)
        self.study_combo.setCurrentIndex(self.study_combo.count() - 1)
        self.study_combo.blockSignals(False)
        self.state.notify_geometry()

    def _rename_study(self):
        old = self._selected_persisted()
        if old is None:
            return
        new_name, ok = QInputDialog.getText(self, "Rename study",
                                             "Name:", text=old.name)
        if not ok or not new_name.strip():
            return
        old.name = new_name.strip()
        idx = self.study_combo.currentIndex()
        self.study_combo.setItemText(idx, old.name)
        self.state.notify_geometry()

    def _delete_study(self):
        project = self.state.project
        idx = self.study_combo.currentIndex()
        if project is None or idx < 0 or idx >= len(project.optimizations):
            return
        confirm = QMessageBox.question(
            self, "Delete study",
            f"Delete study {project.optimizations[idx].name!r} from this "
            "project?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        del project.optimizations[idx]
        self.study_combo.blockSignals(True)
        self.study_combo.removeItem(idx)
        self.study_combo.blockSignals(False)
        self.state.notify_geometry()
        self._load_selected_study()

    def _load_selected_study(self):
        definition = self._selected_persisted()
        if definition is None:
            self.var_table.setRowCount(0)
            self.cons_table.setRowCount(0)
            return
        self._fill_editor(definition)

    # ------------------------------------------------------------------
    # Variable/constraint table handlers
    # ------------------------------------------------------------------
    def _append_variable_row(self, param: str = "tip_chord_norm",
                             lower: float = 0.02, upper: float = 0.15):
        r = self.var_table.rowCount()
        self.var_table.insertRow(r)
        self.var_table.setItem(r, 0, QTableWidgetItem(str(param)))
        self.var_table.setItem(r, 1, QTableWidgetItem(f"{float(lower):g}"))
        self.var_table.setItem(r, 2, QTableWidgetItem(f"{float(upper):g}"))

    def _add_variable(self):
        self._append_variable_row()
        self.state_notify()

    def _remove_selected_variable(self):
        rows = sorted({i.row() for i in self.var_table.selectedIndexes()},
                       reverse=True)
        for r in rows:
            self.var_table.removeRow(r)
        self.state_notify()

    def _append_constraint_row(self, key: str = "CT", operator: str = ">=",
                               value: float = 0.0):
        r = self.cons_table.rowCount()
        self.cons_table.insertRow(r)
        self.cons_table.setItem(r, 0, QTableWidgetItem(str(key)))
        op_combo = QComboBox()
        for op in (">=", "<=", "=="):
            op_combo.addItem(op)
        op_combo.setCurrentIndex(max(op_combo.findText(operator), 0))
        self.cons_table.setCellWidget(r, 1, op_combo)
        self.cons_table.setItem(r, 2, QTableWidgetItem(f"{float(value):g}"))

    def _add_constraint(self):
        self._append_constraint_row()
        self.state_notify()

    def _remove_selected_constraint(self):
        rows = sorted({i.row() for i in self.cons_table.selectedIndexes()},
                       reverse=True)
        for r in rows:
            self.cons_table.removeRow(r)
        self.state_notify()

    # ------------------------------------------------------------------
    # Run page
    # ------------------------------------------------------------------
    def _run(self):
        project = self.state.project
        if project is None:
            return
        self.state_notify()
        definition = self._current_definition()
        # Static findings BEFORE paying solver time (Phase 3.1): errors
        # block, warnings only inform.
        issues = api.validate_optimization(project, definition)
        errors = [str(i) for i in issues if i.level == "error"]
        warnings = [str(i) for i in issues if i.level == "warning"]
        if errors:
            show_error(self, "The study has problems",
                        ValueError("\n".join(errors)))
            return
        self.message_label.setText("\n".join(warnings))
        self._last_definition = definition
        self.btn_run.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.message_label.setText("")
        self._run_started_at = time.time()
        self._worker = OptimizeMultiWorker(project, definition)
        self._thread = launch_worker(self._worker)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(lambda msg: show_error(
            self, "Error running optimization", RuntimeError(msg)))

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)

    def _on_progress(self, done: int, _values):
        elapsed = time.time() - (self._run_started_at or time.time())
        self.elapsed_label.setText(f"{elapsed:.1f}s - {done} designs")

    def _on_finished(self, outcome):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setVisible(False)
        self._outcome = outcome
        self.btn_send_to_designer.setEnabled(
            bool(outcome.front_params))
        keys = list(outcome.objective_keys) or (
            list(outcome.front_values[0]) if outcome.front_values else [])
        param_names = list(outcome.param_names)
        columns = [*param_names, *keys]
        self.front_table.setColumnCount(len(columns))
        self.front_table.setHorizontalHeaderLabels(columns)
        self.message_label.setText(outcome.message)
        self.front_table.setRowCount(len(outcome.front_params))
        for r, (params, values) in enumerate(zip(outcome.front_params,
                                                  outcome.front_values)):
            for c, col in enumerate(columns):
                source = params if c < len(param_names) else values
                value = source.get(col, "")
                text = (f"{float(value):.6g}" if isinstance(value, float)
                        else str(value))
                self.front_table.setItem(r, c, QTableWidgetItem(text))
        self._refresh_plot()

    def _refresh_plot(self):
        outcome = self._outcome
        canvas = self.plot_canvas.use_simple()
        canvas.clear()
        if outcome is None or not outcome.front_values:
            canvas.ax.text(0.5, 0.5, "Run the optimization first.",
                            ha="center", va="center", fontsize=10,
                            color="0.35", transform=canvas.ax.transAxes)
            canvas.draw()
            return
        keys = list(outcome.objective_keys) or (
            list(outcome.front_values[0]))
        view = self.view_combo.currentData() if hasattr(self, "view_combo") \
            else "pareto"
        if view == "parallel":
            plots.plot_parallel_coordinates(
                outcome.front_values, keys,
                param_names=list(outcome.param_names), ax=canvas.ax)
            canvas.draw()
            return
        if len(keys) != 2:
            canvas.ax.text(0.5, 0.5,
                            "The trade-off plot needs TWO objectives; use "
                            "the parallel view instead.",
                            ha="center", va="center", fontsize=10,
                            color="0.35", transform=canvas.ax.transAxes)
            canvas.draw()
            return
        try:
            plots.plot_pareto_front(
                outcome.front_values, keys,
                all_values=[rec["values"] for rec in outcome.all_evaluations],
                ax=canvas.ax)
        except Exception as exc:
            canvas.ax.text(0.5, 0.5, f"Cannot draw: {exc}",
                            ha="center", va="center",
                            transform=canvas.ax.transAxes)
        self._wire_front_picking(canvas, outcome, keys)
        canvas.draw()

    def _wire_front_picking(self, canvas, outcome, keys):
        """Click a front marker to select that design in the table (the
        members are sorted along the first objective in the plot and in
        row order of the sorted index the plot uses)."""
        order = sorted(range(len(outcome.front_values)),
                       key=lambda i: outcome.front_values[i].get(
                           keys[0], float("inf")))
        def on_pick(event):
            line = event.artist
            ind = getattr(event, "ind", None)
            if not ind:
                return
            row = order[event.ind[0]]
            self.front_table.selectRow(row)
        for line in canvas.ax.lines:
            line.set_picker(True)
            line.set_pickradius(6)
        canvas.mpl_connect("pick_event", on_pick)

    def _send_front_to_designer(self):
        """Cross-link 11 (Item 5): the selected study's Pareto members
        become labeled variant rows in the Geometry Designer."""
        outcome = self._outcome
        if outcome is None or not outcome.front_params:
            QMessageBox.information(self, "Nothing to send",
                                     "Run the optimization first.")
            return
        main = self.parent()
        while main is not None and not hasattr(main, "geometry_designer"):
            main = main.parent()
        designer = getattr(main, "geometry_designer", None) \
            if main is not None else None
        if designer is None:
            QMessageBox.information(
                self, "Designer unavailable",
                "Open this window from the main window's Tools menu.")
            return
        study = (self._last_definition.name if self._last_definition
                  else "optimization")
        for i, params in enumerate(outcome.front_params):
            designer.accept_design(f"{study} #{i + 1}", params)
        main.open_geometry_designer()

    def _export_csv(self):
        if self._outcome is None or not self._outcome.front_params:
            QMessageBox.information(self, "Nothing to export",
                                     "Run the optimization first.")
            return
        path, _filter = _save_dialog(self, "pareto_front.csv")
        if not path:
            return
        api.export_pareto_csv(self._outcome, path)
        QMessageBox.information(self, "Exported", f"File written:\n{path}")

    def _export_report(self):
        if self._outcome is None or not self._outcome.front_params:
            QMessageBox.information(self, "Nothing to export",
                                     "Run the optimization first.")
            return
        path, _filter = _save_dialog(self, "pareto_report.html", "html")
        if not path:
            return
        api.generate_optimization_report(
            self._outcome, path, project=self.state.project,
            definition=self._last_definition)
        QMessageBox.information(self, "Exported", f"Report written:\n{path}")
