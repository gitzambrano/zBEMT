"""Apply the flight-angle sign convention update to the working tree.

This temporary migration helper is idempotent. It exists only to make the
multi-file convention change reproducible in CI before the final branch is
promoted to main.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _path(name: str) -> Path:
    return ROOT / name


def replace_once(name: str, old: str, new: str) -> None:
    path = _path(name)
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{name}: expected one old fragment, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def replace_all(name: str, old: str, new: str, expected: int) -> None:
    path = _path(name)
    text = path.read_text(encoding="utf-8")
    if old not in text and new in text:
        return
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{name}: expected {expected} old fragments, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def replace_block(name: str, start: str, end: str, new_block: str,
                  marker: str) -> None:
    path = _path(name)
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    i = text.find(start)
    if i < 0:
        raise RuntimeError(f"{name}: start marker not found: {start!r}")
    j = text.find(end, i)
    if j < 0:
        raise RuntimeError(f"{name}: end marker not found: {end!r}")
    path.write_text(text[:i] + new_block + text[j:], encoding="utf-8")


# ---------------------------------------------------------------------------
# One canonical user-facing convention, owned by nomenclature.py (AR-5).
# ---------------------------------------------------------------------------
replace_once(
    "zbemt/nomenclature.py",
    "import re\nfrom dataclasses import dataclass",
    "import math\nimport re\nfrom dataclasses import dataclass",
)

_helpers = '''\n\n# =============================================================================\n# Signed flight-angle convention\n# =============================================================================\n# Vehicle V_z is positive when the free stream arrives from ABOVE. Both\n# alpha_rotor and alpha_disk are positive when it arrives from BELOW. The\n# engine remains in disk axes; these helpers translate only the user-facing\n# convention at the interface boundary.\n\ndef alpha_rotor_axial_velocity(alpha_rotor_deg: float,\n                                inplane_velocity: float) -> float:\n    \"\"\"Return rotor axial ``V_z`` from ``alpha_rotor`` and ``V_x``.\n\n    Positive ``alpha_rotor`` means flow from below, so the returned ``V_z``\n    is negative for a positive forward velocity.\n    \"\"\"\n    return (-math.tan(math.radians(float(alpha_rotor_deg)))\n            * float(inplane_velocity))\n\n\ndef alpha_rotor_from_components(axial_velocity: float,\n                                inplane_velocity: float) -> float:\n    \"\"\"Return ``alpha_rotor`` [deg] from rotor-display velocity components.\n\n    This preserves the established definition ``-atan2(V_z, V_x)``.\n    \"\"\"\n    vz = float(axial_velocity)\n    vx = float(inplane_velocity)\n    if abs(vx) > 1e-12:\n        return -math.degrees(math.atan2(vz, vx)) + 0.0\n    if vz > 0.0:\n        return -90.0\n    if vz < 0.0:\n        return 90.0\n    return 0.0\n\n\ndef alpha_disk_cross_velocity(alpha_disk_deg: float,\n                              axial_velocity: float) -> float:\n    \"\"\"Return propeller-display cross-flow ``V_z`` from ``alpha_disk``.\n\n    Positive ``alpha_disk`` means flow from below. Positive display ``V_z``\n    means flow from above. The signs are therefore opposite. The magnitude\n    of the along-shaft component sets the scale, so reversing axial flow does\n    not change which side of the disk the cross-flow comes from.\n    \"\"\"\n    return (-math.tan(math.radians(float(alpha_disk_deg)))\n            * abs(float(axial_velocity)))\n\n\ndef alpha_disk_from_components(cross_velocity: float,\n                               axial_velocity: float) -> float:\n    \"\"\"Return propeller ``alpha_disk`` [deg] from display ``V_z`` and ``V_x``.\n\n    The result is in [-90, 90]. Positive means flow from below; positive\n    cross-flow ``V_z`` means flow from above and therefore gives a negative\n    angle.\n    \"\"\"\n    vz_cross = float(cross_velocity)\n    vx_axial = abs(float(axial_velocity))\n    if vx_axial > 1e-12:\n        return math.degrees(math.atan2(-vz_cross, vx_axial)) + 0.0\n    if vz_cross > 0.0:\n        return -90.0\n    if vz_cross < 0.0:\n        return 90.0\n    return 0.0\n\n'''
replace_once(
    "zbemt/nomenclature.py",
    "\n\n# =============================================================================\n# The quantities\n# =============================================================================\n",
    _helpers + "\n# =============================================================================\n# The quantities\n# =============================================================================\n",
)
replace_once(
    "zbemt/nomenclature.py",
    '"DISK PLANE, &alpha;<sub>rotor</sub> = atan2(V<sub>z</sub>, "\n           "V<sub>x</sub>). This is THE angle of rotor mode -- 0 in a "',
    '"DISK PLANE, &alpha;<sub>rotor</sub> = -atan2(V<sub>z</sub>, "\n           "V<sub>x</sub>). This is THE angle of rotor mode -- 0 in a "',
)
replace_once(
    "zbemt/nomenclature.py",
    '"SHAFT, &alpha;<sub>disk</sub> = 90 - &alpha;<sub>rotor</sub>. This "\n           "is THE angle of propeller mode -- 0 in straight cruise (so a 2 deg "\n           "misalignment reads \'2\'), and POSITIVE when the disk is tilted "\n           "nose-up, i.e. the flow arrives from below. Its rotor-mode "',
    '"SHAFT. In propeller vehicle axes, &alpha;<sub>disk</sub> = "\n           "atan2(-V<sub>z</sub>, |V<sub>x</sub>|). This is THE angle of "\n           "propeller mode -- 0 in straight cruise, POSITIVE when the flow "\n           "arrives from below, and NEGATIVE when it arrives from above. Its "\n           "rotor-mode "',
)

# ---------------------------------------------------------------------------
# Engine boundary. Internal disk-axis signs do not change.
# ---------------------------------------------------------------------------
replace_once(
    "zbemt/bemt.py",
    "import matplotlib.pyplot as plt\n\n# Compat:",
    "import matplotlib.pyplot as plt\n\ntry:\n    from . import nomenclature\nexcept ImportError:  # direct `python zbemt/bemt.py`\n    import nomenclature\n\n# Compat:",
)
replace_once(
    "zbemt/bemt.py",
    'Vx=tan(alpha_disk_deg)*Vz).',
    'Vx=-tan(alpha_disk_deg)*|Vz|).',
)
replace_once(
    "zbemt/bemt.py",
    '        return -float(np.tan(np.deg2rad(spec["alpha_deg"]))) * Vinf_long_conhecido',
    '        return nomenclature.alpha_rotor_axial_velocity(\n            spec["alpha_deg"], Vinf_long_conhecido)',
)
old_disk_engine = '''        # |Vz|, not Vz: `alpha_disk` is the flow's tilt relative to the
        # axis LINE, and with Vz<0 (axial descent, windmill) the raw sign
        # would flip the side the cross-flow points to . The reported
        # angle would stop matching the geometry. With the absolute
        # value, the angle that comes out in `alpha_disk_deg` is always
        # the real angle between the free stream and the +axis direction:
        # `alpha_disk` for Vz>0, and `180 - alpha_disk` for Vz<0 (the flow
        # arrives from the front of the disk, and that is what an obtuse
        # angle says).
        Vinf_long = float(np.tan(np.deg2rad(float(long_val)))) * abs(Vv_val)
        mu_val = Vinf_long / rotor.OmegaR'''
new_disk_engine = '''        # Propeller display V_z is the engine's in-plane component. Its sign
        # follows vehicle V_z: positive means flow from above. alpha_disk uses
        # the opposite sign: positive means flow from below.
        Vinf_long = nomenclature.alpha_disk_cross_velocity(long_val, Vv_val)
        mu_val = Vinf_long / rotor.OmegaR'''
replace_once("zbemt/bemt.py", old_disk_engine, new_disk_engine)
replace_once(
    "zbemt/bemt.py",
    '''    # ONE geometric angle, from which BOTH reported angles are derived.
    # `alpha_geom` is the raw `atan2(Vz, Vx)`: it carries the sign of
    # `Vz`, and it is what `_angle_from_axis` has always consumed.
    alpha_geom_deg = _geom_angle_deg(Vv_val, Vinf_long)
    # The reported disk angle of attack is its NEGATIVE, so that it means
    # what the same symbol means for a wing: positive when the stream
    # arrives from below the disk. That is the case with `Vz < 0`, which
    # opposes the induced velocity and raises the thrust.
    alpha_rotor_deg = -alpha_geom_deg + 0.0     # the +0.0 kills a -0.0

    meta = dict(
        mu_x=mu_val, J_x=np.pi * mu_val,
        Vz=Vv_val, mu_z=mu_z_val, J_z=np.pi * mu_z_val,
        alpha_rotor_deg=alpha_rotor_deg,
        # From the GEOMETRIC angle, not from the reported one: a
        # propeller in straight cruise must keep reading zero here, and
        # deriving one reported angle from the other is what would let
        # the pair drift apart after a change like this one.
        alpha_disk_deg=_angle_from_axis(alpha_geom_deg),
        Vx=Vinf_long,
    )''',
    '''    alpha_rotor_deg = nomenclature.alpha_rotor_from_components(
        Vv_val, Vinf_long)
    alpha_disk_deg = nomenclature.alpha_disk_from_components(
        Vinf_long, Vv_val)

    meta = dict(
        mu_x=mu_val, J_x=np.pi * mu_val,
        Vz=Vv_val, mu_z=mu_z_val, J_z=np.pi * mu_z_val,
        alpha_rotor_deg=alpha_rotor_deg,
        alpha_disk_deg=alpha_disk_deg,
        Vx=Vinf_long,
    )''',
)
replace_block(
    "zbemt/bemt.py",
    "def _angle_from_axis(alpha_geom_deg: float) -> float:\n",
    "\n\ndef solve_bemt_flight",
    '''def _angle_from_axis(alpha_geom_deg: float) -> float:\n    \"\"\"Return the signed propeller angle from a geometric disk-plane angle.\n\n    This compatibility helper reconstructs a unit velocity vector and applies\n    the same convention as ``alpha_disk_from_components``. Positive means the\n    free stream arrives from below. The result is limited to [-90, 90].\n    \"\"\"\n    angle = np.deg2rad(float(alpha_geom_deg))\n    cross = float(np.cos(angle))\n    axial = float(np.sin(angle))\n    return nomenclature.alpha_disk_from_components(cross, axial)\n''',
    "compatibility helper reconstructs a unit velocity vector",
)
replace_once(
    "zbemt/bemt.py",
    '                            alpha_rotor_deg=-_geom_angle_deg(Vz, mu_x * OmegaR),',
    '                            alpha_rotor_deg=nomenclature.alpha_rotor_from_components(\n                                Vz, mu_x * OmegaR),',
)
replace_once(
    "zbemt/bemt.py",
    '''    # The angle from the AXIS follows the same GEOMETRY as the angle from
    # the plane, which is the negative of the reported one. Derived from
    # the reported angle instead -- as it was -- a propeller in straight
    # cruise would read 180 degrees here rather than zero, because the
    # reported angle changed sign and this line did not.
    flight_cols["alpha_disk_deg"] = _angle_from_axis(
        -float(flight_cols["alpha_rotor_deg"]))''',
    '''    flight_cols["alpha_disk_deg"] = nomenclature.alpha_disk_from_components(
        float(flight_cols["Vx"]), float(flight_cols["Vz"]))''',
)
replace_all(
    "zbemt/bemt.py",
    "alpha_disk = 90 + alpha_rotor",
    "the two angle inputs require different known velocity components",
    1,
)

# ---------------------------------------------------------------------------
# API, batch builder, CLI.
# ---------------------------------------------------------------------------
replace_once(
    "zbemt/api.py",
    '''            condition.mu_x = V_to_mu(
                float(np.tan(np.deg2rad(degrees))) * abs(Vz),
                float(rpm), radius)''',
    '''            condition.mu_x = V_to_mu(
                nomenclature.alpha_disk_cross_velocity(degrees, Vz),
                float(rpm), radius)''',
)
replace_once(
    "zbemt/studies.py",
    '''            # |Vz|: see `bemt.resolve_advance_velocity`. With Vz<0 the
            # raw sign would flip the side of the cross flow and the
            # reported angle would stop matching the geometry.
            mu_x = ((float(np.tan(np.deg2rad(alpha_disk))) * abs(Vz)) / omega_R
                  if omega_R > 1e-9 else 0.0)''',
    '''            cross_velocity = nomenclature.alpha_disk_cross_velocity(
                alpha_disk, Vz)
            mu_x = (cross_velocity / omega_R if omega_R > 1e-9 else 0.0)''',
)
replace_once(
    "zbemt/cli.py",
    '''            # |Vz|: same reason as `bemt.resolve_advance_velocity`.
            mu_x = api.V_to_mu(
                float(np.tan(np.deg2rad(args.alpha_disk_deg))) * abs(Vz),
                args.rpm, radius_m)''',
    '''            mu_x = api.V_to_mu(
                nomenclature.alpha_disk_cross_velocity(args.alpha_disk_deg, Vz),
                args.rpm, radius_m)''',
)
replace_once(
    "zbemt/cli.py",
    '"(the in-plane component is tan(alpha_disk)*Vz, and mu_x needs Omega*R).",',
    '"(the cross-flow is -tan(alpha_disk)*|V_axial|, and mu_x needs Omega*R).",',
)
replace_once(
    "zbemt/cli.py",
    '"same angle written two ways (alpha_disk = 90 - alpha_rotor): with "',
    '"two alternate angle definitions: with "',
)
replace_once(
    "zbemt/cli.py",
    '"is therefore required. "',
    '"is therefore required. Positive alpha_disk means flow from BELOW; "\n                                  "positive propeller V_z cross-flow means flow from ABOVE. "',
)

# ---------------------------------------------------------------------------
# GUI widgets: sign plus physical unit switching for alpha_disk.
# ---------------------------------------------------------------------------
replace_once(
    "zbemt/gui/widgets.py",
    "from .. import api\n",
    "from .. import api\nfrom .. import nomenclature\n",
)
replace_once(
    "zbemt/gui/widgets.py",
    '"Vz": "<b>V<sub>z</sub></b><br><br>Free-stream velocity component along the vehicle z-axis.<br><br>It is climb/descent for a rotor and cross-flow for a propeller.",',
    '"Vz": "<b>V<sub>z</sub></b><br><br>Free-stream velocity component along the vehicle z-axis.<br><br>Positive V<sub>z</sub> means the free stream arrives from ABOVE in both rotor and propeller modes. It is axial flow for a rotor and cross-flow for a propeller.",',
)
replace_once(
    "zbemt/gui/widgets.py",
    '"alpha_disk": "<b>α<sub>disk</sub></b><br><br>Propeller inflow angle measured from the shaft.<br><br>It is zero when V<sub>z</sub> is zero and the free stream is aligned with the shaft.",',
    '"alpha_disk": "<b>α<sub>disk</sub></b><br><br>Propeller inflow angle measured from the shaft.<br><br>Positive α<sub>disk</sub> means the free stream arrives from BELOW. Positive propeller V<sub>z</sub> cross-flow means it arrives from ABOVE, so the signs are opposite. It is zero in straight axial cruise.",',
)
replace_once(
    "zbemt/gui/widgets.py",
    "        self._context_provider = None  # callable() -> (rpm, radius_m) | None\n        self._prev_unit = self.unit_combo.currentText()",
    "        self._context_provider = None  # callable() -> (rpm, radius_m) | None\n        self._axial_context_provider = None  # callable() -> axial Vz [m/s] | None\n        self._prev_unit = self.unit_combo.currentText()",
)
replace_once(
    "zbemt/gui/widgets.py",
    '''    def set_context_provider(self, fn):
        """Registers a callable that returns (rpm, radius_m) --
        needed to convert between mu_x/J_x and V when the unit is
        switched."""
        self._context_provider = fn

    def _on_unit_changed''',
    '''    def set_context_provider(self, fn):
        """Register the tip-speed context used by velocity conversions."""
        self._context_provider = fn

    def set_axial_context_provider(self, fn):
        """Register a callable returning the current along-shaft speed [m/s]."""
        self._axial_context_provider = fn

    def _axial_context(self):
        return (self._axial_context_provider()
                if self._axial_context_provider is not None else None)

    def _on_unit_changed''',
)
replace_once(
    "zbemt/gui/widgets.py",
    '''        if var == "Vx":
            ctx = self._ctx()
            if ctx is None:
                return None
            rpm, radius_m = ctx
            return api.V_to_mu(value, rpm, radius_m)
        return None       # alpha_disk: depends on Vz, known only by the tab''',
    '''        if var == "Vx":
            ctx = self._ctx()
            if ctx is None:
                return None
            rpm, radius_m = ctx
            return api.V_to_mu(value, rpm, radius_m)
        if var == "alpha_disk":
            ctx = self._ctx()
            Vz = self._axial_context()
            if ctx is None or Vz is None:
                return None
            rpm, radius_m = ctx
            cross = nomenclature.alpha_disk_cross_velocity(value, Vz)
            return api.V_to_mu(cross, rpm, radius_m)
        return None''',
)
replace_once(
    "zbemt/gui/widgets.py",
    '''        if var == "Vx":
            ctx = self._ctx()
            if ctx is None:
                return None
            rpm, radius_m = ctx
            return api.mu_to_V(mu_x, rpm, radius_m)
        return None       # alpha_disk: same''',
    '''        if var == "Vx":
            ctx = self._ctx()
            if ctx is None:
                return None
            rpm, radius_m = ctx
            return api.mu_to_V(mu_x, rpm, radius_m)
        if var == "alpha_disk":
            ctx = self._ctx()
            Vz = self._axial_context()
            if ctx is None or Vz is None:
                return None
            rpm, radius_m = ctx
            cross = api.mu_to_V(mu_x, rpm, radius_m)
            return nomenclature.alpha_disk_from_components(cross, Vz)
        return None''',
)
replace_block(
    "zbemt/gui/widgets.py",
    "    def mu_x(self, Vz: float = 0.0) -> float:\n",
    "\n    def set_default_unit(self, is_propeller: bool):",
    '''    def mu_x(self, Vz: float | None = None) -> float:\n        \"\"\"Return the engine in-plane ratio represented by the field.\"\"\"\n        v = self.spin.value()\n        if self.is_alpha_disk():\n            ctx = self._ctx()\n            axial = self._axial_context() if Vz is None else Vz\n            if ctx is None or axial is None:\n                return 0.0\n            rpm, radius_m = ctx\n            cross = nomenclature.alpha_disk_cross_velocity(v, axial)\n            return api.V_to_mu(cross, rpm, radius_m)\n        converted = self._mu_from(self.unit_combo.currentText(), v)\n        return v if converted is None else converted\n\n    def set_mu(self, mu_x: float, Vz: float | None = None):\n        self.spin.blockSignals(True)\n        if self.is_alpha_disk():\n            ctx = self._ctx()\n            axial = self._axial_context() if Vz is None else Vz\n            if ctx is not None and axial is not None:\n                rpm, radius_m = ctx\n                cross = api.mu_to_V(mu_x, rpm, radius_m)\n                self.spin.setValue(nomenclature.alpha_disk_from_components(\n                    cross, axial))\n            else:\n                self.spin.setValue(0.0)\n        else:\n            converted = self._value_in(self.unit_combo.currentText(), mu_x)\n            self.spin.setValue(mu_x if converted is None else converted)\n        self.spin.blockSignals(False)\n''',
    "Return the engine in-plane ratio represented by the field.",
)

# Give alpha_disk unit switching the axial context without circular dependence.
replace_once(
    "zbemt/gui/tabs/run_case.py",
    "        self.axial.set_context_provider(self._axial_context)\n        self._size_field(self.axial)",
    "        self.axial.set_context_provider(self._axial_context)\n        self.advance.set_axial_context_provider(self._advance_axial_velocity)\n        self._size_field(self.axial)",
)
replace_once(
    "zbemt/gui/tabs/run_case.py",
    '''    def _advance_context(self):
        """Given to LongitudinalInput to convert mu_x<->V when the unit
        changes (depends on this tab's current rpm and radius)."""
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.rpm_spin.value(), radius_m
''',
    '''    def _advance_context(self):
        """Return RPM and radius for the in-plane unit conversions."""
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.rpm_spin.value(), radius_m

    def _advance_axial_velocity(self):
        """Return the along-shaft speed that gives alpha_disk its scale."""
        rpm, radius_m = self._advance_context()
        return self.axial.vv(0.0, rpm, radius_m)
''',
)
replace_once(
    "zbemt/gui/tabs/run_batch.py",
    "        self.fixed_axial.set_context_provider(self._fixed_axial_context)\n",
    "        self.fixed_axial.set_context_provider(self._fixed_axial_context)\n        self.fixed_advance.set_axial_context_provider(self._fixed_axial_velocity)\n",
)
replace_once(
    "zbemt/gui/tabs/run_batch.py",
    "        self.add_row_axial.set_context_provider(self._add_row_axial_context)\n",
    "        self.add_row_axial.set_context_provider(self._add_row_axial_context)\n        self.add_row_advance.set_axial_context_provider(self._add_row_axial_velocity)\n",
)
replace_once(
    "zbemt/gui/tabs/run_batch.py",
    '''    def _fixed_advance_context(self):
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.fixed_rpm.value(), radius_m
''',
    '''    def _fixed_advance_context(self):
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.fixed_rpm.value(), radius_m

    def _fixed_axial_velocity(self):
        rpm, radius_m = self._fixed_advance_context()
        return self.fixed_axial.vv(0.0, rpm, radius_m)
''',
)
replace_once(
    "zbemt/gui/tabs/run_batch.py",
    '''    def _add_row_advance_context(self):
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.rpm_spin.value(), radius_m
''',
    '''    def _add_row_advance_context(self):
        radius_m = self.state.project.geometry.radius_m if self.state.project else 1.0
        return self.rpm_spin.value(), radius_m

    def _add_row_axial_velocity(self):
        rpm, radius_m = self._add_row_advance_context()
        return self.add_row_axial.vv(0.0, rpm, radius_m)
''',
)

# ---------------------------------------------------------------------------
# Requirements and user documentation.
# ---------------------------------------------------------------------------
replace_once(
    "docs/software_requirements.md",
    '''- **EN-13** — In rotor mode, `V_z`, `lambda_z`, `mu_z`, `J_z`, and total axial
  inflow are positive through the disk in the induced-velocity direction.
  `lambda_total = lambda_z + lambda_i`. Positive `V_z` reduces thrust for the
  same remaining inputs.''',
    '''- **EN-13** — In rotor mode, `V_z`, `lambda_z`, `mu_z`, `J_z`, and total axial
  inflow are positive through the disk in the induced-velocity direction. This
  is free stream arriving from above. `lambda_total = lambda_z + lambda_i`.
  Positive `V_z` reduces thrust for the same remaining inputs.''',
)
replace_once(
    "docs/software_requirements.md",
    '''- **EN-14** — In propeller mode, `alpha_disk = atan2(V_z, V_x)` and is measured
  from the shaft. Straight axial cruise has `V_z = 0` and `alpha_disk = 0`.''',
    '''- **EN-14** — In propeller vehicle axes, `V_z` is positive when the free stream
  arrives from above. `alpha_disk = atan2(-V_z, |V_x|)` is measured from the
  shaft and is positive when the free stream arrives from below. Straight axial
  cruise has `V_z = 0` and `alpha_disk = 0`.''',
)
replace_once(
    "docs/software_requirements.md",
    '''- **PA-5c** — `alpha_rotor_deg` and `alpha_disk_deg` can supply the axial flow
  component when their required context is available and the corresponding
  direct component is not supplied.
- **PA-5d** — An axial-angle alias is rejected when RPM is unavailable, when
  both angle forms are supplied, or when the direct axial component is also
  supplied.''',
    '''- **PA-5c** — `alpha_rotor_deg` derives rotor axial flow from a known in-plane
  component. `alpha_disk_deg` derives propeller cross-flow from a known
  along-shaft component. Both use the sign conventions of `EN-13a` and `EN-14`.
- **PA-5d** — An angle alias is rejected when its required velocity scale is
  unavailable, when both angle forms are supplied, or when a direct form of the
  component that the angle would derive is also supplied.''',
)

# documentation.html is the user reference and the source for embedded help.
replace_all(
    "docs/documentation.html",
    r"$\\alpha_{rotor}=\\operatorname{atan2}(V_z,V_x)$",
    r"$\\alpha_{rotor}=-\\operatorname{atan2}(V_z,V_x)$",
    1,
)
replace_all(
    "docs/documentation.html",
    r"$\\mu_x=\\tan(\\alpha_{disk})\\,|V_z|/(\\Omega R)$",
    r"$\\mu_x=-\\tan(\\alpha_{disk})\\,|V_z|/(\\Omega R)$",
    1,
)
replace_once(
    "docs/documentation.html",
    "The rotor angle is still computed and still exported. In cruise\n        it reads $\\alpha_{rotor}=90^\\circ$.",
    "The rotor angle is still computed and still exported. In cruise\n        it reads $\\alpha_{rotor}=-90^\\circ$.",
)
replace_once(
    "docs/documentation.html",
    '''        <li><b>Positive when the flow arrives from below</b>, that is, the disk is tilted nose-up relative to
          the free stream. Axial descent, with flow arriving on the front face, reads
          $180^\\circ$.</li>''',
    '''        <li><b>Positive when the flow arrives from below</b>. Positive vehicle $V_z$ is cross-flow from
          above and therefore gives a negative $\\alpha_{disk}$. Negative vehicle $V_z$ is flow from below
          and gives a positive $\\alpha_{disk}$. Reversing the along-shaft component does not reverse this
          cross-flow sign convention.</li>''',
)

# ---------------------------------------------------------------------------
# Regression tests: change the old alpha_disk geometric-sign contract into
# the unified wind-from-below contract. Existing alpha_rotor coverage remains.
# ---------------------------------------------------------------------------
replace_block(
    "tests/regression/test_axial_sign_convention.py",
    "class TestTheAngleFromTheShaftDidNotChange(unittest.TestCase):\n",
    "\n\nclass TestTheInputConvertersAgreeWithTheOutput",
    '''class TestThePropellerDiskAngleUsesTheSameWindSign(unittest.TestCase):\n    \"\"\"alpha_disk > 0 means flow from below, like alpha_rotor.\"\"\"\n\n    def test_a_propeller_in_straight_cruise_reads_zero(self):\n        summary = _summary(30.0, propeller=True, mu_x=0.0, rpm=3000.0)\n        self.assertAlmostEqual(summary[\"alpha_disk_deg\"], 0.0, places=6)\n\n    def test_positive_cross_flow_is_negative_alpha_disk(self):\n        summary = _summary(60.0, propeller=True, mu_x=0.1, rpm=3000.0)\n        self.assertLess(summary[\"alpha_disk_deg\"], 0.0)\n\n    def test_negative_cross_flow_is_positive_alpha_disk(self):\n        summary = _summary(60.0, propeller=True, mu_x=-0.1, rpm=3000.0)\n        self.assertGreater(summary[\"alpha_disk_deg\"], 0.0)\n''',
    "class TestThePropellerDiskAngleUsesTheSameWindSign",
)
replace_once(
    "tests/regression/test_axial_sign_convention.py",
    '''    alpha_disk is not an angle of attack. It measures the stream's tilt
    away from the SHAFT, keeps the geometric sign, and reads zero for a
    propeller in straight cruise.''',
    '''    alpha_disk is measured from the SHAFT. Like alpha_rotor, it is
    POSITIVE when the stream arrives from BELOW. Propeller display V_z is
    POSITIVE for flow from ABOVE, so alpha_disk and display V_z have opposite
    signs.''',
)

