"""Rich contextual help content by field (Layer 3 of the documentation plan).

Each entry corresponds to a field from BEMTConfig, AirfoilDef, RotorGeometryDef,
or FlightCondition. The popup shows title, definition, unit, equation, effect,
and typical range. Enum fields also list each option with a short description.
"""
from __future__ import annotations

FIELD_HELP: dict[str, dict] = {
    "batches": {
        "title": "Saved batch",
        "definition": (
            "The named queue of conditions stored with the project.\n\n"
            "A batch is what makes a set of runs repeatable: the same "
            "queue, re-run after a change to the blade, is the only way "
            "to say the change did anything."),
        "unit": "—",
        "equation": None,
        "effect": "Selecting one replaces the queue on screen. Saving under an existing name overwrites that batch.",
        "range": "any name in the project",
        "options": None,
        "anchor": "cap-6-4",
    },
    "replace_queue": {
        "title": "Replace the queue when generating",
        "definition": (
            "Whether generating a sweep replaces the queue or adds to "
            "it.\n\n"
            "Adding is how a queue is built from more than one sweep: a "
            "hover point, then a forward-flight sweep, then a descent, "
            "all in one batch."),
        "unit": "—",
        "equation": None,
        "effect": "Checked, each generation starts a fresh queue. Unchecked, the generated cases are appended, so a second generation with the same axes doubles the queue rather than rebuilding it.",
        "range": "checked for a single sweep",
        "options": None,
        "anchor": "cap-6-3",
    },
    "outdir": {
        "title": "Output folder",
        "definition": (
            "Where the exported tables and figures are written.\n\n"
            "A batch produces one CSV and, depending on the plot "
            "switches, a large number of images, so it needs a "
            "destination of its own."),
        "unit": "—",
        "equation": None,
        "effect": "Left empty it defaults to a folder inside the project, so the results travel with the project they belong to. An absolute path sends them anywhere.",
        "range": "any writable folder",
        "options": None,
        "anchor": "cap-6-5",
    },
    "axis_quantity": {
        "title": "Axis quantity",
        "definition": (
            "Which flight-condition quantity this axis of the factorial "
            "sweeps.\n\n"
            "A factorial builds the FULL CROSS PRODUCT: every value of "
            "this axis is combined with every value of the others."),
        "unit": "that of the chosen quantity",
        "equation": r"N_{cases} = \prod_i N_i",
        "effect": "Two axes of ten values each is a hundred cases, not twenty. Adding a third axis of five makes it five hundred. The queue below shows what was actually built, and it is worth reading before running.",
        "range": "each axis must name a different quantity",
        "options": None,
        "anchor": "cap-6-1",
    },
    "axis_unit": {
        "title": "Axis unit",
        "definition": (
            "The form the values on this axis are written in.\n\n"
            "The same physical condition can be stated as a ratio, a "
            "speed, or an angle. This field says which one the list below "
            "uses."),
        "unit": "—",
        "equation": None,
        "effect": "It converts what is typed, not what is stored: the queue always holds the canonical quantity. A dimensional or angular unit needs the rpm and the radius, because the conversion runs through the tip speed.",
        "range": "depends on the chosen quantity",
        "options": None,
        "anchor": "cap-6-1",
    },
    "axis_values": {
        "title": "Axis values",
        "definition": (
            "The values this axis takes, separated by commas.\n\n"
            "This list is what the factorial actually uses. The range "
            "controls beside it are a convenience that WRITES into this "
            "list. They are not read directly."),
        "unit": "that of the axis unit",
        "equation": None,
        "effect": "Editing the list by hand is the way to cluster points where the answer changes fastest, which an evenly spaced range cannot do.",
        "range": "for example 0.0, 0.05, 0.1, 0.15",
        "options": None,
        "anchor": "cap-6-1",
    },
    "range_from": {
        "title": "Range start",
        "definition": (
            "First value the fill button writes into this axis's list."),
        "unit": "that of the axis unit",
        "equation": None,
        "effect": "Nothing happens until the fill button is pressed: this control does not change the sweep by itself, it only prepares what fill will write.",
        "range": "within the model's valid band",
        "options": None,
        "anchor": "cap-6-1",
    },
    "range_to": {
        "title": "Range end",
        "definition": (
            "Last value the fill button writes into this axis's list."),
        "unit": "that of the axis unit",
        "equation": None,
        "effect": "Reached exactly when the step divides the interval evenly, and otherwise the last value written is the largest one that still fits inside it.",
        "range": "within the model's valid band",
        "options": None,
        "anchor": "cap-6-1",
    },
    "range_step": {
        "title": "Range step",
        "definition": (
            "Spacing between consecutive values of the generated "
            "range.\n\n"
            "It sets the case count, and the case count sets the run "
            "time."),
        "unit": "that of the axis unit",
        "equation": r"N = \left\lfloor\dfrac{x_{to}-x_{from}}{\Delta x}\right\rfloor + 1",
        "effect": "Halving the step doubles the number of cases on this axis, and multiplies the total by two on every other axis as well.",
        "range": "coarse first, refined once the shape is known",
        "options": None,
        "anchor": "cap-6-1",
    },
    "plots": {
        "title": "Exported plots",
        "definition": (
            "Which figures are written for the batch.\n\n"
            "Each one answers a different question: how the "
            "coefficients move across the queue, what one blade does "
            "through a revolution, how the load is distributed along "
            "the span, and what the disk looks like from above."),
        "unit": "—",
        "equation": None,
        "effect": "The disk maps cost the most time, because they are one image per field per condition. On a long queue, switching them off is the difference between a quick batch and a slow one.",
        "range": "any combination, including none",
        "options": None,
        "anchor": "cap-6-5",
    },
    "save_csv": {
        "title": "Save CSV",
        "definition": (
            "Writes the summary table of the batch as a comma-separated "
            "file.\n\n"
            "One row per condition and one column per summary quantity, "
            "under the axis letters of the project's mode."),
        "unit": "—",
        "equation": None,
        "effect": "It is the export the results are usually read from outside the program. The figures are a view of the same numbers. The CSV is the numbers.",
        "range": "on for any batch whose results will be used elsewhere",
        "options": None,
        "anchor": "cap-6-5",
    },
    "trim_mode": {
        "title": "Trim mode",
        "definition": (
            "What the solver holds fixed while it solves.\n\n"
            "Without a trim, the collective written in the condition is "
            "the answer's input and the thrust is its output. With one, "
            "the roles swap: the thrust is stated and the collective is "
            "solved for."),
        "unit": "—",
        "equation": r"\text{solve}\;\theta_0\;\text{such that}\;T(\theta_0)=T_{target}",
        "effect": "It changes what a comparison MEANS. Two rotors at the same collective are compared at two different thrusts. At the same thrust they are compared at two different collectives, which is nearly always the intended question.",
        "range": "off | thrust | a coefficient",
        "options": None,
        "anchor": "cap-5-5",
    },
    "target_kind": {
        "title": "Trim target quantity",
        "definition": (
            "Which quantity the trim drives to its target.\n\n"
            "Thrust is dimensional and belongs to one rotor at one air "
            "density. The coefficient is non-dimensional and is what "
            "makes two rotors of different size comparable at all."),
        "unit": "—",
        "equation": r"C_T=\dfrac{T}{\rho A(\Omega R)^2}",
        "effect": "Trimming to a thrust in newtons compares rotors carrying the same weight. Trimming to a thrust coefficient compares them at the same blade loading, which is the fairer comparison between different diameters.",
        "range": "thrust [N] | thrust coefficient",
        "options": None,
        "anchor": "cap-5-5",
    },
    "target_value": {
        "title": "Trim target value",
        "definition": (
            "The number the trim drives the chosen quantity to.\n\n"
            "It has to be reachable: a target above what the blade can "
            "produce before it stalls has no collective that satisfies "
            "it."),
        "unit": "N, or dimensionless",
        "equation": None,
        "effect": "The solver iterates the collective until the quantity matches. An unreachable target does not fail silently: the run reports that it did not converge, and the collective it stopped at.",
        "range": "within what the rotor can produce unstalled",
        "options": None,
        "anchor": "cap-5-5",
    },
    # ---- Geometry Designer (chapter 13) ------------------------------
    "vsweep_param": {
        "title": "Swept geometry parameter",
        "definition": (
            "Which property of the blade is varied across the generated "
            "variants.\n\n"
            "A variation study answers one question at a time: what "
            "happens when THIS changes and nothing else does."),
        "unit": "that of the chosen parameter",
        "equation": None,
        "effect": "Every generated row differs from the base geometry in this parameter alone, so any difference in the result belongs to it and not to a second change made at the same time.",
        "range": "any parameter the generator accepts",
        "options": None,
        "anchor": "designer-variants",
    },
    "vsweep_start": {
        "title": "First generated value",
        "definition": "The lower bound of the generated sweep, included.",
        "unit": "that of the swept parameter",
        "equation": r"x_k = x_{start} + k\,\dfrac{x_{end}-x_{start}}{N-1}",
        "effect": "Choose it and the end so the base geometry sits inside the range: a sweep that never reaches the current design gives no reference point to read the others against.",
        "range": "physically buildable values",
        "options": None,
        "anchor": "designer-variants",
    },
    "vsweep_end": {
        "title": "Last generated value",
        "definition": "The upper bound of the generated sweep, included.",
        "unit": "that of the swept parameter",
        "equation": None,
        "effect": "Included exactly, so a sweep of N rows lands on this value rather than one step short of it.",
        "range": "physically buildable values",
        "options": None,
        "anchor": "designer-variants",
    },
    "vsweep_count": {
        "title": "Number of generated variants",
        "definition": (
            "How many evenly spaced values are produced between the "
            "bounds."),
        "unit": "—",
        "equation": None,
        "effect": "Each variant is a full solve at every condition, so this multiplies the run time directly. Three points show a trend; they do not show a maximum, which needs at least five.",
        "range": "3 to 15",
        "options": None,
        "anchor": "designer-variants",
    },
    "vsweep_values": {
        "title": "Explicit values",
        "definition": (
            "A comma-separated list used INSTEAD of the evenly spaced "
            "sweep.\n\n"
            "An even sweep spends the same effort everywhere. A real "
            "study usually wants points clustered where the answer is "
            "changing fastest."),
        "unit": "that of the swept parameter",
        "equation": None,
        "effect": "When it is not empty it overrides Start, End and Count. Leave it empty to use the even sweep.",
        "range": "for example 0.04, 0.06, 0.07, 0.075",
        "options": None,
        "anchor": "designer-variants",
    },
    "gen_family": {
        "title": "Planform family",
        "definition": (
            "The shape of the generated blade.\n\n"
            "Each family is a different way of spending the same blade "
            "area along the span, and the span is where the local "
            "velocity varies as r."),
        "unit": "—",
        "equation": r"\sigma = \dfrac{N_b\,\bar{c}}{\pi R}",
        "effect": "Rectangular keeps one chord throughout and is the reference case. Tapered moves area inboard, cutting the tip loading where the velocity is highest. Elliptic approaches the minimum induced power for a given thrust.",
        "range": "rectangular | tapered | elliptic",
        "options": None,
        "anchor": "designer-variants",
    },
    "sweep_axis": {
        "title": "Swept flight quantity",
        "definition": (
            "The quantity carried through evenly spaced values to build "
            "the list of conditions.\n\n"
            "It is the x axis of every curve the comparison draws."),
        "unit": "that of the chosen quantity",
        "equation": None,
        "effect": "Sweeping the advance ratio gives the forward-flight curves; sweeping the collective gives the thrust curves; sweeping the rotational speed gives the tip-speed trend.",
        "range": "mu_x | collective | rpm | the axial component",
        "options": None,
        "anchor": "designer-conditions",
    },
    "sweep_start": {
        "title": "First swept value",
        "definition": "The lower bound of the condition sweep, included.",
        "unit": "that of the swept quantity",
        "equation": None,
        "effect": "It sets where every curve begins. Starting at zero includes hover or the static case, which is often the only point with an independent reference to check against.",
        "range": "within the model's valid band",
        "options": None,
        "anchor": "designer-conditions",
    },
    "sweep_stop": {
        "title": "Last swept value",
        "definition": "The upper bound of the condition sweep, included.",
        "unit": "that of the swept quantity",
        "equation": None,
        "effect": "Included exactly. Pushing it past the point where the blade stalls or the momentum theory loses its solution produces numbers, but not answers.",
        "range": "within the model's valid band",
        "options": None,
        "anchor": "designer-conditions",
    },
    "sweep_count": {
        "title": "Number of swept conditions",
        "definition": (
            "How many evenly spaced conditions the sweep produces."),
        "unit": "—",
        "equation": r"N_{solves} = N_{variants}\times N_{conditions}",
        "effect": "It multiplies with the variant count, so a five-variant study over twenty conditions is a hundred solves. Refine it once the shape of the curve is known, not before.",
        "range": "5 to 25",
        "options": None,
        "anchor": "designer-conditions",
    },
    "ranking_field": {
        "title": "Ranking quantity",
        "definition": (
            "The summary quantity the variants are ordered by.\n\n"
            "A comparison has to choose what 'better' means before it "
            "can rank anything, and no single quantity means it in every "
            "study."),
        "unit": "that of the chosen quantity",
        "equation": None,
        "effect": "The ranking is on ONE quantity at the reference condition. A variant that wins on the figure of merit may lose on torque, which is exactly what the full table beside the ranking is for.",
        "range": "any summary key the results carry",
        "options": None,
        "anchor": "designer-run",
    },
    "ranking_condition": {
        "title": "Reference condition of the ranking",
        "definition": (
            "Which of the swept conditions the ranking reads.\n\n"
            "The ordering is not the same at every condition: a blade "
            "that is best in hover is frequently not the one that is "
            "best in cruise, and that reversal is usually the finding."),
        "unit": "—",
        "equation": None,
        "effect": "Changing it re-orders the table without re-running anything, because every variant was already solved at every condition.",
        "range": "any condition in the sweep",
        "options": None,
        "anchor": "designer-run",
    },
    "root_chord_norm": {
        "title": "Root chord",
        "definition": (
            "Chord at the root station of the generated blade, as c/R.\n\n"
            "Together with the tip chord it fixes the taper, and taper "
            "is how area is moved inboard, away from the fast-moving "
            "tip."),
        "unit": "—",
        "equation": r"c(r) = c_{root} + (c_{tip}-c_{root})\,\bar{r}",
        "effect": "A wider root raises solidity and thrust at the same collective, at stations where the local velocity is low, so it buys thrust more cheaply in power than widening the tip would.",
        "range": "0.02 to 0.2 of the radius",
        "options": None,
        "anchor": "designer-variants",
    },
    "max_chord_norm": {
        "title": "Maximum chord",
        "definition": (
            "The peak chord of the elliptic planform, as c/R, reached at "
            "mid span.\n\n"
            "An elliptic blade has no free root or tip chord: the whole "
            "distribution follows from this one number."),
        "unit": "—",
        "equation": r"c(\bar{r}) = c_{max}\sqrt{1-\bar{r}^{\,2}}",
        "effect": "It scales the whole planform, so it sets the solidity and with it the thrust at a given collective. The elliptic shape is what approaches the minimum induced power for that thrust.",
        "range": "0.05 to 0.25 of the radius",
        "options": None,
        "anchor": "designer-variants",
    },
    # ---- the Transient builder (15.2) --------------------------------
    "build_case_a": {
        "title": "Start condition of the ramp",
        "definition": (
            "The saved case the trajectory begins at.\n\n"
            "The builder is a shortcut for the common transient: hold "
            "one condition, move to another over a stated time, hold "
            "that one."),
        "unit": "—",
        "equation": None,
        "effect": "It becomes the first node of the maneuver. Everything the case carries travels with it: the advance ratio, the collective, the cyclic and the rotational speed.",
        "range": "any case saved in the project",
        "options": None,
        "anchor": "cap-transiente-2",
    },
    "build_case_b": {
        "title": "End condition of the ramp",
        "definition": (
            "The saved case the trajectory finishes at."),
        "unit": "—",
        "equation": None,
        "effect": "It becomes the last node. The two cases may differ in more than one quantity at once, and then all of them ramp together, which is a maneuver rather than a parameter study.",
        "range": "any case saved in the project",
        "options": None,
        "anchor": "cap-transiente-2",
    },
    # ---- states perturbed by the derivative study (16.2) -------------
    "u": {
        "title": "u — longitudinal speed",
        "definition": (
            "Perturbation of the speed along the vehicle's x axis.\n\n"
            "It changes the IN-PLANE component of the free stream, so "
            "the disk sees a different advance ratio and the advancing "
            "and retreating sides become more unequal."),
        "unit": "m/s",
        "equation": r"\partial(\cdot)/\partial u",
        "effect": "Gives the speed-damping and speed-stability derivatives. With a hub arm above the CG, the drag change it produces is what pitches the aircraft, and therefore what drives the long-period mode.",
        "range": "step of about 0.1 to 1 m/s",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    "v": {
        "title": "v — lateral speed",
        "definition": (
            "Perturbation of the speed along the vehicle's y axis.\n\n"
            "It rotates the in-plane free stream rather than changing "
            "its size, which is why it is entered as a sideslip on the "
            "condition."),
        "unit": "m/s",
        "equation": r"\partial(\cdot)/\partial v",
        "effect": "Gives the lateral force and rolling-moment derivatives. In hover they are near zero by symmetry. In forward flight they are not, and that asymmetry is what couples roll to sideslip.",
        "range": "step of about 0.1 to 1 m/s",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    "w": {
        "title": "w — axial speed",
        "definition": (
            "Perturbation of the speed along the shaft.\n\n"
            "It is the component the induced velocity adds to, so it "
            "moves the rotor along its own momentum-theory curve."),
        "unit": "m/s",
        "equation": r"\partial T/\partial w",
        "effect": "Gives the heave damping, the strongest and most reliable derivative of a rotor. It is negative in every normal state: climb into the flow and the thrust falls, which is what makes heave stable.",
        "range": "step of about 0.1 to 1 m/s",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    "p": {
        "title": "p — roll rate",
        "definition": (
            "Perturbation of the roll rate of the hub.\n\n"
            "A rate, not a displacement: the hub is rolling while the "
            "blade goes round, so each blade meets a different "
            "out-of-plane velocity depending on where it is in azimuth."),
        "unit": "rad/s",
        "equation": r"\partial M/\partial p",
        "effect": "Gives the roll damping. On a blade with flap freedom it also produces a pitching moment, the classical cross-coupling whose phase lag is set by the Lock number.",
        "range": "step of about 0.01 to 0.1 rad/s",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    "q": {
        "title": "q — pitch rate",
        "definition": (
            "Perturbation of the pitch rate of the hub.\n\n"
            "The counterpart of p about the other in-plane axis, and it "
            "reaches the blade the same way: as a 1/rev variation of the "
            "out-of-plane velocity."),
        "unit": "rad/s",
        "equation": r"\partial M/\partial q",
        "effect": "Gives the pitch damping, and the roll moment that comes with it. The two cross-derivatives are what make a helicopter answer a pitch input partly in roll.",
        "range": "step of about 0.01 to 0.1 rad/s",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    "Omega": {
        "title": "Ω — rotor speed",
        "definition": (
            "Perturbation of the rotational speed.\n\n"
            "Unlike the others it rescales EVERYTHING at once: the tip "
            "speed, the dynamic pressure at every station, and the "
            "advance ratio the condition is stated at."),
        "unit": "rpm",
        "equation": r"\partial Q/\partial \Omega",
        "effect": "Gives the derivative an engine or governor model would need. Because it changes the reference scale, the non-dimensional coefficients move even when the dimensional forces barely do.",
        "range": "step of about 1 to 10 rpm",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    # ---- controls ----------------------------------------------------
    "theta_0": {
        "title": "θ₀ — collective",
        "definition": (
            "Perturbation of the collective pitch.\n\n"
            "A rigid offset added to the twist at every station, so it "
            "moves the whole blade's angle of attack together."),
        "unit": "deg",
        "equation": r"\partial T/\partial \theta_0",
        "effect": "The primary thrust control, and the largest column of the B matrix. It falls off as the blade approaches stall, which is one of the few places the derivative itself stops being constant.",
        "range": "step of about 0.1 to 0.5 deg",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    "theta_1c": {
        "title": "θ₁c — cosine cyclic",
        "definition": (
            "Perturbation of the cosine harmonic of the cyclic pitch.\n\n"
            "Unlike the collective it varies with azimuth, so it does "
            "not change the total thrust much: it TILTS the disk."),
        "unit": "deg",
        "equation": r"\theta(\psi)=\theta_0+\theta_{1c}\cos\psi+\theta_{1s}\sin\psi",
        "effect": "Needs a blade with flap freedom. On a rigid blade the pitch change produces no disk tilt and the derivative is meaningless, which is why the control is disabled there.",
        "range": "step of about 0.1 to 0.5 deg",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    "theta_1s": {
        "title": "θ₁s — sine cyclic",
        "definition": (
            "Perturbation of the sine harmonic of the cyclic pitch.\n\n"
            "The other half of the disk tilt, ninety degrees of azimuth "
            "away from the cosine one."),
        "unit": "deg",
        "equation": r"\theta(\psi)=\theta_0+\theta_{1c}\cos\psi+\theta_{1s}\sin\psi",
        "effect": "The blade answers a pitch input about a quarter of a revolution later, so a sine input tilts the disk mostly in the cosine direction. That phase lag is the reason the two cyclic columns are strongly cross-coupled.",
        "range": "step of about 0.1 to 0.5 deg",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    # ---- outputs measured (16.5) -------------------------------------
    "Thrust": {
        "title": "Thrust",
        "definition": (
            "Total force along the shaft, summed over the blades and "
            "averaged over one revolution."),
        "unit": "N",
        "equation": r"T=\int_{0}^{R} dT",
        "effect": "The output most derivatives are read against. Its derivative with respect to w is the heave damping and its derivative with respect to the collective is the primary control power.",
        "range": "—",
        "options": None,
        "anchor": "cap-stability-run",
    },
    "H": {
        "title": "H — in-plane drag force",
        "definition": (
            "In-plane force along the longitudinal axis: the rotor's "
            "drag in the disk plane."),
        "unit": "N",
        "equation": r"H=\int (dD\sin\psi + dL\,\ldots)",
        "effect": "Small compared with the thrust and decisive anyway: with a hub above the CG it is the force whose arm pitches the aircraft, so it carries the speed-to-pitch coupling.",
        "range": "—",
        "options": None,
        "anchor": "cap-stability-run",
    },
    "Y": {
        "title": "Y — in-plane side force",
        "definition": (
            "In-plane force along the lateral axis, the companion of H "
            "about the other axis."),
        "unit": "N",
        "equation": None,
        "effect": "Near zero in hover by symmetry. In forward flight it is what a sideslip produces, and with a hub arm it rolls the aircraft.",
        "range": "—",
        "options": None,
        "anchor": "cap-stability-run",
    },
    "Mx_total": {
        "title": "Mx,total — hub moment about the ψ=0 axis",
        "definition": (
            "Total moment about the reference in-plane axis, INCLUDING "
            "the structural part carried through a hinge offset or a "
            "root spring."),
        "unit": "N·m",
        "equation": r"M_{hub}=\frac{N_b}{2}I_\beta\Omega^2(\nu_\beta^2-1)\beta_1",
        "effect": "On an articulated blade with no offset the structural part vanishes and only the aerodynamic tilt remains. Offset and spring are what let the rotor transmit a moment to the aircraft at all.",
        "range": "—",
        "options": None,
        "anchor": "cap-stability-hub",
    },
    "My_total": {
        "title": "My,total — hub moment about the ψ=90° axis",
        "definition": (
            "The companion of Mx,total about the other in-plane axis, "
            "built from the same hinge path."),
        "unit": "N·m",
        "equation": None,
        "effect": "The two together are the disk tilt expressed as a moment. Their cross-derivatives with p and q carry the phase lag that couples pitch and roll.",
        "range": "—",
        "options": None,
        "anchor": "cap-stability-hub",
    },
    "Torque": {
        "title": "Torque",
        "definition": (
            "Moment about the shaft: what the engine has to supply."),
        "unit": "N·m",
        "equation": r"Q=\int_{0}^{R} r\,dF_{\text{in-plane}}",
        "effect": "Its derivative with respect to the collective is what an engine or governor model needs, and its derivative with respect to Ω is the rotor's own speed stability.",
        "range": "—",
        "options": None,
        "anchor": "cap-stability-run",
    },
    # ---- shared by the Optimization and Stability windows ------------
    "condition": {
        "title": "Flight condition of the study",
        "definition": (
            "The saved case every design or perturbation is solved "
            "at.\n\n"
            "A rotor is not better or worse in the abstract: it is "
            "better at a stated advance ratio, collective and rotational "
            "speed. Comparing designs across different conditions "
            "compares nothing."),
        "unit": "—",
        "equation": None,
        "effect": "Every number the study reports belongs to this condition and to no other. It must carry an rpm, because the engine needs one to form the tip speed.",
        "range": "any case saved in the project",
        "options": None,
        "anchor": "cap-opt-condition",
    },
    "trim": {
        "title": "Trim",
        "definition": (
            "What is held fixed before the run begins.\n\n"
            "Without a trim, a comparison between two rotors at the same "
            "collective is a comparison at two different thrusts, which "
            "is rarely the question being asked."),
        "unit": "—",
        "equation": r"\theta_0\;\text{or}\;(\theta_{1c},\theta_{1s})\;\text{solved first}",
        "effect": "Zero flapping leaves the controls as written. A thrust trim drives the collective to a stated thrust. A cyclic flapback trim removes the 1/rev disk tilt and needs a blade with flap freedom.",
        "range": "none | thrust | cyclic flapback",
        "options": None,
        "anchor": "cap-stability-trim",
    },
    "parallel_workers": {
        "title": "Parallel workers",
        "definition": (
            "How many designs are solved at the same time.\n\n"
            "Each one runs in its own process, so they do not share "
            "memory and the answer does not depend on how many are "
            "running."),
        "unit": "—",
        "equation": None,
        "effect": "Only the wall-clock time changes. Results are collected in submission order, so one worker and eight workers produce the same front, member for member. In the derivative study the value is stored but not yet used. That run is serial.",
        "range": "1 to the number of cores",
        "options": None,
        "anchor": "cap-opt-workers",
    },
    # ---- Design Optimization (chapter 14) ----------------------------
    "optimization": {
        "title": "Optimization study",
        "definition": (
            "The named search this window runs.\n\n"
            "A study fixes the objectives, the constraints, the design "
            "variables, the condition and the algorithm, so a search can "
            "be repeated instead of re-entered."),
        "unit": "—",
        "equation": None,
        "effect": "Stored in inputs/optimizations.bemt and run from the CLI with --optimize NAME.",
        "range": "any name in the project",
        "options": None,
        "anchor": "cap-optimization",
    },
    "objectives": {
        "title": "Objective",
        "definition": (
            "The quantity the search drives, taken from the results "
            "summary.\n\n"
            "One objective gives a single best design. Two give a "
            "PARETO FRONT: a set of designs where nothing can be "
            "improved on one objective without giving up the other."),
        "unit": "that of the chosen quantity",
        "equation": r"\min_{x\in X} \;\left(f_1(x),\;f_2(x)\right)",
        "effect": "Leaving the second objective empty runs a single-objective search. Filling it runs NSGA-II and produces a front instead of a winner.",
        "range": "any summary key (FM, CT, eta_prop, Torque, ...)",
        "options": None,
        "anchor": "cap-opt-objectives",
    },
    "kind": {
        "title": "Direction of the objective",
        "definition": (
            "Whether the quantity is to be made larger or smaller.\n\n"
            "The search minimizes internally, so a maximization is "
            "carried as its negative. Getting the direction wrong does "
            "not fail: it converges, on the worst design it can find."),
        "unit": "—",
        "equation": None,
        "effect": "Maximize for a figure of merit or an efficiency; minimize for torque, power or a loading.",
        "range": "maximize | minimize",
        "options": None,
        "anchor": "cap-opt-objectives",
    },
    "algorithm": {
        "title": "Search algorithm",
        "definition": (
            "How the population is moved from one generation to the "
            "next.\n\n"
            "Both are population methods that need no gradient, which "
            "matters because a BEMT solve gives none and the objective "
            "surface has flat and stalled regions where a gradient would "
            "be misleading anyway."),
        "unit": "—",
        "equation": None,
        "effect": "NSGA-II ranks by non-domination and crowding, so it evolves a whole front and is the choice for two objectives. Differential evolution drives a single value and is the cheaper choice for one.",
        "range": "nsga2 | de",
        "options": None,
        "anchor": "cap-opt-algorithm",
    },
    "population": {
        "title": "Population",
        "definition": (
            "How many designs are alive in each generation.\n\n"
            "It sets how much of the design space is sampled at once. "
            "Too small a population converges quickly onto one corner of "
            "the front and reports it as the whole front."),
        "unit": "—",
        "equation": r"N_{eval} = N_{pop}\,(1+N_{gen})",
        "effect": "Every generation costs one solve per member, so this multiplies the run time directly. A front needs a larger population than a single-objective search, because the members have to spread along it.",
        "range": "8 to 500; 40 to 100 for two objectives",
        "options": None,
        "anchor": "cap-opt-budget",
    },
    "generations": {
        "title": "Generations",
        "definition": (
            "How many rounds of selection and variation run after the "
            "initial sample.\n\n"
            "The population converges over generations. The hypervolume "
            "curve on the Convergence view is what says whether it "
            "already has."),
        "unit": "—",
        "equation": None,
        "effect": "More generations refine the front but cost one population of solves each. A hypervolume curve that has flattened says further generations buy nothing.",
        "range": "10 to 100",
        "options": None,
        "anchor": "cap-opt-budget",
    },
    "seed": {
        "title": "Random seed",
        "definition": (
            "Fixes the random numbers the search draws.\n\n"
            "An evolutionary search is stochastic: the same study run "
            "twice gives two different fronts unless the seed is held."),
        "unit": "—",
        "equation": None,
        "effect": "The same seed reproduces the same search exactly. Changing it is the honest way to ask whether a front is a property of the design space or of one lucky draw.",
        "range": "any integer",
        "options": None,
        "anchor": "cap-opt-budget",
    },
    "crossover_eta": {
        "title": "Crossover distribution index",
        "definition": (
            "The distribution index \u03b7\u1d04 of simulated binary "
            "crossover.\n\n"
            "It decides how far a child may fall from the two parents "
            "that produced it, and therefore how much of the search is "
            "exploration rather than refinement."),
        "unit": "—",
        "equation": r"\eta_c",
        "effect": "Larger keeps children close to their parents, refining what is already found. Smaller spreads them, which explores but converges more slowly.",
        "range": "5 to 30; 15 is the usual default",
        "options": None,
        "anchor": "cap-opt-operators",
    },
    "mutation_eta": {
        "title": "Mutation distribution index",
        "definition": (
            "The distribution index \u03b7\u2098 of polynomial "
            "mutation.\n\n"
            "Mutation is what stops the population collapsing onto one "
            "point: it perturbs a variable away from its inherited "
            "value."),
        "unit": "—",
        "equation": r"\eta_m",
        "effect": "Larger makes the perturbation smaller, so the search settles sooner. Smaller keeps it moving and is the remedy when every member has become the same design.",
        "range": "5 to 50; 20 is the usual default",
        "options": None,
        "anchor": "cap-opt-operators",
    },
    "mutation_rate": {
        "title": "Mutation rate",
        "definition": (
            "The probability that any one variable is mutated.\n\n"
            "ZERO IS NOT OFF: it selects the NSGA-II default of one over "
            "the number of variables, so on average one variable per "
            "child is perturbed."),
        "unit": "—",
        "equation": r"p_m = 1/n_{var}\;\text{when set to }0",
        "effect": "Raising it explores harder at the cost of destroying good combinations more often. The default is a deliberate compromise and is rarely worth changing first.",
        "range": "0 (the default rule) to 1",
        "options": None,
        "anchor": "cap-opt-operators",
    },
    # ---- Transient (chapter 15) --------------------------------------
    "maneuver": {
        "title": "Maneuver",
        "definition": (
            "The named trajectory this window marches.\n\n"
            "A maneuver is not a batch: each sample INHERITS the inflow "
            "state of the sample before it, which is the whole reason a "
            "transient differs from a sequence of steady solves."),
        "unit": "—",
        "equation": None,
        "effect": "Stored in inputs/maneuvers.bemt and run from the CLI with --maneuver NAME.",
        "range": "any name in the project",
        "options": None,
        "anchor": "cap-transiente",
    },
    "build_duration": {
        "title": "Ramp duration",
        "definition": (
            "Seconds of transition between the two saved cases the "
            "builder ramps across.\n\n"
            "It is what makes the trajectory a transient rather than a "
            "step: the shorter it is, the further the inflow lags "
            "behind the condition."),
        "unit": "s",
        "equation": None,
        "effect": "A long ramp approaches a sequence of steady states. A short one is where the dynamic inflow, and any dynamic stall carried along with it, actually show themselves.",
        "range": "one to a few rotor revolutions",
        "options": None,
        "anchor": "cap-transiente-2",
    },
    "interpolation": {
        "title": "Interpolation between points",
        "definition": (
            "How the condition moves between two nodes of the "
            "trajectory.\n\n"
            "The nodes state where the vehicle is at given instants. "
            "This field states what it does in between."),
        "unit": "—",
        "equation": None,
        "effect": "Linear ramps every quantity smoothly between the nodes. Hold keeps each node's value until the next one, which turns the trajectory into a staircase of steps.",
        "range": "linear | hold",
        "options": None,
        "anchor": "cap-transiente-2",
    },
    "dt_s": {
        "title": "Output sample interval",
        "definition": (
            "The time between two rows of the marched result.\n\n"
            "It sets what the output can resolve, not what the solver "
            "resolves: the inflow is advanced on the finer sub-step "
            "grid underneath."),
        "unit": "s",
        "equation": r"N_{rows} = T/\Delta t",
        "effect": "Smaller gives a finer trace and a longer file. It has to be small enough to resolve the fastest thing the maneuver does, or the trace will alias it into something smoother than it was.",
        "range": "a small fraction of one revolution",
        "options": None,
        "anchor": "cap-transiente-3",
    },
    "substeps_per_step": {
        "title": "Inflow sub-steps per sample",
        "definition": (
            "How many times the inflow state is advanced inside one "
            "output sample.\n\n"
            "The dynamic inflow has its own time constant, and it is "
            "usually shorter than the interval anyone wants to write "
            "rows at."),
        "unit": "—",
        "equation": r"\delta t = \Delta t / N_{sub}",
        "effect": "More sub-steps integrate the inflow more accurately at no cost in file size. Too few make the march itself inaccurate, which does not look like an error: it looks like a slightly different answer.",
        "range": "4 to 16",
        "options": None,
        "anchor": "cap-transiente-3",
    },
    "initial_state": {
        "title": "Where the march starts",
        "definition": (
            "The inflow the first sample begins from.\n\n"
            "A transient has to start somewhere, and that choice is "
            "visible in the first few samples of every result."),
        "unit": "—",
        "equation": None,
        "effect": "Equilibrium solves the steady inflow at the first condition and starts from it, so the trace begins already settled. Zero starts from no inflow at all and shows the build-up, which is the honest choice for a start from rest.",
        "range": "equilibrium | zero",
        "options": None,
        "anchor": "cap-transiente-4",
    },
    "march_dynamic_stall": {
        "title": "March dynamic stall",
        "definition": (
            "Carries the separation state from one sample to the next "
            "instead of re-solving it.\n\n"
            "Dynamic stall is a memory effect: what the boundary layer "
            "does now depends on what the angle of attack has been "
            "doing, not only on what it is."),
        "unit": "—",
        "equation": None,
        "effect": "On, the hysteresis loop appears, and with it the overshoot in lift and the delayed drag rise. Off, each sample is solved as if the blade had always been at that angle.",
        "range": "needs a dynamic-stall model in Config",
        "options": None,
        "anchor": "cap-transiente-5",
    },
    "march_flapping": {
        "title": "March flapping",
        "definition": (
            "Solves the periodic flap response at every sample and "
            "carries it forward.\n\n"
            "The disk tilt is what couples the blade's motion back into "
            "the flow, so a maneuver that changes the disk tilt changes "
            "the inflow through it."),
        "unit": "—",
        "equation": None,
        "effect": "On, the coning and 1/rev harmonics are recomputed as the condition moves. Off, the blade is held rigid. Needs flap freedom set in the Geometry tab: on a rigid blade there is nothing to march.",
        "range": "needs a non-rigid flap model",
        "options": None,
        "anchor": "cap-transiente-5",
    },
    # ---- Stability derivatives (chapter 16) --------------------------
    "derivatives": {
        "title": "Derivative study",
        "definition": (
            "The named study this window runs.\n\n"
            "A study fixes what is perturbed, what is measured, how big "
            "each step is and at which flight condition, so that a set "
            "of derivatives can be reproduced exactly rather than "
            "re-typed."),
        "unit": "—",
        "equation": None,
        "effect": "Selecting a study loads its whole definition into the form. Studies are stored in inputs/derivatives.bemt and are what the CLI runs with --derivatives NAME.",
        "range": "any name in the project",
        "options": None,
        "anchor": "cap-stability",
    },
    "trim_target_thrust": {
        "title": "Thrust target of the trim",
        "definition": (
            "The thrust the collective is driven to before any "
            "perturbation is applied.\n\n"
            "A derivative is a slope AT A POINT, so the point has to be "
            "defined. Comparing two rotors at the same collective "
            "compares them at different thrusts. Comparing them at the "
            "same thrust is almost always the question actually being "
            "asked."),
        "unit": "N",
        "equation": r"\theta_0 \;\text{such that}\; T(\theta_0)=T_{target}",
        "effect": "Zero leaves the condition untrimmed and uses its collective as written. A nonzero value solves for the collective first, so every perturbation is taken about the trimmed state.",
        "range": "0 (untrimmed), or the vehicle weight",
        "options": None,
        "anchor": "cap-stability-trim",
    },
    "richardson_check": {
        "title": "Richardson half-step check",
        "definition": (
            "Repeats every derivative at half the step and compares.\n\n"
            "A central difference carries two errors that move in "
            "opposite directions: truncation, which falls as the square "
            "of the step, and round-off, which grows as the step "
            "shrinks. A single step size cannot tell you which one you "
            "are dominated by. Two can."),
        "unit": "—",
        "equation": r"f'(x)\approx\dfrac{f(x+h)-f(x-h)}{2h}+O(h^2)",
        "effect": "Doubles the cost of the study and reports, per derivative, how far the half-step answer moved. A value that changes a lot means the step is wrong for that variable, not that the derivative is uncertain by that much.",
        "range": "on for any study whose numbers will be quoted",
        "options": None,
        "anchor": "cap-stability-steps",
    },
    # ---- The vehicle block (16.6) ------------------------------------
    "vehicle_enabled": {
        "title": "Build the rigid-body A/B matrices",
        "definition": (
            "Turns the rotor derivatives into aircraft motion.\n\n"
            "The derivatives above belong to the ROTOR. Making them "
            "predict how a vehicle moves needs the vehicle, and the "
            "vehicle is not derivable from the blade: its mass, its "
            "inertias and where the hub sits have to be stated."),
        "unit": "—",
        "equation": r"\dot{x}=Ax+Bu",
        "effect": "Off, the window reports the derivative matrix alone. On, it also builds A and B and draws their eigenvalues. It models ONE ROTOR: no fuselage, no tail rotor, no stabiliser, no engine or governor dynamics.",
        "range": "needs u, v, w and p, q among the states",
        "options": None,
        "anchor": "cap-stability-vehicle",
    },
    "vehicle_mass_kg": {
        "title": "Vehicle mass",
        "definition": (
            "Total mass the rotor forces accelerate.\n\n"
            "It is what converts a force derivative into an "
            "acceleration, so it scales every translational row of the "
            "A matrix and nothing else."),
        "unit": "kg",
        "equation": r"A_{u,u}=-\dfrac{1}{m}\dfrac{\partial H}{\partial u}",
        "effect": "A heavier vehicle responds more slowly to the same rotor force, which moves the translational modes toward the origin. It does not touch the rotational rows.",
        "range": "the all-up mass of the aircraft",
        "options": None,
        "anchor": "cap-stability-vehicle",
    },
    "vehicle_Ix_kg_m2": {
        "title": "Roll inertia",
        "definition": (
            "Moment of inertia about the longitudinal axis.\n\n"
            "It converts a rolling moment into a roll acceleration, so "
            "it sets the time scale of the roll response."),
        "unit": "kg·m²",
        "equation": r"A_{p,p}=\dfrac{1}{I_x}\dfrac{\partial M_y}{\partial p}",
        "effect": "Larger inertia slows the roll mode. For a helicopter Ix is normally the smallest of the three, which is why roll is the fastest of the rigid-body responses.",
        "range": "typically the smallest of the three",
        "options": None,
        "anchor": "cap-stability-vehicle",
    },
    "vehicle_Iy_kg_m2": {
        "title": "Pitch inertia",
        "definition": (
            "Moment of inertia about the lateral axis.\n\n"
            "It converts a pitching moment into a pitch acceleration. "
            "It is the inertia the hub arm acts through, because a hub "
            "force at a height above the center of gravity pitches the "
            "aircraft."),
        "unit": "kg·m²",
        "equation": r"A_{q,q}=\dfrac{1}{I_y}\dfrac{\partial M_x}{\partial q}",
        "effect": "Larger inertia slows the pitch mode and, with a nonzero hub arm, weakens the speed-to-pitch coupling that drives the classic long-period instability.",
        "range": "usually the largest of the three",
        "options": None,
        "anchor": "cap-stability-vehicle",
    },
    "vehicle_Iz_kg_m2": {
        "title": "Yaw inertia",
        "definition": (
            "Moment of inertia about the vertical axis.\n\n"
            "It converts a yawing moment into a yaw acceleration. With "
            "a single rotor and no tail it is the least constrained of "
            "the three, because nothing in this model restores yaw."),
        "unit": "kg·m²",
        "equation": r"A_{r,r}=\dfrac{1}{I_z}\dfrac{\partial Q}{\partial r}",
        "effect": "Affects the yaw row alone. The yaw response of a single rotor with no tail is not a flight-dynamics result: read it as a comparison between designs, not as an aircraft prediction.",
        "range": "between Ix and Iy for most layouts",
        "options": None,
        "anchor": "cap-stability-vehicle",
    },
    "hub_offset_x_m": {
        "title": "Hub ahead of the CG",
        "definition": (
            "Longitudinal distance from the center of gravity to the "
            "hub, positive forward.\n\n"
            "An arm is what makes a FORCE produce a moment. With no "
            "arm, a change in rotor force never reaches the rotational "
            "equations at all."),
        "unit": "m",
        "equation": r"A_{q,u}=\dfrac{1}{I_y}\left(\dfrac{\partial M_x}{\partial u}+z_h\dfrac{\partial H}{\partial u}\right)",
        "effect": "A zero arm is a MODELLING CHOICE, not a neutral default: it removes the term coupling thrust and drag changes into pitch and roll, which for a helicopter is most of the coupling there is.",
        "range": "small compared with the radius on most layouts",
        "options": None,
        "anchor": "cap-stability-vehicle",
    },
    "hub_offset_z_m": {
        "title": "Hub above the CG",
        "definition": (
            "Vertical distance from the center of gravity to the hub, "
            "positive up.\n\n"
            "It is the arm through which a rearward hub force pitches "
            "the aircraft, and the dominant one on a helicopter, where "
            "the rotor sits well above the mass it carries."),
        "unit": "m",
        "equation": r"M_{y}\;{+}{=}\;z_h\,H",
        "effect": "Raising the hub strengthens the speed-to-pitch coupling. It is the term behind the pitch-up a helicopter shows when it gains speed, and the one that makes the long-period mode unstable in hover.",
        "range": "of the order of one metre on a light helicopter",
        "options": None,
        "anchor": "cap-stability-vehicle",
    },
    "gravity_m_s2": {
        "title": "Gravitational acceleration",
        "definition": (
            "The value of g used in the attitude rows.\n\n"
            "Gravity does not enter the rotor derivatives at all. It "
            "enters the rigid-body model, where a change of attitude "
            "tilts the weight vector and therefore accelerates the "
            "vehicle."),
        "unit": "m/s²",
        "equation": r"\dot{u}\;{+}{=}\;-g\cos\theta_{trim}\,\theta",
        "effect": "It is what closes the loop between attitude and speed, and therefore what makes the long-period mode exist at all. Setting it to zero removes that coupling and the mode with it.",
        "range": "9.81 on Earth",
        "options": None,
        "anchor": "cap-stability-vehicle",
    },
    "n_blades": {
        "title": "Number of Blades",
        "definition": (
            "Count of identical blades on the rotor.\n\n"
            "More blades distribute aerodynamic load over more swept area, "
            "increasing solidity and often improving efficiency at low to "
            "moderate advance ratios."),
        "unit": "—",
        "equation": r"\sigma = \dfrac{B\,c(r)}{2\pi r}",
        "effect": "Increasing the blade count raises solidity and typically improves rotor efficiency but increases structural mass and hub complexity.",
        "range": "1–8 (typically 2–4)",
        "options": None
    },
    "radius_m": {
        "title": "Rotor Radius",
        "definition": (
            "Distance from the rotor axis to the blade tip, in meters.\n\n"
            "Defines the disk area and tip speed ΩR, which scale thrust, "
            "torque, and Reynolds/Mach numbers."),
        "unit": "m",
        "equation": r"A = \pi R^2",
        "effect": "Increasing radius grows disk area and thrust scale, but reduces tip speed for a given rpm and increases structural loads.",
        "range": "0.1–10 m",
        "options": None
    },
    "r_norm": {
        "title": "Normalized Radial Position",
        "definition": (
            "Radial station location r/R, ranging from 0 at the root to 1 at "
            "the tip.\n\n"
            "Careful: it must be monotonically increasing with no duplicates "
            "across the blade table."),
        "unit": "—",
        "equation": r"r = R\,\bar{r}",
        "effect": "Changing radial station positions redistributes the mesh resolution; stations clustered near root or tip concentrate analysis in that region.",
        "range": "0–1",
        "options": None
    },
    "chord_norm": {
        "title": "Normalized Chord",
        "definition": (
            "Blade chord c as a fraction of rotor radius c/R.\n\n"
            "Larger values increase blade solidity and profile drag at each "
            "station."),
        "unit": "—",
        "equation": r"\sigma(r) = \dfrac{B\,c(r)}{2\pi r}",
        "effect": "Increasing normalized chord raises solidity and local blade-element area, increasing drag, load, and rotor inertia per unit span.",
        "range": "0.01–0.3",
        "options": None
    },
    "twist_deg": {
        "title": "Geometric Twist",
        "definition": (
            "Airfoil pitch angle relative to the blade root reference frame, in "
            "degrees.\n\n"
            "Compensates for the radial variation of peripheral velocity Ωr, "
            "reducing induced angle of attack variation along the span."),
        "unit": "deg",
        "equation": r"\alpha = \alpha_{col} + \theta_{geo}(r)",
        "effect": "Increasing twist in the positive direction reduces angle of attack at the tip and increases it at the root, flattening the load distribution.",
        "range": "−45 to +45°",
        "options": None
    },
    "root_cutout_norm": {
        "title": "Root Cutout",
        "definition": (
            "Radial position r/R below which the blade is not integrated.\n\n"
            "The hub and root region physically cannot support aerodynamic "
            "loading and are excluded from BEM integration."),
        "unit": "—",
        "equation": r"\int_{r_{cutout}}^{R}",
        "effect": "Increasing the cutout radius removes more blade area from integration, reducing total thrust and power but often improving numerical stability near the singularity.",
        "range": "0–0.3",
        "options": None
    },
    "kind": {
        "title": "Chord Distribution Type",
        "definition": (
            "Shape of the chord distribution along the radius used by the "
            "radial table generator.\n\n"
            "- 'rectangular' keeps a single constant chord.\n"
            "- 'tapered' interpolates linearly between a root chord and a tip chord.\n"
            "- 'elliptic' follows an elliptic planform, which minimizes "
            "induced drag for a given lift in fixed-wing theory."),
        "unit": "—",
        "equation": (
            "rectangular: c(r)=c\\quad"
            "tapered: c(r)=c_{root}+(c_{tip}-c_{root})\\,\\bar r\\quad"
            "elliptic: c(r) \\propto \\sqrt{1-r^2}"),
        "effect": "Changes how chord (and therefore solidity) is distributed along the span. It does not by itself change total blade area.",
        "range": "rectangular, tapered, or elliptic",
        "options": {
            "rectangular": "Constant chord along the whole span: simplest to build, common on small rotors.",
            "tapered": "Linear interpolation between a root chord and a tip chord. It trades build simplicity for a spanwise load closer to elliptic.",
            "elliptic": "Chord follows an elliptic planform: it minimizes induced drag for a given lift, at the cost of a more complex blade to manufacture.",
        }
    },
    "n_stations": {
        "title": "Number of Stations",
        "definition": (
            "Number of radial stations generated between the root cutout "
            "and the tip when the radial table generator builds a new "
            "blade.\n\n"
            "Sets the resolution of the resulting table; it is independent "
            "of the solver's own spanwise mesh (config field "
            "<code>Ne</code>), which resamples this table at solve time."),
        "unit": "—",
        "equation": r"r_i = r_{cutout} + i\,\dfrac{1-r_{cutout}}{N_{stations}-1},\quad i=0,\dots,N_{stations}-1",
        "effect": "More stations describe the chord/twist distribution more finely on export/preview, but do not change solver accuracy, which depends on Ne instead.",
        "range": "3–200 (typically 15–40)",
        "options": None
    },
    "tip_chord_norm": {
        "title": "Tip Chord (Tapered)",
        "definition": (
            "Normalized chord c/R at the blade tip, used together with the "
            "root chord when the radial table generator's chord "
            "distribution type is 'tapered'.\n\n"
            "Linearly interpolated against the root chord across the "
            "generated stations."),
        "unit": "—",
        "equation": r"c(r) = c_{root} + (c_{tip}-c_{root})\,\bar r",
        "effect": "A smaller tip chord than root chord (taper ratio < 1) concentrates solidity inboard and typically reduces tip losses and blade weight.",
        "range": "0.001–2.0",
        "options": None
    },
    "twist_root_deg": {
        "title": "Root Twist",
        "definition": (
            "Geometric twist angle at the blade root, in degrees, used by "
            "the radial table generator.\n\n"
            "Linearly interpolated against the tip twist across the "
            "generated stations to produce the table's <code>twist_deg</code> "
            "column."),
        "unit": "deg",
        "equation": r"\theta_{geo}(r) = \theta_{root} + (\theta_{tip}-\theta_{root})\,\bar r",
        "effect": "A larger root twist raises the geometric angle of attack near the root relative to the tip, shifting load inboard.",
        "range": "−30 to +60°",
        "options": None
    },
    "twist_tip_deg": {
        "title": "Tip Twist",
        "definition": (
            "Geometric twist angle at the blade tip, in degrees, used by "
            "the radial table generator.\n\n"
            "Linearly interpolated against the root twist across the "
            "generated stations to produce the table's <code>twist_deg</code> "
            "column."),
        "unit": "deg",
        "equation": r"\theta_{geo}(r) = \theta_{root} + (\theta_{tip}-\theta_{root})\,\bar r",
        "effect": "A smaller tip twist than root twist (washout) reduces angle of attack at the tip, delaying tip stall and flattening the load distribution.",
        "range": "−30 to +60°",
        "options": None
    },
    "solidity": {
        "title": "Solidity",
        "definition": (
            "Blade area fraction of the rotor disk, shown by the radial "
            "table generator as a live alternate view of the chord fields "
            "above.\n\n"
            "Editing it rescales the chord field(s) to match the target "
            "solidity, keeping chord distribution shape and root cutout "
            "fixed."),
        "unit": "—",
        "equation": r"\sigma = \dfrac{N_b\,S_{blade}}{\pi R^2}",
        "effect": "Increasing solidity (via chord or blade count) raises total blade area and typically thrust and power at a given collective, up to stall limits.",
        "range": "0.02–0.3 (typically 0.05–0.12)",
        "options": None
    },
    "aspect_ratio": {
        "title": "Blade Aspect Ratio",
        "definition": (
            "Planform aspect ratio of a single blade, shown by the radial "
            "table generator as a live alternate view of the chord fields "
            "above.\n\n"
            "Editing it rescales the chord field(s) to match the target "
            "aspect ratio, keeping chord distribution shape and root "
            "cutout fixed."),
        "unit": "—",
        "equation": r"AR = \dfrac{R^2}{S_{blade}}",
        "effect": "A higher aspect ratio (narrower, longer blade for the same radius) reduces solidity and profile drag but increases structural and aeroelastic sensitivity.",
        "range": "5–25 (typically 10–20)",
        "options": None
    },
    "origin": {
        "title": "Geometry Origin",
        "definition": (
            "Metadata indicating how the blade geometry was created.\n\n"
            "Accepted values: 'preset' (built-in template), 'import' (loaded "
            "from file), or 'manual' (edited by user).\n\n"
            "Does not affect calculation."),
        "unit": "",
        "equation": r"\mathrm{origin} \in \{\mathrm{preset},\ \mathrm{import},\ \mathrm{manual}\}",
        "effect": "Does not affect calculation; used for traceability and UI display.",
        "range": "preset, import, or manual",
        "options": None
    },
    "origin_params": {
        "title": "Origin Parameters",
        "definition": (
            "Parameters used when the geometry was generated by a preset "
            "template, stored for traceability.\n\n"
            "Does not replace or override the radial table in calculation."),
        "unit": "",
        "equation": "geometry = f(origin, origin_params) before table materialization",
        "effect": "Does not affect calculation; serves only as a record of the parameters used to generate the original geometry.",
        "range": "preset-specific values; ignored by the solver",
        "options": None
    },
    "name": {
        "title": "Airfoil Name",
        "definition": (
            "Descriptive name or aerodynamic profile designation for the airfoil "
            "(for example, 'NACA 0012', 'SC1095', 'Clark Y').\n\n"
            "Used to identify the aerodynamic section across reports, polar plots, "
            "and project files. In multi-section rotor configurations, this name "
            "distinguishes each radial station's profile along the blade span."),
        "unit": "—",
        "equation": r"\mathrm{profile\ name} \in \{\mathrm{NACA\ 0012},\ \mathrm{SC1095},\ \dots\}",
        "effect": "Labels and organizes airfoil polars in plots, summaries, and generated reports. It does not directly alter numerical aerodynamics.",
        "range": "alphanumeric string (for example, 'NACA 0012', 'Clark Y', 'Root Section')",
        "options": None
    },
    "source": {
        "title": "Polar Source",
        "definition": (
            "Where the Cl(α) and Cd(α) polar curves originate.\n\n"
            "Determines whether aerodynamic coefficients come from an analytical "
            "formula, a precomputed table, or an external solver."),
        "unit": "",
        "equation": r"C_l,\ C_d = f(\alpha,\ Re,\ M)",
        "effect": "Changing the source alters how the blade element forces are computed at each radial station and flight condition.",
        "range": "analytical, table, neuralfoil, or xfoil",
        "options": {
            "analytical": "Polynomial analytical model with stall transition. Fast and smooth, and suitable for preliminary design.",
            "table": "Precomputed polar curves at fixed Reynolds and Mach slices. Accurate, but it requires data and interpolation.",
            "neuralfoil": "The NeuralFoil external solver generates the polar on demand. It gives high fidelity, runs slower than the analytical model, and it requires an external installation.",
            "xfoil": "The XFOIL binary generates the polar on demand, with transition settings of its own (Ncrit and the two Xtr stations). Its fidelity is higher than NeuralFoil's, but it needs the executable installed. zBEMT looks for it through ZBEMT_XFOIL_BIN, your remembered Locate… choice, PATH, and the standard install folders. Locate… remembers your pick between sessions. The check happens when Run is clicked."
        }
    },
    "cl_alpha": {
        "title": "Lift Slope",
        "definition": (
            "Rate of change of lift coefficient with angle of attack, in 1/rad, "
            "in the linear region before stall.\n\n"
            "The 2D thin-airfoil limit is 2π ≈ 6.28."),
        "unit": "1/rad",
        "equation": r"C_l = C_{l\alpha}(\alpha - \alpha_0)",
        "effect": "Increasing lift slope makes the airfoil more responsive to angle of attack, raising lift and the risk of stall separation.",
        "range": "3–7 (typically 5–6)",
        "options": None
    },
    "alpha0_deg": {
        "title": "Zero-Lift Angle",
        "definition": (
            "Angle of attack at which Cl = 0, in degrees.\n\n"
            "Represents airfoil camber; negative values indicate a reflex "
            "(cambered-back) airfoil."),
        "unit": "deg",
        "equation": r"C_l = 0 \quad \mathrm{at}\ \alpha = \alpha_0",
        "effect": "Increasing the zero-lift angle shifts the entire polar to higher angles, requiring more collective pitch to hover.",
        "range": "−5 to +5°",
        "options": None
    },
    "cd0": {
        "title": "Profile Drag at Zero Lift",
        "definition": (
            "Parasitic (zero-lift) drag coefficient, the drag present when "
            "Cl = 0.\n\n"
            "Represents viscous and pressure drag independent of lift."),
        "unit": "—",
        "equation": r"C_d = C_{d0} + k\,C_l^2",
        "effect": "Increasing profile drag raises torque and power consumption uniformly across all flight conditions.",
        "range": "0.005–0.02",
        "options": None
    },
    "k": {
        "title": "Drag-Lift Coupling",
        "definition": (
            "Curvature coefficient of the parabolic drag polar "
            "Cd = Cd0 + k·Cl².\n\n"
            "Defines how much induced and stall-related drag grows with "
            "lift."),
        "unit": "—",
        "equation": r"\Delta C_d = k\,C_l^2",
        "effect": "Increasing the coupling coefficient raises drag at high lift coefficients, increasing power in hover and reducing propeller efficiency.",
        "range": "0.01–0.08",
        "options": None
    },
    "stall_model": {
        "title": "Stall Model",
        "definition": (
            "Algorithm that extends the linear lift polar beyond the stall "
            "angles.\n\n"
            "Defines post-stall behavior and the transition from attached to "
            "separated flow."),
        "unit": "",
        "equation": r"C_l(\alpha):\ \mathrm{attached} \to \mathrm{post\!-\!stall}",
        "effect": "Choosing a different stall model changes how the polar behaves at high angles of attack and in reverse flow.",
        "range": "linear, clip, enhanced, or viterna",
        "options": {
            "linear": "Linear lift up to stall angle, then constant. The simplest model, useful for low-stall-margin designs.",
            "clip": "Linear to stall, then Cl drops to zero immediately. Unrealistic but diagnostic for stall sensitivity.",
            "enhanced": "Smooth transition from linear region through a peak Cl_max to a shallow post-stall decline. Realistic and continuous.",
            "viterna": "Viterna-Corrigan model with curvature. It extends to ±90° if enabled and is a physically grounded choice for high α and reverse flow."
        }
    },
    "alpha_stall_pos_deg": {
        "title": "Positive Stall Angle",
        "definition": (
            "Angle of attack where positive (upper-surface) stall begins, in "
            "degrees.\n\n"
            "Above this angle, the lift polar leaves the linear region."),
        "unit": "deg",
        "equation": r"\alpha_{stall,+}",
        "effect": "Increasing the stall angle raises the maximum lift coefficient and extends the linear region, improving performance at high pitch.",
        "range": "12–20° (typical airfoils)",
        "options": None
    },
    "alpha_stall_neg_deg": {
        "title": "Negative Stall Angle",
        "definition": (
            "Angle of attack where negative (lower-surface) stall begins, in "
            "degrees.\n\n"
            "Typically negative; bounds the linear region on the negative α "
            "side."),
        "unit": "deg",
        "equation": r"\alpha_{stall,-}",
        "effect": "Increasing the magnitude (making more negative) expands the linear range on the negative side, improving reverse-flow performance.",
        "range": "−20 to −12° (typical airfoils)",
        "options": None
    },
    "extend_full_range": {
        "title": "Extend to ±180° (Viterna-Corrigan)",
        "definition": (
            "Boolean flag enabling the Viterna-Corrigan extrapolation from the "
            "stall boundary through ±90° and the reflected branch to ±180°.\n\n"
            "It supplies a continuous aerodynamic closure when the base polar "
            "does not cover reverse flow."),
        "unit": "",
        "equation": r"[\alpha_{min},\alpha_{max}] \to \pm 180^\circ",
        "effect": "Enabling full-range extension expands the polar to extreme angles, enabling analysis in reverse flow and extreme maneuvers.",
        "range": "off/on; use when the base polar does not cover the envelope",
        "options": None
    },
    "viterna_blend_width_deg": {
        "title": "Viterna Blend Width",
        "definition": (
            "Angular width, in degrees, of the smooth transition zone between "
            "the original polar and the Viterna-Corrigan extrapolation.\n\n"
            "Ensures continuity."),
        "unit": "deg",
        "equation": r"\alpha_{stall} \pm \dfrac{w}{2}",
        "effect": "Increasing the blend width creates a smoother but less abrupt transition, reducing numerical stiffness in solvers.",
        "range": "5–20°",
        "options": None
    },
    "use_dynamic_stall": {
        "title": "Dynamic Stall Model",
        "definition": "Boolean flag enabling the Øye dynamic stall lag model, which delays the response of Cl and Cd to rapid angle-of-attack changes.",
        "unit": "—",
        "equation": r"\dfrac{df}{dt} = \dfrac{f_{\mathrm{st}}-f}{\tau},\quad \tau = \dfrac{A\,c}{2W}",
        "effect": (
            "Enable it when the blade sees a rapid cyclic &alpha; excursion through "
            "stall. It adds a boundary-layer separation lag to C<sub>l</sub> and "
            "C<sub>d</sub>.\n\n"
            "Careful: in this solver it is evaluated in the periodic "
            "frequency-domain post-processing stage, not as a time-marched "
            "aerodynamic state in the induction solve."),
        "range": "off/on",
        "options": None
    },
    "dynamic_stall_method": {
        "title": "Dynamic Stall Method",
        "definition": (
            "How the periodic separation response of the Øye model is "
            "solved.\n\n"
            "Frequency solves it algebraically through a Fourier transfer "
            "function with one lag constant per radial station: cheap, and "
            "the default.\n\n"
            "Time march steps the separation state explicitly from azimuth "
            "station to azimuth station over a number of revolutions, "
            "discards the start-up transient and averages the rest."),
        "unit": "—",
        "equation": r"\hat{f}_n = H_n\,\hat{f}_{\mathrm{st},n}, \quad H_n = \dfrac{1}{1 + i\,n\,\Omega\,\tau}",
        "effect": (
            "Frequency is the cheap answer for a steady operating point; the "
            "march reproduces the same periodic regime and reports how far "
            "the last two revolutions still differ (the periodic residual).\n\n"
            "Neither is a transient model: when the flight condition itself "
            "changes with time, use a maneuver (SC-12)."),
        "range": "frequency | time_march",
        "options": {
            "frequency": "Algebraic Fourier solve; Npsi-independent cost.",
            "time_march": "Explicit march over Npsi stations per revolution; cost grows with mesh and revolutions, and the result carries the periodic residual."
        }
    },
    "dynamic_stall_time_march_revolutions": {
        "title": "Revolutions Marched",
        "definition": (
            "How many rotor revolutions the time-march method steps through "
            "before averaging. The first revolutions carry the start-up "
            "transient of the separation state."),
        "unit": "—",
        "equation": r"N_{steps} = N_{\psi} \times N_{rev}",
        "effect": (
            "More revolutions push the transient further out of the average; "
            "the periodic residual reported with the result tells whether "
            "they were needed. Each revolution costs Npsi sequential steps."),
        "range": "1 to 100 (default 8)",
        "options": None
    },
    "dynamic_stall_time_march_avg_last": {
        "title": "Revolutions Averaged",
        "definition": (
            "How many of the last marched revolutions are averaged into the "
            "periodic answer of the time-march method."),
        "unit": "—",
        "equation": r"\bar{f} = \dfrac{1}{N_{avg}}\sum_{k=N_{rev}-N_{avg}+1}^{N_{rev}} f^{(k)}",
        "effect": (
            "Averaging more revolutions smooths residual transients but "
            "blurs real cycle-to-cycle variation; it must not exceed the "
            "revolutions marched."),
        "range": "1 to revolutions marched (default 3)",
        "options": None
    },
    "dynamic_stall_A": {
        "title": "Øye Lag Constant",
        "definition": (
            "Lag constant A of the Øye dynamic stall model, controlling the "
            "time scale of flow separation response.\n\n"
            "Larger values mean slower response."),
        "unit": "—",
        "equation": r"\tau = \dfrac{A\,c}{2W},\quad H_n = \dfrac{1}{1 + i\,n\,\Omega\,\tau}",
        "effect": "Increasing the lag constant slows the separation response, reducing peak stall loads but introducing more phase lag.",
        "range": "Typically 4–12 (default 8)",
        "options": None
    },
    "dynamic_stall_fade_start_deg": {
        "title": "Stall Fade Start Angle",
        "definition": (
            "Angle of attack, in degrees, where the Øye dynamic stall "
            "correction begins to be attenuated linearly.\n\n"
            "Beyond this, correction amplitude decreases."),
        "unit": "deg",
        "equation": r"\chi = 1 \quad (\alpha < \alpha_{\mathrm{fade,start}})",
        "effect": "Increasing the fade start angle extends the range over which dynamic stall effects are strong, affecting post-stall behavior.",
        "range": "20–35°",
        "options": None
    },
    "dynamic_stall_fade_end_deg": {
        "title": "Stall Fade End Angle",
        "definition": (
            "Angle of attack, in degrees, where the Øye dynamic stall "
            "correction attenuation ends and the model switches off.\n\n"
            "No correction beyond this angle."),
        "unit": "deg",
        "equation": r"\chi = 0 \quad (\alpha > \alpha_{\mathrm{fade,end}})",
        "effect": "Increasing the fade end angle extends dynamic stall effects to higher angles. Beyond it, the static polar is used directly.",
        "range": "40–90°",
        "options": None
    },
    # --- 2D profile outline (block "2D Profile Geometry") ---
    # These three fields had NO popup: the outline only appears in
    # NeuralFoil mode, and none of them had an entry here or anchor in
    # HTML, so the "?" never appeared on the line. Section 6.7 of the
    # documentation already described them -- the link was missing.
    "generator_params": {
        "title": "Analytic Family Parameters",
        "definition": (
            "The parameters of the analytic contour families that have no list "
            "of their own. PARSEC takes nine numbers (r_le, x_up, y_up, "
            "y_xx_up, x_lo, y_lo, y_xx_lo, th_te, beta_te_deg): the leading-edge "
            "radius, crest position, height and curvature of each surface, "
            "the trailing-edge thickness, and the trailing-edge angle in degrees. "
            "Joukowski takes two numbers: epsilon (thickness) and camber. "
            "Biconvex takes one number: the thickness t at mid-chord."),
        "unit": "-",
        "equation": (
            r"y(x) = \sum_{k=1}^{6} a_k\,x^{k-\frac{1}{2}} \quad \text{(PARSEC)},\quad "
            r"z = \zeta + \frac{1}{\zeta} \quad \text{(Joukowski)},\quad "
            r"y = \pm 2t\,x(1-x) \quad \text{(biconvex)}"),
        "effect": (
            "Each Source option reveals its row. Generate geometry rebuilds the "
            "contour from these numbers and stores them with it, so a saved "
            "section can be regenerated and edited again without the "
            "coordinates.\n\n"
            "Note: the contour reaches the engine only through the polar "
            "generated from it. Changing the numbers changes nothing until "
            "polar generation runs again."),
        "range": (
            "PARSEC: nine finite numbers (defaults 0.0158, 0.30, 0.0593, "
            "-0.475, 0.35, -0.047, 0.530, 0.0025, 8.0). Joukowski: epsilon and "
            "camber (defaults 0.08, 0.05). Biconvex: thickness (default 0.06; "
            "0 gives a slit)."),
        "options": None
    },
    "naca_code": {
        "title": "NACA Code",
        "definition": (
            "The 4- or 5-digit NACA designation of the section contour.\n\n"
            "In the 4-digit family the first digit is the maximum camber as a "
            "percentage of chord, the second its chordwise position in tenths, "
            "and the last two the maximum thickness as a percentage of chord "
            "(2412 = 2% camber at 40% chord, 12% thick).\n\n"
            "In the 5-digit family the first three digits encode design lift "
            "coefficient and camber position, the last two the thickness."),
        "unit": "—",
        "equation": r"y_t = 5t\left(0.2969\sqrt{x} - 0.126x - 0.3516x^2 + 0.2843x^3 - 0.1015x^4\right)",
        "effect": (
            "Camber shifts the zero-lift angle negative and raises Cl at a given "
            "angle. Thickness governs how gently the section stalls and how much "
            "profile drag it carries.\n\n"
            "Note: the contour reaches the engine only through the polar "
            "generated from it. Changing the code changes nothing until polar "
            "generation runs again."),
        "range": (
            "4 or 5 digits.\n\n"
            "Sections in common rotor use: 0009 (thin symmetric, high-speed tip), "
            "0012 (symmetric, the classic rotor blade), 0015 and 0018 (thicker "
            "symmetric, inboard/root), 23012 (cambered, tail rotors and "
            "propellers), 4412 (classic cambered)."),
        "options": None
    },
    "cst_upper": {
        "title": "CST Upper Surface",
        "definition": "Bernstein weights of the upper surface in the CST (class/shape transformation) description of the contour. Each weight raises or lowers the surface near one chordwise station.",
        "unit": "—",
        "equation": r"y(x) = x^{0.5}(1-x)\sum_{i=0}^{n} A_i\,\binom{n}{i}x^i(1-x)^{n-i}",
        "effect": (
            "The first weight governs the leading-edge radius and the last the "
            "trailing-edge angle.\n\n"
            "The field appears while 'cst' is the selected Source of the 2D "
            "profile geometry; press Generate geometry to rebuild the contour "
            "from it."),
        "range": "typically 0.1–0.3, one value per Bernstein term",
        "options": None
    },
    "cst_lower": {
        "title": "CST Lower Surface",
        "definition": "Bernstein weights of the lower surface, in the same convention as the upper set.",
        "unit": "—",
        "equation": r"t(x) = y_{upper}(x) - y_{lower}(x)",
        "effect": (
            "Negative values put the surface below the chord line; the gap "
            "between the two sets at a station is the local thickness and their "
            "mean is the camber.\n\n"
            "Same availability as the upper set: visible while Source is 'cst'."),
        "range": "typically −0.3 to 0.0, one value per Bernstein term",
        "options": None
    },
    "bezier_control_points": {
        "title": "Bézier Control Points",
        "definition": "Control polygon of the contour, one x,y pair per line, running from the trailing edge over the upper surface, around the leading edge and back along the lower surface.",
        "unit": "—",
        "equation": r"P(u) = \sum_{i=0}^{n}\binom{n}{i}(1-u)^{n-i}u^i\,P_i",
        "effect": (
            "The curve is pulled toward each point without passing through it, "
            "so points crowded near the nose sharpen the leading-edge radius.\n\n"
            "The editor appears while 'bezier' is the selected Source of the 2D "
            "profile geometry; press Generate geometry to rebuild the contour "
            "from it."),
        "range": "4+ points, x from 0 to 1",
        "options": None
    },
    "reverse_flow_model": {
        "title": "Reverse-Flow Polar",
        "definition": (
            "Method for extending the polar when local tangential velocity Ut is "
            "negative (reverse flow).\n\n"
            "Defines how Cl/Cd behave when the blade element moves backward."),
        "unit": "",
        "equation": r"U_T = \Omega r + V_x \sin\psi < 0",
        "effect": (
            "The five options differ in where they act. viterna_full_range and "
            "alpha_blending change the effective angle fed to the polar. "
            "flat_plate and simple_flip post-process Cl/Cd inside the reverse "
            "region. thin_plate_blend blends the polar with thin-plate "
            "theory as a smooth function of |α| with no switch at Ut = 0.\n\n"
            "All five change element forces, not just plots."),
        "range": "viterna_full_range, flat_plate, simple_flip, alpha_blending, thin_plate_blend",
        "options": {
            "viterna_full_range": (
                "No reverse branch at all: φ = atan2(Up, Ut) is already "
                "continuous through Ut = 0, and with a polar defined over ±180° "
                "the standard blade-element formulas generalize on their own. "
                "α_eff = α_geom wrapped into (−180°, 180°].\n\n"
                "The most physically grounded choice, and the only one that "
                "requires the full-range (Viterna-Corrigan) extension to be "
                "active."),
            "flat_plate": (
                "Inside the reverse region the section is treated as a flat "
                "plate: Cl = 0 and Cd = 1.9, with α_eff = −α_geom and the Mach "
                "number taken from |Ut|.\n\n"
                "It is an idealized treatment. It discards the airfoil's own polar where it "
                "applies."),
            "simple_flip": (
                "Mirrors the incidence in the reverse region (α_eff = −α_geom, "
                "Cd forced positive), keeping the airfoil polar.\n\n"
                "Fast, symmetric, and discontinuous at Ut = 0: a diagnostic "
                "approximation."),
            "alpha_blending": (
                "Fades the incidence to zero across the reverse-flow boundary: "
                "α_eff = α_geom·tanh(k·Ut/(Ω r)) for Ut < 0, with "
                "k = reverse_flow_blend_factor.\n\n"
                "Continuous in value at Ut = 0 (α_eff → 0 there) and it "
                "approaches simple_flip's mirrored branch deep inside the "
                "region; the polar itself is untouched."),
            "thin_plate_blend": (
                "Blends the airfoil polar with thin-plate theory "
                "(Cl = π·sin α·cos α, Cd = 2·sin²α) using a smoothstep weight on "
                "|α_geom| between thin_plate_blend_center_deg ± half the "
                "width.\n\n"
                "The only option with no np.where(Ut < 0) switch anywhere, which "
                "is exactly what makes it the friendliest to solver convergence "
                "at the reverse-flow boundary.")
        }
    },
    "reverse_flow_blend_factor": {
        "title": "Reverse-Flow Blend",
        "definition": (
            "Sharpness k of the incidence fade used by "
            "reverse_flow_model = 'alpha_blending' (and only by it).\n\n"
            "Inside the reverse region the effective angle is scaled by "
            "tanh(k·Ut/(Ω r)), which is 0 at the boundary and saturates at the "
            "mirrored branch deep inside it."),
        "unit": "—",
        "equation": r"\alpha_{eff} = \alpha_{geom}\,\tanh\!\left(\dfrac{k\,U_T}{\Omega r}\right),\quad U_T < 0",
        "effect": (
            "Increase k for a sharper (more simple_flip-like) branch transition. "
            "Decrease it to remove oscillations near Ut = 0. It smooths the "
            "numerical switch and does not move the reverse-flow boundary.\n\n"
            "Careful: it is ignored by the other four reverse-flow models."),
        "range": "0.1–50",
        "options": None
    },
    "thin_plate_blend_center_deg": {
        "title": "Thin-Plate Blend Center",
        "definition": "Angular center, in degrees, of the blend with the thin-plate (flat-plate) force model. Near this angle, the model transitions toward thin-plate forces.",
        "unit": "deg",
        "equation": r"\alpha_{center}",
        "effect": "Increasing the blend center moves the transition region to higher angles, preserving airfoil data at low to moderate angles.",
        "range": "60–90°",
        "options": None
    },
    "thin_plate_blend_width_deg": {
        "title": "Thin-Plate Blend Width",
        "definition": "Angular width, in degrees, of the blend zone with the thin-plate model. Wider zones give smoother transitions.",
        "unit": "deg",
        "equation": r"\alpha_{center} \pm \dfrac{w}{2}",
        "effect": "Increasing the blend width broadens the transition, reducing sharp discontinuities in forces at very high angles.",
        "range": "5–30°",
        "options": None
    },
    "mask_reverse_flow_plots": {
        "title": "Mask Reverse Flow in Plots",
        "definition": (
            "Boolean flag to mask (gray out) regions with Ut < 0 in disk load "
            "maps.\n\n"
            "Affects visualization only; forces and CSV output remain "
            "complete."),
        "unit": "",
        "equation": r"\mathrm{mask}: U_T \geq 0",
        "effect": (
            "Enable it when a disk map should emphasize the forward-flow "
            "region.\n\n"
            "It changes only rendering; reverse-flow loads remain in "
            "integration, summaries, CSV, and exported data."),
        "range": "off/on",
        "options": None
    },
    "use_compressibility": {
        "title": "Compressibility Correction",
        "definition": (
            "Boolean flag applying the Prandtl-Glauert compressibility "
            "correction 1/√(1−M²) to Cl and Cd.\n\n"
            "Accounts for transonic flow effects."),
        "unit": "",
        "equation": r"C_l' = \dfrac{C_l}{\sqrt{1-M^2}}",
        "effect": (
            "Enable it when local Mach is high enough that incompressible polars "
            "are no longer adequate.\n\n"
            "Careful: apply it only to a polar that is not already "
            "Mach-resolved. Otherwise the effect is double-counted.\n\n"
            "The correction is local to the airfoil coefficients and does not "
            "alter momentum theory."),
        "range": "off/on (use cautiously as M approaches 1)",
        "options": None
    },
    "a_sound": {
        "title": "Speed of Sound",
        "definition": (
            "Speed of sound in air, in m/s, used to compute local Mach number "
            "M = Utip / a_sound.\n\n"
            "Typical value 343 m/s (20°C sea level)."),
        "unit": "m/s",
        "equation": r"M = \dfrac{V}{a}",
        "effect": "Increasing sound speed lowers Mach numbers and reduces compressibility effects, effectively making the rotor 'slower' in compressibility terms.",
        "range": "320–350 m/s (temp dependent)",
        "options": None
    },
    "external_reynolds_list": {
        "title": "External Reynolds Numbers",
        "definition": (
            "List of Reynolds numbers (one per airfoil chord and local "
            "velocity) used to generate an external (NeuralFoil) polar.\n\n"
            "Defines the Re range of the sweep."),
        "unit": "—",
        "equation": r"Re = \dfrac{V c}{\nu}",
        "effect": "Increasing the Reynolds range expands the external polar coverage, improving accuracy in off-design conditions.",
        "range": "1e4–1e7 (typical rotors)",
        "options": None
    },
    "external_mach_list": {
        "title": "External Mach Numbers",
        "definition": (
            "List of Mach numbers used in the external polar sweep.\n\n"
            "Defines the compressible flow range generated by NeuralFoil."),
        "unit": "—",
        "equation": "M = V / a_sound",
        "effect": "Increasing the Mach range expands the external polar, enabling analysis of transonic and high-speed conditions.",
        "range": "0.1–0.9",
        "options": None
    },
    "external_alpha_min_deg": {
        "title": "External Polar Minimum Angle",
        "definition": "Smallest angle of attack, in degrees, of the angle-of-attack sweep that generates the external polar.",
        "unit": "deg",
        "equation": r"\alpha_{min}",
        "effect": "Decreasing the minimum angle expands the polar sweep range, but may increase computation time.",
        "range": "−180 to 0°",
        "options": None
    },
    "external_alpha_max_deg": {
        "title": "External Polar Maximum Angle",
        "definition": "Largest angle of attack, in degrees, of the angle-of-attack sweep that generates the external polar.",
        "unit": "deg",
        "equation": r"\alpha_{max}",
        "effect": "Increasing the maximum angle expands the polar sweep range and computation cost, but covers more extreme conditions.",
        "range": "0 to 180°",
        "options": None
    },
    "external_alpha_step_deg": {
        "title": "External Polar Angle Step",
        "definition": (
            "Angular step size, in degrees, between consecutive "
            "angle-of-attack points in the external sweep.\n\n"
            "Smaller steps give finer resolution."),
        "unit": "deg",
        "equation": r"\Delta\alpha",
        "effect": "Decreasing the step size increases polar resolution and computation time; finer steps reduce interpolation error.",
        "range": "0.5–5°",
        "options": None
    },
    "xfoil_ncrit": {
        "title": "XFOIL Ncrit",
        "definition": (
            "Critical amplification factor N of the e<sup>N</sup> transition "
            "criterion, used only by the XFOIL engine.\n\n"
            "The boundary layer turns turbulent where small disturbances inside "
            "it have grown by the factor e<sup>N</sup>. A lower N describes a "
            "flow with many disturbances and predicts earlier transition with "
            "higher drag. A higher N lets the layer stay laminar longer.\n\n"
            "NeuralFoil ignores this input."),
        "unit": "—",
        "equation": r"A(x) = e^{N}, \quad N = N_{crit}",
        "effect": (
            "Lowering Ncrit predicts earlier transition and a drag level nearer "
            "the fully turbulent one. Raising it extends laminar flow and lowers "
            "predicted skin friction.\n\n"
            "The value reaches only the XFOIL binary; other engines ignore it."),
        "range": "1–15 (default 9, a clean flow)",
        "options": None
    },
    "xfoil_xtr_top": {
        "title": "XFOIL Xtr Top",
        "definition": (
            "Chord fraction x/c where transition is forced on the upper "
            "surface, used only by the XFOIL engine.\n\n"
            "XFOIL fixes the laminar-to-turbulent transition at that station "
            "instead of predicting it. The default 1 leaves free transition on "
            "the whole surface.\n\n"
            "NeuralFoil ignores this input."),
        "unit": "x/c",
        "equation": r"x_{tr}/c \in (0,\ 1]",
        "effect": (
            "A value below 1 pins transition there, so everything downstream "
            "turns turbulent at once: drag rises toward the fully turbulent "
            "level. This models a trip strip or reproduces a measurement with "
            "fixed transition."),
        "range": "(0, 1] (default 1 = free transition)",
        "options": None
    },
    "xfoil_xtr_bot": {
        "title": "XFOIL Xtr Bottom",
        "definition": (
            "Chord fraction x/c where transition is forced on the lower "
            "surface, used only by the XFOIL engine.\n\n"
            "XFOIL fixes the laminar-to-turbulent transition at that station "
            "instead of predicting it. The default 1 leaves free transition on "
            "the whole surface.\n\n"
            "NeuralFoil ignores this input."),
        "unit": "x/c",
        "equation": r"x_{tr}/c \in (0,\ 1]",
        "effect": (
            "A value below 1 pins transition there, so everything downstream "
            "turns turbulent at once: drag rises toward the fully turbulent "
            "level. This models a trip strip or reproduces a measurement with "
            "fixed transition."),
        "range": "(0, 1] (default 1 = free transition)",
        "options": None
    },
    "table_slices": {
        "title": "Table Slices",
        "definition": (
            "List of Reynolds/Mach slices in a tabulated polar.\n\n"
            "Each slice is a complete Cl(α), Cd(α) curve at fixed Re and M. The "
            "solver interpolates between slices."),
        "unit": "",
        "equation": r"C_l(\alpha, Re, M)",
        "effect": "Does not affect calculation directly; determines the accuracy of interpolation between tabulated polar data.",
        "range": "one or more complete C<sub>l</sub>(&alpha;) curves per condition",
        "options": None
    },
    "geometry": {
        "title": "Airfoil Geometry",
        "definition": (
            "2D airfoil contour definition (NACA, CST, Bézier, and so on) used to "
            "generate an external (NeuralFoil) polar.\n\n"
            "Careful: it is metadata only if source is 'analytical' or "
            "'table'."),
        "unit": "",
        "equation": r"\bar{x}=x/c,\ \bar{y}=y/c",
        "effect": "Does not affect BEM calculation if source is 'analytical' or 'table'; used only for external polar generation.",
        "range": "NACA, CST, Bezier, or imported Selig/Lednicer coordinates",
        "options": None
    },
    "Ne": {
        "title": "Radial Stations",
        "definition": (
            "Number of radial blade stations in the mesh, from root cutout to "
            "tip.\n\n"
            "More stations resolve chord, twist, and loss distributions in "
            "finer detail."),
        "unit": "—",
        "equation": r"N_e",
        "effect": "Increasing radial stations improves resolution and convergence accuracy, but increases CPU time per case linearly.",
        "range": "10–200 (typical 30–90)",
        "options": None
    },
    "Npsi": {
        "title": "Azimuthal Positions",
        "definition": (
            "Number of azimuthal (circumferential) positions per "
            "revolution.\n\n"
            "Npsi=1 assumes axisymmetric flow; larger values resolve "
            "advancing/retreating blade asymmetry."),
        "unit": "—",
        "equation": r"\Delta\psi = \dfrac{360^\circ}{N_\psi}",
        "effect": "Increasing azimuthal positions better captures cyclic loads and forward-flight asymmetry, but multiplies CPU time.",
        "range": "1, 4, 6, 8, 12 (typical 1 or 8)",
        "options": None
    },
    "rho": {
        "title": "Air Density",
        "definition": (
            "Air density, in kg/m³. Scales all aerodynamic forces and power "
            "linearly.\n\n"
            "Typical sea-level value: 1.225 kg/m³."),
        "unit": "kg/m³",
        "equation": r"F \propto \rho V^2",
        "effect": "Increasing air density increases lift, drag, power, and Reynolds number; critical for high-altitude and sea-level comparisons.",
        "range": "0.4–1.5 kg/m³",
        "options": None
    },
    "integration_offset": {
        "title": "Integration Offset",
        "definition": (
            "Small numerical radial offset Δr at integration nodes to avoid "
            "singularities at root (r→0) and tip (r→R).\n\n"
            "Typical value 1e-6 of R."),
        "unit": "—",
        "equation": r"r \pm \Delta r",
        "effect": "Increasing the offset moves integration nodes away from singularities, reducing numerical noise but sacrificing accuracy at extremities.",
        "range": "1e-8–1e-4",
        "options": None
    },
    "inflow_field_model": {
        "title": "Inflow Field Model",
        "definition": (
            "Selects the induced-velocity model and its coupling mode.\n\n"
            "The choice controls whether the wake deficit is solved locally at "
            "each blade element, represented by steady disk harmonics, or "
            "represented by the finite-state Pitt-Peters model."),
        "unit": "",
        "equation": r"\lambda_i = \lambda_0\left[1 + K_x \bar{r}\cos\psi + K_y \bar{r}\sin\psi\right]",
        "effect": (
            "Use the local Glauert, Coleman, or Drees variants when azimuthal load "
            "feedback matters. Use Pitt-Peters for a finite-state disk "
            "response.\n\n"
            "Careful: use the unsteady variant only through the dedicated "
            "time-sequence API."),
        "range": (
            "glauert_local, coleman_local, drees_local, pitt_peters_steady "
            "(GUI)\n\n"
            "The global and unsteady values are compatibility and API cases"),
        "options": {
            "glauert_local": "Classical annular momentum coupling at each mesh node.",
            "coleman_local": "Coleman first harmonic for front/rear wake tilt, solved locally.",
            "drees_local": "Drees longitudinal and lateral harmonics, solved locally.",
            "pitt_peters_steady": "Three-state finite-state actuator-disk equilibrium; use when disk-level induced-flow physics is the target."
        }
    },
    "prandtl_loss_mode": {
        "title": "Prandtl Tip/Root Loss",
        "definition": (
            "Prandtl tip and root loss correction model.\n\n"
            "Applies a reduction factor to blade element loads near root and tip "
            "to account for finite blade count effects."),
        "unit": "",
        "equation": r"F_{tip} = \dfrac{2}{\pi}\arccos\left(e^{-\dfrac{N_b(1-\bar{r})}{2\,\bar{r}\,|\sin\phi|}}\right)",
        "effect": "Choose both for normal finite-blade predictions. Choose tip or root to isolate one physical loss mechanism. Choose off only for an idealized infinite-blade comparison.",
        "range": "off, tip, root, both",
        "options": {
            "off": "No Prandtl loss correction; full blade element loads are used.",
            "tip": "Apply loss at tip only.",
            "root": "Apply loss at root only.",
            "both": "Apply loss at both tip and root (recommended for accurate hover power)."
        }
    },
    "use_rotational_augmentation": {
        "title": 'Rotational augmentation (Himmelskamp / Snel)',
        "definition": (
            'Centrifugal and Coriolis pumping of the boundary layer on a '
            'rotating blade. Fluid inside a separated boundary layer is thrown '
            'outboard by centrifugal force and turned by Coriolis, which drains '
            'the separated region and delays stall.\n\n'
            'The effect is strongest near the root, where the chord is a large '
            'fraction of the radius, and vanishes at the tip.\n\n'
            'Careful: a 2D wind-tunnel polar cannot contain it. The section '
            'there does not rotate.'),
        "unit": '',
        "equation": r"C_l = C_{l,2D} + 3.1\,\dfrac{\lambda_r^2}{1+\lambda_r^2}\,g(\alpha)\left(\dfrac{c}{r}\right)^2\left(C_{l,att}-C_{l,2D}\right)",
        "effect": (
            'The correction pulls the measured lift back toward the ATTACHED '
            'value C<sub>l,att</sub> = C<sub>lα</sub>(α − α<sub>0</sub>), so it does nothing '
            'while the flow is attached and only bites once the polar has '
            'stalled.\n\n'
            'Its size scales with (c/r)&sup2; (doubling the chord at a station '
            'quadruples it), so it is a root-region effect that dies out toward '
            'the tip.\n\n'
            'Expect a higher inner loading and a modest rise in thrust and '
            'torque in cases where the root is stalled (hover at high '
            'collective, low-speed flight); in an unstalled case the change is '
            'near zero.\n\n'
            'The blend g(&alpha;) is 1 below 30&deg;, falls smoothly to 0 at '
            '60&deg;, and above that the correction is off.'),
        "range": 'off/on',
        "options": None
    },
    "use_radial_flow_correction": {
        "title": 'Radial (spanwise) flow correction',
        "definition": (
            "In forward flight the blade also sees a velocity component ALONG "
            "its span, U<sub>R</sub> = V<sub>x</sub>&middot;cos&psi;, built from the IN-PLANE component of "
            "the flight velocity, largest where the blade points along that "
            "component and zero fore and aft.\n\n"
            "In ROTOR mode that in-plane component is V<sub>x</sub>, the advance; in "
            "PROPELLER mode it is the cross-flow V<sub>z</sub>.\n\n"
            "The swept-wing independence principle says the section's lift is "
            "governed only by the flow NORMAL to the span, so lift keeps the "
            "pair (U<sub>p</sub>, U<sub>t</sub>) and the angle built from it. "
            "Drag does not follow that rule: it is a friction force on the "
            "boundary-layer scale, it lies along the TOTAL relative wind, and "
            "part of that wind runs along the blade.\n\n"
            "Written as a vector instead of a number, the drag splits in two: "
            "an in-plane part, which the &phi; resolution turns into thrust "
            "and torque as before, and a spanwise part, which has no arm about "
            "the shaft and so adds no torque at all, but does push the rotor "
            "backward."),
        "unit": '',
        "equation": (r"\vec{D} = \frac{1}{2}\rho c\,C_d\,|\vec{U}|\,\vec{U},"
                     r"\qquad |\vec{U}| = \sqrt{W^2 + U_R^2}"),
        "effect": (
            'It raises the H-force and the profile power and leaves thrust and '
            'induced power untouched. The spanwise part is reported on its own '
            'as C<sub>Hr</sub> in the results table, so what this box does is '
            'visible rather than inferred.\n\n'
            'For a constant drag coefficient the closed form gives its size: '
            'the profile H-force rises from &sigma;C<sub>d0</sub>μ/4 to '
            '3&sigma;C<sub>d0</sub>μ/8, half as much again, and the profile '
            'power from (1 + μ&sup2;) to (1 + 1.5&nbsp;μ&sup2;). Adding back '
            'the work the free stream does on the rotor makes the dissipated '
            'profile power (1 + 4.5&nbsp;μ&sup2;), which is the classical '
            '(1 + 4.65&nbsp;μ&sup2;) of the helicopter literature.\n\n'
            'In ROTOR mode it is identically zero in hover (V<sub>x</sub> = 0, so no '
            'spanwise component) and grows with the in-plane advance ratio '
            'μ<sub>x</sub>, varying once per revolution around the disc with its peaks '
            'fore and aft, where the blade lies along the free stream.\n\n'
            'In PROPELLER mode, in straight cruise, it is inactive: the '
            'in-plane component there is the cross-flow and that is zero.'),
        "range": 'off/on',
        "options": None
    },
    "radial_flow_max_skew_deg": {
        "title": 'Radial-flow saturation skew angle',
        "definition": (
            'A ceiling on the LOCAL yaw angle of the blade element, '
            '&lambda;<sub>y</sub> = arctan(U<sub>R</sub>/W): the angle between '
            'the total relative wind and the plane normal to the span.\n\n'
            'It decides the largest share of the section drag the model may '
            'send along the blade. It is not the wake skew angle; it is read '
            'element by element, from the same two velocities that build the '
            'drag vector.'),
        "unit": 'deg',
        "equation": (r"\lambda_y = \arctan\dfrac{U_R}{W},\qquad"
                     r"|U_R| \leq W \tan \lambda_{y,max}"),
        "effect": (
            'It matters where W collapses and the ratio would otherwise run '
            'away: near the blade root, and inside the reverse-flow region on '
            'the retreating side. Over the rest of the disc the local yaw '
            'angle is well below any sensible ceiling and the value changes '
            'nothing.\n\n'
            'Raising it lets more of the drag act along the span (a larger '
            'C<sub>Hr</sub>); lowering it caps that share earlier. It changes '
            'nothing in hover, where there is no spanwise flow at all.'),
        "range": '30-90 deg',
        "options": None
    },
    "pitt_peters_outer_iter": {
        "title": "Pitt-Peters Outer Iterations",
        "definition": "Maximum number of iterations of the outer loop that solves Pitt-Peters inflow states. Safety limit on state convergence iterations.",
        "unit": "—",
        "equation": r"n_{iter}",
        "effect": "Increasing the iteration limit allows the Pitt-Peters states more time to converge, improving accuracy at the cost of time.",
        "range": "5–50",
        "options": None
    },
    "pitt_peters_relax": {
        "title": "Pitt-Peters Relaxation",
        "definition": "Relaxation factor (0–1) applied when updating Pitt-Peters inflow states. Controls convergence speed and stability of the state update.",
        "unit": "—",
        "equation": r"\lambda_{n+1} = \lambda_n + \omega\left[g(\lambda_n)-\lambda_n\right]",
        "effect": "Decreasing the relaxation factor slows state update and improves stability, but may require more iterations.",
        "range": "0.1–1.0",
        "options": None
    },
    "pitt_peters_tol": {
        "title": "Pitt-Peters Tolerance",
        "definition": "Convergence tolerance for the Pitt-Peters outer loop, based on the maximum variation of inflow states between iterations.",
        "unit": "—",
        "equation": r"\max|\xi_{n+1}-\xi_n| < \epsilon",
        "effect": "Decreasing the tolerance forces stricter convergence, improving accuracy but increasing iteration count.",
        "range": "1e-6–1e-3",
        "options": None
    },
    "solver": {
        "title": "Solver Algorithm",
        "definition": (
            "Iterative algorithm that solves the fixed-point equation "
            "g(λ<sub>i</sub>)=λ<sub>i</sub> of the BEM coupling, where "
            "λ<sub>i</sub> = v_i/(ΩR) is the induced inflow along the shaft.\n\n"
            "Determines convergence rate and stability."),
        "unit": "",
        "equation": r"\lambda_{i,n+1} = g(\lambda_{i,n})",
        "effect": "Changing solver algorithms alters convergence speed, robustness in stalled conditions, and sensitivity to initial guesses.",
        "range": "fixed_point, newton, bisection, aitken",
        "options": {
            "newton": "Newton-Raphson with numerical Jacobian. Fastest for smooth, convergent cases.",
            "fixed_point": "Fixed-point iteration (Picard). Slow but robust and useful for stalled or difficult cases.",
            "bisection": "Bracketing method. It expands from the physical initial estimate and converges to the nearest bracketed root. It is the slowest method.",
            "aitken": "Aitken acceleration of fixed-point. It attempts to speed up slow fixed-point convergence."
        }
    },
    "max_iter": {
        "title": "Max Solver Iterations",
        "definition": (
            "Maximum number of solver iterations per mesh element before "
            "declaring divergence.\n\n"
            "Upper safety limit on iteration count."),
        "unit": "—",
        "equation": r"n_{max}",
        "effect": "Increasing the limit allows more iterations to find convergence, helping difficult cases but masking poor initialization.",
        "range": "10–1000 (typically 50–200)",
        "options": None
    },
    "tol": {
        "title": "Solver Tolerance",
        "definition": (
            "Residual tolerance on |g(λ<sub>i</sub>)−λ<sub>i</sub>| to declare an element "
            "converged.\n\n"
            "Tighter tolerances require more iterations."),
        "unit": "—",
        "equation": r"|g(\lambda_i)-\lambda_i| < \epsilon",
        "effect": "Decreasing the tolerance tightens convergence criteria, improving force accuracy but increasing CPU time.",
        "range": "1e-6–1e-2",
        "options": None
    },
    "relax": {
        "title": "Global Relaxation Factor",
        "definition": (
            "Global relaxation factor ω applied to the induced-inflow update: "
            "λ<sub>i,new</sub> = λ<sub>i,old</sub> + ω·Δλ<sub>i</sub>.\n\n"
            "It typically falls between 0 and 1. It stabilizes oscillatory convergence."),
        "unit": "—",
        "equation": r"\lambda_{i,n+1} = \lambda_{i,n} + \omega\left[g(\lambda_{i,n})-\lambda_{i,n}\right]",
        "effect": "Decreasing the relaxation factor slows convergence but improves stability. Too low a value causes stagnation.",
        "range": "0.1–1.0 (typically 0.5–0.9)",
        "options": None
    },
    "relax_schedule": {
        "title": "Spatial Relaxation Schedule",
        "definition": "Boolean flag activating a spatial relaxation schedule that reduces relaxation near root, tip, and problem azimuths where convergence is hardest.",
        "unit": "",
        "equation": r"\omega(r,\psi) = \omega_0\,f_{root}\,f_{tip}\,f_{\psi}",
        "effect": "Enabling the schedule adapts relaxation locally, improving convergence in stalled or highly loaded regions.",
        "range": "off/on (default on)",
        "options": None
    },
    "relax_root_factor": {
        "title": "Root Relaxation Factor",
        "definition": (
            "Additional relaxation factor applied in the root region "
            "(r/R < relax_root_threshold).\n\n"
            "Multiplicative with global relax."),
        "unit": "—",
        "equation": r"\omega_{root} = \omega_0\,f_{root}",
        "effect": "Decreasing the root factor further slows update near the root, improving stability in the high-loaded inboard region.",
        "range": "0.1–1.0",
        "options": None
    },
    "relax_root_threshold": {
        "title": "Root Region Threshold",
        "definition": (
            "Radial limit r/R below which the root relaxation factor is "
            "applied.\n\n"
            "Defines the inboard region receiving root relaxation."),
        "unit": "—",
        "equation": r"\bar{r} < \bar{r}_{root}",
        "effect": "Increasing the threshold expands the root region and the relaxation reduction applied there.",
        "range": "0.1–0.4",
        "options": None
    },
    "relax_tip_threshold": {
        "title": "Tip Region Threshold",
        "definition": (
            "Radial limit r/R above which the tip relaxation schedule is "
            "applied.\n\n"
            "Defines the outboard region receiving tip relaxation."),
        "unit": "—",
        "equation": r"\bar{r} > \bar{r}_{tip}",
        "effect": "Decreasing the threshold expands the tip region and the relaxation reduction applied there.",
        "range": "0.8–0.95",
        "options": None
    },
    "relax_azimuth_factor": {
        "title": "Azimuthal Relaxation Factor",
        "definition": (
            "Additional relaxation factor applied at azimuths near the "
            "reverse-flow boundary where flow becomes complex.\n\n"
            "Multiplicative with global relax."),
        "unit": "—",
        "equation": r"\omega_\psi = \omega_0\,f_\psi",
        "effect": "Decreasing the azimuth factor slows update at problem azimuths, stabilizing convergence in highly skewed inflow.",
        "range": "0.1–1.0",
        "options": None
    },
    "relax_azimuth_threshold": {
        "title": "Azimuthal Relaxation Threshold",
        "definition": "Threshold (0–1) that activates the azimuthal relaxation factor when a criterion (for example, reverse-flow proximity) is met.",
        "unit": "—",
        "equation": r"f_\psi \ \mathrm{applied\ when}\ c > c_{thr}",
        "effect": "Increasing the threshold restricts azimuthal relaxation to fewer azimuths, localizing the slowdown.",
        "range": "0.1–0.9",
        "options": None
    },
    "early_exit_fraction": {
        "title": "Early Exit Fraction",
        "definition": "Fraction (0–1) of mesh elements that must have converged to allow the solver to exit early before max_iter.",
        "unit": "—",
        "equation": r"\dfrac{n_{conv}}{N_e} > \eta",
        "effect": "Increasing the fraction requires more elements converged before exit, improving accuracy but increasing iteration count.",
        "range": "0.5–0.95",
        "options": None
    },
    "stagnation_patience": {
        "title": "Stagnation Patience",
        "definition": "Number of solver iterations allowed without improvement in the converged fraction before the solver declares stagnation and exits.",
        "unit": "—",
        "equation": "Stagnation counter increments if frac_improvement < min_frac",
        "effect": "Increasing patience allows more non-improving iterations, giving slow-converging cases more time but risking false stagnation.",
        "range": "3–20",
        "options": None
    },
    "stagnation_min_frac": {
        "title": "Stagnation Minimum Fraction",
        "definition": "Minimum improvement in converged fraction per iteration (as a fraction of total elements) to reset the stagnation counter.",
        "unit": "—",
        "equation": r"\Delta\eta = \dfrac{\eta_n - \eta_{n-1}}{N_e}",
        "effect": "Increasing the threshold requires larger improvements to reset patience, causing stagnation detection to trigger sooner.",
        "range": "0.001–0.1",
        "options": None
    },
    "is_propeller": {
        "title": "Rotor/Propeller Mode",
        "definition": (
            "Boolean switch between Rotor mode (helicopter, wind turbine) and "
            "Propeller mode (airplane, UAV).\n\n"
            "The axes are vehicle-fixed (x horizontal, z vertical), so the "
            "switch decides which physical direction each letter names: the "
            "shaft is vertical on a rotor and horizontal on a propeller.\n\n"
            "It also changes the performance coefficients and the reported "
            "angle."),
        "unit": "",
        "equation": "",
        "effect": (
            "Switching modes rotates the axes, so the same displayed names "
            "change meaning.\n\n"
            "μ<sub>x</sub> = V<sub>x</sub>/(ΩR) and J<sub>x</sub> = V<sub>x</sub>/(nD) = π·μ<sub>x</sub> are the IN-PLANE "
            "advance ratio on a rotor and the ALONG-SHAFT airspeed ratio on a "
            "propeller. The ratios μ<sub>z</sub>, J<sub>z</sub> and λ<sub>z</sub> instead name the along-shaft "
            "climb/descent on a rotor and the vertical cross-flow on a "
            "propeller.\n\n"
            "It also switches the reported angle (α<sub>rotor</sub>, from the disk "
            "plane, vs. α<sub>disk</sub>, from the shaft) and the performance metric "
            "(FM vs. η_prop), altering optimization goals."),
        "range": "",
        "options": {
            True: (
                "In PROPELLER mode the shaft is HORIZONTAL, so x runs along it "
                "and z is vertical.\n\n"
                "The airspeed is the along-shaft component V<sub>x</sub>, and "
                "J<sub>x</sub> = V<sub>x</sub>/(n·D) = π·μ<sub>x</sub> is the classic propeller advance "
                "ratio, the one propulsive efficiency uses. λ<sub>x</sub> is the "
                "same number in the inflow vocabulary.\n\n"
                "The in-plane component becomes the vertical CROSS-FLOW V<sub>z</sub> "
                "(μ<sub>z</sub>, J<sub>z</sub>), which is zero in straight cruise.\n\n"
                "The angle shown is α<sub>disk</sub>, measured from the SHAFT (0° in "
                "straight cruise, positive with the disk tilted nose-up).\n\n"
                "Inflow closes as λ<sub>total</sub> = λ<sub>i</sub> + λ<sub>x</sub>, that is, "
                "V<sub>x,total</sub> = V<sub>x</sub> + v_i through the disk. Reported with η_prop "
                "and the axis-thrust convention."),
            False: (
                "In ROTOR mode the shaft is VERTICAL, so x lies in the disk "
                "plane and z along the shaft.\n\n"
                "The advance ratio is the in-plane μ<sub>x</sub> = V<sub>x</sub>/(ΩR) "
                "(equivalently J<sub>x</sub> = V<sub>x</sub>/(n·D) = π·μ<sub>x</sub>, or λ<sub>x</sub>), and the "
                "along-shaft component V<sub>z</sub> is climb (positive) or descent "
                "(negative), written μ<sub>z</sub>, J<sub>z</sub> or λ<sub>z</sub>.\n\n"
                "The angle shown is α<sub>rotor</sub>, measured from the DISK PLANE "
                "(0° in level forward flight, positive when the flow arrives "
                "from below).\n\n"
                "Inflow closes as λ<sub>total</sub> = λ<sub>i</sub> + λ<sub>z</sub>, that is, "
                "V<sub>z,total</sub> = V<sub>z</sub> + v_i through the disk. Reported with "
                "figure-of-merit FM and the disk-thrust convention.")
        }
    },
    "mu_x": {
        "title": "In-plane component (V<sub>x</sub> advance in rotor mode, V<sub>z</sub> cross-flow in propeller mode)",
        "definition": (
            "The component of the flight velocity that lies IN THE PLANE of the disk. It is "
            "the one that varies with azimuth, so it is what makes the advancing and "
            "retreating sides of the disk see different speeds.\n\n"
            "IN ROTOR MODE the shaft is vertical, so the in-plane direction is the HORIZONTAL "
            "one and this is V<sub>x</sub>, the advance: μ<sub>x</sub> = V<sub>x</sub>/(ΩR), with μ<sub>x</sub> = 0 hover and "
            "μ<sub>x</sub> ≈ 0.3 helicopter cruise.\n\n"
            "Accepted there as μ<sub>x</sub>, as J<sub>x</sub> = V<sub>x</sub>/(nD) = π·μ<sub>x</sub>, or as the "
            "dimensional speed V<sub>x</sub> [m/s]. λ<sub>x</sub> is the same number in the inflow "
            "vocabulary.\n\n"
            "IN PROPELLER MODE the shaft is horizontal, so the in-plane direction is the "
            "VERTICAL one and this same component is the CROSS-FLOW V<sub>z</sub>, written μ<sub>z</sub> = "
            "V<sub>z</sub>/(ΩR) or J<sub>z</sub> = V<sub>z</sub>/(nD) = π·μ<sub>z</sub>.\n\n"
            "Careful: it is ZERO in straight cruise (the airspeed "
            "goes in the along-shaft field), and J<sub>z</sub> is NOT the propeller advance ratio, which "
            "is J<sub>x</sub>.\n\n"
            "In propeller mode the field also accepts α<sub>disk</sub>, the angle between the free stream "
            "and the SHAFT (0° in straight cruise, positive with the disk tilted nose-up), "
            "from which the cross-flow comes out as V<sub>z</sub> = tan(α<sub>disk</sub>)·V<sub>x</sub>."),
        "unit": "—",
        "equation": r"\mu_x = \dfrac{V_x}{\Omega R}\ \ \mathrm{(rotor)},\qquad \mu_z = \dfrac{V_z}{\Omega R}\ \ \mathrm{(propeller)}",
        "effect": (
            "Increasing the in-plane component raises the advancing-side "
            "velocity and lowers the retreating-side one, so the disk loading "
            "becomes asymmetric and reverse flow appears near the root on the "
            "retreating side.\n\n"
            "In ROTOR mode that is the whole story of forward flight.\n\n"
            "In PROPELLER mode it is the cross-flow of a yawed or climbing "
            "installation, and it stays at zero in straight cruise."),
        "range": (
            "0–1.5\n\n"
            "In ROTOR mode, cruise μ<sub>x</sub> 0–0.5. In PROPELLER mode the cross-flow "
            "μ<sub>z</sub> is usually 0."),
        "options": None
    },
    "Vz": {
        "title": "Along-shaft component (V<sub>z</sub> climb/descent in rotor mode, V<sub>x</sub> airspeed in propeller mode)",
        "definition": (
            "The component of the flight velocity ALONG THE SHAFT, in m/s. It is uniform "
            "over the disk (it does not vary with azimuth) and it adds directly to the "
            "inflow.\n\n"
            "IN ROTOR MODE the shaft is vertical, so this is the VERTICAL component V<sub>z</sub>: "
            "climb (positive) or descent (negative).\n\n"
            "Written λ<sub>z</sub> = V<sub>z</sub>/(ΩR) in the "
            "inflow vocabulary, μ<sub>z</sub> = V<sub>z</sub>/(ΩR) in the advance-ratio one (the same number), "
            "or J<sub>z</sub> = V<sub>z</sub>/(nD) = π·μ<sub>z</sub>.\n\n"
            "In rotor mode the field also accepts α<sub>rotor</sub> = atan2(V<sub>z</sub>, V<sub>x</sub>), "
            "the angle measured FROM THE DISK PLANE: 0 in level forward flight, positive "
            "when the flow arrives from below the disk.\n\n"
            "IN PROPELLER MODE the shaft is horizontal, so this is the HORIZONTAL component "
            "V<sub>x</sub>: the AIRSPEED, and the whole flight velocity in straight cruise.\n\n"
            "It is then "
            "written as the classic propeller advance ratio J<sub>x</sub> = V<sub>x</sub>/(n·D) = π·μ<sub>x</sub>, which "
            "is the field's default unit and the one propulsive efficiency uses, since thrust "
            "acts along the shaft; λ<sub>x</sub> is the same number in the inflow vocabulary.\n\n"
            "Careful: no "
            "angle is offered here in propeller mode. An angle only splits a known component "
            "into the other one, and the cross-flow V<sub>z</sub> = tan(α<sub>disk</sub>)·V<sub>x</sub> is 0 in every "
            "straight axial flight."),
        "unit": "m/s",
        "equation": r"\lambda_z = \dfrac{V_z}{\Omega R}\ \ \mathrm{(rotor)},\qquad J_x = \dfrac{V_x}{n D} = \pi\,\dfrac{V_x}{\Omega R}\ \ \mathrm{(propeller)}",
        "effect": (
            "Increasing the along-shaft component adds to the inflow through the "
            "disk, which lowers the local angle of attack of every section: "
            "thrust and torque fall at fixed collective.\n\n"
            "In ROTOR mode the inflow closes as "
            "λ<sub>total</sub> = λ<sub>i</sub> + λ<sub>z</sub> (V<sub>z,total</sub> = V<sub>z</sub> + v_i).\n\n"
            "In PROPELLER mode it closes as λ<sub>i</sub> + λ<sub>x</sub> "
            "(V<sub>x,total</sub> = V<sub>x</sub> + v_i), so the propeller unloads as it speeds "
            "up."),
        "range": (
            "In ROTOR mode, −50 to +50 m/s of climb/descent V<sub>z</sub>.\n\n"
            "In PROPELLER mode, the cruise airspeed V<sub>x</sub>, giving "
            "J<sub>x</sub> ≈ 0.2–2."),
        "options": None
    },
    "collective_deg": {
        "title": "Collective Pitch",
        "definition": (
            "Collective pitch angle, in degrees, applied uniformly across the "
            "blade span and added to the geometric twist.\n\n"
            "Together with the inflow it fixes the section angle of attack "
            "α<sub>eff</sub> at every radius and azimuth.\n\n"
            "Careful: α<sub>eff</sub> is not α<sub>rotor</sub> or α<sub>disk</sub>. Those two "
            "describe how the free stream meets the whole disk, while α<sub>eff</sub> "
            "varies with radius and azimuth."),
        "unit": "deg",
        "equation": r"\alpha_{eff} = \alpha_{col} + \theta(r) - \phi",
        "effect": (
            "Increasing collective pitch raises α<sub>eff</sub> and thrust in either "
            "mode, increasing power consumption and stall risk.\n\n"
            "The along-shaft component works the other way (V<sub>z</sub> in ROTOR mode, "
            "V<sub>x</sub> in PROPELLER mode), so a propeller needs more collective as "
            "J<sub>x</sub> grows if it is to hold its loading."),
        "range": "−20 to +20° (typical −5 to +15)",
        "options": None
    },
    "rpm": {
        "title": "Rotor Speed",
        "definition": (
            "Rotor rotational speed, in revolutions per minute. Defines "
            "Ω = 2π·rpm/60, the tip speed ΩR, and the local Reynolds/Mach at "
            "each station.\n\n"
            "Every non-dimensional flight-condition quantity is built from it: "
            "μ<sub>x</sub> = V<sub>x</sub>/(ΩR), μ<sub>z</sub> = V<sub>z</sub>/(ΩR), and the propeller forms "
            "J<sub>x</sub> = V<sub>x</sub>/(nD) = π·μ<sub>x</sub> and J<sub>z</sub> = V<sub>z</sub>/(nD) = π·μ<sub>z</sub>, with "
            "n = rpm/60."),
        "unit": "rpm",
        "equation": r"\Omega = \dfrac{2\pi\,\mathrm{rpm}}{60},\qquad n = \dfrac{\mathrm{rpm}}{60}",
        "effect": (
            "Increasing rpm raises tip speed, Reynolds number, Mach number, and "
            "thrust/power (scaling as rpm² for some coefficients).\n\n"
            "Careful: it also lowers every advance ratio (μ<sub>x</sub>, μ<sub>z</sub>, J<sub>x</sub>, J<sub>z</sub>) "
            "at a fixed flight speed, so a condition entered in m/s slides along "
            "the sweep whenever rpm changes."),
        "range": "100–3000 rpm (highly design dependent)",
        "options": None
    },
    # --- blade dynamics (SC-11) ------------------------------------------
    "flap_model": {
        "title": "Flap Model",
        "definition": (
            "How much rigid-body flap freedom the blade has.\n\n"
            "Rigid keeps the plain disk of every project saved before this "
            "model existed. Hinge offset pins the blade on an offset hinge; "
            "Root spring restrains a hinge at the shaft with a spring; "
            "Offset and spring combines both. The response is periodic in "
            "azimuth and quasi-steady: each revolution repeats the previous "
            "one, and there is no transient."),
        "unit": "—",
        "equation": r"\ddot\beta + \nu_\beta^{2}\,\beta = M_\beta(\psi)/(I_\beta\Omega^{2})",
        "effect": (
            "With any freedom other than Rigid the blade answers loading "
            "with motion: a coning angle appears in hover, the disk tilts in "
            "edgewise flight, and part of the load reaches the hub as a "
            "structural moment through the hinge or the spring."),
        "range": "rigid, offset, spring, offset_spring",
        "options": {
            "rigid": "No flap freedom at all: the behavior of every earlier project.",
            "offset": "Blade on an offset flap hinge; needs a positive inertia.",
            "spring": "Hinge at the shaft with a root spring K.",
            "offset_spring": "Offset hinge and root spring together.",
        }
    },
    "hinge_offset_norm": {
        "title": "Effective Hinge Offset",
        "definition": (
            "EFFECTIVE (equivalent, or virtual) offset of the flap and lag "
            "hinge from the shaft, as a fraction of the radius.\n\n"
            "It is not required to be a real mechanical hinge. The blade is "
            "treated as rigid, and this one number carries the whole root "
            "restraint: on an articulated rotor it is the geometric distance "
            "to the physical hinge, while on a hingeless or bearingless rotor "
            "it is the offset a rigid blade would need for its flap frequency "
            "to match that of the real flexure. Choose it to reproduce the "
            "measured ν<sub>β</sub>, not by measuring the hub.\n\n"
            "It stiffens the flap mode and opens the structural path that "
            "carries part of the blade load into the hub as a moment."),
        "unit": "r/R",
        "equation": r"\nu_\beta^{2} = 1 + \frac{3}{2}\,\dfrac{e}{1-e} + \dfrac{K_\beta}{I_\beta\Omega^{2}}",
        "effect": (
            "Increasing the offset raises the flap frequency ratio away from "
            "1, which moves the response off resonance and grows the hub "
            "moment proportional to (ν²−1)."),
        "range": "0 to 0.3 (articulated rotors 0.03–0.08)",
        "options": None
    },
    "flap_spring_nm_per_rad": {
        "title": "Flap Spring",
        "definition": (
            "Stiffness of a spring restraining the flap hinge, in newton "
            "metres per radian."),
        "unit": "N·m/rad",
        "equation": r"+\,\dfrac{K_\beta}{I_\beta\Omega^{2}} \text{ in } \nu_\beta^{2}",
        "effect": (
            "Adds restoring stiffness without moving the hinge: a soft "
            "spring already moves the first flap mode away from the "
            "resonance at ν = 1."),
        "range": "0 to 1e9 N·m/rad",
        "options": None
    },
    "inertia_source": {
        "title": "Inertia Source",
        "definition": (
            "Where the flap inertia I comes from: converted back from a "
            "Lock number with the airfoil's lift-curve slope and the chord "
            "at r/R = 0.75, given directly, or estimated from a uniform "
            "blade mass over the flapping part of the blade."),
        "unit": "—",
        "equation": r"I_\beta=\rho a c_{ref}R^{4}/\gamma \;\;\|\;\; m_b(R-eR)^{2}/3",
        "effect": (
            "The inertia normalizes the flap equation: light blades (large "
            "Lock number) respond more strongly to the same aerodynamic "
            "moment."),
        "range": "lock, inertia, blade_mass",
        "options": {
            "lock": "Convert from the Lock number (typical rotors 5–12).",
            "inertia": "Give the value directly, in kg·m².",
            "blade_mass": "Estimate from one blade's mass in kg.",
        }
    },
    "lock_number": {
        "title": "Lock Number",
        "definition": (
            "Ratio between aerodynamic and inertial response of the blade, "
            "built from the chord at r/R = 0.75."),
        "unit": "-",
        "equation": r"\gamma = \rho\,a\,c_{ref}\,R^{4}/I_\beta",
        "effect": (
            "Larger γ means air forces move the blade more: bigger coning, "
            "stronger 1/rev response, and more aerodynamic damping "
            "(γ/8 for a hinge at the shaft, growing with the offset)."),
        "range": "1 to 20 (most rotors 5–12)",
        "options": None
    },
    "flap_inertia_kg_m2": {
        "title": "Flap Inertia",
        "definition": (
            "Inertia of one blade about its flap hinge, used directly when "
            "the inertia source is the value itself."),
        "unit": "kg·m²",
        "equation": r"\ddot\beta + \nu_\beta^{2}\beta = M_\beta/(I_\beta\Omega^{2})",
        "effect": (
            "Smaller inertia amplifies the response to the same moment and "
            "raises the resonance risk when the spring term is small."),
        "range": "1e-6 to 1e6 kg·m²",
        "options": None
    },
    "blade_mass_kg": {
        "title": "Blade Mass",
        "definition": (
            "Mass of one blade, treated as uniform over the flapping part, "
            "when the inertia source is the blade mass."),
        "unit": "kg",
        "equation": r"I_\beta = m_b\,(R-eR)^{2}/3",
        "effect": (
            "Heavier blades mean larger inertia and a calmer response for "
            "the same aerodynamics."),
        "range": "0.001 to 10000 kg",
        "options": None
    },
    "pitch_flap_coupling_deg": {
        "title": "Pitch-Flap Coupling (delta-3)",
        "definition": (
            "Kinematic coupling between flap and pitch: a blade flapped up "
            "by β loses tan(δ₃)·β of local pitch."),
        "unit": "deg",
        "equation": r"\theta_{eff} = \theta - \tan(\delta_3)\,\beta",
        "effect": (
            "Positive values add aerodynamic damping and stabilize the flap "
            "response; large values reduce the response to cyclic pitch."),
        "range": "−60° to +60°",
        "options": None
    },
    "harmonics": {
        "title": "Harmonic Count",
        "definition": (
            "Number of harmonics kept in the Fourier balance of the flap "
            "(and lag) response."),
        "unit": "-",
        "equation": r"\beta(\psi)=\beta_0+\sum_{n=1}^{N_h}\left[\beta_{nc}\cos n\psi+\beta_{ns}\sin n\psi\right]",
        "effect": (
            "Two harmonics describe most rotors. Each extra harmonic costs "
            "one solve per outer iteration and must stay below the "
            "resonance guard."),
        "range": "1 to 5",
        "options": None
    },
    "outer_max_iter": {
        "title": "Outer Iterations",
        "definition": (
            "Maximum exchanges between the inflow solution and the blade "
            "motion before the solver gives up and reports the residual."),
        "unit": "-",
        "equation": None,
        "effect": (
            "The flapped solution feeds back into the loads, so the two "
            "must agree; raise this if the reported residual has not met "
            "the tolerance."),
        "range": "5 to 200",
        "options": None
    },
    "outer_tol_deg": {
        "title": "Outer Tolerance",
        "definition": (
            "Convergence tolerance of the outer loop, measured as the "
            "largest coefficient change in degrees."),
        "unit": "deg",
        "equation": None,
        "effect": (
            "Tighter tolerances cost more iterations. Solver noise puts a "
            "floor around 0.001 degrees; going below it wastes time."),
        "range": "1e-8 to 1e-1 deg",
        "options": None
    },
    "outer_relax": {
        "title": "Outer Relaxation",
        "definition": (
            "Fraction of each solved correction applied per outer "
            "iteration."),
        "unit": "-",
        "equation": None,
        "effect": (
            "Values below 1 damp oscillation between inflow and blade "
            "motion at the cost of more iterations."),
        "range": "0.05 to 1.0",
        "options": None
    },
    "lag_enabled": {
        "title": "Lead-Lag Freedom",
        "definition": (
            "Adds an in-plane hinge at the same offset as the flap hinge, "
            "with its own spring, damper and inertia. The lag moment comes "
            "from the tangential force distribution."),
        "unit": "—",
        "equation": r"\nu_\zeta^{2} = \frac{3}{2}\,\dfrac{e}{1-e} + \dfrac{K_\zeta}{I_\zeta\Omega^{2}}",
        "effect": (
            "Without thrust restoring, a lag freedom needs an offset or a "
            "spring: with neither, its frequency ratio is zero and the "
            "response is undefined."),
        "range": "on / off",
        "options": None
    },
    "lag_spring_nm_per_rad": {
        "title": "Lag Spring",
        "definition": (
            "Stiffness of the lag root spring, in newton metres per radian."),
        "unit": "N·m/rad",
        "equation": r"+\,\dfrac{K_\zeta}{I_\zeta\Omega^{2}} \text{ in } \nu_\zeta^{2}",
        "effect": (
            "Keeps the lag angle defined on a rotor whose lag hinge sits at "
            "the shaft."),
        "range": "0 to 1e9 N·m/rad",
        "options": None
    },
    "lag_damping_nms_per_rad": {
        "title": "Lag Damping",
        "definition": (
            "Damping of the lag freedom, in newton metre seconds per "
            "radian. It couples the sine and cosine parts of each harmonic "
            "into a two-by-two solve."),
        "unit": "N·m·s/rad",
        "equation": r"C_\zeta/(I_\zeta\Omega) \text{ per harmonic}",
        "effect": (
            "Real rotors carry a lag damper: without enough of it the lag "
            "motion stays marginal."),
        "range": "0 to 1e9 N·m·s/rad",
        "options": None
    },
    "lag_inertia_kg_m2": {
        "title": "Lag Inertia",
        "definition": (
            "Inertia of one blade about the lag hinge, required whenever "
            "lead-lag is enabled."),
        "unit": "kg·m²",
        "equation": r"M_\zeta/(I_\zeta\Omega^{2})",
        "effect": (
            "Normalizes the lag moment exactly as the flap inertia does for "
            "flapping."),
        "range": "1e-6 to 1e6 kg·m²",
        "options": None
    },
    "lag_feeds_back": {
        "title": "Lag Rate Feedback",
        "definition": (
            "When set, the lag rate modifies the tangential speed of each "
            "element, closing the loop between lag motion and "
            "aerodynamics."),
        "unit": "—",
        "equation": r"U_T \to U_T + (r-eR)\,\dot\zeta",
        "effect": (
            "Leaving it on is the consistent choice; turning it off turns "
            "the lag into a diagnostic that does not act back on the loads."),
        "range": "on / off",
        "options": None
    },
    "cyclic_c_deg": {
        "title": "Cyclic Pitch, Cosine",
        "definition": (
            "Pitch that varies once per revolution as θ₁c·cos(ψ), applied "
            "on top of the collective and the twist."),
        "unit": "deg",
        "equation": r"\theta(\psi)=\theta_0+\theta_{1c}\cos\psi+\theta_{1s}\sin\psi",
        "effect": (
            "Tilts the blade response fore-aft. With flap freedom it is one "
            "of the two controls the zero-flapping trim solves for; on a "
            "rigid blade it enters only as azimuthal pitch."),
        "range": "−30° to +30°",
        "options": None
    },
    "cyclic_s_deg": {
        "title": "Cyclic Pitch, Sine",
        "definition": (
            "Pitch that varies once per revolution as θ₁s·sin(ψ), applied "
            "on top of the collective and the twist."),
        "unit": "deg",
        "equation": r"\theta(\psi)=\theta_0+\theta_{1c}\cos\psi+\theta_{1s}\sin\psi",
        "effect": (
            "Tilts the blade response sideways. Together with the cosine "
            "harmonic it forms the pair the trim solves."),
        "range": "−30° to +30°",
        "options": None
    },
    "Vy": {
        "title": "Lateral Flow",
        "definition": (
            "Component V<sub>y</sub> of the free stream along the vehicle y "
            "axis: sideways, and in the plane of the disk.\n\n"
            "The disk plane has two directions. The field above gives the "
            "first one, and this field gives the second, so the stream can "
            "arrive from the side: sideward flight for a rotor, a propeller "
            "flying with its shaft out of the wind.\n\n"
            "The engine reads the pair as one in-plane speed and one "
            "direction, V = √(V<sub>x</sub>² + V<sub>y</sub>²) at "
            "ψ<sub>w</sub> = atan2(V<sub>y</sub>, V<sub>x</sub>). Zero "
            "reproduces the plain edgewise case, so every condition saved "
            "before this field existed keeps its exact behavior."),
        "unit": "m/s",
        "equation": (
            r"U_T = \Omega r + V\sin(\psi-\psi_w),\qquad "
            r"V=\sqrt{V_x^2+V_y^2},\qquad \psi_w=\operatorname{atan2}(V_y,V_x)"),
        "effect": (
            "At V<sub>x</sub> = 0 the whole advance comes from the side: the "
            "in-plane force H and the side force Y trade places, while thrust "
            "and torque stay put.\n\n"
            "It is the state a lateral-velocity derivative perturbs, so a "
            "stability study sets it to a small value and reads the hub loads "
            "it produces."),
        "range": "−500 to +500 m/s (0 for flight straight ahead)",
        "options": {
            "Vy": (
                "V<sub>y</sub> [m/s] — the lateral velocity itself, in "
                "metres per second."),
            "sideslip_deg": (
                "ψ<sub>w</sub> [deg] — the sideslip angle. It splits "
                "the in-plane component given above into a lateral one, so it "
                "needs that component to be non-zero and stays inside "
                "±89°."),
            "mu_y": (
                "μ<sub>y</sub> — the lateral velocity over the tip "
                "speed, μ<sub>y</sub> = V<sub>y</sub>/(ΩR)."),
            "J_y": (
                "J<sub>y</sub> — the lateral velocity in the propeller "
                "vocabulary, J<sub>y</sub> = V<sub>y</sub>/(nD) = "
                "π·μ<sub>y</sub>."),
        }
    },
    "sideslip_deg": {
        "title": "Sideslip of the In-Plane Flow",
        "definition": (
            "Angle ψ<sub>w</sub> between the in-plane free stream and the "
            "longitudinal direction, measured in the plane of the disk.\n\n"
            "It is the ANGLE SPELLING of the lateral flow V<sub>y</sub>: "
            "ψ<sub>w</sub> = atan2(V<sub>y</sub>, V<sub>x</sub>), so it "
            "SPLITS the in-plane component given above into a lateral one, "
            "exactly as α<sub>rotor</sub> splits it into the axial one. "
            "An angle never sets the scale of a velocity.\n\n"
            "The tangential speed at each azimuth becomes "
            "U<sub>T</sub> = Ωr + V·sin(ψ − ψ<sub>w</sub>), and the spanwise component "
            "becomes U<sub>R</sub> = V·cos(ψ − ψ<sub>w</sub>). The along-shaft flow is "
            "untouched.\n\n"
            "Zero reproduces the plain edgewise case, so every condition saved "
            "before this field existed keeps its exact behavior."),
        "unit": "deg",
        "equation": r"U_T = \Omega r + V\sin(\psi-\psi_w),\qquad U_R = V\cos(\psi-\psi_w)",
        "effect": (
            "It turns the loading pattern with the stream: the in-plane force "
            "H and the side force Y trade shares of the same resultant, while "
            "thrust and torque stay put.\n\n"
            "It is the state a lateral-velocity derivative perturbs, so a "
            "stability study sets it to a small value and reads the hub loads "
            "it produces."),
        "range": (
            "−89° to +89° (0° for straight edgewise flight). "
            "90° is excluded: there the angle asks for a lateral velocity "
            "with no longitudinal one to split, so pure sideward flight is "
            "given as V<sub>y</sub> instead."),
        "options": None
    },
    "p_rate_deg_s": {
        "title": "Hub Roll Rate",
        "definition": (
            "Angular rate p of the hub about the longitudinal axis, positive "
            "when the rotor rolls toward the advancing side.\n\n"
            "A rolling hub carries every blade element out of the disk plane. "
            "The perpendicular speed U<sub>P</sub>, which counts downward, "
            "receives −r·p·sinψ, and with flap freedom the flap balance "
            "receives a gyroscopic forcing of its own."),
        "unit": "deg/s",
        "equation": r"U_P \to U_P - r\,p\sin\psi,\qquad \bar{M}_{gyro} = \frac{2p\cos\psi}{\Omega}",
        "effect": (
            "The hub moment it produces is the roll damping, the derivative of "
            "the rolling moment M<sub>y</sub> with respect to p.\n\n"
            "A rotor with no flap freedom still feels the aerodynamic part of "
            "the effect, because the perpendicular speed reaches the whole "
            "blade-element aerodynamics."),
        "range": "−360 to +360 deg/s (0 in steady flight; a few deg/s for a derivative step)",
        "options": None
    },
    "q_rate_deg_s": {
        "title": "Hub Pitch Rate",
        "definition": (
            "Angular rate q of the hub about the lateral axis, positive nose "
            "up.\n\n"
            "A pitching hub carries every blade element out of the disk plane. "
            "The perpendicular speed U<sub>P</sub>, which counts downward, "
            "receives −r·q·cosψ, so a nose-up rate raises the element at the "
            "nose of the disk, and with flap freedom the flap balance receives "
            "a gyroscopic forcing of its own."),
        "unit": "deg/s",
        "equation": r"U_P \to U_P - r\,q\cos\psi,\qquad \bar{M}_{gyro} = -\frac{2q\sin\psi}{\Omega}",
        "effect": (
            "The hub moment it produces is the pitch damping, the derivative of "
            "the pitching moment M<sub>x</sub> with respect to q.\n\n"
            "A rotor with no flap freedom still feels the aerodynamic part of "
            "the effect, because the perpendicular speed reaches the whole "
            "blade-element aerodynamics."),
        "range": "−360 to +360 deg/s (0 in steady flight; a few deg/s for a derivative step)",
        "options": None
    },
}
