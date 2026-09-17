# zBEMT: Software Requirements

This document is the binding specification for zBEMT. It defines product,
architecture, engine, interface, documentation, GUI, and quality requirements.

Each requirement has a permanent code. Retire a removed code. Never reuse it
for a different requirement. State one independently testable obligation per
requirement and use subcodes when a feature needs several obligations.
Every requirement shall be stated in taxative, normative language ("shall" or "must")
defining concrete system obligations. Rationale, migration history, bug history,
and temporary implementation notes do not belong in this document.

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

#### Core Aerodynamics and Inflow
- **SC-1** — The software shall perform steady-state and quasi-steady BEMT analysis
  of rotors and propellers in hover, forward flight, climb, and descent.
- **SC-2** — The software shall support momentum and finite-state inflow models:
  Glauert, Coleman (local and global), Drees (local and global), and Pitt-Peters
  (steady and dynamic time-marching).
- **SC-3** — The aerodynamic solver shall support local physical corrections on blade elements:
  - **SC-3a** — The solver shall support 3D rotational stall delay and lift augmentation corrections on rotating blade elements.
  - **SC-3b** — The solver shall support subsonic compressibility corrections on airfoil lift and drag coefficients.
  - **SC-3c** — The solver shall support semi-empirical unsteady dynamic stall models, including Leishman-Beddoes and Øye separation lag formulations.
  - **SC-3d** — The solver shall support Prandtl tip loss and root loss attenuation factors on blade circulation and momentum.
  - **SC-3e** — The solver shall support continuous reverse-flow aerodynamic modeling across zero tangential velocity ($U_T = 0$).
  - **SC-3f** — The solver shall support full 360-degree post-stall airfoil polar extension using the Viterna-Corrigan method.
- **SC-4** — The numerical engine shall support root-finding iterative solvers:
  Newton-Raphson, fixed-point relaxation, Aitken acceleration, and bisection.

#### Airfoils and Polars
- **SC-5** — The airfoil geometry generator shall support standard profile parameterizations:
  NACA 4-digit, NACA 5-digit, CST, Bézier, PARSEC, Joukowski, biconvex, and imported coordinate contours.
  - **SC-5a** — Each analytical airfoil family shall provide dedicated parameter editor controls in the GUI without requiring manual external file preparation.
  - **SC-5b** — Profile generator parameters shall persist as structured `generator_params` blocks inside `inputs/airfoil.bemt`.
- **SC-6** — The software shall support airfoil polar data from analytical representations,
  multi-dimensional tabulated grids, and automated generation through NeuralFoil or XFOIL.
- **SC-7** — Tabulated airfoil polar definitions shall specify aerodynamic lift ($C_L$),
  drag ($C_D$), and pitching moment ($C_M$) coefficients as functions of angle of attack ($\alpha$).
  Tabulated data shall support multi-dimensional grids parameterized over Reynolds number ($Re$)
  and Mach number ($M$). The BEMT solver shall interpolate coefficients across $(\alpha, Re, M)$
  during blade-element evaluation.
  - **SC-7a** — A tabulated airfoil definition shall support radial variation across blade span
    stations through normalized radial coordinates ($r/R$ or `r_norm`). Section interpolation
    across radial stations shall evaluate local coefficients along the blade.
  - **SC-7b** — Airfoil table import, CSV export, `.bemt` project serialization, and external
    generation tools shall preserve all defined polar columns ($C_L, C_D, C_M$) and multi-dimensional
    grid dimensions without loss of precision.
- **SC-8** — The software shall support XFOIL as an external viscous airfoil polar
  computation engine.
  - **SC-8a** — The XFOIL executable shall resolve sequentially from `ZBEMT_XFOIL_BIN`,
    the persisted GUI selection, system `PATH`, and standard platform install directories.
  - **SC-8b** — XFOIL generation shall write dedicated execution scripts per Reynolds number
    and shall apply Prandtl-Glauert compressibility post-corrections.
  - **SC-8c** — Viscous transition parameters (`ncrit`, `xtr_top`, `xtr_bot`) shall apply
    exclusively to XFOIL execution and shall be rejected by NeuralFoil.
  - **SC-8d** — A missing XFOIL executable shall disable only XFOIL generation and shall raise
    a `RuntimeError` stating the cause and available remedies.

