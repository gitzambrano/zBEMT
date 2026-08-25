# To-do

## How to use this plan

Every open item below is one work package. A package names the physics, the
data contract, the engine change, the GUI, the CLI, the tests and the
documentation that the change needs. Do the phases of a package in order.

Package order and dependencies:

1. **Item 0** rewrites the requirements. Do it first. Items 1 to 4 all break
   `SC-5` as it stands today, so no code may land before the requirement
   changes.
2. **Item 1** (flapping and lead-lag) must land before **Item 4** (stability
   derivatives). A derivative with respect to pitch rate has no meaning while
   the blade cannot flap.
3. **Item 2** (time marching) is independent of Item 1. It shares the outer
   loop with Item 1 only in Phase 2.6.
4. **Item 3** (optimization window) is independent of Items 1, 2 and 4.
5. **Item 5** (review of the geometry comparison mode) is independent of
   everything else. Item 3 reuses two of its phases.

Rules that apply inside every package:

- `docs/software_requirements.md` decides. Cite the requirement code in the
  commit message and in the test docstring.
- A new configurable field must reach the GUI, the CLI and the `.bemt` file in
  the same change (`PA-1`, `PA-3`).
- A new field needs a help popup and a documentation section (`PR-3`, `DC-4`).
- Run `python tools/field_index.py --write` and `python tools/build_toc.py
  --write` after a field or a chapter moves.
- Run `python tests/run_all_tests.py` once, at the end.
- Never write a plain-text symbol such as `lambda_i` on a user-visible surface
  (`PR-4`).

---

## Item 0 — Rewrite the requirements that forbid this work

`docs/software_requirements.md` forbids, today, most of what Items 1 to 4 add.
Change the document first, deliberately, and in one commit of its own.

### Phase 0.1 — Retire the blanket ban on time marching

`SC-5` reads "Unsteady/time-marching aerodynamics. Pitt-Peters unsteady and any
other dynamic time-marching inflow model must not be implemented". Replace it
with a narrower exclusion:

- **SC-5 (new text)** — Free-wake, prescribed-wake and vortex-lattice inflow,
  and any form of computational fluid dynamics. The inflow field stays an
  annular momentum model or a finite-state model. Blade elasticity, that is a
  modal or a finite-element blade, also stays out of scope. The blade is rigid.
  Its rigid-body flap and lag freedoms are in scope (`SC-11`).

### Phase 0.2 — Add the new scope codes

Add these to Section 1.1, after `SC-10`:

- **SC-11** — Rigid-blade flap and lead-lag dynamics, solved as a periodic
  quasi-steady response. The blade carries a flap hinge offset, a root spring,
  or both. A rigid blade with no flap freedom stays available, and it stays the
  default.
- **SC-12** — Transient time marching over a prescribed sequence of flight
  conditions. The marched states are the Pitt-Peters inflow states and the Øye
  separation state. The blade-element solution stays quasi-steady inside each
  time step.
- **SC-13** — Multi-objective design optimization in a dedicated window, with a
  genetic algorithm and a Pareto front. This supersedes the last two sentences
  of `SC-8`, which say the GUI does not offer optimization.
- **SC-14** — Stability and control derivatives of the rotor hub loads, by
  finite differences about a trim point, in a dedicated window.

### Phase 0.3 — Amend `SC-8` and add the engine codes

- Delete "The GUI deliberately does not offer optimization." from `SC-8`. Keep
  the rest. `SC-8` stays the single-objective, derivative-free study. `SC-13`
  is the multi-objective one.
- Add to Section 3.2:
  - **EN-8** — A periodic response solved by harmonic balance must state its
    harmonic count, and it must reject a resonant denominator instead of
    returning a large number. See `ν_β² − n²` in Item 1.
  - **EN-9** — A time-marched state must report the marched interval, the step
    count, and whether the last revolutions reached a periodic regime. A
    transient that did not settle must not pass as a converged result.

### Phase 0.4 — Guard the new codes

Add to `tests/test_requirements_guardrails.py`:

- a test that reads `docs/software_requirements.md` and fails if `SC-5` still
  contains the words "Pitt-Peters unsteady";
- a test that every new code (`SC-11` to `SC-14`, `EN-8`, `EN-9`) appears at
  least once in a test docstring or a module docstring under `zbemt/`.

**Deliverable.** One commit that touches only `docs/software_requirements.md`
and `tests/test_requirements_guardrails.py`.

---

## Item 1 — Blade flapping and lead-lag

The blade is rigid. It rotates about a flap hinge and a lag hinge at the same
radial offset. A root spring may replace the offset, or supplement it. The
response is periodic in azimuth and quasi-steady, which is what a blade-element
momentum solution can support. The aerodynamics inside one azimuth station
stays steady. Only the blade motion adds terms to the local flow.

### 1.0 Physics and notation

Definitions. `e` is the hinge offset as a fraction of `R`. `β(ψ)` is the flap
angle, positive up. `ζ(ψ)` is the lag angle, positive against the direction of
rotation. `I_β` is the flap inertia of one blade about its hinge. `K_β` is the
flap spring stiffness in newton metres per radian. `Ω` is the rotor angular
speed. `ψ = Ω·t` is the non-dimensional time.

Flap frequency ratio, for a uniform blade with an offset hinge and a root
spring:

```
nu_beta^2 = 1 + (3/2)*e/(1 - e) + K_beta/(I_beta*Omega^2)
```

Lag frequency ratio. The lag freedom gets no restoring term from the thrust, so
the leading 1 is absent:

```
nu_zeta^2 = (3/2)*e/(1 - e) + K_zeta/(I_zeta*Omega^2)
```

Lock number, with `a` the lift-curve slope and `c_ref` the chord at `r/R =
0.75`:

```
gamma = rho*a*c_ref*R^4 / I_beta
```

Flap moment about the hinge, for one blade, from the normal force `Fn(r, ψ)`
that `element_state` already returns:

```
M_beta(psi) = integral of (r - e*R)*Fn(r, psi) dr
```

Lag moment about the hinge, from the tangential force `Ft(r, ψ)`:

```
M_zeta(psi) = integral of (r - e*R)*Ft(r, psi) dr
```

Equation of motion in `ψ`, flap:

```
beta'' + nu_beta^2 * beta = M_beta(psi) / (I_beta*Omega^2)
```

Harmonic balance. Write the response and the forcing as truncated Fourier
series with `N_h` harmonics:

```
beta(psi) = beta_0 + sum_n [ beta_nc*cos(n*psi) + beta_ns*sin(n*psi) ]
Mbar(psi) = M_0    + sum_n [ M_nc*cos(n*psi)    + M_ns*sin(n*psi) ]
Mbar = M_beta/(I_beta*Omega^2)
```

Because `beta'' = -n^2*(beta_nc*cos + beta_ns*sin)` for each harmonic, the
solution is algebraic:

```
beta_0  = M_0  / nu_beta^2
beta_nc = M_nc / (nu_beta^2 - n^2)
beta_ns = M_ns / (nu_beta^2 - n^2)
```

`EN-8` applies here. When `|nu_beta^2 - n^2| < 1e-3`, raise `ValueError` and
name the resonance, the harmonic and the hinge offset that produced it. An
articulated rotor with `e = 0` and `K_β = 0` gives `nu_beta = 1` exactly, so
the first harmonic is undefined. That is a physical fact, not a numerical
failure, and the message must say so.

Lag, with a damper `C_ζ`, needs a two-by-two solve per harmonic, because the
damping couples the sine part to the cosine part:

```
 (nu_zeta^2 - n^2)*zeta_nc + n*(C_zeta/(I_zeta*Omega))*zeta_ns = M_nc
-n*(C_zeta/(I_zeta*Omega))*zeta_nc + (nu_zeta^2 - n^2)*zeta_ns = M_ns
 zeta_0 = M_0 / nu_zeta^2
```

`nu_zeta` is zero when the rotor has no offset and no spring. The same guard
applies, and the message must name the lag freedom.

Coupling back into the local flow. Flap adds two terms to the out-of-plane
velocity. Lag adds one term to the in-plane velocity:

```
U_P = lambda_total*Omega*R + (r - e*R)*beta_dot + V_inf*beta*cos(psi)
U_T = Omega*r + V_inf*sin(psi) + (r - e*R)*zeta_dot
beta_dot = Omega*beta'(psi)      zeta_dot = Omega*zeta'(psi)
```

Pitch-flap coupling, the delta-three hinge:

```
theta_eff(r, psi) = theta(r) - K_p*beta(psi),   K_p = tan(delta_3)
```

Assumptions to state in the module docstring and in the documentation:

1. Small angles. `cos β ≈ 1` and `sin β ≈ β`. The blade element stays in the
   disk plane for the purpose of the area and of the arm.
2. The blade is rigid in bending and in torsion.
3. The response is periodic. There is no transient. This is what
   "quasi-steady" means here, and it is what keeps the model consistent with a
   blade-element momentum solution.
4. Flap and lag are solved from the converged aerodynamic field, and the field
   is then re-solved with the new motion, until both agree. See Phase 1.3.

### Phase 1.1 — Data contract

**File `zbemt/models.py`.** Add one dataclass, and one field on
`RotorGeometryDef`. The user enters the blade dynamics on the Geometry tab, so
the data belongs to `inputs/geom.bemt`.

