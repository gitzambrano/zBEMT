"""The single source of the axis nomenclature: one table, every surface.

WHAT PROBLEM THIS SOLVES
------------------------
The engine (`bemt.py`, Sec.6c) decomposes the free stream in DISK axes and
never changes its mind: `mu_x` is the in-plane component, `Vz` is the
component along the shaft. The user, however, reads VEHICLE axes -- and on a
propeller the shaft is horizontal, so the component the engine calls `z` is
the one the pilot calls `x`. The letters rotate; the physics does not.

That rotation used to be re-implemented by hand in ten places, each with a
comment claiming to be "the single source" for its own narrow surface:
`api._SIMBOLO_DE_COLUNA_HELICE` (report and table headers),
`viz/plots._SUMMARY_KEY_LABELS_HELICE` (plot axis labels),
`studies._SIMBOLO_DE_VARIAVEL_HELICE` (condition names),
`gui/widgets.UNIDADES_DE_CONDICAO` (input unit combos),
`gui/common._ROTULOS_DE_CONDICAO` (row labels and tooltips), and more. The
concrete cost: a report's table header and the axis label of the chart
embedded in that same report came from two different tables and could
silently disagree.

This module is that one table. Everything a human reads about a flow axis --
symbol, unit, tooltip, slot name, visibility, and the key written to disk --
comes from `QUANTITIES` below.

THE THREE RENDER TARGETS COME FROM ONE LATEX SOURCE
---------------------------------------------------
Each quantity stores its symbol ONCE, as a mathtext body (`r"\\mu_x"`). The
matplotlib label, the Qt rich-text label and the HTML report header are
DERIVED from it by `to_mathtext`/`to_html`/`to_unicode`. There is no second
list of HTML entities and no third list of Unicode subscripts to age
silently -- which is also what CLAUDE.md's "render all mathematical notation
in LaTeX" asks for.

LAYERING
--------
Pure data and pure functions: no Qt, no matplotlib, no argparse, no disk
access. It therefore sits below `api`, `studies`, `viz.plots`, `cli` and the
GUI, and all of them import it without a cycle. It reaches neither the engine
nor the disk, so it does not compete with the rule that `api` is the only
path to those.

THE KEY ROTATION
----------------
`display_key`/`to_display_keys` translate the engine's key into the one the
user sees -- and, in propeller mode, the one written into `.bemt` files, CSV
headers and the results table. Rotor mode is the identity, because the rotor
letters already are the engine letters.

The rotation is a SWAP (`mu_x` <-> `mu_z`), so `to_display_keys` builds a new
dict in a single pass. Renaming key by key would collapse both components
onto one value -- that is the one bug this module must never have, and
`tests/test_nomenclature.py::TestKeyRotation` holds the line on it.

A rotated dict is an OUTPUT. It is never fed back into the application: only
`from_display_keys`, at the same boundary that produced it, turns it back
into engine keys.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# The quantities
# =============================================================================

@dataclass(frozen=True)
class AxisQuantity:
    """One flow quantity, in both modes.

    `engine_key` is what `bemt.aggregate_results` emits and what
    `FlightCondition` stores in memory -- always disk axes, never rotated.
    Everything else is what the user sees, which depends on the mode.
    """

    engine_key: str
    #: `"inplane"` (in the disk plane), `"axial"` (along the shaft), or
    #: `"invariant"` (carries no axis letter: induced velocity,
    #: coefficients, collective, rpm).
    slot: str
    #: Symbol as a mathtext body, without the surrounding `$`.
    rotor_latex: str
    #: Same, in propeller axes. `None` means "does not rotate".
    propeller_latex: Optional[str] = None
    #: Key under which the quantity is written to disk / CSV / the results
    #: table in propeller mode. `None` means "does not rotate".
    propeller_key: Optional[str] = None
    unit: str = ""
    #: Suffix appended to the value in a condition NAME (`"°"`, `" m/s"`),
    #: which is tighter than the bracketed table unit.
    name_unit: str = ""
    rotor_visible: bool = True
    propeller_visible: bool = True
    #: Tooltip body, already in symbols (no snake_case field names).
    rotor_description: str = ""
    #: `None` reuses `rotor_description`.
    propeller_description: Optional[str] = None
    #: An input spelling of another quantity (`alpha_deg` is the input name
    #: of `alpha_rotor_deg`). Aliases share the output entry's symbols.
    alias_of: Optional[str] = None

    def latex(self, is_propeller: bool) -> str:
        if is_propeller and self.propeller_latex:
            return self.propeller_latex
        return self.rotor_latex

    def key(self, is_propeller: bool) -> str:
        if is_propeller and self.propeller_key:
            return self.propeller_key
        return self.engine_key

    def visible(self, is_propeller: bool) -> bool:
        return self.propeller_visible if is_propeller else self.rotor_visible

    def description(self, is_propeller: bool) -> str:
        if is_propeller and self.propeller_description is not None:
            return self.propeller_description
        return self.rotor_description


def _q(*args, **kwargs) -> AxisQuantity:
    return AxisQuantity(*args, **kwargs)


#: Every quantity whose name depends on the axis convention, keyed by the
#: ENGINE's name for it.
#:
#: Reading the table: a row says "the engine calls this X; the rotor user
#: reads it as Y; the propeller user reads it as Z". The `_x`/`_z` in the two
#: display columns are vehicle axes and swap between the two; the key on the
#: left never does.
_QUANTITIES: tuple = (
    # --- in-plane component (engine x) -------------------------------------
    _q("mu_x", "inplane", r"\mu_x", r"\mu_z", "mu_z", unit="-",
       rotor_description=(
           "Advance ratio along x: &mu;<sub>x</sub> = V<sub>x</sub>/(&Omega;R). "
           "In rotor mode x is the IN-PLANE direction, so this is the classic "
           "forward-flight advance ratio -- the component that sweeps across "
           "the blades and makes the advancing and retreating sides differ"),
       propeller_description=(
           "Advance ratio along z: &mu;<sub>z</sub> = V<sub>z</sub>/(&Omega;R), "
           "the cross-flow normalised by tip speed. This is the component that "
           "varies with azimuth and makes one side of the disk see more speed "
           "than the other. Zero in straight cruise")),
    _q("J_x", "inplane", r"J_x", r"J_z", "J_z", unit="-",
       rotor_description=(
           "Advance ratio along x in propeller form: J<sub>x</sub> = "
           "V<sub>x</sub>/(nD) = &pi;&middot;&mu;<sub>x</sub>"),
       propeller_description=(
           "Advance ratio along z in propeller form: J<sub>z</sub> = "
           "V<sub>z</sub>/(nD) = &pi;&middot;&mu;<sub>z</sub>. NOT the "
           "propeller advance ratio -- that one is J<sub>x</sub>, built from "
           "the airspeed along the shaft. This is the cross-flow, zero in "
           "straight cruise")),
    _q("Vx", "inplane", r"V_x", r"V_z", "Vz", unit="m/s", name_unit=" m/s",
       rotor_description=(
           "Free-stream component along x [m/s]. In rotor mode x is the "
           "IN-PLANE direction, so this is the horizontal flight speed -- what "
           "&mu;<sub>x</sub> and J<sub>x</sub> are built from"),
       propeller_description=(
           "Free-stream component along z [m/s]. In propeller mode z is "
           "VERTICAL, across the shaft and in the plane of the disk: the "
           "cross-flow. ZERO in straight cruise; non-zero when the propeller "
           "flies at an angle to its axis")),

    # --- axial component (engine z) ----------------------------------------
    _q("mu_z", "axial", r"\mu_z", r"\mu_x", "mu_x", unit="-",
       rotor_description=(
           "Advance ratio along z: &mu;<sub>z</sub> = V<sub>z</sub>/(&Omega;R). "
           "In rotor mode z is the SHAFT direction, so this is climb (positive) "
           "or descent (negative). Same number as &lambda;<sub>z</sub>, written "
           "in the advance-ratio vocabulary instead of the inflow one"),
       propeller_description=(
           "Advance ratio along x: &mu;<sub>x</sub> = V<sub>x</sub>/(&Omega;R), "
           "the airspeed normalised by tip speed. THE SAME NUMBER as "
           "&lambda;<sub>x</sub>, in the advance-ratio vocabulary")),
    _q("J_z", "axial", r"J_z", r"J_x", "J_x", unit="-",
       rotor_description=(
           "Advance ratio along z in propeller form: J<sub>z</sub> = "
           "V<sub>z</sub>/(nD) = &pi;&middot;&mu;<sub>z</sub>"),
       propeller_description=(
           "Advance ratio along x in propeller form: J<sub>x</sub> = "
           "V<sub>x</sub>/(nD) = &pi;&middot;&mu;<sub>x</sub>. THIS IS THE "
           "J<sub>x</sub> of propeller charts, built from the airspeed along "
           "the shaft, and the one propulsive efficiency uses")),
    _q("Vz", "axial", r"V_z", r"V_x", "Vx", unit="m/s", name_unit=" m/s",
       rotor_description=(
           "Free-stream component along z [m/s]. In rotor mode z is the SHAFT "
           "direction, so this is climb (positive) or descent (negative). It is "
           "the FREE STREAM, not the flow through the disk -- that one is "
           "V<sub>z,total</sub>"),
       propeller_description=(
           "Free-stream component along x [m/s]. In propeller mode x is the "
           "SHAFT direction, so this is the aircraft's airspeed -- in straight "
           "cruise, the whole flight velocity. It is the FREE STREAM; the flow "
           "through the disk is V<sub>x,total</sub>")),
    _q("lambda_z", "axial", r"\lambda_z", r"\lambda_x", "lambda_x", unit="-",
       rotor_description=(
           "Inflow ratio along z, from the free stream alone: "
           "&lambda;<sub>z</sub> = V<sub>z</sub>/(&Omega;R). In rotor mode z is "
           "the shaft, so this is the climb inflow -- an input datum, known "
           "before any aerodynamics. THE SAME NUMBER as &mu;<sub>z</sub>, in "
           "the inflow vocabulary instead of the advance-ratio one"),
       propeller_description=(
           "Inflow ratio along x, from the free stream alone: "
           "&lambda;<sub>x</sub> = V<sub>x</sub>/(&Omega;R). In propeller mode "
           "x is the shaft, so this is the axial inflow -- an input datum, "
           "known before any aerodynamics. THE SAME NUMBER as "
           "&mu;<sub>x</sub>, in the inflow vocabulary")),
    _q("Vz_total", "axial", r"V_{z,total}", r"V_{x,total}", "Vx_total",
       unit="m/s", name_unit=" m/s",
       rotor_description=(
           "Total velocity along the shaft, through the disk [m/s]: "
           "V<sub>z,total</sub> = V<sub>z</sub> + v<sub>i</sub>, disk-averaged. "
           "Free stream plus what the rotor adds. Written U<sub>P</sub> in the "
           "manual (Section 2.4.2)"),
       propeller_description=(
           "Total velocity along the shaft, through the disk [m/s]: "
           "V<sub>x,total</sub> = V<sub>x</sub> + v<sub>i</sub>, disk-averaged. "
           "The airspeed plus what the propeller adds. Written U<sub>P</sub> in "
           "the manual (Section 2.4.2)")),

    # --- the two angles: one per mode, each measured from its own reference -
    # They are the SAME angle (alpha_rotor + alpha_disk = 90); showing both
    # would invite reading one as if it were the other, so each mode shows
    # only the one that is zero at its vehicle's normal condition.
    _q("alpha_rotor_deg", "axial", r"\alpha_{rotor}", unit="deg", name_unit="°",
       propeller_visible=False,
       rotor_description=(
           "ROTOR angle of attack [deg]: angle between the free stream and the "
           "DISK PLANE, &alpha;<sub>rotor</sub> = atan2(V<sub>z</sub>, "
           "V<sub>x</sub>). This is THE angle of rotor mode -- 0 in a "
           "helicopter's level forward flight, and POSITIVE when the flow "
           "arrives from below the disk. Its propeller-mode counterpart is "
           "&alpha;<sub>disk</sub>, measured from the shaft; the two are "
           "complementary and each mode shows only its own")),
    _q("alpha_disk_deg", "inplane", r"\alpha_{disk}", unit="deg", name_unit="°",
       rotor_visible=False,
       rotor_description=(
           "DISK angle of attack [deg]: angle between the free stream and the "
           "SHAFT, &alpha;<sub>disk</sub> = 90 - &alpha;<sub>rotor</sub>. This "
           "is THE angle of propeller mode -- 0 in straight cruise (so a 2 deg "
           "misalignment reads '2'), and POSITIVE when the disk is tilted "
           "nose-up, i.e. the flow arrives from below. Its rotor-mode "
           "counterpart is &alpha;<sub>rotor</sub>, measured from the disk "
           "plane; each mode shows only its own")),

    # --- along the shaft in BOTH modes: no letter to rotate -----------------
    _q("Vi", "invariant", r"v_i", unit="m/s", name_unit=" m/s",
       rotor_description=(
           "Induced velocity [m/s], disk-averaged: the velocity the rotor adds "
           "along its own shaft. v<sub>i</sub> = "
           "&lambda;<sub>i</sub>&middot;(&Omega;R). It never changes axis with "
           "the mode -- only the letter naming that axis does")),
    _q("lambda_i", "invariant", r"\lambda_i", unit="-",
       rotor_description=(
           "Induced inflow ratio: &lambda;<sub>i</sub> = "
           "v<sub>i</sub>/(&Omega;R), the unknown solved by the BEMT fixed "
           "point. Area-weighted mean over the meshed span (root cutout to "
           "tip), not the whole geometric disk")),
    _q("lambda_total", "invariant", r"\lambda_{total}", unit="-",
       rotor_description=(
           "Total inflow ratio along the shaft: &lambda;<sub>total</sub> = "
           "&lambda;<sub>i</sub> + &lambda;<sub>z</sub> -- the free-stream part "
           "plus the induced part. Its dimensional counterpart is "
           "V<sub>z,total</sub> = &lambda;<sub>total</sub>&middot;(&Omega;R)"),
       propeller_description=(
           "Total inflow ratio along the shaft: &lambda;<sub>total</sub> = "
           "&lambda;<sub>i</sub> + &lambda;<sub>x</sub> -- the free-stream part "
           "plus the induced part. Its dimensional counterpart is "
           "V<sub>x,total</sub> = &lambda;<sub>total</sub>&middot;(&Omega;R)")),

    # --- the operating point's non-axis inputs ------------------------------
    _q("collective_deg", "invariant", r"\theta_0", unit="deg", name_unit="°",
       rotor_description=("Collective pitch [deg], added on top of the "
                          "built-in blade twist")),
    _q("rpm", "invariant", r"RPM", unit="rev/min",
       rotor_description=(
           "Rotational speed of the rotor for this condition [rev/min] -- the "
           "value the solver actually ran with. Same quantity as "
           "RPM<sub>rotor</sub> (the engine's own echo of it), which is "
           "therefore hidden from the table whenever the two agree")),

    # --- input spellings of the two angles ---------------------------------
    # `studies` and the GUI name the angles `alpha_deg`/`alpha_disk` when they
    # are an INPUT; `aggregate_results` emits them as `alpha_rotor_deg`/
    # `alpha_disk_deg`. Same quantity, same symbol, two spellings.
    _q("alpha_deg", "axial", r"\alpha_{rotor}", unit="deg", name_unit="°",
       propeller_visible=False, alias_of="alpha_rotor_deg"),
    _q("alpha_disk", "inplane", r"\alpha_{disk}", unit="deg", name_unit="°",
       rotor_visible=False, alias_of="alpha_disk_deg"),
)

#: `engine_key -> AxisQuantity`, the table every surface reads.
QUANTITIES: dict = {q.engine_key: q for q in _QUANTITIES}

for _quantidade in _QUANTITIES:
    if _quantidade.alias_of:
        _fonte = QUANTITIES[_quantidade.alias_of]
        QUANTITIES[_quantidade.engine_key] = AxisQuantity(
            **{**_quantidade.__dict__,
               "rotor_description": _fonte.rotor_description,
               "propeller_description": _fonte.propeller_description})
del _quantidade


# =============================================================================
# One LaTeX source -> three renderings
# =============================================================================
# Moved here from `viz/plots.py` (`rotulo_em_texto`/`rotulo_em_html`), which
# is where they were written and where they are still used: `plots` draws
# mathtext directly, the Results-tab combos need Unicode, and the report needs
# HTML. Keeping the converters next to the table is what lets ONE symbol
# string serve all three, instead of a second and a third list.

#: Macros with a Unicode letter of their own.
_GREEK_UNICODE = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν",
    r"\pi": "π", r"\rho": "ρ", r"\sigma": "σ", r"\phi": "φ",
    r"\psi": "ψ", r"\omega": "ω", r"\Omega": "Ω", r"\eta": "η",
    r"\infty": "∞", r"\cdot": "·", r"\times": "×", r"\pm": "±",
    r"\circ": "°",
}

#: HTML entities for the same macros. Kept separate from `_GREEK_UNICODE` on
#: purpose: Qt renders both, but an entity survives a `QTextDocument` built
#: from an HTML source regardless of the encoding of the file that loaded it.
_GREEK_HTML = {
    r"\alpha": "&alpha;", r"\beta": "&beta;", r"\gamma": "&gamma;",
    r"\delta": "&delta;", r"\theta": "&theta;", r"\lambda": "&lambda;",
    r"\mu": "&mu;", r"\nu": "&nu;", r"\pi": "&pi;", r"\rho": "&rho;",
    r"\sigma": "&sigma;", r"\phi": "&phi;", r"\psi": "&psi;",
    r"\omega": "&omega;", r"\Omega": "&Omega;", r"\eta": "&eta;",
    r"\infty": "&infin;", r"\cdot": "&middot;", r"\times": "&times;",
    r"\pm": "&plusmn;", r"\circ": "&deg;",
}

#: Only the characters that EXIST as a Unicode subscript. "T" (from C_T) does
#: not, so it stays on the line -- "CT" reads well, while a half-lowered
#: "Cᵢnf" reads worse than "Cinf".
_SUBSCRIPT_UNICODE = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
    "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ",
    "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}


#: A subscript, in either mathtext spelling: braced (`_{x,total}`) or a lone
#: character (`_x`). Matched as one alternation so a rejected braced group is
#: not re-read as a lone-character subscript.
_SUBSCRIPT = re.compile(r"_\{([^}]*)\}|_(\w)")


def _subscript_unicode(texto: str, lower: str = "all") -> str:
    """Lowers a subscript only when EVERY character has a subscript form.

    A half-lowered subscript reads worse than none at all ("Cᵢnf" vs "Cinf"),
    so the mixed case keeps the `_` that marked it: "V_z" stays "V_z" rather
    than collapsing to "Vz", where the z would read as part of the name.

    ``lower``:

    - ``"all"``   -- lower whatever can be lowered. For a LABEL, where the
      subscript is read, not typed.
    - ``"digits"``-- lower only digit groups (θ₀), keep letters on the line
      (μ_x, α_rotor). For a condition NAME: the name becomes a file name
      through `api.sanitize_filename`, whose ASCII transcription knows Greek
      letters and subscript digits but not "ᵣₒₜₒᵣ", which would travel into a
      zip as mojibake.
    - ``"none"``  -- keep every subscript on the line.
    """
    if not texto:
        return texto
    if lower == "none":
        return f"_{texto}"
    if lower == "digits":
        # A NAME keeps the `_` it could not lower: "mu_x" is an identifier as
        # much as a symbol, and "mux" would not read back as one.
        return ("".join(_SUBSCRIPT_UNICODE[c] for c in texto) if texto.isdigit()
                else f"_{texto}")
    if all(c in _SUBSCRIPT_UNICODE for c in texto):
        return "".join(_SUBSCRIPT_UNICODE[c] for c in texto)
    # A LABEL drops it: "CT" and "CT,prop" read as the coefficients they are,
    # and are what the reader of a chart expects to see on the axis.
    return texto


def _is_mathtext(texto: str) -> bool:
    """Whether a string is mathtext at all.

    Deliberately narrow: a plain name (`"RPM"`, `"cfg_solver"`) must pass
    through untouched, and `cfg_solver` is exactly the case where treating a
    lone underscore as a subscript would produce "cfgₛₒₗᵥₑᵣ"."""
    return "$" in texto or "\\" in texto


def _needs_math(corpo: str) -> bool:
    """Whether a symbol BODY from `QUANTITIES` carries real notation (a Greek
    macro or a subscript) and must be wrapped in `$...$` before rendering.
    `"RPM"` does not; `"J_x"` does."""
    return "\\" in corpo or "_" in corpo or "^" in corpo


def to_unicode(mathtext: str, lower_subscripts: str = "all") -> str:
    """Plain-text (Unicode) rendering of a mathtext body or label.

    ``lower_subscripts`` is ``"all"``, ``"digits"`` or ``"none"`` -- see
    `_subscript_unicode`. A condition NAME uses ``"digits"``.

    ``r"\\mu_x"`` -> ``"μₓ"``; ``r"$C_{T,prop}$ [-]"`` -> ``"CT,prop [-]"``.
    For a plain Qt label, a combo item, or a CSV header.
    """
    if not mathtext:
        return ""
    if not _is_mathtext(mathtext):
        return mathtext
    texto = mathtext
    for macro, simbolo in _GREEK_UNICODE.items():
        texto = texto.replace(macro + " ", simbolo).replace(macro, simbolo)
    texto = texto.replace(r"\,", " ").replace(r"\ ", " ")
    # ONE pass over both subscript forms. Two passes would re-read the `_`
    # that the braced form leaves behind when it cannot be lowered:
    # `_{x,total}` -> `_x,total` -> `ₓ,total`, which lowers half of a group
    # that was rejected as a whole.
    texto = re.sub(_SUBSCRIPT,
                   lambda m: _subscript_unicode(m.group(1) or m.group(2),
                                                 lower_subscripts),
                   texto)
    texto = texto.replace("$", "").replace("{", "").replace("}", "")
    return texto.strip()


def to_html(mathtext: str) -> str:
    """HTML rendering, with a real ``<sub>``.

    ``r"\\mu_x"`` -> ``"&mu;<sub>x</sub>"``; ``r"$C_T$ [-]"`` ->
    ``"C<sub>T</sub> [-]"``. For the report, and for the Qt widgets that
    paint their item with a `QTextDocument`.
    """
    if not mathtext:
        return ""
    if not _is_mathtext(mathtext):
        return mathtext
    texto = mathtext
    for macro, entidade in _GREEK_HTML.items():
        texto = texto.replace(macro + " ", entidade).replace(macro, entidade)
    texto = texto.replace(r"\,", " ").replace(r"\ ", " ")
    texto = re.sub(_SUBSCRIPT,
                   lambda m: f"<sub>{m.group(1) if m.group(1) is not None else m.group(2)}</sub>",
                   texto)
    texto = texto.replace("$", "").replace("{", "").replace("}", "")
    return texto.strip()


def to_mathtext(latex: str, unidade: str = "") -> str:
    """A mathtext body plus its bracketed unit, the form matplotlib draws:
    ``(r"\\mu_x", "-")`` -> ``r"$\\mu_x$ [-]"``.

    The unit is explicit even when dimensionless: an empty bracket reads as
    "forgot to fill in", while "[-]" states that the quantity has none.
    """
    corpo = f"${latex}$" if _needs_math(latex) else latex
    return f"{corpo} [{unidade}]" if unidade else corpo


# =============================================================================
# Accessors -- what every surface calls instead of keeping its own table
# =============================================================================

def quantity(engine_key: str) -> Optional[AxisQuantity]:
    """The entry for a key, or `None`. A key with no entry is not an error:
    `Results.summary` also carries coefficients and `cfg_*` echoes, which
    carry no axis letter and are handled by the caller's own table."""
    return QUANTITIES.get(engine_key)