#### Operating Flight Conditions and Kinematics
- **SC-9** — The flight condition definition shall support a complete 3D free-stream velocity
  vector in vehicle coordinates ($V_x$ longitudinal, $V_y$ lateral, $V_z$ vertical), which maps
  to disk axes according to the active mode: in rotor mode, $V_x$ and $V_y$ are in-plane components
  while $V_z$ is axial along the vertical shaft; in propeller mode, $V_x$ is axial airspeed along
  the horizontal shaft while $V_y$ and $V_z$ are transverse cross-flow components perpendicular to the shaft.
  - **SC-9a** — The lateral velocity component shall accept dimensional speed ($V_y$), in-plane
    advance ratio ($\mu_y$), advance coefficient ($J_y$), or aerodynamic sideslip angle ($\beta$
    or `sideslip_deg`) as mutually exclusive equivalent specifications.
  - **SC-9b** — All velocity components ($V_x, V_y, V_z$ or non-dimensional advance ratios
    $\mu_x, \mu_y, \mu_z, J_x, J_y, J_z$ and orientation angles $\alpha, \beta$) shall be fully
    supported across fixed flight condition inputs, parametric batch sweep axes, results summary
    tables, CSV data exports, and HTML reports.
  - **SC-9c** — Aerodynamic sideslip angle $\beta$ (`sideslip_deg`) shall specify the azimuth
    direction of longitudinal in-plane flow bounded within $\pm 89^\circ$; pure sideward flight
    shall be specified through lateral velocity $V_y$ or advance ratio $\mu_y$.

#### Studies, Optimization, and Dynamic Tools
- **SC-10** — The software shall support single-point case execution, batch execution,
  and multi-variable parametric sweeps across operating conditions and geometry parameters.
- **SC-11** — The Geometry Designer shall evaluate and compare labeled blade planform variants
  against a designated baseline geometry across selected flight conditions while holding
  non-geometry parameters fixed by default.
  - **SC-11a** — Named geometry comparisons shall persist in `inputs/comparisons.bemt` with
    their constituent variants, evaluation flight conditions, and trim configurations.
  - **SC-11b** — The Geometry Designer shall support explicit radial table overrides,
    one-parameter variation sweeps, parametric planform generators (rectangular, linear
    taper, elliptic), and imported project blades.
  - **SC-11c** — The comparison solver shall support constant-loading trim modes holding
    thrust or thrust coefficient ($C_T$) constant (converging via bisection, trimming rotational
    speed in propeller mode and collective pitch in rotor mode); targets outside the solvable
    physical bracket shall raise an explicit named error.
  - **SC-11d** — Comparison outputs shall report performance ranking metrics, deltas relative
    to baseline planform (percentage change for non-zero metrics and absolute difference for
    zero-crossing values), and blade geometric parameters (root cutout, radius, aspect ratio $AR$,
    and solidity $\sigma$).
- **SC-12** — The optimization engine shall execute bounded single-objective planform
  optimization studies over defined blade geometry variables at prescribed operating
  conditions using Powell or Nelder-Mead algorithms, persisting study configurations in
  `inputs/optimizations.bemt`.
  - **SC-12a** — Single-objective optimization searches shall initialize at bound midpoints,
    strictly enforce parameter boundaries, and penalize unconverged solver evaluations.
  - **SC-12b** — Single-objective optimization capabilities shall be fully accessible through
    the CLI `--optimize` interface and Python library `api`.
