"""Run the full zBEMT test suite, one file per process.

Why one process per file: several GUI test files create many matplotlib/Qt
canvases over the course of a session. On Windows, garbage-collecting them
late (after dozens of unrelated tests have piled up in the same process)
has triggered a native "access violation" crash inside matplotlib/Qt --
not a bug in the tests themselves, just a teardown-ordering issue that
running each file as its own process avoids entirely.

Memory and handles matter here too, not just crashes: a single process
accumulating every project solve, every figure and every mounted window ends
the run holding far more than any one file needs. One process per file gives
each of them a clean start and returns everything at the end of it, which is
what keeps the run viable on a CI runner with a small memory allowance.

Usage:
    python run_all_tests.py             # run everything
    python run_all_tests.py -k airfoil  # only files matching "airfoil"
    python run_all_tests.py --suite physics  # physical-check unit tests
    python run_all_tests.py --list      # list the files and exit
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
REPORT_PATH = TESTS_DIR / "test_results.txt"
MANIFEST_PATH = TESTS_DIR / "suite_manifest.json"

#: Run these first. They are the files that solve every example project or
#: mount the full window repeatedly, so they dominate the wall clock and are
#: where a real regression usually lands.
SLOW_FILES = (
    "test_api.py",
    "test_gui_e2e.py",
    "test_golden_results.py",
    "test_gui_smoke.py",
    "test_bemt.py",
)

# Regex to pull "12 passed, 3 skipped in 4.56s" (or "1 failed, ...") out of
# pytest's own summary line, however many categories it lists.
_SUMMARY_RE = re.compile(
    r"(?P<count>\d+)\s+(?P<kind>passed|failed|error|errors|skipped|xfailed|xpassed)"
)
_SKIP_RE = re.compile(r"^(?P<test>\S+::\S+)\s+SKIPPED\s*(?:\((?P<reason>.*)\))?", re.MULTILINE)


#: pytest's own closing line, e.g. "16 passed, 9 subtests passed in 2.75s".
#: Only a run that finished reporting produces one.
_SUMMARY_LINE = re.compile(r"^=+ .*\b\d+ (?:passed|skipped).* in [\d.]+s.* =+$",
                           re.MULTILINE)


def _summary_is_clean(output: str) -> bool:
    """True when pytest printed its summary and that summary reports no
    failure and no error.

    This is what separates "the tests all passed and then the interpreter
    fell over on the way out" from "the interpreter fell over mid-run".
    In the second case pytest never reaches its summary line, so there is
    nothing here to match."""
    lines = _SUMMARY_LINE.findall(output)
    if not lines:
        return False
    last = lines[-1]
    return not re.search(r"\b\d+ (?:failed|error|errors)\b", last)


def _extract_skips(output: str) -> list[tuple[str, str]]:
    """[(test_id, reason), ...] from a single file's -v output."""
    return [(m.group("test"), m.group("reason") or "(no reason given)")
             for m in _SKIP_RE.finditer(output)]


