from pathlib import Path
import json
import re


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected exactly one match, got {count}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


def regex_once(path, pattern, replacement):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    text2, n = re.subn(pattern, lambda _m: replacement, text, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f'{path}: expected one regex match, got {n}: {pattern[:120]!r}')
    p.write_text(text2, encoding='utf-8')


# -----------------------------------------------------------------------------
# Engine configuration: a fixed-condition dynamic Pitt-Peters march gets the
# same periodic-run knobs already used by the Oye time-march path.
# -----------------------------------------------------------------------------
replace_once(
    'zbemt/bemt.py',
    '    # pitt_peters_steady | pitt_peters_unsteady (this last one is not solved\n'
    '    # see `run_sweep_unsteady_pitt_peters`).\n',
    '    # pitt_peters_steady | pitt_peters_unsteady. The unsteady value is\n'
    '    # time-marched either as a fixed periodic operating point (Run Case /\n'
    '    # batch) or along a changing trajectory (Maneuver / Transient).\n',
)
replace_once(
    'zbemt/bemt.py',
    '    pitt_peters_outer_iter: int = 40\n'
    '    pitt_peters_relax: float = 0.5\n'
    '    pitt_peters_tol: float = 1e-6\n',
    '    pitt_peters_outer_iter: int = 40\n'
    '    pitt_peters_relax: float = 0.5\n'
    '    pitt_peters_tol: float = 1e-6\n'
    '    # Fixed-condition time march used by pitt_peters_unsteady on the case\n'
    '    # path. One output map is retained per revolution; the final result is\n'
    '    # the mean of the last N revolutions, after the start-up is discarded.\n'
    '    pitt_peters_time_march_revolutions: int = 8\n'
    '    pitt_peters_time_march_avg_last: int = 3\n'
    '    pitt_peters_time_march_substeps_per_revolution: int = 16\n'
    '    pitt_peters_time_march_initial_state: str = "zero"  # zero | equilibrium\n',
)

