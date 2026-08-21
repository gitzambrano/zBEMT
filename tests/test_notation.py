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

RAIZ = Path(__file__).resolve().parents[1]

#: A quantity written as `name_subscript` in ASCII. The list is the set
#: of Greek names the engine actually uses, plus the two velocity
#: letters that carry an axis subscript.
NOTACAO_EM_TEXTO = re.compile(
    r"\b(?:mu|lambda|alpha|beta|phi|theta|sigma|psi|omega|rho|Vx|Vz)"
    r"_[A-Za-z0-9]+")


#: A Greek letter spelled out in ASCII, or an exponent written with a
#: caret. Both are the source-code form of something the reader expects
#: typeset: `rho*A*(Omega*R)^2` is an expression a program evaluates, not
#: an equation a person reads.
GREGO_EM_TEXTO = re.compile(
    r"(?:rho|Omega|omega|lambda|alpha|beta|gamma|psi|sigma|theta|phi|nu|eta|Delta|pi)"
    r"|\^\d")


def _apenas_o_texto(html: str) -> str:
    """Drops what is already rendered -- the HTML entities and the tags
    around them -- so that only the prose the reader meets as plain
    characters is examined. `&rho;` is a rendered rho and must not be
    reported as the word "rho"."""
    return re.sub(r"&[a-zA-Z]+\d?;", " ", re.sub(r"<[^>]+>", " ", html))


#: A tooltip opens with the field's own `.bemt` key in quotes
#: (`"n_blades" — ...`), which `field_help` reads back. That key is an
#: identifier, not a symbol.
CHAVE_INICIAL = re.compile(r'^\s*"[\w.]+"')

#: Literal identifiers a user types into a file, quoted in a tooltip that
#: documents a file format. `alpha` there is the name of a CSV column, and
#: rendering it would misname the column. Keyed by the widget text that
#: identifies the tooltip, so a NEW tooltip never inherits the allowance.
TOOLTIPS_DE_FORMATO_DE_ARQUIVO = ("ONE LINE = ONE ANGLE OF ATTACK",)


def _sem_matematica_nem_codigo(html: str) -> str:
    """Removes what is legitimately ASCII: the LaTeX spans, the code
    spans, and the tags themselves. A `.bemt` key quoted inside
    `<code>` is a key, not a symbol, and must survive as written."""
    texto = re.sub(r"\$\$.*?\$\$", " ", html, flags=re.S)
    texto = re.sub(r"\$[^$\n]*\$", " ", texto)
    texto = re.sub(r"<code\b.*?</code>", " ", texto, flags=re.S)
    texto = re.sub(r"<pre\b.*?</pre>", " ", texto, flags=re.S)
    return re.sub(r"<[^>]+>", " ", texto)


class TestSimbolosDeColuna(unittest.TestCase):
    """The header of a results column reaches three surfaces at once --
    the GUI table, the report and the plot selector -- from one table in
    `api`. A plain-text symbol there is wrong in all three."""

    def test_nenhum_simbolo_de_coluna_e_texto_puro(self):
        faltas = []
        for helice in (False, True):
            for chave, (simbolo, _descricao) in api.summary_symbols(helice).items():
                if NOTACAO_EM_TEXTO.search(simbolo):
                    faltas.append(f"{'propeller' if helice else 'rotor'}:{chave} -> {simbolo!r}")
        self.assertEqual(faltas, [], "plain-text column symbol: " + str(faltas))

    def test_nenhuma_descricao_de_coluna_soletra_um_eixo(self):
        """The descriptions are English sentences and may name a
        quantity in words, but not by its ASCII key: an axis letter is
        exactly what PR-8 rotates between modes, so a hard-coded
        `mu_x` in the prose is also a mode bug waiting to happen."""
        eixos = re.compile(r"\b(?:mu|lambda|J|V)_[xz]\b")
        faltas = []
        for helice in (False, True):
            for chave, (_simbolo, descricao) in api.summary_symbols(helice).items():
                if eixos.search(descricao):
                    faltas.append(f"{'propeller' if helice else 'rotor'}:{chave}")
        self.assertEqual(faltas, [], "axis key spelled out in a description: " + str(faltas))


    def test_nenhuma_descricao_escreve_uma_letra_grega_por_extenso(self):
        """The description is what the tooltip shows and what the report
        prints under the header, so it is read as often as the symbol.
        A thrust coefficient defined there as `T / (rho*A*(Omega*R)^2)`
        asks the reader to parse an expression; the same line with the
        letters and the exponents rendered is the equation from the
        textbook."""
        faltas = []
        for helice in (False, True):
            for chave, (_simbolo, descricao) in api.summary_symbols(helice).items():
                achados = sorted(set(GREGO_EM_TEXTO.findall(_apenas_o_texto(descricao))))
                if achados:
                    faltas.append(f"{'propeller' if helice else 'rotor'}:{chave} {achados}")
        self.assertEqual(sorted(set(faltas)), [],
                         "unrendered notation in a column description: " + str(sorted(set(faltas))))


class TestSimbolosDeEixo(unittest.TestCase):
    """`nomenclature` is the single LaTeX source (PR-8). Each of its
    three render targets must actually render."""

    def test_cada_alvo_de_renderizacao_sai_renderizado(self):
        faltas = []
        for chave in nomenclature.QUANTITIES:
            for helice in (False, True):
                if not nomenclature.is_visible(chave, helice):
                    continue
                mathtext = nomenclature.symbol_mathtext(chave, helice)
                html = nomenclature.symbol_html(chave, helice)
                if NOTACAO_EM_TEXTO.search(mathtext) and "$" not in mathtext:
                    faltas.append(f"mathtext {chave}: {mathtext!r}")
                if NOTACAO_EM_TEXTO.search(re.sub(r"<[^>]+>", "", html)):
                    faltas.append(f"html {chave}: {html!r}")
        self.assertEqual(faltas, [], "unrendered axis symbol: " + str(faltas))