# Replace only the alpha-disk-focused test classes in propeller convention.
replace_block(
    "tests/regression/test_propeller_axes_convention.py",
    "class TestAngleFromAxis(unittest.TestCase):\n",
    "\n\nclass TestAlphaFromAxisAsInput",
    '''class TestAngleFromAxis(unittest.TestCase):\n    \"\"\"alpha_disk is signed by where the free stream comes from.\"\"\"\n\n    def test_purely_axial_flow_reads_zero_from_the_shaft(self):\n        cfg = bemt.BEMTConfig(is_propeller=True)\n        rot = _rotor()\n        _mu, _Vv, meta = bemt.resolve_advance_velocity(rot, cfg, mu_x=0.0, Vz=50.0)\n        self.assertAlmostEqual(meta[\"alpha_disk_deg\"], 0.0, places=9)\n\n    def test_positive_propeller_Vz_is_flow_from_above(self):\n        cfg = bemt.BEMTConfig(is_propeller=True)\n        rot = _rotor()\n        _mu, _Vv, meta = bemt.resolve_advance_velocity(rot, cfg, mu_x=0.2, Vz=60.0)\n        self.assertLess(meta[\"alpha_disk_deg\"], 0.0)\n\n    def test_negative_propeller_Vz_is_flow_from_below(self):\n        cfg = bemt.BEMTConfig(is_propeller=True)\n        rot = _rotor()\n        _mu, _Vv, meta = bemt.resolve_advance_velocity(rot, cfg, mu_x=-0.2, Vz=60.0)\n        self.assertGreater(meta[\"alpha_disk_deg\"], 0.0)\n\n    def test_edgewise_positive_cross_flow_reads_minus_ninety(self):\n        cfg = bemt.BEMTConfig(is_propeller=True)\n        _mu, _Vv, meta = bemt.resolve_advance_velocity(_rotor(), cfg, mu_x=0.3, Vz=0.0)\n        self.assertAlmostEqual(meta[\"alpha_disk_deg\"], -90.0, places=9)\n''',
    "alpha_disk is signed by where the free stream comes from",
)
replace_block(
    "tests/regression/test_propeller_axes_convention.py",
    "class TestAlphaFromAxisAsInput(unittest.TestCase):\n",
    "\n\nclass TestTwoAlphasOnePerMode",
    '''class TestAlphaFromAxisAsInput(unittest.TestCase):\n    \"\"\"alpha_disk derives propeller cross-flow from along-shaft speed.\"\"\"\n\n    def test_alpha_disk_zero_has_no_crossflow(self):\n        cfg = bemt.BEMTConfig(is_propeller=True)\n        mu_x, Vz, meta = bemt.resolve_advance_velocity(\n            _rotor(), cfg, alpha_disk_deg=0.0, Vz=60.0)\n        self.assertAlmostEqual(mu_x, 0.0, places=12)\n        self.assertAlmostEqual(Vz, 60.0, places=12)\n        self.assertAlmostEqual(meta[\"alpha_disk_deg\"], 0.0, places=9)\n\n    def test_positive_alpha_disk_produces_negative_crossflow(self):\n        cfg = bemt.BEMTConfig(is_propeller=True)\n        rot = _rotor()\n        mu_x, Vz, meta = bemt.resolve_advance_velocity(\n            rot, cfg, alpha_disk_deg=10.0, Vz=60.0)\n        expected = -math.tan(math.radians(10.0)) * 60.0\n        self.assertAlmostEqual(mu_x * rot.OmegaR, expected, places=9)\n        self.assertLess(mu_x, 0.0)\n        self.assertAlmostEqual(meta[\"alpha_disk_deg\"], 10.0, places=6)\n\n    def test_negative_alpha_disk_produces_positive_crossflow(self):\n        cfg = bemt.BEMTConfig(is_propeller=True)\n        rot = _rotor()\n        mu_x, _Vz, meta = bemt.resolve_advance_velocity(\n            rot, cfg, alpha_disk_deg=-10.0, Vz=60.0)\n        self.assertGreater(mu_x, 0.0)\n        self.assertAlmostEqual(meta[\"alpha_disk_deg\"], -10.0, places=6)\n\n    def test_reverse_axial_flow_does_not_reverse_crossflow_side(self):\n        cfg = bemt.BEMTConfig(is_propeller=True)\n        rot = _rotor()\n        mu_x, Vz, meta = bemt.resolve_advance_velocity(\n            rot, cfg, alpha_disk_deg=10.0, Vz=-60.0)\n        self.assertLess(mu_x, 0.0)\n        self.assertEqual(Vz, -60.0)\n        self.assertAlmostEqual(meta[\"alpha_disk_deg\"], 10.0, places=6)\n\n    def test_alpha_disk_accepts_dimensionless_axial(self):\n        cfg = bemt.BEMTConfig(is_propeller=True)\n        rot = _rotor()\n        mu_x, Vz, meta = bemt.resolve_advance_velocity(\n            rot, cfg, alpha_disk_deg=5.0, J_z=0.8)\n        self.assertGreater(Vz, 0.0)\n        self.assertLess(mu_x, 0.0)\n        self.assertAlmostEqual(meta[\"alpha_disk_deg\"], 5.0, places=6)\n\n    def test_both_angles_together_are_error(self):\n        cfg = bemt.BEMTConfig()\n        with self.assertRaises(ValueError):\n            bemt.resolve_advance_velocity(\n                _rotor(), cfg, alpha_disk_deg=5.0, alpha_deg=5.0)\n\n    def test_alpha_disk_still_requires_single_longitudinal(self):\n        cfg = bemt.BEMTConfig()\n        with self.assertRaises(ValueError):\n            bemt.resolve_advance_velocity(\n                _rotor(), cfg, alpha_disk_deg=5.0, mu_x=0.1)\n''',
    "alpha_disk derives propeller cross-flow from along-shaft speed",
)