```python
@dataclass
class BladeDynamicsDef:
    """Rigid-blade flap and lead-lag freedoms. See SC-11."""
    flap_model: str = "rigid"        # "rigid" | "offset" | "spring" | "offset_spring"
    hinge_offset_norm: float = 0.0   # e, fraction of R
    flap_spring_nm_per_rad: float = 0.0     # K_beta
    inertia_source: str = "lock"     # "lock" | "inertia" | "blade_mass"
    lock_number: float = 8.0         # gamma, used when inertia_source == "lock"
    flap_inertia_kg_m2: float = 0.0  # I_beta, used when inertia_source == "inertia"
    blade_mass_kg: float = 0.0       # used when inertia_source == "blade_mass"
    pitch_flap_coupling_deg: float = 0.0    # delta_3
    harmonics: int = 2               # N_h in the harmonic balance
    outer_max_iter: int = 30
    outer_tol_deg: float = 1e-4
    outer_relax: float = 0.5
    # --- lead-lag ---
    lag_enabled: bool = False
    lag_spring_nm_per_rad: float = 0.0
    lag_damping_nms_per_rad: float = 0.0
    lag_inertia_kg_m2: float = 0.0
    lag_feeds_back: bool = True      # apply the zeta_dot term to U_T
```

Add to `RotorGeometryDef`:

```python
dynamics: BladeDynamicsDef = field(default_factory=BladeDynamicsDef)
```

`_from_jsonable` already rebuilds a nested dataclass from the annotation, so
the round trip needs no new code. An old `geom.bemt` with no `dynamics` key
gets the default, which is `flap_model="rigid"`, that is the behavior of every
project that exists today. Add a regression test for that in
`tests/test_models.py`.

`blade_mass_kg` converts under a uniform mass per unit length over the flapping
part of the blade:

```
I_beta = m_b*(R - e*R)^2 / 3
```

`lock_number` converts the other way, with `a` from the airfoil and `c_ref`
from the geometry:

```
I_beta = rho*a*c_ref*R^4 / gamma
```

Put both conversions in `zbemt/geometry.py`, as `flap_inertia_from(dynamics,
geom, rho, cl_alpha)`. `models.py` holds no physics (`AR-3`).

**File `zbemt/validation.py`.** Add `validate_blade_dynamics(dynamics, geom)`,
which returns `Issue`s:

- an error when `flap_model` is not `"rigid"` and the resolved `I_β` is not
  greater than zero;
- an error when `hinge_offset_norm` falls outside 0.0 to 0.3;
- an error when `|nu_beta^2 - n^2| < 1e-3` for any `n` up to `harmonics`,
  naming the resonance (`EN-8`);
- a warning when `flap_model` is `"offset"` and `hinge_offset_norm` is zero,
  because that is the articulated resonance;
- an info when a lag field carries a value while `lag_enabled` is false,
  matching the pattern already used for the time-march fields at
  `zbemt/validation.py:119`.

Wire it into `validate_project`.

### Phase 1.2 — Engine, the motion terms

**File `zbemt/bemt.py`.** `element_state` gains one optional keyword. Nothing
changes for a caller that does not pass it:

```python
def element_state(..., r_root_norm_geom, r_tip_norm_geom, motion=None):
```

`motion` is `None`, or a dictionary that carries the arrays `beta`,
`beta_rate` and `zeta_rate` on the `(Ne, Npsi)` grid, plus the scalars
`e_hinge_dim`, `pitch_flap_K`, `cyclic_c_rad` and `cyclic_s_rad`. Inside
`element_state`, right where `Up` and `Ut` are built today, near
`zbemt/bemt.py:1675`:

```python
if motion is not None:
    arm = np.maximum(R_DIM - motion["e_hinge_dim"], 0.0)
    Up = Up + arm*motion["beta_rate"] + Vinf*motion["beta"]*np.cos(PSI)
    Ut = Ut + arm*motion["zeta_rate"]
    THETA = (THETA
             + motion["cyclic_c_rad"]*np.cos(PSI)
             + motion["cyclic_s_rad"]*np.sin(PSI)
             - motion["pitch_flap_K"]*motion["beta"])
```

`THETA` is a local name, so the rebind is safe. Add `beta`, `beta_rate` and
`zeta_rate` to the returned dictionary, so that `aggregate_results` and the
plots can read them.

Leave the reverse-flow branch untouched. `W`, `phi` and `reverse` are all built
from `Up` and `Ut`, so the motion reaches every downstream model with no other
edit.

### Phase 1.3 — Engine, the outer loop

**File `zbemt/bemt.py`, new Section 4h, after the dynamic-stall block.**

```python
def _fourier_coefficients(field_psi, psi_nodes, n_harm):
    """Returns (a0, a_c, a_s) of a periodic field sampled on psi_nodes."""

def _flap_moment(maps, rotor, e_hinge_dim):
    """M_beta(psi): the radial integral of (r - e*R)*Fn, for one blade."""

def _lag_moment(maps, rotor, e_hinge_dim):
    """M_zeta(psi): the radial integral of (r - e*R)*Ft, for one blade."""

def solve_blade_motion(moment_psi, nu_squared, inertia, Omega, n_harm,
                       damping=0.0):
    """Harmonic balance. Returns the coefficients, and the reconstructed
    angle and rate on the psi grid."""

def solve_bemt_flapping(rotor, airfoil, cfg, mu_x, Vz, dynamics,
                        should_cancel=None):
    """Outer loop: solve_bemt, then the moments, then the harmonic
    balance, until the flap coefficients stop moving."""
```

The outer loop:

1. Start from zero motion, or from the coefficients of the previous case in a
   sweep. The warm start cuts the iteration count in a batch.
2. Call `solve_bemt` with the current `motion`.
3. Compute `M_β(ψ)`, and `M_ζ(ψ)` when lag is on.
4. Solve the harmonic balance for the new coefficients.
5. Relax: `beta_new = beta_old + relax*(beta_solved - beta_old)`.
6. Stop when the largest change is below `outer_tol_deg` in degrees, or when
   `outer_max_iter` is reached. Report the iteration count and the final change
   in `maps["flap_outer_iterations"]` and `maps["flap_outer_residual_deg"]`.
7. Raise `SolveCancelled` from the same `should_cancel` callback that
   `solve_bemt` already honors, so `PR-11` still holds.

`solve_bemt` needs the pass-through. Add the same optional keyword to its
signature, and forward it into `residual_fn`. The Pitt-Peters path
(`_pitt_peters_forcing`) also calls `element_state`, so forward it there too.

**Outputs.** Add these to `aggregate_results`, guarded so that a rigid run
reports nothing new:

| Key | Meaning | Unit |
| --- | --- | --- |
| `beta_0_deg` | coning angle | degree |
| `beta_1c_deg` | first cosine flap coefficient | degree |
| `beta_1s_deg` | first sine flap coefficient | degree |
| `beta_nc_deg`, `beta_ns_deg` | higher harmonics, one column per `n` | degree |
| `tpp_tilt_long_deg` | longitudinal tip-path-plane tilt, the negative of `beta_1c` | degree |
| `tpp_tilt_lat_deg` | lateral tip-path-plane tilt, the negative of `beta_1s` | degree |
| `nu_beta` | flap frequency ratio | - |
| `lock_number` | Lock number | - |
| `flap_inertia_kg_m2` | resolved flap inertia | kilogram metre squared |
| `zeta_0_deg`, `zeta_1c_deg`, `zeta_1s_deg` | lag coefficients | degree |
| `nu_zeta` | lag frequency ratio | - |
| `flap_outer_iterations` | outer-loop count | - |

State the sign convention in the docstring, in the documentation and in the
results-table tooltip. The convention is `beta(psi) = beta_0 + beta_1c*cos(psi)
+ beta_1s*sin(psi)`, and each tip-path-plane tilt is the negative of its first
harmonic.

Add every new key to `zbemt/nomenclature.py`, with its symbol, its unit and its
description. That module owns the whole rotation, and a second table anywhere
else breaks `PR-8`. Regenerate `tests/data/nomenclature_snapshot.json` with
`python tools/nomenclature_snapshot.py`.

**File `zbemt/studies.py`.** In `run_single_case`, after `_to_rotor`:

```python
dynamics = project.geometry.dynamics
if dynamics.flap_model == "rigid" and not dynamics.lag_enabled:
    maps = solve_bemt(...)          # the unchanged path
else:
    maps = solve_bemt_flapping(..., dynamics=dynamics, ...)
```

Everything downstream is unchanged, because `solve_bemt_flapping` returns the
same `maps` contract.

### Phase 1.4 — Cyclic pitch and the flapping trim

Flapping without cyclic pitch is of limited use. The disk tilts, and nothing
holds it. Therefore, add cyclic pitch as a control.

**File `zbemt/models.py`.** Add to `FlightCondition`:

```python
cyclic_c_deg: float = 0.0   # theta_1c, the cosine cyclic
cyclic_s_deg: float = 0.0   # theta_1s, the sine cyclic
```

**File `zbemt/studies.py`, `_to_rotor`.** The collective is a rigid offset on
the twist today. Cyclic pitch varies with azimuth, so it cannot live on the
`Rotor.theta_geom_deg` vector. Pass it to the engine inside `motion` instead,
as Phase 1.2 already provides. A rigid-blade project that sets a cyclic angle
therefore also takes the `motion` path, with `beta` held at zero.