# -----------------------------------------------------------------------------
# Study layer: route an isolated pitt_peters_unsteady condition into the
# existing exponential time marcher. No ManeuverDefinition is required.
# -----------------------------------------------------------------------------
anchor = '''# =============================================================================
# Single case
# =============================================================================

def run_single_case(project: Project, condition: FlightCondition,
                     should_cancel=None) -> Results:
'''
helper = '''# =============================================================================
# Single case
# =============================================================================

def _mean_periodic_maps(maps_list: list[dict]) -> dict:
    """Average numeric disk fields over several settled revolution maps.

    The last map remains the source for non-numeric metadata. Numeric arrays
    with a common shape are averaged element-by-element, which preserves the
    r/psi field needed by the Results azimuth and disk plots. Numeric scalars
    are averaged as diagnostics. Boolean/string metadata stay from the final
    revolution.
    """
    if not maps_list:
        raise ValueError("periodic Pitt-Peters march returned no maps")
    out = dict(maps_list[-1])
    common = set(maps_list[0])
    for maps in maps_list[1:]:
        common.intersection_update(maps)
    for key in common:
        values = [maps[key] for maps in maps_list]
        if all(isinstance(value, np.ndarray) for value in values):
            shapes = {value.shape for value in values}
            if len(shapes) == 1 and all(np.issubdtype(value.dtype, np.number)
                                         for value in values):
                out[key] = np.mean(np.stack(values, axis=0), axis=0)
        elif all(isinstance(value, (int, float, np.integer, np.floating))
                 and not isinstance(value, (bool, np.bool_)) for value in values):
            out[key] = float(np.mean(values))
    return out


def _run_periodic_pitt_peters_case(project: Project, condition: FlightCondition,
                                    cfg: BEMTConfig, should_cancel=None) -> Results:
    """Time-march Pitt-Peters at one CONSTANT operating point.

    A maneuver is only needed when the prescribed condition changes with
    time. Here the condition is repeated once per revolution, the existing
    exponential Pitt-Peters integrator advances the three states inside each
    revolution, the start-up revolutions are discarded, and the last N
    revolution maps are averaged. The returned ``Results.dataframe`` keeps
    the complete state/load time history; ``Results.maps`` is the settled
    mean r/psi field used by the normal disk and azimuth plots.
    """
    from .bemt import run_maneuver as engine_run_maneuver
    from .bemt import steady_pitt_peters_state

    rpm = _require_rpm(condition.rpm, f"condition {condition.name!r}")
    rotor = _to_rotor(project.geometry,
                      collective_deg=condition.collective_deg, rpm=rpm)
    mu_inplane, sideslip_deg = models.resolve_inplane_flow(
        condition, rotor.OmegaR)
    if sideslip_deg != 0.0:
        cfg = replace(cfg, inflow_sideslip_deg=sideslip_deg)

    radial = airfoils.radial_reynolds_mach(rotor, cfg, mu_x=mu_inplane)
    airfoil_obj = airfoils.to_blade_airfoil(
        project.airfoil_sections or [project.airfoil], radial=radial)

    n_rev = max(int(cfg.pitt_peters_time_march_revolutions), 1)
    n_avg = max(min(int(cfg.pitt_peters_time_march_avg_last), n_rev), 1)
    n_sub = max(int(cfg.pitt_peters_time_march_substeps_per_revolution), 1)
    initial_mode = str(cfg.pitt_peters_time_march_initial_state).lower()
    if initial_mode not in ("zero", "equilibrium"):
        raise ValueError(
            "pitt_peters_time_march_initial_state must be 'zero' or 'equilibrium'")

    period_s = 60.0 / rpm
    samples = [
        models.ManeuverPoint(
            t_s=i * period_s,
            mu_x=mu_inplane,
            Vz=condition.Vz,
            collective_deg=condition.collective_deg,
            cyclic_c_deg=condition.cyclic_c_deg,
            cyclic_s_deg=condition.cyclic_s_deg,
            rpm=rpm,
        )
        for i in range(n_rev + 1)
    ]

    def rotor_builder(point):
        return _to_rotor(project.geometry,
                         collective_deg=point.collective_deg,
                         rpm=float(point.rpm))

    initial_nu = None
    if initial_mode == "equilibrium":
        initial_nu = steady_pitt_peters_state(
            rotor, airfoil_obj, cfg, mu_inplane,
            float(condition.Vz) / rotor.OmegaR)

    defs = project.airfoil_sections or [project.airfoil]
    march_dynamic_stall = any(
        bool(getattr(defn, "use_dynamic_stall", False))
        and str(getattr(defn, "dynamic_stall_method", "frequency")) == "time_march"
        for defn in defs
    )
    dynamics = project.geometry.dynamics
    march_flapping = bool(
        dynamics.flap_model != "rigid" or dynamics.lag_enabled
        or condition.cyclic_c_deg or condition.cyclic_s_deg
    )

    history, maps_list = engine_run_maneuver(
        rotor_builder, airfoil_obj, cfg, samples,
        dynamics=dynamics, initial_nu=initial_nu,
        substeps_per_step=n_sub,
        march_dynamic_stall=march_dynamic_stall,
        march_flapping=march_flapping,
        should_cancel=should_cancel,
    )

    settled_maps = maps_list[-n_avg:]
    maps = _mean_periodic_maps(settled_maps)
    summary = aggregate_results(rotor, cfg, maps)
    summary.setdefault("collective_deg", condition.collective_deg)
    summary.setdefault("rpm", summary.get("rotor_rpm", condition.rpm))
    summary.setdefault("cyclic_c_deg", condition.cyclic_c_deg)
    summary.setdefault("cyclic_s_deg", condition.cyclic_s_deg)
    summary["sideslip_deg"] = float(sideslip_deg)
    summary["Vy"] = float(models.lateral_velocity(condition, rotor.OmegaR))
    summary["pitt_peters_time_march_revolutions"] = n_rev
    summary["pitt_peters_time_march_avg_last"] = n_avg
    summary["pitt_peters_time_march_substeps_per_revolution"] = n_sub
    summary["pitt_peters_time_march_initial_state"] = initial_mode
    summary["pitt_peters_time_march_duration_s"] = n_rev * period_s

    state_cols = ["nu0", "nu_s", "nu_c"]
    if len(history) >= 2 and all(key in history for key in state_cols):
        final_state = history[state_cols].iloc[-1].to_numpy(dtype=float)
        previous_state = history[state_cols].iloc[-2].to_numpy(dtype=float)
        residual = float(np.max(np.abs(final_state - previous_state)))
        summary["pitt_peters_time_march_state_residual"] = residual
        summary["pitt_peters_time_march_converged"] = bool(
            residual <= max(float(cfg.pitt_peters_tol), 1e-6))
        maps["pitt_peters_nu_final"] = final_state
    maps["pitt_peters_time_march_revolutions"] = n_rev
    maps["pitt_peters_time_march_avg_last"] = n_avg
    maps["pitt_peters_time_march_substeps_per_revolution"] = n_sub
    maps["collective_deg"] = condition.collective_deg
    maps["rpm"] = summary.get("rotor_rpm", condition.rpm)
    maps["CT"] = summary.get("CT")

    return Results(summary=summary, dataframe=history, maps=maps,
                   condition_name=condition.name)


def run_single_case(project: Project, condition: FlightCondition,
                     should_cancel=None) -> Results:
'''
replace_once('zbemt/studies.py', anchor, helper)
replace_once(
    'zbemt/studies.py',
    '    cfg = _build_config(project.config, airfoil_def=project.airfoil)\n'
    '    rpm = _require_rpm(condition.rpm, f"condition {condition.name!r}")\n',
    '    cfg = _build_config(project.config, airfoil_def=project.airfoil)\n'
    '    if cfg.inflow_field_model == "pitt_peters_unsteady":\n'
    '        return _run_periodic_pitt_peters_case(\n'
    '            project, condition, cfg, should_cancel=should_cancel)\n'
    '    rpm = _require_rpm(condition.rpm, f"condition {condition.name!r}")\n',
)

