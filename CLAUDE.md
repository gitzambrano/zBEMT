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
5. Run focused tests while editing. Run the complete suite once after the
   requested change is complete.
6. Inspect the final diff. Verify generated files and snapshots rather than
   accepting them blindly.
7. Do not report work as complete while a required test fails or the requested
   implementation is partial.

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

Verify subagent work yourself with the diff and real tests. A subagent summary
is not evidence of correctness.

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

Scripts under `zbemt/` and `tools/` must remain runnable without command-line
arguments when they expose a command-line entry path. Put repository defaults
in a `DEFAULT_*` constant near the top of the file.

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

Set `QT_QPA_FONTDIR` when `gui_screenshots.py` runs on a system without a Qt
font backend.

Do not hand-edit generated indexes, field lists, or screenshots.

## Tests and generated data

Use `unittest.TestCase` for repository test classes and keep them discoverable
by pytest. Put shared test constructors and GUI message-box patches in
`tests/helpers.py` rather than duplicating them across test modules.

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

Delegate mechanical work with a clear pattern, such as repetitive edits,
boilerplate, translation passes, and routine test execution. Keep architectural
judgment, physics decisions, and changes to `bemt.py` under direct review.
