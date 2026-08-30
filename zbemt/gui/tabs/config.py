"""Implement GUI tab 4, Config/Engine.

Purpose: expose mesh, atmosphere, inflow, loss/correction, Pitt--Peters, and
solver settings in the order used by the engine.

Inputs and outputs: reads the active ``AppState`` project, displays editable
controls, and writes values back to the project model when applied or saved.
Builders create groups; synchronizers load/store ``BEMTConfig``; validation
helpers update the issue panel. ``api.py`` owns persistence and execution.

Conventions and limitations: controls use SI units and progressive disclosure.
Valid but inactive controls remain visible and disabled. Rotor/propeller mode
and airfoil behavior are configured on their respective tabs.
"""

from __future__ import annotations

from dataclasses import asdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QPushButton,
    QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QMessageBox, QScrollArea,
)
from PyQt6.QtCore import pyqtSignal

from ... import api
from ...bemt import BEMTConfig

from ..common import AppState, show_error, require_project, set_row_visible
from ..widgets import ScientificSpinBox


# =============================================================================
# Tab 4 — Config/Engine (what remains of BEMTConfig after Rotor/
# Propeller moved to Project and reverse-flow/compressibility moved to
# Airfoil): mesh, inflow, augmentation/Prandtl, Pitt-Peters, solver,
# early exit. Progressive disclosure in every conditional block
# (docs/plano.md Section 5).
# =============================================================================