**Trim modes.** Extend `studies.run_case_trimmed` with two modes:

- `"solve_cyclic_flapback"` finds the `θ_1c` and the `θ_1s` that drive
  `beta_1c` and `beta_1s` to zero. This is the wind-tunnel trim, and it is the
  natural default for a stability-derivative run. Solve the two-by-two system
  by Newton with a numerical Jacobian. That costs three outer solves per Newton
  step, and five to eight steps in practice.
- `"solve_collective_and_cyclic"` holds the thrust, `beta_1c` and `beta_1s` at
  targets. That is a three-by-three Newton on `θ_0`, `θ_1c` and `θ_1s`.

Report `trim_dof` and `trim_dof_value` for each solved control, matching the
convention that `compare_geometries` already uses.

### Phase 1.5 — GUI

**File `zbemt/gui/tabs/geometry_tab.py`.** Add one group box, "Blade dynamics",
below "Global Geometry" and above the "Generate Table…" button.

Inputs, in this order. Use `common.set_row_visible` for progressive
disclosure, and never `setVisible` (`PR-2`, and the field-help rule of
`CLAUDE.md`).

| Control | Type | Range | Shown when |
| --- | --- | --- | --- |
| Flap model | combo: Rigid, Hinge offset, Root spring, Offset and spring | - | always |
| Hinge offset [r/R] | double spin | 0.0 to 0.3 | the model is not Rigid |
| Flap spring [N·m/rad] | scientific spin | 0 to 1e9 | the model uses a spring |
| Inertia from | combo: Lock number, Flap inertia, Blade mass | - | the model is not Rigid |
| Lock number | double spin | 1 to 20 | inertia from Lock number |
| Flap inertia [kg·m²] | scientific spin | 1e-6 to 1e6 | inertia from Flap inertia |
| Blade mass [kg] | double spin | 1e-3 to 1e4 | inertia from Blade mass |
| Pitch-flap coupling [deg] | double spin | -60 to 60 | the model is not Rigid |
| Harmonics | spin | 1 to 5 | the model is not Rigid |
| Lead-lag | check box | - | the model is not Rigid |
| Lag spring [N·m/rad] | scientific spin | 0 to 1e9 | lead-lag is on |
| Lag damping [N·m·s/rad] | scientific spin | 0 to 1e9 | lead-lag is on |
| Lag inertia [kg·m²] | scientific spin | 1e-6 to 1e6 | lead-lag is on |
| Feed the lag rate into the in-plane speed | check box | - | lead-lag is on |
| Outer iterations | spin | 5 to 200 | the model is not Rigid |
| Outer tolerance [deg] | scientific spin | 1e-8 to 1e-1 | the model is not Rigid |
| Outer relaxation | double spin | 0.05 to 1.0 | the model is not Rigid |

Read-only outputs, in a small panel beside the inputs, recomputed on every edit
with the same 300 millisecond debounce that the preview already uses:

- the flap frequency ratio and its square, with a red label when the resonance
  guard fires;
- the resolved flap inertia and the Lock number, whichever of the two the user
  did not enter;
- the lag frequency ratio, when lead-lag is on;
- the first flap natural frequency in hertz, which is the frequency ratio times
  the angular speed over two pi. Use the rpm of the first saved case. When no
  case is saved, show a note that says so.

Every label carries a rendered symbol, not a plain-text name (`PR-4`).

**File `zbemt/gui/tabs/run_case.py`.** Add the two cyclic fields next to the
collective field. Keep them visible and disabled when the flap model is Rigid,
because a disabled control still teaches the user that the option exists
(`PR-2`).

**File `zbemt/gui/tabs/results.py`.** No structural change. The new summary
keys flow through the existing table. Add three plots to the plot menu:

- `plot_flap_response`: a polar plot of the flap angle over the azimuth, with
  the harmonics annotated;
- `plot_flap_effect_map`: two disk maps of the effective angle of attack, one
  with flapping off and one with it on, side by side;
- `plot_flap_convergence`: the outer-loop trace.

Put all three in `zbemt/viz/plots.py`. Every title states the flight
condition, as the existing plots do.

### Phase 1.6 — CLI

`--set` already reaches any dataclass field, so `--set
geometry.dynamics.flap_model=offset` works once Phase 1.1 lands. Confirm that
`_apply_set_flags` walks a nested dataclass. If it does not, extend it, and add
a parity test to `tests/test_cli_parity.py`.

Add explicit flags for the four fields that a user changes most:

```
--flap-model {rigid,offset,spring,offset_spring}
--hinge-offset FLOAT
--lock-number FLOAT
--cyclic C S
```

`--cyclic` takes two floats, the cosine cyclic and the sine cyclic, both in
degrees.

### Phase 1.7 — Tests

New file `tests/test_flapping.py`:

1. **The frequency ratio closed form.** With `e = 0.05` and no spring, the
   square of the ratio must equal `1 + 0.075/0.95`. Compare against the
   analytic value (`EN-4`).
2. **The resonance guard.** With `e = 0`, no spring and one harmonic, the
   solver raises `ValueError`, and the message names the harmonic (`EN-8`).
3. **Coning in hover.** For a hover case the harmonic balance must reproduce
   the classic uniform-inflow result, `beta_0 = gamma*C_T/(6*sigma*nu_beta^2)`,
   within a few percent. Use the analytical airfoil and a uniform inflow, so
   the comparison is fair.
4. **Flap relieves the retreating side.** Run one case at an advance ratio of
   0.3 with flapping off, then on. Assert that both hub tilting moments fall,
   and that the largest effective angle of attack on the retreating side falls.
5. **Rigid is the old path.** With `flap_model="rigid"` the summary must match
   `tests/data/golden_results.json` exactly, for every example project.
6. **Round trip.** A `BladeDynamicsDef` survives `save_bemt` and `load_bemt`.
   An old `geom.bemt` with no `dynamics` key loads with the default.
7. **Trim.** `solve_cyclic_flapback` drives both first flap harmonics below
   0.01 degree.
8. **Cancellation.** A `should_cancel` that fires on the third outer iteration
   raises `SolveCancelled` (`PR-11`).

Add a new example project `projects/flapping_rotor`, with an articulated blade
that carries a five percent hinge offset. Add the `!/projects/flapping_rotor/`
line to `.gitignore`. Regenerate `tests/data/golden_results.json` with `python
tools/golden_snapshot.py`, and read the diff. Run `python
tools/check_project_configs.py`.

### Phase 1.8 — Documentation

`docs/documentation.html` gains a section inside chapter 7, Geometry, named
"Blade dynamics". Place it after the global geometry block, because that is
where the GUI puts it (`DC-3`, `DC-7`). The section is self-contained
(`DC-4`). It gives the flap equation, the frequency ratio, the Lock number, the
harmonic balance, the delta-three coupling and the resonance limit. It then
gives the GUI, the `.bemt` and the CLI paragraphs, in that order, each wrapped
in its color span.

Chapter 10, Run Case, gains the two cyclic pitch fields. Chapter 5, The method,
gains one paragraph that states the quasi-steady assumption and links to the
new section.

Update the `bemt.py` module docstring. Item (e) of the optional-models map says
"Flapping: not implemented." Replace it with a real entry that points to
Section 4h (`EN-2`).

---

## Item 2 — Time marching: dynamic stall and Pitt-Peters

Both models already exist in the engine. Neither one is reachable. The Øye
time-march method is hidden in the GUI on purpose, and the unsteady Pitt-Peters
sweep has no entry point at all: `zbemt/validation.py:217` rejects it, and
nothing calls `bemt.run_sweep_unsteady_pitt_peters` outside the module. This
item turns both into real options and gives them one home.

Read `zbemt/bemt.py:1953` (`_oye_time_march_f`) and `zbemt/bemt.py:2672`
(`run_sweep_unsteady_pitt_peters`) before starting. The physics is written. The
work is the contract, the interfaces and the coupling.

### Phase 2.1 — Publish the Øye time-march method

**File `zbemt/gui/tabs/airfoil.py`.** Four places hide the option today. See
the comments at lines 70, 775, 811 and 2515. Undo the hiding:

- Add "Time march" to the dynamic-stall method combo, beside "Frequency".
- Reveal `dyn_revs` and `dyn_avg_last` when the method is "Time march", and
  keep them visible and disabled otherwise (`PR-2`).
- Delete the comment that calls the option an internal escape hatch.

**File `zbemt/validation.py:119`.** The rule fires an info when a time-march
field is edited while the frequency method is active. Keep it. Add one warning:
the time-march method costs `Npsi` sequential steps per revolution, so a run
with a fine azimuthal mesh and many revolutions is slow. State the cost in the
message, as a step count, not as an adjective.

Inputs and outputs of the option:

| Direction | Item |
| --- | --- |
| Input | Dynamic stall on, from the Airfoil tab |
| Input | Method: Frequency or Time march |
| Input | Revolutions marched, 1 to 100, default 8 |
| Input | Revolutions averaged, 1 to the marched count, default 3 |
| Output | The dynamic Cl and Cd maps, exactly as the frequency method returns them |
| Output | `maps["dynamic_stall_time_march_history"]`, the separation function for each marched revolution |
| Output | The new periodic-regime residual of Phase 2.2 |

