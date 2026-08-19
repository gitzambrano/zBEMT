"""
models.py
=========

Project data models (dataclasses) and serialization to ``.bemt`` (JSON)
files.

This file does NOT contain physics nor geometry/polar generation — only
the data structure and how it turns into/back from disk. The physics
lives in ``bemt.py`` (engine), 3D geometry generation in ``geometry.py``,
and everything that is 2D (airfoil aerodynamic model + profile geometry)
in ``airfoils.py``.

General convention: every ``...Def`` is "raw" data, editable by the GUI
and serializable. The physics classes that the engine (``bemt.py``)
actually uses (``AnalyticalAirfoil``, ``TableAirfoil``, ``Rotor``,
``BEMTConfig`` etc.) are constructed from these, never duplicated here.
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass, field, asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np


# =============================================================================
# Generic .bemt (JSON) serialization utility
# =============================================================================

#: NaN and Infinity do NOT exist in JSON. Python's `json` writes them as
#: `NaN`/`Infinity` literals -- which it reads back itself, but which make
#: any other reader (jq, JavaScript, a strict parser) reject the whole
#: file. A `.bemt` is an interchange format, so they become strings and
#: turn back into float on read. A NaN can genuinely land here: an
#: imported polar point that did not converge, a numeric field left blank.
_NAO_FINITOS = {float("inf"): "Infinity", float("-inf"): "-Infinity"}
_NAO_FINITOS_INVERSO = {"NaN": float("nan"), "Infinity": float("inf"),
                        "-Infinity": float("-inf")}


def _float_jsonable(v: float) -> Any:
    if v != v:              # NaN is not equal to itself
        return "NaN"
    return _NAO_FINITOS.get(v, v)


def _from_jsonable_scalar(v: Any) -> Any:
    if isinstance(v, str) and v in _NAO_FINITOS_INVERSO:
        return _NAO_FINITOS_INVERSO[v]
    if isinstance(v, list):
        return [_from_jsonable_scalar(x) for x in v]
    if isinstance(v, dict):
        return {k: _from_jsonable_scalar(x) for k, x in v.items()}
    return v


def _to_jsonable(obj: Any) -> Any:
    """Converts dataclasses (recursively), numpy arrays, tuples etc. into
    something ``json.dump`` accepts directly."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating,)):
        return _float_jsonable(float(obj))
    if isinstance(obj, float):
        return _float_jsonable(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj


def save_bemt(obj: Any, path: str) -> None:
    """Saves any dataclass from the module (or plain dict) as ``.bemt``
    JSON. Creates the parent directories if needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(_to_jsonable(obj), f, indent=2, ensure_ascii=False)


def load_bemt(cls: type, path: str) -> Any:
    """Loads a ``.bemt`` (JSON) file and rebuilds the ``cls`` dataclass.
    Does a shallow recursive reconstruction: fields that are themselves
    dataclasses or lists of dataclasses are resolved via ``cls``'s type
    annotations when possible; otherwise the value is passed through as
    it came from JSON (dict/list/primitive)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return _from_jsonable(cls, raw)


def save_bemt_list(items: list, path: str) -> None:
    """Like ``save_bemt``, but for a LIST of dataclasses (e.g.
    ``Project.airfoil_sections`` -- Phase D, multi-section airfoil). Reuses
    the same ``_to_jsonable`` (already knows how to serialize lists of
    dataclasses)."""
    save_bemt(list(items), path)


def load_bemt_list(cls: type, path: str) -> list:
    """Counterpart of ``save_bemt_list``: loads a list of ``cls``
    dataclasses saved by it."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [_from_jsonable(cls, v) for v in raw]


def _migrate_airfoil_raw(raw: dict) -> dict:
    """Migrates an ``AirfoilDef`` dict saved under the old schema (with
    ``use_viterna_extension``/``blend_with_viterna``/``extrapolate_full_range``
    and/or ``use_compressibility``) to the current schema. See
    docs/plano_v2.md Section 7 -- ``_from_jsonable`` already ignores
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
    # Viterna through that field instead of stall_model -- migrate to the
    # current schema preserving the same physical behavior (see
    # `models.uses_full_range_extension`).
    #
    # The migration only applies to REALLY old files, i.e. without the
    # `stall_model` key. It used to also run on files already in the
    # current schema, and since the AirfoilDef default has
    # extend_full_range=True, ANY stall_model other than 'viterna' was
    # silently reverted on load -- in practice the field was impossible to
    # change without also turning off extend_full_range, both from the GUI
    # and the CLI.
    src = migrated.get("source", "analytical")
    if ("stall_model" not in raw and src in ("analytical", "external")
            and migrated.get("extend_full_range")):
        migrated["stall_model"] = "viterna"
        changed = True

    return migrated if changed else raw


def migrar_config_raw(raw: dict) -> dict:
    """Migrates a ``config.bemt`` from the old schema. Currently: the
    boolean ``use_prandtl_loss`` became the enum ``prandtl_loss_mode``
    (which distinguishes tip, root and both). Without this migration the
    field was silently discarded -- including in the repository's
    reference project, which stored ``use_prandtl_loss: true`` and had
    been running with the default."""
    migrado = dict(raw)
    if "use_prandtl_loss" in migrado:
        antigo = bool(migrado.pop("use_prandtl_loss"))
        migrado.setdefault("prandtl_loss_mode", "both" if antigo else "none")
    return migrado


def avisar_chaves_desconhecidas(cls: type, raw: dict, contexto: str = "") -> list[str]:
    """Warns (``UserWarning``) about keys in the file that ``cls`` does
    not have.

    The previous behavior was to silently discard them: a field renamed
    between versions fell back to the default and the user only found out
    from the wrong result. They are still discarded -- what changes is
    that it now says so. Returns the list, for anyone who wants to handle
    it."""
    known = {f.name for f in fields(cls)}
    unknown = sorted(k for k in raw if k not in known)
    if unknown:
        where = f" in {contexto}" if contexto else ""
        warnings.warn(
            f"{cls.__name__}{where}: {len(unknown)} field(s) from file "
            f"do not exist in current schema and were ignored "
            f"({', '.join(unknown)}). A field renamed in a newer version "
            f"falls back to its default -- check whether the value you "
            f"saved is still being used.", UserWarning, stacklevel=3)
    return unknown


def _from_jsonable(cls: type, raw: Any) -> Any:
    if raw is None:
        return None
    if not is_dataclass(cls):
        return raw
    if cls is AirfoilDef and isinstance(raw, dict):
        raw = _migrate_airfoil_raw(raw)
    if isinstance(raw, dict):
        avisar_chaves_desconhecidas(cls, raw)
    kwargs = {}
    type_hints = {f.name: f.type for f in fields(cls)}
    for f in fields(cls):
        if f.name not in raw:
            continue
        val = raw[f.name]
        ftype = type_hints[f.name]
        kwargs[f.name] = _coerce_field(ftype, _from_jsonable_scalar(val))
    return cls(**kwargs)


def _coerce_field(ftype: Any, val: Any) -> Any:
    # Resolves type strings (from __future__ import annotations) only in
    # the cases where we actually need to rebuild as a nested dataclass.
    type_name = ftype if isinstance(ftype, str) else getattr(ftype, "__name__", "")
    registry = {
        "ProfileGeometry": ProfileGeometry,
        "PolarSlice": PolarSlice,
        "RotorGeometryDef": RotorGeometryDef,
        "AirfoilDef": AirfoilDef,
        "FlightCondition": FlightCondition,
        "BatchDefinition": BatchDefinition,
    }
    for name, klass in registry.items():
        if name in str(type_name):
            if isinstance(val, list):
                return [_from_jsonable(klass, v) if isinstance(v, dict) else v for v in val]
            if isinstance(val, dict):
                return _from_jsonable(klass, val)
    return val


# =============================================================================
# 2D — everything airfoil-related (aerodynamic model + profile geometry)
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
    label: str = ""   # free-form label, e.g. "root", "tip", imported file name


@dataclass
class ProfileGeometry:
    """2D profile geometry (x,y coordinates). Only needed when a polar is
    to be generated via an external engine (NeuralFoil — Phase 7); for the
    analytical/table models it is optional/illustrative."""
    source: str = "naca4"          # "naca4" | "naca5" | "cst" | "bezier" | "imported"
    naca_code: str = "0012"
    cst_upper: list[float] = field(default_factory=list)
    cst_lower: list[float] = field(default_factory=list)
    bezier_control_points: list[list[float]] = field(default_factory=list)
    imported_path: Optional[str] = None
    n_points: int = 200

    # generated coordinates (cache — does not need to be filled to save;
    # airfoils.py recomputes them from the parameters above when needed)
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)


