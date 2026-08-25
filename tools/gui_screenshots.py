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
them would document half the behaviour. The Geometry Designer window (Tools
button) is captured separately, after the tabs: it lives outside the QTabWidget.

    python tools/gui_screenshots.py             # writes docs/img/gui/
    python tools/gui_screenshots.py --check     # fails if any is missing
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Zero-argument run writes the files (the IDE "Run" button).
DEFAULT_CHECK_ONLY = False

OUTPUT_DIR = ROOT / "docs" / "img" / "gui"

#: The project every screenshot is taken from, so the numbers on screen are
#: the ones the documentation quotes elsewhere.
PROJECT = ROOT / "projects" / "starter_rotor"

#: Window size. Wide enough that no field is clipped or scrolled out of
#: view -- a screenshot with a cut-off field documents the wrong thing.
WIDTH, HEIGHT = 1500, 1000

#: (file, tab index, propeller mode?) -- the tab order of the QTabWidget.
SHOTS = [
    ("project.png",              0, False),
    ("geometry.png",             1, False),
    ("airfoil.png",              2, False),
    ("config.png",               3, False),
    ("run-case-rotor.png",       4, False),
    ("run-case-propeller.png",   4, True),
    ("run-batch.png",            5, False),
    ("results.png",              6, False),
]

#: The Geometry Designer window (Tools button), captured in addition to the
#: tabs above -- it lives outside the QTabWidget, so it has no index.
DESIGNER_SHOT = "designer.png"

#: The Design Optimization window (Tools button, SC-13), for the same
#: reason: a dedicated window outside the tab flow.
OPTIMIZER_SHOT = "optimizer.png"


#: Where to look for fonts when the offscreen plugin ships without a font
#: backend. Qt's basic font database reads ``QT_QPA_FONTDIR``; without it
#: every label renders as tofu boxes and the screenshots are worthless while
#: still looking structurally correct -- a silent failure, so this is checked
#: explicitly in `generate` rather than hoped for.
FONT_DIRS = (
    r"C:\Windows\Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/System/Library/Fonts",
)


def _ensure_fonts() -> None:
    """Points Qt at a font directory. Must run BEFORE the QApplication."""
    if os.environ.get("QT_QPA_FONTDIR"):
        return
    for path in FONT_DIRS:
        if Path(path).is_dir():
            os.environ["QT_QPA_FONTDIR"] = path
            return


def _settle(app, cycles: int = 30) -> None:
    """Lets Qt finish laying out before anything is grabbed."""
    for _ in range(cycles):
        app.processEvents()


#: Blank space left below the last widget, in pixels.
MARGIN = 12


def _crop(pixmap, tab):
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
    bottom_edge = 0
    for child in tab.findChildren(QWidget):
        if not child.isVisible() or child.findChildren(QWidget):
            continue
        corner = child.mapTo(tab, child.rect().bottomRight())
        bottom_edge = max(bottom_edge, corner.y())
    crop_height = min(pixmap.height(), bottom_edge + MARGIN)
    if crop_height <= 0:
        return pixmap
    return pixmap.copy(0, 0, pixmap.width(), crop_height)


def generate(destination: Path = OUTPUT_DIR) -> list:
    """Writes every screenshot. Returns the paths written."""
    _ensure_fonts()
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    if not QFontDatabase.families():
        raise SystemExit(
            "gui_screenshots: Qt has no fonts, every label would render as "
            "empty boxes. Set QT_QPA_FONTDIR to a directory of .ttf files "
            f"(tried: {', '.join(FONT_DIRS)}).")

    from zbemt import api
    from zbemt.gui import app as gui

    destination.mkdir(parents=True, exist_ok=True)
    window = gui.MainWindow()
    window.resize(WIDTH, HEIGHT)
    window.show()
    _settle(app)

    written = []
    for filename, index, is_propeller in SHOTS:
        project = api.open_project(str(PROJECT))
        # The mode is a config field; flipping it is what makes the Run Case
        # labels rotate (see zbemt/nomenclature.py).
        project.config["is_propeller"] = is_propeller
        window.state.set_project(project)
        window.tabs.setCurrentIndex(index)
        _settle(app)

        target = destination / filename
        tab = window.tabs.widget(index)
        _crop(tab.grab(), tab).save(str(target))
        if not target.exists() or target.stat().st_size == 0:
            raise SystemExit(f"gui_screenshots: failed to write {target}")
        written.append(target)
        print(f"  {filename:<26} {target.stat().st_size // 1024:>5} KB")

    written.append(_capture_designer(app, window,
                                     api.open_project(str(PROJECT)),
                                     destination))
    written.append(_capture_optimizer(app, window,
                                       api.open_project(str(PROJECT)),
                                       destination))

    window.close()
    return written


def _capture_designer(app, window, project, destination: Path) -> Path:
    """Captures the Geometry Designer window (Tools button > Geometry Designer).

    MainWindow builds it eagerly and parents it to itself, so opening it
    repeats exactly what ``MainWindow.open_geometry_designer`` does.
    """
    window.state.set_project(project)
    designer = window.geometry_designer
    designer.resize(WIDTH, HEIGHT)
    designer.show()
    designer.raise_()
    designer.activateWindow()
    _settle(app)

    target = destination / DESIGNER_SHOT
    _crop(designer.grab(), designer).save(str(target))
    if not target.exists() or target.stat().st_size == 0:
        raise SystemExit(f"gui_screenshots: failed to write {target}")
    print(f"  {DESIGNER_SHOT:<26} {target.stat().st_size // 1024:>5} KB")
    return target


def _capture_optimizer(app, window, project, destination: Path) -> Path:
    """Captures the Design Optimization window (Tools button > Design
    Optimization), the same eager-construction path as the Designer's."""
    window.state.set_project(project)
    optimizer = window.optimizer_window
    optimizer.resize(WIDTH, HEIGHT)
    optimizer.show()
    optimizer.raise_()
    optimizer.activateWindow()
    _settle(app)

    target = destination / OPTIMIZER_SHOT
    _crop(optimizer.grab(), optimizer).save(str(target))
    if not target.exists() or target.stat().st_size == 0:
        raise SystemExit(f"gui_screenshots: failed to write {target}")
    print(f"  {OPTIMIZER_SHOT:<26} {target.stat().st_size // 1024:>5} KB")
    return target


def check_existing(destination: Path = OUTPUT_DIR) -> int:
    names = [f for f, _i, _h in SHOTS] + [DESIGNER_SHOT, OPTIMIZER_SHOT]
    missing = [f for f in names if not (destination / f).exists()]
    if missing:
        print("missing screenshots: " + ", ".join(missing))
        print("run: python tools/gui_screenshots.py")
        return 1
    print(f"{len(names)} screenshots present in {destination}")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if DEFAULT_CHECK_ONLY or "--check" in argv:
        return check_existing()
    generate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
