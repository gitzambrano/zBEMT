"""Define project dataclasses and serialize them to JSON-based ``.bemt`` files.

Purpose and objectives:
    Provide the shared data contract for the GUI, the CLI, the API, the studies
    and the engine layers. The contract includes the defaults, the nested
    definitions, and the round trips.

Inputs and outputs:
    Inputs are dataclass instances, dictionaries, paths, and JSON-compatible
    values. Outputs are project definitions in memory or validated ``.bemt``
    files and file lists on disk.

Functions and conventions:
    Constructors and conversion helpers build the definitions. ``save_bemt``
    and ``load_bemt`` implement the file I/O. ``...Def`` classes contain editable raw
    data. Files use SI units, explicit field names, and string tokens for non-finite
    numbers. Therefore, strict JSON readers stay compatible.

Limitations and interactions:
    This module contains no solver, geometry generation, or polar calculation.
    ``api.py`` owns the application boundary; ``bemt.py``, ``geometry.py``,
    and ``airfoils.py`` consume these definitions.
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass, field, asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from . import nomenclature


# =============================================================================
# Generic .bemt (JSON) serialization utility
# =============================================================================

#: NaN and Infinity do NOT exist in JSON. Python's `json` writes them as
#: `NaN`/`Infinity` literals. It reads them back itself, but any other
#: reader (jq, JavaScript, a strict parser) rejects the whole
#: file. A `.bemt` is an interchange format, so they become strings and
#: turn back into float on read. A NaN can genuinely land here: an
#: imported polar point that did not converge, a numeric field left blank.
_NON_FINITE = {float("inf"): "Infinity", float("-inf"): "-Infinity"}
_NON_FINITE_REVERSE = {"NaN": float("nan"), "Infinity": float("inf"),
                       "-Infinity": float("-inf")}


def _float_jsonable(v: float) -> Any:
    if v != v:              # NaN is not equal to itself
        return "NaN"
    return _NON_FINITE.get(v, v)


def _from_jsonable_scalar(v: Any) -> Any:
    if isinstance(v, str) and v in _NON_FINITE_REVERSE:
        return _NON_FINITE_REVERSE[v]
    if isinstance(v, list):
        return [_from_jsonable_scalar(x) for x in v]
    if isinstance(v, dict):
        return {k: _from_jsonable_scalar(x) for k, x in v.items()}
    return v


def _to_jsonable(obj: Any, is_propeller: bool = False) -> Any:
    """Converts dataclasses (recursively), numpy arrays, tuples, and other
    containers into
    something ``json.dump`` accepts directly.

    ``is_propeller`` rotates the axis letters of a `FlightCondition` into the
    ones the user reads. The airspeed along a propeller's shaft is written
    as ``Vx``, not under the engine's ``Vz``. Nothing else in the file is
    touched, and nothing in memory is: the dataclass keeps its disk-axes
    fields, and the engine never sees this. See `zbemt.nomenclature`."""
    if is_dataclass(obj) and not isinstance(obj, type):
        # `fields` + `getattr`, not `asdict`: `asdict` is DEEP, and would have
        # already flattened a nested `FlightCondition` into a plain dict by
        # the time the recursion reached it, so the conditions inside a
        # `BatchDefinition` would never get their axis letters rotated.
        raw = {f.name: _to_jsonable(getattr(obj, f.name), is_propeller)
               for f in fields(obj)}
        # A ManeuverPoint carries the same engine keys as a condition
        # (mu_x/Vz), so its letters rotate under the propeller
        # convention exactly like a FlightCondition's (PA-4).
        if isinstance(obj, (FlightCondition, ManeuverPoint)):
            return nomenclature.to_display_keys(raw, is_propeller)
        return raw
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating,)):
        return _float_jsonable(float(obj))
    if isinstance(obj, float):
        return _float_jsonable(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, dict):
        return {k: _to_jsonable(v, is_propeller) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v, is_propeller) for v in obj]
    return obj


def save_bemt(obj: Any, path: str, is_propeller: bool = False) -> None:
    """Saves any dataclass from the module (or plain dict) as ``.bemt``
    JSON. Creates the parent directories if needed.

    ``is_propeller`` is the project's mode, and decides the axis letters a
    `FlightCondition` is written under (`_to_jsonable`). Everything else in
    the file is mode-independent."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(_to_jsonable(obj, is_propeller), f, indent=2, ensure_ascii=False)


def load_bemt(cls: type, path: str, is_propeller: bool = False) -> Any:
    """Loads a ``.bemt`` (JSON) file and rebuilds the ``cls`` dataclass.
    Does a shallow recursive reconstruction: fields that are themselves
    dataclasses or lists of dataclasses are resolved via ``cls``'s type
    annotations when possible; otherwise the value is passed through as
    it came from JSON (dict/list/primitive)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return _from_jsonable(cls, raw, is_propeller)


def save_bemt_list(items: list, path: str, is_propeller: bool = False) -> None:
    """Like ``save_bemt``, but for a LIST of dataclasses (for example
    ``Project.airfoil_sections``, the Phase D multi-section airfoil). Reuses
    the same ``_to_jsonable`` (already knows how to serialize lists of
    dataclasses)."""
    save_bemt(list(items), path, is_propeller)


def load_bemt_list(cls: type, path: str, is_propeller: bool = False) -> list:
    """Counterpart of ``save_bemt_list``: loads a list of ``cls``
    dataclasses saved by it."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [_from_jsonable(cls, v, is_propeller) for v in raw]


