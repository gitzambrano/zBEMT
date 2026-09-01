"""Run the public zBEMT CLI against an isolated project copy."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from .models import CliRunResult


ROOT = Path(__file__).resolve().parents[2]
_RESERVED_DESTINATION_FLAGS = frozenset({"--project", "--new", "--save-as"})


def _command_text(command: Sequence[str]) -> str:
    """Return an exact command line for the current platform."""
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


def _validate_arguments(arguments: Sequence[str]) -> tuple[str, ...]:
    """Reject arguments that can replace the isolated project destination."""
    normalized = tuple(str(argument) for argument in arguments)
    for argument in normalized:
        option = argument.split("=", 1)[0]
        if option in _RESERVED_DESTINATION_FLAGS:
            raise ValueError(f"The argument {option} is reserved by the CLI helper.")
    return normalized


def run_cli_in_project_copy(
    project_directory: Path,
    arguments: Sequence[str],
    working_directory: Path,
) -> CliRunResult:
    """Copy a project, run the public CLI, and capture generated CSV files."""
    source = Path(project_directory).resolve()
    if not source.is_dir():
        raise ValueError(f"Project directory does not exist: {source}")

    validated_arguments = _validate_arguments(arguments)
    work = Path(working_directory).resolve()
    if work == source or source in work.parents:
        raise ValueError(
            f"The working directory must not equal or be inside the source project: {work}"
        )
    work.mkdir(parents=True, exist_ok=True)
    project_copy = work / "project"
    if project_copy.exists():
        raise ValueError(f"Project copy already exists: {project_copy}")
    shutil.copytree(source, project_copy)

    command = [
        sys.executable,
        "-m",
        "zbemt.cli",
        "--project",
        str(project_copy),
        *validated_arguments,
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    generated_csv_paths = tuple(sorted(project_copy.rglob("*.csv")))
    return CliRunResult(
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
        generated_csv_paths=generated_csv_paths,
        command=_command_text(command),
        project_copy=project_copy,
    )