@dataclass
class AirfoilDef:
    """Complete, unified definition of the airfoil's 2D behavior:
    aerodynamic model (analytical or table-based, with or without dynamic
    stall) + profile geometry (for polar generation via NeuralFoil, Phase
    7). See docs/plano.md Section 4.1 / 8.3 and docs/plano_v2.md Section
    2.4.

    Architecture note (plano_v2 Section 2.4): this dataclass gathers the
    orthogonal axes A (source), B (analytical model/static stall), C
    (full range extension) and D (dynamic stall) of the airfoil's
    behavior. Compressibility (axis E) and reverse flow (axis F) are a
    property of the ENGINE and live only in BEMTConfig (bemt.py) -- there
    is no longer an equivalent field here (plano_v2 Finding #2)."""
    name: str = "unnamed airfoil"

    # --- radial position of the section (Phase D — multi-section airfoil) ---
    # None = this AirfoilDef is the SINGLE airfoil for the whole blade
    # (normal use, via Project.airfoil) -- behavior as always, unchanged.
    # Only becomes meaningful when this object lives inside
    # Project.airfoil_sections (2+ elements, each with r_norm MANDATORILY
    # set): in that case it represents "the airfoil AT THIS radial
    # station", and airfoils.to_blade_airfoil() interpolates the resulting
    # Cl/Cd between neighboring sections
    # (bemt.HeterogeneousMultiSectionAirfoil).
    r_norm: Optional[float] = None

    # --- A. source of the aerodynamic model ---
    source: str = "analytical"     # "analytical" | "table" | "external" (future)

    # --- B. analytical model (linear + static stall) ---
    cl_alpha: float = 2 * math.pi
    alpha0_deg: float = -4.5
    cd0: float = 0.0155
    k: float = 0.0
    alpha_stall_pos_deg: float = 15.0
    alpha_stall_neg_deg: float = -6.0
    # "linear" (no stall) | "clip" (clipped stall) | "enhanced" (smoothed
    # non-linear stall) | "viterna" (Viterna-Corrigan extension -- see note
    # below). The 4 options are MUTUALLY EXCLUSIVE: there is no
    # combination of "clip"/"enhanced" with Viterna -- when "viterna" is
    # chosen, the PRE-stall curve used as base is always the pure linear
    # line (no clamp), extended via Viterna-Corrigan from
    # `alpha_stall_pos_deg`/`alpha_stall_neg_deg` (see
    # `airfoils.build_analytical`/`apply_viterna_extension`).
    # Default "viterna": matches the previous default of
    # `extend_full_range=True` (full range extension on by default, see
    # field below) and `BEMTConfig.reverse_flow_model=
    # 'viterna_full_range'` (bemt.py Sec.6).
    stall_model: str = "viterna"

    # --- C. full range extension (-180..+180, Viterna-Corrigan) ---
    # For `source='analytical'` (or 'external'), Viterna stopped being an
    # independent toggle: it is the "viterna" option of `stall_model`
    # above itself -- this field is ignored in that case (see
    # `models.uses_full_range_extension`, the single source of truth on
    # whether full range extension is active).
    # For `source='table'`, it remains the user's explicit choice to
    # EXTRAPOLATE the imported table beyond the last real point with
    # Viterna-Corrigan (the table itself never has a "stall_model" -- it
    # is data, not a model -- which is why Viterna remains a separate
    # option here instead of merging into an enum the table does not
    # have).
    # Default True: matches the default of BEMTConfig.reverse_flow_model=
    # 'viterna_full_range' (bemt.py Sec.6) -- without this on, that engine
    # default would fall into an invalid combination (see
    # validation.validate_config).
    extend_full_range: bool = True

    # Width (degrees) of the smooth (C1-continuous) transition window
    # between the base model and the Viterna-Corrigan extrapolation -- see
    # `bemt.ViternaExtendedAirfoil`. Replaces the old abrupt switch
    # exactly at alpha_stall (which produced a "kink"/slope discontinuity)
    # with a gradual blend, both for `source='analytical'` and
    # `source='table'`. For tables, CLmax/CLmin and the corresponding
    # stall angles are ALWAYS detected automatically from the table itself
    # (argmax/argmin of Cl) -- `alpha_stall_pos_deg`/`alpha_stall_neg_deg`
    # above are ignored in that case (they only apply to
    # `source='analytical'`) -- and the extrapolation only kicks in beyond
    # the last real table point on each side, never overwriting existing
    # tabulated data. Note: since it is a C1-continuous (not C2)
    # interpolation, the real Cl peak may fall slightly before alpha_stall
    # with a value slightly above Cl_stall (~1-2% for the default) -- see
    # the detailed note in `ViternaExtendedAirfoil`. Lower this value for a
    # peak closer to the one defined, at the cost of a more abrupt
    # transition.
    viterna_blend_width_deg: float = 4.0

    # --- D. dynamic stall (Øye) -- SINGLE copy (plano_v2.md Finding #1) ---
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

    # --- external engine (Phase 7 — see external_solvers.py) ---
    external_engine: str = "none"      # "none" | "neuralfoil" (XFOIL is not supported)
    external_reynolds_list: list[float] = field(default_factory=list)
    external_mach_list: list[float] = field(default_factory=list)
    external_alpha_min_deg: float = -20.0
    external_alpha_max_deg: float = 20.0
    external_alpha_step_deg: float = 0.5