- **SC-13** — The multi-objective optimization tool shall execute evolutionary genetic algorithms
  (NSGA-II) across bounded planform parameters, evaluate competing aerodynamic metrics, and
  generate Pareto-optimal trade-off frontiers.
- **SC-14** — The dynamic solver shall compute periodic steady-state rigid-blade flapping and
  lead-lag responses with flapping hinge offset, root restraint springs, and pitch-flap
  coupling ($k_1$). The solver shall evaluate Fourier azimuthal coefficients ($\beta_0, \beta_{1c}, \beta_{1s}$)
  and default to rigid unarticulated blades when articulation is disabled.
- **SC-15** — The transient simulation engine shall time-march rotor operating states along
  prescribed flight trajectories, dynamically coupling Pitt-Peters unsteady dynamic inflow
  states and Øye dynamic stall separation lag states with quasi-steady blade-element forces
  at each discrete time step.
- **SC-16** — The stability derivative tool shall evaluate complete rotor hub force ($X, Y, Z$)
  and moment ($L, M, N$) stability and control derivatives via numerical finite-difference
  perturbations about a converged trim operating state. Perturbations shall cover all six
  rigid-body velocity states and rates ($u, v, w, p, q, r$), rotational speed ($\Omega$), and
  rotor control degrees of freedom (collective pitch $\theta_0$, longitudinal cyclic $\theta_{1c}$,
  and lateral cyclic $\theta_{1s}$), generating the full matrix of force derivatives
  ($X_u, X_v, X_w, X_p, X_q, X_r, X_\Omega, X_{\theta_0}, X_{\theta_{1c}}, X_{\theta_{1s}}$;
  $Y_u, Y_v, Y_w, Y_p, Y_q, Y_r, Y_\Omega, Y_{\theta_0}, Y_{\theta_{1c}}, Y_{\theta_{1s}}$;
  $Z_u, Z_v, Z_w, Z_p, Z_q, Z_r, Z_\Omega, Z_{\theta_0}, Z_{\theta_{1c}}, Z_{\theta_{1s}}$),
  moment derivatives ($L_u, L_v, L_w, L_p, L_q, L_r, L_\Omega, L_{\theta_0}, L_{\theta_{1c}}, L_{\theta_{1s}}$;
  $M_u, M_v, M_w, M_p, M_q, M_r, M_\Omega, M_{\theta_0}, M_{\theta_{1c}}, M_{\theta_{1s}}$;
  $N_u, N_v, N_w, N_p, N_q, N_r, N_\Omega, N_{\theta_0}, N_{\theta_{1c}}, N_{\theta_{1s}}$),
  and rotor torque and power sensitivities.

#### Interfaces, Reporting, and Visualization
- **SC-17** — The software shall provide equivalent functional access via graphical interface
  (GUI), command-line interface (CLI), and Python library (`api`). All project inputs,
  geometry definitions, and solver settings shall persist in `.bemt` files.
- **SC-18** — The software shall export case, batch, and study results to self-contained
  HTML reports (with embedded vector plots, numerical summaries, and convergence statistics)
  and structured CSV data files.
- **SC-19** — The software shall provide 2D radial and azimuthal distribution plots,
  planar disk load maps, and interactive 3D rotor geometry visualization.

### 1.2 Excluded capabilities

- **SC-20** — Free-wake, prescribed-wake, vortex-lattice inflow, and computational fluid
  dynamics (CFD) shall be out of scope.
  - **SC-20a** — Supported inflow fields shall remain limited to annular-momentum and finite-state
    dynamic formulations.
- **SC-21** — Modal and finite-element structural blade elasticity shall be out of scope; blade
  degrees of freedom shall remain rigid-body flapping and lagging under `SC-14`.
- **SC-22** — The core BEMT solver and CLI shall run without graphical dependencies (Qt or 3D
  visualization libraries); their required numerical stack shall consist exclusively of
  NumPy, SciPy, Matplotlib, and pandas.

## 2. Product Requirements

