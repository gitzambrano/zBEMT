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

from tests.helpers import requires_qt

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "documentation.html"


def _html() -> str:
    return DOC.read_text(encoding="utf-8")


class TestMathRenders(unittest.TestCase):
    """No HTML tag may sit between two math delimiters.

    KaTeX's auto-render walks TEXT NODES looking for `$`...`$`. An element
    between the two delimiters splits the run in half, so the opening `$$`
    never meets its closing one: the equation is not rendered at all and the
    reader is shown its raw LaTeX source instead.

    It is an easy defect to introduce and an easy one to miss, because the
    markup is well formed and the link inside it points at the right place.
    It happened once, to the coupling equation of 5.9.1, when a pass that
    turned prose cross-references into links did not know to skip formulas --
    and what the reader saw was a paragraph of `$\\lambda_i$` and `$\\mu_x$`.
    """

    def _math_blocks(self, html: str) -> list:
        body = html[html.index("<body>"):]
        body = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", body, flags=re.S)
        blocks = re.findall(r"\$\$.*?\$\$", body, re.S)
        blocks += re.findall(r"(?<!\$)\$[^$\n]*\$(?!\$)", body)
        return blocks

    def test_embedded_katex_is_a_faithful_copy_of_the_vendor(self):
        """The embedded KaTeX must be the vendor build, byte for byte.

        It is minified JavaScript sitting in the same file as the prose, so a
        careless find-and-replace over the document edits the LIBRARY too. That
        happened: a rename of `\\lambda` to `\\lambda_{total}` and of `\\mu` to
        `\\mu_x` reached 205 places inside the bundle and deleted KaTeX's own
        definitions of both commands. Every `$\\lambda_i$` and `$\\mu_x$` in the
        document then failed with "Undefined control sequence" and the reader
        was shown raw LaTeX.

        Nothing in the prose can detect that, which is why the check is here:
        compare the embedded copy against `docs/vendor/katex/`. Regenerate with
        `python tools/katex_inline.py` if this fails.
        """
        html = _html()
        vendor = ROOT / "docs" / "vendor" / "katex"
        for name in ("katex.min.js", "auto-render.min.js"):
            with self.subTest(file=name):
                source = (vendor / name).read_text(encoding="utf-8").strip()
                self.assertIn(
                    source, html,
                    f"the embedded {name} differs from docs/vendor/katex/{name}; "
                    "run `python tools/katex_inline.py` to restore it")

    def test_no_html_tag_inside_math(self):
        blocks = self._math_blocks(_html())
        self.assertGreater(len(blocks), 500, "no math found -- the scan is broken")
        with_tag = [b for b in blocks if re.search(r"<[a-zA-Z/]", b)]
        self.assertEqual(
            [re.sub(r"\s+", " ", b)[:160] for b in with_tag], [],
            "math containing an HTML tag: KaTeX will not render it and the "
            "raw LaTeX is shown to the reader")

    def test_math_delimiters_are_paired(self):
        """An unclosed `$` swallows the prose after it into a bogus formula.

        Checked the way the browser sees it. KaTeX walks the DOM and scans
        each run of CONSECUTIVE text nodes; an element breaks the run, and a
        newline inside one does not. Testing the raw source line by line
        instead would flag every inline formula that a reformatter happened to
        wrap across two lines, which renders perfectly well.
        """
        from html.parser import HTMLParser

        ignored = {"script", "noscript", "style", "textarea", "pre", "code", "option"}

        class TextRuns(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.runs, self._current, self._line, self._skip = [], [], 0, 0

            def _flush(self):
                if self._current:
                    self.runs.append((self._line, "".join(self._current)))
                    self._current = []

            def handle_starttag(self, tag, attrs):
                self._flush()
                if tag in ignored:
                    self._skip += 1

            def handle_endtag(self, tag):
                self._flush()
                if tag in ignored and self._skip:
                    self._skip -= 1

            def handle_startendtag(self, tag, attrs):
                self._flush()

            def handle_data(self, data):
                if self._skip:
                    return
                if not self._current:
                    self._line = self.getpos()[0]
                self._current.append(data)

        html = _html()
        reader = TextRuns()
        reader.feed(html[html.index("<body>"):])
        reader._flush()

        unclosed, found = [], 0
        for line_no, text in reader.runs:
            i = 0
            while i < len(text):
                j = text.find("$", i)
                if j < 0:
                    break
                end = "$$" if text.startswith("$$", j) else "$"
                k = text.find(end, j + len(end))
                if k < 0:
                    unclosed.append(f"line {line_no}: {text[j:j + 90]!r}")
                    break
                found += 1
                i = k + len(end)

        self.assertGreater(found, 500, "no math found -- the scan is broken")
        self.assertEqual(unclosed, [], f"unclosed math delimiters: {unclosed}")


class TestDocumentationIsSelfContained(unittest.TestCase):
    def test_prosa_principal_e_justificada(self):
        """Running prose must use justified alignment in the document."""
        self.assertIn(
            ".page p, .page li, .page figcaption, .page .boxed{text-align:justify;}",
            _html(),
        )

    def test_main_prose_is_justified(self):
        """Running prose must use justified alignment in the document."""
        self.assertIn(
            ".page p, .page li, .page figcaption, .page .boxed{text-align:justify;}",
            _html(),
        )

    def test_workflow_and_input_modes_are_documented(self):
        """The workflow order and the two sizing modes must not disappear."""
        html = _html()
        self.assertLess(html.index('id="uso-geometria"'), html.index('id="uso-aerofolio"'))
        self.assertLess(html.index('id="uso-aerofolio"'), html.index('id="uso-case"'))
        self.assertLess(html.index('id="uso-case"'), html.index('id="uso-resultados"'))
        for snippet in (
            "fixed-thrust trim",
            "fixed-$C_T$ trim",
            # The blade count is N_b throughout, as the nomenclature table
            # defines it; the sizing formulas used to write it as B.
            "\\sigma = \\frac{N_b S_b}{\\pi R^2}",
            "AR = \\frac{R^2}{S_b}",
            # Title only, without its section number: chapters get renumbered
            # when the document is restructured, and the number is not what
            # this test is about.
            "Solidity and blade aspect ratio",
        ):
            self.assertIn(snippet, html)
        self.assertNotIn("botão \"?\"", html)
        self.assertNotIn("Reference definitions (source:", html)
        self.assertNotIn("Repository map", html)

    """The embedded help must open in a lab with no internet."""

    def test_no_resource_loaded_from_outside(self):
        external = re.findall(r'src="(https?://[^"]+)"', _html())
        self.assertEqual(external, [], f"external resources: {external}")

    def test_every_referenced_image_exists_in_the_repository(self):
        html = _html()
        refs = set(re.findall(r'src="((?:img|vendor)/[^"]+)"', html))
        self.assertGreater(len(refs), 20, "expected dozens of figures")
        missing = [r for r in refs if not (DOC.parent / r).exists()]
        self.assertEqual(missing, [], f"referenced but absent: {missing}")

    def test_katex_is_bundled_and_complete(self):
        """Without local KaTeX, the equations turn into raw LaTeX for
        exactly the reader who went looking for them offline."""
        vendor = DOC.parent / "vendor" / "katex"
        for file_name in ("katex.min.js", "auto-render.min.js", "katex.min.css"):
            self.assertTrue((vendor / file_name).exists(), f"missing {file_name}")
        css = (vendor / "katex.min.css").read_text(encoding="utf-8")
        fonts = set(re.findall(r"url\(([^)]+)\)", css))
        missing = [f for f in fonts if not (vendor / f).exists()]
        self.assertEqual(missing, [], f"referenced fonts absent: {missing}")

    def test_renderer_does_not_nest_math_delimiters(self):
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

    def test_no_control_character_in_the_html(self):
        """LaTeX written in a NON-raw Python string arrives corrupted in the HTML.

        `"\alpha"` in a plain string becomes BEL+"lpha", `"\frac"` becomes
        FF+"rac", `"\theta"` becomes TAB+"heta" and `"\rho"` becomes
        CR+"ho" -- and KaTeX fails silently, leaving the equation as raw
        text in red in the middle of the page. This happened with eleven
        commands at once during a batch edit of the physics sections.

        No control character has a legitimate use in this file, so the
        check is simply their absence.
        """
        suspects = sorted({
            hex(ord(c)) for c in _html() if ord(c) < 32 and c != chr(10)
        })
        self.assertEqual(suspects, [],
                          "control character in the HTML -- LaTeX written "
                          f"in a non-raw string: {suspects}")

    def test_every_math_expression_has_balanced_braces(self):
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
        blocks = re.findall(r"\$\$(.+?)\$\$", html, re.S)
        blocks += re.findall(r"(?<!\$)\$([^$\n]{1,400})\$(?!\$)", html)
        broken = []
        for expr in blocks:
            # `\{` and `\}` are literal braces, not delimiters
            clean = expr.replace(r"\{", "").replace(r"\}", "")
            if clean.count("{") != clean.count("}"):
                broken.append(expr.strip()[:70])
        self.assertEqual(broken, [],
                          "expression with unbalanced braces: " + str(broken))

    def test_every_internal_anchor_resolves(self):
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
    DEAD_NAMES = ("main_batch.py", "plot_style.py")

    def test_does_not_mention_a_module_that_no_longer_exists(self):
        html = _html()
        for name in self.DEAD_NAMES:
            with self.subTest(name=name):
                self.assertNotIn(name, html,
                                 f"the documentation still cites {name}, which no longer exists")

    def test_every_module_cited_with_a_path_exists(self):
        """Catches mentions like `<code>gui/app.py</code>` or
        `<code>viz/plots.py</code>`: if the documentation gives the path,
        it has to resolve inside the package."""
        # The documentation does not name modules any more (see the rules in
        # CLAUDE.md). This stays as a guard: if a path is ever cited again,
        # it has to resolve.
        cited = set(re.findall(r"<code>((?:\w+/)+\w+\.py)</code>", _html()))
        # the documentation cites both paths inside the package
        # (`gui/app.py`) and paths from the root (`tools/generate_...py`)
        missing = [c for c in cited
                   if not (ROOT / "zbemt" / c).exists() and not (ROOT / c).exists()]
        self.assertEqual(missing, [], f"cited but nonexistent: {missing}")


class TestCitedFlagsExistInTheCli(unittest.TestCase):
    """A documented flag that the CLI rejects sends the user off to debug
    their own command for an error that is not theirs."""

    #: `--stall-model` appears on purpose, in a note explaining that it
    #: WAS REMOVED and why. Citing a flag to say it does not exist is
    #: useful information, not an error.
    CITED_AS_REMOVED = {"--stall-model", "--dynamic-stall-model"}

    @classmethod
    def setUpClass(cls):
        import argparse
        from zbemt import cli
        parser = cli._build_parser()
        cls.real = set()
        for action in parser._actions:
            cls.real.update(action.option_strings)
        assert isinstance(parser, argparse.ArgumentParser)

    def _cited_flags(self, text: str) -> set:
        # The scripts under `tools/` and `tests/` have their own flags,
        # which the zbemt CLI does not know and should not: `--write`
        # belongs to the index builder and `--list` to the test runner.
        # Out of scope for this check.
        lines = [l for l in text.splitlines()
                 if "tools/" not in l and "tests/" not in l]
        text = chr(10).join(lines)
        # the embedded inline KaTeX block has strings like "--display-mode"
        # which are KaTeX's own option names (its CLI, not zbemt's) -- out of scope
        text = re.sub(r"<!-- KATEX-INLINE:INICIO -->.*?<!-- KATEX-INLINE:FIM -->",
                      "", text, flags=re.DOTALL)
        # `var(--accent)` and the like are CSS variables, not flags
        text = re.sub(r"var\(--[\w-]+\)", "", text)
        text = re.sub(r"--[\w-]+\s*:", "", text)
        return set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]{2,})", text))

    def _check(self, path: Path):
        cited = self._cited_flags(path.read_text(encoding="utf-8"))
        nonexistent = sorted(cited - self.real - self.CITED_AS_REMOVED)
        self.assertEqual(nonexistent, [],
                         f"{path.name} cites flags the CLI does not accept: {nonexistent}")

    def test_documentation_html(self):
        self._check(DOC)

    def test_readme(self):
        self._check(ROOT / "README.md")

    def test_claude_md(self):
        self._check(ROOT / "CLAUDE.md")