# -----------------------------------------------------------------------------
# Validation: dynamic Pitt-Peters is now legal for isolated case/batch paths;
# maneuvers still require it because they actually transport state between
# changing operating points.
# -----------------------------------------------------------------------------
replace_once(
    'zbemt/validation.py',
    '    ``inflow_path`` selects which execution path the config serves:\n'
    '    ``"case"``/``"batch"`` (isolated operating points) or ``"maneuver"``\n'
    '    (SC-12). The unsteady Pitt-Peters model is an ERROR on the case and\n'
    '    batch paths -- those resolve algebraic equilibria -- and it is the\n'
    '    REQUIRED value on the maneuver path, where the inflow state actually\n'
    '    marches.\n',
    '    ``inflow_path`` selects which execution path the config serves:\n'
    '    ``"case"``/``"batch"`` (isolated operating points) or ``"maneuver"``\n'
    '    (SC-12). A case/batch may use ``pitt_peters_unsteady`` as a periodic\n'
    '    fixed-condition time march; a maneuver requires it because only that\n'
    '    formulation transports the inflow state along a changing trajectory.\n',
)
regex_once(
    'zbemt/validation.py',
    r'    # --- pitt_peters_unsteady is path-scoped \(SC-12\) ------------------------\n.*?\n    # --- time march cost warning \(SC-12\) ------------------------------------',
    '''    # --- pitt_peters_unsteady is path-scoped (SC-12) ------------------------
    # Isolated cases/batches now run a periodic fixed-condition march and
    # average the settled revolutions. Maneuvers still REQUIRE the unsteady
    # model because they carry state from one changing sample to the next.
    if inflow_path == "maneuver" and inflow_field_model != "pitt_peters_unsteady":
        issues.append(Issue("error",
            "a maneuver marches the inflow state in time, so it requires "
            "inflow_field_model='pitt_peters_unsteady'. The steady "
            "variant answers algebraically and carries no state to march."))

    if inflow_field_model == "pitt_peters_unsteady" and inflow_path != "maneuver":
        n_rev = int(config.get("pitt_peters_time_march_revolutions", 8) or 0)
        n_avg = int(config.get("pitt_peters_time_march_avg_last", 3) or 0)
        n_sub = int(config.get("pitt_peters_time_march_substeps_per_revolution", 16) or 0)
        initial = str(config.get("pitt_peters_time_march_initial_state", "zero"))
        if n_rev < 1:
            issues.append(Issue("error",
                "pitt_peters_time_march_revolutions must be at least 1."))
        if n_avg < 1 or n_avg > max(n_rev, 0):
            issues.append(Issue("error",
                "pitt_peters_time_march_avg_last must be between 1 and the "
                "number of marched revolutions."))
        if n_sub < 1:
            issues.append(Issue("error",
                "pitt_peters_time_march_substeps_per_revolution must be at least 1."))
        if initial not in ("zero", "equilibrium"):
            issues.append(Issue("error",
                "pitt_peters_time_march_initial_state must be 'zero' or 'equilibrium'."))
        if n_rev > 0 and n_sub > 0:
            issues.append(Issue("info",
                f"Dynamic Pitt-Peters fixed case will march {n_rev} revolutions "
                f"with {n_sub} sub-steps/revolution ({n_rev * n_sub} state "
                f"updates) and average the last {max(n_avg, 0)} revolution(s)."))

    # --- time march cost warning (SC-12) ------------------------------------'''
)