- **PR-1** — GUI, CLI, and `.bemt` project interfaces shall expose equivalent user-configurable
  capabilities unless explicitly scoped to fewer interfaces by another requirement.
- **PR-2** — Form controls inapplicable to the active configuration shall be hidden. Controls
  that are applicable but temporarily blocked by a prerequisite shall remain visible and disabled.
- **PR-3** — Every configurable input field shall provide a hover tooltip and a clickable label
  that opens contextual documentation.
  - **PR-3a** — Field help shall describe governing equations, physical principles, valid input
    ranges, and link to `docs/documentation.html`.
  - **PR-3b** — Field-to-documentation navigation mappings shall derive automatically from control
    metadata and shall not require manual link tables.
- **PR-4** — User-facing mathematical variables, Greek symbols, subscripts, and exponents shall
  be displayed using rendered mathematical typography rather than raw code identifiers.
- **PR-5** — Generated HTML reports shall be completely self-contained and readable offline
  without network access or external asset files.
  - **PR-5a** — Large batch reports shall split into a master page and linked satellite pages
    without truncating or omitting evaluated case data.
- **PR-6** — Static configuration validators shall detect and reject invalid, incomplete, or
  physically contradictory inputs before solver execution in both GUI and CLI workflows.
  - **PR-6a** — The GUI shall present pre-execution validation status through the persistent
    workflow status indicator.
- **PR-7** — Missing optional dependencies (PyVista, NeuralFoil, Plotly) shall disable only
  the specific dependent features while preserving all core BEMT capabilities.
- **PR-8** — User-facing labels, angle definitions, summary metrics, plots, CLI options, and
  `.bemt` keys shall adhere to the active vehicle convention (rotor or propeller) rather than
  internal disk-axis terminology.
  - **PR-8a** — Each vehicle mode shall expose only velocity and angle components physically
    meaningful within that convention.
- **PR-9** — Every plot title shall state the operating condition, flight speed, and rotor
  configuration represented by the figure.
  - **PR-9a** — Plotted data, legends, axes labels, and annotations shall not overlap or obscure
    graphical content.
  - **PR-9b** — Rotor disk load maps shall explicitly state their azimuthal coordinate convention
    and blade rotation direction.
- **PR-10** — Editable input fields shall align consistently within and across related GUI forms.
  - **PR-10a** — Action buttons presented within a group shall maintain uniform widths.
  - **PR-10b** — User-facing text shall not be clipped, truncated, or overflow visible boundaries
    in labels, buttons, tooltips, or dialogs.
  - **PR-10c** — Hiding a form input shall hide both its label and its editor widget simultaneously.
  - **PR-10d** — Dropdown selection menus shall display all available choices without scrolling
    when the option count fits within the popup ceiling.
- **PR-11** — Long-running computations shall execute asynchronously without blocking the GUI
  main event loop, shall report progress, and shall support user cancellation.
  - **PR-11a** — Heavy GUI operations including table population and plot rendering shall execute
    once per user action or coalesced event burst.
- **PR-12** — Multi-panel plots shall maintain a readable minimum panel size and shall scroll
  within their viewport when space is constrained.
  - **PR-12a** — Plot typography shall maintain point sizing and shall not shrink arbitrarily
    when viewport dimensions change.
  - **PR-12b** — Single-panel plots shall fill available drawing areas without imposing artificial
    minimum-size constraints.
  - **PR-12c** — Plot minimum dimensions shall not force containing application windows to expand
    beyond user screen boundaries.
- **PR-13** — Every editable dimensional input shall display its physical unit; every
  dimensionless parameter shall display `[-]`.
- **PR-14** — Each Engineering Tool launcher card shall state the primary engineering objective,
  required prerequisites, and output results produced by that Tool.
  - **PR-14a** — Each Engineering Tool window shall provide a numbered task workflow,
    current-step guidance, Back and Next buttons, and direct step navigation.
  - **PR-14b** — Advanced numerical solver options in Engineering Tools shall be collapsed by default.
  - **PR-14c** — Opening an empty study in an Engineering Tool shall guide the user to the initial
    valid action without displaying errors.

