"""Stability and control derivatives by central finite differences
(SC-14, Item 4).

This module owns the PERTURBATION LOGIC and nothing else: it receives a
project and a `DerivativeRequest`, builds one perturbed
`FlightCondition` per solve, and delegates every solve to
``studies.run_single_case`` (reached through the callable the caller
passes in, so the layering AR-1/AR-2 holds and tests can stub it). No
Qt, no disk.

Every derivative is a central difference

    dF/dx = (F(x0 + h) - F(x0 - h)) / (2*h)

with a PER-VARIABLE step in physical units. Repeating at half the step
gives the Richardson error estimate: the relative difference between
the two estimates, which flags solver noise (the practical failure mode)
rather than truncation.
"""
from __future__ import annotations

import math
from dataclasses import replace as dc_replace

import numpy as np

from .bemt import SolveCancelled
from .models import DerivativeRequest, FlightCondition, Project

#: Default finite-difference steps, in each variable's own unit. Stated,
#: not guessed: a central difference trades truncation (order h^2)
#: against round-off (eps/h), and the balance differs per quantity.
_DEFAULT_STEPS = {
    "u": 0.5,            # m/s   (longitudinal speed)
    "v": 0.5,            # m/s   (lateral speed)
    "w": 0.5,            # m/s   (axial speed)
    "p": 0.02,           # rad/s (roll rate)
    "q": 0.02,           # rad/s (pitch rate)
    "theta_0": 0.1,      # deg   (collective)
    "theta_1c": 0.1,     # deg   (cosine cyclic)
    "theta_1s": 0.1,     # deg   (sine cyclic)
}

#: Omega's step is RELATIVE to the trim rpm (plan: 0.5 percent).
_OMEGA_STEP_FRACTION = 0.005

#: Variables this engine understands, split the way the request splits
#: them (states vs controls is presentation only; both perturb the same
#: way here).
_KNOWN_VARIABLES = tuple(_DEFAULT_STEPS) + ("Omega",)

#: Force outputs divided by rho*A*(Omega*R)^2 when reported
#: non-dimensionally; moments by rho*A*(Omega*R)^2*R.
_FORCE_OUTPUTS = ("Thrust", "H", "Y")
_MOMENT_OUTPUTS = ("Mx_total", "My_total", "Torque")


class DerivativeOutcome:
    """Result of one derivative study (in memory only)."""

    def __init__(self):
        self.matrix = {}          # {(output, variable): dimensional}
        self.matrix_nondim = {}   # {(output, variable): non-dimensional}
        self.step_used = {}       # {variable: h}
        self.step_error = {}      # {(output, variable): relative diff}
        self.trim_state = {}      # controls + loads at the trim point
        self.n_solves = 0
        self.message = ""


def _validate_request(request: DerivativeRequest) -> None:
    for variable in (*request.states, *request.controls):
        if variable not in _KNOWN_VARIABLES:
            raise ValueError(
                f"compute_derivatives: unknown variable {variable!r}; "
                f"known states {_KNOWN_VARIABLES[:6]} and controls "
                f"{_KNOWN_VARIABLES[6:]}.")
        step = float(request.steps.get(variable,
                                        _DEFAULT_STEPS.get(variable, 0.0)))
        if not math.isfinite(step) or step <= 0.0:
            raise ValueError(
                f"compute_derivatives: variable {variable!r} needs a "
                f"finite POSITIVE step (got {step!r}).")


def _condition_at(project: Project, request: DerivativeRequest,
                  base: FlightCondition, variable: str, delta: float,
                  omega_r: float, trim_controls: dict) -> FlightCondition:
    """One perturbed condition: the trim state plus `delta` of ONE
    variable, mapped onto the fields the engine reads."""
    overrides: dict = {}
    if variable == "u":
        overrides["mu_x"] = (
            float(base.mu_x) + (delta + float(trim_controls.get("u", 0.0)))
            / omega_r)
    elif variable == "v":
        # Lateral speed enters as an in-plane direction rotated off the
        # x axis: total in-plane speed and its sideslip angle.
        u_total = float(trim_controls.get("u", float(base.mu_x) * omega_r))
        v_total = delta
        speed = math.hypot(u_total, v_total)
        overrides["mu_x"] = speed / omega_r
        overrides["sideslip_deg"] = math.degrees(
            math.atan2(v_total, u_total)) if speed > 1e-12 else 0.0
    elif variable == "w":
        overrides["Vz"] = float(base.Vz) + delta
    elif variable == "p":
        overrides["p_rate_deg_s"] = math.degrees(delta)
    elif variable == "q":
        overrides["q_rate_deg_s"] = math.degrees(delta)
    elif variable == "Omega":
        overrides["rpm"] = float(base.rpm) + delta
    elif variable == "theta_0":
        overrides["collective_deg"] = (
            float(trim_controls.get("collective_deg",
                                     base.collective_deg)) + delta)
    elif variable == "theta_1c":
        overrides["cyclic_c_deg"] = (
            float(trim_controls.get("cyclic_c_deg", 0.0)) + delta)
    elif variable == "theta_1s":
        overrides["cyclic_s_deg"] = (
            float(trim_controls.get("cyclic_s_deg", 0.0)) + delta)
    return dc_replace(base, **overrides)


