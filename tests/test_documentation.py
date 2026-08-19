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
            # Title only, without its section number: chapters get renumbered
            # when the document is restructured, and the number is not what
            # this test is about.
            "Solidity and blade aspect ratio",
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


class TestReferenciasNumericasResolvem(unittest.TestCase):
    """"Section N.M" in the prose must name a section that exists.

    Anchors are checked elsewhere, but a reference written as plain text
    is invisible to that check. Renumbering bumped the first number of
    "Sections A and B" and left the second one alone, so several pointed
    at sections that had ceased to exist -- 2.9, 2.8.4, 6.9, 9.3.3.
    """

    def test_toda_secao_citada_em_texto_existe(self):
        html = _html()
        inicio, fim = "<!-- INDICE-GERAL -->", "<!-- /INDICE-GERAL -->"
        if inicio in html:
            html = html[:html.index(inicio)] + html[html.index(fim):]

        existentes = {
            m.group(1)
            for m in re.finditer(r'<h[2-6][^>]*>\s*(\d+(?:\.\d+)*)[.\s]', html)
        }
        self.assertGreater(len(existentes), 50, "no numbered headings found")

        texto = re.sub(r"<[^>]+>", " ", html)
        citadas = set()
        for m in re.finditer(
                r"\bSections?\s+(\d+(?:\.\d+)*)(?:\s*(?:,|and|to|&)\s*(\d+(?:\.\d+)*))?",
                texto):
            citadas.update(g for g in m.groups() if g)

        quebradas = sorted(c for c in citadas if c not in existentes)
        self.assertEqual(
            quebradas, [],
            f"prose points at sections that do not exist: {quebradas}")