### Phase 2.2 — Report whether the march settled (`EN-9`)

`_oye_time_march_f` already returns the full history. Nothing reads it.

In `apply_dynamic_stall`, after the march, compute the largest change of the
separation function between the last two revolutions:

```python
resid = float(np.max(np.abs(f_hist[-1] - f_hist[-2]))) if n_rev >= 2 else nan
maps["dynamic_stall_periodic_residual"] = resid
maps["dynamic_stall_revolutions"] = n_rev
```

Add `dynamic_stall_periodic_residual` to `aggregate_results`, and add a
validation warning when it exceeds 1e-3: the march did not reach a periodic
regime, and the remedy is more revolutions. A transient that did not settle
must not pass as a converged result.

Add a plot, `plot_dynamic_stall_history` in `zbemt/viz/plots.py`: the
separation function at one radial station against the azimuth, one curve per
marched revolution, so the reader sees the transient decay. The station is a
plot argument, with the default at `r/R = 0.75`.

### Phase 2.3 — Data contract for a transient

A transient is a sequence of flight conditions in time. It is not a batch,
because a batch holds independent points, and here each point inherits the
state of the point before it.

**File `zbemt/models.py`.** Two dataclasses:

```python
@dataclass
class ManeuverPoint:
    """One node of a prescribed trajectory. The engine keys apply, so
    `Vz` is the axial component in disk axes (see nomenclature.py)."""
    t_s: float = 0.0
    mu_x: float = 0.0
    Vz: float = 0.0
    collective_deg: float = 8.0
    cyclic_c_deg: float = 0.0
    cyclic_s_deg: float = 0.0
    rpm: Optional[float] = None


@dataclass
class ManeuverDefinition:
    """A prescribed transient (SC-12)."""
    name: str = "maneuver 1"
    points: list[ManeuverPoint] = field(default_factory=list)
    interpolation: str = "linear"     # "linear" | "hold"
    dt_s: float = 0.02                # output sample interval
    substeps_per_step: int = 8        # inflow sub-steps inside one sample
    initial_state: str = "equilibrium"  # "equilibrium" | "zero"
    march_dynamic_stall: bool = False
    march_flapping: bool = False
```

Add `maneuvers: list[ManeuverDefinition]` to `Project`, and
`"maneuvers": root/"inputs"/"maneuvers.bemt"` to `default_project_paths`. Load
and save it in `api.open_project` and `api.save_project`, next to
`optimizations`.

`ManeuverPoint` carries a `FlightCondition`-shaped payload, so
`models._to_jsonable` must rotate its axis letters for a propeller project,
exactly as it does for `FlightCondition`. Extend the `isinstance` check at
`zbemt/models.py:_to_jsonable` to cover `ManeuverPoint`, and add a round-trip
test in `tests/test_propeller_axes_convention.py` (`PA-4`).

**File `zbemt/validation.py`.** Add `validate_maneuver(maneuver, config)`:

- an error when fewer than two points exist;
- an error when the times are not strictly increasing;
- an error when a point carries no rpm and no earlier point does either;
- an error when `dt_s` is not greater than zero, or when `dt_s` is larger than
  the shortest interval between two points;
- a warning when the marched interval covers fewer than five rotor
  revolutions, because the inflow states need that long to settle;
- a warning when `march_dynamic_stall` is on and the azimuthal mesh is finer
  than 180 stations, because the cost is the product of the two.

Relax the rule at `zbemt/validation.py:217`. Today `pitt_peters_unsteady` is an
error on every path. Make it an error only on the case path and the batch path,
and make it the *required* value on the maneuver path. Add a matching test to
`tests/test_validation.py`, which today asserts the blanket rejection.

### Phase 2.4 — Engine, generalize the unsteady sweep

`run_sweep_unsteady_pitt_peters` accepts `(t, mu_x, Vz)` tuples only. A
maneuver also changes the collective, the cyclic and the rpm. Generalize it:

1. Change the signature to `run_maneuver(rotor_builder, airfoil, cfg, samples,
   ...)`, where `samples` is a list of resolved `ManeuverPoint`s and
   `rotor_builder(point)` returns the `Rotor` for that point. The rpm and the
   collective both live on the `Rotor`, so a change in either one needs a new
   `Rotor` object. Keep the old name as a thin wrapper, so any script that
   calls it keeps working.
2. Keep the exponential integrator. The docstring at `zbemt/bemt.py:2631`
   explains why plain Runge-Kutta is unstable here. Do not replace it.
3. When the rpm changes between samples, the non-dimensional time step
   `dtau = Omega*dt/n_sub` must use the rpm of the sample being entered, not
   the one being left. State this in the docstring.
4. Record, per sample, the state vector, the marched interval and the sub-step
   count, so `EN-9` can be satisfied by the report.

**Sampling.** Build the sample list from the definition before the march:
resample the trajectory onto a uniform `dt_s` grid, by linear interpolation or
by a zero-order hold, according to `interpolation`. Put this in
`zbemt/studies.py` as `_maneuver_samples(definition)`, because it is
orchestration and not physics (`AR-2`).

**Initial state.** With `initial_state="equilibrium"`, solve the steady
Pitt-Peters problem at the first point and start from that state vector. With
`"zero"`, start from zeros, and expect a start-up transient. Say which one ran,
in the summary and in the report.

### Phase 2.5 — Orchestration and the boundary

**File `zbemt/studies.py`.** Add:

```python
def run_maneuver(project, definition, *, on_sample_done=None,
                 should_cancel=None) -> tuple[pd.DataFrame, list[dict]]:
```

It builds the config, forces `inflow_field_model="pitt_peters_unsteady"`,
builds the sample list, calls the engine, and returns the time history and the
per-sample maps. It reports progress through `on_sample_done(done, total, row)`
and honors `should_cancel` between samples (`PR-11`).

**File `zbemt/api.py`.** Add `run_maneuver(project, definition, **kwargs)`,
`get_maneuver(project, name)` and `export_maneuver_csv(history, path)`. `api`
stays the only boundary (`AR-1`).

`generate_report` gains a transient branch: when the results carry a time
column, the summary table becomes a time history, and the report opens with the
time plots instead of the disk maps. Keep `RP-1`, one implementation for the
GUI and the CLI.

### Phase 2.6 — Couple the other two marched states

Two options ride on the same trajectory. Both are off by default.

- `march_dynamic_stall`. At each sample, the separation function starts from
  the value that the previous sample left, instead of restarting from the
  static value. Thread `f_prev` through the loop, and give `_oye_time_march_f`
  an optional `f_init` argument. With one revolution per sample this makes the
  separation state continuous along the trajectory.
- `march_flapping`. At each sample, run the Item 1 outer loop, warm-started
  from the previous sample's coefficients. The flap response stays a periodic
  quasi-steady solution inside each sample. State that limit plainly in the
  documentation: this is not a flap transient, and it does not capture the flap
  mode.

Both options are only offered when their own model is on. When dynamic stall is
off, the `march_dynamic_stall` check box stays visible and disabled.

### Phase 2.7 — GUI, the Transient window

A new top-level window, opened from the Tools button, beside the Geometry
Designer. Build it as `zbemt/gui/tabs/transient_window.py`, a `QWidget` with
`Qt.WindowType.Window`, wired in `zbemt/gui/app.py` the same way the designer
window is wired at `zbemt/gui/app.py:417`.

The Tools button becomes a menu, because it now opens four windows: Geometry
Designer, Design Optimization, Transient Simulation and Stability Derivatives.
Change `FlowIndicatorBar.tools_requested` to carry the requested window name,
and update `tests/test_requirements_guardrails.py`, which asserts the
documentation states the menu path.

**Page 1, Trajectory.**

| Direction | Item | Detail |
| --- | --- | --- |
| Input | Maneuver list | The project's saved maneuvers. New, Duplicate, Rename, Delete. |
| Input | Point table | One row per node: time, in-plane advance, axial speed, collective, both cyclic angles, rpm. Editable cells, Add and Remove buttons. |
| Input | Build from | A helper that fills the table from two saved cases and a ramp duration, so a transition needs three clicks. |
| Input | Interpolation | Linear or Hold. |
| Input | Sample interval | Seconds. |
| Input | Sub-steps per sample | 1 to 200. |
| Input | Initial state | Equilibrium or Zero. |
| Input | March dynamic stall | Check box, enabled only when dynamic stall is on. |
| Input | March flapping | Check box, enabled only when the flap model is not Rigid. |
| Output | Trajectory preview | Two stacked plots against time: the advance ratio and the axial speed on the first, the collective and the cyclic angles on the second. Redrawn with a 400 millisecond debounce. |
| Output | Cost estimate | The sample count, the sub-step count and the resulting solver-call count, stated as numbers. |
| Output | Validation panel | The `Issue`s from `validate_maneuver`, in the same style as the Config tab. |

**Page 2, Run and results.**

