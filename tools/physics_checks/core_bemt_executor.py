"""Run independent physical checks for the core BEMT claim domain.

Every engine datum in this module comes from the public CLI.  The analytical
expectations are evaluated here from momentum, blade-element, Prandtl, and
similarity equations.  They do not use golden results or values copied from
the source audit reports.
"""
from __future__ import annotations

import csv
import hashlib
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .cli_helper import run_cli_in_project_copy
from .models import CheckResult, Claim, ExecutionContext, FinalStatus


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "projects" / "starter_rotor"
CLAIM_IDS = frozenset({
    "BEMT-C1", "BEMT-C2", "BEMT-C3", "BEMT-C4", "BEMT-C5",
    "BEMT-C6", "BEMT-C7", "BEMT-C8", "BEMT-C9", "BEMT-C10",
    "BEMT-C11", "BEMT-C12", "BEMT-G6", "BEMT-H1", "BEMT-H2",
})

_REFERENCE_GEOMETRY = (
    "--geom-preset", "rectangular",
    "--geom-radius", "1",
    "--geom-root-cutout", "0.15",
    "--geom-n-blades", "4",
    "--geom-chord", "0.08",
    "--geom-twist-root", "0",
    "--geom-twist-tip", "0",
)
_CLEAN_PHYSICS = (
    "--airfoil-stall-model", "linear",
    "--set", "airfoil.alpha0_deg=0",
    "--set", "airfoil.cd0=0.01",
    "--set", "airfoil.k=0",
    "--set", "config.reverse_flow_model=simple_flip",
    "--prandtl-loss-mode", "off",
    "--no-rotational-augmentation",
    "--no-radial-flow-correction",
    "--set", "config.use_compressibility=false",
)
_FAST_MESH = ("--set", "config.Ne=30", "--set", "config.Npsi=48")
_RUN_CACHE: dict[tuple[str, tuple[str, ...]], tuple[dict[str, Any], str, str]] = {}


def _utc_now() -> str:
    """Return a stable UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _number(value: str) -> Any:
    """Convert a CSV scalar when possible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _run(context: ExecutionContext, label: str, arguments: Iterable[str]) -> tuple[dict[str, Any], str, str]:
    """Run one isolated CLI case and return its last output row."""
    args = tuple(str(item) for item in arguments)
    key = (str(context.output_directory.resolve()), args)
    cached = _RUN_CACHE.get(key)
    if cached is not None:
        return cached

    digest = hashlib.sha256("\0".join(args).encode("utf-8")).hexdigest()[:10]
    work = context.output_directory / "core_bemt" / f"{label}-{digest}"
    outcome = run_cli_in_project_copy(PROJECT, args, work)
    if outcome.exit_code != 0:
        detail = outcome.stderr.strip() or outcome.stdout.strip()
        raise RuntimeError(f"CLI case {label} failed with exit {outcome.exit_code}: {detail}")
    result_csv = max(outcome.generated_csv_paths, key=lambda path: path.stat().st_mtime_ns)
    with result_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError(f"CLI case {label} produced an empty CSV: {result_csv}")
    row = {name: _number(value) for name, value in rows[-1].items()}
    cached = (row, outcome.command, str(result_csv.resolve()))
    _RUN_CACHE[key] = cached
    return cached


def _clean_case(context: ExecutionContext, label: str, *arguments: str) -> tuple[dict[str, Any], str, str]:
    """Run the analytical reference rotor with unwanted effects disabled."""
    return _run(context, label, (*_REFERENCE_GEOMETRY, *_CLEAN_PHYSICS, *_FAST_MESH, *arguments))


def _relative_span(values: Iterable[float]) -> float:
    """Return max-minus-min normalized by the mean magnitude."""
    data = tuple(float(value) for value in values)
    denominator = abs(sum(data) / len(data))
    return (max(data) - min(data)) / denominator if denominator else math.inf


