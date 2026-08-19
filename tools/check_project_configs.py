"""Sanity-checks every project under `projects/` before you trust it.

WHY THIS SCRIPT EXISTS
-----------------------
A zBEMT project is a folder of small JSON files (`inputs/*.bemt`): geometry,
airfoil, solver config, saved cases, batches. Nothing stops you from editing
those files by hand -- that's the point, they're meant to be readable and
editable, not an opaque binary blob. But hand-editing JSON has an obvious
failure mode: you can produce a file that is syntactically valid JSON, loads
without a Python exception, and STILL can't actually be solved -- a missing
`rpm` on a saved case, a `stall_model` typo, a geometry with mismatched array
lengths. Those failures normally only surface deep inside the GUI or the CLI,
often with a traceback that doesn't point back to the bad file.

This script is the fast, offline check you run BEFORE opening the GUI or
kicking off a batch: for every project folder, it (1) loads every `.bemt`
file, (2) confirms the loaded objects fill every field required to run --not
just "JSON parsed", but "this project can actually go through
`studies.run_case`"--, and (3) actually solves ONE cheap case (a tiny mesh, a
few iterations) to catch the failure modes that only show up once the solver
starts running, not from static inspection alone.

HOW TO EXTEND THIS SCRIPT
--------------------------
If you add a new required field to `BEMTConfig`/`AirfoilDef`/`RotorGeometryDef`
(in `zbemt/models.py`/`zbemt/bemt.py`) that has NO safe default, add a check
for it in `_check_required_fields()` below -- the goal is that this script
catches the problem, not a cryptic exception three layers into `bemt.py`.

USAGE
-----
Run with no arguments to check every project under `projects/`:

    python tools/check_project_configs.py

Or check a single project:

    python tools/check_project_configs.py projects/starter_rotor

Exit code is 0 if every checked project passes, 1 if any project has an
error (warnings/info-level issues do not fail the run -- only "error"-level
validation issues or an outright crash do).
"""
from __future__ import annotations

import sys
import traceback
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from zbemt import api                                       # noqa: E402
from zbemt.bemt import BEMTConfig                            # noqa: E402
from zbemt.models import FlightCondition, Project, default_project_paths  # noqa: E402

# Run with no arguments (e.g. the "Run" button in an IDE) checks every
# project folder under this directory. Point it elsewhere to check a
# different tree of projects (e.g. a folder of user-authored projects that
# isn't named "projects").
DEFAULT_PROJECTS_DIR = None  # None means RAIZ / "projects"

# The mesh used for the "does it actually solve" smoke test. Deliberately
# tiny -- this script checks CORRECTNESS of the config, not performance of
# the solver, so a coarse/fast mesh that finishes in well under a second per
# project is exactly right. Do not use the project's own (possibly
# production-sized) `config.Ne`/`config.Npsi` here.
_SMOKE_TEST_MESH = dict(Ne=6, Npsi=4, max_iter=40)


def _check_required_fields(project) -> list[str]:
    """Static checks beyond what `api.validate_project` covers.

    `api.validate_project` (called separately, see `_run_checks`) already
    checks physical/model consistency (e.g. "stall model X needs Y").  This
    function checks a narrower, more basic thing: are the fields that have
    NO reasonable default actually filled in? A blank/zero geometry radius
    or zero blade count will not raise inside `validate_project` (they are
    not "wrong physics", they are "there is no project here yet") but WILL
    make `solve_bemt` fail or silently produce garbage (division by zero,
    an empty mesh). Add a new check here whenever a new field like this is
    introduced.
    """
    problems = []
    geom = project.geometry
    if not geom.radius_m or geom.radius_m <= 0:
        problems.append(f"geometry.radius_m is missing or non-positive ({geom.radius_m!r})")
    if not geom.n_blades or geom.n_blades <= 0:
        problems.append(f"geometry.n_blades is missing or non-positive ({geom.n_blades!r})")
    if not geom.chord_norm or len(geom.chord_norm) == 0:
        problems.append("geometry.chord_norm is empty -- no radial stations defined")
    if not geom.r_norm or len(geom.r_norm) == 0:
        problems.append("geometry.r_norm is empty -- no radial stations defined")
    if geom.chord_norm and geom.r_norm and len(geom.chord_norm) != len(geom.r_norm):
        problems.append(
            f"geometry.chord_norm has {len(geom.chord_norm)} stations but "
            f"geometry.r_norm has {len(geom.r_norm)} -- radial arrays must match in length")

    # Cases/batches are optional (a project can be geometry+airfoil-only,
    # meant to be driven entirely from the CLI/GUI at run time) -- but if
    # ANY saved case exists, each one needs an rpm: `studies._require_rpm`
    # deliberately has no default (see its docstring), so a missing rpm
    # here is a real problem this script should catch before the solver
    # does, not a false positive.
    for case in project.saved_cases:
        if case.rpm is None:
            problems.append(f"saved case {case.name!r} has no rpm set")
    for batch in project.batches:
        for cond in getattr(batch, "conditions", None) or []:
            if getattr(cond, "rpm", None) is None:
                problems.append(f"batch {batch.name!r}: a condition has no rpm set")

    return problems