| Direction | Item | Detail |
| --- | --- | --- |
| Input | Run and Cancel buttons | The run goes through a `ManeuverWorker` in `zbemt/gui/workers.py`, built on the `CompareWorker` pattern (`PR-11`). |
| Output | Progress bar | Sample count and elapsed time. |
| Output | Time-history table | One row per sample: time, thrust coefficient, torque coefficient, power coefficient, the three inflow states, and the flap coefficients when flapping is marched. |
| Output | Time-history plots | Four panels: the loads against time, the inflow states against time, the commanded controls against time, and the lag of the inflow behind its steady value. |
| Output | Steady comparison | An overlay that runs the same trajectory with the steady Pitt-Peters model, point by point, and draws both curves. This is the figure that shows what the transient adds. Put it behind a check box, because it doubles the cost. |
| Output | Disk map at a chosen time | A slider over the samples, and the same disk maps that the Results tab draws. |
| Output | Export | CSV of the time history, and an HTML report through `api.generate_report`. |

Every plot title states the maneuver name and the trajectory endpoints.

**Field help.** Every input above needs a popup and a documentation anchor
(`PR-3`). Run `python tools/field_index.py --write` after the window is built.

### Phase 2.8 — CLI

```
--maneuver [NAME]        run one saved maneuver; bare flag runs the first
--maneuver-file PATH     run a maneuver from a .bemt file outside the project
--list-maneuvers         print the saved maneuver names
--maneuver-dt FLOAT      override the sample interval
--maneuver-substeps INT  override the sub-step count
```

Follow the shape of `_run_optimize` at `zbemt/cli.py:914`, including the bare
form that runs the first entry and the error message that lists the available
names. Add the flags to the mutually exclusive action check at
`zbemt/cli.py:1020`.

### Phase 2.9 — Tests

New file `tests/test_transient.py`:

1. **A constant trajectory reaches the steady answer.** March a trajectory that
   holds one condition for twenty revolutions. The final state vector must
   match the steady Pitt-Peters solution to within 1e-4.
2. **The inflow lags.** Step the collective at the midpoint. The thrust
   coefficient must overshoot its steady value and then settle, and the settling
   time must scale with the inflow time constant.
3. **The exponential integrator is stable with one sub-step.** Repeat test 1
   with `substeps_per_step=1` and assert that nothing is not finite. The
   docstring at `zbemt/bemt.py:2631` claims this. Prove it (`QR-8`).
4. **Sampling.** Linear interpolation and hold produce the expected sample
   tables for a three-point trajectory.
5. **Validation.** A non-monotonic time column, a missing rpm and a sample
   interval larger than the shortest node interval each raise the right
   `Issue`.
6. **The unsteady model stays rejected on the case path.** The existing test at
   `tests/test_validation.py:95` must keep passing in its new, narrower form.
7. **Time march equals frequency for a slow variation.** At a low advance
   ratio, where the angle of attack barely changes with azimuth, the two Øye
   methods must agree to within one percent. This is the check that the
   time-march path is not merely different (`QR-8`).
8. **The periodic residual falls with more revolutions.** Run with two, four
   and eight revolutions, and assert that the residual decreases.
9. **Cancellation** between samples raises `SolveCancelled`.

Add a GUI smoke test in `tests/test_gui_smoke.py` that opens the transient
window, and a responsiveness test in `tests/test_gui_responsiveness.py` that
starts a run and cancels it.

Add an example project `projects/transition_evtol` that carries one saved
maneuver: a hover-to-cruise transition over four seconds. Whitelist it in
`.gitignore`.

### Phase 2.10 — Documentation

The tools family grows from one window to four, so chapter 13 becomes a family
of chapters. The new order is:

```
13  Geometry Variation Studies
14  Design Optimization           (Item 3)
15  Transient Simulation          (Item 2)
16  Stability Derivatives         (Item 4)
17  Command-line reference
18  Limitations
```

Renumber the two reference chapters, and run `python tools/build_toc.py
--write`. `tests/test_documentation.py` checks that heading numbers match their
chapter and depth, and that every prose reference resolves, so the renumbering
must be complete before the suite passes.

Chapter 15 is self-contained (`DC-4`, and rule 12 of `CLAUDE.md`). It gives the finite-state inflow
equation of motion, the exponential integrator and the reason for it, the
sampling rules, the initial-state choice, the two coupled marched states and
their limits, and then the GUI, `.bemt` and CLI paragraphs for every field.

Chapter 8, Airfoil, already documents the time-march fields at lines 4739 to
4750. Correct the wording: it must now say that the GUI offers the method, and
it must state the periodic residual that Phase 2.2 adds.

---

## Item 3 — Design optimization window

`studies.optimize_design` exists and works. It handles one objective, with
Powell or Nelder-Mead, and the GUI does not offer it. `zbemt/gui/workers.py:184`
already carries an `OptimizeWorker` that nothing calls. This item adds a second
algorithm family, a second objective, constraints, and a window.

### Phase 3.1 — Data contract

**File `zbemt/models.py`.** Two new dataclasses, and an extended
`OptimizationDefinition` that stays backward compatible with the files that
exist today.

```python
@dataclass
class ObjectiveDef:
    """One objective of a design study."""
    key: str = "FM"                  # any summary key
    kind: str = "maximize"           # "maximize" | "minimize"
    weight: float = 1.0              # used only by the weighted-sum method


@dataclass
class ConstraintDef:
    """One inequality constraint on a summary key."""
    key: str = "CT"
    operator: str = ">="             # ">=" | "<=" | "=="
    value: float = 0.0
    tolerance: float = 0.0           # band for "=="
```

Extend `OptimizationDefinition`:

```python
    objectives: list[ObjectiveDef] = field(default_factory=list)
    constraints: list[ConstraintDef] = field(default_factory=list)
    algorithm: str = "powell"    # "powell" | "nelder-mead" | "nsga2" | "de"
    population: int = 40
    generations: int = 25
    seed: int = 0
    crossover_eta: float = 15.0
    mutation_eta: float = 20.0
    mutation_rate: float = 0.0   # 0 means one over the variable count
    parallel_workers: int = 1
```

Migration. A file written before this change has `objective_key` and
`objective_kind` and no `objectives`. On load, when `objectives` is empty and
`objective_key` is set, build a one-element list from the two old fields. Put
the migration beside `migrate_config_raw` in `models.py`, and test it in
`tests/test_models.py`. Keep writing both forms for one release, so an older
build can still read the file.

**File `zbemt/validation.py`.** Add `validate_optimization(definition,
project)`:

- an error when no variable is defined, or when a bound pair is not finite and
  increasing (`studies.optimize_design` already raises for this; move the rule
  into validation so the GUI can show it before the run);
- an error when a genetic algorithm is chosen with fewer than eight
  individuals;
- an error when two objectives are given to Powell or to Nelder-Mead;
- an error when an objective key or a constraint key is not a summary key;
- a warning when the evaluation count, that is the population times the
  generations, exceeds 2000, stating the count and an estimated wall time from
  one timed evaluation.

### Phase 3.2 — The algorithm module

New file `zbemt/optimization.py`. It holds the search algorithms and nothing
else. It must not import `studies`, `api` or Qt. It receives an evaluation
callable and returns a result object, so it stays testable against analytic
functions.

Do not add a dependency. `scipy` has no multi-objective optimizer, and `PR-7`
asks that an optional dependency degrade gracefully rather than become
required. NSGA-II is about 150 lines of numpy.

```python
def nsga2(evaluate, lower, upper, integer_mask, *, n_objectives,
          population=40, generations=25, seed=0, crossover_eta=15.0,
          mutation_eta=20.0, mutation_rate=None, on_generation=None,
          should_cancel=None) -> ParetoOutcome:
```

The pieces, each a module-level function with its own test:

1. `_fast_non_dominated_sort(F)` returns the front index of every individual.
   Standard Deb sorting, order `O(M·N²)`.
2. `_crowding_distance(F, front)` returns the crowding distance inside one
   front, with the boundary points at infinity.
3. `_constrained_dominates(i, j, F, G)` implements constraint domination: a
   feasible individual always dominates an infeasible one, two infeasible ones
   compare by total violation, and two feasible ones compare by objective
   domination.
4. `_tournament(rng, rank, crowd)` is the binary tournament on rank first and
   crowding distance second.
5. `_sbx_crossover(rng, p1, p2, lower, upper, eta)` is simulated binary
   crossover.
6. `_polynomial_mutation(rng, x, lower, upper, eta, rate)`.
7. `_repair_integers(x, integer_mask, lower, upper)` rounds and clips the
   integer variables, so `n_blades` stays whole. `models.INTEGER_PARAMS`
   already names them.

Determinism. Use one `numpy.random.default_rng(seed)`. The same seed and the
same definition must give the same front, byte for byte. Test it.

Also add `differential_evolution` as the single-objective global option, by
calling `scipy.optimize.differential_evolution` with the same interface. That
gives the user a global search that does not need a population front.

`ParetoOutcome` returns:

```python
@dataclass
class ParetoOutcome:
    front_params: list[dict]        # the non-dominated designs
    front_values: list[dict]        # their objective values, by key
    front_constraints: list[dict]   # their constraint values, by key
    all_evaluations: list[dict]     # every evaluation, for the history plots
    generations_run: int
    n_evals: int
    seed: int
    message: str
    hypervolume_history: list[float]
```

Hypervolume. For two objectives, compute the exact hypervolume against a
reference point taken as the worst value seen in each objective, scaled by 1.1.
For one objective, record the best value instead. The history is what tells the
user whether the search converged.

### Phase 3.3 — Orchestration

