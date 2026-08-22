r"""
test_notation.py
================

PR-4 -- mathematical notation is rendered, never spelled out. A reader
who meets `mu_x` instead of a real mu with a real subscript is reading
source code, not a symbol, and the ambiguity is real: `lambda_i` and
`lambda_z` are two different quantities that a plain-text rendering
lines up as two similar words.

The sweep covers the surfaces PR-4 names and that carry a SYMBOL: the
column headers of the results table and the report, the axis labels of
the plots, the field labels and block titles of the GUI, and the prose
of `docs/documentation.html`. Free-text descriptions are excluded --
they are English sentences, and naming a quantity in words there is
correct.

What counts as a violation is a Greek letter or a subscripted quantity
written in ASCII (`mu_x`, `lambda_i`, `alpha_rotor`). Rendered forms
are accepted in any of the four targets the software uses: LaTeX
(`\mu_x`), mathtext (`$\mu_x$`), HTML (`&mu;<sub>x</sub>`) and Unicode
(`mu_x` with a real mu and a real subscript).
"""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

from zbemt import api, nomenclature

from tests.helpers import requires_qt

ROOT = Path(__file__).resolve().parents[1]

#: A quantity written as `name_subscript` in ASCII. The list is the set
#: of Greek names the engine actually uses, plus the two velocity
#: letters that carry an axis subscript.
NOTATION_IN_TEXT = re.compile(
    r"\b(?:mu|lambda|alpha|beta|phi|theta|sigma|psi|omega|rho|Vx|Vz)"
    r"_[A-Za-z0-9]+")


#: A Greek letter spelled out in ASCII as a standalone word, or an
#: exponent written with a caret. Both are the source-code form of
#: something the reader expects typeset: `rho*A*(Omega*R)^2` is an
#: expression a program evaluates, not an equation a person reads. The
#: boundaries are part of the rule: they accept ordinary English words
#: that merely contain these letter pairs ("number", "pitch"), and they
#: reject the bare words ("rho", "pi") standing in for symbols. An
#: underscore counts as a word character, so an identifier such as
#: `alpha_blending` never matches.
GREEK_IN_TEXT = re.compile(
    r"\b(?:rho|Omega|omega|lambda|alpha|beta|gamma|psi|sigma|theta|phi|nu|eta|Delta|pi)\b"
    r"|\^\d")


def _only_the_text(html: str) -> str:
    """Drops what is already rendered -- the HTML entities and the tags
    around them -- so that only the prose the reader meets as plain
    characters is examined. `&rho;` is a rendered rho and must not be
    reported as the word "rho"."""
    return re.sub(r"&[a-zA-Z]+\d?;", " ", re.sub(r"<[^>]+>", " ", html))


#: A tooltip opens with the field's own `.bemt` key in quotes
#: (`"n_blades" — ...`), which `field_help` reads back. That key is an
#: identifier, not a symbol.
KEY_AT_START = re.compile(r'^\s*"[\w.]+"')

#: Literal identifiers a user types into a file, quoted in a tooltip that
#: documents a file format. `alpha` there is the name of a CSV column, and
#: rendering it would misname the column. Keyed by the widget text that
#: identifies the tooltip, so a NEW tooltip never inherits the allowance.
FILE_FORMAT_TOOLTIPS = ("ONE LINE = ONE ANGLE OF ATTACK",)


def _without_math_nor_code(html: str) -> str:
    """Removes what is legitimately ASCII: the LaTeX spans, the code
    spans, and the tags themselves. A `.bemt` key quoted inside
    `<code>` is a key, not a symbol, and must survive as written."""
    text = re.sub(r"\$\$.*?\$\$", " ", html, flags=re.S)
    text = re.sub(r"\$[^$\n]*\$", " ", text)
    text = re.sub(r"<code\b.*?</code>", " ", text, flags=re.S)
    text = re.sub(r"<pre\b.*?</pre>", " ", text, flags=re.S)
    return re.sub(r"<[^>]+>", " ", text)


class TestColumnSymbols(unittest.TestCase):
    """The header of a results column reaches three surfaces at once --
    the GUI table, the report and the plot selector -- from one table in
    `api`. A plain-text symbol there is wrong in all three."""

    def test_no_column_symbol_is_plain_text(self):
        violations = []
        for propeller in (False, True):
            for key, (symbol, _description) in api.summary_symbols(propeller).items():
                if NOTATION_IN_TEXT.search(symbol):
                    violations.append(f"{'propeller' if propeller else 'rotor'}:{key} -> {symbol!r}")
        self.assertEqual(violations, [], "plain-text column symbol: " + str(violations))

    def test_no_column_description_spells_out_an_axis(self):
        """The descriptions are English sentences and may name a
        quantity in words, but not by its ASCII key: an axis letter is
        exactly what PR-8 rotates between modes, so a hard-coded
        `mu_x` in the prose is also a mode bug waiting to happen."""
        axes = re.compile(r"\b(?:mu|lambda|J|V)_[xz]\b")
        violations = []
        for propeller in (False, True):
            for key, (_symbol, description) in api.summary_symbols(propeller).items():
                if axes.search(description):
                    violations.append(f"{'propeller' if propeller else 'rotor'}:{key}")
        self.assertEqual(violations, [], "axis key spelled out in a description: " + str(violations))


    def test_no_description_writes_a_greek_letter_out_in_full(self):
        """The description is what the tooltip shows and what the report
        prints under the header, so it is read as often as the symbol.
        A thrust coefficient defined there as `T / (rho*A*(Omega*R)^2)`
        asks the reader to parse an expression; the same line with the
        letters and the exponents rendered is the equation from the
        textbook."""
        violations = []
        for propeller in (False, True):
            for key, (_symbol, description) in api.summary_symbols(propeller).items():
                findings = sorted(set(GREEK_IN_TEXT.findall(_only_the_text(description))))
                if findings:
                    violations.append(f"{'propeller' if propeller else 'rotor'}:{key} {findings}")
        self.assertEqual(sorted(set(violations)), [],
                         "unrendered notation in a column description: " + str(sorted(set(violations))))