def symbol_latex(engine_key: str, is_propeller: bool = False) -> str:
    """The mathtext body, the source the other renderings come from."""
    q = QUANTITIES.get(engine_key)
    return q.latex(is_propeller) if q else engine_key


def symbol_mathtext(engine_key: str, is_propeller: bool = False) -> str:
    """Axis label for matplotlib, unit included."""
    q = QUANTITIES.get(engine_key)
    if q is None:
        return engine_key
    return to_mathtext(q.latex(is_propeller), q.unit)


def symbol_html(engine_key: str, is_propeller: bool = False) -> str:
    """Column header for the report and for Qt rich text.

    A key with no entry comes back verbatim: it is a coefficient or a
    `cfg_*` echo, whose underscore is part of its NAME, not a subscript."""
    q = QUANTITIES.get(engine_key)
    return to_html(_como_mathtext(q.latex(is_propeller))) if q else engine_key


def symbol_text(engine_key: str, is_propeller: bool = False) -> str:
    """Plain-Unicode symbol, for a widget without rich text."""
    q = QUANTITIES.get(engine_key)
    return to_unicode(_como_mathtext(q.latex(is_propeller))) if q else engine_key


def symbol_name(engine_key: str, is_propeller: bool = False) -> str:
    """Symbol for a condition NAME: Greek letters and digit subscripts
    (``"θ₀"``), but letter subscripts left on the line (``"μ_x"``, not
    ``"μₓ"``).

    A name is an identifier as much as a label -- it is what
    `api.sanitize_filename` turns into a file name, and that transcription
    knows Greek but not Unicode subscripts."""
    q = QUANTITIES.get(engine_key)
    if q is None:
        return engine_key
    return to_unicode(_como_mathtext(q.latex(is_propeller)),
                      lower_subscripts="digits")


