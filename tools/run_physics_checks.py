"""Run registered zBEMT physics checks and write their result ledger."""
from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.physics_checks.ledger import CLAIMS, select_claims  # noqa: E402
from tools.physics_checks.registry import build_executor_registry  # noqa: E402
from tools.physics_checks.runner import run_campaign  # noqa: E402


def git_commit() -> str:
    """Return the current commit or a stable fallback name."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    commit = completed.stdout.strip()
    return commit if completed.returncode == 0 and commit else "unknown"


def environment_record() -> dict[str, str]:
    """Return the environment fields required by each result."""
    return {
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run zBEMT physics checks.")
    parser.add_argument("--list", action="store_true", help="List selected claims without running them.")
    parser.add_argument("--claim", action="append", default=[], metavar="ID",
                        help="Select one stable claim ID. The option can be repeated.")
    parser.add_argument("--domain", action="append", default=[], metavar="NAME",
                        help="Select one claim domain. The option can be repeated.")
    parser.add_argument("--output", type=Path, metavar="PATH",
                        help="Write results.json and summary.txt in PATH.")
    parser.add_argument("--fail-on-defect", action="store_true",
                        help="Return a nonzero status when a check confirms a defect.")
    parser.add_argument("-k", dest="pattern", metavar="PATTERN",
                        help="Select claims whose ID, domain, or title contains PATTERN.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Select claims, run them, and return the campaign status."""
    args = _parse_args(argv)
    unknown_ids = sorted(set(args.claim) - {claim.claim_id for claim in CLAIMS})
    if unknown_ids:
        print(f"Unknown claim ID: {', '.join(unknown_ids)}", file=sys.stderr)
        return 2

    claims = select_claims(args.claim, args.domain, args.pattern)
    if not claims:
        print("No physics claims matched the selection.", file=sys.stderr)
        return 2

    if args.list:
        for claim in claims:
            print(f"{claim.claim_id}\t{claim.domain}\t{claim.title}")
        return 0

    commit = git_commit()
    output_directory = args.output or ROOT / "outputs" / "physics_checks" / commit
    outcome = run_campaign(
        claims,
        build_executor_registry(),
        output_directory,
        fail_on_defect=args.fail_on_defect,
        commit=commit,
        environment=environment_record(),
    )
    print(f"Physics check results: {output_directory}")
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
