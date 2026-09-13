# CLAUDE.md

Working instructions for this repository.

## Sources of truth

`docs/software_requirements.md` is the binding specification for product,
architecture, engine, interface, documentation, GUI, and quality behavior.
Before changing behavior, identify the requirement codes that govern the
change.

If the requested behavior conflicts with a requirement, do not bypass the
requirement. Update it deliberately in the same change or choose an approach
that satisfies it. New durable behavior needs a requirement code.

Use the `writing-rules` skill for repository prose and user-facing strings.
Claude Code loads it from `.claude/skills/writing-rules/SKILL.md`. Other agents
use the identical mirror at `.agents/skills/writing-rules/SKILL.md`.

Do not copy requirements into this file. Reference their codes instead. Code,
tests, comments, and current behavior are evidence about the implementation,
not replacements for the requirements.

## Workflow

1. Read the relevant requirements, implementation, and tests before editing.
2. Reproduce a bug before fixing it when reproduction is practical.
3. Add a regression test for a solver or business-logic fix. Confirm that the
   test fails before the fix and passes after it. Pure layout and styling fixes
   are exempt.
4. Keep the implementation, tests, requirements, and user documentation
   synchronized when behavior changes.
5. Run the tests that are relevant to the change. Run the complete suite when
   the change has broad impact or a repository-wide result is required.
6. Do not report work as complete while a required test fails or the requested
   implementation is partial.

Before editing `bemt.py`, read its module docstring and keep its `BEMTConfig`
option map current as required by `EN-2`.

## Change discipline

Keep a change as small as the requested behavior permits. Do not combine an
unrelated refactor with a functional change unless the refactor is required to
make the change correct.

Permanent specifications and instructions describe the current required state.
Put rationale, migration history, bug history, and temporary implementation
notes in commits, pull requests, issues, or focused code comments when the
rationale is necessary to prevent a future error.

Avoid duplicate sources of truth. Reference the canonical requirement, module,
registry, or generated source instead of copying its data into another file.

Treat a subagent summary as a pointer to its work, not as evidence of
correctness. Base correctness claims on repository artifacts and test results.

## Commands

```bash
pip install -e ".[all]"

python tests/run_all_tests.py
python tests/run_all_tests.py -k airfoil
python tests/run_all_tests.py --list

python -m pytest tests/regression/test_bemt.py
python -m pytest tests/regression/test_bemt.py::TestSolveBemtHover -v

zbemt-gui
zbemt --project projects/starter_rotor
zbemt --project projects/MyRotor --validate-only

python tools/check_project_configs.py
python tools/golden_snapshot.py
python tools/nomenclature_snapshot.py
```

Use `python tests/run_all_tests.py` for the complete suite. Use direct pytest
only for individual files, classes, or tests. GUI tests already run headless
through `tests/conftest.py`.

Every script under `zbemt/` and `tools/` must remain runnable without
command-line arguments. Put repository defaults in a `DEFAULT_*` constant near
the top of the file when a script otherwise needs an argument.

No linter is configured. Do not invent a lint gate when validating a change.

## Documentation maintenance

Run the generator that owns an affected documentation artifact. Commit the
result and inspect its diff.

```bash
python tools/build_toc.py --write
python tools/field_index.py --write
python tools/gui_screenshots.py
python tools/field_inventory.py
python tools/sync_tools_documentation.py
python tools/regenerate_documentation_plots.py
```

Run `python tools/field_index.py --write` after adding, removing, renaming, or
moving a configurable GUI field.

Set `QT_QPA_FONTDIR` when `gui_screenshots.py` runs on a system without a Qt
font backend. Do not hand-edit generated indexes, field lists, or screenshots.

## Tests and generated data

Use `unittest.TestCase` for repository test classes and keep them discoverable
by pytest. Put shared test constructors in `tests/helpers.py`.

Use `patch_message_box_everywhere(name, value)` from `tests/helpers.py` when a
GUI test must silence `QMessageBox`. Patch each GUI module that owns a message
box reference, not only `zbemt.gui.app`.

Example projects under `projects/` are versioned individually. Add the matching
`.gitignore` allow rule when adding a new versioned example project.

If a physics change intentionally changes versioned reference results,
regenerate `tests/data/golden_results.json` with
`python tools/golden_snapshot.py` and inspect the numerical diff. If an axis or
nomenclature change intentionally changes the user-facing snapshot, regenerate
`tests/data/nomenclature_snapshot.json` with
`python tools/nomenclature_snapshot.py` and inspect the diff.

Run `python tools/check_project_configs.py` after changing a project file or a
dataclass default in `models.py`.

## Continuous integration and test constraints

The GitHub Actions workflow runs three distinct jobs on Ubuntu runners. Each job
enforces specific architectural boundaries. Design tests and tools so that they
remain deterministic and functional across these environments.

1. Do not import Qt in engine or CLI modules. The `engine` matrix runs on Python
   3.10, 3.11, and 3.12 without `PyQt6` installed. If any solver, model, study,
   or CLI utility imports Qt directly or transitively, that job fails.
2. Account for offscreen Qt and platform font metrics. The `gui` job runs with
   `QT_QPA_PLATFORM=offscreen` on headless Linux. System font dimensions and
   baseline alignments vary across operating systems. Therefore, do not write
   tests that rely on single-pixel vertical layout assertions. Use cluster
   tolerances when sorting widgets into rows.
3. Silence modal dialogs in automated test cases. A GUI test must never open an
   unpatched modal message box. Use `patch_message_box_everywhere` from
   `tests/helpers.py` to prevent tests from blocking the headless runner.
4. Set realistic solver tolerances. Floating-point reductions run with single-thread
   settings in CI to preserve determinism. However, spatial discretization noise
   floors on 48-node to 60-node radial grids limit numerical precision. Do not
   assert tolerances tighter than the discretization error.
5. Account for control quantization in the user interface. Spinboxes round
   values to their configured decimal precision. Test assertions that compare
   reconstructed parameters to continuous models must allow for this quantization.
6. Keep standalone scripts runnable without arguments. The CI workflow exercises
   tools such as `gui_qa_screenshots.py`, `gui_tools_used_screenshots.py`, and
   `field_inventory.py` without flags. Every script under `tools/` must exit with
   returncode 0 unattended.
7. Package all offline help assets. The `installation` job builds a wheel and
   validates the package in an isolated directory. The embedded help documentation
   cannot link to external internet resources.

## Subagents

Delegate only sizeable work that is genuinely independent and parallelizable.
Do not delegate work that can be completed directly in a few tool calls. Keep
architectural judgment, physics decisions, and changes to `bemt.py` under
direct control. Prefer one subagent when one is sufficient.

