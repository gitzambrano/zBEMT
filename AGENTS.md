# AGENTS.md

Instructions for this repository.

Instructions for this repository.

Architecture, product/report decisions, and quality requirements live in
`docs/software_requirements.md`. This file is only direct rules for the
agent.

## Language

Write everything in English: code, comments, docstrings, commit messages,
GUI/CLI/report/doc text. Do not mix languages in a single file.

## Core workflow

1. Reproduce a bug before fixing it.
2. Add a regression test for logic fixes (not pure layout/styling). It
   must fail before the fix and pass after.
3. Run the full test suite once, at the end, after all requested changes
   are done.
4. Never mark work as done with a failing test or a partial
   implementation.
5. If a fix changes documented behavior, update that documentation in the
   same change.
6. Verify a subagent's work actually landed — `git status`/`git diff` and
   a real test run, not the subagent's own summary.

## Subagents

Spin up Haiku subagents for mechanical, repetitive, or low-judgment work:
translation passes, applying the same edit across many files, boilerplate
generation, running/parsing test output, simple refactors with a clear
pattern. Keep architectural decisions, physics changes, and anything
touching `bemt.py` for yourself.

## Commands

```bash
pip install -e ".[all]"                 # install (from repo root)

python tests/run_all_tests.py           # full suite -- ONE PROCESS PER FILE
python tests/run_all_tests.py -k airfoil          # only files matching

python -m pytest tests/test_bemt.py      # single file
python -m pytest tests/test_bemt.py::TestSolveBemtHover -v   # single class

zbemt-gui                               # GUI
zbemt --project projects/starter_rotor  # CLI (also runs standalone, zero args)
zbemt --project projects/MyRotor --validate-only   # before long batch

python tools/check_project_configs.py   # sanity-check every projects/* folder
```

Every script under `zbemt/` and `tools/` runs with zero arguments — a
`DEFAULT_*` constant near the top of the file supplies what a flag would
normally give it. This includes running the file directly.

GUI tests run headless (`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`
and the `Agg` backend). No linter is configured.

**Run the full suite with `tests/run_all_tests.py`, never with a bare
`pytest tests/`.** A single pytest process accumulates Qt/matplotlib canvases
across dozens of files and dies with a native access violation
(`test_gui_layout.py::setUpClass`, exit 139) — a teardown-ordering crash, not
a test failure, and it hides every result after it. The runner gives each file
its own process, writes `tests/resultado_testes.txt` with a traceback per
failure, and is what CI (`.github/workflows/tests.yml`) uses. A single file or
class through `python -m pytest` is fine.

## Layout

```
zbemt/
  api.py  studies.py  bemt.py  models.py  validation.py
  geometry.py  airfoils.py  external_solvers.py  paths.py  cli.py
  gui/  app.py  common.py  workers.py  dialogs.py  widgets.py  styles.py
        tabs/  project  geometry_tab  airfoil  config  run_case  run_batch  results
  viz/  plots.py  visualization.py  style.py
```

`api` is the only path through which GUI/CLI run the engine or touch disk.
Before touching `bemt.py`, read its module docstring — it maps every
`BEMTConfig` option to its code section.

## Axes convention

### Axes convention (rotor vs propeller)

**Vehicle axes (what the user sees):** **x** is always longitudinal (horizontal
forward) and **z** is always vertical (up). The on-screen symbols use these
letters everywhere — GUI, results table, plots, reports.

**Vehicle orientation:** a **rotor** is assumed to have a **vertical** shaft; a
**propeller** is assumed to have a **horizontal** shaft (along the aircraft
longitudinal axis). Because the shaft direction differs, the **same letter**
(x or z) names **different physical components** in the two modes.

**Batch / Run Case slot names** (from `gui/widgets.py` and `gui/common.py`):

| Mode      | Slot (engine name) | Batch axis label         | Physical flow                          |
| --------- | ------------------ | ------------------------ | -------------------------------------- |
| Rotor     | `inplane`        | Edgewise (in-plane) Flow | Advance in the disk plane              |
| Rotor     | `axial`          | Axial (along-shaft) Flow | Climb/descent along the shaft          |
| Propeller | `inplane`        | Cross (in-plane) Flow    | Cross-flow across the shaft (vertical) |
| Propeller | `axial`          | Axial (along-shaft) Flow | Airspeed along the shaft               |

#### Rotor mode — input and output symbols

