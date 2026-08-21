"""Provide the application boundary for project I/O, execution, and exports.

The module accepts project paths, model definitions, flight conditions,
batches, and callback options. It creates, validates, loads, saves, runs, and
exports projects. It returns ``Project``, ``Results``, serialized ``.bemt``
data, tables, figures, and reports. Public operations cover project lifecycle,
case and batch execution, polar generation, and result export. GUI and CLI
callers use this boundary. It delegates physics, geometry, airfoil
construction, and nomenclature to their dedicated modules. It also owns the
direct project-file access. The selected models, the validity of the inputs,
and the convergence status all limit the results.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from .models import (
    Project, RotorGeometryDef, AirfoilDef, FlightCondition, BatchDefinition,
    Results, PolarSlice, ProfileGeometry,
    save_bemt, load_bemt, save_bemt_list, load_bemt_list, default_project_paths,
)
from . import geometry
from . import airfoils
from . import external_solvers
from . import models
from . import nomenclature
from . import studies
from . import validation
from .bemt import BEMTConfig


# =============================================================================
# Project: new / open / save
# =============================================================================

def new_project(path: str, name: Optional[str] = None) -> Project:
    project = Project(
        name=name or Path(path).name,
        path=str(path),
        config=asdict(BEMTConfig()),
        geometry=geometry.generate_tapered(airfoil_name="perfil 1"),
        airfoil=AirfoilDef(name="perfil 1"),
        airfoil_sections=[],
        batches=[],
        saved_cases=[],
    )
    save_project(project)
    return project


def project_outputs_dir(project_or_path, create: bool = False) -> str:
    """The ``outputs/`` folder of a project.

    This is the canonical definition, in one place.

    Accepts a `Project` (uses `project.path`) or the path to the project
    folder. Returns ``"outputs"`` (relative to the current directory) when
    there is no project path: it is the same fallback the GUI and CLI
    already used, so that a project not yet saved keeps exporting instead
    of raising an error.

    ``create=True`` creates the folder (and its parents) before returning.

    Exists because `<project>/outputs` was hand-written in at least four
    places (Run Case, Run Batch, Results, CLI). A repeated literal is not
    a bug today, but it is the mechanism by which one surface's output
    folder silently drifts from the others' -- exactly the problem `api`
    exists to not have."""
    caminho = getattr(project_or_path, "path", project_or_path)
    if not caminho:
        destino = Path("outputs")
    else:
        destino = default_project_paths(str(caminho))["outputs"]
    if create:
        destino.mkdir(parents=True, exist_ok=True)
    return str(destino)


def open_project(path: str) -> Project:
    paths = default_project_paths(path)
    config = {}
    if paths["config"].exists():
        import json
        from .models import (_from_jsonable_scalar, avisar_chaves_desconhecidas,
                             migrar_config_raw)
        config = json.loads(paths["config"].read_text(encoding="utf-8"))
        # `config` is a raw dict (not a dataclass), so it does not go
        # through `_from_jsonable` -- it needs the same NaN/Infinity
        # decoding and the same unknown-field warning that the rest of
        # the project receives, or a `config.bemt` from an earlier
        # version silently loses fields. See Q1 in production-plan.md.
        config = migrar_config_raw(_from_jsonable_scalar(config))
        avisar_chaves_desconhecidas(BEMTConfig, config, contexto=str(paths["config"]))
    # Q1 (production-plan.md): the name given in the GUI (which may
    # differ from the folder name) must survive the save/reopen cycle.
    # Older projects (without meta.bemt) still fall back to the usual
    # default (folder name) -- backward compatible.
    name = Path(path).name
    if paths["meta"].exists():
        import json
        meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
        name = meta.get("name", name)
    geom = load_bemt(RotorGeometryDef, paths["geom"]) if paths["geom"].exists() else RotorGeometryDef()
    airfoil_def = load_bemt(AirfoilDef, paths["airfoil"]) if paths["airfoil"].exists() else AirfoilDef()
    airfoil_sections = (load_bemt_list(AirfoilDef, paths["airfoil_sections"])
                         if paths["airfoil_sections"].exists() else [])
    # The axis letters the flight conditions are stored under depend on the
    # project's mode, which `config.bemt` (already loaded above) carries.
    # `config.bemt`, `geom.bemt` and `airfoil*.bemt` hold no axis quantity,
    # so only the two condition files below need it. See
    # `zbemt.nomenclature`.
    is_propeller = bool((config or {}).get("is_propeller", False))
    batches = (load_bemt_list(BatchDefinition, paths["batches"], is_propeller)
               if paths["batches"].exists() else [])
    if paths["legacy_batch"].exists():
        # Migration: an old project may carry a legacy singular
        # `batch.bemt` (from before `batches.bemt`/named batches
        # existed). Its content is NOT always redundant with what is
        # already in `batches.bemt` -- a project can have both a
        # still-useful legacy batch (often a PARAMETRIC definition,
        # sweep_kind+sweep_params with `conditions` empty) and an
        # unrelated list of named batches. Checking only `conditions`
        # silently dropped every parametric legacy batch. Fold it in as
        # an extra entry (unless it is already there verbatim) so it
        # survives the next `save_project` -- which also deletes
        # `batch.bemt`, so this only ever runs once per project.
        legado = load_bemt(BatchDefinition, paths["legacy_batch"], is_propeller)
        tem_conteudo = bool(legado.conditions) or bool(legado.sweep_params)
        if tem_conteudo and legado not in batches:
            batches.append(legado)
    saved_cases = (load_bemt_list(FlightCondition, paths["saved_cases"],
                                  is_propeller)
                   if paths["saved_cases"].exists() else [])
    return Project(name=name, path=str(path), config=config,
                    geometry=geom, airfoil=airfoil_def, airfoil_sections=airfoil_sections,
                    batches=batches, saved_cases=saved_cases)


def save_project(project: Project) -> None:
    paths = default_project_paths(project.path)
    import json
    paths["meta"].parent.mkdir(parents=True, exist_ok=True)
    paths["meta"].write_text(json.dumps({"name": project.name}, ensure_ascii=False), encoding="utf-8")
    is_propeller = bool((project.config or {}).get("is_propeller", False))
    save_bemt(project.config, paths["config"])
    save_bemt(project.geometry, paths["geom"])
    save_bemt(project.airfoil, paths["airfoil"])
    save_bemt_list(project.airfoil_sections, paths["airfoil_sections"])
    # Only these two carry flight conditions, and therefore axis letters.
    save_bemt_list(project.batches, paths["batches"], is_propeller)
    save_bemt_list(project.saved_cases, paths["saved_cases"], is_propeller)
    # Migration cleanup: only after the (possibly migrated, see
    # `load_project`) batches are safely persisted into `batches.bemt` is
    # the old singular `batch.bemt` certainly redundant -- remove it so it
    # is not folded in again (duplicated) on the next open.
    if paths["legacy_batch"].exists():
        paths["legacy_batch"].unlink()


# =============================================================================
# Named, persisted batches/cases (docs/plano_v3.md Part 3) — used by the
# GUI ("Batches defined in this project"/"Saved cases" list) and by the
# CLI (`--from-bemt-batch`/`--from-bemt-case`, `--list-batches`/`--list-cases`
# in main_batch.py). `Project.batches`/`saved_cases` are the single
# source of truth; these functions just avoid repeating the by-name
# lookup in both consumers.
# =============================================================================

def get_batch(project: Project, name: str) -> BatchDefinition:
    for b in project.batches:
        if b.name == name:
            return b
    raise KeyError(f"batch '{name}' not found in project.batches "
                    f"(available: {[b.name for b in project.batches]})")


def get_saved_case(project: Project, name: str) -> FlightCondition:
    for c in project.saved_cases:
        if c.name == name:
            return c
    raise KeyError(f"case '{name}' not found in project.saved_cases "
                    f"(available: {[c.name for c in project.saved_cases]})")


def list_projects(projects_root: str = "projects") -> list[str]:
    root = Path(projects_root)
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


# =============================================================================
# Validation (checking mutually exclusive/redundant combinations — see
# validation.py; does not run the engine nor touch disk, but lives in
# api.py, not gui.py, so that main_batch.py/scripts can call the same
# check before running a large unsupervised batch)
# =============================================================================

def validate_project(project: Project, conditions=None) -> list[validation.Issue]:
    """``conditions`` (optional): the ``FlightCondition`` objects that will
    be run. Passing them, the check also covers each condition's RPM --
    a missing RPM falls back to a placeholder and a zero RPM breaks the
    engine's non-dimensionalization, and neither is visible just by
    looking at config/airfoil."""
    return validation.validate_project(project.config, project.airfoil,
                                       project.airfoil_sections, conditions=conditions,
                                       radius_m=project.geometry.radius_m)


# =============================================================================
# Execution (always in memory, never writes to disk)
# =============================================================================
#
# These functions are "dumb" on purpose (Section 4 of the plan): they
# just forward to studies.py, which knows how to build a Rotor/BEMTConfig
# from the project and orchestrate the engine across one or several
# conditions. No physics lives here.

def run_case(project: Project, condition: FlightCondition,
             should_cancel: Optional[Callable[[], bool]] = None) -> Results:
    """``should_cancel``: polled once per solver iteration. If it
    returns ``True``, raises ``bemt.SolveCancelled`` -- an interrupted
    solve does not converge, and returning it halfway would hand back
    half a solution dressed up as a result."""
    return studies.run_single_case(project, condition, should_cancel=should_cancel)


def run_case_trimmed(project: Project, condition: FlightCondition, *,
                      trim_mode: str, target_kind: str, target_value: float,
                      bracket: Optional[tuple] = None, tol: float = 1e-4, max_iter: int = 40,
                      should_cancel: Optional[Callable[[], bool]] = None) -> Results:
    """Runs ``condition`` holding ONE of the two trim DOFs fixed
    (collective or RPM) and solving the other by bisection until it hits
    a thrust/CT target -- see ``studies.run_case_trimmed`` for the full
    semantics of ``trim_mode``/``target_kind``/``bracket``."""
    return studies.run_case_trimmed(
        project, condition, trim_mode=trim_mode, target_kind=target_kind,
        target_value=target_value, bracket=bracket, tol=tol, max_iter=max_iter,
        should_cancel=should_cancel)


def run_batch(project: Project, batch: BatchDefinition, *,
              on_case_done: Optional[Callable[[int, int, object], None]] = None,
              should_cancel: Optional[Callable[[], bool]] = None,
              trim_mode: Optional[str] = None,
              target_kind: Optional[str] = None,
              target_value: Optional[float] = None) -> list[Results]:
    return studies.run_batch(project, batch, on_case_done=on_case_done,
                             should_cancel=should_cancel, trim_mode=trim_mode,
                             target_kind=target_kind, target_value=target_value)


# --- Sweeps and method comparison (Section 4 / studies.py) -----------------
# Exposed here so that gui.py/main_batch.py can use them without
# violating the "only call api.py" rule — under the hood, studies.py is
# always what actually runs.

def run_mu_sweep(project: Project, mu_values: Sequence[float], **kwargs) -> list[Results]:
    return studies.run_mu_sweep(project, mu_values, **kwargs)


def run_alpha_sweep(project: Project, alpha_deg_values: Sequence[float], **kwargs) -> list[Results]:
    return studies.run_alpha_sweep(project, alpha_deg_values, **kwargs)


def run_collective_sweep(project: Project, collective_deg_values: Sequence[float], **kwargs) -> list[Results]:
    return studies.run_collective_sweep(project, collective_deg_values, **kwargs)


def build_factorial_conditions(project: Project, axes: list[dict],
                                fixed: Optional[dict] = None) -> list[FlightCondition]:
    """Expands the Cartesian product of the axes WITHOUT running the engine.

    This is what allows reviewing the cases before firing off N solves."""
    return studies.build_factorial_conditions(project, axes, fixed)


def run_factorial_batch(project: Project, axes: list[dict], fixed: Optional[dict] = None, *,
                         on_case_done: Optional[Callable[[int, int, object], None]] = None,
                         should_cancel: Optional[Callable[[], bool]] = None) -> list[Results]:
    return studies.run_factorial_batch(project, axes, fixed,
                                        on_case_done=on_case_done, should_cancel=should_cancel)


def benchmark_solvers(project: Project, condition: FlightCondition,
                       solvers: Optional[Sequence[str]] = None) -> list[Results]:
    kwargs = {} if solvers is None else {"solvers": solvers}
    return studies.benchmark_solvers(project, condition, **kwargs)


# =============================================================================
# rotor<->propeller convention conversions (GUI v3 plan, Section 6/9,
# items 8-9) -- extracted from the same formulas already used internally
# by bemt.resolve_advance_velocity, just exposed as public, stateless
# utilities, so gui.py can convert mu_x<->J_x and alpha<->Vz in the Run
# Case/Run Batch fields without importing bemt.py directly (hard rule of
# gui.py: no physics lives in the GUI, only pass-through via api.py).
# =============================================================================

def mu_to_J(mu_x: float) -> float:
    """J_x = pi*mu_x (same convention as bemt.resolve_advance_velocity)."""
    return float(np.pi * mu_x)


def J_to_mu(J_x: float) -> float:
    return float(J_x) / np.pi


def omega_r(rpm: float, radius_m: float) -> float:
    """OmegaR [m/s] from RPM and radius [m]."""
    omega = float(rpm) * 2.0 * np.pi / 60.0
    return omega * float(radius_m)


def mu_to_V(mu_x: float, rpm: float, radius_m: float) -> float:
    """Longitudinal V_∞ [m/s] = mu_x * OmegaR.

    Third representation of the longitudinal slot (besides mu_x and
    J_x), used in the GUI when the user prefers to enter the advance
    velocity directly in m/s instead of non-dimensionalizing it."""
    return float(mu_x) * omega_r(rpm, radius_m)


def V_to_mu(V: float, rpm: float, radius_m: float) -> float:
    """Inverse of mu_to_V: mu_x = V / OmegaR."""
    om = omega_r(rpm, radius_m)
    if abs(om) < 1e-9:
        return 0.0
    return float(V) / om


def vv_from_alpha_deg(alpha_deg: float, mu_x: float, rpm: float, radius_m: float) -> float:
    """Vz = tan(alpha_rotor_deg) * mu_x * OmegaR (bemt.resolve_advance_velocity)."""
    vinf_long = float(mu_x) * omega_r(rpm, radius_m)
    return float(np.tan(np.deg2rad(alpha_deg))) * vinf_long


def alpha_deg_from_vv(Vz: float, mu_x: float, rpm: float, radius_m: float) -> float:
    vinf_long = float(mu_x) * omega_r(rpm, radius_m)
    if abs(vinf_long) < 1e-9:
        if Vz > 0:
            return 90.0
        if Vz < 0:
            return -90.0
        return 0.0
    return float(np.degrees(np.arctan2(float(Vz), vinf_long)))


# =============================================================================
# External polar generation via NeuralFoil (Phase 7, see external_solvers.py)
# =============================================================================

def run_external_polar(airfoil_def: AirfoilDef) -> list[PolarSlice]:
    """Runs the external engine configured in ``airfoil_def`` (today only
    ``"neuralfoil"`` is supported) over the geometry already defined in
    ``airfoil_def.geometry``, using the Reynolds/Mach/alpha sweep also
    already configured in ``airfoil_def.external_*``."""
    if airfoil_def.geometry is None:
        raise ValueError("AirfoilDef.geometry not defined — generate or import a profile geometry first.")
    return external_solvers.run_polar(
        engine=airfoil_def.external_engine,
        geometry=airfoil_def.geometry,
        reynolds_list=airfoil_def.external_reynolds_list,
        mach_list=airfoil_def.external_mach_list,
        alpha_min_deg=airfoil_def.external_alpha_min_deg,
        alpha_max_deg=airfoil_def.external_alpha_max_deg,
        alpha_step_deg=airfoil_def.external_alpha_step_deg,
    )


def run_external_polar_from_geometry(geometry: ProfileGeometry, *, engine: str = "neuralfoil",
                                      reynolds_list: Sequence[float], mach_list: Sequence[float],
                                      alpha_min_deg: float, alpha_max_deg: float,
                                      alpha_step_deg: float) -> list[PolarSlice]:
    """'Direct' variant of ``run_external_polar`` that does not require
    an open ``AirfoilDef``/project — used by the CLI (``--gen-neuralfoil``,
    Phase 7) to generate a table from just a geometry resolved by
    ``airfoils.resolve_geometry_spec``."""
    return external_solvers.run_polar(
        engine=engine, geometry=geometry,
        reynolds_list=list(reynolds_list), mach_list=list(mach_list),
        alpha_min_deg=alpha_min_deg, alpha_max_deg=alpha_max_deg,
        alpha_step_deg=alpha_step_deg,
    )


def export_polar_table(polar_slices: list[PolarSlice], path: str) -> Path:
    """Writes ``polar_slices`` (typically the return of
    ``run_external_polar``/``run_external_polar_from_geometry``) to CSV,
    in the SAME format that ``airfoils.detect_csv_axes``/``import_polar_csv``
    already know how to read back — closes the loop requested in Phase 7:
    generate via NeuralFoil -> save to disk -> reimport like any other
    table (useful for versioning, reusing across projects, or editing
    before reimporting)."""
    return airfoils.export_polar_slices_csv(polar_slices, path)


# =============================================================================
# Persistence / post-processing (explicit, separate from running)
# =============================================================================

# Convenience aliases for disk map field names (Section 7: the plan's
# example uses "disk_map_CT", but the elementary field that integrates
# into CT at each station is "Fn" — there is no literal per-element "CT",
# only the normal force which, integrated, becomes the global CT).
_DISK_MAP_FIELD_ALIASES = {
    "ct": "Fn", "thrust": "Fn", "fn": "Fn",
    "cq": "Ft", "torque": "Ft", "ft": "Ft",
    "inflow": "lambda_i", "lambda": "lambda_i", "lambda_i": "lambda_i",
    "alpha": "alpha_eff", "aoa": "alpha_eff", "alpha_eff": "alpha_eff",
    "mach": "Mach", "cl": "Cl", "cd": "Cd",
}


#: Characters illegal in a filename on Windows. `/` and `\` would also
#: break the path on Linux/macOS, so the list applies to all of them.
_CARACTERES_ILEGAIS = '<>:"/\\|?*'

#: Names reserved by Windows: `CON.png` fails even with an extension.
_NOMES_RESERVADOS = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

#: Margin for the prefix (`disk_map_lambda_i_`) and the extension within
#: the path limit; condition names longer than this are truncated.
_MAX_NOME = 80

#: ASCII transcription of the symbols `studies.nome_de_condicao` uses
#: (μ, α, θ₀, °...). The CONDITION name is Unicode on purpose -- it is
#: what the user reads in the table and in the report --, but the FILE
#: name derived from it lives in a zip, an email, and someone else's
#: filesystem, where "μ=0.1" has come back as "Î¼=0.1" more than once.
#: Only these symbols are transcribed: an accent in a name typed by the
#: user ("Caso Padrão") still passes through intact.
_TRANSCRICAO_ASCII = {
    "μ": "mu", "α": "alpha", "β": "beta", "θ": "theta", "λ": "lambda",
    "ψ": "psi", "φ": "phi", "Ω": "Omega", "η": "eta", "π": "pi",
    "₀": "0", "°": "deg", "·": ".", "∞": "inf", "×": "x", "±": "pm",
}


def sanitize_filename(nome: str, usados: Optional[set] = None) -> str:
    """Converts a flight condition name into a usable filename.

    Case names are free text typed by the user, and factorial batch
    names are built as ``f"{k}={v:g}"`` -- meaning a perfectly ordinary
    case like ``alpha=-5:mu_x=0.2`` contains ``:``, which is legal in a
    condition name and ILLEGAL in a filename on Windows. Without this,
    export would blow up in the middle of an already-run batch.

    What it does, and why this way:

    - transcribes to ASCII the symbols generated by
      `studies.nome_de_condicao` (``μ=0.1, α=-10°`` -> ``mu_x=0.1, alpha=-10deg``);
      see `_TRANSCRICAO_ASCII`;
    - replaces each illegal character with ``-``, instead of deleting it:
      deleting would turn ``mu_x=0.2/J_x=0.6`` into ``mu_x=0.2J=0.6``,
      which is confusing;
    - prefixes Windows reserved names (``CON``, ``COM1``…), which fail
      even with an extension;
    - truncates names that are too long for the path limit;
    - returns ``sem_nome`` for empty or only spaces/dots.

    ``usados``: set of names already emitted. Two DIFFERENT names can
    sanitize to the same text (``a:b`` and ``a?b`` both become ``a-b``)
    and one would silently overwrite the other's file -- pass the set so
    that collisions get a numeric suffix. The function updates it."""
    nome = "".join(_TRANSCRICAO_ASCII.get(c, c) for c in (nome or ""))
    limpo = "".join("-" if c in _CARACTERES_ILEGAIS else c for c in nome)
    # control characters do not show up in an error dialog, they just break things
    limpo = "".join(c for c in limpo if c.isprintable())
    # Windows refuses a name ending in a space or a dot
    limpo = limpo.strip().rstrip(". ")

    if not limpo:
        limpo = "sem_nome"

    raiz = limpo.split(".")[0].upper()
    if raiz in _NOMES_RESERVADOS:
        limpo = f"_{limpo}"

    if len(limpo) > _MAX_NOME:
        limpo = limpo[:_MAX_NOME].rstrip(". ") or "sem_nome"

    if usados is not None:
        base, n = limpo, 2
        while limpo.lower() in {u.lower() for u in usados}:
            # Windows is not case-sensitive: `Caso` and `caso` collide
            limpo = f"{base}_{n}"
            n += 1
        usados.add(limpo)

    return limpo


def mapa_de_nomes_de_arquivo(nomes) -> dict:
    """Maps each condition name to its filename, resolving collisions by
    looking at the WHOLE list at once.

    Has to be done in a batch, not case by case: `_result_plot_path` is
    called once per field PER condition (twelve disk map fields, for
    example), so resolving the collision on each call would give `_2`,
    `_3`, `_4` for the SAME condition -- files scattered around instead
    of overwritten, which is just another form of wrong.

    LIMITATION, and this is why export no longer uses this function to
    index results: the dict key is the name, so N conditions with an
    IDENTICAL name (the common case -- the GUI names every Run Case case
    "caso") collapse into a single entry, whose final value is the
    suffix of the LAST one (``caso_5``). The N figures would all end up
    in the same file, overwriting each other. To index by condition use
    `nomes_de_arquivo_de_condicao`, which returns a LIST by position."""
    usados: set = set()
    return {nome: sanitize_filename(nome, usados) for nome in nomes}


def rotulos_de_condicao(results_list) -> list:
    """``["Case 1", "Case 2", ...]`` -- UNIQUE, numbered label per
    condition, in the order of ``results_list``.

    `Results.condition_name` does not work as an identifier: the GUI
    names every Run Case case "caso" (`gui/tabs/run_case.py`), so a
    selection of five cases would arrive at the report as five "caso"
    rows -- no way to say "row 3" or cross-reference a row with a figure.

    The number comes first because it is what provides the reference.
    The name is only appended after it when it actually distinguishes
    the conditions (all present and all different); when it is the same
    across all of them, repeating it in every label would only take up
    the column without conveying anything."""
    nomes = [str(getattr(r, "condition_name", "") or "").strip()
             for r in results_list]
    distingue = all(nomes) and len(set(nomes)) == len(nomes)
    return [f"Case {i} - {nome}" if distingue else f"Case {i}"
            for i, nome in enumerate(nomes, start=1)]


def nomes_de_arquivo_de_condicao(results_list) -> list:
    """Filename per condition, indexed by POSITION in
    ``results_list`` (not by name -- see `mapa_de_nomes_de_arquivo`).

    Starts from the numbered label, so two conditions never share a
    file even when they share a name; `usados` still resolves the
    residual collision of two labels that sanitize to the same text."""
    usados: set = set()
    return [sanitize_filename(rot, usados) for rot in rotulos_de_condicao(results_list)]


def _nome_de_arquivo_da_condicao(condition_name: str) -> str:
    """Defensive sanitization for callers of `_result_plot_path` that go
    direct, without going through the batch map. Idempotent: an already
    sanitized name passes through intact."""
    return sanitize_filename(condition_name)


def _mascara_de_fluxo_reverso(result) -> bool:
    """Whether (or not) to mask the reverse-flow region in the disk maps.

    EXPLICIT DECISION, because both answers are defensible: the value
    comes from the RUN'S ECHO (`Results.summary["cfg_mask_reverse_flow_plots"]`,
    emitted by `bemt.aggregate_results`), NOT from the project's current
    configuration.

    Consequence worth knowing: the "mask reverse flow" checkbox in the
    Results tab writes to `project.config` and changes the disk ON
    SCREEN right away, but an export only reflects the change for cases
    run AFTER it. Cases already in memory keep exporting with the mask
    they were solved with.

    Why this way: an export is a figure + summary-row pair, and the
    summary row carries `cfg_mask_reverse_flow_plots` as a column.
    Reading the current config would produce a self-contradictory
    package -- the column saying `True` next to a figure with no mask.
    Also `export_results` runs with `project=None` on several paths
    (report from standalone `Results`, a script), where there is no
    "current config" to consult; the summary row always exists.

    If the decision ever flips (favoring what is on screen), this is
    the place -- it is the single point of reading."""
    return bool(result.summary.get("cfg_mask_reverse_flow_plots", True))


def _result_plot_path(plots_dir: Path, layout: str, base: str, condition_name: str) -> Path:
    """Resolves the path of a PER-CONDITION plot file, honoring
    ``layout`` (docs/plano_v3.md Part 4.3 -- batch export of disk maps
    per batch):

    - ``"flat"`` (default, the usual behavior): one file per case,
      self-explanatory name -- ``plots_dir/{base}_{condition_name}.png``.
    - ``"per_case"``: one folder per case -- ``plots_dir/{condition_name}/
      {base}.png`` (creates the subfolder if needed); useful when the
      number of fields exported per case is large and the flat list
      becomes hard to navigate in the file explorer.

    NEVER returns a path that already exists: it goes through
    `_caminho_sem_sobrescrever`, which appends `" (2)"`, `" (3)"`...
    Without this, exporting the disk maps twice to the SAME folder would
    silently erase the first export -- the same class of data loss as
    the bug where N conditions with the same name all landed in the same
    file (see `nomes_de_arquivo_de_condicao`). The suffix does NOT
    scatter the fields of the same case: within one export each field
    has its own `base`, so none collides with the previous one. And
    every caller uses the RETURNED path (never rebuilds the name), so
    the suffix reaches `written`.
    """
    cond = _nome_de_arquivo_da_condicao(condition_name)
    if layout == "per_case":
        d = plots_dir / cond
        d.mkdir(parents=True, exist_ok=True)
        return _caminho_sem_sobrescrever(d / f"{base}.png")
    return _caminho_sem_sobrescrever(plots_dir / f"{base}_{cond}.png")


def _caminho_sem_sobrescrever(path: Path) -> Path:
    """Appends ``" (2)"``, ``" (3)"``... to the name if ``path`` already exists.

    Never silently overwrites a previous export."""
    if not path.exists():
        return path
    i = 2
    while True:
        candidato = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidato.exists():
            return candidato
        i += 1


def _formatador_numero_excel(decimal: str):
    """Formats a float in fixed point, never scientific notation.

    Excel (pt-BR regional settings) imports ``8.279954294566177e-05`` as
    text, not a number: the ``e`` notation is not recognized and the
    ``.`` is not the expected decimal separator. ``%.6g`` (same precision
    used on screen — see ``RunCaseTab._formatar_valor``) switches to
    scientific notation below 1e-4; when that happens, it expands to
    fixed point before swapping the decimal separator."""
    def formatar(x) -> str:
        if x != x:  # NaN
            return ""
        if x == 0:
            return "0"
        try:
            s = f"{float(x):.6g}"
        except (TypeError, ValueError):
            return str(x)
        if "e" in s or "E" in s:
            s = f"{float(x):.10f}".rstrip("0").rstrip(".")
        return s.replace(".", decimal) if decimal != "." else s
    return formatar


def export_results_tabular(results, outdir: str, sep: str = ",",
                           filename: Optional[str] = None) -> str:
    """Writes a delimited file (CSV or TSV) with all the fields of
    ``results.summary`` for each case and returns the path written.

    ``sep``      — ``","`` for CSV, ``"\\t"`` for TSV.
    ``filename`` — file name (without extension); default ``"results"``.

    Numbers never come out in scientific notation nor overwrite a
    previous export (see ``_formatador_numero_excel``/``_caminho_sem_sobrescrever``).
    In CSV, the field separator is ``;`` and the decimal is ``,`` — the
    convention that Excel (pt-BR regional settings) recognizes
    automatically when opening the file; using ``,`` as field separator
    and decimal at the same time is what produces the broken import. In
    TSV the tab already separates fields unambiguously, so the decimal
    also becomes ``,``.
    """
    import pandas as pd
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    ext = "tsv" if sep == "\t" else "csv"
    write_sep = sep if sep == "\t" else ";"
    fname = filename or "results"
    path = _caminho_sem_sobrescrever(out / f"{fname}.{ext}")
    results_list = results if isinstance(results, list) else [results]
    rows = [r.summary for r in results_list]
    df = pd.DataFrame(rows)
    df.to_csv(path, sep=write_sep, index=False,
              float_format=_formatador_numero_excel(","))
    return str(path)


#: Axes a sweep may have traversed, in the order that makes sense as
#: the x-axis of a performance plot.
_EIXOS_DE_VARREDURA = ("mu_x", "collective_deg", "rpm", "alpha_deg")


def _eixo_que_variou(results_list) -> str:
    """Which quantity the sweep traversed -- that is what becomes the x-axis.

    Without this, a collective sweep in hover would be plotted against
    `mu_x`, which is constant: all points stacked on a single abscissa."""
    from .viz import plots as plots_module
    for eixo in _EIXOS_DE_VARREDURA:
        chave = plots_module._AXIS_TO_SUMMARY_KEY.get(eixo, eixo)
        valores = {r.summary.get(chave) for r in results_list}
        valores = {v for v in valores if v is not None}
        if len(valores) > 1:
            return eixo
    return "mu_x"


def _agrupar_condicoes_por_reynolds(condicoes):
    """If the conditions sweep in Reynolds AND in Mach, returns one group
    PER Reynolds value -- each group covers all the Machs for that Re.
    Otherwise returns a single list with all the conditions. Each
    element of the returned list is ``(reynolds_value_or_None, subset)``
    -- the value goes into the filename/figure title in
    `_exportar_polares_de_aerofolio`."""
    if not condicoes or condicoes == [None]:
        return [(None, [None])]
    reynolds = {c.get("reynolds") for c in condicoes if isinstance(c, dict)}
    machs = {c.get("mach") for c in condicoes if isinstance(c, dict)}
    reynolds.discard(None); machs.discard(None)
    if len(reynolds) < 2 or len(machs) < 2:
        return [(None, condicoes)]
    grupos = []
    for re_val in sorted(reynolds):
        subset = [c for c in condicoes
                  if isinstance(c, dict) and c.get("reynolds") == re_val]
        if subset:
            grupos.append((re_val, subset))
    return grupos


def _exportar_polares_de_aerofolio(project, plots_dir: Path, results_list: list,
                                     plots_module, dpi: int = 150) -> list:
    """Cl(alpha), Cd(alpha), Cd(Cl) and the 2D profile of the used polar(s).

    Covers the four shapes an `AirfoilDef` can take, because each one
    breaks a different way if treated like the others:

    - ``analytical``: one curve, evaluated from the formula. It has no
      `ProfileGeometry` unless the user generated one -- so the 2D
      profile may simply not exist, and that is not an error.
    - ``table``: the polar comes from imported slices, with a Reynolds
      and/or Mach axis. Overlays ONE CURVE PER SLICE (`unique_conditions`),
      which is the information the table carries and an averaged curve
      would hide.
    - ``external``/neuralfoil: `to_airfoil` raises `NotImplementedError`
      for `source="external"`, so the attempt is wrapped -- a polar that
      cannot be evaluated must not bring down report generation.
    - multi-section (`project.airfoil_sections` with 2+): the engine
      IGNORES `project.airfoil` in that case (see
      `airfoils.to_blade_airfoil`), so drawing only it would show a
      polar that was not used. Produces a set of curves PER SECTION,
      labeled with the section's r/R.
    """
    if project is None:
        return []

    secoes = list(project.airfoil_sections or [])
    if len(secoes) >= 2:
        alvos = [(f"_r{s.r_norm:.2f}".replace(".", "p"), s) for s in secoes]
    else:
        alvos = [("", project.airfoil)]

    use_comp = bool((project.config or {}).get("use_compressibility", False))
    written: list = []
    for sufixo, af in alvos:
        if af is None:
            continue
        try:
            todas = airfoils.unique_conditions(af) or [None]
            # Grouping by Reynolds: when the table varies in Reynolds
            # AND in Mach (the actual reported case -- e.g. 3 Re x 3 M),
            # overlaying EVERYTHING on the same chart gives 9 curves
            # that are impossible to read. Splitting into ONE figure
            # PER Reynolds, with one curve per Mach inside each, shows
            # the variation with Mach (for a fixed Re) on one page and
            # the variation with Re on another. If only Re varies
            # (without Mach, or vice versa), a SINGLE figure comes out
            # with one curve per value -- same behavior as before.
            grupos = _agrupar_condicoes_por_reynolds(todas)
        except Exception:
            continue
        if not grupos:
            continue

        for chave, subset in grupos:
            try:
                curvas = airfoils.preview_polar_multi(
                    af, conditions=subset if subset != [None] else None,
                    use_compressibility=use_comp)
            except Exception:
                # `source="external"` (NotImplementedError) and any polar
                # that fails to evaluate: skip this group, continue with the rest.
                continue
            if not curvas:
                continue
            sufixo_grupo = sufixo + (f"_Re{chave:.0f}" if chave is not None else "")

            for base, desenhar in (
                ("airfoil_cl_alpha", lambda ax, c: plots_module.plot_cl_alpha(
                    c["alpha_deg"], c["cl"], ax=ax, label=c.get("label"))),
                ("airfoil_cd_alpha", lambda ax, c: plots_module.plot_cd_alpha(
                    c["alpha_deg"], c["cd"], ax=ax, label=c.get("label"))),
                ("airfoil_cd_cl", lambda ax, c: plots_module.plot_cd_cl(
                    c["cl"], c["cd"], ax=ax, label=c.get("label"))),
            ):
                import matplotlib.pyplot as _plt
                fig, ax = _plt.subplots(figsize=(6, 4))
                try:
                    for c in curvas:
                        desenhar(ax, c)
                    if chave is not None:
                        ax.set_title(f"{ax.get_title()} — Re={chave:.3g}")
                    fname = plots_dir / f"{base}{sufixo_grupo}.png"
                    fig.tight_layout()
                    fig.savefig(str(fname), dpi=dpi)
                    written.append(str(fname))
                finally:
                    _plt.close(fig)

        geom_2d = getattr(af, "geometry", None)
        if geom_2d is not None and getattr(geom_2d, "x", None):
            fname = plots_dir / f"airfoil_profile{sufixo}.png"
            try:
                plots_module.plot_profile(geom_2d, fname=str(fname))
                written.append(str(fname))
            except Exception:
                pass
    return written


def export_results(results, outdir: str, plots: Optional[list[str]] = None,
                    save_csv: bool = True, save_maps: bool = False,
                    project: Optional[Project] = None, layout: str = "flat",
                    dpi: int = 150) -> list[str]:
    """Writes ``results.csv`` and/or the requested plots. ``plots`` accepts
    the four kinds from Section 7 of the plan:

    - ``"performance"``    — a single aggregated plot (CT x mu_x) over all
      the results.
    - ``"disk_map"`` — ALL 12 disk fields (see
      ``plots._DISK_GRID_FIELDS``), one PER condition: a single grid
      (``disk_map_grid_<condition>.png``) with all of them together + a
      separate .png per field (``disk_map_<field>_<condition>.png``).
      Reverse-flow masking (``cfg.mask_reverse_flow_plots``, default
      True) is applied to both.
    - ``"disk_map_<field>"`` (e.g. ``disk_map_CT``, ``disk_map_alpha``) —
      only the .png of that specific field, one PER condition.
    - ``"convergence"``    — a plot PER condition (convergence history is
      per-case).
    - ``"comparison"``     — comparison between solvers, expects results
      coming from ``studies.benchmark_solvers`` (uses ``maps['benchmark_*']``).
    - ``"rotor_3d"``       — 3D screenshot of the rotor/blade (via
      PyVista, ``visualization.py``), from ``project.geometry`` — only
      available if PyVista is installed; **requires** that
      ``export_results`` be called with ``project`` (see below).
    - ``"disk_map_3d"`` or ``"disk_map_3d_<field>"`` — disk map in 3D
      (colored relief), one PER condition; default field ``"Fn"``.
    - ``"load_3d"`` or ``"load_3d_<field>"`` — shortcut for
      ``"disk_map_3d_<field>"`` with extrusion (same thing, name reads
      more like "load distribution" — Section 8.5 of the plan).

    Unknown kinds are silently ignored (the GUI only offers the valid
    ones; scripts get an empty file list for that item). The ``*_3d``
    kinds are also silently ignored (no error) when PyVista is not
    installed — the platform keeps working without that optional
    dependency (see docs/plano.md Section 4, ``visualization.py``).

    ``project``: optional; only needed if ``plots`` includes
    ``"rotor_3d"`` (needs the rotor geometry, which does not come inside
    ``Results``).

    ``layout`` (docs/plano_v3.md Part 4.3): ``"flat"`` (default) keeps
    the usual behavior -- one file per case, self-explanatory name
    (``disk_map_{field}_{condition_name}.png``). ``"per_case"`` writes,
    instead, ``{outdir}/plots/{condition_name}/disk_map_{field}.png``
    -- one FOLDER per case, without the name suffix (already implied by
    the folder). Applies to all PER-CONDITION kinds (``disk_map*``,
    ``disk_map_3d*``, ``load_3d*``, ``convergence``);
    ``"performance"``/``"comparison"``/``"rotor_3d"`` are aggregated (a
    single file) and ignore ``layout``.
    """
    import pandas as pd
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    written = []

    results_list = results if isinstance(results, list) else [results]

    # Filenames resolved once for the whole batch, BY POSITION: condition
    # names are free text and may contain `:` `*` `?`, illegal in a
    # filename on Windows, two distinct names may sanitize to the same
    # text, and -- the case that hurts most -- N conditions may have the
    # SAME name, a situation where indexing by name would write the N
    # figures to the same file (see `nomes_de_arquivo_de_condicao`).
    nomes_de_arquivo = nomes_de_arquivo_de_condicao(results_list)

    if save_csv:
        rows = [r.summary for r in results_list]
        df = pd.DataFrame(rows)
        # Same rule as the plots (see `_result_plot_path`): re-exporting
        # to the same folder does not erase the previous CSV.
        csv_path = _caminho_sem_sobrescrever(out / "results.csv")
        df.to_csv(csv_path, index=False)
        written.append(str(csv_path))

    if plots:
        from .viz import plots as plots_module
        plots_module.set_export_dpi(dpi)
        plots_dir = out / "plots"
        plots_dir.mkdir(exist_ok=True)

        for kind in plots:
            if kind == "performance":
                fname = _caminho_sem_sobrescrever(plots_dir / "performance.png")
                plots_module.plot_performance(results_list, fname=str(fname))
                written.append(str(fname))

            elif kind == "convergence":
                for i, r in enumerate(results_list):
                    fname = _result_plot_path(plots_dir, layout, "convergence", nomes_de_arquivo[i])
                    plots_module.plot_convergence(r, fname=str(fname))
                    written.append(str(fname))

            elif kind == "comparison":
                fname = _caminho_sem_sobrescrever(plots_dir / "solver_comparison.png")
                plots_module.plot_solver_comparison(results_list, fname=str(fname))
                written.append(str(fname))

            elif kind.startswith("disk_map_3d") or kind.startswith("load_3d"):
                from .viz import visualization
                if not visualization.is_available():
                    continue  # PyVista not installed — ignored on purpose, see docstring.
                is_load = kind.startswith("load_3d")
                prefix = "load_3d" if is_load else "disk_map_3d"
                raw_field = kind[len(prefix):].lstrip("_") or "Fn"
                field = _DISK_MAP_FIELD_ALIASES.get(raw_field.lower(), raw_field)
                for i, r in enumerate(results_list):
                    if field not in r.maps:
                        continue
                    fname = _result_plot_path(plots_dir, layout, f"{prefix}_{field}", nomes_de_arquivo[i])
                    if is_load:
                        visualization.plot_load_distribution_3d(r.maps, field=field, fname=str(fname))
                    else:
                        visualization.plot_disk_map_3d(r.maps, field=field, fname=str(fname))
                    written.append(str(fname))

            elif kind == "coefficients":
                # The 11 global coefficients as a function of the axis that
                # varied. `performance` (CT x mu_x, a single panel) keeps
                # existing for whoever already depended on it; this is the
                # complete picture.
                eixo = _eixo_que_variou(results_list)
                fname = plots_dir / f"coefficients_vs_{eixo}.png"
                plots_module.plot_coefficients_vs_axis(results_list, axis=eixo, fname=str(fname))
                written.append(str(fname))

            elif kind == "airfoil_polar":
                # The airfoil DEFINITION, not a result: Cl(alpha),
                # Cd(alpha) and Cd(Cl) of the polar(s) the engine actually
                # used. It was missing from the report -- a rotor report
                # without the polar does not let you check the aerodynamic
                # hypothesis that produced the numbers; you had to reopen
                # the GUI to see it.
                written += _exportar_polares_de_aerofolio(
                    project, plots_dir, results_list, plots_module, dpi=dpi)

            elif kind == "blade_geometry":
                # Planform + chord/twist. Same logic: the geometry is
                # input, and without it the reader does not know WHICH
                # blade generated the sweep.
                if project is not None and project.geometry is not None:
                    for base, fn in (("blade_planform", plots_module.plot_planform),
                                      ("blade_chord_twist", plots_module.plot_chord_twist_distribution),
                                      ("blade_rotor_3d", plots_module.plot_rotor_3d)):
                        fname = plots_dir / f"{base}.png"
                        try:
                            fn(project.geometry, fname=str(fname))
                        except Exception:
                            continue
                        written.append(str(fname))

            elif kind == "azimuth":
                for i, r in enumerate(results_list):
                    if not r.maps:
                        continue
                    fname = _result_plot_path(plots_dir, layout, "loads_vs_azimuth",
                                               nomes_de_arquivo[i])
                    plots_module.plot_loads_vs_azimuth(r.maps, fname=str(fname))
                    written.append(str(fname))

            elif kind == "span":
                for i, r in enumerate(results_list):
                    if not r.maps:
                        continue
                    fname = _result_plot_path(plots_dir, layout, "blade_loads_vs_span",
                                               nomes_de_arquivo[i])
                    plots_module.plot_blade_loads_vs_span(r.maps, fname=str(fname))
                    written.append(str(fname))

            elif kind == "disk_map_grid":
                # Only the panel with all 12 together. Exists for a large
                # sweep, where the 12 PER-CASE files from `disk_map`
                # explode in number (13 figures per condition).
                for i, r in enumerate(results_list):
                    if not r.maps:
                        continue
                    mask_reverse = _mascara_de_fluxo_reverso(r)
                    fname = _result_plot_path(plots_dir, layout, "disk_map_grid",
                                               nomes_de_arquivo[i])
                    plots_module.plot_disk_map_grid(r.maps, fname=str(fname),
                                                     mask_reverse=mask_reverse)
                    written.append(str(fname))

            elif kind == "disk_map":
                # "Generic" kind (no field suffix): Section 2 of the
                # update request -- one output with ALL fields together
                # (single grid) + a separate contour .png per field, both
                # honoring `cfg.mask_reverse_flow_plots` (read back from
                # the summary, which always exports `cfg_<field>` -- see
                # `aggregate_results`, bemt.py).
                for i, r in enumerate(results_list):
                    mask_reverse = _mascara_de_fluxo_reverso(r)

                    fname_grid = _result_plot_path(plots_dir, layout, "disk_map_grid", nomes_de_arquivo[i])
                    plots_module.plot_disk_map_grid(r.maps, fname=str(fname_grid),
                                                      mask_reverse=mask_reverse)
                    written.append(str(fname_grid))

                    for field in plots_module._DISK_GRID_FIELDS:
                        fname = _result_plot_path(plots_dir, layout, f"disk_map_{field}", nomes_de_arquivo[i])
                        plots_module.plot_disk_map(r.maps, field=field, fname=str(fname),
                                                    mask_reverse=mask_reverse)
                        written.append(str(fname))

            elif kind.startswith("disk_map"):
                raw_field = kind[len("disk_map"):].lstrip("_") or "lambda_i"
                field = _DISK_MAP_FIELD_ALIASES.get(raw_field.lower(), raw_field)
                for i, r in enumerate(results_list):
                    if field not in r.maps:
                        continue
                    mask_reverse = _mascara_de_fluxo_reverso(r)
                    fname = _result_plot_path(plots_dir, layout, f"disk_map_{field}", nomes_de_arquivo[i])
                    plots_module.plot_disk_map(r.maps, field=field, fname=str(fname),
                                                mask_reverse=mask_reverse)
                    written.append(str(fname))

            elif kind == "rotor_3d":
                from .viz import visualization
                if not visualization.is_available() or project is None:
                    continue  # PyVista not installed, or no `project` (needs the geometry) — ignored.
                fname = _caminho_sem_sobrescrever(plots_dir / "rotor_3d.png")
                visualization.plot_rotor_3d(project.geometry, fname=str(fname))
                written.append(str(fname))

            # else: unknown kind — ignored on purpose, see docstring.

    return written


# =============================================================================
# HTML report
# =============================================================================
#
# A report is a single, self-contained file (images embedded in base64),
# which opens in any browser and survives being sent by email -- no
# folder of PNGs that gets separated from the HTML.
#
# Lives here, not in the GUI, because it writes to disk (the layer rule
# from CLAUDE.md) and so that the CLI (`--report`) and a Python script
# call exactly the same code as the "Generate report…" button.

#: Report style. Goal: look like a real technical engineering report
#: (what you would attach to a project memo), not a debug page --
#: typography with clear hierarchy, a single restrained accent color,
#: figures and tables CENTERED on the page (a reader does not expect a
#: chart/table to stick to the left margin), no excess (no gradients, no
#: emoji as section markers).
_REPORT_CSS = """
  :root { --accent: #2b5d8c; --accent-soft: #eaf1f8; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         margin: 0 auto; max-width: 1600px; padding: 32px 40px 64px;
         color: #1a1a1a; line-height: 1.55; }
  h1 { margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.01em; }
  h1 + p.sub { color: #6b7280; margin-top: 4px; font-size: 14px; }
  h2 { font-size: 19px; font-weight: 700; color: var(--accent);
       border-bottom: 2px solid var(--accent-soft); padding-bottom: 6px;
       margin-top: 44px; letter-spacing: -0.005em; }
  table { border-collapse: collapse; font-size: 14px; width: 100%; margin: 0 auto; }
  th, td { border: 1px solid #dde1e6; padding: 6px 10px; text-align: right; }
  th { background: var(--accent-soft); font-weight: 600; text-align: center;
       color: #1f3a52; cursor: help; }
  td:first-child, th:first-child { text-align: left; }
  tbody tr:nth-child(even) td { background: #fafbfc; }
  tr:hover td { background: #f1f6fb; }
  img { max-width: 100%; border: 1px solid #e5e5e5; border-radius: 4px; }
  /* The "what was run" metadata sits in two columns side by side. The
     block is deliberately generous, because it holds many fields.
     Therefore, a single column would be too tall on a wide screen. */
  .meta-cols { display: flex; flex-wrap: wrap; gap: 8px 48px; justify-content: center; }
  .meta { display: grid; grid-template-columns: max-content 1fr; gap: 3px 16px;
          font-size: 14px; flex: 1 1 420px; max-width: 560px; }
  .meta dt { color: #6b7280; } .meta dd { margin: 0; font-variant-numeric: tabular-nums; }
  details summary { cursor: pointer; margin: 14px 0; font-weight: 600; color: var(--accent); }
  /* blocos lado a lado: a tabela grandeza|valor transposta fica altíssima
     numa coluna só; em N blocos ela cabe na tela sem rolagem lateral */
  .blocos { display: flex; flex-wrap: wrap; gap: 0 24px; align-items: flex-start;
            justify-content: center; }
  .blocos table { width: auto; flex: 1 1 260px; }
  .blocos td:last-child, .blocos th:last-child { text-align: right; }
  /* Uma matriz-resumo de batch pode ter mais colunas do que cabem na
     largura do relatório mesmo depois de `_COLUNAS_PRINCIPAIS`; sem isto
     a tabela larga estica a PÁGINA INTEIRA (rolagem de lado no relatório
     inteiro) em vez de só a si mesma. */
  .tablewrap { overflow-x: auto; margin: 12px 0; border: 1px solid #dde1e6;
               border-radius: 4px; }
  /* `table-layout: fixed` + largura de coluna explícita = TODA coluna com
     a MESMA largura estreita, em vez de cada uma esticando conforme o seu
     conteúdo (o que dava colunas de larguras irregulares e uma tabela
     muito mais larga que o necessário). */
  .tablewrap table { font-size: 12px; table-layout: fixed;
                     width: auto; border: 0; }
  .tablewrap th, .tablewrap td { width: 74px; min-width: 74px; max-width: 74px;
                                 padding: 4px 6px; white-space: nowrap;
                                 overflow: hidden; text-overflow: ellipsis; }
  /* The condition column is the reading anchor. When the reader scrolls
     sideways and loses sight of WHICH case a row is, the rest becomes
     unreadable. */
  .tablewrap th:first-child, .tablewrap td:first-child {
      position: sticky; left: 0; z-index: 1; width: 130px; min-width: 130px;
      max-width: 130px; background: #fff; border-right: 2px solid #c8d2dc; }
  .tablewrap th:first-child { background: var(--accent-soft); z-index: 2; }
  .tablewrap tbody tr:nth-child(even) td:first-child { background: #fafbfc; }
  /* The unit row recedes visually behind the symbol, smaller and grey.
     It is a reference, not content that the reader reads row by row. */
  .tablewrap th.un { font-weight: 400; font-size: 10.5px; color: #6b7280;
                     border-top: 0; padding-top: 0; padding-bottom: 5px;
                     cursor: default; }
  /* An INSTANT tooltip. The native `title=` appears only after
     approximately 1 s at rest over the cell, and in a header of 50
     one-letter columns
     cada, esse atraso transforma a leitura da tabela numa fila de esperas.
     NÃO é mais um `::after` posicionado com `position: absolute` dentro do
     próprio `<th>` -- esse `<th>` mora dentro de `.tablewrap`, que tem
     `overflow-x: auto` contains the scrolling of the wide table, as above.
     By CSS rule, setting only `overflow-x` makes the browser compute
     `overflow-y` as `auto` TOO. One axis cannot scroll while the other
     stays truly "visible". Therefore, the balloon, which starts below the
     header through `top: 100%`, was CUT by the same box that had to scroll
     horizontally, even with `opacity: 1`. The balloon was always invisible,
     although the CSS appeared to work. Therefore, the balloon is now a
     SINGLE shared element with `position: fixed`, relative to the VIEWPORT,
     and no ancestor ever cuts it. A small amount of JavaScript positions it
     on `mouseover` and `mouseout`. See `_REPORT_JS`. */
  .tt { cursor: help; }
  .tt-popup {
      position: fixed; transform: translateX(-50%);
      background: #1f2937; color: #f9fafb; text-align: left;
      padding: 7px 10px; border-radius: 5px; font-size: 12px;
      font-weight: 400; line-height: 1.4; white-space: normal; width: 260px;
      display: none; pointer-events: none; z-index: 9999;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.22);
  }
  /* A vertical header. The configuration echo table (`cfg_*`) has long
     raw field names, for example `reverse_flow_model`, that a 74px column
     never fits horizontally. Truncation with an ellipsis hid almost the
     whole name. Rotated 90 degrees, the name fits a narrow column. The
     extra header height is the price, and the table pays it once, not once
     per row. */
  .tablewrap.vert th.tt { writing-mode: vertical-rl; transform: rotate(180deg);
      white-space: nowrap; overflow: visible; text-overflow: clip;
      height: 140px; vertical-align: bottom; text-align: left; padding-bottom: 8px; }
  /* The first column ("condition") stays out of the rotation. It is short
     and sticky, so rotating it would only hinder reading. */
  .tablewrap.vert th.tt.horiz { writing-mode: horizontal-tb; transform: none;
      height: auto; vertical-align: middle; text-align: left; padding-bottom: inherit; }
  /* A centered figure. A plot pinned to the left margin reads as a draft,
     not as a report. `figure` is already `display: block`, so `margin: auto`
     centers it inside the `body`, which has a `max-width`. */
  /* Index of the satellite reports. A heavy section lives in its own file,
     as `_FIGURAS_ANTES_DE_ARQUIVO_PROPRIO` describes, and is linked from
     here. */
  ul.satelites { list-style: none; padding: 0; display: flex; flex-wrap: wrap;
                 gap: 10px; }
  ul.satelites li { flex: 1 1 300px; border: 1px solid #dde1e6; border-radius: 4px;
                    padding: 10px 14px; background: #fafbfc; }
  ul.satelites a { color: var(--accent); font-weight: 600; text-decoration: none; }
  ul.satelites a:hover { text-decoration: underline; }
  ul.satelites .cnt { color: #6b7280; font-size: 13px; }
  figure { margin: 26px auto; text-align: center; max-width: 100%; }
  figcaption { font-size: 12.5px; color: #6b7280; margin-top: 6px; }
  details table { margin-top: 8px; }
  .nota { background: #fff8e1; border-left: 4px solid #ffb300; padding: 10px 14px;
          font-size: 14px; border-radius: 0 4px 4px 0; }
  @media (prefers-color-scheme: dark) {
    :root { --accent: #7bb3e8; --accent-soft: #1b2733; }
    body { background: #14161a; color: #e6e6e6; }
    th { background: var(--accent-soft); color: #cfe3f5; }
    tbody tr:nth-child(even) td { background: #1a1d22; }
    tr:hover td { background: #1e2836; }
    th, td, img { border-color: #33383f; } h2 { border-bottom-color: var(--accent-soft); }
    .meta dt { color: #9aa4b2; }
    .nota { background: #2a2416; color: #e6e6e6; }
    .tablewrap { border-color: #33383f; }
    .tablewrap th:first-child, .tablewrap td:first-child {
        background: #14161a; border-right-color: #3d4650; }
    .tablewrap th:first-child { background: var(--accent-soft); }
    .tablewrap tbody tr:nth-child(even) td:first-child { background: #1a1d22; }
    .tablewrap th.un { color: #9aa4b2; }
    .tt-popup { background: #0b1220; color: #e6edf5; }
    ul.satelites li { background: #1a1d22; border-color: #33383f; }
  }
  @media print {
    body { max-width: 100%; padding: 0; }
    h2 { break-after: avoid; } figure { break-inside: avoid; }
  }
"""

#: `.tt` tooltip (see the comment in `_REPORT_CSS`): a single
#: `position: fixed` element, shared by the whole page, positioned on
#: `mouseover`/`mouseout` -- `fixed` is relative to the VIEWPORT, so it
#: is never clipped by `.tablewrap`'s `overflow-x: auto` (which clips
#: any `position: absolute` child, even outside the horizontally visible
#: range). Event delegation on `document` (not one listener per `<th>`):
#: the table can have 50+ columns with a tooltip, and a listener per
#: element is needless waste.
_REPORT_JS = """
(function () {
  var pop = document.createElement("div");
  pop.className = "tt-popup";
  document.body.appendChild(pop);
  document.addEventListener("mouseover", function (ev) {
    var alvo = ev.target.closest(".tt");
    if (!alvo) return;
    var dica = alvo.getAttribute("data-tip");
    if (!dica) return;
    pop.textContent = dica;
    var r = alvo.getBoundingClientRect();
    pop.style.left = (r.left + r.width / 2) + "px";
    pop.style.top = (r.bottom + 6) + "px";
    pop.style.display = "block";
  });
  document.addEventListener("mouseout", function (ev) {
    if (ev.target.closest(".tt")) pop.style.display = "none";
  });
})();
"""


#: READING ORDER of the summary table, and its ONLY source of truth --
#: consumed by the HTML report and by the Results tab (via
#: `_chaves_ordenadas`) and by the Run Case tab (which groups the same
#: keys, `run_case.py`'s `_GRUPOS_ROTOR`/`_GRUPOS_HELICE`, in the same
#: relative order; there is a test locking this down in both files).
#:
#: FULL COVERAGE, on purpose: EVERY non-`cfg_` key of `Results.summary`
#: is here. It used to be 25 of 96, and the other 71 fell at the end in
#: the engine dict's insertion order -- an order that exists by
#: implementation accident, that nobody decided, and that the Run Case
#: tab contradicted with its own groups. With the complete list,
#: `_chaves_ordenadas` returns an empty `restantes` and the three
#: surfaces show the SAME quantities in the SAME order.
#:
#: INPUTS come before outputs, and the first eight are the ones that
#: define the operating point, in the order they are naturally asked
#: about: mu_x, V(=V_inf,x), J_x, alpha, Vz(=V_inf,z), J_z, collective, RPM.
#: Without them at the start, a table row cannot be read -- they used to
#: fall after ~40 output columns.
_COLUNAS_PRINCIPAIS = (
    # --- 1. flight condition: the requested operating point ----------------
    # The x component first (the MAIN one in both modes: a helicopter's
    # advance, a propeller's flight speed), then z, then the two angles.
    # `lambda_z` sits next to `mu_z` because it is the SAME number in a
    # different vocabulary -- not one more quantity.
    #
    # EACH QUANTITY ONLY ONCE. There used to be two keys for the same
    # number (`mu`+`mu_x`, `J`+`J_x`), both listed here; the x/z
    # standardization merged them, and a tuple with a repeated key makes
    # `{k: i for i, k in enumerate(...)}` keep the index of the LAST
    # occurrence -- that is how `mu_x` ended up at the end of the Run
    # Case tab.
    "mu_x", "J_x", "Vx",
    "mu_z", "J_z", "Vz", "lambda_z",
    "alpha_rotor_deg", "alpha_disk_deg",
    "collective_deg", "rpm",
    # --- 2. RESOLVED axial flow (the manual's triad, Section 2.6.2) --
    "lambda_i", "lambda_total", "Vi", "Vz_total",
    # --- 3. coefficients, ROTOR convention ------------------------------
    "CT", "CQ", "CP", "CPi", "CPp", "FM",
    "CH", "CHi", "CHp", "CY", "CMx", "CMy",
    # --- 4. coefficients, PROPELLER convention --------------------------
    "CT_prop", "CQ_prop", "CP_prop", "eta_prop",
    # --- 5. dimensional forces, moments and powers ---------------------
    "Thrust", "Torque", "Power", "Power_i", "Power_p",
    "H", "Hi", "Hp", "Y", "Mx", "My",
    # --- 6. echo of the resolved rotor (input from the Geometry tab) -------------
    "rotor_R", "rotor_D", "rotor_Nb", "rotor_Omega", "rotor_OmegaR",
    "rotor_rpm",
    # --- 7. solver diagnostics: can what is above be trusted? -----
    "convergence_pct", "mean_iter", "elapsed_s", "solver", "inflow_coupling",
)

#: Column header in symbol form (LaTeX-like, with an HTML subscript) + the
#: full text that becomes `title=` (tooltip on hover). Without this,
#: the summary matrix is a wall of `snake_case` -- a reader with
#: engineering training reads $C_T$ faster than "CT", and one without that
#: training needs the tooltip anyway; both come out ahead.
#: EVERY key of `Results.summary`, INCLUDING `cfg_*` (echo of
#: `BEMTConfig`), has an entry here: the matrix shows the 90+ columns in a
#: single row per condition, so a column with no symbol would show up as
#: raw `snake_case` in the middle of Greek symbols, and one with no description
#: would have no tooltip -- which is precisely the only way to know what the column
#: means when the header is a symbol of one or two letters.
#: `tests/test_api.py` checks that coverage stays complete.
_SIMBOLO_DE_COLUNA = {
    # --- flight condition (input, in the resolved convention) ---
    # NOT LISTED HERE. Every column whose SYMBOL depends on the axis
    # convention -- mu_x/mu_z, J_x/J_z, Vx/Vz, the two alphas, lambda_z,
    # Vz_total, Vi, collective, rpm -- lives in `zbemt/nomenclature.py` and is
    # merged in below (`_simbolos_de_eixo`). That module is the single source
    # the report, the plots, the GUI combos and the `.bemt` writer all read,
    # so a symbol can no longer be right in the table and wrong in the chart
    # printed next to it.
    "condition":        ("condition", "Flight condition. Cases are numbered in the order they were run, so a row can be cited (\"Case 3\") and matched to the figure with the same label"),

    # --- dimensional forces, moments and powers ---
    "Thrust":           ("T", "Thrust [N], along the shaft axis"),
    "Torque":           ("Q", "Shaft torque [N&middot;m]"),
    "Power":            ("P", "Shaft power [W]"),
    "Power_i":          ("P<sub>i</sub>", "Induced power [W]: the part spent creating the wake"),
    "Power_p":          ("P<sub>p</sub>", "Profile power [W]: the part spent on blade sectional drag"),
    "H":                ("H", "In-plane H-force [N], drag-like, positive aft"),
    "Hi":               ("H<sub>i</sub>", "Induced part of the H-force [N]"),
    "Hp":               ("H<sub>p</sub>", "Profile (sectional drag) part of the H-force [N]"),
    "Y":                ("Y", "In-plane side force [N], positive toward the advancing side"),
    "Mx":               ("M<sub>x</sub>", "Pitch moment about the hub [N&middot;m], positive nose up"),
    "My":               ("M<sub>y</sub>", "Roll moment about the hub [N&middot;m], positive toward the advancing side"),

    # --- coefficients, ROTOR convention (rho*A*(Omega*R)^n) ---
    "CT":               ("C<sub>T</sub>", "Thrust coefficient: C<sub>T</sub> = T / (&rho;&middot;A&middot;(&Omega;R)&sup2;)"),
    "CQ":               ("C<sub>Q</sub>", "Torque coefficient: C<sub>Q</sub> = Q / (&rho;&middot;A&middot;(&Omega;R)&sup2;&middot;R) &mdash; numerically equals C<sub>P</sub> for a rotor"),
    "CP":               ("C<sub>P</sub>", "Power coefficient: C<sub>P</sub> = P / (&rho;&middot;A&middot;(&Omega;R)&sup3;)"),
    "CPi":              ("C<sub>Pi</sub>", "Induced part of the power coefficient"),
    "CPp":              ("C<sub>Pp</sub>", "Profile (sectional drag) part of the power coefficient"),
    "CH":               ("C<sub>H</sub>", "H-force coefficient, in-plane drag-like force (+ aft)"),
    "CHi":              ("C<sub>Hi</sub>", "Induced part of the H-force coefficient"),
    "CHp":              ("C<sub>Hp</sub>", "Profile part of the H-force coefficient"),
    "CY":               ("C<sub>Y</sub>", "Side-force coefficient (+ toward the advancing side)"),
    "CMx":              ("C<sub>Mx</sub>", "Pitch moment coefficient (+ nose up)"),
    "CMy":              ("C<sub>My</sub>", "Roll moment coefficient (+ roll toward the advancing side)"),
    "FM":               ("FM", "Figure of Merit: ideal induced power / actual power. Hover-specific (no in-plane and no axial free-stream); outside hover the same formula can exceed 1"),

    # --- coefficients, PROPELLER convention (rho*n^2*D^4 etc.) ---
    "CT_prop":          ("C<sub>T,prop</sub>", "Propeller-convention thrust coefficient: C<sub>T,prop</sub> = T / (&rho;&middot;n&sup2;&middot;D<sup>4</sup>)"),
    "CQ_prop":          ("C<sub>Q,prop</sub>", "Propeller-convention torque coefficient: C<sub>Q,prop</sub> = Q / (&rho;&middot;n&sup2;&middot;D<sup>5</sup>)"),
    "CP_prop":          ("C<sub>P,prop</sub>", "Propeller-convention power coefficient: C<sub>P,prop</sub> = P / (&rho;&middot;n&sup3;&middot;D<sup>5</sup>)"),
    "eta_prop":         ("&eta;<sub>prop</sub>", "Propulsive efficiency: &eta; = T&middot;V<sub>z</sub>/P = J<sub>z</sub>&middot;C<sub>T,prop</sub>/C<sub>P,prop</sub>. Built from the AXIAL free-stream, since thrust acts along the shaft; meaningful in propeller mode with V<sub>z</sub> &gt; 0"),

    # --- resolved rotor (geometric/kinematic echo of what was run) ---
    "rotor_R":          ("R", "Rotor/propeller radius [m]"),
    "rotor_D":          ("D", "Diameter [m] = 2R"),
    "rotor_Nb":         ("N<sub>b</sub>", "Number of blades"),
    "rotor_Omega":      ("&Omega;", "Angular speed [rad/s]"),
    "rotor_OmegaR":     ("&Omega;R", "Tip speed [m/s]"),
    "rotor_rpm":        ("RPM<sub>rotor</sub>", "Engine echo of the rotational speed built into the Rotor object [rev/min]. Same quantity as RPM; it is shown as a separate column only in the (abnormal) case where the two disagree"),

    # --- solver diagnostics ---
    "convergence_pct":  ("conv.", "Percentage of mesh elements where the inflow fixed point converged [%]"),
    "mean_iter":        ("iter<sub>avg</sub>", "Mean number of solver iterations per mesh element"),
    "elapsed_s":        ("t<sub>cpu</sub>", "Wall-clock solve time [s]"),
    "solver":           ("solver", "Fixed-point solver used for the inflow equation"),
    "inflow_coupling":  ("coupling", "How the inflow field is coupled across elements (local = per element, global = few global DOF)"),

    # --- configuration echo (`cfg_<BEMTConfig field>`) --- a short
    # symbol (not the raw field name, see `_cabecalho_de_coluna`) plus the
    # full description; coverage of EVERY BEMTConfig field is locked
    # by `test_toda_coluna_tem_simbolo_e_tooltip` (no longer excludes
    # `cfg_*`) -- a new field on BEMTConfig with no entry here fails the
    # test, instead of showing up as a raw `cfg_meu_campo_novo` in the table.
    "cfg_Ne":              ("N<sub>e</sub>", "Number of radial stations in the mesh"),
    "cfg_Npsi":             ("N<sub>&psi;</sub>", "Number of azimuthal stations in the mesh"),
    "cfg_rho":              ("&rho;<sub>cfg</sub>", "Air density configured [kg/m&sup3;] (before any per-condition override -- see rho_used)"),
    "cfg_a_sound":          ("a", "Speed of sound [m/s], used for the Mach number"),
    "cfg_nu_air":           ("&nu;", "Air kinematic viscosity [m&sup2;/s], used for the Reynolds number"),
    "cfg_integration_offset": ("&Delta;r<sub>0</sub>", "Radial offset applied to stations to avoid the root/tip singularity"),
    "cfg_is_propeller":     ("prop?", "Whether the case is interpreted in propeller convention (advance ratio and thrust coefficient in the propeller form)"),
    "cfg_inflow_field_model": ("inflow", "Inflow model requested (Glauert/Coleman/Drees/Pitt-Peters, local/global coupling)"),
    "cfg_prandtl_loss_mode": ("F mode", "Prandtl tip/root loss mode requested (off/tip/root/both)"),
    "cfg_use_compressibility": ("compr.", "Whether the Prandtl-Glauert compressibility correction is applied"),
    "cfg_reverse_flow_model": ("rev. flow", "Model used for the reverse-flow region of the disk"),
    "cfg_reverse_flow_blend_factor": ("k<sub>rev</sub>", "Blend sharpness factor for the reverse-flow model"),
    "cfg_thin_plate_blend_center_deg": ("&alpha;<sub>c,tp</sub>", "Thin-plate blend center angle [deg]"),
    "cfg_thin_plate_blend_width_deg": ("&Delta;&alpha;<sub>tp</sub>", "Thin-plate blend width [deg]"),
    "cfg_mask_reverse_flow_plots": ("mask rev.", "Whether the reverse-flow region is masked out in disk-map plots"),
    "cfg_use_rotational_augmentation": ("3D aug.", "Whether rotational (Himmelskamp/Snel) lift augmentation is applied"),
    "cfg_use_radial_flow_correction": ("radial flow", "Whether the radial (spanwise) flow correction is applied"),
    "cfg_radial_flow_max_skew_deg": ("skew<sub>max</sub>", "Maximum skew angle for the radial flow correction [deg]"),
    "cfg_pitt_peters_states": ("N<sub>states</sub>", "Number of Pitt-Peters dynamic inflow states (3 or 5)"),
    "cfg_pitt_peters_outer_iter": ("iter<sub>PP</sub>", "Max outer iterations for the Pitt-Peters ODE coupling"),
    "cfg_pitt_peters_relax": ("relax<sub>PP</sub>", "Relaxation factor for the Pitt-Peters outer loop"),
    "cfg_pitt_peters_tol":  ("tol<sub>PP</sub>", "Convergence tolerance for the Pitt-Peters outer loop"),
    "cfg_use_dynamic_stall": ("dyn. stall", "Whether dynamic stall correction is enabled"),
    "cfg_dynamic_stall_model": ("stall model", "Dynamic stall model used (currently only 'oye')"),
    "cfg_dynamic_stall_method": ("stall method", "Dynamic stall coupling method (frequency-domain or time-march)"),
    "cfg_dynamic_stall_A":  ("A<sub>ds</sub>", "Oye dynamic stall time-constant parameter"),
    "cfg_dynamic_stall_fade_start_deg": ("&alpha;<sub>fade0</sub>", "Angle of attack where dynamic stall correction starts fading out [deg]"),
    "cfg_dynamic_stall_fade_end_deg": ("&alpha;<sub>fade1</sub>", "Angle of attack where dynamic stall correction is fully faded out [deg]"),
    "cfg_dynamic_stall_f_reg": ("f<sub>reg</sub>", "Regularization factor for the Oye separation function"),
    "cfg_dynamic_stall_time_march_revolutions": ("N<sub>rev</sub>", "Revolutions simulated in time-march dynamic stall"),
    "cfg_dynamic_stall_time_march_avg_last": ("N<sub>avg</sub>", "Last N revolutions averaged in time-march dynamic stall"),
    "cfg_solver":           ("solver<sub>cfg</sub>", "Fixed-point solver requested (newton/fixed_point/bisection/aitken)"),
    "cfg_max_iter":         ("iter<sub>max</sub>", "Maximum solver iterations per mesh element"),
    "cfg_tol":              ("tol", "Solver convergence tolerance on the true residual g(&lambda;)-&lambda;"),
    "cfg_relax":            ("relax", "Base relaxation factor for the fixed-point solver"),
    "cfg_relax_schedule":   ("adaptive relax", "Whether adaptive relaxation scheduling is enabled"),
    "cfg_relax_root_factor": ("relax<sub>root</sub>", "Relaxation factor applied near the root"),
    "cfg_relax_root_threshold": ("r<sub>root,relax</sub>", "Root threshold (r/R) below which relax_root_factor applies"),
    "cfg_relax_tip_threshold": ("r<sub>tip,relax</sub>", "Tip threshold (r/R) above which relax_root_factor applies"),
    "cfg_relax_azimuth_factor": ("relax<sub>&psi;</sub>", "Relaxation factor applied near the azimuth crossing"),
    "cfg_relax_azimuth_threshold": ("&psi;<sub>relax</sub>", "Azimuth threshold (rad) for relax_azimuth_factor"),
    "cfg_collect_history":  ("history", "Whether per-iteration convergence history is collected"),
    "cfg_early_exit_fraction": ("f<sub>exit</sub>", "Fraction of converged elements that triggers early exit"),
    "cfg_stagnation_patience": ("N<sub>stag</sub>", "Iterations of stagnation tolerated before declaring non-convergence"),
    "cfg_stagnation_min_frac": ("f<sub>stag</sub>", "Minimum converged fraction required to avoid the stagnation exit"),
    "cfg_rho_used":         ("&rho;<sub>used</sub>", "Air density actually used in this solve [kg/m&sup3;] (may differ from cfg_rho if overridden per condition)"),
}


def _simbolos_de_eixo(is_propeller: bool) -> dict:
    """``key -> (HTML symbol, description)`` for every column whose name
    depends on the axis convention, rendered from `nomenclature`.

    Generated rather than written out twice: the symbol comes from the same
    LaTeX source that produces the plot's axis label, so the table header and
    the chart beside it in the same report cannot disagree.

    Input-only aliases (`alpha_deg`, `alpha_disk`) are left out -- they never
    appear as a `Results.summary` key."""
    return {chave: (nomenclature.symbol_html(chave, is_propeller),
                     nomenclature.description_html(chave, is_propeller))
            for chave, q in nomenclature.QUANTITIES.items() if not q.alias_of}


_SIMBOLO_DE_COLUNA.update(_simbolos_de_eixo(False))


def _descricao_com_simbolos(texto: str) -> str:
    """Converts internal names into mathematical symbols in the displayed text.

    The engine's keys stay in ``snake_case`` for serialization, CLI and CSV
    compatibility. Header descriptions, report tooltips, and selectors,
    however, are a user-facing surface and must never
    expose ``Vx``/``Vz`` or ``mu_x`` as if they were physical symbols.
    """
    substituicoes = (
        ("Vz_total", "V<sub>z,total</sub>"),
        ("Vx_total", "V<sub>x,total</sub>"),
        ("alpha_rotor_deg", "&alpha;<sub>rotor</sub>"),
        ("alpha_disk_deg", "&alpha;<sub>disk</sub>"),
        ("alpha_rotor", "&alpha;<sub>rotor</sub>"),
        ("alpha_disk", "&alpha;<sub>disk</sub>"),
        ("lambda_total", "&lambda;<sub>total</sub>"),
        ("lambda_z", "&lambda;<sub>z</sub>"),
        ("lambda_x", "&lambda;<sub>x</sub>"),
        ("mu_x", "&mu;<sub>x</sub>"),
        ("mu_z", "&mu;<sub>z</sub>"),
        ("J_x", "J<sub>x</sub>"),
        ("J_z", "J<sub>z</sub>"),
        ("Vx", "V<sub>x</sub>"),
        ("Vz", "V<sub>z</sub>"),
        ("V_inf,x", "V<sub>&infin;,x</sub>"),
        ("V_inf,z", "V<sub>&infin;,z</sub>"),
        ("V_x", "V<sub>x</sub>"),
        ("V_z", "V<sub>z</sub>"),
        ("Vx_inf", "V<sub>&infin;,x</sub>"),
        ("Vz_inf", "V<sub>&infin;,z</sub>"),
        ("Vv", "V<sub>z</sub>"),
        ("μ_x", "&mu;<sub>x</sub>"),
        ("μ_z", "&mu;<sub>z</sub>"),
        ("α_rotor", "&alpha;<sub>rotor</sub>"),
        ("α_disk", "&alpha;<sub>disk</sub>"),
        ("λ_x", "&lambda;<sub>x</sub>"),
        ("λ_z", "&lambda;<sub>z</sub>"),
    )
    for antigo, novo in substituicoes:
        texto = re.sub(rf"(?<![\w]){re.escape(antigo)}(?![\w])", novo, texto)
    return texto


#: SI unit of each column, for the header's second row. `"-"`
#: (dimensionless) is EXPLICIT on purpose: an empty cell reads as
#: "forgot to fill in", while "[-]" states that the quantity has no
#: unit -- which in a report full of coefficients is the most
#: common piece of information, and the one that most needs to not be ambiguous.
#: The flight-condition rows are NOT here: their unit lives beside their
#: symbol in `zbemt/nomenclature.py`, and `_unidade_de_coluna` consults that
#: first. A unit does not rotate with the mode -- the letters change, the
#: physics does not -- so there is only ever one entry per quantity.
_UNIDADE_DE_COLUNA = {
    "Thrust": "N", "Torque": "N&middot;m", "Power": "W",
    "Power_i": "W", "Power_p": "W",
    "H": "N", "Hi": "N", "Hp": "N", "Y": "N",
    "Mx": "N&middot;m", "My": "N&middot;m",
    "CT": "-", "CQ": "-", "CP": "-", "CPi": "-", "CPp": "-",
    "CH": "-", "CHi": "-", "CHp": "-", "CY": "-", "CMx": "-", "CMy": "-",
    "FM": "-", "CT_prop": "-", "CQ_prop": "-", "CP_prop": "-", "eta_prop": "-",
    "rotor_R": "m", "rotor_D": "m", "rotor_Nb": "-",
    "rotor_Omega": "rad/s", "rotor_OmegaR": "m/s",
    "rotor_rpm": "rev/min",
    "convergence_pct": "%", "mean_iter": "-", "elapsed_s": "s",
    "solver": "", "inflow_coupling": "",

    "cfg_Ne": "-", "cfg_Npsi": "-", "cfg_rho": "kg/m&sup3;", "cfg_a_sound": "m/s",
    "cfg_nu_air": "m&sup2;/s", "cfg_integration_offset": "-",
    "cfg_is_propeller": "", "cfg_inflow_field_model": "", "cfg_prandtl_loss_mode": "",
    "cfg_use_compressibility": "", "cfg_reverse_flow_model": "",
    "cfg_reverse_flow_blend_factor": "-",
    "cfg_thin_plate_blend_center_deg": "deg", "cfg_thin_plate_blend_width_deg": "deg",
    "cfg_mask_reverse_flow_plots": "", "cfg_use_rotational_augmentation": "",
    "cfg_use_radial_flow_correction": "", "cfg_radial_flow_max_skew_deg": "deg",
    "cfg_pitt_peters_states": "-", "cfg_pitt_peters_outer_iter": "-",
    "cfg_pitt_peters_relax": "-", "cfg_pitt_peters_tol": "-",
    "cfg_use_dynamic_stall": "", "cfg_dynamic_stall_model": "", "cfg_dynamic_stall_method": "",
    "cfg_dynamic_stall_A": "-", "cfg_dynamic_stall_fade_start_deg": "deg",
    "cfg_dynamic_stall_fade_end_deg": "deg", "cfg_dynamic_stall_f_reg": "-",
    "cfg_dynamic_stall_time_march_revolutions": "-", "cfg_dynamic_stall_time_march_avg_last": "-",
    "cfg_solver": "", "cfg_max_iter": "-", "cfg_tol": "-", "cfg_relax": "-",
    "cfg_relax_schedule": "", "cfg_relax_root_factor": "-", "cfg_relax_root_threshold": "-",
    "cfg_relax_tip_threshold": "-", "cfg_relax_azimuth_factor": "-",
    "cfg_relax_azimuth_threshold": "rad", "cfg_collect_history": "",
    "cfg_early_exit_fraction": "-", "cfg_stagnation_patience": "-", "cfg_stagnation_min_frac": "-",
    "cfg_rho_used": "kg/m&sup3;",
}

#: The flight-condition units come from `nomenclature`, which owns them, and
#: are mirrored in so the table stays COMPLETE: the Results and Run Case tabs
#: read it as a plain dict, and a missing key there is a column that silently
#: loses its unit.
_UNIDADE_DE_COLUNA.update({chave: nomenclature.unit(chave)
                           for chave, q in nomenclature.QUANTITIES.items()
                           if not q.alias_of})


# =============================================================================
# The SAME numbers, in the axis letters of a PROPELLER
# =============================================================================
# The engine decomposes the flight velocity relative to the DISK and calls x
# the in-plane component and z the component along the shaft (`bemt.py`,
# Sec.6c). On a helicopter that coincides with the vehicle's axes. On a
# PROPELLER it does not: the shaft points forward, and in cruise the whole
# airspeed lies along it -- so the table used to label the flight velocity
# "V_inf,z", a vertical component, and the vertical component, zero,
# "V_inf,x". Whoever reads the table reads the AIRCRAFT's axes.
#
# The rotation itself -- which letter each component carries, which key it is
# written under, and which of the two angles the mode shows -- lives in
# `zbemt/nomenclature.py`, once, for every surface. What remains here is the
# handful of columns that carry NO axis letter and yet still read differently
# to a propeller user: their prose changes, their symbol does not.
_SIMBOLO_DE_COLUNA_HELICE = {
    "eta_prop":         ("&eta;<sub>prop</sub>", "Propulsive efficiency: &eta; = T&middot;V<sub>x</sub>/P = J<sub>x</sub>&middot;C<sub>T,prop</sub>/C<sub>P,prop</sub>. Built from the airspeed ALONG THE SHAFT, since thrust acts there; meaningful with V<sub>x</sub> &gt; 0"),
    "FM":               ("FM", "Figure of Merit: ideal induced power / actual power. A static (V<sub>x</sub> = 0) figure of merit; in cruise the same formula can exceed 1 -- use &eta;<sub>prop</sub> instead"),
}


def summary_symbols(is_propeller: bool = False) -> dict:
    """Table ``key -> (HTML symbol, description)`` in the axis convention
    of the requested mode.

    In rotor mode returns `_SIMBOLO_DE_COLUNA` unchanged; in propeller mode,
    with the axis letters rotated (from `nomenclature`) and the two
    non-axis columns whose prose differs (`_SIMBOLO_DE_COLUNA_HELICE`).
    SINGLE source for the report, the GUI table, and field selectors -- the
    three surfaces need to say the SAME thing about the same column."""
    if not is_propeller:
        return _SIMBOLO_DE_COLUNA
    tabela = dict(_SIMBOLO_DE_COLUNA)
    tabela.update(_simbolos_de_eixo(True))
    tabela.update(_SIMBOLO_DE_COLUNA_HELICE)
    return tabela


def summary_symbol(chave: str, is_propeller: bool = False) -> tuple:
    """``(symbol, description)`` of a column, or ``(key, "")`` if it is
    not in the table (never leaves the interface without a header)."""
    return summary_symbols(is_propeller).get(chave, (chave, ""))


def _cabecalho_de_coluna(chave: str, is_propeller: bool = False) -> str:
    """`<th>` of the SYMBOL row, with an instant tooltip.

    The tooltip is CSS (`data-tip` + `::after`, see `_REPORT_CSS`), not the
    native `title=`: the native one only appears after ~1 s stopped over the
    cell, and in a header of 50 one-letter columns, that delay
    means reading the table turns into a sequence of waits. The CSS shows it
    instantly.

    Every key of `Results.summary`, INCLUDING `cfg_*` (echo of
    `BEMTConfig`), has an entry here -- `test_toda_coluna_tem_simbolo_e_tooltip`
    locks in complete coverage. The fallback below (`removeprefix("cfg_")`)
    exists only as a safety net for a new key that has not yet
    gained an entry: it never breaks report generation, but falls back to the
    raw name as both symbol AND description -- ugly on purpose, so that the
    coverage gap is obvious just by looking at the report, not only by running the
    test."""
    simbolo, descricao = summary_symbols(is_propeller).get(
        chave, (chave.removeprefix("cfg_"), chave))
    descricao = _descricao_com_simbolos(descricao)
    # `data-tip` becomes CSS content: double quotes would break the attribute.
    dica = descricao.replace('"', "&quot;")
    return f'<th class="tt" data-tip="{dica}">{simbolo}</th>'


def _unidade_de_coluna(chave: str) -> str:
    """`<th>` of the header's second row: the unit."""
    unidade = _UNIDADE_DE_COLUNA.get(chave, "")
    return f'<th class="un">{f"[{unidade}]" if unidade else ""}</th>'


#: How many characters fit in a `.tablewrap` cell before
#: `text-overflow: ellipsis` cuts it off. The columns have a FIXED and
#: uniform width (74 px, 130 px in the first one; see `_REPORT_CSS`) -- that is how
#: it is meant to be, a 50-column table with irregular widths is unreadable --
#: but a cell cut off with no tooltip has NO way of being read.
#: The numbers come from the usable width (minus padding) at ~6 px/character in the
#: table's 12 px body.
_CARACTERES_POR_CELULA = 10
_CARACTERES_PRIMEIRA_COLUNA = 18


def _texto_de_simbolos(html: str) -> str:
    """Converts the small HTML subset of the symbols to a plain-text tooltip."""
    texto = re.sub(r"<[^>]+>", "", html)
    entidades = {
        "&alpha;": "α", "&lambda;": "λ", "&mu;": "μ",
        "&theta;": "θ", "&infin;": "∞", "&eta;": "η",
    }
    for entidade, simbolo in entidades.items():
        texto = texto.replace(entidade, simbolo)
    return texto


def _celula_html(texto: str, primeira: bool = False, html: str | None = None) -> str:
    """`<td>`, with an instant tooltip WHEN the content does not fit.

    Same mechanism as the header (`.tt` + `data-tip`, a single balloon,
    `position: fixed`, assembled by `_REPORT_JS`) and for the same reason: the
    native `title=` only appears after ~1 s, and checking half a dozen
    truncated values in a wide table turns into a queue of waits.

    Only cells that actually overflow get the attribute -- marking every
    cell would put a tooltip on a short number that already reads fine, and
    would bloat the HTML of a 50-column-per-condition table for no reason."""
    limite = _CARACTERES_PRIMEIRA_COLUNA if primeira else _CARACTERES_POR_CELULA
    exibicao = html if html is not None else texto
    dica = _texto_de_simbolos(exibicao)
    if len(texto) <= limite:
        return f"<td>{exibicao}</td>"
    return f'<td class="tt" data-tip="{dica.replace(chr(34), "&quot;")}">{exibicao}</td>'


def _tabela_html(cab: list, linhas: list, *, vertical: bool = False,
                  is_propeller: bool = False) -> str:
    """Table in HTML, wrapped in `<div class="tablewrap">`.

    A batch's summary matrix can have more columns than fit the
    report's width even after the reduction in `_summary_table`
    (`_COLUNAS_PRINCIPAIS`). Without the wrapper, the wide table stretches the
    WHOLE PAGE and the reader has to scroll sideways to read anything below
    it too -- the wrapper (`overflow-x: auto` in `_REPORT_CSS`) contains
    the scrolling INSIDE the table itself; the rest of the report stays
    readable without scrolling sideways.

    ``vertical=True`` (used by the configuration-echo table, whose
    raw field names -- ``reverse_flow_model`` -- do not fit a
    74px column horizontally) rotates the header text 90° via
    ``.tablewrap.vert`` (see `_REPORT_CSS`); the first column
    (``condition``) is left out -- it is short and sticky, rotating it would
    only get in the way."""
    classe = "tablewrap vert" if vertical else "tablewrap"
    linha_cabecalho = [_cabecalho_de_coluna(h, is_propeller) for h in cab]
    if vertical and linha_cabecalho:
        linha_cabecalho[0] = linha_cabecalho[0].replace('class="tt"', 'class="tt horiz"', 1)
    html = [f'<div class="{classe}"><table><thead>',
            "<tr>" + "".join(linha_cabecalho) + "</tr>",
            "<tr>" + "".join(_unidade_de_coluna(h) for h in cab) + "</tr>",
            "</thead><tbody>"]
    for linha in linhas:
        celulas = []
        for j, c in enumerate(linha):
            texto = str(c)
            simbolos = _descricao_com_simbolos(texto) if j == 0 else None
            celulas.append(_celula_html(texto, primeira=(j == 0), html=simbolos))
        html.append("<tr>" + "".join(celulas) + "</tr>")
    html.append("</tbody></table></div>")
    return "".join(html)


def _blocos_grandeza_valor(pares: list, colunas: int = 3,
                            is_propeller: bool = False) -> str:
    """Quantity|value table repeated side by side in N blocks.

    The summary table had one ROW per condition and one column per quantity:
    with ~70 quantities, the reader scrolled horizontally endlessly and never saw
    two related quantities together. Transposed (quantity per row) it
    becomes very tall; in side-by-side blocks, it fits the screen and stays legible.

    Used when there is ONE condition, which is the case where the
    transposed orientation is clearly better.
    """
    if not pares:
        return ""
    por_bloco = -(-len(pares) // colunas)      # ceiling division
    blocos = [pares[i:i + por_bloco] for i in range(0, len(pares), por_bloco)]
    partes = ['<div class="blocos">']
    for bloco in blocos:
        partes.append("<table>")
        partes.append("<tr><th>quantity</th><th>value</th></tr>")
        for chave, valor in bloco:
            simbolo, descricao = summary_symbols(is_propeller).get(chave, (chave, chave))
            partes.append(f'<tr><td title="{descricao}">{simbolo}</td><td>{valor}</td></tr>')
        partes.append("</table>")
    partes.append("</div>")
    return "".join(partes)


def _formatar(valor) -> str:
    """4 significant digits: that is what fits a narrow, uniform column
    without truncation, and it is more precision than any engineering
    decision draws from a summary table read on screen. With
    `.6g`, `0.00387711` used to take up the whole column and the reader compared
    rounding noise between cases instead of the quantities.

    FULL precision remains available wherever it makes sense to consume it by
    machine: `export_results_tabular` (CSV) does not go through here.

    Structurally-null quantities (CY/CMx/CMy/CH in hover, mu_x on a
    propeller) come out of the vectorized sum as rounding noise --
    `6.098e-19`, `-1.951e-19`. Shown as is, the reader compares noise
    exponents and might conclude there is a side force where symmetry
    guarantees there is none. Below the floor, it is ZERO: 1e-12 is ~9 orders
    of magnitude below the smallest physically significant coefficient that
    this engine produces (CHp ~ 1e-5), so there is no real quantity the floor
    could swallow by mistake."""
    if isinstance(valor, float):
        if valor != 0.0 and abs(valor) < 1e-12:
            return "0"
        return f"{valor:.4g}"
    return str(valor)


def _rotor_rpm_e_redundante(results_list: list) -> bool:
    """Does ``rotor_rpm`` say the SAME thing as ``rpm``?

    They do: `studies.run_single_case` does
    ``summary.setdefault("rpm", summary.get("rotor_rpm", condition.rpm))``
    -- ``rpm`` is the alias the plots read, ``rotor_rpm`` is the echo that
    `bemt.aggregate_results` emits from the ``Rotor`` that just ran, and the
    ``Rotor`` is built with the RPM of the condition itself. Two "RPM"
    columns side by side, with the same number, make the reader look for a
    difference that does not exist.

    The check is by VALUE, not by rule: if the two ever
    diverge (a different `Rotor` construction path, a trim that
    does not propagate the RPM back), the column reappears instead of hiding the
    divergence -- exactly when it would matter."""
    for r in results_list:
        if "rotor_rpm" not in r.summary:
            return False
        a, b = r.summary.get("rpm"), r.summary.get("rotor_rpm")
        if a is None or b is None:
            return False
        try:
            if abs(float(a) - float(b)) > 1e-9 * max(1.0, abs(float(b))):
                return False
        except (TypeError, ValueError):
            return False
    return True


def modo_helice(results_list: list, project: Optional[Project] = None) -> bool:
    """The mode in which these results were run.

    The authoritative answer is the project (it is what the user edited); in its
    absence, the `cfg_is_propeller` echo that `export_settings` writes into
    each `Results.summary`. With neither of the two, rotor -- which is
    `BEMTConfig`'s default and what the table has always shown.

    Exists so that the report, the GUI table, and axis labels pick the
    SAME axis convention from the SAME criterion (`summary_symbols`)
    -- three different answers about the same `Results` would be worse than
    one wrong one."""
    if project is not None:
        return bool((project.config or {}).get("is_propeller", False))
    for r in results_list or ():
        valor = r.summary.get("cfg_is_propeller")
        if valor is not None:
            return bool(valor)
    return False


def _chaves_ordenadas(results_list: list, is_propeller: Optional[bool] = None) -> tuple:
    """Returns (primary+remaining, cfg) -- the union of the keys of all
    the results, with reading quantities up front and the configuration
    echo separated out.

    ``rotor_rpm`` leaves the list when it is literally ``rpm`` again
    (see `_rotor_rpm_e_redundante`).

    ``is_propeller`` (``None`` = deduce from `modo_helice`) changes TWO things
    and neither of them is a value: the order of the first columns (a propeller
    reads by axial advance) and which of the two angles is shown -- both read
    from `nomenclature`, so the table, the plots and the `.bemt` writer agree
    by construction."""
    if is_propeller is None:
        is_propeller = modo_helice(results_list)
    chaves: list = []
    vistas = set()
    for r in results_list:
        for k in r.summary.keys():
            if k not in vistas:
                vistas.add(k)
                chaves.append(k)
    if "rpm" in vistas and _rotor_rpm_e_redundante(results_list):
        vistas.discard("rotor_rpm")
        chaves = [k for k in chaves if k != "rotor_rpm"]
    for k in [c for c in chaves if not nomenclature.is_visible(c, is_propeller)]:
        vistas.discard(k)
        chaves = [c for c in chaves if c != k]
    principais = [k for k in nomenclature.primary_order(is_propeller) if k in vistas]
    principais += [k for k in _COLUNAS_PRINCIPAIS
                   if k in vistas and k not in principais]
    cfg = [k for k in chaves if k.startswith("cfg_")]
    restantes = [k for k in chaves if k not in principais and k not in cfg]
    return principais + restantes, cfg


# =============================================================================
# `Results.summary` metadata -- PUBLIC API
# =============================================================================
# `_SIMBOLO_DE_COLUNA`/`_UNIDADE_DE_COLUNA`/`_COLUNAS_PRINCIPAIS`/`_formatar`/
# `_chaves_ordenadas` above are the ONLY source of truth about what each
# `Results.summary` key means (symbol, description, unit,
# formatting, reading order) -- coverage guaranteed by
# `tests/test_api.py`. Exposed here under a public name so that the GUI (Run
# Case, Results) uses the SAME symbols/units/tooltips as the HTML
# report, instead of keeping a second, manually maintained copy that drifts (that was
# exactly what `run_case.py`'s `_GRUPOS_ROTOR`/`_GRUPOS_HELICE`
# did before this exposure).
SUMMARY_SYMBOLS = _SIMBOLO_DE_COLUNA
SUMMARY_UNITS = _UNIDADE_DE_COLUNA
SUMMARY_PRIMARY_KEYS = _COLUNAS_PRINCIPAIS
format_summary_value = _formatar
summary_keys_union = _chaves_ordenadas
#: Condition label ("Case 1", "Case 2"...) -- exposed so that the GUI
#: (Results tab table) labels rows EXACTLY like the report and
#: the figure captions do, instead of keeping its own `r.condition_name or f"case
#: {row+1}"`, which only numbers when the name is empty (and not
#: when it is the same across all rows, which is the common case).
condition_labels = rotulos_de_condicao


def _summary_table(results_list: list, is_propeller: bool = False) -> str:
    """Summary table in HTML.

    With ONE condition, it comes out transposed and in blocks: quantity|value, several
    rows and few columns. It used to be a single row with ~70 columns, which forced
    endless sideways scrolling to read a single case.

    With SEVERAL conditions the matrix orientation is the right one (one row per
    condition allows comparison), so it is kept -- that is what the
    sweep exists for.

    The configuration echo (`cfg_*` keys) is set apart, collapsed: it is ~40
    values identical across all conditions, which only push CT/CQ/FM further away.
    """
    ordenadas, cfg = _chaves_ordenadas(results_list, is_propeller)
    # NUMBERED label, not the raw `condition_name`: five cases coming from Run
    # Case all arrive here called "caso", and five identical rows in the
    # first column would not let any of them be cited (see
    # `rotulos_de_condicao`). It is the SAME label that goes into the file
    # name and, through it, into each figure's caption.
    rotulos = rotulos_de_condicao(results_list)

    def celulas(r, ks):
        return [_formatar(r.summary.get(k, "")) for k in ks]

    # ONE ROW PER CONDITION, with ALL output quantities in columns --
    # including the single-condition case (which used to come out transposed in
    # quantity|value blocks). Two different orientations for the same data
    # forced the reader to relearn the table when switching reports, and the
    # "Additional quantities per condition" block that carried the rest was
    # worse: it repeated the NAME of each quantity once per condition, so
    # comparing the same quantity between two cases required scrolling between two
    # distant blocks -- exactly what a matrix solves in one row.
    #
    # The ~50 columns do not fit in 1600 px and should not: the horizontal
    # scrolling lives INSIDE `.tablewrap` (see `_REPORT_CSS`), so the
    # page never scrolls sideways, only the table does. A narrow, uniform-width
    # column (`table-layout: fixed`) keeps this legible.
    html = _tabela_html(
        ["condition"] + ordenadas,
        [[rotulo] + celulas(r, ordenadas)
         for rotulo, r in zip(rotulos, results_list)],
        is_propeller=is_propeller)
    if cfg:
        # The config echo is the only block that stays collapsed: it is ~46
        # IDENTICAL values across every condition (they do not vary with the case), so
        # it is not output data -- it is the record of what was configured, which
        # already appears summarized in "What was run".
        html += (
            "<details><summary>Configuration echo ("
            f"{len(cfg)} fields, identical across all conditions)</summary>"
            + _tabela_html(["condition"] + cfg,
                            [[rotulo] + celulas(r, cfg)
                             for rotulo, r in zip(rotulos, results_list)],
                            vertical=True, is_propeller=is_propeller)
            + "</details>")
    return html


def _report_metadata(project: Optional[Project], results_list: list) -> str:
    """"What was run" block. A report without this is pretty and useless:
    six months later nobody knows which mesh, which solver, or which rotor
    produced those numbers.

    Deliberately GENEROUS with what it shows here -- better a taller
    block (some fields the reader does not need today) than a "pretty and
    short" report that forces reopening the `.bemt` to find out the twist or
    the reverse-flow model used. Split into two columns
    (`.meta-cols`) so it does not become one gigantic column."""
    geral: list[tuple[str, str]] = []
    fisica: list[tuple[str, str]] = []
    if project is not None:
        cfg = project.config if isinstance(project.config, dict) else asdict(project.config)
        geom = project.geometry
        af = project.airfoil
        multi_secao = len(project.airfoil_sections or []) >= 2

        geral += [
            ("Project", str(project.name or "(unnamed)")),
            ("Mode", "propeller" if cfg.get("is_propeller") else "rotor"),
            ("Blades", str(getattr(geom, "n_blades", "?"))),
            ("Radius", f"{getattr(geom, 'radius_m', float('nan')):.4g} m"),
            ("Root cutout", f"{getattr(geom, 'root_cutout_norm', float('nan')):.3g} R"),
            ("Mesh", f"Ne={cfg.get('Ne', '?')} x Npsi={cfg.get('Npsi', '?')}"),
            ("Solver", f"{cfg.get('solver', '?')} (max_iter={cfg.get('max_iter', '?')}, "
                       f"tol={cfg.get('tol', '?')})"),
            ("Inflow", str(cfg.get("inflow_field_model", "?"))),
            ("Prandtl loss", str(cfg.get("prandtl_loss_mode", "?"))),
            ("Reverse flow", str(cfg.get("reverse_flow_model", "?"))),
            ("Compressibility", "on" if cfg.get("use_compressibility") else "off"),
            ("Rotational augmentation", "on" if cfg.get("use_rotational_augmentation") else "off"),
        ]

        twist = list(getattr(geom, "twist_deg", []) or [])
        chord = list(getattr(geom, "chord_norm", []) or [])
        if twist:
            fisica.append(("Twist (root &rarr; tip)", f"{twist[0]:.3g}&deg; &rarr; {twist[-1]:.3g}&deg;"))
        if chord:
            fisica.append(("Chord c/R (root &rarr; tip)", f"{chord[0]:.3g} &rarr; {chord[-1]:.3g}"))

        if multi_secao:
            fisica.append(("Airfoil", f"multi-section ({len(project.airfoil_sections)} sections)"))
            fisica.append(("Sections at r/R", ", ".join(
                f"{s.r_norm:.2g}" for s in project.airfoil_sections if s.r_norm is not None)))
        else:
            fisica += [
                ("Airfoil", f"{af.source} / stall_model={af.stall_model}"),
            ]
            if af.source == "analytical":
                fisica += [
                    ("C<sub>l,&alpha;</sub>, &alpha;<sub>0</sub>",
                     f"{af.cl_alpha:.3g} /rad, {af.alpha0_deg:.3g}&deg;"),
                    ("C<sub>d0</sub>, k", f"{af.cd0:.3g}, {af.k:.3g}"),
                    ("Stall angles", f"{af.alpha_stall_neg_deg:.3g}&deg; &hellip; "
                                     f"{af.alpha_stall_pos_deg:.3g}&deg;"),
                ]
            elif af.source == "table":
                slices = list(getattr(af, "table_slices", []) or [])
                fisica.append(("Polar table", f"{len(slices)} slice(s)"))
                reynolds = sorted({s.reynolds for s in slices if s.reynolds is not None})
                if reynolds:
                    fisica.append(("Reynolds", ", ".join(f"{r:.3g}" for r in reynolds)))
            elif af.source in ("external", "neuralfoil"):
                fisica.append(("Polar source", str(af.source)))
            if models.uses_full_range_extension(af):
                fisica.append(("Viterna extension", "on"))
            if af.use_dynamic_stall:
                fisica.append(("Dynamic stall", f"&Oslash;ye, A={af.dynamic_stall_A:.3g}"))

    fisica.append(("Conditions", str(len(results_list))))

    def _dl(bloco):
        return ('<dl class="meta">'
                + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in bloco)
                + "</dl>")

    return '<div class="meta-cols">' + _dl(geral) + _dl(fisica) + "</div>"


#: Report plot sections, IN THE ORDER they appear. The order is
#: deliberate: the per-field disk maps come BEFORE the panel with all 12
#: together -- the panel is a visual index, useful for finding again the field
#: just examined, not for presenting it for the first time.
#: Up to how many conditions each PER-CASE section tolerates. The report is an
#: email attachment, not a project file: `disk_map` renders THIRTEEN
#: figures per condition (12 fields + the panel), so a sweep of 8
#: cases already went past 15 MB. Above the limit it falls back to just the panel
#: of 12 together -- which preserves the information at the cost of one figure. The
#: one-figure-per-case sections (azimuth, span, convergence) tolerate much
#: more. Every cut is ANNOUNCED in the report, never silent.
#: Maximum width (px) of figures embedded in the report -- a safety
#: ceiling, NOT a resampling target. Figures come out of matplotlib
#: at ~1920 px; the report body has `max-width: 1600px`, so
#: 1920 px natively already gives ~1.2x oversampling (crisp on
#: HiDPI screens) and still weighs less than the resampled and recompressed version
#: that used to live here. The limit only kicks in for a figure that is really
#: out of the ordinary (see `_figura_embutida`).
_LARGURA_MAXIMA_FIGURA = 2600


#: Caption by file prefix (`_result_plot_path`/`export_results`
#: generate names like ``"{base}_{sanitized condition}.png"``): without this, the
#: report showed the raw filename (``disk_map_Cd_cruise``) as the
#: caption, which is the internal name, not what explains the figure to whoever reads the
#: report without having looked at the code. Matching by LONGEST prefix
#: first, so "disk_map_grid" does not fall under the generic pattern of
#: "disk_map_{field}".
_ROTULO_POR_PREFIXO = [
    ("airfoil_cl_alpha", "Airfoil polar -- lift coefficient vs angle of attack"),
    ("airfoil_cd_alpha", "Airfoil polar -- drag coefficient vs angle of attack"),
    ("airfoil_cd_cl", "Airfoil polar -- drag vs lift (drag polar)"),
    ("airfoil_profile", "Airfoil 2D profile"),
    ("blade_planform", "Blade planform (top view)"),
    ("blade_chord_twist", "Blade chord and twist distribution"),
    ("blade_rotor_3d", "Rotor blade geometry (3D)"),
    ("disk_map_grid", "Disk maps (all fields)"),
    ("coefficients_vs_", "Performance coefficients vs "),
    ("loads_vs_azimuth", "Loads along azimuth"),
    ("blade_loads_vs_span", "Loads along blade span"),
    ("convergence", "Solver convergence"),
    ("disk_map_", "Disk map -- "),
]

#: Spelled-out name of each disk-map field, for the figure
#: caption (``disk_map_Cd_...`` -> "Disk map -- drag coefficient (Cd)").
#: Same fields as `viz.plots._DISK_FIELD_META`, in prose instead of
#: mathtext -- a `<figcaption>` caption does not render LaTeX.
_ROTULO_DE_CAMPO = {
    "Fn": "normal force (Fn)", "Ft": "tangential force (Ft)",
    "Cl": "lift coefficient (Cl)", "Cd": "drag coefficient (Cd)",
    "Vi": "induced velocity (Vi)", "Up": "perpendicular velocity (Up)",
    "Ut": "tangential velocity (Ut)", "W": "resultant velocity (W)",
    "alpha_eff": "effective angle of attack", "phi": "inflow angle (phi)",
    "lambda_z_field": "total inflow ratio (lambda)",
    "lambda_i": "induced inflow ratio (lambda_i)",
}


def _legenda_de_figura(caminho: str) -> str:
    """Derives a readable caption from the file NAME (does not open the image).

    The filename already carries all the information (`_result_plot_path`
    assembles ``"{base}_{condition}.png"``) -- this function only reformats it in
    prose. If no known prefix matches (a figure from a new section,
    still without an entry in `_ROTULO_POR_PREFIXO`), it falls back to the
    raw filename instead of raising -- an ugly caption is a smaller problem
    than a report that fails to finish generating."""
    stem = Path(caminho).stem
    for prefixo, rotulo in _ROTULO_POR_PREFIXO:
        if not stem.startswith(prefixo):
            continue
        resto = stem[len(prefixo):].lstrip("_")
        if prefixo == "disk_map_":
            # Match by LONGEST field first: "lambda_z_field" and
            # "lambda_i" also have "_" in their own name, so a
            # naive `partition("_")` would cut at "lambda" and drag the rest
            # of the field name into the condition by mistake.
            campo = next((c for c in sorted(_ROTULO_DE_CAMPO, key=len, reverse=True)
                          if resto == c or resto.startswith(c + "_")), None)
            if campo is None:
                campo, _, condicao = resto.partition("_")
                campo_legivel = campo
            else:
                condicao = resto[len(campo):].lstrip("_")
                campo_legivel = _ROTULO_DE_CAMPO[campo]
            texto = f"{rotulo}{campo_legivel}"
        elif prefixo == "coefficients_vs_":
            # `resto` IS the whole axis (e.g. "collective_deg" has "_" in its
            # own name) -- this file carries no condition
            # suffix, it is a sweep aggregating ALL conditions.
            texto = f"{rotulo}{resto}"
            condicao = ""
        else:
            texto = rotulo
            condicao = resto
        if condicao:
            texto += f" -- {_condicao_legivel(condicao)}"
        return texto
    return stem


#: The `_` that `sanitize_filename` put in place of SPACES turn back into a space
#: in the caption; the ones that are part of a quantity's NAME do not.
#: Since the x/z standardization every symbol has a subscript (`mu_x`, `J_z`,
#: `alpha_rotor`, `lambda_z`), so the raw `replace('_', ' ')` used to turn
#: "mu_x=0.2" into "mu x=0.2" in EVERY figure caption in the report.
_SIMBOLOS_COM_SUBSCRITO = (
    "mu_x", "mu_z", "J_x", "J_z", "V_x", "V_z", "Vx", "Vz",
    "lambda_x", "lambda_z", "lambda_i", "lambda_total",
    "alpha_rotor", "alpha_disk", "collective_deg", "Vz_total", "Vx_total",
)


def _condicao_legivel(condicao: str) -> str:
    """Condition name coming from the FILE NAME, turned back into prose."""
    marcado = condicao
    for i, simbolo in enumerate(sorted(_SIMBOLOS_COM_SUBSCRITO,
                                        key=len, reverse=True)):
        marcado = marcado.replace(simbolo, f"\x00{i}\x00")
    marcado = marcado.replace("_", " ")
    for i, simbolo in enumerate(sorted(_SIMBOLOS_COM_SUBSCRITO,
                                        key=len, reverse=True)):
        marcado = marcado.replace(f"\x00{i}\x00", simbolo)
    return marcado


def _figura_embutida(caminho: str) -> str:
    """PNG in base64, at NATIVE resolution when that is already reasonable.

    This function used to resample EVERY figure above 1500 px down to 1500 and
    re-encode it as JPEG q88. Figures come out of matplotlib at 1920 px
    wide, so that was a 1920->1500 downscale followed by
    lossy compression -- on top of thin lines and text, which is
    exactly where JPEG artifacts show up. Result: a visibly blurred
    figure in a report that gets read on a HiDPI screen (where 1500 CSS px are
    already 3000 physical px). And it saved nothing: the native 1920 px PNG
    (~204 KB for the 12-map panel) is SMALLER than the 1500 px JPEG
    (~180 KB) per pixel delivered, and it is lossless.

    Now: below the limit, the original PNG passes through intact. Only above it
    (a really huge figure) is there resampling -- and in PNG, not JPEG, so as
    not to blur lines and text."""
    import base64
    legenda = _legenda_de_figura(caminho)
    dados = Path(caminho).read_bytes()
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(dados))
        if im.width > _LARGURA_MAXIMA_FIGURA:
            altura = round(im.height * _LARGURA_MAXIMA_FIGURA / im.width)
            im = im.resize((_LARGURA_MAXIMA_FIGURA, altura), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
            dados = buf.getvalue()
    except Exception:
        pass    # no Pillow, or unexpected format: embed as is
    return ('<figure><img src="data:image/png;base64,'
            + base64.b64encode(dados).decode("ascii")
            + f'"><figcaption>{legenda}</figcaption></figure>')


#: Above how many figures a section ALWAYS becomes its own file. At 1,
#: in practice every plot section leaves the master (none has only one
#: figure, except the coefficient curve of a sweep) -- which is the
#: intended design: the master is the INPUTS + OUTPUTS table page, and
#: each plot type is a separate report, linked from there.
#:
#: This replaces a CUTOFF limit that used to exist here: above 3
#: conditions the report DISCARDED the 12 per-case disk-map figures
#: and announced the discard in a yellow box, offering as the only
#: way out "regenerate with fewer conditions". A report that declares in
#: writing that it is incomplete is not a report. Now nothing is omitted --
#: only relocated.
_FIGURAS_ANTES_DE_ARQUIVO_PROPRIO = 1

#: Section order. The first two are the drawn INPUTS (blade and
#: polar): they come before the results because that is the order in which an
#: engineering report is read -- first what was modeled, then what
#: came out. They used to be missing entirely, and without them there was no way to check the
#: aerodynamic hypothesis that produced the numbers without reopening the GUI.
_SECOES_DO_RELATORIO = (
    ("blade_geometry", "Blade geometry"),
    ("airfoil_polar", "Airfoil polars"),
    ("coefficients", "Performance coefficients"),
    ("azimuth",      "Loads along azimuth"),
    ("span",         "Loads along blade span"),
    ("disk_map",      "Disk maps"),
    ("disk_map_grid", "Disk maps (panel per case)"),
    ("convergence",  "Convergence"),
)


def _slug_de_secao(titulo: str) -> str:
    """"Loads along azimuth" -> "loads_along_azimuth", for the
    satellite report's file name."""
    return re.sub(r"[^a-z0-9]+", "_", titulo.lower()).strip("_")


def _pagina_satelite(titulo: str, figuras: list, master_name: str,
                      report_title: str) -> str:
    """Complete HTML of a satellite report: one section of figures, with a
    link back to the master. Same CSS as the master, so the two pages
    are visibly the same document."""
    return "\n".join([
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>{report_title} &mdash; {titulo}</title>",
        f"<style>{_REPORT_CSS}</style></head><body>",
        f'<p class="sub"><a href="{master_name}">&larr; back to the main report</a></p>',
        f"<h1>{titulo}</h1>",
        f'<p class="sub">{report_title} &mdash; {len(figuras)} figure(s)</p>',
        *figuras,
        f"<script>{_REPORT_JS}</script>",
        "</body></html>",
    ])


def _ordenar_por_condicao(caminhos: list, results_list: list) -> list:
    """Sorts files BY CONDITION in the same order as ``results_list`` (the
    order in which the user ran/selected the cases), not in
    alphabetical order of the filename.

    Plain `sorted()` on top of the filename (``..._mu=0.1.png`` vs
    ``..._mu=0.png``) compares character by character: "1" (digit) comes
    before "p" (from ".png") in the ASCII table, so "mu_x=0.1"/"mu_x=0.2"/
    "mu_x=0.3" used to come out BEFORE "mu_x=0" -- a sweep mu_x=0, 0.1, 0.2, 0.3
    showed up in the report as 0.1, 0.2, 0.3, 0. Condition names are
    free text, they will not sort numerically by luck; the only
    order the engine knows for sure is the one ``results_list`` already
    has."""
    condicoes_em_ordem = nomes_de_arquivo_de_condicao(results_list)

    def posicao(caminho: str) -> int:
        nome = Path(caminho).stem
        # longest condition first: avoids "c1" matching inside
        # "c10" by mistake when both are valid condition names
        for i, cond in sorted(enumerate(condicoes_em_ordem),
                               key=lambda par: -len(par[1])):
            if cond and nome.endswith(cond):
                return i
        return len(condicoes_em_ordem)   # no recognized condition: goes last

    return sorted(caminhos, key=posicao)


def _ordenar_mapas_de_disco(caminhos: list, results_list: list) -> list:
    """Field by field first, the panel of 12 last; within each
    group, in `results_list` order (see `_ordenar_por_condicao`)."""
    individuais = [c for c in caminhos if "disk_map_grid" not in Path(c).name]
    grids = [c for c in caminhos if "disk_map_grid" in Path(c).name]
    return (_ordenar_por_condicao(individuais, results_list)
            + _ordenar_por_condicao(grids, results_list))


def generate_report(results, path: str, *, project: Optional[Project] = None,
                    title: str = "zBEMT Report",
                    plots: Optional[list[str]] = None,
                    notes: Optional[str] = None,
                    dpi: int = 150) -> Path:
    """Generates a self-contained HTML report at ``path`` and returns the path.

    ``results``: a ``Results`` or a list of them (whatever ``run_case`` /
    ``run_batch`` return, no conversion).

    ``project``: optional, but recommended -- it is what allows recording the
    mesh, solver, rotor and polar in the header. Without it the report brings only
    the numbers, without the context that makes them reproducible.

    ``plots``: same names as ``export_results``. Default: everything that
    applies to the selection -- performance coefficients (when there is more than one
    condition, otherwise there is no curve), loads along azimuth and span, disk
    maps and convergence. Pass ``[]`` for a table-only report,
    or an explicit list to choose.

    Sections come out in a FIXED ORDER (``_SECOES_DO_RELATORIO``), with a title
    of their own -- not in alphabetical order of the filename, which used to mix
    everything up.

    ``notes``: free text from the user, embedded as an observations block.

    Images are embedded in base64: the HTML is a single file that can
    be attached to an email without needing to bring along a folder of PNGs.
    """
    import tempfile
    import time

    results_list = list(results) if isinstance(results, list) else [results]
    if not results_list:
        raise ValueError("generate_report: no results to report.")

    tem_mapas = any(bool(getattr(r, "maps", None)) for r in results_list)
    if plots is None:
        plots = []
        # Drawn inputs (blade + polar) first: they only come out if there is a
        # `project` to draw them from (the report works without it, with only
        # the `Results` in hand -- see docstring).
        if project is not None:
            plots += ["blade_geometry", "airfoil_polar"]
        # A single case has no performance curve: one point is not a curve.
        if len(results_list) > 1:
            plots.append("coefficients")
        if tem_mapas:
            plots += ["azimuth", "span", "disk_map"]
        plots.append("convergence")

    secoes: list[tuple[str, list[str]]] = []
    if plots:
        with tempfile.TemporaryDirectory() as tmp:
            # A single call avoids redrawing the same cases for each
            # section. This reduces cost and keeps the worker free of
            # unnecessary pyplot reentrancy.
            try:
                escritos = export_results(results_list, tmp, plots=plots,
                                          save_csv=False, project=project,
                                          layout="flat", dpi=dpi)
            except Exception:
                # One optional plot must not wipe out every figure in the
                # report. If a combination fails, re-export each kind
                # separately to preserve the valid sections; the normal
                # path is still a single pass.
                escritos = []
                for plot_kind in plots:
                    try:
                        escritos.extend(export_results(
                            results_list, tmp, plots=[plot_kind],
                            save_csv=False, project=project,
                            layout="flat", dpi=dpi))
                    except Exception:
                        continue

            por_secao: dict[str, list[str]] = {kind: []
                                               for kind, _ in _SECOES_DO_RELATORIO}
            extras: list[str] = []
            for caminho in (a for a in escritos if a.endswith(".png")):
                nome = Path(caminho).name
                if nome.startswith("airfoil_"):
                    kind = "airfoil_polar"
                elif nome.startswith("coefficients_vs_"):
                    kind = "coefficients"
                elif nome.startswith("loads_vs_azimuth"):
                    kind = "azimuth"
                elif nome.startswith("blade_loads_vs_span"):
                    kind = "span"
                elif nome.startswith("disk_map_grid"):
                    # The consolidated panel belongs to the same section as the
                    # individual maps and must appear after them.
                    kind = "disk_map"
                elif nome.startswith("disk_map_"):
                    kind = "disk_map"
                elif nome.startswith("blade_"):
                    kind = "blade_geometry"
                elif nome.startswith("convergence"):
                    kind = "convergence"
                else:
                    extras.append(caminho)
                    continue
                por_secao[kind].append(caminho)

            for kind, titulo in _SECOES_DO_RELATORIO:
                pngs = por_secao[kind]
                if kind == "disk_map":
                    pngs = _ordenar_mapas_de_disco(pngs, results_list)
                else:
                    pngs = _ordenar_por_condicao(pngs, results_list)
                if pngs:
                    secoes.append((titulo, [_figura_embutida(a) for a in pngs]))
            if extras:
                secoes.append(("Additional plots",
                                [_figura_embutida(a) for a in sorted(extras)]))

    destino = Path(path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    # A new export may have fewer heavy sections than the previous one. Without
    # removing the old satellites, a browser could still open a stale
    # `report_blade_geometry.html` and show figures that no longer
    # belong to that section.
    for antigo in destino.parent.glob(f"{destino.stem}_*.html"):
        try:
            antigo.unlink()
        except OSError:
            pass

    # A heavy section (many figures) becomes its own file next to the master;
    # a light section stays embedded. This way the master remains ONE file that
    # opens quickly and brings what is consulted first (inputs + output
    # table), and no figure is discarded -- only relocated.
    satelites: list[tuple[str, str, int]] = []      # (title, file name, number of figures)
    embutidas: list[tuple[str, list[str]]] = []
    for titulo, figuras in secoes:
        if len(figuras) > _FIGURAS_ANTES_DE_ARQUIVO_PROPRIO:
            nome = f"{destino.stem}_{_slug_de_secao(titulo)}.html"
            (destino.parent / nome).write_text(
                _pagina_satelite(titulo, figuras, destino.name, title),
                encoding="utf-8")
            satelites.append((titulo, nome, len(figuras)))
        else:
            embutidas.append((titulo, figuras))

    partes = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>{title}</title><style>{_REPORT_CSS}</style></head><body>",
        f"<h1>{title}</h1>",
        f'<p class="sub">Generated on {time.strftime("%Y-%m-%d %H:%M")}</p>',
        "<h2>What was run</h2>", _report_metadata(project, results_list),
    ]
    if notes:
        partes += ["<h2>Notes</h2>", f'<div class="nota">{notes}</div>']
    partes += ["<h2>Summary</h2>",
               _summary_table(results_list, modo_helice(results_list, project))]
    if satelites:
        partes += ["<h2>Figure sets</h2>",
                   '<p class="sub">These sections have enough figures to live in '
                   'their own file, so this page stays quick to open. Nothing is '
                   'omitted.</p>',
                   '<ul class="satelites">'
                   + "".join(f'<li><a href="{nome}">{titulo}</a> '
                             f'<span class="cnt">{n} figure(s)</span></li>'
                             for titulo, nome, n in satelites)
                   + "</ul>"]
    for titulo, figuras in embutidas:
        partes += [f"<h2>{titulo}</h2>"] + figuras
    partes.append(f"<script>{_REPORT_JS}</script>")
    partes.append("</body></html>")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(partes), encoding="utf-8")
    return destino
