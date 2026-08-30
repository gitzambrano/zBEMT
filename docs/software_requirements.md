# zBEMT: Software Requirements

zBEMT is a Blade Element Momentum Theory (BEMT) solver for rotors,
propellers, and eVTOL rotors, exposed through three interfaces (GUI, CLI,
Python library) that share a single engine. This document states the
requirements the software must satisfy.

Every requirement carries a code, so that a test, a commit message or a review
comment can name the rule it is about. The prefix says which section it comes
from:

| Prefix | Section | What it covers |
|---|---|---|
| `SC` | 1 | Scope: what the software must and must not do |
| `PR` | 2 | Product: what the user is entitled to |
| `AR` | 3.1 | Architecture: which module may do what |
| `EN` | 3.2 | Engine correctness |
| `PA` | 3.3 | GUI / CLI / `.bemt` parity |
| `RP` | 3.4 | Reports |
| `DC` | 3.5 | Documentation |
| `TB` | 3.6 | GUI tab behaviour |
| `QR` | 4 | Quality: how the work is done and verified |

Codes are permanent. A requirement that is removed leaves its code retired
rather than reassigned, so an old reference never silently points at a
different rule.

---

## 1. Scope

### 1.1 The software must support

- **SC-1** — Steady-state and quasi-steady BEMT analysis of rotors and propellers,
  including forward flight, climb/descent, and hover.
- **SC-2** — Multiple inflow models (Glauert, Coleman, Drees — local and global — and
  Pitt-Peters steady), multiple solvers (Newton-Raphson, fixed-point,
  Aitken, bisection), rotational and compressibility corrections, dynamic
  stall, tip/root loss, and full-range polar extension.
- **SC-3** — Batch and parametric sweeps, self-contained HTML reporting, 2D and 3D
  visualization, and analytical/tabulated/NeuralFoil-generated airfoil
  polars.
- **SC-4** — Three synchronized interfaces (GUI, CLI, library) built on one engine,
  with GUI/CLI/`.bemt`-file parity as required by §3.3.
