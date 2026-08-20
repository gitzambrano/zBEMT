# To-do

1. **Add time-stepping: dynamic Pitt-Peters and dynamic stall.**
   Integrate the inflow states and the separation state in time. Enables manoeuvre and
   transient simulation instead of isolated operating points.

2. **Add simplified flapping and lead-lag, coupled to Pitt-Peters.**
   Spring and virtual-offset approximation, not blade elasticity. Couple to item 1.

3. **XFoil support.**
   Generate and import polars via XFoil, following the NeuralFoil pattern in
   `external_solvers.py`: CLI flag, GUI option, same airfoil-table pipeline.

4. **Compare different geometries.**
   Load and run several rotors side by side and overlay the results in plots and tables.

5. **Design mode: geometry factorial sweep.**
   Factorial over geometry parameters (twist, chord), with comparative plots across the
   generated geometries.

6. **Stability and control derivatives.**
   Perturbation about the trim point. Include the effects of items 1 and 2.

7. **Offer CST and Bézier profile sources in the GUI.**
   `airfoils.generate_cst` / `generate_bezier` and the `ProfileGeometry` fields
   exist and are tested, but the Airfoil tab's source list offers only NACA and
   imported contours. Make the coefficient and control-point fields editable.