## 3. Architectural Requirements

### 3.1 Layering

- **AR-1** — GUI and CLI layers shall invoke the BEMT engine and persist data exclusively through
  the `api` module; direct access to `geometry`, `airfoils`, `viz`, and `validation` shall be
  restricted to local previews and static checks.
- **AR-2** — The `studies` module shall orchestrate multi-condition BEMT executions in memory
  without writing to disk and shall return structured `Results` objects.
- **AR-3** — The `models` module shall contain raw serializable data definitions (`...Def`);
  solver logic and physical calculations shall reside outside dataclass definitions.
- **AR-4** — The `validation` module shall perform purely static configuration audits returning
  `Issue` records without executing numerical solver routines.
- **AR-5** — `zbemt/nomenclature.py` shall serve as the authoritative single source of truth for
  axis conventions, symbols, units, tooltips, and key mappings across rotor and propeller modes.
- **AR-6** — Vehicle-axis key translation shall be a strictly reversible one-pass mapping;
  user-facing keys shall convert to internal disk-axis keys only at interface boundaries.

### 3.2 Engine Correctness

- **EN-1** — Every iterative solver shall evaluate convergence residuals on the raw fixed-point
  step $|g(\lambda) - \lambda|$ before applying relaxation factors.
- **EN-2** — The `bemt.py` module docstring shall maintain an explicit cross-reference table
  linking each `BEMTConfig` option to the code block implementing it.
- **EN-3** — Numerical singularity guards shall be paired with physically valid fallback seeds
  to ensure robust convergence across extreme operating regimes.
- **EN-4** — Aerodynamic corrections named after published literature shall reproduce the
  published closed-form equations within numerical tolerances.
- **EN-5** — All airfoil polar representations (analytical, single polar, multi-station radial
  tables, Reynolds/Mach grids, and extended polars) shall implement a unified coefficient query
  interface; the BEMT engine shall be agnostic to polar origin.
- **EN-6** — Reverse-flow drag and lift formulations shall be defined continuously across zero
  tangential velocity ($U_T = 0$).
- **EN-7** — Radial geometry tables shall validate monotonic spanwise progression, non-negative
  radius values, and equal-length coordinate columns prior to solver execution.
- **EN-8** — Harmonic-balance dynamic solvers shall record evaluated harmonic counts and shall
  evaluate the full damped harmonic operator. A zero stiffness detuning
  ($\nu^2-n^2=0$) shall remain solvable when aerodynamic or mechanical damping keeps the
  operator nonsingular. The solver shall reject only a singular or numerically near-singular
  two-by-two harmonic system rather than returning an unbounded finite quantity.
- **EN-9** — Transient time-marching solvers shall record total simulated duration, time-step
  increments, and periodic settling metrics; unsettled transient states shall not be flagged as converged.
- **EN-10** — Section drag formulations resolving 3D radial cross-flow shall decompose drag along
  the true relative velocity vector rather than applying scalar drag factor scaling.
  - **EN-10a** — The radial drag component shall contribute to in-plane rotor hub forces and shall
    not generate shaft torque or shaft power.
  - **EN-10b** — Radial-flow drag contributions shall be isolated and reported as distinct result
    fields in performance outputs.
  - **EN-10c** — Under constant section drag coefficient, the radial-flow formulation shall match
    classical reference limits: $C_{H,\text{profile}} = \frac{1}{4}\sigma C_{d0}\mu$ without radial
    resolution and $\frac{3}{8}\sigma C_{d0}\mu$ with full vector resolution, with profile power
    factor transitioning from $(1 + \mu^2)$ to $(1 + 1.5\mu^2)$.
