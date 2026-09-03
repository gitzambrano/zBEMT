"""Confirm that a user-facing model-validity warning is written in English.

QR-5 requires English on every surface a user reads. This executor runs the
public CLI at a condition that drives the Pitt-Peters inflow outside its
linear range, then reads the warning from the exported result row.
"""
from __future__ import annotations

import csv
import re
import tempfile
from pathlib import Path
from typing import Any

from .cli_helper import run_cli_in_project_copy
from .evidence import Evidence, build_result, failure_result, status_of, utc_now
from .models import CheckResult, Claim, ExecutionContext


ROOT = Path(__file__).resolve().parents[2]
ROTOR_PROJECT = ROOT / "projects" / "starter_rotor"
CLAIM_IDS = frozenset({"REPO-PITT-WARNING"})

#: Portuguese function words that no English sentence contains. The list is
#: deliberately short: it holds only words with no English meaning, so an
#: English sentence can never match one.
PORTUGUESE_WORDS = (
    "disco", "com", "para", "nao", "não", "está", "uma", "dos",
    "das", "pelo", "pela", "sem", "ou seja", "velocidade", "rotor com",
)

_SENTENCE = re.compile(r"[A-Z][^.]*\.")


def _read_summary_row(path: Path) -> dict[str, str]:
    """Return the last row of one exported result file."""
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError(f"The result file is empty: {path}")
    return rows[-1]


def _portuguese_words_in(text: str) -> list[str]:
    """Return every listed Portuguese word that the text contains."""
    lowered = text.lower()
    return [word for word in PORTUGUESE_WORDS
            if re.search(rf"\b{re.escape(word)}\b", lowered)]


def execute_repository_quality_claim(claim: Claim, context: ExecutionContext) -> CheckResult:
    """Run one repository-quality claim and return its evidence record."""
    started_at = utc_now()
    if claim.claim_id not in CLAIM_IDS:
        return failure_result(
            claim, context, started_at,
            "The claim is outside the repository-quality executor domain.",
        )
    try:
        work_root = Path(context.output_directory) / "repository_quality_cli"
        work_root.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="pitt_warning_", dir=work_root))
        run = run_cli_in_project_copy(
            ROTOR_PROJECT,
            (
                "--rpm", "400", "--mu-inplane", "0.30", "--collective", "12",
                "--inflow", "pitt_peters_steady",
            ),
            work,
        )
        if run.exit_code != 0:
            raise RuntimeError(
                f"The public CLI exited with {run.exit_code}: "
                f"{run.stderr.strip() or run.stdout.strip()}")
        results = [path for path in run.generated_csv_paths
                   if path.stem.startswith("results")]
        if not results:
            raise RuntimeError("The public CLI generated no result file.")
        row = _read_summary_row(max(results, key=lambda path: path.stat().st_mtime_ns))
    except Exception as exc:
        return failure_result(
            claim, context, started_at,
            f"The public CLI probe failed: {type(exc).__name__}: {exc}",
        )

    warning = str(row.get("pitt_peters_warning", "") or "")
    fraction = row.get("pitt_peters_frac_reversed", "")
    portuguese = _portuguese_words_in(warning)
    sentences = _SENTENCE.findall(warning)
    measured: dict[str, Any] = {
        "pitt_peters_warning": warning,
        "pitt_peters_frac_reversed": fraction,
        "portuguese_words_found": portuguese,
        "complete_sentence_count": len(sentences),
        "warning_exported_in_result_row": "pitt_peters_warning" in row,
    }
    passed = bool(warning) and not portuguese and len(sentences) >= 1
    return build_result(claim, context, started_at, Evidence(
        status=status_of(passed),
        measured=measured,
        expected={
            "portuguese_words_found": [],
            "complete_sentence_count": "at least 1",
            "warning_exported_in_result_row": True,
        },
        tolerance="The exported warning must hold at least one complete English sentence and no Portuguese word.",
        command=run.command,
        notes=(
            "The condition drives the total inflow negative over part of the "
            "disk, so the engine writes its linear-theory warning. The check "
            "reads that warning from the exported result row."
        ),
        artifacts=tuple(str(path) for path in run.generated_csv_paths),
    ))
