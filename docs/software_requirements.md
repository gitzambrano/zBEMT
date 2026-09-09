# zBEMT: Software Requirements

This document is the binding specification for zBEMT. It defines product,
architecture, engine, interface, documentation, GUI, and quality requirements.

Each requirement has a permanent code. Retire a removed code. Never reuse it
for a different requirement. State one independently testable obligation per
requirement and use subcodes when a feature needs several obligations.
Requirements state the required end state in the present tense. Rationale,
migration history, bug history, and temporary implementation notes do not
belong in this document.

| Prefix | Section | Scope |
|---|---|---|
| `SC` | 1 | Supported and excluded capabilities |
| `PR` | 2 | User-visible product behavior |
| `AR` | 3.1 | Architecture boundaries |
| `EN` | 3.2 | Engine correctness |
| `PA` | 3.3 | GUI, CLI, and `.bemt` parity |
| `RP` | 3.4 | Reports |
| `DC` | 3.5 | Documentation |
| `TB` | 3.6 | GUI tab behavior |
| `QR` | 4 | Verification and repository quality |

## 1. Scope

### 1.1 Supported capabilities

- **SC-1** — The software performs steady-state and quasi-steady BEMT analysis
  of rotors and propellers in hover, forward flight, climb, and descent.
- **SC-2** — The supported inflow models are Glauert, Coleman, local Drees,
  global Drees, and Pitt-Peters steady.
- **SC-2a** — The supported numerical solvers are Newton-Raphson, fixed-point,
  Aitken, and bisection.
- **SC-2b** — The supported local physics options include rotational and
  compressibility corrections, dynamic stall, tip and root loss, reverse-flow
  models, and full-range polar extension.
- **SC-3** — The software supports batch runs and parametric sweeps.
- **SC-3a** — The software supports self-contained HTML reporting.
- **SC-3b** — The software supports 2D and 3D visualization.
- **SC-3c** — The software supports analytical, tabulated,
  NeuralFoil-generated, and XFOIL-generated airfoil polars.
- **SC-4** — The supported entry points are the GUI, CLI, and Python library.
  `.bemt` files provide the persistent project input format.
- **SC-7** — The Geometry Designer compares labeled blade planform variants
  across selected flight conditions and keeps non-geometry inputs fixed by
  default.
- **SC-7a** — Named comparisons persist in `inputs/comparisons.bemt` with their
  variants, selected conditions, and trim mode.
- **SC-7b** — A geometry comparison accepts explicit override rows,
  one-parameter variation sweeps, generated rectangular, tapered, or elliptic
  blades, and blades imported from another project.
- **SC-7c** — Each comparison variant has a user label or an automatically
  generated `parameter=value` label used by results, plots, and exports.
- **SC-7d** — A summary metric can rank variants at any condition in the
  comparison. The default metric is propeller efficiency in propeller mode and
  figure of merit otherwise.
- **SC-7e** — The comparison reports each variant relative to the base planform
  at the selected condition. It uses percent change unless the base value is
  approximately zero, then it uses absolute difference.
- **SC-7f** — A comparison can hold thrust or `CT` constant. The first variant
  runs untrimmed and defines the target for each condition.
- **SC-7g** — Other variants reach a constant-loading target by bisection.
  Propeller mode trims RPM. Rotor mode trims collective.
- **SC-7h** — A target outside the trim bracket raises a named error. The trim
  solver does not converge outside the bracket.
- **SC-7i** — A trimmed comparison result records the target, trimmed degree of
  freedom, and converged value.
- **SC-7j** — If a base blade has no parametric generator, the Geometry Designer
  applies planform targets directly to the radial table.
- **SC-7k** — Root and tip chord and twist targets rebuild the corresponding
  tables to meet the requested endpoints. `chord_norm` scales chord to the
  requested mean chord. `max_chord_norm` scales chord to the requested peak
  chord.
- **SC-7l** — Variant rows, comparison results, and comparison CSV exports expose
  root cutout, radius, blade aspect ratio, and rotor solidity where applicable.
- **SC-7m** — The Geometry Designer can use an imported project blade as a
  session-only base replacement without modifying the imported project.