**File `zbemt/studies.py`.** Add
`optimize_design_multi(project, definition, *, on_progress=None,
should_cancel=None)`. Reuse the evaluation body of `optimize_design`, which
already regenerates the geometry with `variant_geometry` and runs one case. Two
changes:

1. The evaluation returns a vector of objective values and a vector of
   constraint violations, not one scalar.
2. A failed evaluation returns a not-a-number vector, and the algorithm treats
   it as maximally infeasible instead of penalizing it with a magic number.
   The current penalty of `1e6 + eval_count` at `zbemt/studies.py` is a
   single-objective device and does not carry over.

Keep `optimize_design` as it is, for `SC-8`. Route both through one shared
`_evaluate_variant(project, condition, params)` helper, so the two paths cannot
drift.

**Parallel evaluation.** A generation of forty designs is forty independent
solves. Add an optional `ProcessPoolExecutor` path, chosen by
`parallel_workers`. Each worker rebuilds the project from its dataclasses, so
nothing but plain data crosses the process boundary. Fall back to the serial
path, with a warning and no error, when the pool cannot start (`PR-7`). Do not
make this the default until the tests pass on Windows, where the spawn start
method re-imports the module.

**File `zbemt/api.py`.** Add `optimize_design_multi` and
`export_pareto_csv(outcome, path)`, and extend
`generate_optimization_report` to draw the front.

### Phase 3.4 — GUI, the Design Optimization window

New file `zbemt/gui/tabs/optimizer_window.py`. Four pages, in a `QTabWidget`,
following the designer window's own layout.

**Page 1, Variables.**

| Direction | Item | Detail |
| --- | --- | --- |
| Input | Study list | The project's saved studies. New, Duplicate, Rename, Delete, Save. |
| Input | Variable table | One row per variable: parameter combo over `models.GEOMETRY_PARAMS`, lower bound, upper bound. Add and Remove buttons. |
| Input | Seed from base | A button that fills the bounds with plus or minus thirty percent around the project's own planform value. |
| Output | Bound preview | A planform overlay that draws the base blade, the lower-bound blade and the upper-bound blade, so the search space is visible before the run. |
| Output | Feasibility note | A line that states the variable count, and the fact that an integer variable is rounded. |

**Page 2, Objectives and constraints.**

| Direction | Item | Detail |
| --- | --- | --- |
| Input | Objective table | One or two rows: summary key combo, Maximize or Minimize. Two rows enable the Pareto path and disable Powell and Nelder-Mead. |
| Input | Constraint table | Any number of rows: summary key, operator, value. |
| Input | Flight condition | A saved case, or a manual condition with the same fields the Run Case tab shows, through the shared widget in `zbemt/gui/widgets.py`. |
| Input | Trim before evaluating | Off, Thrust or `CT`. This is the same fairness argument the geometry comparison makes: compare efficiency at equal loading. |
| Output | Objective preview | The value of every chosen key for the base geometry at that condition, from one evaluation, so the user sees the starting point and the units. |

**Page 3, Algorithm.**

| Direction | Item | Detail |
| --- | --- | --- |
| Input | Algorithm | Powell, Nelder-Mead, Differential evolution, NSGA-II. Shown with the note that the first two accept one objective only. |
| Input | Population | 8 to 500, shown for the population methods. |
| Input | Generations | 1 to 500, shown for the population methods. |
| Input | Maximum evaluations | Shown for Powell and Nelder-Mead. |
| Input | Seed | Integer. |
| Input | Crossover and mutation | Two spin boxes, shown for NSGA-II only, with the defaults 15 and 20. |
| Input | Parallel workers | 1 to the processor count. |
| Output | Cost estimate | The evaluation count, and the estimated wall time from one timed base evaluation. |

**Page 4, Run and results.**

| Direction | Item | Detail |
| --- | --- | --- |
| Input | Run and Cancel | Through the existing `OptimizeWorker`, extended for the multi-objective path (`PR-11`). |
| Output | Progress | Generation count, evaluation count, and the best value or the front size. |
| Output | Pareto plot | The two objectives against each other. Every evaluation as a faint point, the current front as a line with markers. Click a marker to select that design. |
| Output | Convergence plot | Hypervolume against generation for two objectives, or the best value against evaluation for one. |
| Output | Front table | One row per non-dominated design: every variable, every objective, every constraint. Sortable. |
| Output | Selected design panel | The planform of the selected design drawn over the base, and its full summary table. |
| Output | Send to Geometry Designer | Adds the selected designs to the designer window's variant table as absolute-geometry rows, which `_append_absolute_row` already supports. |
| Output | Apply to project | Writes the selected geometry into the open project, marks it unsaved, and never touches disk by itself (`TB-3`). |
| Output | Export | The front as CSV, and an HTML report through `api.generate_optimization_report`. |

**Plots.** Add to `zbemt/viz/plots.py`: `plot_pareto_front`,
`plot_optimization_convergence` and `plot_parallel_coordinates`. The last one
draws every front member as a polyline across the normalized variable axes,
which is how a reader sees what the front members have in common. Every title
states the flight condition and the algorithm.

### Phase 3.5 — CLI

Extend `--optimize` rather than adding a second flag. The definition already
says which algorithm to run.

```
--optimize [NAME]
--algorithm {powell,nelder-mead,de,nsga2}
--population INT
--generations INT
--seed INT
--workers INT
--pareto-csv PATH
```

`_run_optimize` at `zbemt/cli.py:914` branches on the definition's algorithm
and prints the front instead of the single best design when the run is
multi-objective. Print the front as a table, one row per design, with the
variables and the objectives.

### Phase 3.6 — Tests

New file `tests/test_optimization.py`, against analytic functions first, so the
algorithm is tested without the solver:

1. **Non-dominated sorting** on a hand-built set with a known front.
2. **Crowding distance** boundary points are infinite, and interior points
   match the hand-computed value.
3. **Constraint domination**: a feasible design beats an infeasible one, and
   two infeasible ones order by total violation.
4. **ZDT1.** NSGA-II on the standard two-objective test problem must reach a
   front whose generational distance to the analytic front is below a stated
   threshold, within 50 generations of 40 individuals.
5. **Determinism.** The same seed gives the same front.
6. **Integer repair.** A variable in `INTEGER_PARAMS` is whole in every
   individual of every generation.
7. **Cancellation** between generations raises `SolveCancelled`.

Then against the engine, in `tests/test_studies.py`:

8. **One objective, two paths.** Powell and NSGA-II on the same single-objective
   study must find figures of merit within two percent of each other.
9. **A constraint binds.** With a thrust-coefficient floor above what the base
   geometry reaches, every front member must satisfy it, or the outcome must
   report that no feasible design was found.
10. **Migration.** An `optimizations.bemt` in the old schema loads, runs and
    saves in the new schema.

GUI tests, in `tests/test_gui_smoke.py` and a new
`tests/test_optimizer_window.py`, mirroring `tests/test_designer_window.py`:
the window opens with an empty project, the algorithm page hides the fields
that do not apply, a two-objective study disables Powell, and the front table
fills after a short run.

### Phase 3.7 — Documentation

New chapter 14, Design Optimization, in the tools family. Self-contained: the
search problem, the difference between a weighted sum and a Pareto front, the
domination rule, the constraint-domination rule, the crossover and mutation
operators with their distribution indices, the hypervolume measure, and the
determinism guarantee. Then one section per field, each with its GUI, `.bemt`
and CLI paragraphs.

Update `SC-8` in the requirements as Phase 0.3 says, and cite `SC-13` in the
new module docstrings.

---

## Item 4 — Stability and control derivatives

A derivative is the change of a hub load for a small change of one state or one
control, about a trim point. The engine already produces every load. The work
is the perturbation set, the missing state inputs, the finite-difference
machinery and the window.

This item needs Item 1. A pitch-rate derivative with no flap freedom reports
the aerodynamic term only, and it misses the flap response, which for an
articulated rotor is the larger part.

### 4.0 Physics and notation

Loads. Work in hub axes: `x` forward, `y` to the right, `z` along the shaft.
`aggregate_results` already returns the thrust, the in-plane force `H`, the
side force `Y`, the two hub tilting moments and the torque.

Hub moment from the hinge offset and the spring. The tilting moments that
`aggregate_results` computes today come from the thrust distribution only. With
an offset hinge or a root spring, a second path carries moment into the hub,
and for a hingeless rotor it is the larger one:

```
M_hub_long = (Nb/2)*I_beta*Omega^2*(nu_beta^2 - 1)*beta_1c
M_hub_lat  = (Nb/2)*I_beta*Omega^2*(nu_beta^2 - 1)*beta_1s
```

Add these two to `aggregate_results`, as `Mx_hub` and `My_hub`, and add the
totals `Mx_total` and `My_total`. They belong to Item 1's output set. Do them
there if Item 1 is still open, and here if it already landed.

States and controls. The derivative set is:

| Symbol | Quantity | Reaches the engine as |
| --- | --- | --- |
| `u` | longitudinal speed | the in-plane advance ratio, at a sideslip angle of zero |
| `v` | lateral speed | the in-plane advance ratio, at a sideslip angle of ninety degrees |
| `w` | axial speed | the axial velocity |
| `p` | roll rate | a new hub angular-rate input |
| `q` | pitch rate | a new hub angular-rate input |
| `Omega` | rotor speed | the rpm |
| `theta_0` | collective | the collective angle |
| `theta_1c` | cosine cyclic | Item 1, Phase 1.4 |
| `theta_1s` | sine cyclic | Item 1, Phase 1.4 |