def _migrate_airfoil_raw(raw: dict) -> dict:
    """Migrates an ``AirfoilDef`` dict saved under the old schema (with
    ``use_viterna_extension``/``blend_with_viterna``/``extrapolate_full_range``
    and/or ``use_compressibility``) to the current schema. See
    docs/plano_v2.md Section 7. ``_from_jsonable`` already ignores
    unknown keys and uses the default for missing ones, so it is enough to
    fill in ``extend_full_range`` with the old intent before rebuilding
    the dataclass; the old ``use_compressibility`` field (now only in
    BEMTConfig) is simply discarded here."""
    old_keys = ("use_viterna_extension", "blend_with_viterna", "extrapolate_full_range")
    migrated = dict(raw)
    changed = False

    if "extend_full_range" not in raw and any(k in raw for k in old_keys):
        migrated["extend_full_range"] = bool(
            raw.get("use_viterna_extension", False)
            or raw.get("blend_with_viterna", False)
            or raw.get("extrapolate_full_range", False)
        )
        for k in old_keys:
            migrated.pop(k, None)
        migrated.pop("use_compressibility", None)
        changed = True

    # Previous schema (before "viterna" became a 4th stall_model option):
    # analytical/external source with extend_full_range=True expressed
    # Viterna through that field instead of stall_model. Migrate to the
    # current schema, preserving the same physical behavior (see
    # `models.uses_full_range_extension`).
    #
    # The migration only applies to REALLY old files, that is, files
    # without the `stall_model` key. It used to also run on files already
    # in the current schema, and since the AirfoilDef default has
    # extend_full_range=True, ANY stall_model other than 'viterna' was
    # silently reverted on load. In practice the field was impossible to
    # change without also turning off extend_full_range, both from the GUI
    # and the CLI.
    src = migrated.get("source", "analytical")
    if ("stall_model" not in raw and src == "analytical"
            and migrated.get("extend_full_range")):
        migrated["stall_model"] = "viterna"
        changed = True

    return migrated if changed else raw


def migrate_config_raw(raw: dict) -> dict:
    """Migrates a ``config.bemt`` from the old schema. Currently: the
    boolean ``use_prandtl_loss`` became the enum ``prandtl_loss_mode``
    (which distinguishes tip, root and both). Without this migration the
    field was silently discarded, including in the repository's
    reference project, which stored ``use_prandtl_loss: true`` and had
    been running with the default.

    ``False`` must map to ``"off"``: that is the value the engine reads as
    "apply no loss factor". Writing anything outside
    ``off | tip | root | both`` makes the engine fall back to ``"both"``,
    so a project that had the correction switched off would silently come
    back with it switched on."""
    migrated = dict(raw)
    if "use_prandtl_loss" in migrated:
        old_value = bool(migrated.pop("use_prandtl_loss"))
        migrated.setdefault("prandtl_loss_mode", "both" if old_value else "off")
    return migrated


def warn_unknown_keys(cls: type, raw: dict, context: str = "") -> list[str]:
    """Warns (``UserWarning``) about keys in the file that ``cls`` does
    not have.

    The previous behavior was to silently discard them: a field renamed
    between versions fell back to the default and the user only found out
    from the wrong result. They are still discarded. What changes is
    that it now says so. Returns the list, for anyone who wants to handle
    it."""
    known = {f.name for f in fields(cls)}
    unknown = sorted(k for k in raw if k not in known)
    if unknown:
        where = f" in {context}" if context else ""
        warnings.warn(
            f"{cls.__name__}{where}: {len(unknown)} field(s) from file "
            f"do not exist in current schema and were ignored "
            f"({', '.join(unknown)}). A field renamed in a newer version "
            f"falls back to its default. Check whether the value you "
            f"saved is still being used.", UserWarning, stacklevel=3)
    return unknown


def _from_jsonable(cls: type, raw: Any, is_propeller: bool = False) -> Any:
    if raw is None:
        return None
    if not is_dataclass(cls):
        return raw
    if cls is AirfoilDef and isinstance(raw, dict):
        raw = _migrate_airfoil_raw(raw)
    if cls is OptimizationDefinition and isinstance(raw, dict):
        raw = migrate_optimization_raw(raw)
    if cls is ManeuverPoint and isinstance(raw, dict):
        # Inverse of the _to_jsonable rotation: the file stores the
        # letters the project's mode shows (PA-4).
        raw = nomenclature.from_display_keys(raw, is_propeller)
    legacy_warned = False
    if cls is FlightCondition and isinstance(raw, dict):
        legacy_warned = warn_legacy_nomenclature(raw, is_propeller)
        raw = nomenclature.from_display_keys(raw, is_propeller)
    alpha_alias = None
    if cls in (FlightCondition, ManeuverPoint) and isinstance(raw, dict):
        raw, alpha_alias = _take_alpha_alias(raw)
    if isinstance(raw, dict) and not legacy_warned:
        # Skipped when the old-nomenclature warning already fired: the leftover
        # keys are the OLD names, and a second warning calling them "fields
        # that do not exist" points away from the actual problem.
        warn_unknown_keys(cls, raw)
    kwargs = {}
    type_hints = {f.name: f.type for f in fields(cls)}
    for f in fields(cls):
        if f.name not in raw:
            continue
        val = raw[f.name]
        ftype = type_hints[f.name]
        kwargs[f.name] = _coerce_field(ftype, _from_jsonable_scalar(val),
                                       is_propeller)
    built = cls(**kwargs)
    if alpha_alias is not None:
        # Parked on the instance, NOT stored as a field. Resolving it
        # needs the rotor RADIUS, which lives in another file
        # (`geom.bemt`) and is unknown here; `api.load_project` finishes
        # the job once the geometry is in hand. Because it is not a
        # field it never reaches `_to_jsonable`, so the file still holds
        # `mu_x` and `Vz` alone and there is no second stored form of
        # one axis.
        setattr(built, ALPHA_ALIAS_ATTRIBUTE, alpha_alias)
    return built