# Widget regression coverage. The helper now supplies the axial scale.
replace_once(
    "tests/regression/test_condition_units.py",
    "        field.set_context_provider(lambda: (RPM, RADIUS_M))\n        field.set_default_unit(is_propeller)",
    "        field.set_context_provider(lambda: (RPM, RADIUS_M))\n        field.set_axial_context_provider(lambda: 60.0)\n        field.set_default_unit(is_propeller)",
)
replace_once(
    "tests/regression/test_condition_units.py",
    '''                if var == "alpha_disk":
                    continue      # derived from the axial component
                with self.subTest(propeller=is_propeller, unit=label):''',
    '''                with self.subTest(propeller=is_propeller, unit=label):''',
)
# Add explicit sign/switch tests before the next test class.
replace_once(
    "tests/regression/test_condition_units.py",
    "\n\nclass TestEveryOfferedUnitConverts(_ConditionWidgetTest):",
    '''\n\n    def test_propeller_alpha_disk_positive_means_negative_crossflow(self):\n        field = self._longitudinal(is_propeller=True)\n        field.unit_combo.setCurrentText("α_dᵢₛₖ [deg]")\n        field.spin.setValue(5.0)\n        self.assertLess(field.mu_x(), 0.0)\n\n    def test_switching_propeller_Vz_to_alpha_disk_preserves_the_vector(self):\n        field = self._longitudinal(is_propeller=True)\n        field.unit_combo.setCurrentText("V_z [m/s]")\n        field.spin.setValue(6.0)\n        before = field.mu_x()\n        field.unit_combo.setCurrentText("α_dᵢₛₖ [deg]")\n        self.assertLess(field.spin.value(), 0.0)\n        self.assertAlmostEqual(field.mu_x(), before, delta=2e-5)\n        field.unit_combo.setCurrentText("V_z [m/s]")\n        self.assertAlmostEqual(field.spin.value(), 6.0, delta=1e-3)\n\n\nclass TestEveryOfferedUnitConverts(_ConditionWidgetTest):''',
)