def uses_full_range_extension(a: "AirfoilDef") -> bool:
    """SINGLE source of truth on whether the Viterna-Corrigan full range
    extension (-180..+180) is active for this `AirfoilDef`, given that the
    choice no longer lives in a single field (see notes on
    `AirfoilDef.stall_model`/`extend_full_range` above):

    - `source='table'`: it is literally `extend_full_range` (explicit
      toggle for extrapolating the imported table).
    - any other source (`'analytical'`/`'external'`): it is
      `stall_model == 'viterna'` -- `extend_full_range` is ignored.

    Used by `airfoils.to_airfoil()` (decides whether to wrap the result in
    `ViternaExtendedAirfoil`) and by `validation.validate_config` (checks
    whether `reverse_flow_model='viterna_full_range'` really has an
    extended polar behind it).
    """
    if a.source == "table":
        return a.extend_full_range
    return a.stall_model == "viterna"


# =============================================================================
# 3D — rotor/blade geometry
# =============================================================================

@dataclass
class RotorGeometryDef:
    """Radial table of the blade (always the canonical on-disk
    representation, regardless of whether it was generated from
    parameters or edited point by point in the graphical editor)."""
    r_norm: list[float] = field(default_factory=list)   # r/R, 0..1
    chord_norm: list[float] = field(default_factory=list)  # c/R
    twist_deg: list[float] = field(default_factory=list)

    origin: str = "parametric"   # "parametric" | "table" | "editor" (metadata/label only)
    origin_params: dict = field(default_factory=dict)   # e.g.: {"kind": "tapered", "root_chord": .., "tip_chord": ..}

    n_blades: int = 2
    radius_m: float = 1.0
    root_cutout_norm: float = 0.15

    #: Free-form label, metadata only: NOTHING in the engine reads this
    #: field, and it has no link to `AirfoilDef.name` nor does it select a
    #: polar. `Project.airfoil` (or `airfoil_sections`, by r_norm) is what
    #: decides the airfoil.
    #: Free-form label, metadata only (Q5): NOTHING in the engine reads
    #: this field. It has no link to `AirfoilDef.name` and does not select
    #: any polar -- `Project.airfoil`, or `airfoil_sections` by r_norm, is
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
    collective_deg: float = 8.0
    Vz: float = 0.0                 # vertical velocity [m/s]
    rpm: Optional[float] = None     # if None, uses Omega from BEMTConfig/Rotor