- **SC-7n** — A comparison variant may define its own airfoil sections or blade
  dynamics. The report identifies such a comparison as not geometry-only and
  does not claim equal-polar fairness.
- **SC-7o** — A geometry-only comparison uses the same airfoil polar, mesh,
  inflow model, and correction settings for every variant.
- **SC-7p** — Comparison conditions can be the project's saved cases, one
  explicit condition, or one swept quantity.
- **SC-8** — Persisted single-objective studies in
  `inputs/optimizations.bemt` optimize one summary quantity at one flight
  condition over bounded parametric planform variables with Powell or
  Nelder-Mead.
- **SC-8a** — A single-objective search starts at the center of the bounds,
  remains inside the bounds, and penalizes failed evaluations instead of
  stopping.
- **SC-8b** — Single-objective optimization is available through the CLI
  `--optimize` path and the Python library.
- **SC-9** — XFOIL is supported as an external polar engine.
- **SC-9a** — The XFOIL executable resolves in this order: `ZBEMT_XFOIL_BIN`,
  the persisted GUI selection, `PATH`, then the standard Windows install
  folders under `%LOCALAPPDATA%\Programs\XFOIL` and
  `%ProgramFiles%\XFOIL`.
- **SC-9b** — XFOIL generation writes one script per Reynolds number and
  applies the same Prandtl-Glauert post-correction used by NeuralFoil.
- **SC-9c** — `ncrit`, `xtr_top`, and `xtr_bot` apply only to XFOIL.
  NeuralFoil rejects these inputs.
- **SC-9d** — A missing XFOIL executable affects only XFOIL and raises a
  `RuntimeError` that states the cause and available remedies.
- **SC-10** — The airfoil geometry resolver supports NACA 4-digit, NACA
  5-digit, CST, Bézier, PARSEC, Joukowski, biconvex, and imported contours
  through preset names and prefixed forms.
- **SC-10a** — Each analytic family is a normal GUI Source option with its own
  editor rows. The GUI has no parallel free-form geometry specification field.
- **SC-10b** — Regenerable geometry parameters persist as `generator_params`
  inside the profile `geometry` block in `inputs/airfoil.bemt`.
- **SC-11** — The software supports periodic quasi-steady rigid-blade flap and
  lead-lag response with a hinge offset, root spring, or both. A rigid blade
  with no flap freedom is the default.
- **SC-12** — The software time-marches prescribed flight conditions with
  Pitt-Peters inflow states and the Øye separation state. Blade-element loads
  remain quasi-steady within each time step.
- **SC-13** — A dedicated GUI tool performs multi-objective genetic-algorithm
  optimization and presents a Pareto front.
- **SC-14** — A dedicated GUI tool computes rotor hub-load stability and
  control derivatives by finite differences about a trim point.
- **SC-15** — A flight condition supports a lateral in-plane component so the
  free-stream velocity has three components.
- **SC-15a** — The lateral component accepts `Vy`, `mu_y`, `J_y`, or
  `sideslip_deg` as equivalent input forms. A condition supplies at most one
  of them.
- **SC-15b** — The lateral component is available as a fixed input, batch axis,
  results field, CSV field, and report field.
- **SC-15c** — `sideslip_deg` specifies the direction of a known longitudinal
  in-plane component and remains inside plus or minus 89 degrees. Pure
  sideward flight is specified through `Vy`.
- **SC-16** — A tabulated polar may include optional `Cm`. CSV import,
  supported external generation, `.bemt` persistence, and CSV export preserve
  it. The force and performance solution does not use `Cm`.
- **SC-16a** — One polar CSV can define multiple radial stations of one airfoil
  definition through `r_norm`.

### 1.2 Excluded capabilities

- **SC-5** — Free-wake, prescribed-wake, vortex-lattice inflow, and
  computational fluid dynamics are out of scope.
- **SC-5a** — Supported inflow fields remain annular-momentum or finite-state
  models.
- **SC-5b** — Modal and finite-element blade elasticity are out of scope.
  Rigid-body flap and lag remain in scope under `SC-11`.
- **SC-6** — The solver and CLI run without Qt or 3D graphics. Their required
  numerical stack is NumPy, SciPy, Matplotlib, and pandas.