#: Where `_from_jsonable` parks an unresolved angle for
#: `api.resolve_alpha_aliases` to finish.
ALPHA_ALIAS_ATTRIBUTE = "_alpha_alias_deg"

#: The two names for the tilt of the stream. `alpha_rotor` is measured
#: from the DISK PLANE, `alpha_disk` from the SHAFT, so they are not the
#: same number and a file that gives both is stating one axis twice.
ALPHA_ALIAS_KEYS = ("alpha_rotor_deg", "alpha_disk_deg")


def _take_alpha_alias(raw: dict):
    """Removes an angle alias from a condition dict and returns it.

    Removed rather than left in place, so `warn_unknown_keys` does not
    report as an unknown field a key that IS understood. Returns the
    dict to build from, and either ``None`` or ``(key, degrees)``."""
    present = [k for k in ALPHA_ALIAS_KEYS if raw.get(k) is not None]
    if not present:
        return raw, None
    stripped = {k: v for k, v in raw.items() if k not in ALPHA_ALIAS_KEYS}
    if len(present) > 1:
        raise ValueError(
            "A flight condition gives both 'alpha_rotor_deg' and "
            "'alpha_disk_deg'. They are the same tilt measured from two "
            "different references (the disk plane and the shaft), so with "
            "both, neither velocity component sets the scale. Give one.")
    return stripped, (present[0], float(raw[present[0]]))


def warn_legacy_nomenclature(raw: dict, is_propeller: bool) -> bool:
    """Warns when a propeller `FlightCondition` still carries the OLD,
    disk-axes key names.

    There is no back-compat by decision, because a SILENT misread is worse
    than a missing feature. Under the new schema a propeller file's ``Vz`` is the
    CROSS-flow. In a file written by the previous version it was the airspeed
    along the shaft. Loading it quietly would turn 65 m/s of cruise into
    65 m/s of cross-flow and solve a completely different condition, with a
    plausible-looking number at the end. Returns whether it warned."""
    if not is_propeller:
        return False
    legacy_keys = {"mu_x", "Vz", "J_x", "lambda_z"} & set(raw)
    if not legacy_keys:
        return False
    warnings.warn(
        f"FlightCondition: {sorted(legacy_keys)} are the DISK-axes names this "
        f"project used before the axis-nomenclature change. A propeller "
        f"project now stores the letters it shows: 'Vx' for the airspeed "
        f"along the shaft, 'mu_z' for the cross-flow. Reading this file as "
        f"is would swap the two components. Re-create the conditions, or "
        f"rename the keys in the file.", UserWarning, stacklevel=3)
    return True


def _coerce_field(ftype: Any, val: Any, is_propeller: bool = False) -> Any:
    # Resolves type strings (from __future__ import annotations) only in
    # the cases where we actually need to rebuild as a nested dataclass.
    type_name = ftype if isinstance(ftype, str) else getattr(ftype, "__name__", "")
    registry = {
        "ProfileGeometry": ProfileGeometry,
        "PolarSlice": PolarSlice,
        "RotorGeometryDef": RotorGeometryDef,
        "BladeDynamicsDef": BladeDynamicsDef,
        "AirfoilDef": AirfoilDef,
        "FlightCondition": FlightCondition,
        "BatchDefinition": BatchDefinition,
        "ManeuverPoint": ManeuverPoint,
        "ManeuverDefinition": ManeuverDefinition,
        "ObjectiveDef": ObjectiveDef,
        "ConstraintDef": ConstraintDef,
        "DesignVariable": DesignVariable,
        "OptimizationDefinition": OptimizationDefinition,
        "DerivativeRequest": DerivativeRequest,
        "ComparisonVariantRow": ComparisonVariantRow,
        "ComparisonDefinition": ComparisonDefinition,
    }
    for name, klass in registry.items():
        if name in str(type_name):
            if isinstance(val, list):
                return [_from_jsonable(klass, v, is_propeller)
                        if isinstance(v, dict) else v for v in val]
            if isinstance(val, dict):
                return _from_jsonable(klass, val, is_propeller)
    return val


# =============================================================================
# 2D: everything airfoil-related (aerodynamic model and profile geometry)
# =============================================================================

@dataclass
class PolarSlice:
    """A polar (alpha_deg, Cl, Cd), optionally labeled by radial section
    (r_norm), Reynolds and/or Mach. The combination of which labels are
    present (None = absent) across the whole slice list of an
    ``AirfoilDef`` determines, in ``airfoils.to_airfoil()``, whether the
    result is a single polar, multi-section, and/or interpolated in
    Re/Mach."""
    alpha_deg: list[float] = field(default_factory=list)
    cl: list[float] = field(default_factory=list)
    cd: list[float] = field(default_factory=list)
    r_norm: Optional[float] = None
    reynolds: Optional[float] = None
    mach: Optional[float] = None
    label: str = ""   # free-form label, for example "root", "tip", imported file name


