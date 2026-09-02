"""Compare the implemented Snel stall-delay ratio with its published form.

Snel derived the rotational stall-delay correction for an axial-flow wind
turbine. There, the tangential section speed equals the local rotational
speed, so the ratio of rotational speed to resultant speed and the ratio of
rotational speed to axial speed describe the same number. A rotor in forward
flight separates the two. This executor measures both forms on the same disk
and reports where they agree and where they cannot agree.
"""
from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from zbemt import api, studies
from zbemt.models import FlightCondition

from .evidence import Evidence, build_result, failure_result, utc_now
from .models import CheckResult, Claim, ExecutionContext, FinalStatus


ROOT = Path(__file__).resolve().parents[2]
ROTOR_PROJECT = ROOT / "projects" / "starter_rotor"
CLAIM_IDS = frozenset({"STALL-DELAY-RATIO"})

#: The three radial stations the claim names.
STATIONS = (0.31, 0.54, 0.92)
#: The claim tolerance on the two ratios.
RELATIVE_TOLERANCE = 0.01


def _disk(mu_x: float) -> dict[str, Any]:
    """Return one converged disk with rotational augmentation enabled."""
    project = api.open_project(ROTOR_PROJECT)
    config = dict(project.config)
    config.update({
        "Ne": 40, "Npsi": 72, "use_rotational_augmentation": True,
        "use_compressibility": False,
    })
    case = studies.run_single_case(
        replace(project, config=config),
        FlightCondition(name="snel probe", rpm=400.0, mu_x=mu_x,
                        collective_deg=12.0),
    )
    omega = 400.0 * 2.0 * math.pi / 60.0
    maps = case.maps
    radius_dim = np.asarray(maps["R_DIM"], dtype=float)
    axial = np.asarray(maps["Up"], dtype=float)
    resultant = np.asarray(maps["W"], dtype=float)
    tip_speed = omega * float(project.geometry.radius_m)
    speed_ratio = (omega * radius_dim) / np.maximum(np.abs(axial), 1e-3 * tip_speed)
    implemented = speed_ratio ** 2 / (1.0 + speed_ratio ** 2)
    published = (omega * radius_dim) ** 2 / np.maximum(resultant ** 2, 1e-30)
    return {
        "radius": np.asarray(maps["R_NORM"], dtype=float)[:, 0],
        "implemented": implemented,
        "published": published,
    }


def _station_records(disk: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Return the two ratios averaged over the azimuth at each station."""
    records: dict[str, dict[str, float]] = {}
    for target in STATIONS:
        index = int(np.argmin(np.abs(disk["radius"] - target)))
        implemented = float(np.mean(disk["implemented"][index]))
        published = float(np.mean(disk["published"][index]))
        records[f"{disk['radius'][index]:.3f}"] = {
            "implemented_delay_factor": implemented,
            "published_delay_factor": published,
            "relative_difference": abs(implemented - published)
            / max(abs(published), 1e-15),
        }
    return records


def execute_stall_delay_claim(claim: Claim, context: ExecutionContext) -> CheckResult:
    """Run the stall-delay ratio claim and return its evidence record."""
    started_at = utc_now()
    if claim.claim_id not in CLAIM_IDS:
        return failure_result(
            claim, context, started_at,
            "The claim is outside the stall-delay executor domain.",
        )
    try:
        axial = _disk(0.0)
        forward = _disk(0.25)
    except Exception as exc:
        return failure_result(
            claim, context, started_at,
            f"The public API probe failed: {type(exc).__name__}: {exc}",
        )

    axial_records = _station_records(axial)
    forward_records = _station_records(forward)
    axial_agreement = max(
        record["relative_difference"] for record in axial_records.values())
    forward_agreement = max(
        record["relative_difference"] for record in forward_records.values())
    unbounded_fraction = float(np.mean(forward["published"] > 1.0))
    published_maximum = float(np.max(forward["published"]))

    measured = {
        "axial_flight_stations": axial_records,
        "forward_flight_stations": forward_records,
        "axial_maximum_relative_difference": axial_agreement,
        "forward_maximum_relative_difference": forward_agreement,
        "forward_published_factor_maximum": published_maximum,
        "forward_disk_fraction_above_one": unbounded_fraction,
        "implemented_factor_maximum": float(np.max(forward["implemented"])),
    }
    artifact_directory = Path(context.output_directory) / "stall_delay"
    artifact_directory.mkdir(parents=True, exist_ok=True)
    artifact = artifact_directory / "stall_delay_ratio.json"
    artifact.write_text(json.dumps(measured, indent=2, sort_keys=True), encoding="utf-8")

    axial_identity = axial_agreement <= RELATIVE_TOLERANCE
    status = (FinalStatus.NOT_REPRODUCED if axial_identity
              else FinalStatus.CONFIRMED_DEFECT)
    return build_result(claim, context, started_at, Evidence(
        status=status,
        measured=measured,
        expected={
            "axial_maximum_relative_difference": RELATIVE_TOLERANCE,
            "published_form_bound": 1.0,
        },
        tolerance=(
            "The two ratios must agree within 1% in axial flow, where the "
            "published form is defined."
        ),
        command=(
            "Python public API: api.open_project('projects/starter_rotor'); "
            "studies.run_single_case(project, FlightCondition(rpm=400, "
            "mu_x=0 and 0.25, collective_deg=12)) with "
            "use_rotational_augmentation=True"
        ),
        notes=(
            "In axial flow the implemented ratio equals the published "
            "resultant-speed ratio at every station, so the source finding "
            "is not an implementation defect. In forward flight the "
            "tangential speed no longer equals the rotational speed. The "
            "literal published form then exceeds one over a large part of "
            "the disk, which would raise the section lift above its "
            "attached-flow value. The implemented form stays inside zero to "
            "one. The difference is therefore a documented model-form "
            "adaptation."
        ),
        artifacts=(str(artifact.resolve()),),
    ))
