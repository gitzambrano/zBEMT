# To-do

## Open

1. **Add time-stepping: dynamic Pitt-Peters and dynamic stall.**
   Integrate the inflow states and the separation state in time. Enables manoeuvre and
   transient simulation instead of isolated operating points.

2. **Add simplified flapping and lead-lag, coupled to Pitt-Peters.**
   Spring and virtual-offset approximation, not blade elasticity. Couple to item 1.

3. **Stability and control derivatives.**
   Perturbation about the trim point. Include the effects of items 1 and 2.

## Done (on `feature/design-tools`)

- ~~**XFoil support.**~~ Engine `xfoil` alongside NeuralFoil: dedicated transition
  inputs (`xfoil_ncrit`, `xfoil_xtr_top`, `xfoil_xtr_bot`), four-place binary lookup
  (`ZBEMT_XFOIL_BIN`, remembered Locate… pick, PATH, standard install folders), CLI
  `--gen-xfoil` with `--ncrit/--xtr-top/--xtr-bot`, same table pipeline (SC-9).
- ~~**Compare different geometries.**~~ Dedicated Geometry Designer window (Tools
  button in the main window's top bar): variants over nine planform parameters,
  generate-from-family and import-from-project variants, any set of flight conditions,
  ranking at any condition, overlay panels, delta-vs-base figure, HTML report and CSV
  export; optional constant-thrust/CT trimming so efficiency compares fairly (SC-7).
- ~~**Design mode: geometry factorial sweep.**~~ Sweep builder in the same window;
  optimization stays an outer loop through the CLI (`--compare`, `--optimize`) and the
  library, deliberately outside the GUI (SC-8).
- ~~**Offer CST and Bézier profile sources in the GUI.**~~ Eight contour sources
  (naca4, naca5, cst, bezier, parsec, joukowski, biconvex, imported) with editable
  per-family fields (SC-10).
- ~~**Surface partial external-polar convergence in the GUI.**~~ Every Reynolds the
  engine drops leaves a line in a diagnostics list; the polar-generation status label
  reports "N of M Reynolds converged" with the failures named, and the CLI prints the
  same lines (SC-9).
