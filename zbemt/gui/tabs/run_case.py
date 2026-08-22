"""Implement GUI tab 5, Run Case.

Purpose: define and execute one flight condition and present its numeric
summary. Inputs are the active project, two flow components, collective, RPM,
and optional trim settings. Outputs are progress signals, a completed in-memory
result, and a history entry managed by ``AppState``.

The tab follows the display-axis convention from ``nomenclature.py`` while
``api.py`` and ``studies.py`` perform validation and execution off the GUI
thread. It does not persist files directly and cannot establish model accuracy
beyond the validation and convergence information returned by the solver.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QScrollArea,
    QHeaderView,
    QProgressBar,
    QInputDialog,
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)
from PyQt6.QtCore import Qt, QThread, QSize
from PyQt6.QtGui import QTextDocument

from ... import api
from ...models import FlightCondition, BatchDefinition

from ..common import (AppState, show_error, require_project, confirm_run_despite_issues,
                      describe_case_settings, symbol_to_plain_text, set_row_visible,
                      condition_label_and_tooltip, set_row_label,
                      align_headers_with_content, TEXT_ALIGN,
                      CONDITION_VALUE_WIDTH, CONDITION_ROW_SPACING,
                      condition_unit_width,
                      apply_condition_unit_width,
                      resolve_condition_pair, apply_condition_pair)
from ..instant_tooltip import install_instant_tooltip
from ..workers import BatchRunnerWorker, launch_worker
from ..widgets import LongitudinalInput, AxialInput


# =============================================================================
# Tab 5 — Run Case (docs/plano.md Section 6): Mu dropdown (or J_x), Alpha
# dropdown (or Vz), Collective, RPM. No canvas — the visual result goes to
# the Results tab; here it's just a numeric summary (key-quantity table).
# =============================================================================


#: Item role that holds the HTML symbol (`"C<sub>T</sub>"`), painted by
#: `_RichSymbolDelegate`. The DISPLAY role stays the plain text from
#: `common.symbol_to_plain_text` ("C_T"): that's what copy/paste and the
#: tests read, and it's the fallback if the delegate isn't installed.
HTML_SYMBOL_ROLE = Qt.ItemDataRole.UserRole + 1


class _RichSymbolDelegate(QStyledItemDelegate):
    """Paints the label column as RICH text, with real subscripts.

    `QTableWidgetItem` doesn't render HTML: `api.SUMMARY_SYMBOLS` holds
    `"C<sub>T</sub>"` and the table showed the flattened `"C_T"`
    (`common.symbol_to_plain_text`). Unicode subscript doesn't solve it,
    because Unicode has no subscript for UPPERCASE letters, which is exactly the
    case for almost every coefficient here (C_T, C_Q, C_P, C_Mx...). So
    the label is drawn by a `QTextDocument`, which understands `<sub>` and
    the Greek entities (`&mu;`, `&Omega;`) from the same dictionary the
    HTML report uses, so there is no second list of symbols.

    Only rows with `HTML_SYMBOL_ROLE` filled in are painted this way;
    group-header rows (plain, bold text) fall back to the default
    delegate."""

    def _doc(self, html: str, option: QStyleOptionViewItem) -> QTextDocument:
        color = option.palette.color(
            option.palette.ColorRole.HighlightedText
            if option.state & QStyle.StateFlag.State_Selected
            else option.palette.ColorRole.Text)
        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setDocumentMargin(0)
        # the color comes from the palette (not QTextDocument's default
        # black), otherwise the label disappears in a dark theme
        doc.setHtml(f'<span style="color:{color.name()};white-space:pre">{html}</span>')
        return doc

    def paint(self, painter, option, index):
        html = index.data(HTML_SYMBOL_ROLE)
        if not html:
            super().paint(painter, option, index)
            return
        option = QStyleOptionViewItem(option)
        self.initStyleOption(option, index)
        option.text = ""          # the plain text would be painted underneath
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter,
                           option.widget)
        area = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText,
                                     option, option.widget)
        doc = self._doc(html, option)
        painter.save()
        painter.translate(area.left(),
                          area.top() + max(0.0, (area.height() - doc.size().height()) / 2))
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        html = index.data(HTML_SYMBOL_ROLE)
        if not html:
            return super().sizeHint(option, index)
        option = QStyleOptionViewItem(option)
        self.initStyleOption(option, index)
        doc = self._doc(html, option)
        size = doc.size()
        base = super().sizeHint(option, index)
        return QSize(int(size.width()) + 8, max(base.height(), int(size.height()) + 4))

class RunCaseTab(QWidget):
    #: "Run mode" dropdown label -> trim_mode of `api.run_case_trimmed`
    #: (None = direct run, no trim loop).
    _RUN_MODE_TO_TRIM = {
        "Fixed collective & RPM": None,
        "Fixed RPM, target thrust/CT": "solve_collective",
        "Fixed collective, target thrust/CT": "solve_rpm",
    }

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        # Bug 3: wrap in a QScrollArea so results aren't cut off when the
        # window has little vertical space (same as GeometryTab, AirfoilTab,
        # and ConfigMotorTab, which already use this pattern).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        run_box = QGroupBox("Run Case")
        form = QFormLayout(run_box)
        self._run_form = form

        # --- run mode (Step 8): direct (collective+RPM fixed) or one of the
        # two bisection trim loops (`api.run_case_trimmed`). Choosing here
        # decides which of the two fields below (collective/RPM) stays
        # locked as target/input and which is solved by the loop.
        self.run_mode_combo = QComboBox()
        self.run_mode_combo.addItems(list(self._RUN_MODE_TO_TRIM))
        self.run_mode_combo.setToolTip(
            '"trim_mode" — direct run (collective and RPM both as entered) or a bisection '
            'trim loop that solves collective (RPM fixed) or RPM (collective fixed) for a '
            'target thrust/CT')
        self.run_mode_combo.currentTextChanged.connect(self._update_run_mode_visibility)
        form.addRow("Run mode:", self.run_mode_combo)

        # --- advance ratio: mu_x / J_x / V [m/s] (label-dropdown) ----------
        self.advance = LongitudinalInput(default_mu=0.2)
        self.advance.set_context_provider(self._advance_context)
        self._size_field(self.advance)
        form.addRow("Advance:", self.advance)

        # --- axial component: alpha [deg] or Vz [m/s] (label-dropdown) ---
        self.axial = AxialInput(default_value=0.0)
        self.axial.set_context_provider(self._axial_context)
        self._size_field(self.axial)
        form.addRow("Axial flow:", self.axial)

        self.collective_spin = QDoubleSpinBox(); self.collective_spin.setRange(-10, 30); self.collective_spin.setValue(8.0)
        self.collective_spin.setSingleStep(0.5)
        self.collective_spin.setToolTip(
            '"collective_deg"<br><br>'
            'Collective pitch added to the blade twist at every radial station.<br><br>'
            'Increasing it generally increases thrust, until stall or another model limit is reached.')
        self.rpm_spin = QDoubleSpinBox(); self.rpm_spin.setRange(1, 20000); self.rpm_spin.setValue(600)
        self.rpm_spin.setSingleStep(10)
        self.rpm_spin.setToolTip(
            '"rpm"<br><br>'
            'Rotational speed of the rotor or propeller in revolutions per minute.<br><br>'
            'It defines Ω and the velocity scale ΩR used by the dimensionless ratios.')
        self._size_field(self.collective_spin)
        self._size_field(self.rpm_spin)
        form.addRow("Collective [deg]:", self._with_unit_indent(self.collective_spin))
        form.addRow("RPM:", self._with_unit_indent(self.rpm_spin))

        self.trim_target_kind_combo = QComboBox()
        self.trim_target_kind_combo.addItems(["Thrust [N]", "CT [-]"])
        self.trim_target_kind_combo.setToolTip(
            '"target_kind" — trim the free DOF (collective or RPM, per Run mode above) until '
            'either the dimensional Thrust [N] or the dimensionless CT hits Target value')
        self.trim_target_value = QDoubleSpinBox()
        self.trim_target_value.setRange(-1e9, 1e9)
        self.trim_target_value.setDecimals(6)
        self.trim_target_value.setValue(1000.0)
        self.trim_target_value.setToolTip(
            '"target_value"<br><br>'
            'Target value used by the selected trim mode.<br><br>'
            'The unit is thrust in newtons or the dimensionless thrust coefficient, '
            'according to the target type.')
        form.addRow("Trim target:", self.trim_target_kind_combo)
        form.addRow("Target value:", self.trim_target_value)
        #: kept to swap the LABEL of the two velocity-component rows when
        #: the mode changes (see `_refresh_mode_defaults`)
        self._condition_form = form
        self._update_run_mode_visibility()

        self.btn_run_case = QPushButton("Run Case")
        self.btn_run_case.clicked.connect(self._run_case)
        form.addRow(self.btn_run_case)
        layout.addWidget(run_box)

        # --- saved cases (docs/plano_v3.md Part 3.2): same persistence
        # pattern as named batches, applied to `Project.saved_cases`.
        saved_box = QGroupBox("Saved Cases")
        saved_row = QHBoxLayout(saved_box)
        self.saved_cases_combo = QComboBox()
        self.saved_cases_combo.addItem("(none selected)")
        self.saved_cases_combo.setToolTip(
            "Flight conditions stored with this project. Selecting one loads "
            "its values into the fields above; it does not run the case.")
        self.saved_cases_combo.currentIndexChanged.connect(self._on_saved_case_selected)
        saved_row.addWidget(self.saved_cases_combo, 1)
        btn_save_case = QPushButton("Save")
        btn_save_case.clicked.connect(self._save_current_as_case)
        saved_row.addWidget(btn_save_case)
        btn_remove_case = QPushButton("Remove")
        btn_remove_case.clicked.connect(self._remove_saved_case)
        saved_row.addWidget(btn_remove_case)
        # The row's slack goes at the END, not on the buttons: in a
        # `QHBoxLayout` an 80px-text "Remove" stretched up to the QSS
        # width ceiling of 550px. `setSizePolicy(Fixed)` does NOT fix this:
        # with the stylesheet applied the buttons keep growing to
        # `max-width` even with Fixed policy (verified in the assembled
        # window: policy=Fixed, hint=80, width=550). Removing the slack is
        # what works, and it's the same fix already used in
        # `widgets.LongitudinalInput`.
        saved_row.addStretch(1)
        layout.addWidget(saved_box)

        # --- worker thread (docs/plano_v3.md Part 2): same infra as
        # Run Batch, "for free" — Run Case rarely stalls, but this avoids
        # any perceptible window freeze. Progress is indeterminate (a
        # single case has no "N/M" worth showing).
        prog_row = QHBoxLayout()
        self.progress = QProgressBar(); self.progress.setVisible(False)
        self.btn_cancel = QPushButton("Cancel"); self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel)
        prog_row.addWidget(self.progress, 1)
        prog_row.addWidget(self.btn_cancel)
        layout.addLayout(prog_row)
        self._thread: QThread | None = None
        self._worker: BatchRunnerWorker | None = None

        results_header_row = QHBoxLayout()
        # The table is ALWAYS complete (includes the `cfg_*` configuration
        # echo): the old "Show configuration echo" checkbox hid, by default,
        # the only proof of WHICH configuration that number came from, and
        # anyone who didn't know the checkbox existed never saw it. Scrolling
        # a few dozen extra lines costs less than reading a result without
        # knowing the config that produced it.
        # Just the title. The sentence that explained the table ("full table,
        # configuration echo included...") described what the table itself
        # already shows, and still got cut off at the available width.
        results_header_row.addWidget(QLabel("<b>Results</b>"))
        results_header_row.addStretch(1)
        layout.addLayout(results_header_row)
        self.results_table = QTableWidget(0, 2)
        self.results_table.setHorizontalHeaderLabels(["Quantity", "Value"])
        # Columns sized to their CONTENT, not stretched to the edge: with
        # `Stretch` the two split the tab's whole width and the value ended
        # up half a screen away from the quantity name it answers for. The
        # last column stops stretching for the same reason.
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        # Both columns left-aligned, header matching the content
        # (empty set of numeric columns).
        align_headers_with_content(self.results_table, set())
        # Let the table grow with its content (don't cut off rows)
        self.results_table.setSizeAdjustPolicy(
            QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.results_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        # The 1, 2, 3… numbering doesn't identify anything (the row's
        # identity is the quantity, in column 0) and eats up dozens of
        # pixels of width.
        self.results_table.verticalHeader().setVisible(False)
        self._symbol_delegate = _RichSymbolDelegate(self.results_table)
        self.results_table.setItemDelegateForColumn(0, self._symbol_delegate)
        self._row_keys: list[str | None] = []
        # The event filter has to go on the VIEWPORT: `QTableWidget` is a
        # `QAbstractScrollArea`, and Qt delivers Enter/MouseMove to the
        # viewport, not the outer widget: installed on the widget, the
        # tooltip never fired with a real mouse (only when a test sent the
        # event by hand). `rowAt()` also expects viewport coordinates.
        install_instant_tooltip(self.results_table.viewport(), self._row_tooltip)
        layout.addWidget(self.results_table)

        # --- quick export buttons (enabled after the run) ------------------
        export_row = QHBoxLayout()
        self.btn_export_csv = QPushButton("⬇ Export CSV")
        self.btn_export_csv.setToolTip("Saves results.csv to the project's outputs/ folder")
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(self._export_case_csv)
        self.btn_export_tsv = QPushButton("⬇ Export TSV")
        self.btn_export_tsv.setToolTip("Saves results.tsv to the project's outputs/ folder")
        self.btn_export_tsv.setEnabled(False)
        self.btn_export_tsv.clicked.connect(self._export_case_tsv)
        export_row.addWidget(self.btn_export_csv)
        export_row.addWidget(self.btn_export_tsv)
        export_row.addStretch(1)   # slack goes at the end, not on the buttons
        layout.addLayout(export_row)
        layout.addStretch(1)

        self.state.mode_changed.connect(self._refresh_mode_defaults)
        self.state.project_changed.connect(self._refresh_saved_cases_combo)
        # Order matters: the unit (mu_x/J_x, alpha/Vz) has to be decided
        # before writing the value, or the number lands on the wrong scale.
        self.state.project_changed.connect(self._refresh_mode_defaults)
        self.state.project_changed.connect(self._adopt_project_condition)
        self._refresh_mode_defaults()
        self._refresh_saved_cases_combo()

    def _size_field(self, field) -> None:
        """Fixes the same width for condition fields in both tabs."""
        combo = getattr(field, "unit_combo", None)
        spin = getattr(field, "spin", field)
        if combo is not None:
            combo.setFixedWidth(condition_unit_width())
            spin.setFixedWidth(CONDITION_VALUE_WIDTH)
            combo._width_capped = True
            spin._width_capped = True
            if field.layout() is not None:
                field.layout().setSpacing(CONDITION_ROW_SPACING)
        else:
            spin.setFixedWidth(CONDITION_VALUE_WIDTH)
            spin._width_capped = True

    def _with_unit_indent(self, spin) -> QWidget:
        """Aligns the plain number to the composite widgets' column."""
        container = QWidget()
        box = QHBoxLayout(container)
        box.setContentsMargins(condition_unit_width() + CONDITION_ROW_SPACING, 0, 0, 0)
        box.setSpacing(0)
        box.addWidget(spin)
        box.addStretch(1)
        container.setToolTip(spin.toolTip())
        spin._help_container = container
        #: mark read by `common.apply_condition_unit_width`
        #: to re-adjust the indent along with the combo's width
        container._unit_indent = True
        return container

    def showEvent(self, event):
        """Re-measures the unit combos' width on the FIRST show.

        Only here does their `sizeHint` already reflect the theme's font
        and padding (the QSS polish happens on display). Measured at
        construction, the number came out short and "alpha [deg]" got cut
        off on screens with a different font or scale."""
        super().showEvent(event)
        if not getattr(self, "_unit_width_reviewed", False):
            self._unit_width_reviewed = True
            apply_condition_unit_width(self)

    def _advance_context(self):
        """Given to LongitudinalInput to convert mu_x<->V when the unit
        changes (depends on this tab's current rpm and radius)."""
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.rpm_spin.value(), radius_m

    def _axial_context(self):
        """Given to AxialInput to convert alpha<->Vz when the unit
        changes (depends on this tab's current mu_x/rpm/radius)."""
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.advance.mu_x(), self.rpm_spin.value(), radius_m

    # --- column axis convention (rotor vs. propeller) ---------------------
    def _propeller_mode(self) -> bool:
        return bool(self.state.is_propeller()) if self.state is not None else False

    def _symbols(self) -> dict:
        """Column symbols/descriptions in the mode's axis convention.

        In propeller mode the x axis is the rotor's, so `Vz` reads as
        V_inf,x and `J_z` reads as J_x (see `api.summary_symbols`). The
        on-screen table and the report table read from the SAME source,
        since two answers for the same column would be worse than one wrong
        one."""
        return {
            key: (symbol, api._description_with_symbols(description))
            for key, (symbol, description)
            in api.summary_symbols(self._propeller_mode()).items()
        }

    def _trim_mode_key(self):
        return self._RUN_MODE_TO_TRIM.get(self.run_mode_combo.currentText())

    def _update_run_mode_visibility(self, _text=None):
        trim_mode = self._trim_mode_key()
        # "solve_collective" solves collective (it disappears here, it's an
        # output, not an input) while keeping RPM fixed (still editable);
        # "solve_rpm" is the mirror of that.
        set_row_visible(self._run_form, self.collective_spin, trim_mode != "solve_collective")
        set_row_visible(self._run_form, self.rpm_spin, trim_mode != "solve_rpm")
        is_trim = trim_mode is not None
        set_row_visible(self._run_form, self.trim_target_kind_combo, is_trim)
        set_row_visible(self._run_form, self.trim_target_value, is_trim)

    def _refresh_mode_defaults(self):
        propeller = self.state.is_propeller()
        self.advance.set_default_unit(propeller)
        self.axial.set_default_unit(propeller)
        # Label and help follow the mode's CONVENTION: on a propeller the
        # flight speed is axial, and the longitudinal field (labeled
        # "Advance" in either mode) invited putting the aircraft's speed
        # there -- which enters as edgewise flow and produces the solution
        # for an edgewise rotor. See `common.condition_label_and_tooltip`.
        for field, slot in ((self.advance, "inplane"), (self.axial, "axial")):
            label, tip = condition_label_and_tooltip(propeller, slot)
            field.setToolTip(tip)
            set_row_label(self._condition_form, field, label)

    def _adopt_project_condition(self):
        """Starts from the PROJECT's condition, not a fixed number in code.

        This tab's defaults used to be constants (mu_x=0.2, collective=8°,
        600 RPM) independent of the open project. On an 8.18 m rotor, 600
        RPM gives 514 m/s at the tip (Mach 1.5, 1.8 on the advancing
        side): opening a medium-size helicopter and pressing "Run Case"
        silently computed a supersonic rotor, outside any model this
        solver covers. 600 RPM is reasonable only for a small rotor, which
        happened to be the one in the example project the number was
        chosen from.

        The project's first saved case is the best available definition of
        "a sensible condition for THIS rotor": it's what the project's
        own author saved. Without saved cases, the fields stay as they
        are: inventing an RPM from the radius would be guessing, and
        `validation` already warns when the tip exceeds the valid regime.
        """
        project_state = self.state.project
        if project_state is None or not project_state.saved_cases:
            return
        saved_case = project_state.saved_cases[0]
        if saved_case.rpm:
            self.rpm_spin.setValue(float(saved_case.rpm))
        self.collective_spin.setValue(saved_case.collective_deg)
        apply_condition_pair(self.advance, self.axial, saved_case.mu_x, saved_case.Vz,
                                 self.rpm_spin.value(), project_state.geometry.radius_m)

    def _current_condition(self) -> FlightCondition:
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        mu_x, Vz = resolve_condition_pair(self.advance, self.axial,
                                           self.rpm_spin.value(), radius_m)
        return FlightCondition(name="case", mu_x=mu_x,
                                collective_deg=self.collective_spin.value(),
                                Vz=Vz, rpm=self.rpm_spin.value())

    # --- saved cases (docs/plano_v3.md Part 3.2) -------------------------

    def _refresh_saved_cases_combo(self):
        self.saved_cases_combo.blockSignals(True)
        self.saved_cases_combo.clear()
        self.saved_cases_combo.addItem("(none selected)")
        cases = self.state.project.saved_cases if self.state.project else []
        for c in cases:
            self.saved_cases_combo.addItem(c.name)
        self.saved_cases_combo.blockSignals(False)

    def _on_saved_case_selected(self, index: int):
        if index <= 0 or self.state.project is None:
            return
        case = self.state.project.saved_cases[index - 1]
        # Saved cases always keep the canonical representation (mu_x, Vz)
        # -- when loading, we display it in that same convention (mu_x/alpha
        # or J_x/Vz, per the project's is_propeller), without forcing the
        # user to recheck the unit every time they switch cases.
        self.advance.set_default_unit(self.state.is_propeller())
        self.axial.set_default_unit(self.state.is_propeller())
        if case.rpm is not None:
            self.rpm_spin.setValue(case.rpm)
        apply_condition_pair(self.advance, self.axial, case.mu_x, case.Vz,
                                 self.rpm_spin.value(),
                                 self.state.project.geometry.radius_m)
        self.collective_spin.setValue(case.collective_deg)

    def _save_current_as_case(self):
        if not require_project(self, self.state):
            return
        name, ok = QInputDialog.getText(self, "Save Case", "Case name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        condition = self._current_condition()
        condition.name = name
        cases = self.state.project.saved_cases
        for i, c in enumerate(cases):
            if c.name == name:
                cases[i] = condition
                break
        else:
            cases.append(condition)
        self._refresh_saved_cases_combo()
        self.saved_cases_combo.setCurrentText(name)

    def _remove_saved_case(self):
        idx = self.saved_cases_combo.currentIndex()
        if idx <= 0 or self.state.project is None:
            return
        del self.state.project.saved_cases[idx - 1]
        self._refresh_saved_cases_combo()

    def _run_case(self):
        if not require_project(self, self.state):
            return
        if not confirm_run_despite_issues(self, self.state):
            return
        condition = self._current_condition()
        # Results history label (docs/plano_v3.md Part 4.1): uses the
        # selected saved case's name, if any; otherwise none (the final
        # label comes from `describe_case_settings` over the result, in
        # `_on_run_finished`). Compare against the combo's literal item
        # ("(none selected)", see `_refresh_saved_cases_combo`). It used
        # to compare against a Portuguese string the combo never held, so
        # this branch never fired and every case without a saved name
        # ended up as "(none selected)" in the history instead of the
        # condition's summary.
        combo_text = self.saved_cases_combo.currentText()
        self._pending_label = combo_text if combo_text and combo_text != "(none selected)" else None

        trim_mode = self._trim_mode_key()
        if trim_mode is not None:
            target_kind = "thrust" if self.trim_target_kind_combo.currentText().startswith("Thrust") else "CT"
            self._worker = BatchRunnerWorker(self.state.project, trim={
                "condition": condition, "trim_mode": trim_mode,
                "target_kind": target_kind, "target_value": self.trim_target_value.value(),
            })
        else:
            batch = BatchDefinition(name="run_case_gui", conditions=[condition])
            self._worker = BatchRunnerWorker(self.state.project, batch=batch)
        self._worker.case_finished.connect(self._on_case_finished)
        self._worker.finished.connect(self._on_run_finished)
        self._worker.failed.connect(self._on_run_failed)
        self.btn_run_case.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self._thread = launch_worker(self._worker)

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)

    def _on_case_finished(self, _index: int, _total: int, result_or_exc: object):
        if isinstance(result_or_exc, Exception):
            show_error(self, "Error running case", result_or_exc)

    def _on_run_finished(self, results: list):
        self._reset_run_ui()
        if results:
            result = results[0]
            self.state.last_results = result
            self._case_results = result   # kept for quick export
            self._show_summary(result.summary)
            self.state.notify_results()
            settings_desc = describe_case_settings(result.summary)
            saved_name = getattr(self, "_pending_label", None)
            label = f"{saved_name} ({settings_desc})" if saved_name else settings_desc
            self.state.add_history_entry(kind="case", label=label, results=result)
            self.btn_export_csv.setEnabled(True)
            self.btn_export_tsv.setEnabled(True)

    def _on_run_failed(self, message: str):
        self._reset_run_ui()
        QMessageBox.critical(self, "Error running case", message)

    def _reset_run_ui(self):
        self.progress.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.btn_run_case.setEnabled(True)
        self._thread = None
        self._worker = None

    def _outdir(self) -> str:
        """The loaded project's outputs/ folder (created if missing).

        Delegates to `api.project_outputs_dir`, the canonical definition.
        This method used to assemble `Path(project.path) / "outputs"` by
        hand, one of four places where the same literal was repeated."""
        return api.project_outputs_dir(self.state.project, create=True)

    def _quick_export(self, sep: str, ext: str):
        res = getattr(self, "_case_results", None)
        if res is None:
            QMessageBox.warning(self, "Nothing to export", "Run a case first.")
            return
        try:
            path = api.export_results_tabular(res, self._outdir(), sep=sep)
            QMessageBox.information(self, "Exported",
                                    f"File saved at:\n{path}")
        except Exception as exc:
            show_error(self, f"Error exporting {ext.upper()}", exc)

    def _export_case_csv(self):
        self._quick_export(",", "csv")

    def _export_case_tsv(self):
        self._quick_export("\t", "tsv")

    #: Result-table groups. The SET of quantities and the order WITHIN each
    #: group come from `api.SUMMARY_PRIMARY_KEYS`, the same tuple that
    #: orders the HTML report's matrix and the Results tab's table (see
    #: `_build_groups`). Only the GROUPING and the order of groups relative
    #: to each other, which is what changes between rotor and propeller,
    #: is decided here.
    #:
    #: This tab used to keep a second opinion on the order ("mu_x, J_x,
    #: Vz, J_z, alpha...") and on the set: it hid the coefficient family of
    #: the OTHER convention (no CT_prop on a rotor, no FM on a propeller)
    #: and never showed mu_x/J_x/mu_z/lambda_z nor the propeller's
    #: induced/profile terms. The engine always computes both conventions
    #: (`bemt.aggregate_results`), the CSV exports both, and the report
    #: shows both -- hiding them here made the tab the only one of the
    #: three surfaces with less information, with no warning.
    #: `rotor_rpm` stays out: it's the SAME number as `rpm`, already listed
    #: under "Flight condition", and two identical rows under different
    #: names only make one look for a difference that doesn't exist.
    #: x first (the MAIN component in both modes), then z, then the two
    #: angles. `mu_x`/`J_x` used to appear TWICE here: they were distinct
    #: keys in the engine (`mu`+`mu_x`) that standardization merged into a
    #: single name. The old list listed both, and the tab showed the same
    #: quantity on two consecutive rows, under the same symbol.
    _CONDITION_GROUP = ("Flight condition",
                       ["mu_x", "J_x", "Vx",
                        "mu_z", "J_z", "Vz", "lambda_z",
                        "alpha_rotor_deg", "alpha_disk_deg",
                        "collective_deg", "rpm"])
    _INFLOW_GROUP = ("Inflow (solved)", ["lambda_i", "lambda_total", "Vi", "Vz_total"])
    _GEOMETRY_GROUP = ("Rotor geometry (resolved)",
                        ["rotor_R", "rotor_D", "rotor_Nb", "rotor_Omega",
                         "rotor_OmegaR", "rotor_rpm"])
    _ROTOR_COEF_GROUP = ("Rotor coefficients — thrust / torque / power",
                         ["CT", "CQ", "CP", "CPi", "CPp", "FM"])
    _ROTOR_HUB_GROUP = ("Rotor coefficients — hub forces and moments",
                        ["CH", "CHi", "CHp", "CY", "CMx", "CMy"])
    _PROPELLER_COEF_GROUP = ("Propeller coefficients",
                          ["CT_prop", "CQ_prop", "CP_prop", "eta_prop"])
    _DIM_TQP_GROUP = ("Dimensional — thrust / torque / power",
                      ["Thrust", "Torque", "Power", "Power_i", "Power_p"])
    _DIM_HUB_GROUP = ("Dimensional — hub forces and moments",
                       ["H", "Hi", "Hp", "Y", "Mx", "My"])
    _CONVERGENCE_GROUP = ("Convergence",
                           ["convergence_pct", "mean_iter", "elapsed_s",
                            "solver", "inflow_coupling"])

    #: Rotor and propeller show the SAME set in the SAME order as the
    #: Results tab/report table. The propeller convention stays identified
    #: by its own header, without swapping column position between modes.
    _GROUPS_ROTOR = (
        _CONDITION_GROUP, _INFLOW_GROUP,
        _ROTOR_COEF_GROUP, _ROTOR_HUB_GROUP, _PROPELLER_COEF_GROUP,
        _DIM_TQP_GROUP, _DIM_HUB_GROUP,
        _GEOMETRY_GROUP, _CONVERGENCE_GROUP,
    )
    _GROUPS_PROPELLER = (
        _CONDITION_GROUP, _INFLOW_GROUP,
        _ROTOR_COEF_GROUP, _ROTOR_HUB_GROUP, _PROPELLER_COEF_GROUP,
        _DIM_TQP_GROUP, _DIM_HUB_GROUP,
        _GEOMETRY_GROUP, _CONVERGENCE_GROUP,
    )

    @classmethod
    def _build_groups(cls, propeller: bool) -> tuple:
        """Groups with keys REORDERED by `api.SUMMARY_PRIMARY_KEYS`.

        The ordering is done here, not by hand in the lists above, because
        that's what keeps the tab from developing a second opinion: moving
        a quantity in `api._MAIN_COLUMNS` moves it here too, with no
        edit needed. A key not (yet) in the main tuple goes to the end of
        its group, preserving the order it was written in, so it never
        disappears."""
        primary_order_pos = {k: i for i, k in enumerate(api.SUMMARY_PRIMARY_KEYS)}
        end = len(primary_order_pos)
        base = cls._GROUPS_PROPELLER if propeller else cls._GROUPS_ROTOR
        return tuple(
            (title, sorted(keys, key=lambda k: primary_order_pos.get(k, end)))
            for title, keys in base)

    def _show_summary(self, summary: dict):
        """Shows the grouped summary, in the project's convention, with the
        SAME symbols/units/tooltips as the Results tab and the HTML report
        (via `api.SUMMARY_SYMBOLS`/`SUMMARY_UNITS`/`format_summary_value`).
        This table used to keep its own labels and formatting (`.6g`), a
        second hand-kept copy that could diverge from the report.

        The quantities and the order within each group come from
        `api.SUMMARY_PRIMARY_KEYS` (see `_build_groups`): the set is the
        same as the report's and the Results tab's, for rotor and
        propeller.

        The configuration echo (`cfg_*`) is ALWAYS included, at the end:
        there's no key left hidden behind a checkbox anymore (see
        `__init__`)."""
        groups = self._build_groups(self.state.is_propeller())
        cfg_keys = sorted(k for k in summary if k.startswith("cfg_"))
        if cfg_keys:
            groups = groups + (("Configuration echo (cfg_*)", cfg_keys),)

        # (plain label, HTML label | None, value, is_header)
        rows: list[tuple[str, str | None, str, bool]] = []
        self._row_keys: list[str | None] = []      # summary key per row, for tooltip; None = header
        for title, keys in groups:
            present = [k for k in keys if k in summary]
            # The output table shows only the angle belonging to the mode:
            # rotor uses alpha_rotor and propeller uses alpha_disk. The
            # other stays in the internal summary for conversion/CSV, but
            # isn't duplicated in the UI or the report (which applies the
            # same rule).
            hidden_angle = ("alpha_rotor_deg" if self.state.is_propeller()
                             else "alpha_disk_deg")
            present = [k for k in present if k != hidden_angle]
            if "rotor_rpm" in present:
                rpm = summary.get("rpm")
                rotor_rpm = summary.get("rotor_rpm")
                try:
                    echo_redundant = (
                        rpm is not None and rotor_rpm is not None
                        and abs(float(rpm) - float(rotor_rpm))
                        <= 1e-9 * max(1.0, abs(float(rotor_rpm))))
                except (TypeError, ValueError):
                    echo_redundant = False
                if echo_redundant:
                    present.remove("rotor_rpm")
            if not present:
                continue
            rows.append((title, None, "", True))
            self._row_keys.append(None)
            for k in present:
                symbol, _ = self._symbols().get(k, (k, k))
                unit = api.SUMMARY_UNITS.get(k, "")
                suffix = f" [{unit}]" if unit and unit != "-" else ""
                rows.append((symbol_to_plain_text(symbol) + symbol_to_plain_text(suffix),
                               symbol + suffix,
                               api.format_summary_value(summary[k]), False))
                self._row_keys.append(k)

        self.results_table.setRowCount(len(rows))
        for i, (label, label_html, value, is_header) in enumerate(rows):
            item_label = QTableWidgetItem(label)
            item_value = QTableWidgetItem(value)
            # Value on the LEFT, next to the label. It used to go on the
            # right (decimals aligned), but with both columns stretched to
            # the edge the "quantity ... value" pair ended up separated by
            # a gap of hundreds of pixels, and reading one row required
            # sweeping the screen. With the columns sized by content
            # (below), the numbers are short and close, and reading the
            # pair goes back to being a single eye movement.
            item_value.setTextAlignment(TEXT_ALIGN)
            if label_html is not None:
                # the plain text stays as the display role (copy, tests);
                # the delegate paints the rich version over it
                item_label.setData(HTML_SYMBOL_ROLE, label_html)
            if is_header:
                font = item_label.font()
                font.setBold(True)
                item_label.setFont(font)
                item_label.setFlags(Qt.ItemFlag.NoItemFlags)
                item_value.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results_table.setItem(i, 0, item_label)
            self.results_table.setItem(i, 1, item_value)

    def _row_tooltip(self, pos):
        """Text of the instant tooltip for the row under `pos` (table
        VIEWPORT coordinates): symbol, unit, full name/description, and
        the raw `Results.summary` key -- the same name that appears in the
        exported CSV and the report, so the user can connect the on-screen
        row to the file's column. Everything comes from
        `api.SUMMARY_SYMBOLS`/`SUMMARY_UNITS` (the HTML report's tables).
        No description is written here."""
        row = self.results_table.rowAt(pos.y())
        if row < 0 or row >= len(self._row_keys):
            return None
        key = self._row_keys[row]
        if key is None:
            return None
        symbol, description = self._symbols().get(key, (key, key))
        unit = api.SUMMARY_UNITS.get(key, "")
        return (f"<b>{symbol}</b>{f' [{unit}]' if unit and unit != '-' else ''}"
                f"<br>{description}<br><i>summary key: {key}</i>")