@dataclass
class ProfileGeometry:
    """2D profile geometry (x,y coordinates). Only needed when a polar is
    to be generated via an external engine (NeuralFoil, Phase 7); for the
    analytical/table models it is optional/illustrative."""
    source: str = "naca4"          # "naca4" | "naca5" | "cst" | "bezier" | "parsec" | "joukowski" | "biconvex" | "imported"
    naca_code: str = "0012"
    cst_upper: list[float] = field(default_factory=list)
    cst_lower: list[float] = field(default_factory=list)
    bezier_control_points: list[list[float]] = field(default_factory=list)
    #: Parameters of the analytic families that have no dedicated fields
    # ("parsec", "joukowski", "biconvex"): the exact keyword dictionary
    # accepted by the generator of the same name in airfoils.py, so a
    # saved contour can be regenerated without the coordinates.
    generator_params: dict = field(default_factory=dict)
    imported_path: Optional[str] = None
    n_points: int = 200

    # generated coordinates (cache. Filling it is not required to save,
    # because airfoils.py recomputes them from the parameters above when
    # needed)
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)


@dataclass
class AirfoilDef:
    """Complete, unified definition of the airfoil's 2D behavior:
    aerodynamic model (analytical or table-based, with or without dynamic
    stall) and profile geometry (for polar generation via NeuralFoil,
    Phase 7). See docs/plano.md Sections 4.1 and 8.3 and docs/plano_v2.md Section
    2.4.

    Architecture note (plano_v2 Section 2.4): this dataclass gathers the
    orthogonal axes A (source), B (analytical model/static stall), C
    (full range extension) and D (dynamic stall) of the airfoil's
    behavior. Compressibility (axis E) and reverse flow (axis F) are a
    property of the ENGINE and live only in BEMTConfig (bemt.py). There
    is no longer an equivalent field here (plano_v2 Finding #2)."""
    name: str = "unnamed airfoil"

    # --- radial position of the section (Phase D — multi-section airfoil) ---
    # None = this AirfoilDef is the SINGLE airfoil for the whole blade
    # (normal use, via Project.airfoil). Behavior as always, unchanged.
    # Only becomes meaningful when this object lives inside
    # Project.airfoil_sections (2+ elements, each with r_norm MANDATORILY
    # set): in that case it represents "the airfoil AT THIS radial
    # station", and airfoils.to_blade_airfoil() interpolates the resulting
    # Cl/Cd between neighboring sections
    # (bemt.HeterogeneousMultiSectionAirfoil).
    r_norm: Optional[float] = None

    # --- A. source of the aerodynamic model ---
    # XFOIL and NeuralFoil polars are imported through `table_slices`, so
    # "table" covers every externally generated polar.
    source: str = "analytical"     # "analytical" | "table"

    # --- B. analytical model (linear + static stall) ---
    cl_alpha: float = 2 * math.pi
    alpha0_deg: float = -4.5
    cd0: float = 0.0155
    k: float = 0.0
    alpha_stall_pos_deg: float = 15.0
    alpha_stall_neg_deg: float = -6.0
    # "linear" (no stall) | "clip" (clipped stall) | "enhanced" (smoothed
    # non-linear stall) | "viterna" (Viterna-Corrigan extension, see note
    # below). The 4 options are MUTUALLY EXCLUSIVE: there is no
    # combination of "clip"/"enhanced" with Viterna. When "viterna" is
    # chosen, the PRE-stall curve used as base is always the pure linear
    # line (no clamp), extended via Viterna-Corrigan from
    # `alpha_stall_pos_deg`/`alpha_stall_neg_deg` (see
    # `airfoils.build_analytical`/`apply_viterna_extension`).
    # Default "viterna": matches the previous default of
    # `extend_full_range=True` (full range extension on by default, see
    # field below) and `BEMTConfig.reverse_flow_model=
    # 'viterna_full_range'` (bemt.py Section 6).
    stall_model: str = "viterna"

    # --- C. full range extension (-180..+180, Viterna-Corrigan) ---
    # For `source='analytical'` (or 'external'), Viterna stopped being an
    # independent toggle: it is the "viterna" option of `stall_model`
    # above itself, and this field is ignored in that case (see
    # `models.uses_full_range_extension`, the single source of truth on
    # whether full range extension is active).
    # For `source='table'`, it remains the user's explicit choice to
    # EXTRAPOLATE the imported table beyond the last real point with
    # Viterna-Corrigan. The table itself never has a "stall_model", since
    # it is data, not a model. That is why Viterna remains a separate
    # option here instead of merging into an enum the table does not
    # have.
    # Default True: matches the default of BEMTConfig.reverse_flow_model=
    # 'viterna_full_range' (bemt.py Section 6). Without this on, that engine
    # default would fall into an invalid combination (see
    # validation.validate_config).
    extend_full_range: bool = True

    # Width (degrees) of the smooth (C1-continuous) transition window
    # between the base model and the Viterna-Corrigan extrapolation. See
    # `bemt.ViternaExtendedAirfoil`. Replaces the old abrupt switch
    # exactly at alpha_stall (which produced a "kink"/slope discontinuity)
    # with a gradual blend, both for `source='analytical'` and
    # `source='table'`. For tables, CLmax/CLmin and the corresponding
    # stall angles are ALWAYS detected automatically from the table itself
    # (argmax/argmin of Cl). `alpha_stall_pos_deg`/`alpha_stall_neg_deg`
    # above are ignored in that case (they only apply to
    # `source='analytical'`). The extrapolation only kicks in beyond
    # the last real table point on each side, never overwriting existing
    # tabulated data. Note: since it is a C1-continuous (not C2)
    # interpolation, the real Cl peak may fall slightly before alpha_stall,
    # with a value slightly above Cl_stall (approximately 1-2% for the
    # default). See the detailed note in `ViternaExtendedAirfoil`. Lower
    # this value for a peak closer to the one defined, at the cost of a
    # more abrupt transition.
    viterna_blend_width_deg: float = 4.0

    # --- D. dynamic stall (Øye), SINGLE copy (plano_v2.md Finding #1) ---
    # airfoils.to_airfoil() attaches these values to the airfoil object
    # (`airfoil.dynamic_stall_params`) for the engine to read from there,
    # instead of duplicating these fields in BEMTConfig.
    use_dynamic_stall: bool = False
    dynamic_stall_method: str = "frequency"   # "frequency" | "time_march"
    dynamic_stall_A: float = 8.0
    dynamic_stall_fade_start_deg: float = 40.0
    dynamic_stall_fade_end_deg: float = 50.0
    dynamic_stall_time_march_revolutions: int = 8
    dynamic_stall_time_march_avg_last: int = 3

    # --- table-based polar (CSV/DAT import), flexible in Re and/or Mach ---
    table_slices: list[PolarSlice] = field(default_factory=list)

    # --- 2D profile geometry (only needed for NeuralFoil) ---
    geometry: Optional[ProfileGeometry] = None

    # --- external engine (Phase 7, see external_solvers.py) ---
    external_engine: str = "none"      # "none" | "neuralfoil" | "xfoil"
    external_reynolds_list: list[float] = field(default_factory=list)
    external_mach_list: list[float] = field(default_factory=list)
    external_alpha_min_deg: float = -20.0
    external_alpha_max_deg: float = 20.0
    external_alpha_step_deg: float = 0.5

    # --- XFOIL-only adjustment inputs, read only when
    # external_engine == "xfoil" (see external_solvers._run_polar_xfoil).
    # xfoil_ncrit is the critical amplification factor N of the e^N
    # transition criterion; xfoil_xtr_top/xfoil_xtr_bot force transition
    # at a chord fraction, where 1.0 leaves free transition. Serialized by
    # airfoil.bemt automatically. NeuralFoil ignores them.
    xfoil_ncrit: float = 9.0
    xfoil_xtr_top: float = 1.0
    xfoil_xtr_bot: float = 1.0