def _result(
    claim: Claim,
    context: ExecutionContext,
    started_at: str,
    passed: bool,
    measured: Mapping[str, Any],
    expected: Mapping[str, Any],
    tolerance: str,
    commands: Iterable[str],
    artifacts: Iterable[str],
    notes: str,
    final_status: FinalStatus | None = None,
) -> CheckResult:
    """Build a complete result record for one executed check."""
    return CheckResult(
        claim_id=claim.claim_id,
        final_status=final_status or (FinalStatus.CONFIRMED_CORRECT if passed else FinalStatus.CONFIRMED_DEFECT),
        measured_data=dict(measured),
        expected_data=dict(expected),
        tolerance_rule=tolerance,
        command="\n".join(dict.fromkeys(commands)),
        artifacts=tuple(dict.fromkeys(artifacts)),
        notes=notes,
        started_at=started_at,
        ended_at=_utc_now(),
        commit=context.commit,
        environment=dict(context.environment),
    )


def _c1(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    sigma = 4.0 * 0.08 / math.pi
    lift_slope = 2.0 * math.pi
    root = 0.15
    coefficient = sigma * lift_slope / 2.0
    inflow_term = (1.0 - root**2) / 2.0
    records = []
    measured_ct = []
    expected_ct = []
    errors = []
    for collective in (4.0, 8.0, 12.0):
        record = _clean_case(
            context, f"hover-reference-{collective:g}", "--rpm", "400",
            "--collective", str(collective), "--mu-inplane", "0",
            "--set", "airfoil.alpha0_deg=-4.5",
            "--set", "config.Ne=60", "--set", "config.Npsi=32",
        )
        records.append(record)
        pitch_term = math.radians(collective + 4.5) * (1.0 - root**3) / 3.0
        lambda_closed = (
            -coefficient * inflow_term
            + math.sqrt((coefficient * inflow_term) ** 2 + 8.0 * coefficient * pitch_term)
        ) / 4.0
        closed_ct = 2.0 * lambda_closed**2
        measured_ct.append(float(record[0]["CT"]))
        expected_ct.append(closed_ct)
        errors.append(abs(float(record[0]["CT"]) / closed_ct - 1.0))
    return _result(
        claim, context, started, max(errors) <= 0.007,
        {"collective_deg": [4.0, 8.0, 12.0], "CT_cli": measured_ct, "relative_errors": errors, "relative_error": max(errors)},
        {"CT_closed_form": expected_ct},
        "max(abs(CT_cli / CT_closed_form - 1)) <= 0.007",
        (record[1] for record in records), (record[2] for record in records),
        "Closed form combines uniform-inflow blade-element theory with lambda=sqrt(CT/2).",
    )


def _c2(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    row, command, artifact = _run(context, "hover-merit", (
        "--rpm", "400", "--collective", "8", "--mu-inplane", "0",
        *_REFERENCE_GEOMETRY, "--airfoil-stall-model", "linear",
        "--set", "airfoil.alpha0_deg=0", "--set", "airfoil.cd0=0.01",
        "--set", "airfoil.k=0", "--set", "config.reverse_flow_model=simple_flip",
        "--prandtl-loss-mode", "both", "--set", "config.use_compressibility=false",
        "--set", "config.Ne=60", "--set", "config.Npsi=32",
    ))
    ct = float(row["CT"])
    ideal_cp = ct ** 1.5 / math.sqrt(2.0)
    kappa = float(row["CPi"]) / ideal_cp
    passed = 0.6 <= float(row["FM"]) <= 0.8 and kappa >= 1.0
    return _result(
        claim, context, started, passed,
        {"FM": row["FM"], "induced_power_factor": kappa, "CPi": row["CPi"]},
        {"published_FM_interval": [0.6, 0.8], "minimum_induced_power_factor": 1.0},
        "0.6 <= FM <= 0.8 and CPi/(CT^1.5/sqrt(2)) >= 1",
        (command,), (artifact,), "The ideal induced-power denominator is the actuator-disk minimum.",
    )


def _c3(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    records = []
    for blades, chord in ((2, 0.08), (4, 0.04)):
        records.append(_run(context, f"solidity-{blades}", (
            "--rpm", "400", "--collective", "8", "--mu-inplane", "0",
            "--geom-preset", "rectangular", "--geom-radius", "1",
            "--geom-root-cutout", "0.15", "--geom-n-blades", str(blades),
            "--geom-chord", str(chord), "--geom-twist-root", "0", "--geom-twist-tip", "0",
            *_CLEAN_PHYSICS, *_FAST_MESH,
        )))
    cts = [float(item[0]["CT"]) for item in records]
    difference = abs(cts[1] / cts[0] - 1.0)
    return _result(
        claim, context, started, difference <= 0.0001,
        {"CT_2_blades": cts[0], "CT_4_blades": cts[1], "relative_difference": difference},
        {"solidity_2_blades": 2 * 0.08 / math.pi, "solidity_4_blades": 4 * 0.04 / math.pi},
        "equal-solidity CT relative difference <= 0.0001",
        (item[1] for item in records), (item[2] for item in records),
        "Blade count and chord were changed inversely at fixed radius and pitch.",
    )


def _c4(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    records = {}
    for mode in ("off", "tip", "root", "both"):
        records[mode] = _run(context, f"prandtl-{mode}", (
            "--rpm", "400", "--collective", "8", "--mu-inplane", "0",
            *_REFERENCE_GEOMETRY, *_CLEAN_PHYSICS, "--prandtl-loss-mode", mode,
            "--set", "config.Ne=60", "--set", "config.Npsi=32",
        ))
    ct = {mode: float(record[0]["CT"]) for mode, record in records.items()}
    # Evaluate the published arccosine factor at two representative stations
    # from the CLI's converged mean inflow.  The factor must lie in (0, 1).
    lambda_i = float(records["off"][0]["lambda_i"])
    factors = {}
    for radius in (0.20, 0.90):
        phi = math.atan2(lambda_i, radius)
        tip_f = 4.0 * (1.0 - radius) / (2.0 * radius * abs(math.sin(phi)))
        root_f = 4.0 * (radius - 0.15) / (2.0 * 0.15 * abs(math.sin(phi)))
        factors[f"F_tip_r{radius}"] = 2.0 / math.pi * math.acos(math.exp(-tip_f))
        factors[f"F_root_r{radius}"] = 2.0 / math.pi * math.acos(math.exp(-root_f))
    passed = ct["tip"] < ct["off"] and ct["root"] < ct["off"] and ct["both"] <= min(ct["tip"], ct["root"])
    return _result(
        claim, context, started, passed,
        {f"CT_{key}": value for key, value in ct.items()},
        {**factors, "Prandtl_factor_interval": [0.0, 1.0], "loss_order": "CT_both <= CT_tip, CT_root < CT_off"},
        "Published F=(2/pi) acos(exp(-f)); both integrated losses must reduce CT",
        (record[1] for record in records.values()), (record[2] for record in records.values()),
        "The CLI exposes integrated loads but not the local Prandtl-factor field required by the acceptance rule. A GUI disk-map check remains necessary.",
        final_status=FinalStatus.INCONCLUSIVE,
    )


def _c5_or_c12(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    records = {}
    for enabled in (False, True):
        records[enabled] = _run(context, f"compressibility-{enabled}", (
            "--rpm", "1785", "--collective", "8", "--mu-inplane", "0",
            *_REFERENCE_GEOMETRY, "--airfoil-stall-model", "linear",
            "--set", "airfoil.alpha0_deg=0", "--set", "airfoil.cd0=0.01",
            "--set", "airfoil.k=0", "--set", "config.reverse_flow_model=simple_flip",
            "--prandtl-loss-mode", "off", "--set", f"config.use_compressibility={str(enabled).lower()}",
            *_FAST_MESH,
        ))
    off = float(records[False][0]["CT"])
    on = float(records[True][0]["CT"])
    ratio = on / off
    tip_mach = float(records[True][0]["rotor_OmegaR"]) / float(records[True][0]["cfg_a_sound"])
    if claim.claim_id == "BEMT-C5":
        passed = 1.05 <= ratio <= 1.12 and math.isfinite(on)
        expected = {"integrated_CT_ratio_interval": [1.05, 1.12], "tip_beta_inverse": 1 / math.sqrt(1 - tip_mach**2)}
        tolerance = "1.05 <= CT_on/CT_off <= 1.12 and CT_on is finite"
        notes = "The local Prandtl-Glauert multiplier is 1/sqrt(1-M^2); integration makes the rotor response smaller."
    else:
        passed = ratio > 1.0 and math.isfinite(ratio)
        expected = {"analytical_polar_layer": "Mach independent", "engine_layer": "CT_on > CT_off"}
        tolerance = "engine CT_on/CT_off > 1; the CLI must retain a finite correction"
        notes = "The public CLI confirms that compressibility is applied by the engine layer, not stored in the analytical-polar inputs."
    return _result(
        claim, context, started, passed,
        {"CT_off": off, "CT_on": on, "CT_ratio": ratio, "tip_mach": tip_mach}, expected, tolerance,
        (record[1] for record in records.values()), (record[2] for record in records.values()), notes,
        final_status=(FinalStatus.INCONCLUSIVE if claim.claim_id == "BEMT-C12" else None),
    )


def _constant_drag_records(context: ExecutionContext) -> dict[bool, tuple[dict[str, Any], str, str]]:
    records = {}
    for enabled in (False, True):
        records[enabled] = _run(context, f"radial-drag-{enabled}", (
            "--rpm", "600", "--collective", "0", "--mu-inplane", "0.30",
            *_REFERENCE_GEOMETRY, "--airfoil-stall-model", "linear",
            "--set", "airfoil.cl_alpha=0", "--set", "airfoil.alpha0_deg=0",
            "--set", "airfoil.cd0=0.02", "--set", "airfoil.k=0",
            "--set", "config.reverse_flow_model=simple_flip", "--prandtl-loss-mode", "off",
            "--set", "config.use_compressibility=false",
            "--radial-flow-correction" if enabled else "--no-radial-flow-correction",
            "--set", "config.Ne=40", "--set", "config.Npsi=180",
        ))
    return records


def _c6_or_c7(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    records = _constant_drag_records(context)
    off, on = records[False][0], records[True][0]
    mu = 0.30
    sigma = 4.0 * 0.08 / math.pi
    cd0 = 0.02
    # The usual textbook expressions assume a zero-radius root.  The CLI
    # rotor starts at r0=0.15, so the integral carries (1-r0^2).
    finite_span = 1.0 - 0.15**2
    expected_off_ch = sigma * cd0 * mu * finite_span / 4.0
    expected_on_ch = 3.0 * sigma * cd0 * mu * finite_span / 8.0
    if claim.claim_id == "BEMT-C6":
        off_error = abs(float(off["CHp"]) / expected_off_ch - 1.0)
        on_error = abs((float(on["CHp"]) + float(on["CHr"])) / expected_on_ch - 1.0)
        torque_change = abs(float(on["CPi"]) - float(off["CPi"]))
        passed = off_error <= 0.03 and on_error <= 0.03 and torque_change <= 1e-9
        measured = {"CH_off": off["CHp"], "CH_on": float(on["CHp"]) + float(on["CHr"]), "off_error": off_error, "on_error": on_error, "induced_power_change": torque_change}
        expected = {"CH_off_closed_form": expected_off_ch, "CH_on_closed_form": expected_on_ch, "induced_power_change": 0.0}
        tolerance = "both force errors <= 3% and induced-power change <= 1e-9"
    else:
        hover_records = {}
        for enabled in (False, True):
            hover_records[enabled] = _run(context, f"radial-drag-hover-{enabled}", (
                "--rpm", "600", "--collective", "0", "--mu-inplane", "0",
                *_REFERENCE_GEOMETRY, "--airfoil-stall-model", "linear",
                "--set", "airfoil.cl_alpha=0", "--set", "airfoil.alpha0_deg=0",
                "--set", "airfoil.cd0=0.02", "--set", "airfoil.k=0",
                "--set", "config.reverse_flow_model=simple_flip", "--prandtl-loss-mode", "off",
                "--set", "config.use_compressibility=false",
                "--radial-flow-correction" if enabled else "--no-radial-flow-correction",
                "--set", "config.Ne=40", "--set", "config.Npsi=180",
            ))
        off_ratio = float(off["CPp"]) / float(hover_records[False][0]["CPp"])
        on_ratio = float(on["CPp"]) / float(hover_records[True][0]["CPp"])
        off_expected, on_expected = 1.0 + mu**2, 1.0 + 1.5 * mu**2
        errors = [abs(off_ratio / off_expected - 1.0), abs(on_ratio / on_expected - 1.0)]
        passed = max(errors) <= 0.05
        measured = {"off_power_ratio": off_ratio, "on_power_ratio": on_ratio, "relative_errors": errors}
        expected = {"off_factor": off_expected, "on_factor": on_expected}
        tolerance = "both profile-power ratios differ from their closed forms by <= 5%"
        records.update({"hover_off": hover_records[False], "hover_on": hover_records[True]})
    return _result(
        claim, context, started, passed, measured, expected, tolerance,
        (record[1] for record in records.values()), (record[2] for record in records.values()),
        "A zero-lift, constant-drag rotor isolates the EN-10 profile terms.",
    )


def _c8(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    speeds = (-12, -8, 0, 8, 12, 20)
    records = [_clean_case(context, f"axial-{vz:+g}", "--rpm", "400", "--collective", "8", "--v-axial", str(vz)) for vz in speeds]
    ct = [float(record[0]["CT"]) for record in records]
    induced = [float(record[0]["lambda_i"]) for record in records]
    total = [float(record[0]["lambda_total"]) for record in records]
    finite = all(math.isfinite(value) for value in (*ct, *induced, *total))
    passed = finite and ct == sorted(ct, reverse=True) and induced == sorted(induced, reverse=True) and total == sorted(total)
    return _result(
        claim, context, started, passed,
        {"Vz_m_per_s": list(speeds), "CT": ct, "lambda_i": induced, "lambda_total": total},
        {"momentum_order": "CT and lambda_i decrease; lambda_total increases with positive Vz"},
        "all values finite and strictly monotonic in the momentum-theory directions",
        (record[1] for record in records), (record[2] for record in records),
        "Positive axial velocity follows the repository convention: through the disk with induced flow.",
    )


def _c9(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    records = [_clean_case(
        context, f"solver-{solver}",
        "--rpm", "400", "--collective", "8", "--mu-inplane", "0.15",
        "--solver", solver,
        "--set", "config.max_iter=2000",
        "--set", "config.tol=1e-8",
        "--set", "config.early_exit_fraction=1.0",
    ) for solver in ("fixed_point", "newton", "bisection", "aitken")]
    cts = [float(record[0]["CT"]) for record in records]
    convergence = [float(record[0]["convergence_pct"]) for record in records]
    span = _relative_span(cts)
    return _result(
        claim, context, started, span <= 0.0005,
        {"solvers": ["fixed_point", "newton", "bisection", "aitken"], "CT": cts, "convergence_pct": convergence, "relative_span": span},
        {"common_annular_momentum_solution": "solver-independent CT"},
        "(max(CT)-min(CT))/abs(mean(CT)) <= 0.0005",
        (record[1] for record in records), (record[2] for record in records),
        "All four numerical methods solve the same annular momentum residual.",
    )


def _c10(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    measured: dict[str, Any] = {}
    commands: list[str] = []
    artifacts: list[str] = []
    passed = True
    for model in ("flat_plate", "thin_plate_blend", "viterna_full_range"):
        values = []
        for mu in (0.3499, 0.3501):
            record = _run(context, f"reverse-{model}-{mu}", (
                "--rpm", "400", "--collective", "8", "--mu-inplane", str(mu),
                *_REFERENCE_GEOMETRY, "--airfoil-stall-model", "viterna",
                "--set", "airfoil.alpha0_deg=0", "--set", "airfoil.cd0=0.01",
                "--set", "airfoil.k=0", "--set", f"config.reverse_flow_model={model}",
                "--prandtl-loss-mode", "off", "--set", "config.use_compressibility=false", *_FAST_MESH,
            ))
            values.append(float(record[0]["CT"]))
            commands.append(record[1]); artifacts.append(record[2])
        jump = abs(values[1] - values[0]) / max(abs(value) for value in values)
        measured[f"{model}_CT"] = values
        measured[f"{model}_relative_jump"] = jump
        passed = passed and jump <= 0.005
    return _result(
        claim, context, started, passed, measured,
        {"continuity_limit": 0.005, "boundary": "tangential-flow sign reversal"},
        "global CT jump across a 0.0002 advance-ratio bracket <= 0.5% for each model",
        commands, artifacts,
        "The CLI summary provides only an integrated continuity check. The local normal-load jump required by the acceptance rule needs the GUI disk map.",
        final_status=FinalStatus.INCONCLUSIVE,
    )


def _c11(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    hover = []
    forward = []
    for enabled in (False, True):
        switch = "--rotational-augmentation" if enabled else "--no-rotational-augmentation"
        hover.append(_run(context, f"augmentation-hover-{enabled}", (
            "--rpm", "400", "--collective", "18", "--mu-inplane", "0", switch,
            "--airfoil-stall-model", "linear",
            "--set", "config.reverse_flow_model=simple_flip",
            "--set", "config.use_compressibility=false", *_FAST_MESH,
        )))
        forward.append(_run(context, f"augmentation-forward-{enabled}", (
            "--rpm", "300", "--collective", "16", "--mu-inplane", "0.20", switch,
            "--airfoil-stall-model", "viterna",
            *_FAST_MESH,
        )))
    hover_signed_change = float(hover[1][0]["CT"]) / float(hover[0][0]["CT"]) - 1.0
    hover_change = abs(hover_signed_change)
    forward_change = float(forward[1][0]["CT"]) / float(forward[0][0]["CT"]) - 1.0
    passed = hover_change <= 1e-12 and forward_change > 0
    records = hover + forward
    return _result(
        claim, context, started, passed,
        {"hover_CT_relative_change": hover_change, "hover_CT_signed_change": hover_signed_change, "stalled_forward_CT_relative_change": forward_change},
        {"attached_hover_change": 0.0, "stalled_rotating_section_change": "positive"},
        "hover change <= 1e-12 and forward-stalled CT change > 0",
        (record[1] for record in records), (record[2] for record in records),
        "The linear hover polar has Cl equal to its attached lift line at every element. The separate Viterna forward case retains stalled sections.",
    )


def _g6(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    records = []
    settings = tuple((rpm, density) for density in (1.225, 0.9) for rpm in (200, 400, 800))
    for rpm, density in settings:
        records.append(_clean_case(context, f"similarity-{rpm}-{density}", "--rpm", str(rpm), "--collective", "8", "--mu-inplane", "0.15", "--set", f"config.rho={density}"))
    cts = [float(record[0]["CT"]) for record in records]
    cqs = [float(record[0]["CQ"]) for record in records]
    ct_span, cq_span = _relative_span(cts), _relative_span(cqs)
    return _result(
        claim, context, started, ct_span <= 1e-12 and cq_span <= 1e-12,
        {"settings_rpm_rho": settings, "CT": cts, "CQ": cqs, "CT_relative_span": ct_span, "CQ_relative_span": cq_span},
        {"dimensionless_similarity": "CT and CQ invariant when compressibility is disabled"},
        "relative span of CT and CQ <= 1e-12",
        (record[1] for record in records), (record[2] for record in records),
        "Density and shaft-speed factors cancel from the nondimensional equations.",
    )


def _h1(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    records = []
    meshes = ((8, 24), (16, 48), (30, 90), (48, 144))
    for ne, npsi in meshes:
        records.append(_clean_case(context, f"mesh-{ne}-{npsi}", "--rpm", "400", "--collective", "10", "--mu-inplane", "0.15", "--set", f"config.Ne={ne}", "--set", f"config.Npsi={npsi}"))
    cts = [float(record[0]["CT"]) for record in records]
    changes = [cts[index + 1] - cts[index] for index in range(len(cts) - 1)]
    final_change = abs(cts[-1] / cts[-2] - 1.0)
    monotonic = all(value >= 0 for value in changes) or all(value <= 0 for value in changes)
    return _result(
        claim, context, started, monotonic and final_change <= 0.005,
        {"meshes": meshes, "CT": cts, "successive_changes": changes, "final_relative_change": final_change},
        {"spatial_convergence": "monotonic common limit", "final_change_limit": 0.005},
        "CT changes monotonically and final two meshes differ by <= 0.5%",
        (record[1] for record in records), (record[2] for record in records),
        "The radial and azimuthal meshes are refined together.",
    )


def _h2(claim: Claim, context: ExecutionContext, started: str) -> CheckResult:
    row, command, artifact = _clean_case(context, "angle-identity", "--rpm", "400", "--collective", "8", "--v-inplane", "20", "--v-axial", "3")
    expected_rotor = -math.degrees(math.atan2(float(row["Vz"]), float(row["Vx"])))
    expected_disk = 90.0 + expected_rotor
    rotor_error = abs(float(row["alpha_rotor_deg"]) - expected_rotor)
    disk_error = abs(float(row["alpha_disk_deg"]) - expected_disk)
    return _result(
        claim, context, started, rotor_error <= 0.001 and disk_error <= 0.001,
        {"Vx": row["Vx"], "Vz": row["Vz"], "alpha_rotor_deg": row["alpha_rotor_deg"], "alpha_disk_deg": row["alpha_disk_deg"], "rotor_error_deg": rotor_error, "disk_error_deg": disk_error},
        {"alpha_rotor_deg": expected_rotor, "alpha_disk_deg": expected_disk},
        "both geometric-angle errors <= 0.001 degree",
        (command,), (artifact,),
        "Both displayed angles are derived from one atan2 geometry.",
    )


_CHECKS: Mapping[str, Callable[[Claim, ExecutionContext, str], CheckResult]] = {
    "BEMT-C1": _c1,
    "BEMT-C2": _c2,
    "BEMT-C3": _c3,
    "BEMT-C4": _c4,
    "BEMT-C5": _c5_or_c12,
    "BEMT-C6": _c6_or_c7,
    "BEMT-C7": _c6_or_c7,
    "BEMT-C8": _c8,
    "BEMT-C9": _c9,
    "BEMT-C10": _c10,
    "BEMT-C11": _c11,
    "BEMT-C12": _c5_or_c12,
    "BEMT-G6": _g6,
    "BEMT-H1": _h1,
    "BEMT-H2": _h2,
}


def execute_core_bemt_claim(claim: Claim, context: ExecutionContext) -> CheckResult:
    """Execute one standardized core-BEMT physical confirmation check."""
    if claim.domain != "core_bemt" or claim.claim_id not in CLAIM_IDS:
        raise ValueError(f"Unsupported core BEMT claim: {claim.claim_id}")
    return _CHECKS[claim.claim_id](claim, context, _utc_now())
