# AGENTS.md

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

## Subagents

Delegate only sizeable work that is genuinely independent and parallelizable.
Do not delegate work that can be completed directly in a few tool calls. Keep
architectural judgment, physics decisions, and changes to `bemt.py` under
direct control. Prefer one subagent when one is sufficient.