class TestDocumentacao(unittest.TestCase):
    """`docs/documentation.html` is read by a human, and its equations
    are typeset. Prose that falls back to `mu_x` between two typeset
    equations reads as a third notation."""

    def test_prosa_nao_usa_notacao_em_texto(self):
        html = (RAIZ / "docs" / "documentation.html").read_text(encoding="utf-8")
        achados = sorted(set(NOTACAO_EM_TEXTO.findall(_sem_matematica_nem_codigo(html))))
        self.assertEqual(achados, [], "plain-text notation in the documentation: " + str(achados))


class TestAjuda(unittest.TestCase):
    """The help popup is where a reader goes to find the equation, so it
    is the last place that should present one in source form. Its
    `equation` entries are raw LaTeX by design and are typeset by the
    popup; the surrounding prose is not, and has to carry its own
    rendering."""

    #: Rendered by the popup as mathematics, so ASCII there is the input
    #: format, not a fallback.
    CHAVES_DE_LATEX = ("equation", "equations")

    def _varrer(self, no, caminho, faltas):
        if isinstance(no, str):
            achados = sorted(set(GREGO_EM_TEXTO.findall(
                _apenas_o_texto(_sem_matematica_nem_codigo(no)))))
            if achados:
                faltas.append(f"{caminho} {achados}")
        elif isinstance(no, dict):
            for chave, valor in no.items():
                if chave not in self.CHAVES_DE_LATEX:
                    self._varrer(valor, f"{caminho}.{chave}", faltas)
        elif isinstance(no, (list, tuple)):
            for i, valor in enumerate(no):
                self._varrer(valor, f"{caminho}[{i}]", faltas)

    def test_a_prosa_dos_campos_nao_soletra_notacao(self):
        from zbemt.gui import help_content

        faltas = []
        self._varrer(help_content.FIELD_HELP, "FIELD_HELP", faltas)
        self.assertEqual(faltas, [], "unrendered notation in field help: " + str(faltas))

    def test_a_prosa_dos_blocos_nao_soletra_notacao(self):
        from zbemt.gui import help_blocks

        faltas = []
        self._varrer(help_blocks.BLOCK_HELP, "BLOCK_HELP", faltas)
        self.assertEqual(faltas, [], "unrendered notation in block help: " + str(faltas))


@requires_qt
class TestRotulosDaGui(unittest.TestCase):
    """A field label and a block title are the shortest user-facing
    text there is, and the one most likely to be typed as the field's
    own name."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication

        from zbemt.gui.app import MainWindow

        cls.app = QApplication.instance() or QApplication([])
        cls.janela = MainWindow()
        cls.janela.resize(1400, 900)

    @classmethod
    def tearDownClass(cls):
        cls.janela.close()
        cls.janela.deleteLater()

    def test_nenhum_rotulo_visivel_soletra_um_simbolo(self):
        from PyQt6.QtWidgets import (QCheckBox, QGroupBox, QLabel, QPushButton,
                                     QRadioButton)

        faltas = []
        for classe in (QLabel, QGroupBox, QCheckBox, QRadioButton, QPushButton):
            for widget in self.janela.findChildren(classe):
                texto = widget.title() if classe is QGroupBox else widget.text()
                if not texto:
                    continue
                if NOTACAO_EM_TEXTO.search(_sem_matematica_nem_codigo(texto)):
                    faltas.append(f"{classe.__name__}: {texto.strip()[:70]!r}")
        self.assertEqual(sorted(set(faltas)), [],
                         "plain-text notation on a GUI label: " + str(sorted(set(faltas))))


    def test_nenhuma_dica_escreve_uma_letra_grega_por_extenso(self):
        """The tooltip is the first explanation the user gets, and it
        sits directly under a label that already carries the rendered
        symbol. Falling back to `|alpha|` or `Ut` there makes the two
        halves of the same field disagree about how the quantity is
        written."""
        from PyQt6.QtWidgets import QWidget

        faltas = []
        for widget in self.janela.findChildren(QWidget):
            dica = widget.toolTip()
            if not dica or any(m in dica for m in TOOLTIPS_DE_FORMATO_DE_ARQUIVO):
                continue
            texto = _sem_matematica_nem_codigo(CHAVE_INICIAL.sub(" ", dica))
            achados = sorted(set(GREGO_EM_TEXTO.findall(_apenas_o_texto(texto))))
            if achados:
                faltas.append(f"{achados} in {dica.strip()[:60]!r}")
        self.assertEqual(sorted(set(faltas)), [],
                         "unrendered notation in a tooltip: " + str(sorted(set(faltas))))


if __name__ == "__main__":
    unittest.main()
"""Verify rendered mathematical notation across user-facing surfaces.

Purpose: prevent plain-text or Unicode approximations from replacing LaTeX
symbols and subscripts in GUI, plots, help, reports, and HTML documentation.
Inputs are source modules and documentation fixtures; outputs are unittest or
pytest failures identifying the invalid surface. Code identifiers inside
``<code>`` and serialized keys are allowed. The checks complement notation and
nomenclature parity tests and do not modify application files.
"""
