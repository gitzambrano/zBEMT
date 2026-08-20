# zBEMT

A **BEMT solver** (Blade Element Momentum Theory) for rotors, propellers, and eVTOL aircraft. Three ways to run: PyQt6 graphical interface, command-line tool, or Python library — all sharing the same vectorized NumPy engine.

*Developed by Gustavo José Zambrano, 2026*

---

## Install

```bash
pip install -e ".[all]"
```

The core solver and CLI run on just `numpy`, `scipy`, `matplotlib`, and `pandas` — by design, so a batch on a headless server does not need Qt or 3D graphics:

```bash
pip install -e .                 # core engine + CLI only
pip install -e ".[gui]"          # + PyQt6 (graphical interface)
pip install -e ".[viz3d]"        # + PyVista (3D visualization)
pip install -e ".[neuralfoil]"   # + NeuralFoil (airfoil polar generation)
pip install -e ".[interactive]"  # + Plotly (interactive charts in reports)
pip install -e ".[all]"          # everything above
pip install -e ".[dev]"          # + pytest (for running tests)
```

---

## First Run: GUI

```bash
zbemt-gui
```

(or `python -m zbemt.gui.app` if you installed from source without `pip install -e`)

The window opens empty. The first step is always the **Project** tab: load one of the example projects included in the repository (`starter_rotor` or `starter_propeller`) or create a new one.

The workflow follows seven tabs in order: **Project → Geometry → Airfoil → Config/Engine → Run Case → Run Batch → Results**. The flow bar at the top (`FlowIndicatorBar`, not the OS/Qt status bar) shows validation state for each step (gray = pending, green = ready, red = error) and also serves as tab navigation.

**Progressive disclosure:** options that don't apply to your current choices disappear (analytical polar parameters hide when you switch to tabulated data; Pitt-Peters settings only appear with that inflow model). Fields that exist but are incompatible in this mode are *disabled* rather than hidden — communicating "this option exists, just not here."

Press **F1** to open the complete physics documentation and field-by-field help.

---

## First Run: CLI

```bash
# Run a single case from the example rotor
zbemt --project projects/starter_rotor --rpm 300 --mu-inplane 0.2 --collective 8

# Validate before launching a long batch without supervision
zbemt --project projects/starter_rotor --rpm 300 --validate-only
```

Every config field is reachable via `--set` even without a dedicated flag, and reports come from the same execution:

```bash
zbemt --project projects/starter_rotor --rpm 300 --mu-inplane 0.2 \
    --set config.Ne=90 --set config.Npsi=144 \
    --report
```

Run `zbemt --help` to list all available flags.

---

## File Structure

```
zbemt/
  api.py               Unified facade: GUI and CLI talk only to this
  studies.py           Orchestrates the engine across flight conditions
  bemt.py              The solver (most important file)
  models.py            Dataclasses + .bemt serialization, no physics
  validation.py        Pre-flight static checks
  geometry.py          Rotor geometry and mesh generation
  airfoils.py          Airfoil definition and polar import
  external_solvers.py  NeuralFoil bridge for polar generation
  cli.py               Command-line entry point
  gui/                 PyQt6 interface
  viz/                 2D plots (matplotlib) and 3D (PyVista)

tests/                 Test suite (1000+ tests)
docs/                  Physics reference + software requirements
projects/              14 example projects (included in git)
tools/                 Repository maintenance scripts
```

**Key rule:** `api` is the only path through which the GUI or CLI run the engine or write to disk. `studies` orchestrates `bemt` and never touches disk — always returns `Results` in memory. `models` contains no physics: the dataclasses `...Def` are raw, editable, serializable data, and the physics-aware classes the engine uses are built from them.

---

## Main Features

**Solvers:** Newton-Raphson (default, vectorized with numerical Jacobian), fixed-point iteration (Picard with relaxation), Aitken acceleration, and bisection (for post-stall nonmonotic regions).

**Inflow models:** Glauert local, Glauert global, Coleman local, Coleman global, Drees local, Drees global, and Pitt-Peters steady. (Note: Pitt-Peters unsteady is not implemented; dynamic time-marching is out of scope for this BEMT solver by design.)

**Rotational correction:** Himmelskamp/Snel rotational augmentation and radial flow correction.

