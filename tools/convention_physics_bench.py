"""Independent convention and physics bench for zBEMT.

This is deliberately separate from the normal regression baselines.  The
checks are mostly contract and metamorphic checks: the same physical state
written through different interfaces must reach the same engine state, and
changes that have an exact dimensional scaling must preserve it.

Run from the repository root::

    python tools/convention_physics_bench.py
    python tools/convention_physics_bench.py --json outputs/convention_bench.json
    python tools/convention_physics_bench.py --strict

``--strict`` returns a non-zero exit code when a FAIL is found.  Without it,
the bench is diagnostic and always writes/prints the full ledger.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Callable

import numpy as np

from zbemt import api, geometry, nomenclature, studies
from zbemt.bemt import BEMTConfig, _INFLOW_FIELD_MODELS, resolve_advance_velocity
from zbemt.models import AirfoilDef, FlightCondition, Project, default_project_paths


class Bench:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def record(self, group: str, name: str, status: str, detail: str,
               measured=None, expected=None) -> None:
        self.rows.append({
            "group": group,
            "name": name,
            "status": status,
            "detail": detail,
            "measured": measured,
            "expected": expected,
        })

    def check(self, group: str, name: str, condition: bool, detail: str,
              measured=None, expected=None) -> None:
        self.record(group, name, "PASS" if condition else "FAIL", detail,
                    measured, expected)

    def close(self, group: str, name: str, actual: float, expected: float,
              *, rtol: float = 1e-8, atol: float = 1e-10,
              detail: str = "") -> None:
        ok = bool(np.isclose(actual, expected, rtol=rtol, atol=atol))
        msg = detail or f"actual={actual:.12g}, expected={expected:.12g}"
        self.check(group, name, ok, msg, float(actual), float(expected))

    def warn(self, group: str, name: str, detail: str,
             measured=None, expected=None) -> None:
        self.record(group, name, "WARN", detail, measured, expected)

    def run(self, group: str, name: str, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as exc:  # bench must report the failing route, not abort the ledger
            self.record(group, name, "FAIL",
                        f"check raised {type(exc).__name__}: {exc}")

    def summary(self) -> dict:
        counts = {status: sum(r["status"] == status for r in self.rows)
                  for status in ("PASS", "WARN", "FAIL")}
        return {"counts": counts, "checks": self.rows}


def _omega_r(rpm: float, radius_m: float) -> float:
    return 2.0 * math.pi * rpm / 60.0 * radius_m


def _base_project(**config_overrides) -> Project:
    """Small, smooth, Reynolds-independent case for exact scaling checks."""
    geom = geometry.generate_tapered(
        root_cutout_norm=0.20,
        radius_m=1.0,
        root_chord_norm=0.10,
        tip_chord_norm=0.06,
        twist_root_deg=8.0,
        twist_tip_deg=2.0,
        n_blades=3,
        n_stations=14,
        airfoil_name="bench-airfoil",
    )
    airfoil = AirfoilDef(
        name="bench-airfoil",
        source="analytical",
        stall_model="linear",
        alpha0_deg=0.0,
        cl_alpha=2.0 * math.pi,
        cd0=0.012,
        k=0.008,
        extend_full_range=False,
    )
    cfg = asdict(BEMTConfig(
        Ne=18,
        Npsi=36,
        solver="newton",
        max_iter=120,
        tol=1e-8,
        inflow_field_model="glauert_local",
        prandtl_loss_mode="off",
        use_compressibility=False,
        reverse_flow_model="simple_flip",
        use_rotational_augmentation=False,
        use_radial_flow_correction=False,
    ))
    cfg.update(config_overrides)
    return Project(name="convention-physics-bench", geometry=geom,
                   airfoil=airfoil, config=cfg)


def _run(project: Project, *, mu_x: float = 0.08, Vz: float = 0.0,
         collective_deg: float = 6.0, rpm: float = 900.0,
         Vy: float = 0.0, sideslip_deg: float = 0.0):
    condition = FlightCondition(
        name="bench",
        mu_x=float(mu_x),
        Vz=float(Vz),
        collective_deg=float(collective_deg),
        rpm=float(rpm),
        Vy=float(Vy),
        sideslip_deg=float(sideslip_deg),
    )
    return api.run_case(project, condition)


def _normalized_angle(angle_deg: float) -> float:
    value = (float(angle_deg) + 180.0) % 360.0 - 180.0
    return 180.0 if value == -180.0 else value


def check_convention_core(bench: Bench) -> None:
    group = "convention-core"
    project = _base_project()
    rotor = studies._to_rotor(project.geometry, collective_deg=0.0, rpm=900.0)
    cfg = studies._build_config(project.config, project.airfoil)

    mu = 0.173
    Vz = -12.0
    a_mu, a_vz, a_meta = resolve_advance_velocity(rotor, cfg, mu_x=mu, Vz=Vz)
    b_mu, b_vz, _ = resolve_advance_velocity(rotor, cfg,
                                              J_x=math.pi * mu, Vz=Vz)
    c_mu, c_vz, _ = resolve_advance_velocity(
        rotor, cfg, mu_x=mu, mu_z=Vz / rotor.OmegaR)
    d_mu, d_vz, _ = resolve_advance_velocity(
        rotor, cfg, mu_x=mu, J_z=math.pi * Vz / rotor.OmegaR)
    bench.close(group, "J_inplane == pi*mu_inplane", b_mu, a_mu)
    bench.close(group, "mu_z representation preserves Vz", c_vz, a_vz)
    bench.close(group, "J_z representation preserves Vz", d_vz, a_vz)
    bench.close(group, "equivalent spellings preserve mu_x", d_mu, a_mu)

    alpha = 7.0
    _, alpha_vz, alpha_meta = resolve_advance_velocity(
        rotor, cfg, mu_x=mu, alpha_rotor_deg=alpha)
    bench.check(
        group,
        "positive alpha_rotor means negative axial free stream",
        alpha_vz < 0.0,
        "With z positive along the shaft, positive rotor angle of attack is flow "
        "arriving from below, hence Vz < 0.",
        alpha_vz,
        "< 0",
    )
    bench.close(group, "alpha_rotor round-trip", alpha_meta["alpha_rotor_deg"], alpha,
                atol=1e-9)

    alpha_disk = 11.0
    pos_mu, _, _ = resolve_advance_velocity(
        rotor, cfg, alpha_disk_deg=alpha_disk, Vz=40.0)
    neg_mu, _, neg_meta = resolve_advance_velocity(
        rotor, cfg, alpha_disk_deg=alpha_disk, Vz=-40.0)
    bench.close(
        group,
        "alpha_disk keeps cross-flow side when axial component changes sign",
        neg_mu,
        pos_mu,
        atol=1e-12,
        detail="The angle has its own sign; the cross-flow magnitude is built from |V_axial|.",
    )

    relation = _normalized_angle(90.0 + neg_meta["alpha_rotor_deg"])
    bench.close(
        group,
        "reported angle relation uses alpha_disk = 90 + alpha_rotor (mod 360)",
        neg_meta["alpha_disk_deg"], relation, atol=1e-9,
    )

    tooltip = nomenclature.description_html("alpha_rotor_deg", False)
    has_minus = ("-atan2" in tooltip or "&minus;atan2" in tooltip
                 or "−atan2" in tooltip)
    bench.check(
        group,
        "alpha_rotor help uses the engine sign convention",
        has_minus,
        "The user-facing definition must show alpha_rotor = -atan2(Vz,Vx), "
        "matching resolve_advance_velocity and aggregate_results.",
        tooltip,
        "-atan2(Vz,Vx)",
    )


def check_cli_contract(bench: Bench) -> None:
    group = "cli-contract"
    from zbemt.cli import _build_parser

    parser = _build_parser()
    inflow_action = next(action for action in parser._actions
                         if getattr(action, "dest", None) == "inflow")
    cli_choices = set(inflow_action.choices or ())
    engine_choices = set(_INFLOW_FIELD_MODELS)

    missing = sorted(engine_choices - cli_choices)
    extra = sorted(cli_choices - engine_choices)
    bench.check(
        group,
        "dedicated --inflow choices match engine model names",
        not missing and not extra,
        f"missing={missing}; extra={extra}. A legacy alias may be supported, "
        "but it must not silently masquerade as a distinct physical model.",
        sorted(cli_choices),
        sorted(engine_choices),
    )

    required = {"coleman_feingold_global"}
    bench.check(
        group,
        "CLI exposes Coleman-Feingold global inflow directly",
        required <= cli_choices,
        "The GUI/engine expose this model; a dedicated CLI selector should not omit it.",
        sorted(cli_choices),
        sorted(required),
    )

    bench.check(
        group,
        "CLI does not advertise nonexistent Glauert-global physics",
        "glauert_global" not in cli_choices,
        "studies._migrate_config_dict maps glauert_global to glauert_local; "
        "advertising it as a choice makes two CLI names run one model.",
        "glauert_global" in cli_choices,
        False,
    )


def check_bemt_roundtrip(bench: Bench) -> None:
    group = ".bemt-contract"
    with tempfile.TemporaryDirectory(prefix="zbemt-convention-bench-") as tmp:
        project = _base_project(is_propeller=True)
        project.path = tmp
        project.saved_cases = [FlightCondition(
            name="propeller-roundtrip",
            mu_x=0.041,
            Vz=53.0,
            collective_deg=5.0,
            rpm=900.0,
        )]
        api.save_project(project)
        paths = default_project_paths(tmp)
        raw = json.loads(Path(paths["saved_cases"]).read_text(encoding="utf-8"))
        row = raw[0]

        bench.check(
            group,
            "propeller .bemt writes display-axis keys",
            "mu_z" in row and "Vx" in row and "mu_x" not in row and "Vz" not in row,
            "A propeller file must use the same x/z vocabulary the GUI shows.",
            sorted(row),
            "contains mu_z and Vx; not mu_x/Vz",
        )

        reopened = api.open_project(tmp)
        condition = reopened.saved_cases[0]
        bench.close(group, "propeller .bemt round-trip preserves internal mu_x",
                    condition.mu_x, 0.041, atol=1e-12)
        bench.close(group, "propeller .bemt round-trip preserves internal Vz",
                    condition.Vz, 53.0, atol=1e-12)


def check_gui_contract(bench: Bench) -> None:
    group = "gui-contract"
    try:
        from PyQt6.QtWidgets import QApplication
        from zbemt.gui.common import resolve_condition_pair
        from zbemt.gui.widgets import (AxialInput, CONDITION_UNITS,
                                       LongitudinalInput)
    except ModuleNotFoundError as exc:
        bench.warn(group, "GUI checks available", f"PyQt6 unavailable: {exc}")
        return

    app = QApplication.instance() or QApplication([])
    _ = app
    rpm, radius = 900.0, 1.0
    omega_r = _omega_r(rpm, radius)

    def label(slot: str, is_propeller: bool, variable: str) -> str:
        return next(text for text, key in CONDITION_UNITS[(slot, is_propeller)]
                    if key == variable)

    advance = LongitudinalInput()
    axial = AxialInput()
    advance.set_context_provider(lambda: (rpm, radius))
    axial.set_context_provider(lambda: (0.0, rpm, radius))
    advance.set_default_unit(True)
    axial.set_default_unit(True)

    axial.unit_combo.setCurrentText(label("axial", True, "Vz"))
    axial.spin.setValue(-40.0)
    advance.unit_combo.setCurrentText(label("inplane", True, "alpha_disk"))
    advance.spin.setValue(11.0)
    mu_gui, vz_gui = resolve_condition_pair(advance, axial, rpm, radius)
    mu_expected = math.tan(math.radians(11.0)) * 40.0 / omega_r
    bench.close(
        group,
        "GUI alpha_disk agrees with engine for negative axial flow",
        mu_gui, mu_expected, atol=2e-7,
        detail=("Same alpha_disk and |V_axial| must identify the same cross-flow side "
                "in GUI, CLI, .bemt and engine."),
    )
    bench.close(group, "GUI keeps signed axial component", vz_gui, -40.0,
                atol=1e-9)

    # Unit-change preservation: changing the spelling must not change the
    # physical state.  LongitudinalInput currently has rpm/R context only; this
    # exposes whether alpha_disk can be converted using the current axial speed.
    advance.unit_combo.setCurrentText(label("inplane", True, "Vx"))
    advance.spin.setValue(6.0)
    axial.spin.setValue(60.0)
    advance.unit_combo.setCurrentText(label("inplane", True, "alpha_disk"))
    shown_angle = float(advance.spin.value())
    expected_angle = math.degrees(math.atan2(6.0, 60.0))
    bench.close(
        group,
        "switching cross-flow velocity -> alpha_disk preserves the vector",
        shown_angle, expected_angle, atol=2e-3,
        detail=("A unit dropdown is a representation change, not a new command; "
                "6 m/s cross-flow with 60 m/s axial flow is about 5.711 deg."),
    )


def check_dynamic_stall_single_source(bench: Bench) -> None:
    group = "schema-contract"
    project = _base_project()
    duplicated = sorted(name for name in project.config
                        if name == "use_dynamic_stall"
                        or name.startswith("dynamic_stall_"))
    if duplicated:
        bench.warn(
            group,
            "dynamic-stall fields have two serialized homes",
            "AirfoilDef is documented as the canonical project source, while "
            "BEMTConfig still serializes backward-compatibility fields. Normal "
            "project execution lets airfoil.dynamic_stall_params override the "
            f"config copy. Duplicated config keys: {duplicated}",
            duplicated,
            "one authoritative project input location",
        )
    else:
        bench.record(group, "dynamic-stall fields have one serialized home",
                     "PASS", "No duplicate project-level dynamic-stall inputs found.")


def check_physics_scalings(bench: Bench) -> None:
    group = "physics-metamorphic"
    base = _base_project()
    r0 = _run(base)
    s0 = r0.summary
    omega = 2.0 * math.pi * 900.0 / 60.0

    bench.close(group, "shaft power identity P = Q*Omega",
                s0["Power"], s0["Torque"] * omega,
                rtol=2e-12, atol=1e-9)
    bench.close(group, "rotor coefficient identity CP = CQ",
                s0["CP"], s0["CQ"], rtol=2e-12, atol=1e-12)
    bench.close(group, "propeller coefficient identity CP_prop = 2*pi*CQ_prop",
                s0["CP_prop"], 2.0 * math.pi * s0["CQ_prop"],
                rtol=2e-12, atol=1e-12)
    bench.close(group, "CT_prop conversion from rotor CT",
                s0["CT_prop"], s0["CT"] * math.pi ** 3 / 4.0,
                rtol=2e-12, atol=1e-12)
    bench.close(group, "CQ_prop conversion from rotor CQ",
                s0["CQ_prop"], s0["CQ"] * math.pi ** 3 / 8.0,
                rtol=2e-12, atol=1e-12)
    bench.close(group, "CP_prop conversion from rotor CP",
                s0["CP_prop"], s0["CP"] * math.pi ** 4 / 4.0,
                rtol=2e-12, atol=1e-12)

    # Density must factor out of the momentum/BET fixed point when the polar
    # itself is unchanged: dimensional forces scale with rho, coefficients do not.
    dense = copy.deepcopy(base)
    dense.config["rho"] = 2.0 * float(base.config["rho"])
    sd = _run(dense).summary
    for key in ("Thrust", "Torque", "Power"):
        bench.close(group, f"density x2 -> {key} x2", sd[key], 2.0 * s0[key],
                    rtol=3e-6, atol=1e-8)
    for key in ("CT", "CQ", "CP"):
        bench.close(group, f"density x2 leaves {key} invariant", sd[key], s0[key],
                    rtol=3e-6, atol=1e-10)

    # At fixed nondimensional condition, with compressibility disabled and an
    # analytical Re-independent polar, force/moment scale as Omega^2 and power
    # as Omega^3.
    rpm1, rpm2 = 720.0, 1080.0
    ratio = rpm2 / rpm1
    s1 = _run(base, rpm=rpm1).summary
    s2 = _run(base, rpm=rpm2).summary
    bench.close(group, "fixed-mu RPM scaling of thrust",
                s2["Thrust"], s1["Thrust"] * ratio ** 2,
                rtol=4e-5, atol=1e-7)
    bench.close(group, "fixed-mu RPM scaling of torque",
                s2["Torque"], s1["Torque"] * ratio ** 2,
                rtol=4e-5, atol=1e-7)
    bench.close(group, "fixed-mu RPM scaling of power",
                s2["Power"], s1["Power"] * ratio ** 3,
                rtol=4e-5, atol=1e-6)
    for key in ("CT", "CQ", "CP"):
        bench.close(group, f"fixed-mu RPM leaves {key} invariant",
                    s2[key], s1[key], rtol=4e-5, atol=1e-10)


def check_physics_coordinate_invariance(bench: Bench) -> None:
    group = "physics-coordinate-invariance"
    project = _base_project()
    rpm, radius, mag = 900.0, project.geometry.radius_m, 0.12
    omega_r = _omega_r(rpm, radius)
    base = _run(project, mu_x=mag, rpm=rpm).summary

    beta = math.radians(37.0)
    rotated = _run(
        project,
        mu_x=mag * math.cos(beta),
        Vy=mag * math.sin(beta) * omega_r,
        rpm=rpm,
    ).summary
    bench.close(group, "rotating in-plane free stream preserves thrust",
                rotated["Thrust"], base["Thrust"], rtol=8e-4, atol=1e-6)
    bench.close(group, "rotating in-plane free stream preserves torque",
                rotated["Torque"], base["Torque"], rtol=8e-4, atol=1e-6)

    # is_propeller is nomenclature/non-dimensional reporting only.  The same
    # internal disk-axis state must solve to the same dimensional loads.
    prop = copy.deepcopy(project)
    prop.config["is_propeller"] = True
    prop_result = _run(prop, mu_x=mag, rpm=rpm).summary
    for key in ("Thrust", "Torque", "Power", "H", "Y", "Mx", "My"):
        bench.close(group, f"rotor/propeller mode leaves dimensional {key} unchanged",
                    prop_result[key], base[key], rtol=2e-10, atol=1e-8)


def check_pitch_parameterization(bench: Bench) -> None:
    group = "physics-parameterization"
    project_a = _base_project()
    project_b = copy.deepcopy(project_a)
    delta = 2.25
    project_b.geometry.twist_deg = [float(x) + delta
                                   for x in project_b.geometry.twist_deg]

    a = _run(project_a, collective_deg=7.0).summary
    b = _run(project_b, collective_deg=7.0 - delta).summary
    for key in ("Thrust", "Torque", "Power", "CT", "CQ", "CP", "H", "Y"):
        bench.close(
            group,
            f"collective/twist gauge equivalence for {key}",
            b[key], a[key], rtol=2e-10, atol=1e-9,
            detail="Adding a rigid pitch offset to geometry and removing it from collective must be identical.",
        )


def check_propeller_efficiency_identity(bench: Bench) -> None:
    group = "physics-propeller"
    project = _base_project(is_propeller=True)
    rpm = 900.0
    Vaxial = 0.16 * _omega_r(rpm, project.geometry.radius_m)
    result = _run(project, mu_x=0.0, Vz=Vaxial,
                  collective_deg=14.0, rpm=rpm).summary
    if result["CT_prop"] <= 0.0 or result["CP_prop"] <= 1e-9:
        bench.warn(group, "propulsive-efficiency identity",
                   "Bench point did not land in positive-thrust/positive-power propulsion; "
                   "identity not asserted.",
                   {k: result[k] for k in ("CT_prop", "CP_prop", "J_z", "eta_prop")})
        return
    expected = result["J_z"] * result["CT_prop"] / result["CP_prop"]
    bench.close(group, "eta_prop = J_axial*CT_prop/CP_prop",
                result["eta_prop"], expected, rtol=2e-12, atol=1e-12)


def check_model_validity_flags(bench: Bench) -> None:
    group = "physics-model-validity"
    # Prandtl-Glauert is a linearized subsonic correction.  zBEMT clamps it
    # numerically at M=0.9, but the model should be treated as approximate
    # substantially before that.  This is recorded as a model-scope warning,
    # not as a numerical defect.
    bench.warn(
        group,
        "Prandtl-Glauert is not a transonic model",
        "use_compressibility applies a Prandtl-Glauert factor and clamps the "
        "factor at M=0.9. Results approaching the critical/transonic regime "
        "must not be interpreted as shock/wave-drag physics.",
        "M clamp = 0.9",
        "linearized subsonic regime",
    )
    bench.warn(
        group,
        "uniform PG scaling of tabulated Cd is a modeling assumption",
        "The engine divides both Cl and Cd by beta. The classical PG rule is "
        "a linearized pressure/force correction; viscous/profile drag and wave "
        "drag are not generally obtained by uniformly scaling a low-speed Cd. "
        "Treat this as an explicit approximation, especially for imported polars.",
    )


def build_bench() -> Bench:
    bench = Bench()
    checks = (
        ("convention-core", "core conversions", check_convention_core),
        ("cli-contract", "CLI contract", check_cli_contract),
        (".bemt-contract", ".bemt round-trip", check_bemt_roundtrip),
        ("gui-contract", "GUI conversion contract", check_gui_contract),
        ("schema-contract", "schema single-source", check_dynamic_stall_single_source),
        ("physics-metamorphic", "physics scalings", check_physics_scalings),
        ("physics-coordinate-invariance", "coordinate invariance", check_physics_coordinate_invariance),
        ("physics-parameterization", "pitch parameterization", check_pitch_parameterization),
        ("physics-propeller", "propeller identities", check_propeller_efficiency_identity),
        ("physics-model-validity", "model validity", check_model_validity_flags),
    )
    for group, label, fn in checks:
        bench.run(group, label, lambda fn=fn: fn(bench))
    return bench


def _print_report(report: dict) -> None:
    current = None
    for row in report["checks"]:
        if row["group"] != current:
            current = row["group"]
            print(f"\n[{current}]")
        print(f"  {row['status']:4s}  {row['name']}: {row['detail']}")
    c = report["counts"]
    print(f"\nSummary: {c['PASS']} PASS, {c['WARN']} WARN, {c['FAIL']} FAIL")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_path",
                        help="Write the complete machine-readable ledger to this path.")
    parser.add_argument("--strict", action="store_true",
                        help="Return 1 when any diagnostic check fails.")
    args = parser.parse_args(argv)

    bench = build_bench()
    report = bench.summary()
    _print_report(report)

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        print(f"JSON: {path}")

    return 1 if args.strict and report["counts"]["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