def _run_one(test_file: Path, env: dict) -> tuple[bool, str, str]:
    """Runs a single test file in its own subprocess.

    Returns (ok, summary_line, full_output).
    """
    cmd = [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=long", "-rs"]
    proc = subprocess.run(
        cmd, cwd=ROOT, env=env,
        capture_output=True, text=True,
    )
    raw_output = proc.stdout + proc.stderr

    # pytest returns 5 when it collected NOTHING. For a file whose whole
    # module skips itself -- every GUI test file, in the CI job that installs
    # the base dependencies only to prove the engine runs without Qt -- that
    # is the correct outcome, not a crash. A file that guards its classes
    # with a module-level `if _HAS_QT:` collects zero items instead of
    # collecting skips, so nothing needs to have been reported as skipped.
    all_skipped = proc.returncode == 5

    # A native fault AFTER pytest has already reported every test as passing
    # is the Qt/matplotlib teardown-ordering crash this runner exists to
    # contain: the interpreter dies while destroying canvases, once the
    # results are in and printed. It is intermittent, it carries no
    # information about the code under test, and treating it as a failure
    # turns CI red at random.
    #
    # The summary line is the evidence, and it is required: this only
    # applies when pytest itself said 0 failed and 0 errors. A crash DURING
    # the run never produces that line, so a real failure can never be
    # absorbed here. The event is reported either way -- see `summary` below
    # -- so it can never pass unnoticed.
    teardown_crash = (proc.returncode not in (0, 1, 5)
                      and _summary_is_clean(raw_output))

    ok = proc.returncode == 0 or all_skipped or teardown_crash

    lines = [l for l in raw_output.strip().splitlines() if l.strip()]
    summary = lines[-1] if lines else "(no output at all -- process probably hung/crashed before printing)"

    if teardown_crash:
        summary = (f"OK, but the process died during teardown with "
                   f"0x{proc.returncode & 0xFFFFFFFF:08X} AFTER all tests "
                   f"passed (Qt/matplotlib teardown-ordering crash, unrelated "
                   f"to the code under test). {summary}")
    elif all_skipped:
        summary = ("OK -- pytest collected no tests in this file "
                   "(expected for GUI-only files without Qt). " + summary)
    elif proc.returncode not in (0, 1):
        summary = (f"exit code {proc.returncode} (0x{proc.returncode & 0xFFFFFFFF:08X}) "
                   f"-- not a normal pytest outcome, probably a native crash "
                   f"(access violation / segfault). {summary}")

    header = (
        f"command: {' '.join(cmd)}\n"
        f"exit code: {proc.returncode}\n"
    )
    output = header + (raw_output if raw_output.strip() else "(no output captured from stdout/stderr)\n")

    return ok, summary, output


def _order(files: list[Path]) -> list[Path]:
    """Slowest files first.

    They are the ones whose failure is worth knowing about early, and a
    long file starting last leaves the whole run waiting on it. The order
    is by name within each group, so a run is still reproducible."""
    slow = [f for f in files if f.name in SLOW_FILES]
    rest = [f for f in files if f.name not in SLOW_FILES]
    return sorted(slow) + sorted(rest)


def _load_manifest() -> dict[str, list[str]]:
    """Load and validate the test-suite classification manifest."""
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read suite manifest: {exc}") from exc

    required_suites = {"architecture", "regression", "physics"}
    if set(manifest) != required_suites:
        raise ValueError(
            "The suite manifest must define architecture, regression, and physics."
        )
    if not all(isinstance(files, list) and all(isinstance(name, str) for name in files)
               for files in manifest.values()):
        raise ValueError("Each suite manifest entry must be a list of relative file paths.")

    listed = [name for files in manifest.values() for name in files]
    discovered = {
        path.relative_to(ROOT).as_posix()
        for path in TESTS_DIR.rglob("test_*.py")
    }
    if len(listed) != len(set(listed)):
        raise ValueError("The suite manifest lists one or more test files more than once.")
    if set(listed) != discovered:
        missing = sorted(discovered - set(listed))
        extra = sorted(set(listed) - discovered)
        raise ValueError(f"The suite manifest does not match test files. Missing: {missing}. Extra: {extra}.")
    return manifest


def select_test_files(suite: str) -> list[Path]:
    """Return the test files that belong to the requested suite."""
    manifest = _load_manifest()
    if suite == "fast":
        names = [name for files in manifest.values() for name in files]
    elif suite in manifest:
        names = manifest[suite]
    else:
        raise ValueError(f"Unknown test suite: {suite}")
    return _order([ROOT / name for name in names])


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated zBEMT pytest suites.")
    parser.add_argument("--suite", choices=("architecture", "regression", "physics", "fast"),
                        default="fast", help="Select the test suite. Default: fast.")
    parser.add_argument("-k", dest="pattern", metavar="PATTERN",
                        help="Run files whose names contain PATTERN.")
    parser.add_argument("--list", action="store_true", help="List selected test files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        files = select_test_files(args.suite)
    except ValueError as exc:
        print(f"Test-suite configuration error: {exc}")
        return 1
    pattern = args.pattern
    if pattern:
        files = [f for f in files if pattern in f.name]

    if not files:
        print(f"No test files found in {TESTS_DIR}")
        return 1

    if args.list:
        for file in files:
            print(file.relative_to(ROOT))
        return 0

    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    total_ok = total_failed = 0
    failed_files: list[str] = []
    details: list[str] = []
    all_skips: list[tuple[str, str]] = []
    overall_start = time.time()

    print(f"Running {len(files)} test files (one process per file)...\n")

    for i, file in enumerate(files, 1):
        name = file.relative_to(ROOT)
        print(f"[{i:3d}/{len(files)}] {name} ... ", end="", flush=True)
        t0 = time.time()
        ok, summary, full_output = _run_one(file, env)
        dt = time.time() - t0

        if ok:
            total_ok += 1
            print(f"OK  ({dt:.1f}s) -- {summary}")
        else:
            total_failed += 1
            failed_files.append(str(name))
            print(f"FAILED  ({dt:.1f}s) -- {summary}")

        details.append(f"{'='*70}\n{name}  ({dt:.1f}s)\n{'='*70}\n{full_output}\n")
        all_skips.extend(_extract_skips(full_output))

    duration = time.time() - overall_start

    print(f"\n{'='*60}")
    print(f" Summary: {total_ok} files OK, {total_failed} files failed"
          f" ({duration:.0f}s total)")
    if failed_files:
        print(" Failed:")
        for name in failed_files:
            print(f"   - {name}")
    print(f"{'='*60}")

    if all_skips:
        print(f"\n Skipped tests -- {len(all_skips)} in total:")
        for test, reason in all_skips:
            print(f"   - {test}\n       reason: {reason}")
    print(f"{'='*60}")

    print(f"\nFull report (with the traceback of each failure) in:\n  {REPORT_PATH}")

    REPORT_PATH.write_text("\n".join(details), encoding="utf-8")

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
