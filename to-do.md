# To-do

Open work only. Everything that has shipped lives in the git history and in
`docs/software_requirements.md`; it is not repeated here.

Rules that apply to every item:

- `docs/software_requirements.md` decides. Cite the requirement code in the
  commit message and in the test docstring.
- A new configurable field must reach the GUI, the CLI and the `.bemt` file in
  the same change (`PA-1`, `PA-3`, `PA-5`), with a help popup and a
  documentation section that names it (`PR-3`, `DC-4`).
- Run `python tools/field_index.py --write` and `python tools/build_toc.py
  --write` after a field or a chapter moves.
- Run `python tests/run_all_tests.py` once, at the end.

---

## 1. Interpolate between Reynolds and Mach slices

**Where.** `airfoils.build_table`, which says so in its own docstring:
"Real interpolation BETWEEN Reynolds and Mach slices remains future work.
Today it is nearest neighbor."

**What happens now.** A tabulated polar may carry slices at several Reynolds
and Mach numbers. Each radial station picks the slice NEAREST to its own
condition, so the root and the tip of one blade land on different polars and
the radial variation of Reynolds does reach the forces. But the choice is a
step: a station halfway between two slices gets one of them, not a blend, and
the coefficient jumps as the station crosses the midpoint.

**Why it matters.** A sweep that crosses a slice boundary shows a step in the
result that belongs to the table's spacing, not to the rotor.

**What to do.** Interpolate in log-Reynolds and in Mach, bilinearly, with the
edges held rather than extrapolated. Keep the nearest-neighbour path for a
table with a single slice on an axis.

**Tests.** `tests/regression/test_model_effects.py::TestTabulatedPolarsUseReynoldsAndMach`
pins the current behaviour, including
`test_the_choice_snaps_rather_than_interpolating`. That test states the
limitation deliberately: changing it is part of this work, not a casualty of
it. The documentation says the same in six places (`build_table`, chapter 8's
polar sections, the preview's own note) and all of them have to move together.

---

## 2. Run the derivative sweep in parallel

**Where.** `DerivativeRequest.parallel_workers` is stored, travels to
`inputs/derivatives.bemt`, reaches the CLI, and does nothing. Only
`studies.py` honours a worker count, and only for the optimization.

**What happens now.** The Stability window's tooltip is honest about it:
"This build evaluates the derivatives SERIALLY, so the value travels with the
file and does not yet change the run time." A study with eight states and a
Richardson check is thirty-plus solves, one after another.

**What to do.** The optimization's pattern already exists and is proven:
`studies._optimizer_design_task` plus a `ProcessPoolExecutor` opened once for
the whole search, results collected in SUBMISSION order so the answer does not
depend on the worker count. Apply the same shape to the perturbation sweep.

**Tests.** The optimization's guarantee is checked by a front CSV that is
byte-identical between one and two workers
(`tests/regression/test_optimizer_parallel.py`). The derivative sweep needs the
equivalent: the same matrix, to the last digit, at any worker count.

---

## 3. Cut the cost of the two curve views in the Results tab

**Where.** `plots.plot_coefficients_vs_axis` and the azimuth/radius view.

**What happens now.** Measured cold, one redraw is about 520 ms, and 0.594 s
of a three-redraw profile is matplotlib's `tight_layout` measuring the
bounding box of every tick label across eleven panels. There is no double
layout work to remove: `_new_figure` sets no layout engine, so the explicit
`fig.tight_layout(...)` runs once.

**What NOT to do.** Fixing the margins by hand is the obvious saving and it
risks clipping text, which the repository forbids outright ("No text may ever
be clipped or overflow its area"). Any approach has to keep that guarantee.

**What to try.** Compute the layout once per figure SIZE and cache the
resulting subplot parameters, since the labels rarely change between redraws
of the same view; or draw fewer panels at once, with the rest a click away, as
the disk map now does.

**Reference.** The disk map went from 9919 ms to 53 ms by not drawing until
asked, and the 3D preview from 1861 ms to 305 ms by drawing at preview
resolution. Both are in `tests/regression/test_disk_map_is_lazy.py` with their numbers.

---

## 4. Decide what `transition_evtol/cruise` is meant to show

**What it does now.** At `mu_x = 0.35` with 8 degrees of collective the rotor
AUTOROTATES: the shaft power is negative, and always was. The engine reports
that correctly; it is the case that is not a powered cruise.

**Why it was invisible.** A defect in the Øye separation function inflated the
case's thrust from 2996 N to 10260 N and its induced power from -18 kW to
+42 kW, so the autorotation hid behind a plausible positive number. With the
defect fixed the case reports what it is.

**The decision.** Either the windmilling is what the example is meant to show,
and it stays, or the example is under-pitched for its advance ratio and the
collective should rise (16 degrees makes the induced power positive). This is
a product decision about what the example teaches, not an engine question.

**What is in place meanwhile.** `tests/regression/test_golden_results.py` names the case
in `AUTOROTATING` with the physics stated, and
`test_every_named_autorotating_case_really_autorotates` revokes the exemption
automatically if the case ever stops autorotating.

---

## 5. Block-level help for the Results tab's view selectors

**What happens now.** 223 of 250 input controls open a popup on click. The 27
that do not are view selectors: they choose what is drawn from results that
already exist, not a field of the project. They are named one by one in
`tests/architecture/test_every_field_has_a_popup.py::VIEW_ONLY`, so a genuinely new field
cannot join them by accident, and every one of them has a written tooltip.

**What would improve it.** `help_blocks.BLOCK_HELP` and
`common.make_block_title_clickable` already give a GROUP BOX a clickable
title. The Results tab's view controls sit in group boxes; giving those boxes
block entries would explain the whole view -- what the disk map is for, what
the parallel-coordinates plot shows -- which is the right granularity for a
control that picks a view rather than sets a value.

---

## 6. Peters-He five-state inflow, if it is ever wanted

Both options that were declared and not built are now GONE, not offered:
`AirfoilDef.source="external"` and `pitt_peters_states=5`. XFOIL and
NeuralFoil polars reach the engine as `source="table"` through
`table_slices`, and the inflow model solves its three states
(nu0, nu_s, nu_c). `validation.py` still reports either old value as an
error, so a project file written before the removal fails with a sentence
instead of a traceback.

**What is left.** Building the Peters-He second harmonic (five states) is
open work, not a defect. It needs the generalized gain matrix for the m=2
states, which no source in this repository carries. The three-state matrices
in `_pitt_peters_L_V` name their reference; the five-state extension must do
the same before it is written, because a gain matrix guessed from memory
produces plausible numbers that no test in this repository can catch.