# -----------------------------------------------------------------------------
# GUI: Pitt-Peters gets Steady and Dynamic (time march). Dynamic-only controls
# are shown progressively in the existing Pitt-Peters box.
# -----------------------------------------------------------------------------
replace_once(
    'zbemt/gui/tabs/config.py',
    '        "pitt_peters": ("steady",),\n',
    '        "pitt_peters": ("steady", "unsteady"),\n',
)
replace_once(
    'zbemt/gui/tabs/config.py',
    "            '<b>Steady</b>: steady finite-state Pitt-Peters solution.')\n",
    "            '<b>Steady</b>: algebraic equilibrium of the Pitt-Peters states.<br>'\n"
    "            '<b>Dynamic</b>: time-marches the three states at the fixed case, then averages the settled revolutions.')\n",
)
replace_once(
    'zbemt/gui/tabs/config.py',
    '            "steady": "Steady",\n',
    '            "steady": "Steady",\n'
    '            "unsteady": "Dynamic (time march)",\n',
)
replace_once(
    'zbemt/gui/tabs/config.py',
    '        self.cfg_inflow_family.currentTextChanged.connect(self._on_inflow_family_changed)\n'
    '        return box\n',
    '        self.cfg_inflow_family.currentTextChanged.connect(self._on_inflow_family_changed)\n'
    '        self.cfg_inflow_coupling.currentIndexChanged.connect(\n'
    '            self._update_pitt_peters_dynamic_visibility)\n'
    '        return box\n',
)
replace_once(
    'zbemt/gui/tabs/config.py',
    '    def _update_pitt_peters_visibility(self, family: str):\n'
    '        """Pitt-Peters parameters have meaning only for that family."""\n'
    '        self.pitt_peters_box.setVisible(family == "pitt_peters")\n',
    '    def _update_pitt_peters_visibility(self, family: str):\n'
    '        """Pitt-Peters parameters have meaning only for that family."""\n'
    '        self.pitt_peters_box.setVisible(family == "pitt_peters")\n'
    '        self._update_pitt_peters_dynamic_visibility()\n\n'
    '    def _update_pitt_peters_dynamic_visibility(self, *_args):\n'
    '        """Show time-march controls only for Dynamic Pitt-Peters."""\n'
    '        if not hasattr(self, "_pitt_peters_form"):\n'
    '            return\n'
    '        dynamic = (self.cfg_inflow_family.currentText() == "pitt_peters"\n'
    '                   and self.cfg_inflow_coupling.currentData() == "unsteady")\n'
    '        for widget in (self.cfg_pitt_peters_time_march_revolutions,\n'
    '                       self.cfg_pitt_peters_time_march_avg_last,\n'
    '                       self.cfg_pitt_peters_time_march_substeps_per_revolution,\n'
    '                       self.cfg_pitt_peters_time_march_initial_state):\n'
    '            set_row_visible(self._pitt_peters_form, widget, dynamic)\n',
)
replace_once(
    'zbemt/gui/tabs/config.py',
    '        form.addRow("Maximum outer iterations [-]:", self.cfg_pitt_peters_outer_iter)\n'
    '        form.addRow("Relaxation factor [-]:", self.cfg_pitt_peters_relax)\n'
    '        form.addRow("Convergence tolerance [-]:", self.cfg_pitt_peters_tol)\n'
    '        return box\n',
    '        form.addRow("Maximum outer iterations [-]:", self.cfg_pitt_peters_outer_iter)\n'
    '        form.addRow("Relaxation factor [-]:", self.cfg_pitt_peters_relax)\n'
    '        form.addRow("Convergence tolerance [-]:", self.cfg_pitt_peters_tol)\n'
    '        self.cfg_pitt_peters_time_march_revolutions = QSpinBox()\n'
    '        self.cfg_pitt_peters_time_march_revolutions.setRange(1, 500)\n'
    '        self.cfg_pitt_peters_time_march_revolutions.setToolTip(\n'
    '            "Number of constant-condition rotor revolutions marched before the periodic result is reported.")\n'
    '        self.cfg_pitt_peters_time_march_avg_last = QSpinBox()\n'
    '        self.cfg_pitt_peters_time_march_avg_last.setRange(1, 500)\n'
    '        self.cfg_pitt_peters_time_march_avg_last.setToolTip(\n'
    '            "Number of final revolutions averaged into the reported coefficients and azimuthal maps.")\n'
    '        self.cfg_pitt_peters_time_march_substeps_per_revolution = QSpinBox()\n'
    '        self.cfg_pitt_peters_time_march_substeps_per_revolution.setRange(1, 500)\n'
    '        self.cfg_pitt_peters_time_march_substeps_per_revolution.setToolTip(\n'
    '            "Pitt-Peters state-integration sub-steps inside each revolution.")\n'
    '        self.cfg_pitt_peters_time_march_initial_state = QComboBox()\n'
    '        self.cfg_pitt_peters_time_march_initial_state.addItem("Zero", "zero")\n'
    '        self.cfg_pitt_peters_time_march_initial_state.addItem("Equilibrium", "equilibrium")\n'
    '        self.cfg_pitt_peters_time_march_initial_state.setToolTip(\n'
    '            "Zero shows the inflow build-up transient. Equilibrium starts from the steady Pitt-Peters state and removes start-up lag.")\n'
    '        form.addRow("Dynamic march revolutions [-]:", self.cfg_pitt_peters_time_march_revolutions)\n'
    '        form.addRow("Average final revolutions [-]:", self.cfg_pitt_peters_time_march_avg_last)\n'
    '        form.addRow("State sub-steps / revolution [-]:", self.cfg_pitt_peters_time_march_substeps_per_revolution)\n'
    '        form.addRow("Dynamic initial state:", self.cfg_pitt_peters_time_march_initial_state)\n'
    '        self._pitt_peters_form = form\n'
    '        self._update_pitt_peters_dynamic_visibility()\n'
    '        return box\n',
)
replace_once(
    'zbemt/gui/tabs/config.py',
    '        self.cfg_pitt_peters_outer_iter.setValue(int(g("pitt_peters_outer_iter")))\n'
    '        self.cfg_pitt_peters_relax.setValue(float(g("pitt_peters_relax")))\n'
    '        self.cfg_pitt_peters_tol.setValue(float(g("pitt_peters_tol")))\n',
    '        self.cfg_pitt_peters_outer_iter.setValue(int(g("pitt_peters_outer_iter")))\n'
    '        self.cfg_pitt_peters_relax.setValue(float(g("pitt_peters_relax")))\n'
    '        self.cfg_pitt_peters_tol.setValue(float(g("pitt_peters_tol")))\n'
    '        self.cfg_pitt_peters_time_march_revolutions.setValue(\n'
    '            int(g("pitt_peters_time_march_revolutions")))\n'
    '        self.cfg_pitt_peters_time_march_avg_last.setValue(\n'
    '            int(g("pitt_peters_time_march_avg_last")))\n'
    '        self.cfg_pitt_peters_time_march_substeps_per_revolution.setValue(\n'
    '            int(g("pitt_peters_time_march_substeps_per_revolution")))\n'
    '        idx = self.cfg_pitt_peters_time_march_initial_state.findData(\n'
    '            str(g("pitt_peters_time_march_initial_state")))\n'
    '        self.cfg_pitt_peters_time_march_initial_state.setCurrentIndex(\n'
    '            idx if idx >= 0 else 0)\n'
    '        self._update_pitt_peters_dynamic_visibility()\n',
)
replace_once(
    'zbemt/gui/tabs/config.py',
    '            pitt_peters_outer_iter=self.cfg_pitt_peters_outer_iter.value(),\n'
    '            pitt_peters_relax=self.cfg_pitt_peters_relax.value(),\n'
    '            pitt_peters_tol=self.cfg_pitt_peters_tol.value(),\n',
    '            pitt_peters_outer_iter=self.cfg_pitt_peters_outer_iter.value(),\n'
    '            pitt_peters_relax=self.cfg_pitt_peters_relax.value(),\n'
    '            pitt_peters_tol=self.cfg_pitt_peters_tol.value(),\n'
    '            pitt_peters_time_march_revolutions=self.cfg_pitt_peters_time_march_revolutions.value(),\n'
    '            pitt_peters_time_march_avg_last=self.cfg_pitt_peters_time_march_avg_last.value(),\n'
    '            pitt_peters_time_march_substeps_per_revolution=self.cfg_pitt_peters_time_march_substeps_per_revolution.value(),\n'
    '            pitt_peters_time_march_initial_state=self.cfg_pitt_peters_time_march_initial_state.currentData(),\n',
)