def uses_full_range_extension(a: "AirfoilDef") -> bool:
    """SINGLE source of truth on whether the Viterna-Corrigan full range
    extension (-180..+180) is active for this `AirfoilDef`, given that the
    choice no longer lives in a single field (see notes on
    `AirfoilDef.stall_model`/`extend_full_range` above):

    - `source='table'`: it is literally `extend_full_range` (explicit
      toggle for extrapolating the imported table).
    - any other source (`'analytical'`/`'external'`): it is
      `stall_model == 'viterna'`, and `extend_full_range` is ignored.

    Used by `airfoils.to_airfoil()` (decides whether to wrap the result in
    `ViternaExtendedAirfoil`) and by `validation.validate_config` (checks
    whether `reverse_flow_model='viterna_full_range'` really has an
    extended polar behind it).
    """
    if a.source == "table":
        return a.extend_full_range
    return a.stall_model == "viterna"


# =============================================================================
# 3D: rotor and blade geometry
# =============================================================================

@dataclass
class BladeDynamicsDef:
    """Rigid-blade flap and lead-lag freedoms. See SC-11.

    The blade stays rigid; what this block adds is its rigid-body motion
    about a flap hinge (and optionally a lag hinge) at ``hinge_offset_norm``
    (= e, a fraction of R), with optional root springs. The response is
    periodic in azimuth and quasi-steady: there is no transient here
    (SC-12 owns transients). The physics conversions (resolved inertia,
    frequency ratios) live in ``geometry.py``; the solver lives in
    ``bemt.solve_bemt_flapping``. This class holds only editable data
    (AR-3).

    ``flap_model`` selects how much freedom the blade has:

    - ``"rigid"``          -- no flap freedom at all. The behavior of every
      project that predates this block, and still the default.
    - ``"offset"``         -- flap hinge at e > 0, no spring.
    - ``"spring"``         -- flap root spring at e = 0.
    - ``"offset_spring"``  -- hinge offset AND root spring together.

    ``inertia_source`` decides how the flap inertia I_beta is obtained:
    from a given Lock number (``"lock"``, converted with the airfoil's
    lift-curve slope and the chord at r/R = 0.75), given directly
    (``"inertia"``), or from a uniform blade mass over the flapping part
    (``"blade_mass"``).
    """
    flap_model: str = "rigid"        # "rigid" | "offset" | "spring" | "offset_spring"
    hinge_offset_norm: float = 0.0   # e, fraction of R
    flap_spring_nm_per_rad: float = 0.0     # K_beta [N*m/rad]
    inertia_source: str = "lock"     # "lock" | "inertia" | "blade_mass"
    lock_number: float = 8.0         # gamma, used when inertia_source == "lock"
    flap_inertia_kg_m2: float = 0.0  # I_beta, used when inertia_source == "inertia"
    blade_mass_kg: float = 0.0       # used when inertia_source == "blade_mass"
    pitch_flap_coupling_deg: float = 0.0    # delta_3, the delta-three hinge
    harmonics: int = 2               # N_h in the harmonic balance
    outer_max_iter: int = 30
    outer_tol_deg: float = 1e-4
    outer_relax: float = 0.5
    # --- lead-lag ---
    lag_enabled: bool = False
    lag_spring_nm_per_rad: float = 0.0      # K_zeta [N*m/rad]
    lag_damping_nms_per_rad: float = 0.0    # C_zeta [N*m*s/rad]
    lag_inertia_kg_m2: float = 0.0          # I_zeta [kg*m^2]
    lag_feeds_back: bool = True      # apply the zeta_dot term to U_T


