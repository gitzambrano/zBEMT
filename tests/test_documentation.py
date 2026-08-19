"""The documentation has to tell the truth about the code.

`docs/documentation.html` is the application's embedded help (the "?" /
F1 button). It once aged badly: it described the file tree that predated
the package reorganization and taught `python main_batch.py`, a command
that no longer exists. Wrong documentation is worse than none -- the
reader trusts it and wastes time looking for what is not there.

These tests do not judge the writing. They verify checkable facts: file
names that must exist, flags that the CLI must accept, anchors that must
resolve, resources that must be bundled.
"""
import re
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DOC = RAIZ / "docs" / "documentation.html"


def _html() -> str:
    return DOC.read_text(encoding="utf-8")


class TestDocumentationIsSelfContained(unittest.TestCase):
    def test_prosa_principal_e_justificada(self):
        """Running prose must use justified alignment in the document."""
        self.assertIn(
            ".page p, .page li, .page figcaption, .page .boxed{text-align:justify;}",
            _html(),
        )

    def test_workflow_e_modos_de_entrada_estao_documentados(self):
        """The workflow order and the two sizing modes must not disappear."""
        html = _html()
        self.assertLess(html.index('id="uso-geometria"'), html.index('id="uso-aerofolio"'))
        self.assertLess(html.index('id="uso-aerofolio"'), html.index('id="uso-case"'))
        self.assertLess(html.index('id="uso-case"'), html.index('id="uso-resultados"'))
        for trecho in (
            "fixed-thrust trim",
            "fixed-$C_T$ trim",
            "\\sigma = \\frac{B S_b}{\\pi R^2}",
            "AR = \\frac{R^2}{S_b}",
            "5.2.1 Solidity and blade aspect ratio",
        ):
            self.assertIn(trecho, html)
        self.assertNotIn("botão \"?\"", html)
        self.assertNotIn("Reference definitions (source:", html)
        self.assertNotIn("Repository map", html)

    """The embedded help must open in a lab with no internet."""

    def test_nenhum_recurso_carregado_de_fora(self):
        externos = re.findall(r'src="(https?://[^"]+)"', _html())
        self.assertEqual(externos, [], f"recursos externos: {externos}")

    def test_toda_imagem_referenciada_existe_no_repositorio(self):
        html = _html()
        refs = set(re.findall(r'src="((?:img|vendor)/[^"]+)"', html))
        self.assertGreater(len(refs), 20, "esperava dezenas de figuras")
        faltando = [r for r in refs if not (DOC.parent / r).exists()]
        self.assertEqual(faltando, [], f"referenciadas e ausentes: {faltando}")

    def test_katex_esta_empacotado_e_completo(self):
        """Without local KaTeX, the equations turn into raw LaTeX for
        exactly the reader who went looking for them offline."""
        vendor = DOC.parent / "vendor" / "katex"
        for arquivo in ("katex.min.js", "auto-render.min.js", "katex.min.css"):
            self.assertTrue((vendor / arquivo).exists(), f"falta {arquivo}")
        css = (vendor / "katex.min.css").read_text(encoding="utf-8")
        fontes = set(re.findall(r"url\(([^)]+)\)", css))
        faltando = [f for f in fontes if not (vendor / f).exists()]
        self.assertEqual(faltando, [], f"fontes referenciadas e ausentes: {faltando}")

    def test_renderizador_nao_aninha_delimitadores_matematicos(self):
        r"""Rendering must not rewrite symbols inside a formula.

        This rewriting used to produce expressions like ``\mu_{x,V}_z``
        and made KaTeX display the whole formula in red over a double
        subscript.
        """
        html = _html()
        self.assertNotIn("createTreeWalker", html)
        # The embedded auto-renderer code contains the word preProcess
        # internally; what must not exist is a custom hook in the
        # documentation's configuration block.
        self.assertIn("lambda", html)
        self.assertIn("mu", html)
        self.assertNotIn("preProcess:", html)

    def test_nenhum_caractere_de_controle_no_html(self):
        """LaTeX written in a NON-raw Python string arrives corrupted in the HTML.

        `"\alpha"` in a plain string becomes BEL+"lpha", `"\frac"` becomes
        FF+"rac", `"\theta"` becomes TAB+"heta" and `"\rho"` becomes
        CR+"ho" -- and KaTeX fails silently, leaving the equation as raw
        text in red in the middle of the page. This happened with eleven
        commands at once during a batch edit of the physics sections.

        No control character has a legitimate use in this file, so the
        check is simply their absence.
        """
        suspeitos = sorted({
            hex(ord(c)) for c in _html() if ord(c) < 32 and c != chr(10)
        })
        self.assertEqual(suspeitos, [],
                          "caractere de controle no HTML -- LaTeX escrito "
                          f"em string nao-raw: {suspeitos}")

    def test_toda_expressao_matematica_tem_chaves_balanceadas(self):
        """One stray brace brings down the whole equation in KaTeX.

        Found this way: the Pitt-Peters state equation carried a `}`
        with no matching opener, and the reader saw the raw LaTeX source
        in place of the formula. The test walks every `$$...$$` block and
        every `$...$`.
        """
        # KaTeX ships EMBEDDED in the file (self-contained documentation,
        # runs offline), and the minified bundle is full of `$` and of
        # JavaScript braces -- scanning the raw HTML would flag KaTeX itself.
        html = re.sub(r"<script\b.*?</script>", "", _html(), flags=re.S | re.I)
        html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
        blocos = re.findall(r"\$\$(.+?)\$\$", html, re.S)
        blocos += re.findall(r"(?<!\$)\$([^$\n]{1,400})\$(?!\$)", html)
        quebrados = []
        for expr in blocos:
            # `\{` and `\}` are literal braces, not delimiters
            limpo = expr.replace(r"\{", "").replace(r"\}", "")
            if limpo.count("{") != limpo.count("}"):
                quebrados.append(expr.strip()[:70])
        self.assertEqual(quebrados, [],
                          "expressao com chaves desbalanceadas: " + str(quebrados))

    def test_toda_ancora_interna_resolve(self):
        html = _html()
        ids = re.findall(r'id="([\w-]+)"', html)
        self.assertEqual(len(ids), len(set(ids)), "duplicate IDs in the documentation")
        ids = set(ids)
        refs = set(re.findall(r'href="#([\w-]+)"', html))
        self.assertEqual(sorted(refs - ids), [], "broken anchors")


