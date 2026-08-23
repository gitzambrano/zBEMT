# To-do

## Open

1. **Add time-stepping: dynamic Pitt-Peters and dynamic stall.**
   Integrate the inflow states and the separation state in time. Enables manoeuvre and
   transient simulation instead of isolated operating points.

2. **Add simplified flapping and lead-lag, coupled to Pitt-Peters.**
   Spring and virtual-offset approximation, not blade elasticity. Couple to item 1.

3. **Stability and control derivatives.**
   Perturbation about the trim point. Include the effects of items 1 and 2.

4. **Surface partial external-polar convergence in the GUI.**
   When XFOIL fails to converge at some Reynolds numbers, `_run_polar_xfoil` warns on
   stderr, which the windowed GUI never shows. Report the count in the polar-generation
   status line ("3 of 4 Reynolds converged") and in the generated-table note.

## Done (on `feature/design-tools`)

- ~~**XFoil support.**~~ Engine `xfoil` alongside NeuralFoil: dedicated transition
  inputs (`xfoil_ncrit`, `xfoil_xtr_top`, `xfoil_xtr_bot`), binary lookup through
  `ZBEMT_XFOIL_BIN` then PATH, CLI `--gen-xfoil` with `--ncrit/--xtr-top/--xtr-bot`,
  same table pipeline (SC-9).
- ~~**Compare different geometries.**~~ Dedicated Geometry Designer window
  (Tools menu): variants over nine planform parameters, any set of flight conditions,
  ranking at any condition, overlay panels, delta-vs-base figure, HTML report and CSV
  export; optional constant-thrust/CT trimming so efficiency compares fairly (SC-7).
- ~~**Design mode: geometry factorial sweep.**~~ Sweep builder in the same window;
  optimization stays an outer loop through the CLI (`--compare`, `--optimize`) and the
  library, deliberately outside the GUI (SC-8).
- ~~**Offer CST and Bézier profile sources in the GUI.**~~ Five contour sources
  (naca4, naca5, cst, bezier, imported) with editable coefficient and control-point
  fields, plus the shared `Geometry spec` grammar and presets catalog (SC-10).