- **EN-11** — The solution validator shall emit explicit warnings when any radial blade element
  fails to achieve convergence tolerance, reporting the converged element percentage.
- **EN-12** — Blade aspect ratio ($AR$) and rotor solidity ($\sigma$) shall be referenced to the
  full theoretical blade spanning from root axis ($r/R = 0$) to tip ($r/R = 1$), defined as
  $AR = R^2 / S_{\text{ref}}$ and $\sigma = N_b S_{\text{ref}} / (\pi R^2)$.
  - **EN-12a** — Root cutout shall truncate aerodynamic integration bounds but shall not alter
    reference blade aspect ratio or solidity when the reference planform is preserved.
  - **EN-12b** — For tapered blades, `root_chord_norm` shall represent the extrapolated theoretical
    root chord at $r/R = 0$ and `tip_chord_norm` shall represent the chord at $r/R = 1$.
- **EN-13** — In rotor mode, axial velocity $V_z$, axial inflow ratio $\lambda_z = V_z/(\Omega R)$,
  advance ratio $\mu_z$, advance coefficient $J_z$, and total axial flow shall be defined positive
  through the disk in the induced flow direction (free-stream flow arriving from above, as in
  axial climb where upward vehicle motion produces downward relative wind through the rotor).
  Total axial inflow shall satisfy $\lambda_{\text{total}} = \lambda_z + \lambda_i$; positive
  $V_z$ shall reduce rotor thrust.
  - **EN-13a** — In rotor mode, rotor angle of attack $\alpha_{\text{rotor}}$ shall be measured from
    the disk plane as $\alpha_{\text{rotor}} = -\operatorname{atan2}(V_z, V_x)$, where positive
    $\alpha_{\text{rotor}}$ corresponds to negative $V_z$ (free-stream flow arriving from below the
    disk plane, as in descent, autorotation, or flared pitch-up attitude).
- **EN-14** — In propeller vehicle axes, axial cruise velocity $V_x$ shall be directed along the
  propeller shaft, and vertical cross-flow $V_z$ shall be defined positive when the free stream
  arrives from above. Propeller disk angle of attack $\alpha_{\text{disk}}$ shall be measured from
  the shaft axis as $\alpha_{\text{disk}} = \operatorname{atan2}(-V_z, |V_x|)$, where positive
  $\alpha_{\text{disk}}$ corresponds to cross-flow arriving from below (as in aircraft pitch-up
  attitude). Pure axial cruise shall satisfy $V_z = 0$ and $\alpha_{\text{disk}} = 0^\circ$.
- **EN-15** — Longitudinal and lateral in-plane free-stream flow shall resolve into unified in-plane
  magnitude and wake azimuth: $\mu_{\text{inplane}} = \sqrt{V_x^2 + V_y^2} / (\Omega R)$ and
  $\psi_w = \operatorname{atan2}(V_y, V_x)$.

### 3.3 GUI, CLI, and `.bemt` Parity

- **PA-1** — Every project configuration and solver parameter configurable through the GUI shall
  be accessible from the CLI via direct flags or `--set`.
- **PA-2** — Project configurations persisted to `.bemt` files shall round-trip through GUI,
  CLI, and Python library interfaces without semantic data loss or schema distortion.
- **PA-3** — Any newly introduced configuration parameter shall be implemented across GUI, CLI,
  and `.bemt` serialization simultaneously before feature completion.
