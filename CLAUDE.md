# CLAUDE.md

Working rules for this repository.

## Software requirements come first

`docs/software_requirements.md` is binding. Every requirement in it carries a
code (`PR-4`, `EN-2`, `QR-8`, …), and the software must satisfy all of them.

- Before changing behavior, check whether a requirement governs it. If one
  does, the requirement decides — not convenience, and not what the code
  happens to do today.
- If a change would break a requirement, do not make it silently. Say so, and
  either change the requirement deliberately or find another approach.
- New behavior that is worth keeping needs a requirement. Add it, with a code,
  in the section it belongs to.
- Cite the code when a test or a commit exists because of a requirement. That
  is what makes the link findable in both directions.

This file holds only the rules for working in the repository. Architecture,
product decisions and quality standards live in the requirements document.

## Language

Write everything in English: code, comments, docstrings, commit messages, and
every string the user sees in the GUI, the CLI, a report or the documentation.
Never mix languages within one file.

Follow the `writing-rules` skill for sentence-level style. It adapts
ASD-STE100 (Simplified Technical English) rules for this project's
documentation, docstrings, comments, and GUI strings. Claude Code loads it
from `.claude/skills/writing-rules/SKILL.md`. A mirror at
`.agents/skills/writing-rules/SKILL.md` carries the same content for any
other agent. `tests/test_agent_instructions.py` keeps the two identical.

## Core workflow

1. Reproduce a bug before fixing it.
2. Add a regression test for any logic fix. It must fail before the fix and
   pass after. Pure layout and styling fixes are exempt.
3. Run the full suite once, at the end, after every requested change is done.
4. Never report work as done while a test fails or an implementation is
   partial.
5. When a fix changes documented behavior, update the documentation in the
   same change.
6. Verify a subagent's work yourself, with `git diff` and a real test run. Its
   own summary is not evidence.

## Subagents

Use less powerful subagents for mechanical, repetitive work with a clear pattern:
translation passes, the same edit applied across many files, boilerplate,
running and parsing test output, simple refactors.

Keep for yourself anything that requires judgement: architectural decisions,
physics changes, and any change to `bemt.py`.

## Commands

```bash
pip install -e ".[all]"                 # install, from the repository root

python tests/run_all_tests.py           # the full suite -- one process per file
python tests/run_all_tests.py -k airfoil          # only files matching
python tests/run_all_tests.py --list             # list the files, run nothing

python -m pytest tests/test_bemt.py                           # one file
python -m pytest tests/test_bemt.py::TestSolveBemtHover -v     # one class

zbemt-gui                               # GUI
zbemt --project projects/starter_rotor  # CLI
zbemt --project projects/MyRotor --validate-only   # before a long batch

python tools/check_project_configs.py   # sanity-check every projects/* folder
python tools/golden_snapshot.py         # re-record the engine's numbers
```

Every script under `zbemt/` and `tools/` runs with no arguments: a `DEFAULT_*`
constant near the top of the file supplies what a flag would otherwise give it.
This includes running the file directly.

GUI tests run headless — `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`
and the `Agg` backend. No linter is configured.

**Run the full suite with `tests/run_all_tests.py`, never with a bare
`pytest tests/`.** A single pytest process accumulates Qt and matplotlib
canvases across dozens of files and dies with a native access violation
(exit 139) — a teardown-ordering crash, not a test failure, which hides every
result after it. The runner gives each file its own process, keeps memory
bounded, writes `tests/test_results.txt` with a traceback per failure, and
is what CI runs. Running a single file or class through `python -m pytest` is
fine.

## Layout

```
zbemt/
  api.py  studies.py  bemt.py  models.py  validation.py  nomenclature.py
  geometry.py  airfoils.py  external_solvers.py  paths.py  cli.py
  gui/  app.py  common.py  workers.py  dialogs.py  widgets.py  styles.py
        tabs/  project  geometry_tab  airfoil  config  run_case  run_batch
               designer_window  results
  viz/  plots.py  visualization.py  style.py
```

`api` is the only path through which the GUI or the CLI run the engine or touch
disk. Before changing `bemt.py`, read its module docstring: it maps every
`BEMTConfig` option to the section of code that implements it.

## Axes convention

**Vehicle axes are what the user sees.** `x` is always longitudinal (horizontal,
forward) and `z` always vertical (up). Every on-screen symbol uses these
letters — GUI, results table, plots, reports.

**The shaft direction differs by mode.** A rotor has a vertical shaft, a
propeller a horizontal one. The same letter therefore names a different physical
component in each mode.

Slot names, used by `gui/widgets.py` and `gui/common.py`:

| Mode      | Slot        | Batch axis label         | Physical flow                    |
| --------- | ----------- | ------------------------ | -------------------------------- |
| Rotor     | `inplane` | Edgewise (in-plane) Flow | Advance in the disk plane        |
| Rotor     | `axial`   | Axial (along-shaft) Flow | Climb or descent along the shaft |
| Propeller | `inplane` | Cross (in-plane) Flow    | Cross-flow, vertical             |
| Propeller | `axial`   | Axial (along-shaft) Flow | Airspeed along the shaft         |

