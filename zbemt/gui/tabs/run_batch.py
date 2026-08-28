"""Implement the Run Batch GUI tab.

The tab accepts an active project, sweep definitions, fixed flight-condition values,
and optional saved batches. It generates factorial or explicit conditions, places
them in a reviewable queue, and executes the queue with progress and cancellation.
Outputs are queued conditions, worker signals, and in-memory results; project I/O
and solver execution cross the ``api.py`` boundary. Display-axis labels follow the
nomenclature contract while the model retains disk-axis keys. The tab does not
change the aerodynamic model and remains subject to project validation and engine
convergence limits.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

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
    QCheckBox,
    QDoubleSpinBox,
    QRadioButton,
    QButtonGroup,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QProgressBar,
    QProgressDialog,
    QInputDialog,
    QAbstractItemView,
    QApplication,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QCursor

from ... import api
from ...models import FlightCondition, BatchDefinition

from ..common import (
    parse_list,
    parse_list_reporting,
    AppState,
    condition_label_and_tooltip,
    set_row_label,
    show_error,
    require_project,
    confirm_run_despite_issues,
    set_row_visible,
    describe_batch_settings,
    condition_unit_width,
    apply_condition_unit_width,
    equalize_button_widths,
    resolve_condition_pair,
)
from ..workers import BatchRunnerWorker, launch_worker
from ..widgets import (LongitudinalInput, AxialInput, CONDITION_UNITS,
                        unit_label_variable,
                        configure_unit_combo)


class RunBatchTab(QWidget):
    # Each axis picks a logical SLOT: "inplane" (mu_x OR J_x) and
    # "axial" (alpha_deg OR Vz) group two representations of the same
    # quantity (Section 6c of bemt.py). The unit within the slot is chosen by
    # a second dropdown, never by two competing axes.
    _AXIS_SLOTS = [
        ("(none)", None),
        ("Edgewise (in-plane) Flow", "inplane"),
        ("Axial (along-shaft) Flow", "axial"),
        ("Collective", "collective_deg"),
        ("RPM", "rpm"),
    ]

    #: Name of each axis slot in PROPELLER mode. The decomposition is the
    #: same (`mu_x` in the disk plane, `Vz` along the shaft), but which one
    #: carries the flight speed swaps places: on a propeller in straight
    #: flight it's the AXIAL component. Labeled "Advance" in both modes,
    #: the longitudinal axis invited sweeping the aircraft's speed there,
    #: and the result would be an edgewise-flow sweep. Only the LABEL
    #: changes. The slot (and what's written into the condition) stays the
    #: same.
    _AXIS_SLOTS_PROPELLER = {
        "inplane": "Cross (in-plane) Flow",
        "axial": "Axial (along-shaft) Flow",
    }

    _SLOT_TOOLTIPS = {
        False: {
            "inplane": "Edgewise (in-plane) Flow: vehicle-axis component V<sub>x</sub> that sweeps across the disk.",
            "axial": "Axial (along-shaft) Flow: vehicle-axis component V<sub>z</sub> along the rotor shaft.",
        },
        True: {
            "inplane": "<b>Cross (in-plane) Flow</b><br>V<sub>z</sub> crosses the propeller shaft.<br>Zero in straight cruise.<br>Aircraft airspeed V<sub>x</sub> belongs in the axial field.",
            "axial": "<b>Axial (along-shaft) Flow</b><br>V<sub>x</sub> is the aircraft airspeed along the shaft.<br>This is the propeller advance direction.",
        },
    }

    def _rename_axis_slots(self, is_propeller: bool) -> None:
        """Rewrites the slot combos' text in the mode's convention,
        preserving each row's choice (the index doesn't change -- only the
        displayed label)."""
        for slot_combo, _unit, _values in getattr(self, "axis_rows", []):
            for index, (rotor_label, slot) in enumerate(self._AXIS_SLOTS):
                text = (self._AXIS_SLOTS_PROPELLER.get(slot, rotor_label)
                         if is_propeller else rotor_label)
                if slot_combo.itemText(index) != text:
                    slot_combo.setItemText(index, text)
                tip = self._SLOT_TOOLTIPS[bool(is_propeller)].get(
                    slot, "Choose this batch axis.")
                tip = f"<b>{text}</b><br><br>{tip}"
                slot_combo.setItemData(index, tip, Qt.ItemDataRole.ToolTipRole)

    #: Queue columns. The first four are the canonical form of a
    #: `FlightCondition`. "status" is filled in during the run, so the
    #: user sees progress in the SAME table where they reviewed the
    #: cases, instead of a second table that repeated the numbering.
    _QUEUE_COLUMNS = ["#", "name", "μₓ", "V_z [m/s]", "collective [deg]", "RPM", "status"]
    _COL_NAME, _COL_MU, _COL_VV, _COL_COLLECTIVE, _COL_RPM, _COL_STATUS = 1, 2, 3, 4, 5, 6

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        # This was the ONLY tab without `QScrollArea` (Geometry, Airfoil,
        # Config/Engine, and Run Case already used the pattern). Without
        # it, the four stacked stages add up to more height than the
        # window, and Qt squeezes whichever has less priority: the
        # "1. Generate cases" box ended up 89px BELOW its own
        # `minimumSizeHint`, with the four "Fixed values" rows flattened
        # to about 14 px, text cut off, and the spinboxes reduced to a dash.
        # Scrolling is the right behavior: no control needs to shrink for
        # the content to fit.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        layout.addWidget(self._build_generate_step())
        layout.addWidget(self._build_queue_step(), stretch=1)
        layout.addWidget(self._build_run_step())
        layout.addWidget(self._build_export_step())
        # After the four stages: the buttons it equalizes are born in
        # three different boxes.
        self._equalize_action_buttons()

        self._thread: QThread | None = None
        self._worker: BatchRunnerWorker | None = None
        self._run_label = ""

        self.state.project_changed.connect(self._on_project_changed)
        self.state.mode_changed.connect(self._refresh_mode_defaults)
        self._refresh_mode_defaults()
        self._on_axes_changed()
        self._update_queue_label()

    # =====================================================================
    # Stage 1 -- generate cases (the two modes, side by side)
    # =====================================================================

    def _build_generate_step(self) -> QGroupBox:
        box = QGroupBox("1. Generate cases")
        vbox = QVBoxLayout(box)

        # Mode selector. The two modes are peers: neither is "advanced".
        # The explicit list used to live in a closed collapsible group,
        # labeled "(advanced)" -- which hid half the functionality from
        # anyone who didn't know it existed.
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.radio_factorial = QRadioButton("Factorial analysis")
        self.radio_factorial.setToolTip(
            "Combines 1 to 3 axes (Cartesian product). Example: 3 values of mu_x "
            "× 4 of collective = 12 cases.")
        self.radio_list = QRadioButton("Case by case")
        self.radio_list.setToolTip(
            "Adds one case at a time, with manually chosen values.")
        self.radio_factorial.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_factorial, 0)
        self.mode_group.addButton(self.radio_list, 1)
        mode_row.addWidget(self.radio_factorial)
        mode_row.addWidget(self.radio_list)
        mode_row.addStretch(1)
        vbox.addLayout(mode_row)

        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self._build_factorial_editor())
        self.mode_stack.addWidget(self._build_case_list_editor())
        # `toggled`, not `idClicked`: `idClicked` only fires on a user
        # click, so checking the radio button from code (and a test does
        # that) left the panel and the button text telling a different
        # story.
        self.radio_factorial.toggled.connect(
            lambda checked: (self.mode_stack.setCurrentIndex(0 if checked else 1),
                             self._update_generate_action()))
        vbox.addWidget(self.mode_stack)

        acao_row = QHBoxLayout()
        self.btn_generate = QPushButton(self._GENERATE_LABELS[0])
        self.btn_generate.clicked.connect(self._generate_cases)
        acao_row.addWidget(self.btn_generate)
        self.check_replace_queue = QCheckBox("Replace queue")
        self.check_replace_queue.setChecked(True)
        self.check_replace_queue.setToolTip(
            "Checked: generating replaces the queue with the cases generated now.\n"
            "Unchecked: the cases are ADDED to what's already in the queue "
            "-- this is how you mix a factorial with individual cases.\n"
            "The line beside the box always states which of the two will happen.")
        # The checkbox does nothing WHEN CLICKED -- it only changes what
        # the button next to it will do afterward. Without immediate
        # feedback it reads as broken ("replace queue doesn't work"), so
        # SOMETHING on screen has to change the instant it's clicked.
        #
        # That feedback used to live in the button text ("Generate cases →
        # replace queue"), but the button's label went back to being just
        # the action's name (item 5: the tab's four buttons share the same
        # short label and the same width). The announcement moves to the
        # the echo beside the checkbox, which is where the decision is made,
        # and it still changes on click.
        self.check_replace_queue.toggled.connect(lambda _c: self._update_generate_action())
        acao_row.addWidget(self.check_replace_queue)
        self.lbl_queue_effect = QLabel()
        self.lbl_queue_effect.setStyleSheet("color: gray;")
        acao_row.addWidget(self.lbl_queue_effect)
        acao_row.addStretch(1)
        vbox.addLayout(acao_row)
        self._update_generate_action()
        return box

    def _build_factorial_editor(self) -> QWidget:
        panel = QWidget()
        fbox = QVBoxLayout(panel)
        fbox.setContentsMargins(0, 0, 0, 0)

        # The run mode comes BEFORE the axes, in stage 1.
        #
        # It used to live in stage "3. Run", after the queue was already
        # assembled, and that was the reported confusion: the user built
        # cases sweeping RPM and only found out down there that the "Fixed
        # CT" mode was going to solve RPM, making the sweep they'd just
        # written irrelevant. The mode is a decision about WHICH CASES
        # EXIST, so it belongs to the step where the cases are built, as
        # in the Run Case tab.
        self._trim_form = QFormLayout()
        self._layout_field_form(self._trim_form)
        # The mode label states what stays FIXED and what is SOLVED. There
        # used to be two controls ("Entered values/Fixed thrust/Fixed CT"
        # plus "Trim variable"), and the pair had to be read together to
        # know which quantity was still an input -- exactly the reported
        # confusion.
        self.run_mode_combo = QComboBox()
        for label in self._RUN_MODE_LABELS:
            self.run_mode_combo.addItem(label)
        self.run_mode_combo.setToolTip(
            '"trim_mode" — run every generated condition exactly as entered, or let the '
            'trim loop solve one control (collective or RPM) so that all of them hit the '
            'same thrust/CT. The quantity being solved stops being offered as an input.')
        self.trim_target_kind_combo = QComboBox()
        self.trim_target_kind_combo.addItems(["Thrust [N]", "CT [-]"])
        self.trim_target_kind_combo.setToolTip(
            '"target_kind" — whether the target below is a dimensional thrust or a '
            'thrust coefficient')
        self.trim_target_value = QDoubleSpinBox()
        self.trim_target_value.setRange(-1e9, 1e9)
        self.trim_target_value.setDecimals(6)
        self.trim_target_value.setValue(0.1)
        self.trim_target_value.setToolTip(
            '"target_value" — thrust [N] or CT that every generated condition is trimmed to')
        self._trim_form.addRow("Run mode:", self.run_mode_combo)
        self._trim_form.addRow("Target is:", self.trim_target_kind_combo)
        self._trim_form.addRow("Target:", self.trim_target_value)
        fbox.addLayout(self._trim_form)
        self.run_mode_combo.currentIndexChanged.connect(self._update_batch_trim_visibility)

        self.axis_rows = []   # each item: (slot_combo, unit_combo, values_edit)
        for i in range(3):
            row_widget, slot_combo, unit_combo, values_edit, _btn = self._build_axis_row(i + 1)
            fbox.addWidget(row_widget)
            self.axis_rows.append((slot_combo, unit_combo, values_edit))
            slot_combo.currentIndexChanged.connect(self._on_axes_changed)
            unit_combo.currentIndexChanged.connect(self._update_total_cases)
            values_edit.textChanged.connect(self._update_total_cases)

        fixed_box = QGroupBox("Fixed values (what isn't an axis)")
        fixed_form = QFormLayout(fixed_box)
        self._layout_field_form(fixed_form)
        # Item 1: the last row (RPM) touched the box's frame: the
        # group's closing line ran right against the field, and the whole
        # thing read as if it were cut off. `_layout_field_form`
        # zeroes the margins (which is right for the tab's loose forms).
        # Here the form IS the layout of a QGroupBox, and the frame needs
        # slack above and below the content.
        fixed_form.setContentsMargins(0, self._FOLGA_NA_MOLDURA,
                                      0, self._FOLGA_NA_MOLDURA)
        self.fixed_advance = LongitudinalInput(default_mu=0.2)
        self.fixed_advance.set_context_provider(self._fixed_advance_context)
        self.fixed_advance.setToolTip(
            '"mu_x"<br><br>Fixed in-plane velocity ratio for every generated case.<br><br>'
            'Choose μ<sub>x</sub>, J<sub>x</sub>, or V<sub>x</sub> from the unit selector.')
        self.fixed_axial = AxialInput(default_value=0.0)
        self.fixed_axial.set_context_provider(self._fixed_axial_context)
        self.fixed_axial.setToolTip(
            '"Vz"<br><br>Fixed second velocity component for every generated case.<br><br>'
            'Its physical direction follows the selected rotor or propeller mode.')
        self.fixed_collective = QDoubleSpinBox()
        self.fixed_collective.setToolTip(
            '"collective_deg"<br><br>Collective pitch added to blade twist at each radial station.')
        self.fixed_collective.setRange(-10, 30); self.fixed_collective.setValue(8.0)
        self.fixed_collective.setSingleStep(0.5)
        self.fixed_rpm = QDoubleSpinBox()
        self.fixed_rpm.setToolTip(
            '"rpm"<br><br>Rotational speed for every generated case, in revolutions per minute.')
        self.fixed_rpm.setRange(1, 20000); self.fixed_rpm.setValue(600)
        self.fixed_rpm.setSingleStep(10)
        for field in (self.fixed_advance, self.fixed_axial,
                      self.fixed_collective, self.fixed_rpm):
            self._size_field(field)
        # All four rows have their label in the LABEL COLUMN: previously
        # the two composite ones (advance/axial) went in as a spanning
        # row, so their combo-label started at the margin while
        # "Collective [deg]:"/"RPM:" started in the label column, so each
        # row's fields started at a different x, and that's what read as
        # "everything misaligned".
        fixed_form.addRow("Advance:", self.fixed_advance)
        fixed_form.addRow("Axial flow:", self.fixed_axial)
        fixed_form.addRow("Collective [deg]:",
                          self._with_unit_indent(self.fixed_collective))
        fixed_form.addRow("RPM:", self._with_unit_indent(self.fixed_rpm))
        # kept to hide the WHOLE ROW, label included: hiding only the
        # field left "Collective [deg]:" dangling, pointing at nothing
        self._fixed_form = fixed_form
        fbox.addWidget(fixed_box)
        self._fixed_widgets = {
            "inplane": (self.fixed_advance,), "axial": (self.fixed_axial,),
            "collective_deg": (self.fixed_collective,), "rpm": (self.fixed_rpm,),
        }

        self.total_cases_label = QLabel("Total cases: —")
        fbox.addWidget(self.total_cases_label)
        return panel

    #: Field-column widths for this tab's forms. A `QDoubleSpinBox` in a
    #: `QFormLayout` grows to the end of the window by default
    #: (`AllNonFixedFieldsGrow`): a field for ONE number taking up the
    #: whole screen, which is the other side of this box's layout
    #: complaint.
    # The width of the unit-label combo (mu_x/J_x/V, alpha/Vz) is NOT a
    # constant of this tab: it comes from
    # `common.condition_unit_width`, measured in the current
    # font and shared with the Run Case tab. The old fixed 110px cut off
    # "alpha [deg]" in both tabs, and two copies of the number would leave
    # the value column at a different x from one tab to the other.
    #: Width of the from/to/step fields. Fixed and equal across the three
    #: columns so the right edges line up from one axis row to the next.
    #: Left loose, the layout came out 90/90/86 px and the column
    #: looked jagged.
    _RANGE_WIDTH = 92
    #: Horizontal spacing between the unit combo and the spin inside a
    #: composite field (`LongitudinalInput`/`AxialInput`).
    _COMPOSITE_SPACING = 6
    _VALUE_WIDTH = 150        # numeric spinbox
    #: Padding between the content and the frame of an inner `QGroupBox`.
    _FOLGA_NA_MOLDURA = 12
    # The label's padding inside a button lives in `common.BUTTON_MARGIN`
    # (the same value as `ensure_button_legibility`, so the shared width
    # already satisfies the floor it requires) -- see
    # `common.equalize_button_widths`, which this tab and Results
    # share.

    def _layout_field_form(self, form: QFormLayout) -> None:
        """Left-aligned labels and fields sized to their content."""
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)

    def _size_field(self, field) -> None:
        """Fixed widths for a simple field (spinbox) or a composite one
        (unit combo + spinbox), so the value column stays aligned from
        one row to the next."""
        combo = getattr(field, "unit_combo", None)
        spin = getattr(field, "spin", field)
        if combo is not None:
            combo.setFixedWidth(condition_unit_width())
            spin.setFixedWidth(self._VALUE_WIDTH)
            # The global compaction policy runs after the tab is built.
            # Without this flag it would loosen only the composite spin
            # up to 150px, while Collective/RPM stayed at 120px.
            combo._width_capped = True
            spin._width_capped = True
            # EXPLICIT spacing between combo and spin: this is what
            # `_with_unit_indent` reproduces to put simple fields'
            # numbers in the same column. Left at the style's default,
            # the indent would be computed from a value the theme can
            # change.
            layout = field.layout()
            if layout is not None:
                layout.setSpacing(self._COMPOSITE_SPACING)
        else:
            spin.setFixedWidth(self._VALUE_WIDTH)
            spin._width_capped = True

    def _with_unit_indent(self, spin: QDoubleSpinBox) -> QWidget:
        """Wraps a simple field, indenting it to the composite fields'
        NUMBER COLUMN.

        Advance and Axial flow are composite (unit combo + spin), so
        their number starts ``condition_unit_width() +
        _COMPOSITE_SPACING`` px to the right of Collective/RPM's number,
        and the four rows used to end at different x positions (item 4).
        Widening the simple spins to the same edge would be the OPPOSITE
        defect -- a half-screen-wide box to type
        "8", which is exactly what `test_campos_numericos_nao_ocupam_a_largura_toda`
        forbids, rightly so. What moves is the POSITION, not the width.

        The price of the wrapping is that the `QFormLayout` field
        column's widget is no longer the spin, and three things read
        precisely that widget. All three are compensated for here:

        * ``_help_container``: `common.set_row_visible` looks
          up the row by its field widget; without the flag, hiding the
          Collective/RPM row (progressive disclosure of axes and
          trimming) would fail silently, leaving the orphaned label that
          function exists to avoid;
        * the tooltip is COPIED onto the container: it's from there
          that `field_help._widget_field` pulls the `.bemt` field
          name to link the label to the documentation, and that
          `tools/field_index.py` reads to generate the per-tab field
          index;
        * `_field_form` already searched for the spin inside the
          field widget too (`findChildren`), so it still finds the row.
        """
        container = QWidget()
        box = QHBoxLayout(container)
        box.setContentsMargins(
            condition_unit_width() + self._COMPOSITE_SPACING, 0, 0, 0)
        box.setSpacing(0)
        box.addWidget(spin)
        box.addStretch(1)
        container.setToolTip(spin.toolTip())
        spin._help_container = container
        #: flag read by `common.apply_condition_unit_width`
        #: to readjust the indent along with the combo's width
        container._unit_indent = True
        return container

    def _build_case_list_editor(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self._layout_field_form(form)
        self.add_row_advance = LongitudinalInput(default_mu=0.2)
        self.add_row_advance.set_context_provider(self._add_row_advance_context)
        self.add_row_advance.setToolTip(
            '"mu_x"<br><br>In-plane velocity ratio for this case.<br><br>'
            'Choose μ<sub>x</sub>, J<sub>x</sub>, or V<sub>x</sub> from the unit selector.')
        self.add_row_axial = AxialInput(default_value=0.0)
        self.add_row_axial.set_context_provider(self._add_row_axial_context)
        self.add_row_axial.setToolTip(
            '"Vz"<br><br>Second velocity component for this case.<br><br>'
            'Its physical direction follows the selected rotor or propeller mode.')
        self.collective_spin = QDoubleSpinBox()
        self.collective_spin.setToolTip(
            '"collective_deg"<br><br>Collective pitch added to blade twist at each radial station.')
        self.collective_spin.setRange(-10, 30); self.collective_spin.setValue(8.0)
        self.collective_spin.setSingleStep(0.5)
        self.rpm_spin = QDoubleSpinBox()
        self.rpm_spin.setToolTip(
            '"rpm"<br><br>Rotational speed for this case, in revolutions per minute.')
        self.rpm_spin.setRange(1, 20000); self.rpm_spin.setValue(600)
        self.rpm_spin.setSingleStep(10)
        for field in (self.add_row_advance, self.add_row_axial,
                      self.collective_spin, self.rpm_spin):
            self._size_field(field)
        form.addRow("Advance:", self.add_row_advance)
        form.addRow("Axial flow:", self.add_row_axial)
        form.addRow("Collective [deg]:",
                    self._with_unit_indent(self.collective_spin))
        form.addRow("RPM:", self._with_unit_indent(self.rpm_spin))
        # Kept so `_reflect_trim_variable` can hide the whole row
        # (label included) of the quantity the trim loop solves.
        self._case_form = form
        return panel

    #: Generate button label per mode (factorial, case by case). There
    #: are two because the action differs -- one builds the whole
    #: Cartesian product, the other adds ONE case --, but both feed into
    #: the buttons' common width calculation, so the button doesn't
    #: change size when the mode is switched.
    _GENERATE_LABELS = ("Generate Cases", "Add Case")

    def _update_generate_action(self):
        """Syncs the button label and the "Replace queue" box's echo."""
        is_factorial = self.radio_factorial.isChecked()
        self.btn_generate.setText(self._GENERATE_LABELS[0 if is_factorial else 1])
        # adding one case at a time only makes sense accumulating
        self.check_replace_queue.setVisible(is_factorial)
        self.lbl_queue_effect.setVisible(is_factorial)
        self.lbl_queue_effect.setText(
            "→ generating REPLACES the queue"
            if self.check_replace_queue.isChecked()
            else "→ generating APPENDS to the queue")

    def action_buttons(self) -> tuple:
        """The tab's four action buttons, in the order they appear.

        A single place defines the set: the common width comes from
        here, and the invariant test ("the four have the same width, Run
        is wider") reads the same list, instead of repeating the names.
        """
        return (self.btn_generate, self.btn_remove, self.btn_clear, self.btn_export)

    def _equalize_action_buttons(self) -> int:
        """Same width for the four action buttons; "Run" is wider.

        Item 5. The width comes from the FONT METRIC of the longest
        label (and of the TWO labels the generate button alternates
        between, so it doesn't change size when the mode is switched),
        never from a pixel number: this way it keeps holding if the text
         or the font changes -- same principle as
        `common.ensure_button_legibility`, which runs afterward and
        never shrinks anything, only raises a floor this calculation
        already satisfies.

        Two traps the previous version had, which only showed up with
        the THEME applied (that is, in the real window, never in a tab
        instantiated standalone):

        1. `setFixedWidth` does NOT hold anything here. The stylesheet
           declares `QPushButton { max-width: 520px }`, and a QSS width
           rule overrides the maximum fixed in code, so the four buttons
           went back to each growing to its own `sizeHint`, coming out
           at 109, 119, 88, and 88px on screen. That's why what gets
           fixed is the common MINIMUM: each one's `sizeHint` stays
           below it, and the four settle at the same width.
        2. `sizeHint` only includes the theme's padding AFTER the QSS
           polish, which happens on first display. That's why the
           calculation is redone in `showEvent` (see `showEvent`), when
           the numbers are finally the real ones. It also takes
           `sizeHint` into account, instead of assuming a fixed padding
           the theme could change.
        """
        buttons = self.action_buttons()
        width = equalize_button_widths(
            buttons, extra_labels=self._GENERATE_LABELS)
        # "Run" is the button that fires the work, and it's the only one
        # in the tab that isn't in the set of four: wider, by explicit
        # request. Only the MINIMUM is fixed -- the label grows with the
        # case count ("Run 128 case(s)") and a fixed width would elide it.
        self.btn_run.setMinimumWidth(int(width * 1.5))
        return width

    def showEvent(self, event):
        """Redoes, on the FIRST display, the two widths that depend on
        the theme: the buttons' common width and the unit-label combos'
        width.

        Only here does a widget's `sizeHint` already reflect the
        stylesheet's padding (the QSS polish happens on display).
        Calculated before that, the buttons' common width came out
        smaller than the real `sizeHint` and the four settled at
        different widths (`_equalize_action_buttons`), and the
        combos' width came out short, cutting off "alpha [deg]"
        (`common.apply_condition_unit_width`)."""
        super().showEvent(event)
        if not getattr(self, "_widths_reviewed", False):
            self._widths_reviewed = True
            self._equalize_action_buttons()
            apply_condition_unit_width(self)

    # =====================================================================
    # Stage 2 -- the queue (single source of what will run)
    # =====================================================================

    def _build_queue_step(self) -> QGroupBox:
        self.queue_box = QGroupBox("2. Case queue")
        vbox = QVBoxLayout(self.queue_box)

        self.batch_table = QTableWidget(0, len(self._QUEUE_COLUMNS))
        self.batch_table.setHorizontalHeaderLabels(self._QUEUE_COLUMNS)
        self.batch_table.setToolTip(
            "What will be run, in canonical form (<code>mu_x</code>, <code>Vz</code>). "
            "Stage 1 fields accept <code>mu_x</code>/<code>J_x</code> and "
            "<code>alpha</code>/<code>Vz</code>; conversion happens when generating "
            "cases.")
        header = self.batch_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.batch_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # Qt's vertical header would already number the rows: with the
        # "#" column beside it, the number appeared twice
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.setMinimumHeight(180)
        vbox.addWidget(self.batch_table)

        row = QHBoxLayout()
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.setToolTip("Removes the selected row from the queue.")
        self.btn_remove.clicked.connect(self._remove_batch_row)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setToolTip("Empties the queue.")
        self.btn_clear.clicked.connect(self._clear_queue)
        row.addWidget(self.btn_remove)
        row.addWidget(self.btn_clear)
        row.addStretch(1)

        # Presets: the materialized queue is what gets saved. Previously
        # only the explicit list was savable, so a carefully assembled
        # factorial was lost when the project closed.
        row.addWidget(QLabel("Saved in project:"))
        self.batches_combo = QComboBox()
        self.batches_combo.addItem("(none selected)")
        self.batches_combo.setToolTip(
            "Case queues stored with this project. Selecting one replaces the "
            "queue below with its conditions; it does not run anything.")
        self.batches_combo.setMinimumWidth(180)
        self.batches_combo.currentIndexChanged.connect(self._on_saved_batch_selected)
        row.addWidget(self.batches_combo)
        btn_load_batch = QPushButton("load")
        btn_load_batch.setToolTip(
            "Replaces the queue below with the conditions of the selected "
            "batch. Choosing a name in the list does the same; this button "
            "also reloads the name that is ALREADY selected, which is how "
            "you discard edits made to the queue since it was loaded.")
        btn_load_batch.clicked.connect(self._load_selected_batch)
        row.addWidget(btn_load_batch)
        btn_save_batch = QPushButton("save queue")
        btn_save_batch.setToolTip("Saves the current queue as a named batch in the project.")
        btn_save_batch.clicked.connect(self._save_current_as_batch)
        row.addWidget(btn_save_batch)
        btn_remove_batch = QPushButton("remove")
        btn_remove_batch.clicked.connect(self._remove_saved_batch)
        row.addWidget(btn_remove_batch)
        vbox.addLayout(row)
        return self.queue_box

    def _update_queue_label(self):
        n = self.batch_table.rowCount()
        self.queue_box.setTitle(f"2. Case queue ({n})" if n else "2. Case queue (empty)")
        self.btn_run.setEnabled(n > 0)
        self.btn_run.setText(f"▶ Run {n} case(s)" if n else "▶ Run")

    #: The role the authoritative `FlightCondition` of a row is stored
    #: under, on the row-number item of column 0.
    _CONDITION_ROLE = Qt.ItemDataRole.UserRole + 1

    @staticmethod
    def _cell_texts(condition: "FlightCondition", row_number: int) -> dict:
        """The text of every cell of a row, for one condition.

        One place, used both to FILL a row and to decide afterwards
        whether a cell still holds what was filled into it.
        """
        rpm = condition.rpm
        return {
            0: str(row_number),
            RunBatchTab._COL_NAME: condition.name or f"case_{row_number}",
            RunBatchTab._COL_MU: f"{condition.mu_x:.4g}",
            RunBatchTab._COL_VV: f"{condition.Vz:.4g}",
            RunBatchTab._COL_COLLECTIVE: f"{condition.collective_deg:.4g}",
            # An absent RPM is absent, not zero. Written as "0" -- as it
            # was -- it read back as a rotor commanded to stand still,
            # and `rpm=None` means "use the speed the configuration
            # already carries".
            RunBatchTab._COL_RPM: "" if rpm is None else f"{rpm:.5g}",
            RunBatchTab._COL_STATUS: "",
        }

    def _queue_conditions(self) -> list[FlightCondition]:
        conditions, rejected = self._queue_conditions_and_rejects()
        return conditions

    def _queue_conditions_and_rejects(self):
        """Every queued condition, plus every cell that is not a number.

        The stored condition is the starting point and the cells are an
        OVERLAY on it, so a field the table does not show survives, and a
        field the table does show but the user did not touch keeps the
        precision it was created with rather than the four figures its
        own display was rounded to.
        """
        conditions: list[FlightCondition] = []
        rejected: list[str] = []
        for i in range(self.batch_table.rowCount()):

            def txt(col):
                item = self.batch_table.item(i, col)
                return item.text().strip() if item is not None else ""

            marker = self.batch_table.item(i, 0)
            stored = (marker.data(self._CONDITION_ROLE)
                      if marker is not None else None)
            if not isinstance(stored, FlightCondition):
                # A row that predates this (or one built by hand): fall
                # back to the cells, which is all there is.
                stored = FlightCondition()
            filled = self._cell_texts(stored, i + 1)

            def number(col, current, label):
                """The cell, if the user changed it; the stored value if not."""
                shown = txt(col)
                if shown == filled[col]:
                    return current
                if not shown:
                    return None if col == self._COL_RPM else current
                try:
                    return float(shown)
                except ValueError:
                    rejected.append(f"row {i + 1}: {shown!r}")
                    return current

            name = txt(self._COL_NAME) or f"case_{i + 1}"
            conditions.append(replace(
                stored,
                name=name,
                mu_x=number(self._COL_MU, stored.mu_x, "mu_x"),
                Vz=number(self._COL_VV, stored.Vz, "Vz"),
                collective_deg=number(self._COL_COLLECTIVE,
                                       stored.collective_deg, "collective"),
                rpm=number(self._COL_RPM, stored.rpm, "rpm"),
            ))
        return conditions, rejected

    def _fill_queue(self, conditions: list, replace: bool = True):
        if replace:
            self.batch_table.setRowCount(0)
        for c in conditions:
            r = self.batch_table.rowCount()
            self.batch_table.insertRow(r)
            values = self._cell_texts(c, r + 1)
            for col, text in values.items():
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    # The row keeps the condition it was built from. The
                    # five visible columns are a VIEW of it, not the
                    # record: `FlightCondition` has ten fields, and the
                    # five that are not shown used to be replaced by
                    # their defaults every time the queue was read back.
                    item.setData(self._CONDITION_ROLE, c)
                self.batch_table.setItem(r, col, item)
        self._renumber()
        self._update_queue_label()

    def _renumber(self):
        # Only the TEXT is rewritten. The stored condition lives on the
        # same item and must survive a removal from the middle of the
        # queue.
        for i in range(self.batch_table.rowCount()):
            item = self.batch_table.item(i, 0)
            if item is not None:
                item.setText(str(i + 1))

    def _clear_queue(self):
        self.batch_table.setRowCount(0)
        self._update_queue_label()

    def _remove_batch_row(self):
        r = self.batch_table.currentRow()
        if r >= 0:
            self.batch_table.removeRow(r)
            self._renumber()
            self._update_queue_label()

    def _generate_cases(self):
        if not require_project(self, self.state):
            return
        try:
            if self.radio_factorial.isChecked():
                axes, rejected = self._active_axes_and_rejects()
                if rejected:
                    QMessageBox.warning(
                        self, "Unreadable values",
                        "These entries are not numbers, so the batch would "
                        "not contain the cases you wrote:\n\n    "
                        + ", ".join(rejected)
                        + "\n\nCorrect them, or remove them, and generate "
                          "again.")
                    return
                if not axes:
                    QMessageBox.warning(self, "No axis",
                                         "Choose at least 1 axis and specify its values.")
                    return
                conditions = api.build_factorial_conditions(
                    self.state.project, axes, self._factorial_fixed_values())
                self._fill_queue(conditions, replace=self.check_replace_queue.isChecked())
            else:
                self._fill_queue([self._standalone_condition()], replace=False)
        except Exception as exc:
            show_error(self, "Error generating cases", exc)

    def _standalone_condition(self) -> FlightCondition:
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        rpm = self.rpm_spin.value()
        mu_x, Vz = resolve_condition_pair(self.add_row_advance,
                                           self.add_row_axial, rpm, radius_m)
        return FlightCondition(
            name=f"case_{self.batch_table.rowCount() + 1}",
            mu_x=mu_x, Vz=Vz,
            collective_deg=self.collective_spin.value(), rpm=rpm)

    def _factorial_fixed_values(self) -> dict:
        """Only the current representation of the slot that did NOT
        become an axis: mu_x/J_x and alpha_deg/Vz cannot be both axis
        AND fixed at the same time (`studies.build_factorial_conditions`
        itself refuses it)."""
        axis_slots = {self._slot_of_combo(sc) for sc, _uc, _ve in self.axis_rows}
        fixed = {}
        if "inplane" not in axis_slots:
            fixed[self.fixed_advance.variable_name()] = self.fixed_advance.raw_value()
        if "axial" not in axis_slots:
            fixed[self.fixed_axial.variable_name()] = self.fixed_axial.raw_value()
        if "collective_deg" not in axis_slots:
            fixed["collective_deg"] = self.fixed_collective.value()
        if "rpm" not in axis_slots:
            fixed["rpm"] = self.fixed_rpm.value()
        return fixed

    # =====================================================================
    # Stage 3 -- run
    # =====================================================================

    def _build_run_step(self) -> QGroupBox:
        box = QGroupBox("3. Run")
        vbox = QVBoxLayout(box)
        # Run mode / trim variable / target moved from here to stage 1
        # (see `_build_factorial_editor`): they are decisions about
        # WHICH cases exist, and need to be visible while the cases are
        # being assembled. This stage is left with only the run itself.
        self.lbl_modo_corrente = QLabel()
        self.lbl_modo_corrente.setStyleSheet("color: gray;")
        vbox.addWidget(self.lbl_modo_corrente)
        row = QHBoxLayout()
        self.btn_run = QPushButton("▶ Run")
        self.btn_run.clicked.connect(self._run_batch)
        row.addWidget(self.btn_run, 0)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        row.addWidget(self.progress, 1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel)
        row.addWidget(self.btn_cancel)
        # Without this slack at the end of the row, the Run button was
        # stretched to the window's edge whenever the progress bar was
        # hidden (its stretch factor's space fell to the row's only
        # widget): a full-screen-wide button, with nothing to compare
        # the requested width from item 5 against. With the bar visible,
        # the space still all goes to it (factor 1 vs 0).
        row.addStretch(0)
        vbox.addLayout(row)
        self.status_label = QLabel("")
        vbox.addWidget(self.status_label)
        self._update_batch_trim_visibility()
        return box

    #: Mode label -> (quantity SOLVED by the trim loop, `trim_mode` of
    #: `studies.run_batch`). `None` = nothing is solved, runs as entered.
    _RUN_MODE_LABELS = ("Fixed collective & RPM",
                           "Fixed RPM, target thrust/CT",
                           "Fixed collective, target thrust/CT")
    _SOLVED_BY_MODE = {
        "Fixed collective & RPM": (None, None),
        # Fixed RPM => what's left free for the loop to move is collective.
        "Fixed RPM, target thrust/CT": ("collective_deg", "solve_collective"),
        "Fixed collective, target thrust/CT": ("rpm", "solve_rpm"),
    }

    def _trim_variable(self) -> str | None:
        return self._SOLVED_BY_MODE.get(
            self.run_mode_combo.currentText(), (None, None))[0]

    def _trim_spec(self) -> dict | None:
        """Trim dictionary handed to `studies.run_batch`.

        `None` when nothing is solved. Keeps exactly the same keys as
        before this layout reorganization (GUI/.bemt/CLI parity).
        """
        _variable, mode = self._SOLVED_BY_MODE.get(
            self.run_mode_combo.currentText(), (None, None))
        if mode is None:
            return None
        return {
            "trim_mode": mode,
            "target_kind": ("CT" if self.trim_target_kind_combo.currentText().startswith("CT")
                            else "thrust"),
            "target_value": self.trim_target_value.value(),
        }

    def _update_batch_trim_visibility(self):
        """`set_row_visible`, not `setVisible`: with `setVisible`
        only the FIELD disappears and the label stays on screen pointing
        at nothing. Seen in the real window, "Trim variable:" and
        "Target:" were left dangling with no field beside them in
        "Entered values" mode (trap #1 of `common.set_row_visible`'s
        docstring).

        Besides showing/hiding the target, it reflects the mode in the
        assembly fields: the quantity the trim loop is going to SOLVE
        stops being offered as a fixed value, because the number typed
        there would be discarded by the trim loop. That was exactly what
        made the stage confusing.
        """
        solved_variable = self._trim_variable()
        trim = solved_variable is not None
        set_row_visible(self._trim_form, self.trim_target_kind_combo, trim)
        set_row_visible(self._trim_form, self.trim_target_value, trim)
        self._reflect_trim_variable(solved_variable)
        if hasattr(self, "lbl_modo_corrente"):
            if solved_variable is None:
                self.lbl_modo_corrente.setText(
                    "Run mode: collective and RPM as entered (set in step 1).")
            else:
                readable = "collective" if solved_variable == "collective_deg" else "RPM"
                self.lbl_modo_corrente.setText(
                    f"Run mode: solving {readable} for "
                    f"{self.trim_target_kind_combo.currentText()} = "
                    f"{self.trim_target_value.value():g} (set in step 1).")

    def _reflect_trim_variable(self, solved_variable: str | None):
        """Removes from case assembly the quantity the trim loop will
        solve.

        It stops being an INPUT in three places at once: the fixed-value
        field, the case-by-case mode's field, and the axis list -- an
        axis sweeping precisely the quantity the trim loop overwrites
        produces a whole sweep that means nothing. An axis already
        pointed at it reverts to "(none)".
        """
        for variable, fields in (
                ("collective_deg", (getattr(self, "fixed_collective", None),
                                     getattr(self, "collective_spin", None))),
                ("rpm", (getattr(self, "fixed_rpm", None),
                          getattr(self, "rpm_spin", None)))):
            is_solved = (variable == solved_variable)
            for field in fields:
                if field is None:
                    continue
                form = self._field_form(field)
                if form is not None:
                    set_row_visible(form, field, not is_solved)
                else:
                    field.setVisible(not is_solved)

        # Axis list: disables the item and disarms anyone who already chose it.
        for slot_combo, _uc, values_edit in getattr(self, "axis_rows", []):
            for index, (label, slot) in enumerate(self._AXIS_SLOTS):
                if slot not in ("collective_deg", "rpm"):
                    continue
                item = slot_combo.model().item(index)
                if item is None:
                    continue
                item.setEnabled(slot != solved_variable)
            current = self._slot_of_combo(slot_combo)
            if solved_variable is not None and current == solved_variable:
                slot_combo.setCurrentIndex(0)
                values_edit.clear()

    def _field_form(self, field):
        """`QFormLayout` that contains `field`, or None if it isn't in one.

        `set_row_visible` needs the right form; the fixed-value
        fields and the case-by-case mode's fields live in different
        forms.
        """
        for name in ("_fixed_form", "_case_form"):
            form = getattr(self, name, None)
            if form is None:
                continue
            for row_idx in range(form.rowCount()):
                item = form.itemAt(row_idx, QFormLayout.ItemRole.FieldRole)
                if item is None:
                    continue
                w = item.widget()
                if w is field or (w is not None and field in w.findChildren(type(field))):
                    return form
        return None

    def _run_batch(self):
        if not require_project(self, self.state):
            return
        conditions = self._queue_conditions()
        if not conditions:
            QMessageBox.warning(self, "Queue empty",
                                 "Generate or add at least one case in stage 1.")
            return
        if not confirm_run_despite_issues(self, self.state):
            return
        for i in range(self.batch_table.rowCount()):
            self.batch_table.setItem(i, self._COL_STATUS, QTableWidgetItem("in queue"))
        trim_spec = self._trim_spec()
        batch = BatchDefinition(name="fila_gui", conditions=conditions,
                                sweep_params={"trim": trim_spec} if trim_spec else {})
        self._start_run(BatchRunnerWorker(self.state.project, batch=batch),
                         total=len(conditions), label="batch")

    def _start_run(self, worker: BatchRunnerWorker, *, total: int, label: str):
        self.status_label.setText(f"Running {label}: 0/{total}…")
        self.progress.setVisible(True)
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(0)
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)
        self.btn_run.setEnabled(False)
        self.btn_generate.setEnabled(False)
        self._run_label = label
        self._worker = worker
        self._worker.case_finished.connect(self._on_case_finished)
        self._worker.finished.connect(self._on_run_finished)
        self._worker.failed.connect(self._on_run_failed)
        self._thread = launch_worker(worker)

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)
            self.status_label.setText("Canceling…")

    def _on_case_finished(self, index: int, total: int, result_or_exc: object):
        self.progress.setRange(0, total)
        self.progress.setValue(index + 1)
        if index < self.batch_table.rowCount():
            if isinstance(result_or_exc, Exception):
                text = f"ERROR: {result_or_exc}"
            else:
                ct = result_or_exc.summary.get("CT")
                text = f"OK · CT={ct:.4g}" if isinstance(ct, (int, float)) else "OK"
            self.batch_table.setItem(index, self._COL_STATUS, QTableWidgetItem(text))
            self.batch_table.scrollToItem(self.batch_table.item(index, self._COL_STATUS))
        self.status_label.setText(f"Running {self._run_label}: {index + 1}/{total}…")

    def _on_run_finished(self, results: list):
        label = self._run_label
        self._reset_run_ui()
        self.state.last_results = results
        self.status_label.setText(f"{len(results)} case(s) completed ({label}).")
        self.state.notify_results()
        if results:
            settings_desc = describe_batch_settings(results)
            rich_label = f"{label} ({settings_desc})" if label else settings_desc
            self.state.add_history_entry(kind="batch", label=rich_label, results=results)

    def _on_run_failed(self, message: str):
        self._reset_run_ui()
        show_error(self, "Error running batch", RuntimeError(message))

    def _reset_run_ui(self):
        self.progress.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.btn_generate.setEnabled(True)
        self._update_queue_label()
        self._thread = None
        self._worker = None

    # =====================================================================
    # Export
    # =====================================================================

    def _build_export_step(self) -> QGroupBox:
        box = QGroupBox("Export (the Results tab has the complete visualization)")
        eform = QFormLayout(box)
        self.outdir_edit = QLineEdit()
        self.outdir_edit.setToolTip(
            "Folder that receives the exported tables and figures. It defaults "
            "to the project's own outputs/ folder; an existing file of the "
            "same name is never overwritten silently.")
        btn_browse = QPushButton("…")
        btn_browse.clicked.connect(self._browse_outdir)
        outdir_row = QHBoxLayout()
        outdir_row.addWidget(self.outdir_edit)
        outdir_row.addWidget(btn_browse)
        eform.addRow("Output folder:", outdir_row)
        self.plot_checks = {}
        plot_row = QHBoxLayout()
        # The KEY is still the identifier `api.export_results` expects;
        # only the on-screen LABEL stops being that identifier. The boxes
        # used to show literally "coefficients", "azimuth", "span",
        # "disk_map" -- and "span"/"disk_map" alone don't say which
        # figure comes out of each.
        _PLOT_LABEL = {
            "coefficients": ("Coefficients",
                              "Thrust/torque/power coefficients across the queued conditions."),
            "azimuth": ("Azimuthal loads",
                         "Blade load through one revolution, at fixed radial stations."),
            "span": ("Spanwise loads",
                      "Blade load along the radius, at fixed azimuths."),
            "disk_map": ("Disk maps",
                          "Top view of the rotor disk, one map per field."),
        }
        for kind in ("coefficients", "azimuth", "span", "disk_map"):
            label, tip = _PLOT_LABEL[kind]
            cb = QCheckBox(label)
            cb.setToolTip(tip)
            self.plot_checks[kind] = cb
            plot_row.addWidget(cb)
        plot_row.addStretch(1)
        eform.addRow("Plots:", plot_row)
        self.save_csv_check = QCheckBox("Save CSV")
        self.save_csv_check.setChecked(True)
        eform.addRow(self.save_csv_check)
        self.btn_export = QPushButton("Export")
        self.btn_export.clicked.connect(self._export)
        # In a spanning row the button was stretched end to end across
        # the form; with its own width (item 5) it needs a row that just
        # snugs it to the left.
        export_row = QHBoxLayout()
        export_row.addWidget(self.btn_export)
        export_row.addStretch(1)
        eform.addRow(export_row)
        return box

    def _browse_outdir(self):
        path = QFileDialog.getExistingDirectory(self, "Output folder")
        if path:
            self.outdir_edit.setText(path)

    def _export(self):
        if self.state.last_results is None:
            QMessageBox.warning(self, "Nothing to export", "Run a case or batch first.")
            return
        # VISIBLE progress (same rationale as ResultsTab._generate_report/
        # _export_batch_disk_maps): disk-map plots for a whole batch can
        # take tens of seconds running synchronously on the GUI thread --
        # without this, the button just freezes.
        progresso = QProgressDialog(
            "Exporting...\nThis can take a moment for large batches.",
            None, 0, 0, self)
        progresso.setWindowTitle("Exporting")
        progresso.setWindowModality(Qt.WindowModality.ApplicationModal)
        progresso.setMinimumDuration(0)
        progresso.setCancelButton(None)
        progresso.show()
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        QApplication.processEvents()
        try:
            plots_selected = [k for k, cb in self.plot_checks.items() if cb.isChecked()]
            written = api.export_results(self.state.last_results, self.outdir_edit.text(),
                                          plots=plots_selected,
                                          save_csv=self.save_csv_check.isChecked())
            progresso.close()
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Exported", "Files generated:\n" + "\n".join(written))
        except Exception as exc:
            progresso.close()
            QApplication.restoreOverrideCursor()
            show_error(self, "Error exporting", exc)

    # =====================================================================
    # Factorial analysis axes
    # =====================================================================

    def _build_axis_row(self, index: int):
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(f"Axis {index}:"))
        slot_combo = QComboBox()
        for label, _slot in self._AXIS_SLOTS:
            slot_combo.addItem(label)
        # Keeps the row compact, but opens the popup wide enough for the
        # full options (no truncated text).
        slot_combo.view().setMinimumWidth(slot_combo.sizeHint().width())
        slot_combo.setToolTip(
            "Which flight-condition quantity this axis sweeps. Every axis in "
            "use is combined with every other one (a full factorial), so the "
            "number of cases is the product of the value counts — not their "
            "sum. Leave it at (none) to disable the axis.")
        row.addWidget(slot_combo)
        unit_combo = QComboBox()
        configure_unit_combo(
            unit_combo, CONDITION_UNITS[("inplane", False)])
        unit_combo.view().setMinimumWidth(unit_combo.sizeHint().width())
        unit_combo.setToolTip(
            "Unit the values below are written in. It changes how the numbers "
            "are read, not the condition itself: the engine always works with "
            "the advance ratio, and the other units are converted into it "
            "using the current radius and RPM.")
        unit_combo.setVisible(False)
        # The combo goes inside a FIXED-width container, and it's the
        # container that goes into the row. Two things at once, both
        # visible in the user's screenshot: (a) "mu_x" and "alpha [deg]"
        # have quite different natural widths, so the "values:" label
        # started at a different x per row; (b) on the "(none)" axis the
        # combo is HIDDEN, and a hidden widget takes up no width at all
        # -- that row started dozens of pixels to the left of the
        # others. The container reserves the same column across the
        # three rows, whether or not a combo sits inside it.
        unit_box = QWidget()
        unit_layout = QHBoxLayout(unit_box)
        unit_layout.setContentsMargins(0, 0, 0, 0)
        unit_layout.setSpacing(0)
        unit_layout.addWidget(unit_combo)
        unit_box.setFixedWidth(condition_unit_width())
        #: flags read by `common.apply_condition_unit_width`,
        #: which re-measures the column after the theme's polish
        unit_combo._is_unit_combo = True
        unit_box._unit_reserve = True
        row.addWidget(unit_box)
        slot_combo.currentIndexChanged.connect(
            lambda _i, uc=unit_combo, sc=slot_combo: self._sync_unit_combo(sc, uc))
        row.addWidget(QLabel("values:"))
        values_edit = QLineEdit()
        values_edit.setPlaceholderText("e.g.: 0, 0.1, 0.2, 0.3")
        values_edit.setToolTip(
            "The values this axis takes, separated by commas. This list is "
            "what actually gets swept — the from/to/step boxes beside it are "
            "only a way to fill it in.")
        row.addWidget(values_edit, stretch=1)
        row.addWidget(QLabel("from:"))
        v_from = QDoubleSpinBox(); v_from.setRange(-100000, 100000); v_from.setDecimals(3)
        v_from.setSingleStep(0.1)
        v_from.setToolTip("First value of the range that the 'fill' button writes "
                          "into the values list.")
        row.addWidget(v_from)
        row.addWidget(QLabel("to:"))
        v_to = QDoubleSpinBox(); v_to.setRange(-100000, 100000); v_to.setDecimals(3); v_to.setValue(1.0)
        v_to.setSingleStep(0.1)
        v_to.setToolTip("Last value of the range that the 'fill' button writes "
                        "into the values list.")
        row.addWidget(v_to)
        row.addWidget(QLabel("step:"))
        v_step = QDoubleSpinBox(); v_step.setRange(0.001, 100000); v_step.setDecimals(3); v_step.setValue(0.1)
        v_step.setSingleStep(0.01)
        v_step.setToolTip(
            "Spacing between consecutive values in the generated range. "
            "Halving it doubles the number of cases on this axis, and "
            "multiplies the total by two.")
        row.addWidget(v_step)
        btn_gen = QPushButton("fill")
        btn_gen.setToolTip("Fills the 'values' field with the from/to/step range.")
        btn_gen.clicked.connect(
            lambda: self._generate_axis_values(values_edit, v_from, v_to, v_step))
        row.addWidget(btn_gen)
        # Item 11: same width for the same role on EVERY axis row, so the
        # fields end up aligned vertically instead of each stopping at a
        # different x (90/90/86 px measured before).
        for box in (v_from, v_to, v_step):
            box.setFixedWidth(self._RANGE_WIDTH)
            # Without this flag, `common.compact_form_fields`
            # (the window's policy, which runs AFTER construction) calls
            # `setMaximumWidth(150)` on top of `setFixedWidth(92)`: the
            # maximum goes up, the minimum stays at 92, and the three
            # stop having a fixed width -- the row starts distributing
            # the leftover space among them. Since the leftover depends
            # on what else is in the row (the unit combo appears only on
            # the longitudinal/axial axes), each axis row ended with
            # "from:/to:/step:" at a different x. That's how it showed
            # up on screen.
            box._width_capped = True
        # Keeps the trio together with the slot combo: `_sync_unit_combo`
        # needs it to readjust the range when the axis quantity changes.
        slot_combo._generators = (v_from, v_to, v_step)
        unit_combo.currentIndexChanged.connect(
            lambda _i, sc=slot_combo, uc=unit_combo: self._tune_generator_range(sc, uc))
        self._tune_generator_range(slot_combo, unit_combo)
        return row_widget, slot_combo, unit_combo, values_edit, btn_gen

    #: Plausible range/step/decimal places per axis quantity.
    #: (from, to, step, decimals, accepted_min, accepted_max)
    #: The last two are the spin's own LIMIT: with the single 100000
    #: ceiling inherited from before, you could type 5000 degrees of disk
    #: angle. The 0.001 floor on step prevented a 50 RPM step from
    #: being written as such.
    _RANGE_BY_VARIABLE = {
        "mu_x": (0.0, 0.4, 0.05, 3, 0.0, 2.0),
        "J_x": (0.0, 2.0, 0.1, 3, 0.0, 20.0),
        # "Vx", not "V". `CONDITION_UNITS` names the in-plane speed `Vx`;
        # under the old key this entry never matched, so the "fill" button
        # kept the advance-ratio range (0 to 1, step 0.1) while the axis was
        # a speed in metres per second, and filled it with eleven values
        # under one metre per second.
        "Vx": (0.0, 80.0, 5.0, 1, -500.0, 500.0),
        "alpha_deg": (-10.0, 10.0, 2.0, 2, -90.0, 90.0),
        "alpha_disk": (-10.0, 10.0, 2.0, 2, -90.0, 90.0),
        "Vz": (-10.0, 10.0, 2.0, 2, -200.0, 200.0),
        # the AXIAL advance of a propeller: the same useful range as
        # mu_x/J_x, just in the other slot (see `widgets.CONDITION_UNITS`)
        "mu_z": (0.0, 0.4, 0.05, 3, -2.0, 2.0),
        "J_z": (0.0, 2.0, 0.1, 3, -20.0, 20.0),
        "collective_deg": (0.0, 14.0, 1.0, 2, -30.0, 60.0),
        "rpm": (200.0, 400.0, 20.0, 0, 0.0, 60000.0),
    }

    def _range_widgets(self, index: int):
        """(from, to, step) of axis row `index` (0-based)."""
        return getattr(self.axis_rows[index][0], "_generators", (None, None, None))

    def _tune_generator_range(self, slot_combo: QComboBox, unit_combo: QComboBox):
        """Retunes the "fill" button's from/to/step for the axis quantity.

        The three fields used to be born fixed at 0 / 1.0 / 0.1 -- advance
        ratio values -- and stayed that way no matter the axis. With the
        axis set to disk angle, pressing "fill" wrote
        "0, 0.1, ... 1": eleven cases between zero and ONE DEGREE, when
        the useful range is tens of degrees. In RPM it was even worse.
        The user saw a nonsensical list in the field they had just touched.
        """
        trio = getattr(slot_combo, "_generators", None)
        if trio is None:
            return
        variable = self._axis_variable(slot_combo, unit_combo)
        bounds = self._RANGE_BY_VARIABLE.get(variable)
        if bounds is None:
            return
        start, end, step, decimals, minimum, maximum = bounds
        v_from, v_to, v_step = trio
        for box in (v_from, v_to, v_step):
            box.blockSignals(True)
            box.setDecimals(decimals)
        v_from.setRange(minimum, maximum)
        v_to.setRange(minimum, maximum)
        # Step is a distance: positive, and never larger than the whole range.
        v_step.setRange(10.0 ** -decimals if decimals else 1.0, max(maximum - minimum, 1.0))
        v_from.setSingleStep(step)
        v_to.setSingleStep(step)
        # The "step" field's own step is one order of magnitude smaller:
        # adjusting the spacing needs finer resolution than the spacing itself.
        v_step.setSingleStep(max(step / 10.0, 10.0 ** -decimals))
        v_from.setValue(start)
        v_to.setValue(end)
        v_step.setValue(step)
        for box in (v_from, v_to, v_step):
            box.blockSignals(False)

    def _slot_of_combo(self, slot_combo: QComboBox) -> str | None:
        """Slot chosen in the combo, or ``None`` if there is no choice.

        `QComboBox.currentIndex()` returns -1 for an empty combo, and
        `self._AXIS_SLOTS[-1]` is valid indexing in Python: it would
        SILENTLY return the last slot in the list (RPM) as if the user
        had chosen it -- a phantom axis in a tab where nothing was
        selected. Every access to the table goes through here.
        """
        index = slot_combo.currentIndex()
        if index < 0 or index >= len(self._AXIS_SLOTS):
            return None
        return self._AXIS_SLOTS[index][1]

    def _sync_unit_combo(self, slot_combo: QComboBox, unit_combo: QComboBox):
        """Shows the unit dropdown only when the axis is the longitudinal
        or the axial slot -- and with the units for THE CURRENT MODE.

        The lists come from `widgets.CONDITION_UNITS`, the same
        source as the fixed-value fields and the single-case row: in
        propeller mode the axial axis sweeps J_x/mu_x/Vx_inf (the
        propeller's advance) and the longitudinal one sweeps the cross
        flow. Two hand-maintained lists would diverge on the first new
        mode -- and a sweep labeled with the wrong unit is
        indistinguishable from a correct sweep until someone checks the
        numbers."""
        slot = self._slot_of_combo(slot_combo)
        is_propeller = self.state.is_propeller()
        unit_combo.blockSignals(True)
        unit_combo.clear()
        if slot in ("inplane", "axial"):
            configure_unit_combo(
                unit_combo, CONDITION_UNITS[(slot, is_propeller)])
            unit_combo.setVisible(True)
        else:
            unit_combo.setVisible(False)
        unit_combo.view().setMinimumWidth(unit_combo.sizeHint().width())
        unit_combo.blockSignals(False)
        # The quantity changed along with the slot: redo the generator's range.
        self._tune_generator_range(slot_combo, unit_combo)

    def _axis_variable(self, slot_combo: QComboBox, unit_combo: QComboBox) -> str | None:
        slot = self._slot_of_combo(slot_combo)
        if slot is None:
            return None
        if slot in ("inplane", "axial"):
            var = unit_label_variable(slot, unit_combo.currentText())
            if var:
                return var
            # combo not yet synced with the slot: falls back to the
            # mode's first unit, never to a made-up variable name
            return CONDITION_UNITS[(slot, self.state.is_propeller())][0][1]
        return slot

    def _fill_axis_values(self, index: int):
        """Triggers the "fill" action for axis row `index` (0-based)."""
        slot_combo, _unit_combo, values_edit = self.axis_rows[index]
        trio = getattr(slot_combo, "_generators", None)
        if trio is None:
            return
        self._generate_axis_values(values_edit, *trio)

    def _generate_axis_values(self, values_edit: QLineEdit, v_from: QDoubleSpinBox,
                               v_to: QDoubleSpinBox, v_step: QDoubleSpinBox):
        lo, hi, step = v_from.value(), v_to.value(), v_step.value()
        if step <= 0 or hi < lo:
            QMessageBox.warning(self, "Invalid range", "Check 'from'/'to'/'step'.")
            return
        n = int(round((hi - lo) / step)) + 1
        values_edit.setText(", ".join(f"{lo + i * step:g}" for i in range(n)))

    def _active_axes(self) -> list[dict]:
        axes, _rejected = self._active_axes_and_rejects()
        return axes

    def _active_axes_and_rejects(self) -> tuple[list[dict], list[str]]:
        """The axes, plus every token that is not a number.

        The two travel together because the live read-out and the generate
        button want opposite things from a half-typed list: the label has to
        keep working while the user types, and the button must not build a
        batch out of the part it happened to understand.
        """
        axes: list[dict] = []
        rejected: list[str] = []
        for slot_combo, unit_combo, values_edit in self.axis_rows:
            var = self._axis_variable(slot_combo, unit_combo)
            if var is None:
                continue
            values, bad = parse_list_reporting(values_edit.text())
            rejected.extend(bad)
            if values:
                axes.append({"variable": var, "values": values})
        return axes, rejected

    def _on_axes_changed(self, *_args):
        """Progressive disclosure: a SLOT already used as an axis is
        disabled in the other combos, and the corresponding 'fixed'
        field disappears -- the same quantity cannot be axis and fixed
        at the same time."""
        chosen_slots = {self._slot_of_combo(sc) for sc, _uc, _ve in self.axis_rows}
        chosen_slots.discard(None)

        for slot_combo, _unit_combo, _values_edit in self.axis_rows:
            current_slot = self._slot_of_combo(slot_combo)
            model = slot_combo.model()
            for row_idx, (_label, slot) in enumerate(self._AXIS_SLOTS):
                item = model.item(row_idx)
                usado_alhures = slot is not None and slot in chosen_slots and slot != current_slot
                item.setEnabled(not usado_alhures)

        for slot, widgets in self._fixed_widgets.items():
            visivel = slot not in chosen_slots
            for w in widgets:
                set_row_visible(self._fixed_form, w, visivel)
        self._update_total_cases()

    def _update_total_cases(self, *_args):
        axes, rejected = self._active_axes_and_rejects()
        if not axes:
            self.total_cases_label.setText("Total cases: — (choose at least 1 axis)")
            return
        total = 1
        factors = []
        for ax in axes:
            total *= len(ax["values"])
            factors.append(str(len(ax["values"])))
        text = f"Total cases: {' × '.join(factors)} = {total}"
        if rejected:
            # Said, not hidden: while a number is half typed this is the
            # normal state, and the count above is the count of what is
            # readable SO FAR. Silence here would read as "that value
            # counted", which is the reading that makes a short batch look
            # like a correct one.
            text += "   (ignoring: " + ", ".join(rejected) + ")"
        self.total_cases_label.setText(text)

    # =====================================================================
    # Conversion contexts and project state
    # =====================================================================

    def _refresh_mode_defaults(self):
        is_prop = self.state.is_propeller()
        self.fixed_advance.set_default_unit(is_prop)
        self.fixed_axial.set_default_unit(is_prop)
        self.add_row_advance.set_default_unit(is_prop)
        self.add_row_axial.set_default_unit(is_prop)
        # Label and help in the mode's CONVENTION, in the two forms that
        # have the component pair (the factorial's fixed values and the
        # case-by-case mode's row). See `common.condition_label_and_tooltip`:
        # on a propeller the flight speed is AXIAL, and a field labeled
        # "Advance" invited putting the aircraft's speed there.
        fields = ((self._fixed_form, self.fixed_advance, "inplane"),
                  (self._fixed_form, self.fixed_axial, "axial"),
                  (self._case_form, self.add_row_advance, "inplane"),
                  (self._case_form, self.add_row_axial, "axial"))
        for form, field, slot in fields:
            label, tip = condition_label_and_tooltip(is_prop, slot)
            field.setToolTip(tip)
            if form is not None:
                set_row_label(form, field, label)
        # The factorial's axes name the same decomposition: the slot
        # combo's label now states which component is which in the mode.
        self._rename_axis_slots(is_prop)
        # ...and each axis's UNIT LIST changes along with it. Without
        # this, an axis already chosen as "axial" would keep offering
        # "alpha [deg]" after switching to propeller mode -- the unit
        # that cannot express straight axial flight (see `AxialInput`).
        for slot_combo, unit_combo, _values in getattr(self, "axis_rows", []):
            self._sync_unit_combo(slot_combo, unit_combo)

    def _fixed_advance_context(self):
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.fixed_rpm.value(), radius_m

    def _fixed_axial_context(self):
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.fixed_advance.mu_x(), self.fixed_rpm.value(), radius_m

    def _add_row_advance_context(self):
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.rpm_spin.value(), radius_m

    def _add_row_axial_context(self):
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.add_row_advance.mu_x(), self.rpm_spin.value(), radius_m

    def _on_project_changed(self):
        if self.state.project is not None:
            self.outdir_edit.setText(str(Path(self.state.project.path) / "outputs"))
        self._refresh_saved_batches_combo()

    # =====================================================================
    # Batches saved in the project
    # =====================================================================

    def _refresh_saved_batches_combo(self):
        self.batches_combo.blockSignals(True)
        self.batches_combo.clear()
        self.batches_combo.addItem("(none selected)")
        for b in (self.state.project.batches if self.state.project else []):
            self.batches_combo.addItem(b.name)
        self.batches_combo.blockSignals(False)

    def _load_selected_batch(self):
        """The "load" button: reloads whatever the combo names.

        Selecting a DIFFERENT name already loads it, so this button
        exists for the two cases the selection cannot serve -- reloading
        the name already selected, and being visible at all, which the
        combo alone was not.
        """
        index = self.batches_combo.currentIndex()
        if index <= 0:
            QMessageBox.information(
                self, "No batch selected",
                "Choose a saved batch in the list beside this button.")
            return
        self._on_saved_batch_selected(index)

    def _on_saved_batch_selected(self, index: int):
        """Loads the saved batch INTO THE QUEUE. A sweep batch stores
        `sweep_params` instead of conditions; in that case we expand it,
        so the queue shows what will actually run."""
        if index <= 0 or self.state.project is None:
            return
        batch = self.state.project.batches[index - 1]
        conditions = list(batch.conditions)
        if not conditions and batch.sweep_kind:
            try:
                conditions = self._expand_sweep(batch)
            except Exception as exc:
                show_error(self, "Error loading saved batch", exc)
                return
        self._fill_queue(conditions, replace=True)

    def _expand_sweep(self, batch: BatchDefinition) -> list:
        params = dict(batch.sweep_params or {})
        if batch.sweep_kind == "factorial":
            return api.build_factorial_conditions(
                self.state.project, params.get("axes", []), params.get("fixed"))
        axis = {"mu_sweep": ("mu_x", "mu_values"),
                "alpha_sweep": ("alpha_deg", "alpha_deg_values"),
                "collective_sweep": ("collective_deg", "collective_deg_values")}.get(batch.sweep_kind)
        if axis is None:
            return []
        variable, key = axis
        values = params.pop(key, [])
        fixed_values = {k: v for k, v in params.items() if not isinstance(v, (list, tuple))}
        return api.build_factorial_conditions(
            self.state.project, [{"variable": variable, "values": list(values)}], fixed_values)

    def _save_current_as_batch(self):
        if not require_project(self, self.state):
            return
        conditions, rejected = self._queue_conditions_and_rejects()
        if rejected:
            QMessageBox.warning(
                self, "Unreadable cells",
                "These cells are not numbers, so the batch cannot be saved "
                "as it is shown:\n\n    " + "\n    ".join(rejected))
            return
        if not conditions:
            QMessageBox.warning(self, "Queue empty", "Generate cases before saving.")
            return
        name, ok = QInputDialog.getText(self, "Save queue", "Batch name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        new_batch = BatchDefinition(name=name, conditions=conditions)
        batches = self.state.project.batches
        for i, b in enumerate(batches):
            if b.name == name:
                batches[i] = new_batch
                break
        else:
            batches.append(new_batch)
        self.state.notify_config()
        self._refresh_saved_batches_combo()
        # Selected WITHOUT reloading. The queue on screen is already
        # exactly what was saved, and letting the selection fire would
        # refill it from the freshly written batch -- which is how the
        # rounding described above became visible the instant the name
        # was typed.
        self.batches_combo.blockSignals(True)
        self.batches_combo.setCurrentText(name)
        self.batches_combo.blockSignals(False)

    def _remove_saved_batch(self):
        idx = self.batches_combo.currentIndex()
        if idx <= 0 or self.state.project is None:
            return
        del self.state.project.batches[idx - 1]
        self.state.notify_config()
        self._refresh_saved_batches_combo()
