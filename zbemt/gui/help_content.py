"""Rich contextual help content by field (Layer 3 of the documentation plan).

Each entry corresponds to a field from BEMTConfig, AirfoilDef, RotorGeometryDef,
or FlightCondition. The popup shows title, definition, unit, equation, effect,
and typical range. Enum fields also list each option with a short description.
"""
from __future__ import annotations

FIELD_HELP: dict[str, dict] = {
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
            "'rectangular' keeps a single constant chord; 'tapered' "
            "interpolates linearly between a root and a tip chord; "
            "'elliptic' follows an elliptic planform, which minimizes "
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
        "equation": "origin ∈ {preset, import, manual} (metadata only)",
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
            "analytical": "Polynomial analytical model with stall transition. Fast and smooth, best for preliminary design.",
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
            "viterna": "Viterna-Corrigan model with curvature. It extends to ±90° if enabled and is the most physically grounded choice for high α and reverse flow."
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
                "Robust and idealized; discards the airfoil's own polar where it "
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
            "governed only by the flow NORMAL to the span, but that spanwise "
            "component still sweeps the boundary layer and changes its drag."),
        "unit": '',
        "equation": r"U_R = V_x\cos\psi,\qquad C_d \leftarrow C_d\,f(\chi)",
        "effect": (
            'This acts on DRAG only. It does not change lift, does not add a '
            'wake state, and does not solve a radial momentum equation. So it '
            'moves torque and power, and barely moves thrust.\n\n'
            'In ROTOR mode it is identically zero in hover (V<sub>x</sub> = 0, so no '
            'spanwise component) and grows with the in-plane advance ratio '
            'μ<sub>x</sub>, varying once per revolution around the disc with its peaks '
            'on the advancing and retreating sides.\n\n'
            'In PROPELLER mode, in straight cruise, it is inactive: the '
            'in-plane component there is the cross-flow and that is zero.'),
        "range": 'off/on',
        "options": None
    },
    "radial_flow_max_skew_deg": {
        "title": 'Radial-flow saturation skew angle',
        "definition": (
            'The wake skew angle chi at which the radial-flow correction stops '
            'growing.\n\n'
            'Skew compares the IN-PLANE advance ratio μ<sub>x</sub> with the total '
            'inflow along the shaft λ<sub>total</sub>, so it measures how far the '
            'wake has been tilted away from the shaft: chi = 0 in hover, and it '
            'approaches 90 deg as the wake is swept back into the disc plane at '
            'high in-plane speed.'),
        "unit": 'deg',
        "equation": r"\chi = \arctan\dfrac{\mu_x}{\lambda_{total}},\qquad f(\chi)=f(\chi_{max})\ \ (\chi>\chi_{max})",
        "effect": (
            'It sets where the correction plateaus, so it is a ceiling on how '
            'much drag the spanwise flow may add. Raising it lets the '
            'correction keep growing further into high-speed flight (more '
            'profile power predicted there); lowering it caps the effect '
            'earlier.\n\n'
            'It changes nothing in hover, where the skew is zero, and nothing '
            'below the chosen angle. Only the high-μ<sub>x</sub> end of a sweep '
            'moves.'),
        "range": '30-90 deg',
        "options": None
    },
    "pitt_peters_states": {
        "title": "Pitt-Peters States",
        "definition": (
            "Number of dynamic inflow states in the Pitt-Peters model.\n\n"
            "More states increase fidelity but computational cost; typical "
            "values 1, 2, or 4."),
        "unit": "—",
        "equation": r"\nu = (\nu_0, \nu_s, \nu_c)",
        "effect": "Increasing state count improves dynamic response accuracy, especially for transient maneuvers and control inputs.",
        "range": "1–4",
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
            "bisection": "Bracketing method. Guaranteed convergence but slowest, so it is used for safety.",
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
            "λ<sub>i</sub>,new = λ<sub>i</sub>,old + ω·Δlambda_i.\n\n"
            "Typically 0–1; stabilizes oscillatory convergence."),
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
        "equation": "Azimuth factor applied when criterion > threshold",
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
        "title": "Hinge Offset",
        "definition": (
            "Distance of the flap (and lag) hinge from the shaft, as a "
            "fraction of the radius.\n\n"
            "It stiffens the flap mode and opens the structural path that "
            "carries part of the blade load into the hub as a moment."),
        "unit": "r/R",
        "equation": r"\nu_\beta^{2} = 1 + \tfrac{3}{2}\,\dfrac{e}{1-e} + \dfrac{K_\beta}{I_\beta\Omega^{2}}",
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
        "equation": r"\nu_\zeta^{2} = \tfrac{3}{2}\,\dfrac{e}{1-e} + \dfrac{K_\zeta}{I_\zeta\Omega^{2}}",
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
        "equation": r"U_T \mathrel{+}= (r-eR)\,\dot\zeta",
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
}