def _check_files_present(project_dir: Path) -> list[str]:
    """Confirms the files a runnable project needs actually exist on disk.

    `geom.bemt` and `airfoil.bemt` are the two files with NO safe fallback
    that still produces a meaningful rotor (missing ones silently become an
    empty/default `RotorGeometryDef()`/`AirfoilDef()` -- see
    `api.open_project` -- which loads fine and fails later, confusingly, in
    `_check_required_fields` or in the solver). Everything else (config,
    batches, saved_cases, meta) is genuinely optional.
    """
    paths = default_project_paths(str(project_dir))
    missing = []
    for key in ("geom", "airfoil"):
        if not paths[key].exists():
            missing.append(str(paths[key].relative_to(project_dir.parent)))
    return missing


def _smoke_test_solve(project) -> str | None:
    """Runs ONE tiny, cheap case through the real solver (`api.run_case`,
    the exact same entry point the GUI's "Run Case" button and the CLI's
    default action use -- not a lower-level engine call, so this test is
    honest about what "this project actually runs" means).

    Returns None on success, or a short error description on failure.
    This is the check that catches everything static inspection can't:
    an inconsistent combination of fields that only blows up once
    `element_state()`/the fixed-point solver actually runs.
    """
    try:
        BEMTConfig(**{**project.config, **_SMOKE_TEST_MESH})
    except TypeError as exc:
        return f"config has an unknown/invalid field: {exc}"

    if project.saved_cases:
        condition = project.saved_cases[0]
    else:
        # No saved case in the project -- synthesize a minimal, always-valid
        # one just to exercise the solver. This does NOT mean "the project
        # has no cases" is itself a problem (it commonly isn't: a
        # geometry+airfoil-only project driven entirely from the CLI is a
        # legitimate use) -- it only means this smoke test needs SOME
        # condition to solve.
        condition = FlightCondition(name="smoke-test", mu_x=0.0, collective_deg=6.0, rpm=600.0)
    if condition.rpm is None:
        condition = replace(condition, rpm=600.0)

    # A copy of the project with the tiny smoke-test mesh swapped in, so we
    # never run the project's own (possibly production-sized) mesh here --
    # see `_SMOKE_TEST_MESH`'s docstring above.
    smoke_project = Project(
        name=project.name, path=project.path,
        config={**project.config, **_SMOKE_TEST_MESH},
        geometry=project.geometry, airfoil=project.airfoil,
        airfoil_sections=project.airfoil_sections,
        batch=project.batch, batches=project.batches,
        saved_cases=project.saved_cases)

    try:
        api.run_case(smoke_project, condition)
    except Exception as exc:                                   # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"
    return None


def check_project(project_dir: Path) -> bool:
    """Checks one project folder. Prints a report. Returns True if it passed
    (no errors -- warnings are printed but do not fail the check)."""
    print(f"\n{project_dir.name}")
    print("-" * len(project_dir.name))

    missing_files = _check_files_present(project_dir)
    if missing_files:
        print(f"  [FAIL] missing required file(s): {', '.join(missing_files)}")
        return False

    try:
        project = api.open_project(str(project_dir))
    except Exception as exc:                                    # noqa: BLE001
        print(f"  [FAIL] could not load project: {type(exc).__name__}: {exc}")
        return False

    ok = True

    field_problems = _check_required_fields(project)
    for problem in field_problems:
        print(f"  [FAIL] {problem}")
        ok = False

    # `api.validate_project` covers physical/model-consistency issues (e.g.
    # "reverse_flow_model=X needs Y enabled") -- pass the saved cases too so
    # each one's rpm/collective/etc is checked in context, matching what the
    # GUI/CLI actually do before a run.
    try:
        issues = api.validate_project(project, conditions=project.saved_cases or None)
    except Exception as exc:                                    # noqa: BLE001
        print(f"  [FAIL] validate_project crashed: {type(exc).__name__}: {exc}")
        return False
    for issue in issues:
        tag = "FAIL" if issue.level == "error" else issue.level.upper()
        print(f"  [{tag}] {issue.message}")
        if issue.level == "error":
            ok = False

    if ok:
        smoke_error = _smoke_test_solve(project)
        if smoke_error:
            print(f"  [FAIL] smoke-test solve failed: {smoke_error}")
            ok = False
        else:
            print("  [OK] loads, validates, and solves a smoke-test case")

    return ok


def main(target: Path | None = None) -> int:
    if target is not None:
        project_dirs = [target]
    else:
        base = Path(DEFAULT_PROJECTS_DIR) if DEFAULT_PROJECTS_DIR else RAIZ / "projects"
        project_dirs = sorted(
            p for p in base.iterdir()
            if p.is_dir() and (p / "inputs").exists()
        )
        if not project_dirs:
            print(f"No project folders found under {base}")
            return 1

    results = {p.name: check_project(p) for p in project_dirs}

    print("\n" + "=" * 40)
    n_ok = sum(results.values())
    print(f"{n_ok}/{len(results)} project(s) passed")
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        print("Failed: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    # Accept an optional single-project path as argv[1]; zero args checks
    # every project under DEFAULT_PROJECTS_DIR (see docstring above).
    arg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    try:
        sys.exit(main(arg_path))
    except Exception:                                           # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