@dataclass
class RotorGeometryDef:
    """Radial table of the blade (always the canonical on-disk
    representation, regardless of whether it was generated from
    parameters or edited point by point in the graphical editor)."""
    r_norm: list[float] = field(default_factory=list)   # r/R, 0..1
    chord_norm: list[float] = field(default_factory=list)  # c/R
    twist_deg: list[float] = field(default_factory=list)

    origin: str = "parametric"   # "parametric" | "table" | "editor" (metadata/label only)
    origin_params: dict = field(default_factory=dict)   # for example: {"kind": "tapered", "root_chord": .., "tip_chord": ..}

    n_blades: int = 2
    radius_m: float = 1.0
    root_cutout_norm: float = 0.15

    #: Rigid-blade flap and lead-lag freedoms (SC-11). The default is a
    #: blade with no flap freedom, which is the behavior of every project
    #: saved before this field existed: an old ``geom.bemt`` without a
    #: ``dynamics`` key loads with exactly this default.
    dynamics: BladeDynamicsDef = field(default_factory=BladeDynamicsDef)

    #: Free-form label, metadata only: NOTHING in the engine reads this
    #: field, and it has no link to `AirfoilDef.name` nor does it select a
    #: polar. `Project.airfoil` (or `airfoil_sections`, by r_norm) is what
    #: decides the airfoil.
    #: Free-form label, metadata only (Q5): NOTHING in the engine reads
    #: this field. It has no link to `AirfoilDef.name` and does not select
    #: any polar. `Project.airfoil`, or `airfoil_sections` by r_norm, is
    #: what decides the airfoil. Kept because it is already stored in
    #: existing `.bemt` files.
    airfoil_name: str = ""


# =============================================================================
# Flight conditions / batch / results
# =============================================================================

@dataclass
class FlightCondition:
    name: str = "Case 1"
    mu_x: float = 0.0                 # advance ratio
    collective_deg: float = 0.0
    Vz: float = 0.0                 # vertical velocity [m/s]
    rpm: Optional[float] = None     # if None, uses Omega from BEMTConfig/Rotor
    #: Cyclic pitch, the 1/rev harmonics theta_1c (cosine) and theta_1s
    #: (sine), in degrees. Unlike the collective, which is a rigid offset on
    #: the twist vector, cyclic varies with azimuth, so it reaches the
    #: engine inside the blade-motion dictionary instead of on
    #: ``Rotor.theta_geom_deg``. A rigid-blade project that sets either one
    #: to a nonzero value is solved through the same path, with the flap
    #: angle held at zero. Both default to zero: every condition saved
    #: before these fields existed keeps its exact behavior.
    cyclic_c_deg: float = 0.0   # theta_1c, the cosine cyclic
    cyclic_s_deg: float = 0.0   # theta_1s, the sine cyclic
    #: Perturbation inputs of the stability derivatives (SC-14): the
    #: sideslip angle rotates the in-plane free stream, and the hub
    #: angular rates roll/pitch the hub. They belong to the CONDITION,
    #: not to the configuration -- they describe the state the rotor flies,
    #: not the solver that evaluates it. All default to zero, which keeps
    #: every condition saved before these fields existed exact.
    sideslip_deg: float = 0.0       # psi_w, rotation of the in-plane flow
    p_rate_deg_s: float = 0.0       # roll rate  [deg/s]
    q_rate_deg_s: float = 0.0       # pitch rate [deg/s]


@dataclass
class BatchDefinition:
    name: str = "batch 1"
    conditions: list[FlightCondition] = field(default_factory=list)
    sweep_kind: str = "custom"   # "custom" | "mu_sweep" | "alpha_sweep" | "collective_sweep" | "factorial"
    sweep_params: dict = field(default_factory=dict)
    outdir: Optional[str] = None
    plots: list[str] = field(default_factory=list)


@dataclass
class ManeuverPoint:
    """One node of a prescribed trajectory (SC-12).

    The engine keys apply, so ``mu_x`` is the IN-PLANE component and
    ``Vz`` the axial one in disk axes -- exactly what a `FlightCondition`
    stores. Under the propeller convention the letters rotate on disk,
    exactly as they do for a condition (see `nomenclature`)."""
    t_s: float = 0.0
    mu_x: float = 0.0
    Vz: float = 0.0
    collective_deg: float = 0.0
    cyclic_c_deg: float = 0.0
    cyclic_s_deg: float = 0.0
    rpm: Optional[float] = None


@dataclass
class ManeuverDefinition:
    """A prescribed transient (SC-12): a sequence of flight conditions in
    time. It is not a batch -- each sample inherits the inflow state of
    the sample before it."""
    name: str = "maneuver 1"
    points: list[ManeuverPoint] = field(default_factory=list)
    interpolation: str = "linear"     # "linear" | "hold"
    dt_s: float = 0.02                # output sample interval
    substeps_per_step: int = 8        # inflow sub-steps inside one sample
    initial_state: str = "equilibrium"  # "equilibrium" | "zero"
    march_dynamic_stall: bool = False
    march_flapping: bool = False


# =============================================================================
# Design tools: geometry comparison and design optimization
# =============================================================================

#: Parameters a design optimization may vary, with their roles. Geometry
#: planform parameters are generator inputs (they live in
#: ``RotorGeometryDef.origin_params``); ``n_blades``, ``radius_m`` and
#: ``root_cutout_norm`` are direct ``RotorGeometryDef`` fields.
GEOMETRY_PARAMS = (
    "root_chord_norm", "tip_chord_norm", "twist_root_deg", "twist_tip_deg",
    "max_chord_norm", "chord_norm", "n_blades", "radius_m", "root_cutout_norm",
)