def _como_mathtext(corpo: str) -> str:
    """Wraps a symbol body so the converters recognise it as mathtext. A body
    with no notation (`"RPM"`) is left alone, so it never gets treated as a
    name with a subscript."""
    return f"${corpo}$" if _needs_math(corpo) else corpo


def unit(engine_key: str) -> str:
    """SI unit. It does NOT depend on the mode: the letters rotate, the
    physics does not."""
    q = QUANTITIES.get(engine_key)
    return q.unit if q else ""


def description_html(engine_key: str, is_propeller: bool = False) -> str:
    """Tooltip body, already in symbols -- a user-facing surface never shows
    a `snake_case` field name as if it were a physical symbol."""
    q = QUANTITIES.get(engine_key)
    return q.description(is_propeller) if q else ""


def is_visible(engine_key: str, is_propeller: bool = False) -> bool:
    """Whether the mode shows this quantity at all.

    Only the two angles are hidden, and only ever one of them: they are the
    same angle from different references, and two columns whose numbers never
    coincide invite reading one as the other."""
    q = QUANTITIES.get(engine_key)
    return q.visible(is_propeller) if q else True


def slot_of(engine_key: str) -> str:
    """`"inplane"`, `"axial"` or `"invariant"` -- the physical component the
    quantity describes, which does NOT rotate with the mode. Used to detect
    a conflict between two factorial axes and to group the input fields."""
    q = QUANTITIES.get(engine_key)
    return q.slot if q else "invariant"


