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

- ~~**XFoil support.**~~ The engine runs `xfoil` alongside NeuralFoil, with dedicated
  transition inputs (`xfoil_ncrit`, `xfoil_xtr_top`, `xfoil_xtr_bot`) and a four-place
  binary lookup (`ZBEMT_XFOIL_BIN`, remembered Locate… pick, PATH, standard install
  folders). The CLI gains `--gen-xfoil` with `--ncrit`, `--xtr-top` and `--xtr-bot`,
  and the table pipeline stays the same (SC-9).
- ~~**Compare different geometries.**~~ A dedicated Geometry Designer window opens from
  the Tools button in the main window's top bar. It compares variants over nine planform
  parameters, generates variants from a planform family, imports variants from another
  project, runs any set of flight conditions, ranks at any condition, draws overlay
  panels and a delta-to-base figure, and writes an HTML report and a CSV export.
  Optional trimming holds thrust or `CT` constant so efficiency is compared at equal
  loading (SC-7).
- ~~**Design mode: geometry factorial sweep.**~~ The sweep builder lives in the same
  window. Optimization stays an outer loop through the CLI (`--compare`, `--optimize`)
  and the library, deliberately outside the GUI (SC-8).
- ~~**Offer CST and Bézier profile sources in the GUI.**~~ Eight contour sources
  (naca4, naca5, cst, bezier, parsec, joukowski, biconvex, imported) with editable
  per-family fields (SC-10).
- ~~**Surface partial external-polar convergence in the GUI.**~~ The engine writes a
  line to a diagnostics list for every Reynolds number it drops. The polar-generation
  status label reports "N of M Reynolds converged" with the failures named, and the CLI
  prints the same lines (SC-9).