Shaft vertical: **x** = in-plane (edgewise), **z** = along shaft (axial).

| Flow                 | GUI units (dropdown)                 | Shown in results               | Engine /`FlightCondition` key                              | `.bemt` / CLI key | Definition                                                                         |
| -------------------- | ------------------------------------ | ------------------------------ | ------------------------------------------------------------ | ------------------- | ---------------------------------------------------------------------------------- |
| Edgewise             | μ_x, J_x, V_x [m/s]                 | μ_x, J_x, V_x                 | `mu_x`, `J_x`, `Vx`                                    | same                | V_x/(ΩR), V_x/(nD)=π·μ_x, dimensional speed in the disk plane                  |
| Axial                | α_rotor [deg], V_z [m/s], μ_z, J_z | α_rotor, V_z, μ_z, J_z, λ_z | `alpha_rotor_deg`, `Vz`, `mu_z`, `J_z`, `lambda_z` | same                | α_rotor=atan2(V_z,V_x); climb (+) / descent (−) along shaft; λ_z=V_z/(ΩR)=μ_z |
| Axial total (output) | —                                   | V_z,total, λ_total            | `Vz_total`, `lambda_total`                               | same                | V_z,total = V_z + v_i; λ_total = λ_z + λ_i                                      |
| Induced (output)     | —                                   | v_i, λ_i                      | `Vi`, `lambda_i`                                         | same                | Along the shaft; letters do not rotate with mode                                   |

Typical rotor flight: edgewise μ_x > 0, α_rotor ≈ 0° (level forward cruise).

#### Propeller mode — input and output symbols

Shaft horizontal: **x** = along shaft (axial), **z** = vertical (cross-flow in
the disk plane).

| Flow                 | GUI units (dropdown)                | Shown in results        | Engine /`FlightCondition` key               | `.bemt` / CLI key                           | Definition                                                                                     |
| -------------------- | ----------------------------------- | ----------------------- | --------------------------------------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Axial                | J_x, μ_x, V_x [m/s]                | J_x, μ_x, V_x, λ_x    | `Vz`, `mu_z`, `J_z`, `lambda_z`       | `Vx`, `mu_x`, `J_x`, `lambda_x`       | Aircraft airspeed along shaft; J_x=V_x/(nD) is the classic propeller advance ratio             |
| Cross                | V_z [m/s], α_disk [deg], μ_z, J_z | V_z, α_disk, μ_z, J_z | `Vx`, `mu_x`, `J_x`, `alpha_disk_deg` | `Vz`, `mu_z`, `J_z`, `alpha_disk_deg` | Cross-flow; zero in straight cruise; α_disk=atan2(V_z,V_x), 0° when stream aligns with shaft |
| Axial total (output) | —                                  | V_x,total, λ_total     | `Vz_total`, `lambda_total`                | `Vx_total`, `lambda_total`                | V_x,total = V_x + v_i                                                                          |
| Induced (output)     | —                                  | v_i, λ_i               | `Vi`, `lambda_i`                          | same                                          | Along the shaft (shown as v_i along x in propeller mode)                                       |

Typical propeller flight: axial flow J_x (or V_x) set in the **Axial** field; cross
V_z = 0, α_disk = 0°.

#### Letter rotation summary (propeller display only)

The BEMT engine always works in disk axes, never vehicle axes: `bemt.py`,
`FlightCondition` and `Results.summary` in memory keep the internal key below,
in every mode. What rotates when `is_propeller=True` is everything the user
meets — the displayed symbol, and the key written into `.bemt` files, CSV
headers and the results table.

**One module owns the whole rotation: `zbemt/nomenclature.py`.** Edit a symbol,
a unit, a tooltip or a slot name there and every surface follows — the GUI
fields, the results table, the plots, the HTML report, the CLI help and the
`.bemt` writer. Do not add a second table anywhere; that is what this
consolidated the ten of them into.

Two rules that module depends on, and that a change must not break:

- The rotation is a **swap** (`mu_x` ↔ `mu_z`), so it is applied in ONE pass
  into a NEW dict (`to_display_keys`). Renaming key by key collapses both
  components onto one value, silently and plausibly.
- A rotated dict is an **output**. It is never fed back into the application;
  only `from_display_keys`, at the boundary that produced it, turns it back.