class TestDocumentationDoesNotCiteMissingFiles(unittest.TestCase):
    """It once mistakenly described the tree that predated the reorganization."""

    #: names that existed at the repository root before v0.1.0 and now
    #: live inside the package, at a different path
    NOMES_MORTOS = ("main_batch.py", "plot_style.py")

    def test_nao_menciona_modulo_que_deixou_de_existir(self):
        html = _html()
        for nome in self.NOMES_MORTOS:
            with self.subTest(nome=nome):
                self.assertNotIn(nome, html,
                                 f"the documentation still cites {nome}, which no longer exists")

    def test_todo_modulo_citado_com_caminho_existe(self):
        """Catches mentions like `<code>gui/app.py</code>` or
        `<code>viz/plots.py</code>`: if the documentation gives the path,
        it has to resolve inside the package."""
        citados = set(re.findall(r"<code>((?:\w+/)+\w+\.py)</code>", _html()))
        self.assertTrue(citados, "expected module paths cited in the documentation")
        # the documentation cites both paths inside the package
        # (`gui/app.py`) and paths from the root (`tools/generate_...py`)
        faltando = [c for c in citados
                    if not (RAIZ / "zbemt" / c).exists() and not (RAIZ / c).exists()]
        self.assertEqual(faltando, [], f"citados e inexistentes: {faltando}")