## 2. Product Requirements

- **PR-1** — GUI, CLI, and `.bemt` project inputs expose equivalent
  user-configurable capabilities unless another requirement explicitly scopes a
  capability to fewer interfaces.
- **PR-2** — A control that is inapplicable to the active configuration is
  hidden. A control that is applicable but temporarily unavailable because of
  a prerequisite remains visible and disabled.
- **PR-3** — Every configurable field provides a short hover tooltip and a
  clickable field label that opens help.
- **PR-3a** — Field help contains the governing physics and mathematics and
  links to the corresponding section in `docs/documentation.html`.
- **PR-3b** — The field-to-documentation mapping is derived from field label and
  tooltip metadata. It is not maintained as a separate manual list.
- **PR-4** — User-facing mathematical symbols, Greek letters, subscripts, and
  exponents use rendered mathematical notation. Plain identifier spellings such
  as `lambda_i` and `mu_x` do not replace rendered notation on user-facing
  surfaces.
- **PR-5** — A generated report is readable without external files or network
  access.
- **PR-5a** — Large batches may split into a master page and satellite pages,
  but no data is omitted because of report size.
- **PR-6** — Static validation rejects invalid or physically inconsistent
  configurations before the engine runs in GUI and CLI workflows.
- **PR-6a** — The GUI presents pre-execution validation state through its flow
  indicator.
- **PR-7** — Missing PyVista, NeuralFoil, Plotly, or another optional dependency
  disables only the feature that requires it.
- **PR-8** — User-facing labels, angles, summary fields, plots, CLI help, and
  `.bemt` keys use the active rotor or propeller vehicle convention rather than
  internal disk-axis names.
- **PR-8a** — Each mode exposes only angle and velocity components that are
  meaningful in that vehicle convention.
- **PR-9** — Every plot title states the general flight or operating condition
  represented by the plot.
- **PR-9a** — Legends, labels, titles, and annotations do not overlap plotted
  data or each other in a way that blocks reading.
- **PR-9b** — A disk map states its azimuth convention.
- **PR-10** — Editable field columns align within and across related forms.
- **PR-10a** — Buttons presented as a group share a width.
- **PR-10b** — User-facing text is not clipped or overflowed in labels, buttons,
  tooltips, help popups, or other controls.
- **PR-10c** — Hiding a form field hides both its label and its editor.
- **PR-10d** — A dropdown does not silently hide options behind Qt's default
  ten-item limit. Lists that fit the supported popup limit show all options
  without scrolling.
- **PR-11** — Long work does not block the GUI main thread. The GUI remains
  responsive, reports progress, supports cancellation where the operation can
  be cancelled, and presents available results as they arrive.
- **PR-11a** — Main-thread work such as table filling and figure construction
  runs once per user gesture or coalesced event burst, not once per row, column,
  or repeated signal.
- **PR-12** — A multi-panel figure maintains a readable minimum size per panel
  and scrolls inside its drawing area when the available area is smaller.
- **PR-12a** — Figure text uses point sizing and does not shrink merely because a
  panel is compressed.
- **PR-12b** — A single-panel figure fills the available drawing area and has no
  multi-panel minimum-size floor.
- **PR-12c** — A figure minimum size does not propagate outside the drawing area
  to enlarge the containing window.
- **PR-13** — Every editable dimensional value shows its unit. Every editable
  dimensionless value shows `[-]`.
- **PR-14** — Each Engineering Tool card states the engineering question,
  prerequisite or input, and result produced by the Tool.
- **PR-14a** — Each Tool window provides numbered steps, current-action
  guidance, Back and Next navigation, and direct step navigation.
- **PR-14b** — Advanced numerical tuning starts collapsed.
- **PR-14c** — An empty study presents the first valid action instead of an
  error.

## 3. Architectural Requirements

### 3.1 Layering

- **AR-1** — The GUI and CLI run the engine and write application data only
  through `api`. Direct imports of `geometry`, `airfoils`, `viz`, and
  `validation` are limited to preview, drawing, and static validation.
- **AR-2** — `studies` orchestrates `bemt` across flight conditions, does not
  write to disk, and returns `Results` objects in memory.
