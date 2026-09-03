# Physics Evidence Closure Plan

## Purpose

This file is the single working plan for the physical verification campaign.
The campaign must give every canonical claim a reproducible result. A result
must be confirmed correct, confirmed defect, not reproduced, or a documented
model limitation. An absent executor is not a valid conclusion.

## Current State

The campaign covers 138 canonical claims from 208 source occurrences. Every
claim resolves: 128 confirmed correct, 4 not reproduced, 6 documented model
limitations, and no inconclusive result. The quality orchestrator owns three
separate suites: architecture, regression, and physics.
`tools/run_quality_checks.py` is the only public suite selector.

`docs/physics_verification_report.md` holds the campaign result, the defects
the campaign found and corrected, the findings that are model-form differences
rather than defects, the documented limits, and every acceptance rule that was
restated.

## Evidence Rules

- Use the CLI when a CSV or report contains the required quantity.
- Use the public API only when the CLI cannot export the required local field,
  harmonic state, marched history, or derivative component.
- State the theory, condition, acceptance rule, command, and measured values.
- Add a regression test before every production correction.
- Preserve the existing test module. Assign each test module to one suite.
- When an acceptance rule names a constant from a fixture the source reports
  did not preserve, restate the rule as a criterion that follows from the
  model, and record the restatement in the report.

## Remaining Work

None of the original claim groups is open. Keep the campaign green:

1. Run `python tools/run_quality_checks.py --suite physics` after any change
   to `zbemt/bemt.py`, to a correction model, or to a claim executor.
2. Regenerate `tests/data/golden_results.json` with
   `python tools/golden_snapshot.py` after a deliberate physics change, and
   read the diff before committing it.
3. Give every new physical behavior a claim in
   `tools/physics_checks/claim_catalog.py`, with its theory statement, its
   acceptance rule, and both reproduction routes.
