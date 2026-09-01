"""Preserve the complete claim inventory from the five source reports."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .claim_catalog import claim_details
from .models import Claim, EvidenceGrade, SourceInventoryEntry, SourceReference


PROP_REPORT = "report_propeller_vs_literature.md"
STABILITY_REPORT = "report_stability_derivatives_flapping.md"
STALL_REPORT = "report_stall_pittpeters.md"
AUDIT_REPORT = "docs/physics_audit_flapping_pittpeters.md"
DYNAMIC_REPORT = "docs/report_dynamic_stall_pitt_peters_review.md"

_inventory: list[SourceInventoryEntry] = []
_metadata: dict[str, tuple[str, str, str]] = {}
_first_occurrence: dict[str, str] = {}


def _add_rows(
    report: str,
    locator_group: str,
    rows: Iterable[tuple[str, str, str, str, str]],
) -> None:
    """Add static source rows and link later occurrences as duplicates."""
    for original_id, canonical_id, title, status, domain in rows:
        locator = f"{locator_group}:{original_id}"
        occurrence_id = f"{report}:{locator}"
        duplicate_of = _first_occurrence.get(canonical_id)
        if duplicate_of is None:
            _first_occurrence[canonical_id] = occurrence_id
            _metadata[canonical_id] = (title, status, domain)
        _inventory.append(SourceInventoryEntry(
            occurrence_id=occurrence_id,
            report=report,
            original_id=original_id,
            locator=locator,
            canonical_claim_id=canonical_id,
            duplicate_of=duplicate_of,
        ))


_add_rows(PROP_REPORT, "heading", [
    ("T1", "PROP-T1", "Propeller coefficient definitions", "OK", "propeller"),
    ("C14", "PROP-C14", "Power equals torque times shaft speed", "OK", "propeller"),
    ("T2a", "PROP-T2A", "Momentum efficiency bound", "OK", "propeller"),
    ("T2b", "PROP-T2B", "Induced velocity exceeds the momentum minimum", "OK", "propeller"),
    ("T3", "PROP-T3", "Static figure of merit range", "OK", "propeller"),
    ("C13", "PROP-C13", "Induced-power bookkeeping", "OK", "propeller"),
    ("F5", "PROP-F5", "Hover induced velocity for gentle twist", "OK", "propeller"),
    ("T4", "PROP-T4", "Propeller curve shapes", "OK", "propeller"),
    ("N-2", "PROP-N2", "Borderline propeller convergence", "INFO", "propeller"),
    ("T5a", "PROP-T5A", "Prandtl loss ordering", "OK", "propeller"),
    ("T5c", "PROP-T5C", "Solver cross-agreement", "OK", "propeller"),
    ("T5d / F-A", "PROP-FA", "Steady Pitt-Peters axial agreement", "notOK", "pitt_peters"),
    ("T6a", "PROP-T6A", "RPM similarity without compressibility", "OK", "propeller"),
    ("T6b / F-B", "PROP-FB", "Compressibility behavior above its valid Mach range", "notOK", "model_effects"),
    ("T6c", "PROP-T6C", "Density scaling", "OK", "propeller"),
    ("T7", "PROP-T7", "Cross-flow symmetry and normal force", "OK", "propeller"),
    ("T8", "PROP-T8", "Windmill, brake, and reverse-flow regimes", "OK", "propeller"),
    ("N-1", "PROP-N1", "Windmill efficiency clamp", "INFO", "model_limitation"),
    ("F-C / T9-N3", "PROP-N3", "Static reverse thrust for the starter geometry", "INFO", "propeller"),
    ("T9a", "PROP-T9A", "Blade-count scaling", "OK", "propeller"),
    ("T9b", "PROP-T9B", "Radius scaling", "OK", "propeller"),
    ("T10", "PROP-T10", "Propeller mesh convergence", "OK", "propeller"),
    ("K1", "PROP-K1", "Induced-power factor", "OK", "propeller"),
    ("K3", "PROP-K3", "Axial-flight correction no-ops", "OK", "model_effects"),
    ("K4", "PROP-K4", "Azimuthal discretization convergence", "OK", "propeller"),
    ("K5", "PROP-K5", "Stall-model ordering", "OK", "model_effects"),
    ("K6", "PROP-K6", "Profile-drag scaling", "OK", "propeller"),
    ("K7", "PROP-K7", "Reverse thrust with symmetric twist", "OK", "propeller"),
    ("K9", "PROP-K9", "Extreme-collective behavior", "OK", "propeller"),
    ("K8", "PROP-K8", "Validation of non-positive density", "notOK", "input_validation"),
])

_prop_summary_rows = [
    ("T1", "PROP-T1", "Propeller coefficient definitions", "OK", "propeller"),
    ("C14/C13", "PROP-POWER-SUMMARY", "Propeller power bookkeeping summary", "OK", "propeller"),
    ("T2a/T2b", "PROP-MOMENTUM-SUMMARY", "Propeller momentum bounds summary", "OK", "propeller"),
    ("T3 / F5", "PROP-STATIC-SUMMARY", "Static performance summary", "OK", "propeller"),
    ("K1", "PROP-K1", "Induced-power factor", "OK", "propeller"),
    ("T4", "PROP-T4", "Propeller curve shapes", "OK", "propeller"),
    ("T5a", "PROP-T5A", "Prandtl loss ordering", "OK", "propeller"),
    ("T5c", "PROP-T5C", "Solver cross-agreement", "OK", "propeller"),
    ("F-A", "PROP-FA", "Steady Pitt-Peters axial agreement", "notOK", "pitt_peters"),
    ("T6a", "PROP-T6A", "RPM similarity", "OK", "propeller"),
    ("F-B", "PROP-FB", "Compressibility Mach limit", "notOK", "model_effects"),
    ("T6c", "PROP-T6C", "Density scaling", "OK", "propeller"),
    ("T7", "PROP-T7", "Cross-flow symmetry", "OK", "propeller"),
    ("T8", "PROP-T8", "Windmill and brake regimes", "OK", "propeller"),
    ("T9a/T9b", "PROP-GEOMETRY-SUMMARY", "Geometry scaling summary", "OK", "propeller"),
    ("T10", "PROP-T10", "Grid convergence", "OK", "propeller"),
    ("K3", "PROP-K3", "Axial-flight correction no-ops", "OK", "model_effects"),
    ("K4", "PROP-K4", "Azimuthal convergence", "OK", "propeller"),
    ("K5", "PROP-K5", "Stall-model ordering", "OK", "model_effects"),
    ("K6", "PROP-K6", "Profile-drag scaling", "OK", "propeller"),
    ("K7", "PROP-K7", "Reverse thrust", "OK", "propeller"),
    ("K9", "PROP-K9", "Extreme collective", "OK", "propeller"),
    ("K8", "PROP-K8", "Physical-range validation", "notOK", "input_validation"),
    ("N-1", "PROP-N1", "Windmill efficiency clamp", "INFO", "model_limitation"),
    ("N-2", "PROP-N2", "Borderline convergence", "INFO", "propeller"),
    ("N-3", "PROP-N3", "Starter geometry reverse thrust", "INFO", "propeller"),
]
_add_rows(PROP_REPORT, "verdict-summary-1", _prop_summary_rows)
_add_rows(PROP_REPORT, "verdict-summary-2", [
    row for row in _prop_summary_rows if row[0] not in {"K1", "K3", "K4", "K5", "K6", "K7", "K9", "K8"}
])


_stability_primary = [
    ("P1", "DERIV-P1", "Hover heave damping", "OK", "stability_derivatives"),
    ("P2", "DERIV-P2", "Hover pitch damping with flapping", "OK", "stability_derivatives"),
    ("P3", "DERIV-P3", "Hover roll and pitch damping equality", "OK", "stability_derivatives"),
    ("P4", "DERIV-P4", "Rigid hover rate-matrix invariance", "OK", "stability_derivatives"),
    ("P5", "DERIV-P5", "Flapping hover control-matrix invariance", "OK", "stability_derivatives"),
    ("P6", "DERIV-P6", "Derivative sign conventions", "OK", "stability_derivatives"),
    ("P7", "DERIV-P7", "Flapping reduction of rate damping", "OK", "stability_derivatives"),
    ("E1", "DERIV-E1", "Flapping hover rate-matrix invariance", "notOK", "stability_derivatives"),
    ("E2", "DERIV-E2", "Flapping outer-loop convergence", "notOK", "flapping"),
    ("E3", "DERIV-E3", "High-advance thrust-trim derivative study", "notOK", "stability_derivatives"),
]
_add_rows(STABILITY_REPORT, "verdict-summary", _stability_primary)
_add_rows(STABILITY_REPORT, "detailed-heading", _stability_primary + [
    ("A1", "DERIV-A1", "Rate-matrix defect across Lock number and hinge offset", "notOK", "stability_derivatives"),
    ("A2", "DERIV-A2", "Heave damping and flap-loop convergence", "OK/notOK", "stability_derivatives"),
    ("A3", "DERIV-A3", "Forward pitch and roll damping", "OK", "stability_derivatives"),
    ("A4", "DERIV-A4", "Positive RPM derivatives", "OK", "stability_derivatives"),
    ("A5", "DERIV-A5", "Derivative reliability boundary", "PROVISIONAL", "model_limitation"),
])


_add_rows(STALL_REPORT, "dynamic-stall-table", [
    ("A1", "DS-A1", "Steady separation-state invariance", "PASSED", "dynamic_stall"),
    ("A4", "DS-A2", "Sinusoidal separation-state amplitude and phase", "PASSED", "dynamic_stall"),
    ("A3", "DS-A3", "Time-constant response ordering", "PASSED", "dynamic_stall"),
    ("A7", "DS-A4", "Separation-state step response", "PASSED", "dynamic_stall"),
    ("A5", "DS-A5", "Periodic residual decay", "PASSED", "dynamic_stall"),
    ("A6", "DS-A6", "Maneuver separation-state continuity", "PASSED", "dynamic_stall"),
    ("D1", "DS-A7", "Dynamic-stall hover invariance", "PASSED", "dynamic_stall"),
    ("D3", "DS-D3-HYSTERESIS-DIRECTION", "Stalled-element lift direction", "PASSED", "dynamic_stall"),
    ("D3b", "DS-D3B-FADE-50", "Static-polar return beyond 50 degrees", "PASSED", "dynamic_stall"),
    ("D4/D5", "DS-MANEUVER-REPORTING", "Maneuver history and residual reporting", "PASSED", "reporting"),
])
_add_rows(STALL_REPORT, "pitt-peters-table", [
    ("P1", "PP-B1", "Pitt-Peters hover equilibrium", "PASSED", "pitt_peters"),
    ("P2", "PP-B2", "Pitt-Peters march to steady equilibrium", "PASSED", "pitt_peters"),
    ("P3", "PP-B3", "Pitt-Peters linear decay rate", "PASSED", "pitt_peters"),
    ("P4", "PP-B4", "Pitt-Peters collective step", "PASSED", "pitt_peters"),
    ("P5", "PP-P5-ASYMMETRY", "Pitt-Peters forward-flight asymmetry", "PASSED", "pitt_peters"),
    ("P6", "PP-P6-THRUST", "Pitt-Peters and Drees thrust agreement", "PASSED", "pitt_peters"),
])
_add_rows(STALL_REPORT, "numbered-finding", [
    ("1", "PP-B7", "Sideslip consistency between steady and marched inflow", "CONFIRMED", "pitt_peters"),
    ("2", "REPO-PITT-WARNING", "English Pitt-Peters warning text", "CONFIRMED", "repository_quality"),
    ("3", "PP-B10", "Pitt-Peters substep default", "OBSERVATION", "model_limitation"),
    ("4", "PP-B9", "Time-march reporting", "VERIFIED", "reporting"),
])


_add_rows(AUDIT_REPORT, "headed-check", [
    ("The apparent mass matrix", "PP-MASS-MATRIX", "Pitt-Peters apparent mass matrix", "VERIFIED", "pitt_peters"),
    ("The gain matrix L", "PP-GAIN-L", "Pitt-Peters gain matrix", "VERIFIED", "pitt_peters"),
    ("The mass-flow parameter matrix V", "PP-MASS-FLOW", "Pitt-Peters mass-flow matrix", "VERIFIED", "pitt_peters"),
    ("The steady state and the march", "PP-STEADY-MARCH-AUDIT", "Pitt-Peters equilibrium and march audit", "VERIFIED", "pitt_peters"),
])
_add_rows(AUDIT_REPORT, "numbered-finding", [
    ("1", "DERIV-NONDIM-RATES", "Non-dimensional angular-rate derivative scaling", "CONFIRMED", "stability_derivatives"),
    ("2", "STALL-DELAY-RATIO", "Snel stall-delay velocity ratio", "CONFIRMED", "stall_delay"),
])
_add_rows(AUDIT_REPORT, "numbered-observation", [
    ("1", "PP-PHASE-CONVENTION", "Pitt-Peters harmonic phase convention", "OBSERVATION", "model_limitation"),
    ("2", "PP-LINEAR-LIMITATION", "Pitt-Peters linear-theory boundary", "OBSERVATION", "model_limitation"),
    ("3", "LAG-CORIOLIS-LIMITATION", "Lead-lag Coriolis limitation", "OBSERVATION", "model_limitation"),
])


_dynamic_sections = {
    "A": ("dynamic_stall", [
        "Steady separation-state invariance", "Sinusoidal separation-state response",
        "Dynamic-stall time-constant ordering", "Dynamic-stall step response",
        "Periodic residual decay", "Maneuver state continuity", "Hover invariance",
        "Frequency and time-march agreement", "Hysteresis direction", "Hysteresis causality",
        "Lift peak timing", "Lift overshoot magnitude", "Post-stall drag",
        "Dynamic-stall fade window", "Time-constant monotonicity", "Integrated load magnitude",
        "Discrete and frequency method distinction", "Multi-section dynamic-stall opt-out",
    ]),
    "B": ("pitt_peters", [
        "Pitt-Peters hover equilibrium", "March to steady equilibrium", "Linearized decay rate",
        "Collective-step response", "Forward-flight inflow comparison", "Hover outer convergence",
        "Sideslip steady and march consistency", "RPM-step state continuity", "Time-march reporting",
        "Pitt-Peters substep default",
    ]),
    "C": ("core_bemt", [
        "Hover closed-form thrust", "Hover figure of merit", "Solidity invariance",
        "Prandtl factor closed form", "Compressibility at moderate Mach", "Radial-flow drag closed form",
        "Profile-power scaling", "Axial-flow ordering", "Solver agreement", "Reverse-flow continuity",
        "Himmelskamp and Snel activation", "Analytical-polar Mach layering",
    ]),
    "D": ("extremes", [
        "Axial sweep through the vortex-ring band", "Strong-climb convergence", "Coefficient normalization",
        "Partial convergence warning threshold", "Autorotation transitions", "Propeller efficiency envelope",
    ]),
    "E": ("flapping", [
        "Offset-hinge flap frequency", "Flap resonance guard", "Hover coning", "Forward-flight blowback",
        "Cyclic response phase", "Delta-3 coupling direction", "Gyroscopic rate response",
        "Cyclic hub-moment relief", "Rigid-path identity", "Rigid-path flap result keys",
        "Collective and RPM trim accuracy", "Bisection trim reporting",
    ]),
}


def _dynamic_claim_id(section: str, index: int) -> str:
    """Return the stable claim ID for one dynamic-report table row."""
    if section == "B" and index == 5:
        return "PP-B5-COMBINED"
    prefix = {
        "A": "DS",
        "B": "PP",
        "C": "BEMT",
        "D": "EXT",
        "E": "FLAP",
    }[section]
    return f"{prefix}-{section}{index}"


for section, (domain, titles) in _dynamic_sections.items():
    _add_rows(DYNAMIC_REPORT, f"section-{section}-table", [
        (f"{section}{index}", _dynamic_claim_id(section, index), title,
         "NOTE" if (section, index) in {("A", 17), ("A", 18), ("B", 10), ("C", 12), ("D", 2)} else
         "NOT OK" if (section, index) in {("B", 7), ("E", 10), ("E", 12)} else "OK", domain)
        for index, title in enumerate(titles, start=1)
    ])

_add_rows(DYNAMIC_REPORT, "section-F-heading", [
    ("F1", "PP-B7", "Sideslip and marched Pitt-Peters inconsistency", "NOT OK", "pitt_peters"),
    ("F2", "REPO-PITT-WARNING", "Bilingual Pitt-Peters warning", "NOT OK", "repository_quality"),
    ("F3", "FLAP-E10", "Rigid flapping result keys", "NOT OK", "flapping"),
    ("F4", "FLAP-E12", "Bisection trim record", "NOT OK", "reporting"),
    ("F5", "FLAP-G5B", "Lead-lag request with a rigid flap model", "NOT OK", "lead_lag"),
    ("F6", "FLAP-H3B", "Three-degree-of-freedom trim execution", "NOT OK", "flapping"),
])
_add_rows(DYNAMIC_REPORT, "section-G-table", [
    ("G1", "MODEL-G1", "Stall-model polar shapes", "OK", "model_effects"),
    ("G2", "MODEL-G2", "Deep reverse-flow model spread", "OK", "model_effects"),
    ("G3", "MODEL-G3", "Compressibility near the Mach ceiling", "OK", "model_effects"),
    ("G4", "FLAP-G4", "Flap spring frequency", "OK", "flapping"),
    ("G5", "FLAP-G5", "Lead-lag spring frequency", "OK", "lead_lag"),
    ("G5b", "FLAP-G5B", "Lead-lag request with a rigid flap model", "NOT OK", "lead_lag"),
    ("G6", "BEMT-G6", "Density and RPM similarity", "OK", "core_bemt"),
    ("G7", "PP-G7", "Coleman and Drees sideslip rotation", "OK", "pitt_peters"),
    ("G8", "PROP-G8", "Oblique propeller loading", "NOTE", "propeller"),
])
_add_rows(DYNAMIC_REPORT, "section-H-table", [
    ("H1", "BEMT-H1", "Mesh convergence", "OK", "core_bemt"),
    ("H2", "BEMT-H2", "Rotor and disk angle identity", "OK", "core_bemt"),
    ("H3", "FLAP-H3", "Cyclic flapback trim", "OK", "flapping"),
    ("H3b", "FLAP-H3B", "Three-degree-of-freedom trim execution", "NOT OK", "flapping"),
    ("H3c", "FLAP-H3C", "Flapback trim iteration limit", "NOTE", "flapping"),
    ("H4", "DS-H4", "Maneuver dynamic-stall hysteresis", "OK", "dynamic_stall"),
    ("H5", "DERIV-H5", "Stability derivative signs", "OK", "stability_derivatives"),
])


SOURCE_INVENTORY = tuple(_inventory)

_references: dict[str, list[SourceReference]] = defaultdict(list)
for _entry in SOURCE_INVENTORY:
    _references[_entry.canonical_claim_id].append(SourceReference(
        report=_entry.report,
        original_id=_entry.original_id,
        locator=_entry.locator,
    ))

def _build_claim(claim_id: str) -> Claim:
    """Build one canonical claim from its static inventory and catalog."""
    title, original_status, domain = _metadata[claim_id]
    reference_text, rule, cli_route, gui_route, requirements = claim_details(
        claim_id,
        title,
        domain,
    )
    return Claim(
        claim_id=claim_id,
        domain=domain,
        title=title,
        source_references=tuple(_references[claim_id]),
        original_status=original_status,
        requirement_codes=requirements,
        evidence_grade=EvidenceGrade.UNVERIFIED,
        theory_reference_text=reference_text,
        acceptance_rule=rule,
        cli_route=cli_route,
        gui_route=gui_route,
        executor_name=f"{domain}_executor",
    )


CLAIMS = tuple(_build_claim(claim_id) for claim_id in sorted(_metadata))


def select_claims(
    claim_ids: Iterable[str] | None = None,
    domains: Iterable[str] | None = None,
    pattern: str | None = None,
) -> list[Claim]:
    """Select claims by intersection and return stable-ID order."""
    requested_ids = set(claim_ids or ())
    requested_domains = {domain.casefold() for domain in (domains or ())}
    normalized_pattern = pattern.casefold() if pattern else None
    selected = []
    for claim in CLAIMS:
        if requested_ids and claim.claim_id not in requested_ids:
            continue
        if requested_domains and claim.domain.casefold() not in requested_domains:
            continue
        searchable = f"{claim.claim_id} {claim.domain} {claim.title}".casefold()
        if normalized_pattern and normalized_pattern not in searchable:
            continue
        selected.append(claim)
    return selected