class TestCitedApiFunctionsExist(unittest.TestCase):
    def test_every_cited_api_exists(self):
        from zbemt import api
        texts = [DOC, ROOT / "README.md", ROOT / "CLAUDE.md"]
        cited = set()
        for path in texts:
            cited |= set(re.findall(r"\bapi\.(\w+)\s*\(", path.read_text(encoding="utf-8")))
        self.assertTrue(cited, "expected api calls cited in the documentation")
        missing = sorted(n for n in cited if not hasattr(api, n))
        self.assertEqual(missing, [], f"cited but nonexistent in zbemt.api: {missing}")



class TestFieldIndexFollowsTheScreen(unittest.TestCase):
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
            raise unittest.SkipTest("PyQt6 not installed")

    def _published(self, tab: str) -> list:
        html = _html()
        block = re.search(rf"<!-- INDICE-DE-CAMPOS:{tab} -->(.*?)<!-- /INDICE", html, re.S)
        self.assertIsNotNone(block, f"the documentation has no entry for the {tab} tab")
        return re.findall(r"<li><code>(\w+)</code>", block.group(1))

    def test_each_tab_index_matches_the_screen_order(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from field_index import TABS, collect_screen_order

        on_screen = collect_screen_order()
        for tab in TABS:
            with self.subTest(tab=tab):
                expected = [field for field, _anchor in on_screen[tab]]
                if not expected:
                    continue
                self.assertEqual(
                    self._published(tab), expected,
                    f"{tab} tab index out of sync -- run "
                    f"`python tools/field_index.py --write`")

    def test_every_link_of_the_index_resolves(self):
        html = _html()
        ids = set(re.findall(r'id="([\w-]+)"', html))
        for bloco in re.findall(r"<!-- INDICE-DE-CAMPOS:.*?<!-- /INDICE", html, re.S):
            for anchor in re.findall(r'href="#([\w-]+)"', bloco):
                self.assertIn(anchor, ids)


class TestReferenciasNumericasResolvem(unittest.TestCase):
    """"Section N.M" in the prose must name a section that exists.

    Anchors are checked elsewhere, but a reference written as plain text
    is invisible to that check. Renumbering bumped the first number of
    "Sections A and B" and left the second one alone, so several pointed
    at sections that had ceased to exist -- 2.9, 2.8.4, 6.9, 9.3.3.
    """

    def test_every_section_cited_in_text_exists(self):
        html = _html()
        start, end = "<!-- INDICE-GERAL -->", "<!-- /INDICE-GERAL -->"
        if start in html:
            html = html[:html.index(start)] + html[html.index(end):]

        existing = {
            m.group(1)
            for m in re.finditer(r'<h[2-6][^>]*>\s*(\d+(?:\.\d+)*)[.\s]', html)
        }
        self.assertGreater(len(existing), 50, "no numbered headings found")

        text = re.sub(r"<[^>]+>", " ", html)
        cited = set()
        for m in re.finditer(
                r"\bSections?\s+(\d+(?:\.\d+)*)(?:\s*(?:,|and|to|&)\s*(\d+(?:\.\d+)*))?",
                text):
            cited.update(g for g in m.groups() if g)

        broken = sorted(c for c in cited if c not in existing)
        self.assertEqual(
            broken, [],
            f"prose points at sections that do not exist: {broken}")

    def test_every_reference_is_a_link_to_the_right_section(self):
        """A cross-reference must be a link, and the link must resolve to
        the heading carrying that number.

        The two halves used to drift apart: the number was maintained by
        hand and the anchor by a different hand, so a reference could name
        5.6.2 and open 8.2, or -- for most of the document's life -- name a
        section and be no link at all, leaving the reader to search. Binding
        the number to the anchor here is what stops both.
        """
        html = _html()
        start, end = "<!-- INDICE-GERAL -->", "<!-- /INDICE-GERAL -->"
        if start in html:
            html = html[:html.index(start)] + html[html.index(end):]
        for m in re.finditer(
                r"<!-- INDICE-DE-CAMPOS:.*?<!-- /INDICE-DE-CAMPOS:[^>]*-->",
                html, re.S):
            html = html.replace(m.group(0), "")

        # number -> the id of the heading that carries it
        number_to_id = {}
        for m in re.finditer(r'<h[2-6]\s+id="([^"]+)"[^>]*>\s*(\d+(?:\.\d+)*)[.\s]',
                             html):
            number_to_id.setdefault(m.group(2), m.group(1))
        self.assertGreater(len(number_to_id), 50, "no numbered headings with an id")

        without_link, pointing_wrong = [], []
        # every "Section N.M" outside an <a>, a <code> or a <pre>
        neutral = re.sub(r"<a\b.*?</a>|<code>.*?</code>|<pre>.*?</pre>", " ",
                         html, flags=re.S)
        for m in re.finditer(r"\bSection\s+(\d+(?:\.\d+)*)", neutral):
            without_link.append(m.group(1))

        for m in re.finditer(
                r'<a[^>]*href="#([^"]+)"[^>]*>\s*(?:Section|Chapter)\s+(\d+(?:\.\d+)*)\s*</a>',
                html):
            destination, number = m.group(1), m.group(2)
            expected = number_to_id.get(number)
            if expected is None:
                pointing_wrong.append(f"{number} (no such heading)")
            elif destination != expected:
                pointing_wrong.append(f"{number} -> #{destination}, expected #{expected}")

        self.assertEqual(sorted(set(without_link)), [],
                         "cross-references written as plain text instead of links: "
                         f"{sorted(set(without_link))}")
        self.assertEqual(sorted(set(pointing_wrong)), [],
                         "links whose number and target disagree: "
                         f"{sorted(set(pointing_wrong))}")


class TestTabChaptersAreSelfContained(unittest.TestCase):
    """Chapters 6-13 are the GUI-tab chapters, and DC-4 makes each field
    section self-contained: the reader must not have to follow a link to
    understand or to set a field.

    A reference out of one of those chapters is therefore a defect unless
    it is a statement of SCOPE -- "that setting lives in another tab" --
    rather than a deferral of physics. The few of those are listed here by
    hand, so that adding one is a deliberate act.
    """

    #: (chapter, target) pairs that are scope statements, not deferrals.
    EXCEPTIONS = {
        (8, "9"),      # "the rotor-wide settings are in the Config/Engine tab"
        (8, "14.2"),   # the checks panel runs the validation rules of 14.2
        (11, "10"),    # a batch sweeps the four quantities Run Case defines
        (11, "10.1"),  # ... and a single ad hoc condition uses its flags
    }

    def test_no_reference_leaves_the_chapter(self):
        html = _html()
        start, end = "<!-- INDICE-GERAL -->", "<!-- /INDICE-GERAL -->"
        if start in html:
            html = html[:html.index(start)] + html[html.index(end):]
        for m in re.finditer(
                r"<!-- INDICE-DE-CAMPOS:.*?<!-- /INDICE-DE-CAMPOS:[^>]*-->",
                html, re.S):
            html = html.replace(m.group(0), "")

        lines = html.split("\n")
        chapter_start = {}
        for i, line in enumerate(lines):
            m = re.match(r'<h2[^>]*>\s*(\d+)\.', line)
            if m:
                chapter_start[int(m.group(1))] = i
        bounds = sorted(chapter_start.items())

        def chapter_of(i):
            current = None
            for number, begin in bounds:
                if i >= begin:
                    current = number
            return current

        citation = re.compile(r"\b(?:Section|Chapter)\s+(\d+(?:\.\d+)*)")
        escapes = []
        for i, line in enumerate(lines):
            cap = chapter_of(i)
            if cap is None or not (6 <= cap <= 13):
                continue
            for m in citation.finditer(line):
                target = m.group(1)
                if int(target.split(".")[0]) == cap:
                    continue
                if (cap, target) in self.EXCEPTIONS:
                    continue
                escapes.append(f"chapter {cap}, line {i + 1}: -> {target}")

        self.assertEqual(escapes, [],
                         "tab chapters must be self-contained (DC-4); these "
                         f"reference material outside their own chapter: {escapes}")


class TestCitedExamplesExist(unittest.TestCase):
    """Every example the reader is told to run must actually be there.

    The document sent people to `projects/heli_utility_medium` and
    `projects/propeller_light_aircraft`, neither of which is in the
    repository, and to a batch named "mu_x sweep" that no project
    defines. A command that cannot run is worse than no example.
    """

    def test_every_cited_project_exists(self):
        # Real project folders are lowercase; a capitalised name is a
        # placeholder standing in for the reader's own project.
        cited = {c for c in re.findall(r"projects/([a-zA-Z_][\w]*)", _html())
                 if not c[0].isupper()}
        self.assertTrue(cited, "the examples stopped naming any project")
        missing = sorted(c for c in cited if not (ROOT / "projects" / c).is_dir())
        self.assertEqual(missing, [], f"projects cited but absent: {missing}")

    def test_every_cited_batch_exists(self):
        import json
        cited = set(re.findall(r'--from-bemt-batch\s+"([^"]+)"', _html()))
        if not cited:
            self.skipTest("no batch named in the examples")
        names = set()
        for file_path in (ROOT / "projects").glob("*/inputs/batches.bemt"):
            try:
                names.update(b.get("name") for b in json.loads(
                    file_path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                continue
        missing = sorted(c for c in cited if c not in names)
        self.assertEqual(missing, [], f"batches cited but not defined: {missing}")


class TestCitedCliPaths(unittest.TestCase):
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

    def test_every_cited_set_exists(self):
        # `--set NAMESPACE.FIELD` is the placeholder in the CLI's own help
        # text, not a path; real paths are lowercase.
        cited = [(ns, c) for ns, c in re.findall(r"--set\s+(\w+)\.(\w+)", _html())
                 if not ns.isupper()]
        self.assertGreater(len(cited), 10, "the --set examples disappeared")
        invalid = []
        for ns, field in cited:
            members = self.namespaces.get(ns)
            if members is None:
                invalid.append(f"--set {ns}.{field} (unknown namespace)")
            elif field not in members:
                invalid.append(f"--set {ns}.{field} (no such field in {ns})")
        self.assertEqual(sorted(set(invalid)), [], f"broken --set paths: {invalid}")

    def test_no_field_is_declared_without_a_cli_path(self):
        """No field may be documented as unreachable from the command line."""
        html = _html()
        for frase in ("CLI</span>: not exposed",
                      "CLI</span>: <b>not exposed</b>"):
            self.assertNotIn(
                frase, html,
                "a field is documented as having no CLI path; every field of "
                "config/airfoil/geom is reachable with --set")


class TestHeadingNumbering(unittest.TestCase):
    """A heading's number must have as many parts as its depth.

    Restructuring renumbers hundreds of references at once, and the way
    that goes wrong is silent: a regex with `(\\.\\d+)*` keeps only the LAST
    repetition, so "12.3.1.1" collapses to "9.1" and an `<h4>` ends up
    numbered like an `<h3>`. The document still renders; the numbering is
    simply wrong. This catches it.
    """

    def test_heading_number_matches_chapter_and_level(self):
        """A heading's number must name its chapter and match its depth.

        Renumbering also caught headings that were never section numbers:
        the workflow steps in the tutorial read 1..7 for the seven tabs,
        and three renumbering passes bumped them to 2,3,4,5,7,8,13. They
        are excluded here by their `uso-` ids, and everything else has to
        agree with the chapter it sits in.
        """
        html = _html()
        start, end = "<!-- INDICE-GERAL -->", "<!-- /INDICE-GERAL -->"
        if start in html:                       # the index repeats every number
            html = html[:html.index(start)] + html[html.index(end):]

        chapter, wrong = None, []
        for m in re.finditer(r'<h([2-6])([^>]*)>(.*?)</h\1>', html, re.S):
            level, attrs = int(m.group(1)), m.group(2)
            text = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            found = re.match(r"(\d+(?:\.\d+)*)[.\s]", text)
            if not found or 'id="uso-' in attrs:
                continue
            number = found.group(1)
            if level == 2:
                chapter = number
                continue
            parts = number.split(".")
            if parts[0] != str(chapter):
                wrong.append(f"h{level} '{number}' in chapter {chapter}: {text[:40]}")
            elif len(parts) != level - 1:
                wrong.append(f"h{level} '{number}' needs {level - 1} parts: {text[:40]}")
        self.assertEqual(wrong, [], f"heading numbers out of step: {wrong}")

    def test_chapters_are_sequential(self):
        html = _html()
        start, end = "<!-- INDICE-GERAL -->", "<!-- /INDICE-GERAL -->"
        if start in html:
            html = html[:html.index(start)] + html[html.index(end):]
        numeros = [int(m.group(1))
                   for m in re.finditer(r'<h2[^>]*>\s*(\d+)[.\s]', html)]
        self.assertEqual(numeros, list(range(len(numeros))),
                         f"chapter numbers are not 0,1,2,...: {numeros}")


@requires_qt
class TestEveryFieldHasASection(unittest.TestCase):
    """Every settable field is explained, and says how to set it in all three.

    One chapter per GUI page, one subsection per field of that page. The
    subsection has to state the widget, the `.bemt` key AND the CLI flag --
    a field explained only for the window leaves the other two interfaces
    undocumented, which is the gap this checks.

    Requires PyQt6: `documentation_sections` lives in
    `zbemt.gui.field_help`, which also defines Qt-dependent classes at
    module level, so the module cannot be imported without it. The engine
    and CLI job (no PyQt6, by design) skips this class rather than failing
    to import it."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "tools"))
        from field_inventory import collect
        from zbemt.gui.field_help import documentation_sections
        cls.records = collect()
        cls.sections = documentation_sections()

    def _field_sections(self, field: str) -> list:
        target = re.compile(rf"<code>{re.escape(field)}</code>")
        return [s for s in self.sections if target.search(s.body)]

    @staticmethod
    def _marks(section) -> int:
        return sum(m in section.body
                   for m in ('class="gui"', 'class="bemt"', 'class="cli"'))

    def test_every_field_has_a_section_with_gui_bemt_and_cli(self):
        missing = []
        for record in self.records:
            if not any(self._marks(s) == 3 for s in self._field_sections(record["field"])):
                missing.append(f"{record['dataclass']}.{record['field']}")
        self.assertEqual(
            missing, [],
            "fields with no subsection stating GUI, .bemt and CLI together: "
            f"{missing}")

    def test_no_field_is_cited_only_in_the_index_table(self):
        """A field named only in the generated per-tab list is not documented."""
        for record in self.records:
            with self.subTest(field=record["field"]):
                self.assertTrue(self._field_sections(record["field"]),
                                f"{record['field']} is not cited anywhere")


class TestGeneralIndex(unittest.TestCase):
    """The table of contents is generated, so it must match the headings.

    A hand-edited index is the classic way for a long document to start
    lying: a chapter is renamed, the index keeps the old name, and the
    reader concludes the section was removed.
    """

    def _builder(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_toc
        return build_toc

    def test_index_is_present(self):
        html = _html()
        self.assertIn("<!-- INDICE-GERAL -->", html)
        self.assertIn('<nav class="indice-geral"', html)

    def test_index_matches_the_headings(self):
        build_toc = self._builder()
        current = _html()
        clean = current
        i = clean.index(build_toc.MARK_START)
        j = clean.index(build_toc.MARK_END) + len(build_toc.MARK_END)
        if clean[j:j + 1] == "\n":
            j += 1
        clean = clean[:i] + clean[j:]
        clean, entries = build_toc.collect(clean)
        expected = build_toc.apply(clean, build_toc.render(entries))
        self.assertEqual(
            expected, current,
            "table of contents out of sync -- run `python tools/build_toc.py --write`")

    def test_every_link_of_the_index_resolves(self):
        html = _html()
        ids = set(re.findall(r'id="([\w-]+)"', html))
        block = re.search(r"<!-- INDICE-GERAL -->(.*?)<!-- /INDICE-GERAL -->", html, re.S)
        self.assertIsNotNone(block)
        anchors = re.findall(r'href="#([\w-]+)"', block.group(1))
        self.assertGreater(len(anchors), 50, "the index looks truncated")
        for anchor in anchors:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, ids)


if __name__ == "__main__":
    unittest.main()


class TestHelpOpensInTheTabChapter(unittest.TestCase):
    """A help popup must open the chapter of the tab it belongs to.

    The documentation is one chapter per GUI tab, so a field or a block on
    the Airfoil tab has to open somewhere inside the Airfoil chapter. When
    the physics chapters were dissolved into the page chapters, ten block
    anchors were left pointing at sections that no longer existed, and the
    field anchors had to follow the content across. Nothing about the page
    looks wrong when that happens -- the link simply lands somewhere else.
    """

    #: The fields Run Case and Run Batch SHARE. They are one quantity
    #: shown on two tabs, not two, so their help opens the Run Case
    #: description rather than a second copy of it: the four condition
    #: fields, and the three trim controls.
    CONDITION = {"mu_x", "Vz", "collective_deg", "rpm",
                 "trim_mode", "target_kind", "target_value",
                 # Sideslip and the cyclic pair are offered in the batch as
                 # fixed values only. They are the SAME quantities Run Case
                 # sets per condition, so their help opens that one
                 # description rather than a second copy of it.
                 "sideslip_deg", "cyclic_c_deg", "cyclic_s_deg"}

    #: GUI tab -> the chapter title that documents it
    TAB_CHAPTER = {
        "geometria": "Geometry",
        "aerofolio": "Airfoil",
        "config": "Config/Engine",
        "run_case": "Run Case",
        "run_batch": "Run Batch",
    }

    @classmethod
    def setUpClass(cls):
        try:
            import PyQt6  # noqa: F401
        except ModuleNotFoundError:
            raise unittest.SkipTest("PyQt6 is not installed")
        cls.html = _html()
        cls.chapters = [
            (m.start(), re.sub(r"<[^>]+>", "", m.group(1)).strip())
            for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", cls.html, re.S)
        ]
        cls.position = {m.group(1): m.start()
                        for m in re.finditer(r'id="([\w-]+)"', cls.html)}

    def _chapter_of(self, anchor: str) -> str:
        pos = self.position.get(anchor)
        self.assertIsNotNone(pos, f"anchor '{anchor}' is not in the document")
        current = None
        for p, title in self.chapters:
            if p <= pos:
                current = title
            else:
                break
        return current or ""

    def test_block_anchors_resolve(self):
        from zbemt.gui.help_blocks import BLOCK_HELP
        ids = set(self.position)
        dead = sorted({v.get("anchor") for v in BLOCK_HELP.values()
                       if v.get("anchor") not in ids})
        self.assertEqual(dead, [], f"block help points at missing anchors: {dead}")

    def test_field_help_opens_in_its_tabs_chapter(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from field_index import collect_screen_order
        from zbemt.gui.field_help import field_anchor

        for tab, fields in collect_screen_order().items():
            title = self.TAB_CHAPTER.get(tab)
            if not title:
                continue
            for field, _old in fields:
                anchor = field_anchor(field)
                if anchor is None:
                    continue
                accepted = [title]
                # Run Batch sweeps the very same four condition fields that
                # Run Case sets one at a time. They are one quantity, not
                # two, so their help opens the Run Case description rather
                # than a second copy of it.
                if tab == "run_batch" and field in self.CONDITION:
                    accepted.append("Run Case")
                with self.subTest(tab=tab, field=field):
                    self.assertTrue(
                        any(t in self._chapter_of(anchor) for t in accepted),
                        f"{field} is on the {tab} tab but its help opens "
                        f"'{self._chapter_of(anchor)}'")
