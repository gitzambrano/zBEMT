"""Define the typed claim and result records for physics checks."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


class EvidenceGrade(str, Enum):
    """State the current evidence grade for a claim."""

    UNVERIFIED = "UNVERIFIED"
    ANALYTICAL = "ANALYTICAL"
    LITERATURE = "LITERATURE"
    CROSS_MODEL = "CROSS_MODEL"
    LIMIT = "LIMIT"


class FinalStatus(str, Enum):
    """State one allowed final result status."""

    CONFIRMED_DEFECT = "CONFIRMED_DEFECT"
    CONFIRMED_CORRECT = "CONFIRMED_CORRECT"
    NOT_REPRODUCED = "NOT_REPRODUCED"
    INCONCLUSIVE = "INCONCLUSIVE"
    OUT_OF_SCOPE_LIMITATION = "OUT_OF_SCOPE_LIMITATION"


@dataclass(frozen=True)
class SourceReference:
    """Identify one claim occurrence in a preserved source report."""

    report: str
    original_id: str
    locator: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-compatible representation."""
        return {
            "report": self.report,
            "original_id": self.original_id,
            "locator": self.locator,
        }


@dataclass(frozen=True)
class SourceInventoryEntry:
    """Map one source occurrence to one canonical claim."""

    occurrence_id: str
    report: str
    original_id: str
    locator: str
    canonical_claim_id: str
    duplicate_of: str | None

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-compatible representation."""
        return {
            "occurrence_id": self.occurrence_id,
            "report": self.report,
            "original_id": self.original_id,
            "locator": self.locator,
            "canonical_claim_id": self.canonical_claim_id,
            "duplicate_of": self.duplicate_of,
        }


@dataclass(frozen=True)
class Claim:
    """Define one predeclared physical or product claim."""

    claim_id: str
    domain: str
    title: str
    source_references: tuple[SourceReference, ...]
    original_status: str
    requirement_codes: tuple[str, ...]
    evidence_grade: EvidenceGrade
    theory_reference_text: str
    acceptance_rule: str
    cli_route: str
    gui_route: str
    executor_name: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return {
            "claim_id": self.claim_id,
            "domain": self.domain,
            "title": self.title,
            "source_references": [item.to_dict() for item in self.source_references],
            "original_status": self.original_status,
            "requirement_codes": list(self.requirement_codes),
            "evidence_grade": self.evidence_grade.value,
            "theory_reference_text": self.theory_reference_text,
            "acceptance_rule": self.acceptance_rule,
            "cli_route": self.cli_route,
            "gui_route": self.gui_route,
            "executor_name": self.executor_name,
        }


@dataclass(frozen=True)
class CheckResult:
    """Record one completed or attempted claim execution."""

    claim_id: str
    final_status: FinalStatus
    measured_data: Mapping[str, Any]
    expected_data: Mapping[str, Any]
    tolerance_rule: str
    command: str
    artifacts: tuple[str, ...]
    notes: str
    started_at: str
    ended_at: str
    commit: str
    environment: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return {
            "claim_id": self.claim_id,
            "final_status": self.final_status.value,
            "measured_data": dict(self.measured_data),
            "expected_data": dict(self.expected_data),
            "tolerance_rule": self.tolerance_rule,
            "command": self.command,
            "artifacts": list(self.artifacts),
            "notes": self.notes,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "commit": self.commit,
            "environment": dict(self.environment),
        }


@dataclass(frozen=True)
class ExecutionContext:
    """Provide shared execution metadata to a domain executor."""

    output_directory: Path
    commit: str
    environment: Mapping[str, str]


@dataclass(frozen=True)
class CampaignOutcome:
    """Return the complete campaign result and aggregate exit status."""

    results: tuple[CheckResult, ...]
    execution_failures: int
    exit_code: int


@dataclass(frozen=True)
class CliRunResult:
    """Capture one public CLI execution in a copied project."""

    stdout: str
    stderr: str
    exit_code: int
    generated_csv_paths: tuple[Path, ...]
    command: str
    project_copy: Path