# -----------------------------------------------------------------------------
# Field popup and block popup: correct the meaning of "dynamic" and explain
# fixed periodic march versus a changing maneuver.
# -----------------------------------------------------------------------------
replace_once(
    'zbemt/gui/help_content.py',
    '            "pitt_peters_unsteady": "Time-marching Pitt-Peters finite-state inflow; used by the maneuver/transient path, not an isolated case."\n',
    '            "pitt_peters_unsteady": "Dynamic Pitt-Peters time march. For an isolated case it marches a constant operating point for several revolutions and averages the settled revolutions; Maneuver is only needed when the prescribed condition changes with time."\n',
)
replace_once(
    'zbemt/gui/help_content.py',
    '            "Glauert is the axisymmetric annular-momentum reference. Coleman and Drees may couple their skewed-wake law locally or use one disk-wide wake condition; Coleman-Feingold is global only. Global variants close the radial mean inflow against the full two-dimensional disk loading."\n',
    '            "Glauert is the axisymmetric annular-momentum reference. Coleman and Drees may couple their skewed-wake law locally or use one disk-wide wake condition; Coleman-Feingold is global only. Global variants close the radial mean inflow against the full two-dimensional disk loading. Pitt-Peters has a steady equilibrium form and a genuinely dynamic time-marching form; the latter can run at one fixed case and does not require a maneuver."\n',
)
replace_once(
    'zbemt/gui/help_blocks.py',
    '            r"$$\\lambda_i(r,\\psi) = \\nu_0 + \\nu_c\\,x\\cos\\psi + \\nu_s\\,x\\sin\\psi$$"\n'
    '            "<i>\\\"Dynamic\\\"</i> here refers to the <b>disk</b> degrees of freedom, not to time — the steady variant does not march in time.",\n',
    '            r"$$\\lambda_i(r,\\psi) = \\nu_0 + \\nu_c\\,x\\cos\\psi + \\nu_s\\,x\\sin\\psi$$"\n'
    '            "<b>Dynamic is literal.</b> The full Pitt-Peters equations contain dν/dt. The Steady formulation sets that derivative to zero and solves the equilibrium. Dynamic (time march) integrates ν<sub>0</sub>, ν<sub>s</sub> and ν<sub>c</sub> in time.",\n',
)
replace_once(
    'zbemt/gui/help_blocks.py',
    '            "<br>A fixed point in 3 scalars, iterated with relaxation. <code>pitt_peters_outer_iter</code> caps the outer iterations, <code>pitt_peters_relax</code> damps the update, <code>pitt_peters_tol</code> tests ‖ν<sub>new</sub> − ν<sub>old</sub>‖<sub>∞</sub>.",\n'
    '            "The model solves the three states ν<sub>0</sub>, ν<sub>s</sub>, ν<sub>c</sub>. N<sub>ψ</sub> must be large enough to resolve the first harmonic cleanly (at least 24; 72 or more preferred).",\n',
    '            "<br>A fixed point in 3 scalars, iterated with relaxation. <code>pitt_peters_outer_iter</code> caps the outer iterations, <code>pitt_peters_relax</code> damps the update, <code>pitt_peters_tol</code> tests ‖ν<sub>new</sub> − ν<sub>old</sub>‖<sub>∞</sub>.",\n'
    '            "<b>Dynamic fixed case.</b> Run Case may select Dynamic (time march) without creating a maneuver. zBEMT holds μ, Vz, controls and rpm constant, advances the three inflow states for the configured number of revolutions, discards the start-up, and averages the configured final revolutions. The normal Results disk/azimuth plots then read the averaged r/ψ map, while the result dataframe retains the time history.",\n'
    '            "<b>Maneuver.</b> Use Transient Simulation only when the prescribed operating point itself changes with time. Each sample then inherits the previous sample\'s inflow state, which is the physics that a set of unrelated fixed cases cannot reproduce.",\n'
    '            "The model solves the three states ν<sub>0</sub>, ν<sub>s</sub>, ν<sub>c</sub>. N<sub>ψ</sub> must be large enough to resolve the first harmonic cleanly (at least 24; 72 or more preferred).",\n',
)

