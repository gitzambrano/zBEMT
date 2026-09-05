"""Temporary transformer for the user-facing documentation audit.

This script is intentionally kept out of the product. It rewrites only user-facing
HTML/help prose and adds a regression test. Delete this file after the audit lands.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "documentation.html"
HELP = ROOT / "zbemt" / "gui" / "help_content.py"
BLOCKS = ROOT / "zbemt" / "gui" / "help_blocks.py"
REQ = ROOT / "docs" / "software_requirements.md"
TEST = ROOT / "tests" / "architecture" / "test_user_facing_documentation.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one occurrence, found {n}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    out, n = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f"{label}: expected one regex match, found {n}")
    return out


def update_documentation() -> None:
    text = DOC.read_text(encoding="utf-8-sig")

    text = replace_once(
        text,
        "The core solver uses NumPy, SciPy, Matplotlib, and pandas. <span class=\"gui\">GUI</span>, three-dimensional visualization, interactive reporting, and external polar generation are\n      optional dependencies. This separation permits headless batch execution. Therefore you can run a batch without a graphics stack.",
        "The base installation provides command-line analysis and batch execution. <span class=\"gui\">GUI</span>, three-dimensional visualization, interactive reporting, and external polar generation require the corresponding optional dependencies.",
        "installation dependencies",
    )

    text = sub_once(
        text,
        r'<p>If the shell does not find the commands,.*?python -m zbemt\.cli.*?</p>',
        '<p>If the shell does not find <code>zbemt</code> or <code>zbemt-gui</code>, verify that zBEMT is installed in the active Python environment and that the environment\'s command directory is on <code>PATH</code>.</p>',
        "module-path launch fallback",
    )

    text = replace_once(
        text,
        "      Without installing, the equivalents are <code>python -m zbemt.gui.app</code> and\n      <code>python -m zbemt.cli</code>. The window opens maximized and empty. The first step is always the <b>Project</b> tab. There you choose one of the examples that come preinstalled (<a class=\"xref\" href=\"#cap-0-5\" title=\"3.2.5 First use\">Section 3.2.5</a>) or create a new project.",
        "      The window opens on the <b>Project</b> tab. Select an installed example (<a class=\"xref\" href=\"#cap-0-5\" title=\"3.2.5 First use\">Section 3.2.5</a>) or create a project.",
        "tutorial module-path fallback",
    )

    text = replace_once(
        text,
        "<b><span class=\"gui\">GUI</span></b>, the <b><span class=\"bemt\">.bemt</span></b> project files, and the\n      <b><span class=\"cli\">CLI</span></b> use the same validation, solver, and reporting paths. Equivalent\n      inputs therefore produce equivalent numerical results. This chapter defines the role of each interface. It identifies the file that stores each setting. It describes the outputs that a run produces.",
        "<b><span class=\"gui\">GUI</span></b>, <b><span class=\"bemt\">.bemt</span></b> project files, and the <b><span class=\"cli\">CLI</span></b> describe the same analysis case. Equivalent inputs produce equivalent numerical results. This chapter explains the role of each interface, where settings are stored, and what a run produces.",
        "interfaces internal paths",
    )

    text = replace_once(
        text,
        "                          <code>zbemt</code> is available. Without installing, <code>python -m zbemt.cli</code> is the\n                          equivalent.",
        "                          <code>zbemt</code> is available from the active environment.",
        "cli module-path fallback",
    )

    text = sub_once(
        text,
        r'<p>An example project with an articulated blade lives at\s*<a href="#cap-projeto"[^>]*><code>projects/test13</code></a>\.</p>',
        '<p>Use the blade-dynamics controls above to define an articulated blade. Save the project before using the same configuration in a batch or from the CLI.</p>',
        "test project reference",
    )

    text = replace_once(
        text,
        "The Geometry tab describes the blade. Two numbers apply to the rotor as a whole: the number of\n      blades and the radius. The rest of the blade is a table that gives the chord and the twist at a\n      series of radial stations. The solver reads only the table, independently of what produced it. A blade\n      generated from a preset and a blade entered cell by cell are the same object once they are on\n      screen.",
        "The Geometry tab defines the blade. The number of blades and radius apply to the complete rotor. A radial table defines local chord and twist. Presets and manual entry both populate this table, so equivalent table values define equivalent geometry.",
        "geometry implementation prose",
    )

    text = replace_once(
        text,
        "                <p>This block holds the two-dimensional contour of the section: the shape itself, not the blade\n                  planform. It is required only when a polar is to be generated from the shape, which is the external\n                  solver of 8.8. With an analytical or an already tabulated polar it is optional and purely\n                  illustrative, feeding the profile preview and nothing else.</p>\n\n                <p>The contour never enters the blade element equations. What the solver reads is the polar, and the\n                  shape reaches the solution only through the coefficients a generator produces from it. Once those\n                  coefficients exist, editing the contour changes nothing until the generator is run again. The\n                  sources below are eight ways of arriving at the same thing, a list of normalized coordinate\n                  pairs.</p>",
        "                <p>This block defines the two-dimensional section contour, not the blade planform. A contour is required when a polar is generated from geometry. It is optional when an analytical or tabulated polar already defines the aerodynamic coefficients.</p>\n\n                <p>Aerodynamic analysis uses the polar coefficients. Editing the contour therefore does not change aerodynamic results until a new polar is generated. Each source option below defines the same output: normalized section coordinates.</p>",
        "profile contour implementation prose",
    )

    text = replace_once(
        text,
        "                <p><b>The physics.</b> The contour never enters the blade element equations. What the solver reads\n                  is the polar, and the shape matters only because a polar can be generated from it. A profile is\n                  therefore needed when a polar is to be produced from the section itself. It is optional, and purely\n                  illustrative, when the polar is analytical or already tabulated.</p>",
        "                <p><b>The physics.</b> Blade-element forces depend on aerodynamic coefficients from the selected polar. The contour matters when those coefficients are generated from section geometry. It is optional when the polar is analytical or already tabulated.</p>",
        "profile physics implementation prose",
    )

    text = sub_once(
        text,
        r'<p><b>Drawing resolution\.</b>.*?</p>',
        '<p><b>Drawing resolution.</b> Preview resolution controls display detail and interaction speed only. It does not change the analysis mesh or numerical results. Use a lower preview resolution for faster interaction and increase it only when finer visual detail is needed.</p>',
        "drawing implementation prose",
    )

    text = replace_once(
        text,
        "The formulation in the physics chapters is developed in standard <b>disk-oriented rotor coordinates</b>,\n      matching the internal solver frame. This chapter details the physical distinctions and the coordinate\n      transformations that an <b>airplane propeller</b> introduces: flow axis alignment, non-dimensional\n      parameter conventions, incident inflow angle definitions, and applicable propulsive efficiency metrics.",
        "The physics chapters use disk-oriented rotor coordinates. Propeller mode expresses the same physical quantities using shaft-oriented flight variables and standard propeller non-dimensional coefficients. This section defines the coordinate conventions, inflow angles, and efficiency measures used in each mode.",
        "propeller internal frame",
    )

    text = sub_once(
        text,
        r'<p>The core governing equations of Blade Element Momentum Theory remain identical across both modes\.\s*The numerical solver accepts.*?pure axial cruise:</p>',
        '<p>Blade Element Momentum Theory uses the same force and momentum balances in rotor and propeller modes. The selected mode changes the flight-variable convention and which asymmetric-flow effects are relevant. In pure axial propeller operation, the following edgewise-flow effects are inactive:</p>',
        "propeller numerical solver",
    )

    text = replace_once(
        text,
        "This section defines\n      the mapping between display symbols and internal solver keys.",
        "This section defines the user-facing notation for each operating mode.",
        "display to internal key mapping",
    )

    text = replace_once(
        text,
        "<p>Project files and internal engine variables maintain disk-aligned coordinates and <b>do not rotate</b>.\n      User interfaces, tabular outputs, and generated plots display vehicle-fixed notation corresponding to\n      the selected operating mode:</p>",
        "<p>Project inputs, tabular outputs, and plots use the notation associated with the selected operating mode. The following table relates the rotor and propeller conventions:</p>",
        "internal engine variables",
    )

    text = sub_once(
        text,
        r'<div class="boxed note">\s*zBEMT calculates both coefficient families.*?never what is calculated internally\.\s*</div>',
        '<div class="boxed note">\n      Rotor and propeller coefficient families represent the same dimensional forces and powers with different reference scales. The <code>is_propeller</code> setting selects the convention used by default in plots and sweeps (<a class="xref" href="#cap-projeto-1" title="6.1 Operation mode: rotor or propeller">Section 6.1</a>).\n    </div>',
        "cfg internal note",
    )

    DOC.write_text(text, encoding="utf-8")


def update_field_help() -> None:
    text = HELP.read_text(encoding="utf-8-sig")

    substitutions = {
        "A batch is what makes a set of runs repeatable: the same ": "A saved batch makes a set of runs repeatable. Re-running the same ",
        "queue, re-run after a change to the blade, is the only way ": "queue after a blade change provides a consistent basis ",
        "to say the change did anything.": "for comparison.",
        "A factorial builds the FULL CROSS PRODUCT": "A factorial builds the full Cartesian product",
        "that WRITES into this ": "that writes into this ",
        "It changes what a comparison MEANS.": "It changes the basis of the comparison.",
        "A variation study answers one question at a time: what ": "A variation study changes one parameter at a time so the ",
        "happens when THIS changes and nothing else does.": "effect of that parameter can be isolated.",
        "The search minimizes internally, so a maximization is ": "Choose Maximize when larger objective values are preferred and ",
        "carried as its negative. Getting the direction wrong does ": "Minimize when smaller values are preferred. The selection changes ",
        "not fail: it converges, on the worst design it can find.": "the optimization direction, not the objective definition.",
        "Note: the contour reaches the engine only through the polar ": "Aerodynamic results use the polar generated from the contour. ",
        "generated from it. Changing the numbers changes nothing until ": "Changing these geometry parameters does not affect aerodynamic results until ",
        "polar generation runs again.": "the polar is regenerated.",
        "Note: the contour reaches the engine only through the polar ": "Aerodynamic results use the polar generated from the contour. ",
        "generated from it. Changing the code changes nothing until polar ": "Changing the NACA code does not affect aerodynamic results until the polar ",
        "generation runs again.": "is regenerated.",
        "used only by the XFOIL engine.": "used only by XFOIL polar generation.",
        "The value reaches only the XFOIL binary; other engines ignore it.": "Other polar-generation methods ignore this setting.",
        "because the engine needs one to form the tip speed.": "because rotational speed is required to determine tip speed.",
        "The engine reads the pair as one in-plane speed and one ": "Together, the two components define the in-plane speed and ",
        "direction, V = √(V<sub>x</sub>² + V<sub>y</sub>²) at ": "direction: V = √(V<sub>x</sub>² + V<sub>y</sub>²) and ",
        "ψ<sub>w</sub> = atan2(V<sub>y</sub>, V<sub>x</sub>). Zero ": "ψ<sub>w</sub> = atan2(V<sub>y</sub>, V<sub>x</sub>). A zero value ",
        "reproduces the plain edgewise case, so every condition saved ": "gives the standard edgewise case. Conditions saved ",
        "before this field existed keeps its exact behavior.": "without this field therefore retain the same behavior.",
        "which is nearly always the intended question.": "which is appropriate when equal thrust is the required comparison basis.",
        "which is the fairer comparison between different diameters.": "which supports comparison at equal non-dimensional loading across different diameters.",
        "and it is worth reading before running.": "and should be checked before running.",
        "The CSV is the numbers.": "The CSV contains the numerical data used by the figures.",
        "Unlike the others it rescales EVERYTHING at once": "This variable changes the reference tip speed and therefore rescales several quantities at once",
        "It models ONE ROTOR": "It models one rotor",
    }
    for old, new in substitutions.items():
        if old in text:
            text = text.replace(old, new)

    # Keep the public term "engine" where it means an aircraft engine or governor.
    # Remove it only when it refers to zBEMT implementation details.
    text = text.replace("the engine needs one to form the tip speed", "tip speed requires rotational speed")
    text = text.replace("the XFOIL engine", "XFOIL")
    text = text.replace("other engines ignore it", "other polar-generation methods ignore it")

    HELP.write_text(text, encoding="utf-8")


def update_block_help() -> None:
    text = BLOCKS.read_text(encoding="utf-8-sig")

    replacements = {
        "The same solver runs both. What changes is the <b>reference frame the answer is reported in</b>, and that choice is not cosmetic. The two conventions non-dimensionalize thrust and power by different scales, so the same physical rotor produces two entirely different sets of numbers.":
            "Rotor and propeller modes use the same physical model but report results with different reference conventions. The two conventions use different scales for non-dimensional thrust and power, so their coefficient values are not interchangeable.",
        "The engine solves the same blade-element/momentum coupling either way.":
            "The blade-element and momentum balances are unchanged between the two conventions.",
        "Between rows the engine interpolates linearly, so the table is a piecewise-linear description of a real blade, not a set of independent design points.":
            "Values between rows are linearly interpolated. The table therefore defines a piecewise-linear blade geometry rather than independent design points.",
        "With two or more sections defined, the engine assigns each blade element the polar of the <b>nearest</b> defined station and no longer looks at the single-airfoil definition at all. There is no blending between neighboring sections: the change is a step at the midpoint between two stations, which is visible as a discontinuity in the spanwise load if the two polars differ strongly.":
            "With two or more radial sections, each blade element uses the polar of the <b>nearest</b> defined station. Neighboring section polars are not blended. The transition occurs at the midpoint between stations and can create a visible spanwise-load discontinuity when the polars differ strongly.",
        "They are a <b>viewing</b> choice only. Nothing here changes the project or the computation. During a run the engine picks the slice for each element from that element's own local conditions, interpolating between the tabulated values.":
            "These controls change the preview only. During analysis, each blade element uses the polar data associated with its local conditions, with interpolation between tabulated values where applicable.",
        "The table may carry additional axes: one curve per Reynolds number, per Mach number, per spanwise station. The engine interpolates between them using each element's own local conditions. A table that already resolves Mach must <b>not</b> be combined with the compressibility correction: that applies the same physics twice.":
            "A table can include Reynolds number, Mach number, and spanwise position as additional axes. Local blade-element conditions select or interpolate the applicable data. Do <b>not</b> combine a Mach-resolved table with the separate compressibility correction, because that applies the same effect twice.",
        "The factor is 1.005 at M = 0.1, 1.048 at M = 0.3, 1.25 at M = 0.6 and formally diverges at M → 1, which is why the engine floors β instead of letting it diverge. Above M from approximately 0.75 to 0.8 the linearization is void anyway: shocks and wave drag are not modeled.":
            "The factor is 1.005 at M = 0.1, 1.048 at M = 0.3, and 1.25 at M = 0.6. It diverges as M approaches 1, where the correction is not valid. Above approximately M = 0.75 to 0.8, shocks and wave drag make this linear correction unsuitable.",
        "Two external engines generate the polar from the 2D contour. <b>NeuralFoil</b> is a neural network trained on a large body of XFOIL runs: given the contour and (α, Re, M) it returns Cl and Cd in milliseconds. <b>XFOIL</b> runs the classic boundary-element binary directly. It gives higher fidelity where it converges and takes minutes instead of milliseconds, and it needs the executable installed (zBEMT looks in ZBEMT_XFOIL_BIN, your remembered Locate… choice, PATH, and the standard install folders).":
            "Two external methods can generate a polar from a two-dimensional contour. <b>NeuralFoil</b> evaluates a trained aerodynamic model and is fast. <b>XFOIL</b> runs the established panel and boundary-layer method and is slower but useful as an independent reference where it converges. XFOIL requires an installed executable selected in the GUI or available on <code>PATH</code>.",
        "What comes out is an ordinary tabulated polar: one complete Cl(α), Cd(α) curve per (Re, M) pair. From that point on the engine treats it exactly like an imported table: linear interpolation in α, selection/interpolation of the slice by local Re, M and r/R.":
            "The output is a tabulated polar with one complete C<sub>l</sub>(α), C<sub>d</sub>(α) curve for each Reynolds-number and Mach-number pair. Analysis then uses it in the same way as an imported polar table.",
        "The contour never enters the blade element equations. It matters in exactly two places: drawing, and generating a polar with NeuralFoil. Once a polar exists, the engine only ever sees Cl(α, Re, M) and Cd(α, Re, M).":
            "The contour is used for geometry visualization and polar generation. Once a polar exists, aerodynamic forces depend on C<sub>l</sub>(α, Re, M) and C<sub>d</sub>(α, Re, M), not directly on the contour coordinates.",
        "Everything else in the engine is preparation for this root find.":
            "The required solution is the induced-inflow field that satisfies this equation at every node.",
        "A FAIL here means an engine sign flipped somewhere, not that your rotor is exotic.":
            "A FAIL indicates an inconsistency in the sign convention, derivative calculation, or model setup. Investigate it before using the derivatives.",
        "Everything the tabs edit lives in a single project file: geometry, airfoil definition, engine settings, saved flight conditions and saved case queues. It is the same file the command line reads, so a case set up in the window and a case run from a script are the same case.":
            "A project folder stores the geometry, airfoil definition, analysis settings, saved flight conditions, and saved case queues. The GUI and CLI use the same project data, so equivalent inputs define the same case.",
    }
    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError(f"block help replacement missing: {old[:70]!r}")
        text = text.replace(old, new, 1)

    # Titles use a colon instead of an em dash. This is clearer and follows G15.
    text = re.sub(r'("title":\s*"[^"\n]*?) — ([^"\n]*")', r'\1: \2', text)
    text = re.sub(r'("title":\s*"[^"\n]*?) - ([^"\n]*")', r'\1: \2', text)

    BLOCKS.write_text(text, encoding="utf-8")


def update_requirements() -> None:
    text = REQ.read_text(encoding="utf-8")
    old = (
        "- **DC-2** — Structure: introduction (chapters 0-5), one chapter per GUI tab in tab order\n"
        "  (6-12), the Geometry Designer window chapter (13), reference (14-15)."
    )
    new = (
        "- **DC-2** — Structure: introduction and physical method (chapters 0-5); one chapter per GUI tab in tab order\n"
        "  (6-12); Geometry Designer (13); Optimization, Transient, and Stability tool windows (14-16);\n"
        "  CLI and limitations (17-18); then symbols and references."
    )
    text = replace_once(text, old, new, "DC-2 stale chapter map")
    REQ.write_text(text, encoding="utf-8")


def add_regression_test() -> None:
    TEST.write_text(r'''"""Protect user-facing documentation from implementation-detail regressions."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def _visible_html() -> str:
    html = (ROOT / "docs" / "documentation.html").read_text(encoding="utf-8")
    body = html.split("<body", 1)[-1]
    body = re.sub(r"<script\b.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style\b.*?</style>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    return body


class TestUserFacingDocumentationBoundary(unittest.TestCase):
    """DC-5: user help describes the product, not source-code implementation."""

    def test_documentation_has_no_internal_code_surface(self):
        body = _visible_html()
        forbidden = {
            "python module launch path": r"python\s+-m\s+zbemt\.",
            "config object attribute": r"\bcfg\.[A-Za-z_]",
            "test project": r"projects/test\d+",
            "internal solver wording": r"\binternal solver\b",
            "internal engine wording": r"\binternal engine\b",
            "display-to-key implementation mapping": r"internal solver keys",
        }
        for label, pattern in forbidden.items():
            with self.subTest(label=label):
                self.assertIsNone(re.search(pattern, body, flags=re.I), label)

    def test_popup_copy_has_no_internal_optimization_explanation(self):
        source = (ROOT / "zbemt" / "gui" / "help_content.py").read_text(encoding="utf-8")
        for phrase in (
            "search minimizes internally",
            "reaches the engine only through",
            "engine reads the pair",
            "FULL CROSS PRODUCT",
            "comparison MEANS",
            "when THIS changes",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, source)

    def test_block_help_avoids_engine_implementation_language(self):
        source = (ROOT / "zbemt" / "gui" / "help_blocks.py").read_text(encoding="utf-8")
        for phrase in (
            "Everything else in the engine",
            "engine sign flipped",
            "engine interpolates",
            "engine assigns each blade element",
            "the engine floors",
            "the engine only ever sees",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, source)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")


def main() -> None:
    update_documentation()
    update_field_help()
    update_block_help()
    update_requirements()
    add_regression_test()
    print("documentation user-facing audit transformations applied")


if __name__ == "__main__":
    main()