def variables_in_slot(slot: str, is_propeller: bool = False) -> tuple:
    """Engine keys that represent `slot`, in the order a user of this mode
    would look for them, and without the angle the mode does not use."""
    return tuple(q.engine_key for q in _QUANTITIES
                 if q.slot == slot and q.visible(is_propeller))


# --- the key rotation --------------------------------------------------------

def display_key(engine_key: str, is_propeller: bool = False) -> str:
    """The key the user reads -- in the results table, the CSV header and the
    `.bemt` file. Rotor mode is the identity."""
    q = QUANTITIES.get(engine_key)
    return q.key(is_propeller) if q else engine_key


#: `display -> engine`, per mode. Built once, from the same table, so the two
#: directions cannot drift apart.
_ENGINE_KEY_OF = {
    True: {q.key(True): q.engine_key for q in _QUANTITIES if not q.alias_of},
    False: {q.key(False): q.engine_key for q in _QUANTITIES if not q.alias_of},
}


def engine_key_of(display: str, is_propeller: bool = False) -> str:
    """Inverse of `display_key`: what the engine calls a key the user wrote."""
    return _ENGINE_KEY_OF[bool(is_propeller)].get(display, display)


def to_display_keys(mapping: dict, is_propeller: bool = False) -> dict:
    """A copy of `mapping` with its keys in the user's vocabulary.

    ONE pass, into a NEW dict. The propeller rotation is a swap
    (`mu_x` <-> `mu_z`), so renaming in place, key by key, would collapse
    both components onto whichever was written last -- silently, with a
    plausible number. That is why this is the only place the rotation
    happens."""
    if not is_propeller:
        return dict(mapping)
    return {display_key(chave, True): valor for chave, valor in mapping.items()}