### Rotor mode

Shaft vertical, so `x` is in-plane (edgewise) and `z` is along the shaft.

| Flow                 | GUI units                            | Shown in results               | Engine key                                                   | `.bemt` / CLI key |
| -------------------- | ------------------------------------ | ------------------------------ | ------------------------------------------------------------ | ------------------- |
| Edgewise             | μ_x, J_x, V_x [m/s]                 | μ_x, J_x, V_x                 | `mu_x`, `J_x`, `Vx`                                    | same                |
| Axial                | α_rotor [deg], V_z [m/s], μ_z, J_z | α_rotor, V_z, μ_z, J_z, λ_z | `alpha_rotor_deg`, `Vz`, `mu_z`, `J_z`, `lambda_z` | same                |
| Axial total (output) | —                                   | V_z,total, λ_total            | `Vz_total`, `lambda_total`                               | same                |
| Induced (output)     | —                                   | v_i, λ_i                      | `Vi`, `lambda_i`                                         | same                |

α_rotor = atan2(V_z, V_x), measured from the disk plane; climb is positive,
descent negative. λ_z = V_z/(ΩR) = μ_z. Level forward cruise is μ_x > 0 with
α_rotor ≈ 0°.

### Propeller mode

Shaft horizontal, so `x` is along the shaft (axial) and `z` is the vertical
cross-flow in the disk plane.

| Flow                 | GUI units                           | Shown in results        | Engine key                                    | `.bemt` / CLI key                           |
| -------------------- | ----------------------------------- | ----------------------- | --------------------------------------------- | --------------------------------------------- |
| Axial                | J_x, μ_x, V_x [m/s]                | J_x, μ_x, V_x, λ_x    | `Vz`, `mu_z`, `J_z`, `lambda_z`       | `Vx`, `mu_x`, `J_x`, `lambda_x`       |
| Cross                | V_z [m/s], α_disk [deg], μ_z, J_z | V_z, α_disk, μ_z, J_z | `Vx`, `mu_x`, `J_x`, `alpha_disk_deg` | `Vz`, `mu_z`, `J_z`, `alpha_disk_deg` |
| Axial total (output) | —                                  | V_x,total, λ_total     | `Vz_total`, `lambda_total`                | `Vx_total`, `lambda_total`                |
| Induced (output)     | —                                  | v_i, λ_i               | `Vi`, `lambda_i`                          | same                                          |

J_x = V_x/(nD) is the classic propeller advance ratio, built from the axial
component. α_disk = atan2(V_z, V_x) is measured from the shaft and is 0° when
the stream is aligned with it. Straight cruise is J_x set in the Axial field,
with V_z = 0 and α_disk = 0°.

### The letter rotation

The engine always works in disk axes. `bemt.py`, `FlightCondition` and
`Results.summary` in memory keep the internal key below, in every mode. What
rotates when `is_propeller=True` is only what the user meets: the displayed
symbol, and the key written into `.bemt` files, CSV headers and the results
table.

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

**`zbemt/nomenclature.py` owns the whole rotation.** Edit a symbol, a unit, a
tooltip or a slot name there and every surface follows: the GUI fields, the
results table, the plots, the HTML report, the CLI help and the `.bemt` writer.
Never add a second table anywhere — consolidating ten of them into that module
is the point (`PR-8`).

Two invariants a change must not break:

- The rotation is a **swap** (`mu_x` ↔ `mu_z`), so it is applied in one pass
  into a new dict, by `to_display_keys`. Renaming key by key collapses both
  components onto one value, silently and plausibly.
- A rotated dict is an **output**. It never re-enters the application; only
  `from_display_keys`, at the boundary that produced it, converts it back.

## Field help

Every configurable field needs a popup explaining the physics and the
mathematics behind it.

To hide a form field, use `common.definir_linha_visivel`. Never call
`widget.setVisible(False)` or `form.setRowVisible(widget, …)` directly: they
hide the field and leave its label on screen, pointing at nothing.

Hide a control only when it has nothing to say in the current configuration. A
control that is real but blocked stays visible and disabled, so the user can
learn that it exists (`PR-2`).

After moving or adding a field, run `python tools/field_index.py --write`.

## Documentation (`docs/documentation.html`)

Structure:

```
0-5   Introduction  how to think · installation · GUI/CLI/.bemt · tutorial ·
                    nomenclature and axes · the method
6-12  THE PAGES     Project · Geometry · Airfoil · Config/Engine ·
                    Run Case · Run Batch · Results
13    TOOLS WINDOW  Geometry Variation Studies (the Geometry Designer,
                    opened from the Tools button in the main window's top
                    bar, next to Help)
14-15 Reference     command line · limitations
```