**Advanced options:** dynamic stall (Øye model), Prandtl tip/root loss, full-range polar extension (Viterna-Corrigan, ±180°), and compressibility effects.

**Batch and sweep:** single case, parametric factorial, case-by-case definition, and saved batch templates.

**Report generation:** self-contained HTML (plots embedded as base64, no external files needed to view it) with summary, mesh info, solver settings, rotor data, and all charts — inputs (blade geometry, airfoil polars) and outputs alike. A report with many figures (e.g. a large batch) splits into a small master page (input/output tables, links) plus per-section satellite pages next to it, so the master stays fast to open; nothing is ever dropped or truncated.

**3D disk maps:** contour plots on the rotor disk (requires PyVista optional dependency; degrades gracefully without it).

**Multi-section airfoils:** vary airfoil profile radially along the blade.

**NeuralFoil integration:** generate polars at arbitrary Reynolds and Mach via neural network (requires `neuralfoil` package; optional `--gen-neuralfoil` mode).

**Interactive charts:** optional Plotly dashboards in reports when the `interactive` package group is installed.

Full documentation — one chapter per tab, every field with its physics, mathematics and how to set it in the GUI, in `.bemt` and from the CLI — is at **[docs/documentation.html](docs/documentation.html)** or press **F1** in the GUI.

---

## Example Projects

zBEMT ships with ready-to-run starter projects covering both rotary-wing and propeller modes:

| Folder | Type | Radius | Blades | σ | Tip speed | Notable coverage |
| --------------------- | ----------------------------- | ------ | ------ | ----- | --------- | --------------------------------------------------------- |
| `starter_rotor` | Rotor / helicopter quickstart | 1.25 m | 4 | 0.141 | 78 m/s | `is_propeller=False`, Coleman local inflow |
| `starter_propeller` | Airplane propeller quickstart | 0.94 m | 3 | 0.109 | 246 m/s | `is_propeller=True`, axial flight, Glauert local inflow |

List and run saved batches:

```bash
zbemt --project projects/starter_rotor --list-batches
zbemt --project projects/starter_rotor --from-bemt-batch "mu_sweep" --report
```

---

## As a Python Library

```python
from zbemt import api
from zbemt.models import FlightCondition

project = api.open_project("projects/starter_rotor")

# Validate before running — some configurations the engine rejects,
# and it's better to discover that now than mid-batch
for issue in api.validate_project(project):
    print(issue)

result = api.run_case(
    project,
    FlightCondition(name="cruise", mu_x=0.25, collective_deg=8.0, rpm=300.0),
)
print(result.summary["CT"], result.summary["FM"])

# Same report as the GUI button and CLI --report flag
api.generate_report([result], "report.html", project=project,
                    notes="preliminary sweep")
```

---

## Tests

```bash
python tests/run_all_tests.py            # full suite

python tests/run_all_tests.py -k airfoil # only files matching "airfoil"
python -m pytest tests/test_bemt.py      # a single file
```

1000+ tests in ~7 minutes, including all GUI tests (headless via `QT_QPA_PLATFORM=offscreen`, already configured in `tests/conftest.py`). A summary is printed and a full report, with a traceback per failure, is written to `tests/resultado_testes.txt`.

Run the full suite through `run_all_tests.py`, which gives each test file its own process. A single `pytest tests/` over everything accumulates Qt/matplotlib canvases across dozens of files and eventually dies with a native access violation during teardown — not a test failure, but it aborts the run and hides every result after it. Individual files and classes run fine under plain `pytest`.

The reference project `projects/starter_rotor/` and its end-to-end test suite (`tests/test_example_project.py`) exercise the full stack at production mesh resolution (Ne=90 / Npsi=144). `tools/check_project_configs.py` loads, validates, and smoke-solves every folder under `projects/` — run it after touching a project file or `models.py`'s dataclass defaults.

---

## Contributing & License

Licensed under the GNU General Public License v3.0 or later (GPL-3.0-or-later). See [LICENSE](LICENSE) for the full text. See [software_requirements.md](docs/software_requirements.md) for the high-level requirements guiding upcoming versions.

The physics is validated against theory: momentum balance reproduces blade loads, figure of merit respects the hover ideal limit, and inflow converges correctly in forward flight.
