# zBEMT — Software Requirements

zBEMT is a Blade Element Momentum Theory (BEMT) solver for rotors,
propellers, and eVTOL rotors, exposed through three interfaces (GUI, CLI,
Python library) that share a single engine. This document states the
requirements the software must satisfy.

---

## 1. Scope

### 1.1 The software must support

- Steady-state and quasi-steady BEMT analysis of rotors and propellers,
  including forward flight, climb/descent, and hover.
- Multiple inflow models (Glauert, Coleman, Drees — local and global — and
  Pitt-Peters steady), multiple solvers (Newton-Raphson, fixed-point,
  Aitken, bisection), rotational and compressibility corrections, dynamic
  stall, tip/root loss, and full-range polar extension.
- Batch and parametric sweeps, self-contained HTML reporting, 2D and 3D
  visualization, and analytical/tabulated/NeuralFoil-generated airfoil
  polars.
- Three synchronized interfaces (GUI, CLI, library) built on one engine,
  with GUI/CLI/`.bemt`-file parity as required by §3.3.

### 1.2 The software must not support

- Unsteady/time-marching aerodynamics. Pitt-Peters unsteady and any other
  dynamic time-marching inflow model must not be implemented; zBEMT
  solves steady/quasi-steady flight conditions only.
- Mandatory GUI dependencies in the core engine. The solver and CLI must
  keep running on `numpy` + `scipy` + `matplotlib` + `pandas` alone; a
  batch run on a headless server must never require Qt or 3D graphics.

---

## 2. Product Requirements

- **PR-1 — Three equivalent entry points.** Every capability reachable
  from the GUI must be reachable from the CLI and from a `.bemt` project
  file, and vice versa. A feature implemented in only one interface must
  not be considered complete.
- **PR-2 — Progressive disclosure in the GUI.** Options that do not apply
  to the current configuration must be hidden. Options that exist but are
  incompatible with the current mode must be disabled, not hidden, so the
  user can discover that the option exists without it applying.
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
  field hides its whole row, label included — a visible label pointing at a
  hidden field is a defect.
- **PR-11 — The GUI never freezes.** No user action may block the main
  thread. Solving, batch runs, report generation, polar generation and file
  import run off the main thread; the GUI stays responsive, reports progress,
  can be cancelled, and updates itself as results arrive.

---

## 3. Architectural Requirements

### 3.1 Layering

- `api` must be the only path through which the GUI or CLI run the engine
  or write to disk. `geometry`, `airfoils`, `viz`, and `validation` may be
  imported directly by the GUI/CLI only for on-screen preview and
  drawing; they must not run the engine or write files outside `api`.
- `studies` must orchestrate `bemt` across flight conditions and must
  never touch disk; it must always return `Results` (or `list[Results]`)
  in memory.
- `models` must hold no physics: every `...Def` dataclass must be raw,
  editable, serializable data; physics-aware classes must be constructed
  from them, never duplicated.
- `validation` must return static `Issue`s (error/warning/info) and must
  not run the engine.

### 3.2 Engine correctness

- Convergence must always be tested on the true residual
  `g(lambda) - lambda`, evaluated before relaxation, never on the relaxed
  step. This applies to every solver mode.
- Every physics option must be documented in `bemt.py`'s module
  docstring, mapping the `BEMTConfig` field to its code section.
- A numerical guard (e.g. a protected denominator near a singular
  configuration) must be paired with a correct seed/starting point where
  applicable. A guard that only prevents `NaN` while still allowing
  divergence to a nonphysical value must not be considered a complete
  fix.
- A published correction must reproduce its published closed form. A
  correction implemented as a simplification of the form it is named after —
  a dropped factor, a linearized term — is a defect, not a variant, and must
  be tested against the closed form rather than against a stored number.
- The airfoil polar sources — analytical, tabulated single polar, tabulated
  by radial section, tabulated by Reynolds and/or Mach, Viterna-Corrigan
  extension, and the table+Viterna blend — must be interchangeable behind one
  interface: the engine must not know which source produced a coefficient.
- Every reverse-flow model must be defined on both sides of the boundary, and
  a model advertised as continuous must be continuous at zero tangential
  velocity. A discontinuity there appears as an azimuthal step in the loads,
  not as a solver failure.
- Geometry generation and custom geometry tables must be validated before the
  engine runs: monotonic radial stations, a span inside the hub and tip
  radii, and consistent lengths across the columns.

### 3.3 GUI / CLI / `.bemt` parity

- Every `Project`/`BEMTConfig` field editable in the GUI must be reachable
  from the CLI (dedicated flag or `--set config.<field>=<value>`).
- Every `.bemt` project produced by any of the three paths must traverse
  the other two identically.
- A new configuration field must be wired into all three interfaces
  before the feature is considered complete.
- The three interfaces speak the SAME axis vocabulary: a `.bemt` file
  stores a flight condition under the letters the GUI shows for that
  project's mode, and the CLI's help describes each flag by the slot it
  fills and the letter it carries in each mode. The engine keeps its own
  disk-axes names, which never reach a user-facing surface.

### 3.4 Reports

- `api.generate_report` must be the single implementation used by the GUI
  button, the CLI `--report` flag, and direct library calls. HTML
  assembly must not be duplicated in the GUI layer.
- Section order must be: blade geometry and airfoil polars (inputs) →
  performance coefficients → azimuth/span loads → disk maps →
  convergence.
- The summary table must have one row per condition and one column per
  `Results.summary` key, each with a symbol, unit, and description. A new
  summary key must ship with a column entry.

### 3.5 Documentation

- `docs/documentation.html` is the single physics reference and the embedded
  help source, written in English. Every flag, module, project, batch and
  anchor it cites must exist.
- Structure: introduction (chapters 0-5), one chapter per GUI tab in tab order
  (6-12), reference (13-14).
- A GUI page gets a chapter of its own. Its sections follow the order of the
  blocks and fields on screen. A page is never documented inside a physics
  chapter.
- A field's section is self-contained: the physics, the mathematics, every
  option it offers, and how to set it in the GUI, in `.bemt` and in the CLI as
  three separate paragraphs. A reader must not follow a link to understand or
  set a field. Named models are explained where their control is.
- No class names, function names, package paths or development notes. The
  three interfaces are called GUI, CLI and `.bemt`.
- Each page chapter opens with its tab screenshot from `docs/img/gui/`.
- A field or block belonging to a tab opens a section inside that tab's
  chapter.
- Figures are files under `docs/img/`, never base64 in the HTML. Regenerate
  through `tools/regenerate_documentation_plots.py` against a real example
  project, with all on-screen text in English.
- All mathematical notation, including Greek symbols and subscripts, is
  rendered in LaTeX (per PR-4).
- The index, the per-tab field lists and the screenshots are generated by
  tools and never hand-edited.
- Enforced by `tests/test_documentation.py` and `tests/test_help_content.py`.

### 3.6 GUI tab behaviour

- The Results tab groups a batch into series by the swept variable, within a
  numerical tolerance. Series height and colour are independent controls: a
  series must never encode two quantities at once.
- A tab must reflect the project it has open. A control whose value came from
  a project that has since been closed must not remain offered.
- A tab that mutates the project in memory marks it as unsaved; Save writes
  it and Restore reloads the last saved version.
- Every tab must survive an empty project, a project with no results, and a
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
  reference external to the code — a published formula, a limit the engine
  must reproduce, or a property the model must have (harmonic inflow models
  coinciding in hover, for instance).
