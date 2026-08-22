"""Implement the Design GUI tab.

The tab gathers the two design tools on one page: a geometry comparison
that runs the project's saved cases over several blade planforms, and a
design optimization that drives one summary quantity with bounded
geometry parameters. Inputs are the active project (its geometry, its
saved cases, its saved optimization studies); outputs are in-memory
results, convergence plots, exported reports, and persisted
``OptimizationDefinition`` entries. Project I/O and solver execution
cross the ``api.py`` boundary; both long jobs run on worker threads so
the window never freezes.

Block titles are plain text for now: block help popups for this tab are
wired by a later documentation pass.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QScrollArea,
)

from ... import api
from ... import nomenclature
from ...models import (
    DesignVariable,
    FlightCondition,
    GEOMETRY_PARAMS,
    OptimizationDefinition,
)
from ...viz import plots

from ..common import (
    AppState,
    CanvasHost,
    equalize_button_widths,
    require_project,
    set_row_label,
    show_error,
)
from ..workers import CompareWorker, OptimizeWorker, launch_worker


class DesignTab(QWidget):
    """Design tools: geometry comparison and design optimization."""

    #: Columns of the variant table. The first column holds the label
    #: that names the geometry in results, plots and reports; "base" is
    #: the project's own planform.
    _VARIANT_COLUMNS = ["Label", "Root chord c/R", "Tip chord c/R",
                        "Twist root [deg]", "Twist tip [deg]", "Blades"]
    _COL_LABEL, _COL_ROOT_CHORD, _COL_TIP_CHORD = 0, 1, 2
    _COL_TWIST_ROOT, _COL_TWIST_TIP, _COL_BLADES = 3, 4, 5

    #: Columns of the design-variable table.
    _VARIABLE_COLUMNS = ["Parameter", "Lower", "Upper"]

    #: Summary quantities shown per geometry, and the choices offered as
    #: optimization objectives. Rows stay only when at least one summary
    #: carries them.
    _SUMMARY_ROWS = ("CT", "CQ", "CP", "FM", "eta_prop", "Thrust")
    _OBJECTIVE_KEYS = ("CT", "FM", "CP", "CQ", "eta_prop", "Thrust", "Power")

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        # Reentrancy guards (same pattern as GeometryTab): True while the
        # tab fills its widgets FROM the project, and True while it writes
        # back to the project, so a signal fired by either direction does
        # not re-enter the other one mid-flight.
        self._refreshing_from_project = False
        self._applying_locally = False

        # One worker/thread pair per block; both stay None between runs.
        self._compare_thread: QThread | None = None
        self._compare_worker: CompareWorker | None = None
        self._opt_thread: QThread | None = None
        self._opt_worker: OptimizeWorker | None = None

        # Outputs of each run, kept for the tables, the canvases and the
        # export buttons. ``_opt_history`` is the live buffer redrawn on
        # every progress signal until the real history arrives.
        self._comparison_results: list | None = None
        self._last_outcome = None
        self._last_definition: OptimizationDefinition | None = None
        self._opt_history: list[dict] = []
        self._variant_counter = 0

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(self._build_comparison_block())
        layout.addWidget(self._build_optimization_block())
        layout.addStretch(1)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.state.project_changed.connect(self._on_project_changed)
        self.state.mode_changed.connect(self._refresh_mode_labels)
        self._on_project_changed()

    # =====================================================================
    # Block A -- geometry comparison
    # =====================================================================

    def _build_comparison_block(self) -> QGroupBox:
        box = QGroupBox("Geometry comparison")
        vbox = QVBoxLayout(box)

        vbox.addWidget(QLabel("Blade geometries to compare:"))
        self.variants_table = QTableWidget(0, len(self._VARIANT_COLUMNS))
        self.variants_table.setHorizontalHeaderLabels(self._VARIANT_COLUMNS)
        self.variants_table.setToolTip(
            "One row per blade geometry.\n\n"
            "Each cell states an override over the project's own planform; "
            "an empty cell keeps the project value. The rectangular "
            "generator takes a single chord parameter, so its two chord "
            "cells name the same value and the root cell wins when they "
            "differ. The elliptic generator has no tip-chord parameter, "
            "which is why that cell stays disabled there. Blades accepts "
            "a whole number.")
        self.variants_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.variants_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.variants_table.verticalHeader().setVisible(False)
        self.variants_table.setMinimumHeight(100)
        vbox.addWidget(self.variants_table)

        variant_row = QHBoxLayout()
        self.btn_add_variant = QPushButton("Add variant")
        self.btn_add_variant.setToolTip(
            "Adds a copy of the base row. Edit the copy to describe "
            "another blade planform.")
        self.btn_add_variant.clicked.connect(self._add_variant_row)
        variant_row.addWidget(self.btn_add_variant)
        self.btn_remove_variant = QPushButton("Remove selected")
        self.btn_remove_variant.setToolTip(
            "Removes the selected rows from the geometry table.")
        self.btn_remove_variant.clicked.connect(self._remove_selected_variants)
        variant_row.addWidget(self.btn_remove_variant)
        variant_row.addStretch(1)
        vbox.addLayout(variant_row)

        self.lbl_conditions = QLabel("")
        self.lbl_conditions.setStyleSheet("color: gray;")
        vbox.addWidget(self.lbl_conditions)

        run_row = QHBoxLayout()
        self.btn_compare_run = QPushButton("Run comparison")
        self.btn_compare_run.setToolTip(
            "Runs the flight conditions listed above on every geometry in "
            "the table. Results stay in memory.")
        self.btn_compare_run.clicked.connect(self._run_comparison)
        run_row.addWidget(self.btn_compare_run)
        self.compare_progress = QProgressBar()
        self.compare_progress.setVisible(False)
        run_row.addWidget(self.compare_progress, 1)
        self.btn_compare_cancel = QPushButton("Cancel")
        self.btn_compare_cancel.setVisible(False)
        self.btn_compare_cancel.clicked.connect(self._cancel_comparison)
        run_row.addWidget(self.btn_compare_cancel)
        run_row.addStretch(0)
        vbox.addLayout(run_row)

        self.compare_status = QLabel("")
        vbox.addWidget(self.compare_status)

        vbox.addWidget(QLabel("Integrated results (first condition per geometry):"))
        self.results_table = QTableWidget(0, 0)
        self.results_table.setToolTip(
            "One column per geometry, one row per summary quantity. The "
            "value comes from the FIRST condition each geometry ran. When "
            "several saved cases ran per geometry, the full sweep belongs "
            "in the exported report and CSV.")
        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setMinimumHeight(130)
        vbox.addWidget(self.results_table)

        self.compare_canvas = CanvasHost()
        self.compare_canvas.setMinimumHeight(240)
        self.compare_canvas.show_message("Run a comparison to see the overlay figure.")
        vbox.addWidget(self.compare_canvas, stretch=1)

        export_row = QHBoxLayout()
        self.btn_export_report = QPushButton("Export report")
        self.btn_export_report.setToolTip(
            "Writes a self-contained HTML report with the comparison "
            "figure and the full summary table.")
        self.btn_export_report.clicked.connect(self._export_comparison_report)
        export_row.addWidget(self.btn_export_report)
        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.setToolTip(
            "Writes one CSV row per geometry and condition.")
        self.btn_export_csv.clicked.connect(self._export_comparison_csv)
        export_row.addWidget(self.btn_export_csv)
        export_row.addStretch(1)
        vbox.addLayout(export_row)
        return box

    # --- variant table ---------------------------------------------------

    @staticmethod
    def _fmt(value) -> str:
        """Formats a generator parameter for a table cell ('' when absent)."""
        if value is None:
            return ""
        return f"{float(value):.4g}"

    def _seed_variant_rows(self):
        """Rebuilds the variant table from the project's own geometry.

        One "base" row carries the planform parameters the current
        generator actually stores in ``origin_params``. An imported or
        hand-edited table has no parametric origin: its planform cells
        stay empty (empty means "no override"), and only the blade count
        applies.
        """
        table = self.variants_table
        table.setRowCount(0)
        self._variant_counter = 0
        project = self.state.project
        if project is None:
            return
        geom = project.geometry
        origin_params = dict(getattr(geom, "origin_params", {}) or {})
        kind = str(origin_params.get("kind", ""))
        values = ["base", "", "", "", "", str(int(geom.n_blades))]
        if kind == "rectangular":
            values[self._COL_ROOT_CHORD] = self._fmt(origin_params.get("chord_norm"))
            values[self._COL_TIP_CHORD] = values[self._COL_ROOT_CHORD]
        elif kind == "tapered":
            values[self._COL_ROOT_CHORD] = self._fmt(origin_params.get("root_chord_norm"))
            values[self._COL_TIP_CHORD] = self._fmt(origin_params.get("tip_chord_norm"))
        elif kind == "elliptic":
            values[self._COL_ROOT_CHORD] = self._fmt(origin_params.get("max_chord_norm"))
        values[self._COL_TWIST_ROOT] = self._fmt(origin_params.get("twist_root_deg"))
        values[self._COL_TWIST_TIP] = self._fmt(origin_params.get("twist_tip_deg"))
        table.insertRow(0)
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            if col == self._COL_TIP_CHORD and kind == "elliptic":
                item.setText("-")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(
                    "Not applicable: the elliptic generator has a single "
                    "chord parameter (max_chord_norm).")
            table.setItem(0, col, item)

    def _add_variant_row(self):
        """Duplicates the base row under the label "variant N"."""
        source = self.variants_table
        if source.rowCount() == 0:
            return
        self._variant_counter += 1
        target_row = source.rowCount()
        source.insertRow(target_row)
        for col in range(source.columnCount()):
            base_item = source.item(0, col)
            text = base_item.text() if base_item is not None else ""
            item = QTableWidgetItem(text)
            if base_item is not None and not (base_item.flags() & Qt.ItemFlag.ItemIsEditable):
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(base_item.toolTip())
            source.setItem(target_row, col, item)
        label_item = source.item(target_row, self._COL_LABEL)
        if label_item is not None:
            label_item.setText(f"variant {self._variant_counter}")

    def _remove_selected_variants(self):
        row = self.variants_table.currentRow()
        if row >= 0:
            self.variants_table.removeRow(row)

    def _row_overrides(self, row: int) -> tuple[str, dict]:
        """``(label, overrides)`` read from one variant-table row.

        Empty cells produce no override. Chord cells map onto the
        parameter the CURRENT generator understands, so a table written
        for a tapered project still reads sensibly after the project
        switches kind.
        """
        project = self.state.project
        origin_params = dict(getattr(project.geometry, "origin_params", {}) or {})
        kind = str(origin_params.get("kind", ""))

        def cell(col: int) -> str:
            item = self.variants_table.item(row, col)
            return item.text().strip() if item is not None else ""

        label = cell(self._COL_LABEL) or f"variant {row + 1}"
        overrides: dict = {}
        blades = cell(self._COL_BLADES)
        if blades:
            overrides["n_blades"] = int(float(blades))
        root, tip = cell(self._COL_ROOT_CHORD), cell(self._COL_TIP_CHORD)
        twist_root, twist_tip = cell(self._COL_TWIST_ROOT), cell(self._COL_TWIST_TIP)
        if kind == "rectangular":
            chord = root or tip
            if chord:
                overrides["chord_norm"] = float(chord)
        elif kind == "tapered":
            if root:
                overrides["root_chord_norm"] = float(root)
            if tip:
                overrides["tip_chord_norm"] = float(tip)
        elif kind == "elliptic":
            if root:
                overrides["max_chord_norm"] = float(root)
        if twist_root:
            overrides["twist_root_deg"] = float(twist_root)
        if twist_tip:
            overrides["twist_tip_deg"] = float(twist_tip)
        return label, overrides

    @staticmethod
    def _unique_label(label: str, variants: dict) -> str:
        if label not in variants:
            return label
        n = 2
        while f"{label} ({n})" in variants:
            n += 1
        return f"{label} ({n})"

    def _collect_variants(self) -> dict:
        """Builds ``{label: RotorGeometryDef}`` from the variant table."""
        variants: dict = {}
        for row in range(self.variants_table.rowCount()):
            try:
                label, overrides = self._row_overrides(row)
            except ValueError as exc:
                raise ValueError(f"Geometry table, row {row + 1}: {exc}") from exc
            label = self._unique_label(label, variants)
            try:
                variants[label] = api.variant_geometry(
                    self.state.project.geometry, overrides)
            except Exception as exc:
                raise ValueError(f"Geometry {label!r}: {exc}") from exc
        if not variants:
            raise ValueError("Add at least one geometry row before running.")
        return variants

    def _comparison_conditions(self) -> list[FlightCondition]:
        """Saved cases, or one hover case built from the condition fields.

        The engine has no default rotation speed on purpose, so the
        fallback hover case takes collective and rpm from the
        optimization block instead of inventing numbers here.
        """
        conditions = list(self.state.project.saved_cases)
        if conditions:
            return conditions
        return [FlightCondition(
            name="hover",
            mu_x=0.0,
            collective_deg=self.collective_spin.value(),
            Vz=self.vz_spin.value(),
            rpm=float(self.rpm_spin.value()),
        )]

    # --- comparison run ---------------------------------------------------

    def _run_comparison(self):
        if not require_project(self, self.state):
            return
        if self._compare_worker is not None:
            return
        try:
            variants = self._collect_variants()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid geometry table", str(exc))
            return
        conditions = self._comparison_conditions()
        total = len(variants) * len(conditions)
        self._set_compare_running(True)
        self.compare_status.setText(f"Running comparison: 0/{total}…")
        self.compare_progress.setRange(0, max(total, 1))
        self.compare_progress.setValue(0)
        worker = CompareWorker(self.state.project, variants, conditions)
        worker.progress.connect(self._on_compare_progress)
        worker.finished.connect(self._on_compare_finished)
        worker.failed.connect(self._on_compare_failed)
        self._compare_worker = worker
        self._compare_thread = launch_worker(worker)

    def _cancel_comparison(self):
        if self._compare_worker is not None:
            self._compare_worker.cancel()
            self.btn_compare_cancel.setEnabled(False)
            self.compare_status.setText("Canceling comparison…")

    def _on_compare_progress(self, done: int, total: int):
        self.compare_progress.setRange(0, max(total, 1))
        self.compare_progress.setValue(done)
        self.compare_status.setText(f"Running comparison: {done}/{total}…")

    def _on_compare_finished(self, results: list):
        cancelled = (self._compare_worker is not None
                     and self._compare_worker.cancel_requested)
        self._reset_compare_ui()
        self._comparison_results = list(results)
        if cancelled and not results:
            self.compare_status.setText("Comparison canceled.")
            return
        self._populate_comparison_table(results)
        self._draw_comparison_canvas(results)
        self.compare_status.setText(
            f"Comparison finished: {len(results)} case(s).")

    def _on_compare_failed(self, message: str):
        self._reset_compare_ui()
        self.compare_status.setText("Comparison failed.")
        show_error(self, "Error running comparison", RuntimeError(message))

    def _set_compare_running(self, running: bool):
        self.btn_compare_run.setEnabled(not running)
        self.btn_add_variant.setEnabled(not running)
        self.btn_remove_variant.setEnabled(not running)
        self.compare_progress.setVisible(running)
        self.btn_compare_cancel.setVisible(running)
        self.btn_compare_cancel.setEnabled(running)

    def _reset_compare_ui(self):
        self._set_compare_running(False)
        self._compare_thread = None
        self._compare_worker = None

    # --- comparison output --------------------------------------------------

    def _populate_comparison_table(self, results: list):
        """Fills the integrated table: one column per geometry, one row
        per present summary quantity, values from each geometry's FIRST
        condition."""
        first_by_label: dict[str, object] = {}
        for res in results:
            label = str(res.summary.get("geometry_label")
                        or res.condition_name or "?")
            first_by_label.setdefault(label, res)
        labels = list(first_by_label)
        rows = [key for key in self._SUMMARY_ROWS
                if any(key in r.summary for r in first_by_label.values())]
        table = self.results_table
        table.clear()
        table.setRowCount(len(rows))
        table.setColumnCount(len(labels))
        table.setHorizontalHeaderLabels(labels)
        table.setVerticalHeaderLabels(rows)
        for i, key in enumerate(rows):
            for j, label in enumerate(labels):
                value = first_by_label[label].summary.get(key)
                text = "" if value is None else f"{float(value):.4g}"
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled
                              | Qt.ItemFlag.ItemIsSelectable)
                table.setItem(i, j, item)

    def _draw_comparison_canvas(self, results: list):
        try:
            axes = plots.plot_geometry_comparison(results)
            axes_list = np.atleast_1d(axes)
            self.compare_canvas.show_figure(axes_list[0].figure)
        except Exception as exc:
            self.compare_canvas.show_message(
                f"Could not draw the comparison figure: {exc}")

    def _export_destination(self, default_name: str, filter_text: str) -> str | None:
        """Asks where to write an export, starting in the project's
        outputs folder."""
        project = self.state.project
        start_dir = Path(api.project_outputs_dir(project, create=True)) \
            if project is not None and project.path else Path("outputs")
        path, _selected = QFileDialog.getSaveFileName(
            self, "Export", str(start_dir / default_name), filter_text)
        return path or None

    def _export_comparison_report(self):
        if not self._comparison_results:
            QMessageBox.warning(self, "Nothing to export",
                                "Run a comparison first.")
            return
        path = self._export_destination("comparison.html", "HTML report (*.html)")
        if path is None:
            return
        project = self.state.project
        title = "Geometry comparison"
        if project is not None:
            title = f"Geometry comparison - {project.name}"
        try:
            dest = api.generate_comparison_report(
                self._comparison_results, path, project=project, title=title)
        except Exception as exc:
            show_error(self, "Error exporting report", exc)
            return
        QMessageBox.information(self, "Exported", f"Report written to {dest}")

    def _export_comparison_csv(self):
        if not self._comparison_results:
            QMessageBox.warning(self, "Nothing to export",
                                "Run a comparison first.")
            return
        path = self._export_destination("comparison.csv", "CSV (*.csv)")
        if path is None:
            return
        try:
            dest = api.export_comparison_csv(self._comparison_results, path)
        except Exception as exc:
            show_error(self, "Error exporting CSV", exc)
            return
        QMessageBox.information(self, "Exported", f"CSV written to {dest}")

    # =====================================================================
    # Block B -- design optimization
    # =====================================================================

    def _build_optimization_block(self) -> QGroupBox:
        box = QGroupBox("Design optimization")
        outer = QVBoxLayout(box)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft
                               | Qt.AlignmentFlag.AlignVCenter)

        self.opt_name_edit = QLineEdit()
        self.opt_name_edit.setPlaceholderText("optimization 1")
        self.opt_name_edit.setToolTip(
            '"name" — Name of the optimization study. Saving a study '
            'under an existing name replaces that entry in the project.')
        form.addRow("Name:", self.opt_name_edit)

        self.objective_kind_combo = QComboBox()
        self.objective_kind_combo.addItems(["maximize", "minimize"])
        self.objective_kind_combo.setToolTip(
            '"objective_kind" — Whether the search drives the objective '
            'coefficient to its maximum ("maximize") or its minimum '
            '("minimize").')
        form.addRow("Objective kind:", self.objective_kind_combo)

        self.objective_key_combo = QComboBox()
        self.objective_key_combo.setEditable(True)
        self.objective_key_combo.addItems(list(self._OBJECTIVE_KEYS))
        self.objective_key_combo.setCurrentText("FM")
        self.objective_key_combo.setToolTip(
            '"objective_key" — Summary coefficient the search drives '
            'toward its best found value, for example FM or CT. Any key '
            "that appears in a results summary works; the list offers the "
            "usual candidates.")
        form.addRow("Objective key:", self.objective_key_combo)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["powell", "nelder-mead"])
        self.method_combo.setToolTip(
            '"method" — Derivative-free search method: Powell or '
            "Nelder-Mead. Both evaluate complete cases, so neither needs "
            "gradients; the search starts at the middle of the bounds.")
        form.addRow("Method:", self.method_combo)

        self.max_evals_spin = QSpinBox()
        self.max_evals_spin.setRange(5, 500)
        self.max_evals_spin.setValue(40)
        self.max_evals_spin.setToolTip(
            '"max_evals" - Maximum number of full-solve evaluations the '
            "search may spend. Each evaluation solves one complete flight "
            "condition on a regenerated geometry; the search stops at this "
            "number even without convergence.")
        form.addRow("Max evaluations:", self.max_evals_spin)
        outer.addLayout(form)

        condition_header = QLabel("<b>Flight condition</b>")
        outer.addWidget(condition_header)
        condition_form = QFormLayout()
        self._condition_form = condition_form

        self.mu_x_spin = QDoubleSpinBox()
        self.mu_x_spin.setRange(-0.5, 1.5)
        self.mu_x_spin.setDecimals(3)
        self.mu_x_spin.setSingleStep(0.01)
        self.mu_x_spin.setValue(0.0)
        self.mu_x_spin.setToolTip(
            '"mu_x" — Advance ratio along the vehicle x axis for the '
            'condition every candidate geometry must satisfy.')
        condition_form.addRow("mu_x:", self.mu_x_spin)

        self.collective_spin = QDoubleSpinBox()
        self.collective_spin.setRange(-10.0, 30.0)
        self.collective_spin.setSingleStep(0.5)
        self.collective_spin.setValue(8.0)
        self.collective_spin.setToolTip(
            '"collective_deg" — Collective pitch applied to every blade '
            'station during the optimization runs.')
        condition_form.addRow("collective [deg]:", self.collective_spin)

        self.vz_spin = QDoubleSpinBox()
        self.vz_spin.setRange(-50.0, 50.0)
        self.vz_spin.setDecimals(2)
        self.vz_spin.setSingleStep(1.0)
        self.vz_spin.setValue(0.0)
        self.vz_spin.setToolTip(
            '"Vz" — Velocity along the shaft, in m/s. Zero gives axial '
            'flight; climb is positive.')
        condition_form.addRow("axial V [m/s]:", self.vz_spin)

        self.rpm_spin = QSpinBox()
        self.rpm_spin.setRange(100, 20000)
        self.rpm_spin.setSingleStep(50)
        self.rpm_spin.setValue(1500)
        self.rpm_spin.setToolTip(
            '"rpm" — Rotational speed of the condition. The engine '
            'requires rpm on every condition: every result scales with '
            'the tip speed Ω·R, so no default exists.')
        condition_form.addRow("RPM:", self.rpm_spin)
        outer.addLayout(condition_form)

        outer.addWidget(QLabel("Design variables (bounded):"))
        self.variables_table = QTableWidget(0, len(self._VARIABLE_COLUMNS))
        self.variables_table.setHorizontalHeaderLabels(self._VARIABLE_COLUMNS)
        self.variables_table.setToolTip(
            "The geometry parameters the search may move, each one held "
            "between its lower and upper bound. The search starts at the "
            "center of the bounds.")
        header = self.variables_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.variables_table.verticalHeader().setVisible(False)
        self.variables_table.setMinimumHeight(110)
        outer.addWidget(self.variables_table)

        variable_row = QHBoxLayout()
        self.btn_add_variable = QPushButton("Add variable")
        self.btn_add_variable.setToolTip(
            "Adds a row for one more bounded geometry parameter.")
        self.btn_add_variable.clicked.connect(
            lambda: self._add_variable_row())
        variable_row.addWidget(self.btn_add_variable)
        self.btn_remove_variable = QPushButton("Remove selected")
        self.btn_remove_variable.setToolTip(
            "Removes the selected variable rows.")
        self.btn_remove_variable.clicked.connect(self._remove_selected_variables)
        variable_row.addWidget(self.btn_remove_variable)
        variable_row.addStretch(1)
        outer.addLayout(variable_row)

        action_row = QHBoxLayout()
        self.btn_save_definition = QPushButton("Save definition")
        self.btn_save_definition.setToolTip(
            "Stores the study in the project (inputs/optimizations.bemt) "
            "under the name above. An entry with the same name is replaced.")
        self.btn_save_definition.clicked.connect(self._save_definition)
        action_row.addWidget(self.btn_save_definition)
        self.btn_optimize_run = QPushButton("Run optimization")
        self.btn_optimize_run.setToolTip(
            "Runs the study defined above. Every evaluation solves one "
            "full case on a regenerated geometry.")
        self.btn_optimize_run.clicked.connect(self._run_optimization)
        action_row.addWidget(self.btn_optimize_run)
        self.opt_progress = QProgressBar()
        self.opt_progress.setVisible(False)
        action_row.addWidget(self.opt_progress, 1)
        self.btn_optimize_cancel = QPushButton("Cancel")
        self.btn_optimize_cancel.setVisible(False)
        self.btn_optimize_cancel.clicked.connect(self._cancel_optimization)
        action_row.addWidget(self.btn_optimize_cancel)
        self.btn_export_opt_report = QPushButton("Export report")
        self.btn_export_opt_report.setToolTip(
            "Writes a self-contained HTML report with the convergence "
            "history and the best parameters.")
        self.btn_export_opt_report.clicked.connect(self._export_optimization_report)
        action_row.addWidget(self.btn_export_opt_report)
        action_row.addStretch(0)
        outer.addLayout(action_row)

        self.best_label = QLabel("")
        self.best_label.setStyleSheet("color: gray;")
        outer.addWidget(self.best_label)
        self.opt_status = QLabel("")
        outer.addWidget(self.opt_status)

        self.convergence_canvas = CanvasHost()
        self.convergence_canvas.setMinimumHeight(220)
        self.convergence_canvas.show_message(
            "Run an optimization to see the convergence.")
        outer.addWidget(self.convergence_canvas, stretch=1)
        return box

    # --- variables table ---------------------------------------------------

    def _add_variable_row(self, param: str = "tip_chord_norm",
                          lower: float = 0.02, upper: float = 0.12):
        """Adds one bounded-parameter row, or seeds the default row when
        called without arguments on an empty table."""
        table = self.variables_table
        row = table.rowCount()
        table.insertRow(row)

        combo = QComboBox()
        combo.addItems(list(GEOMETRY_PARAMS))
        combo.setCurrentText(param)
        combo.setToolTip(
            "Geometry parameter varied between the bounds beside it. "
            "Names follow the geometry generators; n_blades takes whole "
            "numbers.")
        table.setCellWidget(row, 0, combo)

        lower_spin = QDoubleSpinBox()
        lower_spin.setRange(-1000.0, 1000.0)
        lower_spin.setDecimals(4)
        lower_spin.setValue(float(lower))
        lower_spin.setToolTip("Lower bound the search may give this parameter.")
        table.setCellWidget(row, 1, lower_spin)

        upper_spin = QDoubleSpinBox()
        upper_spin.setRange(-1000.0, 1000.0)
        upper_spin.setDecimals(4)
        upper_spin.setValue(float(upper))
        upper_spin.setToolTip("Upper bound the search may give this parameter.")
        table.setCellWidget(row, 2, upper_spin)

    def _remove_selected_variables(self):
        row = self.variables_table.currentRow()
        if row >= 0:
            self.variables_table.removeRow(row)

    # --- definition collect / load ------------------------------------------

    def _collect_definition(self) -> OptimizationDefinition:
        """Reads block B into an ``OptimizationDefinition``, raising
        ``ValueError`` with a readable message when the definition cannot
        run."""
        name = self.opt_name_edit.text().strip() or "optimization 1"
        variables: list[DesignVariable] = []
        for row in range(self.variables_table.rowCount()):
            combo = self.variables_table.cellWidget(row, 0)
            lower = self.variables_table.cellWidget(row, 1)
            upper = self.variables_table.cellWidget(row, 2)
            if combo is None or lower is None or upper is None:
                continue
            lo, hi = float(lower.value()), float(upper.value())
            if not lo < hi:
                raise ValueError(
                    f"Variable {combo.currentText()!r} needs "
                    f"lower < upper (got {lo}, {hi}).")
            variables.append(DesignVariable(
                param=combo.currentText(), lower=lo, upper=hi))
        if not variables:
            raise ValueError("Add at least one design variable row.")
        rpm = float(self.rpm_spin.value())
        condition = FlightCondition(
            name=f"{name} case",
            mu_x=self.mu_x_spin.value(),
            collective_deg=self.collective_spin.value(),
            Vz=self.vz_spin.value(),
            rpm=rpm,
        )
        return OptimizationDefinition(
            name=name,
            objective_kind=self.objective_kind_combo.currentText(),
            objective_key=self.objective_key_combo.currentText().strip() or "FM",
            variables=variables,
            method=self.method_combo.currentText(),
            max_evals=int(self.max_evals_spin.value()),
            condition=condition,
        )

    def _load_definition(self, definition: OptimizationDefinition):
        """Fills block B from one saved study (project load)."""
        self.opt_name_edit.setText(definition.name)
        index = self.objective_kind_combo.findText(definition.objective_kind)
        self.objective_kind_combo.setCurrentIndex(max(index, 0))
        if self.objective_key_combo.findText(definition.objective_key) < 0:
            self.objective_key_combo.addItem(definition.objective_key)
        self.objective_key_combo.setCurrentText(definition.objective_key)
        index = self.method_combo.findText(definition.method)
        self.method_combo.setCurrentIndex(max(index, 0))
        self.max_evals_spin.setValue(int(definition.max_evals))
        condition = definition.condition
        if condition is not None:
            self.mu_x_spin.setValue(float(condition.mu_x))
            self.collective_spin.setValue(float(condition.collective_deg))
            self.vz_spin.setValue(float(condition.Vz))
            if condition.rpm is not None:
                self.rpm_spin.setValue(int(round(float(condition.rpm))))
        self.variables_table.setRowCount(0)
        for var in definition.variables:
            self._add_variable_row(var.param, var.lower, var.upper)

    def _save_definition(self):
        """Upserts the form into ``project.optimizations`` and writes the
        project to disk (inputs/optimizations.bemt)."""
        if not require_project(self, self.state):
            return
        try:
            definition = self._collect_definition()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid optimization", str(exc))
            return
        self._applying_locally = True
        try:
            optimizations = self.state.project.optimizations
            for i, existing in enumerate(optimizations):
                if existing.name == definition.name:
                    optimizations[i] = definition
                    break
            else:
                optimizations.append(definition)
        finally:
            self._applying_locally = False
        try:
            api.save_project(self.state.project)
        except Exception as exc:
            show_error(self, "Error saving project", exc)
            return
        self.state.mark_saved()
        self.opt_status.setText(f"Saved study {definition.name!r}.")

    # --- optimization run -----------------------------------------------------

    def _run_optimization(self):
        if not require_project(self, self.state):
            return
        if self._opt_worker is not None:
            return
        try:
            definition = self._collect_definition()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid optimization", str(exc))
            return
        self._opt_history = []
        self._last_definition = definition
        self._last_outcome = None
        total = int(definition.max_evals)
        self._set_optimize_running(True)
        self.opt_progress.setRange(0, max(total, 1))
        self.opt_progress.setValue(0)
        self.opt_status.setText("Running optimization: 0 evaluations…")
        self._redraw_convergence()
        worker = OptimizeWorker(self.state.project, definition)
        worker.progress.connect(self._on_opt_progress)
        worker.finished.connect(self._on_opt_finished)
        worker.failed.connect(self._on_opt_failed)
        self._opt_worker = worker
        self._opt_thread = launch_worker(worker)

    def _cancel_optimization(self):
        if self._opt_worker is not None:
            self._opt_worker.cancel()
            self.btn_optimize_cancel.setEnabled(False)
            self.opt_status.setText("Canceling optimization…")

    def _on_opt_progress(self, evals_done: int, max_evals: int, best_value: float):
        """Live update: bar position, best-value line, and the partial
        history buffer the convergence canvas redraws from.

        The engine reports only ``(evaluations, limit, best so far)``
        during the run, so the buffer holds the running-best sequence;
        the true per-evaluation values arrive with the outcome and
        replace the buffer on completion.
        """
        self.opt_progress.setRange(0, max(max_evals, 1))
        self.opt_progress.setValue(evals_done)
        key = self._current_objective_key()
        if np.isfinite(best_value):
            self._opt_history.append(
                {"eval": evals_done, key: float(best_value)})
            self.best_label.setText(
                f"{key} best = {best_value:.4g}")
        self.opt_status.setText(
            f"Running optimization: {evals_done}/{max_evals} evaluations…")
        self._redraw_convergence()

    def _on_opt_finished(self, outcome):
        cancelled = (self._opt_worker is not None
                     and self._opt_worker.cancel_requested)
        self._reset_optimize_ui()
        self._last_outcome = outcome
        if outcome.history:
            self._opt_history = list(outcome.history)
        key = outcome.objective_key or self._current_objective_key()
        if np.isfinite(outcome.best_value):
            self.best_label.setText(
                f"{key} best = {outcome.best_value:.4g} at "
                f"{outcome.best_params}")
        self._redraw_convergence()
        if cancelled or outcome.message == "cancelled":
            self.opt_status.setText("Optimization canceled.")
        else:
            self.opt_status.setText(
                f"Optimization finished after {outcome.n_evals} "
                f"evaluations. {outcome.message}")

    def _on_opt_failed(self, message: str):
        self._reset_optimize_ui()
        self.opt_status.setText("Optimization failed.")
        show_error(self, "Error running optimization", RuntimeError(message))

    def _set_optimize_running(self, running: bool):
        self.btn_optimize_run.setEnabled(not running)
        self.btn_save_definition.setEnabled(not running)
        self.btn_add_variable.setEnabled(not running)
        self.btn_remove_variable.setEnabled(not running)
        self.opt_progress.setVisible(running)
        self.btn_optimize_cancel.setVisible(running)
        self.btn_optimize_cancel.setEnabled(running)

    def _reset_optimize_ui(self):
        self._set_optimize_running(False)
        self._opt_thread = None
        self._opt_worker = None

    def _current_objective_key(self) -> str:
        return (self.objective_key_combo.currentText().strip() or "FM")

    def _redraw_convergence(self):
        """Draws the convergence plot from the buffer kept in this tab."""
        canvas = self.convergence_canvas.use_simple()
        canvas.clear()
        try:
            plots.plot_optimization_convergence(
                self._opt_history, self._current_objective_key(),
                mode=self.objective_kind_combo.currentText(),
                ax=canvas.ax)
        except Exception as exc:
            canvas.ax.text(0.5, 0.5, f"Could not draw convergence: {exc}",
                           ha="center", va="center",
                           transform=canvas.ax.transAxes, wrap=True)
        canvas.draw()

    def _export_optimization_report(self):
        if self._last_outcome is None:
            QMessageBox.warning(self, "Nothing to export",
                                "Run an optimization first.")
            return
        slug = api.sanitize_filename(
            self._last_definition.name if self._last_definition else "optimization")
        path = self._export_destination(
            f"{slug}_optimization.html", "HTML report (*.html)")
        if path is None:
            return
        try:
            dest = api.generate_optimization_report(
                self._last_outcome, path, project=self.state.project,
                definition=self._last_definition)
        except Exception as exc:
            show_error(self, "Error exporting report", exc)
            return
        QMessageBox.information(self, "Exported", f"Report written to {dest}")

    # =====================================================================
    # Project reactivity
    # =====================================================================

    def _on_project_changed(self):
        """Rebuilds what depends on the project: the variant table, the
        conditions note, the mode labels and the first saved study."""
        if self._refreshing_from_project or self._applying_locally:
            return
        self._refreshing_from_project = True
        try:
            # Results belong to the previous project: drop them before
            # anything else can read them.
            self._comparison_results = None
            self._last_outcome = None
            self._last_definition = None
            self._opt_history = []
            self.results_table.setRowCount(0)
            self.results_table.setColumnCount(0)
            self.compare_canvas.show_message(
                "Run a comparison to see the overlay figure.")
            self.convergence_canvas.show_message(
                "Run an optimization to see the convergence.")
            self.best_label.setText("")
            self.compare_status.setText("")
            self.opt_status.setText("")

            self._seed_variant_rows()
            self._update_conditions_label()
            self._refresh_mode_labels()

            project = self.state.project
            if project is not None and project.optimizations:
                self._load_definition(project.optimizations[0])
            elif self.variables_table.rowCount() == 0:
                self._add_variable_row("tip_chord_norm", 0.02, 0.12)
        finally:
            self._refreshing_from_project = False

    def _update_conditions_label(self):
        project = self.state.project
        count = len(project.saved_cases) if project is not None else 0
        if count:
            self.lbl_conditions.setText(
                f"{count} saved cases per geometry")
        else:
            self.lbl_conditions.setText(
                "no saved cases: one default hover case will run")

    def _refresh_mode_labels(self):
        """Rewrites the condition rows' symbols for the current mode.

        The stored quantities are the engine's disk-axis keys; only the
        letters the user reads rotate with rotor/propeller mode, and
        they come from ``nomenclature`` -- never from a second table
        here.
        """
        prop = self.state.is_propeller()
        for key, field in (("mu_x", self.mu_x_spin),
                           ("collective_deg", self.collective_spin),
                           ("Vz", self.vz_spin)):
            symbol = nomenclature.symbol_text(key, prop)
            unit = nomenclature.unit(key)
            label = f"{symbol} [{unit}]:" if unit else f"{symbol}:"
            set_row_label(self._condition_form, field, label)

    def showEvent(self, event):
        """Equalizes the width of each button group on the FIRST display.

        Only after the stylesheet's polish does a button's ``sizeHint``
        include the theme's padding (see
        ``common.equalize_button_widths``)."""
        super().showEvent(event)
        if getattr(self, "_widths_reviewed", False):
            return
        self._widths_reviewed = True
        equalize_button_widths((self.btn_add_variant, self.btn_remove_variant))
        equalize_button_widths((self.btn_export_report, self.btn_export_csv))
        equalize_button_widths((self.btn_add_variable, self.btn_remove_variable))
        equalize_button_widths((self.btn_save_definition, self.btn_optimize_run,
                                self.btn_export_opt_report))


if __name__ == "__main__":   # pragma: no cover
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    state = AppState()
    window = DesignTab(state)
    window.show()
    sys.exit(app.exec())
