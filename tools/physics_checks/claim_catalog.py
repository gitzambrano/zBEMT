"""Store claim-specific references, rules, routes, and requirements."""
from __future__ import annotations


_REFERENCE_AND_RULE = {
    "BEMT-C1": (
        "Uniform-inflow blade-element theory gives a closed hover thrust coefficient.",
        "Accept when the computed thrust coefficient differs from the closed form by at most 0.7%.",
    ),
    "BEMT-C2": (
        "Published rotor data place hover figure of merit between 0.6 and 0.8, with induced-power factor at least one.",
        "Accept when figure of merit is 0.6 to 0.8 and the induced-power factor is at least 1.0.",
    ),
    "BEMT-C3": (
        "Equal solidity gives equal ideal loading when blade count and chord change inversely.",
        "Accept when two blades at full chord and four blades at half chord differ in thrust coefficient by at most 0.01%.",
    ),
    "BEMT-C4": (
        "The Prandtl tip and root factor is the published arccosine loss expression evaluated with the local inflow angle.",
        "Accept when the element factors match the closed form within 1e-12 and both losses reduce hover thrust.",
    ),
    "BEMT-C5": (
        "The Prandtl-Glauert correction increases section coefficients by the inverse compressibility factor below its Mach limit.",
        "Accept when enabling compressibility at tip Mach 0.55 increases integrated thrust by 5% to 12% and stays finite.",
    ),
    "BEMT-C6": (
        "The radial-flow drag reference is the EN-10 closed form for in-plane force and profile power.",
        "Accept when the force and power coefficients differ from both EN-10 closed forms by at most 3% and torque does not change.",
    ),
    "BEMT-C7": (
        "Constant profile drag gives the published profile-power factors 1 plus advance-ratio squared and 1 plus 1.5 times that square.",
        "Accept when both measured power ratios differ from their closed forms by at most 5%.",
    ),
    "BEMT-C8": (
        "Momentum theory requires descent to reduce thrust and induced inflow while increasing total axial inflow at fixed pitch.",
        "Accept when the axial sweep is finite, continuous, and monotonic in all three stated directions.",
    ),
    "BEMT-C9": (
        "All converged numerical solvers resolve the same annular momentum residual.",
        "Accept when fixed-point, Newton, bisection, and Aitken thrust coefficients span at most 0.05% at an advance ratio of 0.15.",
    ),
    "BEMT-C10": (
        "A continuous reverse-flow model has no physical load discontinuity where tangential velocity changes sign.",
        "Accept when each reverse-flow model has a load jump no larger than 0.5% of its peak load across the boundary.",
    ),
    "BEMT-C11": (
        "The Himmelskamp and Snel correction acts only on stalled rotating sections and raises their lift toward the attached line.",
        "Accept when the option changes hover lift by zero at 18 degrees and raises mean stalled-root lift at advance ratio 0.20.",
    ),
    "BEMT-C12": (
        "Compressibility belongs to the blade-element state and the analytical polar remains Mach independent.",
        "Accept when direct analytical-polar coefficients are identical at Mach 0 and 0.6 while the engine correction remains active.",
    ),
    "BEMT-G6": (
        "Non-dimensional BEMT coefficients are invariant under density and shaft-speed scaling when compressibility is disabled.",
        "Accept when thrust and torque coefficients agree to 1e-12 across density 0.9 and 1.225 and speed 200 to 800 RPM.",
    ),
    "BEMT-H1": (
        "A consistent spatial discretization approaches one limit as its radial and azimuthal meshes are refined.",
        "Accept when thrust coefficient changes monotonically and the final two meshes differ by at most 0.5%.",
    ),
    "BEMT-H2": (
        "The rotor angle is minus the arctangent of axial over in-plane speed, and the disk angle uses the same geometric angle.",
        "Accept when both reported angles match the shared geometric identity within 0.001 degree.",
    ),
    "DERIV-A1": (
        "Hover rotational invariance must hold for every tested Lock number and hinge offset.",
        "Accept when both matrix invariance residuals are at most 1e-6 for Lock numbers 4, 8, and 16 and offsets 0.02 to 0.10.",
    ),
    "DERIV-A2": (
        "Hover heave damping is independent of flap freedom, while a failed flap iteration invalidates forward-flight derivatives.",
        "Accept when hover values agree within 0.1% and every non-converged forward case is reported as inconclusive.",
    ),
    "DERIV-A3": (
        "Forward flight makes articulated aerodynamic damping anisotropic while a rigid rotor remains nearly symmetric at low advance ratio. An offset hinge adds a separate structural hub moment.",
        "Accept when rigid total damping terms differ by at most 1%, flap aerodynamic pitch damping is smaller in magnitude at advance ratio 0.10, and the flap total equals the aerodynamic and hub terms.",
    ),
    "DERIV-A4": (
        "Thrust and torque increase with shaft speed at fixed collective in hover.",
        "Accept when both finite-difference derivatives with respect to RPM are strictly positive.",
    ),
    "DERIV-A5": (
        "Stability derivatives require a converged flap equilibrium at the base and perturbed conditions.",
        "Classify a derivative as usable only when every flap solve satisfies its declared outer-loop tolerance; otherwise classify it as inconclusive.",
    ),
    "DERIV-E1": (
        "Axisymmetry requires equal diagonal rate terms and opposite off-diagonal terms for the hover hub-moment matrix.",
        "Accept when both rotational-invariance residuals are at most 1e-6 at 600 RPM.",
    ),
    "DERIV-E2": (
        "A flapping derivative study is valid only after the outer harmonic-balance loop reaches its declared tolerance.",
        "Accept when every case at advance ratios 0.15, 0.20, and 0.25 has a residual at most 1e-4 degree before 30 iterations.",
    ),
    "DERIV-E3": (
        "A thrust-trim derivative study needs a bracket that contains the requested thrust.",
        "Accept when the advance-ratio 0.20 study either completes inside its declared bracket or returns a named bracket error without a partial matrix.",
    ),
    "DERIV-H5": (
        "Classical fixed-pitch rotor trends give positive forward-speed thrust derivative, negative torque derivative, and negative descent thrust derivative.",
        "Accept when all three finite-difference derivative signs match the stated physical trends at advance ratio 0.10.",
    ),
    "DERIV-NONDIM-RATES": (
        "A non-dimensional angular-rate derivative uses rate divided by shaft speed and therefore includes one shaft-speed factor.",
        "Accept when the reported non-dimensional p and q derivatives equal the dimensional values times shaft speed divided by their load scales within 0.1%.",
    ),
    "DERIV-P1": (
        "Coupled uniform-inflow theory predicts hover heave damping near minus 35 newtons per meter per second for the reference rotor.",
        "Accept when measured hover heave damping is negative and within 15% of minus 35 N/(m/s).",
    ),
    "DERIV-P2": (
        "Articulated-rotor theory gives pitch damping equal to minus flap inertia times shaft speed times Lock number divided by eight.",
        "Accept when the measured pitch damping is negative and within 5% of the minus 20.2 N m/(rad/s) reference.",
    ),
    "DERIV-P3": (
        "Hover axisymmetry makes direct roll and pitch damping equal.",
        "Accept when the two direct damping derivatives differ by at most 0.1% for both rigid and flapping blades.",
    ),
    "DERIV-P4": (
        "A rigid hovering rotor has an isotropic in-plane rate matrix with negligible cross-axis terms.",
        "Accept when direct damping terms agree within 0.1% and both cross-axis terms are below 1e-6 in magnitude.",
    ),
    "DERIV-P5": (
        "Hover rotational invariance requires equal diagonal cyclic-control terms and opposite off-diagonal terms.",
        "Accept when both cyclic-control invariance residuals are at most 1e-6.",
    ),
    "DERIV-P6": (
        "Physical damping derivatives are negative, while thrust derivatives with respect to collective and shaft speed are positive.",
        "Accept when every listed derivative has the prescribed sign and no value is numerically zero.",
    ),
    "DERIV-P7": (
        "Articulated flap freedom relieves the uncoupled aerodynamic pitch and roll damping in hover. Forward flight has a coupled damping matrix and does not require each direct term to decrease.",
        "Accept when both aerodynamic damping magnitudes decrease in hover. Record the coupled matrix at advance ratio 0.20 without an individual monotonic ordering.",
    ),
    "DS-A1": (
        "A constant static separation state is an exact fixed point of both Oye solution methods.",
        "Accept when both methods return the static separation state with absolute error at most 1e-12.",
    ),
    "DS-A2": (
        "A first-order lag has amplitude 1 divided by the square root of one plus reduced frequency squared and phase equal to its arctangent.",
        "Accept when numerical amplitude and phase each differ from the analytical transfer function by at most 1e-4.",
    ),
    "DS-A3": (
        "A larger Oye time constant reduces sinusoidal amplitude and increases phase lag.",
        "Accept when the A equals 40 response is smaller and later than the A equals 8 response and matches theory within 1e-4.",
    ),
    "DS-A4": (
        "The Oye step response is an exponential with its declared time constant.",
        "Accept when the time-march step response differs from the exponential solution by at most 1e-12.",
    ),
    "DS-A5": (
        "A settled periodic separation state has a residual that decreases with each marched revolution.",
        "Accept when the residual decreases from two to four revolutions and a value above 1e-3 emits a warning.",
    ),
    "DS-A6": (
        "A maneuver passes the final separation state of one sample into the next sample without a reset.",
        "Accept when a march initialized from the preceding final state has an initial residual at most 1e-12.",
    ),
    "DS-A7": (
        "Constant angle of attack in hover produces no dynamic-stall hysteresis.",
        "Accept when enabling either dynamic-stall method changes hover thrust coefficient by at most 1e-12.",
    ),
    "DS-A8": (
        "The frequency Oye method is a dominant-harmonic approximation of the time-marched first-order separation dynamics. They agree near hover and can separate when higher harmonics grow in forward flight.",
        "Accept when their thrust coefficients differ by less than 1% at advance ratios 0.02 and 0.05, remain finite at 0.20, and the 0.20 difference exceeds the 0.05 difference.",
    ),
    "DS-A9": (
        "Delayed separation carries more lift on pitch-up than on pitch-down at the same stalled angle.",
        "Accept when pitch-up lift exceeds pitch-down lift at 18 degrees and the hysteresis loop has the expected direction.",
    ),
    "DS-A10": (
        "A causal separation response trails the static separation input, with more lag where local relative speed is lower.",
        "Accept when the dynamic minimum follows the static minimum and root lag exceeds tip lag.",
    ),
    "DS-A11": (
        "Dynamic-stall lift reaches its peak after static stall begins but before the angle-of-attack peak.",
        "Accept when the lift-peak azimuth lies strictly between those two reference azimuths.",
    ),
    "DS-A12": (
        "The Oye model produces a bounded lift overshoot during delayed separation.",
        "Accept when peak dynamic lift exceeds static lift by 5% to 25% and remains finite.",
    ),
    "DS-A13": (
        "Dynamic post-stall drag remains non-negative and rises relative to the static polar during delayed separation.",
        "Accept when drag is non-negative everywhere and mean dynamic-to-static post-stall drag is at least 1.0.",
    ),
    "DS-A14": (
        "The documented fade window restores the static polar at angles beyond 55 degrees.",
        "Accept when lift and drag outside plus or minus 55 degrees equal the static polar within 1e-12.",
    ),
    "DS-A15": (
        "Increasing the Oye time constant increases the separation-state lag at engine level.",
        "Accept when root-mean-square lag rises monotonically for A values 2, 8, and 20.",
    ),
    "DS-A16": (
        "A separation lag changes integrated thrust and power by a bounded percentage at moderate advance ratio.",
        "Accept when the advance-ratio 0.20 changes in thrust and power are each between 0% and 5%.",
    ),
    "DS-A17": (
        "The discrete exponential recursion and the continuous frequency transfer function are distinct approximations.",
        "Accept when the documented synthetic case differs by approximately 0.0024 and each method matches its own analytical form.",
    ),
    "DS-A18": (
        "A disabled airfoil section uses the static polar, while radial interpolation blends the enabled weight between sections.",
        "Accept when the disabled station has zero correction and the interpolation station retains approximately 12% of the enabled correction.",
    ),
    "DS-H4": (
        "A collective ramp with dynamic stall retains state continuity and produces more lift on the rising branch at equal collective.",
        "Accept when all 41 samples remain continuous and rising-branch thrust exceeds falling-branch thrust at 13 degrees.",
    ),
    "DS-D3-HYSTERESIS-DIRECTION": (
        "Delayed separation keeps element lift above the static value through the stalled portion of the azimuth cycle.",
        "Accept when at least 70% of stalled elements gain lift and their mean lift increment is at least 0.10.",
    ),
    "DS-D3B-FADE-50": (
        "The focused fade check expects the static polar outside plus or minus 50 degrees.",
        "Accept when lift outside plus or minus 50 degrees differs from the static polar by at most 1e-12.",
    ),
    "DS-MANEUVER-REPORTING": (
        "EN-9 requires the maneuver history and the periodic residual for every marched sample.",
        "Accept when history dimensions include revolution, radius, and azimuth and every sample reports its periodic residual.",
    ),
    "EXT-D1": (
        "A physical axial sweep remains finite and continuous through the vortex-ring velocity band.",
        "Accept when thrust coefficient is finite and monotonic from minus 12 to plus 20 meters per second.",
    ),
    "EXT-D2": (
        "Strong climb can reduce numerical convergence without invalidating every converged element.",
        "Accept as a limitation when the result reports its convergence percentage and finite loads, regardless of whether the stated source fixture reaches 90%.",
    ),
    "EXT-D3": (
        "Rotor and propeller coefficient conventions are related by fixed normalization identities.",
        "Accept when both normalization identities agree to 1e-12 for the same dimensional loads.",
    ),
    "EXT-D4": (
        "EN-11 permits the documented 99.5% warning threshold but requires a warning below it.",
        "Accept when 99.9% convergence emits no warning and any value below 99.5% emits one.",
    ),
    "EXT-D5": (
        "Autorotation makes torque cross zero before the deeply descending windmill state.",
        "Accept only after the source rotor, pitch, and descent convention reproduce the stated torque transition; a different fixture is not evidence of a defect.",
    ),
    "EXT-D6": (
        "Propeller efficiency starts at zero, reaches one positive peak, and returns to zero at the windmill boundary.",
        "Accept when efficiency remains between zero and one and has one peak before thrust changes sign.",
    ),
    "FLAP-E1": (
        "Offset-hinge theory gives flap frequency squared equal to one plus 1.5 times offset divided by one minus offset.",
        "Accept when frequency squared matches the closed form within 1e-12 for offsets 0.02, 0.05, 0.10, and 0.15.",
    ),
    "FLAP-E2": (
        "EN-8 requires rejection when a requested harmonic equals the undamped flap natural frequency.",
        "Accept when the central-hinge first-harmonic case returns a named resonance error and no flap solution.",
    ),
    "FLAP-E3": (
        "A loaded articulated rotor in hover has positive coning and negligible first harmonics and hub moments.",
        "Accept when coning is positive, first harmonics are below 1e-6 degree, and hub moments are below 1e-12.",
    ),
    "FLAP-E4": (
        "Forward-flight dissymmetry produces aft blowback and a positive longitudinal tip-path-plane tilt.",
        "Accept when aft flap exceeds forward flap and longitudinal tilt is positive at advance ratio 0.15.",
    ),
    "FLAP-E5": (
        "A first-harmonic flap response occurs approximately 90 degrees after a cyclic pitch input.",
        "Accept when one degree of longitudinal cyclic produces a dominant orthogonal flap harmonic and the secondary harmonic is below 20%.",
    ),
    "FLAP-E6": (
        "Positive delta-3 coupling reduces pitch as the blade flaps up and therefore reduces coning.",
        "Accept when 30 degrees of coupling lowers coning relative to zero coupling at the same hover condition.",
    ),
    "FLAP-E7": (
        "Pitch and roll rates excite orthogonal first flap harmonics with symmetric magnitude and rate-reversal signs.",
        "Accept when reversing each rate reverses its dominant harmonic and pitch-roll magnitudes agree within 15%.",
    ),
    "FLAP-E8": (
        "Free flapping absorbs first-harmonic cyclic loading and relieves fixed-hub moments.",
        "Accept when enabling flap freedom reduces both cyclic hub-moment magnitudes at the same condition.",
    ),
    "FLAP-E9": (
        "The rigid blade-dynamics path must preserve the plain BEMT solution.",
        "Accept when every scalar result and array is bit-identical between the rigid dynamics path and the plain solve.",
    ),
    "FLAP-E10": (
        "The rigid dynamics contract advertises zero-valued flap result keys for downstream consumers.",
        "Accept when every documented flap key exists and contains zero on the rigid path.",
    ),
    "FLAP-E11": (
        "Bisection trim must reach a declared thrust target through collective or RPM.",
        "Accept when both trim modes reach 20000 N within 2 N and report the solved degree of freedom.",
    ),
    "FLAP-E12": (
        "Every trim path must record its target, degree of freedom, residual, and convergence state.",
        "Accept when all four fields exist for a successful bisection trim and a trim limited to one iteration records trim_converged as false instead of silently returning an unmarked candidate.",
    ),
    "FLAP-G4": (
        "A root spring adds spring stiffness divided by flap inertia and shaft speed squared to flap frequency squared.",
        "Accept when the computed frequency matches the closed form within 1e-12 for three spring stiffness values.",
    ),
    "FLAP-G5": (
        "Lead-lag frequency combines offset-hinge centrifugal stiffness and root-spring stiffness.",
        "Accept when the computed lead-lag frequency squared matches the closed form within 1e-12.",
    ),
    "FLAP-G5B": (
        "A requested lead-lag freedom must run or fail validation; it must not disappear when the flap model is rigid.",
        "Accept when the rigid-flap and enabled-lag combination returns a validation error before execution.",
    ),
    "FLAP-H3": (
        "Cyclic flapback trim drives both first flap harmonics to zero and increases compensating cyclic with advance ratio.",
        "Accept when both harmonics are within 0.001 degree and cyclic magnitude rises from advance ratio 0.05 to 0.15.",
    ),
    "FLAP-H3B": (
        "Three-degree-of-freedom trim holds thrust while driving both first flap harmonics to zero.",
        "Accept when the mode completes without an exception, meets the thrust tolerance, and leaves both harmonics within 0.001 degree.",
    ),
    "FLAP-H3C": (
        "Flapback trim must report a clear failure when it cannot meet tolerance inside the iteration limit.",
        "Accept when one iteration at advance ratio 0.15 returns a named convergence error and 120 iterations converge.",
    ),
    "LAG-CORIOLIS-LIMITATION": (
        "The current lead-lag oscillator omits Coriolis coupling to flap motion.",
        "Classify the claim as an out-of-scope limitation only when the result and documentation identify the omitted coupling without claiming a full lead-lag model.",
    ),
    "MODEL-G1": (
        "The four stall models have distinct published full-angle lift shapes.",
        "Accept when linear is unbounded, clip clamps, enhanced decays, and Viterna approaches its full-angle plateau at 35 degrees.",
    ),
    "MODEL-G2": (
        "Deep reverse-flow models remain finite and the flat-plate option uses its declared drag coefficient.",
        "Accept when thrust-coefficient spread is at most 1% at advance ratio 0.60 and flat-plate drag equals 1.90.",
    ),
    "MODEL-G3": (
        "The protected Prandtl-Glauert correction grows monotonically and remains finite below Mach 0.95.",
        "Accept when thrust increases monotonically from Mach 0.7 to 0.95 and every result remains finite.",
    ),
    "PP-B1": (
        "Pitt-Peters hover equilibrium reduces to actuator-disk momentum theory.",
        "Accept when uniform inflow divided by the square root of half thrust coefficient differs from one by at most 1e-5.",
    ),
    "PP-B2": (
        "A constant-condition Pitt-Peters march must settle on its algebraic steady fixed point.",
        "Accept when all three inflow states differ by at most 1e-6 after 20 revolutions at advance ratios 0, 0.05, and 0.15.",
    ),
    "PP-B3": (
        "Small-perturbation decay follows the eigenvalues of the finite-difference Pitt-Peters Jacobian.",
        "Accept when measured and predicted dominant decay rates differ by at most 5%.",
    ),
    "PP-B4": (
        "A collective step produces dynamic-inflow overshoot and then settles on the new steady equilibrium.",
        "Accept when thrust overshoot is positive and final thrust differs from the new steady value by at most 0.001%.",
    ),
    "PP-P5-ASYMMETRY": (
        "Forward-flight Pitt-Peters inflow has the same fore-aft harmonic pattern as the Drees reference field.",
        "Accept when field correlation is at least 0.75 and both fields place their maximum at the same azimuth station.",
    ),
    "PP-P6-THRUST": (
        "Pitt-Peters and Drees are different low-order inflow parameterizations. Their load difference is a model-form comparison, not an implementation-equivalence test.",
        "Accept as not reproduced when both models run finite cases with their documented parameterizations; compare against experiment before choosing a preferred model.",
    ),
    "PP-B5-COMBINED": (
        "The baseline compares both Pitt-Peters field phase and integrated thrust with the Drees model.",
        "Accept when field correlation is at least 0.75, maxima share one azimuth station, and thrust differs by at most 4%.",
    ),
    "PP-B6": (
        "The protected hover seed must converge the Pitt-Peters outer iteration from momentum inflow.",
        "Accept when hover reaches its declared residual tolerance in at most 15 outer iterations.",
    ),
    "PP-B7": (
        "Steady and marched Pitt-Peters equations must use the same wind-axis rotation at nonzero sideslip.",
        "Accept when all inflow states agree within 1e-6 after a constant march at 30 degrees of sideslip.",
    ),
    "PP-B8": (
        "A prescribed RPM step changes Pitt-Peters state through its differential equation without resetting the state.",
        "Accept when the state at the RPM boundary is continuous to the maneuver time-step tolerance.",
    ),
    "PP-B9": (
        "EN-9 requires interval, substep count, and periodic residual for a marched Pitt-Peters state.",
        "Accept when all three fields exist for every maneuver sample and an unsettled state is not marked converged.",
    ),
    "PP-B10": (
        "Eight exponential substeps per maneuver step are conservative because each frozen linear system is integrated exactly.",
        "Accept as a documented limitation when one and eight substeps remain finite and converge to the same steady state within 1e-6.",
    ),
    "PP-G7": (
        "A sideslip angle rotates the Coleman and Drees harmonic inflow pattern by the opposite azimuth angle.",
        "Accept when 30 degrees of sideslip moves the field maximum by minus 30 degrees within one azimuth cell.",
    ),
    "PP-GAIN-L": (
        "The Pitt-Peters gain matrix uses the published half-wake-angle form.",
        "Accept when every gain-matrix element matches the Peters closed form within 1e-12 over the tested inflow-angle range.",
    ),
    "PP-LINEAR-LIMITATION": (
        "Pitt-Peters is a linear finite-state inflow theory and can produce local reverse total inflow at high loading.",
        "Classify the claim as a model limitation only when the reversed-flow fraction is reported and no value is silently clamped.",
    ),
    "PP-MASS-FLOW": (
        "The harmonic mass-flow parameter equals twice uniform inflow in hover and approaches total velocity in fast forward flight.",
        "Accept when both limiting relations agree with the implemented matrix within 1e-12.",
    ),
    "PP-MASS-MATRIX": (
        "Pitt-Peters apparent mass uses the published diagonal constants 128/(75 pi) and 16/(45 pi).",
        "Accept when all diagonal terms match the published constants within 1e-12 and every off-diagonal term is zero.",
    ),
    "PP-PHASE-CONVENTION": (
        "The harmonic-state phase depends on the documented hub-axis convention while integrated thrust remains invariant.",
        "Accept as a convention limitation when the state-to-axis mapping is documented and a phase rotation leaves thrust unchanged within 1e-12.",
    ),
    "PP-STEADY-MARCH-AUDIT": (
        "The audit combines the algebraic Pitt-Peters equilibrium, its 20-revolution march, and the hover momentum limit.",
        "Accept when the marched state matches equilibrium within 1e-6 after 20 revolutions and hover inflow matches momentum theory to six significant figures.",
    ),
    "PROP-FA": (
        "At zero skew, Pitt-Peters removes its harmonic states but retains a uniform finite-state mean inflow. It need not equal the annular local Glauert solution for a nonuniform blade.",
        "Accept as not reproduced when the Pitt-Peters hover state satisfies its momentum identity and the remaining difference is only against a differently parameterized local model.",
    ),
    "PROP-FB": (
        "Prandtl-Glauert theory is invalid near sonic helical Mach and must be bounded or rejected before divergence.",
        "Accept when a tip Mach above 0.85 produces a named range warning or a documented bounded correction rather than unbounded thrust growth.",
    ),
    "PROP-G8": (
        "Pre-stall oblique propeller loading can rise mildly with cross-flow angle.",
        "Accept as a reference observation when thrust remains finite and changes smoothly from 0 to 83 degrees of disk angle.",
    ),
    "PROP-K1": (
        "The induced-power factor compares actual induced speed with the ideal momentum solution.",
        "Accept when the induced-power factor is 1.0 to 1.15 and decreases monotonically from static to advance ratio 1.2.",
    ),
    "PROP-K3": (
        "Skew-only, reverse-flow, and dynamic-stall corrections have no effect in a steady purely axial attached-flow case.",
        "Accept when each option changes thrust and power coefficients by at most 1e-12 at advance ratio 0.8.",
    ),
    "PROP-K4": (
        "A converged axial or first-harmonic oblique propeller solution is insensitive to further azimuthal refinement.",
        "Accept when 12, 36, and 72 azimuth stations change thrust coefficient and normal force by at most 0.01%.",
    ),
    "PROP-K5": (
        "Deep-stall lift ordering follows the definitions of linear, clip, Viterna, and enhanced polar extensions.",
        "Accept when thrust orders linear above clip above Viterna above enhanced at 20 degrees collective.",
    ),
    "PROP-K6": (
        "The zero-lift drag contribution to profile power is linear in the zero-lift drag coefficient.",
        "Accept when the profile-power increment per drag-coefficient increment is constant within 1% across 0.004 to 0.016.",
    ),
    "PROP-K7": (
        "A symmetric low-twist blade produces a monotonic thrust reversal as collective becomes negative.",
        "Accept when thrust rises monotonically from minus 20 to plus 10 degrees and crosses zero between minus 10 and minus 5 degrees.",
    ),
    "PROP-K8": (
        "PR-6 requires rejection of non-positive fluid density before the engine runs.",
        "Accept when density zero and minus one each produce a validation error and no result file.",
    ),
    "PROP-K9": (
        "A full-range stall model remains finite at extreme collective and loses thrust after the whole blade stalls.",
        "Accept when all cases from 25 to 40 degrees converge with finite values and static thrust decreases monotonically.",
    ),
    "PROP-C14": (
        "Shaft power obeys the exact mechanical identity P = Q times shaft angular speed.",
        "Accept when P = Q times shaft speed within 0.1 W at 2400 RPM and advance ratio 0.6.",
    ),
    "PROP-C13": (
        "Actuator-disk induced power is thrust times axial speed plus induced speed, with extra power attributable to swirl.",
        "Accept when measured power divided by the no-swirl induced-power estimate is 1.0 to 1.08 from static to advance ratio 0.8.",
    ),
    "PROP-POWER-SUMMARY": (
        "The summary combines mechanical shaft-power identity with induced-power bookkeeping including wake swirl.",
        "Accept when shaft power closes within 0.1 W and the induced-power ratio remains 1.0 to 1.08 at the declared cases.",
    ),
    "PROP-T2A": (
        "Glauert actuator-disk theory gives an upper propulsive-efficiency bound from the minimum induction factor.",
        "Accept when propeller efficiency does not exceed the Glauert bound at any advance ratio from 0 to 1.2.",
    ),
    "PROP-T2B": (
        "A finite non-ideal blade requires more induced velocity than an ideal uniformly loaded disk at equal thrust coefficient.",
        "Accept when induced velocity is strictly above the momentum minimum at every positive-thrust point from advance ratio 0 to 1.2.",
    ),
    "PROP-MOMENTUM-SUMMARY": (
        "The momentum summary combines the ideal efficiency ceiling and the finite-blade induced-velocity excess.",
        "Accept when both the efficiency bound and induced-velocity lower bound hold from advance ratio 0 to 1.2.",
    ),
    "PROP-T3": (
        "Published fixed-pitch propeller data place efficient static figure of merit between 0.5 and 0.75.",
        "Accept when static figure of merit at zero collective is 0.5 to 0.75.",
    ),
    "PROP-F5": (
        "A finite gently twisted blade should require 5% to 15% more hover inflow than the ideal momentum value.",
        "Accept when induced inflow divided by the ideal value is 1.05 to 1.15 for the 20-to-8-degree twist case.",
    ),
    "PROP-STATIC-SUMMARY": (
        "The static summary combines a literature figure-of-merit range and a finite-blade induced-inflow excess.",
        "Accept when figure of merit is 0.5 to 0.75 and the gentle-twist inflow ratio is 1.05 to 1.15.",
    ),
    "PROP-N1": (
        "Conventional propulsive efficiency is not meaningful when both thrust and power indicate windmilling.",
        "Accept as a reporting limitation when windmill efficiency is explicitly clamped to zero and absorbed power remains available separately.",
    ),
    "PROP-N2": (
        "A single near-tolerance station may reduce the reported convergence percentage without causing a crash or non-finite result.",
        "Accept as a tracked observation when the collective-8 static case reports at least 98.6% convergence and all outputs remain finite.",
    ),
    "PROP-N3": (
        "The starter propeller root twist can keep static thrust positive at negative collective.",
        "Accept as a geometry observation when thrust remains positive through minus 20 degrees and a symmetric-twist control case reverses thrust.",
    ),
    "PROP-T1": (
        "Propeller thrust, power, and efficiency coefficients follow their dimensional definitions.",
        "Accept when all three recomputed coefficients agree with reported values within 1e-12 before the windmill clamp.",
    ),
    "PROP-T4": (
        "Classical propeller charts show thrust and power decreasing after the static-stall pocket and one efficiency peak before zero thrust.",
        "Accept when each collective curve has those trends from advance ratio 0 to its zero-thrust point.",
    ),
    "PROP-T5A": (
        "Prandtl losses can only reduce lift, with tip loss larger than root loss for the reference blade.",
        "Accept when thrust orders loss-off above root-only above tip-only above both at advance ratio 0.8.",
    ),
    "PROP-T5C": (
        "Converged inflow is independent of the nonlinear solver used to find the residual root.",
        "Accept when four solver thrust coefficients span at most 0.5% at advance ratio 0.8.",
    ),
    "PROP-T6A": (
        "Without Reynolds or compressibility effects, coefficients at fixed advance ratio are independent of RPM.",
        "Accept when thrust coefficient spread is at most 1e-12 from 1200 to 4800 RPM at advance ratio 0.6.",
    ),
    "PROP-T6C": (
        "Dimensional force scales linearly with density while its coefficient remains invariant.",
        "Accept when thrust divided by density and thrust coefficient each agree within 1e-10 at densities 0.8, 1.0, and 1.225.",
    ),
    "PROP-T7": (
        "Cross-flow reversal leaves thrust and power even while reversing normal force and pitching moment.",
        "Accept when even quantities agree and odd quantities sum to zero within 0.1% for cross-flow plus and minus 10, 20, and 40 m/s.",
    ),
    "PROP-T8": (
        "A propeller passes continuously from thrust through brake and windmill regimes as advance ratio rises.",
        "Accept when thrust and power become negative beyond zero thrust, reverse axial flow restores loading, and every case converges.",
    ),
    "PROP-T9A": (
        "Adding blades raises total thrust but lowers thrust coefficient per blade because induced losses increase.",
        "Accept when total thrust rises and thrust coefficient per blade falls monotonically from one to six blades.",
    ),
    "PROP-T9B": (
        "At fixed advance ratio and speed, dimensional thrust scales approximately with radius to the fourth power, modified by Mach effects.",
        "Accept when thrust rises monotonically across radii 0.7, 0.94, and 1.2 m and each coefficient remains finite.",
    ),
    "PROP-GEOMETRY-SUMMARY": (
        "The geometry summary combines the blade-count loading trend and the radius scaling trend.",
        "Accept when blade-count thrust rises while per-blade loading falls and radius produces monotonic finite thrust growth.",
    ),
    "PROP-T10": (
        "A converged propeller mesh approaches one thrust-coefficient limit under radial and azimuthal refinement.",
        "Accept when the final two meshes differ by at most 0.1% and the sequence is asymptotic.",
    ),
    "REPO-PITT-WARNING": (
        "QR-5 requires every user-facing Pitt-Peters warning to use English only.",
        "Accept when the reverse-inflow warning contains a complete English sentence and no Portuguese words.",
    ),
    "STALL-DELAY-RATIO": (
        "The published Snel stall-delay ratio uses local rotational speed divided by total relative speed.",
        "Accept when the implemented ratio and delay factor match the published resultant-speed form within 1% at three radial stations.",
    ),
}