INTEGER_PARAMS = ("n_blades",)


@dataclass
class DesignVariable:
    """One bounded degree of freedom of a design optimization."""
    param: str = "tip_chord_norm"
    lower: float = 0.02
    upper: float = 0.15


@dataclass
class ObjectiveDef:
    """One objective of a design study (SC-13). One or two objectives:
    two of them switch the search to the Pareto front."""
    key: str = "FM"                  # any summary key
    kind: str = "maximize"           # "maximize" | "minimize"
    weight: float = 1.0              # used only by the weighted-sum method


@dataclass
class ConstraintDef:
    """One inequality constraint on a summary key (SC-13)."""
    key: str = "CT"
    operator: str = ">="             # ">=" | "<=" | "=="
    value: float = 0.0
    tolerance: float = 0.0           # band for "=="


@dataclass
class OptimizationDefinition:
    """A persisted design-optimization study (inputs/optimizations.bemt).

    The study varies bounded geometry parameters and drives one or two
    summary quantities on one flight condition toward their best found
    values. It carries no physics of its own: every evaluation is a plain
    ``run_single_case`` on a regenerated variant geometry.

    ``algorithm`` selects the family: Powell / Nelder-Mead (single
    objective, derivative-free, SC-8), differential evolution (global,
    single objective) or NSGA-II (multi-objective Pareto front,
    SC-13)."""
    name: str = "optimization 1"
    # --- legacy single-objective pair (still written for one release so
    # an older build can read the file; superseded by `objectives`) ---
    objective_kind: str = "maximize"   # "maximize" | "minimize"
    objective_key: str = "FM"
    variables: list[DesignVariable] = field(default_factory=list)
    method: str = "powell"             # legacy alias of `algorithm`
    max_evals: int = 40
    condition: Optional[FlightCondition] = None
    # --- SC-13 extensions ---
    objectives: list[ObjectiveDef] = field(default_factory=list)
    constraints: list[ConstraintDef] = field(default_factory=list)
    algorithm: str = ""                # "" falls back to `method`
    population: int = 40
    generations: int = 25
    seed: int = 0
    crossover_eta: float = 15.0
    mutation_eta: float = 20.0
    mutation_rate: float = 0.0   # 0 means one over the variable count
    parallel_workers: int = 1


def migrate_optimization_raw(raw: dict) -> dict:
    """Migrates an ``optimizations.bemt`` entry saved before SC-13: when
    ``objectives`` is absent/empty and the legacy ``objective_key`` is
    set, builds the one-element list from the legacy pair. The legacy
    fields stay on the dataclass and are still written, so an OLDER
    build keeps reading the file for one release."""
    migrated = dict(raw)
    objectives = migrated.get("objectives")
    if not objectives and migrated.get("objective_key"):
        migrated["objectives"] = [{
            "key": migrated["objective_key"],
            "kind": migrated.get("objective_kind", "maximize"),
            "weight": 1.0,
        }]
    return migrated


@dataclass
class DerivativeRequest:
    """One stability-derivative study (SC-14): which states and controls
    to perturb, about which trim point, and with which finite-difference
    steps. Persisted as ``inputs/derivatives.bemt``."""
    name: str = "derivatives 1"
    condition: Optional[FlightCondition] = None
    #: "none" | "thrust" | "cyclic_flapback" -- the trim that fixes the
    #: reference controls before any perturbation.
    trim: str = "cyclic_flapback"
    trim_target_thrust: Optional[float] = None   # "thrust" trim only
    states: list[str] = field(default_factory=list)      # u,v,w,p,q,Omega
    controls: list[str] = field(default_factory=list)    # theta_0,1c,1s
    outputs: list[str] = field(default_factory=list)     # summary keys
    steps: dict = field(default_factory=dict)            # per-variable override
    richardson_check: bool = True
    parallel_workers: int = 1
    #: The optional rigid-body model (phase 4.3). These describe the
    #: AIRCRAFT, not the rotor, so they cannot be derived from the
    #: geometry and have to be stated. They used to live only in the
    #: window's spin boxes, which put them outside the `.bemt` file and
    #: outside the CLI, against `PA-3`; the defaults below are exactly
    #: the values those spin boxes were born with, so a study saved
    #: before this existed builds the same matrices.
    vehicle_enabled: bool = False
    vehicle_mass_kg: float = 100.0
    vehicle_Ix_kg_m2: float = 50.0
    vehicle_Iy_kg_m2: float = 80.0
    vehicle_Iz_kg_m2: float = 20.0
    #: Hub position relative to the centre of gravity, in metres,
    #: (x forward, y starboard, z ABOVE the CG). A rotor above the CG is
    #: what turns a hub force into a moment about it, so a zero here is
    #: a real modelling choice and not a neutral default.
    hub_offset_x_m: float = 0.0
    hub_offset_y_m: float = 0.0
    hub_offset_z_m: float = 0.0
    gravity_m_s2: float = 9.81


@dataclass
class VariantDef:
    """A comparison variant that may carry more than the planform
    (SC-7a): besides the geometry it may bring its own single airfoil
    and blade-dynamics block. When either extra is present the run is
    NOT geometry alone, and the comparison must say so beside its
    ranking."""
    geometry: RotorGeometryDef
    airfoil: Optional[AirfoilDef] = None
    dynamics: Optional[BladeDynamicsDef] = None


@dataclass
class ComparisonVariantRow:
    """One saved variant row of a comparison (SC-7a): its label and the
    override cells as ``param -> value``."""
    label: str = "variant"
    overrides: dict = field(default_factory=dict)


