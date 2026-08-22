"""Validate project inputs before aerodynamic execution.

The module checks airfoil definitions, engine configuration, and complete projects for
invalid, redundant, ignored, or risky combinations. It accepts model definitions and
engine settings and returns ``Issue`` records or aggregate validation results. The
public functions are ``validate_airfoil_def``, ``validate_config``, and
``validate_project``. ``api.py`` invokes them. The GUI and CLI layers present
their messages. Errors identify non-executable inputs, warnings identify questionable but
allowed inputs, and informational records identify settings ignored by the active
model. The checks are pure, do not access files, and cannot establish aerodynamic
accuracy or replace experimental validation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import AirfoilDef, uses_full_range_extension



@dataclass
class Issue:
    level: str    # "error" | "warning" | "info"
    message: str

    def __str__(self) -> str:
        tag = {"error": "[ERROR]", "warning": "[WARNING]", "info": "[INFO]"}.get(self.level, "[?]")
        return f"{tag} {self.message}"


# =============================================================================
# AirfoilDef: checks internal to the 2D object itself
# =============================================================================

def validate_airfoil_def(a: AirfoilDef) -> list[Issue]:
    issues: list[Issue] = []

    # --- dynamic stall requires a base polar that actually has stall -----
    # Øye interpolates between the attached (potential) Cl and the Cl
    # separated from the STATIC polar. Without stall in the base polar
    # ('linear' = pure line, no saturation), there is no "separation" at
    # all for the dynamic model to model. The result degenerates back to
    # the potential Cl, making the toggle deceptively harmless instead of
    # simply blocked. This is the ONLY dynamic stall rule derivable purely
    # from the `stall_model` enum (without inspecting any data). That is
    # why the GUI disables the dynamic stall checkbox in this case by
    # construction (docs/plano_v2.md Sections 2.2 and 2.5). The check here
    # is the safety net for the script/API path.
    if a.use_dynamic_stall and a.source == "analytical" and a.stall_model == "linear":
        issues.append(Issue("error",
            "Dynamic stall (Øye) enabled with analytical model 'linear' (no "
            "static stall): Øye interpolates between the potential Cl and the Cl "
            "separated from the static polar. Without stall in the base polar there is "
            "no separation to model, and the result degenerates silently "
            "back to linear model. Change 'Stall model' to "
            "'clip' or 'enhanced', or disable dynamic stall."))

    # --- source='external' has no execution path -----------------------
    # `airfoils.to_airfoil` raises NotImplementedError for 'external'.
    # Without this check the user only finds out in the middle of the
    # solve, with a raw traceback, and the previous validation treated
    # 'external' as a perfectly valid option.
    if a.source == "external":
        issues.append(Issue("error",
            "source='external' does not yet have an execution path in the engine "
            "(airfoils.to_airfoil raises NotImplementedError). Generate the external "
            "polar first (NeuralFoil) and import the result as "
            "source='table' with table_slices."))
    elif a.source not in ("analytical", "table"):
        issues.append(Issue("error",
            f"unknown source: {a.source!r}. Use 'analytical' or 'table'."))

    # --- stall_model unknown ------------------------------------------------
    if a.stall_model not in ("linear", "clip", "enhanced", "viterna"):
        issues.append(Issue("error",
            f"unknown stall_model: {a.stall_model!r}. Use 'linear', "
            "'clip', 'enhanced' or 'viterna'."))

    # --- extend_full_range only applies to analytical/table -----------------
    if a.extend_full_range and a.source not in ("analytical", "table"):
        issues.append(Issue("info",
            f"'extend_full_range' only has effect with source='analytical' or "
            f"'table' (current: '{a.source}'). This field is being ignored."))

    # --- extend_full_range is ignored for analytical source -------------------
    # Since Viterna became the 4th stall_model option (instead of an
    # orthogonal toggle), this field only has an effect for source='table'.
    # See models.uses_full_range_extension.
    if a.source == "analytical" and a.extend_full_range and a.stall_model != "viterna":
        issues.append(Issue("info",
            "'extend_full_range' is marked, but is ignored with "
            "source='analytical': choose stall_model='viterna' to activate "
            "full range extension."))

    # --- table source without any table imported ----------------------------
    if a.source == "table" and not a.table_slices:
        issues.append(Issue("error",
            "source='table' selected, but no polar was imported "
            "(table_slices empty). Import a CSV/DAT in block 'd'."))

    # --- extend_full_range + MULTI-SECTION table -----------------------------
    # Supported since the fix in bemt.ViternaExtendedAirfoil: when the
    # base airfoil is a MultiSectionTableAirfoil, the class now builds a
    # Viterna-Corrigan extrapolation PER radial section (each anchored on
    # its own Cl_stall/Cd_stall, rather than a single scalar alpha_stall
    # calling base.cl_cd() without r_norm, which was the real bug here,
    # because MultiSectionTableAirfoil.cl_cd requires r_norm). The per-section
    # result is then interpolated in r_norm, same as the pasted region. No
    # additional validation is required for this combination.

    # --- external engine without 2D profile geometry ------------------------
    if a.external_engine != "none" and a.geometry is None:
        issues.append(Issue("error",
            f"External engine '{a.external_engine}' selected, but no "
            "2D profile geometry was generated/imported (block 'e')."))

    # --- time_march parameters edited but active method is 'frequency' ----
    if (a.use_dynamic_stall and a.dynamic_stall_method != "time_march"
            and (a.dynamic_stall_time_march_revolutions != 8
                 or a.dynamic_stall_time_march_avg_last != 3)):
        issues.append(Issue("info",
            "'time_march' parameters (revolutions / average of last N) "
            "were changed, but the active dynamic stall method is "
            "'frequency'. They have no effect in this mode."))

    if a.use_dynamic_stall and a.dynamic_stall_fade_start_deg >= a.dynamic_stall_fade_end_deg:
        issues.append(Issue("error",
            "dynamic_stall_fade_start_deg must be less than "
            "dynamic_stall_fade_end_deg (invalid fade window)."))

    # --- stall angles with reversed sign ------------------------------------
    if a.stall_model != "linear" and (a.alpha_stall_neg_deg >= 0 or a.alpha_stall_pos_deg <= 0):
        issues.append(Issue("warning",
            "alpha_stall_pos_deg should be > 0 and alpha_stall_neg_deg < 0. "
            "The current values suggest that positive and negative stall are swapped."))

    # --- dynamic stall + table with no apparent sign of stall (heuristic) ---
    # Best-effort check (not structural, plano_v2 Section 2.2/4.2): it is only
    # answerable by looking at the CONTENT of table_slices, not an enum.
    # That is why the GUI cannot disable anything here at the moment the
    # user switches tabs, and this remains a warning, not an error.
    if a.use_dynamic_stall and a.source == "table" and a.table_slices:
        for s in a.table_slices:
            if len(s.cl) < 3:
                continue
            cl = s.cl
            idx_max = max(range(len(cl)), key=lambda i: abs(cl[i]))
            # if the peak of |Cl| is at one of the edges of the imported
            # range, the table probably does not cover real stall (it was
            # cut before saturating).
            if idx_max in (0, len(cl) - 1):
                issues.append(Issue("warning",
                    f"Dynamic stall enabled with source='table' (slice "
                    f"'{s.label or 'unlabeled'}'): the peak of |Cl| is at the "
                    "edge of the imported alpha range, suggesting that the "
                    "table may not contain real stall (was cut before "
                    "saturation). Øye may degenerate back to "
                    "potential in this range. Confirm that the table covers "
                    "saturation, or disable dynamic stall."))
                break

    return issues


# =============================================================================
# BEMTConfig <-> AirfoilDef: checks cross-referencing the two objects
# =============================================================================

def validate_config(config: dict, airfoil_def: AirfoilDef) -> list[Issue]:
    issues: list[Issue] = []

    inflow_field_model = config.get("inflow_field_model", "glauert_local")

    # --- reverse_flow_model='viterna_full_range' requires extended airfoil
    # The GUI ADDS the option to the dropdown when the full-range extension
    # is active (`airfoil._refresh_reverse_flow_options`). It does NOT
    # reduce the list to this single option, as this note used to claim.
    # The other four remain selectable on purpose: they are the comparison
    # that Section 8.2 of the manual offers. This check still applies to
    # the reverse path, which is indeed an error.
    reverse_flow_model = config.get("reverse_flow_model", "flat_plate")
    if reverse_flow_model == "viterna_full_range" and not uses_full_range_extension(airfoil_def):
        issues.append(Issue("error",
            "reverse_flow_model='viterna_full_range' requires active "
            "Viterna-Corrigan full-range extension. Without it the engine "
            "receives a non-extended polar and the result in the reverse "
            "flow region has no physical meaning. In the Airfoil tab, choose "
            "stall_model='viterna' (source 'analytical') or enable "
            "'Extrapolate table with Viterna-Corrigan' (source 'table'), or "
            "choose another reverse_flow_model."))

    # --- the reverse path is a WARNING, not an error -------------------------------
    # With the polar extended to ±180 there is real (extrapolated) data in
    # the reverse region. Any of the other four models THROWS THAT DATA
    # AWAY and puts a flat plate in its place. That is almost always not
    # what is wanted, hence the warning. Still, it is a legitimate choice
    # (comparing models, reproducing an old result), so forbidding it
    # would remove exactly the comparison that Section 8.2 of the manual
    # exists to offer.
    if reverse_flow_model != "viterna_full_range" and uses_full_range_extension(airfoil_def):
        issues.append(Issue("warning",
            f"The polar is extended to +/-180 deg (Viterna-Corrigan), but "
            f"reverse_flow_model='{reverse_flow_model}' replaces that data with a "
            "flat-plate-style model inside the reverse-flow region. The extrapolated "
            "polar already covers those angles, so 'viterna_full_range' is normally "
            "the consistent choice; keep the current one only if you are deliberately "
            "comparing reverse-flow treatments."))

    # --- pitt_peters_unsteady does not run per isolated case ----------------
    # `bemt.solve_bemt` raises ValueError for the unsteady variant:
    # it requires a TEMPORAL SEQUENCE (time_mu_Vv), which only
    # `run_sweep_unsteady_pitt_peters` assembles. Neither the GUI nor main_batch.py
    # constructs this sequence. Without this check, choosing the option was a
    # raw traceback in the middle of the solve.
    if inflow_field_model == "pitt_peters_unsteady":
        issues.append(Issue("error",
            "inflow_field_model='pitt_peters_unsteady' is the UNSTEADY variant: "
            "it requires a temporal sequence of flight conditions, which the "
            "case/batch path does not assemble (only `bemt.run_sweep_unsteady_pitt_peters` does). "
            "Use 'pitt_peters_steady'."))

    # --- pitt_peters_states: only implemented option is 3 ------------------
    pp_states = config.get("pitt_peters_states", 3)
    if pp_states not in (3, 5):
        issues.append(Issue("error", "pitt_peters_states must be 3 or 5."))
    elif pp_states == 5:
        issues.append(Issue("error",
            "pitt_peters_states=5 (Peters-He, 2nd harmonic) is not yet "
            "implemented in the engine. Use 3."))

    # --- double counting of compressibility (Finding #4, plan_v2 Section 2.1)
    # `use_compressibility` applies Prandtl-Glauert on top of the selected
    # polar; if the imported table already varies with Mach (one polar per
    # slice, `PolarSlice.mach` filled in more than one slice), the
    # "true" compressibility is already embedded in the polar chosen by
    # `_select_slice_for_condition`. Applying the empirical correction on top
    # is double counting compressibility. It is not structural (depends on
    # the CONTENT of table_slices, not just an enum), so it is a warning, not
    # something the GUI can disable by switching tabs.
    if config.get("use_compressibility", False) and airfoil_def.source == "table":
        has_mach_axis = sum(1 for s in airfoil_def.table_slices if s.mach is not None) > 1
        if has_mach_axis:
            issues.append(Issue("warning",
                "use_compressibility=True with a table that already varies with "
                "Mach (table_slices has more than one polar labeled by "
                "Mach): the polar selected in each condition is already "
                "compressible. Applying Prandtl-Glauert on top is "
                "'double counting', unless it is intentional (for example, "
                "a sensitivity study)."))

    # --- dynamic stall does not exist in UNSTEADY Pitt-Peters ----------
    # Finding #5 (plano_v2 Section 2.2/5.3): `run_sweep_unsteady_pitt_peters`
    # marches only 3 scalar degrees of freedom (nu0,nu_s,nu_c). Øye would
    # need a state per blade element (Ne*Npsi), a real structural
    # incompatibility with the current implementation. The GUI does not
    # prevent this today (they are different screens and objects, see
    # Section 5.3), so this check is the only guarantee.
    if inflow_field_model == "pitt_peters_unsteady" and airfoil_def.use_dynamic_stall:
        issues.append(Issue("error",
            "Dynamic stall (Øye) is not implemented in UNSTEADY Pitt-Peters mode "
            "('pitt_peters_unsteady'): this solver marches only 3 scalar DOF "
            "(nu0,nu_s,nu_c). Øye would need state per blade element (Ne*Npsi). "
            "Disable dynamic stall, or use 'pitt_peters_steady'."))

    # --- is_propeller changes the default of advance_kind, it is not exclusive
    # with anything by itself, but together with explicit mu_x/Vz in a condition
    # it can be confusing.
    if config.get("is_propeller", False) and airfoil_def.external_engine != "none":
        issues.append(Issue("info",
            "is_propeller=True does not affect external polar generation "
            "(NeuralFoil). Its only effect is on the BEMT non-dimensionalization."))

    return issues


def validate_airfoil_sections(sections: list[AirfoilDef]) -> list[Issue]:
    """Checks specific to multi-section airfoils (Phase D, docs/plano.md
    Section 4). Only relevant when ``Project.airfoil_sections`` has 2+
    elements. An empty list (single airfoil) does not go through here
    (see ``validate_project``)."""
    issues: list[Issue] = []
    if len(sections) == 1:
        issues.append(Issue("error",
            "airfoil_sections with exactly 1 element is not a valid state: "
            "use empty list (single airfoil, `airfoil` field) or 2+ sections."))
        return issues
    if len(sections) < 2:
        return issues

    seen_r: dict[float, str] = {}
    for s in sections:
        label = s.name or "(unlabeled)"
        if s.r_norm is None:
            issues.append(Issue("error",
                f"Section {label!r}: r_norm not defined. It is required with 2+ sections."))
            continue
        if not (0.0 <= s.r_norm <= 1.0):
            issues.append(Issue("warning",
                f"Section {label!r}: r_norm={s.r_norm:g} outside interval [0, 1]."))
        if s.r_norm in seen_r:
            issues.append(Issue("error",
                f"Sections {seen_r[s.r_norm]!r} and {label!r} have the same "
                f"r_norm={s.r_norm:g}. Each section needs a distinct radial position."))
        else:
            seen_r[s.r_norm] = label
        for issue in validate_airfoil_def(s):
            issues.append(Issue(issue.level, f"Section {label!r}: {issue.message}"))

    # Q4: dynamic stall's method and time march are properties of the
    # BLADE, not the section, because the engine marches once per solve.
    # Sections that disagree are not an illegal state (each still
    # turns its own stall on/off and has its own A), but the user needs
    # to know which value will prevail. Until now this passed silently.
    stall_sections = [s for s in sections if s.use_dynamic_stall]
    if len(stall_sections) >= 2:
        for field, label in (("dynamic_stall_method", "method"),
                             ("dynamic_stall_time_march_revolutions", "march revolutions"),
                             ("dynamic_stall_time_march_avg_last", "revolutions in average")):
            values = {getattr(s, field) for s in stall_sections}
            if len(values) > 1:
                winner = getattr(stall_sections[0], field)
                issues.append(Issue("warning",
                    f"Dynamic stall: sections disagree on {label} "
                    f"({sorted(map(str, values))}). This parameter applies to the entire blade. "
                    f"zBEMT will use {winner!r}, from the innermost section with dynamic stall enabled."))
    return issues


def validate_flight_condition(condition) -> list[Issue]:
    """Checks the RPM of a ``FlightCondition``. RPM is mandatory.

    Reason: the BEMT non-dimensionalizes everything by ``Omega*R``, so a
    zero RPM makes ``lambda_z = Vz/OmegaR`` turn into inf/nan and
    contaminate every map without raising any exception (today
    `bemt._check_rotor_rotation` blocks this, but the error only shows up
    in the middle of the solve). A missing RPM was even worse: it fell
    back to a 1000 RPM placeholder and produced a perfectly plausible-
    looking thrust from a made-up rotation, with nothing to give it away.
    The placeholder was removed. Both cases are now an error.

    This check is the *early* warning. `studies._require_rpm` is the
    hard guarantee, which raises at run time."""
    issues: list[Issue] = []
    rpm = getattr(condition, "rpm", None)

    if rpm is None:
        issues.append(Issue("error", (
            "Flight condition without RPM. The BEMT non-dimensionalizes everything "
            "by Omega*R, so rotation defines the entire problem scale (thrust, torque, "
            "tip Reynolds and Mach) and there is no physically defensible default. "
            "Provide the condition's RPM.")))
        return issues

    try:
        rpm_value = float(rpm)
    except (TypeError, ValueError):
        issues.append(Issue("error", f"RPM is not numeric: {rpm!r}."))
        return issues

    if not math.isfinite(rpm_value):
        issues.append(Issue("error", f"RPM is not finite: {rpm_value!r}."))
    elif rpm_value <= 0.0:
        issues.append(Issue("error", (
            f"RPM must be > 0 (received {rpm_value:g}). The BEMT non-dimensionalizes "
            "by Omega*R; with zero rotation the solution is undefined (division by zero "
            "in lambda_z = Vz/(Omega*R)).")))
    return issues


#: Above this Mach the Prandtl-Glauert correction stops being an
#: approximation and turns into an amplifier: the factor 1/sqrt(1-M^2) is
#: 1.4 at M=0.7, 2.3 at M=0.9 and diverges at M=1. The theory is
#: linearized and SUBSONIC. There is no shock in it, so nothing in the
#: model warns that the flow has stopped being what it describes.
_MACH_LIMITE_PRANDTL_GLAUERT = 0.85


def _validate_tip_mach(condition, radius_m: float, config: dict) -> list[Issue]:
    """Warns when the advancing blade tip goes past the regime in which
    this solver's airfoil models are valid.

    Found while running: an 8.18 m rotor at 600 RPM gives 514 m/s at the
    tip, Mach 1.51, and Mach 1.8 on the advancing side with mu_x=0.2.
    The compressibility correction then divides Cl by sqrt(1-M^2), which
    at two of the 7776 elements is worth approximately 0.004. Cl jumped to
    599, and the 99th percentile is 2.5. Nothing in the result gave it
    away. A good-looking CT came out, and the disk maps became unreadable.

    Warning, not error: running is still allowed, because the user may be
    precisely investigating the limit. But they now know they crossed
    the model's boundary instead of finding out from the plot.
    """
    issues: list[Issue] = []
    rpm = getattr(condition, "rpm", None)
    if rpm is None or not radius_m:
        return issues
    try:
        rpm_v, raio = float(rpm), float(radius_m)
    except (TypeError, ValueError):
        return issues
    a_som = float(config.get("a_sound", 340.29) or 340.29)
    if not (math.isfinite(rpm_v) and math.isfinite(raio) and a_som > 0):
        return issues

    omega_r = 2.0 * math.pi * rpm_v / 60.0 * raio
    mu_x = float(getattr(condition, "mu_x", 0.0) or 0.0)
    # ADVANCING blade tip (psi=90): the rotational speed adds to the
    # advance speed. It is the fastest point on the disk, and the first
    # to break the limit.
    mach_avancante = omega_r * (1.0 + abs(mu_x)) / a_som
    if mach_avancante <= _MACH_LIMITE_PRANDTL_GLAUERT:
        return issues

    detalhe = (f"advancing-tip Mach is {mach_avancante:.2f} "
               f"(tip speed {omega_r:.0f} m/s, speed of sound {a_som:.0f} m/s)")
    if mach_avancante >= 1.0:
        issues.append(Issue("warning", (
            f"Supersonic advancing tip: {detalhe}. The airfoil model here is "
            "subsonic: the Prandtl-Glauert factor 1/sqrt(1-M^2) diverges at "
            "M=1, so lift and drag near the tip are amplified without bound "
            "and are not physical. Lower the RPM or the rotor radius, or "
            "turn the compressibility correction off and read the tip region "
            "as invalid.")))
    else:
        issues.append(Issue("warning", (
            f"Transonic advancing tip: {detalhe}. Prandtl-Glauert is a "
            "linearized subsonic correction and loses validity above about "
            f"M={_MACH_LIMITE_PRANDTL_GLAUERT:g}; treat the outer span of the "
            "advancing side as approximate.")))
    return issues


def validate_project(config: dict, airfoil_def: AirfoilDef,
                      airfoil_sections: list[AirfoilDef] | None = None,
                      conditions=None, radius_m: float | None = None) -> list[Issue]:
    """Convenience: joins the lists above. Used by api.validate_project.

    If ``airfoil_sections`` has 2+ elements (multi-section airfoil, Phase
    D), ``airfoil_def`` (the usual single airfoil) is IGNORED for
    validation purposes. The engine also ignores it in that case (see
    ``airfoils.to_blade_airfoil``).

    ``conditions`` (optional): the ``FlightCondition``s that will be run.
    When given, each one goes through ``validate_flight_condition``, with
    the index/name in the ``Issue``'s field so the user knows which
    condition complained."""
    if airfoil_sections:
        issues = validate_airfoil_sections(airfoil_sections) + validate_config(config, airfoil_sections[0])
    else:
        issues = validate_airfoil_def(airfoil_def) + validate_config(config, airfoil_def)

    is_propeller = bool(config.get("is_propeller", False))
    for i, condition in enumerate(conditions or []):
        label = getattr(condition, "name", None) or f"#{i}"
        for issue in validate_flight_condition(condition):
            issues.append(Issue(issue.level, f"[condition {label}] {issue.message}"))
        for issue in _validate_propeller_convention(condition, is_propeller):
            issues.append(Issue(issue.level, f"[condition {label}] {issue.message}"))
        if radius_m:
            for issue in _validate_tip_mach(condition, radius_m, config):
                issues.append(Issue(issue.level, f"[condition {label}] {issue.message}"))
    return issues


def _validate_propeller_convention(condition, is_propeller: bool) -> list[Issue]:
    """The easiest mistake to make in propeller mode generates no error and
    produces just wrong results.

    ``mu_x`` is the velocity component IN THE PLANE of the disk: it is what makes the
    blade see ``+-V`` along the azimuth (advancing/retreating) and originates the
    reverse flow. The flight speed of a propeller in level flight is AXIAL,
    along the thrust axis: it goes in ``Vz``, with ``mu_x = 0``.

    Swapping the two gives a rotor edgewise condition that no propeller in level flight
    experiences. The classic symptom is propulsive efficiency above 1.

    It is a WARNING, not an error: a propeller with the axis tilted with respect to the wind
    (tilt-rotor in transition, propeller on an aircraft in sideslip) has both
    components true. What is flagged is the case where ALL the advance
    is in the plane and NOTHING on the axis, which is the signature of the swap."""
    if not is_propeller:
        return []
    mu_x = float(getattr(condition, "mu_x", 0.0) or 0.0)
    vv = float(getattr(condition, "Vz", 0.0) or 0.0)
    if abs(mu_x) > 1e-9 and abs(vv) <= 1e-9:
        return [Issue("warning",
            f"Project in propeller mode (is_propeller=True) with all advance in the "
            f"DISK PLANE (mu_x={mu_x:g}, shown as mu_z / V_inf,z in this mode) and none "
            f"along the shaft (Vz=0, shown as V_inf,x / mu_x / J_x). A propeller's "
            f"flight speed is axial: it goes in the 'Advance, axial (J_x)' field, with "
            f"the cross-flow at 0. As is, the blade sees +-V across azimuth, which a "
            f"propeller in level flight does not. The reported propulsive "
            f"efficiency will be meaningless. If axis tilt is intentional, also provide "
            f"the axial component (or give the tilt as alpha_disk, measured from the shaft, "
            f"which derives the cross-flow from it).")]
    return []