- **AR-3** — `models` contains raw editable and serializable data definitions.
  Physics-aware behavior lives outside `...Def` dataclasses.
- **AR-4** — `validation` returns static `Issue` objects and does not run the
  engine.
- **AR-5** — `zbemt/nomenclature.py` is the single source for user-facing axis
  symbols, units, tooltips, slot names, and display-key mappings.
- **AR-6** — Vehicle-axis key conversion is a one-pass reversible mapping. A
  display-key dictionary returns to internal disk-axis form only through the
  inverse mapping at the boundary that produced it.

### 3.2 Engine Correctness

- **EN-1** — Every solver tests convergence on `g(lambda) - lambda` before
  relaxation.
- **EN-2** — The `bemt.py` module docstring maps each `BEMTConfig` physics
  option to the code section that implements it.
- **EN-3** — A numerical singularity guard is paired with a physically valid
  seed or starting point where one is required.
- **EN-4** — An implementation named after a published correction reproduces
  the published closed form.
- **EN-5** — Analytical polars, a single tabulated polar, radial tabulated
  polars, Reynolds-conditioned and Mach-conditioned tables,
  Viterna-Corrigan extension, table-plus-Viterna blending, and external polar
  sources implement one coefficient interface. The engine does not depend on
  which source produced a coefficient.
- **EN-6** — Every reverse-flow model is defined on both sides of zero
  tangential velocity. A model advertised as continuous is continuous at that
  boundary.
- **EN-7** — Generated and tabulated geometry validates monotonic radial
  stations, radial bounds, and consistent column lengths before execution.
- **EN-8** — A harmonic-balance result records its harmonic count and rejects a
  resonant denominator instead of returning a large finite value. For flap
  response, this includes the denominator `nu_beta^2 - n^2`.
- **EN-9** — A transient result records the marched interval, step count, and
  final periodic-state status. An unsettled transient is not reported as
  converged.
- **EN-10** — A model that resolves radial flow resolves section drag along the
  total relative-wind vector rather than only rescaling the drag coefficient.
- **EN-10a** — The radial drag component contributes to in-plane hub forces and
  does not contribute to shaft torque or power.
- **EN-10b** — The radial-flow drag contribution is reported as a distinct
  result term.
- **EN-10c** — For constant drag coefficient, the implementation reproduces the
  reference limits `C_H,profile = sigma*C_d0*mu/4` without radial-flow
  resolution and `3*sigma*C_d0*mu/8` with full vector resolution. The profile
  power factor changes from `(1 + mu^2)` to `(1 + 1.5*mu^2)`.
- **EN-11** — The result validator issues a warning when one or more inflow
  elements do not converge. The warning reports the converged mesh percentage,
  and the result is not presented as fully converged.
- **EN-12** — Blade aspect ratio and rotor solidity use a reference blade that
  spans `r/R = 0` to `r/R = 1`, with `AR = R^2/S_ref` and
  `sigma = N_b*S_ref/(pi*R^2)`.
- **EN-12a** — Root cutout truncates aerodynamic loading but does not change
  `AR` or `sigma` when the reference chord law is unchanged.
- **EN-12b** — For a tapered blade, `root_chord_norm` is the reference chord at
  `r/R = 0` and `tip_chord_norm` is the chord at `r/R = 1`.
- **EN-13** — In rotor mode, `V_z`, `lambda_z`, `mu_z`, `J_z`, and total axial
  inflow are positive through the disk in the induced-velocity direction.
  `lambda_total = lambda_z + lambda_i`. Positive `V_z` reduces thrust for the
  same remaining inputs.
- **EN-13a** — In rotor mode, `alpha_rotor = -atan2(V_z, V_x)` and is measured
  from the disk plane. Positive `alpha_rotor` corresponds to negative `V_z`.
- **EN-14** — In propeller mode, `alpha_disk = atan2(V_z, V_x)` and is measured
  from the shaft. Straight axial cruise has `V_z = 0` and `alpha_disk = 0`.
- **EN-15** — Longitudinal and lateral in-plane flow resolve as one magnitude
  and direction: `mu_inplane = hypot(V_x, V_y)/(Omega*R)` and
  `psi_w = atan2(V_y, V_x)`.

