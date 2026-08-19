"""Regenerates the table of contents at the top of ``docs/documentation.html``.

The document is long enough that a reader who knows what they are looking for
should not have to scroll to find it. The index is DERIVED from the headings
actually present, so it cannot fall out of step with the document the way a
hand-maintained list would -- the same reason ``tools/field_index.py`` derives
the per-tab field lists from the running GUI.

Two levels: chapters (``<h2>``) and their sections (``<h3>``). Deeper
headings are deliberately left out; at four levels the index stops being
easier to scan than the document.

A heading with no anchor of its own, and none immediately before it, gets a
slug id injected so it can be linked. That is the only edit made outside the
index block itself.

    python tools/build_toc.py             # shows what would change
    python tools/build_toc.py --escrever  # writes it
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DOC = RAIZ / "docs" / "documentation.html"

#: Zero-argument run is a dry run, like tools/field_index.py.
DEFAULT_WRITE_MODE = False

MARCA_INICIO = "<!-- INDICE-GERAL -->"
MARCA_FIM = "<!-- /INDICE-GERAL -->"

#: A heading, with its own id when it has one.
_CABECALHO = re.compile(r'<h([23])(?:\s+id="([\w-]+)")?[^>]*>(.*?)</h\1>', re.S)

#: `<a id="x"></a>` used as an anchor immediately before a heading.
_ANCORA_SOLTA = re.compile(r'<a id="([\w-]+)"></a>')


def _texto(bruto: str) -> str:
    """Heading text with the markup removed, entities left readable."""
    limpo = re.sub(r"<[^>]+>", "", bruto)
    limpo = limpo.replace("&mdash;", "—").replace("&rarr;", "→")
    limpo = limpo.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return " ".join(limpo.split())


def _slug(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    base = re.sub(r"[^\w\s-]", "", base).strip().lower()
    return "sec-" + re.sub(r"[\s_]+", "-", base)[:48].strip("-")


def coletar(html: str):
    """[(level, anchor, text)] in document order, injecting ids when needed.

    Returns the (possibly edited) html alongside the entries, because giving
    an unanchored heading an id is part of making the index linkable.
    """
    entradas = []
    usados = set(re.findall(r'id="([\w-]+)"', html))
    saida = []
    fim_anterior = 0

    for m in _CABECALHO.finditer(html):
        nivel, ancora_propria, bruto = int(m.group(1)), m.group(2), m.group(3)
        texto = _texto(bruto)
        if not texto:
            continue

        ancora = ancora_propria
        if not ancora:
            # `<a id="..."></a>` sitting just above the heading, possibly
            # several of them (the document keeps old anchors as aliases).
            antes = html[max(0, m.start() - 260):m.start()]
            soltas = _ANCORA_SOLTA.findall(antes)
            if soltas and not _texto(_ANCORA_SOLTA.sub("", antes)):
                ancora = soltas[-1]

        if not ancora:
            ancora = _slug(texto)
            n = 2
            while ancora in usados:
                ancora, n = f"{_slug(texto)}-{n}", n + 1
            usados.add(ancora)
            saida.append(html[fim_anterior:m.start()])
            saida.append(f'<h{nivel} id="{ancora}">{bruto}</h{nivel}>')
            fim_anterior = m.end()

        entradas.append((nivel, ancora, texto))

    saida.append(html[fim_anterior:])
    return "".join(saida), entradas


def renderizar(entradas) -> str:
    linhas = [MARCA_INICIO, '<nav class="indice-geral" aria-label="Table of contents">',
              '<div class="indice-titulo">Contents</div>', "<ol>"]
    aberto = False
    for nivel, ancora, texto in entradas:
        if nivel == 2:
            if aberto:
                linhas.append("</ol></li>")
                aberto = False
            linhas.append(f'<li><a href="#{ancora}">{texto}</a>')
            linhas.append("<ol>")
            aberto = True
        else:
            linhas.append(f'<li><a href="#{ancora}">{texto}</a></li>')
    if aberto:
        linhas.append("</ol></li>")
    linhas += ["</ol>", "</nav>", MARCA_FIM]
    return "\n".join(linhas)


def aplicar(html: str, bloco: str) -> str:
    if MARCA_INICIO in html:
        inicio = html.index(MARCA_INICIO)
        fim = html.index(MARCA_FIM) + len(MARCA_FIM)
        return html[:inicio] + bloco + html[fim:]
    # The index goes after the title block and before the first chapter.
    # Anchoring on the first `<hr>` was wrong: inserting a chapter consumed
    # the rule that followed the title, and the index silently drifted to
    # the end of chapter 1. The first `<h2>` cannot move.
    #
    # The spacing is normalised rather than preserved, so that
    # strip-then-reinsert always lands on the same bytes; otherwise the
    # round trip differs by a newline and the sync test fails forever.
    corte = html.index("<h2")
    return html[:corte].rstrip() + "\n\n" + bloco + "\n\n" + html[corte:]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    escrever = DEFAULT_WRITE_MODE or "--escrever" in argv

    original = DOC.read_text(encoding="utf-8")
    # Strip any existing index BEFORE scanning, so the block never indexes
    # itself and `aplicar` always inserts into a clean document.
    html = original
    if MARCA_INICIO in html:
        i = html.index(MARCA_INICIO)
        j = html.index(MARCA_FIM) + len(MARCA_FIM)
        # Consume the newline `aplicar` adds after the block too, or a run
        # would insert one more each time and never reach a fixed point.
        if html[j:j + 1] == "\n":
            j += 1
        html = html[:i] + html[j:]
    html, entradas = coletar(html)
    novo = aplicar(html, renderizar(entradas))

    capitulos = sum(1 for n, _, _ in entradas if n == 2)
    print(f"{capitulos} chapters, {len(entradas) - capitulos} sections")
    if novo == original:
        print("index already up to date")
        return 0
    if not escrever:
        print("(use --escrever to write it)")
        return 0
    DOC.write_text(novo, encoding="utf-8")
    print("index written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