# -----------------------------------------------------------------------------
# Main HTML documentation: correct the old "dynamic is not time" statement,
# add fixed-case time march semantics and expose the unsteady enum in the table.
# -----------------------------------------------------------------------------
regex_once(
    'docs/documentation.html',
    r'<p class="boxed note"><b>A note on the word "dynamic"\.</b> Pitt-Peters is often called a\s*<i>dynamic inflow</i> model, and the name misleads\..*?</p>',
    '''<p class="boxed note"><b>Steady versus dynamic Pitt-Peters.</b> The word <i>dynamic</i> is literal.
                  The full finite-state equations contain time derivatives of the three inflow states
                  $\\boldsymbol{\\nu}=(\\nu_0,\\nu_s,\\nu_c)$. The <b>Steady</b> formulation sets
                  $\\dot{\\boldsymbol{\\nu}}=0$ and solves the equilibrium. The <b>Dynamic (time march)</b>
                  formulation integrates those states in time. A fixed Run Case does not need a maneuver:
                  zBEMT holds the flight condition and controls constant for several revolutions, discards the
                  start-up, and averages the configured final revolutions. Use a Maneuver only when the prescribed
                  flight condition or controls themselves change with time.</p>'''
)
replace_once(
    'docs/documentation.html',
    '                    <tr>\n'
    '                      <td id="cap-4-2-1-4"><code>pitt_peters_steady</code></td>\n'
    '                      <td>Three finite-state disk-level inflow states solved to equilibrium.</td>\n'
    '                      <td>Finite-state steady</td>\n'
    '                    </tr>\n',
    '                    <tr>\n'
    '                      <td id="cap-4-2-1-4"><code>pitt_peters_steady</code></td>\n'
    '                      <td>Three finite-state disk-level inflow states solved to equilibrium, with dν/dt = 0.</td>\n'
    '                      <td>Finite-state steady</td>\n'
    '                    </tr>\n'
    '                    <tr>\n'
    '                      <td><code>pitt_peters_unsteady</code></td>\n'
    '                      <td>Time integration of ν0, νs and νc. In Run Case the operating point is held constant for several revolutions and the final revolutions are averaged; in Maneuver the states are transported along the changing trajectory.</td>\n'
    '                      <td>Finite-state dynamic / time march</td>\n'
    '                    </tr>\n',
)
replace_once(
    'docs/documentation.html',
    '                  <code>pitt_peters_steady</code> when a finite-state disk model is desired instead of an empirical\n'
    '                  harmonic law. In hover, all skewed-wake gradients vanish and the Global empirical variants collapse\n',
    '                  <code>pitt_peters_steady</code> for the finite-state equilibrium, or\n'
    '                  <code>pitt_peters_unsteady</code> to time-march the same three states. A fixed dynamic case\n'
    '                  marches a constant operating point and averages the settled revolutions; a Maneuver is only\n'
    '                  required when the prescribed inputs vary with time. In hover, all skewed-wake gradients vanish and the Global empirical variants collapse\n',
)