def compute_derivatives(project: Project, request: DerivativeRequest, *,
                        run_case=None, on_progress=None, should_cancel=None):
    """Runs one derivative study and returns a `DerivativeOutcome`.

    ``run_case(project, condition) -> summary-dict-like`` replaces the
    solver in tests (layering AR-2); the default goes through
    ``studies.run_single_case``. Progress fires after every solve with
    ``(solves done, solves total)``; cancellation raises
    ``SolveCancelled`` between solves."""
    from . import studies   # lazy: keeps module import side-effect free

    _validate_request(request)
    solve = run_case or (lambda proj, cond: studies.run_single_case(
        proj, cond, should_cancel=should_cancel).summary)
    condition = request.condition or (
        project.saved_cases[0] if project.saved_cases else None)
    if condition is None:
        raise ValueError("compute_derivatives: the request has no "
                          "condition and the project stores no saved case.")
    if not condition.rpm:
        raise ValueError("compute_derivatives: the study's condition "
                          "carries no RPM.")

    variables = [*request.states, *request.controls]
    outputs = list(request.outputs) or ["Thrust", "H", "Y",
                                         "Mx_total", "My_total", "Torque"]
    outcome = DerivativeOutcome()
    rpm = float(condition.rpm)
    omega_r = rpm * 2.0 * math.pi / 60.0 * project.geometry.radius_m

    # --- 1) Trim ----------------------------------------------------------
    trim_controls: dict = {}
    working = condition
    if request.trim != "none":
        if request.trim == "thrust":
            target = request.trim_target_thrust
            if target is None:
                base_summary = solve(project, condition)
                outcome.n_solves += 1
                target = float(base_summary.get("Thrust", 0.0))
            trimmed = studies.run_case_trimmed(
                project, condition, trim_mode="solve_collective",
                target_kind="thrust", target_value=target,
                should_cancel=should_cancel)
            working = dc_replace(
                condition,
                collective_deg=float(trimmed.summary.get(
                    "collective_deg", condition.collective_deg)))
        elif request.trim == "cyclic_flapback":
            trimmed = studies.run_case_trimmed(
                project, condition, trim_mode="solve_cyclic_flapback",
                should_cancel=should_cancel)
            working = dc_replace(
                condition,
                cyclic_c_deg=float(trimmed.summary.get(
                    "cyclic_c_deg", condition.cyclic_c_deg)),
                cyclic_s_deg=float(trimmed.summary.get(
                    "cyclic_s_deg", condition.cyclic_s_deg)))
        else:
            raise ValueError(
                f"compute_derivatives: trim must be 'none', 'thrust' or "
                f"'cyclic_flapback' (got {request.trim!r}).")

    # --- 2) The trim point itself -----------------------------------------
    base_summary = dict(solve(project, working))
    outcome.n_solves += 1
    outcome.trim_state = {
        "collective_deg": float(working.collective_deg),
        "cyclic_c_deg": float(working.cyclic_c_deg),
        "cyclic_s_deg": float(working.cyclic_s_deg),
        "mu_x": float(working.mu_x),
        "Vz": float(working.Vz),
        "rpm": float(working.rpm),
        "Thrust": float(base_summary.get("Thrust", float("nan"))),
        "Torque": float(base_summary.get("Torque", float("nan"))),
        "trim": request.trim,
    }

    qA = (float(project.config.get("rho", 1.225))
           * math.pi * project.geometry.radius_m ** 2 * omega_r ** 2)

    def loads_of(summary: dict) -> dict:
        values = {}
        for key in outputs:
            if key in summary:
                values[key] = float(summary[key])
            elif key == "H" and "CH" in summary:
                values[key] = float(summary["CH"]) * qA
            elif key == "Y" and "CY" in summary:
                values[key] = float(summary["CY"]) * qA
            else:
                values[key] = float("nan")
        return values

    base_loads = loads_of(base_summary)

    # --- 3)+4) Central differences, optional half-step check --------------
    total = sum(2 if not request.richardson_check else 4
                 for _ in variables)
    done = 0
    for variable in variables:
        if should_cancel is not None and should_cancel():
            raise SolveCancelled()
        step = float(request.steps.get(variable,
                                        _DEFAULT_STEPS.get(
                                            variable,
                                            _OMEGA_STEP_FRACTION * rpm
                                            if variable == "Omega" else 0.0)))
        if variable == "Omega":
            step = float(request.steps.get("Omega",
                                            _OMEGA_STEP_FRACTION * rpm))
        outcome.step_used[variable] = step

        def perturbed(delta: float) -> dict:
            nonlocal done
            cond = _condition_at(project, request, working, variable,
                                  delta, omega_r, trim_controls)
            summary = dict(solve(project, cond))
            done += 1
            outcome.n_solves += 1
            if on_progress is not None:
                on_progress(done, total)
            return loads_of(summary)

        plus = perturbed(+step)
        minus = perturbed(-step)
        derivative = {key: (plus[key] - minus[key]) / (2.0 * step)
                       for key in outputs}
        if request.richardson_check:
            plus_h = perturbed(+step / 2.0)
            minus_h = perturbed(-step / 2.0)
            derivative_half = {key: (plus_h[key] - minus_h[key]) / step
                                for key in outputs}
            for key in outputs:
                scale = max(abs(derivative[key]), 1e-12)
                outcome.step_error[(key, variable)] = (
                    abs(derivative[key] - derivative_half[key]) / scale)
        for key in outputs:
            outcome.matrix[(key, variable)] = derivative[key]
            # Non-dimensional form: forces by rho*A*(Omega*R)^2, moments
            # by rho*A*(Omega*R)^2*R, then the VARIABLE by its scale --
            # linear speeds by Omega*R, angular rates by Omega.
            var_scale = (omega_r if variable in ("u", "v", "w")
                          else omega_r if variable == "Omega"
                          else 1.0)
            out_scale = (qA if key in _FORCE_OUTPUTS
                          else qA * project.geometry.radius_m)
            outcome.matrix_nondim[(key, variable)] = (
                derivative[key] * var_scale / out_scale)

    outcome.message = (f"{len(variables)} variable(s), "
                        f"{outcome.n_solves} solves, trim "
                        f"{request.trim!r}")
    return outcome