class TestFlagsCitadasExistemNoCli(unittest.TestCase):
    """A documented flag that the CLI rejects sends the user off to debug
    their own command for an error that is not theirs."""

    #: `--stall-model` appears on purpose, in a note explaining that it
    #: WAS REMOVED and why. Citing a flag to say it does not exist is
    #: useful information, not an error.
    CITADAS_COMO_REMOVIDAS = {"--stall-model", "--dynamic-stall-model"}

    @classmethod
    def setUpClass(cls):
        import argparse
        from zbemt import cli
        parser = cli._build_parser()
        cls.reais = set()
        for acao in parser._actions:
            cls.reais.update(acao.option_strings)
        assert isinstance(parser, argparse.ArgumentParser)

    def _flags_citadas(self, texto: str) -> set:
        # The scripts under `tools/` have their own flags, which the
        # zbemt CLI does not know and should not: out of scope for this check.
        linhas = [l for l in texto.splitlines() if "tools/" not in l]
        texto = chr(10).join(linhas)
        # the embedded inline KaTeX block has strings like "--display-mode"
        # which are KaTeX's own option names (its CLI, not zbemt's) -- out of scope
        texto = re.sub(r"<!-- KATEX-INLINE:INICIO -->.*?<!-- KATEX-INLINE:FIM -->",
                       "", texto, flags=re.DOTALL)
        # `var(--accent)` and the like are CSS variables, not flags
        texto = re.sub(r"var\(--[\w-]+\)", "", texto)
        texto = re.sub(r"--[\w-]+\s*:", "", texto)
        return set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]{2,})", texto))

    def _conferir(self, caminho: Path):
        citadas = self._flags_citadas(caminho.read_text(encoding="utf-8"))
        inexistentes = sorted(citadas - self.reais - self.CITADAS_COMO_REMOVIDAS)
        self.assertEqual(inexistentes, [],
                         f"{caminho.name} cites flags the CLI does not accept: {inexistentes}")

    def test_documentation_html(self):
        self._conferir(DOC)

    def test_readme(self):
        self._conferir(RAIZ / "README.md")

    def test_claude_md(self):
        self._conferir(RAIZ / "CLAUDE.md")


class TestFuncoesDeApiCitadasExistem(unittest.TestCase):
    def test_toda_api_citada_existe(self):
        from zbemt import api
        textos = [DOC, RAIZ / "README.md", RAIZ / "CLAUDE.md"]
        citadas = set()
        for caminho in textos:
            citadas |= set(re.findall(r"\bapi\.(\w+)\s*\(", caminho.read_text(encoding="utf-8")))
        self.assertTrue(citadas, "expected api calls cited in the documentation")
        faltando = sorted(n for n in citadas if not hasattr(api, n))
        self.assertEqual(faltando, [], f"citadas e inexistentes em zbemt.api: {faltando}")



class TestIndiceDeCamposSegueATela(unittest.TestCase):
    """Each tab chapter opens with an index of its fields IN THE ORDER
    they appear in the window -- it is the bridge in the direction the
    user travels: they are looking at the third box in the tab and want
    the explanation for that.

    The index is generated from `tools/field_index.py`, reading the real
    GUI. This test redoes that reading and compares: a field moved,
    added, or removed makes the index lie, and lying about order is
    worse than having no index."""

    @classmethod
    def setUpClass(cls):
        try:
            from PyQt6.QtWidgets import QApplication          # noqa: F401
        except ImportError:                                   # pragma: no cover
            raise unittest.SkipTest("sem PyQt6")

    def _publicado(self, aba: str) -> list:
        html = _html()
        bloco = re.search(rf"<!-- INDICE-DE-CAMPOS:{aba} -->(.*?)<!-- /INDICE", html, re.S)
        self.assertIsNotNone(bloco, f"the documentation has no entry for the {aba} tab")
        return re.findall(r"<li><code>(\w+)</code>", bloco.group(1))

    def test_indice_de_cada_aba_bate_com_a_ordem_da_tela(self):
        sys.path.insert(0, str(RAIZ / "tools"))
        from field_index import ABAS, coletar_ordem_da_tela

        na_tela = coletar_ordem_da_tela()
        for aba in ABAS:
            with self.subTest(aba=aba):
                esperado = [campo for campo, _ancora in na_tela[aba]]
                if not esperado:
                    continue
                self.assertEqual(
                    self._publicado(aba), esperado,
                    f"{aba} tab index out of sync -- run "
                    f"`python tools/field_index.py --escrever`")

    def test_todo_link_do_indice_resolve(self):
        html = _html()
        ids = set(re.findall(r'id="([\w-]+)"', html))
        for bloco in re.findall(r"<!-- INDICE-DE-CAMPOS:.*?<!-- /INDICE", html, re.S):
            for ancora in re.findall(r'href="#([\w-]+)"', bloco):
                self.assertIn(ancora, ids)


if __name__ == "__main__":
    unittest.main()
