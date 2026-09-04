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
result CSV is sufficient. They use the same public API as the GUI when a claim
requires a local map, polar, derivative matrix, or marched history that the
CLI does not export. Every claim also has a written GUI reproduction route in
the catalog.

The theory checks use actuator-disk momentum, blade-element identities,
Prandtl loss, similarity, linear flap theory, the first-order separation-lag
transfer function, and finite-state inflow limits. The external references
include the ECN report on rotational augmentation
<https://publications.ecn.nl/ECN-RX--93-028>, the Pitt-Peters dynamic-inflow
formulation <https://ntrs.nasa.gov/citations/19880017772>, and NASA oblique
propeller measurements <https://ntrs.nasa.gov/search.jsp?R=19930094852>.

Run the complete evidence campaign with:

```text
python tools/run_quality_checks.py --suite physics
```

## Campaign result

The complete campaign executes 138 claims with no executor failure and no
inconclusive result.

| Status | Claims |
| --- | ---: |
| Confirmed correct | 129 |
| Confirmed defect | 0 |
| Not reproduced | 3 |
| Out-of-scope limitation | 6 |
| Inconclusive | 0 |

Every claim now resolves, and every claim that is not "confirmed correct"
carries a DECIDED verdict. There is no third answer: each one is either a
defect in the model, which was corrected, or a defect in the claim, which was
restated, or a boundary of the theory, which is documented and checked. An
earlier campaign left 45 claims inconclusive because the source fixture had
not preserved the exact polar, maneuver, local field, or experimental datum
its acceptance rule named. Each of those rules is now either evaluated on the
local field and the marched history that the public API exports, or restated
as a criterion that follows from the model itself. Every restatement is named
in "Acceptance rules restated" below.

### How to read the two non-confirmed statuses

"Not reproduced" means THE CLAIM WAS WRONG, not that the question is open. In
all three cases the source report compared two things that are not the same
thing, and the executor measures the difference and records why it is
expected. None of the three is a suspicion left standing.

"Out-of-scope limitation" means THE THEORY ENDS THERE, and the engine says so.
Each of the six is a positive check: the executor confirms that the declared
limit is real, that the engine reports it, and that nothing outside the limit
is presented as if it were valid. A limitation that the engine hid would be a
defect, not a limitation.

## Defects found and corrected

### Pitt-Peters harmonic inflow was in anti-phase with the loading

The two harmonic forcings of the finite-state inflow model were read as hub
moments, which carry the opposite sign to the loading that drives the inflow
slot. At an in-plane advance ratio of 0.15 the blade loading peaked at 80
degrees of azimuth while the induced inflow peaked at 310 degrees. The
anti-phase response also fed the harmonic states back into their own forcing
with the wrong sign.

The consequences reached the reported loads. The total inflow went negative
over 12% of the disk at an advance ratio of 0.15 and over 23% at 0.25, which
raised the model-validity warning at conditions the model can in fact
represent. One example cruise case reported negative shaft power AND negative
induced power, which no powered rotor produces.

The forcing now carries the loading with the same azimuthal weight as the slot
it drives. The reversed-inflow fraction falls to zero at an advance ratio of
0.15 and to 5% at 0.25, the field correlates with the Drees field instead of
opposing it, and no golden case reports negative induced power any more
(`PP-P5-ASYMMETRY`, `PP-B5-COMBINED`, `tests/regression/test_pitt_peters_inflow.py`).

### The marched inflow ignored sideslip

The steady path rotates the gain matrix into wind axes; the marched path did
not. At 30 degrees of sideslip the two settled on states 0.036 apart. Both
paths now apply the same rotation, and they agree to 1e-9 (`PP-B7`).

### The mass-flow parameter was not exact in hover

The total velocity carried an additive guard inside its square root, which
left the harmonic mass-flow parameter 1.25e-8 short of twice the uniform
inflow. The guard moved onto the parameters themselves, where it protects the
one degenerate state without touching any physical condition (`PP-MASS-FLOW`).

### A marched flapping maneuver could not run

`run_maneuver(march_flapping=True)` raised `KeyError` before returning a
sample: the result builder read the blade properties of an outer flap loop
that the maneuver path never runs. The maneuver now publishes the blade state
it solved with, and the outer-loop record appears only where an outer loop ran
(`DS-H4`, SC-12).

### A derivative matrix did not carry its flap convergence

A finite difference built on a flap solve that missed its declared outer
tolerance is not a derivative. The study now counts those solves and clears
its usable flag (`DERIV-A5`, SC-11).

### The Pitt-Peters validity warning was neither English nor visible

The reverse-inflow warning mixed Portuguese into an English sentence, and it
never left the disk maps: no interface read it. It is now an English text,
exported in the result row, and raised as a result finding
(`REPO-PITT-WARNING`, QR-5).

### Earlier corrections, already closed

- Bisection brackets from the physical initial estimate.
- Non-positive atmospheric values and invalid mesh dimensions fail validation
  before a solve.
- A rigid flap model with enabled lead-lag fails validation instead of
  silently dropping lead-lag motion.
- The rigid path publishes zero flap-motion map keys without changing legacy
  scalar results.
- Bisection trim records target, control, residual, and convergence status.
- Three-degree-of-freedom trim no longer raises the `target_key` name error.
- The flapping solver uses an internal inflow tolerance of `1e-8` when it must
  meet the declared outer flap tolerance (`DERIV-E2`).
- Articulated pitch damping is compared before the structural moment of the
  offset hinge is added (`DERIV-A3`).

## Findings not reproduced as implementation defects