The yaw rate has no first-order effect on an isolated rotor with a vertical
shaft, so it is out of the set. State that in the documentation instead of
leaving it unexplained.

Two engine inputs are missing today.

**Sideslip.** `U_T = Omega*r + V_inf*sin(psi)` fixes the free-stream direction.
A lateral velocity needs an in-plane direction. Add a sideslip angle
`psi_w`, and use `sin(psi - psi_w)` in the in-plane speed and `cos(psi -
psi_w)` in the radial-flow correction. The default of zero reproduces every
result that exists today, which the golden snapshot must confirm.

**Hub angular rates.** A hub that rotates makes each blade element move out of
the disk plane:

```
U_P = U_P + r*(q*cos(psi) - p*sin(psi))
```

The flap equation gains a Coriolis forcing from the same rates:

```
Mbar_gyro(psi) = 2*(q*sin(psi) + p*cos(psi)) / Omega
```

Derive the signs from the rotating-frame kinematics before writing the code,
and then prove them with the test in Phase 4.5: in hover, a steady pitch rate
must produce a flap response that lags by ninety degrees, and the resulting hub
moment must oppose the rate. A pitch damping derivative with the wrong sign is
the failure mode this item must not ship.

Finite differences. Use a central difference for every derivative:

```
dF/dx = (F(x0 + h) - F(x0 - h)) / (2*h)
```

Step size. A central difference has a truncation error of order `h²` and a
round-off error of order `eps/h`, so the step must be stated, not guessed. Give
each state its own default step, in physical units, and let the user change it:

| State | Default step |
| --- | --- |
| `u`, `v`, `w` | 0.5 metre per second |
| `p`, `q` | 0.02 radian per second |
| `Omega` | 0.5 percent of the trim rpm |
| `theta_0`, `theta_1c`, `theta_1s` | 0.1 degree |

Error estimate. Repeat every derivative at half the step. Report the difference
between the two estimates as the step-size error. A derivative whose two
estimates differ by more than five percent is marked in the table, and the
remedy stated in the message is a larger step, because the cause is almost
always solver noise, not truncation.

Non-dimensional form. Report both. The dimensional derivative is in newtons per
metre per second, and so on. The non-dimensional form divides the force by
`rho*A*(Omega*R)^2`, the moment by `rho*A*(Omega*R)^2*R`, the linear speed by
`Omega*R`, and the angular rate by `Omega`. `zbemt/nomenclature.py` owns the
symbols and the units, as always.

### Phase 4.1 — Engine inputs

**File `zbemt/bemt.py`.** Add the sideslip angle to `BEMTConfig` as
`inflow_sideslip_deg: float = 0.0`, and the hub rates to the `motion`
dictionary of Item 1, Phase 1.2, as `p_rate` and `q_rate` in radians per
second. A rigid-blade project that sets a hub rate takes the `motion` path with
the flap angle held at zero, exactly as a cyclic angle does.

Add the gyroscopic forcing to `solve_bemt_flapping`, added to the aerodynamic
flap moment before the harmonic balance.

**File `zbemt/models.py`.** Add `p_rate_deg_s` and `q_rate_deg_s` to
`FlightCondition`, both defaulting to zero, and `sideslip_deg` beside them.
These are perturbation inputs, so they belong to the condition and not to the
configuration.

### Phase 4.2 — The derivative engine

New file `zbemt/derivatives.py`. It holds the perturbation logic and nothing
else. It calls `studies.run_single_case` through a callable it receives, so the
layering holds (`AR-1`, `AR-2`).

```python
@dataclass
class DerivativeRequest:
    """One stability-derivative study (SC-14)."""
    name: str = "derivatives 1"
    condition: Optional[FlightCondition] = None
    trim: str = "cyclic_flapback"   # "none" | "thrust" | "cyclic_flapback"
    states: list[str] = field(default_factory=list)      # u, v, w, p, q, Omega
    controls: list[str] = field(default_factory=list)    # theta_0, theta_1c, theta_1s
    outputs: list[str] = field(default_factory=list)     # Thrust, H, Y, Mx_total, My_total, Torque
    steps: dict = field(default_factory=dict)            # per-state override
    richardson_check: bool = True
    parallel_workers: int = 1


@dataclass
class DerivativeOutcome:
    matrix: dict            # {(output, variable): value}
    matrix_nondim: dict
    step_used: dict
    step_error: dict        # {(output, variable): relative difference}
    trim_state: dict        # the controls and loads at the trim point
    n_solves: int
    message: str
```

`compute_derivatives(project, request, *, on_progress=None,
should_cancel=None)`:

1. Trim first, unless the trim is `"none"`. Reuse `studies.run_case_trimmed`
   with the mode that Item 1, Phase 1.4 adds. Record the trimmed controls.
2. Run the trim point once, and keep its loads as the reference row.
3. For every variable, run two cases at plus and minus the step, and one more
   pair at half the step when the Richardson check is on. That is two solves per
   variable, or four with the check.
4. Assemble the matrix, the non-dimensional matrix and the error table.
5. Report progress after every solve, and honor `should_cancel` between solves.

Cost. Nine variables with the check is thirty-six solves, plus the trim. Each
solve of a flapping rotor is an outer loop of five to ten inner solves. State
the count in the window before the run starts.

The perturbations are independent, so the parallel path of Item 3, Phase 3.3
applies unchanged. Reuse it.

**File `zbemt/api.py`.** Add `compute_derivatives`,
`export_derivatives_csv(outcome, path)` and
`generate_derivatives_report(outcome, path, *, project=None)`.

**Persistence.** Add `derivatives: list[DerivativeRequest]` to `Project`, and
`inputs/derivatives.bemt` to `default_project_paths`, following the pattern of
`optimizations`.

### Phase 4.3 — Optional, the vehicle state matrix

A rotor derivative set becomes a flight-dynamics model only after the vehicle
mass properties join it. Offer this as a second, clearly separated block, and
state its limits: one rotor, no fuselage, no tail, no engine dynamics.

Inputs: the vehicle mass, the three moments of inertia, the hub position
relative to the center of gravity, and the gravity term. Output: the `A` and
`B` matrices of the linearized six-degree-of-freedom model built from the hub
derivatives, and their eigenvalues.

Draw the eigenvalues on the complex plane, and name the classic modes when they
can be identified: the phugoid, the pitch subsidence, the roll subsidence and
the Dutch roll. Label a mode only when its damping and frequency fall in the
expected band, and otherwise leave it unnamed. A wrong label is worse than no
label.

Keep this block behind a check box that is off by default, and state in the
documentation that the model omits the fuselage and the tail.

### Phase 4.4 — GUI, the Stability Derivatives window

New file `zbemt/gui/tabs/stability_window.py`, opened from the Tools menu that
Item 2, Phase 2.7 introduces. Three pages.

**Page 1, Trim point.**

| Direction | Item | Detail |
| --- | --- | --- |
| Input | Study list | The project's saved derivative requests. New, Duplicate, Rename, Delete, Save. |
| Input | Flight condition | A saved case, or a manual condition, through the shared condition widget. |
| Input | Trim | None, Thrust, or Zero flapping. Zero flapping is the default, and it is disabled when the flap model is Rigid. |
| Input | Trim target | Thrust or thrust coefficient, shown only for the thrust trim. |
| Output | Trim result | The solved controls, the loads and the flap coefficients at the trim point. A button runs the trim alone, so the user can check it before spending the full run. |
| Output | Validation panel | The `Issue`s from the project and from the request. |

**Page 2, Perturbations.**

| Direction | Item | Detail |
| --- | --- | --- |
| Input | State check boxes | Longitudinal, lateral and axial speed, roll rate, pitch rate, rotor speed. A rate is visible and disabled when the flap model is Rigid, with a tooltip that says why. |
| Input | Control check boxes | Collective, and both cyclic angles. A cyclic control is visible and disabled when the flap model is Rigid. |
| Input | Output check boxes | Thrust, in-plane force, side force, both hub moments, torque. |
| Input | Step table | One row per selected variable: the step, in its own unit, with the default filled in. |
| Input | Richardson check | Check box, on by default. |
| Input | Parallel workers | 1 to the processor count. |
| Output | Cost estimate | The solve count and the estimated wall time, from one timed trim solve. |

**Page 3, Run and results.**

| Direction | Item | Detail |
| --- | --- | --- |
| Input | Run and Cancel | Through a `DerivativeWorker` in `zbemt/gui/workers.py` (`PR-11`). |
| Output | Derivative matrix | Outputs down the rows, variables across the columns. Each cell shows the value and, on hover, the step, both one-sided values and the step-size error. A cell whose error exceeds five percent is marked. |
| Output | Dimensional or non-dimensional | A radio pair that switches the whole table, without re-running. |
| Output | Bar chart | One output at a time, its derivatives against every variable, so the dominant term is visible. |
| Output | Sign check panel | A short list of the derivatives whose sign is known from theory, with a pass or a fail beside each: the heave damping is negative, the pitch damping is negative, the thrust rises with collective. This panel is the reason the window is trustworthy. |
| Output | Vehicle block | Phase 4.3, behind its check box: the mass inputs, the two matrices, the eigenvalue plot. |
| Output | Export | CSV of the matrix, and an HTML report. |