- **PA-4** — GUI, CLI, reports, data exports, and `.bemt` files shall utilize identical vehicle-axis
  nomenclature corresponding to the active mode (rotor or propeller); internal engine modules
  shall maintain invariant disk axes.
  - **PA-4a** — A `.bemt` flight condition shall serialize axis identifiers matching GUI display
    nomenclature for that mode; internal disk-axis labels shall not appear in persisted user files.
  - **PA-4b** — CLI help strings shall document each flight-condition parameter by physical purpose
    and corresponding rotor/propeller mode symbols.
  - **PA-4c** — Vehicle coordinate systems shall define vehicle $x$ as longitudinal forward, vehicle
    $y$ as lateral starboard (right), and vehicle $z$ as vertical upward.
  - **PA-4d** — Rotor mode shall align the rotor shaft vertically along vehicle $z$; propeller mode
    shall align the propeller shaft horizontally forward along vehicle $x$.
  - **PA-4e** — Propeller display mapping shall swap internal disk-axis pairs $V_x \leftrightarrow V_z$,
    $\mu_x \leftrightarrow \mu_z$, and $J_x \leftrightarrow J_z$. Internal $\lambda_z$ shall display
    as $\lambda_x$, and internal $V_{z,\text{total}}$ shall display as $V_{x,\text{total}}$. Rotor mode
    shall preserve corresponding $x$ and z labels directly.
  - **PA-4f** — `alpha_rotor_deg` shall be exposed in rotor mode and hidden in propeller mode.
    `alpha_disk_deg` shall be exposed in propeller mode and hidden in rotor mode.
- **PA-5** — When the GUI accepts alternative parameter representations (for example, speed vs.
  advance ratio vs. angle), CLI and `.bemt` interfaces shall accept identical alternatives.
  - **PA-5a** — Alternative input forms shall resolve to one canonical internal representation;
    conflicting duplicate inputs shall be rejected rather than silently resolved.
  - **PA-5b** — Incomplete or mutually incompatible flight condition inputs shall be rejected with
    explicit error messages before solver invocation.
  - **PA-5c** — Alternate angle forms shall derive axial flow in rotor mode and vertical cross-flow
    in propeller mode using the sign conventions specified in `EN-13a` and `EN-14`.
  - **PA-5d** — Aerodynamic angles shall be rejected when required reference velocities are omitted,
    when redundant angle forms conflict, or when direct velocity components are simultaneously supplied.

### 3.4 Reports

- **RP-1** — The reporting system shall generate HTML reports via `api.generate_report` as the
  single canonical path shared across GUI, CLI, and Python library.
- **RP-2** — Report documents shall present sections in ordered sequence: blade geometry and polars,
  global performance summary, radial and azimuthal load distributions, disk maps, and solver convergence.
- **RP-3** — The summary results table shall include every evaluated condition with columns
  corresponding to all `Results.summary` keys, complete with symbol, unit, and description headers.

### 3.5 Documentation

- **DC-1** — `docs/documentation.html` shall serve as the single authoritative user documentation
  and the direct source for embedded GUI help.
  - **DC-1a** — Every flag, project, batch option, field name, and anchor cited in documentation
    shall exist in the codebase.
- **DC-2** — The documentation structure shall maintain Chapters 0 through 5 for physical
  methodology, Chapters 6 through 12 for the seven primary GUI tabs, Chapters 13 through 16 for
  Engineering Tools (Geometry Designer, Optimization, Transient, Stability), Chapters 17 and 18
  for CLI and limitations, followed by nomenclature and references.
- **DC-3** — Each GUI tab chapter shall follow the exact visible layout sequence and group-box
  order of the corresponding interface tab.
- **DC-4** — Every field documentation entry shall be self-contained, specifying governing equations,
  physical rationale, valid bounds, and options.
  - **DC-4a** — Every field entry shall explain configuration procedures across GUI, `.bemt`, and
    CLI in separate dedicated paragraphs.
  - **DC-4b** — Theoretical models shall be explained in the documentation section of their
    controlling configuration field.
- **DC-5** — User documentation prose shall omit internal implementation class names, function
  names, and file paths, referencing interfaces exclusively as GUI, CLI, and `.bemt`.
- **DC-6** — Each GUI chapter shall open with an official screenshot of the current tab matching
  `docs/img/gui/`.
- **DC-7** — All configurable fields and option blocks belonging to a GUI tab shall be documented
  within that tab's chapter.