# -----------------------------------------------------------------------------
# Regression test and suite manifest.
# -----------------------------------------------------------------------------
test_path = Path('tests/regression/test_pitt_peters_periodic_case.py')
test_path.write_text('''"""Fixed-condition dynamic Pitt-Peters does not require a maneuver."""
from __future__ import annotations

from dataclasses import replace
import unittest

import numpy as np

from zbemt import api, studies
from zbemt.models import FlightCondition


def _project(model: str, **extra):
    project = api.open_project("projects/starter_rotor")
    cfg = dict(project.config)
    cfg.update({
        "Ne": 16,
        "Npsi": 24,
        "use_compressibility": False,
        "inflow_field_model": model,
        "pitt_peters_outer_iter": 160,
        "pitt_peters_tol": 1e-8,
        "pitt_peters_time_march_revolutions": 8,
        "pitt_peters_time_march_avg_last": 3,
        "pitt_peters_time_march_substeps_per_revolution": 16,
        "pitt_peters_time_march_initial_state": "zero",
    })
    cfg.update(extra)
    return replace(project, config=cfg)


class TestPeriodicPittPetersCase(unittest.TestCase):
    def test_unsteady_run_case_returns_history_and_azimuthal_mean_map(self):
        result = studies.run_single_case(
            _project("pitt_peters_unsteady"),
            FlightCondition(name="hold", rpm=400.0, mu_x=0.12,
                            collective_deg=8.0),
        )
        self.assertIsNotNone(result.dataframe)
        self.assertEqual(len(result.dataframe), 9)  # t=0 plus 8 revolutions
        self.assertEqual(result.maps["lambda_i"].shape, (16, 24))
        self.assertTrue(np.all(np.isfinite(result.maps["lambda_i"])))
        self.assertEqual(result.summary["pitt_peters_time_march_revolutions"], 8)
        self.assertEqual(result.summary["pitt_peters_time_march_avg_last"], 3)
        self.assertIn("pitt_peters_time_march_state_residual", result.summary)

    def test_settled_dynamic_case_agrees_with_steady_equilibrium(self):
        condition = FlightCondition(name="hold", rpm=400.0, mu_x=0.10,
                                    collective_deg=8.0)
        dynamic = studies.run_single_case(
            _project("pitt_peters_unsteady",
                     pitt_peters_time_march_revolutions=14,
                     pitt_peters_time_march_avg_last=4,
                     pitt_peters_time_march_substeps_per_revolution=20),
            condition,
        )
        steady = studies.run_single_case(
            _project("pitt_peters_steady"), condition)
        self.assertLess(abs(float(dynamic.summary["CT"]) - float(steady.summary["CT"])), 5e-4)
        self.assertLess(abs(float(dynamic.summary["CQ"]) - float(steady.summary["CQ"])), 5e-4)

    def test_validation_allows_unsteady_case_and_rejects_bad_periodic_settings(self):
        project = _project("pitt_peters_unsteady")
        issues = api.validate_project(project)
        self.assertFalse(any(i.level == "error" for i in issues), issues)

        bad = replace(project, config={**project.config,
                                      "pitt_peters_time_march_avg_last": 99})
        issues = api.validate_project(bad)
        self.assertTrue(any(i.level == "error" and "avg_last" in i.message
                            for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
''', encoding='utf-8')

manifest = Path('tests/suite_manifest.json')
data = json.loads(manifest.read_text(encoding='utf-8'))
entry = 'tests/regression/test_pitt_peters_periodic_case.py'
if entry not in data['regression']:
    idx = data['regression'].index('tests/regression/test_pitt_peters_inflow.py') + 1
    data['regression'].insert(idx, entry)
manifest.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

print('Pitt-Peters fixed periodic case patch applied')