| Internal key        | Rotor label  | Propeller label |
| ------------------- | ------------ | --------------- |
| `Vz`              | V_z          | V_x             |
| `Vx`              | V_x          | V_z             |
| `mu_x`            | μ_x         | μ_z            |
| `mu_z`            | μ_z         | μ_x            |
| `J_x`             | J_x          | J_z             |
| `J_z`             | J_z          | J_x             |
| `lambda_z`        | λ_z         | λ_x            |
| `Vz_total`        | V_z,total    | V_x,total       |
| `alpha_rotor_deg` | α_rotor     | *(hidden)*    |
| `alpha_disk_deg`  | *(hidden)* | α_disk         |

## Field help

Every configurable field must have a popup that clearly explains the
physics and mathematics behind it. To hide a form field, use
`common.definir_linha_visivel`, never `widget.setVisible(False)` or
`form.setRowVisible(widget, …)` directly.

When moving or adding a field, run `python tools/field_index.py --escrever`.

## Documentation (`docs/documentation.html`)

Structure:

```
0-5   Introduction  how to think · installation · GUI/CLI/.bemt · tutorial ·
                    nomenclature and axes · the method
6-12  THE PAGES     Project · Geometry · Airfoil · Config/Engine ·
                    Run Case · Run Batch · Results
13-14 Reference     command line · limitations
```

Rules:

1. One chapter per GUI tab, in tab order. Only the introduction chapters may
   span tabs. Never document a page inside a physics chapter.
2. Inside a chapter, follow the GUI: block by block, field by field.
3. No links out of a field's section. Put the physics, the mathematics, the
   options and the ranges in that section. Explain a named model (Glauert,
   Øye, Prandtl, Newton, Viterna) where its control is.
4. Every field: what it is physically, the equation it enters, every option
   it offers, then GUI, `.bemt` and CLI as three separate paragraphs in that
   order.
5. No class names, function names, package paths or development notes.
6. Call the three interfaces GUI, CLI and `.bemt`. Nothing else.
7. Plain, formal, explicative English. Full sentences.
8. Open each page chapter with its tab screenshot. Number tabs 1-7.
9. A field or block on a tab must open a section inside that tab's chapter.

Regenerate and commit:

```bash
python tools/build_toc.py --escrever      # index
python tools/field_index.py --escrever    # per-tab field lists
python tools/gui_screenshots.py           # docs/img/gui/*.png
python tools/field_inventory.py           # field -> tab/default/.bemt/CLI
```

Set `QT_QPA_FONTDIR` for `gui_screenshots.py` where Qt has no font backend.

`tests/test_documentation.py` and `tests/test_help_content.py` enforce: every
field has a section naming GUI, `.bemt` and CLI; every `--set` path, flag,
project and batch cited exists; heading numbers match chapter and depth;
chapters are sequential; prose section references resolve; popups open the
right chapter.

## Math notation

Render all mathematical notation in LaTeX: Greek symbols, subscripts,
everything. This applies everywhere it appears — plots, GUI field labels
and values, help popups, tables, and `docs/documentation.html`. Never use
plain-text or Unicode approximations (`lambda_i`, `mu_x`).

## GUI layout

- Align fields vertically as much as possible across forms.
- Buttons that appear together must be the same width as much as
  possible.
- Check that no text is ever cut off or overflows its area — buttons,
  tooltips, help popups, labels, everything.
- No user action may freeze the UI. Long-running work runs off the main
  thread; the interface stays responsive and updates automatically as
  results become available.

## Plots

- Every plot title must state the general flight/operating condition it
  was generated under.
- Legends, labels, titles, and annotations must never overlap the
  plotted data or otherwise block readability.

## Tests

- `unittest.TestCase`, discoverable by pytest; both runners work.
- `tests/helpers.py` has shared project constructors and
  `patch_em_toda_gui(name, value)` for silencing `QMessageBox` — patch
  each GUI module that wires its own instance, not just `zbemt.gui.app`.
- Example projects under `projects/` are versioned individually
  (`.gitignore` whitelists each by name) — a new example needs its own
  `!/projects/<name>/` line.
- Run `python tools/check_project_configs.py` after touching a project
  file or `models.py`'s dataclass default

Architecture, product/report decisions, and quality requirements live in
`docs/software_requirements.md`. This file is only direct rules for the
agent.

## Language

Write everything in English: code, comments, docstrings, commit messages,
GUI/CLI/report/doc text. Do not mix languages in a single file.

## Core workflow