@dataclass
class BatchDefinition:
    name: str = "batch 1"
    conditions: list[FlightCondition] = field(default_factory=list)
    sweep_kind: str = "custom"   # "custom" | "mu_sweep" | "alpha_sweep" | "collective_sweep" | "factorial"
    sweep_params: dict = field(default_factory=dict)
    outdir: Optional[str] = None
    plots: list[str] = field(default_factory=list)


@dataclass
class Results:
    """Lightweight container for the result of one case/batch. The real
    DataFrame (aggregated rows) and the 2D maps (optional) stay outside
    the formal dataclass for I/O simplicity — this object is what
    circulates in memory between api.py, studies.py, plots.py."""
    summary: dict = field(default_factory=dict)   # CT, CQ, CP, FM, H, Y, Mx, My ...
    dataframe: Any = None    # pandas.DataFrame or None
    maps: dict = field(default_factory=dict)       # e.g.: {"CT_map": ndarray, ...}
    condition_name: str = ""


@dataclass
class ResultEntry:
    """One entry in the GUI's session results history (``ResultsTab``,
    docs/plano_v3.md Part 4.1). Each execution (Run Case OR Run Batch)
    ``append``s to ``AppState.results_history`` -- never replaces what was
    already there (unlike the old single-overwrite ``last_results``). NOT
    persisted to ``.bemt`` (docs/plano_v3.md Section 4.4: computed results
    are expensive and ephemeral, the history is "per session", cleared
    when switching/closing the project) -- lives here, and not in
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
    name: str = "novo_projeto"
    path: str = ""   # project root folder on disk

    config: dict = field(default_factory=dict)          # BEMTConfig as dict (asdict)
    geometry: RotorGeometryDef = field(default_factory=RotorGeometryDef)
    airfoil: AirfoilDef = field(default_factory=AirfoilDef)
    # Multi-section airfoil (Phase D, docs/plano.md Section 4): EMPTY list
    # (default, behavior as always) = the whole blade uses `airfoil`
    # above. 2+ elements (each with `r_norm` set) = the airfoil varies
    # along the radius; `airfoil` above is then ignored by the engine
    # (airfoils.to_blade_airfoil), but continues to be saved/kept as a
    # fallback in case the user switches back to "single airfoil". A list
    # with exactly 1 element is not a valid state -- see
    # validation.validate_project.
    airfoil_sections: list[AirfoilDef] = field(default_factory=list)
    # v3 Part 3: list of NAMED batches/cases persisted in the project --
    # what the GUI ("Batches defined in this project"/"Saved cases" list)
    # and the CLI (`--from-bemt-batch`/`--from-bemt-case`) read and write.
    # The legacy singular `batch` field/`batch.bemt` file no longer
    # exists: `api.load_project` migrates any old `batch.bemt` into this
    # list (as its first entry) the first time an old project is opened.
    batches: list[BatchDefinition] = field(default_factory=list)
    saved_cases: list[FlightCondition] = field(default_factory=list)


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
        "meta": root / "inputs" / "meta.bemt",
    }
