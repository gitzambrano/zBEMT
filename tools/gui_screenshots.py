"""Regenerates the GUI screenshots used by ``docs/documentation.html``.

Each chapter of the field reference opens with a picture of the tab it
documents, so the reader can match the list of fields against the page in
front of them. Those pictures are GENERATED, never pasted: a hand-made
screenshot goes stale the first time a field moves, and nothing detects it.

Rendering is headless (``QT_QPA_PLATFORM=offscreen`` + ``QWidget.grab()``),
so this runs in CI and on a machine with no display, exactly like the GUI
tests.

The Run Case tab is captured TWICE, in rotor and in propeller mode: that is
the one page whose field labels rotate with the mode, and showing only one of
them would document half the behaviour.

    python tools/gui_screenshots.py             # writes docs/img/gui/
    python tools/gui_screenshots.py --check     # fails if any is missing
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Zero-argument run writes the files (the IDE "Run" button).
DEFAULT_CHECK_ONLY = False

DESTINO = RAIZ / "docs" / "img" / "gui"

#: The project every screenshot is taken from, so the numbers on screen are
#: the ones the documentation quotes elsewhere.
PROJETO = RAIZ / "projects" / "starter_rotor"

#: Window size. Wide enough that no field is clipped or scrolled out of
#: view -- a screenshot with a cut-off field documents the wrong thing.
LARGURA, ALTURA = 1500, 1000

#: (file, tab index, propeller mode?) -- the tab order of the QTabWidget.
CAPTURAS = [
    ("project.png",              0, False),
    ("geometry.png",             1, False),
    ("airfoil.png",              2, False),
    ("config.png",               3, False),
    ("run-case-rotor.png",       4, False),
    ("run-case-propeller.png",   4, True),
    ("run-batch.png",            5, False),
    ("results.png",              6, False),
]


#: Where to look for fonts when the offscreen plugin ships without a font
#: backend. Qt's basic font database reads ``QT_QPA_FONTDIR``; without it
#: every label renders as tofu boxes and the screenshots are worthless while
#: still looking structurally correct -- a silent failure, so this is checked
#: explicitly in `gerar` rather than hoped for.
DIRETORIOS_DE_FONTE = (
    r"C:\Windows\Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/System/Library/Fonts",
)


def _garantir_fontes() -> None:
    """Points Qt at a font directory. Must run BEFORE the QApplication."""
    if os.environ.get("QT_QPA_FONTDIR"):
        return
    for caminho in DIRETORIOS_DE_FONTE:
        if Path(caminho).is_dir():
            os.environ["QT_QPA_FONTDIR"] = caminho
            return


def _assentar(app, ciclos: int = 30) -> None:
    """Lets Qt finish laying out before anything is grabbed."""
    for _ in range(ciclos):
        app.processEvents()


#: Blank space left below the last widget, in pixels.
MARGEM = 12


def _recortar(pixmap, aba):
    """Trims the empty area below the last widget.

    A tab sized for a 1000 px window but whose fields end at 450 px yields a
    figure that is more than half blank, which wastes the width the page can
    give it. Cropping to the content keeps the fields legible when the image
    is scaled to the text column.
    """
    from PyQt6.QtWidgets import QWidget

    # Only LEAF widgets: the containers (scroll areas, group boxes, the tab's
    # own panel) are stretched to the full window height by the layout, so
    # measuring them would always return the uncropped height.
    fundo = 0
    for filho in aba.findChildren(QWidget):
        if not filho.isVisible() or filho.findChildren(QWidget):
            continue
        canto = filho.mapTo(aba, filho.rect().bottomRight())
        fundo = max(fundo, canto.y())
    altura = min(pixmap.height(), fundo + MARGEM)
    if altura <= 0:
        return pixmap
    return pixmap.copy(0, 0, pixmap.width(), altura)


def gerar(destino: Path = DESTINO) -> list:
    """Writes every screenshot. Returns the paths written."""
    _garantir_fontes()
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    if not QFontDatabase.families():
        raise SystemExit(
            "gui_screenshots: Qt has no fonts, every label would render as "
            "empty boxes. Set QT_QPA_FONTDIR to a directory of .ttf files "
            f"(tried: {', '.join(DIRETORIOS_DE_FONTE)}).")

    from zbemt import api
    from zbemt.gui import app as gui

    destino.mkdir(parents=True, exist_ok=True)
    janela = gui.MainWindow()
    janela.resize(LARGURA, ALTURA)
    janela.show()
    _assentar(app)

    escritos = []
    for arquivo, indice, helice in CAPTURAS:
        projeto = api.open_project(str(PROJETO))
        # The mode is a config field; flipping it is what makes the Run Case
        # labels rotate (see zbemt/nomenclature.py).
        projeto.config["is_propeller"] = helice
        janela.state.set_project(projeto)
        janela.tabs.setCurrentIndex(indice)
        _assentar(app)

        alvo = destino / arquivo
        aba = janela.tabs.widget(indice)
        _recortar(aba.grab(), aba).save(str(alvo))
        if not alvo.exists() or alvo.stat().st_size == 0:
            raise SystemExit(f"gui_screenshots: failed to write {alvo}")
        escritos.append(alvo)
        print(f"  {arquivo:<26} {alvo.stat().st_size // 1024:>5} KB")

    janela.close()
    return escritos


def conferir(destino: Path = DESTINO) -> int:
    faltando = [f for f, _i, _h in CAPTURAS if not (destino / f).exists()]
    if faltando:
        print("missing screenshots: " + ", ".join(faltando))
        print("run: python tools/gui_screenshots.py")
        return 1
    print(f"{len(CAPTURAS)} screenshots present in {destino}")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if DEFAULT_CHECK_ONLY or "--check" in argv:
        return conferir()
    gerar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