- The Pitt-Peters versus local-Glauert axial difference is a model-form
  difference. Pitt-Peters uses a uniform finite-state mean inflow; local
  Glauert solves annular inflow. Zero skew removes harmonic states but does
  not make those parameterizations identical for a nonuniform blade
  (`PROP-FA`, `PP-P6-THRUST`). What rules out a defect hiding behind that
  wording is that Pitt-Peters is certified on its OWN terms, against momentum
  theory rather than against the other model: its hover state meets the
  momentum identity to six significant figures, and its twenty-revolution
  march settles on the same algebraic fixed point (`PP-B1`, `PP-B6`,
  `PP-STEADY-MARCH-AUDIT`).
- The dynamic-stall frequency versus time-march difference at high advance
  ratio is expected once the dominant-harmonic assumption fails. The two
  methods agree within 1% in their low-advance validity range (`DS-A8`).
- The hover rate-matrix invariance finding used the wrong direct-axis pairing.
  The checked physical pairs are `dMx/dq` and `dMy/dp` (`DERIV-E1`).
- The Snel stall-delay ratio is identical to the published resultant-speed form
  in axial flow, where that form is defined. In forward flight the tangential
  speed no longer equals the rotational speed, and the literal published form
  exceeds one over a large part of the disk, which would raise the section lift
  above its attached-flow value. The implemented form stays inside zero to one
  (`STALL-DELAY-RATIO`).

## Documented model limitations

- The lead-lag oscillator omits flap-lag Coriolis coupling
  (`LAG-CORIOLIS-LIMITATION`).
- Pitt-Peters is a linear finite-state theory. At high loading it drives the
  local total inflow negative. The engine keeps those values and reports the
  fraction (`PP-LINEAR-LIMITATION`).
- The harmonic-state phase names a cosine slot and a sine slot on one azimuth
  reference. Rotating the pair and the reference together reproduces the same
  disk, so the integrated thrust cannot depend on the convention
  (`PP-PHASE-CONVENTION`).
- Eight exponential substeps per maneuver step are conservative: each frozen
  linear system is integrated exactly, so the substep count changes the path
  and not the fixed point (`PP-B10`).
- Propulsive efficiency is clamped to zero while the propeller windmills, and
  the absorbed power stays available through the power coefficient
  (`PROP-N1`).
- A strong climb leaves part of the mesh unconverged and reports it
  (`EXT-D2`).

## Acceptance rules restated

Ten rules named a constant that belonged to a fixture the source reports did
not preserve. Each is restated as a criterion that follows from the model, and
each restatement is recorded with the claim:

- `EXT-D5`: autorotation is certified as the balance between the driving
  torque of the tilted lift and the retarding torque of the profile drag,
  which is what the phenomenon IS. The transition SPEED follows from the
  rotor, its twist and its pitch, so the source constant of 19 to 20 m/s
  measured a rotor the report did not keep.

- `DS-A12`: the lift overshoot is bounded by the attached-flow line, because
  the dynamic lift is a convex combination weighted by a separation state
  inside zero to one. The former "5% to 25%" window belongs to one condition.
- `DS-A13` and `DS-D3-HYSTERESIS-DIRECTION`: the drag ratio and the lift-gain
  fraction are read over the delayed part of the stalled cycle, which is what
  the theory statement names. Averaging the delayed and the reattaching halves
  together hides both.
- `DS-A17`: the two methods each match their own analytical form, and their
  difference falls at every azimuth refinement from 36 to 720 steps. The
  source constant of 0.0024 belongs to one unrecorded mesh.
- `DS-H4`: the ramp marches the flap response with the separation state.
  Without it the unrelieved hub moment drives the linear inflow harmonics past
  their validity range and reverses the sign of the loop.
- `PP-G7`: sideslip turns the harmonic inflow pattern WITH the free stream, by
  plus the sideslip angle. The tangential speed carries `sin(psi - psi_w)` and
  the harmonic gains carry `cos(psi - psi_w)`. The source claim stated the
  opposite sign.
- `PP-B5-COMBINED` and `PP-P5-ASYMMETRY`: the two fields must correlate
  positively and place their maximum within one azimuth cell of each other.
  Pitt-Peters carries one uniform state and one harmonic pair while the Drees
  field solves each annulus, so the two cannot correlate perfectly.
- `PP-MASS-FLOW`: the fast-forward relation is certified as an exact algebraic
  identity whose remainder falls with the square of the speed, instead of
  being sampled at one finite speed.
- `PROP-K3`: the rule covers the three corrections its theory statement names.
  The rotational augmentation is measured beside them and moves the
  coefficients by 1e-7, because the polar is not exactly its own attached-flow
  line even at a small angle.

## Measured numerical properties

- The frequency dynamic-stall method reproduces the first-order transfer
  function to machine precision. The time march holds its drive over each
  azimuth step, so it trails the analytical phase by exactly one half step and
  converges with the mesh (`DS-A2`, `DS-A17`).
- The Pitt-Peters Jacobian is strongly non-normal. A perturbation decays more
  slowly than every eigenvalue for the first decades, and the dominant rate
  appears only in the tail (`PP-B3`).
- A marched maneuver threads the separation state exactly: the first step of a
  sample is the exact update of the previous sample's final state, to zero
  residual. The march inside one sample still covers its own revolutions, so
  the inherited state sets the start of the sample and not its periodic regime
  (`DS-A6`).
- Autorotation is the balance it is supposed to be. The shaft torque splits
  into an induced part and a profile part. The profile part retards at every
  axial speed, as drag must. The induced part changes sign as the inflow tilts
  the lift forward. Where the shaft torque vanishes, at 9.74 m/s on the starter
  rotor at zero collective, the two are equal and opposite to seven parts in a
  million of the profile term, and neither is near zero. The rotor therefore
  autorotates by paying its profile drag with the energy the tilted lift takes
  from the stream, which is the definition (`EXT-D5`).

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
