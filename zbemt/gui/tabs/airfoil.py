"""Implement GUI tab 3, Airfoil.

Purpose: configure the two-dimensional aerodynamic model, radial sections,
stall, reverse flow, compressibility, profile geometry, and external polar
generation. Inputs are editable airfoil definitions and optional imported
tables; outputs are project-model updates, preview plots, and generated polar
data. ``airfoils.py`` and ``external_solvers.py`` provide the calculations,
``validation.py`` checks combinations, and ``api.py`` owns persistence.

Conventions and limitations: angles are in degrees, lengths use SI units, and
tabulated data must cover the operating range or use the documented extension
model. Preview curves are diagnostic and do not replace validation of the
selected polar in the complete rotor or propeller case.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import asdict, replace

import numpy as np

from PyQt6.QtWidgets import (
    QWidget,
    QTabWidget,
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
    QSpinBox,
    QFileDialog,
    QMessageBox,
    QListWidget,
    QScrollArea,
    QSplitter,
    QPlainTextEdit,
    QListWidgetItem,
    QProgressBar,
    QSlider,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer

from ... import api
from ... import airfoils
from ... import validation
from ...viz import plots
from ...models import AirfoilDef, ProfileGeometry, PolarSlice, uses_full_range_extension
from ...bemt import BEMTConfig

from ..common import (parse_list, AppState, show_error, CanvasHost, set_row_visible,
                      require_optional_package, require_optional_binary)
from ..dialogs import adjust_combo_width
from ..workers import ExternalPolarWorker, launch_worker


# =============================================================================
# Internal class to simulate a QComboBox interface with a fixed value
# =============================================================================
class _FixedValueHolder:
    """Simulates the QComboBox interface for a field that only has one valid value.

    Used for `dynamic_stall_method`, which is just "frequency" in the GUI
    (time_march is an internal escape hatch for compatibility with old .bemt
    files, not editable here). Preserves the .currentText() and
    .setCurrentText() interface so that AirfoilDef read/write code does not
    change."""

    def __init__(self, fixed_value: str):
        self._value = fixed_value

    def currentText(self) -> str:
        """Returns the fixed value."""
        return self._value

    def setCurrentText(self, value: str) -> None:
        """Silently accepts only the fixed value."""
        if value == self._value:
            self._value = value


def _unir_curvas_coincidentes(curves: list) -> list:
    """Merges numerically identical curves into a single legend entry.

    Three of the six legend entries could name the SAME line: with
    ``reverse_flow_model="viterna_full_range"`` the reverse branch is the
    extended polar itself (there is no separate reverse treatment), and the
    comparison curve at M=0 is the polar without compressibility correction,
    that is, the main curve again. The legend announced six curves with only
    four actually drawn, and the three coincident ones stacked on the same
    line thickness, indistinguishable.

    Merging (instead of discarding) preserves the useful information: the
    resulting label states WHICH conditions fall on the same curve, which is
    exactly what the reader needs to know.
    """
    merged: list = []
    for curve in curves:
        key = (tuple(np.round(np.asarray(curve["alpha_deg"], float), 9)),
                 tuple(np.round(np.asarray(curve["cl"], float), 12)),
                 tuple(np.round(np.asarray(curve["cd"], float), 12)))
        for previous, previous_key in merged:
            if key == previous_key:
                previous["label"] += f" = {curve['label']}"
                break
        else:
            merged.append((dict(curve), key))
    return [curve for curve, _ in merged]


def NACA_CATALOG_TEXT() -> str:
    """One line per typical blade section, from `airfoils.AIRFOIL_PRESETS`,
    the catalog that used to feed the presets combo, now read where the
    code is typed.

    Derived, not copied: a new catalog entry (which the CLI also accepts in
    `--airfoil-geometry`) appears here on its own. Only the NACA families
    are listed: this text sits in the NACA field's help, and the analytic
    presets (parsec/joukowski/biconvex) carry generator parameters, not a
    NACA code -- they are reachable through the Geometry spec field below."""
    return "; ".join(
        f"{preset['code']} ({preset['note'].split('--')[0].strip().rstrip('.').lower()})"
        for _alias, preset in sorted(airfoils.AIRFOIL_PRESETS.items())
        if preset["family"] in ("naca4", "naca5"))


class _XfoilPolarWorker(ExternalPolarWorker):
    """``ExternalPolarWorker`` carrying the XFOIL-dedicated adjustment
    inputs (ncrit, xtr_top, xtr_bot).

    ``workers.ExternalPolarWorker`` keeps one engine-neutral signature;
    this subclass adds the three XFOIL-only transition inputs and forwards
    them to ``api.run_external_polar_from_geometry``, which passes them on
    to the binary only on the xfoil path. Threading, cancellation and the
    finished/failed protocol stay exactly the worker's own."""

    def __init__(self, profile: ProfileGeometry, *, reynolds_list: list,
                 mach_list: list, alpha_min_deg: float, alpha_max_deg: float,
                 alpha_step_deg: float, ncrit: float, xtr_top: float,
                 xtr_bot: float):
        super().__init__(
            profile, engine="xfoil",
            reynolds_list=reynolds_list, mach_list=mach_list,
            alpha_min_deg=alpha_min_deg, alpha_max_deg=alpha_max_deg,
            alpha_step_deg=alpha_step_deg)
        self.ncrit = ncrit
        self.xtr_top = xtr_top
        self.xtr_bot = xtr_bot

    def run(self):
        try:
            slices = api.run_external_polar_from_geometry(
                self.profile, engine="xfoil",
                reynolds_list=self.reynolds_list, mach_list=self.mach_list,
                alpha_min_deg=self.alpha_min_deg, alpha_max_deg=self.alpha_max_deg,
                alpha_step_deg=self.alpha_step_deg,
                ncrit=self.ncrit, xtr_top=self.xtr_top, xtr_bot=self.xtr_bot,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(slices)


# =============================================================================
# Tab 3 — Airfoil (single-section at this stage. Multi-section is Phase D
# of the plan). Gains here, by relocation (docs/plano.md Section 4): reverse
# flow + compressibility (coming from Analysis) and the visual grouping of
# Viterna together with the static stall model. Loses: the preview canvases
# (polar and profile), which migrate to the Results tab (principle 5).
# =============================================================================

class AirfoilTab(QWidget):
    dirty_changed = pyqtSignal(bool)   # "unsaved to disk" asterisk (same mechanism as config.py/geometry_tab.py)

    #: Width of the left panel (item 3). The minimum is what guarantees that
    #: the QDoubleSpinBox spin buttons appear without dragging the
    #: splitter; the initial value gives some slack above that.
    _FORM_MIN_WIDTH = 520
    _FORM_INITIAL_WIDTH = 600

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._dirty = False
        # True while this tab is writing its own edit back to
        # `state.project` (see `_apply_to_project`). That prevents
        # `_refresh_from_project` (connected to `airfoil_changed`, which the
        # write itself triggers) from rebuilding the form/section scratch
        # from what just came out of it.
        self._applying_locally = False
        self._imported_slices: list[PolarSlice] = []
        self._profile: ProfileGeometry | None = None
        self._generated_external_slices: list[PolarSlice] = []
        self._ext_thread: QThread | None = None
        self._ext_worker: ExternalPolarWorker | None = None

        # --- multi-section airfoil state (Phase D, docs/plano.md
        # Section 4) --------------------------------------------------------
        # self._sections empty = "single airfoil" mode (the usual
        # behavior), and the form below edits project.airfoil directly.
        # self._sections with 2+ AirfoilDef = multi-section mode. The
        # form ALWAYS edits the section selected in self.sections_list
        # (self._current_section_index), never both things at the same
        # time. Switching sections saves the previous one to scratch before
        # loading the new one. Any field edit applies live (see
        # _apply_to_project), which always resolves the entire scratch (all
        # sections, not just the current one) before writing to the project.
        self._sections: list[AirfoilDef] = []
        self._current_section_index: int = -1   # -1 = editing the single airfoil

        # Item 6: while False, the preview's alpha range automatically
        # follows the full range extension (see
        # `_sync_alpha_range_to_extension`); becomes True the instant the
        # user picks a range in the combo, and from then on their choice
        # wins.
        self._alpha_range_chosen_by_user = False
        # Item 15: same idea for the generated-table Reynolds/Mach lists
        # (NeuralFoil and XFOIL modes) -- suggested from the rotor until
        # the user types their own list.
        self._re_mach_user_edited = False

        # Live preview (docs/plano_v3.md Part 5): state of the multi-axis
        # navigator (r/R, Reynolds, Mach), shared between the "Polar" and
        # "Profile" tabs of the mini-canvas -- see `_build_preview_panel`.
        self._nav_selection: dict = {"r_norm": None, "reynolds": None, "mach": None}
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._ao_expirar_debounce)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Item 3: at 460px the field column already opened cramped and the
        # increment/decrement ARROWS of the QDoubleSpinBox got cut off by
        # the scroll area's border, so the user had to drag the splitter
        # before being able to use the widget. The minimum width below is
        # that of the entire form (longest label + field + spin buttons)
        # and the initial size gives some slack above it.
        scroll.setMinimumWidth(self._FORM_MIN_WIDTH)
        left_widget = QWidget()
        self._airfoil_left_widget = left_widget
        # The minimum width also needs to be on the content: the splitter can
        # respect the viewport and still compress the inner widget, cutting
        # off the spin box arrows on the right side of the form.
        left_widget.setMinimumWidth(self._FORM_MIN_WIDTH)
        left = QVBoxLayout(left_widget)
        scroll.setWidget(left_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(self._build_preview_panel())
        # Extra space goes to the CANVAS, not to the form, see the
        # equivalent note in `geometry_tab.py`.
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([self._FORM_INITIAL_WIDTH, 900])
        outer = QVBoxLayout(self)
        outer.addWidget(splitter)

        left.addWidget(self._build_sections_box())
        left.addWidget(self._build_model_box())
        left.addWidget(self._build_dynamic_stall_box())
        left.addWidget(self._build_out_of_curve_box())
        left.addWidget(self._build_table_box())
        left.addWidget(self._build_geometry_box())
        left.addWidget(self._build_external_box())

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignLeft)  # Bug 2: do not expand buttons needlessly
        # The buttons live in the side column, which also has to accommodate
        # the canvas. Long labels compressed the three buttons and got
        # truncated; the full explanation stays in the tooltip.
        # No "Check airfoil": the check runs on its own on the same preview
        # debounce (see `_ao_expirar_debounce`), so the button only repeated
        # what any field edit already triggers.
        # No "Apply to project": every field already writes to
        # `state.project` live (see `_apply_to_project`, now called on every
        # edit). "Save"/"Restore" only decide whether that goes to disk
        # or is discarded.
        btn_save = QPushButton("Save")
        btn_save.setToolTip("Write the project to disk")
        btn_save.clicked.connect(self._save_project)
        btn_row.addWidget(btn_save)
        btn_restore = QPushButton("Restore")
        btn_restore.setToolTip("Discard changes and reload the project from disk")
        btn_restore.clicked.connect(self._restore_project)
        btn_row.addWidget(btn_restore)
        left.addLayout(btn_row)

        left.addWidget(QLabel("<b>Checks (excluding/redundant combinations)</b>"))
        self.validation_label = QLabel("No warnings.")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("font-size: 11px;")
        left.addWidget(self.validation_label)
        left.addStretch(1)

        self.state.airfoil_changed.connect(self._refresh_from_project)
        # The NeuralFoil Reynolds/Mach suggestion is a function of the
        # GEOMETRY (radius, chord) and the CONDITION (RPM, advance). Both
        # live outside this tab, so it needs to listen for both changing,
        # otherwise it keeps showing the envelope of a rotor that no longer
        # exists.
        # `project_changed` covers editing conditions in Run Case/Run
        # Batch (which save the case to the project).
        self.state.geometry_changed.connect(self._re_suggest_re_mach)
        self.state.project_changed.connect(self._re_suggest_re_mach)
        self.state.config_changed.connect(self._re_suggest_re_mach)
        # cascade (docs/plano.md Section 4): source/stall model decide
        # whether the dynamic stall toggle makes sense.
        self.source_combo.currentTextChanged.connect(self._update_dynamic_stall_enabled)
        self.stall_model_combo.currentTextChanged.connect(self._update_dynamic_stall_enabled)
        self.extend_full_range.toggled.connect(self._update_viterna_visibility)
        self._update_dynamic_stall_enabled()
        self._update_source_visibility()

        # Live update (about 300 ms debounce, docs/plano_v3.md Part 5): any form
        # field edit schedules a redraw of the embedded canvas -- a generic
        # connection (findChildren) instead of one widget at a time, so it
        # does not go stale with every new form field.
        #
        # `_VIEW_ONLY` are controls for HOW TO DRAW (alpha
        # range, axis scale, reverse branch, overlay Machs), not project
        # fields: they redraw the canvas, but must not call
        # `_apply_to_project`. Otherwise changing a chart's scale would
        # mark the project as unsaved and prompt for confirmation on
        # window close. Since item 8 they moved to the control strip above
        # the canvas, OUTSIDE `left_widget`: the loops below no longer
        # reach them and `_wire_plot_toolbar` wires them explicitly. The
        # `not in _VIEW_ONLY` check remains as a safety belt in
        # case one of them moves back into the form.
        for w in left_widget.findChildren(QDoubleSpinBox):
            w.valueChanged.connect(self._schedule_preview_refresh)
            w.valueChanged.connect(self._apply_to_project)
        for w in left_widget.findChildren(QSpinBox):
            w.valueChanged.connect(self._schedule_preview_refresh)
            w.valueChanged.connect(self._apply_to_project)
        for w in left_widget.findChildren(QComboBox):
            w.currentTextChanged.connect(self._schedule_preview_refresh)
            if w not in self._VIEW_ONLY:
                w.currentTextChanged.connect(self._apply_to_project)
        for w in left_widget.findChildren(QCheckBox):
            w.toggled.connect(self._schedule_preview_refresh)
            if w not in self._VIEW_ONLY:
                w.toggled.connect(self._apply_to_project)
        for w in left_widget.findChildren(QLineEdit):
            w.editingFinished.connect(self._schedule_preview_refresh)
            w.editingFinished.connect(self._apply_to_project)
        for w in left_widget.findChildren(QPlainTextEdit):
            w.textChanged.connect(self._schedule_preview_refresh)
            w.textChanged.connect(self._apply_to_project)
        self._wire_plot_toolbar()
        # Item 15: `textEdited` (not `textChanged`) fires only when the
        # user types, so an automatic suggestion written via `setText`
        # does not count as "the user set the list".
        self.re_list_edit.textEdited.connect(self._on_re_mach_edited)
        self.mach_list_edit.textEdited.connect(self._on_re_mach_edited)
        # Item 9: the sections list is always visible, including in single
        # airfoil mode (one row, r/R='all'); that row's label is the
        # airfoil's name, so it has to track the field.
        self.airfoil_name_edit.textChanged.connect(self._on_airfoil_name_edited)
        self._refresh_sections_list_widget()
        self._sync_alpha_range_to_extension()
        self._refresh_preview()

    #: Base tooltip of the dynamic stall checkbox. Constant because
    #: `_update_dynamic_stall_enabled` rewrites the tooltip and needs to
    #: recompose the original text. The first token in quotes is what
    #: `field_help` reads to know WHICH field to open in the help popup.
    _DYNAMIC_STALL_TOOLTIP = (
        '"airfoil.use_dynamic_stall" — applies the Øye model for aerodynamic '
        'lag; requires a base polar with real stall')

    @property
    def _VIEW_ONLY(self) -> tuple:
        return (self.alpha_range_combo, self.autoscale_y_check,
                self.show_reverse_branch_check, self.mach_compare_edit)

    def _save_project(self):
        from ..common import save_project_from_tab
        save_project_from_tab(self, self.state)
        self._clear_dirty()

    def _restore_project(self):
        from ..common import restore_project_from_disk
        restore_project_from_disk(self, self.state)

    # --- Radial sections (Phase D, docs/plano.md Section 4) -------------------

    def _build_sections_box(self) -> QGroupBox:
        box = QGroupBox("Radial Sections")
        layout = QVBoxLayout(box)

        self.sections_mode_label = QLabel("Current mode: single airfoil")
        self.sections_mode_label.setWordWrap(True)
        self.sections_mode_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.sections_mode_label)

        self.sections_list = QListWidget()
        # Item 9: the list ALWAYS exists (short, scrolling if needed) --
        # before it only appeared with 2+ sections, which hid precisely the
        # starting point: in single airfoil mode it shows one row,
        # "r/R=all", and the "+ section" button next to it makes it obvious
        # that you can have more than one profile along the span.
        self.sections_list.setMaximumHeight(90)
        self.sections_list.currentRowChanged.connect(self._on_section_row_changed)
        layout.addWidget(self.sections_list)

        r_row = QHBoxLayout()
        r_row.addWidget(QLabel("r/R of this section:"))
        self.section_r_norm = QDoubleSpinBox()
        self.section_r_norm.setRange(0.0, 1.0)
        self.section_r_norm.setDecimals(3)
        self.section_r_norm.setSingleStep(0.05)
        self.section_r_norm.setToolTip(
            '"r_norm" — spanwise station of this airfoil, as a fraction of the '
            "rotor radius (0 at the axis, 1 at the tip). The engine assigns "
            "each blade element the section whose station is nearest to it, so "
            "moving this value moves the boundary between two profiles along "
            "the span.")
        self.section_r_norm.valueChanged.connect(self._on_section_r_norm_edited)
        r_row.addWidget(self.section_r_norm)
        r_row.addStretch(1)
        layout.addLayout(r_row)
        self._section_r_row_widgets = (r_row.itemAt(0).widget(), self.section_r_norm)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ section")
        btn_add.clicked.connect(self._add_section)
        btn_row.addWidget(btn_add)
        btn_remove = QPushButton("- section")
        btn_remove.clicked.connect(self._remove_section)
        btn_row.addWidget(btn_remove)
        # The slack goes to the end of the row, not to the buttons (see
        # `tests/test_gui_layout.py`: without this they stretch to the
        # QSS width ceiling, and `setSizePolicy(Fixed)` doesn't hold).
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._update_sections_ui()
        return box

    def _update_sections_ui(self):
        multi = len(self._sections) >= 2
        self.sections_mode_label.setText(
            f"Current mode: {len(self._sections)} sections" if multi else
            "Current mode: single airfoil (spans the whole blade)")
        # The list stays visible in both modes (item 9). Only the "r/R of
        # this section" row remains hidden in single mode -- there r/R is
        # not editable: the profile applies to the whole blade.
        self.sections_list.setVisible(True)
        for w in self._section_r_row_widgets:
            w.setVisible(multi)

    def _refresh_sections_list_widget(self):
        """Populates the sections list. In single airfoil mode (item 9)
        draws ONE row, r/R='all', instead of leaving the list empty --
        it's the same information, in a format that is already the
        multi-section one, and that makes "+ section" self-explanatory."""
        if not hasattr(self, "sections_list"):
            return
        self.sections_list.blockSignals(True)
        self.sections_list.clear()
        if self._sections:
            for s in self._sections:
                r_txt = f"{s.r_norm:.3f}" if s.r_norm is not None else "?"
                self.sections_list.addItem(QListWidgetItem(f"r/R={r_txt} — {s.name}"))
            if 0 <= self._current_section_index < len(self._sections):
                self.sections_list.setCurrentRow(self._current_section_index)
        else:
            name = (self.airfoil_name_edit.text().strip()
                    if hasattr(self, "airfoil_name_edit") else "") or "airfoil"
            self.sections_list.addItem(QListWidgetItem(f"r/R=all — {name}"))
            self.sections_list.setCurrentRow(0)
        self.sections_list.blockSignals(False)

    def _on_airfoil_name_edited(self, text: str):
        if 0 <= self._current_section_index < len(self._sections):
            self._sections[self._current_section_index].name = text.strip()
        self._refresh_sections_list_widget()

    def _save_current_form_into_scratch(self):
        """Saves the CURRENT state of the form into the section being
        edited (or does nothing in single airfoil mode, where the form IS
        project.airfoil and needs no intermediate scratch)."""
        if 0 <= self._current_section_index < len(self._sections):
            r_norm = self.section_r_norm.value()
            self._sections[self._current_section_index] = self._collect_airfoil_def(r_norm=r_norm)

    def _load_form_from_section(self, index: int):
        if not (0 <= index < len(self._sections)):
            return
        self.section_r_norm.blockSignals(True)
        self.section_r_norm.setValue(self._sections[index].r_norm or 0.0)
        self.section_r_norm.blockSignals(False)
        self._load_form_from_airfoil_def(self._sections[index])

    def _on_section_row_changed(self, row: int):
        # In single airfoil mode the list has the synthetic row "r/R=all"
        # (item 9), which does not correspond to any entry of
        # `self._sections`: selecting it is not switching section.
        if not self._sections:
            return
        if row < 0 or row == self._current_section_index:
            return
        self._save_current_form_into_scratch()
        self._current_section_index = row
        self._load_form_from_section(row)
        self._refresh_validation()

    def _on_section_r_norm_edited(self, value: float):
        if 0 <= self._current_section_index < len(self._sections):
            self._sections[self._current_section_index].r_norm = value
            self._refresh_sections_list_widget()

    def _suggest_new_r_norm(self) -> float:
        if not self._sections:
            return 0.15
        used = sorted(s.r_norm for s in self._sections if s.r_norm is not None)
        if len(used) < 2:
            return min(1.0, (used[0] if used else 0.15) + 0.2)
        # largest gap between neighboring sections -> propose its midpoint
        gaps = [(used[i + 1] - used[i], used[i], used[i + 1]) for i in range(len(used) - 1)]
        gap, lo, hi = max(gaps)
        return round((lo + hi) / 2.0, 3)

    def _add_section(self):
        """With 0 or 1 section defined (single mode), CREATES the minimal
        pair (root + tip) from the current form, cloned; with 2+, adds one
        more section cloned from the currently selected one, in a free
        r_norm gap (docs/plano.md Section 4)."""
        if len(self._sections) < 2:
            base = self._collect_airfoil_def()
            root = replace(base, name=base.name or "raiz", r_norm=0.15)
            tip = replace(base, name=(base.name or "ponta") + " (ponta)", r_norm=1.0)
            self._sections = [root, tip]
            self._current_section_index = 0
        else:
            self._save_current_form_into_scratch()
            current = self._sections[self._current_section_index]
            new_r = self._suggest_new_r_norm()
            new_section = replace(current, name=f"{current.name} (copy)", r_norm=new_r)
            self._sections.append(new_section)
            self._current_section_index = len(self._sections) - 1
        self._update_sections_ui()
        self._refresh_sections_list_widget()
        self._load_form_from_section(self._current_section_index)
        self._refresh_validation()

    def _remove_section(self):
        if not self._sections:
            return
        idx = self._current_section_index
        if not (0 <= idx < len(self._sections)):
            return
        del self._sections[idx]
        if len(self._sections) <= 1:
            # we don't let the invalid state "1 section only" exist in the
            # GUI: it automatically collapses back to single airfoil,
            # using the remaining section (if any) as the base.
            remaining = self._sections[0] if self._sections else self._collect_airfoil_def()
            self._sections = []
            self._current_section_index = -1
            self._load_form_from_airfoil_def(replace(remaining, r_norm=None))
        else:
            self._current_section_index = min(idx, len(self._sections) - 1)
            self._load_form_from_section(self._current_section_index)
        self._update_sections_ui()
        self._refresh_sections_list_widget()
        self._refresh_validation()

    # --- UI blocks -------------------------------------------------

    def _build_model_box(self) -> QGroupBox:
        """a) Aerodynamic model — Viterna now sits right below the stall
        model combo, in a single contiguous QGroupBox (docs/plano.md
        Section 4, "Viterna next to the stall model")."""
        box = QGroupBox("Aerodynamic Model")
        form = QFormLayout(box)

        self.airfoil_name_edit = QLineEdit("profile 1")
        self.airfoil_name_edit.setToolTip('"airfoil.name" — airfoil profile designation (e.g., NACA 0012, Clark Y)')
        form.addRow("Airfoil name:", self.airfoil_name_edit)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["analytical", "table", "neuralfoil", "xfoil"])
        self.source_combo.setMinimumWidth(150)
        self.source_combo.setToolTip(
            '"airfoil.source" — "analytical": analytical curves; '
            '"table": imported CSV; "neuralfoil": generate the table via '
            'NeuralFoil; "xfoil": generate the table via the XFOIL binary.\n\n'
            '"xfoil" needs XFOIL installed and reachable through ZBEMT_XFOIL_BIN '
            "or PATH. The check happens when you click Run. Without the binary, "
            "a dialog opens and explains how to install it.")
        form.addRow("Data source:", self.source_combo)

        self.cl_alpha = QDoubleSpinBox(); self.cl_alpha.setRange(0.1, 10.0); self.cl_alpha.setValue(2 * np.pi); self.cl_alpha.setDecimals(3)
        self.cl_alpha.setSingleStep(0.1)
        self.cl_alpha.setToolTip('"airfoil.cl_alpha" — slope of the Cl(α) curve in [1/rad]; theoretical value = 2π ≈ 6.283')
        self.alpha0_deg = QDoubleSpinBox(); self.alpha0_deg.setRange(-20, 20); self.alpha0_deg.setValue(-4.5)
        self.alpha0_deg.setSingleStep(0.1)
        self.alpha0_deg.setToolTip('"airfoil.alpha0_deg" — angle of attack where Cl = 0')
        self.cd0 = QDoubleSpinBox(); self.cd0.setRange(0.0, 0.5); self.cd0.setDecimals(4); self.cd0.setSingleStep(0.001); self.cd0.setValue(0.0155)
        self.cd0.setToolTip('"airfoil.cd0" — minimum parasitic drag (friction + pressure drag in unseparated regime)')
        self.k_coef = QDoubleSpinBox(); self.k_coef.setRange(0.0, 1.0); self.k_coef.setDecimals(4); self.k_coef.setValue(0.0)
        self.k_coef.setSingleStep(0.01)
        self.k_coef.setToolTip('"airfoil.k" — induced drag coefficient; Cd = Cd0 + k·Cl²; 0 = parabolic polar disabled')
        form.addRow("Cl polar slope [1/rad]:", self.cl_alpha)
        form.addRow("Zero-lift angle [deg]:", self.alpha0_deg)
        form.addRow("Parasitic drag Cd0:", self.cd0)
        form.addRow("Induced drag coef. k:", self.k_coef)

        # --- static stall + Viterna, a single contiguous block ---------
        self.stall_model_combo = QComboBox()
        self.stall_model_combo.addItems(["linear", "clip", "enhanced", "viterna"])
        self.stall_model_combo.setMinimumWidth(130)
        self.stall_model_combo.setToolTip(
            '"airfoil.stall_model" — '
            '"linear": no stall (unbounded linear Cl); '
            '"clip": clipped at the stall angles; '
            '"enhanced": smoothed nonlinear; '
            '"viterna": Viterna-Corrigan extension ±180°')
        form.addRow("Stall model:", self.stall_model_combo)

        self.alpha_stall_pos = QDoubleSpinBox(); self.alpha_stall_pos.setRange(0, 90); self.alpha_stall_pos.setValue(15.0)
        self.alpha_stall_pos.setSingleStep(0.5)
        self.alpha_stall_pos.setToolTip('"airfoil.alpha_stall_pos_deg" — positive stall angle (stall onset for α > 0)')
        self.alpha_stall_neg = QDoubleSpinBox(); self.alpha_stall_neg.setRange(-90, 0); self.alpha_stall_neg.setValue(-6.0)
        self.alpha_stall_neg.setSingleStep(0.5)
        self.alpha_stall_neg.setToolTip('"airfoil.alpha_stall_neg_deg" — negative stall angle (stall onset for α < 0)')
        form.addRow("Positive stall angle [deg]:", self.alpha_stall_pos)
        form.addRow("Negative stall angle [deg]:", self.alpha_stall_neg)

        # extend_full_range: for source 'table' it is the explicit choice
        # to EXTRAPOLATE the imported table with Viterna-Corrigan beyond
        # the last real point. For source 'analytical' it stays hidden.
        self.extend_full_range = QCheckBox("Extrapolate with Viterna-Corrigan (±180°)")
        self.extend_full_range.setToolTip('"airfoil.extend_full_range" — extends the table beyond the imported data using the Viterna-Corrigan model; CLmax/CLmin auto-detected')
        form.addRow(self.extend_full_range)
        self.viterna_blend_width_deg = QDoubleSpinBox(); self.viterna_blend_width_deg.setRange(0.0, 30.0)
        self.viterna_blend_width_deg.setValue(4.0)
        self.viterna_blend_width_deg.setSingleStep(0.5)
        self.viterna_blend_width_deg.setToolTip(
            '"airfoil.viterna_blend_width_deg" — width [deg] of the smooth transition zone between polar and Viterna; '
            'larger = more gradual stall; 0 = abrupt switch')
        self.viterna_width_label = QLabel("Viterna transition width [deg]:")
        form.addRow(self.viterna_width_label, self.viterna_blend_width_deg)

        # analytical-only widgets (a) — hidden entirely when
        # source='table' (point 1: source decides what appears, no
        # disabled-but-visible middle ground).
        self._analytical_field_widgets = [
            self.cl_alpha, self.alpha0_deg, self.cd0, self.k_coef,
            self.stall_model_combo,
            self.alpha_stall_pos, self.alpha_stall_neg,
        ]
        self._analytical_form = form

        self.source_combo.currentTextChanged.connect(self._update_source_visibility)
        self.stall_model_combo.currentTextChanged.connect(self._update_source_visibility)
        return box

    def _update_viterna_visibility(self, *_args):
        """Progressive disclosure: the Viterna fields (blend width) only
        appear when the full range extension is actually active -- source
        'table' with the toggle on, or source 'analytical' with
        stall_model='viterna'."""
        on = self._airfoil_extend_full_range()
        set_row_visible(self._analytical_form, self.viterna_blend_width_deg, on)
        self._sync_alpha_range_to_extension()

    def _update_source_visibility(self, *_args):
        """Item 6 (plano_v3.md Part 7), extended to four options: 'Source'
        now has analytical / table / neuralfoil / xfoil, each showing only
        the relevant fields. 'neuralfoil' and 'xfoil' are NOT separate
        `AirfoilDef.source` values in the data model (both remain
        `source='table'` internally, see `_collect_airfoil_def`/
        `_load_form_from_airfoil_def`). They are GUI MODES that treat the
        external generator as "a special table generated on the fly" (per
        section, when Radial sections exist): both show geometry (f) + the
        engine (g) to generate the table, and hide manual CSV import (e),
        which makes no sense in these modes. One decision, one control: the
        hidden `engine_combo` is derived from the mode ("neuralfoil",
        "xfoil", or "none")."""
        mode = self.source_combo.currentText()  # "analytical" | "table" | "neuralfoil" | "xfoil"
        is_analytical = mode == "analytical"
        is_table_like = mode in ("table", "neuralfoil", "xfoil")
        is_generated = mode in ("neuralfoil", "xfoil")

        for w in self._analytical_field_widgets:
            set_row_visible(self._analytical_form, w, is_analytical)

        set_row_visible(self._analytical_form, self.extend_full_range, is_table_like)
        if hasattr(self, "table_box"):
            self.table_box.setVisible(is_table_like)
            if mode == "neuralfoil":
                self.table_box.setTitle("Table generated by NeuralFoil (per section)")
            elif mode == "xfoil":
                self.table_box.setTitle("Table generated by XFOIL (per section)")
            else:
                self.table_box.setTitle("Data import / tabulated polar")
            self._btn_import_csv.setVisible(mode == "table")
        if hasattr(self, "geometry_box"):
            self.geometry_box.setVisible(is_generated)
        if hasattr(self, "external_box"):
            self.external_box.setVisible(is_generated)
        # 'neuralfoil' always runs with the 'neuralfoil' engine and 'xfoil'
        # with the XFOIL binary. There is no separate "Engine" combo to
        # choose it (that was the source of the reported confusion: two
        # selectors for a single decision).
        self.engine_combo.setCurrentText(mode if is_generated else "none")

        self._update_viterna_visibility()
        self._update_dynamic_stall_enabled()
        # The availability of the compressibility correction depends on
        # the source (only the table IN USE can double-count Mach), so it
        # is reevaluated here, not just when the slices list changes.
        # That was what left the toggle grayed out forever after a pass
        # through 'table'.
        self._update_prandtl_glauert_availability()

        # Item 15: suggest Reynolds/Mach only on the TRANSITION into one
        # of the generated-table modes ('neuralfoil' or 'xfoil'). This
        # method runs on every source/stall change. Without the
        # transition guard, the suggestion would overwrite the list on
        # every signal, including while loading a project.
        previous = getattr(self, "_previous_source_mode", None)
        self._previous_source_mode = mode
        if is_generated and previous != mode and not getattr(self, "_loading", False):
            self._suggest_re_mach(force=False)

    def _build_dynamic_stall_box(self) -> QGroupBox:
        """b) Dynamic stall (Øye) — only the quasi-static option
        ('frequency') stays visible (docs/plano.md Section 5, "Dynamic
        stall — static option only"); 'time_march' and the fields that
        only made sense for it (revolutions / average of last N
        revolutions) go away with it, via progressive disclosure.

        Note: dynamic_stall_method is always "frequency" in the GUI (no
        visible widget). The internal class _FixedValueHolder preserves
        the .currentText() / .setCurrentText() interface so that the
        AirfoilDef read/write code works unchanged."""
        box = QGroupBox("Dynamic Stall")
        form = QFormLayout(box)
        self.use_dynamic_stall = QCheckBox("Enable dynamic stall (Øye)")
        self.use_dynamic_stall.setToolTip(self._DYNAMIC_STALL_TOOLTIP)
        form.addRow(self.use_dynamic_stall)
        # dynamic_stall_method is always "frequency" — we don't offer UI to choose it
        self.dyn_method = _FixedValueHolder("frequency")
        self.dyn_A = QDoubleSpinBox(); self.dyn_A.setRange(0.1, 30); self.dyn_A.setValue(8.0)
        self.dyn_A.setSingleStep(0.5)
        self.dyn_A.setToolTip('"airfoil.dynamic_stall_A" — lag constant of the Øye model; controls the dynamic response speed')
        self.dyn_A_label = QLabel("Lag constant A:")
        form.addRow(self.dyn_A_label, self.dyn_A)
        self.dyn_fade_start = QDoubleSpinBox(); self.dyn_fade_start.setRange(0, 90); self.dyn_fade_start.setValue(40.0)
        self.dyn_fade_start.setSingleStep(0.5)
        self.dyn_fade_start.setToolTip('"airfoil.dynamic_stall_fade_start_deg" — angle from which the dynamic correction starts to fade out')
        self.dyn_fade_end = QDoubleSpinBox(); self.dyn_fade_end.setRange(0, 90); self.dyn_fade_end.setValue(50.0)
        self.dyn_fade_end.setSingleStep(0.5)
        self.dyn_fade_end.setToolTip('"airfoil.dynamic_stall_fade_end_deg" — angle at which the dynamic correction is fully switched off')
        self.dyn_fade_start_label = QLabel("Fade-out start [deg]:")
        self.dyn_fade_end_label = QLabel("Fade-out end [deg]:")
        form.addRow(self.dyn_fade_start_label, self.dyn_fade_start)
        form.addRow(self.dyn_fade_end_label, self.dyn_fade_end)

        # Progressive disclosure (principle 1): with the box unchecked, the
        # model parameters make no sense -- and, staying on screen, gave
        # the impression that dynamic stall is always on.
        self.use_dynamic_stall.toggled.connect(self._update_dynamic_stall_visibility)
        # Deliberate orphans (not added to the form): they only exist to
        # preserve the value of old projects that used time_march via
        # script; the GUI no longer offers editing them.
        self.dyn_revs = QSpinBox(); self.dyn_revs.setRange(1, 50); self.dyn_revs.setValue(8)
        self.dyn_avg_last = QSpinBox(); self.dyn_avg_last.setRange(1, 50); self.dyn_avg_last.setValue(3)
        self._dynamic_stall_form = form
        return box

    def _update_dynamic_stall_visibility(self, *_args):
        """Shows the Øye parameters only when the model is enabled.

        Hides the ROW (label + field) via `set_row_visible` --
        `widget.setVisible(False)` directly left the "?" help button (which
        wraps the field in a container) alone on screen, the size of the
        whole row, with the field hidden inside it.

        Note: dynamic_stall_method is not included because it has no visible widget."""
        ligado = self.use_dynamic_stall.isChecked() and self.use_dynamic_stall.isEnabled()
        for w in (self.dyn_A, self.dyn_fade_start, self.dyn_fade_end):
            set_row_visible(self._dynamic_stall_form, w, ligado)

    def _update_dynamic_stall_enabled(self, *_args):
        blocked = self.source_combo.currentText() == "analytical" and self.stall_model_combo.currentText() == "linear"
        if blocked:
            self.use_dynamic_stall.setChecked(False)
        self.use_dynamic_stall.setEnabled(not blocked)
        # The BASE tooltip is never erased. This line used to replace it with
        # "" whenever the box was not blocked -- and since it runs during
        # the tab's construction, the field ended up with no tooltip at
        # all. Two losses at once: the user did not see the explanation,
        # and `field_help` derives the field's NAME precisely from the
        # first token in quotes in the tooltip, so the help popup also
        # disappeared (that was the reported defect: "no popup and no
        # tooltip"). The restriction, when it exists, is appended to the
        # base text instead of taking its place.
        tip = self._DYNAMIC_STALL_TOOLTIP
        if blocked:
            tip += ("\n\nUnavailable here: dynamic stall needs a base polar with "
                     "real static stall ('clip'/'enhanced'/'viterna' model, or "
                     "the 'table' source).")
        self.use_dynamic_stall.setToolTip(tip)
        self._update_dynamic_stall_visibility()

    #: Preview alpha range -> (min, max, step) for `preview_polar`.
    #: "Typical" is the range in which the project's polar is read. "Full
    #: range" is the only one where you can actually SEE what Viterna/the
    #: ±180 extension did, which was the blind spot: with extend_full_range
    #: on, the extrapolation existed but was entirely off the drawn axis.
    _RANGE_TYPICAL = "Typical (-30° to 30°)"
    _RANGE_FULL = "Full range (-180° to 180°)"
    _ALPHA_RANGES = {
        _RANGE_TYPICAL: (-30.0, 30.0, 1.0),
        "Extended (-90° to 90°)": (-90.0, 90.0, 1.0),
        _RANGE_FULL: (-180.0, 180.0, 1.0),
    }

    def _build_plot_toolbar(self) -> QWidget:
        """Item 8: the HOW-TO-DRAW controls now sit in a compact strip
        above the canvas, on the right, no longer in a QGroupBox
        ("Comparative Visualization") lost in the middle of the form on
        the left, where they competed for width with the project fields
        and ended up out of view.

        Design consequence that needs to keep holding: these are DISPLAY
        controls (`_VIEW_ONLY`). They redraw the canvas but
        NEVER call `_apply_to_project`; otherwise adjusting a chart's
        scale would mark the project as unsaved. Since they now live
        outside `left_widget`, the constructor's generic `findChildren`
        connections don't reach them: each signal is wired explicitly in
        `_wire_plot_toolbar`."""
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 4)
        row.setSpacing(8)

        alpha_lbl = QLabel("Alpha:")
        alpha_lbl.setToolTip("Polar angle-of-attack range shown in the preview")
        alpha_lbl.setToolTip(
            "Angle-of-attack span drawn in the polar preview. Pick 'Full range' to actually see "
            "the Viterna / full-range extrapolation — in the typical span it lies entirely off-axis. "
            "Zooming the axes with the toolbar does NOT recompute the curves; this control does.")
        row.addWidget(alpha_lbl)
        self.alpha_range_combo = QComboBox()
        self.alpha_range_combo.addItems(list(self._ALPHA_RANGES))
        self.alpha_range_combo.setToolTip(alpha_lbl.toolTip())
        adjust_combo_width(self.alpha_range_combo)
        row.addWidget(self.alpha_range_combo)

        self.autoscale_y_check = QCheckBox("Auto-fit Y")
        self.autoscale_y_check.setChecked(True)
        self.autoscale_y_check.setToolTip(
            "On: each axis fits its own curves. Off: Cl/Cd keep a fixed span, so curves stay "
            "comparable between two different airfoils/settings instead of both filling the frame.")
        row.addWidget(self.autoscale_y_check)

        self.show_reverse_branch_check = QCheckBox("Reverse-flow branch")
        self.show_reverse_branch_check.setChecked(True)
        self.show_reverse_branch_check.setToolTip(
            "Overlays the curve the engine actually uses where the section sees reverse flow "
            "(U<sub>t</sub> &lt; 0), per the Reverse flow model in the form. For 'thin_plate_blend' both branches "
            "coincide by construction — its blend depends on |&alpha;| only, not on the sign of U<sub>t</sub>.")
        row.addWidget(self.show_reverse_branch_check)

        mach_lbl = QLabel("Machs:")
        mach_lbl.setToolTip("List of Mach values (comma-separated) to overlay curves in the preview")
        row.addWidget(mach_lbl)
        self.mach_compare_edit = QLineEdit("0.0, 0.3, 0.5, 0.7")
        self.mach_compare_edit.setToolTip("E.g.: 0.0, 0.3, 0.5, 0.7 — adds one curve per Mach to the chart")
        self.mach_compare_edit.setMaximumWidth(170)
        row.addWidget(self.mach_compare_edit)
        row.addStretch(1)
        return bar

    def _wire_plot_toolbar(self):
        """Wires the signals of the canvas control strip. Explicit on
        purpose: these widgets are OUTSIDE `left_widget`, so the
        constructor's generic (`findChildren`) connections don't see
        them, and forgetting this fails silently (the control appears on
        screen and simply does nothing)."""
        self.alpha_range_combo.currentTextChanged.connect(self._schedule_preview_refresh)
        # `activated` fires only on user interaction, never on programmatic
        # `setCurrentText`. That's what distinguishes "the user chose a
        # range" from "the tab adjusted the range on its own".
        self.alpha_range_combo.activated.connect(self._on_alpha_range_chosen)
        self.autoscale_y_check.toggled.connect(self._schedule_preview_refresh)
        self.show_reverse_branch_check.toggled.connect(self._schedule_preview_refresh)
        self.mach_compare_edit.editingFinished.connect(self._schedule_preview_refresh)

    def _on_alpha_range_chosen(self, _index: int):
        self._alpha_range_chosen_by_user = True

    def _sync_alpha_range_to_extension(self):
        """Item 6: when the full range extension (Viterna ±180°) is
        active, the drawn range defaults to the full one.

        Reason: the extrapolation existed and was correct, but the preview
        kept being computed only from -30° to 30°. The user's
        natural way out (opening 'Edit axis, curve and image parameters'
        on the matplotlib toolbar and setting the X axis to ±180) only
        RESCALES the axes, it does not recompute the curve. The result is
        an empty chart from 30° onward, which reads as "the extension
        doesn't work". Respects an explicit user choice in the combo (see
        `_on_alpha_range_chosen`)."""
        if getattr(self, "_alpha_range_chosen_by_user", False):
            return
        if not hasattr(self, "alpha_range_combo"):
            return
        target = self._RANGE_FULL if self._airfoil_extend_full_range() else self._RANGE_TYPICAL
        if self.alpha_range_combo.currentText() != target:
            self.alpha_range_combo.setCurrentText(target)

    def _alpha_range(self) -> tuple:
        return self._ALPHA_RANGES[self.alpha_range_combo.currentText()]

    def _build_table_box(self) -> QGroupBox:
        box = QGroupBox("Aerodynamic Polar Data")
        self.table_box = box
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        btn_import = QPushButton("Import CSV…")
        btn_import.setToolTip(self._CSV_IMPORT_TOOLTIP)
        btn_import.clicked.connect(self._import_csv)
        self._btn_import_csv = btn_import
        btn_export = QPushButton("Export CSV…")
        btn_export.setToolTip(
            "Writes the current polar in the same CSV format the importer "
            "reads — one row per angle of attack, with a column for each of "
            "r/R, Reynolds and Mach that this polar actually uses. Exporting "
            "once is the quickest way to get a template to fill in.")
        btn_export.clicked.connect(self._export_csv)
        row.addWidget(btn_import)
        row.addWidget(btn_export)
        row.addStretch(1)
        layout.addLayout(row)
        #: the two read as a pair: same width (see `showEvent`)
        self._table_buttons = (btn_import, btn_export)

        # The same text as the button, visible without having to discover
        # there is a tooltip: whoever reaches this block is precisely
        # trying to assemble the file. `_CSV_IMPORT_TOOLTIP` is the
        # single source for both screens.
        format_hint = QLabel(
            'Expected file: one line per angle of attack, columns '
            '<code>alpha_deg, Cl, Cd</code> — plus <code>r_norm</code>, '
            '<code>reynolds</code> and/or <code>mach</code> repeated on every '
            'line to declare a sweep. Hover "Import CSV…" for the full format '
            'with examples.')
        format_hint.setWordWrap(True)
        format_hint.setStyleSheet("color: #666; font-size: 11px;")
        format_hint.setToolTip(self._CSV_IMPORT_TOOLTIP)
        layout.addWidget(format_hint)
        self._csv_format_tooltip = format_hint

        self.detected_axes_label = QLabel("No data imported yet.")
        self.detected_axes_label.setWordWrap(True)
        layout.addWidget(self.detected_axes_label)

        layout.addWidget(QLabel("Available conditions (check = overlay in preview):"))
        self.slices_list = QListWidget()
        self.slices_list.setMaximumHeight(120)
        self.slices_list.itemChanged.connect(self._schedule_preview_refresh)
        layout.addWidget(self.slices_list)
        return box

    #: Help text for the tabulated polar IMPORTER. The previous text only
    #: said "imports a polar CSV" -- whoever had never seen the format had
    #: no way to assemble the file. Here is the entire contract of
    #: `airfoils.import_polar_csv`: which columns, what a row is, what a
    #: block is, and how a Reynolds/Mach/radial station sweep is declared
    #: (the answer is the same for all three: one extra COLUMN, repeated
    #: on every row of the block).
    _CSV_IMPORT_TOOLTIP = (
        "Imports a Cl/Cd polar from a CSV, as one or more slices.\n\n"
        "ONE LINE = ONE ANGLE OF ATTACK. The file is a plain table with a "
        "header line and one row per point:\n"
        "    alpha_deg,Cl,Cd\n"
        "    -5,-0.32,0.0121\n"
        "    0,0.21,0.0098\n"
        "    5,0.74,0.0115\n\n"
        "REQUIRED COLUMNS: alpha_deg (degrees), Cl and Cd. Names are matched "
        "case-insensitively and common spellings are accepted: alpha_deg, "
        "alpha, aoa and aoa_deg for the angle, CL / cl and CD / cd for the "
        "coefficients. "
        "Any other column is ignored.\n\n"
        "OPTIONAL COLUMNS — this is how a sweep is declared: add r_norm "
        "(also accepted: r/R, radial_station), reynolds (Re) and/or mach (M). "
        "Every row carries the value of the condition it belongs to, repeated:\n"
        "    alpha_deg,Cl,Cd,reynolds,mach\n"
        "    -5,-0.30,0.0140,200000,0.2\n"
        "     0,0.19,0.0115,200000,0.2\n"
        "    -5,-0.32,0.0121,600000,0.2\n"
        "     0,0.21,0.0098,600000,0.2\n\n"
        "ONE BLOCK = ONE COMBINATION of the optional columns. The rows above "
        "make two slices (Re=2e5 and Re=6e5, both at Mach 0.2), each with its "
        "own sweep in angle of attack. Rows do not need to be sorted or grouped together — "
        "they are collected by value, not by position. The same file may carry "
        "r/R, Reynolds and Mach at once: the engine then interpolates the "
        "polar in every axis present, per radial station and flight condition.\n\n"
        "With no optional column at all, the file is a single polar used "
        "everywhere on the blade.\n\n"
        "The importer shows which columns it recognized before anything is "
        "applied, and 'Export CSV…' writes this very format — export once to "
        "have a template to fill in."
    )

    #: Help text for the contour import button. It is the answer to the
    #: user's question ("does the same .dat work for any generator?"): yes,
    #: it does. An imported contour is NOT another generation "family":
    #: it is the final list of points, and it replaces whatever any
    #: generator would produce.
    _DAT_IMPORT_TOOLTIP = (
        "Loads the contour from a coordinate file and uses it as the profile, "
        "whatever the source above was — an imported contour is the final list "
        "of points, not another family to generate from.\n\n"
        "WHAT THE FILE MUST CONTAIN: one point per line, two numbers — x then "
        "y, both normalized by the chord — separated by space, tab or comma:\n"
        "    1.000000   0.001300\n"
        "    0.500000   0.065000\n"
        "    0.000000   0.000000\n"
        "    0.500000  -0.035000\n"
        "    1.000000  -0.001300\n\n"
        "Any line that is not a pair of numbers is skipped, so a profile name, "
        "a header or a comment line costs nothing. The extension does not "
        "matter (.dat, .txt and .csv are offered); the content decides.\n\n"
        "SELIG format works as downloaded (UIUC / airfoiltools): a name line "
        "followed by a single loop — trailing edge, over the upper surface, "
        "around the leading edge, back along the lower surface, trailing "
        "edge.\n\n"
        "LEDNICER format needs editing first, and the import will say so "
        "rather than accept it: it starts with a line holding the number of "
        "points of each surface (\"61.  61.\"), which reads as a coordinate, "
        "and it lists the two surfaces separately, both starting at the "
        "leading edge. Delete that first numeric line and join the surfaces "
        "into one loop — or simply download the Selig version of the same "
        "airfoil.\n\n"
        "The points are used exactly as given: no reordering, no closing of "
        "the trailing edge, no rescaling. x should span 0 to 1.")

    #: CONTOUR sources offered on screen. CST and Bézier are first-class
    #: options again (user decision reversing the earlier request that had
    #: removed them from this dropdown): the generators
    #: (`airfoils.generate_cst`/`generate_bezier`) and their editor fields
    #: below never left the code -- only the list here hid them.
    _PROFILE_SOURCES = ("naca4", "naca5", "cst", "bezier", "imported")

    def _build_geometry_box(self) -> QGroupBox:
        box = QGroupBox("2D Profile Geometry")
        self.geometry_box = box
        form = QFormLayout(box)

        # Full geometry specification in one string, resolved by
        # `airfoils.resolve_geometry_spec` -- the SAME entry point the CLI's
        # `--airfoil-geometry` uses. When non-empty it takes precedence over
        # the Source/NACA fields above, which is what gives on-screen access
        # to the analytic families (parsec/joukowski/biconvex), to CST and
        # Bezier, and to the presets catalog.
        self.geometry_spec_edit = QLineEdit()
        self.geometry_spec_edit.setToolTip(
            '"geometry_spec" — complete description of the 2D contour in a single '
            "string, resolved by the same engine as the CLI's --airfoil-geometry "
            "flag. Accepted grammars:\n\n"
            "• preset nickname — naca0012, naca23012, naca4412, parsec_default, "
            "joukowski_t8c5, biconvex_t6;\n"
            "• NACA code — naca2412 or just 2412 (4 digits), naca23012 or 23012 "
            "(5 digits);\n"
            "• cst:a1,a2,... — CST coefficients, an even count (4 or more), split "
            "half into the upper surface and half into the lower;\n"
            "• bezier:x1,y1;x2,y2;... — control points as x,y pairs separated by "
            "semicolons;\n"
            "• parsec:r_le,x_up,y_up,y_xx_up,x_lo,y_lo,y_xx_lo,th_te,beta_te_deg — "
            "nine numbers, the trailing-edge angle last and in degrees;\n"
            "• joukowski:epsilon,camber — two numbers;\n"
            "• biconvex:thickness — one number, 0 allowed (a slit);\n"
            "• dat:path/to/file.dat — reads the contour from a coordinate file.\n\n"
            "When this field is non-empty it takes precedence over the Source and "
            "NACA fields: 'Generate geometry' resolves THIS string first. Leave it "
            "empty to use the fields above.")
        form.addRow("Geometry spec:", self.geometry_spec_edit)

        # No "typical preset" combo: the NACA entries of
        # `airfoils.AIRFOIL_PRESETS` are all NACA codes (0009, 0012,
        # 0015, 0018, 23012, 4412), so the preset and the "NACA code"
        # field right below were two controls for a single decision --
        # choosing in the combo just wrote the code into the field. What
        # the preset added was the NOTE ("what is typical of what"), and
        # it moved to the NACA field's help, where it is read at the
        # moment the code is typed. The catalog keeps existing for the CLI
        # (`--airfoil-geometry naca0012`) and for scripts, and every
        # family -- including the analytic presets -- is reachable on
        # screen through the Geometry spec field above.
        self.profile_source_combo = QComboBox()
        for source_name in self._PROFILE_SOURCES:
            self.profile_source_combo.addItem(source_name)
        self.profile_source_combo.setMinimumWidth(130)
        # No quoted token on purpose: the field is called `source`, the
        # same name as the POLAR's source, and `field_help._campo_do_widget`
        # only looks at the last segment -- the help would land on the
        # wrong section.
        self.profile_source_combo.setToolTip(
            "How the 2D contour of the profile is described. The contour "
            "feeds the drawing and the external solver; it does not feed the "
            "engine directly, which reads lift and drag from the polar.")
        form.addRow("Source:", self.profile_source_combo)
        # Progressive reveal must follow the combo LIVE: without this
        # connection the editor rows only matched the selection at build
        # time and on project load, and picking another source left the
        # previous family's fields on screen (rot that stayed hidden while
        # cst/bezier were out of the list, since naca4/naca5 share one row).
        self.profile_source_combo.currentTextChanged.connect(self._update_profile_fields)

        self.naca_code_edit = QLineEdit("2412")
        self.naca_code_edit.setToolTip(
            '"naca_code" — the NACA designation of the profile. In the '
            "4-digit family the first digit is the maximum camber as a "
            "percentage of chord, the second its chordwise position in tenths, "
            "and the last two the maximum thickness as a percentage of chord. "
            "Camber shifts the zero-lift angle negative; thickness governs how "
            "gently the profile stalls.\n\n"
            "Sections in common rotor use: " + NACA_CATALOG_TEXT())
        form.addRow("NACA code:", self.naca_code_edit)

        self.cst_upper_edit = QLineEdit("0.17, 0.16, 0.20, 0.18")
        self.cst_upper_edit.setToolTip(
            '"cst_upper" — Bernstein weights of the upper surface in the CST '
            "(class/shape transformation) description. Each weight raises or "
            "lowers the surface near one chordwise station; the first governs "
            "the leading-edge radius, the last the trailing-edge angle.")
        self.cst_lower_edit = QLineEdit("-0.12, -0.10, -0.08, -0.05")
        self.cst_lower_edit.setToolTip(
            '"cst_lower" — Bernstein weights of the lower surface, in the same '
            "convention as the upper set. Negative values put the surface "
            "below the chord line; the gap between the two sets at a given "
            "station is the local thickness, and their mean is the camber.")
        form.addRow("CST upper (coefs, comma):", self.cst_upper_edit)
        form.addRow("CST lower (coefs, comma):", self.cst_lower_edit)

        # Order: trailing edge -> upper surface -> leading edge -> lower
        # surface -> trailing edge (the list CLOSES at the trailing edge,
        # see the convention in `airfoils.generate_bezier`). The old
        # default closed at the leading edge ("0,0 / 0.3,0.08 / 1,0 /
        # 0.3,-0.05 / 0,0") and came out with the blunt nose at the back
        # and the point at the front.
        self.bezier_points_edit = QPlainTextEdit(
            "1,0\n0.5,0.12\n0,0.15\n-0.05,0\n0,-0.10\n0.5,-0.06\n1,0")
        self.bezier_points_edit.setMaximumHeight(70)
        self.bezier_points_edit.setToolTip(
            '"bezier_control_points" — control polygon of the contour, one '
            "x,y pair per line, running from the trailing edge over the upper "
            "surface, around the leading edge and back along the lower "
            "surface. The curve is pulled toward each point without passing "
            "through it, so points crowded near the nose sharpen the "
            "leading-edge radius.")
        form.addRow("Bézier (x,y per line):", self.bezier_points_edit)

        row = QHBoxLayout()
        btn_generate_profile = QPushButton("Generate geometry")
        btn_generate_profile.setToolTip(
            "Builds the contour from the fields above and draws it in the "
            "Profile tab on the right. It only redraws the shape — the polar, "
            "and with it the engine, changes only when the external engine "
            "runs (NeuralFoil or XFOIL).")
        btn_generate_profile.clicked.connect(self._generate_profile)
        btn_import_dat = QPushButton("Import .dat…")
        btn_import_dat.setToolTip(self._DAT_IMPORT_TOOLTIP)
        btn_import_dat.clicked.connect(self._import_dat)
        row.addWidget(btn_generate_profile)
        row.addWidget(btn_import_dat)
        form.addRow(row)
        # The two read as a pair ("generate OR import"): same width.
        self._geometry_buttons = (btn_generate_profile, btn_import_dat)
        #: kept to hide the entire ROW of contour fields (label included)
        #: -- see `_update_profile_fields`
        self._geometry_form = form

        self._update_profile_fields(self.profile_source_combo.currentText())
        return box

    def _build_external_box(self) -> QGroupBox:
        box = QGroupBox("Polar Generation via External Engine")
        self.external_box = box
        form = QFormLayout(box)

        # `engine_combo` is not displayed — its value is DERIVED from the
        # polar Source mode, one-to-one across the four options (see
        # `_update_source_visibility`): 'neuralfoil' -> 'neuralfoil',
        # 'xfoil' -> 'xfoil', anything else -> 'none'. Kept for
        # compatibility with `_collect_airfoil_def` /
        # `_load_form_from_airfoil_def`, which read it as the persisted
        # `external_engine`.
        # 'xfoil' runs the XFOIL binary; the GUI checks for it (ZBEMT_XFOIL_BIN
        # or PATH) at the moment the user clicks Run.
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["none", "neuralfoil", "xfoil"])

        self.re_list_edit = QLineEdit("1e5, 2e5, 5e5, 1e6")
        self.re_list_edit.setToolTip('"airfoil.external_reynolds_list" — Reynolds values suggested automatically based on the blade\'s typical envelope')
        self.mach_list_edit = QLineEdit("0.0, 0.1, 0.2, 0.3, 0.4, 0.5")
        self.mach_list_edit.setToolTip('"airfoil.external_mach_list" — Mach values suggested automatically based on the blade\'s typical envelope')
        form.addRow("Reynolds (list, commas):", self.re_list_edit)
        form.addRow("Mach (list, commas):", self.mach_list_edit)

        self.btn_suggest_re_mach = QPushButton("Suggest from rotor")
        self.btn_suggest_re_mach.setToolTip(
            "Fills the two lists above with three Reynolds and three Mach values bracketing the "
            "blade's operating point — computed in closed form from radius, chord distribution, "
            "RPM and the atmosphere (nu_air, a_sound). Nothing is solved; no engine run.")
        self.btn_suggest_re_mach.clicked.connect(lambda: self._suggest_re_mach(force=True))
        self.suggestion_label = QLabel("")
        self.suggestion_label.setWordWrap(True)
        self.suggestion_label.setStyleSheet("color: #666; font-size: 11px;")
        form.addRow(self.btn_suggest_re_mach)
        form.addRow(self.suggestion_label)

        self.ext_alpha_min = QDoubleSpinBox(); self.ext_alpha_min.setRange(-90, 90); self.ext_alpha_min.setValue(-20)
        self.ext_alpha_min.setSingleStep(0.5)
        self.ext_alpha_min.setToolTip('"airfoil.external_alpha_min_deg" — minimum angle of attack of the sweep')
        self.ext_alpha_max = QDoubleSpinBox(); self.ext_alpha_max.setRange(-90, 90); self.ext_alpha_max.setValue(20)
        self.ext_alpha_max.setSingleStep(0.5)
        self.ext_alpha_max.setToolTip('"airfoil.external_alpha_max_deg" — maximum angle of attack of the sweep')
        self.ext_alpha_step = QDoubleSpinBox(); self.ext_alpha_step.setRange(0.05, 10); self.ext_alpha_step.setValue(0.5)
        self.ext_alpha_step.setSingleStep(0.05)
        self.ext_alpha_step.setToolTip('"airfoil.external_alpha_step_deg" — angle of attack increment between points')
        form.addRow("Minimum alpha [deg]:", self.ext_alpha_min)
        form.addRow("Maximum alpha [deg]:", self.ext_alpha_max)
        form.addRow("Alpha step [deg]:", self.ext_alpha_step)

        # XFOIL-dedicated adjustment inputs (AirfoilDef.xfoil_ncrit /
        # xfoil_xtr_top / xfoil_xtr_bot). The rows appear only when the
        # engine is xfoil (see _update_xfoil_visibility); the values are
        # collected and loaded like the sibling external_* fields, so they
        # round-trip through airfoil.bemt even while hidden.
        self.ext_ncrit = QDoubleSpinBox()
        self.ext_ncrit.setRange(1.0, 15.0)
        self.ext_ncrit.setDecimals(2)
        self.ext_ncrit.setValue(9.0)
        self.ext_ncrit.setSingleStep(0.5)
        self.ext_ncrit.setToolTip(
            '"xfoil_ncrit" — critical amplification factor N of the '
            'e<sup>N</sup> transition criterion. The boundary layer turns '
            'turbulent where the amplification of small disturbances reaches '
            'e<sup>N</sup>. A lower N predicts earlier transition and higher '
            'drag; 9 approximates a clean flow (typical range: 1 to 15). This '
            'input reaches only the XFOIL binary; NeuralFoil ignores it.')
        form.addRow("Ncrit:", self.ext_ncrit)

        self.ext_xtr_top = QDoubleSpinBox()
        self.ext_xtr_top.setRange(0.01, 1.0)
        self.ext_xtr_top.setDecimals(2)
        self.ext_xtr_top.setValue(1.0)
        self.ext_xtr_top.setSingleStep(0.05)
        self.ext_xtr_top.setToolTip(
            '"xfoil_xtr_top" — chord fraction where transition is FORCED on '
            'the upper surface, in (0,&nbsp;1]. XFOIL fixes transition at that '
            'station instead of predicting it; 1 leaves free transition on the '
            'whole surface. This input reaches only the XFOIL binary; NeuralFoil '
            'ignores it.')
        form.addRow("Xtr top:", self.ext_xtr_top)

        self.ext_xtr_bot = QDoubleSpinBox()
        self.ext_xtr_bot.setRange(0.01, 1.0)
        self.ext_xtr_bot.setDecimals(2)
        self.ext_xtr_bot.setValue(1.0)
        self.ext_xtr_bot.setSingleStep(0.05)
        self.ext_xtr_bot.setToolTip(
            '"xfoil_xtr_bot" — chord fraction where transition is FORCED on '
            'the lower surface, in (0,&nbsp;1]. XFOIL fixes transition at that '
            'station instead of predicting it; 1 leaves free transition on the '
            'whole surface. This input reaches only the XFOIL binary; NeuralFoil '
            'ignores it.')
        form.addRow("Xtr bot:", self.ext_xtr_bot)
        #: stored to hide the three rows above as a unit
        #: (see `_update_xfoil_visibility`)
        self._external_form = form
        self.engine_combo.currentTextChanged.connect(self._update_xfoil_visibility)
        self._update_xfoil_visibility()

        row = QHBoxLayout()
        self.btn_run_external = QPushButton("Run polar generation")
        # Stays CLICKABLE even without the package or the binary: the
        # click opens a dialog explaining what is missing
        # (`require_optional_package` for neuralfoil,
        # `require_optional_binary` for xfoil). A disabled button only
        # stated the reason in a tooltip.
        self.btn_run_external.setToolTip(
            "Generates a Cl/Cd×α polar for each Reynolds×Mach combination with the "
            "selected external engine (neuralfoil: neural network; xfoil: XFOIL binary "
            "found via ZBEMT_XFOIL_BIN or PATH)")
        self.btn_run_external.clicked.connect(self._run_external)
        self.btn_cancel_external = QPushButton("Cancel")
        self.btn_cancel_external.setVisible(False)
        self.btn_cancel_external.setToolTip(
            "The engine cannot be interrupted mid-point (α) once it's already computing -- "
            "cancel only discards the result when it finishes, instead of applying it.")
        self.btn_cancel_external.clicked.connect(self._cancel_external)
        self.btn_export_external = QPushButton("Export generated table…")
        self.btn_export_external.setEnabled(False)
        self.btn_export_external.clicked.connect(self._export_external_table)
        row.addWidget(self.btn_run_external)
        row.addWidget(self.btn_cancel_external)
        row.addWidget(self.btn_export_external)
        form.addRow(row)
        self.progress_external = QProgressBar()
        self.progress_external.setVisible(False)
        self.progress_external.setRange(0, 0)  # indeterminate: the engine does not report per-point progress
        self.status_label_external = QLabel("")
        form.addRow(self.progress_external)
        form.addRow(self.status_label_external)
        return box

    def _update_xfoil_visibility(self, *_args):
        """Progressive disclosure: Ncrit and the two Xtr inputs describe
        transition options of the XFOIL binary alone, so their rows appear
        only when `engine_combo` is 'xfoil'. The rows hide through
        `set_row_visible` so the label never stays on screen pointing at
        nothing; the values themselves keep round-tripping while hidden."""
        show = self.engine_combo.currentText() == "xfoil"
        for w in (self.ext_ncrit, self.ext_xtr_top, self.ext_xtr_bot):
            set_row_visible(self._external_form, w, show)

    #: RPM used in the item 15 estimate when the project has no saved
    #: case -- the same default as `cli.DEFAULT_RPM` and the RPM field in
    #: the Run Case tab, so the suggestion matches what the user is going
    #: to run.
    _DEFAULT_SUGGESTION_RPM = 600.0

    def _reference_rpm(self) -> float:
        """Representative RPM for the project, without running anything:
        the first saved case that declares one, else the first one of the
        first batch, else the GUI/CLI default. RPM is not a `Project`
        field -- it lives in `FlightCondition` -- so an estimate by
        geometry needs to pick one, and picking explicitly is better than
        pretending a canonical value exists."""
        project = self.state.project
        if project is not None:
            candidates = list(project.saved_cases)
            for b in project.batches:
                candidates.extend(b.conditions)
            for c in candidates:
                if getattr(c, "rpm", None):
                    return float(c.rpm)
        return self._DEFAULT_SUGGESTION_RPM

    def _reference_mu(self) -> float:
        """Representative advance ratio of the project, chosen with the
        SAME rule as RPM (see `_reference_rpm`): the first saved
        condition that declares one, else 0 (hover).

        The largest mu_x among the conditions, not the first: the
        suggested list is an ENVELOPE, and an envelope that doesn't cover
        the project's fastest condition is useless."""
        project = self.state.project
        if project is None:
            return 0.0
        candidates = list(project.saved_cases)
        for b in project.batches:
            candidates.extend(b.conditions)
        mus = [abs(float(getattr(c, "mu_x", 0.0) or 0.0)) for c in candidates]
        return max(mus) if mus else 0.0

    def _re_suggest_re_mach(self, *_args):
        """Reacts to a change in the project's geometry/condition.

        The suggestion used to depend only on the instant the source
        switched to 'neuralfoil': changing the radius, chord, RPM or
        advance speed AFTER that left an envelope on screen that was
        computed for a different rotor. It keeps respecting the list the
        user typed by hand (`_re_mach_user_edited`), and only
        acts in the mode where these lists exist.

        The reentrancy guard is not decorative: `_suggest_re_mach` ends in
        `_apply_to_project`, which NOTIFIES the project -- and that is
        precisely one of the signals that brings this control back here.
        Without it, a geometry edit would enter infinite recursion and
        crash the process with a stack overflow (a native failure, with no
        Python exception)."""
        if getattr(self, "_loading", False) or getattr(self, "_suggesting", False):
            return
        if getattr(self, "_applying_locally", False):
            return
        # Both generated-table modes carry these lists ('neuralfoil' and
        # 'xfoil'); in the other modes the fields do not even appear.
        if self.source_combo.currentText() not in ("neuralfoil", "xfoil"):
            return
        self._suggesting = True
        try:
            self._suggest_re_mach(force=False)
        finally:
            self._suggesting = False

    def _suggest_re_mach(self, force: bool = False):
        """Item 15: fills the generated-table Reynolds/Mach lists (used by
        both NeuralFoil and XFOIL) with three values each, bracketing the
        blade's operating point (`airfoils.suggest_reynolds_mach_lists` --
        closed form, no engine run).

        With ``force=False`` (automatic call when entering one of the
        generated modes) respects lists the user has already typed; the
        "Suggest from rotor" button calls with ``force=True``."""
        if not force and self._re_mach_user_edited:
            return
        project = self.state.project
        if project is None:
            if force:
                self.suggestion_label.setText("No project open — nothing to estimate from.")
            return
        cfg = dict(project.config)
        rpm = self._reference_rpm()
        mu_x = self._reference_mu()
        suggestion = airfoils.suggest_reynolds_mach_lists(
            project.geometry, rpm,
            nu_air=float(cfg.get("nu_air", 1.46e-5)),
            a_sound=float(cfg.get("a_sound", 340.294)),
            mu_x=mu_x,
        )
        if not suggestion["reynolds"] and not suggestion["mach"]:
            if force:
                self.suggestion_label.setText(
                    "Could not estimate: the radial table needs at least 2 stations "
                    "and a positive radius/RPM.")
            return
        if suggestion["reynolds"]:
            self.re_list_edit.setText(", ".join(f"{v:.3g}" for v in suggestion["reynolds"]))
        if suggestion["mach"]:
            self.mach_list_edit.setText(", ".join(f"{v:.2f}" for v in suggestion["mach"]))
        stations_text = ", ".join(f"r/R={r:g}" for r in airfoils.SUGGESTION_STATIONS)
        # mu_x only enters the text when it is nonzero: in hover the
        # phrase would say "and mu_x=0" to explain a term that added
        # nothing.
        advance_text = f" at μ={mu_x:g}" if mu_x else ""
        self.suggestion_label.setText(
            f"Estimated at {stations_text} for R={project.geometry.radius_m:g} m and {rpm:g} RPM"
            f"{advance_text} (closed form: Re=U·c/ν, M=U/a, U=ΩR(r/R+|μ|)). It follows the project: "
            "change the blade, the RPM or the fastest condition and this list is redrawn — "
            "until you type your own, which is then kept.")
        self._apply_to_project()

    def _on_re_mach_edited(self, *_args):
        self._re_mach_user_edited = True

    def _build_out_of_curve_box(self) -> QGroupBox:
        """"Behavior outside the pasted curve": reverse flow and
        compressibility, relocated from Config/Engine to here
        (docs/plano.md Section 4) -- they physically describe how the
        airfoil behaves in extreme conditions, even though they remain,
        in the dataclass, as BEMTConfig fields (not AirfoilDef). Only the
        widget's location changes; they write to the SAME project.config
        as always."""
        box = QGroupBox("Compressibility and Reverse Flow Effects")
        outer = QVBoxLayout(box)

        rf_box = QGroupBox("Reverse flow")
        form = QFormLayout(rf_box)
        self.cfg_reverse_flow_model = QComboBox()
        self._refresh_reverse_flow_options()
        self.cfg_reverse_flow_model.setMinimumWidth(222)
        self.cfg_reverse_flow_model.setToolTip(
            '"reverse_flow_model" — '
            '"simple_flip": mirrored Cl/Cd; '
            '"flat_plate": flat plate model; '
            '"alpha_blending": angle blending; '
            '"thin_plate_blend": smooth thin plate; '
            '"viterna_full_range": Viterna ±180° (requires full range extension)')
        form.addRow("Reverse flow model:", self.cfg_reverse_flow_model)
        self.cfg_reverse_flow_blend_factor = QDoubleSpinBox(); self.cfg_reverse_flow_blend_factor.setRange(0.1, 50.0)
        self.cfg_reverse_flow_blend_factor.setSingleStep(0.5)
        self.cfg_reverse_flow_blend_factor.setToolTip('"reverse_flow_blend_factor" — controls smoothness of transition between forward and reverse flow regimes')
        form.addRow("Reverse flow blend factor:", self.cfg_reverse_flow_blend_factor)
        self.cfg_thin_plate_center = QDoubleSpinBox(); self.cfg_thin_plate_center.setRange(0, 90)
        self.cfg_thin_plate_center.setSingleStep(0.5)
        self.cfg_thin_plate_center.setToolTip('"thin_plate_blend_center_deg" — center angle of blend zone for thin_plate_blend model')
        self.cfg_thin_plate_width = QDoubleSpinBox(); self.cfg_thin_plate_width.setRange(0.1, 90)
        self.cfg_thin_plate_width.setSingleStep(0.5)
        self.cfg_thin_plate_width.setToolTip('"thin_plate_blend_width_deg" — width [deg] of blend zone for thin_plate_blend model')
        form.addRow("Blend zone center [deg]:", self.cfg_thin_plate_center)
        form.addRow("Blend zone width [deg]:", self.cfg_thin_plate_width)
        # Q5: this text was recomputed on every source/stall change and
        # never reached the screen -- `setVisible(True)` was never called
        # anywhere. It is exactly the explanation missing for whoever
        # looks for 'viterna_full_range' in the dropdown and can't find it.
        self.reverse_flow_note = QLabel()
        self.reverse_flow_note.setWordWrap(True)
        self.reverse_flow_note.setStyleSheet("color: #666; font-size: 11px;")
        form.addRow(self.reverse_flow_note)
        #: stored to hide the note's ROW (see `_update_reverse_flow_note`)
        self._reverse_flow_form = form
        # "Mask reverse flow" moved out of here (item 10): it is a
        # DRAWING choice -- it hides the Ut<0 region in disk maps and
        # does not touch physics, force, or the CSV --, so it lives only
        # on the Results tab, next to the plot it affects. Here, among
        # the reverse flow models, it looked more like a modeling option.
        outer.addWidget(rf_box)

        comp_box = QGroupBox("Compressibility")
        cform = QFormLayout(comp_box)
        self.cfg_use_compressibility = QCheckBox("Apply compressibility correction (Prandtl-Glauert)")
        #: value stored while the toggle is locked by the table's Mach
        #: dependency, restored on re-enabling (see `_update_prandtl_glauert_availability`)
        self._compressibilidade_antes_do_bloqueio = None
        self.cfg_use_compressibility.setToolTip(
            '"use_compressibility" — corrects Cl and Cd by factor 1/√(1−M²); '
            'do not use with tables that already vary with Mach (double counting)')
        cform.addRow(self.cfg_use_compressibility)
        outer.addWidget(comp_box)

        self.extend_full_range.toggled.connect(lambda _v: self._refresh_reverse_flow_options(keep_current=True))
        self.extend_full_range.toggled.connect(self._update_reverse_flow_note)
        self.stall_model_combo.currentTextChanged.connect(lambda _v: self._refresh_reverse_flow_options(keep_current=True))
        self.stall_model_combo.currentTextChanged.connect(self._update_reverse_flow_note)
        self.source_combo.currentTextChanged.connect(lambda _v: self._refresh_reverse_flow_options(keep_current=True))
        self.source_combo.currentTextChanged.connect(self._update_reverse_flow_note)
        # Initial state: without this call the note's row starts out
        # visible and empty (a blank strip in the middle of the form)
        # when the full-range extension is already on.
        self._update_reverse_flow_note()
        return box

    def _airfoil_extend_full_range(self) -> bool:
        """Mirrors `models.uses_full_range_extension` from the GUI's
        current state (before an AirfoilDef exists yet): the table-like
        sources ('table', 'neuralfoil', 'xfoil') -> explicit toggle; any
        other source -> stall_model == 'viterna'."""
        if self.source_combo.currentText() in ("table", "neuralfoil", "xfoil"):
            return self.extend_full_range.isChecked()
        return self.stall_model_combo.currentText() == "viterna"

    def _refresh_reverse_flow_options(self, keep_current: bool = False):
        """Offers every reverse-flow model, disabling the one the current
        airfoil cannot supply.

        `viterna_full_range` needs a polar extended to the full circle,
        which only some sources produce. It used to be REMOVED from the
        list while unavailable, which left no way to discover that the
        model exists, and made the note below the only evidence of it.
        PR-2 draws the line here: a control with nothing to say is hidden,
        a control that is real but blocked is shown disabled. This one is
        blocked, so it stays, greyed out, with the note saying what would
        unlock it."""
        current = self.cfg_reverse_flow_model.currentText() if keep_current else None
        # List coming from the ENGINE (`bemt.REVERSE_FLOW_MODELS`), not a
        # local copy: a new model shows up here on its own.
        from ...bemt import REVERSE_FLOW_MODELS
        options = list(REVERSE_FLOW_MODELS)
        enabled = self._airfoil_extend_full_range()
        self.cfg_reverse_flow_model.blockSignals(True)
        self.cfg_reverse_flow_model.clear()
        self.cfg_reverse_flow_model.addItems(options)
        combo_model = self.cfg_reverse_flow_model.model()
        idx = self.cfg_reverse_flow_model.findText("viterna_full_range")
        if idx >= 0 and combo_model is not None:
            item = combo_model.item(idx)
            if item is not None:
                item.setEnabled(enabled)
        # An option that is present but disabled cannot be the selection.
        # Falling back to the first model keeps the widget and the project
        # agreeing about what will actually run.
        if current == "viterna_full_range" and not enabled:
            current = options[0]
        if current in options:
            self.cfg_reverse_flow_model.setCurrentText(current)
        self.cfg_reverse_flow_model.blockSignals(False)

    def _update_reverse_flow_note(self, *_args):
        """The note explains why 'viterna_full_range' is greyed out in the
        list. Once the option is selectable the note has nothing to add
        over the list itself, so the row disappears."""
        if self._airfoil_extend_full_range():
            self.reverse_flow_note.clear()
            set_row_visible(self._reverse_flow_form, self.reverse_flow_note, False)
        else:
            set_row_visible(self._reverse_flow_form, self.reverse_flow_note, True)
            # bare verb: the sentence below reads "... after you {hint}"
            hint = ("choose stall_model='viterna' in block (a)" if self.source_combo.currentText() == "analytical"
                    else "enable 'Extrapolate with Viterna-Corrigan' in block (a)")
            self.reverse_flow_note.setText(
                f"'viterna_full_range' is listed but not selectable; it "
                f"becomes available after you {hint}.")

    def _update_profile_fields(self, source: str):
        """Progressive reveal of the outline's rows.

        `set_row_visible`, not `setVisible` on the field: the
        field is wrapped by the "?" help icon, and hiding only that
        left the label ("CST upper (coefs, comma):") orphaned on
        screen, pointing at nothing -- which was the defect reported as
        "CST fields that can't be edited"."""
        form = self._geometry_form
        set_row_visible(form, self.naca_code_edit, source in ("naca4", "naca5"))
        set_row_visible(form, self.cst_upper_edit, source == "cst")
        set_row_visible(form, self.cst_lower_edit, source == "cst")
        set_row_visible(form, self.bezier_points_edit, source == "bezier")

    # --- Embedded preview canvas (docs/plano_v3.md Part 5) ---------------
    # "Polar" tab (Cl/Cd x alpha, navigated slice + overlay from block d/e)
    # and "Profile" (2D geometry from block f), always visible, with a
    # ~300ms debounce on any edit to the form on the left. The "Compare"
    # tab from Part 5 reuses the controls already present in blocks (c)
    # comparison Mach and (d) marked conditions -- no duplicated widget.

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._build_plot_toolbar())

        self.preview_tabs = QTabWidget()
        self.cl_alpha_canvas = CanvasHost(with_toolbar=True)
        self.cd_alpha_canvas = CanvasHost(with_toolbar=True)
        self.cd_cl_canvas = CanvasHost(with_toolbar=True)
        self.profile_canvas = CanvasHost(with_toolbar=True)
        self.preview_tabs.addTab(self.cl_alpha_canvas, "C_L × α")
        self.preview_tabs.addTab(self.cd_alpha_canvas, "C_D × α")
        self.preview_tabs.addTab(self.cd_cl_canvas, "C_D × C_L")
        self.preview_tabs.addTab(self.profile_canvas, "Profile")
        self.preview_tabs.currentChanged.connect(lambda _i: self._refresh_preview())
        layout.addWidget(self.preview_tabs, stretch=1)

        self.nav_box = QGroupBox("Navigate (r/R, Reynolds, Mach)")
        self.nav_form = QFormLayout(self.nav_box)
        self.nav_box.setVisible(False)
        layout.addWidget(self.nav_box)
        self._nav_widgets: dict = {}
        self._nav_axes_cache: tuple = ()

        return panel

    def _fmt_axis_value(self, axis: str, v: float) -> str:
        if axis == "r_norm":
            return f"{v:.3f}"
        if axis == "reynolds":
            return f"{v:.3g}"
        return f"{v:.2f}"

    def _rebuild_nav_controls(self, axes: dict):
        """Rebuilds the navigation controls only when the SET of
        axes/values actually changes (e.g., new table imported) -- never on
        each refresh, to avoid losing the user's slider/combo selection
        in the middle of a live edit."""
        key = tuple(tuple(axes[a]) for a in ("r_norm", "reynolds", "mach"))
        if key == self._nav_axes_cache:
            return
        self._nav_axes_cache = key

        while self.nav_form.rowCount():
            self.nav_form.removeRow(0)
        self._nav_widgets = {}

        labels = {"r_norm": "r/R:", "reynolds": "Reynolds:", "mach": "Mach:"}
        any_axis = False
        for axis in ("r_norm", "reynolds", "mach"):
            values = axes[axis]
            if len(values) < 2:
                continue
            any_axis = True
            self._nav_selection[axis] = values[0]
            if len(values) >= 5:
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, len(values) - 1)
                slider.setValue(0)
                value_label = QLabel(self._fmt_axis_value(axis, values[0]))

                def _on_change(idx, axis=axis, values=values, value_label=value_label):
                    value_label.setText(self._fmt_axis_value(axis, values[idx]))
                    self._nav_selection[axis] = values[idx]
                    self._schedule_preview_refresh()

                slider.valueChanged.connect(_on_change)
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.addWidget(slider, stretch=1)
                row_layout.addWidget(value_label)
                self.nav_form.addRow(labels[axis], row)
                self._nav_widgets[axis] = slider
            else:
                combo = QComboBox()
                for v in values:
                    combo.addItem(self._fmt_axis_value(axis, v), v)

                def _on_change(idx, axis=axis, combo=combo):
                    self._nav_selection[axis] = combo.itemData(idx)
                    self._schedule_preview_refresh()

                combo.currentIndexChanged.connect(_on_change)
                self.nav_form.addRow(labels[axis], combo)
                self._nav_widgets[axis] = combo
        self.nav_box.setVisible(any_axis)

    def _schedule_preview_refresh(self, *_args):
        if hasattr(self, "_preview_timer"):
            self._preview_timer.start()

    def _mark_dirty(self, *_args):
        if getattr(self, "_loading", False):
            return
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)

    def _clear_dirty(self):
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)

    def _refresh_preview(self):
        if not hasattr(self, "preview_tabs"):
            return
        try:
            airfoil_def = self._collect_airfoil_def()
        except Exception as exc:
            self.cl_alpha_canvas.show_message(f"Error reading airfoil: {exc}")
            return

        self._rebuild_nav_controls(airfoils.axis_values(airfoil_def))

        idx = self.preview_tabs.currentIndex()
        if idx == 3:
            self._refresh_profile_canvas()
            return

        host = (self.cl_alpha_canvas, self.cd_alpha_canvas, self.cd_cl_canvas)[idx]
        canvas = host.use_simple()
        canvas.clear()

        if airfoil_def.source == "table" and not airfoil_def.table_slices:
            canvas.ax.set_axis_off()
            canvas.ax.text(0.5, 0.5,
                            "Import a polar table first (Data import / tabulated polar).",
                            ha="center", va="center", transform=canvas.ax.transAxes)
            canvas.draw()
            return

        try:
            curves = self._collect_polar_curves(airfoil_def)
            draw_fn = (self._draw_cl_alpha, self._draw_cd_alpha, self._draw_cd_cl)[idx]
            draw_fn(canvas.ax, curves)
            range_label = ("full range (−180° to 180°)"
                     if uses_full_range_extension(airfoil_def)
                     else "measured range only")
            canvas.ax.set_title(f"{canvas.ax.get_title()} · {airfoil_def.stall_model} · "
                                 f"{range_label}{self.current_section_label()}", fontsize=9)
        except Exception as exc:
            canvas.clear()
            canvas.ax.set_axis_off()
            canvas.ax.text(0.5, 0.5, f"Error drawing polar: {exc}", ha="center", va="center",
                            wrap=True, transform=canvas.ax.transAxes)
        canvas.draw()

    def _use_compressibility(self) -> bool:
        """Compressibility checkbox state, not the saved project state.

        It used to read `project.config`, which only changes on "Apply to
        project" click: unchecking the box did not change the preview, and
        curves continued to separate by Mach. The user saw the correction
        active after disabling it and reasonably concluded the plot was
        lying -- the physics was correct, the preview just read the wrong
        source. All the rest of this preview reacts to the widget; this is
        the state the user is editing."""
        if hasattr(self, "cfg_use_compressibility"):
            return bool(self.cfg_use_compressibility.isChecked())
        if self.state.project is None:
            return False
        return bool(self.state.project.config.get("use_compressibility", True))

    def _config_para_preview(self) -> dict | None:
        """Config to use in polar preview. Prefers widgets FROM THIS TAB
        (the user may have just switched the reverse flow model and the
        plot must respond immediately), falling back to `project.config` and
        None if there is no project (no post-processing)."""
        if self.state.project is None:
            return None
        cfg = dict(self.state.project.config)
        if hasattr(self, "cfg_reverse_flow_model"):
            cfg["reverse_flow_model"] = self.cfg_reverse_flow_model.currentText()
            cfg["reverse_flow_blend_factor"] = self.cfg_reverse_flow_blend_factor.value()
            cfg["thin_plate_blend_center_deg"] = self.cfg_thin_plate_center.value()
            cfg["thin_plate_blend_width_deg"] = self.cfg_thin_plate_width.value()
        return cfg

    def _collect_polar_curves(self, airfoil_def: AirfoilDef) -> list:
        """Main curve (navigator selection r/R-Reynolds-Mach, or the
        analytical polar) + overlay curves ("Compare", blocks d/e) --
        shared by the 3 mini-tabs of plot (Cl x alpha / Cd x alpha /
        Cd x Cl), to avoid repeating the logic of slicing table x analytical
        preview 3 times.

        When ``use_compressibility`` is enabled in the project, applies the
        Prandtl-Glauert correction in previews (same as what BEMT does
        in element_state), so the plots reflect the actual corrections."""
        use_comp = self._use_compressibility()
        range_label = self._alpha_range()
        # `project.config` enables reverse flow post-processing inside
        # `preview_polar` (which calls `bemt.apply_reverse_flow_to_polar`,
        # the same function as the engine) -- without it, the drawn curve
        # ignored `reverse_flow_model` completely.
        cfg_dict = self._config_para_preview()
        curves = []
        if airfoil_def.source == "table":
            sel = self._nav_selection
            sel_mach = sel.get("mach")
            sel_re = sel.get("reynolds")

            if uses_full_range_extension(airfoil_def):
                # Use preview_polar to evaluate the extended polar (includes Viterna and comp if active)
                alpha_arr, cl_arr, cd_arr = airfoils.preview_polar(
                    airfoil_def, range_label, reynolds=sel_re, mach=sel_mach,
                    use_compressibility=use_comp, config=cfg_dict,
                )
                # Item 32: identify the curve by the actual (Re, Mach)
                # selected, not just by the airfoil name -- which is the
                # same across all slices generated by NeuralFoil.
                label = airfoils.condition_label(
                    {"reynolds": sel_re, "mach": sel_mach, "label": airfoil_def.name})
                if use_comp and sel_mach and sel_mach > 0.0:
                    label += " (P-G/Viterna)"
                else:
                    label += " (Viterna)"
                curves.append(dict(alpha_deg=alpha_arr, cl=list(cl_arr), cd=list(cd_arr), label=label))
            else:
                # Show the slice from the original table
                slc = airfoils.slice_table_at(airfoil_def, r_norm=sel.get("r_norm"),
                                               reynolds=sel_re, mach=sel_mach)
                cl_arr = list(slc.cl)
                cd_arr = list(slc.cd)
                # Item 32: `slc.label` alone is generic in NeuralFoil tables
                # (an entire Re×Mach sweep shares the same text, derived only
                # from geometry) -- the actual (Re, Mach) of the slice comes first.
                label = airfoils.condition_label(
                    {"r_norm": slc.r_norm, "reynolds": slc.reynolds,
                     "mach": slc.mach, "label": slc.label})
                if use_comp and sel_mach and sel_mach > 0.0:
                    beta = float(np.sqrt(max(0.0, 1.0 - sel_mach ** 2)))
                    if beta > 1e-3:
                        cl_arr = [v / beta for v in cl_arr]
                        cd_arr = [v / beta for v in cd_arr]
                        label += " (P-G)"
                curves.append(dict(alpha_deg=slc.alpha_deg, cl=cl_arr, cd=cd_arr, label=label))
        else:
            alpha, cl, cd = airfoils.preview_polar(
                airfoil_def, range_label, use_compressibility=False, config=cfg_dict)
            curves.append(dict(alpha_deg=alpha, cl=cl, cd=cd, label=airfoil_def.name))

        if cfg_dict is not None and self.show_reverse_branch_check.isChecked():
            sel = self._nav_selection
            alpha_r, cl_r, cd_r = airfoils.preview_polar(
                airfoil_def, range_label, reynolds=sel.get("reynolds"), mach=sel.get("mach"),
                use_compressibility=use_comp, config=cfg_dict, reverse=True)
            model_name = cfg_dict.get("reverse_flow_model", "")
            curves.append(dict(alpha_deg=alpha_r, cl=cl_r, cd=cd_r,
                                label=f"reverse flow ({model_name})"))

        opts = self.preview_options()
        if opts["conditions"] or opts["mach_compare"]:
            extra = airfoils.preview_polar_multi(
                airfoil_def, conditions=opts["conditions"] or None,
                mach_compare=opts["mach_compare"] or None,
                alpha_deg_range=range_label,
                use_compressibility=use_comp,
            )
            for curve in extra:
                curves.append(dict(alpha_deg=curve["alpha_deg"], cl=curve["cl"], cd=curve["cd"],
                                    label=curve["label"]))
        return _unir_curvas_coincidentes(curves)

    def _legend_ncols(self, curves: list) -> int:
        return 1 if len(curves) <= 6 else 2

    #: Fixed Cl/Cd range when "Auto-fit Y axis" is unchecked -- wide
    #: enough to contain an extended ±180 polar without cutting, and equal
    #: across refreshes, which is the point: with autoscale, changing an
    #: airfoil rescales the axis and the two curves look identical.
    _FIXED_CL_RANGE = (-2.0, 2.5)
    _FIXED_CD_RANGE = (0.0, 2.2)

    def _apply_y_scale(self, ax, fixed_range):
        if not self.autoscale_y_check.isChecked():
            ax.set_ylim(*fixed_range)

    def _draw_cl_alpha(self, ax, curves: list):
        for curve in curves:
            plots.plot_cl_alpha(curve["alpha_deg"], curve["cl"], ax=ax, label=curve["label"])
        self._apply_y_scale(ax, self._FIXED_CL_RANGE)
        ax.legend(fontsize=7, ncols=self._legend_ncols(curves))

    def _draw_cd_alpha(self, ax, curves: list):
        for curve in curves:
            plots.plot_cd_alpha(curve["alpha_deg"], curve["cd"], ax=ax, label=curve["label"])
        self._apply_y_scale(ax, self._FIXED_CD_RANGE)
        ax.legend(fontsize=7, ncols=self._legend_ncols(curves))

    def _draw_cd_cl(self, ax, curves: list):
        for curve in curves:
            plots.plot_cd_cl(curve["cl"], curve["cd"], ax=ax, label=curve["label"])
        ax.legend(fontsize=7, ncols=self._legend_ncols(curves))

    def _refresh_profile_canvas(self):
        canvas = self.profile_canvas.use_simple()
        canvas.clear()
        if self._profile is not None:
            plots.plot_profile(self._profile, ax=canvas.ax)
        else:
            canvas.ax.set_axis_off()
            canvas.ax.text(0.5, 0.5,
                            "No profile geometry generated yet (Profile 2D geometry).",
                            ha="center", va="center", transform=canvas.ax.transAxes)
        canvas.draw()

    # --- actions ----------------------------------------------------------

    def _collect_airfoil_def(self, r_norm: float | None = None) -> AirfoilDef:
        gui_mode = self.source_combo.currentText()  # "analytical" | "table" | "neuralfoil" | "xfoil"
        # 'neuralfoil' and 'xfoil' are GUI MODES (item 6), not separate
        # `AirfoilDef.source` values -- in the data model/`bemt.py` they ARE
        # tables (generated on-the-fly from geometry, one section at a
        # time), so both map to source='table' here; `external_engine`
        # carries WHICH generator produced it (see
        # `_update_source_visibility` for the mirror: engine_combo is set
        # automatically by these modes).
        source = "table" if gui_mode in ("neuralfoil", "xfoil") else gui_mode
        stall_model = self.stall_model_combo.currentText()
        # extend_full_range is only an independent toggle for the user in
        # the table-like modes ('table', 'neuralfoil', 'xfoil') -- for
        # 'analytical' it is DERIVED from stall_model=='viterna' (see
        # models.uses_full_range_extension), synchronized here so the value
        # saved in the project stays consistent.
        extend_full_range = (self.extend_full_range.isChecked() if gui_mode != "analytical"
                              else stall_model == "viterna")
        return AirfoilDef(
            name=self.airfoil_name_edit.text().strip() or "airfoil",
            r_norm=r_norm,
            source=source,
            cl_alpha=self.cl_alpha.value(),
            alpha0_deg=self.alpha0_deg.value(),
            cd0=self.cd0.value(),
            k=self.k_coef.value(),
            alpha_stall_pos_deg=self.alpha_stall_pos.value(),
            alpha_stall_neg_deg=self.alpha_stall_neg.value(),
            stall_model=stall_model,
            extend_full_range=extend_full_range,
            viterna_blend_width_deg=self.viterna_blend_width_deg.value(),
            use_dynamic_stall=self.use_dynamic_stall.isChecked(),
            dynamic_stall_method=self.dyn_method.currentText(),
            dynamic_stall_A=self.dyn_A.value(),
            dynamic_stall_fade_start_deg=self.dyn_fade_start.value(),
            dynamic_stall_fade_end_deg=self.dyn_fade_end.value(),
            dynamic_stall_time_march_revolutions=self.dyn_revs.value(),
            dynamic_stall_time_march_avg_last=self.dyn_avg_last.value(),
            table_slices=self._imported_slices,
            geometry=self._profile,
            external_engine=self.engine_combo.currentText(),
            external_reynolds_list=parse_list(self.re_list_edit.text()),
            external_mach_list=parse_list(self.mach_list_edit.text()),
            external_alpha_min_deg=self.ext_alpha_min.value(),
            external_alpha_max_deg=self.ext_alpha_max.value(),
            external_alpha_step_deg=self.ext_alpha_step.value(),
            xfoil_ncrit=self.ext_ncrit.value(),
            xfoil_xtr_top=self.ext_xtr_top.value(),
            xfoil_xtr_bot=self.ext_xtr_bot.value(),
        )

    def preview_options(self) -> dict:
        """Used by the embedded preview canvas (docs/plano_v3.md Part 5)."""
        txt = self.mach_compare_edit.text().strip()
        mach_compare = parse_list(txt) if txt else []
        return dict(mach_compare=mach_compare, conditions=self._checked_conditions())

    def _apply_to_project(self, *_args):
        if self.state.project is None or getattr(self, "_loading", False):
            return
        self._mark_dirty()
        try:
            self._save_current_form_into_scratch()
            if len(self._sections) >= 2:
                self.state.project.airfoil_sections = [replace(s) for s in self._sections]
                names = ", ".join(s.name for s in self._sections)
                self.state.project.geometry.airfoil_name = f"{len(self._sections)} sections ({names})"
            else:
                airfoil_def = self._collect_airfoil_def()
                self.state.project.airfoil = airfoil_def
                self.state.project.airfoil_sections = []
                self.state.project.geometry.airfoil_name = airfoil_def.name
            self.state.project.config["reverse_flow_model"] = self.cfg_reverse_flow_model.currentText()
            self.state.project.config["reverse_flow_blend_factor"] = self.cfg_reverse_flow_blend_factor.value()
            self.state.project.config["thin_plate_blend_center_deg"] = self.cfg_thin_plate_center.value()
            self.state.project.config["thin_plate_blend_width_deg"] = self.cfg_thin_plate_width.value()
            self.state.project.config["use_compressibility"] = self.cfg_use_compressibility.isChecked()
            self._applying_locally = True
            try:
                self.state.notify_airfoil()
                self.state.notify_config()
            finally:
                self._applying_locally = False
            self._refresh_validation()
        except Exception as exc:
            show_error(self, "Error applying airfoil", exc)

    def _checked_conditions(self) -> list[dict]:
        conds = []
        for i in range(self.slices_list.count()):
            item = self.slices_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                conds.append(item.data(Qt.ItemDataRole.UserRole))
        return conds

    def _revalidar(self):
        """Runs the static check and paints the result -- WITHOUT
        rescheduling the preview.

        Separate from `_refresh_validation` because the debounce timer calls
        this: if the timer slot were to call `_schedule_preview_refresh`
        again (as `_refresh_validation` does), each firing would rearm the
        timer itself and the tab would enter an infinite redraw loop.
        """
        try:
            self._save_current_form_into_scratch()
            if len(self._sections) >= 2:
                issues = validation.validate_airfoil_sections(self._sections)
            else:
                airfoil_def = self._collect_airfoil_def()
                issues = validation.validate_airfoil_def(airfoil_def)
            self._render_issues(issues)
        except Exception as exc:
            show_error(self, "Error during check", exc)

    def _refresh_validation(self):
        self._revalidar()
        self._schedule_preview_refresh()

    def _ao_expirar_debounce(self):
        """Timer's single slot: redraws the canvas AND revalidates.

        The check used to be triggered only by the "Check airfoil" button.
        Since any field edit already schedules a preview redraw, the check
        now accompanies it in the same debounce -- and the button, which no
        longer did anything the edit itself didn't do, ceased to exist.
        """
        self._refresh_preview()
        self._revalidar()

    def _render_issues(self, issues: list[validation.Issue]):
        if not issues:
            self.validation_label.setText('<font color="#2e7d32">No warnings.</font>')
            return
        colors = {"error": "#c62828", "warning": "#f0ad4e", "info": "#555555"}
        lines = [f'<font color="{colors.get(i.level, "#000000")}">{i}</font>' for i in issues]
        self.validation_label.setText("<br>".join(lines))

    def _populate_slices_list(self):
        self.slices_list.blockSignals(True)
        self.slices_list.clear()
        conditions = airfoils.unique_conditions(
            AirfoilDef(source="table", table_slices=self._imported_slices)
        )
        for idx, cond in enumerate(conditions):
            tag = []
            if cond["r_norm"] is not None: tag.append(f"r/R={cond['r_norm']:.2f}")
            if cond["reynolds"] is not None: tag.append(f"Re={cond['reynolds']:.0f}")
            if cond["mach"] is not None: tag.append(f"M={cond['mach']:.2f}")
            item = QListWidgetItem(", ".join(tag) or cond.get("label") or "single polar")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = len(conditions) <= 6 or idx < 6
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, cond)
            self.slices_list.addItem(item)
        self.slices_list.blockSignals(False)
        self._update_prandtl_glauert_availability()
        self._schedule_preview_refresh()

    #: Base tooltip of the compressibility toggle (the text when it IS
    #: available). Constant so the lock path can add the reason without
    #: erasing the explanation -- and so `field_help` can keep finding the
    #: field name in the first quoted token in both states.
    _COMPRESSIBILITY_TOOLTIP = (
        '"use_compressibility" — corrects Cl and Cd by factor 1/√(1−M²); '
        'do not use with tables that already vary with Mach (double counting)')

    def _update_prandtl_glauert_availability(self, *_args):
        """Disables the Prandtl-Glauert toggle when the polar IN USE already
        carries Mach as data: table (or table generated by NeuralFoil/XFOIL)
        with 2+ slices of `PolarSlice.mach`. In that case the polar chosen in
        each condition already comes compressible, and applying the empirical
        correction on top would count Mach twice. Same rule as
        `validation.validate_config` (which keeps warning if a `.bemt`
        loaded comes with the toggle on).

        "IN USE" is the part that was missing: the condition looked only at
        imported slices, which stay stored when switching source (to not lose
        them going back and forth). Reported result: it was enough to pass
        through 'table' with a table swept in Mach for the toggle to stay
        gray FOREVER -- in 'analytical', where no table is consulted, it
        stayed locked for no reason.

        The previous value is returned when re-enabled: locking unchecks the
        box, and without this the user's choice would be lost on a source
        round-trip."""
        if not hasattr(self, "cfg_use_compressibility"):
            # called by `_update_source_visibility`, which runs during
            # construction -- the box is created in a block assembled later
            return
        machs = {s.mach for s in (self._imported_slices or []) if s.mach is not None}
        uses_table = self.source_combo.currentText() in ("table", "neuralfoil", "xfoil")
        blocked = uses_table and len(machs) > 1
        if blocked:
            if self.cfg_use_compressibility.isEnabled():
                self._compressibilidade_antes_do_bloqueio = (
                    self.cfg_use_compressibility.isChecked())
            self.cfg_use_compressibility.setChecked(False)
            self.cfg_use_compressibility.setEnabled(False)
            self.cfg_use_compressibility.setToolTip(
                self._COMPRESSIBILITY_TOOLTIP
                + f'\n\nUnavailable here: the table in use already varies with '
                  f'Mach ({len(machs)} distinct Mach slices), so the polar is '
                  f'compressible by data and the correction would count Mach twice.')
            return
        if not self.cfg_use_compressibility.isEnabled():
            self.cfg_use_compressibility.setEnabled(True)
            previous = getattr(self, "_compressibilidade_antes_do_bloqueio", None)
            if previous is not None:
                self.cfg_use_compressibility.setChecked(previous)
                self._compressibilidade_antes_do_bloqueio = None
        self.cfg_use_compressibility.setToolTip(self._COMPRESSIBILITY_TOOLTIP)

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import polar CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            axes = airfoils.detect_csv_axes(path)
            self._imported_slices = airfoils.import_polar_csv(path)
            self.source_combo.setCurrentText("table")
            detected = ", ".join(k for k, v in axes.items() if v and k not in ("alpha_deg", "cl", "cd"))
            self.detected_axes_label.setText(
                f"Imported: {Path(path).name} — {len(self._imported_slices)} polar(s). "
                f"Extra axes detected: {detected or 'none (single polar)'}"
            )
            self._populate_slices_list()
            self._apply_to_project()   # see note in `_on_external_finished`
        except Exception as exc:
            show_error(self, "Error importing CSV", exc)

    def _export_csv(self):
        if not self._imported_slices:
            QMessageBox.warning(self, "Nothing to export", "No tabulated polar loaded.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export polar CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            airfoil_def = self._collect_airfoil_def()
            airfoils.export_polar_csv(airfoil_def, path)
            QMessageBox.information(self, "Exported", f"Polar exported to {path}")
        except Exception as exc:
            show_error(self, "Error exporting CSV", exc)

    def _sync_profile_source(self, profile) -> None:
        """Sets the "Source:" combo to the source of the LOADED outline.

        Without this the combo was not synchronized with the project --
        opening a project imported from .dat showed "naca4" over an
        outline that was not NACA at all."""
        source_name = (getattr(profile, "source", "") or "").strip()
        combo = self.profile_source_combo
        options = list(self._PROFILE_SOURCES)
        target = source_name if source_name in options else combo.currentText()
        combo.blockSignals(True)
        if target in options:
            combo.setCurrentText(target)
        combo.blockSignals(False)
        self._update_profile_fields(combo.currentText())

    def _generate_profile(self):
        # The Geometry spec string, when non-empty, takes precedence over
        # the Source/NACA fields (see the field's tooltip). It resolves
        # through the same entry point as the CLI's --airfoil-geometry.
        spec = self.geometry_spec_edit.text().strip()
        if spec:
            try:
                self._profile = airfoils.resolve_geometry_spec(spec)
            except Exception as exc:
                show_error(self, "Error generating profile geometry", exc)
                return
            self._apply_to_project()
            self._schedule_preview_refresh()
            return

        source = self.profile_source_combo.currentText()
        try:
            if source == "naca4":
                self._profile = airfoils.generate_naca4(self.naca_code_edit.text())
            elif source == "naca5":
                self._profile = airfoils.generate_naca5(self.naca_code_edit.text())
            elif source == "cst":
                upper = [float(v) for v in self.cst_upper_edit.text().split(",") if v.strip()]
                lower = [float(v) for v in self.cst_lower_edit.text().split(",") if v.strip()]
                self._profile = airfoils.generate_cst(upper, lower)
            elif source == "bezier":
                pts = []
                for line in self.bezier_points_edit.toPlainText().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    x_str, y_str = line.split(",")
                    pts.append([float(x_str), float(y_str)])
                self._profile = airfoils.generate_bezier(pts)
            else:
                QMessageBox.information(self, "Import", "Use the 'Import .dat…' button for this source.")
                return
        except Exception as exc:
            show_error(self, "Error generating profile geometry", exc)
            return
        # The 2D geometry is a project field (`AirfoilDef.geometry`), not
        # preview-only state: without applying it here it stayed trapped in
        # `self._profile` and validation blocked execution with "no 2D
        # profile geometry was generated/imported".
        self._apply_to_project()
        self._schedule_preview_refresh()

    def _import_dat(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import profile .dat", "", "Profile (*.dat *.txt *.csv)")
        if not path:
            return
        try:
            self._profile = airfoils.load_profile_dat(path)
            self.profile_source_combo.setCurrentText("imported")
        except Exception as exc:
            show_error(self, "Error importing profile", exc)
        self._apply_to_project()   # see note in `_generate_profile`
        self._schedule_preview_refresh()

    def _run_external(self):
        """C4 (production-plan.md): the external engine runs in
        ``ExternalPolarWorker`` on a ``QThread`` (same pattern as
        ``BatchRunnerWorker``/``launch_worker`` used by RunCaseTab/
        RunBatchTab), no longer synchronous on the GUI thread -- before it
        froze the window ("Not responding") for minutes on a modest
        Reynolds×Mach×alpha sweep."""
        engine = self.engine_combo.currentText()
        # Availability is checked HERE, per engine, at the moment of the
        # click: neuralfoil needs the Python package, xfoil needs the
        # binary (ZBEMT_XFOIL_BIN or PATH). The dialog says what to
        # install; the button never goes dead.
        if engine == "neuralfoil":
            if not require_optional_package(self, "neuralfoil"):
                return
        elif engine == "xfoil":
            if not require_optional_binary(
                    self, feature="XFOIL", env_var="ZBEMT_XFOIL_BIN",
                    download_hint="Install XFOIL and set ZBEMT_XFOIL_BIN or add it to PATH."):
                return
        if self._profile is None:
            QMessageBox.warning(self, "No geometry", "Generate or import the profile geometry (block 'f') first.")
            return
        if self._ext_worker is not None:
            return  # already running
        try:
            reynolds_list = [float(v) for v in self.re_list_edit.text().split(",") if v.strip()]
            mach_list = [float(v) for v in self.mach_list_edit.text().split(",") if v.strip()]
        except Exception as exc:
            show_error(self, "Error running polar generation", exc)
            return

        self._ext_reynolds_list = reynolds_list
        self._ext_mach_list = mach_list
        self.btn_run_external.setEnabled(False)
        self.btn_cancel_external.setVisible(True)
        self.btn_cancel_external.setEnabled(True)
        self.progress_external.setVisible(True)
        self.status_label_external.setText(
            f"Running {engine} ({len(reynolds_list)} Reynolds x {len(mach_list)} Mach)…")

        if engine == "xfoil":
            worker = _XfoilPolarWorker(
                self._profile,
                reynolds_list=reynolds_list, mach_list=mach_list,
                alpha_min_deg=self.ext_alpha_min.value(),
                alpha_max_deg=self.ext_alpha_max.value(),
                alpha_step_deg=self.ext_alpha_step.value(),
                ncrit=self.ext_ncrit.value(), xtr_top=self.ext_xtr_top.value(),
                xtr_bot=self.ext_xtr_bot.value())
        else:
            worker = ExternalPolarWorker(
                self._profile, engine=engine,
                reynolds_list=reynolds_list, mach_list=mach_list,
                alpha_min_deg=self.ext_alpha_min.value(),
                alpha_max_deg=self.ext_alpha_max.value(),
                alpha_step_deg=self.ext_alpha_step.value(),
            )
        self._ext_worker = worker
        worker.finished.connect(self._on_external_finished)
        worker.failed.connect(self._on_external_failed)
        self._ext_thread = launch_worker(worker)

    def _cancel_external(self):
        if self._ext_worker is not None:
            self._ext_worker.cancel()
            self.btn_cancel_external.setEnabled(False)
            self.status_label_external.setText(
                "Canceling… (the engine cannot interrupt a point mid-calculation; "
                "result will be discarded when it finishes)")

    def _reset_external_run_ui(self):
        self.progress_external.setVisible(False)
        self.btn_cancel_external.setVisible(False)
        self.btn_cancel_external.setEnabled(True)
        # Clickable again, whatever the availability: a click explains
        # what is missing instead of leaving a dead button.
        self.btn_run_external.setEnabled(True)
        self._ext_thread = None
        self._ext_worker = None

    def _on_external_failed(self, message: str):
        cancelled = self._ext_worker.cancel_requested if self._ext_worker is not None else False
        self._reset_external_run_ui()
        self.status_label_external.setText("")
        if cancelled:
            return
        show_error(self, "Error running polar generation", RuntimeError(message))

    def _on_external_finished(self, slices: list):
        cancelled = self._ext_worker.cancel_requested if self._ext_worker is not None else False
        reynolds_list = getattr(self, "_ext_reynolds_list", [])
        mach_list = getattr(self, "_ext_mach_list", [])
        engine = self.engine_combo.currentText() or "external engine"
        self._reset_external_run_ui()
        self.status_label_external.setText("")
        if cancelled:
            self.status_label_external.setText("Canceled -- result discarded.")
            return

        if not slices:
            QMessageBox.warning(self, "No points converged",
                                 f"{engine} did not return any alpha points with sufficient confidence "
                                 "for this geometry/range.")
            return

        self._generated_external_slices = slices
        self.btn_export_external.setEnabled(True)
        self._imported_slices = list(slices)
        # The result becomes the active table immediately. This keeps the
        # generated-table mode (NeuralFoil or XFOIL) and the generated
        # slices together in the Project, allowing the case to run without
        # manually going back to Table mode.
        self._populate_slices_list()
        # Stay in the generated mode that started the run: forcing
        # 'neuralfoil' here would silently switch an XFOIL run's source.
        if self.source_combo.currentText() not in ("neuralfoil", "xfoil"):
            self.source_combo.setCurrentText("neuralfoil")
        # `setCurrentText` only writes to the project AS A SIDE EFFECT TABLE:
        # who calls `_apply_to_project` is the signal `currentTextChanged`.
        # In the real flow the combo IS ALREADY in the generated mode
        # (otherwise this generation block wouldn't even be visible), the
        # signal doesn't fire, and the newly generated polars never reached
        # `state.project.airfoil` -- the project continued with empty
        # table_slices and execution was blocked by "no polar was imported",
        # pointing the user back to 'table' mode. Applying explicitly does
        # not depend on the value having changed.
        self._apply_to_project()
        self._schedule_preview_refresh()
        QMessageBox.information(
            self, f"{engine} completed",
            f"{len(slices)} polar(s) generated ({len(reynolds_list)} Reynolds x {len(mach_list)} Mach). "
            # There is no 'Apply' button anymore: the line above already wrote
            # the slices to the project in memory. What's left for the user to
            # decide is whether to save to disk or not -- and that was what the
            # old message told them to do in a button the GUI doesn't have.
            f"Written to the project — use 'Save' to keep it, or "
            f"'Export generated table…' to save a CSV first.")

    def _export_external_table(self):
        slices = getattr(self, "_generated_external_slices", None)
        if not slices:
            QMessageBox.warning(self, "Nothing to export", "Run polar generation first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export generated table", "", "CSV (*.csv)")
        if not path:
            return
        try:
            out = api.export_polar_table(slices, path)
            QMessageBox.information(self, "Exported", f"Generated table exported to {out}")
        except Exception as exc:
            show_error(self, "Error exporting table", exc)

    def current_profile(self) -> ProfileGeometry | None:
        return self._profile

    def current_section_label(self) -> str:
        """Used by the embedded canvas to make clear, in the preview title,
        whether what is being shown is the single airfoil or a specific
        section (Phase D, docs/plano.md Section 4)."""
        if 0 <= self._current_section_index < len(self._sections):
            s = self._sections[self._current_section_index]
            return f" -- section {s.name!r} (r/R={s.r_norm:.3f})"
        return ""

    def _load_form_from_airfoil_def(self, a: AirfoilDef):
        self.airfoil_name_edit.setText(a.name)
        # Unknown/legacy engine values fall back to "none"; the original
        # value stays in the .bemt until the user re-applies via GUI/CLI.
        # "xfoil" is a first-class option again (the GUI offers it and
        # checks for the binary at run time).
        engine = a.external_engine if a.external_engine in ("none", "neuralfoil", "xfoil") else "none"
        # Item 6: both generated modes are reconstructed here from
        # source='table' + external_engine ('neuralfoil'/'xfoil') -- see
        # `_collect_airfoil_def` for the inverse mapping.
        if a.source == "table" and engine == "neuralfoil":
            gui_mode = "neuralfoil"
        elif a.source == "table" and engine == "xfoil":
            gui_mode = "xfoil"
        else:
            gui_mode = a.source
        self.source_combo.setCurrentText(gui_mode)
        self.cl_alpha.setValue(a.cl_alpha)
        self.alpha0_deg.setValue(a.alpha0_deg)
        self.cd0.setValue(a.cd0)
        self.k_coef.setValue(a.k)
        self.alpha_stall_pos.setValue(a.alpha_stall_pos_deg)
        self.alpha_stall_neg.setValue(a.alpha_stall_neg_deg)
        self.stall_model_combo.setCurrentText(a.stall_model)
        self.extend_full_range.setChecked(a.extend_full_range)
        self.viterna_blend_width_deg.setValue(a.viterna_blend_width_deg)
        self._update_source_visibility()
        self.use_dynamic_stall.setChecked(a.use_dynamic_stall)
        if a.dynamic_stall_method in ("frequency",):
            self.dyn_method.setCurrentText(a.dynamic_stall_method)
        # 'time_march' from old projects: the GUI no longer offers the
        # option (docs/plano.md Section 5); the combo stays on 'frequency'
        # until the user re-applies.
        self.dyn_A.setValue(a.dynamic_stall_A)
        self.dyn_fade_start.setValue(a.dynamic_stall_fade_start_deg)
        self.dyn_fade_end.setValue(a.dynamic_stall_fade_end_deg)
        self.dyn_revs.setValue(a.dynamic_stall_time_march_revolutions)
        self.dyn_avg_last.setValue(a.dynamic_stall_time_march_avg_last)
        self._update_dynamic_stall_enabled()
        self.re_list_edit.setText(", ".join(str(v) for v in a.external_reynolds_list))
        self.mach_list_edit.setText(", ".join(str(v) for v in a.external_mach_list))
        # A list that came WITH the project counts as user choice: it was
        # saved on purpose, and rewriting it because the radius changed would
        # erase their data. Only the EMPTY list stays open to automatic
        # suggestion (see `_re_suggest_re_mach`, called at the end of
        # loading). The "Suggest from rotor" button ignores this mark.
        self._re_mach_user_edited = bool(
            a.external_reynolds_list or a.external_mach_list)
        self.ext_alpha_min.setValue(a.external_alpha_min_deg)
        self.ext_alpha_max.setValue(a.external_alpha_max_deg)
        self.ext_alpha_step.setValue(a.external_alpha_step_deg)
        self.ext_ncrit.setValue(a.xfoil_ncrit)
        self.ext_xtr_top.setValue(a.xfoil_xtr_top)
        self.ext_xtr_bot.setValue(a.xfoil_xtr_bot)
        self._imported_slices = list(a.table_slices)
        self._populate_slices_list()
        self._profile = a.geometry
        self._sync_profile_source(a.geometry)

    def _refresh_from_project(self):
        if self.state.project is None:
            return
        if self._applying_locally:
            return
        self._loading = True
        try:
            self._refresh_from_project_impl()
        finally:
            self._loading = False
        self._clear_dirty()
        # Project saved in a generated-table mode (NeuralFoil or XFOIL)
        # and WITHOUT Reynolds/Mach lists opened with both fields blank
        # and nothing filled them: automatic suggestion only fired on
        # TRANSITION to the mode, which on this path never happens (the
        # project already enters it). Here it runs after loading -- and
        # only when the fields are empty, because a list from the project
        # counts as user choice (see `_load_form_from_airfoil_def`).
        self._re_suggest_re_mach()
        # The preview does NOT redraw on its own here: `_loading` silences
        # precisely the field-change signals that would schedule it. Without
        # this line, opening a project would repopulate the form but leave the
        # PREVIOUS airfoil curve on screen -- seen with the form already
        # saying "viterna / full range" while the plot next to it still said
        # "linear / measured range only". The user read the polar from a
        # different airfoil with no sign it was different.
        self._refresh_preview()

    def _refresh_from_project_impl(self):
        # LOCAL copy (scratch) of project.airfoil_sections -- edited
        # freely in this tab; only returns to project.airfoil_sections on
        # "Apply to project" (Phase D, docs/plano.md Section 4).
        self._sections = [replace(s) for s in self.state.project.airfoil_sections]
        if len(self._sections) >= 2:
            # preserves the selected section when still valid (e.g., this
            # refresh was triggered by "Apply to project" from this tab) --
            # only goes back to the first section on new loads (old index
            # invalid, e.g., -1 when opening a project).
            idx = self._current_section_index if 0 <= self._current_section_index < len(self._sections) else 0
            self._current_section_index = idx
            self._update_sections_ui()
            self._refresh_sections_list_widget()
            self._load_form_from_section(idx)
        else:
            self._sections = []
            self._current_section_index = -1
            self._update_sections_ui()
            self._refresh_sections_list_widget()
            self._load_form_from_airfoil_def(self.state.project.airfoil)

        cfg = dict(self.state.project.config)
        d = asdict(BEMTConfig())
        def g(key):
            return cfg.get(key, d[key])
        self._refresh_reverse_flow_options()
        self.cfg_reverse_flow_model.setCurrentText(str(g("reverse_flow_model")))
        self._update_reverse_flow_note()
        self.cfg_reverse_flow_blend_factor.setValue(float(g("reverse_flow_blend_factor")))
        self.cfg_thin_plate_center.setValue(float(g("thin_plate_blend_center_deg")))
        self.cfg_thin_plate_width.setValue(float(g("thin_plate_blend_width_deg")))
        self.cfg_use_compressibility.setChecked(bool(g("use_compressibility")))

        self._refresh_validation()