- **DC-8** — Documentation illustrations shall reside as standalone image files under `docs/img/`
  generated from authentic project models with English labels.
- **DC-9** — Documentation prose shall follow the standard mathematical notation conventions
  defined in `PR-4`.
- **DC-10** — The master index, per-tab field tables, and interface screenshots shall be
  automatically generated artifacts and shall not be edited by hand.
- **DC-11** — Automated architecture tests shall verify documentation integrity, link validity,
  and interface synchronization upon every change.
- **DC-12** — The Engineering Tools launcher and Tool chapters shall match GUI task steps, control
  labels, action buttons, table columns, and launcher card descriptions.
  - **DC-12a** — Configurable parameter names within Tool chapters shall link to their primary field
    definitions in main tab documentation.
- **DC-13** — Interface references shall be decorated with semantic styling: GUI elements using
  `<span class="gui">`, CLI flags using `<span class="cli">`, and `.bemt` keys using `<span class="bemt">`.
- **DC-14** — Cross-references between documentation chapters shall use descriptive hyperlinks
  containing the target section title rather than bare numbers.
- **DC-15** — Tab chapters 6 through 16 shall contain complete self-contained parameter guidance
  and shall not defer essential configuration instructions to external chapters.

### 3.6 GUI Tab Behavior

- **TB-1** — The Results tab shall group batch results into distinct series by swept parameter
  within numerical tolerance, preserving independent series height and color encodings.
- **TB-2** — GUI tabs shall reflect the active project state and shall not retain stale choices
  or options from previously opened projects.
- **TB-3** — Modifying parameters in any tab shall mark the project state as unsaved; saving
  shall persist changes to `.bemt` files, and revert shall reload the last saved state.
- **TB-4** — Every GUI tab shall handle empty projects, unrun cases, and switching between rotor
  and propeller modes without data loss or interface exceptions.
- **TB-5** — The Geometry radial table shall support multi-cell clipboard pasting starting at the
  selected cell, automatically adding rows as required by clipboard dimensions.
  - **TB-5a** — The radial table shall accept tab-delimited, semicolon-delimited, and comma-separated
    tabular text, correctly handling decimal points and decimal commas.
  - **TB-5b** — Clipboard paste operations shall validate the full pasted block prior to updating
    model state, committing all changes in a single atomic transaction.

## 4. Quality Requirements

- **QR-1** — Any solver or business logic bug fix shall include an automated regression test that
  reproduces the defect before the fix and passes thereafter.
- **QR-2** — Proposed code changes shall pass the full test suite (`python tests/run_all_tests.py`)
  before being considered complete.
- **QR-3** — The test suite shall maintain versioned project configurations covering all supported
  airfoil sources, inflow models, stall corrections, and vehicle modes.
- **QR-4** — Any modification to project configuration schemas or `models.py` dataclasses shall be
  validated using `python tools/check_project_configs.py`.
- **QR-5** — All codebase comments, docstrings, documentation, commit messages, and user-facing
  text shall be written in formal technical English following ASD-STE100 guidelines.
- **QR-6** — Changes altering user-visible or documented software behavior shall update corresponding
  documentation in the same revision.
- **QR-7** — All codebase components, external dependencies, and generated assets shall be strictly
  compatible with GPL-3.0-or-later licensing.
- **QR-8** — Every implemented physical model and correction shall possess dedicated tests
  validating its numerical output against external literature, published formulas, or physical benchmarks.
- **QR-9** — Identifiers throughout `zbemt/`, `tools/`, and `tests/` shall use descriptive English
  naming reflecting their engineering purpose.
  - **QR-9a** — New internal symbols, HTML identifiers, and Qt object/slot names shall use standard
    English terminology.
- **QR-10** — The test suite shall be organized into distinct architecture, regression, and physics
  suites orchestrated by a unified runner. Architecture tests shall guard interfaces and documentation;
  regression tests shall protect software behaviors; physics tests shall validate against external references.