def from_display_keys(mapping: dict, is_propeller: bool = False) -> dict:
    """Exact inverse of `to_display_keys`, for reading back what a user (or a
    `.bemt` file) wrote."""
    if not is_propeller:
        return dict(mapping)
    return {engine_key_of(chave, True): valor for chave, valor in mapping.items()}


# =============================================================================
# The two input slots, as the user meets them
# =============================================================================
# One row of the Run Case / Run Batch form per slot. The engine's slot names
# are `inplane` (its `mu_x`) and `axial` (its `Vz`); which of the two carries
# the letter x, and which one carries the vehicle's flight speed, is what the
# mode decides.
#
# Why the propeller's angle lives in the IN-PLANE slot and not the axial one:
# an angle never fixes the scale of a velocity, it only splits a KNOWN
# component into the other one. In straight cruise the known component is the
# axial one, so that is the one given as a number and the in-plane one is
# derived from the angle. Put in the axial slot, alpha_disk would solve
# `Vz = V_inplane/tan(alpha_disk)`, which is 0/0 in exactly the cruise a
# propeller spends its life in.
_SLOT_LABELS = {
    ("inplane", False): (
        "Edgewise (in-plane) Flow:",
        "The horizontal component of the flight velocity, V<sub>x</sub>. On a "
        "rotor the shaft is vertical, so x lies IN THE PLANE OF THE DISK: this "
        "is THE ADVANCE, the component that sweeps across the blades and makes "
        "the advancing and retreating sides differ.\n\n"
        "Units offered: &mu;<sub>x</sub> = V<sub>x</sub>/(&Omega;R), "
        "J<sub>x</sub> = V<sub>x</sub>/(nD) = &pi;&middot;&mu;<sub>x</sub>, and "
        "the dimensional speed V<sub>x</sub> [m/s]. The vertical component "
        "V<sub>z</sub> is the field below."),
    ("axial", False): (
        "Axial (along-shaft) Flow:",
        "The vertical component of the flight velocity, V<sub>z</sub>. On a "
        "rotor the shaft is vertical, so z runs ALONG THE SHAFT: this is climb "
        "(positive) or descent (negative), and the engine adds the induced "
        "velocity to it to form V<sub>z,total</sub> = V<sub>z</sub> + "
        "v<sub>i</sub>.\n\n"
        "Units offered: &alpha;<sub>rotor</sub> [deg], V<sub>z</sub> [m/s], and "
        "the ratios &mu;<sub>z</sub> = V<sub>z</sub>/(&Omega;R) (also written "
        "&lambda;<sub>z</sub>) and J<sub>z</sub> = V<sub>z</sub>/(nD).\n\n"
        "&alpha;<sub>rotor</sub> = atan2(V<sub>z</sub>, V<sub>x</sub>) is THE "
        "angle of rotor mode, measured FROM THE DISK PLANE: 0&deg; is level "
        "forward flight, and it is POSITIVE when the flow arrives from below "
        "the disk. Propeller mode offers &alpha;<sub>disk</sub> instead, "
        "measured from the shaft; each mode offers only its own angle, so "
        "there is never a doubt about which of the two a number is.\n\n"
        "The angle lives in this field in both modes for one reason: an angle "
        "never fixes the scale of the velocity, it only splits the KNOWN "
        "component into the other one."),
    ("inplane", True): (
        "Cross (in-plane) Flow:",
        "The cross-flow across the propeller shaft, V<sub>z</sub>. Propeller "
        "axes: x is along the shaft, z is in the disk plane. In straight cruise "
        "V<sub>z</sub> = 0 -- the aircraft's airspeed goes in the axial field "
        "below.\n\n"
        "Units offered: V<sub>z</sub> [m/s], &alpha;<sub>disk</sub> [deg], "
        "&mu;<sub>z</sub> = V<sub>z</sub>/(&Omega;R), or J<sub>z</sub> = "
        "V<sub>z</sub>/(nD). J<sub>z</sub> is the cross-flow, NOT the propeller "
        "advance ratio.\n\n"
        "&alpha;<sub>disk</sub> = atan2(V<sub>z</sub>, V<sub>x</sub>): 0&deg; "
        "means the free stream is aligned with the shaft."),
    ("axial", True): (
        "Axial (along-shaft) Flow:",
        "The horizontal component of the flight velocity, V<sub>x</sub>: the "
        "aircraft's AIRSPEED. On a propeller the shaft is horizontal, so x runs "
        "ALONG THE SHAFT, and the engine adds the induced velocity to it to "
        "form V<sub>x,total</sub> = V<sub>x</sub> + v<sub>i</sub>.\n\n"
        "THIS IS THE PROPELLER'S ADVANCE RATIO. The default unit J<sub>x</sub> "
        "is the classic one of the propeller charts, J<sub>x</sub> = V/(nD), "
        "built from the AXIAL airspeed -- the same J<sub>x</sub> that "
        "propulsive efficiency uses, since thrust acts along the shaft.\n\n"
        "Units offered: J<sub>x</sub>, &mu;<sub>x</sub> = J<sub>x</sub>/&pi; = "
        "V<sub>x</sub>/(&Omega;R) (the same number in the rotor vocabulary, "
        "also written &lambda;<sub>x</sub>), and the dimensional speed "
        "V<sub>x</sub> [m/s].\n\n"
        "No angle is offered here, on purpose: an angle only splits the known "
        "component into the other one, and on a propeller the known component "
        "is this one. The angle lives in the cross-flow field above, measured "
        "from the shaft (&alpha;<sub>disk</sub>)."),
}


