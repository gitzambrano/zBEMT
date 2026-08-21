"""Generates, for each tab, the index of fields IN THE ORDER THEY APPEAR ON SCREEN.

The documentation already had a section per field, grouped by tab. What
was missing was the bridge in the direction the user travels: they are
looking at the third box from the top in the Config/Engine tab and want
the explanation for that -- they don't want to search a summary organized
by the logic of the physics.

The index is DERIVED from the real GUI: it opens the window, walks the
widgets and orders them by position on screen. It is not a hand-written
list, which would drift out of sync the first time a field moved.

    python tools/field_index.py            # shows what would change
    python tools/field_index.py --escrever # injects into the documentation

`tests/test_documentation.py` checks that the published index still
matches the on-screen order.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Run with no arguments (e.g. the IDE "Run" button) uses dry-run mode (show without writing).
# Use --escrever to actually inject into the documentation.
DEFAULT_WRITE_MODE = False

MARCA_INICIO = "<!-- INDICE-DE-CAMPOS:{aba} -->"
MARCA_FIM = "<!-- /INDICE-DE-CAMPOS:{aba} -->"

#: tab -> (index in the QTabWidget, id of the chapter that documents it)
ABAS = {
    # Two tabs are deliberately absent.
    #
    # Results: its controls select a view of results that already exist, not a
    # field of the project, so there is no field list to generate.
    #
    # Project: it carries `is_propeller`, which resolves correctly, and `name`,
    # which does not. Two different fields are called `name` -- the project's,
    # in `meta.bemt`, and the airfoil section's -- and the field-to-section map
    # is keyed on the bare name, so the project's would be listed against the
    # airfoil's section. A generated index that sends the reader to the wrong
    # chapter is worse than no index, so this tab is left out until the map can
    # tell the two apart.
    "geometria": (1, "cap-2"),
    "aerofolio": (2, "cap-3"),
    "config": (3, "cap-4"),
    "run_case": (4, "cap-5"),
    "run_batch": (5, "cap-6"),
}


def coletar_ordem_da_tela() -> dict:
    """{tab: [(field, anchor), ...]} in visual order (top->bottom, left->right)."""
    from PyQt6.QtWidgets import QApplication, QWidget

    # QApplication must exist before any `zbemt.gui.*` import: that is what
    # sets matplotlib's backend to QtAgg, and matplotlib picks the wrong Qt
    # platform plugin if no QApplication is running yet.
    app = QApplication.instance() or QApplication([])

    from zbemt.gui import app as gui
    from zbemt.gui.field_help import _NOME_NO_TOOLTIP, mapa_de_campos

    mapa = mapa_de_campos()
    janela = gui.MainWindow()
    janela.resize(1500, 1000)
    janela.show()
    for _ in range(30):
        app.processEvents()

    resultado = {}
    for nome_aba, (indice, _cap) in ABAS.items():
        janela.tabs.setCurrentIndex(indice)
        for _ in range(20):
            app.processEvents()
        aba = janela.tabs.widget(indice)
        posicoes = {}
        for wd in aba.findChildren(QWidget):
            achado = _NOME_NO_TOOLTIP.match(wd.toolTip() or "")
            if not achado:
                continue
            campo = achado.group(1).split(".")[-1]
            if campo not in mapa or campo in posicoes:
                continue
            ponto = wd.mapTo(aba, wd.rect().topLeft())
            posicoes[campo] = (ponto.y(), ponto.x())
        ordenados = sorted(posicoes.items(), key=lambda kv: kv[1])
        resultado[nome_aba] = [(campo, mapa[campo]) for campo, _ in ordenados]
    return resultado


#: `<h2 id="x">3.1 Title</h2>` and also the form `<a id="x"></a>` on its own
#: line BEFORE the heading -- seven chapters of the documentation use the
#: latter, and a regex that only looked at the heading's attribute would
#: miss them.
_HEADING = re.compile(
    r'<a\s+id="(?P<ancora_solta>[^"]+)"[^>]*>\s*</a>\s*'
    r'|<h(?P<nivel>[1-6])(?P<attrs>[^>]*)>\s*(?P<texto>[^<]*)',
    re.IGNORECASE)
_NUMERO_INICIAL = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s")


def numeros_de_secao(html: str) -> dict:
    """``{anchor id: "2.8.2.4"}`` -- the number the heading REALLY shows
    today.

    The field index used to derive the number from the anchor's own NAME
    (``cap-19-2-4`` -> "19.2.4"). The ids are frozen on purpose (the GUI's
    `field_help` points to them), so that derivation only knew how to
    reproduce the OLD numbering: after any renumbering of the
    documentation, the index went on citing sections that no longer
    exist -- and, since it generated the very text that checked it, the
    test kept passing against the wrong number.

    Resolving from the heading is what breaks that cycle: the number comes
    from where the reader reads it."""
    numeros: dict = {}
    soltas: list = []
    for m in _HEADING.finditer(html):
        if m.group("ancora_solta"):
            soltas.append(m.group("ancora_solta"))
            continue
        numero = _NUMERO_INICIAL.match(m.group("texto") or "")
        ids = re.findall(r'id="([^"]+)"', m.group("attrs") or "")
        # loose anchors immediately before belong to THIS heading
        for ancora in soltas + ids:
            if numero:
                numeros[ancora] = numero.group(1)
        soltas = []
    return numeros


def montar_html(nome_aba: str, campos: list, numeros: dict | None = None) -> str:
    if not campos:
        return ""
    numeros = numeros or {}

    def rotulo(ancora: str) -> str:
        # A missing heading is reported by its anchor so the inventory remains
        # inspectable instead of silently dropping the field.
        return numeros.get(ancora, ancora)

    itens = "".join(
        f'<li><code>{campo}</code> &rarr; '
        f'<a href="#{ancora}">{rotulo(ancora)}</a></li>'
        for campo, ancora in campos)
    return (
        f'<div class="boxed">\n'
        f"<b>Fields in this tab, in the order they appear on screen</b> "
        f"({len(campos)}). The sections below are self-contained and use the "
        f"same explanations as the field Help in the window.\n"
        f'<ol class="indice-de-campos">{itens}</ol>\n'
        f"</div>"
    )


def injetar(html: str, nome_aba: str, bloco: str) -> str:
    inicio = MARCA_INICIO.format(aba=nome_aba)
    fim = MARCA_FIM.format(aba=nome_aba)
    novo = f"{inicio}\n{bloco}\n{fim}"
    if inicio in html:
        return re.sub(re.escape(inicio) + r".*?" + re.escape(fim), lambda _m: novo,
                       html, flags=re.S)
    # first time: right after the tab's chapter <h2>
    _indice, cap = ABAS[nome_aba]
    padrao = re.compile(rf'(<h2 id="{re.escape(cap)}">.*?</h2>\n)')
    achado = padrao.search(html)
    if not achado:
        raise SystemExit(f"chapter {cap} was not found in the documentation")
    return html[:achado.end()] + novo + "\n" + html[achado.end():]


def main(escrever: bool) -> int:
    ordem = coletar_ordem_da_tela()
    doc = RAIZ / "docs" / "documentation.html"
    html = doc.read_text(encoding="utf-8")
    # The numbers come from the documentation's HEADINGS, not from the
    # anchor name -- see `numeros_de_secao`. Read BEFORE the loop: injecting
    # does not change any heading, so a single read is enough and there is
    # no risk of one tab's index seeing one numbering and the next tab's
    # index seeing another.
    numeros = numeros_de_secao(html)
    for nome_aba, campos in ordem.items():
        print(f"{nome_aba:<12} {len(campos)} fields")
        if campos:
            html = injetar(html, nome_aba, montar_html(nome_aba, campos, numeros))
    if escrever:
        doc.write_text(html, encoding="utf-8")
        print("documentation updated")
    else:
        print("(use --escrever to inject the index into the documentation)")
    return 0


if __name__ == "__main__":
    # If no argument was given, uses DEFAULT_WRITE_MODE; CLI args still override.
    escrever = DEFAULT_WRITE_MODE if len(sys.argv) == 1 else ("--escrever" in sys.argv)
    raise SystemExit(main(escrever))
