"""Run the selected zBEMT quality checks and write one command report."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = ROOT / "tests" / "quality_check_results.txt"


def build_commands(suite: str, pattern: str | None = None) -> list[list[str]]:
    """Build the delegated commands for one requested quality suite."""
    test_runner = [sys.executable, str(ROOT / "tests" / "run_all_tests.py")]
    physics_runner = [sys.executable, str(ROOT / "tools" / "run_physics_checks.py")]

    if suite in ("architecture", "regression", "fast"):
        commands = [test_runner + ["--suite", suite]]
    elif suite == "physics":
        commands = [test_runner + ["--suite", "physics"], physics_runner]
    elif suite == "all":
        commands = [test_runner + ["--suite", "fast"], physics_runner]
    else:
        raise ValueError(f"Unknown quality suite: {suite}")

    if pattern:
        for command in commands:
            command.extend(["-k", pattern])
    return commands


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run zBEMT quality checks.")
    parser.add_argument("--suite", choices=("architecture", "regression", "physics", "fast", "all"),
                        default="fast", help="Select the quality suite. Default: fast.")
    parser.add_argument("--list", action="store_true", help="List delegated commands.")
    parser.add_argument("--dry-run", action="store_true", help="Write the report without running commands.")
    parser.add_argument("--keep-going", action="store_true",
                        help="Run later commands after a command fails.")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH,
                        metavar="PATH", help="Write the report to PATH.")
    parser.add_argument("-k", dest="pattern", metavar="PATTERN",
                        help="Pass PATTERN to each delegated check.")
    return parser.parse_args(argv)


def _command_text(command: list[str]) -> str:
    """Return a command line that the current platform can execute."""
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _write_report(report_path: Path, records: list[tuple[list[str], int | None, str]],
                  dry_run: bool) -> None:
    """Write the status and captured output for each delegated command."""
    lines = ["Quality check report"]
    if dry_run:
        lines.append("Mode: DRY RUN")
    for command, returncode, output in records:
        lines.extend(["", f"command: {_command_text(command)}"])
        if returncode is None:
            lines.append("exit code: not run")
        else:
            lines.append(f"exit code: {returncode}")
        if output:
            lines.append(output.rstrip())
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run commands, write their report, and return an aggregate status."""
    args = _parse_args(argv)
    commands = build_commands(args.suite, args.pattern)

    if args.list:
        for command in commands:
            print(_command_text(command))
        return 0

    records: list[tuple[list[str], int | None, str]] = []
    if args.dry_run:
        records = [(command, None, "") for command in commands]
        _write_report(args.output, records, dry_run=True)
        print(f"Quality check report: {args.output}")
        return 0

    failed = False
    for command in commands:
        print(f"Running: {_command_text(command)}")
        try:
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            output = completed.stdout + completed.stderr
            returncode = completed.returncode
        except OSError as exc:
            output = f"Could not start command: {exc}\n"
            returncode = 1
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
        records.append((command, returncode, output))
        if returncode != 0:
            failed = True
            if not args.keep_going:
                break

    _write_report(args.output, records, dry_run=False)
    print(f"Quality check report: {args.output}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