# Real Run Case tab: GUI input -> FlightCondition -> engine result.
replace_once(
    "tests/regression/test_run_tabs.py",
    "\n\n@unittest.skipUnless(_HAS_QT, \"PyQt6 not installed\")\nclass TestUnitCombosFollowPr2",
    '''\n\n@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")\nclass TestRunCaseFlightSignConvention(unittest.TestCase):\n    @classmethod\n    def setUpClass(cls):\n        cls.app = QApplication.instance() or QApplication([])\n\n    def _propeller_tab(self):\n        from zbemt.gui.common import AppState\n        from zbemt.gui.tabs.run_case import RunCaseTab\n        state = AppState()\n        project = helpers.make_studies_project()\n        project.config["is_propeller"] = True\n        state.project = project\n        tab = RunCaseTab(state)\n        self.addCleanup(tab.deleteLater)\n        tab.show()\n        self.app.processEvents()\n        return tab, project\n\n    def test_positive_alpha_disk_builds_flow_from_below_and_runs_that_case(self):\n        from zbemt import api\n        tab, project = self._propeller_tab()\n        tab.axial.unit_combo.setCurrentText("Vₓ [m/s]")\n        tab.axial.spin.setValue(60.0)\n        tab.advance.unit_combo.setCurrentText("α_dᵢₛₖ [deg]")\n        tab.advance.spin.setValue(10.0)\n        condition = tab._current_condition()\n        self.assertGreater(condition.Vz, 0.0)\n        self.assertLess(condition.mu_x, 0.0)\n        result = api.run_case(project, condition)\n        self.assertAlmostEqual(result.summary["alpha_disk_deg"], 10.0, places=3)\n\n    def test_positive_propeller_Vz_builds_negative_alpha_disk(self):\n        from zbemt import api\n        tab, project = self._propeller_tab()\n        tab.axial.unit_combo.setCurrentText("Vₓ [m/s]")\n        tab.axial.spin.setValue(60.0)\n        tab.advance.unit_combo.setCurrentText("V_z [m/s]")\n        tab.advance.spin.setValue(6.0)\n        condition = tab._current_condition()\n        self.assertGreater(condition.mu_x, 0.0)\n        result = api.run_case(project, condition)\n        self.assertLess(result.summary["alpha_disk_deg"], 0.0)\n\n\n@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")\nclass TestUnitCombosFollowPr2''',
)

print("flight-sign patch applied")