def slot_label(slot: str, is_propeller: bool = False) -> tuple:
    """`(row label, tooltip)` for one of the two input slots.

    Single source for Run Case and Run Batch, which between them lay out
    three pairs of these fields."""
    return _SLOT_LABELS[(slot, bool(is_propeller))]


# =============================================================================
# Reading order of the operating point
# =============================================================================
#: First the component that carries the letter x -- the mode's PRIMARY one, a
#: helicopter's advance or a propeller's airspeed -- then the secondary one,
#: then the angle. The keys are the ENGINE's; what changes between modes is
#: which one is the primary.
_PRIMARY_ROTOR = (
    "mu_x", "J_x", "Vx",                          # x = in-plane (advance)
    "mu_z", "J_z", "Vz", "lambda_z",              # z = shaft (climb/descent)
    "alpha_rotor_deg", "alpha_disk_deg",
    "collective_deg", "rpm",
)

_PRIMARY_PROPELLER = (
    "mu_z", "J_z", "Vz", "lambda_z",              # x = shaft (airspeed)
    "mu_x", "J_x", "Vx",                          # z = in-plane (cross-flow)
    "alpha_disk_deg", "alpha_rotor_deg",
    "collective_deg", "rpm",
)


def primary_order(is_propeller: bool = False) -> tuple:
    """The flight-condition columns, in reading order, without the angle the
    mode does not use."""
    ordem = _PRIMARY_PROPELLER if is_propeller else _PRIMARY_ROTOR
    return tuple(c for c in ordem if is_visible(c, is_propeller))


# =============================================================================
# Naming a condition
# =============================================================================

def condition_label(valores: dict, is_propeller: bool = False) -> str:
    """Readable name for a condition, from its `{variable: value}` dict.

    ``{"mu_x": 0.1, "alpha_deg": -10}`` -> ``"μ_x=0.1, α_rotor=-10°"``. This
    is what appears in the condition combo, in the label column of the
    results table and in the report, where the raw
    ``mu_x=0_alpha_deg=-10`` would be a field name rather than a quantity.

    The letters are the MODE's: a propeller case named "μ_x=0.4" for its
    cross-flow would name the cross-flow as if it were the advance ratio.

    Order follows `valores`, which is the order of the axes the user chose.
    An unknown variable falls back to its own name, so a new axis never
    leaves a condition unnamed."""
    partes = []
    for chave, valor in valores.items():
        q = QUANTITIES.get(chave)
        simbolo = symbol_name(chave, is_propeller) if q else chave
        sufixo = q.name_unit if q else ""
        try:
            texto = f"{float(valor):g}"
        except (TypeError, ValueError):
            texto = str(valor)
        partes.append(f"{simbolo}={texto}{sufixo}")
    return ", ".join(partes)
