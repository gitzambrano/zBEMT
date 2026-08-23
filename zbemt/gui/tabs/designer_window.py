"""Implement the Geometry Designer window.

The window gathers the geometry-comparison tool that left the Design
tab. It mirrors the vocabulary of Run Case and Run Batch in three pages:
the Variants page defines what to compare, the Conditions page decides
what each variant runs, and the Run & Results page executes the solves
and reads them (a verdict strip, one ranking figure, one
delta-against-base figure, one overlay figure). Inputs are the active
project, its geometry origin parameters, its saved cases, and the
values typed on the pages; outputs are in-memory results, canvases,
and exported report or CSV files in the project ``outputs`` folder.
Project I/O and solver execution cross the
``api.py`` boundary; the solve itself runs on a worker thread so the
window never freezes (PR-11). The Variants page leads with a variation
sweep builder -- one geometry parameter through several values, one
table row per value -- because comparing generated variants is the tool's
main use; beside it, a Generate block builds one blade from a planform
family and an Import button brings another project's blade in, either as
a row of its own or as this session's base. Manual override rows stay
available around both.

Block titles are plain text for now: block help popups for this window
are wired by a later documentation pass.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QStackedWidget,
    QTabWidget,
)

from matplotlib.lines import Line2D

from ... import api
from ... import geometry
from ... import nomenclature
from ...models import (FlightCondition, GEOMETRY_PARAMS, INTEGER_PARAMS,
                        default_project_paths)
from ...viz import plots

from ..common import (
    AppState,
    CanvasHost,
    equalize_button_widths,
    parse_list,
    require_project,
    set_row_label,
    set_row_visible,
    show_error,
)
from ..workers import CompareWorker, launch_worker


class _AbsoluteRowGeometry:
    """A COMPLETE geometry carried by one variant row.

    A variant row holds either overrides over the base planform (table
    cells plus a dict on the label item) or one of these payloads: a
    ``RotorGeometryDef`` built elsewhere -- generated from a family
    dropdown or imported from another project -- used exactly as given
    at collect time. The projection columns read this payload too:
    aspect ratio and solidity derive from it, and its root cutout and
    radius fill the empty cells of the row. ``marker`` is the short
    text the read-only "Extra overrides" column shows instead of an
    override summary."""

    __slots__ = ("geometry", "marker")

    def __init__(self, geometry_obj, marker: str):
        self.geometry = geometry_obj
        self.marker = marker


# Same alias as bemt.py: numpy 2 renames trapz to trapezoid.
_trapz = getattr(np, "trapezoid", None) or np.trapz


def _planform_integral(geom) -> float:
    """∫c d(r/R) of one geometry, over its own stations.

    The trapezoidal rule integrates the chord table against the r/R
    table as given. Returns ``0.0`` when the table holds fewer than
    two stations or the two arrays differ in length; callers render
    that case as an em dash."""
    r = np.asarray(getattr(geom, "r_norm", None) or [], dtype=float)
    c = np.asarray(getattr(geom, "chord_norm", None) or [], dtype=float)
    if r.size < 2 or c.size != r.size:
        return 0.0
    return float(_trapz(c, x=r))


class GeometryDesignerWindow(QWidget):
    """Dedicated window for comparing blade geometries."""

    #: Columns of the variant table. The first column holds the label
    #: that names the geometry in results, plots and reports; "base" is
    #: the project's own planform. Root cutout and Radius are DIRECT
    #: geometry parameters with editable cells of their own, exactly
    #: like Blades; the base row and the rows carrying a complete
    #: geometry display their geometry's values there. "Aspect ratio"
    #: and "Solidity" are read-only derivations of the row's resolved
    #: planform. The last column is a read-only projection of the
    #: remaining overrides.
    _VARIANT_COLUMNS = ["Label", "Root chord c/R", "Tip chord c/R",
                        "Twist root [deg]", "Twist tip [deg]", "Blades",
                        "Root cutout [r/R]", "Radius [m]", "Aspect ratio",
                        "Solidity", "Extra overrides"]
    _COL_LABEL, _COL_ROOT_CHORD, _COL_TIP_CHORD = 0, 1, 2
    _COL_TWIST_ROOT, _COL_TWIST_TIP, _COL_BLADES = 3, 4, 5
    _COL_ROOT_CUTOUT, _COL_RADIUS = 6, 7
    _COL_ASPECT_RATIO, _COL_SOLIDITY = 8, 9
    _COL_EXTRA_OVERRIDES = 10

    #: Geometry parameters with a dedicated column of their own, mapped
    #: to that column's index. Every other parameter of
    #: ``GEOMETRY_PARAMS`` surfaces in the "Extra overrides" column.
    _COLUMN_MAPPED_PARAMS = {
        "root_chord_norm": _COL_ROOT_CHORD,
        "tip_chord_norm": _COL_TIP_CHORD,
        "twist_root_deg": _COL_TWIST_ROOT,
        "twist_tip_deg": _COL_TWIST_TIP,
        "n_blades": _COL_BLADES,
        "root_cutout_norm": _COL_ROOT_CUTOUT,
        "radius_m": _COL_RADIUS,
    }

    #: Tooltip each read-only projection column receives when the
    #: refresh materializes its item for the first time.
    _PROJECTION_TOOLTIPS = {
        _COL_ASPECT_RATIO:
            "Derived from this row's planform: AR = 1/∫c d(r/R); "
            "solidity σ = n·∫c d(r/R)/π.",
        _COL_SOLIDITY:
            "Derived from this row's planform: AR = 1/∫c d(r/R); "
            "solidity σ = n·∫c d(r/R)/π.",
        _COL_EXTRA_OVERRIDES:
            "Parameters without a dedicated column, overridden by "
            "this row.",
    }

    #: Ranking fields offered after a run, in display order; the combo
    #: keeps only the ones present in at least one summary.
    _RANKING_FIELDS = ("CT", "FM", "CP", "eta_prop", "Thrust",
                       "aspect_ratio", "solidity")

    #: Fields of the full overlay figure, in panel order.
    _OVERLAY_FIELDS = ("CT", "FM", "CP", "eta_prop",
                       "aspect_ratio", "solidity")

    #: "Thrust matching" choices of the Conditions page, as shown,
    #: mapped to the ``trim`` argument ``api.compare_geometries``
    #: understands. The first variant of the table is the reference
    #: every other one is trimmed to; this is a choice of the run, not
    #: a stored project field, so it has no .bemt key.
    _TRIM_CHOICES = {"(off)": "none", "Thrust": "thrust", "CT": "CT"}

    def __init__(self, state: AppState, parent: QWidget | None = None):
        super().__init__(parent)
        # A separate top-level window that still belongs to the main
        # window's lifetime: without the Window flag, a parented QWidget
        # would embed INSIDE the parent instead of opening its own
        # window.
        self.setWindowFlag(Qt.WindowType.Window)
        self.setWindowTitle("Geometry Designer")
        self.resize(1080, 700)
        self.state = state

        # True while the window fills its widgets FROM the project, so a
        # signal fired by the fill does not schedule previews mid-flight.
        self._seeding = False
        # Reentrancy guard for the project rebuild itself.
        self._refreshing_from_project = False
        # Reentrancy guard for the derived-cell projection (the
        # read-only columns), whose own writes would otherwise
        # retrigger it through cellChanged.
        self._refreshing_derived = False

        # One worker/thread pair; both stay None between runs.
        self._compare_thread: QThread | None = None
        self._compare_worker: CompareWorker | None = None

        # Outputs of the last run, kept for the verdict strip, the
        # ranking combo and the export buttons.
        self._comparison_results: list | None = None

        self._variant_counter = 0

        # Per-family counters of the Generate block ("rectangular 1",
        # "rectangular 2", ...), reset whenever the table is reseeded.
        self._generate_counters: dict = {}

        # Session base override: the geometry imported through "Replace
        # base", which stands in for the project's own planform until
        # another project opens. The project file itself is never
        # touched; ``_imported_base_name`` only feeds the note shown in
        # the base row's "Extra overrides" cell.
        self._base_override = None
        self._imported_base_name = ""

        # Debounce for the planform preview: one redraw 400 ms after the
        # last cell edit, never one per keystroke.
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(400)
        self._preview_timer.timeout.connect(self._draw_preview)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.pages = QTabWidget()
        self.pages.addTab(self._build_variants_page(), "Variants")
        self.pages.addTab(self._build_conditions_page(), "Conditions")
        self.pages.addTab(self._build_run_page(), "Run && results")
        layout.addWidget(self.pages)

        self.state.project_changed.connect(self._on_project_changed)
        self.state.mode_changed.connect(self._refresh_mode_labels)
        self._on_project_changed()

    # =====================================================================
    # Page 1 -- variants
    # =====================================================================

    def _build_variants_page(self) -> QWidget:
        page = QWidget()
        hbox = QHBoxLayout(page)

        # The groupbox title keeps the block's help entry ("Geometry
        # comparison") anchored to the tool that moved into this window.
        box = QGroupBox("Geometry comparison")
        hbox.addWidget(box, stretch=1)
        inner = QHBoxLayout(box)

        table_column = QVBoxLayout()
        table_column.addWidget(QLabel("Blade geometries to compare:"))
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
            "a whole number. Root cutout and Radius are direct "
            "parameters of every row: an empty cell keeps the session "
            "base value, and the base row shows the base's own values."
            "\n\n"
            "Aspect ratio and Solidity are read-only derivations: "
            "AR = 1/I and σ = n_blades·I/π, with I = ∫c d(r/R) over the "
            "row's own stations.\n\n"
            "Extra overrides summarizes, read-only, every override of "
            "the row that has no column of its own.")
        self.variants_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.variants_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.variants_table.verticalHeader().setVisible(False)
        self.variants_table.setMinimumHeight(160)
        self.variants_table.cellChanged.connect(
            self._on_variant_cell_changed)
        table_column.addWidget(self.variants_table)

        button_row = QHBoxLayout()
        self.btn_add_variant = QPushButton("Add")
        self.btn_add_variant.setToolTip(
            "Adds a copy of the base row under the label \"variant N\". "
            "Edit the copy to describe another blade planform.")
        self.btn_add_variant.clicked.connect(self._add_variant_row)
        button_row.addWidget(self.btn_add_variant)
        self.btn_duplicate_variant = QPushButton("Duplicate")
        self.btn_duplicate_variant.setToolTip(
            "Adds a copy of the selected row under a new unique label.")
        self.btn_duplicate_variant.clicked.connect(
            self._duplicate_selected_variant)
        button_row.addWidget(self.btn_duplicate_variant)
        self.btn_remove_variant = QPushButton("Remove")
        self.btn_remove_variant.setToolTip(
            "Removes the selected rows from the geometry table.")
        self.btn_remove_variant.clicked.connect(self._remove_selected_variants)
        button_row.addWidget(self.btn_remove_variant)
        button_row.addStretch(1)
        table_column.addLayout(button_row)
        builder_column = QVBoxLayout()
        builder_column.addWidget(self._build_sweep_box())
        builder_column.addWidget(self._build_generate_box())
        builder_column.addStretch(1)
        inner.addLayout(builder_column)
        inner.addLayout(table_column, stretch=3)

        preview_column = QVBoxLayout()
        preview_column.addWidget(QLabel("Planform preview:"))
        self.preview_canvas = CanvasHost()
        self.preview_canvas.setMinimumHeight(240)
        preview_column.addWidget(self.preview_canvas, stretch=1)
        inner.addLayout(preview_column, stretch=2)

        return page

    # --- variation sweep builder -------------------------------------------

    def _build_sweep_box(self) -> QFrame:
        """The variation-sweep builder: one geometry parameter carried
        through several values, one appended row per value.

        A framed panel with a text heading rather than a ``QGroupBox``:
        block-title help popups resolve through the groupbox titles, and
        this builder has no block entry yet (a later documentation pass
        owns that wiring -- see the module docstring)."""
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        vbox = QVBoxLayout(box)
        heading = QLabel("Variation sweep")
        heading.setStyleSheet("font-weight: bold;")
        vbox.addWidget(heading)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(inner)

        self.vsweep_param_combo = QComboBox()
        self.vsweep_param_combo.setToolTip(
            "Geometry parameter varied across the generated rows. Each "
            "value is validated against the base planform and becomes "
            "one new table row. On a base without a parametric generator "
            "(an imported blade, a hand-edited table) the planform "
            "parameters are applied in table space: the chord and twist "
            "distributions are rescaled so their endpoints hit the "
            "requested values.")
        for name in GEOMETRY_PARAMS:
            self.vsweep_param_combo.addItem(name, userData=name)
        self.vsweep_param_combo.setCurrentText("tip_chord_norm")
        form.addRow("Parameter:", self.vsweep_param_combo)

        start_end_tooltip = "Range of the generated values, both included."
        self.vsweep_start = QDoubleSpinBox()
        self.vsweep_start.setRange(-10.0, 10.0)
        self.vsweep_start.setDecimals(4)
        self.vsweep_start.setSingleStep(0.005)
        self.vsweep_start.setValue(0.03)
        self.vsweep_start.setToolTip(start_end_tooltip)
        form.addRow("Start:", self.vsweep_start)

        self.vsweep_end = QDoubleSpinBox()
        self.vsweep_end.setRange(-10.0, 10.0)
        self.vsweep_end.setDecimals(4)
        self.vsweep_end.setSingleStep(0.005)
        self.vsweep_end.setValue(0.06)
        self.vsweep_end.setToolTip(start_end_tooltip)
        form.addRow("End:", self.vsweep_end)

        self.vsweep_count = QSpinBox()
        self.vsweep_count.setRange(1, 50)
        self.vsweep_count.setValue(3)
        self.vsweep_count.setToolTip(
            "Number of evenly spaced values between Start and End.")
        form.addRow("Count:", self.vsweep_count)

        self.vsweep_values_edit = QLineEdit()
        self.vsweep_values_edit.setPlaceholderText("e.g. 0.04, 0.06, 0.09")
        self.vsweep_values_edit.setToolTip(
            "Optional explicit values, comma separated. When this field "
            "has content it replaces Start/End/Count.")
        form.addRow("Values:", self.vsweep_values_edit)

        self.btn_build_sweep = QPushButton("Build variants")
        self.btn_build_sweep.setToolTip(
            "Appends one geometry row per value of the sweep, under a "
            "label naming the parameter and its value.")
        self.btn_build_sweep.clicked.connect(self._build_sweep_variants)
        form.addRow(self.btn_build_sweep)
        return box

    # --- generate variant block ---------------------------------------------

    #: Planform families offered by the Generate block, in display
    #: order. Same list as ``studies.variant_geometry``'s builders and
    #: ``geometry``'s generators; a new generator lands in all three
    #: places or not at all.
    _GENERATE_FAMILIES = ("rectangular", "tapered", "elliptic")

    #: Which families expose which planform field. The twist pair, the
    #: radius, the blade count, the root cutout and the station count
    #: are shared by every family and always visible.
    _GENERATE_FIELD_FAMILIES = {
        "gen_chord_spin": ("rectangular",),
        "gen_root_chord_spin": ("tapered",),
        "gen_tip_chord_spin": ("tapered",),
        "gen_max_chord_spin": ("elliptic",),
    }

    def _build_generate_box(self) -> QFrame:
        """The Generate block: pick a planform family, fill its fields,
        add the built blade as one row carrying the GENERATED geometry.

        Same framed-panel pattern as the variation-sweep builder (see
        its docstring for why not a ``QGroupBox``), and the same
        progressive-reveal pattern as the Airfoil tab's contour Source
        dropdown: one combo decides which family fields are on screen,
        with `set_row_visible` so no label is ever orphaned."""
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        vbox = QVBoxLayout(box)
        heading = QLabel("Generate variant")
        heading.setStyleSheet("font-weight: bold;")
        vbox.addWidget(heading)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(inner)
        self._generate_form = form

        self.gen_family_combo = QComboBox()
        self.gen_family_combo.addItems(list(self._GENERATE_FAMILIES))
        self.gen_family_combo.setToolTip(
            "Planform family of the generated blade: rectangular keeps "
            "one chord along the span, tapered interpolates root to tip "
            "chord, elliptic peaks at the root.")
        form.addRow("Family:", self.gen_family_combo)

        def add_chord_spin(attr, label, default):
            spin = QDoubleSpinBox()
            spin.setRange(0.001, 5.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.005)
            spin.setValue(default)
            form.addRow(label, spin)
            setattr(self, attr, spin)
            return spin

        add_chord_spin("gen_chord_spin", "Chord [c/R]:", 0.08).setToolTip(
            '"chord_norm" — Constant chord of the rectangular blade, '
            "as c/R.")
        add_chord_spin("gen_root_chord_spin", "Root chord [c/R]:",
                        0.10).setToolTip(
            '"root_chord_norm" — Chord at the root station, as c/R; the '
            "tip chord interpolates linearly toward it.")
        add_chord_spin("gen_tip_chord_spin", "Tip chord [c/R]:",
                        0.04).setToolTip(
            '"tip_chord_norm" — Chord at the tip station, as c/R.')
        add_chord_spin("gen_max_chord_spin", "Max chord [c/R]:",
                        0.10).setToolTip(
            '"max_chord_norm" — Peak chord of the elliptic planform, '
            "reached at the root, as c/R.")

        self.gen_twist_root_spin = QDoubleSpinBox()
        self.gen_twist_root_spin.setRange(-30.0, 30.0)
        self.gen_twist_root_spin.setDecimals(1)
        self.gen_twist_root_spin.setSingleStep(0.5)
        self.gen_twist_root_spin.setValue(12.0)
        self.gen_twist_root_spin.setToolTip(
            '"twist_root_deg" — Pitch angle at the root station of the '
            "generated blade.")
        form.addRow("Twist root [deg]:", self.gen_twist_root_spin)

        self.gen_twist_tip_spin = QDoubleSpinBox()
        self.gen_twist_tip_spin.setRange(-30.0, 30.0)
        self.gen_twist_tip_spin.setDecimals(1)
        self.gen_twist_tip_spin.setSingleStep(0.5)
        self.gen_twist_tip_spin.setValue(4.0)
        self.gen_twist_tip_spin.setToolTip(
            '"twist_tip_deg" — Pitch angle at the tip station; the twist '
            "interpolates linearly from the root value.")
        form.addRow("Twist tip [deg]:", self.gen_twist_tip_spin)

        self.gen_radius_spin = QDoubleSpinBox()
        self.gen_radius_spin.setRange(0.01, 100.0)
        self.gen_radius_spin.setDecimals(3)
        self.gen_radius_spin.setSingleStep(0.1)
        self.gen_radius_spin.setToolTip(
            '"radius_m" — Rotor radius in m. The table measures every '
            "r/R and c/R against it.")
        form.addRow("Radius [m]:", self.gen_radius_spin)

        self.gen_blades_spin = QSpinBox()
        self.gen_blades_spin.setRange(1, 8)
        self.gen_blades_spin.setToolTip(
            '"n_blades" — Number of blades of the generated rotor.')
        form.addRow("Blades:", self.gen_blades_spin)

        self.gen_cutout_spin = QDoubleSpinBox()
        self.gen_cutout_spin.setRange(0.0, 0.95)
        self.gen_cutout_spin.setDecimals(3)
        self.gen_cutout_spin.setSingleStep(0.01)
        self.gen_cutout_spin.setToolTip(
            '"root_cutout_norm" — Inner radius where the blade starts, '
            "as r/R. It is the first station of the table.")
        form.addRow("Root cutout [r/R]:", self.gen_cutout_spin)

        self.gen_stations_spin = QSpinBox()
        self.gen_stations_spin.setRange(4, 60)
        self.gen_stations_spin.setToolTip(
            '"n_stations" — Number of radial stations of the generated '
            "table. More stations resolve the tip gradient better but "
            "solve slower.")
        form.addRow("Stations:", self.gen_stations_spin)

        button_row = QHBoxLayout()
        self.btn_add_generated = QPushButton("Add as variant")
        self.btn_add_generated.setToolTip(
            "Builds the blade from these fields. Then it appends the "
            "blade as a row that carries the generated geometry "
            "itself, not overrides over the base. The label cell stays "
            "editable.")
        self.btn_add_generated.clicked.connect(self._add_generated_variant)
        button_row.addWidget(self.btn_add_generated)
        self.btn_import_project = QPushButton("Import from project…")
        self.btn_import_project.setToolTip(
            "Brings the blade of another project into this comparison. "
            "Add it as an extra variant row, or use it as this "
            "session's base planform. This window only reads the other "
            "project.")
        self.btn_import_project.clicked.connect(self._import_from_project)
        button_row.addWidget(self.btn_import_project)
        button_row.addStretch(1)
        form.addRow(button_row)

        self.gen_family_combo.currentTextChanged.connect(
            lambda _text: self._update_generate_fields())
        self._update_generate_fields()
        return box

    def _update_generate_fields(self):
        """Reveals only the planform fields of the selected family.

        Goes through ``set_row_visible`` so each hidden field takes its
        whole row -- label included -- off the screen."""
        family = self.gen_family_combo.currentText()
        for attr, families in self._GENERATE_FIELD_FAMILIES.items():
            set_row_visible(self._generate_form, getattr(self, attr),
                            family in families)

    def _reset_generate_defaults(self):
        """Seeds the shared Generate fields from the session base:
        radius, blade count, root cutout and station count."""
        base = self._session_base_geometry()
        if base is None:
            return
        self.gen_radius_spin.setValue(float(base.radius_m))
        self.gen_blades_spin.setValue(int(base.n_blades))
        self.gen_cutout_spin.setValue(float(base.root_cutout_norm))
        stations = len(base.r_norm) or 25
        self.gen_stations_spin.setValue(int(min(max(stations, 4), 60)))

    def _add_generated_variant(self):
        """Builds one blade from the Generate block's fields and appends
        it as a row carrying the GENERATED geometry itself."""
        project = self.state.project
        if project is None:
            QMessageBox.warning(self, "No project",
                                "Open or create a project first.")
            return
        family = self.gen_family_combo.currentText()
        kwargs: dict = {
            "twist_root_deg": float(self.gen_twist_root_spin.value()),
            "twist_tip_deg": float(self.gen_twist_tip_spin.value()),
            "radius_m": float(self.gen_radius_spin.value()),
            "n_blades": int(self.gen_blades_spin.value()),
            "root_cutout_norm": float(self.gen_cutout_spin.value()),
            "n_stations": int(self.gen_stations_spin.value()),
            "airfoil_name": getattr(self._session_base_geometry(),
                                    "airfoil_name", ""),
        }
        if family == "rectangular":
            builder, planform = geometry.generate_rectangular, {
                "chord_norm": float(self.gen_chord_spin.value())}
        elif family == "tapered":
            builder, planform = geometry.generate_tapered, {
                "root_chord_norm": float(self.gen_root_chord_spin.value()),
                "tip_chord_norm": float(self.gen_tip_chord_spin.value())}
        else:
            builder, planform = geometry.generate_elliptic, {
                "max_chord_norm": float(self.gen_max_chord_spin.value())}
        try:
            geom = builder(**kwargs, **planform)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid variant parameters",
                                str(exc))
            return
        count = self._generate_counters.get(family, 0) + 1
        self._generate_counters[family] = count
        self._append_absolute_row(f"{family} {count}", geom,
                                  f"generated ({family})")

    def _append_absolute_row(self, label: str, geom, marker: str):
        """Appends one row whose label item carries a COMPLETE geometry.

        The planform cells stay on screen but inert (non-editable):
        they would read as overrides over the base, which this row does
        not have -- its geometry IS the definition. ``_row_resolved``
        and therefore collect, preview and exports use the payload as
        given; Duplicate copies it verbatim."""
        table = self.variants_table
        self._seeding = True
        try:
            row = table.rowCount()
            table.insertRow(row)
            inert_tooltip = ("This row carries a complete generated "
                             "geometry. Its cells are not editable "
                             "table overrides.")
            for col in range(table.columnCount()):
                item = QTableWidgetItem("")
                if col != self._COL_LABEL:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled
                                  | Qt.ItemFlag.ItemIsSelectable)
                    item.setToolTip(inert_tooltip)
                table.setItem(row, col, item)
            table.item(row, self._COL_LABEL).setText(label)
            table.item(row, self._COL_LABEL).setData(
                Qt.ItemDataRole.UserRole, _AbsoluteRowGeometry(geom,
                                                                marker))
            self._refresh_derived_cells()
        finally:
            self._seeding = False
        self._draw_preview()

    # --- import from project -------------------------------------------------

    def _import_from_project(self):
        """Brings another project's blade into this comparison.

        The user picks a project folder; after the project opens, a
        modal choice decides between appending its blade as one more
        variant row and making it this session's base. The other
        project's files are only ever READ."""
        if self.state.project is None:
            QMessageBox.warning(self, "No project",
                                "Open or create a project first.")
            return
        path = QFileDialog.getExistingDirectory(
            self, "Import blade from project")
        if not path:
            return
        try:
            imported = self._read_import_project(path)
        except Exception as exc:
            show_error(self, "Error importing project", exc)
            return
        choice = self._ask_import_choice(imported.name)
        if choice == "variant":
            self._append_imported_variant(imported)
        elif choice == "base":
            self._replace_session_base(imported)

    @staticmethod
    def _read_import_project(path: str):
        """Opens the project at ``path``, refusing folders that hold no
        project at all.

        ``api.open_project`` fills every missing file with defaults, so
        without this check an arbitrary folder would import a silent,
        default-shaped blade. A project folder is a folder with the
        project's .bemt files (geom.bemt, config.bemt, ...) inside an
        ``inputs`` subfolder."""
        paths = default_project_paths(path)
        if not paths["geom"].exists():
            raise ValueError(
                f"{path} is not a project folder. A project folder "
                "contains the .bemt files of a project (geom.bemt, "
                'config.bemt, ...) inside an "inputs" subfolder.')
        return api.open_project(path)

    def _ask_import_choice(self, name: str) -> str:
        """The modal "what should the imported blade become" question.

        Returns ``"variant"``, ``"base"`` or ``"cancel"``; split from
        ``_import_from_project`` so tests can decide for it."""
        box = QMessageBox(self)
        box.setWindowTitle("Import from project")
        box.setText(f'Use the blade of "{name}" as:')
        variant_button = box.addButton("Add as variant",
                                        QMessageBox.ButtonRole.AcceptRole)
        base_button = box.addButton("Replace base",
                                     QMessageBox.ButtonRole.ActionRole)
        cancel_button = box.addButton("Cancel",
                                       QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is base_button:
            return "base"
        if clicked is variant_button:
            return "variant"
        return "cancel"

    def _append_imported_variant(self, imported):
        """Adds the imported blade as one absolute-geometry row labeled
        with the project name (deduplicated against current labels)."""
        table = self.variants_table
        existing = {self._row_label(row)
                    for row in range(table.rowCount())}
        label = self._unique_label(imported.name, existing)
        self._append_absolute_row(label, imported.geometry, "imported")

    def _replace_session_base(self, imported):
        """Makes the imported blade THIS SESSION's base planform.

        Stores the geometry on the window (never in the project): every
        override row now builds on it through
        ``_session_base_geometry``, the base row's cells reseed from it,
        and its Extra overrides cell notes the origin. The imported
        project file stays untouched."""
        table = self.variants_table
        if table.rowCount() == 0:
            QMessageBox.warning(self, "No project",
                                "Open or create a project first.")
            return
        self._base_override = imported.geometry
        self._imported_base_name = imported.name
        self._seeding = True
        try:
            self._write_base_row_cells(imported.geometry)
            self._refresh_derived_cells()
        finally:
            self._seeding = False
        self._draw_preview()
    def _sweep_values(self) -> list[float]:
        """The values of the variation sweep: the comma-separated list
        when it has content, otherwise evenly spaced Start..End..Count.

        Raises ``ValueError`` with a readable message when the fields
        hold no usable range."""
        raw = self.vsweep_values_edit.text().strip()
        if raw:
            values = parse_list(raw)
            if not values:
                raise ValueError("The Values field holds no readable number.")
        else:
            start, end = (float(self.vsweep_start.value()),
                          float(self.vsweep_end.value()))
            count = int(self.vsweep_count.value())
            if end < start:
                raise ValueError("End must be greater than or equal to Start.")
            values = [float(v) for v in np.linspace(start, end, count)]
        param = self.vsweep_param_combo.currentData()
        if param in INTEGER_PARAMS:
            unique_ints: list[int] = []
            for value in values:
                candidate = int(round(value))
                if candidate not in unique_ints:
                    unique_ints.append(candidate)
            values = [float(v) for v in unique_ints]
        return values

    @staticmethod
    def _override_fragment(param: str, value) -> str:
        """One ``param=value`` fragment, in the sweep-label format
        ("tip_chord_norm=0.040")."""
        if param in INTEGER_PARAMS:
            return f"{param}={int(value)}"
        return f"{param}={float(value):.3f}"

    @classmethod
    def _sweep_label(cls, param: str, value) -> str:
        """Row label of one swept value."""
        return cls._override_fragment(param, value)

    @classmethod
    def _extra_override_params(cls) -> tuple:
        """The geometry parameters without a dedicated table column,
        derived from ``GEOMETRY_PARAMS`` minus ``_COLUMN_MAPPED_PARAMS``
        so the two lists can never drift apart."""
        return tuple(name for name in GEOMETRY_PARAMS
                     if name not in cls._COLUMN_MAPPED_PARAMS)

    @classmethod
    def _extra_overrides_text(cls, overrides: dict) -> str:
        """Renders a row's columnless overrides as ``param=value``
        fragments joined with "; "; an em dash when there are none."""
        fragments = [cls._override_fragment(param, overrides[param])
                     for param in cls._extra_override_params()
                     if param in overrides]
        return "; ".join(fragments) if fragments else "—"

    def _param_cells(self, param: str, value) -> dict:
        """Table cells a swept parameter fills, keyed by column index.

        Follows the same parameter-to-column map ``_row_overrides``
        reads back, so an edited built row stays coherent. Every
        parameter of ``GEOMETRY_PARAMS`` fills at least one cell
        today; the fallback (the value riding on the label item's
        data, which ``_row_overrides`` also reads) remains for any
        parameter a future generator adds without a column.
        """
        base = self._session_base_geometry()
        origin_params = dict(getattr(base, "origin_params", {}) or {})
        kind = str(origin_params.get("kind", ""))
        text = self._fmt(value)
        if param == "n_blades":
            return {self._COL_BLADES: str(int(value))}
        if param == "root_cutout_norm":
            return {self._COL_ROOT_CUTOUT: text}
        if param == "radius_m":
            return {self._COL_RADIUS: text}
        if param == "twist_root_deg":
            return {self._COL_TWIST_ROOT: text}
        if param == "twist_tip_deg":
            return {self._COL_TWIST_TIP: text}
        if param == "root_chord_norm" and kind == "tapered":
            return {self._COL_ROOT_CHORD: text}
        if param == "tip_chord_norm" and kind == "tapered":
            return {self._COL_TIP_CHORD: text}
        if param == "chord_norm":   # rectangular reads root-or-tip
            return {self._COL_ROOT_CHORD: text, self._COL_TIP_CHORD: text}
        if param == "max_chord_norm":   # elliptic reads root only
            return {self._COL_ROOT_CHORD: text}
        return {}

    def _append_sweep_row(self, param: str, value) -> None:
        """Appends one variant row for ``param=value``, starting from a
        copy of the base row so the other parameters keep the project's
        values."""
        table = self.variants_table
        target_row = table.rowCount()
        table.insertRow(target_row)
        self._copy_row(0, target_row)
        cells = self._param_cells(param, value)
        for column, text in cells.items():
            item = table.item(target_row, column)
            if item is not None:
                item.setText(text)
        label_item = table.item(target_row, self._COL_LABEL)
        if label_item is not None:
            label_item.setText(self._sweep_label(param, value))
            if not cells:
                # No cell carries this parameter (defensive fallback:
                # every current parameter owns a cell): the override
                # travels in the label item's data instead, and
                # `_row_overrides` picks it up.
                label_item.setData(Qt.ItemDataRole.UserRole, {param: value})

    def _build_sweep_variants(self):
        """Appends one table row per value of the variation sweep.

        Every value is validated through ``api.variant_geometry``
        BEFORE its row is added, so a parameter the current generator
        does not accept stops the build with a message instead of
        leaving rows that fail only at run time."""
        project = self.state.project
        if project is None:
            QMessageBox.warning(self, "No project",
                                "Open or create a project first.")
            return
        param = self.vsweep_param_combo.currentData()
        try:
            values = self._sweep_values()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid variation sweep", str(exc))
            return
        if not values:
            QMessageBox.warning(
                self, "Invalid variation sweep",
                "Enter at least one value, or set Count to at least 1.")
            return
        base = self._session_base_geometry()
        self._seeding = True
        try:
            for value in values:
                overrides = {param: value}
                try:
                    api.variant_geometry(base, overrides)
                except Exception as exc:
                    raise ValueError(f"{param}={value:g}: {exc}") from exc
                self._append_sweep_row(param, value)
                self._refresh_derived_cells()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid variation sweep", str(exc))
        finally:
            self._seeding = False
        self._update_summary_label()
        self._draw_preview()

    # --- variant table ---------------------------------------------------

    def _session_base_geometry(self):
        """The geometry every override row builds on: the blade imported
        through "Replace base" while that choice is active, otherwise
        the project's own planform. The project file is never modified;
        this is a session-only substitution."""
        if self._base_override is not None:
            return self._base_override
        project = self.state.project
        return None if project is None else project.geometry

    @staticmethod
    def _fmt(value) -> str:
        """Formats a generator parameter for a table cell ('' when absent)."""
        if value is None:
            return ""
        return f"{float(value):.4g}"

    def _on_variant_cell_changed(self, row: int, column: int):
        """Refreshes the read-only projections after any cell edit,
        then schedules the planform preview."""
        self._refresh_derived_cells()
        self._schedule_preview()

    @staticmethod
    def _derived_texts(geom) -> tuple[str, str]:
        """``(aspect ratio, solidity)`` cell texts of one geometry.

        With I = ∫c d(r/R) over the row's own stations, AR = 1/I and
        σ = n_blades·I/π. An integral too small to be meaningful (a
        table too short or ragged to integrate) renders both as an em
        dash."""
        integral = _planform_integral(geom)
        if integral > 1e-9:
            return (f"{1.0 / integral:.2f}",
                    f"{int(geom.n_blades) * integral / np.pi:.3f}")
        return ("—", "—")

    def _write_projection_cell(self, row: int, column: int, text: str):
        """Writes one read-only projection cell.

        Creates the item on first use with the column's flags and
        tooltip; afterwards only the text moves."""
        table = self.variants_table
        item = table.item(row, column)
        if item is None:
            item = QTableWidgetItem("")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled
                          | Qt.ItemFlag.ItemIsSelectable)
            item.setToolTip(self._PROJECTION_TOOLTIPS.get(column, ""))
            table.setItem(row, column, item)
        if item.text() != text:
            item.setText(text)

    def _fill_direct_value_cells(self, row: int, geom):
        """Fills EMPTY Root-cutout and Radius cells from ``geom``.

        Only rows that carry a complete geometry of their own qualify:
        payload rows (generated or imported), whose cells stay inert,
        and the base row, whose cells remain EDITABLE -- filling only
        when empty means a user edit is never clobbered. Override rows
        are left alone: there an empty cell means "inherit the session
        base value"."""
        table = self.variants_table
        for column, value in ((self._COL_ROOT_CUTOUT,
                               getattr(geom, "root_cutout_norm", None)),
                              (self._COL_RADIUS,
                               getattr(geom, "radius_m", None))):
            if value is None:
                continue
            item = table.item(row, column)
            if item is not None and not item.text().strip():
                item.setText(f"{float(value):.3f}")

    def _refresh_derived_cells(self):
        """Recomputes every row's projected cells from its own data.

        Three columns are projections, never stores: "Aspect ratio",
        "Solidity" and "Extra overrides". Both metrics derive from the
        SAME resolution the run consumes (the rules of
        ``_row_resolved``), so the table can never disagree with what
        a run solves; "Extra overrides" renders the overrides that
        have no dedicated column, with ``_row_overrides`` staying the
        single reader of an override row. On top of the projections,
        the Root cutout and Radius cells of the base row and of
        payload rows are filled from their geometry while empty. A
        half-typed cell leaves that row's previous texts in place. The
        guard keeps the method's own writes from retriggering it
        through ``cellChanged``."""
        if self._refreshing_derived or self.state.project is None:
            return
        self._refreshing_derived = True
        try:
            table = self.variants_table
            for row in range(table.rowCount()):
                payload = self._stored_row_payload(row)
                if payload is not None:
                    extra_text = payload.marker
                    geom = payload.geometry
                else:
                    try:
                        _, overrides = self._row_overrides(row)
                    except (ValueError, TypeError):
                        continue   # a half-typed cell; keep the old texts
                    if row == 0 and self._base_override is not None:
                        extra_text = f"imported: {self._imported_base_name}"
                    else:
                        extra_text = \
                            self._extra_overrides_text(overrides)
                    try:
                        geom = api.variant_geometry(
                            self._session_base_geometry(), overrides)
                    except (ValueError, TypeError):
                        continue
                self._write_projection_cell(
                    row, self._COL_EXTRA_OVERRIDES, extra_text)
                # The direct values of a complete geometry surface even
                # where no override cell stores them.
                if payload is not None or row == 0:
                    self._fill_direct_value_cells(row, geom)
                ar_text, solidity_text = self._derived_texts(geom)
                self._write_projection_cell(
                    row, self._COL_ASPECT_RATIO, ar_text)
                self._write_projection_cell(
                    row, self._COL_SOLIDITY, solidity_text)
        finally:
            self._refreshing_derived = False

    def _seed_variant_rows(self):
        """Rebuilds the variant table from the session base geometry
        (the project's own planform, or the blade imported through
        "Replace base").

        One "base" row carries the planform parameters that geometry's
        origin actually stores in ``origin_params``. An imported or
        hand-edited table has no parametric origin: its planform cells
        stay empty (empty means "no override"), and only the blade count
        applies.
        """
        self._seeding = True
        try:
            table = self.variants_table
            table.setRowCount(0)
            self._variant_counter = 0
            self._generate_counters = {}
            if self.state.project is None:
                return
            table.insertRow(0)
            self._write_base_row_cells(self._session_base_geometry())
            # The projection columns (aspect ratio, solidity, extra
            # overrides) are not seeded: the refresh fills them from
            # each row itself.
            self._refresh_derived_cells()
        finally:
            self._seeding = False

    def _write_base_row_cells(self, geom):
        """Writes the BASE row's cells from ``geom``: the project's own
        planform on a reseed, or an imported blade after "Replace
        base".

        The override columns are written from ``geom`` itself; root
        cutout and radius are direct fields every geometry carries, so
        they seed regardless of the origin. The derived columns and
        "Extra overrides" are projections that
        ``_refresh_derived_cells`` fills."""
        table = self.variants_table
        origin_params = dict(getattr(geom, "origin_params", {}) or {})
        kind = str(origin_params.get("kind", ""))
        values = ["base", "", "", "", "", str(int(geom.n_blades)), "", ""]
        if kind == "rectangular":
            values[self._COL_ROOT_CHORD] = self._fmt(
                origin_params.get("chord_norm"))
            values[self._COL_TIP_CHORD] = values[self._COL_ROOT_CHORD]
        elif kind == "tapered":
            values[self._COL_ROOT_CHORD] = self._fmt(
                origin_params.get("root_chord_norm"))
            values[self._COL_TIP_CHORD] = self._fmt(
                origin_params.get("tip_chord_norm"))
        elif kind == "elliptic":
            values[self._COL_ROOT_CHORD] = self._fmt(
                origin_params.get("max_chord_norm"))
        values[self._COL_TWIST_ROOT] = self._fmt(
            origin_params.get("twist_root_deg"))
        values[self._COL_TWIST_TIP] = self._fmt(
            origin_params.get("twist_tip_deg"))
        values[self._COL_ROOT_CUTOUT] = f"{float(geom.root_cutout_norm):.3f}"
        values[self._COL_RADIUS] = f"{float(geom.radius_m):.3f}"
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            if col == self._COL_TIP_CHORD and kind == "elliptic":
                item.setText("-")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(
                    "Not applicable: the elliptic generator has a single "
                    "chord parameter (max_chord_norm).")
            table.setItem(0, col, item)

    def _copy_row(self, source_row: int, target_row: int) -> None:
        """Copies every cell of one row into another, flags and carried
        overrides included.

        Every override column copies as it stands, so a copy of the
        base row carries the base's own cutout and radius values as
        its starting overrides; a copy of a row that carries a
        complete geometry stays inert in every column."""
        source = self.variants_table
        for col in range(source.columnCount()):
            base_item = source.item(source_row, col)
            text = base_item.text() if base_item is not None else ""
            item = QTableWidgetItem(text)
            if base_item is not None:
                if not (base_item.flags() & Qt.ItemFlag.ItemIsEditable):
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    item.setToolTip(base_item.toolTip())
                carried = base_item.data(Qt.ItemDataRole.UserRole)
                if carried is not None:
                    item.setData(Qt.ItemDataRole.UserRole, carried)
            source.setItem(target_row, col, item)

    def _add_variant_row(self):
        """Duplicates the base row under the label "variant N"."""
        source = self.variants_table
        if source.rowCount() == 0:
            return
        self._seeding = True
        try:
            self._variant_counter += 1
            target_row = source.rowCount()
            source.insertRow(target_row)
            self._copy_row(0, target_row)
            label_item = source.item(target_row, self._COL_LABEL)
            if label_item is not None:
                label_item.setText(f"variant {self._variant_counter}")
            self._refresh_derived_cells()
        finally:
            self._seeding = False
        self._draw_preview()

    def _duplicate_selected_variant(self):
        """Duplicates the selected row under a new unique label."""
        source = self.variants_table
        row = source.currentRow()
        if row < 0:
            return
        self._seeding = True
        try:
            target_row = source.rowCount()
            source.insertRow(target_row)
            self._copy_row(row, target_row)
            label_item = source.item(row, self._COL_LABEL)
            base_label = label_item.text() if label_item is not None else ""
            label_item = source.item(target_row, self._COL_LABEL)
            if label_item is not None:
                label_item.setText(f"{base_label} copy")
            self._refresh_derived_cells()
        finally:
            self._seeding = False
        self._draw_preview()

    def _remove_selected_variants(self):
        row = self.variants_table.currentRow()
        if row >= 0:
            self.variants_table.removeRow(row)
            self._draw_preview()

    def _row_overrides(self, row: int) -> tuple[str, dict]:
        """``(label, overrides)`` read from one variant-table row.

        Empty cells produce no override. Chord cells map onto the
        parameter the CURRENT base planform understands (the session
        base, which may be an imported blade), so a table written for a
        tapered project still reads sensibly after the base changes.
        """
        base = self._session_base_geometry()
        origin_params = dict(getattr(base, "origin_params", {}) or {})
        kind = str(origin_params.get("kind", ""))

        def cell(col: int) -> str:
            item = self.variants_table.item(row, col)
            text = item.text().strip() if item is not None else ""
            return "" if text == "-" else text

        label = self._row_label(row)
        overrides: dict = {}
        # Overrides carried by the row itself (the defensive fallback
        # for a swept parameter whose `_param_cells` found no cell).
        # Cell values read below take precedence: an edit on the
        # table wins.
        label_item = self.variants_table.item(row, self._COL_LABEL)
        if label_item is not None:
            carried = label_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(carried, dict):
                overrides.update(carried)
        blades = cell(self._COL_BLADES)
        if blades:
            overrides["n_blades"] = int(float(blades))
        cutout = cell(self._COL_ROOT_CUTOUT)
        if cutout:
            overrides["root_cutout_norm"] = float(cutout)
        radius = cell(self._COL_RADIUS)
        if radius:
            overrides["radius_m"] = float(radius)
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

    def _row_label(self, row: int) -> str:
        """The label cell of one row, with the shared fallback name."""
        item = self.variants_table.item(row, self._COL_LABEL)
        text = item.text().strip() if item is not None else ""
        return "" if text == "-" else text or f"variant {row + 1}"

    def _stored_row_payload(self, row: int) -> _AbsoluteRowGeometry | None:
        """The complete geometry a row carries, or None: override rows
        (the sweep builder and manual rows) keep a dict on their label
        item, absolute rows keep an ``_AbsoluteRowGeometry``."""
        item = self.variants_table.item(row, self._COL_LABEL)
        if item is None:
            return None
        carried = item.data(Qt.ItemDataRole.UserRole)
        return carried if isinstance(carried, _AbsoluteRowGeometry) else None

    def _row_resolved(self, row: int) -> tuple[str, object]:
        """``(label, geometry)`` of one row through the SAME resolution
        the run consumes -- so the preview, the exports and
        ``_collect_variants`` can never disagree about what a row means.

        An absolute row returns its stored geometry as given; every
        other row applies its overrides over the session base."""
        payload = self._stored_row_payload(row)
        if payload is not None:
            return self._row_label(row), payload.geometry
        label, overrides = self._row_overrides(row)
        return label, api.variant_geometry(self._session_base_geometry(),
                                            overrides)

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
                label, geom = self._row_resolved(row)
            except ValueError as exc:
                raise ValueError(f"Geometry table, row {row + 1}: {exc}") from exc
            label = self._unique_label(label, variants)
            variants[label] = geom
        if not variants:
            raise ValueError("Add at least one geometry row before running.")
        return variants

    # --- planform preview --------------------------------------------------

    def _schedule_preview(self):
        """Starts the debounce timer after a user edit of the table."""
        if self._seeding:
            return
        self._preview_timer.start()

    def _draw_preview(self):
        """Overlays the planform outline of every row on one canvas.

        Each row resolves through ``_row_resolved``, the same path the
        run consumes, so absolute rows (generated or imported) draw
        their own geometry instead of re-deriving overrides."""
        canvas = self.preview_canvas.use_simple()
        canvas.clear()
        ax = canvas.ax
        n_rows = self.variants_table.rowCount()
        try:
            proxies = []
            for row in range(n_rows):
                label, geom = self._row_resolved(row)
                color = f"C{row % 10}"
                before = len(ax.lines)
                plots.plot_planform(geom, ax=ax, show_hub=False,
                                    show_tip_circle=(row == 0))
                # `plot_planform` colors the blades of EVERY call with the
                # same palette; recoloring the lines it just added keeps
                # one color per VARIANT, which is what an overlay needs.
                fade = 1.0 - 0.5 * (row / max(n_rows - 1, 4))
                for line in ax.lines[before:]:
                    line.set_color(color)
                    line.set_alpha(fade)
                proxies.append(Line2D([0], [0], color=color, linewidth=2,
                                      label=label))
            ax.set_title(f"Planform overlay ({n_rows} variants)")
            if proxies:
                ax.legend(handles=proxies, fontsize=7, loc="upper right")
        except Exception as exc:
            ax.clear()
            ax.set_axis_off()
            ax.text(0.5, 0.5, f"Could not draw the preview: {exc}",
                    ha="center", va="center", transform=ax.transAxes,
                    wrap=True)
        canvas.draw()

    # =====================================================================
    # Page 2 -- conditions
    # =====================================================================

    def _build_conditions_page(self) -> QWidget:
        page = QWidget()
        vbox = QVBoxLayout(page)

        mode_row = QHBoxLayout()
        self.radio_saved_cases = QRadioButton("Saved cases")
        self.radio_saved_cases.setToolTip(
            "Runs every case already stored in the project (Run Case > "
            "Save as case) on every variant.")
        self.radio_single = QRadioButton("Single condition")
        self.radio_single.setToolTip(
            "Runs one condition, built from the fields below, on every "
            "variant.")
        self.radio_sweep = QRadioButton("Sweep")
        self.radio_sweep.setToolTip(
            "Runs one axis through evenly spaced values, on every "
            "variant.")
        self.radio_single.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_saved_cases, 0)
        self.mode_group.addButton(self.radio_single, 1)
        self.mode_group.addButton(self.radio_sweep, 2)
        mode_row.addWidget(self.radio_saved_cases)
        mode_row.addWidget(self.radio_single)
        mode_row.addWidget(self.radio_sweep)
        vbox.addLayout(mode_row)

        self.conditions_stack = QStackedWidget()
        self.conditions_stack.addWidget(self._build_saved_cases_panel())
        self.conditions_stack.addWidget(self._build_single_condition_panel())
        self.conditions_stack.addWidget(self._build_sweep_panel())
        # `toggled`, not `idClicked`: checking a radio button from code
        # must switch the panel too, exactly as in Run Batch.
        self.radio_saved_cases.toggled.connect(
            lambda checked: self._show_conditions_panel(0 if checked else None))
        self.radio_single.toggled.connect(
            lambda checked: self._show_conditions_panel(1 if checked else None))
        self.radio_sweep.toggled.connect(
            lambda checked: self._show_conditions_panel(2 if checked else None))
        vbox.addWidget(self.conditions_stack)

        # Applies to every conditions mode: it changes WHAT one case
        # solves (a trimmed solve), never WHICH cases run.
        trim_row = QHBoxLayout()
        self.trim_label = QLabel("Thrust matching:")
        trim_row.addWidget(self.trim_label)
        self.trim_combo = QComboBox()
        for choice in self._TRIM_CHOICES:
            self.trim_combo.addItem(choice)
        self.trim_combo.setCurrentText("(off)")
        self.trim_combo.setToolTip(
            "Holds the loading constant across every variant, so "
            "efficiency compares fairly.\n\n"
            "Thrust or CT is read from the FIRST variant of the table "
            "(the base row), which is the reference: at every condition, "
            "each other variant re-solves one control to hit that "
            "target. Propellers solve RPM; rotors solve collective. "
            "This is a choice of this run only -- it is not stored in "
            "the project and has no .bemt key.\n\n"
            "Each trimmed case bisects its control, multiplying the "
            "runtime roughly tenfold per non-reference case.")
        self.trim_combo.currentIndexChanged.connect(
            lambda _index: self._update_summary_label())
        trim_row.addWidget(self.trim_combo)
        trim_row.addStretch(1)
        vbox.addLayout(trim_row)

        vbox.addStretch(1)

        summary_row = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: gray;")
        self.summary_label.setWordWrap(True)
        summary_row.addWidget(self.summary_label, 1)
        vbox.addLayout(summary_row)

        self._wire_summary_updates()
        self._update_summary_label()
        return page

    def _show_conditions_panel(self, index: int | None):
        """Shows the panel of the checked radio button, then refreshes
        the solve estimate."""
        if index is not None:
            self.conditions_stack.setCurrentIndex(index)
        self._update_summary_label()

    def _build_saved_cases_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.saved_count_label = QLabel("")
        self.saved_count_label.setToolTip(
            "Number of flight conditions stored in the project. Every "
            "one of them runs on every variant.")
        form.addRow("Stored conditions:", self.saved_count_label)
        return panel

    def _build_single_condition_panel(self) -> QWidget:
        panel = QWidget()
        self._single_form = QFormLayout(panel)

        self.mu_x_spin = QDoubleSpinBox()
        self.mu_x_spin.setRange(-0.5, 1.5)
        self.mu_x_spin.setDecimals(3)
        self.mu_x_spin.setSingleStep(0.01)
        self.mu_x_spin.setValue(0.0)
        self.mu_x_spin.setToolTip(
            '"mu_x" — Advance ratio along the vehicle x axis for the '
            'condition every variant runs.')
        self._single_form.addRow("mu_x:", self.mu_x_spin)

        self.collective_spin = QDoubleSpinBox()
        self.collective_spin.setRange(-10.0, 30.0)
        self.collective_spin.setSingleStep(0.5)
        self.collective_spin.setValue(8.0)
        self.collective_spin.setToolTip(
            '"collective_deg" — Collective pitch applied to every blade '
            'station of every variant.')
        self._single_form.addRow("collective [deg]:", self.collective_spin)

        self.vz_spin = QDoubleSpinBox()
        self.vz_spin.setRange(-50.0, 50.0)
        self.vz_spin.setDecimals(2)
        self.vz_spin.setSingleStep(1.0)
        self.vz_spin.setValue(0.0)
        self.vz_spin.setToolTip(
            '"Vz" — Velocity along the shaft, in m/s. Zero gives axial '
            'flight; climb is positive.')
        self._single_form.addRow("axial V [m/s]:", self.vz_spin)

        self.rpm_spin = QDoubleSpinBox()
        self.rpm_spin.setRange(1.0, 20000.0)
        self.rpm_spin.setDecimals(0)
        self.rpm_spin.setSingleStep(50)
        self.rpm_spin.setValue(1500)
        self.rpm_spin.setToolTip(
            '"rpm" — Rotational speed of the condition. The engine '
            'requires rpm on every condition: every result scales with '
            'the tip speed Ω·R, so no default exists.')
        self._single_form.addRow("RPM:", self.rpm_spin)
        return panel

    def _build_sweep_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)

        self.sweep_axis_combo = QComboBox()
        self.sweep_axis_combo.setToolTip(
            "Quantity carried through evenly spaced values. mu_x sweeps "
            "the edgewise flow; collective sweeps the blade pitch.")
        for key in ("mu_x", "collective_deg"):
            self.sweep_axis_combo.addItem(key, userData=key)
        self.sweep_axis_combo.currentIndexChanged.connect(
            lambda _index: self._update_summary_label())
        form.addRow("Axis:", self.sweep_axis_combo)

        self.sweep_start = QDoubleSpinBox()
        self.sweep_start.setRange(-1000.0, 1000.0)
        self.sweep_start.setDecimals(3)
        self.sweep_start.setValue(0.0)
        self.sweep_start.setToolTip("First value of the sweep, included.")
        form.addRow("Start:", self.sweep_start)

        self.sweep_stop = QDoubleSpinBox()
        self.sweep_stop.setRange(-1000.0, 1000.0)
        self.sweep_stop.setDecimals(3)
        self.sweep_stop.setValue(0.2)
        self.sweep_stop.setToolTip("Last value of the sweep, included.")
        form.addRow("Stop:", self.sweep_stop)

        self.sweep_count = QSpinBox()
        self.sweep_count.setRange(1, 200)
        self.sweep_count.setValue(5)
        self.sweep_count.setToolTip(
            "Number of evenly spaced values between start and stop.")
        form.addRow("Count:", self.sweep_count)

        fixed_hint = QLabel(
            "The remaining quantities keep the Single condition values.")
        fixed_hint.setStyleSheet("color: gray;")
        form.addRow(fixed_hint)
        return panel

    def _wire_summary_updates(self):
        """Refreshes the solve estimate whenever any input changes."""
        for spin in (self.sweep_start, self.sweep_stop, self.collective_spin,
                     self.vz_spin, self.rpm_spin, self.mu_x_spin):
            spin.valueChanged.connect(self._update_summary_label)
        self.sweep_count.valueChanged.connect(self._update_summary_label)

    def _selected_conditions(self) -> list[FlightCondition]:
        """Builds the ordered condition list of the Conditions page.

        Raises ``ValueError`` with a readable message when the current
        choice cannot run (no project, no saved cases, or a sweep with
        an inverted range).
        """
        project = self.state.project
        if project is None:
            raise ValueError("Open or create a project before running.")
        rpm = float(self.rpm_spin.value())
        if rpm <= 0.0:
            raise ValueError("Set an RPM greater than zero before running.")
        if self.radio_saved_cases.isChecked():
            conditions = list(project.saved_cases)
            if not conditions:
                raise ValueError(
                    "The project has no saved cases. Choose another "
                    "conditions mode, or store cases in the Run Case tab.")
            missing_rpm = [c.name for c in conditions if not c.rpm]
            if missing_rpm:
                raise ValueError(
                    "Every saved case needs an RPM. Set it on: "
                    + ", ".join(missing_rpm))
            return conditions
        if self.radio_sweep.isChecked():
            axis = self.sweep_axis_combo.currentData()
            start, stop = float(self.sweep_start.value()), float(self.sweep_stop.value())
            count = int(self.sweep_count.value())
            if stop < start:
                raise ValueError("The sweep needs stop >= start.")
            prefix = "mu" if axis == "mu_x" else "theta"
            names = {axis: f"{prefix}={{v:.2f}}"}
            fixed = dict(mu_x=self.mu_x_spin.value(),
                         collective_deg=self.collective_spin.value(),
                         Vz=self.vz_spin.value())
            conditions = []
            for value in np.linspace(start, stop, count):
                name = names[axis].format(v=float(value))
                kwargs = dict(fixed)
                kwargs[axis] = float(value)
                conditions.append(FlightCondition(name=name, rpm=rpm, **kwargs))
            return conditions
        return [FlightCondition(
            name="hover",
            mu_x=self.mu_x_spin.value(),
            collective_deg=self.collective_spin.value(),
            Vz=self.vz_spin.value(),
            rpm=rpm,
        )]

    def _selected_trim(self) -> str:
        """The ``trim`` argument of the next comparison, read from the
        "Thrust matching" combo at run start."""
        return self._TRIM_CHOICES.get(self.trim_combo.currentText(), "none")

    def _update_summary_label(self):
        """States the resulting case count, the variant count and the
        total number of solves the Run button would start."""
        n_variants = max(self.variants_table.rowCount(), 0)
        try:
            n_cases = len(self._selected_conditions())
        except ValueError as exc:
            self.summary_label.setText(str(exc))
            return
        if n_variants == 0:
            self.summary_label.setText(
                "Add at least one geometry row on the Variants page.")
            return
        total = n_variants * n_cases
        mode_name = ("saved cases" if self.radio_saved_cases.isChecked()
                     else "sweep" if self.radio_sweep.isChecked()
                     else "single condition")
        text = (f"{mode_name}: {n_variants} variants × {n_cases} cases = "
                f"{total} solves")
        # A trimmed case bisects its control (~15 engine solves), so the
        # wall-clock estimate is a multiple of the case count. The base
        # row runs untrimmed; this is the rough ceiling.
        if self._selected_trim() != "none":
            text += f" · ≈ {total} solves × ~15 (trim)"
        self.summary_label.setText(text)

    # --- mode reactivity -------------------------------------------------

    def _refresh_mode_labels(self):
        """Rewrites the single-condition rows' symbols for the current
        mode.

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
            set_row_label(self._single_form, field, label)
        axis_key = self.sweep_axis_combo.currentData()
        for index in range(self.sweep_axis_combo.count()):
            key = self.sweep_axis_combo.itemData(index)
            symbol = nomenclature.symbol_text(key, prop)
            self.sweep_axis_combo.setItemText(index, symbol)

    # =====================================================================
    # Page 3 -- run and results
    # =====================================================================

    def _build_run_page(self) -> QWidget:
        page = QWidget()
        vbox = QVBoxLayout(page)

        run_row = QHBoxLayout()
        self.btn_compare_run = QPushButton("Run comparison")
        self.btn_compare_run.setToolTip(
            "Runs the selected conditions on every geometry in the "
            "table. Results stay in memory.")
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

        vbox.addWidget(QLabel("Verdict at the reference condition:"))
        self.verdict_strip = QVBoxLayout()
        verdict_holder = QWidget()
        verdict_holder.setLayout(self.verdict_strip)
        vbox.addWidget(verdict_holder)
        self.guidance_label = QLabel("")
        self.guidance_label.setStyleSheet("color: gray;")
        self.guidance_label.setWordWrap(True)
        vbox.addWidget(self.guidance_label)

        # The two result canvases exist before the rows above them, so
        # the layout can pair the two single-axis figures side by side.
        self.ranking_canvas = CanvasHost()
        self.ranking_canvas.setMinimumHeight(180)
        self.ranking_canvas.show_message(
            "Run a comparison to see the ranking.")
        self.delta_canvas = CanvasHost()
        self.delta_canvas.setMinimumHeight(180)
        self.delta_canvas.show_message(
            "Run a comparison to see the delta view.")
        self.overlay_canvas = CanvasHost()
        self.overlay_canvas.setMinimumHeight(220)
        self.overlay_canvas.show_message(
            "Run a comparison to see the overlay figure.")

        ranking_row = QHBoxLayout()
        ranking_row.addWidget(QLabel("Rank by:"))
        self.ranking_field_combo = QComboBox()
        # Never empty: a dropdown with no options reads as broken, and
        # the first post-construction insertion would otherwise move the
        # index from -1 to 0.
        self.ranking_field_combo.addItem("(none)")
        self.ranking_field_combo.setToolTip(
            "Summary quantity ranked across variants at the reference "
            "condition. The list keeps only the quantities this run "
            "produced.")
        # `activated`, not `currentIndexChanged`: programmatic rebuilds
        # of these lists happen while results are being laid out, and a
        # canvas redraw must not run inside such a change (it crashed
        # the process natively under the offscreen platform). Every
        # programmatic fill redraws explicitly right after it sets the
        # selection; only a USER selection needs to trigger one here.
        self.ranking_field_combo.activated.connect(
            self._on_ranking_selection_changed)
        ranking_row.addWidget(self.ranking_field_combo)

        ranking_row.addWidget(QLabel("Condition:"))
        self.ranking_condition_combo = QComboBox()
        self.ranking_condition_combo.setToolTip(
            "Case whose results the ranking reads. The list holds the "
            "distinct conditions of the last run; the first one ranks "
            "by default.")
        self.ranking_condition_combo.activated.connect(
            self._on_ranking_selection_changed)
        ranking_row.addWidget(self.ranking_condition_combo)
        ranking_row.addStretch(1)
        vbox.addLayout(ranking_row)

        # Ranking and delta side by side: both are single-axis summary
        # figures that read well at half width, and stacking a third
        # canvas would leave nothing of the 1080x700 window for them.
        figures_row = QHBoxLayout()
        figures_row.addWidget(self.ranking_canvas, stretch=1)
        delta_column = QVBoxLayout()
        delta_column.setSpacing(0)
        delta_column.addWidget(QLabel("Delta vs base (%)"))
        delta_column.addWidget(self.delta_canvas, stretch=1)
        figures_row.addLayout(delta_column, stretch=1)
        vbox.addLayout(figures_row, stretch=1)

        vbox.addWidget(self.overlay_canvas, stretch=2)

        export_row = QHBoxLayout()
        self.btn_export_report = QPushButton("Export report")
        self.btn_export_report.setToolTip(
            "Writes a self-contained HTML report with the comparison "
            "figure and the full summary table, in the project outputs "
            "folder.")
        self.btn_export_report.clicked.connect(self._export_comparison_report)
        export_row.addWidget(self.btn_export_report)
        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.setToolTip(
            "Writes one CSV row per geometry and condition, in the "
            "project outputs folder.")
        self.btn_export_csv.clicked.connect(self._export_comparison_csv)
        export_row.addWidget(self.btn_export_csv)
        export_row.addStretch(1)
        vbox.addLayout(export_row)
        return page

    # --- run ---------------------------------------------------------------

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
        try:
            conditions = self._selected_conditions()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid conditions", str(exc))
            return
        total = len(variants) * len(conditions)
        self._set_compare_running(True)
        self.compare_status.setText(f"Running comparison: 0/{total}…")
        self.compare_progress.setRange(0, max(total, 1))
        self.compare_progress.setValue(0)
        worker = CompareWorker(self.state.project, variants, conditions,
                               trim=self._selected_trim())
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
        self._populate_results(results)
        self.compare_status.setText(
            f"Comparison finished: {len(results)} case(s).")

    def _on_compare_failed(self, message: str):
        self._reset_compare_ui()
        self.compare_status.setText("Comparison failed.")
        show_error(self, "Error running comparison", RuntimeError(message))

    def _set_compare_running(self, running: bool):
        self.btn_compare_run.setEnabled(not running)
        self.btn_add_variant.setEnabled(not running)
        self.btn_duplicate_variant.setEnabled(not running)
        self.btn_remove_variant.setEnabled(not running)
        # The trim choice is read once, at run start; changing it while
        # a run is in flight would suggest it still applies.
        self.trim_combo.setEnabled(not running)
        # The ranking reads the results of the LAST run; both of its
        # combos wait until the new run has replaced them.
        self.ranking_field_combo.setEnabled(not running)
        self.ranking_condition_combo.setEnabled(not running)
        self.compare_progress.setVisible(running)
        self.btn_compare_cancel.setVisible(running)
        self.btn_compare_cancel.setEnabled(running)

    def _reset_compare_ui(self):
        self._set_compare_running(False)
        self._compare_thread = None
        self._compare_worker = None

    # --- results reading -----------------------------------------------------

    def _first_result_by_label(self, results: list) -> dict:
        """First result of each geometry, which is its result at the
        reference condition (the first case of the ordered list)."""
        first_by_label: dict[str, object] = {}
        for res in results:
            label = str(res.summary.get("geometry_label")
                        or res.condition_name or "?")
            first_by_label.setdefault(label, res)
        return first_by_label

    def _populate_results(self, results: list):
        """Fills the reasoning views after a finished run."""
        self._populate_verdict(self._first_result_by_label(results))
        self._fill_ranking_combo(results)
        self._fill_ranking_condition_combo(results)
        self._draw_ranking()
        self._draw_delta(results)
        self._draw_overlay(results)

    # --- verdict strip -------------------------------------------------------

    #: Badge definitions: (badge name, direction, candidate keys,
    #: propeller-only). The first key present in the summaries supplies
    #: the values; direction says whether the best value is the maximum
    #: or the minimum. A propeller-only badge applies only when the
    #: summaries carry a truthy ``cfg_is_propeller`` echo: eta_prop is
    #: always computed, but as a ranking goal it means something only
    #: in propeller convention.
    _BADGES = (
        ("best thrust", "max", ("CT", "Thrust"), False),
        ("best figure of merit", "max", ("FM",), False),
        ("best propeller efficiency", "max", ("eta_prop",), True),
        ("lowest power", "min", ("CP", "Power"), False),
    )

    def _populate_verdict(self, first_by_label: dict):
        """One chip per variant, with its best-in-class badges, plus one
        sentence of guidance composed from the winners."""
        while self.verdict_strip.count():
            item = self.verdict_strip.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        propeller_mode = any(bool(res.summary.get("cfg_is_propeller"))
                             for res in first_by_label.values())
        winners: dict[str, str] = {}
        badge_names: dict[str, list[str]] = {label: [] for label in first_by_label}
        for badge, direction, keys, prop_only in self._BADGES:
            if prop_only and not propeller_mode:
                continue
            key = next((k for k in keys
                        if any(k in r.summary for r in first_by_label.values())),
                       None)
            if key is None:
                continue
            pick = max if direction == "max" else min
            best_label, best_value = None, None
            for label, res in first_by_label.items():
                try:
                    value = float(res.summary[key])
                except (TypeError, ValueError, KeyError):
                    continue
                if best_value is None or pick(value, best_value) == value:
                    best_label, best_value = label, value
            if best_label is None:
                continue
            winners[badge] = best_label
            badge_names[best_label].append(badge)
        for label in first_by_label:
            chip = QLabel()
            badges = badge_names[label]
            name = f"<b>{label}</b>" if badges else label
            detail = "<br>" + ", ".join(badges) if badges else ""
            chip.setTextFormat(Qt.TextFormat.RichText)
            chip.setText(name + detail)
            chip.setToolTip(
                "Values read at the reference condition, which is the "
                "first case of the run.")
            self.verdict_strip.addWidget(chip)
        self.guidance_label.setText(self._compose_guidance(winners))

    @staticmethod
    def _compose_guidance(winners: dict[str, str]) -> str:
        """One sentence that names the winner per design goal."""
        parts = []
        if "best thrust" in winners:
            parts.append(f"for thrust pick {winners['best thrust']}")
        if "best figure of merit" in winners:
            parts.append(f"for endurance pick {winners['best figure of merit']}")
        if "best propeller efficiency" in winners:
            parts.append(
                f"in cruise {winners['best propeller efficiency']} "
                "converts power best")
        if "lowest power" in winners:
            parts.append(f"{winners['lowest power']} needs the least power")
        if not parts:
            return ""
        head = parts[0].capitalize()
        tail = "".join(f"; {part}" for part in parts[1:]) + "."
        return head + tail

    # --- ranking -------------------------------------------------------------

    def _fill_ranking_combo(self, results: list):
        """Offers only the ranking quantities this run produced, and
        opens on the mode-appropriate default: eta_prop for a propeller
        run, FM otherwise."""
        current = (self.ranking_field_combo.currentText()
                   if self.ranking_field_combo.count() else "")
        present = [key for key in self._RANKING_FIELDS
                   if any(key in r.summary for r in results)]
        self.ranking_field_combo.blockSignals(True)
        self.ranking_field_combo.clear()
        self.ranking_field_combo.addItem("(none)")
        for key in present:
            self.ranking_field_combo.addItem(key)
        if any(bool(r.summary.get("cfg_is_propeller")) for r in results) \
                and "eta_prop" in present:
            default = "eta_prop"
        elif "FM" in present:
            default = "FM"
        else:
            default = present[0] if present else "(none)"
        index = self.ranking_field_combo.findText(current)
        if index < 0:
            index = self.ranking_field_combo.findText(default)
        self.ranking_field_combo.setCurrentIndex(max(index, 0))
        self.ranking_field_combo.blockSignals(False)

    def _fill_ranking_condition_combo(self, results: list):
        """Lists the distinct condition names of the last run, in
        first-appearance order.

        Results are variant-major and every variant runs the same
        ordered conditions, so position p names the same case in every
        variant; each name carries that position as its data, which is
        exactly the ``ref_index`` the ranking plot expects. The first
        condition stays selected, as before this combo existed."""
        groups: dict = {}
        for res in results:
            label = (res.summary or {}).get("geometry_label")
            if label is None:
                continue
            groups.setdefault(label, []).append(res)
        positions: dict[str, int] = {}
        for idxs in groups.values():
            for position, res in enumerate(idxs):
                name = str(getattr(res, "condition_name", "") or "")
                if name:
                    positions.setdefault(name, position)
        combo = self.ranking_condition_combo
        combo.blockSignals(True)
        combo.clear()
        for name, position in positions.items():
            combo.addItem(name, userData=position)
        if combo.count():
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _on_ranking_selection_changed(self):
        """Redraws every view that follows the ranking selections."""
        self._draw_ranking()
        self._draw_delta(self._comparison_results)

    def _draw_ranking(self):
        """Draws the horizontal bar ranking at the chosen condition."""
        field = self.ranking_field_combo.currentText()
        canvas = self.ranking_canvas.use_simple()
        canvas.clear()
        if not self._comparison_results or field in ("", "(none)"):
            self.ranking_canvas.show_message(
                "Run a comparison to see the ranking.")
            return
        ref_index = self.ranking_condition_combo.currentData()
        try:
            plots.plot_geometry_ranking(
                self._comparison_results, field, ax=canvas.ax,
                ref_index=int(ref_index) if ref_index is not None else 0)
        except Exception as exc:
            canvas.ax.text(0.5, 0.5, f"Could not draw the ranking: {exc}",
                           ha="center", va="center",
                           transform=canvas.ax.transAxes, wrap=True)
        canvas.draw()

    def _draw_delta(self, results):
        """Draws every variant's percent change against the base
        planform, for the selected metric."""
        field = self.ranking_field_combo.currentText()
        canvas = self.delta_canvas.use_simple()
        canvas.clear()
        if not results or field in ("", "(none)"):
            self.delta_canvas.show_message(
                "Run a comparison to see the delta view.")
            return
        try:
            plots.plot_geometry_delta(results, field, ax=canvas.ax)
        except Exception as exc:
            canvas.ax.text(0.5, 0.5,
                           f"Could not draw the delta view: {exc}",
                           ha="center", va="center",
                           transform=canvas.ax.transAxes, wrap=True)
        canvas.draw()

    # --- overlay ---------------------------------------------------------------

    def _draw_overlay(self, results: list):
        """Full multi-panel overlay figure, one curve per geometry."""
        available = [key for key in self._OVERLAY_FIELDS
                     if any(key in r.summary for r in results)]
        try:
            axes = plots.plot_geometry_comparison(
                results, fields=tuple(available) or None)
            axes_list = np.atleast_1d(axes)
            self.overlay_canvas.show_figure(axes_list[0].figure)
        except Exception as exc:
            self.overlay_canvas.show_message(
                f"Could not draw the comparison figure: {exc}")

    # --- exports ---------------------------------------------------------------

    def _export_destination(self, suffix: str) -> str:
        """Timestamped path inside the project outputs folder. The
        timestamp keeps an existing report from being overwritten
        silently."""
        project = self.state.project
        start_dir = Path(api.project_outputs_dir(project, create=True)) \
            if project is not None and project.path else Path("outputs")
        stamp = time.strftime("%Y%m%d_%H%M%S")
        return str(start_dir / f"geometry_comparison_{stamp}{suffix}")

    def _export_comparison_report(self):
        if not self._comparison_results:
            QMessageBox.warning(self, "Nothing to export",
                                "Run a comparison first.")
            return
        path = self._export_destination(".html")
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
        path = self._export_destination(".csv")
        try:
            dest = api.export_comparison_csv(self._comparison_results, path)
        except Exception as exc:
            show_error(self, "Error exporting CSV", exc)
            return
        QMessageBox.information(self, "Exported", f"CSV written to {dest}")

    # =====================================================================
    # Project reactivity
    # =====================================================================

    def _on_project_changed(self):
        """Rebuilds what depends on the project: the variant table, the
        saved-case count and the mode labels. Results of the previous
        project are dropped first."""
        if self._refreshing_from_project:
            return
        self._refreshing_from_project = True
        try:
            self._comparison_results = None
            # A "Replace base" import belongs to the project it was
            # made from: another project drops it.
            self._base_override = None
            self._imported_base_name = ""
            while self.verdict_strip.count():
                item = self.verdict_strip.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self.guidance_label.setText("")
            self.compare_status.setText("")
            self.ranking_field_combo.blockSignals(True)
            self.ranking_field_combo.clear()
            self.ranking_field_combo.blockSignals(False)
            self.ranking_condition_combo.blockSignals(True)
            self.ranking_condition_combo.clear()
            self.ranking_condition_combo.blockSignals(False)
            self.ranking_canvas.show_message(
                "Run a comparison to see the ranking.")
            self.delta_canvas.show_message(
                "Run a comparison to see the delta view.")
            self.overlay_canvas.show_message(
                "Run a comparison to see the overlay figure.")

            self._seed_variant_rows()
            self._refresh_mode_labels()
            self._reset_generate_defaults()
            self._update_saved_count_label()
            self._update_summary_label()
            self._draw_preview()
        finally:
            self._refreshing_from_project = False

    def _update_saved_count_label(self):
        project = self.state.project
        count = len(project.saved_cases) if project is not None else 0
        if count:
            self.saved_count_label.setText(f"{count} saved case(s)")
        else:
            self.saved_count_label.setText("none stored in the project")

    def showEvent(self, event):
        """Equalizes the width of each button group on the FIRST display.

        Only after the stylesheet's polish does a button's ``sizeHint``
        include the theme's padding (see
        ``common.equalize_button_widths``)."""
        super().showEvent(event)
        if getattr(self, "_widths_reviewed", False):
            return
        self._widths_reviewed = True
        equalize_button_widths((self.btn_add_variant,
                                self.btn_duplicate_variant,
                                self.btn_remove_variant))
        equalize_button_widths((self.btn_build_sweep,
                                self.btn_add_generated,
                                self.btn_import_project))
        equalize_button_widths((self.btn_export_report, self.btn_export_csv))


if __name__ == "__main__":   # pragma: no cover
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    state = AppState()
    window = GeometryDesignerWindow(state)
    window.show()
    sys.exit(app.exec())