### Phase 4.5 — Tests

New file `tests/test_derivatives.py`:

1. **A zero step is rejected**, and a negative step is rejected, with a message
   that names the variable.
2. **Heave damping is negative.** In hover, the derivative of thrust with
   respect to axial speed must be negative. This is the most basic rotor
   result, and it needs no reference data (`QR-8`).
3. **Thrust rises with collective**, in hover and in forward flight.
4. **Pitch damping is negative** for a rotor with a hinge offset, in hover.
   This is the test that fixes the sign of the gyroscopic term.
5. **The flap response to a pitch rate lags by ninety degrees** in hover, to
   within five degrees.
6. **Linearity.** Halving the step must change a derivative by less than the
   reported step-size error. This checks the finite-difference machinery
   against itself.
7. **The sideslip default is inert.** With a sideslip of zero, every example
   project must reproduce `tests/data/golden_results.json` exactly.
8. **Sideslip of ninety degrees equals a rotation.** A case at a sideslip of
   ninety degrees must give the same thrust and torque as the same case at zero
   sideslip, because the rotor is axisymmetric in that respect. The in-plane
   force and the side force must swap.
9. **Cancellation** between solves raises `SolveCancelled`.

Add a GUI smoke test and a responsiveness test, as for the other two windows.

### Phase 4.6 — Documentation

New chapter 16, Stability Derivatives. Self-contained: the definition of a
derivative, the trim point and why it matters, the finite-difference formula,
the step-size trade-off, the Richardson estimate, the non-dimensional
convention, the state and control set, the reason the yaw rate is absent, the
hub-moment path through the hinge offset, and the limits of the optional
vehicle model.

---

## Item 5 — Review of the geometry comparison mode

The comparison mode works and its scope is documented in `SC-7`. It does not
need a rewrite. It needs six fixes, and it would gain from three additions.
Below is what the review found, with the evidence.

### 5.0 Findings

**Correctness and honesty.**

1. **No variant is validated.** `studies.compare_geometries` checks the rpm of
   every condition, and nothing else. A variant with a negative chord, a
   non-monotonic radial table or a root cutout above the tip runs to a number,
   and the number reads as a result. `geometry._validate_and_sort_table`
   already exists. Nothing calls it on a variant.
2. **Two chord cells are silently dropped.** In
   `designer_window._row_overrides`, a rectangular base maps the root chord and
   the tip chord onto one parameter, `chord_norm`, taking whichever cell is
   filled. An elliptic base reads the root-chord cell as the peak chord and
   ignores the tip-chord cell. The cells stay editable in both cases. The user
   types a value, sees it accepted, and it changes nothing.
3. **A near-zero endpoint changes the request silently.**
   `_apply_table_space_planform` divides by the base chord at each endpoint and
   falls back to a factor of one when the endpoint is near zero. The blade then
   does not have the requested endpoint chord, and nothing says so.
4. **Chord targets compose in a fixed, undocumented order.** The same function
   applies the endpoint rescale, then the mean-chord scale, then the peak-chord
   scale. Giving two of the three produces a blade that satisfies only the
   last. The docstring does not say this.

**Cost and scale.**

5. **The run is serial and unbudgeted.** Ten variants over twenty conditions
   with a thrust trim is about three thousand solves, started by one button
   with no estimate and no worker count.
6. **Duplicate rows run twice.** Nothing compares a row's resolved geometry
   against the rows above it.

**Reach.**

7. **The ranking and the overlay read fixed key lists.**
   `_RANKING_FIELDS` holds seven keys and `_OVERLAY_FIELDS` holds six. Every
   other summary key is unreachable, including every key that Items 1, 2 and 4
   add.
8. **Only the planform varies.** A variant cannot carry a different airfoil, a
   different blade dynamics block or a different mesh. Comparing two blades that
   differ by their airfoil is a normal design question, and the window cannot
   ask it.
9. **Nothing is persisted.** `SC-7` states this on purpose. It is still the
   most common complaint a user will have: a comparison cannot be re-run,
   reviewed or versioned.

### 5.1 Phase — Fix what is wrong

Do these first. They are small and they are corrections, so each one needs a
regression test that fails before the fix (`QR-1`).

1. Call `validation.validate_project` on every resolved variant inside
   `compare_geometries`, before the first solve. Raise a `ValueError` that names
   the variant and the issue. In the window, show the issues in a panel and
   disable the Run button while an error stands.
2. In the variant table, disable the cell that the base planform cannot use,
   and give the disabled cell a tooltip that says why. A rectangular base
   disables the tip-chord cell and renames the root-chord header to "Chord
   c/R". An elliptic base disables the tip-chord cell and renames the
   root-chord header to "Max chord c/R". Add a test that the disabled cell
   count matches the base kind.
3. Raise instead of falling back when an endpoint chord is near zero. The
   message names the endpoint, the base value and the requested value.
4. Reject more than one chord target in one override set, with a message that
   names the two targets. Document the composition order in the docstring
   either way.

### 5.2 Phase — Cost, duplicates and parallelism

5. Add a cost estimate to the Conditions page: the variant count, the condition
   count, the trim multiplier and the resulting solve count, stated as numbers.
   Time one base solve when the page opens, and give an estimated wall time.
6. Detect duplicate variants by comparing the resolved radial tables, and warn
   before the run with the two labels named. Do not block. A user may want the
   repeat as a solver-noise check.
7. Add a worker count to the Conditions page, and reuse the process-pool path
   of Item 3, Phase 3.3. A comparison is embarrassingly parallel across
   variants. Keep the serial path as the default until the pool is proven on
   Windows.

### 5.3 Phase — Reach

8. Replace `_RANKING_FIELDS` and `_OVERLAY_FIELDS` with a live list built from
   the keys that the results actually carry, filtered through
   `api.summary_symbols` so each entry shows its rendered symbol and its unit.
   Keep the present seven as the default order, so nothing moves for a user who
   does not go looking.
9. Let a variant carry more than the planform. Extend the variant payload from
   a `RotorGeometryDef` to a small `VariantDef` that may also carry an
   `AirfoilDef` and a `BladeDynamicsDef`. `compare_geometries` already builds a
   sub-project per variant with `dataclasses.replace`, so the change is a
   wider replace and a wider table, not a new mechanism. Guard the fairness
   claim: when a variant changes the airfoil, the report must say so beside the
   ranking, because the comparison is no longer geometry alone.
10. Persist a comparison. Add `ComparisonDefinition` to `models.py` and
    `inputs/comparisons.bemt` to the project paths, holding the variant rows,
    the chosen conditions and the trim mode. Amend `SC-7`, which currently says
    comparison variants are session data. This is a deliberate requirement
    change, so make it in its own commit, as Item 0 does.

### 5.4 Phase — Cross-links to the new windows

11. Accept designs from the optimizer. Item 3, Phase 3.4 sends the selected
    Pareto members into the variant table. Confirm that
    `_append_absolute_row` labels them with the study name and the front index,
    so the origin of a row is readable.
12. Add a "Compare with derivatives" action that runs Item 4 on each variant at
    the ranking condition and adds the pitch damping and the heave damping to
    the ranking table. A blade that wins on the figure of merit and loses on
    damping is a result the current window cannot show.

### 5.5 Phase — Tests and documentation

Extend `tests/test_designer_window.py` and `tests/test_studies.py` with one
test per finding above. Update chapter 13 of the documentation for every
behavior that changes, and update `SC-7` for the persistence change and the
wider variant payload.

---

## Done (on `feature/design-tools`)

- ~~**XFoil support.**~~ The engine runs `xfoil` alongside NeuralFoil, with dedicated
  transition inputs (`xfoil_ncrit`, `xfoil_xtr_top`, `xfoil_xtr_bot`) and a four-place
  binary lookup (`ZBEMT_XFOIL_BIN`, remembered Locate… pick, PATH, standard install
  folders). The CLI gains `--gen-xfoil` with `--ncrit`, `--xtr-top` and `--xtr-bot`,
  and the table pipeline stays the same (SC-9).
- ~~**Compare different geometries.**~~ A dedicated Geometry Designer window opens from
  the Tools button in the main window's top bar. It compares variants over nine planform
  parameters, generates variants from a planform family, imports variants from another
  project, runs any set of flight conditions, ranks at any condition, draws overlay
  panels and a delta-to-base figure, and writes an HTML report and a CSV export.
  Optional trimming holds thrust or `CT` constant so efficiency is compared at equal
  loading (SC-7).
- ~~**Design mode: geometry factorial sweep.**~~ The sweep builder lives in the same
  window. Optimization stays an outer loop through the CLI (`--compare`, `--optimize`)
  and the library, deliberately outside the GUI (SC-8).
- ~~**Offer CST and Bézier profile sources in the GUI.**~~ Eight contour sources
  (naca4, naca5, cst, bezier, parsec, joukowski, biconvex, imported) with editable
  per-family fields (SC-10).
- ~~**Surface partial external-polar convergence in the GUI.**~~ The engine writes a
  line to a diagnostics list for every Reynolds number it drops. The polar-generation
  status label reports "N of M Reynolds converged" with the failures named, and the CLI
  prints the same lines (SC-9).