1. Reproduce a bug before fixing it.
2. Add a regression test for logic fixes (not pure layout/styling). It
   must fail before the fix and pass after.
3. Run the full test suite once, at the end, after all requested changes
   are done.
4. Never mark work as done with a failing test or a partial
   implementation.
5. If a fix changes documented behavior, update that documentation in the
   same change.
6. Verify a subagent's work actually landed — `git status`/`git diff` and
   a real test run, not the subagent's own summary.

## Subagents

Spin up Haiku subagents for mechanical, repetitive, or low-judgment work:
translation passes, applying the same edit across many files, boilerplate
generation, running/parsing test output, simple refactors with a clear
pattern. Keep architectural decisions, physics changes, and anything
touching `bemt.py` for yourself.

## Commands

```bash
pip install -e ".[all]"                 # install (from repo root)

pytest                                  # full suite
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -p "test_*.py"

python -m unittest tests.test_bemt      # single file
pytest tests/test_bemt.py::TestSolveBemtHover -v   # single test class

zbemt-gui                               # GUI
zbemt --project projects/starter_rotor  # CLI (also runs standalone, zero args)
zbemt --project projects/MyRotor --validate-only   # before long batch

python tools/check_project_configs.py   # sanity-check every projects/* folder
```

Every script under `zbemt/` and `tools/` runs with zero arguments — a
`DEFAULT_*` constant near the top of the file supplies what a flag would
normally give it. This includes running the file directly.

GUI tests run headless (`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`
and the `Agg` backend). No linter is configured.

## Layout

```
zbemt/
  api.py  studies.py  bemt.py  models.py  validation.py
  geometry.py  airfoils.py  external_solvers.py  paths.py  cli.py
  gui/  app.py  common.py  workers.py  dialogs.py  widgets.py  styles.py
        tabs/  project  geometry_tab  airfoil  config  run_case  run_batch  results
  viz/  plots.py  visualization.py  style.py
```

`api` is the only path through which GUI/CLI run the engine or touch disk.
Before touching `bemt.py`, read its module docstring — it maps every
`BEMTConfig` option to its code section.

## Axes convention

### Axes convention (rotor vs propeller)

**Vehicle axes (what the user sees):** **x** is always longitudinal (horizontal
forward) and **z** is always vertical (up). The on-screen symbols use these
letters everywhere — GUI, results table, plots, reports.

**Vehicle orientation:** a **rotor** is assumed to have a **vertical** shaft; a
**propeller** is assumed to have a **horizontal** shaft (along the aircraft
longitudinal axis). Because the shaft direction differs, the **same letter**
(x or z) names **different physical components** in the two modes.

**Batch / Run Case slot names** (from `gui/widgets.py` and `gui/common.py`):

| Mode      | Slot (engine name) | Batch axis label         | Physical flow                          |
| --------- | ------------------ | ------------------------ | -------------------------------------- |
| Rotor     | `longitudinal`   | Edgewise (in-plane) flow | Advance in the disk plane              |
| Rotor     | `axial`          | Axial (along-shaft) Flow | Climb/descent along the shaft          |
| Propeller | `longitudinal`   | Cross (in-plane) Flow    | Cross-flow across the shaft (vertical) |
| Propeller | `axial`          | Axial (along-shaft) Flow | Airspeed along the shaft               |

#### Rotor mode — input and output symbols

Shaft vertical: **x** = in-plane (edgewise), **z** = along shaft (axial).

| Flow                 | GUI units (dropdown)                 | Shown in results               | Engine /`.bemt` / `FlightCondition` key                  | Definition                                                                         |
| -------------------- | ------------------------------------ | ------------------------------ | ------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| Edgewise             | μ_x, J_x, V_x [m/s]                 | μ_x, J_x, V_x                 | `mu_x`, `J_x`, `Vx`                                    | V_x/(ΩR), V_x/(nD)=π·μ_x, dimensional speed in the disk plane                  |
| Axial                | α_rotor [deg], V_z [m/s], μ_z, J_z | α_rotor, V_z, μ_z, J_z, λ_z | `alpha_rotor_deg`, `Vz`, `mu_z`, `J_z`, `lambda_z` | α_rotor=atan2(V_z,V_x); climb (+) / descent (−) along shaft; λ_z=V_z/(ΩR)=μ_z |
| Axial total (output) | —                                   | V_z,total, λ_total            | `Vz_total`, `lambda_total`                               | V_z,total = V_z + v_i; λ_total = λ_z + λ_i                                      |
| Induced (output)     | —                                   | v_i, λ_i                      | `Vi`, `lambda_i`                                         | Along the shaft; letters do not rotate with mode                                   |

