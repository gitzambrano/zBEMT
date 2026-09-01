"""Records the numbers every example project produces, so that a change to
the physics shows up as a diff instead of as silence.

WHY THIS EXISTS
---------------
The suite locks a handful of hand-written values (`CT = 0.027625` and a few
more). Everything else about the engine's OUTPUT was unguarded: a change to
an inflow model, a loss factor or an integration rule could shift every
coefficient of every project by a few percent and no test would notice,
because no test knew what those coefficients were supposed to be.

This script solves every saved case of every project under `projects/` with
the project's own configuration and writes the results to
`tests/data/golden_results.json`. `tests/regression/test_golden_results.py` compares the
live run against that file.

The point is NOT that the recorded numbers are right in an absolute sense --
they are what the code produces today. The point is that changing them has to
be deliberate: the diff of this file is the change to the physics, stated in
the units the user reads.

CHANGING A NUMBER ON PURPOSE
----------------------------
    python tools/golden_snapshot.py

and read the diff before committing it. A one-line physics fix that moves
forty numbers is telling you something.

USAGE
-----
    python tools/golden_snapshot.py            # every project
    python tools/golden_snapshot.py starter_rotor
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from zbemt import api                                        # noqa: E402
from zbemt.models import Project                             # noqa: E402

DEFAULT_PROJECTS_DIR = None          # None means ROOT / "projects"

OUTPUT = ROOT / "tests" / "data" / "golden_results.json"

#: The summary keys recorded. Deliberately the OUTPUTS a reader of the
#: results table looks at first, not every one of the ninety-odd columns:
#: the `cfg_*` echo repeats the input, and the timings are machine
#: dependent. A key absent from a given run (propeller coefficients on a
#: rotor project) is simply not recorded for it.
KEYS = (
    "Thrust", "Torque", "Power", "Power_i", "Power_p",
    "CT", "CQ", "CP", "CPi", "CPp", "CH", "CY", "CMx", "CMy", "FM",
    "CT_prop", "CQ_prop", "CP_prop", "eta_prop",
    "Vi", "lambda_i", "lambda_total", "convergence_pct",
)

#: Digits kept. Ten significant digits would turn every platform difference
#: in the last bit of a `numpy` reduction into a test failure; six is far
#: tighter than any physically meaningful change and survives a different
#: BLAS.
DIGITS = 6


def _round(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if value != value:                                    # NaN
        return "nan"
    return round(float(value), DIGITS)


def collect_project(project_dir: Path) -> dict:
    """``{case name: {summary key: value}}`` for one project."""
    project: Project = api.open_project(str(project_dir))
    record = {}
    for condition in project.saved_cases:
        result = api.run_case(project, condition)
        record[condition.name] = {
            key: _round(result.summary[key])
            for key in KEYS if key in result.summary
        }
    return record


def collect(projects_dir: Path | None = None, only: str | None = None) -> dict:
    root = projects_dir or DEFAULT_PROJECTS_DIR or (ROOT / "projects")
    everything = {}
    for project_dir in sorted(Path(root).iterdir()):
        if not project_dir.is_dir() or (only and project_dir.name != only):
            continue
        everything[project_dir.name] = collect_project(project_dir)
    return everything


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if only:
        only = Path(only).name
    everything = collect(only=only)
    if only and OUTPUT.exists():
        complete = json.loads(OUTPUT.read_text(encoding="utf-8"))
        complete.update(everything)
        everything = complete
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(everything, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    cases = sum(len(v) for v in everything.values())
    print(f"golden results written to {OUTPUT}")
    print(f"  {len(everything)} project(s), {cases} case(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
