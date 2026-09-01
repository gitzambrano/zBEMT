# Physics Evidence Closure Design

## Goal

Correct each confirmed physical defect. Classify every inconclusive physical claim with reproducible evidence.

## Scope

The work first corrects the coupled flapping and inflow convergence defect. The work then investigates the articulated forward-flight damping result. The work finally completes the evidence for each remaining inconclusive claim.

## Design

Each correction begins with a regression test that reproduces the physical failure. The test must fail before the production change. The solver change must satisfy the stated numerical or physical acceptance rule.

Each inconclusive claim receives an executor or a documented model limit. An executor runs a public CLI case when exported results are sufficient. It uses the public API only for an internal quantity that the CLI does not export. The executor records the theoretical reference, numerical measurements, command, and artifacts.

The campaign may classify a claim as confirmed correct, confirmed defect, not reproduced, or out-of-scope limitation. It must not leave a claim inconclusive because an executor is absent.

## Constraints

- `docs/software_requirements.md` is binding.
- Use English for code, tests, reports, and user-visible strings.
- Preserve each existing test. Assign every test module to exactly one suite.
- Run the full test runner through `python tests/run_all_tests.py`.
- Use a failing test before each production correction.