class TestAxisSymbols(unittest.TestCase):
    """`nomenclature` is the single LaTeX source (PR-8). Each of its
    three render targets must actually render."""

    def test_each_render_target_comes_out_rendered(self):
        violations = []
        for key in nomenclature.QUANTITIES:
            for propeller in (False, True):
                if not nomenclature.is_visible(key, propeller):
                    continue
                mathtext = nomenclature.symbol_mathtext(key, propeller)
                html = nomenclature.symbol_html(key, propeller)
                if NOTATION_IN_TEXT.search(mathtext) and "$" not in mathtext:
                    violations.append(f"mathtext {key}: {mathtext!r}")
                if NOTATION_IN_TEXT.search(re.sub(r"<[^>]+>", "", html)):
                    violations.append(f"html {key}: {html!r}")
        self.assertEqual(violations, [], "unrendered axis symbol: " + str(violations))


class TestDocumentation(unittest.TestCase):
    """`docs/documentation.html` is read by a human, and its equations
    are typeset. Prose that falls back to `mu_x` between two typeset
    equations reads as a third notation."""

    def test_prose_does_not_use_plain_text_notation(self):
        html = (ROOT / "docs" / "documentation.html").read_text(encoding="utf-8")
        findings = sorted(set(NOTATION_IN_TEXT.findall(_without_math_nor_code(html))))
        self.assertEqual(findings, [], "plain-text notation in the documentation: " + str(findings))


class TestHelp(unittest.TestCase):
    """The help popup is where a reader goes to find the equation, so it
    is the last place that should present one in source form. Its
    `equation` entries are raw LaTeX by design and are typeset by the
    popup; the surrounding prose is not, and has to carry its own
    rendering."""

    #: Rendered by the popup as mathematics, so ASCII there is the input
    #: format, not a fallback.
    LATEX_KEYS = ("equation", "equations")

    def _sweep(self, node, path, violations):
        if isinstance(node, str):
            findings = sorted(set(GREEK_IN_TEXT.findall(
                _only_the_text(_without_math_nor_code(node)))))
            if findings:
                violations.append(f"{path} {findings}")
        elif isinstance(node, dict):
            for key, value in node.items():
                if key not in self.LATEX_KEYS:
                    self._sweep(value, f"{path}.{key}", violations)
        elif isinstance(node, (list, tuple)):
            for i, value in enumerate(node):
                self._sweep(value, f"{path}[{i}]", violations)

    def test_field_prose_does_not_spell_out_notation(self):
        from zbemt.gui import help_content

        violations = []
        self._sweep(help_content.FIELD_HELP, "FIELD_HELP", violations)
        self.assertEqual(violations, [], "unrendered notation in field help: " + str(violations))

    def test_block_prose_does_not_spell_out_notation(self):
        from zbemt.gui import help_blocks

        violations = []
        self._sweep(help_blocks.BLOCK_HELP, "BLOCK_HELP", violations)
        self.assertEqual(violations, [], "unrendered notation in block help: " + str(violations))


@requires_qt
class TestGuiLabels(unittest.TestCase):
    """A field label and a block title are the shortest user-facing
    text there is, and the one most likely to be typed as the field's
    own name."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication

        from zbemt.gui.app import MainWindow

        cls.app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()
        cls.window.resize(1400, 900)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.window.deleteLater()

    def test_no_visible_label_spells_out_a_symbol(self):
        from PyQt6.QtWidgets import (QCheckBox, QGroupBox, QLabel, QPushButton,
                                     QRadioButton)

        violations = []
        for widget_class in (QLabel, QGroupBox, QCheckBox, QRadioButton, QPushButton):
            for widget in self.window.findChildren(widget_class):
                text = widget.title() if widget_class is QGroupBox else widget.text()
                if not text:
                    continue
                if NOTATION_IN_TEXT.search(_without_math_nor_code(text)):
                    violations.append(f"{widget_class.__name__}: {text.strip()[:70]!r}")
        self.assertEqual(sorted(set(violations)), [],
                         "plain-text notation on a GUI label: " + str(sorted(set(violations))))


    def test_no_tooltip_writes_a_greek_letter_out_in_full(self):
        """The tooltip is the first explanation the user gets, and it
        sits directly under a label that already carries the rendered
        symbol. Falling back to `|alpha|` or `Ut` there makes the two
        halves of the same field disagree about how the quantity is
        written."""
        from PyQt6.QtWidgets import QWidget

        violations = []
        for widget in self.window.findChildren(QWidget):
            tooltip = widget.toolTip()
            if not tooltip or any(m in tooltip for m in FILE_FORMAT_TOOLTIPS):
                continue
            text = _without_math_nor_code(KEY_AT_START.sub(" ", tooltip))
            findings = sorted(set(GREEK_IN_TEXT.findall(_only_the_text(text))))
            if findings:
                violations.append(f"{findings} in {tooltip.strip()[:60]!r}")
        self.assertEqual(sorted(set(violations)), [],
                         "unrendered notation in a tooltip: " + str(sorted(set(violations))))


if __name__ == "__main__":
    unittest.main()
