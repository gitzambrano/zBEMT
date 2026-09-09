"""Define the user-visible axis and quantity nomenclature.

This pure data module supplies symbols, units, tooltips, slot names, visibility,
and serialized display keys for rotor and propeller modes. It accepts internal
engine keys, display-mode flags, and mathematical symbols; it returns labels,
renderings, and boundary key mappings. ``to_display_keys`` and
``from_display_keys`` perform one-pass conversion, while rendering helpers serve
the GUI, plots, reports, and CLI. The engine remains in disk axes; only user-facing
boundaries apply the rotor/propeller swap. A rotated mapping is output-only and must
not be passed back into the application. The module imports no Qt, plotting backend,
engine, filesystem, or argument parser.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# Signed flight-angle convention
# =============================================================================
# Vehicle V_z is positive when the free stream arrives from ABOVE. Both
# alpha_rotor and alpha_disk are positive when it arrives from BELOW. The
# engine remains in disk axes; these helpers translate only the user-facing
# convention at the interface boundary.

def alpha_rotor_axial_velocity(alpha_rotor_deg: float,
                                inplane_velocity: float) -> float:
    """Return rotor axial ``V_z`` from ``alpha_rotor`` and ``V_x``.

    Positive ``alpha_rotor`` means flow from below, so the returned ``V_z``
    is negative for a positive forward velocity.
    """
    return (-math.tan(math.radians(float(alpha_rotor_deg)))
            * float(inplane_velocity))


def alpha_rotor_from_components(axial_velocity: float,
                                inplane_velocity: float) -> float:
    """Return ``alpha_rotor`` [deg] from rotor-display velocity components.

    This preserves the established definition ``-atan2(V_z, V_x)``.
    """
    vz = float(axial_velocity)
    vx = float(inplane_velocity)
    if abs(vx) > 1e-12:
        return -math.degrees(math.atan2(vz, vx)) + 0.0
    if vz > 0.0:
        return -90.0
    if vz < 0.0:
        return 90.0
    return 0.0


def alpha_disk_cross_velocity(alpha_disk_deg: float,
                              axial_velocity: float) -> float:
    """Return propeller-display cross-flow ``V_z`` from ``alpha_disk``.

    Positive ``alpha_disk`` means flow from below. Positive display ``V_z``
    means flow from above. The signs are therefore opposite. The magnitude
    of the along-shaft component sets the scale, so reversing axial flow does
    not change which side of the disk the cross-flow comes from.
    """
    return (-math.tan(math.radians(float(alpha_disk_deg)))
            * abs(float(axial_velocity)))


def alpha_disk_from_components(cross_velocity: float,
                               axial_velocity: float) -> float:
    """Return propeller ``alpha_disk`` [deg] from display ``V_z`` and ``V_x``.

    The result is in [-90, 90]. Positive means flow from below; positive
    cross-flow ``V_z`` means flow from above and therefore gives a negative
    angle.
    """
    vz_cross = float(cross_velocity)
    vx_axial = abs(float(axial_velocity))
    if vx_axial > 1e-12:
        return math.degrees(math.atan2(-vz_cross, vx_axial)) + 0.0
    if vz_cross > 0.0:
        return -90.0
    if vz_cross < 0.0:
        return 90.0
    return 0.0


# =============================================================================
# The quantities
# =============================================================================

@dataclass(frozen=True)
class AxisQuantity:
    """One flow quantity, in both modes.

    `engine_key` is what `bemt.aggregate_results` emits and what
    `FlightCondition` stores in memory -- always disk axes, never rotated.
    Everything else is what the user sees, which depends on the mode.
    """

    engine_key: str
    #: `"inplane"` (in the disk plane), `"axial"` (along the shaft), or
    #: `"invariant"` (carries no axis letter: induced velocity,
    #: coefficients, collective, rpm).
    slot: str
    #: Symbol as a mathtext body, without the surrounding `$`.
    rotor_latex: str
    #: Same, in propeller axes. `None` means "does not rotate".
    propeller_latex: Optional[str] = None
    #: Key under which the quantity is written to disk / CSV / the results
    #: table in propeller mode. `None` means "does not rotate".
    propeller_key: Optional[str] = None
    unit: str = ""
    #: Suffix appended to the value in a condition NAME (`"°"`, `" m/s"`),
    #: which is tighter than the bracketed table unit.
    name_unit: str = ""
    rotor_visible: bool = True
    propeller_visible: bool = True
    #: Tooltip body, already in symbols (no snake_case field names).
    rotor_description: str = ""
    #: `None` reuses `rotor_description`.
    propeller_description: Optional[str] = None
    #: An input spelling of another quantity (`alpha_deg` is the input name
    #: of `alpha_rotor_deg`). Aliases share the output entry's symbols.
    alias_of: Optional[str] = None

    def latex(self, is_propeller: bool) -> str:
        if is_propeller and self.propeller_latex:
            return self.propeller_latex
        return self.rotor_latex

    def key(self, is_propeller: bool) -> str:
        if is_propeller and self.propeller_key:
            return self.propeller_key
        return self.engine_key

    def visible(self, is_propeller: bool) -> bool:
        return self.propeller_visible if is_propeller else self.rotor_visible

    def description(self, is_propeller: bool) -> str:
        if is_propeller and self.propeller_description is not None:
            return self.propeller_description
        return self.rotor_description


def _q(*args, **kwargs) -> AxisQuantity:
    return AxisQuantity(*args, **kwargs)


#: Every quantity whose name depends on the axis convention, keyed by the
#: ENGINE's name for it.
#:
#: Reading the table: a row says "the engine calls this X. The rotor user
#: reads it as Y. The propeller user reads it as Z". The `_x`/`_z` in the two
#: display columns are vehicle axes and swap between the two. The key on the
#: left never does.
_QUANTITIES: tuple = (
    # --- in-plane component (engine x) -------------------------------------
    _q("mu_x", "inplane", r"\mu_x", r"\mu_z", "mu_z", unit="-",
       rotor_description=(
           "Advance ratio along x: &mu;<sub>x</sub> = V<sub>x</sub>/(&Omega;R). "
           "In rotor mode x is the IN-PLANE direction, so this is the classic "
           "forward-flight advance ratio -- the component that sweeps across "
           "the blades and makes the advancing and retreating sides differ"),
       propeller_description=(
           "Advance ratio along z: &mu;<sub>z</sub> = V<sub>z</sub>/(&Omega;R), "
           "the cross-flow normalized by tip speed. Positive V<sub>z</sub> "
           "means the free stream arrives from ABOVE. This is the component "
           "that varies with azimuth and makes one side of the disk see more "
           "speed than the other. Zero in straight cruise")),
    _q("J_x", "inplane", r"J_x", r"J_z", "J_z", unit="-",
       rotor_description=(
           "Advance ratio along x in propeller form: J<sub>x</sub> = "
           "V<sub>x</sub>/(nD) = &pi;&middot;&mu;<sub>x</sub>"),
       propeller_description=(
           "Advance ratio along z in propeller form: J<sub>z</sub> = "
           "V<sub>z</sub>/(nD) = &pi;&middot;&mu;<sub>z</sub>. NOT the "
           "propeller advance ratio -- that one is J<sub>x</sub>, built from "
           "the airspeed along the shaft. This is the cross-flow, zero in "
           "straight cruise")),
    _q("Vx", "inplane", r"V_x", r"V_z", "Vz", unit="m/s", name_unit=" m/s",
       rotor_description=(
           "Free-stream component along x [m/s]. In rotor mode x is the "
           "IN-PLANE direction, so this is the horizontal flight speed -- what "
           "&mu;<sub>x</sub> and J<sub>x</sub> are built from"),
       propeller_description=(
           "Free-stream component along z [m/s]. In propeller mode z is "
           "VERTICAL, across the shaft and in the plane of the disk: the "
           "cross-flow. Positive V<sub>z</sub> means the free stream arrives "
           "from ABOVE. ZERO in straight cruise; non-zero when the propeller "
           "flies at an angle to its axis")),

    # --- lateral component (engine y, in the disk plane) --------------------
    # y is lateral in BOTH modes: the rotor disk holds x and y, the propeller
    # disk holds y and z, and y is the horizontal one of the pair either way.
    # So nothing here rotates -- there is no second letter to swap with.
    _q("Vy", "lateral", r"V_y", unit="m/s", name_unit=" m/s",
       rotor_description=(
           "Lateral free-stream component [m/s], in the disk plane and "
           "perpendicular to V<sub>x</sub>. It is what makes the flow arrive "
           "from the side instead of from straight ahead. Zero reproduces the "
           "plain edgewise case"),
       propeller_description=(
           "Lateral free-stream component [m/s], in the disk plane and "
           "perpendicular to V<sub>z</sub>. The propeller disk holds y and z, "
           "so y is the horizontal cross-flow. Zero in straight cruise")),
    _q("mu_y", "lateral", r"\mu_y", unit="-",
       rotor_description=(
           "Lateral advance ratio: &mu;<sub>y</sub> = V<sub>y</sub>/(&Omega;R), "
           "the sideways component normalized by tip speed")),
    _q("J_y", "lateral", r"J_y", unit="-",
       rotor_description=(
           "Lateral advance ratio in propeller form: J<sub>y</sub> = "
           "V<sub>y</sub>/(nD) = &pi;&middot;&mu;<sub>y</sub>")),

    # --- axial component (engine z) ----------------------------------------
    _q("mu_z", "axial", r"\mu_z", r"\mu_x", "mu_x", unit="-",
       rotor_description=(
           "Advance ratio along z: &mu;<sub>z</sub> = V<sub>z</sub>/(&Omega;R). "
           "In rotor mode z is the SHAFT direction. Positive V<sub>z</sub> "
           "means free stream arriving from ABOVE the rotor disk. Same number "
           "as &lambda;<sub>z</sub>, written in the advance-ratio vocabulary "
           "instead of the inflow one"),
       propeller_description=(
           "Advance ratio along x: &mu;<sub>x</sub> = V<sub>x</sub>/(&Omega;R), "
           "the airspeed normalized by tip speed. THE SAME NUMBER as "
           "&lambda;<sub>x</sub>, in the advance-ratio vocabulary")),
    _q("J_z", "axial", r"J_z", r"J_x", "J_x", unit="-",
       rotor_description=(
           "Advance ratio along z in propeller form: J<sub>z</sub> = "
           "V<sub>z</sub>/(nD) = &pi;&middot;&mu;<sub>z</sub>"),
       propeller_description=(
           "Advance ratio along x in propeller form: J<sub>x</sub> = "
           "V<sub>x</sub>/(nD) = &pi;&middot;&mu;<sub>x</sub>. THIS IS THE "
           "J<sub>x</sub> of propeller charts, built from the airspeed along "
           "the shaft, and the one propulsive efficiency uses")),
    _q("Vz", "axial", r"V_z", r"V_x", "Vx", unit="m/s", name_unit=" m/s",
       rotor_description=(
           "Free-stream component along z [m/s]. In rotor mode z is the SHAFT "
           "direction. Positive V<sub>z</sub> means the free stream arrives "
           "from ABOVE; negative means it arrives from BELOW. It is the FREE "
           "STREAM, not the flow through the disk -- that one is "
           "V<sub>z,total</sub>"),
       propeller_description=(
           "Free-stream component along x [m/s]. In propeller mode x is the "
           "SHAFT direction, so this is the aircraft's airspeed -- in straight "
           "cruise, the whole flight velocity. It is the FREE STREAM; the flow "
           "through the disk is V<sub>x,total</sub>")),
    _q("lambda_z", "axial", r"\lambda_z", r"\lambda_x", "lambda_x", unit="-",
       rotor_description=(
           "Inflow ratio along z, from the free stream alone: "
           "&lambda;<sub>z</sub> = V<sub>z</sub>/(&Omega;R). Positive is free "
           "stream arriving from ABOVE the rotor disk. It is an input datum, "
           "known before any aerodynamics. THE SAME NUMBER as "
           "&mu;<sub>z</sub>, in the inflow vocabulary instead of the "
           "advance-ratio one"),
       propeller_description=(
           "Inflow ratio along x, from the free stream alone: "
           "&lambda;<sub>x</sub> = V<sub>x</sub>/(&Omega;R). In propeller mode "
           "x is the shaft, so this is the axial inflow -- an input datum, "
           "known before any aerodynamics. THE SAME NUMBER as "
           "&mu;<sub>x</sub>, in the inflow vocabulary")),
    _q("Vz_total", "axial", r"V_{z,total}", r"V_{x,total}", "Vx_total",
       unit="m/s", name_unit=" m/s",
       rotor_description=(
           "Total velocity along the shaft, through the disk [m/s]: "
           "V<sub>z,total</sub> = V<sub>z</sub> + v<sub>i</sub>, disk-averaged. "
           "Free stream plus what the rotor adds. Written U<sub>P</sub> in the "
           "manual (Section 2.4.2)"),
       propeller_description=(
           "Total velocity along the shaft, through the disk [m/s]: "
           "V<sub>x,total</sub> = V<sub>x</sub> + v<sub>i</sub>, disk-averaged. "
           "The airspeed plus what the propeller adds. Written U<sub>P</sub> in "
           "the manual (Section 2.4.2)")),

    # --- the two user-facing flight angles ---------------------------------
    # They use different reference axes but the SAME wind-side sign:
    # positive means the free stream arrives from below. Each mode shows only
    # its own operational angle to avoid mixing the two definitions.
    _q("alpha_rotor_deg", "axial", r"\alpha_{rotor}", unit="deg", name_unit="°",
       propeller_visible=False,
       rotor_description=(
           "ROTOR angle of attack [deg], measured from the DISK PLANE: "
           "&alpha;<sub>rotor</sub> = -atan2(V<sub>z</sub>, V<sub>x</sub>). "
           "It is 0 in level forward flight, POSITIVE when the free stream "
           "arrives from below, and NEGATIVE when it arrives from above")),
    _q("alpha_disk_deg", "inplane", r"\alpha_{disk}", unit="deg", name_unit="°",
       rotor_visible=False,
       rotor_description=(
           "DISK angle of attack [deg], measured from the SHAFT in propeller "
           "vehicle axes: &alpha;<sub>disk</sub> = atan2(-V<sub>z</sub>, "
           "|V<sub>x</sub>|). It is 0 in straight axial cruise, POSITIVE when "
           "the free stream arrives from below, and NEGATIVE when it arrives "
           "from above. Positive propeller V<sub>z</sub> cross-flow therefore "
           "has the opposite sign to &alpha;<sub>disk</sub>")),

    # --- along the shaft in BOTH modes: no letter to rotate -----------------
    _q("Vi", "invariant", r"v_i", unit="m/s", name_unit=" m/s",
       rotor_description=(
           "Induced velocity [m/s], disk-averaged: the velocity the rotor adds "
           "along its own shaft. v<sub>i</sub> = "
           "&lambda;<sub>i</sub>&middot;(&Omega;R). It never changes axis with "
           "the mode -- only the letter naming that axis does")),
    _q("lambda_i", "invariant", r"\lambda_i", unit="-",
       rotor_description=(
           "Induced inflow ratio: &lambda;<sub>i</sub> = "
           "v<sub>i</sub>/(&Omega;R), the unknown solved by the BEMT fixed "
           "point. Area-weighted mean over the meshed span (root cutout to "
           "tip), not the whole geometric disk")),
    _q("lambda_total", "invariant", r"\lambda_{total}", unit="-",
       rotor_description=(
           "Total inflow ratio along the shaft: &lambda;<sub>total</sub> = "
           "&lambda;<sub>i</sub> + &lambda;<sub>z</sub> -- the free-stream part "
           "plus the induced part. Its dimensional counterpart is "
           "V<sub>z,total</sub> = &lambda;<sub>total</sub>&middot;(&Omega;R)"),
       propeller_description=(
           "Total inflow ratio along the shaft: &lambda;<sub>total</sub> = "
           "&lambda;<sub>i</sub> + &lambda;<sub>x</sub> -- the free-stream part "
           "plus the induced part. Its dimensional counterpart is "
           "V<sub>x,total</sub> = &lambda;<sub>total</sub>&middot;(&Omega;R)")),

    # --- blade dynamics (SC-11): flap and lead-lag response -----------------
    # Sign convention for the whole family: beta(psi) = beta_0 +
    # beta_1c*cos(psi) + beta_1s*sin(psi), positive up, and each
    # tip-path-plane tilt is the NEGATIVE of its first harmonic.
    _q("beta_0_deg", "invariant", r"\beta_0", unit="deg", name_unit="°",
       rotor_description=(
           "Coning angle [deg]: the mean flap angle &beta;<sub>0</sub>, the "
           "constant part of &beta;(&psi;) = &beta;<sub>0</sub> + "
           "&beta;<sub>1c</sub>cos&psi; + &beta;<sub>1s</sub>sin&psi;. Positive "
           "with the blades up. It grows with thrust and falls with the square "
           "of the flap frequency ratio")),
    _q("beta_1c_deg", "invariant", r"\beta_{1c}", unit="deg", name_unit="°",
       rotor_description=(
           "First cosine flap coefficient [deg]: the fore-aft 1/rev part of "
           "&beta;(&psi;). The longitudinal tip-path-plane tilt is its "
           "NEGATIVE (&theta;<sub>TPP,long</sub> = &minus;&beta;<sub>1c</sub>)")),
    _q("beta_1s_deg", "invariant", r"\beta_{1s}", unit="deg", name_unit="°",
       rotor_description=(
           "First sine flap coefficient [deg]: the lateral 1/rev part of "
           "&beta;(&psi;). The lateral tip-path-plane tilt is its NEGATIVE "
           "(&theta;<sub>TPP,lat</sub> = &minus;&beta;<sub>1s</sub>)")),
    _q("tpp_tilt_long_deg", "invariant", r"\theta_{TPP,long}", unit="deg",
       name_unit="°",
       rotor_description=(
           "Longitudinal tip-path-plane tilt [deg]: how far the disk tilts "
           "fore-aft under flapping, &theta;<sub>TPP,long</sub> = "
           "&minus;&beta;<sub>1c</sub>. Negative usually means the disk blows "
           "back relative to the shaft")),
    _q("tpp_tilt_lat_deg", "invariant", r"\theta_{TPP,lat}", unit="deg",
       name_unit="°",
       rotor_description=(
           "Lateral tip-path-plane tilt [deg]: how far the disk tilts sideways "
           "under flapping, &theta;<sub>TPP,lat</sub> = &minus;&beta;<sub>1s"
           "</sub>. On a rotor it reflects the classic response to the "
           "advancing/retreating load asymmetry")),
    _q("nu_beta", "invariant", r"\nu_\beta", unit="-",
       rotor_description=(
           "Flap frequency ratio: &nu;<sub>&beta;</sub><sup>2</sup> = 1 + "
           "(3/2)&middot;e/(1&minus;e) + K<sub>&beta;</sub>/(I<sub>&beta;</sub>"
           "&Omega;<sup>2</sup>). How far the first flap mode sits above the "
           "rotor rotation. An articulated rotor has exactly 1, which is why "
           "its first harmonic resonates")),
    _q("nu_zeta", "invariant", r"\nu_\zeta", unit="-",
       rotor_description=(
           "Lead-lag frequency ratio: &nu;<sub>&zeta;</sub><sup>2</sup> = "
           "(3/2)&middot;e/(1&minus;e) + K<sub>&zeta;</sub>/(I<sub>&zeta;</sub>"
           "&Omega;<sup>2</sup>). No leading 1: the lag freedom gets no "
           "restoring term from the thrust")),
    _q("lock_number", "invariant", r"\gamma", unit="-",
       rotor_description=(
           "Lock number: &gamma; = &rho;&middot;a&middot;c<sub>ref</sub>"
           "&middot;R<sup>4</sup>/I<sub>&beta;</sub>, the ratio of aerodynamic "
           "to inertial blade response, built from the chord at r/R = 0.75. "
           "It sets how strongly the air moves the blade")),
    _q("dynamic_stall_periodic_residual", "invariant", r"\Delta f_{periodic}",
       unit="-",
       rotor_description=(
           "Largest change of the Oye separation function between the last "
           "two marched revolutions. Near zero means the time march reached "
           "a periodic regime; a value above 1e-3 means the transient had "
           "NOT decayed and more revolutions are needed (EN-9). Only "
           "reported by the 'time_march' dynamic-stall method")),
    _q("dynamic_stall_revolutions", "invariant", r"N_{rev}", unit="-",
       rotor_description=(
           "Revolutions marched by the 'time_march' dynamic-stall method, "
           "echoed beside its periodic residual (EN-9)")),
    _q("flap_inertia_kg_m2", "invariant", r"I_\beta", unit="kg·m²",
       rotor_description=(
           "Resolved flap inertia of one blade about its hinge [kg·m²], "
           "whichever inertia source was chosen. It normalizes the flap "
           "moment in the harmonic balance")),
    _q("zeta_0_deg", "invariant", r"\zeta_0", unit="deg", name_unit="°",
       rotor_description=(
           "Mean lead-lag angle [deg]: the constant part of &zeta;(&psi;). "
           "Positive against the direction of rotation")),
    _q("zeta_1c_deg", "invariant", r"\zeta_{1c}", unit="deg", name_unit="°",
       rotor_description=(
           "First cosine lead-lag coefficient [deg] of "
           "&zeta;(&psi;) = &zeta;<sub>0</sub> + &zeta;<sub>1c</sub>cos&psi; + "
           "&zeta;<sub>1s</sub>sin&psi;")),
    _q("zeta_1s_deg", "invariant", r"\zeta_{1s}", unit="deg", name_unit="°",
       rotor_description=(
           "First sine lead-lag coefficient [deg] of "
           "&zeta;(&psi;)")),
    _q("Mx_hub", "invariant", r"M_{x,hub}", unit="N·m",
       rotor_description=(
           "Hub moment carried through the flap hinge or root spring [N·m], "
           "about the axis pointing to &psi;=0: (N<sub>b</sub>/2)"
           "&middot;I<sub>&beta;</sub>&Omega;<sup>2</sup>(&nu;<sub>&beta;</sub>"
           "<sup>2</sup>&minus;1)&beta;<sub>1c</sub>. This structural path is "
           "absent on a rigid-blade run and dominates on hingeless rotors")),
    _q("My_hub", "invariant", r"M_{y,hub}", unit="N·m",
       rotor_description=(
           "Hub moment carried through the flap hinge or root spring [N·m], "
           "about the &psi;=90&deg; axis: (N<sub>b</sub>/2)"
           "&middot;I<sub>&beta;</sub>&Omega;<sup>2</sup>(&nu;<sub>&beta;</sub>"
           "<sup>2</sup>&minus;1)&beta;<sub>1s</sub>")),
    _q("Mx_total", "invariant", r"M_{x,total}", unit="N·m",
       rotor_description=(
           "Total tilting moment about the &psi;=0 axis [N·m]: the "
           "aerodynamic moment M<sub>x</sub> plus the hub moment carried "
           "through the flap hinge or root spring M<sub>x,hub</sub>")),
    _q("My_total", "invariant", r"M_{y,total}", unit="N·m",
       rotor_description=(
           "Total tilting moment about the &psi;=90&deg; axis [N·m]: the "
           "aerodynamic moment M<sub>y</sub> plus the hub moment carried "
           "through the flap hinge or root spring M<sub>y,hub</sub>")),

    # --- the operating point's non-axis inputs ------------------------------
    _q("collective_deg", "invariant", r"\theta_0", unit="deg", name_unit="°",
       rotor_description=("Collective pitch [deg], added on top of the "
                           "built-in blade twist")),
    _q("cyclic_c_deg", "invariant", r"\theta_{1c}", unit="deg", name_unit="°",
       rotor_description=(
           "Cyclic pitch, cosine harmonic [deg]: pitch that varies once per "
           "revolution as &theta;<sub>1c</sub>cos&psi;. With flap freedom it "
           "tilts the blade response fore-aft and is one of the two controls "
           "the zero-flapping trim solves")),
    _q("cyclic_s_deg", "invariant", r"\theta_{1s}", unit="deg", name_unit="°",
       rotor_description=(
           "Cyclic pitch, sine harmonic [deg]: pitch that varies once per "
           "revolution as &theta;<sub>1s</sub>sin&psi;. Together with the "
           "cosine harmonic it forms the pair the trim solves")),
    _q("sideslip_deg", "lateral", r"\psi_w", unit="deg", name_unit="°",
       rotor_description=(
           "Sideslip angle [deg] of the in-plane free stream (SC-14): "
           "&psi;<sub>w</sub> = atan2(V<sub>y</sub>, V<sub>x</sub>), the "
           "direction the stream arrives from within the disk plane. It is "
           "the ANGLE SPELLING of V<sub>y</sub>: it splits the known "
           "longitudinal component into a lateral one, exactly as "
           "&alpha;<sub>rotor</sub> splits it into the axial one. The engine "
           "carries it as U<sub>T</sub> = &Omega;r + "
           "V&middot;sin(&psi;&minus;&psi;<sub>w</sub>). Zero reproduces the "
           "plain edgewise case"),
       propeller_description=(
           "Sideslip angle [deg] of the in-plane free stream (SC-14): "
           "&psi;<sub>w</sub> = atan2(V<sub>y</sub>, V<sub>z</sub>), the "
           "direction the stream arrives from within the disk plane. It is "
           "the ANGLE SPELLING of V<sub>y</sub>, which splits the known "
           "in-plane component into a lateral one. Zero reproduces the plain "
           "cross-flow case")),
    _q("p_rate_deg_s", "invariant", r"p", unit="deg/s",
       rotor_description=(
           "Hub roll rate [deg/s] (SC-14): carries every blade element out "
           "of the disk plane and forces the flap response gyroscopically")),
    _q("q_rate_deg_s", "invariant", r"q", unit="deg/s",
       rotor_description=(
           "Hub pitch rate [deg/s] (SC-14): same path as the roll rate, "
           "about the &psi;=0 axis; its hub moment is the pitch damping")),
    _q("rpm", "invariant", r"RPM", unit="rev/min",
       rotor_description=(
           "Rotational speed of the rotor for this condition [rev/min] -- the "
           "value the solver actually ran with. Same quantity as "
           "RPM<sub>rotor</sub> (the engine's own echo of it), which is "
           "therefore hidden from the table whenever the two agree")),

    # --- input spellings of the two angles ---------------------------------
    # `studies` and the GUI name the angles `alpha_deg`/`alpha_disk` when they
    # are an INPUT. `aggregate_results` emits them as `alpha_rotor_deg`/
    # `alpha_disk_deg`. Same quantity, same symbol, two spellings.
    _q("alpha_deg", "axial", r"\alpha_{rotor}", unit="deg", name_unit="°",
       propeller_visible=False, alias_of="alpha_rotor_deg"),
    _q("alpha_disk", "inplane", r"\alpha_{disk}", unit="deg", name_unit="°",
       rotor_visible=False, alias_of="alpha_disk_deg"),
)

#: `engine_key -> AxisQuantity`, the table every surface reads.
QUANTITIES: dict = {q.engine_key: q for q in _QUANTITIES}

#: Higher flap harmonics (n = 2..MAX_FLAP_HARMONICS), registered here so a
#: `beta_2c_deg` column carries the same rendered symbol and unit as the
#: first-harmonic ones instead of falling back to its raw key. The GUI caps
#: the harmonic count at MAX_FLAP_HARMONICS.
MAX_FLAP_HARMONICS = 5
for _n in range(2, MAX_FLAP_HARMONICS + 1):
    QUANTITIES[f"beta_{_n}c_deg"] = AxisQuantity(
        engine_key=f"beta_{_n}c_deg", slot="invariant",
        rotor_latex=rf"\beta_{{{_n}c}}",
        unit="deg",
        rotor_description=(
            f"Cosine flap coefficient of harmonic {_n} [deg], from the "
            "harmonic balance of &beta;(&psi;) = &beta;<sub>0</sub> + "
            "&Sigma;<sub>n</sub>[&beta;<sub>nc</sub>cos(n&psi;) + "
            "&beta;<sub>ns</sub>sin(n&psi;)]"))
    QUANTITIES[f"beta_{_n}s_deg"] = AxisQuantity(
        engine_key=f"beta_{_n}s_deg", slot="invariant",
        rotor_latex=rf"\beta_{{{_n}s}}",
        unit="deg",
        rotor_description=(
            f"Sine flap coefficient of harmonic {_n} [deg], from the "
            "harmonic balance of &beta;(&psi;)."))
del _n

for _quantity in _QUANTITIES:
    if _quantity.alias_of:
        _source = QUANTITIES[_quantity.alias_of]
        QUANTITIES[_quantity.engine_key] = AxisQuantity(
            **{**_quantity.__dict__,
               "rotor_description": _source.rotor_description,
               "propeller_description": _source.propeller_description})
del _quantity


# =============================================================================
# One LaTeX source -> three renderings
# =============================================================================

_GREEK_UNICODE = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν",
    r"\pi": "π", r"\rho": "ρ", r"\sigma": "σ", r"\phi": "φ",
    r"\psi": "ψ", r"\omega": "ω", r"\Omega": "Ω", r"\eta": "η",
    r"\zeta": "ζ", r"\Delta": "Δ",
    r"\infty": "∞", r"\cdot": "·", r"\times": "×", r"\pm": "±",
    r"\circ": "°",
}

_GREEK_HTML = {
    r"\alpha": "&alpha;", r"\beta": "&beta;", r"\gamma": "&gamma;",
    r"\delta": "&delta;", r"\theta": "&theta;", r"\lambda": "&lambda;",
    r"\mu": "&mu;", r"\nu": "&nu;", r"\pi": "&pi;", r"\rho": "&rho;",
    r"\sigma": "&sigma;", r"\phi": "&phi;", r"\psi": "&psi;",
    r"\omega": "&omega;", r"\Omega": "&Omega;", r"\eta": "&eta;",
    r"\zeta": "&zeta;", r"\Delta": "&Delta;",
    r"\infty": "&infin;", r"\cdot": "&middot;", r"\times": "&times;",
    r"\pm": "&plusmn;", r"\circ": "&deg;",
}

_SUBSCRIPT_UNICODE = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
    "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ",
    "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}

_SUBSCRIPT = re.compile(r"_\{([^}]*)\}|_(\\[a-zA-Z]+|\w)")
_SUPERSCRIPT = re.compile(r"\^\{([^}]*)\}|\^(\\[a-zA-Z]+|\w)")

_SUPERSCRIPT_UNICODE = {
    "0": "\u2070", "1": "\u00b9", "2": "\u00b2", "3": "\u00b3",
    "4": "\u2074", "5": "\u2075", "6": "\u2076", "7": "\u2077",
    "8": "\u2078", "9": "\u2079", "+": "\u207a", "-": "\u207b",
    "n": "\u207f", "i": "\u2071",
}

_OVERBAR = re.compile(r"\\bar\{([^}]*)\}|\\bar(\\[a-zA-Z]+|\w)")
_COMBINING_MACRON = "\u0304"


def _overbar(text: str) -> str:
    """Replaces every overbar group by its body plus a combining macron."""
    def repl(match):
        body = match.group(1) if match.group(1) is not None else match.group(2)
        return (body + _COMBINING_MACRON) if body else ""
    return _OVERBAR.sub(repl, text)


def _superscript_unicode(text: str) -> str:
    """Raises a superscript only when every character has a raised form."""
    if not text:
        return text
    if all(c in _SUPERSCRIPT_UNICODE for c in text):
        return "".join(_SUPERSCRIPT_UNICODE[c] for c in text)
    return "^" + text


def _subscript_unicode(text: str, lower: str = "all") -> str:
    """Lowers a subscript only when every character has a subscript form."""
    if not text:
        return text
    if lower == "none":
        return f"_{text}"
    if lower == "digits":
        return ("".join(_SUBSCRIPT_UNICODE[c] for c in text) if text.isdigit()
                else f"_{text}")
    if all(c in _SUBSCRIPT_UNICODE for c in text):
        return "".join(_SUBSCRIPT_UNICODE[c] for c in text)
    return text


def _is_mathtext(text: str) -> bool:
    return "$" in text or "\\" in text


def _needs_math(body: str) -> bool:
    return "\\" in body or "_" in body or "^" in body


def to_unicode(mathtext: str, lower_subscripts: str = "all") -> str:
    """Plain-text Unicode rendering of a mathtext body or label."""
    if not mathtext:
        return ""
    if not _is_mathtext(mathtext):
        return mathtext
    text = _overbar(mathtext)
    text = re.sub(_SUBSCRIPT,
                  lambda m: _subscript_unicode(
                      m.group(1) if m.group(1) is not None else m.group(2),
                      lower_subscripts),
                  text)
    text = re.sub(_SUPERSCRIPT,
                  lambda m: _superscript_unicode(
                      m.group(1) if m.group(1) is not None else m.group(2)),
                  text)
    for macro, symbol in _GREEK_UNICODE.items():
        text = text.replace(macro + " ", symbol).replace(macro, symbol)
    text = text.replace(r"\,", " ").replace(r"\ ", " ")
    text = text.replace("$", "").replace("{", "").replace("}", "")
    return text.strip()


def to_html(mathtext: str) -> str:
    """HTML rendering, with real subscript and superscript tags."""
    if not mathtext:
        return ""
    if not _is_mathtext(mathtext):
        return mathtext
    text = _overbar(mathtext)
    text = re.sub(_SUBSCRIPT,
                  lambda m: "<sub>%s</sub>" % (m.group(1)
                                                if m.group(1) is not None
                                                else m.group(2)),
                  text)
    text = re.sub(_SUPERSCRIPT,
                  lambda m: "<sup>%s</sup>" % (m.group(1)
                                                if m.group(1) is not None
                                                else m.group(2)),
                  text)
    for macro, entity in _GREEK_HTML.items():
        text = text.replace(macro + " ", entity).replace(macro, entity)
    text = text.replace(r"\,", " ").replace(r"\ ", " ")
    text = text.replace("$", "").replace("{", "").replace("}", "")
    return text.strip()


def to_mathtext(latex: str, unit: str = "") -> str:
    """A mathtext body plus its bracketed unit, the form matplotlib draws."""
    body = f"${latex}$" if _needs_math(latex) else latex
    return f"{body} [{unit}]" if unit else body


# =============================================================================
# Accessors -- what every surface calls instead of keeping its own table
# =============================================================================

def quantity(engine_key: str) -> Optional[AxisQuantity]:
    q = QUANTITIES.get(engine_key)
    return q


def symbol_latex(engine_key: str, is_propeller: bool = False) -> str:
    q = QUANTITIES.get(engine_key)
    return q.latex(is_propeller) if q else engine_key


def symbol_mathtext(engine_key: str, is_propeller: bool = False) -> str:
    q = QUANTITIES.get(engine_key)
    if q is None:
        return engine_key
    return to_mathtext(q.latex(is_propeller), q.unit)


def symbol_html(engine_key: str, is_propeller: bool = False) -> str:
    q = QUANTITIES.get(engine_key)
    return to_html(_as_mathtext(q.latex(is_propeller))) if q else engine_key


def symbol_text(engine_key: str, is_propeller: bool = False) -> str:
    q = QUANTITIES.get(engine_key)
    return to_unicode(_as_mathtext(q.latex(is_propeller))) if q else engine_key


def symbol_name(engine_key: str, is_propeller: bool = False) -> str:
    q = QUANTITIES.get(engine_key)
    if q is None:
        return engine_key
    return to_unicode(_as_mathtext(q.latex(is_propeller)),
                      lower_subscripts="digits")


def _as_mathtext(body: str) -> str:
    return f"${body}$" if _needs_math(body) else body


def unit(engine_key: str) -> str:
    q = QUANTITIES.get(engine_key)
    return q.unit if q else ""


def description_html(engine_key: str, is_propeller: bool = False) -> str:
    q = QUANTITIES.get(engine_key)
    return q.description(is_propeller) if q else ""


def is_visible(engine_key: str, is_propeller: bool = False) -> bool:
    q = QUANTITIES.get(engine_key)
    return q.visible(is_propeller) if q else True


def slot_of(engine_key: str) -> str:
    q = QUANTITIES.get(engine_key)
    return q.slot if q else "invariant"


def variables_in_slot(slot: str, is_propeller: bool = False) -> tuple:
    return tuple(q.engine_key for q in _QUANTITIES
                 if q.slot == slot and q.visible(is_propeller))


# --- the key rotation --------------------------------------------------------

def display_key(engine_key: str, is_propeller: bool = False) -> str:
    q = QUANTITIES.get(engine_key)
    return q.key(is_propeller) if q else engine_key


_ENGINE_KEY_OF = {
    True: {q.key(True): q.engine_key for q in _QUANTITIES if not q.alias_of},
    False: {q.key(False): q.engine_key for q in _QUANTITIES if not q.alias_of},
}


def engine_key_of(display: str, is_propeller: bool = False) -> str:
    return _ENGINE_KEY_OF[bool(is_propeller)].get(display, display)


def to_display_keys(mapping: dict, is_propeller: bool = False) -> dict:
    if not is_propeller:
        return dict(mapping)
    return {display_key(key, True): value for key, value in mapping.items()}


def from_display_keys(mapping: dict, is_propeller: bool = False) -> dict:
    if not is_propeller:
        return dict(mapping)
    return {engine_key_of(key, True): value for key, value in mapping.items()}


# =============================================================================
# The input slots, as the user meets them
# =============================================================================
_SLOT_LABELS = {
    ("inplane", False): (
        "Edgewise (in-plane) Flow:",
        "The horizontal component of the flight velocity, V<sub>x</sub>. On a "
        "rotor the shaft is vertical, so x lies IN THE PLANE OF THE DISK: this "
        "is THE ADVANCE, the component that sweeps across the blades and makes "
        "the advancing and retreating sides differ.\n\n"
        "Units offered: &mu;<sub>x</sub> = V<sub>x</sub>/(&Omega;R), "
        "J<sub>x</sub> = V<sub>x</sub>/(nD) = &pi;&middot;&mu;<sub>x</sub>, and "
        "the dimensional speed V<sub>x</sub> [m/s]. The vertical component "
        "V<sub>z</sub> is the field below."),
    ("axial", False): (
        "Axial (along-shaft) Flow:",
        "The vertical free-stream component V<sub>z</sub>. Positive "
        "V<sub>z</sub> means wind arriving from ABOVE the rotor disk; negative "
        "means wind arriving from BELOW.\n\n"
        "Units offered: &alpha;<sub>rotor</sub> [deg], V<sub>z</sub> [m/s], "
        "&mu;<sub>z</sub> = V<sub>z</sub>/(&Omega;R), and "
        "J<sub>z</sub> = V<sub>z</sub>/(nD).\n\n"
        "&alpha;<sub>rotor</sub> = -atan2(V<sub>z</sub>, V<sub>x</sub>) is "
        "measured from the disk plane. It is POSITIVE when the free stream "
        "arrives from BELOW and NEGATIVE when it arrives from ABOVE."),
    ("inplane", True): (
        "Cross (in-plane) Flow:",
        "The propeller cross-flow V<sub>z</sub>, in the disk plane. Positive "
        "V<sub>z</sub> means the free stream arrives from ABOVE; negative "
        "means it arrives from BELOW. In straight cruise V<sub>z</sub> = 0.\n\n"
        "Units offered: V<sub>z</sub> [m/s], &alpha;<sub>disk</sub> [deg], "
        "&mu;<sub>z</sub> = V<sub>z</sub>/(&Omega;R), or J<sub>z</sub> = "
        "V<sub>z</sub>/(nD).\n\n"
        "&alpha;<sub>disk</sub> = atan2(-V<sub>z</sub>, |V<sub>x</sub>|), "
        "measured from the shaft. It is POSITIVE when the free stream arrives "
        "from BELOW, so its sign is opposite to propeller V<sub>z</sub>."),
    ("lateral", False): (
        "Lateral (in-plane, sideways) Flow:",
        "The sideways component of the flight velocity, V<sub>y</sub>. The "
        "rotor disk holds x and y, so this component also lies IN THE PLANE "
        "OF THE DISK, at a right angle to the edgewise flow above. It is what "
        "makes the stream arrive from the side: sideward flight, or a "
        "helicopter flying with sideslip.\n\n"
        "Units offered: &psi;<sub>w</sub> [deg], V<sub>y</sub> [m/s], "
        "&mu;<sub>y</sub> = V<sub>y</sub>/(&Omega;R), and J<sub>y</sub> = "
        "V<sub>y</sub>/(nD).\n\n"
        "&psi;<sub>w</sub> = atan2(V<sub>y</sub>, V<sub>x</sub>) is the "
        "SIDESLIP ANGLE, measured in the disk plane from the edgewise "
        "direction: 0&deg; is flight straight ahead, and 90&deg; is pure "
        "sideward flight."),
    ("lateral", True): (
        "Lateral (in-plane, sideways) Flow:",
        "The sideways component of the flight velocity, V<sub>y</sub>. The "
        "propeller disk holds y and z, so this component lies IN THE PLANE OF "
        "THE DISK, at a right angle to the cross-flow above. Together the two "
        "give the propeller a stream that arrives off its shaft from any "
        "direction. Zero in straight cruise.\n\n"
        "Units offered: &psi;<sub>w</sub> [deg], V<sub>y</sub> [m/s], "
        "&mu;<sub>y</sub> = V<sub>y</sub>/(&Omega;R), and J<sub>y</sub> = "
        "V<sub>y</sub>/(nD).\n\n"
        "&psi;<sub>w</sub> = atan2(V<sub>y</sub>, V<sub>z</sub>) is the "
        "SIDESLIP ANGLE, measured in the disk plane."),
    ("axial", True): (
        "Axial (along-shaft) Flow:",
        "The horizontal component of the flight velocity, V<sub>x</sub>: the "
        "aircraft's AIRSPEED. On a propeller the shaft is horizontal, so x runs "
        "ALONG THE SHAFT, and the engine adds the induced velocity to it to "
        "form V<sub>x,total</sub> = V<sub>x</sub> + v<sub>i</sub>.\n\n"
        "THIS IS THE PROPELLER'S ADVANCE RATIO. The default unit J<sub>x</sub> "
        "is the classic one of the propeller charts, J<sub>x</sub> = V/(nD), "
        "built from the AXIAL airspeed.\n\n"
        "Units offered: J<sub>x</sub>, &mu;<sub>x</sub> = J<sub>x</sub>/&pi; = "
        "V<sub>x</sub>/(&Omega;R), and V<sub>x</sub> [m/s]. The angle lives in "
        "the cross-flow field above, measured from the shaft "
        "(&alpha;<sub>disk</sub>)."),
}


def slot_label(slot: str, is_propeller: bool = False) -> tuple:
    return _SLOT_LABELS[(slot, bool(is_propeller))]


# =============================================================================
# Reading order of the operating point
# =============================================================================
_PRIMARY_ROTOR = (
    "mu_x", "J_x", "Vx",
    "Vy", "mu_y", "J_y", "sideslip_deg",
    "mu_z", "J_z", "Vz", "lambda_z",
    "alpha_rotor_deg", "alpha_disk_deg",
    "collective_deg", "rpm",
)

_PRIMARY_PROPELLER = (
    "mu_z", "J_z", "Vz", "lambda_z",
    "mu_x", "J_x", "Vx",
    "Vy", "mu_y", "J_y", "sideslip_deg",
    "alpha_disk_deg", "alpha_rotor_deg",
    "collective_deg", "rpm",
)


def primary_order(is_propeller: bool = False) -> tuple:
    order = _PRIMARY_PROPELLER if is_propeller else _PRIMARY_ROTOR
    return tuple(c for c in order if is_visible(c, is_propeller))


# =============================================================================
# Naming a condition
# =============================================================================

def condition_label(values: dict, is_propeller: bool = False) -> str:
    """Readable name for a condition from its ``{variable: value}`` mapping."""
    parts = []
    for key, value in values.items():
        q = QUANTITIES.get(key)
        symbol = symbol_name(key, is_propeller) if q else key
        suffix = q.name_unit if q else ""
        try:
            text = f"{float(value):g}"
        except (TypeError, ValueError):
            text = str(value)
        parts.append(f"{symbol}={text}{suffix}")
    return ", ".join(parts)
