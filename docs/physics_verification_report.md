# Physics Verification Report

## Scope

This report consolidates the five previous physics-audit reports. The source
inventory contains 208 report occurrences mapped to 138 canonical claims in
`tools/physics_checks/ledger.py`. The claim catalog gives each claim a theory
statement, acceptance rule, CLI route, GUI route, and evidence grade.

Source reports consolidated here:

- Propeller mode versus literature.
- Stability derivatives and flapping.
- Dynamic stall and Pitt-Peters time marching.
- Flapping, lead-lag, Pitt-Peters, derivatives, and model effects audit.
- Dynamic stall and Pitt-Peters review baseline.

## Method

The quality orchestrator separates architecture, regression, and physics
checks. Physics checks execute isolated project copies through the CLI where a
result CSV is sufficient. They use the same public API as the GUI only when a
claim requires a local map, polar, or derivative matrix not exported by the
CLI. Every claim also has a written GUI reproduction route in the catalog.

The theory checks use actuator-disk momentum, blade-element identities,
Prandtl loss, similarity, linear flap theory, and finite-state inflow limits.
The external references include the ECN report on rotational augmentation
<https://publications.ecn.nl/ECN-RX--93-028>, the Pitt-Peters dynamic-inflow
formulation <https://ntrs.nasa.gov/citations/19880017772>, and NASA oblique
propeller measurements <https://ntrs.nasa.gov/search.jsp?R=19930094852>.

Run the complete evidence campaign with:

```text
python tools/run_quality_checks.py --suite physics
```

The latest complete campaign is in
`outputs/physics_checks/all-after-integration/results.json`.

## Campaign result

The complete campaign executed 138 claims with no executor failure.

| Status | Claims |
| --- | ---: |
| Confirmed correct | 87 |
| Confirmed defect | 2 |
| Not reproduced | 3 |
| Out-of-scope limitation | 1 |
| Inconclusive | 45 |

An inconclusive result is not a pass. It means that the source report did not
preserve the exact polar, maneuver, local field, or experimental datum needed
to apply its acceptance rule. The standardized CLI and GUI routes remain in
the catalog for completing those checks.

## Confirmed defects still open

### DERIV-E2: forward flap-loop convergence

At advance ratios 0.20 and 0.25, the coupled inflow and flap fixed-point loop
does not reach its declared `1e-4 deg` tolerance in 30 iterations. The
measured residuals are `2.939e-3 deg` and `2.631e-4 deg`. The result is now
explicitly marked with `flap_outer_converged=false`, the tolerance is exported,
and result validation warns that the case must not support stability derivatives
or trim. The numerical convergence mechanism remains an open correction.

### DERIV-A3: articulated forward damping

At advance ratio 0.10, the articulated model converges but gives longitudinal
pitch damping magnitude slightly larger than the rigid result. The check
measured `|dMx/dq| = 25.336` for the articulated rotor and `24.884` for the
rigid rotor. This conflicts with the stated articulated-rotor damping trend and
needs a focused model review after the forward flap-loop correction.

## Confirmed and corrected defects

- Bisection now brackets from the physical initial estimate. It no longer
  selects a distant mathematical root in nonlinear inflow residuals.
- Non-positive atmospheric values and invalid mesh dimensions now fail
  validation before a solve.
- A rigid flap model with enabled lead-lag now fails validation instead of
  silently dropping lead-lag motion.
- The rigid path now publishes zero flap-motion map keys without changing
  legacy scalar results.
- Bisection trim records target, control, residual, and convergence status on
  both success and iteration exhaustion.
- Three-degree-of-freedom trim no longer raises the `target_key` name error.

## Findings not reproduced as implementation defects

- The reported Pitt-Peters versus local-Glauert axial difference is a
  model-form difference. Pitt-Peters uses a uniform finite-state mean inflow;
  local Glauert solves annular inflow. Zero skew removes harmonic states but
  does not make those parameterizations identical for a nonuniform blade.
- The reported dynamic-stall frequency versus time-march difference at high
  advance ratio is expected once the dominant-harmonic assumption fails. The
  two methods agree within 1% in their low-advance validity range.
- The reported hover rate-matrix invariance defect used the wrong direct-axis
  pairing. The checked physical pairs are `dMx/dq` and `dMy/dp`; the current
  matrix satisfies the rotational invariance test.

## Suite ownership

- `tests/architecture/` contains requirements, documentation, interface, and
  dependency-boundary tests.
- `tests/regression/` contains behavior, bug, snapshot, and GUI-workflow
  regression tests.
- `tests/physics/` contains harness and executor tests for the external
  physics evidence campaign.

Shared fixtures, data, and the one-process-per-file runner stay directly under
`tests/`. `tests/suite_manifest.json` assigns every test module to exactly one
suite. `tools/run_quality_checks.py` is the single orchestrator.