class ConfigMotorTab(QWidget):
    # Inflow coupling is today FIXED per family. There is no real
    # choice to offer (glauert/coleman/drees only have "local"
    # implemented; pitt_peters only has "steady"). That's why there is
    # no more "Type:" combo in the GUI (removed, see
    # docs/CHANGELOG.md): a combo with a single option is not a choice,
    # it's noise. The engine (bemt.py) still accepts "global" in old
    # configs for backward compatibility; only the GUI no longer offers
    # that option.
    _FIXED_COUPLING = {
        "glauert": "local",
        "coleman": "local",
        "drees": "local",
        "pitt_peters": "steady",
    }

    dirty_changed = pyqtSignal(bool)   # asterisk for "not saved to disk", same mechanism as geometry_tab.py/airfoil.py

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._dirty = False
        self._refreshing_from_project = False
        # True while an edit IN THIS TAB is being written back into
        # `state.project.config`. That prevents `_refresh_config_from_project`
        # (connected to `config_changed`, which the write itself
        # triggers) from rebuilding the form from what just came out of
        # it, and avoids clearing the asterisk before the user sees that
        # the change has not yet been saved.
        self._applying_locally = False
        self._warned_global_fallback = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        left = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.addWidget(scroll)

        left.addWidget(self._build_mesh_box())
        left.addWidget(self._build_inflow_box())
        left.addWidget(self._build_prandtl_box())
        left.addWidget(self._build_augmentation_box())
        self.pitt_peters_box = self._build_pitt_peters_box()
        left.addWidget(self.pitt_peters_box)
        left.addWidget(self._build_solver_box())
        left.addWidget(self._build_advanced_box())


        config_actions_box = QGroupBox("Project configuration")
        cform = QVBoxLayout(config_actions_box)
        self.config_issues_label = QLabel("")
        self.config_issues_label.setWordWrap(True)
        self.config_issues_label.setStyleSheet("font-size: 11px;")
        cform.addWidget(self.config_issues_label)
        btn_row = QHBoxLayout()
        # No "Apply to project": every field already writes into
        # `state.project.config` live, on each edit (see
        # `_on_field_changed`). "Save"/"Restore" only decide whether
        # that goes to disk or is discarded, not whether it reaches
        # memory anymore. One-word labels: the pair is always read
        # together, and "Save project"/"Restore from disk" only repeated
        # on each button what the whole block already says, besides
        # "Restore from disk" not fitting the button's natural width and
        # coming out with the text cut off.
        btn_save = QPushButton("Save")
        btn_save.setToolTip("Write the project to disk")
        btn_save.clicked.connect(self._save_project)
        btn_row.addWidget(btn_save)
        btn_restore = QPushButton("Restore")
        btn_restore.setToolTip("Discard changes and reload the project from disk")
        btn_restore.clicked.connect(self._restore_project)
        btn_row.addWidget(btn_restore)
        # No "Validate configuration": the check runs on every edit
        # (`_on_field_changed`), on every project switch, and on every
        # config change coming from another tab (see the connections
        # below), so the button only repeated what the screen already
        # shows, and a "validate" button next to an always-updated
        # warnings panel suggests the warnings could be stale, which is
        # the opposite of what happens. Same decision already made for
        # "Check airfoil" in the Airfoil tab.
        # The slack goes to the end of the row, not to the buttons (see
        # `tests/test_gui_layout.py`: without this they stretch to the
        # QSS width ceiling, and `setSizePolicy(Fixed)` doesn't hold).
        btn_row.addStretch(1)
        cform.addLayout(btn_row)
        left.addWidget(config_actions_box)
        left.addStretch(1)

        self.state.project_changed.connect(self._on_project_changed)
        self.state.config_changed.connect(self._refresh_config_from_project)
        self.state.mode_changed.connect(self._refresh_mode_label)
        # Half of `validate_project`'s warnings come from OUTSIDE this
        # tab (geometry, airfoil, condition): without listening to these
        # signals, the panel would only update when a field IN THIS TAB
        # changed.
        self.state.geometry_changed.connect(self._validate_config_display)
        self.state.airfoil_changed.connect(self._validate_config_display)
        self.state.config_changed.connect(self._validate_config_display)

        # Applies live + "not saved to disk" asterisk: generically
        # connects ALL value widgets already built above, instead of
        # listing the about 27 fields one by one. A new field is
        # automatically covered without having to remember to add it
        # here.
        for w in self.findChildren(QSpinBox):
            w.valueChanged.connect(self._on_field_changed)
        for w in self.findChildren(QDoubleSpinBox):
            w.valueChanged.connect(self._on_field_changed)
        for w in self.findChildren(QComboBox):
            w.currentTextChanged.connect(self._on_field_changed)
        for w in self.findChildren(QCheckBox):
            w.toggled.connect(self._on_field_changed)

    def _on_field_changed(self, *_args):
        if self._refreshing_from_project or self.state.project is None:
            return
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)
        self._applying_locally = True
        try:
            self.state.project.config.update(self._collect_config_updates())
            self.state.notify_config()
        finally:
            self._applying_locally = False
        self._validate_config_display()

    def _clear_dirty(self):
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)

    def _save_project(self):
        from ..common import save_project_from_tab
        save_project_from_tab(self, self.state)
        self._clear_dirty()

    def _restore_project(self):
        from ..common import restore_project_from_disk
        restore_project_from_disk(self, self.state)

    # --- 1-2) mesh + mode (read-only) -----------------------------------

    def _build_mesh_box(self) -> QGroupBox:
        box = QGroupBox("Mesh and atmospheric conditions")
        form = QFormLayout(box)
        self.cfg_Ne = QSpinBox(); self.cfg_Ne.setRange(5, 500)
        self.cfg_Ne.setToolTip(
            '"Ne"<br><br>Number of radial stations along the blade.<br><br>'
            'More stations resolve radial changes more accurately, but increase computation time.')
        self.cfg_Npsi = QSpinBox(); self.cfg_Npsi.setRange(1, 720)
        self.cfg_Npsi.setToolTip(
            '"Npsi"<br><br>Number of azimuthal positions around the disk.<br><br>'
            'Set it to 1 for an axisymmetric calculation with no azimuthal variation.')
        self.cfg_rho = QDoubleSpinBox(); self.cfg_rho.setRange(0.01, 10.0); self.cfg_rho.setDecimals(4)
        self.cfg_rho.setSingleStep(0.005)
        self.cfg_rho.setToolTip(
            '"rho"<br><br>Air density in kg/m³.<br><br>'
            'The standard sea-level ISA value is 1.225 kg/m³.')
        self.cfg_a_sound = QDoubleSpinBox(); self.cfg_a_sound.setRange(1.0, 2000.0); self.cfg_a_sound.setDecimals(2)
        self.cfg_a_sound.setToolTip(
            '"a_sound"<br><br>Speed of sound in m/s.<br><br>'
            'This value is used to calculate Mach number. The standard sea-level ISA value is 340.29 m/s.')
        self.cfg_integration_offset = QDoubleSpinBox(); self.cfg_integration_offset.setRange(0.0001, 0.1); self.cfg_integration_offset.setDecimals(4)
        self.cfg_integration_offset.setSingleStep(0.0001)
        self.cfg_integration_offset.setToolTip(
            '"integration_offset"<br><br>Small radial offset applied to integration stations.<br><br>'
            'It keeps the calculation away from the mathematical singularities at the hub and tip.')
        form.addRow("Radial stations Ne [-]:", self.cfg_Ne)
        form.addRow("Azimuthal stations Nψ [-]:", self.cfg_Npsi)
        form.addRow("Air density ρ [kg/m³]:", self.cfg_rho)
        form.addRow("Speed of sound a [m/s]:", self.cfg_a_sound)
        form.addRow("Radial integration offset [r/R]:", self.cfg_integration_offset)
        self.mode_label = QLabel("Rotor")
        self.mode_label.setStyleSheet("font-weight: bold;")
        form.addRow("Operation mode:", self.mode_label)
        return box

    def _refresh_mode_label(self):
        # Just the value: the row label already says "Operation mode:".
        # Repeating the word in the value produced the stutter
        # "Operation mode: Mode: Rotor".
        self.mode_label.setText("Propeller" if self.state.is_propeller() else "Rotor")
        self.mode_label.setToolTip(
            "Operation mode selected in the Project tab.<br><br>"
            "The mode determines the shaft direction and which coefficients are reported.")

    # --- 3-4) inflow + prandtl -----------------------------------------
    #
    # SEPARATE blocks. While the two shared the "Inflow model and
    # Prandtl loss" box, the block help could only point to one of the
    # two: `app._BLOCKS` matches the title, and the content written
    # about tip/root loss became unreachable in the window, with no
    # error at all. These are two distinct physics: one distributes the
    # induced velocity over the disk, the other corrects the continuous-
    # blade hypothesis near the edges.

    def _build_inflow_box(self) -> QGroupBox:
        box = QGroupBox("Inflow model")
        form = QFormLayout(box)
        self.cfg_inflow_family = QComboBox()
        self.cfg_inflow_family.addItems(["glauert", "coleman", "drees", "pitt_peters"])
        self.cfg_inflow_family.setToolTip(
            '"inflow_field_model"<br><br>'
            'Selects how the free-stream and induced velocity are distributed over the disk.<br><br>'
            '<b>glauert</b>: classical uniform inflow.<br>'
            '<b>coleman</b>: oblique-flow correction.<br>'
            '<b>drees</b>: non-uniform inflow model.<br>'
            '<b>pitt_peters</b>: finite-state dynamic inflow.')
        form.addRow("Inflow model:", self.cfg_inflow_family)
        self.cfg_inflow_family.currentTextChanged.connect(self._update_pitt_peters_visibility)
        return box

    def _build_prandtl_box(self) -> QGroupBox:
        box = QGroupBox("Tip and root loss (Prandtl)")
        form = QFormLayout(box)
        self.cfg_prandtl_loss_mode = QComboBox()
        for key, label in (("off", "Off"), ("tip", "Tip only"),
                           ("root", "Root only"), ("both", "Tip + root")):
            self.cfg_prandtl_loss_mode.addItem(f"{label} ({key})", key)
        self.cfg_prandtl_loss_mode.setToolTip(
            '"prandtl_loss_mode"<br><br>'
            'Approximates the loss of lift near the finite blade tip and root.<br><br>'
            '<b>Off</b>: no correction.<br><b>Tip</b>: tip correction only.<br>'
            '<b>Root</b>: root correction only.<br><b>Tip + root</b>: both corrections.')
        form.addRow("Tip/root loss (Prandtl):", self.cfg_prandtl_loss_mode)
        return box

    def _update_pitt_peters_visibility(self, family: str):
        """Progressive disclosure (docs/plano.md Section 5): the
        Pitt-Peters block only appears when the inflow family is
        'pitt_peters'. It is hidden (not just disabled) otherwise."""
        self.pitt_peters_box.setVisible(family == "pitt_peters")

    def _inflow_field_model_from_widgets(self) -> str:
        family = self.cfg_inflow_family.currentText()
        coupling = self._FIXED_COUPLING[family]
        if family == "pitt_peters":
            return f"pitt_peters_{coupling}"
        return f"{family}_{coupling}"

    def _set_inflow_widgets_from_field_model(self, inflow_field_model: str):
        if inflow_field_model.startswith("pitt_peters"):
            family, coupling = "pitt_peters", inflow_field_model.split("_", 2)[-1]
        else:
            family, coupling = inflow_field_model.rsplit("_", 1)
        if coupling == "global" and not self._warned_global_fallback:
            self._warned_global_fallback = True
            QMessageBox.warning(
                self, "Option 'global' removed from GUI",
                "This project uses inflow_field_model with 'global' coupling, which is no longer "
                "offered in this tab. When applying any changes here, the value saved in "
                "project.config will use 'local' (glauert/coleman/drees) or 'steady' "
                "(Pitt-Peters), the only coupling offered today.")
        self.cfg_inflow_family.blockSignals(True)
        self.cfg_inflow_family.setCurrentText(family)
        self.cfg_inflow_family.blockSignals(False)
        self._update_pitt_peters_visibility(family)

    # --- 7-8) Snel + radial flow -----------------------------------------

    def _build_augmentation_box(self) -> QGroupBox:
        box = QGroupBox("3D rotational effects")
        form = QFormLayout(box)
        self.cfg_use_rotational_augmentation = QCheckBox("Rotational augmentation (Himmelskamp/Snel)")
        self.cfg_use_rotational_augmentation.setToolTip(
            '"use_rotational_augmentation" — increases Cl in the inner blade region due to centrifugal field; '
            'important at high rotational load regimes')
        form.addRow(self.cfg_use_rotational_augmentation)
        self.cfg_use_radial_flow_correction = QCheckBox("Radial flow correction (independence principle)")
        self.cfg_use_radial_flow_correction.setToolTip(
            '"use_radial_flow_correction" — decouples the radial velocity component in section analysis (ISAE); '
            'recommended for rotors with high skew angle')
        form.addRow(self.cfg_use_radial_flow_correction)
        self.radial_flow_label = QLabel("Maximum skew angle [deg]:")
        self.cfg_radial_flow_max_skew_deg = QDoubleSpinBox(); self.cfg_radial_flow_max_skew_deg.setRange(1, 89)
        self.cfg_radial_flow_max_skew_deg.setSingleStep(0.5)
        self.cfg_radial_flow_max_skew_deg.setToolTip('"radial_flow_max_skew_deg" — skew angle limit; above this the correction is applied fully')
        form.addRow(self.radial_flow_label, self.cfg_radial_flow_max_skew_deg)
        self.cfg_use_radial_flow_correction.toggled.connect(self._update_radial_flow_visibility)
        self._radial_flow_form = form
        self._update_radial_flow_visibility(self.cfg_use_radial_flow_correction.isChecked())
        return box

    def _update_radial_flow_visibility(self, on: bool):
        """Progressive disclosure: radial_flow_max_skew_deg only appears
        when use_radial_flow_correction is on."""
        set_row_visible(self._radial_flow_form, self.cfg_radial_flow_max_skew_deg, on)

    # --- 9) Pitt-Peters ---------------------------------------------------

    def _build_pitt_peters_box(self) -> QGroupBox:
        box = QGroupBox("Pitt-Peters (finite-state dynamic inflow)")
        form = QFormLayout(box)
        self.cfg_pitt_peters_states = QComboBox(); self.cfg_pitt_peters_states.addItems(["3", "5"])
        self.cfg_pitt_peters_states.setToolTip('"pitt_peters_states" — 3 = Peters model (implemented); 5 = Peters-He (not yet implemented)')
        form.addRow("Number of states:", self.cfg_pitt_peters_states)
        self.cfg_pitt_peters_outer_iter = QSpinBox(); self.cfg_pitt_peters_outer_iter.setRange(1, 500)
        self.cfg_pitt_peters_outer_iter.setToolTip('"pitt_peters_outer_iter" — maximum number of iterations in the outer finite-state loop')
        self.cfg_pitt_peters_relax = QDoubleSpinBox(); self.cfg_pitt_peters_relax.setRange(0.01, 1.0); self.cfg_pitt_peters_relax.setDecimals(3)
        self.cfg_pitt_peters_relax.setSingleStep(0.01)
        self.cfg_pitt_peters_relax.setToolTip('"pitt_peters_relax" — relaxation factor for the outer Pitt-Peters loop')
        self.cfg_pitt_peters_tol = ScientificSpinBox(); self.cfg_pitt_peters_tol.setRange(1e-10, 1e-2)
        self.cfg_pitt_peters_tol.setToolTip('"pitt_peters_tol" — convergence tolerance for the outer Pitt-Peters loop')
        form.addRow("Maximum outer iterations [-]:", self.cfg_pitt_peters_outer_iter)
        form.addRow("Relaxation factor [-]:", self.cfg_pitt_peters_relax)
        form.addRow("Convergence tolerance [-]:", self.cfg_pitt_peters_tol)
        return box

    # --- 11) solver ---------------------------------------------------

    def _build_solver_box(self) -> QGroupBox:
        box = QGroupBox("Induced-inflow solver")
        form = QFormLayout(box)
        self.cfg_solver = QComboBox(); self.cfg_solver.addItems(["fixed_point", "newton", "bisection", "aitken"])
        self.cfg_solver.setToolTip(
            '"solver" — iterative algorithm to solve νi: '
            '"fixed_point": simple fixed point; '
            '"newton": Newton-Raphson; '
            '"bisection": bisection (robust, slower); '
            '"aitken": Aitken acceleration (accelerated fixed point)')
        form.addRow("Iterative algorithm:", self.cfg_solver)
        self.cfg_max_iter = QSpinBox(); self.cfg_max_iter.setRange(1, 5000)
        self.cfg_max_iter.setToolTip('"max_iter" — maximum number of iterations per element')
        self.cfg_tol = ScientificSpinBox(); self.cfg_tol.setRange(1e-12, 1e-2)
        self.cfg_tol.setToolTip('"tol" — convergence tolerance for νi residual')
        self.cfg_relax = QDoubleSpinBox(); self.cfg_relax.setRange(0.01, 1.0); self.cfg_relax.setDecimals(3)
        self.cfg_relax.setSingleStep(0.01)
        self.cfg_relax.setToolTip('"relax" — global relaxation factor for iteration (0 = no update; 1 = no relaxation)')
        form.addRow("Maximum iterations [-]:", self.cfg_max_iter)
        form.addRow("Convergence tolerance [-]:", self.cfg_tol)
        form.addRow("Relaxation factor [-]:", self.cfg_relax)
        self.cfg_relax_schedule = QCheckBox("Adaptive relaxation (root/tip/azimuth)")
        self.cfg_relax_schedule.setToolTip('"relax_schedule" — reduces the relaxation factor near root and tip to improve convergence')
        form.addRow(self.cfg_relax_schedule)

        self.relax_schedule_box = QGroupBox("Adaptive relaxation parameters")
        rform = QFormLayout(self.relax_schedule_box)
        self.cfg_relax_root_factor = QDoubleSpinBox(); self.cfg_relax_root_factor.setRange(0.01, 1.0); self.cfg_relax_root_factor.setDecimals(3)
        self.cfg_relax_root_factor.setSingleStep(0.01)
        self.cfg_relax_root_factor.setToolTip('"relax_root_factor" — relaxation factor applied in the root region')
        self.cfg_relax_root_threshold = QDoubleSpinBox(); self.cfg_relax_root_threshold.setRange(0.0, 1.0); self.cfg_relax_root_threshold.setDecimals(3)
        self.cfg_relax_root_threshold.setSingleStep(0.01)
        self.cfg_relax_root_threshold.setToolTip('"relax_root_threshold" — r/R limit below which the root is considered')
        self.cfg_relax_tip_threshold = QDoubleSpinBox(); self.cfg_relax_tip_threshold.setRange(0.0, 1.0); self.cfg_relax_tip_threshold.setDecimals(3)
        self.cfg_relax_tip_threshold.setSingleStep(0.01)
        self.cfg_relax_tip_threshold.setToolTip('"relax_tip_threshold" — r/R limit above which the tip is considered')
        self.cfg_relax_azimuth_factor = QDoubleSpinBox(); self.cfg_relax_azimuth_factor.setRange(0.01, 1.0); self.cfg_relax_azimuth_factor.setDecimals(3)
        self.cfg_relax_azimuth_factor.setSingleStep(0.01)
        self.cfg_relax_azimuth_factor.setToolTip('"relax_azimuth_factor" — extra azimuthal relaxation factor')
        self.cfg_relax_azimuth_threshold = QDoubleSpinBox(); self.cfg_relax_azimuth_threshold.setRange(0.0, 1.0); self.cfg_relax_azimuth_threshold.setDecimals(3)
        self.cfg_relax_azimuth_threshold.setSingleStep(0.01)
        self.cfg_relax_azimuth_threshold.setToolTip('"relax_azimuth_threshold" — azimuthal convergence threshold before applying extra relaxation')
        rform.addRow("Root factor [-]:", self.cfg_relax_root_factor)
        rform.addRow("Root radial threshold [r/R]:", self.cfg_relax_root_threshold)
        rform.addRow("Tip radial threshold [r/R]:", self.cfg_relax_tip_threshold)
        rform.addRow("Azimuthal factor [-]:", self.cfg_relax_azimuth_factor)
        rform.addRow("Azimuthal convergence threshold [-]:", self.cfg_relax_azimuth_threshold)
        form.addRow(self.relax_schedule_box)
        self.cfg_relax_schedule.toggled.connect(self.relax_schedule_box.setVisible)
        self.relax_schedule_box.setVisible(self.cfg_relax_schedule.isChecked())
        return box

    def _build_advanced_box(self) -> QGroupBox:
        box = QGroupBox("Early exit")
        form = QFormLayout(box)
        self.cfg_early_exit_fraction = QDoubleSpinBox(); self.cfg_early_exit_fraction.setRange(0.5, 1.0); self.cfg_early_exit_fraction.setDecimals(4)
        self.cfg_early_exit_fraction.setSingleStep(0.001)
        self.cfg_early_exit_fraction.setToolTip('"early_exit_fraction" — exit when this fraction of elements has converged; speeds up easy cases')
        self.cfg_stagnation_patience = QSpinBox(); self.cfg_stagnation_patience.setRange(1, 500)
        self.cfg_stagnation_patience.setToolTip('"stagnation_patience" — number of iterations without improvement before exiting due to stagnation')
        self.cfg_stagnation_min_frac = QDoubleSpinBox(); self.cfg_stagnation_min_frac.setRange(0.0, 1.0); self.cfg_stagnation_min_frac.setDecimals(4)
        self.cfg_stagnation_min_frac.setSingleStep(0.01)
        self.cfg_stagnation_min_frac.setToolTip('"stagnation_min_frac" — minimum improvement in element fraction per iteration to not count as stagnation')
        form.addRow("Early exit fraction [-]:", self.cfg_early_exit_fraction)
        form.addRow("Stagnation patience [iter]:", self.cfg_stagnation_patience)
        form.addRow("Minimum improvement per iteration [-]:", self.cfg_stagnation_min_frac)
        return box

    # --- bridge with the `project.config` dict (asdict of BEMTConfig) ------

    def _set_prandtl_mode_widget(self, mode: str):
        idx = self.cfg_prandtl_loss_mode.findData(mode)
        if idx < 0:
            idx = self.cfg_prandtl_loss_mode.findData("both")
        self.cfg_prandtl_loss_mode.setCurrentIndex(max(idx, 0))

    def _refresh_config_from_project(self):
        if self.state.project is None:
            return
        if self._applying_locally:
            # This tab itself just wrote into `state.project.config`
            # (see `_on_field_changed`), which triggered `config_changed`
            # and called this method back. Rebuilding the form from
            # what just came out of it is redundant and would clear the
            # asterisk before the user saves to disk.
            return
        # Populating the widgets from the project triggers the same
        # valueChanged/toggled/currentTextChanged that a manual user edit
        # would trigger. Without this guard, opening/switching a
        # project would mark the tab as "edited" right away, a false
        # positive.
        self._refreshing_from_project = True
        try:
            self._refresh_config_from_project_impl()
        finally:
            self._refreshing_from_project = False
        self._clear_dirty()

    def _refresh_config_from_project_impl(self):
        cfg = dict(self.state.project.config)
        d = asdict(BEMTConfig())

        def g(key):
            return cfg.get(key, d[key])

        if "inflow_field_model" not in cfg and ("inflow_model" in cfg or "inflow_coupling" in cfg):
            old_model = cfg.get("inflow_model", "glauert")
            old_coupling = cfg.get("inflow_coupling", "local")
            if old_coupling == "pitt_peters":
                cfg["inflow_field_model"] = "pitt_peters_steady"
            else:
                cfg["inflow_field_model"] = f"{old_model}_{old_coupling}"

        if "prandtl_loss_mode" not in cfg and "use_prandtl_loss" in cfg:
            # Display migration (docs/plano.md GUI v3, Phase B): the
            # actual value in project.config is only rewritten when the
            # user clicks "Apply to project" (same spirit as the inflow
            # migration above). studies._migrate_config_dict already
            # does the same when running the engine, regardless of
            # whether the GUI was ever opened.
            cfg["prandtl_loss_mode"] = "both" if cfg["use_prandtl_loss"] else "off"

        self.cfg_Ne.setValue(int(g("Ne")))
        self.cfg_Npsi.setValue(int(g("Npsi")))
        self.cfg_rho.setValue(float(g("rho")))
        self.cfg_a_sound.setValue(float(g("a_sound")))
        self.cfg_integration_offset.setValue(float(g("integration_offset")))
        self._refresh_mode_label()

        self._set_inflow_widgets_from_field_model(str(g("inflow_field_model")))
        self._set_prandtl_mode_widget(str(g("prandtl_loss_mode")))

        self.cfg_use_rotational_augmentation.setChecked(bool(g("use_rotational_augmentation")))
        self.cfg_use_radial_flow_correction.setChecked(bool(g("use_radial_flow_correction")))
        self.cfg_radial_flow_max_skew_deg.setValue(float(g("radial_flow_max_skew_deg")))
        self._update_radial_flow_visibility(self.cfg_use_radial_flow_correction.isChecked())

        self.cfg_pitt_peters_states.setCurrentText(str(int(g("pitt_peters_states"))))
        self.cfg_pitt_peters_outer_iter.setValue(int(g("pitt_peters_outer_iter")))
        self.cfg_pitt_peters_relax.setValue(float(g("pitt_peters_relax")))
        self.cfg_pitt_peters_tol.setValue(float(g("pitt_peters_tol")))

        self.cfg_solver.setCurrentText(str(g("solver")))
        self.cfg_max_iter.setValue(int(g("max_iter")))
        self.cfg_tol.setValue(float(g("tol")))
        self.cfg_relax.setValue(float(g("relax")))
        self.cfg_relax_schedule.setChecked(bool(g("relax_schedule")))
        self.relax_schedule_box.setVisible(self.cfg_relax_schedule.isChecked())
        self.cfg_relax_root_factor.setValue(float(g("relax_root_factor")))
        self.cfg_relax_root_threshold.setValue(float(g("relax_root_threshold")))
        self.cfg_relax_tip_threshold.setValue(float(g("relax_tip_threshold")))
        self.cfg_relax_azimuth_factor.setValue(float(g("relax_azimuth_factor")))
        self.cfg_relax_azimuth_threshold.setValue(float(g("relax_azimuth_threshold")))

        self.cfg_early_exit_fraction.setValue(float(g("early_exit_fraction")))
        self.cfg_stagnation_patience.setValue(int(g("stagnation_patience")))
        self.cfg_stagnation_min_frac.setValue(float(g("stagnation_min_frac")))

        self._validate_config_display()

    def _collect_config_updates(self) -> dict:
        return dict(
            Ne=self.cfg_Ne.value(),
            Npsi=self.cfg_Npsi.value(),
            rho=self.cfg_rho.value(),
            a_sound=self.cfg_a_sound.value(),
            integration_offset=self.cfg_integration_offset.value(),
            inflow_field_model=self._inflow_field_model_from_widgets(),
            prandtl_loss_mode=self.cfg_prandtl_loss_mode.currentData(),
            use_rotational_augmentation=self.cfg_use_rotational_augmentation.isChecked(),
            use_radial_flow_correction=self.cfg_use_radial_flow_correction.isChecked(),
            radial_flow_max_skew_deg=self.cfg_radial_flow_max_skew_deg.value(),
            pitt_peters_states=int(self.cfg_pitt_peters_states.currentText()),
            pitt_peters_outer_iter=self.cfg_pitt_peters_outer_iter.value(),
            pitt_peters_relax=self.cfg_pitt_peters_relax.value(),
            pitt_peters_tol=self.cfg_pitt_peters_tol.value(),
            solver=self.cfg_solver.currentText(),
            max_iter=self.cfg_max_iter.value(),
            tol=self.cfg_tol.value(),
            relax=self.cfg_relax.value(),
            relax_schedule=self.cfg_relax_schedule.isChecked(),
            relax_root_factor=self.cfg_relax_root_factor.value(),
            relax_root_threshold=self.cfg_relax_root_threshold.value(),
            relax_tip_threshold=self.cfg_relax_tip_threshold.value(),
            relax_azimuth_factor=self.cfg_relax_azimuth_factor.value(),
            relax_azimuth_threshold=self.cfg_relax_azimuth_threshold.value(),
            early_exit_fraction=self.cfg_early_exit_fraction.value(),
            stagnation_patience=self.cfg_stagnation_patience.value(),
            stagnation_min_frac=self.cfg_stagnation_min_frac.value(),
        )

    def _apply_config_to_project(self):
        """Kept for compatibility with direct calls (tests, scripts):
        every field already applies live via `_on_field_changed` (there
        is no more "Apply to project" button in the GUI), so this is
        merely idempotent: it reapplies the widgets' current values."""
        if not require_project(self, self.state):
            return
        try:
            self._applying_locally = True
            try:
                self.state.project.config.update(self._collect_config_updates())
                self.state.notify_config()
            finally:
                self._applying_locally = False
            self._validate_config_display()
        except Exception as exc:
            show_error(self, "Error applying configuration", exc)

    def _validate_config_display(self):
        if self.state.project is None:
            self.config_issues_label.setText("")
            return
        issues = api.validate_project(self.state.project)
        if not issues:
            self.config_issues_label.setText('<font color="#2e7d32">No warnings.</font>')
        else:
            colors = {"error": "#c62828", "warning": "#f0ad4e", "info": "#555555"}
            self.config_issues_label.setText("<br>".join(
                f'<font color="{colors.get(i.level, "#000000")}">{i}</font>' for i in issues
            ))

    def _on_project_changed(self):
        if self.state.project is not None:
            self._refresh_config_from_project()
        # The check also runs here: without this, a freshly opened
        # project would leave the warnings panel EMPTY until the first
        # edit, and empty, there, reads as "no problems".
        self._validate_config_display()
