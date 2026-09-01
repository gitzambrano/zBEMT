# Physics Evidence Closure Plan

## Purpose

This file is the single working plan for the physical verification campaign.
The campaign must give every canonical claim a reproducible result. A result
must be confirmed correct, confirmed defect, not reproduced, or a documented
model limitation. An absent executor is not a valid conclusion.

## Current State

The campaign contains 138 canonical claims from 208 source occurrences. The
quality orchestrator owns three separate suites: architecture, regression, and
physics. `tools/run_quality_checks.py` is the only public suite selector.

Two earlier findings are closed:

- `DERIV-E2`: The flapping solver now uses an internal inflow tolerance of
  `1e-8` when it must meet the declared outer flap tolerance. The reference
  cases at advance ratios 0.20 and 0.25 converge.
- `DERIV-A3`: The evidence now compares aerodynamic pitch damping before the
  structural moment of the offset hinge is added. The aerodynamic damping is
  lower than the rigid result. The reported total equals the aerodynamic and
  structural terms.

## Evidence Rules

- Use the CLI when a CSV or report contains the required quantity.
- Use the public API only when the CLI cannot export the required local field,
  harmonic state, or derivative component.
- State the theory, condition, acceptance rule, command, and measured values.
- Add a regression test before every production correction.
- Preserve the existing test module. Assign each test module to one suite.

## Remaining Work

### 1. Complete existing partial executors

First close claims that already have an executor but return `INCONCLUSIVE`:

- Core BEMT: `BEMT-C4`, `BEMT-C10`, `BEMT-C12`.
- Flapping and derivatives: `FLAP-E9`, `DERIV-P7`.
- Dynamic stall: `DS-A2` through `DS-A6`, `DS-A9` through `DS-A13`,
  `DS-A17`, `DS-A18`, `DS-D3-HYSTERESIS-DIRECTION`, and `DS-H4`.
- Pitt-Peters: `PP-B2` through `PP-B8`, `PP-G7`, `PP-MASS-FLOW`,
  `PP-P5-ASYMMETRY`, and `PP-STEADY-MARCH-AUDIT`.
- Propeller: `PROP-G8`.

### 2. Implement missing evidence executors

Create focused executors for these claim groups:

- Stall delay: `STALL-DELAY-RATIO`.
- Input validation: `PROP-K8`.
- Model effects: `MODEL-G2`, `PROP-K3`.
- Reporting: `DS-MANEUVER-REPORTING`, `PP-B9`, `REPO-PITT-WARNING`.
- Extreme conditions: `EXT-D4`.

### 3. Record model limits explicitly

Evaluate and document these limits. Use `OUT_OF_SCOPE_LIMITATION` only when
the mathematical model cannot answer the claim without a new product model:

- `DERIV-A5`, `LAG-CORIOLIS-LIMITATION`, `PP-B10`,
  `PP-LINEAR-LIMITATION`, `PP-PHASE-CONVENTION`, and `PROP-N1`.

### 4. Close and verify

After each domain:

1. Run the focused physics executor test.
2. Run the relevant regression test when production code changed.
3. Run `python tools/run_quality_checks.py --suite physics`.
4. Update `docs/physics_verification_report.md` with the new evidence.
5. Commit the domain-sized change on `main` and push it.

At final closure, run the architecture, regression, and physics suites through
the quality orchestrator. Then update the consolidated report with final
counts and any documented model limits.