_CLAIM_ROUTE_BASES: dict[str, tuple[str, str]] = {}


def _register_routes(
    claim_ids: tuple[str, ...],
    cli_route: str,
    gui_route: str,
) -> None:
    """Register one source experiment for one or more related assertions."""
    for claim_id in claim_ids:
        if claim_id in _CLAIM_ROUTE_BASES:
            raise ValueError(f"Duplicate reproduction route for {claim_id}")
        _CLAIM_ROUTE_BASES[claim_id] = (cli_route, gui_route)


# Core BEMT checks.
_register_routes(
    ("BEMT-C1",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/bemt-c1. Set an analytical polar with lift slope 2*pi and zero-lift angle -4.5 degrees. Set config.Ne=72, config.Npsi=144, Prandtl losses off, and compressibility off. Run python -m zbemt.cli --project outputs/physics_checks/manual/bemt-c1 --rpm 400 --mu-inplane 0 --collective 4. Then run python -m zbemt.cli --project outputs/physics_checks/manual/bemt-c1 --rpm 400 --mu-inplane 0 --collective 8. Then run python -m zbemt.cli --project outputs/physics_checks/manual/bemt-c1 --rpm 400 --mu-inplane 0 --collective 12. Compare CT with the independent hover thrust coefficient at each collective.",
    "Open the prepared analytical-polar project. Open Run Batch. Add hover rows at 400 RPM and collective 4, 8, and 12 degrees. Run the batch. In Results, inspect CT and compare each value with the closed hover thrust coefficient.",
)
_register_routes(
    ("BEMT-C2",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/bemt-c2 and keep Prandtl tip and root losses enabled. Run python -m zbemt.cli --project outputs/physics_checks/manual/bemt-c2 --rpm 400 --mu-inplane 0 --collective 8 --outdir outputs/physics_checks/manual/bemt-c2/results. Inspect FM, CT, CP, and induced inflow in results.csv.",
    "Open the prepared rotor project. In Run Case, set 400 RPM, zero in-plane and axial flow, and collective 8 degrees. Run the case. In Results, inspect FM, CT, CP, and induced inflow.",
)
_register_routes(
    ("BEMT-C3",),
    "Prepare two copies of projects/starter_rotor with rectangular geometry and equal solidity. Use two blades with chord 0.12 in outputs/physics_checks/manual/bemt-c3-two and four blades with chord 0.06 in outputs/physics_checks/manual/bemt-c3-four. Run python -m zbemt.cli --project outputs/physics_checks/manual/bemt-c3-two --rpm 400 --mu-inplane 0 --collective 8. Then run python -m zbemt.cli --project outputs/physics_checks/manual/bemt-c3-four --rpm 400 --mu-inplane 0 --collective 8. Compare CT.",
    "Open the first prepared project. In Geometry, set two blades and chord ratio 0.12. Run hover at 400 RPM and collective 8 degrees. Repeat with four blades and chord ratio 0.06. Compare CT in Results.",
)
_register_routes(
    ("BEMT-C4",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0 --collective 8 --prandtl-loss-mode off. Repeat with --prandtl-loss-mode tip, root, and both. Export disk maps and compare the local Prandtl factor with the closed form and compare CT across modes.",
    "Open the starter rotor project. In Config, select Prandtl modes Off, Tip, Root, and Both in turn. Run hover at 400 RPM and collective 8 degrees. Inspect the Prandtl disk map and CT in Results.",
)
_register_routes(
    ("BEMT-C5",),
    "Prepare outputs/physics_checks/manual/bemt-c5 from projects/starter_rotor so its tip Mach is 0.55 at the selected RPM. Run python -m zbemt.cli --project outputs/physics_checks/manual/bemt-c5 --rpm 400 --mu-inplane 0 --collective 8 --set config.use_compressibility=false. Then run the same command with --set config.use_compressibility=true. Compare CT and the local Mach field.",
    "Open the prepared rotor project. In Airfoil, disable compressibility and run hover at tip Mach 0.55. Enable compressibility and run again. Inspect CT and the Mach disk map in Results.",
)
_register_routes(
    ("BEMT-C6", "BEMT-C7"),
    "Prepare outputs/physics_checks/manual/bemt-c6 from projects/starter_rotor with constant section drag. Run python -m zbemt.cli --project outputs/physics_checks/manual/bemt-c6 --rpm 400 --mu-inplane 0.30 --collective 8 --no-radial-flow-correction. Then run the same condition with --radial-flow-correction. Compare CHp, CHr, profile power, torque, and the EN-10 closed forms.",
    "Open the prepared rotor project. In Config, disable Radial flow correction. Run at 400 RPM, in-plane advance ratio 0.30, and collective 8 degrees. Enable the correction and repeat. In Results, inspect CHp, CHr, profile power, and torque.",
)
_register_routes(
    ("BEMT-C8",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --v-axial -12 --collective 8. Repeat with --v-axial -8, 0, 8, 12, and 20. Compare CT, induced inflow, and total axial inflow in each results.csv row.",
    "Open the starter rotor project. In Run Batch, sweep axial speed through -12, -8, 0, 8, 12, and 20 m/s at 400 RPM and collective 8 degrees. Run the batch. Inspect CT and both inflow quantities in Results.",
)
_register_routes(
    ("BEMT-C9",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.15 --collective 10 --solver fixed_point. Repeat with --solver newton, bisection, and aitken. Compare CT and the true residual in the four outputs.",
    "Open the starter rotor project. In Config, select Fixed point, Newton, Bisection, and Aitken in turn. Run each at 400 RPM, in-plane advance ratio 0.15, and collective 10 degrees. Compare CT and convergence residuals in Results.",
)
_register_routes(
    ("BEMT-C10",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.35 --collective 10 --set config.reverse_flow_model=flat_plate --plots disk_map. Repeat with --set config.reverse_flow_model=thin_plate_blend and viterna_full_range. Compare normal-load values on both sides of zero tangential velocity.",
    "Open the starter rotor project. In Airfoil, select Flat plate, Thin-plate blend, and Viterna full range as the reverse-flow model. Run each at in-plane advance ratio 0.35. In Results, inspect the normal-load disk map across the reverse-flow boundary.",
)
_register_routes(
    ("BEMT-C11",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0 --collective 18 --rotational-augmentation. Then run python -m zbemt.cli --project projects/starter_rotor --rpm 300 --mu-inplane 0.20 --collective 16 --rotational-augmentation. Repeat both conditions with --no-rotational-augmentation. Compare CT and stalled-root lift.",
    "Open the starter rotor project. In Config, enable rotational augmentation. Run hover at 400 RPM and collective 18 degrees, then run 300 RPM, in-plane advance ratio 0.20, and collective 16 degrees. Repeat with the option disabled. Inspect CT and root lift in Results.",
)
_register_routes(
    ("BEMT-C12",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/bemt-c12 and set the analytical polar from the source report. Run python -m zbemt.cli --project outputs/physics_checks/manual/bemt-c12 --rpm 400 --mu-inplane 0 --collective 8 --set config.use_compressibility=false. Repeat with --set config.use_compressibility=true. Compare the unchanged polar table with the changed blade-element CT.",
    "Open the prepared project. In Airfoil, inspect the analytical polar at Mach 0 and 0.6, then run the same hover case with compressibility disabled and enabled there. Compare the polar coefficients and CT in Results.",
)
_register_routes(
    ("BEMT-G6",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 200 --mu-inplane 0.15 --collective 10 --set config.rho=1.225 --set config.use_compressibility=false. Repeat at 400 and 800 RPM, then repeat the three speeds with --set config.rho=0.9. Compare CT and CQ.",
    "Open the starter rotor project. In Run Batch, combine RPM 200, 400, and 800 with density 1.225 and 0.9 kg/m^3 at in-plane advance ratio 0.15. Disable compressibility. Run the batch and compare CT and CQ in Results.",
)
_register_routes(
    ("BEMT-H1",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.15 --collective 10 --set config.Ne=8 --set config.Npsi=24. Repeat with mesh pairs 16 by 48, 32 by 96, and 48 by 144. Compare CT in mesh order.",
    "Open the starter rotor project. In Config, set mesh pairs 8 by 24, 16 by 48, 32 by 96, and 48 by 144. Run each at 400 RPM, in-plane advance ratio 0.15, and collective 10 degrees. Compare CT in Results.",
)
_register_routes(
    ("BEMT-H2",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --v-inplane 30 --v-axial 4.3 --collective 10. Inspect Vx, Vz, alpha_rotor_deg, and alpha_disk_deg in results.csv and recompute both angles from the two velocities.",
    "Open the starter rotor project. In Run Case, set 400 RPM, in-plane speed 30 m/s, axial speed 4.3 m/s, and collective 10 degrees. Run the case. In Results, inspect both velocity components and both reported angles.",
)

# Dynamic-stall checks. The prepared project uses the analytical polar and
# saved maneuvers described in the source report.
_register_routes(
    ("DS-A1", "DS-A7"),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/ds-steady. Set airfoil.use_dynamic_stall=true and prepare frequency and time_march variants. Run python -m zbemt.cli --project outputs/physics_checks/manual/ds-steady --rpm 400 --mu-inplane 0 --collective 16 --set airfoil.dynamic_stall_method=frequency. Then repeat with --set airfoil.dynamic_stall_method=time_march and with --no-dynamic-stall. Compare separation-state maps and CT.",
    "Open the prepared project. In Airfoil, select Dynamic stall Frequency and run hover at 400 RPM and collective 16 degrees. Select Time march and repeat, then disable dynamic stall and repeat. Inspect separation state and CT in Results.",
)
_register_routes(
    ("DS-A2", "DS-A3", "DS-A4", "DS-A10", "DS-A11", "DS-A12", "DS-A13", "DS-A17"),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/ds-harmonic. Add inputs/maneuvers.bemt with a maneuver named oye-harmonic that drives the source sinusoidal stalled-angle cycle for 16 revolutions at 400 RPM. Run python -m zbemt.cli --project outputs/physics_checks/manual/ds-harmonic --maneuver oye-harmonic --set airfoil.dynamic_stall_method=time_march. Repeat with --set airfoil.dynamic_stall_method=frequency and with airfoil.dynamic_stall_A values 8 and 40. Inspect the time-history CSV for separation state, lift, drag, angle, amplitude, phase, and peak azimuth.",
    "Open the prepared project and the Transient window. Select the saved Oye harmonic maneuver at 400 RPM and 16 revolutions. Run Time march and Frequency with A equal to 8, then run A equal to 40. Inspect separation state, lift, drag, angle, amplitude, phase, and peak timing in the transient plots and Results.",
)
_register_routes(
    ("DS-A5",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/ds-a5. Add inputs/maneuvers.bemt with a saved constant-condition maneuver named periodic-residual at 400 RPM and collective 16 degrees. Run python -m zbemt.cli --project outputs/physics_checks/manual/ds-a5 --maneuver periodic-residual --set airfoil.dynamic_stall_method=time_march --set airfoil.dynamic_stall_time_march_revolutions=2. Repeat with airfoil.dynamic_stall_time_march_revolutions=4. Compare the periodic residual and warning in both histories.",
    "Open the prepared project and the Transient window. Select periodic-residual. Set Dynamic stall revolutions to 2 and run, then set 4 and run. Inspect the periodic residual and warning in the transient Results.",
)
_register_routes(
    ("DS-A6",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/ds-a6. Add inputs/maneuvers.bemt with a two-segment maneuver named state-threading whose second segment starts at the first segment condition. Run python -m zbemt.cli --project outputs/physics_checks/manual/ds-a6 --maneuver state-threading --set airfoil.dynamic_stall_method=time_march. Inspect the state on both sides of the segment boundary.",
    "Open the prepared project and the Transient window. Run the saved state-threading maneuver. Inspect the separation-state history immediately before and after the repeated-condition boundary.",
)
_register_routes(
    ("DS-A8", "DS-A16"),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.05 --collective 16 --dynamic-stall --set airfoil.dynamic_stall_method=frequency. Repeat at advance ratios 0.10 and 0.20. Repeat all three conditions with --set airfoil.dynamic_stall_method=time_march and 16 revolutions. Compare CT and CP between methods and against dynamic stall off.",
    "Open the starter rotor project. In Run Batch, add in-plane advance ratios 0.05, 0.10, and 0.20 at 400 RPM and collective 16 degrees. Run Dynamic stall Frequency, Time march with 16 revolutions, and Off. Compare CT and CP in Results.",
)
_register_routes(
    ("DS-A9", "DS-D3-HYSTERESIS-DIRECTION", "DS-H4"),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/ds-ramp. Add inputs/maneuvers.bemt with a 41-sample maneuver named collective-ramp that changes collective 6 to 16 to 6 degrees at 400 RPM and advance ratio 0.20. Run python -m zbemt.cli --project outputs/physics_checks/manual/ds-ramp --maneuver collective-ramp --set airfoil.dynamic_stall_method=time_march. Compare lift and CT on rising and falling branches at equal collective.",
    "Open the prepared project and the Transient window. Run the 41-sample collective-ramp maneuver from 6 to 16 to 6 degrees. Inspect stalled-element lift and CT at equal collective on the rising and falling branches.",
)
_register_routes(
    ("DS-A14", "DS-D3B-FADE-50"),
    "Prepare outputs/physics_checks/manual/ds-fade from projects/starter_rotor with the source analytical polar. Run python -m zbemt.cli --project outputs/physics_checks/manual/ds-fade --rpm 400 --mu-inplane 0.60 --collective 16 --dynamic-stall --set airfoil.dynamic_stall_fade_end_deg=50 --plots disk_map. Repeat with fade end 55 degrees. Compare dynamic and static lift outside each declared fade angle.",
    "Open the prepared project. In Airfoil, set the dynamic-stall fade end to 50 degrees and run the deep-angle case. Repeat at 55 degrees. In Results, inspect dynamic and static lift outside each fade boundary.",
)
_register_routes(
    ("DS-A15",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.20 --collective 16 --dynamic-stall --set airfoil.dynamic_stall_A=2. Repeat with A equal to 8 and 20. Compare the separation-state lag and CT.",
    "Open the starter rotor project. In Airfoil, set dynamic-stall A to 2, 8, and 20 in turn. Run each at 400 RPM, in-plane advance ratio 0.20, and collective 16 degrees. Inspect separation-state lag and CT in Results.",
)
_register_routes(
    ("DS-A18",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/ds-sections. Add inputs/airfoil_sections.bemt with one section that has use_dynamic_stall=false at radial ratio 0.88 and one enabled section. Run python -m zbemt.cli --project outputs/physics_checks/manual/ds-sections --rpm 400 --mu-inplane 0.20 --collective 16 --dynamic-stall --plots disk_map. Compare the disabled station and the interpolated station.",
    "Open the prepared project. In Airfoil sections, disable dynamic stall at the radial ratio 0.88 section and keep the adjacent section enabled. Run at advance ratio 0.20 and collective 16 degrees. Inspect the lift-correction disk map at both stations.",
)

# Pitt-Peters checks.
_register_routes(
    ("PP-B1",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0 --collective 8 --inflow pitt_peters_steady --outdir outputs/physics_checks/manual/pp-b1. Read nu0 and CT from results.csv and compare nu0 with sqrt(CT/2).",
    "Open the starter rotor project. In Config, select Pitt-Peters steady. In Run Case, set 400 RPM, zero in-plane and axial flow, and collective 8 degrees. Run the case. In Results, inspect nu0 and CT and compare nu0 with the momentum value.",
)
_register_routes(
    ("PP-B2", "PP-STEADY-MARCH-AUDIT"),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/pp-b2. Add inputs/maneuvers.bemt with constant-condition maneuvers named pp-mu000, pp-mu005, and pp-mu015 for 20 revolutions. Run python -m zbemt.cli --project outputs/physics_checks/manual/pp-b2 --inflow pitt_peters_unsteady --maneuver pp-mu000. Repeat for pp-mu005 and pp-mu015, and run matching pitt_peters_steady cases. Compare nu0, nu_s, and nu_c.",
    "Open the prepared project and the Transient window. Run the three 20-revolution constant-condition maneuvers at in-plane advance ratios 0, 0.05, and 0.15. Run the matching steady cases from Run Case. Compare all three inflow states in Results.",
)
_register_routes(
    ("PP-B3",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/pp-b3. Add inputs/maneuvers.bemt with a small inflow perturbation maneuver named pp-decay at 400 RPM. Run python -m zbemt.cli --project outputs/physics_checks/manual/pp-b3 --inflow pitt_peters_unsteady --maneuver pp-decay --maneuver-substeps 8. Fit the nu0 decay rate from the time-history CSV and compare it with the precomputed finite-difference Jacobian eigenvalue.",
    "Open the prepared project and the Transient window. Run pp-decay at 400 RPM with eight substeps. In the transient Results, fit the nu0 decay rate and compare it with the independent Jacobian eigenvalue.",
)
_register_routes(
    ("PP-B4",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/pp-b4. Add inputs/maneuvers.bemt with a hover collective step named pp-collective-step at 400 RPM. Run python -m zbemt.cli --project outputs/physics_checks/manual/pp-b4 --inflow pitt_peters_unsteady --maneuver pp-collective-step. Run a final-condition steady case and compare CT overshoot and settled CT.",
    "Open the prepared project and the Transient window. Run pp-collective-step in hover at 400 RPM. Run the final collective as a steady Run Case. Inspect peak and final CT in Results.",
)
_register_routes(
    ("PP-P5-ASYMMETRY", "PP-P6-THRUST", "PP-B5-COMBINED"),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.15 --collective 8 --inflow pitt_peters_steady --plots disk_map. Repeat with --inflow drees_global and repeat both models in hover. Compare lambda_i disk-map correlation, maximum azimuth, and CT.",
    "Open the starter rotor project. In Config, run Pitt-Peters steady and Drees global in hover and at in-plane advance ratio 0.15. Export the induced-inflow disk maps. Compare field correlation, maximum azimuth, and CT in Results.",
)
_register_routes(
    ("PP-B6",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0 --collective 8 --inflow pitt_peters_steady --pitt-peters-outer-iter 15 --pitt-peters-tol 1e-6. Inspect the Pitt-Peters outer iteration count and residual.",
    "Open the starter rotor project. In Config, select Pitt-Peters steady, set the outer limit to 15 and tolerance to 1e-6. Run hover at 400 RPM and collective 8 degrees. Inspect outer iterations and residual in Results.",
)
_register_routes(
    ("PP-B7",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/pp-b7. Add inputs/maneuvers.bemt with a 20-revolution constant maneuver named sideslip-30 at 400 RPM, advance ratio 0.10, collective 8 degrees, and inflow sideslip 30 degrees. Run python -m zbemt.cli --project outputs/physics_checks/manual/pp-b7 --inflow pitt_peters_steady --rpm 400 --mu-inplane 0.10 --collective 8 --set config.inflow_sideslip_deg=30. Then run python -m zbemt.cli --project outputs/physics_checks/manual/pp-b7 --inflow pitt_peters_unsteady --maneuver sideslip-30. Compare nu0, nu_s, and nu_c.",
    "Open the prepared project. In Config, set Pitt-Peters sideslip to 30 degrees. Run the steady case at 400 RPM and in-plane advance ratio 0.10. In the Transient window, run sideslip-30. Compare all three inflow states in Results.",
)
_register_routes(
    ("PP-B8",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/pp-b8. Add inputs/maneuvers.bemt with a maneuver named rpm-step that changes 400 to 300 RPM while holding the flight condition. Run python -m zbemt.cli --project outputs/physics_checks/manual/pp-b8 --inflow pitt_peters_unsteady --maneuver rpm-step. Inspect all inflow states on both sides of the RPM boundary.",
    "Open the prepared project and the Transient window. Run rpm-step from 400 to 300 RPM. Inspect nu0, nu_s, and nu_c immediately before and after the speed change.",
)
_register_routes(
    ("PP-G7",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.15 --collective 8 --inflow drees_global --set config.inflow_sideslip_deg=0 --plots disk_map. Repeat with sideslip 30 degrees and with coleman_global. Compare the azimuth of maximum induced inflow.",
    "Open the starter rotor project. In Config, select Drees global and sideslip 0 degrees, then run at advance ratio 0.15. Repeat at 30 degrees and repeat both angles with Coleman global. Compare the induced-inflow disk-map maximum in Results.",
)
_register_routes(
    ("PP-GAIN-L", "PP-MASS-FLOW", "PP-MASS-MATRIX"),
    "Prepare outputs/physics_checks/manual/pp-matrices with the source analytical rotor and saved hover and advance-ratio 0.15 cases. Run python -m zbemt.cli --project outputs/physics_checks/manual/pp-matrices --rpm 400 --mu-inplane 0 --collective 8 --inflow pitt_peters_steady. Then run at --mu-inplane 0.15. Use CT, nu0, nu_s, nu_c, and total inflow from results.csv to evaluate the published Pitt-Peters matrix limits.",
    "Open the prepared project. In Config, select Pitt-Peters steady. Run hover and in-plane advance ratio 0.15 at 400 RPM and collective 8 degrees. In Results, inspect CT, all three inflow states, and total inflow and evaluate the published matrix limits.",
)
_register_routes(
    ("PROP-FA",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 0 --inflow glauert_local. Repeat at J 0.4, 0.8, and 1.2. Repeat all four points with --inflow pitt_peters_steady. Compare CT and CP by point.",
    "Open the starter propeller project. In Run Batch, add axial advance ratios 0, 0.4, 0.8, and 1.2 at 2400 RPM and collective 0 degrees. Run Glauert local and Pitt-Peters steady. Compare CT and CP in Results.",
)

# Propeller checks.
_register_routes(
    ("PROP-T1",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.6 --collective 0 --outdir outputs/physics_checks/manual/prop-t1. Recompute CT_prop, CP_prop, and eta_prop from Thrust, Power, density, RPM, diameter, and J in results.csv.",
    "Open the starter propeller project. In Run Case, set 2400 RPM, axial advance ratio 0.6, and collective 0 degrees. Run the case. In Results, inspect dimensional thrust and power and the three propeller coefficients and recompute them.",
)
_register_routes(
    ("PROP-C14",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.6 --collective 0 --outdir outputs/physics_checks/manual/prop-c14. Compare Power with Torque times shaft angular speed from results.csv.",
    "Open the starter propeller project. Run 2400 RPM, axial advance ratio 0.6, and collective 0 degrees. In Results, inspect Power and Torque and multiply torque by shaft angular speed.",
)
_register_routes(
    ("PROP-C13",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 0. Then run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.4 --collective 0. Then run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.8 --collective 0. Read Power, Thrust, Vx, and Vi from results.csv and compare Power with Thrust times (Vx + Vi).",
    "Open the starter propeller project. In Run Batch, add axial advance ratios 0, 0.4, and 0.8 at 2400 RPM and collective 0 degrees. Run the batch. In Results, inspect Power, Thrust, Vx, and Vi and compute the induced-power ratio.",
)
_register_routes(
    ("PROP-POWER-SUMMARY",),
    "Run the PROP-C14 condition at axial advance ratio 0.6 and the PROP-C13 sweep at 0, 0.4, and 0.8 with python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --collective 0. Compare Power with Torque times shaft speed and with Thrust times total axial speed.",
    "Open the starter propeller project. In Run Batch, run axial advance ratios 0, 0.4, 0.6, and 0.8 at 2400 RPM and collective 0 degrees. In Results, inspect Power, Torque, Thrust, Vx, and Vi for both bookkeeping comparisons.",
)
_register_routes(
    ("PROP-T2A",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 0. Repeat for J 0.2 through 1.2 in increments of 0.2. Compute the Glauert efficiency ceiling from CT_prop and compare eta_prop at each point.",
    "Open the starter propeller project. In Run Batch, sweep axial advance ratio 0 to 1.2 in increments of 0.2 at 2400 RPM and collective 0 degrees. In Results, inspect CT_prop and eta_prop and compute the Glauert ceiling.",
)
_register_routes(
    ("PROP-T2B",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 0. Repeat for J 0.2 through 1.2 in increments of 0.2. Compare Vi with the ideal momentum induced velocity calculated from CT_prop.",
    "Open the starter propeller project. In Run Batch, sweep axial advance ratio 0 to 1.2 in increments of 0.2. In Results, inspect Vi and CT_prop and calculate the ideal momentum induced velocity.",
)
_register_routes(
    ("PROP-MOMENTUM-SUMMARY",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 0 and repeat through J 1.2 in increments of 0.2. Compare eta_prop with the Glauert ceiling and Vi with the momentum minimum.",
    "Open the starter propeller project. In Run Batch, sweep axial advance ratio 0 to 1.2 in increments of 0.2. Inspect eta_prop, CT_prop, and Vi in Results for both momentum bounds.",
)
_register_routes(
    ("PROP-T3",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --v-axial 0 --collective 0. Inspect FM, CT, and CP in results.csv.",
    "Open the starter propeller project. In Run Case, set 2400 RPM, zero axial and cross flow, and collective 0 degrees. Run the case and inspect FM, CT, and CP in Results.",
)
_register_routes(
    ("PROP-F5",),
    "Copy projects/starter_propeller to outputs/physics_checks/manual/prop-f5 and set a linear twist from 20 to 8 degrees. Run python -m zbemt.cli --project outputs/physics_checks/manual/prop-f5 --rpm 2400 --v-axial 0 --collective 0. Compare Vi with the ideal value from CT_prop.",
    "Open the prepared gentle-twist propeller. In Geometry, confirm root twist 20 and tip twist 8 degrees. Run the static 2400 RPM case. In Results, inspect Vi and CT_prop and compute the ideal inflow.",
)
_register_routes(
    ("PROP-STATIC-SUMMARY",),
    "Run the starter static case and the prepared 20-to-8-degree twist case with python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --v-axial 0 --collective 0. Compare FM with the literature band and the gentle-twist Vi with ideal momentum inflow.",
    "Open the starter and gentle-twist propeller projects. Run each statically at 2400 RPM and collective 0 degrees. In Results, inspect FM, Vi, and CT_prop for both static checks.",
)
_register_routes(
    ("PROP-T4",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 0 and repeat J in 0.1 increments through 1.8. Repeat the sweep at collective -5 and 8 degrees. Compare CT_prop, CP_prop, and eta_prop curve shapes.",
    "Open the starter propeller project. In Run Batch, sweep axial advance ratio 0 to 1.8 by 0.1 at collective -5, 0, and 8 degrees. Run the batch and inspect CT_prop, CP_prop, and eta_prop curves in Results.",
)
_register_routes(
    ("PROP-N2",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 8. Inspect convergence_pct and all finite result fields.",
    "Open the starter propeller project. Run the static case at 2400 RPM and collective 8 degrees. In Results, inspect convergence percentage and confirm that all outputs are finite.",
)
_register_routes(
    ("PROP-T5A",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.8 --collective 0 --prandtl-loss-mode off. Repeat with root, tip, and both. Compare CT_prop and CP_prop.",
    "Open the starter propeller project. In Config, run Prandtl modes Off, Root, Tip, and Both at 2400 RPM and axial advance ratio 0.8. Compare CT_prop and CP_prop in Results.",
)
_register_routes(
    ("PROP-T5C",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.8 --collective 0 --solver fixed_point. Repeat with newton, bisection, and aitken. Compare CT_prop and convergence percentage.",
    "Open the starter propeller project. In Config, run Fixed point, Newton, Bisection, and Aitken at axial advance ratio 0.8. Compare CT_prop and convergence in Results.",
)
_register_routes(
    ("PROP-T6A",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 1200 --j-axial 0.6 --collective 0 --set config.use_compressibility=false. Repeat at 2400, 3600, and 4800 RPM. Compare CT_prop.",
    "Open the starter propeller project. Disable compressibility. In Run Batch, run 1200, 2400, 3600, and 4800 RPM at axial advance ratio 0.6. Compare CT_prop in Results.",
)
_register_routes(
    ("PROP-T6C",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.6 --collective 0 --set config.rho=0.8. Repeat with density 1.0 and 1.225. Compare Thrust divided by density and CT_prop.",
    "Open the starter propeller project. In Run Batch, run densities 0.8, 1.0, and 1.225 kg/m^3 at 2400 RPM and axial advance ratio 0.6. Compare Thrust and CT_prop in Results.",
)
_register_routes(
    ("PROP-T7",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --v-axial 30 --v-inplane -40 --collective 0. Repeat for cross-flow speeds -20, -10, 0, 10, 20, and 40 m/s. Compare Thrust, Power, H, and My_total under sign reversal.",
    "Open the starter propeller project. In Run Batch, hold axial speed 30 m/s and sweep cross-flow speed from -40 to 40 m/s through the listed points. Inspect Thrust, Power, H, and My_total in Results.",
)
_register_routes(
    ("PROP-T8",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 1.2 --collective 0. Repeat at J 1.6 and 1.99, then run --v-axial -20. Compare CT_prop, CP_prop, and convergence.",
    "Open the starter propeller project. In Run Batch, add axial advance ratios 1.2, 1.6, and 1.99 plus axial speed -20 m/s at 2400 RPM. Inspect CT_prop, CP_prop, and convergence in Results.",
)
_register_routes(
    ("PROP-N1",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 1.4 --collective 0 and repeat at J 1.6. Inspect eta_prop, CT_prop, and CP_prop and also compute J times CT_prop divided by CP_prop.",
    "Open the starter propeller project. Run axial advance ratios 1.4 and 1.6 at 2400 RPM. In Results, inspect eta_prop, CT_prop, and CP_prop and calculate the unclamped ratio.",
)
_register_routes(
    ("PROP-N3",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --v-axial 0 --collective -20 and repeat through collective 0 degrees. Then prepare a constant 5-degree twist project and repeat the negative-collective sweep. Compare Thrust.",
    "Open the starter propeller project. In Run Batch, sweep collective -20 to 0 degrees in static operation. Repeat after setting constant twist to 5 degrees in Geometry. Compare Thrust in Results.",
)
_register_routes(
    ("PROP-T9A",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.6 --collective 0 --geom-n-blades 1. Repeat with blade counts 2, 3, 4, 5, and 6. Compare CT_prop and CT_prop per blade.",
    "Open the starter propeller project. In Geometry, set blade counts 1 through 6 and run each at axial advance ratio 0.6. Compare CT_prop and per-blade CT_prop in Results.",
)
_register_routes(
    ("PROP-T9B",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.6 --collective 0 --geom-radius 0.7. Repeat with radius 0.94 and 1.2 m. Compare Thrust and CT_prop.",
    "Open the starter propeller project. In Geometry, set radius 0.7, 0.94, and 1.2 m and run each at axial advance ratio 0.6. Compare Thrust and CT_prop in Results.",
)
_register_routes(
    ("PROP-GEOMETRY-SUMMARY",),
    "Run the PROP-T9A blade-count sweep and the PROP-T9B radius sweep with python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.6 --collective 0. Compare total thrust, per-blade CT_prop, and radius scaling.",
    "Open the starter propeller project. In Geometry, run the blade-count and radius sweeps at axial advance ratio 0.6. Inspect Thrust and CT_prop in Results for both geometry trends.",
)
_register_routes(
    ("PROP-T10",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.6 --collective 0 --set config.Ne=18 --set config.Npsi=12. Repeat with meshes 36 by 24, 72 by 36, and 108 by 48. Compare CT_prop.",
    "Open the starter propeller project. In Config, run meshes 18 by 12, 36 by 24, 72 by 36, and 108 by 48 at axial advance ratio 0.6. Compare CT_prop in Results.",
)
_register_routes(
    ("PROP-K1",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 0 and repeat J 0.2 through 1.2 by 0.2. Read Thrust, Vx, Vi, and CT_prop and calculate the induced-power factor.",
    "Open the starter propeller project. In Run Batch, sweep axial advance ratio 0 to 1.2 by 0.2. In Results, inspect Thrust, Vx, Vi, and CT_prop and calculate the induced-power factor.",
)
_register_routes(
    ("PROP-K4",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.4 --collective 0 --set config.Npsi=12. Repeat with Npsi 36 and 72 in axial flow, then repeat at --v-axial 30 --v-inplane 20. Compare CT_prop and H.",
    "Open the starter propeller project. In Config, set Npsi to 12, 36, and 72. Run axial advance ratio 0.4 and the 30 m/s axial, 20 m/s cross-flow case. Compare CT_prop and H in Results.",
)
_register_routes(
    ("PROP-K6",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.8 --collective 0 --set airfoil.cd0=0.004. Repeat with cd0 0.008 and 0.016. Compare profile power and CT_prop.",
    "Open the starter propeller project. In Airfoil, set zero-lift drag to 0.004, 0.008, and 0.016. Run each at axial advance ratio 0.8. Inspect profile power and CT_prop in Results.",
)
_register_routes(
    ("PROP-K7",),
    "Copy projects/starter_propeller to outputs/physics_checks/manual/prop-k7 and set constant twist 5 degrees. Run python -m zbemt.cli --project outputs/physics_checks/manual/prop-k7 --rpm 2400 --v-axial 0 --collective -20 and repeat collective -15, -10, -5, 0, 5, and 10. Compare Thrust.",
    "Open the prepared constant-twist propeller. In Run Batch, sweep collective -20 to 10 degrees through the listed points at 2400 RPM and zero flow. Compare Thrust in Results.",
)
_register_routes(
    ("PROP-K9",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 25 and repeat collective 30 and 40 degrees. Repeat all three at J 1.0. Compare CT_prop, convergence, and finite outputs.",
    "Open the starter propeller project. In Run Batch, combine collective 25, 30, and 40 degrees with axial advance ratios 0 and 1. Run the batch and inspect CT_prop and convergence in Results.",
)

# Model effects and validation.
_register_routes(
    ("PROP-K3",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0.8 --collective 0 --no-radial-flow-correction --no-rotational-augmentation --no-dynamic-stall. Repeat with each option enabled alone. Compare CT_prop and CP_prop.",
    "Open the starter propeller project. In Config, enable Radial flow correction, Rotational augmentation, and Dynamic stall one at a time. Run axial advance ratio 0.8 for each setting. Compare CT_prop and CP_prop in Results.",
)
_register_routes(
    ("PROP-K5",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 20 --airfoil-stall-model linear. Repeat with clip, viterna, and enhanced. Compare Thrust and CT_prop.",
    "Open the starter propeller project. In Airfoil, select Linear, Clip, Viterna, and Enhanced stall models. Run each statically at collective 20 degrees. Compare Thrust and CT_prop in Results.",
)
_register_routes(
    ("PROP-FB",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 1200 --j-axial 0.6 --collective 0 --set config.use_compressibility=true. Repeat at 2400, 3600, and 4800 RPM and repeat with --set config.use_compressibility=false. Compare tip Mach, CT_prop, and Power.",
    "Open the starter propeller project. In Run Batch, run 1200, 2400, 3600, and 4800 RPM at axial advance ratio 0.6. Run Prandtl-Glauert and no compressibility. Inspect tip Mach, CT_prop, and Power in Results.",
)
_register_routes(
    ("MODEL-G1",),
    "Evaluate the polar itself at 35 degrees with python -c \"from zbemt.models import AirfoilDef; from zbemt.airfoils import preview_polar; [print(model, preview_polar(AirfoilDef(stall_model=model), (35, 35, 1))[1][0]) for model in ('linear', 'clip', 'enhanced', 'viterna')]\". Then prepare outputs/physics_checks/manual/model-g1 from projects/starter_rotor and run python -m zbemt.cli --project outputs/physics_checks/manual/model-g1 --rpm 400 --mu-inplane 0.20 --collective 12 --airfoil-stall-model linear. Repeat with --airfoil-stall-model clip, --airfoil-stall-model enhanced, and --airfoil-stall-model viterna as an integrated-load corroboration.",
    "Open the prepared project. In the Airfoil tab, select Linear, Clip, Enhanced, and Viterna. For each model, read the polar directly at 35 degrees. Then run the same 400 RPM and 12-degree collective case as an integrated-load corroboration. Compare the lift curves and CT in Results.",
)
_register_routes(
    ("MODEL-G2",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.60 --collective 10 --set config.reverse_flow_model=flat_plate. Repeat with thin_plate_blend and viterna_full_range. Compare CT and reverse-zone Cd.",
    "Open the starter rotor project. In Airfoil, select Flat plate, Thin-plate blend, and Viterna full range. Run each at in-plane advance ratio 0.60. Inspect CT and reverse-zone drag in Results.",
)
_register_routes(
    ("MODEL-G3",),
    "Prepare outputs/physics_checks/manual/model-g3 from projects/starter_rotor. Run python -m zbemt.cli --project outputs/physics_checks/manual/model-g3 --collective 8 --set config.use_compressibility=true at RPM values that produce tip Mach 0.7, 0.8, 0.9, and 0.95. Compare CT and confirm finite results.",
    "Open the prepared project. In Run Batch, use the four RPM values that produce tip Mach 0.7, 0.8, 0.9, and 0.95. Enable compressibility in Airfoil. Run the batch and inspect CT and finite outputs in Results.",
)
_register_routes(
    ("PROP-K8",),
    "Run python -m zbemt.cli --project projects/starter_propeller --validate-only --set config.rho=-1. Repeat with config.rho=0. Confirm that validation stops before a result file is written.",
    "Open the starter propeller project. In the Config tab, set air density to -1 kg/m^3 and request validation. Repeat with 0 kg/m^3. Inspect the validation errors and confirm that Run remains blocked.",
)
_register_routes(
    ("STALL-DELAY-RATIO",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.25 --collective 12 --rotational-augmentation --plots disk_map. Repeat with --no-rotational-augmentation. At radial ratios 0.31, 0.54, and 0.92, compare the applied correction with rotational speed divided by total relative speed.",
    "Open the starter rotor project. In Config, enable rotational augmentation. Run 400 RPM, in-plane advance ratio 0.25, and collective 12 degrees, then repeat with rotational augmentation disabled. In Results, inspect the section correction at radial ratios 0.31, 0.54, and 0.92.",
)

# Flapping, lead-lag, trim, and derivative checks.
_register_routes(
    ("FLAP-E1",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model offset --hinge-offset 0.02 --lock-number 8 --rpm 400 --mu-inplane 0 --collective 8. Repeat with offsets 0.05, 0.10, and 0.15. Inspect flap frequency squared.",
    "Open the starter rotor project. In Geometry, select Offset hinge and set offsets 0.02, 0.05, 0.10, and 0.15. Run hover at 400 RPM. Inspect flap frequency in Results.",
)
_register_routes(
    ("FLAP-E2",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model offset --hinge-offset 0 --rpm 400 --mu-inplane 0 --collective 8 --set geom.dynamics.harmonics=1. Inspect the resonance validation error and confirm that no result is written.",
    "Open the starter rotor project. In Geometry, select an articulated central hinge and one harmonic. Request the hover run. Inspect the resonance error and confirm that Results has no new case.",
)
_register_routes(
    ("FLAP-E3",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model offset --hinge-offset 0.05 --lock-number 8 --rpm 400 --mu-inplane 0 --collective 8. Inspect beta_0, beta_1c, beta_1s, hub moments, outer iterations, and residual.",
    "Open the starter rotor project. In Geometry, set offset hinge 0.05 and Lock number 8. Run hover at 400 RPM and collective 8 degrees. Inspect flap coefficients, hub moments, and outer convergence in Results.",
)
_register_routes(
    ("FLAP-E4",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model offset --hinge-offset 0.05 --lock-number 8 --rpm 400 --mu-inplane 0.15 --collective 8 --plots disk_map. Compare front and rear flap angle and longitudinal tip-path-plane tilt.",
    "Open the starter rotor project. Run the offset-hinge model at 400 RPM, in-plane advance ratio 0.15, and collective 8 degrees. In Results, inspect flap angle by azimuth and longitudinal tip-path-plane tilt.",
)
_register_routes(
    ("FLAP-E5",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model offset --rpm 400 --mu-inplane 0.15 --collective 8 --cyclic 1 0. Inspect beta_1c and beta_1s.",
    "Open the starter rotor project. In Run Case, set longitudinal cyclic to 1 degree and lateral cyclic to 0 at advance ratio 0.15. Run the offset-hinge model and inspect beta_1c and beta_1s in Results.",
)
_register_routes(
    ("FLAP-E6",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model offset --rpm 400 --mu-inplane 0 --collective 8 --set geom.dynamics.pitch_flap_coupling_deg=0. Repeat with coupling 30 degrees. Compare beta_0.",
    "Open the starter rotor project. In Geometry, set pitch-flap coupling to 0 and 30 degrees. Run hover for each setting. Compare coning beta_0 in Results.",
)
_register_routes(
    ("FLAP-E7",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/flap-e7. Add inputs/derivatives.bemt with a study named gyro-rates that perturbs p and q by 0.2 rad/s at 400 RPM. Run python -m zbemt.cli --project outputs/physics_checks/manual/flap-e7 --flap-model offset --derivatives gyro-rates --derivatives-csv outputs/physics_checks/manual/flap-e7/rates.csv. Compare beta_1c and beta_1s under positive and negative rates.",
    "Open the prepared project and the Stability Derivatives window. Select p and q with 0.2 rad/s steps and the flap-coefficient outputs. Run gyro-rates. Inspect beta_1c and beta_1s for both rate signs.",
)
_register_routes(
    ("FLAP-E8",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.15 --collective 8 --cyclic 1 1 --flap-model rigid. Repeat with --flap-model offset --hinge-offset 0.05. Compare CMx and CMy.",
    "Open the starter rotor project. In Run Case, set both cyclic controls to 1 degree at advance ratio 0.15. Run Rigid and Offset hinge models. Compare CMx and CMy in Results.",
)
_register_routes(
    ("FLAP-E9",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.15 --collective 8 --flap-model rigid --outdir outputs/physics_checks/manual/flap-e9. Compare every scalar and exported array with the same project run before the blade-dynamics block is present.",
    "Open the starter rotor project. Run the rigid flap model at 400 RPM, advance ratio 0.15, and collective 8 degrees. Compare all Results fields with the saved plain-BEMT baseline.",
)
_register_routes(
    ("FLAP-E10",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0 --collective 8 --flap-model rigid --outdir outputs/physics_checks/manual/flap-e10. Inspect beta_0_rad, beta_coeffs, beta_1c, and beta_1s in the exported result.",
    "Open the starter rotor project. Run the Rigid flap model in hover. In Results, inspect beta_0, beta_1c, beta_1s, and the flap coefficient fields and confirm that each key exists with zero.",
)
_register_routes(
    ("FLAP-E11",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0 --collective 8 --trim-mode solve_collective --trim-target-thrust 20000. Then run python -m zbemt.cli --project projects/starter_rotor --collective 8 --trim-mode solve_rpm --trim-target-thrust 20000. Compare achieved Thrust and solved controls.",
    "Open the starter rotor project. In Run Case Trim, set a 20000 N thrust target and solve Collective, then solve RPM. Run both trims and inspect achieved Thrust and solved controls in Results.",
)
_register_routes(
    ("FLAP-E12",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0 --collective 8 --trim-mode solve_collective --trim-target-thrust 300 --outdir outputs/physics_checks/manual/flap-e12. Inspect trim_target, trim_dof, trim_residual, and trim_converged in results.csv. Then run python tools/physics_checks/trim_exhaustion_probe.py --project projects/starter_rotor --target-thrust 400 --max-iter 1 and confirm that the exhausted trim records trim_converged as false.",
    "Open the starter rotor project. In Run Case, select Trim to thrust, Solve collective, and target 300 N. Run the case and inspect trim_target, trim_dof, trim_residual, and trim_converged in Results. The GUI does not expose the trim iteration cap; use the standardized CLI probe for the one-iteration exhaustion condition.",
)
_register_routes(
    ("DERIV-E2",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model offset --hinge-offset 0.05 --lock-number 8 --rpm 400 --mu-inplane 0.15 --collective 8 --set geom.dynamics.outer_max_iter=30 --set geom.dynamics.outer_tol_deg=0.0001. Repeat at advance ratios 0.20 and 0.25. Inspect outer iterations and residual.",
    "Open the starter rotor project. In Geometry, set Offset hinge, Lock number 8, outer limit 30, and tolerance 0.0001 degree. Run advance ratios 0.15, 0.20, and 0.25. Inspect flap outer convergence in Results.",
)
_register_routes(
    ("FLAP-G4",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model spring --rpm 400 --mu-inplane 0 --collective 8 --set geom.dynamics.inertia_source=inertia --set geom.dynamics.flap_inertia_kg_m2=100 --set geom.dynamics.flap_spring_nm_per_rad=5000. Repeat with spring values 20000 and 100000. Compare flap frequency squared.",
    "Open the starter rotor project. In Geometry, select Spring flap, inertia 100 kg m^2, and spring values 5000, 20000, and 100000 N m/rad. Run hover and inspect flap frequency in Results.",
)
_register_routes(
    ("FLAP-G5",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model offset --hinge-offset 0.05 --rpm 400 --mu-inplane 0.15 --collective 8 --set geom.dynamics.lag_enabled=true --set geom.dynamics.lag_spring_nm_per_rad=8000 --set geom.dynamics.lag_inertia_kg_m2=100. Inspect lead-lag frequency and zeta coefficients.",
    "Open the starter rotor project. In Geometry, open Lead-lag, enable it, set spring 8000 N m/rad and inertia 100 kg m^2, then run 400 RPM and advance ratio 0.15. Inspect lead-lag frequency and zeta coefficients in Results.",
)
_register_routes(
    ("FLAP-G5B",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model rigid --rpm 400 --mu-inplane 0.15 --collective 8 --set geom.dynamics.lag_enabled=true --set geom.dynamics.lag_spring_nm_per_rad=8000 --set geom.dynamics.lag_inertia_kg_m2=100 --validate-only. Inspect the validation result and confirm that the configuration is not silently run.",
    "Open the starter rotor project. In Geometry, first select a non-rigid flap model and note the Lead-lag controls. Select Rigid and confirm that the GUI removes the inapplicable Lead-lag controls. Use the CLI route to validate the otherwise representable rigid-flap and enabled-lag combination and confirm that it cannot run silently.",
)
_register_routes(
    ("FLAP-H3",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/flap-h3. Add inputs/derivatives.bemt with cyclic_flapback studies at advance ratios 0.05, 0.10, and 0.15. Run python -m zbemt.cli --project outputs/physics_checks/manual/flap-h3 --derivatives flapback-005. Repeat with flapback-010 and flapback-015. Compare beta_1c, beta_1s, and cyclic controls.",
    "Open the prepared project and the Stability Derivatives window. Run cyclic flapback studies at advance ratios 0.05, 0.10, and 0.15. Inspect both first flap harmonics and solved cyclic controls.",
)
_register_routes(
    ("FLAP-H3B",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/flap-h3b. Add a saved case that uses solve_collective_and_cyclic with thrust target 18000 N and an offset-hinge blade. Run python -m zbemt.cli --project outputs/physics_checks/manual/flap-h3b --report outputs/physics_checks/manual/flap-h3b/result.html. Inspect execution status, Thrust, beta_1c, and beta_1s.",
    "Open the prepared project. In Run Case Trim, select Collective plus cyclics and target 18000 N with an offset-hinge blade. Run the case. Inspect execution status, Thrust, beta_1c, and beta_1s in Results.",
)
_register_routes(
    ("FLAP-H3C",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/flap-h3c with a saved cyclic-flapback study at advance ratio 0.15. Run python -m zbemt.cli --project outputs/physics_checks/manual/flap-h3c --derivatives flapback-015 --set geom.dynamics.outer_max_iter=40. Repeat with 120. Compare the convergence error and final residual.",
    "Open the prepared project and the Stability Derivatives window. Run flapback-015 with iteration limits 40 and 120. Inspect the convergence error and final residual.",
)

# Stability derivative checks use saved DerivativeRequest records. The CLI has
# no ad hoc derivative-study flags, so each route states its saved study.
_register_routes(
    ("DERIV-A1",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/deriv-a1. Add inputs/derivatives.bemt with a hover study named hover-rates, states p and q, outputs Mx_total and My_total, rate step 0.02 rad/s, and no trim. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-a1 --derivatives hover-rates --flap-model offset --lock-number 4 --hinge-offset 0.02 --derivatives-csv outputs/physics_checks/manual/deriv-a1/g4-e002.csv. Repeat with --lock-number 8 and --lock-number 16 and with --hinge-offset 0.05 and --hinge-offset 0.10. Compare the hover rate matrix invariance residuals.",
    "Open the prepared project. In Geometry, run Lock numbers 4, 8, and 16 and hinge offsets 0.02, 0.05, and 0.10. For each geometry, open the Stability Derivatives window, load hover-rates with p and q states and both hub moments, and inspect the rate matrix and its two invariance residuals.",
)
_register_routes(
    ("DERIV-A2",),
    "Prepare outputs/physics_checks/manual/deriv-a2 with inputs/derivatives.bemt studies named hover-heave and fwd015-heave using state w and output Thrust. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-a2 --derivatives hover-heave --flap-model rigid. Repeat with --flap-model offset and repeat fwd015-heave. Compare dThrust/dw and flap outer convergence.",
    "Open the prepared project and the Stability Derivatives window. Run hover-heave and fwd015-heave with Rigid and Offset hinge flap models. Inspect dThrust/dw and the flap convergence record.",
)
_register_routes(
    ("DERIV-A3",),
    "Prepare outputs/physics_checks/manual/deriv-a3 with inputs/derivatives.bemt study fwd010-rates, states p and q, and Mx, Mx_hub, Mx_total, and My_total outputs. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-a3 --derivatives fwd010-rates --flap-model rigid. Repeat with --flap-model offset. Compare aerodynamic pitch damping and the hub-moment balance.",
    "Open the prepared project and the Stability Derivatives window. Run fwd010-rates with Rigid and Offset hinge models. Inspect Mx, Mx_hub, and Mx_total. Compare aerodynamic pitch damping and the hub-moment balance.",
)
_register_routes(
    ("DERIV-A4",),
    "Prepare outputs/physics_checks/manual/deriv-a4 with inputs/derivatives.bemt study hover-rpm, state Omega, and outputs Thrust and Torque. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-a4 --derivatives hover-rpm --derivatives-csv outputs/physics_checks/manual/deriv-a4/rpm.csv. Inspect both RPM derivatives.",
    "Open the prepared project and the Stability Derivatives window. Load hover-rpm with state Omega and outputs Thrust and Torque. Run the study and inspect both RPM derivatives.",
)
_register_routes(
    ("DERIV-E1", "DERIV-P3"),
    "Prepare outputs/physics_checks/manual/deriv-e1 with inputs/derivatives.bemt hover-rates, states p and q, and outputs Mx_total and My_total. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-e1 --derivatives hover-rates --flap-model offset --hinge-offset 0.05 --lock-number 8 --derivatives-csv outputs/physics_checks/manual/deriv-e1/matrix.csv. Compare both rotational-invariance identities and direct damping terms.",
    "Open the prepared project and the Stability Derivatives window. Run hover-rates with offset 0.05 and Lock number 8. Inspect the four hub-moment rate derivatives and both invariance identities.",
)
_register_routes(
    ("DERIV-E3",),
    "Prepare outputs/physics_checks/manual/deriv-e3 with inputs/derivatives.bemt study fwd020-thrust-trim at advance ratio 0.20, base collective 10 degrees, trim thrust 1488.5 N, and collective bracket -10 to 30 degrees. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-e3 --derivatives fwd020-thrust-trim. Inspect completion or the named bracket error and confirm that no partial matrix is accepted.",
    "Open the prepared project and the Stability Derivatives window. Run fwd020-thrust-trim with the -10 to 30 degree collective bracket. Inspect the named bracket error or the complete derivative matrix.",
)
_register_routes(
    ("DERIV-H5", "DERIV-P6"),
    "Prepare outputs/physics_checks/manual/deriv-h5 with inputs/derivatives.bemt study fwd010-signs, states u, w, p, q, and Omega, controls theta_0, theta_1c, theta_1s, and hub-load outputs. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-h5 --derivatives fwd010-signs --derivatives-csv outputs/physics_checks/manual/deriv-h5/signs.csv. Inspect every prescribed derivative sign.",
    "Open the prepared project and the Stability Derivatives window. Run fwd010-signs with the listed states, controls, and hub-load outputs. Inspect all derivative signs in the matrix.",
)
_register_routes(
    ("DERIV-NONDIM-RATES",),
    "Prepare outputs/physics_checks/manual/deriv-nondim with inputs/derivatives.bemt hover-rates at 600 RPM, states p and q, and outputs Mx_total and My_total. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-nondim --derivatives hover-rates --derivatives-csv outputs/physics_checks/manual/deriv-nondim/rates.csv. Compare derivative and derivative_nondim after applying the shaft-speed scale.",
    "Open the prepared project and the Stability Derivatives window. Set 600 RPM and run hover-rates. Switch between Dimensional and Non-dimensional displays and compare p and q moment derivatives with the shaft-speed scaling.",
)
_register_routes(
    ("DERIV-P1",),
    "Prepare outputs/physics_checks/manual/deriv-p1 with inputs/derivatives.bemt hover-heave, state w with step 0.5 m/s, and output Thrust. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-p1 --derivatives hover-heave --derivatives-csv outputs/physics_checks/manual/deriv-p1/heave.csv. Compare dThrust/dw with -35 N/(m/s).",
    "Open the prepared project and the Stability Derivatives window. Run hover-heave with state w, step 0.5 m/s, and output Thrust. Inspect dThrust/dw and compare it with -35 N/(m/s).",
)
_register_routes(
    ("DERIV-P2",),
    "Prepare outputs/physics_checks/manual/deriv-p2 with inputs/derivatives.bemt hover-pitch, state q with step 0.02 rad/s, and output Mx_total. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-p2 --derivatives hover-pitch --flap-model offset --lock-number 8. Compare dMx/dq with -20.2 N m/(rad/s).",
    "Open the prepared project and the Stability Derivatives window. Run hover-pitch with q step 0.02 rad/s, output Mx_total, and Lock number 8. Compare dMx/dq with -20.2 N m/(rad/s).",
)
_register_routes(
    ("DERIV-P4",),
    "Prepare outputs/physics_checks/manual/deriv-p4 with inputs/derivatives.bemt hover-rigid-rates, states p and q, and both hub moments. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-p4 --derivatives hover-rigid-rates --flap-model rigid. Inspect the rigid rate matrix.",
    "Open the prepared project and the Stability Derivatives window. Run hover-rigid-rates with the Rigid model. Inspect all four hub-moment rate derivatives.",
)
_register_routes(
    ("DERIV-P5",),
    "Prepare outputs/physics_checks/manual/deriv-p5 with inputs/derivatives.bemt hover-controls, controls theta_1c and theta_1s, and both hub moments. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-p5 --derivatives hover-controls --flap-model offset. Inspect the cyclic-control matrix.",
    "Open the prepared project and the Stability Derivatives window. Run hover-controls with both cyclic controls and both hub moments. Inspect the four cyclic-control derivatives.",
)
_register_routes(
    ("DERIV-P7",),
    "Prepare outputs/physics_checks/manual/deriv-p7 with hover and advance-ratio 0.20 rate studies in inputs/derivatives.bemt. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-p7 --derivatives hover-rates --flap-model rigid and repeat with offset. Repeat both models for fwd020-rates. Compare damping magnitudes.",
    "Open the prepared project and the Stability Derivatives window. Run hover-rates and fwd020-rates with Rigid and Offset hinge models. Compare roll and pitch damping magnitudes.",
)

# Explicit limitations and reporting routes.
_register_routes(
    ("LAG-CORIOLIS-LIMITATION",),
    "Run python -m zbemt.cli --project projects/starter_rotor --flap-model offset --rpm 400 --mu-inplane 0.15 --collective 8 --set geom.dynamics.lag_enabled=true --set geom.dynamics.lag_spring_nm_per_rad=8000 --set geom.dynamics.lag_inertia_kg_m2=100. Inspect the zeta response and confirm that no flap-lag Coriolis term is reported.",
    "Open the starter rotor project. In Geometry, enable Lead-lag with the offset flap model. Run the case at advance ratio 0.15. In Results, inspect zeta outputs and the documented absence of flap-lag Coriolis coupling.",
)
_register_routes(
    ("PP-B10",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/pp-b10 with a constant Pitt-Peters maneuver in inputs/maneuvers.bemt. Run python -m zbemt.cli --project outputs/physics_checks/manual/pp-b10 --inflow pitt_peters_unsteady --maneuver constant-pp --maneuver-substeps 1. Repeat with --maneuver-substeps 8. Compare final inflow states and finite histories.",
    "Open the prepared project and the Transient window. Run constant-pp with one substep and eight substeps. Compare final inflow states and confirm that both histories remain finite.",
)
_register_routes(
    ("PP-LINEAR-LIMITATION",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.20 --collective 16 --inflow pitt_peters_steady --plots disk_map. Inspect the reversed-total-inflow fraction, warning, CT, and CQ without clamping the disk map.",
    "Open the starter rotor project. Run Pitt-Peters steady at 400 RPM, in-plane advance ratio 0.20, and collective 16 degrees. In Results, inspect the reversed-total-inflow fraction, warning, CT, CQ, and disk map.",
)
_register_routes(
    ("PP-PHASE-CONVENTION",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.15 --collective 8 --inflow pitt_peters_steady --plots disk_map. Rotate the saved sideslip by 90 degrees in a project copy, rerun, and compare the nu_s and nu_c phase with unchanged CT.",
    "Open the starter rotor project. Run Pitt-Peters steady at advance ratio 0.15 with sideslip 0 and 90 degrees. Compare nu_s, nu_c, the inflow disk-map phase, and CT in Results.",
)
_register_routes(
    ("DERIV-A5",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/deriv-a5. Add inputs/derivatives.bemt with flap studies named fwd015, fwd020, and fwd025 at in-plane advance ratios 0.15, 0.20, and 0.25. Include states u, w, p, and q and hub-load outputs. Run python -m zbemt.cli --project outputs/physics_checks/manual/deriv-a5 --derivatives fwd015 --flap-model offset. Repeat with fwd020 and fwd025. Compare every derivative with the base and perturbed flap convergence records.",
    "Open the prepared project and the Stability Derivatives window. Run the saved flap studies at advance ratios 0.15, 0.20, and 0.25. Inspect the base and perturbed flap convergence records before accepting any derivative in the matrix.",
)
_register_routes(
    ("DS-MANEUVER-REPORTING",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/ds-reporting. Add inputs/maneuvers.bemt with a four-revolution dynamic-stall maneuver named ds-reporting, 72 azimuth steps per revolution, and march_dynamic_stall=true. Run python -m zbemt.cli --project outputs/physics_checks/manual/ds-reporting --maneuver ds-reporting. Inspect history dimensions, the four-revolution interval, 288 steps, and periodic residual in the CSV and report.",
    "Open the prepared project and the Transient window. Run the four-revolution ds-reporting case with 72 azimuth steps per revolution and dynamic-stall marching enabled. In transient Results, inspect history dimensions, 288 steps, and periodic residual.",
)
_register_routes(
    ("PP-B9",),
    "Copy projects/starter_rotor to outputs/physics_checks/manual/pp-b9. Add inputs/maneuvers.bemt with a Pitt-Peters maneuver named pp-reporting and a declared substep count. Run python -m zbemt.cli --project outputs/physics_checks/manual/pp-b9 --inflow pitt_peters_unsteady --maneuver pp-reporting. Inspect marched interval, substep count, periodic residual, and convergence in the time-history CSV.",
    "Open the prepared project and the Transient window. Run pp-reporting. In transient Results, inspect the marched interval, substep count, periodic residual, and convergence state.",
)
_register_routes(
    ("REPO-PITT-WARNING",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.15 --collective 16 --inflow pitt_peters_steady --outdir outputs/physics_checks/manual/pitt-warning. Inspect the Pitt-Peters warning text in console output and results.csv.",
    "Open the starter rotor project. Run Pitt-Peters steady at 400 RPM, in-plane advance ratio 0.15, and collective 16 degrees. In Results, inspect the Pitt-Peters warning and confirm that it is complete English text.",
)

# Extreme-condition checks.
_register_routes(
    ("EXT-D1",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --v-axial -12 --collective 8. Repeat at --v-axial -8, -4, 0, 4, 8, 12, and 16, then run --v-axial 20. Compare CT and convergence through the full sweep.",
    "Open the starter rotor project. In Run Batch, sweep axial speed from -12 to 20 m/s through the listed values at 400 RPM and collective 8 degrees. Run the batch. Inspect CT and convergence in Results.",
)
_register_routes(
    ("EXT-D2",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --v-axial -8 --collective 8 and repeat at -12 m/s. Inspect convergence_pct and finite load outputs.",
    "Open the starter rotor project. In Run Batch, add axial speeds -8 and -12 m/s at 400 RPM and collective 8 degrees. Inspect convergence percentage and loads in Results.",
)
_register_routes(
    ("EXT-D3",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --mu-inplane 0.15 --collective 10. Read CT, CT_prop, CQ, and CP_prop and evaluate both convention-normalization identities.",
    "Open the starter rotor project. Run 400 RPM, in-plane advance ratio 0.15, and collective 10 degrees. In Results, inspect CT, CT_prop, CQ, and CP_prop and evaluate both identities.",
)
_register_routes(
    ("EXT-D4",),
    "Prepare outputs/physics_checks/manual/ext-d4 with cases that produce 99.9% and less than 99.5% convergence. Run python -m zbemt.cli --project outputs/physics_checks/manual/ext-d4 --rpm 400 --v-axial 20 --collective 16. Inspect convergence_pct and the EN-11 warning for both saved cases.",
    "Open the prepared project. Run the saved 99.9% and below-99.5% convergence cases from Run Case. In Results, compare convergence percentage and the EN-11 warning.",
)
_register_routes(
    ("EXT-D5",),
    "Run python -m zbemt.cli --project projects/starter_rotor --rpm 400 --v-axial 10 --collective 0. Repeat at axial speeds 11, 19, 20, and 25 m/s. Compare CT and CQ zero crossings.",
    "Open the starter rotor project. In Run Batch, add axial speeds 10, 11, 19, 20, and 25 m/s at collective 0 degrees. Inspect CT and CQ in Results and locate both zero crossings.",
)
_register_routes(
    ("EXT-D6",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 2400 --j-axial 0 --collective 0 and repeat J 0.1 through 1.6 by 0.1. Compare eta_prop, CT_prop, and CP_prop across the envelope.",
    "Open the starter propeller project. In Run Batch, sweep axial advance ratio 0 to 1.6 by 0.1 at 2400 RPM. Inspect eta_prop, CT_prop, and CP_prop in Results.",
)
_register_routes(
    ("PROP-G8",),
    "Run python -m zbemt.cli --project projects/starter_propeller --rpm 600 --v-axial 7.5 --v-inplane 0 --collective 0 --set config.use_compressibility=false. Repeat with cross-flow speeds 30 and 60 m/s through --v-inplane. Compare alpha_disk and CT_prop at approximately 0, 76, and 83 degrees, and verify that every value is finite and changes smoothly without a supersonic-tip warning.",
    "Open the starter propeller project. Disable compressibility. In Run Batch, keep axial speed at 7.5 m/s and sweep cross-flow speed through 0, 30, and 60 m/s at 600 RPM. Inspect alpha_disk and CT_prop near 0, 76, and 83 degrees, and verify that every value is finite and changes smoothly without a supersonic-tip warning.",
)


_REQUIREMENT_GROUPS = (
    (("BEMT-C6",), ("SC-1", "EN-10", "QR-8")),
    (("BEMT-C11", "STALL-DELAY-RATIO"), ("SC-2", "EN-4", "QR-8")),
    (("BEMT-C4", "PROP-T5A"), ("SC-2", "EN-4", "QR-8")),
    (("BEMT-C5", "MODEL-G3", "PROP-FB"), ("SC-2", "EN-4", "QR-8")),
    (("BEMT-C10",), ("SC-1", "EN-6", "QR-8")),
    (("EXT-D4",), ("SC-1", "EN-11")),
    (("FLAP-E2",), ("SC-11", "EN-8", "QR-8")),
    (("FLAP-E10", "FLAP-E12"), ("SC-11", "RP-3", "QR-1")),
    (("FLAP-G5B",), ("SC-11", "PR-6", "QR-1")),
    (("FLAP-H3B",), ("SC-11", "QR-1")),
    (("PROP-K8",), ("PR-6", "QR-1")),
    (("REPO-PITT-WARNING",), ("QR-5",)),
    (("DERIV-NONDIM-RATES",), ("SC-14", "QR-8")),
    (("LAG-CORIOLIS-LIMITATION",), ("SC-11",)),
    (("PP-LINEAR-LIMITATION", "PP-PHASE-CONVENTION", "PP-B10"), ("SC-2",)),
    (("DERIV-A5",), ("SC-14", "EN-11")),
    (("PROP-N1",), ("SC-1", "RP-3")),
)


def _requirement_codes(claim_id: str, domain: str) -> tuple[str, ...]:
    """Return the requirement codes that govern one claim."""
    for claim_ids, codes in _REQUIREMENT_GROUPS:
        if claim_id in claim_ids:
            return codes
    if domain == "dynamic_stall":
        return ("SC-12", "QR-8")
    if domain == "pitt_peters":
        return ("SC-2", "SC-12", "QR-8")
    if domain == "flapping":
        return ("SC-11", "QR-8")
    if domain == "lead_lag":
        return ("SC-11", "QR-8")
    if domain == "stability_derivatives":
        return ("SC-14", "QR-8")
    if domain == "reporting":
        return ("RP-3", "EN-9")
    if domain == "model_effects":
        return ("SC-2", "EN-4", "QR-8")
    if domain == "input_validation":
        return ("PR-6", "QR-1")
    return ("SC-1", "QR-8")


def claim_details(
    claim_id: str,
    title: str,
    domain: str,
) -> tuple[str, str, str, str, tuple[str, ...]]:
    """Return the complete static detail record for one canonical claim."""
    try:
        reference_text, acceptance_rule = _REFERENCE_AND_RULE[claim_id]
    except KeyError as exc:
        raise ValueError(f"Missing claim details for {claim_id}: {title}") from exc
    try:
        cli_base, gui_base = _CLAIM_ROUTE_BASES[claim_id]
    except KeyError as exc:
        raise ValueError(f"Missing reproduction route for {claim_id}: {title}") from exc
    cli_route = f"{cli_base} For {claim_id}, {acceptance_rule}"
    gui_route = f"{gui_base} For {claim_id}, {acceptance_rule}"
    return (
        reference_text,
        acceptance_rule,
        cli_route,
        gui_route,
        _requirement_codes(claim_id, domain),
    )
