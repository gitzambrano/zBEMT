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
    python tools/field_index.py --write    # injects into the documentation

`tests/test_documentation.py` checks that the published index still
matches the on-screen order.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Run with no arguments (e.g. the IDE "Run" button) uses dry-run mode (show without writing).
# Use --write to actually inject into the documentation.
DEFAULT_WRITE_MODE = False

MARK_START = "<!-- INDICE-DE-CAMPOS:{tab} -->"
MARK_END = "<!-- /INDICE-DE-CAMPOS:{tab} -->"

#: tab -> (index in the QTabWidget, id of the chapter that documents it)
TABS = {
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
    #
    # The Geometry Designer window: absent for a different reason. It is a
    # separate Tools-menu window, not one of the seven tabs of the main
    # window's QTabWidget, so there is no tab index to walk here.
    "geometria": (1, "cap-2"),
    "aerofolio": (2, "cap-3"),
    "config": (3, "cap-4"),
    "run_case": (4, "cap-5"),
    "run_batch": (5, "cap-6"),
}


def collect_screen_order() -> dict:
    """{tab: [(field, anchor), ...]} in visual order (top->bottom, left->right)."""
    from PyQt6.QtWidgets import QApplication, QWidget

    # QApplication must exist before any `zbemt.gui.*` import: that is what
    # sets matplotlib's backend to QtAgg, and matplotlib picks the wrong Qt
    # platform plugin if no QApplication is running yet.
    app = QApplication.instance() or QApplication([])

    from zbemt.gui import app as gui
    from zbemt.gui.field_help import _NAME_IN_TOOLTIP, field_map

    label_map = field_map()
    window = gui.MainWindow()
    window.resize(1500, 1000)
    window.show()
    for _ in range(30):
        app.processEvents()

    order = {}
    for tab_name, (index, _chapter) in TABS.items():
        window.tabs.setCurrentIndex(index)
        for _ in range(20):
            app.processEvents()
        tab = window.tabs.widget(index)
        positions = {}
        for widget in tab.findChildren(QWidget):
            match = _NAME_IN_TOOLTIP.match(widget.toolTip() or "")
            if not match:
                continue
            field_name = match.group(1).split(".")[-1]
            if field_name not in label_map or field_name in positions:
                continue
            # A HIDDEN widget has no position: `mapTo` returns (0, 0)
            # for it, so every hidden field sorted to the very top and
            # the one visible field of the block sorted last. The
            # Geometry block is the case that showed it -- `flap_model`
            # is the FIRST row on screen and the eighteen rows it
            # governs are hidden until it is set, so the published order
            # put `flap_model` at the END of a list that claims to be
            # "in the order they appear on screen".
            #
            # A field that is not on screen has no screen order, so it
            # is placed by its position in the form instead, right after
            # the field that reveals it: `mapTo` on its PARENT still
            # describes where the block sits.
            if widget.isVisibleTo(tab):
                point = widget.mapTo(tab, widget.rect().topLeft())
                positions[field_name] = (0, point.y(), point.x())
            else:
                parent = widget.parentWidget() or tab
                anchor = parent.mapTo(tab, parent.rect().topLeft())
                positions[field_name] = (1, anchor.y(), anchor.x())
        ordered = sorted(positions.items(), key=lambda kv: kv[1])
        order[tab_name] = [(name, label_map[name]) for name, _ in ordered]
    return order


#: `<h2 id="x">3.1 Title</h2>` and also the form `<a id="x"></a>` on its own
#: line BEFORE the heading -- seven chapters of the documentation use the
#: latter, and a regex that only looked at the heading's attribute would
#: miss them.
_HEADING = re.compile(
    r'<a\s+id="(?P<free_anchor>[^"]+)"[^>]*>\s*</a>\s*'
    r'|<h(?P<level>[1-6])(?P<attrs>[^>]*)>\s*(?P<text>[^<]*)',
    re.IGNORECASE)
_LEADING_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s")


def section_numbers(html: str) -> dict:
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
    numbers: dict = {}
    pending: list = []
    for m in _HEADING.finditer(html):
        if m.group("free_anchor"):
            pending.append(m.group("free_anchor"))
            continue
        number = _LEADING_NUMBER.match(m.group("text") or "")
        ids = re.findall(r'id="([^"]+)"', m.group("attrs") or "")
        # loose anchors immediately before belong to THIS heading
        for anchor in pending + ids:
            if number:
                numbers[anchor] = number.group(1)
        pending = []
    return numbers


def build_html(tab_name: str, fields: list, numbers: dict | None = None) -> str:
    if not fields:
        return ""
    numbers = numbers or {}

    def label(anchor: str) -> str:
        # A missing heading is reported by its anchor so the inventory remains
        # inspectable instead of silently dropping the field.
        return numbers.get(anchor, anchor)

    items = "".join(
        f'<li><code>{name}</code> &rarr; '
        f'<a href="#{anchor}">{label(anchor)}</a></li>'
        for name, anchor in fields)
    return (
        f'<div class="boxed">\n'
        f"<b>Fields in this tab, in the order they appear on screen</b> "
        f"({len(fields)}). The sections below are self-contained and use the "
        f"same explanations as the field Help in the window.\n"
        f'<ol class="indice-de-campos">{items}</ol>\n'
        f"</div>"
    )


def inject(html: str, tab_name: str, block: str) -> str:
    start = MARK_START.format(tab=tab_name)
    end = MARK_END.format(tab=tab_name)
    new_block = f"{start}\n{block}\n{end}"
    if start in html:
        return re.sub(re.escape(start) + r".*?" + re.escape(end),
                      lambda _m: new_block, html, flags=re.S)
    # first time: right after the tab's chapter <h2>
    _index, chapter = TABS[tab_name]
    pattern = re.compile(rf'(<h2 id="{re.escape(chapter)}">.*?</h2>\n)')
    found = pattern.search(html)
    if not found:
        raise SystemExit(f"chapter {chapter} was not found in the documentation")
    return html[:found.end()] + new_block + "\n" + html[found.end():]


def main(write: bool) -> int:
    order = collect_screen_order()
    doc = ROOT / "docs" / "documentation.html"
    html = doc.read_text(encoding="utf-8")
    # The numbers come from the documentation's HEADINGS, not from the
    # anchor name -- see `section_numbers`. Read BEFORE the loop: injecting
    # does not change any heading, so a single read is enough and there is
    # no risk of one tab's index seeing one numbering and the next tab's
    # index seeing another.
    numbers = section_numbers(html)
    for tab_name, fields in order.items():
        print(f"{tab_name:<12} {len(fields)} fields")
        if fields:
            html = inject(html, tab_name, build_html(tab_name, fields, numbers))
    if write:
        doc.write_text(html, encoding="utf-8")
        print("documentation updated")
    else:
        print("(use --write to inject the index into the documentation)")
    return 0


if __name__ == "__main__":
    # If no argument was given, uses DEFAULT_WRITE_MODE; CLI args still override.
    write = DEFAULT_WRITE_MODE if len(sys.argv) == 1 else ("--write" in sys.argv)
    raise SystemExit(main(write))