- **SC-7** — Geometry comparison across labeled variants in a dedicated
  Geometry Designer window. A chosen set of flight conditions (the
  project's saved cases, one single condition, or one swept quantity)
  runs over several blade planforms, and everything except the geometry
  stays fixed: the same airfoil polar, mesh, inflow model and corrections
  go into every run. Variants are override rows over the project's own
  planform, or they come from a one-parameter variation sweep. A user
  label (or an auto-generated `param=value` label) tags each variant in
  the verdicts, plots and exports. After a run, the summary metric may be
  ranked across variants at any condition of the run, not only the first.
  The ranking default follows the mode convention: propeller efficiency
  for propeller-convention runs, figure of merit otherwise. Beside the
  ranking, the software draws each variant's percent change against the
  base planform at that same condition, and it falls back to the absolute
  difference when the base value is approximately zero. The comparison may
  instead hold the loading constant across variants, at constant thrust or
  constant `CT`. The first variant is then the reference and runs
  untrimmed. Its thrust or `CT` at each condition becomes that condition's
  target. Every other variant reaches the target by bisection over one
  degree of freedom chosen automatically from the mode convention (RPM for
  propellers, collective for rotors). A variant whose target falls outside
  the search bracket raises a named error instead of converging outside
  it. Trimmed summaries record the target, the solved degree of freedom
  and its converged value. Variants may also come ready-made. The window
  generates blades from the three parametric families (rectangular,
  tapered, elliptic), and it imports the blade of any project folder,
  either as one more variant or as a session-only replacement of the base
  planform (the imported project file is only ever read). For a base
  without a parametric generator, the window applies a planform parameter
  in table space instead of failing. It reads the parameter as a target on
  the radial table. The root and tip chord and twist parameters rebuild
  the chord and twist tables so their endpoints meet the requested values,
  `chord_norm` scales the chord uniformly to the mean chord, and
  `max_chord_norm` scales it uniformly to the peak chord. The variant table
  exposes each row's root cutout, radius, aspect ratio and solidity beside
  its overrides, and every comparison result summary carries the blade aspect
  ratio and the rotor solidity (`studies._blade_planform_metrics`), so the
  ranking, the overlay figure and the CSV export can compare shape next to
  performance.
- **SC-7a** - Persisted comparisons (`inputs/comparisons.bemt`). A comparison
  — its variant rows, chosen conditions and trim mode — may be saved with the
  project under a name and re-run or reviewed later; it is no longer strictly
  session data. A variant row may also carry its own airfoil section and blade
  dynamics block, in which case the run is no longer geometry alone: the
  report says so beside the ranking, because the equal-polar fairness claim
  of `SC-7` no longer holds for that run.
- **SC-8** — Persisted design-optimization studies (`inputs/optimizations.bemt`)
  drive one summary quantity on one flight condition through a bounded,
  derivative-free search over parametric planform parameters (Powell or
  Nelder-Mead). The search starts deterministically from the center of the
  bounds, respects them throughout, and penalizes failed evaluations instead
  of stopping. This single-objective search is reachable from the CLI
  (`--optimize`) and the library; the multi-objective search of `SC-13` adds
  the GUI window.
- **SC-9** — XFOIL as an external polar engine. Polar generation may drive
  the `xfoil` binary, which the software looks up through a four-place
  chain: the `ZBEMT_XFOIL_BIN`
  environment variable first, then the executable path remembered from a
  previous GUI "Locate…" pick (stored between sessions in the application
  settings file), then PATH, then the standard Windows install folders
  (`%LOCALAPPDATA%\Programs\XFOIL` and `%ProgramFiles%\XFOIL`). Generation
  writes one script per Reynolds number and applies the same
  Prandtl-Glauert post-correction as NeuralFoil.
  The XFOIL-only transition
  inputs (`ncrit`, `xtr_top`, `xtr_bot`: the e^N criterion and forced
  transition stations) reach the binary only on the XFOIL path. With
  `--gen-neuralfoil`, the solver rejects them. Per PR-7, a missing binary
  degrades only this feature. The failure raises a RuntimeError that names
  the cause and the remedies.
- **SC-10** — Analytic airfoil geometry families (PARSEC, Joukowski,
  biconvex) join the NACA 4- and 5-digit codes, CST, Bézier and imported
  contours. All families are reachable through one resolver grammar
  (preset nicknames and prefixed forms) served by the CLI's
  `--airfoil-geometry`. In the GUI, every family is a normal entry of the
  contour Source dropdown and reveals its own editor rows. No parallel
  specification-string field exists on screen. The software serializes the
  parameters under the profile geometry (`generator_params` inside the
  `geometry` block of
  `inputs/airfoil.bemt`) so a saved contour can be regenerated without its
  coordinate table.
- **SC-11** — Rigid-blade flap and lead-lag dynamics, solved as a periodic
  quasi-steady response. The blade carries a flap hinge offset, a root
  spring, or both. A rigid blade with no flap freedom stays available, and
  it stays the default.
- **SC-12** — Transient time marching over a prescribed sequence of flight
  conditions. The marched states are the Pitt-Peters inflow states and the
  Øye separation state. The blade-element solution stays quasi-steady
  inside each time step.
- **SC-13** — Multi-objective design optimization in a dedicated window,
  with a genetic algorithm and a Pareto front. `SC-8` stays the
  single-objective study; `SC-13` is the multi-objective one.
- **SC-14** — Stability and control derivatives of the rotor hub loads, by
  finite differences about a trim point, in a dedicated window.

### 1.2 The software must not support

- **SC-5** — Free-wake, prescribed-wake and vortex-lattice inflow, and any
  form of computational fluid dynamics. The inflow field stays an annular
  momentum model or a finite-state model. Blade elasticity, that is a modal
  or a finite-element blade, also stays out of scope. The blade is rigid.
  Its rigid-body flap and lag freedoms are in scope (`SC-11`).
- **SC-6** — Mandatory GUI dependencies in the core engine. The solver and CLI must
  keep running on `numpy` + `scipy` + `matplotlib` + `pandas` alone; a
  batch run on a headless server must never require Qt or 3D graphics.

---

## 2. Product Requirements

- **PR-1 — Three equivalent entry points.** Every capability reachable
  from the GUI must be reachable from the CLI and from a `.bemt` project
  file, and vice versa. A feature implemented in only one interface must
  not be considered complete.
- **PR-2 — Progressive disclosure in the GUI.** Options that do not apply
  to the current configuration must be hidden. A control that cannot affect
  the active model must never remain on screen in a blocked state.
- **PR-3 — Field-level help.** Every configurable field must expose its
  help through two paths: a hover tooltip with a short description, and a
  click on the field's name/label that opens a popup. The popup must
  contain the complete descriptive physics and mathematics governing that
  field's behavior, and it must always include a link to the
  corresponding section of the full HTML documentation
  (`docs/documentation.html`). The mapping from field to documentation section must be
  derived from the field's tooltip/name, not maintained as a separate
  hand-written list.
- **PR-4 — LaTeX rendering of mathematical notation.** Greek symbols and
  subscripts must be rendered in LaTeX everywhere they appear: GUI field
  labels and values, field-help popups, tables, plots/graphs, and
  `docs/documentation.html`. Plain-text or Unicode approximations
  (`lambda_i`, `mu_x`) must not be used in any user-facing surface.
- **PR-5 — Self-contained reports.** `generate_report` output must be
  viewable with no external files or network access. Large batches must
  split into a master page plus per-section satellite pages; a report
  must never omit data because it was "too large."
- **PR-6 — Validate before running.** Static validation
  (`validation.py`) must catch invalid or physically inconsistent
  configurations before the engine runs, both in the GUI (step-by-step,
  via the flow indicator) and the CLI (automatically, before every
  execution).
- **PR-7 — Graceful optional dependencies.** PyVista (3D), NeuralFoil (ML
  polars), and Plotly (interactive reports) must remain optional; their
  absence must degrade only the specific feature that depends on them,
  and must never crash an unrelated feature.
- **PR-8 — Correct propeller/rotor axis conventions.** Field labels,
  angles, summary columns, plot axes, CLI help and the keys written into
  `.bemt` files must all reflect the vehicle convention in use (rotor vs.
  propeller), not the engine's internal disk-axes decomposition. Every mode
  must show only the angle and velocity components meaningful to it.

  This is enforced structurally, not by convention: `zbemt/nomenclature.py`
  is the single table every surface reads, so a symbol cannot be right in
  the results table and wrong in the chart printed beside it in the same
  report.
- **PR-9 — Plots must read correctly.** A plot states the general
  flight/operating condition it was generated under in its title. Legends,
  labels and annotations must not overlap the plotted data. A disk map must
  carry the azimuth convention it was drawn in.
- **PR-10 — GUI layout invariants.** Fields align vertically across forms;
  buttons that appear together share a width; no text is ever clipped or
  overflowed, in a label, a button, a tooltip or a help popup. A hidden form
  field hides its whole row, label included. A visible label pointing at a
  hidden field is a defect.
- **PR-11 — The GUI never freezes.** No user action may block the main
  thread. Solving, batch runs, report generation, polar generation and file
  import run off the main thread; the GUI stays responsive, reports progress,
  can be cancelled, and updates itself as results arrive. Work that only the
  main thread can do — filling a table, building a figure — is done once per
  user gesture, not once per row or per column, and a burst of clicks
  produces one refresh, not one per click.
- **PR-12 — A figure keeps a readable size, or scrolls.** A multi-panel
  figure has a minimum size per panel and the drawing area scrolls when the
  window is smaller than that minimum. Text is measured in points and does
  not shrink with the panel, so squeezing a grid into a small screen makes
  its labels collide instead of making it smaller. A single-panel figure has
  no such floor: it fills whatever area the window gives it, at any screen
  size. A figure's minimum never propagates out of the drawing area to
  enlarge the window itself.
- **PR-13 — Units on editable values.** Every editable dimensional value in
  the GUI states its unit in the label or an adjacent unit selector. A
  dimensionless value states that it is dimensionless with `[-]`.

---

## 3. Architectural Requirements

### 3.1 Layering

- **AR-1** — `api` must be the only path through which the GUI or CLI run the engine
  or write to disk. `geometry`, `airfoils`, `viz`, and `validation` may be
  imported directly by the GUI/CLI only for on-screen preview and
  drawing; they must not run the engine or write files outside `api`.
- **AR-2** — `studies` must orchestrate `bemt` across flight conditions and must
  never touch disk; it must always return `Results` (or `list[Results]`)
  in memory.
- **AR-3** — `models` must hold no physics: every `...Def` dataclass must be raw,
  editable, serializable data; physics-aware classes must be constructed
  from them, never duplicated.
- **AR-4** — `validation` must return static `Issue`s (error/warning/info) and must
  not run the engine.

### 3.2 Engine correctness

- **EN-1** — Convergence must always be tested on the true residual
  `g(lambda) - lambda`, evaluated before relaxation, never on the relaxed
  step. This applies to every solver mode.
- **EN-2** — Every physics option must be documented in `bemt.py`'s module
  docstring, mapping the `BEMTConfig` field to its code section.
- **EN-3** — A numerical guard (e.g. a protected denominator near a singular
  configuration) must be paired with a correct seed/starting point where
  applicable. A guard that only prevents `NaN` while still allowing
  divergence to a nonphysical value must not be considered a complete
  fix.
- **EN-4** — A published correction must reproduce its published closed form. A
  correction implemented as a simplification of the form it is named after (
  a dropped factor, a linearized term) is a defect, not a variant, and must
  be tested against the closed form rather than against a stored number.
- **EN-5** — The airfoil polar sources — analytical, tabulated single polar, tabulated
  by radial section, tabulated by Reynolds and/or Mach, Viterna-Corrigan
  extension, and the table+Viterna blend, must be interchangeable behind one
  interface: the engine must not know which source produced a coefficient.
- **EN-6** — Every reverse-flow model must be defined on both sides of the boundary, and
  a model advertised as continuous must be continuous at zero tangential
  velocity. A discontinuity there appears as an azimuthal step in the loads,
  not as a solver failure.
- **EN-7** — Geometry generation and custom geometry tables must be validated before the
  engine runs: monotonic radial stations, a span inside the hub and tip
  radii, and consistent lengths across the columns.
- **EN-8** — A periodic response solved by harmonic balance must state its
  harmonic count, and it must reject a resonant denominator instead of
  returning a large number. See the resonant denominator ν_β² − n² of the
  flap response (`SC-11`).
- **EN-9** — A time-marched state must report the marched interval, the step
  count, and whether the last revolutions reached a periodic regime. A
  transient that did not settle must not pass as a converged result.
- **EN-10** — Where a model resolves the section drag in spanwise (radial)
  flow, it must resolve the drag VECTOR along the total relative wind, not
  merely rescale the drag coefficient. The spanwise component carries no arm
  about the shaft, so it must reach the in-plane hub forces and leave torque
  and power untouched, and it must be reported as its own term so the user
  can see what the option did. The closed form for a constant drag
  coefficient — C_H,profile rising from σC_d0μ/4 to 3σC_d0μ/8, profile power
  from (1 + μ²) to (1 + 1.5μ²) — is the reference the implementation is
  checked against.
- **EN-11** — A result with one or more non-converged inflow elements must
  state that limitation. The result validator must issue a warning with the
  converged mesh percentage. A partial field must never appear as a fully
  converged solution.

### 3.3 GUI / CLI / `.bemt` parity

- **PA-1** — Every `Project`/`BEMTConfig` field editable in the GUI must be reachable
  from the CLI (dedicated flag or `--set config.<field>=<value>`).
- **PA-2** — Every `.bemt` project produced by any of the three paths must traverse
  the other two identically.
- **PA-3** — A new configuration field must be wired into all three interfaces
  before the feature is considered complete.
- **PA-4** — The three interfaces speak the SAME axis vocabulary: a `.bemt` file
  stores a flight condition under the letters the GUI shows for that
  project's mode, and the CLI's help describes each flag by the slot it
  fills and the letter it carries in each mode. The engine keeps its own
  disk-axes names, which never reach a user-facing surface.
- **PA-5** — The three interfaces accept the same INPUTS, not only the same
  fields. Where the GUI lets a quantity be given in an alternative form
  that it converts on the spot, the CLI and the `.bemt` file must accept
  that form too. The axial component of a flight condition may be stated
  as `alpha_rotor_deg` (from the disk plane) or `alpha_disk_deg` (from
  the shaft) instead of `Vz`, in a file exactly as on a flag. Such a
  form is an INPUT ALIAS: the canonical field stays the only thing
  stored, so no axis has two stored forms that can disagree. An alias
  that cannot be resolved -- no RPM, both angles at once, or an angle
  beside the very component it would set -- must be REFUSED. It must
  never be dropped, because a dropped angle leaves the case running at
  the default velocity and returning a plausible wrong answer.

### 3.4 Reports

- **RP-1** — `api.generate_report` must be the single implementation used by the GUI
  button, the CLI `--report` flag, and direct library calls. HTML
  assembly must not be duplicated in the GUI layer.
- **RP-2** — Section order must be: blade geometry and airfoil polars (inputs) →
  performance coefficients → azimuth/span loads → disk maps →
  convergence.
- **RP-3** — The summary table must have one row per condition and one column per
  `Results.summary` key, each with a symbol, unit, and description. A new
  summary key must ship with a column entry.

### 3.5 Documentation

- **DC-1** — `docs/documentation.html` is the single physics reference and the embedded
  help source, written in English. Every flag, module, project, batch and
  anchor it cites must exist.
- **DC-2** — Structure: introduction (chapters 0-5), one chapter per GUI tab in tab order
  (6-12), the Geometry Designer window chapter (13), reference (14-15).
- **DC-3** — A GUI page gets a chapter of its own. Its sections follow the order of the
  blocks and fields on screen. A page is never documented inside a physics
  chapter.
- **DC-4** — A field's section is self-contained: the physics, the mathematics, every
  option it offers, and how to set it in the GUI, in `.bemt` and in the CLI as
  three separate paragraphs. A reader must not follow a link to understand or
  set a field. Named models are explained where their control is.
- **DC-5** — No class names, function names, package paths or development notes. The
  three interfaces are called GUI, CLI and `.bemt`.
- **DC-6** — Each page chapter opens with its tab screenshot from `docs/img/gui/`.
- **DC-7** — A field or block belonging to a tab opens a section inside that tab's
  chapter.
- **DC-8** — Figures are files under `docs/img/`, never base64 in the HTML. Regenerate
  through `tools/regenerate_documentation_plots.py` against a real example
  project, with all on-screen text in English.
- **DC-9** — All mathematical notation, including Greek symbols and subscripts, is
  rendered in LaTeX (per PR-4).
- **DC-10** — The index, the per-tab field lists and the screenshots are generated by
  tools and never hand-edited.
- **DC-11** — Enforced by `tests/test_documentation.py` and `tests/test_help_content.py`.

### 3.6 GUI tab behaviour

- **TB-1** — The Results tab groups a batch into series by the swept variable, within a
  numerical tolerance. Series height and color are independent controls: a
  series must never encode two quantities at once.
- **TB-2** — A tab must reflect the project it has open. A control whose value came from
  a project that has since been closed must not remain offered.
- **TB-3** — A tab that mutates the project in memory marks it as unsaved; Save writes
  it and Restore reloads the last saved version.
- **TB-4** — Every tab must survive an empty project, a project with no results, and a
  mode switch between rotor and propeller without losing user input.

---

## 4. Quality Requirements

- **QR-1 — Regression tests for logic fixes.** A fix to solver or
  business logic must ship with a regression test that fails before the
  fix and passes after. Pure layout/styling fixes are exempt.
- **QR-2 — Full suite must pass before completion.** The complete test
  suite (`pytest`, including headless GUI tests) must pass before work is
  marked complete. Failing or partial work must not be shipped.
- **QR-3 — Coverage of the physics/mode matrix.** The versioned example
  projects under `projects/` must span airfoil sources (analytical /
  table / external+NeuralFoil), inflow models (including
  `pitt_peters_steady`), stall models, both rotor and propeller mode, and
  multi-section airfoils. A gap in that coverage must be treated as a
  defect.
- **QR-4 — Project/model changes must be checked.** Any change to a
  project file or to `models.py`'s dataclass defaults must be followed by
  `python tools/check_project_configs.py`, which loads, validates, and
  smoke-solves every folder under `projects/`.
- **QR-5 — English everywhere.** All code, comments, docstrings, and
  everything a user of the GUI/CLI/reports/plots/docs sees must be
  English. A single file must not mix languages.
- **QR-6 — Boundaries documented alongside fixes.** A fix that changes
  documented behavior (a docstring's claim, a known limitation) must
  correct the documentation in the same change.
- **QR-7 — License compliance.** Third-party code, generated code, or
  dependencies must be compatible with GPL-3.0-or-later. A dependency
  requiring a more restrictive or incompatible license must not be
  introduced.
- **QR-8 — A physics option must be shown to do something.** Locking down a
  toggle's default value is not coverage. Every physics option must have a
  test that turns it on and verifies the expected physical effect against a
  reference external to the code: a published formula, a limit the engine
  must reproduce, or a property the model must have (harmonic inflow models
  coinciding in hover, for instance).
- **QR-9 — English internal identifiers.** Every function, class, variable,
  constant and parameter name in `zbemt/`, `tools/` and `tests/` is an
  English name that states its purpose. A Portuguese identifier is a defect
  even when every user-facing string is English. Renames never touch
  user-facing keys: `.bemt` keys, product CLI flag names, CSV headers, HTML
  `id` attributes and Qt object/slot names stay fixed.