### 3.3 GUI, CLI, and `.bemt` Parity

- **PA-1** — Every `Project` or `BEMTConfig` field editable in the GUI is
  reachable from the CLI through a dedicated flag or `--set`.
- **PA-2** — A `.bemt` project produced by any supported entry point traverses
  the other entry points without semantic change.
- **PA-3** — A new configuration field is wired into every interface required
  by `PR-1` before the feature is complete.
- **PA-4** — GUI, CLI, reports, exports, and `.bemt` persistence use the same
  vehicle-axis vocabulary for a project mode. Internal engine keys remain
  disk-axis keys.
- **PA-4a** — A `.bemt` flight condition stores the axis letters shown by the
  GUI for that project mode. Internal disk-axis names do not reach persistent
  user-facing keys.
- **PA-4b** — CLI help describes each flight-condition input by its physical
  slot and the letter used in rotor and propeller modes.
- **PA-4c** — Vehicle `x` is longitudinal and forward, vehicle `y` is lateral,
  and vehicle `z` is vertical and upward.
- **PA-4d** — Rotor mode uses a vertical shaft aligned with vehicle `z`.
  Propeller mode uses a horizontal shaft aligned with vehicle `x`.
- **PA-4e** — Propeller display mapping swaps the internal disk-axis pairs
  `Vx` and `Vz`, `mu_x` and `mu_z`, and `J_x` and `J_z`. Internal
  `lambda_z` displays as `lambda_x`, and internal `Vz_total` displays as
  `Vx_total`. Rotor mode keeps the corresponding `x` and `z` labels.
- **PA-4f** — `alpha_rotor_deg` is user-facing in rotor mode and hidden in
  propeller mode. `alpha_disk_deg` is user-facing in propeller mode and hidden
  in rotor mode.
- **PA-5** — If the GUI accepts an alternate form of an input, the CLI and
  `.bemt` format accept the same form unless another requirement explicitly
  scopes it.
- **PA-5a** — Alternate input forms resolve to one canonical stored field.
  Equivalent forms do not persist as independent values that can disagree.
- **PA-5b** — An alternate input that lacks required context or conflicts with
  another form is rejected. It is never silently dropped.
- **PA-5c** — `alpha_rotor_deg` and `alpha_disk_deg` can supply the axial flow
  component when their required context is available and the corresponding
  direct component is not supplied.
- **PA-5d** — An axial-angle alias is rejected when RPM is unavailable, when
  both angle forms are supplied, or when the direct axial component is also
  supplied.

### 3.4 Reports

- **RP-1** — `api.generate_report` is the single report implementation used by
  GUI, CLI, and library calls.
- **RP-2** — Reports present blade geometry and airfoil polars, performance
  coefficients, azimuth and span loads, disk maps, then convergence.
- **RP-3** — The summary table has one row per condition and one column for
  every `Results.summary` key, with symbol, unit, and description metadata.

### 3.5 Documentation

- **DC-1** — `docs/documentation.html` is the single user-facing physics
  reference and the source for embedded field help.
- **DC-1a** — Every flag, project, batch, field, and anchor named by the
  documentation exists.
- **DC-2** — Chapters 0 to 5 contain the introduction and physical method.
  Chapters 6 to 12 follow the seven GUI tabs. Chapter 13 covers Geometry
  Designer. Chapters 14 to 16 cover Optimization, Transient, and Stability.
  Chapters 17 and 18 cover CLI and limitations. Symbols and references follow.
- **DC-3** — Each GUI page has its own chapter, and the chapter follows the
  visible block and field order of that page.
- **DC-4** — A field section is self-contained and contains the field's physics,
  mathematics, options, and valid ranges.
- **DC-4a** — Each field section explains how to set the field in GUI, `.bemt`,
  and CLI in three separate paragraphs.
- **DC-4b** — A named model is explained where its controlling field is
  documented.
- **DC-5** — User documentation contains no class names, function names,
  package paths, or development notes. The interfaces are named GUI, CLI, and
  `.bemt`.
- **DC-6** — Each GUI page chapter opens with its current tab screenshot from
  `docs/img/gui/`.