@dataclass
class ComparisonDefinition:
    """A persisted geometry comparison (SC-7a,
    ``inputs/comparisons.bemt``): the variant rows as override maps, the
    conditions they run, and the trim mode of the run. Saving makes a
    comparison re-runnable and reviewable instead of strictly session
    data."""
    name: str = "comparison 1"
    variants: list[ComparisonVariantRow] = field(default_factory=list)
    conditions: list[FlightCondition] = field(default_factory=list)
    trim: str = "none"     # "none" | "thrust" | "CT"


@dataclass
class OptimizationOutcome:
    """Result of one design-optimization run (in memory only)."""
    best_params: dict = field(default_factory=dict)
    best_value: float = float("nan")
    objective_key: str = ""
    objective_kind: str = "maximize"
    history: list[dict] = field(default_factory=list)
    best_results: Optional[Any] = None   # Results of the best evaluation
    n_evals: int = 0
    message: str = ""


@dataclass
class Results:
    """Lightweight container for the result of one case/batch. The real
    DataFrame (aggregated rows) and the 2D maps (optional) stay outside
    the formal dataclass for I/O simplicity. This object is what
    circulates in memory between api.py, studies.py, plots.py."""
    summary: dict = field(default_factory=dict)   # CT, CQ, CP, FM, H, Y, Mx, My ...
    dataframe: Any = None    # pandas.DataFrame or None
    maps: dict = field(default_factory=dict)       # for example: {"CT_map": ndarray, ...}
    condition_name: str = ""


@dataclass
class ResultEntry:
    """One entry in the GUI's session results history (``ResultsTab``,
    docs/plano_v3.md Part 4.1). Each execution (Run Case OR Run Batch)
    ``append``s to ``AppState.results_history`` and never replaces what was
    already there (unlike the old single-overwrite ``last_results``). NOT
    persisted to ``.bemt`` (docs/plano_v3.md Section 4.4: computed results
    are expensive and ephemeral, the history is "per session", cleared
    when switching/closing the project). It lives here, and not in
    ``gui.py``, only so that ``plots.flatten_selection`` and
    ``test_plots.py``'s tests can use it without depending on PyQt6."""
    id: str
    label: str
    kind: str            # "case" | "batch"
    results: Any          # Results (kind="case") | list[Results] (kind="batch")
    timestamp: str = ""


# =============================================================================
# Project
# =============================================================================

@dataclass
class Project:
    name: str = "new_project"
    path: str = ""   # project root folder on disk

    config: dict = field(default_factory=dict)          # BEMTConfig as dict (asdict)
    geometry: RotorGeometryDef = field(default_factory=RotorGeometryDef)
    airfoil: AirfoilDef = field(default_factory=AirfoilDef)
    # Multi-section airfoil (Phase D, docs/plano.md Section 4): EMPTY list
    # (default, behavior as always) = the whole blade uses `airfoil`
    # above. 2+ elements (each with `r_norm` set) = the airfoil varies
    # along the radius. `airfoil` above is then ignored by the engine
    # (airfoils.to_blade_airfoil), but continues to be saved/kept as a
    # fallback in case the user switches back to "single airfoil". A list
    # with exactly 1 element is not a valid state. See
    # validation.validate_project.
    airfoil_sections: list[AirfoilDef] = field(default_factory=list)
    # v3 Part 3: list of NAMED batches/cases persisted in the project, what
    # what the GUI ("Batches defined in this project"/"Saved cases" list)
    # and the CLI (`--from-bemt-batch`/`--from-bemt-case`) read and write.
    # The legacy singular `batch` field/`batch.bemt` file no longer
    # exists: `api.load_project` migrates any old `batch.bemt` into this
    # list (as its first entry) the first time an old project is opened.
    batches: list[BatchDefinition] = field(default_factory=list)
    saved_cases: list[FlightCondition] = field(default_factory=list)
    # Design tools: named optimization studies persisted as
    # inputs/optimizations.bemt (same lifecycle as `batches`).
    optimizations: list[OptimizationDefinition] = field(default_factory=list)
    # Transients (SC-12): named maneuvers persisted as
    # inputs/maneuvers.bemt.
    maneuvers: list[ManeuverDefinition] = field(default_factory=list)
    # Stability derivatives (SC-14): named perturbation studies persisted
    # as inputs/derivatives.bemt.
    derivatives: list["DerivativeRequest"] = field(default_factory=list)
    # Persisted geometry comparisons (SC-7a):
    # inputs/comparisons.bemt.
    comparisons: list["ComparisonDefinition"] = field(default_factory=list)


def default_project_paths(project_path: str) -> dict:
    root = Path(project_path)
    return {
        "root": root,
        "inputs": root / "inputs",
        "outputs": root / "outputs",
        "config": root / "inputs" / "config.bemt",
        "geom": root / "inputs" / "geom.bemt",
        "airfoil": root / "inputs" / "airfoil.bemt",
        "airfoil_sections": root / "inputs" / "airfoil_sections.bemt",
        # Read-only: old projects' singular batch, migrated into
        # `batches` on load (see `api.load_project`). Never written again.
        "legacy_batch": root / "inputs" / "batch.bemt",
        "batches": root / "inputs" / "batches.bemt",
        "saved_cases": root / "inputs" / "saved_cases.bemt",
        "optimizations": root / "inputs" / "optimizations.bemt",
        "maneuvers": root / "inputs" / "maneuvers.bemt",
        "derivatives": root / "inputs" / "derivatives.bemt",
        "comparisons": root / "inputs" / "comparisons.bemt",
        "meta": root / "inputs" / "meta.bemt",
    }
