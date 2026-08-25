"""Implement the Geometry GUI tab.

The tab accepts global blade dimensions and spanwise chord, twist, and radial
stations. It displays and edits the authoritative radial table and can fill it from
a parametric generator. Outputs are validated geometry definitions and preview
figures; project persistence crosses the application boundary. The tab does not
select airfoil polars or execute BEMT.
"""

from __future__ import annotations

import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QPushButton,
    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QScrollArea, QSplitter, QHeaderView, QDialog, QCheckBox, QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from ... import geometry
from ...models import BladeDynamicsDef
from ...viz import plots
from ...nomenclature import to_html as symbol_html

from ..common import AppState, CanvasHost, set_row_visible
from ..dialogs import GeometryGeneratorDialog
from ..widgets import ScientificSpinBox


def _sym(latex: str) -> str:
    """Rendered HTML symbol for a label (PR-4: never a plain-text name)."""
    return symbol_html(latex)


class GeometryTab(QWidget):
    """Geometry = radial table (r/R, chord, twist). The parametric
    generator is just a convenience to fill it (popup); number of
    blades and radius are constants always visible, outside the popup
    (docs/plano.md Section 3).

    Embedded canvas (docs/plano_v3.md Part 6.1): same rationale as the
    Airfoil tab (Part 5): a horizontal `QSplitter`, form on the left,
    "Top View" and "Chord/Twist" preview on the right, always visible,
    live with a debounce of about 300 ms. Replaces the old "Geometry"
    mode of ResultsTab, removed in this Part."""

    dirty_changed = pyqtSignal(bool)   # asterisk for "not saved to disk" (same mechanism as config.py/airfoil.py)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._dirty = False
        # True while this tab is writing its own edit back into
        # `state.project.geometry`. That prevents `_refresh_from_project`
        # (connected to `geometry_changed`, which the write itself
        # triggers) from rebuilding the table from what just came out of
        # it and clearing the asterisk before the user saves to disk.
        self._applying_locally = False

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._refresh_preview)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        scroll.setWidget(left_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(self._build_preview_panel())
        # All extra space goes to the CANVAS (stretch 0 x 1), not to the
        # form: the window opens maximized (`app.main` calls
        # showMaximized), and with the form growing along with it a wide
        # screen turned into half an empty field panel and a squeezed
        # plot. `setSizes` fixes only the INITIAL width of each side.
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([460, 900])
        outer = QVBoxLayout(self)
        outer.addWidget(splitter)

        const_box = QGroupBox("Global Geometry")
        const_form = QFormLayout(const_box)
        self.n_blades = QSpinBox(); self.n_blades.setRange(1, 12); self.n_blades.setValue(2)
        self.n_blades.setToolTip('"n_blades"<br><br>Number of blades in the rotor or propeller.')
        self.radius_m = QDoubleSpinBox(); self.radius_m.setRange(0.01, 100); self.radius_m.setValue(1.0)
        self.radius_m.setSingleStep(0.1)
        self.radius_m.setToolTip('"radius_m"<br><br>Rotor or propeller radius in metres.<br><br>Chord values in the table are normalized by this radius.')
        const_form.addRow("Number of Blades:", self.n_blades)
        const_form.addRow("Rotor Radius [m]:", self.radius_m)
        self.n_blades.valueChanged.connect(self._apply_constants)
        self.radius_m.valueChanged.connect(self._apply_constants)
        layout.addWidget(const_box)

        layout.addWidget(self._build_dynamics_box())

        btn_gen = QPushButton("Generate Table…")
        btn_gen.setToolTip(
            "Generate the radial blade table from a parametric chord distribution.<br><br>"
            "The available shapes are rectangular, tapered, and elliptical.")
        btn_gen.clicked.connect(self._open_generator)
        layout.addWidget(btn_gen)

        table_box = QGroupBox("Radial Distribution Table")
        tbox_layout = QVBoxLayout(table_box)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["r/R", "chord c/R", "twist [deg]"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._schedule_preview_refresh)
        self.table.itemChanged.connect(self._apply_table_edits)
        tbox_layout.addWidget(self.table)
        layout.addWidget(table_box, stretch=1)

        save_row = QHBoxLayout()
        # One-word labels, see the same change in `tabs/config.py`.
        btn_save = QPushButton("Save")
        btn_save.setToolTip("Save the current geometry and project settings to disk.")
        btn_save.clicked.connect(self._save_project)
        save_row.addWidget(btn_save)
        btn_restore = QPushButton("Restore")
        btn_restore.setToolTip("Discard unsaved geometry changes and reload the project from disk.")
        btn_restore.clicked.connect(self._restore_project)
        save_row.addWidget(btn_restore)
        # The slack goes to the end of the row, not to the buttons (see
        # `tests/test_gui_layout.py`: without this they stretch to the
        # QSS width ceiling, and `setSizePolicy(Fixed)` doesn't hold).
        save_row.addStretch(1)
        layout.addLayout(save_row)

        self.state.geometry_changed.connect(self._refresh_from_project)
        self._refresh_preview()

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_tabs = QTabWidget()
        self.planform_canvas = CanvasHost()
        self.chord_twist_canvas = CanvasHost()
        self.rotor_3d_canvas = CanvasHost()
        self.preview_tabs.addTab(self.planform_canvas, "Plan View")
        self.preview_tabs.addTab(self.chord_twist_canvas, "Chord/Twist")
        self.preview_tabs.addTab(self.rotor_3d_canvas, "Rotor 3D")
        self.preview_tabs.currentChanged.connect(lambda _i: self._refresh_preview())
        panel_layout.addWidget(self.preview_tabs, stretch=1)
        return panel

    #: Flap-model combo text -> the value stored in
    #: ``RotorGeometryDef.flap_model``.
    _FLAP_MODES = [
        ("Rigid", "rigid"),
        ("Hinge offset", "offset"),
        ("Root spring", "spring"),
        ("Offset and spring", "offset_spring"),
    ]
    _INERTIA_SOURCES = [
        ("Lock number", "lock"),
        ("Flap inertia", "inertia"),
        ("Blade mass", "blade_mass"),
    ]

    def _build_dynamics_box(self) -> QGroupBox:
        """The 'Blade dynamics' group (SC-11): rigid-body flap and
        lead-lag freedoms. Progressive disclosure via
        `set_row_visible` only (PR-2); every label carries a rendered
        symbol (PR-4)."""
        box = QGroupBox("Blade Dynamics")
        row = QHBoxLayout(box)
        form = QFormLayout()
        self._dynamics_form = form

        def _tip(field: str, body: str) -> str:
            # The `"dotted.field"` head is how the help system resolves
            # the field; keep it first in every tooltip.
            return f'"geometry.dynamics.{field}"<br><br>{body}'

        self.dyn_flap_model = self._make_combo(self._FLAP_MODES)
        self.dyn_flap_model.setToolTip(_tip("flap_model",
            "How much flap freedom the rigid blade has: a plain rigid disk, "
            "a hinge offset e from the shaft, a root spring, or both "
            "together. Rigid keeps the behavior of every project saved "
            "before this model existed."))
        form.addRow("Flap model:", self.dyn_flap_model)

        self.dyn_hinge_offset = QDoubleSpinBox()
        self.dyn_hinge_offset.setRange(0.0, 0.3)
        self.dyn_hinge_offset.setDecimals(3)
        self.dyn_hinge_offset.setSingleStep(0.01)
        self.dyn_hinge_offset.setToolTip(_tip("hinge_offset_norm",
            "Flap hinge offset as a fraction of the rotor radius. It "
            "raises the flap frequency ratio by (3/2)·e/(1−e) above 1 and "
            "lets part of the blade load reach the hub as a structural "
            "moment."))
        form.addRow(_sym(r"\bar{e") + " — Hinge offset [r/R]:",
                    self.dyn_hinge_offset)

        self.dyn_flap_spring = ScientificSpinBox()
        self.dyn_flap_spring.setRange(0.0, 1e9)
        self.dyn_flap_spring.setDecimals(4)
        self.dyn_flap_spring.setToolTip(_tip("flap_spring_nm_per_rad",
            "Stiffness of a spring restraining the flap hinge, in newton "
            "metres per radian. It adds K/(I·Ω²) to the square of the flap "
            "frequency ratio."))
        form.addRow(_sym(r"K_\beta") + " — Flap spring [N·m/rad]:",
                    self.dyn_flap_spring)

        self.dyn_inertia_source = self._make_combo(self._INERTIA_SOURCES)
        self.dyn_inertia_source.setToolTip(_tip("inertia_source",
            "Where the flap inertia comes from: converted back from a Lock "
            "number with the airfoil's lift-curve slope and the chord at "
            "r/R = 0.75, given directly, or estimated from a uniform blade "
            "mass over the flapping part."))
        form.addRow("Inertia from:", self.dyn_inertia_source)

        self.dyn_lock_number = QDoubleSpinBox()
        self.dyn_lock_number.setRange(1.0, 20.0)
        self.dyn_lock_number.setDecimals(2)
        self.dyn_lock_number.setValue(8.0)
        self.dyn_lock_number.setToolTip(_tip("lock_number",
            "Lock number of the blade: ratio between aerodynamic and "
            "inertial response. Typical rotors sit between 5 and 12. Used "
            "when the inertia source is the Lock number."))
        form.addRow(_sym(r"\gamma") + " — Lock number:",
                    self.dyn_lock_number)

        self.dyn_flap_inertia = ScientificSpinBox()
        self.dyn_flap_inertia.setRange(1e-6, 1e6)
        self.dyn_flap_inertia.setDecimals(6)
        self.dyn_flap_inertia.setToolTip(_tip("flap_inertia_kg_m2",
            "Flap inertia of one blade about its hinge, in kilogram metres "
            "squared. Used when the inertia source is the direct value."))
        form.addRow(_sym(r"I_\beta") + " — Flap inertia [kg·m²]:",
                    self.dyn_flap_inertia)

        self.dyn_blade_mass = QDoubleSpinBox()
        self.dyn_blade_mass.setRange(1e-3, 1e4)
        self.dyn_blade_mass.setDecimals(3)
        self.dyn_blade_mass.setToolTip(_tip("blade_mass_kg",
            "Mass of one blade in kilograms, treated as uniform over the "
            "flapping part: I = m·(R−eR)²/3. Used when the inertia source "
            "is the blade mass."))
        form.addRow(_sym(r"m_b") + " — Blade mass [kg]:",
                    self.dyn_blade_mass)

        self.dyn_delta3 = QDoubleSpinBox()
        self.dyn_delta3.setRange(-60.0, 60.0)
        self.dyn_delta3.setDecimals(2)
        self.dyn_delta3.setToolTip(_tip("pitch_flap_coupling_deg",
            "The \u03b4\u2083 hinge: kinematic pitch-flap coupling. An upward "
            "flapping angle reduces the local pitch by tan(\u03b4\u2083)\u00b7\u03b2, "
            "which stabilizes the flap response."))
        form.addRow(_sym(r"\delta_3") + " — Pitch-flap coupling [deg]:",
                    self.dyn_delta3)

        self.dyn_harmonics = QSpinBox()
        self.dyn_harmonics.setRange(1, 5)
        self.dyn_harmonics.setValue(2)
        self.dyn_harmonics.setToolTip(_tip("harmonics",
            "Number of harmonics kept in the harmonic balance of the flap "
            "(and lag) response. Two usually suffices; more cost one solve "
            "each per iteration."))
        form.addRow(_sym(r"N_h") + " — Harmonics:", self.dyn_harmonics)

        self.dyn_lag_enabled = QCheckBox("Enable lead-lag freedom")
        self.dyn_lag_enabled.setToolTip(_tip("lag_enabled",
            "Adds a lag hinge at the same offset, with its own spring, "
            "damper and inertia. The lag moment comes from the tangential "
            "force distribution."))
        form.addRow(self.dyn_lag_enabled)

        self.dyn_lag_spring = ScientificSpinBox()
        self.dyn_lag_spring.setRange(0.0, 1e9)
        self.dyn_lag_spring.setDecimals(4)
        self.dyn_lag_spring.setToolTip(_tip("lag_spring_nm_per_rad",
            "Stiffness of the lag root spring, in newton metres per radian. "
            "It is what keeps the lag angle defined on a rotor without a "
            "lag hinge offset."))
        form.addRow(_sym(r"K_\zeta") + " — Lag spring [N·m/rad]:",
                    self.dyn_lag_spring)

        self.dyn_lag_damping = ScientificSpinBox()
        self.dyn_lag_damping.setRange(0.0, 1e9)
        self.dyn_lag_damping.setDecimals(4)
        self.dyn_lag_damping.setToolTip(_tip("lag_damping_nms_per_rad",
            "Damping of the lag freedom, in newton metre seconds per "
            "radian. Real rotors carry a lag damper to keep the lag motion "
            "stable."))
        form.addRow(_sym(r"C_\zeta") + " — Lag damping [N·m·s/rad]:",
                    self.dyn_lag_damping)

        self.dyn_lag_inertia = ScientificSpinBox()
        self.dyn_lag_inertia.setRange(1e-6, 1e6)
        self.dyn_lag_inertia.setDecimals(6)
        self.dyn_lag_inertia.setToolTip(_tip("lag_inertia_kg_m2",
            "Inertia of one blade about the lag hinge, in kilogram metres "
            "squared. Required when lead-lag is enabled."))
        form.addRow(_sym(r"I_\zeta") + " — Lag inertia [kg·m²]:",
                    self.dyn_lag_inertia)

        self.dyn_lag_feeds_back = QCheckBox(
            "Feed the lag rate into the in-plane speed")
        self.dyn_lag_feeds_back.setChecked(True)
        self.dyn_lag_feeds_back.setToolTip(_tip("lag_feeds_back",
            "When on, the lag rate modifies the tangential flow speed of "
            "each element, closing the coupling between lag motion and "
            "aerodynamics."))
        form.addRow(self.dyn_lag_feeds_back)

        self.dyn_outer_iter = QSpinBox()
        self.dyn_outer_iter.setRange(5, 200)
        self.dyn_outer_iter.setValue(30)
        self.dyn_outer_iter.setToolTip(_tip("outer_max_iter",
            "Maximum number of outer iterations that exchange the inflow "
            "solution with the flap/lag response until both agree."))
        form.addRow("Outer iterations:", self.dyn_outer_iter)

        self.dyn_outer_tol = ScientificSpinBox()
        self.dyn_outer_tol.setRange(1e-8, 1e-1)
        self.dyn_outer_tol.setDecimals(8)
        self.dyn_outer_tol.setValue(1e-4)
        self.dyn_outer_tol.setToolTip(_tip("outer_tol_deg",
            "Convergence tolerance of the outer loop, in degrees of flap "
            "coefficient change. The run stops earlier when it is met."))
        form.addRow("Outer tolerance [deg]:", self.dyn_outer_tol)

        self.dyn_outer_relax = QDoubleSpinBox()
        self.dyn_outer_relax.setRange(0.05, 1.0)
        self.dyn_outer_relax.setDecimals(2)
        self.dyn_outer_relax.setSingleStep(0.05)
        self.dyn_outer_relax.setValue(0.5)
        self.dyn_outer_relax.setToolTip(_tip("outer_relax",
            "Relaxation factor of the outer loop: fraction of each solved "
            "correction applied per iteration. Lower it if the iteration "
            "oscillates."))
        form.addRow("Outer relaxation:", self.dyn_outer_relax)

        row.addLayout(form, 1)

        # --- live readout panel --------------------------------------
        readout_form = QFormLayout()
        self.dyn_out_ratio = QLabel("—")
        self.dyn_out_ratio.setToolTip(
            "Flap frequency ratio and its square, from the current inputs.")
        self.dyn_out_inertia = QLabel("—")
        self.dyn_out_inertia.setToolTip(
            "Resolved flap inertia and Lock number: whichever of the two "
            "the user did not enter directly.")
        self.dyn_out_lag = QLabel("—")
        self.dyn_out_lag.setToolTip(
            "Lead-lag frequency ratio, when lead-lag is enabled.")
        self.dyn_out_freq = QLabel("—")
        self.dyn_out_freq.setToolTip(
            "First flap natural frequency in hertz: frequency ratio times "
            "the rotation speed over 2π, using the RPM of the first saved "
            "case of this project.")
        readout_form.addRow(
            "<b>" + _sym(r"\nu_\beta") + "</b> / "
            + _sym(r"\nu_\beta^2") + ":", self.dyn_out_ratio)
        readout_form.addRow(
            "<b>" + _sym(r"I_\beta") + "</b> / "
            + _sym(r"\gamma") + ":", self.dyn_out_inertia)
        readout_form.addRow(
            "<b>" + _sym(r"\nu_\zeta") + ":</b>", self.dyn_out_lag)
        readout_form.addRow(
            "<b>" + _sym(r"f_1") + " [Hz]:</b>", self.dyn_out_freq)
        note = QLabel("<i>Readouts update as you edit.</i>")
        note.setToolTip(
            "The panel recomputes on every edit, with the same short delay "
            "as the preview drawing.")
        readout_form.addRow(note)
        row.addLayout(readout_form, 0)

        # --- progressive disclosure + write-back ---------------------
        for combo in (self.dyn_flap_model, self.dyn_inertia_source):
            combo.currentIndexChanged.connect(self._apply_dynamics)
        for cb in (self.dyn_lag_enabled, self.dyn_lag_feeds_back):
            cb.toggled.connect(self._apply_dynamics)
        for w in (self.dyn_hinge_offset, self.dyn_lock_number,
                  self.dyn_blade_mass, self.dyn_delta3,
                  self.dyn_outer_relax, self.dyn_flap_spring,
                  self.dyn_flap_inertia, self.dyn_lag_spring,
                  self.dyn_lag_damping, self.dyn_lag_inertia,
                  self.dyn_outer_tol, self.dyn_harmonics,
                  self.dyn_outer_iter):
            w.valueChanged.connect(self._apply_dynamics)

        self._refresh_dynamics_visibility()
        return box

    def _make_combo(self, pairs):
        """Combo box whose items carry (text, stored value)."""
        from PyQt6.QtWidgets import QComboBox
        combo = QComboBox()
        for text, _value in pairs:
            combo.addItem(text)
        combo.setCurrentIndex(0)
        return combo

    def _make_combo(self, pairs):
        """Combo box whose items carry (text, stored value)."""
        from PyQt6.QtWidgets import QComboBox
        combo = QComboBox()
        for text, _value in pairs:
            combo.addItem(text)
        combo.setCurrentIndex(0)
        return combo

    def _combo_value(self, combo, pairs):
        return pairs[combo.currentIndex()][1]

    def _set_combo_by_value(self, combo, pairs, value):
        for index, (_text, stored) in enumerate(pairs):
            if stored == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _collect_dynamics(self) -> BladeDynamicsDef:
        return BladeDynamicsDef(
            flap_model=self._combo_value(self.dyn_flap_model, self._FLAP_MODES),
            hinge_offset_norm=self.dyn_hinge_offset.value(),
            flap_spring_nm_per_rad=self.dyn_flap_spring.value(),
            inertia_source=self._combo_value(self.dyn_inertia_source,
                                              self._INERTIA_SOURCES),
            lock_number=self.dyn_lock_number.value(),
            flap_inertia_kg_m2=self.dyn_flap_inertia.value(),
            blade_mass_kg=self.dyn_blade_mass.value(),
            pitch_flap_coupling_deg=self.dyn_delta3.value(),
            harmonics=self.dyn_harmonics.value(),
            outer_max_iter=self.dyn_outer_iter.value(),
            outer_tol_deg=self.dyn_outer_tol.value(),
            outer_relax=self.dyn_outer_relax.value(),
            lag_enabled=self.dyn_lag_enabled.isChecked(),
            lag_spring_nm_per_rad=self.dyn_lag_spring.value(),
            lag_damping_nms_per_rad=self.dyn_lag_damping.value(),
            lag_inertia_kg_m2=self.dyn_lag_inertia.value(),
            lag_feeds_back=self.dyn_lag_feeds_back.isChecked(),
        )

    def _apply_dynamics(self, *_args):
        """Writes the group's controls into the project's dynamics."""
        self._refresh_dynamics_visibility()
        self._schedule_preview_refresh()
        if self.state.project is None:
            return
        self._mark_dirty()
        self.state.project.geometry.dynamics = self._collect_dynamics()

    def _refresh_dynamics_visibility(self):
        """Progressive disclosure (PR-2): fields that cannot apply to the
        current configuration hide; real-but-blocked ones stay disabled.
        Here each field either applies or hides — nothing is blocked."""
        model = self._combo_value(self.dyn_flap_model, self._FLAP_MODES)
        uses_offset = model in ("offset", "offset_spring")
        uses_spring = model in ("spring", "offset_spring")
        flapping = model != "rigid"
        source = self._combo_value(self.dyn_inertia_source,
                                    self._INERTIA_SOURCES)
        set_row_visible(self._dynamics_form, self.dyn_hinge_offset,
                        uses_offset)
        set_row_visible(self._dynamics_form, self.dyn_flap_spring,
                        uses_spring)
        set_row_visible(self._dynamics_form, self.dyn_inertia_source, flapping)
        set_row_visible(self._dynamics_form, self.dyn_lock_number,
                        flapping and source == "lock")
        set_row_visible(self._dynamics_form, self.dyn_flap_inertia,
                        flapping and source == "inertia")
        set_row_visible(self._dynamics_form, self.dyn_blade_mass,
                        flapping and source == "blade_mass")
        set_row_visible(self._dynamics_form, self.dyn_delta3, flapping)
        set_row_visible(self._dynamics_form, self.dyn_harmonics, flapping)
        set_row_visible(self._dynamics_form, self.dyn_lag_enabled, flapping)
        lag = flapping and self.dyn_lag_enabled.isChecked()
        for w in (self.dyn_lag_spring, self.dyn_lag_damping,
                  self.dyn_lag_inertia, self.dyn_lag_feeds_back):
            set_row_visible(self._dynamics_form, w, lag)
        set_row_visible(self._dynamics_form, self.dyn_outer_iter, flapping)
        set_row_visible(self._dynamics_form, self.dyn_outer_tol, flapping)
        set_row_visible(self._dynamics_form, self.dyn_outer_relax, flapping)

    def _refresh_dynamics_readout(self):
        """Recomputes the read-only panel beside the inputs (same debounce
        as the preview drawing)."""
        import math
        dyn = self._collect_dynamics()
        geom_now = self.state.project.geometry if self.state.project else None
        radius = geom_now.radius_m if geom_now else self.radius_m.value()
        rho = float(self.state.project.config.get("rho", 1.225)) \
            if self.state.project else 1.225
        cl_alpha = float(getattr(
            getattr(self.state.project, "airfoil", None), "cl_alpha", 2 * math.pi)) \
            if self.state.project else 2 * math.pi
        try:
            chord_ref = geometry.reference_chord_m(geom_now) if geom_now else \
                self.radius_m.value() * 0.08
            inertia = geometry.resolve_flap_inertia(
                inertia_source=dyn.inertia_source,
                lock_number=dyn.lock_number,
                flap_inertia_kg_m2=dyn.flap_inertia_kg_m2,
                blade_mass_kg=dyn.blade_mass_kg,
                hinge_offset_norm=dyn.hinge_offset_norm,
                radius_m=radius, chord_ref_m=chord_ref,
                rho=rho, cl_alpha=cl_alpha)
        except Exception:
            inertia = float("nan")

        red = '<span style="color:#c00;">%s</span>'
        rpm = None
        if self.state.project and self.state.project.saved_cases:
            rpm = self.state.project.saved_cases[0].rpm

        if dyn.flap_model == "rigid":
            self.dyn_out_ratio.setText("— (rigid)")
            self.dyn_out_inertia.setText("—")
            self.dyn_out_lag.setText("—")
            self.dyn_out_freq.setText("—")
            return

        gamma_resolved = (rho * cl_alpha * chord_ref * radius ** 4 / inertia
                          if np.isfinite(inertia) and inertia > 0 else float("nan"))
        if dyn.inertia_source == "lock":
            self.dyn_out_inertia.setText(
                f"{inertia:.4g} kg·m²" if np.isfinite(inertia) and inertia > 0
                else red % "invalid γ or chord table")
        else:
            self.dyn_out_inertia.setText(
                f"{inertia:.4g} kg·m² · γ {gamma_resolved:.3g}"
                if np.isfinite(gamma_resolved) and gamma_resolved > 0
                else red % "invalid I")

        if not rpm:
            self.dyn_out_ratio.setText("— (no saved case: no RPM)")
            self.dyn_out_lag.setText("—")
            self.dyn_out_freq.setText("— (save a case first)")
            return
        omega = 2.0 * math.pi * float(rpm) / 60.0
        nu2 = geometry.flap_frequency_ratio_squared(
            dyn.hinge_offset_norm, max(dyn.flap_spring_nm_per_rad, 0.0),
            inertia, omega)
        nu = math.sqrt(max(nu2, 0.0))
        resonant = any(abs(nu2 - n * n) < 1e-3
                       for n in range(1, dyn.harmonics + 1))
        ratio_text = f"{nu:.4f} / {nu2:.4f}"
        self.dyn_out_ratio.setText(red % ratio_text if resonant else ratio_text)
        self.dyn_out_freq.setText(f"{nu * omega / (2.0 * math.pi):.2f}")
        if dyn.lag_enabled:
            nz2 = geometry.lag_frequency_ratio_squared(
                dyn.hinge_offset_norm, max(dyn.lag_spring_nm_per_rad, 0.0),
                dyn.lag_inertia_kg_m2, omega)
            self.dyn_out_lag.setText(
                f"{math.sqrt(max(nz2, 0.0)):.4f} / {nz2:.4f}")
        else:
            self.dyn_out_lag.setText("—")

    def _schedule_preview_refresh(self, *_args):
        if hasattr(self, "_preview_timer"):
            self._preview_timer.start()

    def _mark_dirty(self, *_args):
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)

    def _clear_dirty(self):
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)

    def _current_geometry(self):
        """Geometry to draw in the preview: reflects the table/constants
        exactly as they are in the form RIGHT NOW, even before "Apply
        table edits". This is the whole reason the live canvas exists
        (see the same principle in Part 5, `_collect_airfoil_def`)."""
        r, c, t = [], [], []
        for i in range(self.table.rowCount()):
            item_r, item_c, item_t = self.table.item(i, 0), self.table.item(i, 1), self.table.item(i, 2)
            if item_r is None or item_c is None or item_t is None:
                continue
            r.append(float(item_r.text())); c.append(float(item_c.text())); t.append(float(item_t.text()))
        if len(r) < 2:
            if self.state.project is not None:
                return self.state.project.geometry
            return None
        airfoil_name = self.state.project.geometry.airfoil_name if self.state.project else ""
        return geometry.generate_custom(r, c, t, radius_m=self.radius_m.value(),
                                          n_blades=self.n_blades.value(), airfoil_name=airfoil_name)

    def _refresh_preview(self):
        if not hasattr(self, "preview_tabs"):
            return
        self._refresh_dynamics_readout()
        try:
            geom = self._current_geometry()
        except Exception as exc:
            self.planform_canvas.show_message(f"Error reading geometry: {exc}")
            return
        if geom is None:
            self.planform_canvas.show_message("No project/geometry yet.")
            self.chord_twist_canvas.show_message("No project/geometry yet.")
            self.rotor_3d_canvas.show_message("No project/geometry yet.")
            return
        if self.preview_tabs.currentIndex() == 0:
            canvas = self.planform_canvas.use_simple()
            canvas.clear()
            try:
                plots.plot_planform(geom, ax=canvas.ax)
            except Exception as exc:
                canvas.clear()
                canvas.ax.text(0.5, 0.5, f"Error drawing planform: {exc}", ha="center",
                                va="center", wrap=True, transform=canvas.ax.transAxes)
            canvas.draw()
        elif self.preview_tabs.currentIndex() == 1:
            canvas = self.chord_twist_canvas.use_simple()
            canvas.clear()
            try:
                plots.plot_chord_twist_distribution(geom, ax=canvas.ax)
            except Exception as exc:
                canvas.clear()
                canvas.ax.text(0.5, 0.5, f"Error drawing chord/twist: {exc}", ha="center",
                                va="center", wrap=True, transform=canvas.ax.transAxes)
            canvas.draw()
        else:
            canvas = self.rotor_3d_canvas.use_simple()
            canvas.fig.clear()
            canvas.ax = canvas.fig.add_subplot(111, projection="3d")
            try:
                plots.plot_rotor_3d(geom, ax=canvas.ax)
            except Exception as exc:
                canvas.clear()
                canvas.ax.text(0.5, 0.5, f"Error drawing rotor: {exc}", ha="center",
                               va="center", wrap=True, transform=canvas.ax.transAxes)
            canvas.draw()

    def _open_generator(self):
        airfoil_name = self.state.project.airfoil.name if self.state.project else ""
        dlg = GeometryGeneratorDialog(self, self.n_blades.value(), self.radius_m.value(), airfoil_name)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.generated_geom is not None:
            if self.state.project is not None:
                self.state.project.geometry = dlg.generated_geom
                # Round-trip from item 2: number of blades and radius
                # are now EDITABLE inside the popup, so the "Global
                # Geometry" box here has to start showing what was
                # actually generated. Otherwise the two places diverge
                # and the next `_apply_table_edits` would overwrite the
                # geometry with this tab's stale values.
                self._sync_constants_from_geometry(dlg.generated_geom)
                self._mark_dirty()
                self.state.notify_geometry()
            else:
                QMessageBox.warning(self, "No Project", "Create or open a project first.")

    def _sync_constants_from_geometry(self, geom):
        """Mirrors `n_blades`/`radius_m` from the geometry into the
        spinboxes, without triggering `_apply_constants` (which would
        overwrite the geometry that just arrived)."""
        self.n_blades.blockSignals(True)
        self.radius_m.blockSignals(True)
        self.n_blades.setValue(int(geom.n_blades))
        self.radius_m.setValue(float(geom.radius_m))
        self.n_blades.blockSignals(False)
        self.radius_m.blockSignals(False)

    def _sync_dynamics_from_project(self, dyn):
        """Mirrors the project's dynamics block into the group's controls,
        without triggering `_apply_dynamics`."""
        widgets = (self.dyn_flap_model, self.dyn_inertia_source,
                   self.dyn_hinge_offset, self.dyn_flap_spring,
                   self.dyn_lock_number, self.dyn_flap_inertia,
                   self.dyn_blade_mass, self.dyn_delta3, self.dyn_harmonics,
                   self.dyn_outer_iter, self.dyn_outer_tol,
                   self.dyn_outer_relax, self.dyn_lag_spring,
                   self.dyn_lag_damping, self.dyn_lag_inertia)
        for w in widgets:
            w.blockSignals(True)
        for cb in (self.dyn_lag_enabled, self.dyn_lag_feeds_back):
            cb.blockSignals(True)
        try:
            self._set_combo_by_value(self.dyn_flap_model, self._FLAP_MODES,
                                      dyn.flap_model)
            self._set_combo_by_value(self.dyn_inertia_source,
                                      self._INERTIA_SOURCES,
                                      dyn.inertia_source)
            self.dyn_hinge_offset.setValue(float(dyn.hinge_offset_norm))
            self.dyn_flap_spring.setValue(float(dyn.flap_spring_nm_per_rad))
            self.dyn_lock_number.setValue(float(dyn.lock_number))
            self.dyn_flap_inertia.setValue(float(dyn.flap_inertia_kg_m2))
            self.dyn_blade_mass.setValue(float(dyn.blade_mass_kg))
            self.dyn_delta3.setValue(float(dyn.pitch_flap_coupling_deg))
            self.dyn_harmonics.setValue(int(dyn.harmonics))
            self.dyn_outer_iter.setValue(int(dyn.outer_max_iter))
            self.dyn_outer_tol.setValue(float(dyn.outer_tol_deg))
            self.dyn_outer_relax.setValue(float(dyn.outer_relax))
            self.dyn_lag_enabled.setChecked(bool(dyn.lag_enabled))
            self.dyn_lag_feeds_back.setChecked(bool(dyn.lag_feeds_back))
            self.dyn_lag_spring.setValue(float(dyn.lag_spring_nm_per_rad))
            self.dyn_lag_damping.setValue(float(dyn.lag_damping_nms_per_rad))
            self.dyn_lag_inertia.setValue(float(dyn.lag_inertia_kg_m2))
        finally:
            for w in widgets:
                w.blockSignals(False)
            for cb in (self.dyn_lag_enabled, self.dyn_lag_feeds_back):
                cb.blockSignals(False)
        self._refresh_dynamics_visibility()
        self._refresh_dynamics_readout()

    def _apply_constants(self, _value=None):
        """Number of blades and radius are editable at any time,
        including after pasting a custom table. This writes directly
        into geom.n_blades/geom.radius_m without reopening the generation
        popup (docs/plano.md Section 3, engineering note)."""
        self._schedule_preview_refresh()
        if self.state.project is None:
            return
        self._mark_dirty()
        geom = self.state.project.geometry
        geom.n_blades = self.n_blades.value()
        geom.radius_m = self.radius_m.value()
        self._applying_locally = True
        try:
            self.state.notify_geometry()
        finally:
            self._applying_locally = False

    def _save_project(self):
        from ..common import save_project_from_tab
        save_project_from_tab(self, self.state)
        self._clear_dirty()

    def _restore_project(self):
        from ..common import restore_project_from_disk
        restore_project_from_disk(self, self.state)

    def _refresh_from_project(self):
        if self.state.project is None:
            return
        if self._applying_locally:
            return
        geom = self.state.project.geometry
        self._sync_constants_from_geometry(geom)
        self._sync_dynamics_from_project(geom.dynamics)

        self.table.blockSignals(True)
        self.table.setRowCount(len(geom.r_norm))
        for i, (r, c, t) in enumerate(zip(geom.r_norm, geom.chord_norm, geom.twist_deg)):
            self.table.setItem(i, 0, QTableWidgetItem(f"{r:.4f}"))
            self.table.setItem(i, 1, QTableWidgetItem(f"{c:.4f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{t:.3f}"))
        self.table.blockSignals(False)
        self._clear_dirty()
        self._refresh_preview()

    def _apply_table_edits(self, *_args):
        if self.state.project is None:
            return
        try:
            r, c, t = [], [], []
            for i in range(self.table.rowCount()):
                r.append(float(self.table.item(i, 0).text()))
                c.append(float(self.table.item(i, 1).text()))
                t.append(float(self.table.item(i, 2).text()))
            geom = self.state.project.geometry
            new_geom = geometry.generate_custom(r, c, t, radius_m=self.radius_m.value(),
                                                  n_blades=self.n_blades.value(),
                                                  airfoil_name=geom.airfoil_name)
        except Exception:
            # Live: a temporarily invalid cell while the user is typing
            # (empty, a lone "-") should not interrupt with a dialog on
            # every keystroke, since the preview already shows the error
            # (`_refresh_preview`), and nothing is written to the project
            # until the row becomes a valid number again.
            return
        self._mark_dirty()
        self.state.project.geometry = new_geom
        self._applying_locally = True
        try:
            self.state.notify_geometry()
        finally:
            self._applying_locally = False