- **DC-7** — A field or block belonging to a page is documented inside that
  page chapter.
- **DC-8** — Documentation figures are files under `docs/img/`, not base64
  data, and are generated from a real example project with user-visible text in
  English.
- **DC-9** — Documentation follows the mathematical-notation rule in `PR-4` and
  does not define a competing notation convention.
- **DC-10** — The general index, per-page field lists, and GUI screenshots are
  generated artifacts and are not hand-edited.
- **DC-11** — Architecture tests enforce documentation structure, field-help
  integration, link validity, and interface-reference validity.
- **DC-12** — The Engineering Tools launcher and Tool chapters match the GUI's
  current steps, configurable control labels, action labels, table-column
  labels, and launcher cards.
- **DC-12a** — Configurable labels in Tool documentation link to their complete
  field documentation.
- **DC-13** — Field instructions mark interface references with their semantic
  classes: GUI uses `<span class="gui">`, CLI uses `<span class="cli">`, and
  `.bemt` uses `<span class="bemt">`. The corresponding presentation uses blue,
  red, and green respectively.
- **DC-14** — A reference to another section is an underlined navigable link and
  carries the target section title. Bare section numbers are not used as
  cross-references.
- **DC-15** — Chapters 6 to 16 do not defer required field physics or setup
  instructions to another chapter. A link to another chapter can identify
  scope or related material.

### 3.6 GUI Tab Behavior

- **TB-1** — The Results tab groups a batch into series by swept variable within
  numerical tolerance. Series height and color remain independent encodings.
- **TB-2** — A tab reflects the project currently open and does not retain
  selectable values from a closed project.
- **TB-3** — A tab that changes the in-memory project marks it unsaved. Save
  persists it. Restore reloads the last saved state.
- **TB-4** — Every tab supports an empty project, a project with no results, and
  rotor-to-propeller mode changes without losing valid user input.
- **TB-5** — The Geometry radial table supports spreadsheet-style rectangular
  clipboard paste starting at the selected cell and grows rows as needed.
- **TB-5a** — Geometry paste accepts tab-delimited spreadsheet data,
  semicolon-delimited data, and simple three-column CSV. A decimal comma is
  accepted in spreadsheet and semicolon-delimited input.
- **TB-5b** — The complete pasted block validates before any cell changes, and a
  successful paste produces one project update.

## 4. Quality Requirements

- **QR-1** — A solver or business-logic fix includes a regression test that
  fails before the fix and passes after it. Pure layout and styling fixes are
  exempt.
- **QR-2** — Work is complete only after `python tests/run_all_tests.py` passes.
  A failing or partial change is not reported as complete.
- **QR-3** — Versioned example projects cover the supported airfoil-source
  classes, inflow-model classes, stall-model classes, rotor and propeller
  modes, and multi-section airfoils.
- **QR-4** — A project-file change or a dataclass default change in `models.py`
  is followed by `python tools/check_project_configs.py`.
- **QR-5** — Code comments, docstrings, repository documentation, commit
  messages, and user-facing text are English. A text file does not mix natural
  languages.
- **QR-6** — A change to documented behavior updates the affected documentation
  in the same change.
- **QR-7** — Third-party code, generated code, and dependencies are compatible
  with GPL-3.0-or-later.
- **QR-8** — Every physics option has a test that enables the option and
  verifies its expected effect against a published equation, physical limit,
  literature datum, or other reference external to the implementation.
- **QR-9** — Every function, class, variable, constant, and parameter name in
  `zbemt/`, `tools/`, and `tests/` is an English name that states its purpose.
  Stable external keys, product CLI flags, CSV headers, HTML `id` values, and Qt
  compatibility names are not renamed only to satisfy this rule.
- **QR-9a** — New internal identifiers, HTML `id` values, and Qt object or slot
  names are English unless compatibility requires an existing stable name.
- **QR-10** — One quality orchestrator selects the architecture, regression, or
  physics suite. Architecture tests enforce contracts and boundaries.
  Regression tests protect implemented behavior and bug fixes. Physics tests
  compare executed behavior with external references and record their evidence.
  Test modules live in the directory for their suite, shared support remains
  outside suite directories, and a test module belongs to one suite only.
