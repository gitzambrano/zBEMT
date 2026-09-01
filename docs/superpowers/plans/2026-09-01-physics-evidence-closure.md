# Physics Evidence Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the confirmed physical defects and classify every physics claim with executable evidence.

**Architecture:** Regression tests protect solver corrections. Physics executors create reproducible CLI or public-API evidence for each claim. The unified quality runner executes architecture, regression, and physics checks without duplicating ownership.

**Tech Stack:** Python 3.11, NumPy, unittest, pytest, zBEMT CLI and public API.

**Spec:** `docs/superpowers/specs/2026-09-01-physics-closure-design.md`

## Global Constraints

- `docs/software_requirements.md` governs behavior and requirement links.
- Tests and reports use English.
- Run the full suite with `python tests/run_all_tests.py`.
- Every production correction starts with a regression test that fails before the correction.

---

### Task 1: Coupled flap and inflow convergence

**Files:**
- Modify: `tests/regression/test_flapping.py`
- Modify: `zbemt/bemt.py`
- Modify: `tools/physics_checks/flapping_executor.py`

**Interfaces:**
- Consumes: `solve_bemt_flapping(...)` and `maps["flap_outer_converged"]`.
- Produces: a converged forward-flight map at advance ratios 0.20 and 0.25.

- [ ] **Step 1: Write a failing test**

```python
for advance_ratio in (0.20, 0.25):
    result = api.run_case(project, FlightCondition(mu_x=advance_ratio, ...))
    self.assertTrue(result.summary["flap_outer_converged"])
```

- [ ] **Step 2: Run the test to verify failure**

Run: `python -m pytest tests/regression/test_flapping.py::TestForwardFlapConvergence -v`

Expected: failure because the coupled iteration stops above the declared tolerance.

- [ ] **Step 3: Implement the minimal convergence correction**

```python
# Update the coupled-state iteration only after measuring the true
# coefficient residual. Stop only when every flap coefficient meets tolerance.
```

- [ ] **Step 4: Run the focused regression and physical executor**

Run: `python -m pytest tests/regression/test_flapping.py tests/physics/test_physics_flapping_executor.py -q`

Expected: PASS.

### Task 2: Articulated forward-flight damping

**Files:**
- Modify: `tests/regression/test_derivatives.py`
- Modify: `tools/physics_checks/flapping_executor.py`
- Modify: `zbemt/derivatives.py` or `zbemt/bemt.py` only if the independent comparison finds a defect.

**Interfaces:**
- Consumes: public derivative calculation and converged flap results.
- Produces: a physically defined comparison between articulated and rigid damping.

- [ ] **Step 1: Write a failing acceptance test or a controlled counterexample**

```python
articulated = calculate_derivatives(project_with_flap, condition)
rigid = calculate_derivatives(project_with_rigid_hub, condition)
self.assertLessEqual(abs(articulated["Mx_q"]), abs(rigid["Mx_q"]))
```

- [ ] **Step 2: Run the test and record the physical quantity**

Run: `python -m pytest tests/regression/test_derivatives.py -k damping -v`

Expected: fail only if the model contradicts the accepted reference convention.

- [ ] **Step 3: Correct the model or revise the claim with an explicit reference limit**

```python
# Retain the derivative sign convention. Change only the term identified by
# the independent rigid-versus-articulated comparison.
```

- [ ] **Step 4: Run focused regression and physics checks**

Run: `python -m pytest tests/regression/test_derivatives.py tests/physics/test_physics_flapping_executor.py -q`

Expected: PASS.

### Task 3: Inconclusive claim closure

**Files:**
- Modify: `tools/physics_checks/registry.py`
- Modify: `tools/physics_checks/claim_catalog.py`
- Modify: `tools/physics_checks/*_executor.py`
- Modify: `tests/physics/test_physics_check_harness.py`

**Interfaces:**
- Consumes: each canonical `Claim` with an executor name, acceptance rule, CLI route, and GUI route.
- Produces: a final non-inconclusive status for every claim unless the catalog explicitly documents a model limit.

- [ ] **Step 1: Add a failing completeness test**

```python
outcome = run_campaign(CLAIMS, build_executor_registry(), output, ...)
self.assertFalse(any(result.final_status is FinalStatus.INCONCLUSIVE
                     for result in outcome.results))
```

- [ ] **Step 2: Run the harness test to verify failure**

Run: `python -m pytest tests/physics/test_physics_check_harness.py -k inconclusive -v`

Expected: failure listing the unresolved claim identifiers.

- [ ] **Step 3: Add executors by physics domain**

```python
registry.register("stall_delay_executor", execute_stall_delay_claim)
registry.register("repository_quality_executor", execute_repository_quality_claim)
```

- [ ] **Step 4: Run the full evidence campaign**

Run: `python tools/run_quality_checks.py --suite physics`

Expected: no `INCONCLUSIVE` status and no executor failure.

### Task 4: Report and final verification

**Files:**
- Modify: `docs/physics_verification_report.md`
- Modify: `to-do.md`

- [ ] **Step 1: Update the report with measured evidence and remaining model limits**

```markdown
## Final campaign result

The campaign contains no unresolved executable claim.
```

- [ ] **Step 2: Run every quality suite**

Run: `python tools/run_quality_checks.py --suite architecture`, `python tools/run_quality_checks.py --suite regression`, and `python tools/run_quality_checks.py --suite physics`

Expected: all commands exit with code 0.

- [ ] **Step 3: Review the diff and commit the verified work**

Run: `git diff --check` and `git status --short`

Expected: the staged change excludes unrelated user files.