Rules:

1. One chapter per GUI tab, in tab order. Only the introduction chapters may
   span tabs. Never document a page inside a physics chapter.
2. Within a chapter, follow the GUI: block by block, field by field.
3. A field's section is self-contained. Put the physics, the mathematics, the
   options and the ranges in it, and explain any named model (Glauert, Øye,
   Prandtl, Newton, Viterna) where its control is. The reader must never have
   to follow a link to understand or set a field.
4. Give every field, in this order: what it is physically, the equation it
   enters, every option it offers, and then how to set it in the GUI, in
   `.bemt` and from the CLI — as three separate paragraphs.
5. No class names, function names, package paths or development notes.
6. Call the three interfaces GUI, CLI and `.bemt`. Nothing else.
7. Plain, formal, explanatory English, in full sentences.
8. Open each page chapter with its tab screenshot. Number the tabs 1 to 7.
9. A field or block belonging to a tab opens a section inside that tab's
   chapter.
10. Mark each interface with its color: GUI blue, CLI red, `.bemt` green.
    Wrap every mention in `<span class="gui">`, `<span class="cli">` or
    `<span class="bemt">`.
11. Every reference to another section is a link, underlined, carrying the
    target's title as its `title`. A number written as plain text is a defect:
    it cannot be followed, and it drifts silently when sections are renumbered.
    `tests/test_documentation.py` enforces both the link and the fact that its
    number and its target agree.
12. Chapters 6-13 are self-contained. A reference out of one of them is allowed
    only as a statement of scope — "that setting lives in another tab" — never
    as a deferral of physics, and every such exception is listed by name in
    `TestCapitulosDeAbaSaoEstanques`.

**HTML `id` attributes are exempt from the English rule.** Several are in
Portuguese (`cap-projeto`, `cap-nomenclatura`, the `INDICE-GERAL` and
`INDICE-DE-CAMPOS:*` markers). They are addresses, not text: no reader sees
them, and the generators, the help registry and the field-help map all resolve
against them. Renaming them buys nothing and risks breaking every popup. Do not
rename them; do not add new ones in Portuguese either.

Regenerate and commit:

```bash
python tools/build_toc.py --write      # index
python tools/field_index.py --write    # per-tab field lists
python tools/gui_screenshots.py           # docs/img/gui/*.png
python tools/field_inventory.py           # field -> tab/default/.bemt/CLI
```

Set `QT_QPA_FONTDIR` for `gui_screenshots.py` where Qt has no font backend.

`tests/test_documentation.py` and `tests/test_help_content.py` enforce that
every field has a section naming GUI, `.bemt` and CLI; that every `--set` path,
flag, project and batch cited exists; that heading numbers match their chapter
and depth; that chapters are sequential; that prose section references resolve;
and that each popup opens the right chapter.

## Mathematical notation

Render all mathematical notation properly — Greek symbols, subscripts,
exponents — everywhere it appears: plots, GUI labels and values, tooltips, help
popups, tables, reports and `docs/documentation.html`. Use LaTeX where the
surface renders it, and HTML entities with `<sub>`/`<sup>` where it does not.

Never use a plain-text approximation such as `lambda_i`, `mu_x` or
`rho*A*(Omega*R)^2`. `tests/test_notation.py` enforces this (`PR-4`).

## GUI layout

- Align fields vertically across forms as far as possible.
- Buttons that appear together should share a width.
- No text may ever be clipped or overflow its area — buttons, tooltips, help
  popups, labels, everything.
- Every dropdown opens showing all of its options. Qt shows only ten by
  default; `common.mostrar_todas_as_opcoes` raises that cap and is applied to
  the whole window at construction.
- No user action may freeze the interface. Long work runs off the main thread;
  the GUI stays responsive, reports progress and can be cancelled (`PR-11`).

## Plots

- Every plot title states the flight or operating condition it was generated
  under.
- Legends, labels, titles and annotations must never overlap the plotted data
  or otherwise block readability.

## Tests

- Use `unittest.TestCase`, discoverable by pytest. Both runners must work.
- `tests/helpers.py` holds shared project constructors and
  `patch_message_box_everywhere(name, value)` for silencing `QMessageBox`. Patch every GUI
  module that wires its own instance, not just `zbemt.gui.app`.
- Example projects under `projects/` are versioned individually — `.gitignore`
  whitelists each by name, so a new example needs its own `!/projects/<name>/`
  line.
- `tests/data/golden_results.json` records what the engine produces for every
  example project. A deliberate change to the physics means regenerating it
  with `python tools/golden_snapshot.py` and reading the diff; an accidental
  one fails `tests/test_golden_results.py`.
- `tests/data/nomenclature_snapshot.json` does the same for every axis symbol
  the user sees. Regenerate with `python tools/nomenclature_snapshot.py`.
- Run `python tools/check_project_configs.py` after touching a project file or
  a dataclass default in `models.py`.
