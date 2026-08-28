"""Provide concise block-level help for GUI group boxes.

The registry maps each visible block identifier to a title, Qt rich-text body, and
documentation anchor. ``help_popup.py`` renders the entries and tab widgets provide
the identifiers. Bodies use HTML ``<sub>`` and ``<sup>`` notation supported by Qt
rich text and summarize the block's physical role; the HTML documentation remains
the complete reference. This module contains data only and has no solver, file, or
persistent-state responsibilities.
"""
from __future__ import annotations

BLOCK_HELP: dict[str, dict] = {
    "operation_mode": {
        "title": "Operation Mode — rotor or propeller",
        "body": [
            "The same solver runs both. What changes is the <b>reference frame the answer is reported in</b>, and that choice is not cosmetic. The two conventions non-dimensionalize thrust and power by different scales, so the same physical rotor produces two entirely different sets of numbers.",
            "<b>Rotor convention.</b> The disk is the reference area and tip speed the reference velocity: C<sub>T</sub> = T/(ρ·A·Ω²R²), C<sub>Q</sub> = Q/(ρ·A·Ω²R³), C<sub>P</sub> = P/(ρ·A·Ω³R³). The natural efficiency measure is the <b>figure of merit</b> FM = C<sub>T</sub><sup>3/2</sup>/(√2·C<sub>P</sub>), which compares the actual hover power with the induced power an ideal actuator disk would need for the same thrust. FM is a hover metric and loses meaning in fast forward flight.",
            "<b>Propeller convention.</b> The rotational frequency n = rpm/60 and the diameter D = 2R are the reference scales: C<sub>T</sub> = T/(ρ·n²D⁴), C<sub>P</sub> = P/(ρ·n³D⁵), with advance ratio J<sub>x</sub> = V<sub>x</sub>/(nD). Efficiency is η = J<sub>x</sub>·C<sub>T</sub>/C<sub>P</sub>, the ratio of useful propulsive power T·V<sub>x</sub> to shaft power. That ratio is identically zero at static thrust and peaks at a finite J<sub>x</sub>.",
            "The distinction also changes what the flight-condition fields mean. A rotor is described by the advance ratio μ<sub>x</sub> = V<sub>x</sub>/(ΩR) and an angle α<sub>rotor</sub>; a propeller by J<sub>x</sub> and an axial speed V<sub>x</sub>, since the flow is essentially along the shaft. The engine solves the same blade-element/momentum coupling either way.",
            "Pick the convention your reference data uses. Reading a propeller C<sub>T</sub> as if it were a rotor C<sub>T</sub> is a factor-of-7.75 error and nothing warns you: substituting Ω = 2πn and D = 2R gives C<sub>T,prop</sub>/C<sub>T,rotor</sub> = π³/4 ≈ 7.75 and C<sub>P,prop</sub>/C<sub>P,rotor</sub> = π⁴/4 ≈ 24.4, for the same rotor at the same operating point.",
        ],
        "anchor": "cap-14-4",
    },
    "global_geometry": {
        "title": "Global Geometry — the scales that set everything else",
        "body": [
            "Four numbers fix the size of the problem before any aerodynamics happens: the number of blades, the radius, the root cutout, and the reference chord that the radial table is normalized against.",
            "<b>Radius</b> is the strongest lever in the tool. It sets the tip speed ΩR at a given rpm, hence the dynamic pressure ½ρW² at every station, hence every force. Thrust scales roughly as R⁴ at fixed rpm and fixed blade loading, and power as R⁵. Doubling the radius is not a small change, and it is also what pushes the tip toward the Mach numbers where compressibility and wave drag start to matter.",
            "<b>Number of blades</b> enters in two distinct places that pull in opposite directions. It multiplies the total load through the solidity:"
            "\n\n"
            r"$$\sigma = \dfrac{N_b\,\bar{c}}{\pi R}$$"
            "\n\n"
            "so more blades at fixed chord means more thrust at the same collective. It also enters the Prandtl tip-loss exponent through N<sub>b</sub>/2: more blades approximate the continuous actuator disk more closely, so the tip loss shrinks and the effective disk area grows. The net effect at fixed solidity is a modest efficiency gain, which is why blade count and chord are usually traded against each other rather than chosen independently.",
            "<b>Root cutout</b> is the inboard station where the aerodynamic blade begins; inboard of it the hub and shaft occupy the disk and carry no useful lift. It removes the innermost annuli from the integration, where the local velocity Ωr is small and the contribution is minor for thrust but not negligible for the root-loss factor.",
            "These values are shared by every flight condition in the project. Changing one invalidates any result already computed, which is why the geometry is edited here rather than per case.",
        ],
        "anchor": "cap-2-1",
    },
    "blade_dynamics": {
        "title": "Blade Dynamics - the rigid blade's flap and lead-lag freedoms",
        "body": [
            "A real blade is never bolted stiff to the hub: it flaps out of the disk plane and lags against the rotation. This block gives the rigid blade those two rigid-body freedoms, solved as one periodic response that repeats every revolution. The blade does not bend; only its hinge motion acts on the flow.",
            "Flapping answers thrust with a coning angle &beta;<sub>0</sub>, tilts the disk in edgewise flight through its 1/rev harmonics, and - when the hinge carries an offset or a spring - feeds a structural moment back into the hub: M<sub>hub</sub> = (N<sub>b</sub>/2)&middot;I<sub>&beta;</sub>&Omega;<sup>2</sup>(&nu;<sub>&beta;</sub><sup>2</sup>&minus;1)&beta;<sub>1</sub>. Lead-lag follows the same scheme in the disk plane, with a damper instead of thrust restoring.",
            "The defaults keep the blade fully rigid, which reproduces every result computed before this block existed. Enable a flap model and the panel beside the inputs shows the resolved frequency ratio, inertia and natural frequency as you type.",
        ],
        "anchor": "sec-blade-dynamics",
    },
    "flap_plots": {
        "title": "Blade dynamics plots - what the flap response did",
        "body": [
            "Three figures read the blade-dynamics part of a result. The <b>flap response</b> draws &beta;(&psi;) over one revolution as a polar curve, with each harmonic's amplitude annotated. The <b>effect of flapping</b> re-solves the same condition once more with a rigid blade and puts the two disk maps side by side, so the change is visible where it happens.",
            "The <b>convergence</b> figure shows the outer-loop trace: how large a correction each exchange between inflow and blade motion tried to apply, until it met the tolerance. A trace that falls smoothly means the coupling agreed; a trace that stalls names its residual honestly.",
        ],
        "anchor": "sec-blade-dynamics",
    },
    "radial_table": {
        "title": "Radial Distribution Table — how the blade varies along the span",
        "body": [
            "Each row is a spanwise station: its position as a fraction of the radius, the local chord (normalized by the radius) and the local geometric twist. Between rows the engine interpolates linearly, so the table is a piecewise-linear description of a real blade, not a set of independent design points.",
            "<b>Chord distribution</b> sets how much area each annulus has to work with. Because the local dynamic pressure grows as (Ωr)², an untapered blade loads its outboard half heavily and its root barely at all. Tapering the tip trades some of that outboard area away, which lowers the tip vortex strength and moves the peak loading inboard. The ideal hover distribution (the one that makes induced velocity uniform over the disk) has chord falling roughly as 1/r, which is why practical rotors taper.",
            "<b>Twist</b> is the built-in pitch variation, almost always negative outboard (washout). The reason is geometric: the inflow angle φ = arctan(U<sub>P</sub>/U<sub>T</sub>) is large near the root, where U<sub>T</sub> = Ωr is small, and small at the tip. Without twist the root would operate near or past stall while the tip ran at a small angle of attack. Ideal hover twist varies as 1/r. Linear washout of −8° to −14° over the span is the usual practical approximation, and it is the single most effective way to flatten the spanwise loading and raise the figure of merit.",
            "In forward flight twist interacts with the advancing/retreating asymmetry: the same washout that balances hover leaves the advancing tip at low or negative angle of attack and the retreating blade closer to stall. That trade is why forward-flight-optimized and hover-optimized twist distributions differ.",
            "Resolution matters where the gradients are: a table dense near the tip resolves the region where the Prandtl factor collapses and the loading falls steeply, which a uniform coarse table smears out.",
        ],
        "anchor": "s1",
    },
    "radial_sections": {
        "title": "Radial Sections — more than one airfoil along the blade",
        "body": [
            "A real blade rarely uses one profile from root to tip. The two ends face genuinely different flow, and the sections are chosen accordingly: a thick, high-camber, high-maximum-lift profile inboard, where the local velocity is low and structural depth is needed, and a thin, low-drag, high-critical-Mach profile outboard. Outboard the velocity is high and compressibility is the binding constraint.",
            "With two or more sections defined, the engine assigns each blade element the polar of the <b>nearest</b> defined station and no longer looks at the single-airfoil definition at all. There is no blending between neighboring sections: the change is a step at the midpoint between two stations, which is visible as a discontinuity in the spanwise load if the two polars differ strongly.",
            "The consequence to expect in the result is concentrated where the sections differ most in maximum lift and in zero-lift angle: a section with a more negative α₀ produces lift at a lower geometric pitch, so switching profiles mid-span shifts the local angle of attack the same way a twist step would.",
            "With zero or one section the tab is in single-airfoil mode and the whole blade uses one polar. That is the right choice when the polar is the dominant uncertainty anyway. A second section is only worth defining when its polar is genuinely known.",
        ],
        "anchor": "cap-3-1",
    },
    "polar_navigator": {
        "title": "Navigate (r/R, Reynolds, Mach) — which slice you are looking at",
        "body": [
            "A tabulated polar is not one curve. It is a family: Cl and Cd depend on angle of attack, on Reynolds number and on Mach number, and in a multi-section blade also on spanwise position. These controls choose which slice of that family the preview draws.",
            "They are a <b>viewing</b> choice only. Nothing here changes the project or the computation. During a run the engine picks the slice for each element from that element's own local conditions, interpolating between the tabulated values.",
            "The three axes matter for different reasons. <b>Reynolds number</b> Re = ρ·W·c/μ governs the state of the boundary layer: below roughly 10⁵ the layer stays laminar over much of the chord, separation happens early, and minimum drag can be several times its high-Reynolds value. <b>Mach number</b> M = W/a governs compressibility: lift slope grows as 1/√(1−M²) until the critical Mach number, beyond which a shock forms and drag rises steeply. <b>Spanwise position</b> matters only when the blade has more than one defined section.",
            "Use the navigator to check that the tabulated data actually covers the conditions your case will produce. A polar tabulated only up to M = 0.4 evaluated on a rotor whose advancing tip reaches M = 0.8 will hold the edge value, silently and wrongly.",
        ],
        "anchor": "cap-3-10",
    },
    "local_corrections": {
        "title": "Compressibility and Reverse Flow — where the 2D polar stops being enough",
        "body": [
            "This block groups the two corrections that both answer the same question: the polar was measured (or computed) in a steady, incompressible, forward-facing 2D flow, and parts of a real rotor disk are none of those things.",
            "<b>Reverse flow</b> is a geometric consequence of forward flight. The tangential velocity of an element is U<sub>T</sub> = Ωr + V∞·sin ψ, which changes sign wherever the free stream overwhelms the rotation (inboard on the retreating side). The locus U<sub>T</sub> = 0 is a circle of diameter μR tangent to the hub. Inside it the trailing edge meets the flow first, and a polar measured leading-edge-first says nothing valid about that. Its size grows linearly with the advance ratio, so it is negligible in hover and dominates the inboard retreating quadrant at high speed.",
            "<b>Compressibility</b> is the opposite corner of the disk. The largest relative velocity is at the advancing tip, W ≈ ΩR + V∞, and there the flow can be transonic while the rest of the disk is comfortably subsonic. The Prandtl-Glauert factor stretches the incompressible lift curve to account for it.",
            "The two are complementary in space, not competing: reverse flow is an inboard-retreating effect and compressibility an outboard-advancing one. A high-speed rotor has both at once, at opposite ends of the disk, and each is handled by its own sub-block below.",
        ],
        "anchor": "cap-4-4",
    },
    "table_import": {
        "title": "Data import / tabulated polar — measured or computed coefficients",
        "body": [
            "An imported table replaces the analytical lift and drag model entirely. Instead of Cl = Cl_α(α − α₀) with a stall closure, the engine interpolates directly between the tabulated points. So everything the table contains (the real stall shape, the drag bucket, the Reynolds and Mach trends) is used, and everything it omits is invented by whatever extrapolation rule is active.",
            "That last point is the one that bites. Outside the tabulated angle-of-attack range the interpolation holds the edge value: a table swept from −10° to 20° evaluated at 40° returns the 20° coefficients, which understates drag by a large factor. On a rotor in forward flight, inboard retreating elements routinely see angles far outside any wind-tunnel sweep, so a table without the full-range extension active is a silent source of error exactly where the loads are hardest to get right.",
            "The table may carry additional axes: one curve per Reynolds number, per Mach number, per spanwise station. The engine interpolates between them using each element's own local conditions. A table that already resolves Mach must <b>not</b> be combined with the compressibility correction: that applies the same physics twice.",
            "Two numbers are re-derived from the table because other corrections need them: the lift-curve slope, from a finite difference near the middle of the curve, and the zero-lift angle, from where lift crosses zero. The rotational-augmentation correction is written in terms of those two quantities and cannot work without them.",
        ],
        "anchor": "cap-3-6",
    },
    "project_configuration": {
        "title": "Project configuration — what is stored and what is not",
        "body": [
            "Everything the tabs edit lives in a single project file: geometry, airfoil definition, engine settings, saved flight conditions and saved case queues. It is the same file the command line reads, so a case set up in the window and a case run from a script are the same case.",
            "What is <b>not</b> stored is anything derived: results, figures, and reports. Those are regenerated from the inputs, which is what makes a project reproducible: the file is the experiment, not its output.",
            "Applying a change and saving it are separate steps on purpose. Applying makes the change take effect in the session so a run reflects it immediately. Saving writes it to disk. A window closed with applied-but-unsaved changes warns before discarding them.",
        ],
        "anchor": "cap-interfaces-2",
    },
    "saved_cases": {
        "title": "Saved Cases — flight conditions kept with the project",
        "body": [
            "A flight condition is four numbers: advance ratio (or axial speed), disk angle (or climb velocity), collective pitch and rotational speed. Together they fix the entire velocity field the blade sees, and therefore the whole solution.",
            "Saving one stores it in the project file under a name, so the exact condition survives closing the window and is available to the command line and to scripts. This is the mechanism for a reproducible reference point: the design hover case, the cruise case, the condition a wind-tunnel run was measured at.",
            "Selecting a saved case only loads its values into the fields. It does not run anything. That separation is deliberate: a condition can be loaded, adjusted and run without overwriting the stored version.",
            "A project's first saved case also seeds the defaults when the tab opens, which is what keeps a freshly opened rotor from starting at a condition that has nothing to do with it.",
        ],
        "anchor": "cap-5-4",
    },
    "batch_fixed_values": {
        "title": "Fixed values — the condition variables that are not being swept",
        "body": [
            "A sweep varies one to three quantities; the rest of the flight condition still has to be specified, and these fields do that. Every generated case shares them.",
            "They are not neutral background. A sweep in collective at fixed rpm and fixed advance ratio traces a thrust curve at constant tip speed. The same collective sweep at a different fixed rpm traces a different curve. Rotational speed rescales the relative velocity at every station and therefore the Reynolds number, the Mach number, and the dynamic pressure that the coefficients are divided by. Fixing a value is a statement about the experiment, not a formality.",
            "The most consequential fixed value is usually the advance ratio, because it alone decides how much of the disk is in reverse flow and how strong the advancing/retreating asymmetry is. A collective sweep at zero advance ratio is a hover polar; the same sweep at 0.3 is a different physical problem.",
            "A quantity assigned to an axis is swept and its fixed field is ignored: the axis wins.",
        ],
        "anchor": "cap-6-2",
    },
    "case_queue": {
        "title": "Case queue — the single source of truth for what will run",
        "body": [
            "Both ways of specifying a batch (a factorial expansion over axes, and an explicit list of conditions) end in this queue, and only the queue is executed. Generating cases fills it. It does not run anything and computes no physics.",
            "That separation is what makes a large sweep safe to set up. A three-axis factorial multiplies rather than adds: ten advance ratios by five collectives by four rotational speeds is two hundred cases, not nineteen. The queue shows the actual count before any solver time is spent, which is the moment to notice that the mesh and the case count together imply an overnight run.",
            "Cases can be reviewed, removed and reordered here. A queue that is right can be saved with the project under a name and reloaded later, which is how a sweep becomes reproducible rather than re-typed.",
        ],
        "anchor": "cap-6-3",
    },
    "batch_run": {
        "title": "Run — executing the queue, directly or trimmed",
        "body": [
            "Each queued condition is solved exactly as a single case would be: same mesh, same inflow model, same corrections, same convergence criterion. A batch is a loop, not a different physics.",
            "<b>Direct mode</b> takes the collective as given and reports whatever thrust results. This is the right mode when the question is about the rotor's response: a collective sweep, a stall boundary, the shape of a power curve.",
            "<b>Trim mode</b> inverts the question: thrust (or its coefficient) is prescribed, and the collective becomes an unknown that an outer iteration solves for. This is the right mode when comparing configurations at equal lift, the only fair comparison for power, since a rotor producing more thrust will always draw more power. The outer loop wraps the whole element solve, so a trimmed case costs several times a direct one.",
            "Trim can fail to bracket its target when the requested thrust is beyond what the rotor can produce at that condition. Past stall, the thrust-versus-collective curve flattens and then falls, so a target above the peak has no solution and two below it may have.",
            "Running does not save anything to disk. Results accumulate in this session's history, and export is a separate, explicit step.",
        ],
        "anchor": "cap-6",
    },
    "batch_export": {
        "title": "Export — writing tables and figures to disk",
        "body": [
            "Export writes what is already computed: one row per condition in a table, plus whichever figure families are ticked. It runs no physics and cannot change a result.",
            "The tabular export carries the full summary of every case: coefficients, dimensional forces, and the configuration echo that records which solver, inflow model and corrections produced those numbers. That echo is what makes a result file interpretable months later. A table of coefficients without it is not.",
            "Figures are generated per case and per family, so a large batch with several families ticked produces a large number of files. The output folder defaults to the project's own outputs directory, and an existing file of the same name is never overwritten silently.",
            "For a document rather than a folder of files, the report generator in the Results tab produces a single self-contained page with the same data.",
        ],
        "anchor": "cap-6-4",
    },
    "view_3d": {
        "title": "3D view — geometry and load in space",
        "body": [
            "The three-dimensional view paints a solved field onto the actual blade surface, which is the one representation that shows spanwise and azimuthal variation together with the blade's own shape. It is a rendering of results already computed. Changing the field here re-colors the view. It does not re-solve.",
            "It answers questions the flat disk map cannot. Twist and taper are visible as geometry rather than inferred from a curve, so a loading peak can be read directly against the chord and pitch that produced it: for instance whether a high local lift coefficient is a genuinely stalled station or simply a narrow chord carrying an ordinary load.",
            "The schematic planform preview is always available. The full three-dimensional view depends on an optional rendering package; without it the export is disabled and the flat preview remains.",
        ],
        "anchor": "cap-7-4",
    },
    "aerodynamic_model": {
        "title": "Aerodynamic Model — the 2D airfoil polar",
        "body": [
            "Every blade element gets its force from a <b>polar</b>: the pair of functions "
            "C<sub>l</sub>(α, Re, M) and C<sub>d</sub>(α, Re, M). BEMT never solves the flow "
            "around the section. It looks the coefficients up and projects them onto the disk:"
            "\n\n"
            r"$$dL = \dfrac{1}{2}\rho W^2 c\,C_l\,dr, \quad dD = \dfrac{1}{2}\rho W^2 c\,C_d\,dr$$"
            "\n\n"
            r"$$dF_n = dL\cos\varphi - dD\sin\varphi, \quad dF_t = dL\sin\varphi + dD\cos\varphi$$",
            "<b>Analytical (thin-airfoil) core.</b> "
            "Valid while the boundary layer stays attached (α<sub>0</sub> &lt; 0 for positive camber):"
            "\n\n"
            r"$$C_l = C_{l\alpha}(\alpha - \alpha_0), \quad C_{l\alpha} \approx 2\pi\,\mathrm{rad}^{-1}$$"
            "\n\n"
            r"$$C_d = C_{d0} + k\,C_l^2$$",
            "<b>Static stall models</b> extend the linear curve past α<sub>stall</sub>, "
            "where C<sub>l,s</sub> = C<sub>lα</sub>(α<sub>stall</sub> − α<sub>0</sub>):<br>"
            "• <b>linear</b> — no limit; the line is used for every α "
            "(solver-verification / theoretical reference only).<br>"
            "• <b>clip</b> — C<sub>l</sub> saturates at C<sub>l,s</sub>; value-continuous but with a derivative corner.<br>"
            "• <b>enhanced</b> (default) — C¹-continuous cosine roll-off past stall over Δ = 30°:"
            "\n\n"
            r"$$C_l = C_{l,s}\cos\left[\min\left(\dfrac{\pi}{2},\, \dfrac{\alpha - \alpha_s}{\Delta}\dfrac{\pi}{2}\right)\right]$$"
            "\n\n"
            r"$$C_d \to C_{d,\mathrm{fp}} \approx 1.9 \quad \text{as } \sin^2\left(\dfrac{\alpha-\alpha_s}{\Delta}\dfrac{\pi}{2}\right)$$"
            "• <b>viterna</b> — Viterna-Corrigan full-range closure (see below).",
            "<b>Viterna-Corrigan extrapolation (1981)</b>, for α<sub>s</sub> &lt; |α| ≤ 90°:"
            "\n\n"
            r"$$C_l = A_1\sin 2\alpha + A_2\dfrac{\cos^2\alpha}{\sin\alpha}, \quad C_d = B_1\sin^2\alpha + B_2\cos\alpha$$"
            "\n\n"
            r"$$A_1 = \dfrac{C_{d,\max}}{2}, \quad B_1 = C_{d,\max}$$"
            "with C<sub>d,max</sub> = 2.01 (pure 2D) or 1.11 + 0.018·AR (finite span)."
            "<br>A<sub>2</sub> and B<sub>2</sub> enforce exact continuity at α<sub>s</sub>. "
            "For 90° &lt; |α| ≤ 180° the curve is reflected about 90° (C<sub>l</sub> odd, C<sub>d</sub> even).",
            "<b>Tabulated source.</b> Direct linear interpolation over measured or XFOIL points "
            "(α<sub>i</sub>, C<sub>l,i</sub>, C<sub>d,i</sub>), optionally one table per Reynolds, Mach and r/R "
            "(bilinear interpolation in the extra axis). Highest fidelity where data exist. "
            "Outside the measured α range the edge value is held, which is exactly why "
            "the Viterna closure exists.",
            "<b>NeuralFoil source.</b> A neural surrogate of XFOIL evaluated on a (α, Re, M) "
            "grid; the result becomes an ordinary table consumed by the identical code path. "
            "C<sub>lα</sub> and α<sub>0</sub> are re-estimated from the table by finite difference "
            "and zero-crossing. The rotational-augmentation correction needs those two numbers "
            "even when the polar is tabulated.",
        ],
        "anchor": "cap-3-2",
    },
    "dynamic_stall": {
        "title": "Dynamic Stall (Øye) — separation lag",
        "body": [
            "Separation does not follow α instantly: it lags by a few convective times c/W. Sweeping through stall once per revolution therefore traces a <b>hysteresis loop</b>, not the static curve: Cl overshoots while α rises and stays low while α falls.",
            "<b>State variable.</b> Attached fraction of the chord f ∈ [0,1] from Kirchhoff's mixture with static polar C<sub>l,att</sub> = C<sub>lα</sub>(α − α<sub>0</sub>):\n\n"
            r"$$f_{\mathrm{st}} = \left(2\sqrt{\dfrac{C_{l,\mathrm{st}}}{C_{l,\mathrm{att}}}} - 1\right)^2 \quad (\text{clipped to } [0,1])$$",
            "<b>Lag equation.</b> First-order relaxation towards the quasi-steady attached state:\n\n"
            r"$$\dfrac{df}{dt} = \dfrac{f_{\mathrm{st}} - f}{\tau}, \quad \tau = \dfrac{A\,c}{2W} \quad (A \approx 8)$$",
            "<b>Dynamic loads reconstruction.</b> Weighted blend for lift and Bergami extension for drag:\n\n"
            r"$$C_{l,\mathrm{dyn}} = f\,C_{l,\mathrm{att}} + (1 - f)\,C_{l,\mathrm{sep}}$$"
            "\n\n"
            r"$$C_{d,\mathrm{dyn}} = C_{d,\mathrm{st}} + (C_{d,\mathrm{st}} - C_{d0})\left[\dfrac{1}{2}(\sqrt{f_{\mathrm{st}}} - \sqrt{f}) - \dfrac{1}{4}(f - f_{\mathrm{st}})\right]$$",
            "<b>Frequency-domain solution.</b> In periodic flight, harmonic decomposition yields an exact solution without time marching:\n\n"
            r"$$\hat{f}_n = H_n\,\hat{f}_{\mathrm{st},n}, \quad H_n = \dfrac{1}{1 + i\,n\,\Omega\,\tau}$$"
            "\n\n"
            r"$$|H_n| = \left[1 + (n\,\Omega\,\tau)^2\right]^{-1/2}, \quad \angle H_n = -\arctan(n\,\Omega\,\tau)$$",
            "<b>Fade window.</b> A smoothstep in |α<sub>eff</sub>| between fade_start and fade_end returns the result to the static polar at extreme angles, where the lag model is no longer validated. The correction is applied as post-processing on the converged inflow field, so it never feeds back into the momentum equation.",
        ],
        "anchor": "cap-3-3",
    },
    "reverse_flow": {
        "title": "Reverse Flow — the retreating-side circle",
        "body": [
            "In forward flight U<sub>T</sub> = Ωr + V∞·sin ψ changes sign inboard on the retreating side. U<sub>T</sub> = 0 traces the circle r = −μR·sin ψ (only where sin ψ &lt; 0): a disk of diameter μR tangent to the hub. Inside it the trailing edge faces the flow.",
            "<b>simple_flip</b> — α<sub>eff</sub> = −α<sub>geom</sub>, |U<sub>T</sub>| in Mach. Discontinuous at U<sub>T</sub> = 0.",
            "<b>flat_plate</b> — Cl = 0, Cd ≈ 1.9 inside the region. The most abrupt jump in Cl of the five, but physically defensible as a crude bound.",
            "<b>alpha_blending</b> — α<sub>geom</sub> multiplied by a tanh of normalized U<sub>T</sub> (rate set by reverse_flow_blend_factor): reduces, does not remove, the discontinuity.",
            "<b>thin_plate_blend</b> — no branch on sign(U<sub>T</sub>) at all: φ = atan2(U<sub>P</sub>, U<sub>T</sub>) is already continuous through U<sub>T</sub> = 0, so α<sub>eff</sub> = θ − φ is too. A smoothstep in |α<sub>geom</sub>| (center/width fields) blends the real polar into the thin-plate limit Cl<sub>fp</sub> = ½π·sin 2α, Cd<sub>fp</sub> = 2·sin²α. C¹ everywhere.",
            "<b>viterna_full_range</b> — with the polar already extended to ±180°, α<sub>eff</sub> is simply α<sub>geom</sub> mapped into (−π, π]: no reverse-flow branch is needed, the polar carries the physics in every quadrant. Requires the full-range extension to be active.",
            "Rule of thumb: below μ ≈ 0.2–0.3 the region is small (often inside the root cutout) and all five agree. Above that, the choice is worth a sensitivity run. Masking in disk plots is a drawing option only: forces and CSV always contain the region.",
        ],
        "anchor": "cap-3-4",
    },
    "compressibility": {
        "title": "Compressibility (Prandtl-Glauert)",
        "body": [
            "The local Mach number is M = W/a<sub>sound</sub>, with W the total relative velocity of the element, highest at the advancing tip, where M = (ΩR + V∞)/a.",
            "<b>Correction.</b> The Prandtl-Glauert factor β = √(1 − M²) stretches the incompressible lift slope to its compressible equivalent:"
            "\n\n"
            r"$$C_l \to \dfrac{C_l}{\beta}, \quad C_d \to \dfrac{C_d}{\beta}, \quad \beta = \sqrt{1 - M^2}$$",
            "The factor is 1.005 at M = 0.1, 1.048 at M = 0.3, 1.25 at M = 0.6 and formally diverges at M → 1, which is why the engine floors β instead of letting it blow up. Above M ≈ 0.75–0.8 the linearization is void anyway: shocks and wave drag are not modeled.",
            "Enable it whenever the tip Mach exceeds ≈ 0.3. Do <b>not</b> enable it on a tabulated polar that already carries a Mach axis. That counts compressibility twice, and validation warns about exactly this combination.",
        ],
        "anchor": "cap-3-5",
    },
    "polar_generation": {
        "title": "Polar Generation (External Engines)",
        "body": [
            "Two external engines generate the polar from the 2D contour. <b>NeuralFoil</b> is a neural network trained on a large body of XFOIL runs: given the contour and (α, Re, M) it returns Cl and Cd in milliseconds. <b>XFOIL</b> runs the classic boundary-element binary directly. It gives higher fidelity where it converges and takes minutes instead of milliseconds, and it needs the executable installed (zBEMT looks in ZBEMT_XFOIL_BIN, your remembered Locate… choice, PATH, and the standard install folders).",
            "What comes out is an ordinary tabulated polar: one complete Cl(α), Cd(α) curve per (Re, M) pair. From that point on the engine treats it exactly like an imported table: linear interpolation in α, selection/interpolation of the slice by local Re, M and r/R.",
            "Because it is a table, the same two limits apply: nothing outside the swept α range is known (hold-edge behavior unless the Viterna full-range extension is on), and Cl_α and α₀ used by the rotational-augmentation correction are re-estimated numerically from the generated curve.",
            "Accuracy is best for conventional sections at −5° &lt; α &lt; 25°; it degrades at extreme α, very thin sections and unusual shapes. For production cases, validate one operating point against measured or XFOIL data.",
        ],
        "anchor": "cap-3-8",
    },
    "profile_2d": {
        "title": "2D Profile Geometry",
        "body": [
            "The contour x/c ∈ [0,1] with upper/lower ordinates y/c. It is <b>not</b> the blade geometry (chord, twist, planform) — it is the shape of one section.",
            "The contour never enters the blade element equations. It matters in exactly two places: drawing, and generating a polar with NeuralFoil. Once a polar exists, the engine only ever sees Cl(α, Re, M) and Cd(α, Re, M).",
            "Sources: NACA 4- and 5-digit codes, CST (class-shape transformation) coefficients, Bézier control points, the analytic PARSEC, Joukowski and biconvex families, or imported .dat coordinates (Selig or Lednicer). Each one is a Source option of its own and reveals its fields. Import reads chord-normalized units, so scale the file first when it uses mm or inches.",
        ],
        "anchor": "cap-3-7",
    },
    "mesh_atmosphere": {
        "title": "Mesh & Atmosphere",
        "body": [
            "The disk is discretized into Ne radial × Npsi azimuthal stations; the solver evaluates all Ne×Npsi elements at once per iteration. Δψ = 360°/Npsi. Npsi = 1 means axisymmetric (hover or axial). Resolving advancing and retreating asymmetry needs enough harmonics: 24 is a minimum, 72–144 for high μ or cyclic pitch. Radially, 30–50 is usually converged. The reference production mesh is 120×180.",
            "The integration offset shifts the innermost and outermost nodes off r/R = 0 and r/R = 1, where the Prandtl factor F → 0 and 1/|sin φ| is singular. Too small and the edge nodes are noisy. Too large and real root and tip physics is lost.",
            "ρ scales every force and moment linearly (dL, dD ∝ ρW²), so thrust and power scale with it directly. a<sub>sound</sub> only enters through M = W/a<sub>sound</sub> in the compressibility correction. Reynolds at each station is Re = ρ·W·c(r)/μ<sub>dyn</sub>, which is what selects the slice of a tabulated polar.",
        ],
        "anchor": "cap-4-1-1",
    },
    "inflow": {
        "title": "Inflow Model — how λi is distributed over the disk",
        "body": [
            "Momentum theory gives the mean induced inflow; a real wake in forward flight is <b>tilted backwards</b>, so the front of the disk sees more inflow than the rear. The three classical models add that asymmetry as a first harmonic on top of the mean (ring-theory) solution:"
            "\n\n"
            r"$$\lambda_i(r,\psi) = \lambda_{i,0}\left[1 + K_x\,x\cos\psi + K_y\,x\sin\psi\right], \quad x = r/R$$",
            "<b>Glauert (1926)</b> — the original annular momentum theory: K<sub>x</sub> = K<sub>y</sub> = 0. Every ring is solved independently of ψ. This is classical BEMT and the cheapest option; it cannot represent any fore/aft or lateral asymmetry by construction.",
            "<b>Coleman (1945)</b> — one longitudinal harmonic only (K<sub>y</sub> = 0):"
            "\n\n"
            r"$$K_x = \sqrt{1 + \mathrm{ratio}^2} - \mathrm{ratio}, \quad \mathrm{ratio} = \dfrac{\lambda}{\mu}$$"
            "At high μ (ratio → 0), K<sub>x</sub> → 1. In hover (ratio → ∞), K<sub>x</sub> → 0 (axisymmetric).",
            "<b>Drees (1949)</b> — adds the lateral harmonic and refines the longitudinal one:"
            "\n\n"
            r"$$K_x = \dfrac{4}{3}\left[(1 - 1.8\mu^2)\sqrt{1+\mathrm{ratio}^2} - \mathrm{ratio}\right], \quad K_y = -2\mu$$"
            "K<sub>y</sub> is quasi-constant (depends only on μ): an approximately uniform lateral tilt that Coleman ignores. Both coefficients are empirical fits. K<sub>x</sub> and K<sub>y</sub> follow from the μ and λ already solved, with no tunable parameter.",
            "<b>Pitt-Peters (1981)</b> — derives the same harmonic shape from linearized unsteady actuator-disk theory. Three states (x = r/R):"
            "\n\n"
            r"$$\lambda_i = \nu_0 + \nu_c\,x\cos\psi + \nu_s\,x\sin\psi$$"
            "\n\n"
            r"$$\mathbf{M}\,\dot{\boldsymbol{\nu}} + \mathbf{V}\mathbf{L}^{-1}\boldsymbol{\nu} = \mathbf{C}, \quad \mathbf{C} = (C_T,\, C_{M_y},\, C_{M_x})$$"
            "Solved at equilibrium (dν/dt = 0): ν = LV<sup>−1</sup>C(ν), a fixed point in 3 scalars.",
            "Choosing: Glauert for axial flight and quick scans; Coleman (default) when fore/aft asymmetry matters; Drees for helicopter cruise 0.1 &lt; μ &lt; 0.4 where the lateral tilt is measurable; Pitt-Peters when you want the asymmetry to emerge from the physics, at the cost of a global 3-DOF solve, and with the linear-theory caveat that unrelieved hub moments can push it out of its validity range around μ ≈ 0.16–0.19.",
        ],
        "anchor": "cap-4-2",
    },
    "tip_root_loss": {
        "title": "Tip/Root Loss (Prandtl)",
        "body": [
            "Annular momentum theory assumes infinitely many infinitesimally thin blades. A real rotor has N<sub>b</sub> discrete blades, and near the edges the flow escapes around them instead of being captured by the ring. The visible form of it is the tip vortex.",
            "Prandtl's factor F ∈ (0, 1] multiplies the elemental thrust:"
            "\n\n"
            r"$$f_{\mathrm{tip}} = \dfrac{N_b}{2}\dfrac{1-x}{x\,|\sin\varphi|}, \quad F_{\mathrm{tip}} = \dfrac{2}{\pi}\arccos\!\left(e^{-f_{\mathrm{tip}}}\right)$$"
            "\n\n"
            r"$$f_{\mathrm{root}} = \dfrac{N_b}{2}\dfrac{x - x_{\mathrm{root}}}{x\,|\sin\varphi|}, \quad F_{\mathrm{root}} = \dfrac{2}{\pi}\arccos\!\left(e^{-f_{\mathrm{root}}}\right)$$"
            "\n\n"
            r"$$F = F_{\mathrm{tip}}\cdot F_{\mathrm{root}}, \qquad x = r/R$$",
            "More blades → smaller loss (closer to the continuous-curtain limit). Closer to an edge, or larger φ (more heavily loaded rotor), the faster F drops. In the code F multiplies the effective U<sub>P</sub> in the momentum balance: a smaller F means the same load must be sustained by a larger induced velocity over a smaller effective area.",
            "Modes: off (F = 1, for theoretical comparison only), tip, root, both (default and the physical case).",
        ],
        "anchor": "cap-4-3",
    },
    "rotational_augmentation": {
        "title": "3D Rotational Effects (Himmelskamp/Snel + radial flow)",
        "body": [
            "Himmelskamp (1945) measured sectional lift on rotating blades above anything the same airfoil reaches in a static 2D tunnel, most strongly near the root. Mechanism: rotation drives a spanwise (centrifugal) secondary flow inside the boundary layer. The Coriolis force on that radial flow sets up a chordwise pressure gradient that <b>delays separation</b>.",
            "<b>Snel, Houwink &amp; Bosschers (1993)</b>, applied to lift only (λ<sub>r</sub> = Ωr / |U<sub>P</sub>|):"
            "\n\n"
            r"$$C_{l,3D} = C_{l,2D} + \dfrac{3.1\,\lambda_r^2}{1+\lambda_r^2}\,g(\alpha)\left(\dfrac{c}{r}\right)^2 [C_{l\alpha}(\alpha-\alpha_0) - C_{l,2D}]$$",
            "Read the three factors. (c/r)² makes it a root effect, because it collapses outboard. λ<sub>r</sub>²/(1 + λ<sub>r</sub>²) → 1 when rotation dominates (root, hover) and → 0 when the axial component dominates (tip, high μ), recovering pure 2D at the tip. The bracket is the <b>lift deficit</b> the static polar has already lost to separation, so the correction is identically zero while the flow is attached and grows only past stall. g(α) fades the model out above ≈ 60°.",
            "The correction touches Cl only (never Cd) by construction of the original model, because Snel's underlying data do not characterize drag under rotation.",
            "<b>Radial flow (independence principle).</b> In forward flight each station also sees U<sub>R</sub> = V∞·cos ψ along the span, maximum at ψ = 0°/180° (blade pointing along the free stream, which is then entirely spanwise) and exactly zero at ψ = 90°/270°, where the free stream is entirely tangential and only U<sub>T</sub> feels it. Swept-wing independence says only the velocity normal to the span sets the pressure field (hence lift), while drag responds to the whole flow. zBEMT therefore re-evaluates Cd, and only Cd, at a skewed angle α<sub>y</sub> = α<sub>eff</sub>·cos λ<sub>y</sub>, λ<sub>y</sub> = arctan(U<sub>R</sub>/U<sub>T</sub>), saturating at radial_flow_max_skew_deg to avoid a spurious Cd → 0. The two corrections act on complementary coefficients and do not overlap.",
        ],
        "anchor": "cap-4-4-1",
    },
    "pitt_peters": {
        "title": "Pitt-Peters Dynamic Inflow (finite state)",
        "body": [
            "Three states describe the whole inflow field (x = r/R):"
            "\n\n"
            r"$$\lambda_i(r,\psi) = \nu_0 + \nu_c\,x\cos\psi + \nu_s\,x\sin\psi$$"
            "<i>\"Dynamic\"</i> here refers to the <b>disk</b> degrees of freedom, not to time — the steady variant does not march in time.",
            "<b>Governing system.</b> With ν = (ν<sub>0</sub>, ν<sub>s</sub>, ν<sub>c</sub>) and C = (C<sub>T</sub>, C<sub>My</sub>, C<sub>Mx</sub>) recomputed from element loads:"
            "\n\n"
            r"$$\mathbf{M}\,\dot{\boldsymbol{\nu}} + \mathbf{V}\mathbf{L}^{-1}\boldsymbol{\nu} = \mathbf{C}(\tau), \quad \tau = \Omega t$$",
            "<b>Apparent mass:</b>"
            "\n\n"
            r"$$\mathbf{M} = \mathrm{diag}\left(\dfrac{128}{75\pi},\, \dfrac{16}{45\pi},\, \dfrac{16}{45\pi}\right)$$"
            "\n\n"
            r"$$\mathbf{V} = \mathrm{diag}(V_T,\, \bar{V},\, \bar{V}), \quad V_T = \sqrt{\mu^2 + \lambda^2}$$"
            "\n\n"
            "<b>Gain</b> L couples ν<sub>0</sub> to ν<sub>c</sub> through X = tan(χ/2) = √[(1−sinα*)/(1+sinα*)], "
            "with α* = arctan(λ/μ) the wake skew angle. That off-diagonal term is the wake tilt: the same role as K<sub>x</sub> in Coleman and Drees, but emerging from physics.",
            "<b>Steady solve.</b> With the rate of change dν/dt = 0:"
            "\n\n"
            r"$$\boldsymbol{\nu} = \mathbf{L}\mathbf{V}^{-1}\mathbf{C}(\boldsymbol{\nu})$$"
            "<br>A fixed point in 3 scalars, iterated with relaxation. <code>pitt_peters_outer_iter</code> caps the outer iterations, <code>pitt_peters_relax</code> damps the update, <code>pitt_peters_tol</code> tests ‖ν<sub>new</sub> − ν<sub>old</sub>‖<sub>∞</sub>.",
            "<code>states = 3</code> is what the engine implements. The value 5 (Peters-He, second harmonic) is accepted by the schema but not implemented. N<sub>ψ</sub> must be large enough to resolve the first harmonic cleanly (at least 24; 72 or more preferred).",
        ],
        "anchor": "cap-4-2-5",
    },
    "induction_solver": {
        "title": "Induction Solver — the fixed point in λi",
        "body": [
            "At every element, blade-element theory and momentum theory must give the same load. Written as one scalar equation per node:"
            "\n\n"
            r"$$g(\lambda_i) = \lambda_i$$"
            "<br>where g comes from evaluating the polar at α(λ<sub>i</sub>) and inverting the momentum balance. Everything else in the engine is preparation for this root find.",
            "<b>fixed_point</b> — Picard with relaxation:"
            "\n\n"
            r"$$\lambda_{n+1} = \lambda_n + \omega\left[g(\lambda_n) - \lambda_n\right]$$"
            "<br>Linear convergence, very robust.<br><b>newton</b> (default) — Newton-Raphson on r(λ) = g(λ) − λ. Quadratic near the root, but the finite-difference Jacobian degrades on derivative corners (a reason to avoid <code>stall_model=\"clip\"</code> with it).<br><b>bisection</b> — derivative-free, guaranteed once the root is bracketed, slowest.<br><b>aitken</b> — Δ² extrapolation over two Picard iterates: superlinear, no derivative needed.",
            "<b>Convergence is always tested on the true residual g(λ) − λ, before relaxation.</b> Near root, tip and the reverse-flow azimuths the relaxation factor is deliberately small, so a relaxed step is small there whether or not the element has converged. Testing it would report convergence exactly where convergence is hardest.",
            "<b>Adaptive relaxation.</b> With relax_schedule on, the effective factor is relax·relax_root_factor for r/R &lt; relax_root_threshold, similarly near the tip (relax_tip_threshold) and at azimuths flagged by relax_azimuth_threshold. Lower factors buy stability at those nodes at the cost of iterations.",
            "If an element refuses to converge, the usual causes are physical, not numerical: the polar is queried outside its α range, reverse flow is unmodeled, or the stall model has a corner. Loosen tol, smooth the stall model, or change solver before raising max_iter.",
        ],
        "anchor": "cap-4-5",
    },
    "early_exit": {
        "title": "Early Exit & Stagnation",
        "body": [
            "The sweep over solver iterations stops when every element meets |g(λ) − λ| &lt; tol, or earlier, under two guards.",
            "<b>Early exit.</b> Once the converged fraction exceeds early_exit_fraction (default 0.999), the sweep stops. A handful of stubborn nodes (typically at the reverse-flow boundary) otherwise costs as many iterations as the whole mesh did.",
            "<b>Stagnation.</b> If the converged fraction improves by less than stagnation_min_frac for stagnation_patience consecutive iterations, the residual has stopped moving and further iterations are waste. Note the distinction: convergence is a small and shrinking residual. Stagnation is a residual that has stopped shrinking while still above tol.",
            "Both are diagnostics as much as speed-ups: frequent stagnation means the fixed point is ill-conditioned at some nodes. The remedy is a finer mesh, a smoother stall model, tighter adaptive relaxation, or a different solver, rather than a looser threshold.",
        ],
        "anchor": "cap-4-5-4",
    },
    "run_case": {
        "title": "Run Case — one flight condition end to end",
        "body": [
            "A case is (μ<sub>x</sub> or J<sub>x</sub>, V<sub>z</sub>, collective, rpm). From it: Ω = 2π·rpm/60, tip speed ΩR, and the two element velocities U<sub>T</sub> = Ωr + V<sub>x</sub>·sin ψ and U<sub>P</sub> = V<sub>z</sub> + v<sub>i</sub> + (radial and coning terms), with W = √(U<sub>T</sub>² + U<sub>P</sub>²).",
            "Per element: φ = atan2(U<sub>P</sub>, U<sub>T</sub>), θ(r,ψ) = θ<sub>col</sub> + θ<sub>geo</sub>(r), α<sub>eff</sub> = θ − φ. The polar gives Cl, Cd; dL and dD project to dFn = dL·cos φ − dD·sin φ and dFt = dL·sin φ + dD·cos φ. λ<sub>i</sub> at that node comes from the fixed point that equates this load with the momentum balance.",
            "Integrating over r and ψ gives T, Q, P and the dimensionless coefficients: rotor convention C<sub>T</sub> = T/(ρAΩ²R²), C<sub>Q</sub>, C<sub>P</sub> with figure of merit FM = C<sub>T</sub><sup>3/2</sup>/(√2·C<sub>P</sub>); propeller convention C<sub>T</sub> = T/(ρn²D⁴), C<sub>P</sub> = P/(ρn³D⁵), η = J<sub>x</sub>·C<sub>T</sub>/C<sub>P</sub>. Which set you get is decided by the project mode, not by the case.",
            "Everything per-element (Cl, Cd, α, Re, M, Fn, Ft, λ<sub>i</sub>, iterations) is retained for the Results tab: the summary numbers are integrals of fields you can inspect directly.",
            "Use direct mode for a prescribed collective; use trim mode when thrust or C<sub>T</sub> is the requirement. Save a checked condition before running it again.",
        ],
        "anchor": "cap-17",
    },
    "run_batch": {
        "title": "Run Batch — sweeping the dimensionless space",
        "body": [
            "A batch is a Cartesian product over up to three axes chosen from Edgewise (in-plane) Flow (μ<sub>x</sub> or J<sub>x</sub>), Cross (in-plane) Flow (μ<sub>z</sub> or J<sub>z</sub>), Axial (along-shaft) Flow (α<sub>rotor</sub> or V<sub>z</sub>), collective, and rpm. Expansion is instant and runs no physics; the queue it fills is the single source of truth for what will run.",
            "The axes are not independent knobs on the same physics: μ<sub>x</sub> = V<sub>x</sub>/(ΩR) sets the fore/aft asymmetry of the disk (and therefore how much reverse flow exists at all, the region r = −μ<sub>x</sub>R·sin ψ). Collective shifts α<sub>eff</sub> uniformly. rpm rescales W, hence Reynolds, Mach, and every coefficient's denominator. A sweep that varies rpm at fixed μ<sub>x</sub> is not the same experiment as one that varies V<sub>x</sub>.",
            "Each generated point is a complete flight condition solved exactly as a single Run Case: same solver, same corrections. Results accumulate in memory and can be exported as one row per case (CSV) plus per-case plots and a report.",
            "Choose factorial mode for a Cartesian sweep and explicit-list mode for hand-picked points. Review the queue before Run, and use fixed thrust or fixed C<sub>T</sub> only when the outer collective trim is part of the experiment.",
        ],
        "anchor": "cap-14",
    },
    "results": {
        "title": "Results — choose, inspect, and interpret the solution",
        "body": [
            "Start by selecting one or more entries in <b>Results from this session</b>. A Run Case creates one entry; a Run Batch creates one entry containing all of its conditions. Use <b>Select all</b> and <b>Clear selection</b> to change what is plotted, and <b>Delete entries</b> only when an entry should be removed from this session's history for good.",
            "Choose <b>Disk map</b> for the spatial answer at one condition, <b>Coefficients vs. Axis</b> for a sweep, <b>Azimuth / Radius</b> for a sectional load distribution, or <b>3D</b> for geometry and load inspection. These controls change the question being plotted. They do not rerun the aerodynamic solver.",
            "Interpret the outputs physically: <i>C<sub>T</sub></i> measures thrust relative to disk area and tip-speed scale, <i>C<sub>Q</sub></i> and <i>C<sub>P</sub></i> measure torque and power, and <i>FM</i> compares ideal induced power with computed hover power. In disk maps, compare <i>F<sub>n</sub></i>/<i>F<sub>t</sub></i>, <i>α</i>, <i>λ<sub>i</sub></i>, and <i>W</i> together. A sharp feature may be a real effect of the advancing and retreating sides or of reverse flow, not automatically a numerical error.",
            "Use <b>Batch condition</b> only when a selected batch must be reduced to one condition for a disk, azimuth/radius, or 3D view. <b>Overlay selections</b> keeps one curve per selected case. <b>Copy table</b> copies the numeric summary, while <b>Generate report…</b> exports selected results with symbols, units, plots, and configuration context.",
            "A convergence plot is a diagnostic of the residual |g(λ) − λ| and the converged fraction. If it stagnates, inspect the polar range, reverse-flow model, stall model, mesh, and solver tolerance before interpreting the integrated coefficients as final.",
        ],
        "anchor": "cap-7",
    },
    "geometry_comparison": {
        "title": "Geometry comparison: one condition set, several planforms",
        "body": [
            "This window runs one set of flight conditions over several blade geometries in one pass. Everything except the blade geometry is held identical: the same airfoil polar, the same mesh, the same inflow model and the same solver settings go into every run. Any difference between two results therefore has a geometric cause.",
            "The table holds one row per geometry. The first row is <b>base</b>, the project's own planform. Each cell states an override over it, and an empty cell keeps the project value. Use <b>Add variant</b> to copy the base row under a new label, then edit the copy. Use <b>Remove selected</b> to delete rows. The variation sweep builder turns one parameter into several rows at once: pick the parameter, give a Start, End and Count range or explicit values, and press <b>Build variants</b>. The builder validates each appended row against the project's own generator before it adds the row.",
            "The label is what names the geometry in the verdict chips, in the figures and in the exports, so give every variant a name that states its design idea.",
            "The <b>Conditions</b> page decides what every variant runs: the project's saved cases, one single condition built from four fields, or a sweep of one quantity. The estimate line states variants × cases = solves before anything runs.",
            "<b>Run comparison</b> solves every condition of every geometry on a worker thread, reports progress, and can be canceled. The verdict strip reads the first condition of each geometry. The ranking figure draws the chosen summary quantity for every geometry at the reference case. The overlay figure draws every curve across all conditions. <b>Export report</b> writes a self-contained HTML file with the full summary, and <b>Export CSV</b> writes one row per geometry per condition, both into the project's outputs folder.",
            "Comparison variants are not persisted. The table is rebuilt from the project's own geometry on every load, so a comparison worth keeping should be re-created deliberately or exported before closing. Design optimization is not part of this window: it runs as an outer loop from the command line or the library.",
        ],
        "anchor": "designer-variants",
    },
    "optimization_studies": {
        "title": "Optimization studies stored in this project",
        "body": [
            "A study is a persisted search problem: which quantities to drive, in which direction, over which bounded parameters, at one flight condition. It lives in inputs/optimizations.bemt beside the project and survives sessions.",
            "<b>New</b> appends an empty study with one objective and one variable as a starting point. <b>Duplicate</b> copies what is on screen under a new name, which is the cheap way to compare algorithms on the same problem. <b>Rename</b> changes only the name; <b>Delete</b> removes the study from the project after confirmation.",
            "The name labels the report, the front CSV and the evaluations CSV, so two studies never overwrite each other's artifacts.",
        ],
        "anchor": "cap-optimization",
    },
    "optimization_objectives": {
        "title": "Objectives — what better means",
        "body": [
            "An objective names one summary quantity and states its good direction. The first row is required; the second row is the switch between the two regimes of this window: an empty second box drives ONE quantity with the global search, a filled one evolves a whole <b>Pareto front</b> of designs no member of which dominates another.",
            "Domination rule: design A dominates B when A is at least as good on every objective and strictly better on one. The front is the set dominated by nobody. With constraints, any feasible design beats any infeasible one first.",
            "Usual pairs trade thrust against efficiency: FM against CT, or CP against CT. When both objectives agree on the same optimum, the honest answer is a single-point front — there is no trade-off on that rotor at that condition.",
        ],
        "anchor": "cap-opt-objectives",
    },
    "optimization_constraints": {
        "title": "Constraints — the designs the search may not keep",
        "body": [
            "Each row reads one summary quantity and requires it above (&ge;), below (&le;) or equal (=) to a value. Constraints are not penalties added to a fitness: a design that breaks one loses to every design that respects it, whatever the objectives say, and among violators the milder ones rank better.",
            "This keeps thresholds honest: a thrust floor either holds or it does not, and when nothing satisfied the constraints the outcome says so instead of dressing up the least-bad design as a success. Every front member reports its constraint values next to its objectives.",
        ],
        "anchor": "cap-opt-constraints",
    },
    "optimization_variables": {
        "title": "Design variables — the degrees of freedom",
        "body": [
            "Each row is one parameter the search may turn, with the range it may turn it over: planform generator inputs (root_chord_norm, tip_chord_norm, twist_root_deg, twist_tip_deg, max_chord_norm) or the direct fields n_blades, radius_m, root_cutout_norm.",
            "Bounds need finite numbers with lower below upper. The first population already spreads across the whole box, stratified, before evolution starts — so the search sees every corner at least once.",
            "Every variable multiplies the cost of seeing the box properly. Two or three variables are usually enough for a first study.",
        ],
        "anchor": "cap-opt-variables",
    },
    "optimization_search": {
        "title": "Search settings — condition, algorithm and budget",
        "body": [
            "<b>Condition</b> is the saved case every candidate is solved at; rotation is mandatory because the solver adimensionalizes by &Omega;R.",
            "<b>Algorithm</b>: NSGA-II evolves the whole front (tournament by the domination rules, then crossover and mutation); differential evolution drives the FIRST objective only through global difference vectors. The SBX crossover index &eta;<sub>c</sub>, the mutation index &eta;<sub>m</sub> and the mutation rate belong to NSGA-II and disable under DE. A rate of 0 means one over the variable count — the classic default, and the reason the population does not contract into a corner.",
            "<b>Population &times; (generations + 1)</b> is almost exactly the solver-call count; the estimate line states it before anything runs. The seed drives every random choice, so the same seed reproduces the same search exactly.",
        ],
        "anchor": "cap-opt-algorithm",
    },
    "optimization_run": {
        "title": "Pareto front, trade-off plot and exports",
        "body": [
            "The table lists one non-dominated design per row: variables first, then raw objective values, then constraint values. No row dominates another — that is what makes them the front.",
            "The Pareto view plots the two objectives against each other: every evaluated design as a faint grey point behind, the current front as a red line on top. Click a marker to select that design in the table. The parallel-coordinates view draws one polyline per member across every quantity normalized per axis — high where the member wins, low where it pays.",
            "<b>Export CSV</b> writes the front table; <b>Export report</b> writes the self-contained HTML report plus an evaluations CSV with every solve of the search, both named after the study.",
        ],
        "anchor": "cap-opt-run",
    },
    "stability_studies": {
        "title": "Derivative studies stored in this project",
        "body": [
            "A derivative study is a persisted perturbation plan (SC-14): which states and controls to nudge, about which trim point, with which finite-difference steps. It lives in inputs/derivatives.bemt beside the project.",
            "New/Duplicate/Rename/Delete behave exactly as on the Design Optimization window: duplicate is the cheap way to rerun the same plan with another step size or another trim.",
        ],
        "anchor": "cap-stability",
    },
    "stability_trim": {
        "title": "Trim point — the state everything is measured about",
        "body": [
            "A derivative is only meaningful once the reference state is fixed. Zero flapping solves both cyclic harmonics so the tip-path plane sits level at the trim point; Thrust solves collective to a target thrust; None keeps the controls exactly as saved.",
            "Run the trim ALONE first and read its controls and loads. A trim that surprises you will surprise every derivative built on top of it.",
            "A rotor whose blade has no flap freedom cannot use the zero-flapping trim — there is no flap angle to zero.",
        ],
        "anchor": "cap-stability-trim",
    },
    "stability_perturbations": {
        "title": "Perturbations — what is nudged, and by how much",
        "body": [
            "Each selected variable gets TWO solves per derivative (plus/minus the step), or FOUR when the Richardson half-step check is on: nine variables with the check cost thirty-six solves plus the trim. The estimate line states it before anything runs.",
            "Steps are stated per quantity in its own unit — 0.5 m/s for speeds, 0.02 rad/s for rates, 0.1 deg for pitch controls, half a percent of the trim rpm for &Omega; — because truncation error grows as h<sup>2</sup> while round-off shrinks as 1/h.",
            "With no flap freedom the rate and cyclic controls stay visible but disabled: they cannot act on a rigid blade.",
        ],
        "anchor": "cap-stability-steps",
    },
    "stability_results": {
        "title": "Matrix, sign checks and the optional vehicle model",
        "body": [
            "Outputs run down the rows, variables across the columns; hover a cell for its step and step-size error, and any cell whose two estimates differ by more than five percent turns red — trust its trend, not its digits.",
            "The SIGN CHECKS panel is why the window can be trusted: heave damping must be negative, pitch damping must be negative, thrust must rise with collective. A FAIL here means an engine sign flipped somewhere, not that your rotor is exotic.",
            "The optional vehicle block turns hub derivatives into rigid-body A/B matrices and draws their eigenvalues (one rotor only: no fuselage, tail or engine dynamics). Poles left of the axis are damped; red poles are unstable.",
        ],
        "anchor": "cap-stability-run",
    },
    "stability_export": {
        "title": "Export — the derivative matrix as a file",
        "body": [
            "Export writes what is already computed. It runs no solve and cannot change a derivative.",
            "The CSV file carries the matrix as it stands on screen: one row per output, one column per variable. The HTML report adds the trim point, the perturbation steps, the sign checks and the step-size error of every entry, which is what makes the numbers interpretable later. A matrix without its trim point and its steps is not.",
            "Run the study before exporting. With no result in the window there is nothing to write.",
        ],
        "anchor": "cap-stability-run",
    },
    "maneuver_studies": {
        "title": "Maneuvers stored in this project",
        "body": [
            "A maneuver is a persisted trajectory: a list of flight conditions in time, together with the sampling and march settings that turn the list into a run. It lives in inputs/maneuvers.bemt beside the project and survives the session.",
            "<b>New</b> appends a two-point trajectory as a starting point. <b>Duplicate</b> copies what is on screen under a new name, which is the cheap way to march the same trajectory with another sample interval. <b>Rename</b> changes only the name. <b>Delete</b> removes the maneuver from the project after confirmation.",
            "An edit in this window writes the maneuver back into the project at once and marks the project unsaved. Saving the project is the separate step that puts the maneuver on disk.",
        ],
        "anchor": "cap-transiente",
    },
    "maneuver_points": {
        "title": "Trajectory points — the prescribed flight condition in time",
        "body": [
            "Each row is one node of the trajectory: the time, the in-plane advance ratio, the axial speed, the collective, the two cyclic harmonics and the rotational speed. Together the columns fix the whole flight condition at that instant.",
            "The rows are nodes, not samples. Their times must increase strictly, and the sampler builds the uniform grid between them. Therefore the table states the shape of the input, and the Sampling and march block states the resolution it is read at.",
            "A node without a rotational speed inherits the nearest earlier value, so the first node must carry one: the inflow march non-dimensionalizes by &Omega;R and cannot start without a rotation.",
            "<b>Add point</b> appends a node half a second after the last one. <b>Remove selected</b> deletes the selected rows. A row that is still half typed is skipped until every one of its cells holds a number.",
        ],
        "anchor": "cap-transiente",
    },
    "maneuver_build": {
        "title": "Build from two saved cases — a ramp between known conditions",
        "body": [
            "This block writes the trajectory from two conditions the project already holds, which is faster and safer than typing the nodes by hand. Select a start case, an end case and a duration, then press <b>Build ramp</b>.",
            "The result is a two-node trajectory: the start condition at the origin of time, and the end condition after the duration plus a short hold. The hold is a quarter of the duration, up to half a second, and it keeps both boundary conditions visible in the time history.",
            "Building a ramp replaces the whole point table. When the end case carries no rotational speed, the start case supplies it.",
        ],
        "anchor": "cap-transiente",
    },
    "maneuver_march": {
        "title": "Sampling and march — how the trajectory becomes a run",
        "body": [
            "These settings turn the trajectory into a solve. The sampler resamples the nodes onto a uniform grid, and the march integrates the three Pitt-Peters inflow states along that grid. Every sample inherits the state of the sample before it, so the three states are the marched degrees of freedom.",
            "<b>Interpolation</b> decides how a sample reads the trajectory between two nodes. Linear blends every quantity between the neighboring nodes. Hold keeps the value of the last node whose time is not past, which is what a step input needs.",
            "<b>Sample interval</b> is the output resolution: one sample is one row of the time history and one disk map. <b>Sub-steps per sample</b> refine the integration inside one sample without adding rows. The inflow states are stiff, therefore the march integrates them with an exponential step that stays stable at a coarse sub-step count.",
            "<b>Initial state</b> decides where the march starts. Equilibrium solves the steady inflow at the first sample, so no start-up transient appears. Zero starts the three states from zero and shows the transient decay, which is the honest choice when the first sample is not a settled condition.",
            "<b>March dynamic stall</b> threads the Øye separation state from sample to sample instead of restarting it at every sample, so separation stays continuous along the trajectory. <b>March flapping</b> solves the periodic flap response at every sample and feeds the motion into the loads. That response stays quasi-steady inside one sample, therefore the march does not resolve the flap mode itself. Each control needs its own model enabled on the Airfoil tab or on the Geometry tab, and stays visible and disabled otherwise.",
        ],
        "anchor": "cap-transiente",
    },
    "maneuver_cost": {
        "title": "Cost estimate — the size of the march before it runs",
        "body": [
            "The line states the sample count times the sub-steps per sample, which is almost exactly the number of solver calls the march makes. It is arithmetic on the settings above and runs no physics.",
            "Both factors are cheap to change and expensive to ignore. Halving the sample interval doubles the samples, and doubling the sub-steps doubles the calls again. Read the number before you press <b>Run maneuver</b>.",
        ],
        "anchor": "cap-transiente",
    },
    "maneuver_validation": {
        "title": "Validation — the static findings for this trajectory",
        "body": [
            "The panel lists what can be checked without a solve, in the same style as the Config tab. It re-reads the form after every edit.",
            "An <b>error</b> is a condition the march cannot start from: fewer than two nodes, times that do not increase strictly, no rotational speed from the first node onward, or a sample interval that is not positive. A sample interval larger than the shortest interval between two nodes is an error for the same reason: the grid would step over a node and lose part of the prescribed input.",
            "A <b>warning</b> states a consequence and leaves the decision to you. A trajectory shorter than about five rotor revolutions does not give the inflow states time to shed their initial condition, so a start-up transient remains in the result. A marched separation state on a fine azimuthal mesh costs one sequential step per azimuthal station, which is what makes such a run expensive.",
        ],
        "anchor": "cap-transiente",
    },
    "maneuver_preview": {
        "title": "Trajectory preview — the sampled input, not the table",
        "body": [
            "The figure draws the in-plane component and the axial speed of every sample against time. It shows the grid the march will read, therefore an interpolation or a sample interval that misrepresents the intended input is visible here before any solver time is spent.",
            "The two interpolation rules look different on purpose: Hold draws a staircase and Linear draws straight segments between nodes.",
            "A trajectory that cannot be sampled states the reason in place of the curve. The usual cause is a missing rotational speed or a node order that the Validation panel already reports.",
        ],
        "anchor": "cap-transiente",
    },
    "maneuver_history": {
        "title": "Time history — one row per sample",
        "body": [
            "The table holds the marched result: the time, the load coefficients, the three inflow states, the collective, the interval the march actually integrated and the sub-step count of that step.",
            "The three states describe the whole inflow field of Pitt-Peters, with x = r/R:"
            "\n\n"
            r"$$\lambda_i(r,\psi) = \nu_0 + \nu_c\,x\cos\psi + \nu_s\,x\sin\psi$$"
            "\n\n"
            "&nu;<sub>0</sub> is the uniform part and &nu;<sub>c</sub> and &nu;<sub>s</sub> the two first-harmonic tilts of the disk.",
            "Reading the states across time is reading the lag of the wake. The apparent-mass terms of the Pitt-Peters system give the disk a time constant of its own, so the inflow does not follow a control input at once and the loads answer the input late. A steady solve at the same condition cannot show that delay, because it assumes the states already settled.",
            "The marched interval and the sub-step count are recorded per row so that the result stays interpretable later. <b>Export CSV</b> writes this table. <b>Export report</b> writes the self-contained HTML report of the whole maneuver.",
        ],
        "anchor": "cap-transiente",
    },
    "maneuver_disk_map": {
        "title": "Disk map at sample — where the transient happened",
        "body": [
            "The map draws the induced inflow &lambda;<sub>i</sub> over the disk at one sample of the march. The spin box selects the sample index, so stepping through it walks the transient in space.",
            "The time history states what the integrated loads did. This map states where on the disk they did it. During a transient the first harmonic of the inflow lags the input, therefore the tilt of the field here is not the tilt a steady solve at the same condition returns.",
            "One map exists per sample, so the sample interval also sets how finely the transient can be examined in space.",
        ],
        "anchor": "cap-transiente",
    },
}