class TestExemplosCitadosExistem(unittest.TestCase):
    """Every example the reader is told to run must actually be there.

    The document sent people to `projects/heli_utility_medium` and
    `projects/propeller_light_aircraft`, neither of which is in the
    repository, and to a batch named "mu_x sweep" that no project
    defines. A command that cannot run is worse than no example.
    """

    def test_todo_projeto_citado_existe(self):
        # Real project folders are lowercase; a capitalised name is a
        # placeholder standing in for the reader's own project.
        citados = {c for c in re.findall(r"projects/([a-zA-Z_][\w]*)", _html())
                   if not c[0].isupper()}
        self.assertTrue(citados, "the examples stopped naming any project")
        faltando = sorted(c for c in citados if not (RAIZ / "projects" / c).is_dir())
        self.assertEqual(faltando, [], f"projects cited but absent: {faltando}")

    def test_todo_batch_citado_existe(self):
        import json
        citados = set(re.findall(r'--from-bemt-batch\s+"([^"]+)"', _html()))
        if not citados:
            self.skipTest("no batch named in the examples")
        nomes = set()
        for arquivo in (RAIZ / "projects").glob("*/inputs/batches.bemt"):
            try:
                nomes.update(b.get("name") for b in json.loads(
                    arquivo.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                continue
        faltando = sorted(c for c in citados if c not in nomes)
        self.assertEqual(faltando, [], f"batches cited but not defined: {faltando}")


class TestCaminhosDeCliCitados(unittest.TestCase):
    """Every `--set` path cited must name a real field of that namespace.

    The documentation repeatedly claimed a field was "not exposed" on the
    command line when `--set config.X=...` reached it perfectly well, and
    it cited `--set config.dynamic_stall_A` for a field that lives in the
    airfoil namespace. Both send the reader to a command that fails.
    """

    @classmethod
    def setUpClass(cls):
        from dataclasses import fields
        from zbemt.bemt import BEMTConfig
        from zbemt.models import AirfoilDef, RotorGeometryDef
        cls.namespaces = {
            "config": {f.name for f in fields(BEMTConfig)},
            "airfoil": {f.name for f in fields(AirfoilDef)},
            "geom": {f.name for f in fields(RotorGeometryDef)},
        }

    def test_todo_set_citado_existe(self):
        # `--set NAMESPACE.FIELD` is the placeholder in the CLI's own help
        # text, not a path; real paths are lowercase.
        citados = [(ns, c) for ns, c in re.findall(r"--set\s+(\w+)\.(\w+)", _html())
                   if not ns.isupper()]
        self.assertGreater(len(citados), 10, "the --set examples disappeared")
        invalidos = []
        for ns, campo in citados:
            se = self.namespaces.get(ns)
            if se is None:
                invalidos.append(f"--set {ns}.{campo} (unknown namespace)")
            elif campo not in se:
                invalidos.append(f"--set {ns}.{campo} (no such field in {ns})")
        self.assertEqual(sorted(set(invalidos)), [], f"broken --set paths: {invalidos}")

    def test_nenhum_campo_e_declarado_sem_caminho_de_cli(self):
        """No field may be documented as unreachable from the command line."""
        html = _html()
        for frase in ("CLI</span>: not exposed",
                      "CLI</span>: <b>not exposed</b>"):
            self.assertNotIn(
                frase, html,
                "a field is documented as having no CLI path; every field of "
                "config/airfoil/geom is reachable with --set")


class TestNumeracaoDosTitulos(unittest.TestCase):
    """A heading's number must have as many parts as its depth.

    Restructuring renumbers hundreds of references at once, and the way
    that goes wrong is silent: a regex with `(\\.\\d+)*` keeps only the LAST
    repetition, so "12.3.1.1" collapses to "9.1" and an `<h4>` ends up
    numbered like an `<h3>`. The document still renders; the numbering is
    simply wrong. This catches it.
    """

    def test_numero_do_titulo_bate_com_o_capitulo_e_o_nivel(self):
        """A heading's number must name its chapter and match its depth.

        Renumbering also caught headings that were never section numbers:
        the workflow steps in the tutorial read 1..7 for the seven tabs,
        and three renumbering passes bumped them to 2,3,4,5,7,8,13. They
        are excluded here by their `uso-` ids, and everything else has to
        agree with the chapter it sits in.
        """
        html = _html()
        inicio, fim = "<!-- INDICE-GERAL -->", "<!-- /INDICE-GERAL -->"
        if inicio in html:                       # the index repeats every number
            html = html[:html.index(inicio)] + html[html.index(fim):]

        capitulo, errados = None, []
        for m in re.finditer(r'<h([2-6])([^>]*)>(.*?)</h\1>', html, re.S):
            nivel, attrs = int(m.group(1)), m.group(2)
            texto = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            achado = re.match(r"(\d+(?:\.\d+)*)[.\s]", texto)
            if not achado or 'id="uso-' in attrs:
                continue
            numero = achado.group(1)
            if nivel == 2:
                capitulo = numero
                continue
            partes = numero.split(".")
            if partes[0] != str(capitulo):
                errados.append(f"h{nivel} '{numero}' in chapter {capitulo}: {texto[:40]}")
            elif len(partes) != nivel - 1:
                errados.append(f"h{nivel} '{numero}' needs {nivel - 1} parts: {texto[:40]}")
        self.assertEqual(errados, [], f"heading numbers out of step: {errados}")

    def test_capitulos_sao_sequenciais(self):
        html = _html()
        inicio, fim = "<!-- INDICE-GERAL -->", "<!-- /INDICE-GERAL -->"
        if inicio in html:
            html = html[:html.index(inicio)] + html[html.index(fim):]
        numeros = [int(m.group(1))
                   for m in re.finditer(r'<h2[^>]*>\s*(\d+)[.\s]', html)]
        self.assertEqual(numeros, list(range(len(numeros))),
                         f"chapter numbers are not 0,1,2,...: {numeros}")


class TestTodoCampoTemSecao(unittest.TestCase):
    """Every settable field is explained, and says how to set it in all three.

    One chapter per GUI page, one subsection per field of that page. The
    subsection has to state the widget, the `.bemt` key AND the CLI flag --
    a field explained only for the window leaves the other two interfaces
    undocumented, which is the gap this checks.
    """

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(RAIZ / "tools"))
        from field_inventory import coletar
        from zbemt.gui.field_help import secoes_da_documentacao
        cls.registros = coletar()
        cls.secoes = secoes_da_documentacao()

    def _secoes_do_campo(self, campo: str) -> list:
        alvo = re.compile(rf"<code>{re.escape(campo)}</code>")
        return [s for s in self.secoes if alvo.search(s.corpo)]

    @staticmethod
    def _marcas(secao) -> int:
        return sum(m in secao.corpo
                   for m in ('class="gui"', 'class="bemt"', 'class="cli"'))

    def test_todo_campo_tem_secao_com_gui_bemt_e_cli(self):
        faltando = []
        for reg in self.registros:
            if not any(self._marcas(s) == 3 for s in self._secoes_do_campo(reg["field"])):
                faltando.append(f"{reg['dataclass']}.{reg['field']}")
        self.assertEqual(
            faltando, [],
            "fields with no subsection stating GUI, .bemt and CLI together: "
            f"{faltando}")

    def test_nenhum_campo_e_citado_so_em_tabela_de_indice(self):
        """A field named only in the generated per-tab list is not documented."""
        for reg in self.registros:
            with self.subTest(campo=reg["field"]):
                self.assertTrue(self._secoes_do_campo(reg["field"]),
                                f"{reg['field']} is not cited anywhere")


class TestIndiceGeral(unittest.TestCase):
    """The table of contents is generated, so it must match the headings.

    A hand-edited index is the classic way for a long document to start
    lying: a chapter is renamed, the index keeps the old name, and the
    reader concludes the section was removed.
    """

    def _construtor(self):
        sys.path.insert(0, str(RAIZ / "tools"))
        import build_toc
        return build_toc

    def test_indice_esta_presente(self):
        html = _html()
        self.assertIn("<!-- INDICE-GERAL -->", html)
        self.assertIn('<nav class="indice-geral"', html)

    def test_indice_bate_com_os_titulos(self):
        build_toc = self._construtor()
        atual = _html()
        limpo = atual
        i = limpo.index(build_toc.MARCA_INICIO)
        j = limpo.index(build_toc.MARCA_FIM) + len(build_toc.MARCA_FIM)
        if limpo[j:j + 1] == "\n":
            j += 1
        limpo = limpo[:i] + limpo[j:]
        limpo, entradas = build_toc.coletar(limpo)
        esperado = build_toc.aplicar(limpo, build_toc.renderizar(entradas))
        self.assertEqual(
            esperado, atual,
            "table of contents out of sync -- run `python tools/build_toc.py --escrever`")

    def test_todo_link_do_indice_resolve(self):
        html = _html()
        ids = set(re.findall(r'id="([\w-]+)"', html))
        bloco = re.search(r"<!-- INDICE-GERAL -->(.*?)<!-- /INDICE-GERAL -->", html, re.S)
        self.assertIsNotNone(bloco)
        ancoras = re.findall(r'href="#([\w-]+)"', bloco.group(1))
        self.assertGreater(len(ancoras), 50, "the index looks truncated")
        for ancora in ancoras:
            with self.subTest(ancora=ancora):
                self.assertIn(ancora, ids)


if __name__ == "__main__":
    unittest.main()
