"""Second pass for the user-facing documentation audit.

Runs after _apply_documentation_user_audit.py and removes residual implementation
language, stale explanatory prose, and technically incorrect popup descriptions.
Delete this temporary file after the audited files are committed.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "documentation.html"
BLOCKS = ROOT / "zbemt" / "gui" / "help_blocks.py"
TEST = ROOT / "tests" / "architecture" / "test_user_facing_documentation.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one occurrence, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected one regex match, found {count}")
    return out


def update_documentation() -> None:
    text = DOC.read_text(encoding="utf-8")

    text = sub_once(
        text,
        r'<p><b>Axis conventions in rotor and propeller mode\.</b> In rotor mode, \$\\mu_x\$ denotes the in-plane advance\s*ratio.*?</p>',
        '<p><b>Axis conventions in rotor and propeller mode.</b> In rotor mode, $\\mu_x$ is the in-plane advance ratio and $\\mu_z$ is axial inflow along the shaft. In propeller mode, axial flight uses $J_x$ and cross-flow uses $J_z$. The GUI, CLI, project files, tables, and plots use the notation for the selected operating mode (<a class="xref" href="#cap-5-1" title="10.1 In-plane flow: the first row">Section 10.1</a>).</p>',
        "axis conventions internal variables",
    )

    text = sub_once(
        text,
        r'<p>Two features of the denominator are worth reading\..*?does not affect a converged result\.</p>',
        '<p>The denominator contains the local mass-flow speed $\\sqrt{\\lambda_{total}^{2}+\\mu_x^{2}}$. It reduces to the axial component in hover and increases with in-plane speed. Therefore the induced velocity required for a given load decreases as advance ratio increases. Hover at zero load is the limiting case in which both velocity components approach zero.</p>',
        "momentum denominator implementation detail",
    )

    text = replace_once(
        text,
        '<h4 id="cap-20-2">5.9.2 Order in which an element is evaluated</h4>',
        '<h4 id="cap-20-2">5.9.2 Element evaluation sequence</h4>',
        "element evaluation heading",
    )
    text = sub_once(
        text,
        r'<p>Given a trial field \$\\lambda_i\$, the function executes, vectorized over the entire \$N_e\\times N_\\psi\$ mesh,\s*the following sequence:</p>',
        '<p>For a trial field $\\lambda_i$, each mesh point is evaluated in the following sequence:</p>',
        "vectorized implementation prose",
    )

    text = replace_once(
        text,
        'That is worth doing before an unattended batch that will take hours.',
        'Use this check before an unattended batch.',
        "validate-only conversational prose",
    )
    text = replace_once(
        text,
        'They are worth opening because together they cover both operating modes, common machine sizes, and most of the available models.',
        'Together they cover both operating modes, common machine sizes, and most available models.',
        "examples conversational prose",
    )
    text = replace_once(
        text,
        'More is worth having only where the planform changes rapidly.',
        'Use more stations only where the planform changes rapidly.',
        "geometry resolution conversational prose",
    )

    text = sub_once(
        text,
        r'<h3 id="cap-3-8">8\.8 External polar generation</h3>\s*<p>Two external engines estimate.*?</p>',
        '<h3 id="cap-3-8">8.8 External polar generation</h3>\n                <p>Two external methods can generate tabulated polars from a two-dimensional contour. <b>NeuralFoil</b> provides fast estimates over an angle, Reynolds-number, and Mach-number grid. <b>XFOIL</b> provides an independent panel and boundary-layer calculation where it converges. XFOIL requires an installed executable selected in the GUI or available on <code>PATH</code>.</p>',
        "external engines implementation prose",
    )

    text = sub_once(
        text,
        r'<p>The solver never sees the constraint as a penalty.*?lawbreakers.*?</p>',
        '<p>Feasible designs are always preferred to infeasible designs. Among infeasible designs, smaller total constraint violation is preferred. This keeps a physical limit separate from the objective value.</p>',
        "optimization constraint implementation prose",
    )

    text = text.replace('ONE chord', 'one chord')
    text = text.replace('ONE quantity', 'one quantity')
    text = text.replace('RESISTS', 'resists')
    text = text.replace('SHORT compared with', 'short compared with')
    text = text.replace('The SAMPLE interval', 'The sample interval')
    text = text.replace('The SUB-STEP is', 'The sub-step is')
    text = text.replace('yaw DAMPING', 'yaw damping')
    text = text.replace('belong to the ROTOR', 'belong to the rotor')

    text = sub_once(
        text,
        r'<p>The matrix lists outputs down the rows.*?The SIGN CHECKS panel is the window\'s conscience:',
        '<p>The matrix lists outputs down the rows and variables across the columns. The display can switch between dimensional and non-dimensional derivatives without rerunning. Forces are divided by $\\rho A(\\Omega R)^2$, moments by $\\rho A(\\Omega R)^2 R$, speeds by $\\Omega R$, and rates by $\\Omega$. The bar chart compares one output across all variables. The <i>Sign checks</i> panel verifies basic expected trends:',
        "stability results conversational prose",
    )

    text = sub_once(
        text,
        r'<p>The <span class="cli">CLI</span> points at a project folder, runs the requested condition or\s*sweep, and writes the results\. It goes through the same code as the <span\s*class="gui">GUI</span>\s*and applies the same validation\. Therefore, a project run either way gives the same numbers\.</p>',
        '<p>The <span class="cli">CLI</span> opens a project folder, runs the requested condition or sweep, and writes the results. It uses the same project definition and validation rules as the <span class="gui">GUI</span>. Equivalent inputs therefore produce equivalent numerical results.</p>',
        "cli same-code implementation prose",
    )
    text = replace_once(
        text,
        'Every configuration is checked before the solver is called, and the same checks apply to the',
        'Every configuration is checked before analysis begins. The same checks apply to the',
        "validation solver-called prose",
    )
    text = replace_once(
        text,
        'Every editable project field remains reachable through\n                          the serialized project representation, including fields without a dedicated\n                          <span class="gui">GUI</span> control.',
        'Project files include all configurable analysis fields, including fields without a dedicated\n                          <span class="gui">GUI</span> control.',
        "serialized representation prose",
    )

    text = text.replace('nothing the other designs write &mdash; so the\n                          generation can be spread over several processes and reassembled afterwards.',
                        'independent of the other designs. Multiple workers can therefore evaluate designs concurrently.')
    text = text.replace('Nothing\n                          pays solver time to learn about a bad definition.',
                        'Invalid definitions are rejected before analysis begins.')

    text = text.replace('the mesh, solver, rotor and polar behind the results',
                        'the mesh, analysis settings, rotor geometry, and polar data used for the results')

    DOC.write_text(text, encoding="utf-8")


def update_block_help() -> None:
    text = BLOCKS.read_text(encoding="utf-8")

    text = replace_once(
        text,
        'With two or more radial sections, each blade element uses the polar of the <b>nearest</b> defined station. Neighboring section polars are not blended. The transition occurs at the midpoint between stations and can create a visible spanwise-load discontinuity when the polars differ strongly.',
        'With two or more radial sections, aerodynamic coefficients are interpolated between neighboring section polars as a function of r/R. This gives a continuous spanwise transition between the defined sections.',
        "radial-section interpolation correctness",
    )
    text = replace_once(
        text,
        'With zero or one section the tab is in single-airfoil mode and the whole blade uses one polar. That is the right choice when the polar is the dominant uncertainty anyway. A second section is only worth defining when its polar is genuinely known.',
        'With zero or one radial section, the complete blade uses one polar. Add sections when distinct spanwise polar data are available.',
        "radial-section concise guidance",
    )

    text = replace_once(
        text,
        'These controls change the preview only. During analysis, each blade element uses the polar data associated with its local conditions, with interpolation between tabulated values where applicable.',
        'These controls change the preview only. During analysis, coefficients are interpolated in angle of attack and radial position. Reynolds-number and Mach-number dimensions use the nearest available tabulated condition.',
        "polar navigator interpolation correctness",
    )

    text = replace_once(
        text,
        'An imported table replaces the analytical lift and drag model entirely. Instead of Cl = Cl_α(α − α₀) with a stall closure, the engine interpolates directly between the tabulated points. So everything the table contains (the real stall shape, the drag bucket, the Reynolds and Mach trends) is used, and everything it omits is invented by whatever extrapolation rule is active.',
        'An imported table replaces the analytical lift and drag model. Coefficients are linearly interpolated in angle of attack. The supplied data define stall shape, drag behavior, and any Reynolds-number, Mach-number, or radial variation represented by the table.',
        "table import engine interpolation",
    )
    text = replace_once(
        text,
        'A table can include Reynolds number, Mach number, and spanwise position as additional axes. Local blade-element conditions select or interpolate the applicable data. Do <b>not</b> combine a Mach-resolved table with the separate compressibility correction, because that applies the same effect twice.',
        'A table can include Reynolds number, Mach number, and spanwise position as additional axes. Radial sections are interpolated in r/R. Reynolds-number and Mach-number dimensions use the nearest available condition. Do <b>not</b> combine a Mach-resolved table with the separate compressibility correction, because that applies the same effect twice.',
        "table extra-axis interpolation correctness",
    )

    text = replace_once(
        text,
        '"<b>Tabulated source.</b> Direct linear interpolation over measured or XFOIL points "\n            "(α<sub>i</sub>, C<sub>l,i</sub>, C<sub>d,i</sub>), optionally one table per Reynolds, Mach and r/R "\n"(bilinear interpolation in the extra axis). It is accurate where the data exist. "',
        '"<b>Tabulated source.</b> Direct linear interpolation over measured or XFOIL points "\n            "(α<sub>i</sub>, C<sub>l,i</sub>, C<sub>d,i</sub>). Radial sections are interpolated in r/R. "\n"Reynolds and Mach dimensions use the nearest available condition. It is accurate where the data exist. "',
        "aerodynamic model extra-axis correctness",
    )

    text = replace_once(
        text,
        'More blades → smaller loss (closer to the continuous-curtain limit). Closer to an edge, or larger φ (more heavily loaded rotor), the faster F drops. In the code F multiplies the effective U<sub>P</sub> in the momentum balance: a smaller F means the same load must be sustained by a larger induced velocity over a smaller effective area.',
        'More blades reduce the loss and approach the continuous-disk limit. The factor decreases near the root and tip and at larger inflow angles. A smaller F represents a smaller effective lifting area, so the same local load requires more induced velocity.',
        "tip-loss implementation prose",
    )

    text = replace_once(
        text,
        'The disk is discretized into Ne radial × Npsi azimuthal stations; the solver evaluates all Ne×Npsi elements at once per iteration. Δψ = 360°/Npsi. Npsi = 1 means axisymmetric (hover or axial). Resolving advancing and retreating asymmetry needs enough harmonics: 24 is a minimum, and 72 to 144 for high μ or cyclic pitch. Radially, 30 to 50 is usually converged. The reference production mesh is 120×180.',
        'The disk is discretized into Ne radial × Npsi azimuthal stations. Δψ = 360°/Npsi. Npsi = 1 is axisymmetric and is appropriate for hover or axial flow. Edgewise flight and cyclic pitch require azimuthal resolution. Use at least 24 stations for basic asymmetric cases and refine the mesh until the integrated outputs are insensitive to further refinement.',
        "mesh implementation prose",
    )

    text = replace_once(
        text,
        '<b>Condition</b> is the saved case every candidate is solved at; rotation is mandatory because the solver adimensionalizes by &Omega;R.',
        '<b>Condition</b> is the saved case used to evaluate every candidate. Rotational speed is required because advance ratios and several coefficients use &Omega;R as a reference velocity.',
        "optimization condition implementation prose",
    )

    text = replace_once(
        text,
        '<b>Run comparison</b> solves every condition of every geometry on a worker thread, reports progress, and can be canceled.',
        '<b>Run comparison</b> evaluates every condition for every geometry, reports progress, and can be canceled.',
        "geometry comparison worker thread",
    )
    text = replace_once(
        text,
        'The line states the sample count times the sub-steps per sample, which is almost exactly the number of solver calls the march makes. It is arithmetic on the settings above and runs no physics.',
        'The line states the sample count times the sub-steps per sample, which estimates the number of analysis evaluations required by the march. It is calculated from the settings above without running the analysis.',
        "maneuver cost solver calls",
    )
    text = replace_once(
        text,
        'The figure draws the in-plane component and the axial speed of every sample against time. It shows the grid the march will read, therefore an interpolation or a sample interval that misrepresents the intended input is visible here before any solver time is spent.',
        'The figure draws the in-plane component and axial speed of every sample against time. It shows the sampled trajectory, so an unsuitable interpolation rule or sample interval is visible before the analysis runs.',
        "maneuver preview solver time",
    )

    text = text.replace('which is the cheap way to compare algorithms on the same problem',
                        'which provides a convenient way to compare algorithms on the same problem')
    text = text.replace('duplicate is the cheap way to rerun the same plan',
                        'Duplicate provides a convenient way to rerun the same plan')
    text = text.replace('which is the cheap way to march the same trajectory',
                        'which provides a convenient way to march the same trajectory')

    BLOCKS.write_text(text, encoding="utf-8")


def extend_guardrail() -> None:
    text = TEST.read_text(encoding="utf-8")
    text = text.replace(
        '"display-to-key implementation mapping": r"internal solver keys",',
        '"display-to-key implementation mapping": r"internal solver keys",\n            "implementation wording": r"\\bthe implementation\\b",\n            "vectorized implementation wording": r"\\bvectorized over\\b",\n            "function execution wording": r"the function executes",',
    )
    text = text.replace(
        '"the engine only ever sees",',
        '"the engine only ever sees",\n            "In the code F multiplies",\n            "bilinear interpolation in the extra axis",',
    )
    TEST.write_text(text, encoding="utf-8")


def main() -> None:
    update_documentation()
    update_block_help()
    extend_guardrail()
    print("extended documentation audit transformations applied")


if __name__ == "__main__":
    main()
