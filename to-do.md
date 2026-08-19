# To-do

1. **Unify axis nomenclature (Vx, Vz, alpha, mu, J, lambda, etc.) across GUI, `.bemt`, CLI, and engine.**
   Today the letter used for "flow axis" (x vs z) flips meaning between rotor mode and propeller mode (see CLAUDE.md, "Axes convention" section), and the engine (`bemt.py`, `FlightCondition`) always works in disk axes, while the GUI/report show vehicle axes — this already causes confusion even though it's documented. Survey EVERY point where an axis quantity appears under a different name than what the GUI shows: `FlightCondition`/`BEMTConfig` keys, fields saved in `.bemt`, CLI flags (`cli.py`), internal labels in `studies.py`/`api.py` (`_SIMBOLO_DE_COLUNA_HELICE` etc.). Do not touch `bemt.py` (the engine) or the internal disk-axes convention — only the input/output layer (`api.py`, `models.py`, `cli.py`, GUI, report, `.bemt`) should switch to the GUI's nomenclature as the single source of truth, with a centralized, tested translation table (not scattered across comments). Update `docs/software_requirements.md` and CLAUDE.md accordingly.
   Create an SVG with the axis convention (rotor: vertical shaft, x edgewise/z axial; propeller: horizontal shaft, x axial/z cross-flow) to make it visually unambiguous which axis is which in each mode — use it in `documentation.html` and possibly as a GUI help popup.

2. **Full refactor of `documentation.html`.**
   Rewrite it to be clearer, more concise, and more direct (it currently has redundant/verbose text in several places). Check every section against the current state of the code (`api.py`, `bemt.py`, `models.py`, GUI) — there are likely passages citing fields/flows that have already changed. `tests/test_documentation.py` already covers anchors, images, cited modules, etc.; keep those tests passing and, if needed, add new consistency checks during the refactor.

3. **Add time-stepping: dynamic Pitt-Peters and dynamic stall.**
   The solver currently resolves a steady/quasi-steady state per case. Introduce time integration (even a simple Euler/RK scheme) of dynamic inflow (Pitt-Peters with time derivatives, not just the static form already in use) and of the dynamic stall model (Cl/Cd hysteresis as a function of alpha's rate of change), enabling maneuver/transient simulation instead of only isolated operating points.

4. **Add simplified flapping and lead-lag (stiffness/virtual offset), coupled to Pitt-Peters.**
   Model blade flapping and lead-lag via a simplified spring/virtual-offset approximation (not real blade elasticity), coupled to the dynamic Pitt-Peters inflow from item 3, to capture the effect of these degrees of freedom on rotor response without needing a full aeroelastic model.

5. **XFoil support.**
   Allow generating/importing airfoil polars via XFoil (NeuralFoil already exists, see `external_solvers.py`) as an alternative/complement, following the same external-integration pattern already in use (CLI flag, GUI option, same airfoil-table pipeline).

6. **Support for comparing different geometries.**
   Allow loading/running multiple rotor/propeller geometries side by side (same flight condition or not) and viewing results overlaid/compared in plots and tables — today the flow is always one project/one geometry at a time.

7. **Design mode: geometry factorial sweep + useful plots.**
   Beyond the flight-condition factorial that already exists (`sweep_kind="factorial"` in `studies.py`), allow a factorial over geometry parameters (twist, chord, etc.) for design/optimization purposes, with comparative plots across the generated geometries (e.g., FM vs. parameter, performance envelope).

8. **Stability and control derivatives mode.**
   Numerically compute (perturbation around the trim point) the classic stability and control derivatives (e.g., dCT/dmu, dCT/dcollective, moment derivatives, etc.), including the effects of flapping, lead-lag (item 4), and dynamic inflow (item 3) on the response — needed for flight/control analysis beyond the static performance already covered.