Typical rotor flight: edgewise μ_x > 0, α_rotor ≈ 0° (level forward cruise).

#### Propeller mode — input and output symbols

Shaft horizontal: **x** = along shaft (axial), **z** = vertical (cross-flow in
the disk plane).

| Flow                 | GUI units (dropdown)                | Shown in results        | Engine /`.bemt` / `FlightCondition` key   | Definition                                                                                     |
| -------------------- | ----------------------------------- | ----------------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Axial                | J_x, μ_x, V_x [m/s]                | J_x, μ_x, V_x, λ_x    | `Vz`, `mu_z`, `J_z`, `lambda_z`       | Aircraft airspeed along shaft; J_x=V_x/(nD) is the classic propeller advance ratio             |
| Cross                | V_z [m/s], α_disk [deg], μ_z, J_z | V_z, α_disk, μ_z, J_z | `Vx`, `mu_x`, `J_x`, `alpha_disk_deg` | Cross-flow; zero in straight cruise; α_disk=atan2(V_z,V_x), 0° when stream aligns with shaft |
| Axial total (output) | —                                  | V_x,total, λ_total     | `Vz_total`, `lambda_total`                | V_x,total = V_x + v_i (stored under engine key`Vz_total`)                                    |
| Induced (output)     | —                                  | v_i, λ_i               | `Vi`, `lambda_i`                          | Along the shaft (shown as v_i along x in propeller mode)                                       |

Typical propeller flight: axial flow J_x (or V_x) set in the **Axial** field; cross
V_z = 0, α_disk = 0°.

#### Letter rotation summary (propeller display only)

Throughout the solver layer (internal key), the BEMT engine always works in disk axes, not vehicle axe; only the **display subscript** rotates when `is_propeller=True`
(`api.summary_symbols`, `viz/plots._SUMMARY_KEY_LABELS_HELICE`):

| Internal key        | Rotor label  | Propeller label |
| ------------------- | ------------ | --------------- |
| `Vz`              | V_z          | V_x             |
| `Vx`              | V_x          | V_z             |
| `mu_x`            | μ_x         | μ_z            |
| `mu_z`            | μ_z         | μ_x            |
| `J_x`             | J_x          | J_z             |
| `J_z`             | J_z          | J_x             |
| `lambda_z`        | λ_z         | λ_x            |
| `Vz_total`        | V_z,total    | V_x,total       |
| `alpha_rotor_deg` | α_rotor     | *(hidden)*    |
| `alpha_disk_deg`  | *(hidden)* | α_disk         |

## Field help

Every configurable field must have a popup that clearly explains the
physics and mathematics behind it. To hide a form field, use
`common.definir_linha_visivel`, never `widget.setVisible(False)` or
`form.setRowVisible(widget, …)` directly.

When moving or adding a field, run `python tools/field_index.py --escrever`.

## Math notation

Render all mathematical notation in LaTeX: Greek symbols, subscripts,
everything. This applies everywhere it appears — plots, GUI field labels
and values, help popups, tables, and `docs/documentation.html`. Never use
plain-text or Unicode approximations (`lambda_i`, `mu_x`).

## GUI layout

- Align fields vertically as much as possible across forms.
- Buttons that appear together must be the same width as much as
  possible.
- Check that no text is ever cut off or overflows its area — buttons,
  tooltips, help popups, labels, everything.
- No user action may freeze the UI. Long-running work runs off the main
  thread; the interface stays responsive and updates automatically as
  results become available.

## Plots

- Every plot title must state the general flight/operating condition it
  was generated under.
- Legends, labels, titles, and annotations must never overlap the
  plotted data or otherwise block readability.

## Tests

- `unittest.TestCase`, discoverable by pytest; both runners work.
- `tests/helpers.py` has shared project constructors and
  `patch_em_toda_gui(name, value)` for silencing `QMessageBox` — patch
  each GUI module that wires its own instance, not just `zbemt.gui.app`.
- Example projects under `projects/` are versioned individually
  (`.gitignore` whitelists each by name) — a new example needs its own
  `!/projects/<name>/` line.
- Run `python tools/check_project_configs.py` after touching a project
  file or `models.py`'s dataclass defaults.
