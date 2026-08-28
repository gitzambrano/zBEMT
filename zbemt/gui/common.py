"""Infrastructure shared by the GUI tabs.

``AppState`` (the single state object, with signals), the matplotlib canvases,
the dialog helpers and the pre-execution guards. Knows nothing about any tab:
the dependency only points from the tabs to here, never the other way around.
"""


from __future__ import annotations

import importlib
import os
import shutil
import traceback
from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox, QWidget, QVBoxLayout, QMessageBox,
    QDialog, QLabel, QPushButton, QFileDialog, QHBoxLayout,
    QFrame, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, QEvent, QObject, QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices

#: True whenever Qt is running under the offscreen platform plugin (set by
#: `tests/conftest.py` for every headless test run). QtWebEngineWidgets is
#: known to hard-crash the whole process -- not raise a Python exception --
#: the moment it is imported under this platform on some Qt/Chromium
#: builds, before a single `QWebEngineView` is ever constructed (a step
#: below the already-documented instantiation-time crash on
#: `PlotlyCanvasHost`). There is nothing to catch: skip the import
#: entirely rather than let it take the interpreter down.
_HEADLESS = os.environ.get("QT_QPA_PLATFORM") == "offscreen"

if _HEADLESS:
    QWebEngineView = None
    HAS_INTERACTIVE_PLOTS = False
else:
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        HAS_INTERACTIVE_PLOTS = True
    except ImportError:
        QWebEngineView = None
        HAS_INTERACTIVE_PLOTS = False

# This module is imported by ALL other GUI modules, so it is the right
# place to fix the matplotlib backend: it must happen before any
# `FigureCanvasQTAgg` exists. Headless test runs already set the Agg
# backend in `tests/conftest.py` (QtAgg needs a real/offscreen Qt
# application, which `matplotlib.use` does not always detect correctly
# once QT_QPA_PLATFORM=offscreen); respect that instead of overriding it.
import matplotlib
if not _HEADLESS:
    matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from .. import api
from .. import nomenclature
from .. import paths
from ..external_solvers import (
    known_xfoil_location_names, resolve_xfoil_binary, XFOIL_SETTINGS_KEY,
)
from ..models import Project, ResultEntry


#: `docs/`, `projects/` and `outputs/` do NOT live inside the package --
#: they are user data and documentation, not code. `zbemt.paths` resolves
#: each one depending on whether zBEMT is running from the repository
#: (clone / `pip install -e .`) or actually installed, in which case
#: `parents[2]` would point inside `site-packages`.
PROJECTS_ROOT = str(paths.projects_root())


def in_scroll_area(page: QWidget, minimum_px: int = 120) -> QScrollArea:
    """Wraps a page so a window built from it can be made SMALLER.

    A tool window whose pages state a large minimum size cannot be
    resized below it: Qt honours the minimum, the content runs past the
    screen edge, and nothing scrolls to it. The Stability window asked
    for 1490 pixels of width, which a 1366-wide laptop cannot give.

    `setWidgetResizable(True)` keeps the page stretched to the viewport
    whenever there IS room, so on a large screen the layout is exactly
    what it was; the scroll bars appear only once the viewport is
    smaller than what the page needs.

    `minimum_px` is the floor the SCROLL AREA itself keeps, so the
    viewport never collapses to nothing and leaves the user with two
    scroll bars around an empty square.
    """
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(page)
    area.setMinimumSize(minimum_px, minimum_px)
    return area


def parse_list_reporting(text: str) -> tuple[list[float], list[str]]:
    """Splits a comma-separated list into the numbers and the leftovers.

    Returns ``(values, rejected)``. A token that is not a number is NOT an
    exception: every one of these fields is read on `textChanged`, so the
    function sees each number in every half-typed state it passes through --
    "-", "0.", "1e", "1e-" -- and a partial number is the normal case, not an
    error.

    It used to raise. `float("-")` is a `ValueError`, the call happened inside
    a Qt slot, and PyQt6 aborts the process on an exception it cannot return
    across the C++ boundary. Typing the minus sign of the first disk angle
    therefore closed the whole application (`PR-11`).

    The rejected tokens are returned instead of dropped so that the paths
    which BUILD something -- generating a batch, generating a polar -- can
    refuse a list they cannot read in full, rather than quietly producing
    fewer cases than the user wrote.
    """
    values: list[float] = []
    rejected: list[str] = []
    for token in (text or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(float(token))
        except ValueError:
            rejected.append(token)
    return values, rejected


def parse_list(text: str) -> list[float]:
    """The numbers of a comma-separated list, skipping what is not one.

    For a LIVE read-out. Use `parse_list_reporting` where an unreadable
    token has to stop the action.
    """
    return parse_list_reporting(text)[0]


def symbol_to_plain_text(symbol_html: str) -> str:
    """`api.SUMMARY_SYMBOLS` stores symbols in HTML (`"C<sub>T</sub>"`,
    `"&mu;"`) intended for the report; a `QTableWidgetItem` does not
    render HTML, so "&mu;" would appear literally instead of "μ".
    Converts subscript to a `_` suffix and decodes HTML entities into
    the actual Unicode character. Shared between `ResultsTab` (column
    header) and `RunCaseTab` (row label) -- same conversion, a single
    implementation."""
    import html
    text = symbol_html.replace("<sub>", "_").replace("</sub>", "")
    return html.unescape(text)


def describe_case_settings(summary: dict) -> str:
    """Short string with the parameters that define a case ("μ_x=0.3,
    θ₀=8°, rpm=600"), so that a history entry (Results tab) states by
    itself what was run, instead of a generic label like "case μ_x=0.3"
    (which could already be confused between two cases with the same
    μ_x but different collective/rpm). Reads directly from
    `Results.summary` -- the same keys `api.SUMMARY_SYMBOLS`/the report
    use, so the description never diverges from what the report would
    show for the same case.

    The symbols are the ones from the final nomenclature (`μ_x`,
    `V_z`), never `μ` or `V` without an index: the same label appears
    in both modes and without the index it is impossible to tell which
    component it is."""
    parts = []
    if "mu_x" in summary:
        parts.append(f"μ_x={summary['mu_x']:.3g}")
    if "collective_deg" in summary:
        parts.append(f"θ₀={summary['collective_deg']:.3g}°")
    if "rpm" in summary and summary["rpm"] is not None:
        parts.append(f"rpm={summary['rpm']:.0f}")
    vz_value = summary.get("Vz")
    if vz_value is not None and abs(vz_value) > 1e-9:
        parts.append(f"V_z={vz_value:.3g}")
    return ", ".join(parts) if parts else "case"


def describe_batch_settings(results_list: list) -> str:
    """Same idea as `describe_case_settings`, for a batch: for each key
    quantity, shows the RANGE if it varies between cases ("μ_x:
    0→0.4, 9 cases") or the single value if it is constant across the
    whole batch ("θ₀=8°") -- tells at a glance what the sweep axis
    was without having to open the case queue."""
    if not results_list:
        return "batch"
    parts = []
    n = len(results_list)
    for key, symbol, fmt, suffix in (
        ("mu_x", "μ_x", "{:.3g}", ""),
        ("collective_deg", "θ₀", "{:.3g}", "°"),
        ("rpm", "rpm", "{:.0f}", ""),
        ("Vz", "V_z", "{:.3g}", ""),
    ):
        values = [r.summary[key] for r in results_list
                   if key in r.summary and r.summary[key] is not None]
        if not values:
            continue
        if key == "Vz" and all(abs(v) < 1e-9 for v in values):
            continue
        lo, hi = min(values), max(values)
        if hi - lo > 1e-9 * max(1.0, abs(hi)):
            parts.append(f"{symbol}: {fmt.format(lo)}{suffix}→{fmt.format(hi)}{suffix}")
        else:
            parts.append(f"{symbol}={fmt.format(lo)}{suffix}")
    parts.append(f"{n} case(s)")
    return ", ".join(parts)


# =============================================================================
# State shared between tabs
# =============================================================================

class AppState(QObject):
    project_changed = pyqtSignal()
    geometry_changed = pyqtSignal()
    airfoil_changed = pyqtSignal()
    config_changed = pyqtSignal()
    results_changed = pyqtSignal()
    history_changed = pyqtSignal()   # docs/plano_v3.md Part 4.1 -- Results hub
    mode_changed = pyqtSignal()   # rotor <-> propeller (docs/plano.md Section 2)

    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.last_results = None          # Results | list[Results] | None
        self.last_maps: dict | None = None
        # --- results history for this session (Part 4.1) ------------------
        # Unlike `last_results` above (overwritten by EVERY Run Case/Run
        # Batch, used only by each tab's local "Export" button),
        # `results_history` is a list that only GROWS (append), consumed by
        # `ResultsTab` (multi-selection history). "For this session": cleared
        # in `set_project` (switch/close project) -- see docs/plano_v3.md
        # Section 4.4, computed results are expensive and are not
        # "pre-definition" data.
        self.results_history: list = []   # list[models.ResultEntry]
        self._history_counter = 0
        # Q7: "Apply to project" only writes to memory; nothing auto-saves.
        # Without this flag, closing the window would silently discard
        # work. Set by the `notify_*` methods (called by a tab when it
        # applies) and cleared by `mark_saved`/`set_project`.
        self.unsaved = False

    def set_project(self, project: Project):
        self.project = project
        self.unsaved = False
        self.clear_history()
        self.project_changed.emit()
        self.geometry_changed.emit()
        self.airfoil_changed.emit()
        self.config_changed.emit()
        self.mode_changed.emit()

    def add_history_entry(self, kind: str, label: str, results) -> "ResultEntry":
        """Records a new run (Run Case or Run Batch) in the session
        history -- NEVER replaces an existing entry (docs/plano_v3.md
        Part 4.1). ``kind``: "case" (``results`` is a single ``Results``)
        or "batch" (``results`` is ``list[Results]``)."""
        import time
        self._history_counter += 1
        entry = ResultEntry(
            id=f"r{self._history_counter}", label=label, kind=kind,
            results=results, timestamp=time.strftime("%H:%M:%S"),
        )
        self.results_history.append(entry)
        self.history_changed.emit()
        return entry

    def clear_history(self):
        self.results_history = []
        self._history_counter = 0
        self.history_changed.emit()

    def remove_history_entry(self, entry_id: str) -> bool:
        """Removes ONE entry from the history (unlike `clear_history`,
        which clears everything) -- returns True if something was
        removed. `entry_id` is the `ResultEntry.id` (for example `"r3"`), the
        same value stored in `Qt.ItemDataRole.UserRole` of the list item
        in `ResultsTab`."""
        antes = len(self.results_history)
        self.results_history = [e for e in self.results_history if e.id != entry_id]
        removeu = len(self.results_history) < antes
        if removeu:
            self.history_changed.emit()
        return removeu

    def is_propeller(self) -> bool:
        if self.project is None:
            return False
        return bool(self.project.config.get("is_propeller", False))

    def notify_geometry(self):
        self.unsaved = True
        self.geometry_changed.emit()

    def notify_airfoil(self):
        self.unsaved = True
        self.airfoil_changed.emit()

    def notify_config(self):
        self.unsaved = True
        self.config_changed.emit()

    def notify_results(self):
        self.results_changed.emit()

    def notify_mode(self):
        self.unsaved = True
        self.mode_changed.emit()

    def mark_saved(self):
        """Called after `api.save_project`: what is in memory is now
        on disk."""
        self.unsaved = False


#: Qt shows at most `maxVisibleItems` rows in a dropdown and scrolls the
#: rest. The default is 10, which is invisible until a list grows past it:
#: the popup then looks complete, and the options past the tenth are
#: reachable only by scrolling a list that gives no sign of continuing.
#: Seen on screen with the disk-map field selectors (17 entries).
#:
#: Above this many rows a dropdown genuinely is a list to scroll, and a
#: popup taller than the screen is worse than a scrollbar.
MAX_OPTIONS_WITHOUT_SCROLL = 40


def show_all_options(combo: QComboBox) -> None:
    """Makes the dropdown open with every option already visible.

    Qt sizes the popup to ``min(count, maxVisibleItems)`` rows, so raising
    the cap once is enough: a combo with three entries still shows three,
    and one filled from results long after it was built shows all of them
    without anything having to notice the change."""
    combo.setMaxVisibleItems(MAX_OPTIONS_WITHOUT_SCROLL)


def show_all_options_in(root: QWidget) -> int:
    """Applies `show_all_options` to every combo under `root`.

    Called once on the assembled window, so that a new combo added
    anywhere inherits the behavior without having to remember to ask for
    it. Returns how many it touched."""
    combos = root.findChildren(QComboBox)
    for combo in combos:
        show_all_options(combo)
    return len(combos)


def set_row_visible(form, widget, visible: bool) -> None:
    """Hides/shows the entire ROW of a ``QFormLayout`` -- label included.

    Two pitfalls this function exists to avoid:

    1. ``widget.setVisible(False)`` hides only the field: the label
       stays on screen, pointing at nothing.
    2. ``form.setRowVisible(widget, ...)`` looks up the row by the FIELD
       widget. If the field was wrapped (which is what
       `install_field_popups` does to make the label clickable), the
       original widget is no longer the row's field, and Qt finds
       nothing -- failing silently.
    """
    target = getattr(widget, "_help_container", None) or widget
    try:
        form.setRowVisible(target, visible)
    except RuntimeError:
        # widget outside this form: fall back to the simple behavior
        target.setVisible(visible)


# =============================================================================
# Width of form fields
# =============================================================================
#
# A `QFormLayout` stretches the field to the end of the row. In a 1400px
# window that gave an approximately 1370px box to type "72" into -- and, worse, the SAME
# quantity appeared with different widths in each tab, depending on which
# panel it landed in. It is not a matter of taste: a field that wide
# separates the label from the value by half the screen, and the eye loses
# the row.
#
# The rule is by content TYPE, not by tab, so the same kind of data always
# has the same box throughout the GUI:
#
#   number          short, fixed box -- a number has a known size
#   enumeration     width of the longest option (+ arrow clearance), capped
#   free text       grows (folder path, list of values, name)
#
NUMBER_WIDTH = 150           # px: fits "-1234.567890" with room to spare
ENUM_MIN_WIDTH = 180         # px: a combo never gets narrow enough to
                             #     elide the selected option
ENUM_MAX_WIDTH = 340         # px: cap, so it does not go back to the
                             #     stretched-field problem

# Condition fields (Run Case/Run Batch) use the same geometry, including
# when the value sits inside a composite widget (mu_x/J_x or alpha/Vz).
CONDITION_UNIT_WIDTH = 110
CONDITION_VALUE_WIDTH = NUMBER_WIDTH
CONDITION_ROW_SPACING = 6

#: Texts of the unit-label combos (`widgets.LongitudinalInput` and
#: `widgets.AxialInput`). Listed here, rather than read from the widgets,
#: because the width has to be the SAME in both tabs and both field
#: families: measured per combo, the x-field row (mu_x/J_x/Vx [m/s]) would
#: end up narrower than the z-field row (alpha_rotor [deg]/Vz [m/s]) and
#: the number in each row would start at a different x -- the misalignment
#: this module exists to prevent.
#: Derived from `widgets.CONDITION_UNITS` (every mode, every slot):
#: the width has to fit the longest label of ANY mode, otherwise switching
#: to propeller would cut off "alpha_disk [deg]" -- and a hand-copied list
#: would silently go stale the moment a new unit was added.
def _all_unit_labels() -> tuple:
    from .widgets import CONDITION_UNITS
    return tuple(sorted({label
                         for pairs in CONDITION_UNITS.values()
                         for label, _var in pairs}))

#: Slack for the text inside a QComboBox: arrow (22px, see styles.py),
#: side padding (6+6) and border (1+1).
_COMBO_SLACK = 38


def condition_unit_width(combos=()) -> int:
    """Width of the unit-label combos, MEASURED instead of fixed.

    "alpha [deg]" used to come out clipped ("alpha [deg") at the old
    fixed 110px -- and the clipping point changes with the font, the
    theme and the monitor scale, so the right number is not a
    constant, it is a measurement.
    `CONDITION_UNIT_WIDTH` becomes the FLOOR (no row shrinks
    below what already looked good).

    ``combos``: the actual unit `QComboBox` widgets, when they exist.
    Their `sizeHint` is the only measurement that includes EVERYTHING
    -- the widget's real font (not the app's), the stylesheet's
    padding and the dropdown arrow --, but it is only valid AFTER the
    QSS polish, which happens on first display. That is why the caller
    passes the combos from inside a `showEvent`
    (see `RunCaseTab`/`RunBatchTab._update_unit_width`), and
    the font-metric calculation below serves as the floor for
    construction time, when there is no reliable `sizeHint` yet.

    Without a `QApplication` (import in a pure logic test), returns the
    floor instead of blowing up."""
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return CONDITION_UNIT_WIDTH
    fm = QFontMetrics(app.font())
    needed = max(fm.horizontalAdvance(t) for t in _all_unit_labels())
    width = max(CONDITION_UNIT_WIDTH, needed + _COMBO_SLACK)
    for combo in combos:
        # A QComboBox's `sizeHint` already embeds the longest option;
        # `minimumSizeHint` covers the case of a combo with an imposed
        # maximum width (none of these have one, but it costs nothing
        # and prevents a regression).
        width = max(width, combo.sizeHint().width(),
                    combo.minimumSizeHint().width())
    return width


#: Engine field each input slot is bound to. `field_help` identifies the row
#: by the quoted token that opens the tooltip, so this has to be the ENGINE's
#: name (disk axes) and not the one displayed, which rotates with the mode.
_SLOT_FIELD = {"inplane": "mu_x", "axial": "Vz"}


def resolve_condition_pair(advance, axial, rpm: float, radius_m: float) -> tuple:
    """``(mu_x, Vz)`` for the pair of condition fields, in the ORDER the
    chosen unit requires.

    Normally the in-plane component is the known one and the axial one
    can be derived from it (the disk angle). With `alpha_disk` -- the
    angle measured from the SHAFT, which is what a propeller uses --
    the dependency reverses: the axial one is the known one and the
    in-plane one comes from it. Always resolving in the old order would
    give `mu_x` from a `Vz` that has not been read yet, that is, zero.

    Same inversion as `bemt.resolve_advance_velocity` and
    `studies.build_factorial_conditions`; it exists here because Run
    Case and the standalone Run Batch row build the condition without
    going through either of the two."""
    if getattr(advance, "is_alpha_disk", lambda: False)():
        Vz = axial.vv(0.0, rpm, radius_m)
        return advance.mu_x(Vz), Vz
    mu_x = advance.mu_x()
    return mu_x, axial.vv(mu_x, rpm, radius_m)


def apply_condition_pair(advance, axial, mu_x: float, Vz: float,
                             rpm: float, radius_m: float) -> None:
    """Writes ``(mu_x, Vz)`` into the two fields -- the inverse of
    `resolve_condition_pair`, used when loading a saved case.

    The axial one goes first: with `alpha_disk` in the in-plane field,
    it is the already-written `Vz` that gives the angle its meaning."""
    axial.set_vv(Vz, mu_x, rpm, radius_m)
    if getattr(advance, "is_alpha_disk", lambda: False)():
        advance.set_mu(mu_x, Vz)
    else:
        advance.set_mu(mu_x)


def condition_label_and_tooltip(is_propeller: bool, slot: str) -> tuple:
    """``(row label, tooltip)`` for field ``slot``
    (``"inplane"``/``"axial"``) in the current mode's convention.

    The text itself lives in `nomenclature.slot_label`, which owns every
    axis name the user meets. All this adds is the quoted engine key that
    opens the tooltip: `field_help` reads it to find which field the row
    belongs to, and without it the row loses its help popup.
    """
    label, tip = nomenclature.slot_label(slot, is_propeller)
    # QToolTip renders plain text as running text, so the paragraph breaks
    # have to be HTML for them to survive the hover.
    tip = tip.replace("\n\n", "<br><br>").replace("\n", "<br>")
    return label, f'"{_SLOT_FIELD[slot]}" — {tip}'


def set_row_label(form, widget, text: str) -> bool:
    """Changes the TEXT of the row label of ``widget`` in a
    ``QFormLayout``.

    Same pitfall as `set_row_visible`: the field may be wrapped
    by the "?" help container, and the row label may already have
    become a clickable `QToolButton` (`field_help`). Both cases are
    handled here, instead of keeping a reference to the original
    `QLabel` -- which would stop being the row's label as soon as the
    help was installed."""
    from PyQt6.QtWidgets import QFormLayout

    target = getattr(widget, "_help_container", None) or widget
    row_idx, _role = form.getWidgetPosition(target)
    if row_idx < 0:
        return False
    item = form.itemAt(row_idx, QFormLayout.ItemRole.LabelRole)
    label = item.widget() if item is not None else None
    if label is None or not hasattr(label, "setText"):
        return False
    label.setText(text)
    return True


def apply_condition_unit_width(root) -> int:
    """Measures and applies the common width of the unit-label combos
    under ``root`` (a tab), adjusting the simple fields' indent along
    with it.

    Called from the tab's ``showEvent``, not from construction: it is
    only after the stylesheet's polish that a combo's `sizeHint`
    reflects the real font, padding and arrow -- calculated earlier,
    the width came out short and "alpha [deg]" got clipped precisely
    on screens whose font/scale differs from the developer's.

    The simple fields (Collective/RPM) are indented up to the number
    column by a container marked with ``_unit_indent`` (see
    ``_with_unit_indent`` in both tabs); their indent moves along
    with it, otherwise the values column would split in two.

    Returns the applied width."""
    from PyQt6.QtWidgets import QWidget
    from .widgets import LongitudinalInput, AxialInput

    from PyQt6.QtWidgets import QComboBox

    fields = root.findChildren((LongitudinalInput, AxialInput))
    combos = [c.unit_combo for c in fields if getattr(c, "unit_combo", None) is not None]
    # STANDALONE unit combos (the factorial's axis rows), marked at
    # construction: they get included in the same measurement,
    # otherwise the "values:" column would land at a different x per
    # row -- "mu_x" and "alpha [deg]" have quite different natural
    # widths.
    combos += [c for c in root.findChildren(QComboBox)
               if getattr(c, "_is_unit_combo", False)]
    width = condition_unit_width(combos)
    for combo in combos:
        combo.setFixedWidth(width)
    for container in root.findChildren(QWidget):
        if getattr(container, "_unit_indent", False):
            layout = container.layout()
            if layout is not None:
                layout.setContentsMargins(width + CONDITION_ROW_SPACING, 0, 0, 0)
        elif getattr(container, "_unit_reserve", False):
            # Reserves the column even with the combo hidden (axis
            # "(none)"): a hidden widget takes up no width, and the
            # whole row would slide to the left.
            container.setFixedWidth(width)
    return width


#: Clearance for the label inside a `QPushButton` (frame + theme padding).
BUTTON_MARGIN = 26


def equalize_button_widths(buttons, extra_labels=()) -> int:
    """Gives the SAME width to a group of buttons that read together,
    and returns the applied width.

    Two pitfalls, learned on screen and both invisible without the
    theme applied:

    1. `setFixedWidth` does NOT hold a button's width here. The
       stylesheet declares ``QPushButton { max-width: 520px }``, and a
       QSS width rule overrides the maximum fixed in code -- each
       button would grow back to its own `sizeHint`. That is why what
       gets fixed is the common MINIMUM: each one's `sizeHint` stays
       below it, and the group settles at the same width.
    2. `sizeHint` only includes the theme's padding AFTER the QSS
       polish, which happens on first display -- hence this function
       being called from the tab's `showEvent`, not from construction.

    ``extra_labels``: texts the button will still display (the
    generate-cases one alternates between two), so it does not change
    size on the switch.

    Each button gets marked with ``_group_width``: the sweep in
    `tests/test_gui_layout.py` forbids a button much wider than its
    own text -- a sign of a missing `addStretch` -- and a short button
    in a group is exactly that, on purpose."""
    buttons = [b for b in buttons if b is not None]
    if not buttons:
        return 0
    metrics = buttons[0].fontMetrics()
    labels = [b.text() for b in buttons] + list(extra_labels)
    width = max(
        max(metrics.horizontalAdvance(t) for t in labels) + BUTTON_MARGIN,
        max(b.sizeHint().width() for b in buttons),
    )
    for button in buttons:
        button.setMinimumWidth(width)
        button._group_width = width
    return width


def ensure_button_legibility(root) -> int:
    """Prevents a `QPushButton` from ending up narrower than its own
    text.

    Returns how many buttons were widened.

    In a tight `QHBoxLayout` (or inside a `QDialogButtonBox`, which
    distributes width between the buttons) Qt shrinks the button below
    what is needed and ELIDES the label: "Generate cases → replace
    queue" turned into "Generate cases → replace q…", and "Restore
    from disk"/"Validate configuration"/"Generate report…" showed up
    clipped the same way. The tooltip stayed correct, but nobody reads
    the tooltip of a button that appears to already be spelled out in
    full.

    The floor comes from the button's own FONT METRICS, not a fixed
    number: this way it keeps working if the text, the font or the
    language changes (no pixel assertions -- see CLAUDE.md rule 3).

    Called once per tab, from outside, like
    `compact_form_fields` and
    `field_help.install_field_popups` -- it is window policy, and
    a new tab obeys it without having to remember anything.
    """
    from PyQt6.QtWidgets import QPushButton

    #: Clearance for the frame, the theme's padding and (when present)
    #: the icon.
    SLACK = 26
    adjusted = 0
    for button in root.findChildren(QPushButton):
        text = button.text().replace("&", "")
        if not text:
            continue
        needed = button.fontMetrics().horizontalAdvance(text) + SLACK
        if button.icon() is not None and not button.icon().isNull():
            needed += button.iconSize().width() + 6
        if button.minimumWidth() < needed:
            button.setMinimumWidth(needed)
            adjusted += 1
    return adjusted


#: Minimum vertical spacing between rows of a `QFormLayout`.
#: The style's default (6px) is too tight when the row is a lone
#: QCheckBox followed by a field: the two stick together and read as
#: one thing (seen in "Enable dynamic stall" + "Lag constant A", in
#: the three rows of "3D rotational effects" and in "Adaptive
#: relaxation" right above its parameter box).
MIN_ROW_SPACING = 10

#: Minimum horizontal spacing between NEIGHBORING checkboxes on the
#: same row. A `QCheckBox` draws its indicator and label flush against
#: its own border, so two of them side by side with the style's
#: default spacing (approximately 6px) read as one thing: "Coefficients" touched
#: the square of "Azimuthal loads", and the eye could not tell which
#: box each word belonged to. The value is larger than the ordinary
#: layout spacing on purpose -- it is the distance that separates
#: independent CONTROLS, not parts of the same field.
MIN_CHECKBOX_SPACING = 18


def ensure_row_spacing(root, min_spacing: int = MIN_ROW_SPACING,
                        min_checkbox_spacing: int = MIN_CHECKBOX_SPACING) -> int:
    """Gives breathing room to the layout under ``root``, in two
    directions, and returns how many layouts changed.

    * VERTICAL: minimum spacing between the rows of every
      ``QFormLayout`` -- a row occupied only by a `QCheckBox` is
      shorter than a field row, and the two would stick together.
    * HORIZONTAL: minimum spacing between neighboring checkboxes on
      the same ``QHBoxLayout`` (see `MIN_CHECKBOX_SPACING`).

    WINDOW policy, applied from outside alongside
    `compact_form_fields` and `ensure_button_legibility` --
    for the same reason: this way a new tab is born obeying it,
    without having to remember anything. Only INCREASES: a layout that
    already explicitly asked for more space keeps what it asked for."""
    from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QCheckBox, QRadioButton

    ajustados = 0
    for form in root.findChildren(QFormLayout):
        if form.verticalSpacing() < min_spacing:
            form.setVerticalSpacing(min_spacing)
            ajustados += 1
    for row_idx in root.findChildren(QHBoxLayout):
        checkbox_count = sum(1 for i in range(row_idx.count())
                     if isinstance(row_idx.itemAt(i).widget(), (QCheckBox, QRadioButton)))
        if checkbox_count >= 2 and row_idx.spacing() < min_checkbox_spacing:
            row_idx.setSpacing(min_checkbox_spacing)
            ajustados += 1
    return ajustados


def align_form_labels(root) -> int:
    """Left-aligns the label of every ``QFormLayout`` under ``root``
    and returns how many layouts changed.

    The style's default on Windows is `AlignRight`: labels get
    right-justified, flush against the field, and the START of each
    row's word falls in a different column ("Type:" starts far to the
    right of "Number of blades:"). The eye looks for the start of a
    word, not the end, so the label column reads as a jagged margin
    and is more expensive to scan top to bottom -- this is what the
    user saw in the "Generate radial table" dialog.

    `AlignVCenter` comes along because the vertical default aligns the
    label with the top of the field, and a tall row (combo, spin box
    with arrows) would leave the text floating above the center of the
    field it belongs to.

    WINDOW policy like `ensure_row_spacing` and
    `compact_form_fields`, applied from outside for the
    same reason: a new tab is born obeying it without having to
    remember anything."""
    from PyQt6.QtWidgets import QFormLayout

    target = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    ajustados = 0
    for form in root.findChildren(QFormLayout):
        if form.labelAlignment() != target:
            form.setLabelAlignment(target)
            ajustados += 1
    return ajustados


def compact_form_fields(root) -> int:
    """Gives a readable width to numeric and enumeration fields under
    ``root``. Returns how many widgets were adjusted.

    Called ONCE per tab, from outside (``app.MainWindow``), for the
    same reason as ``field_help.install_field_popups``: it is
    visual policy for the whole window, not a per-tab decision -- and
    a new tab starts obeying it without having to remember anything.

    Deliberately does NOT touch ``QLineEdit``/``QPlainTextEdit``:
    there the content is free text of unpredictable size (``outputs/``
    folder path, list ``0, 0.1, 0.2``, project name) and shortening
    the box would hide the beginning or the end of what the user
    typed.

    Idempotent: a widget already adjusted is not readjusted (the
    second calculation would see the already-limited ``sizeHint`` and
    shrink the field on every call).
    """
    from PyQt6.QtWidgets import QAbstractSpinBox, QComboBox

    ajustados = 0
    for w in root.findChildren(QAbstractSpinBox):
        if getattr(w, "_width_capped", False):
            continue
        w.setMaximumWidth(NUMBER_WIDTH)
        w._width_capped = True
        ajustados += 1
    for w in root.findChildren(QComboBox):
        if getattr(w, "_width_capped", False):
            continue
        if w.property("_form_width_stretch"):
            # Flagged by the tab as a full-column field (vertical
            # alignment rule): it must share the line edits' width, so
            # the enum cap would defeat the size policy set on it.
            # Qt dynamic property: setProperty/getProperty, not getattr.
            w._width_capped = True
            ajustados += 1
            continue
        # `sizeHint` already embeds the longest option; the clearance
        # covers the dropdown arrow (styles.py) and the side padding.
        width = min(max(w.sizeHint().width() + 24, ENUM_MIN_WIDTH),
                    ENUM_MAX_WIDTH)
        # The cap NEVER overrides the minimum the combo itself asks
        # for: `dialogs.adjust_combo_width` already fixes a
        # `minimumWidth` equal to the longest item, precisely so the
        # popup does not come out elided with "…". A cap smaller than
        # that would shrink nothing (Qt honors the minimum) and would
        # only create a misleading constraint -- and there is a real
        # option wider than `ENUM_MAX_WIDTH` ("Full range (-180°
        # to 180°)", 354px).
        width = max(width, w.minimumWidth(), w.minimumSizeHint().width())
        w.setMaximumWidth(width)
        w._width_capped = True
        ajustados += 1
    return ajustados


#: alignments used in numeric tables (text left, number right -- so a
#: column's decimal places line up under one another)
TEXT_ALIGN = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
NUMBER_ALIGN = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def align_headers_with_content(table, numeric_columns) -> None:
    """Aligns each header like the column it sits above.

    Qt's default centers every header; over a column of text flush
    left (or numbers flush right) this leaves the label offset from
    what it names.
    """
    for column in range(table.columnCount()):
        item = table.horizontalHeaderItem(column)
        if item is None:
            continue
        item.setTextAlignment(NUMBER_ALIGN if column in numeric_columns
                              else TEXT_ALIGN)


def show_error(parent, title: str, exc: Exception):
    # Format the PASSED exception's own traceback. The previous
    # `traceback.format_exc()` reads the AMBIENT exception context: called
    # outside the `except` block that produced `exc` (the usual case for
    # errors captured in a worker and surfaced later), it found nothing
    # and printed the useless "NoneType: None" under the message.
    detail = "".join(traceback.format_exception(
        type(exc), exc, exc.__traceback__, limit=3))
    QMessageBox.critical(parent, title, f"{exc}\n\n{detail}")


# =============================================================================
# Help (docs/documentation.html) -- single source of physics + GUI +
# shortcuts documentation. The "?" button (FlowIndicatorBar) and the F1
# shortcut (MainWindow) call this same function: it opens the HTML in the
# system's default browser via QDesktopServices, without embedding any
# HTML engine inside the GUI itself.
# =============================================================================

def open_help(parent=None, anchor: str | None = None):
    """Opens the documentation in the default browser.

    ``anchor``: section id (for example ``"cap-3-2-1"``). With it, the browser
    jumps straight to the field -- this is what makes the "?" next to
    each field worth more than the global "?"."""
    help_path = paths.documentation_path()
    if help_path is None:
        QMessageBox.warning(
            parent, "Help not found",
            "File docs/documentation.html not found within the package or in the repository.")
        return
    url = QUrl.fromLocalFile(str(help_path))
    if anchor:
        url.setFragment(anchor)
    QDesktopServices.openUrl(url)


class _ClickableBlockTitle(QObject):
    """Makes the TITLE of a QGroupBox clickable (opens the block's
    popup).

    Replaces the old floating "?" button: no "?" exists in the window
    anymore. The groupbox neither gains nor loses any widget -- just
    an event filter --, so the internal layout and widget order that
    ``tools/field_index.py`` depends on stay identical.
    """

    def __init__(self, groupbox, block_id: str):
        super().__init__(groupbox)
        self._gb = groupbox
        self._block_id = block_id
        groupbox.installEventFilter(self)

    def title_rect(self):
        """Area occupied by the title text, in the groupbox's
        coordinates."""
        from PyQt6.QtWidgets import QStyle, QStyleOptionGroupBox
        option = QStyleOptionGroupBox()
        self._gb.initStyleOption(option)
        return self._gb.style().subControlRect(
            QStyle.ComplexControl.CC_GroupBox, option,
            QStyle.SubControl.SC_GroupBoxLabel, self._gb)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            try:
                pos = event.position().toPoint()
            except AttributeError:                      # pragma: no cover
                return False
            if self.title_rect().contains(pos):
                from .help_popup import HelpPopup
                HelpPopup.instance(self._gb.window()).show_block(
                    self._block_id, self._gb)
                # A "checkable" groupbox uses the title to toggle: do
                # not swallow the click in that case, just add the
                # help.
                return not self._gb.isCheckable()
        return False


def make_block_title_clickable(groupbox, block_id: str) -> bool:
    """The QGroupBox title opens the block's conceptual explanation.

    Returns ``True`` if it was installed. Idempotent.
    """
    from . import help_blocks

    if block_id not in help_blocks.BLOCK_HELP:
        return False
    if groupbox.layout() is None:
        return False
    if getattr(groupbox, "_block_help", None) is not None:
        return False

    groupbox.setStyleSheet(
        (groupbox.styleSheet() or "")
        + "\nQGroupBox::title { color: #3a6dbd; }"
    )
    groupbox.setToolTip(
        "Click the section title for an overview and the full physics "
        "documentation of this block.")
    groupbox._block_help = _ClickableBlockTitle(groupbox, block_id)
    return True


# Historical name: the call stays the same, it is the "?" that stopped
# existing.
add_block_help_button = make_block_title_clickable


def apply_figure_minimum_size(canvas: FigureCanvasQTAgg, figure: Figure) -> tuple:
    """Gives ``canvas`` the smallest size at which ``figure`` still
    reads, and returns it.

    A MULTI-PANEL figure gets a floor: each of its panels keeps a
    minimum number of pixels, and a window too small for the whole grid
    scrolls over it. A SINGLE-PANEL figure gets no floor at all, so it
    goes on filling whatever area the window gives it, at any screen
    size. `viz.plots.figure_minimum_pixels` decides which is which
    (`QR-14`).
    """
    from ..viz import plots

    width, height = plots.figure_minimum_pixels(figure)
    canvas.setMinimumSize(width, height)
    return width, height


class MplCanvas(FigureCanvasQTAgg):
    """Single-axis canvas (most of the simple plots)."""
    def __init__(self, figsize=(5, 3.5)):
        self.fig = Figure(figsize=figsize, tight_layout=True)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)

    def clear(self):
        for extra in list(self.fig.axes):
            if extra is not self.ax:
                self.fig.delaxes(extra)
        self.ax.clear()


class CanvasHost(QWidget):
    """Drawing area that swaps its content dynamically: sometimes a
    single-axis ``MplCanvas`` (which is only cleared/redrawn),
    sometimes an entire multi-panel ``Figure`` returned by a grid
    function of ``plots.py`` (plot_disk_map_grid, plot_coefficients_vs_mu,
    plot_blade_loads_vs_span, plot_loads_vs_azimuth) -- used by the
    Results tab (docs/plano.md Section 8; docs/plano_v3.md Part 4),
    which is the only tab with drawing on screen.
    """
    #: Smallest the drawing area itself may become. It exists so that a
    #: figure's own minimum NEVER propagates up to the tab: whatever the
    #: scrolled figure demands stops at this widget, and the surrounding
    #: layout keeps deciding how much room the plot gets (`QR-14`).
    _VIEWPORT_MINIMUM_PX = 120

    def __init__(self, with_toolbar: bool = False):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._current: FigureCanvasQTAgg | None = None
        self._with_toolbar = with_toolbar
        self._toolbar: NavigationToolbar2QT | None = None
        # A figure that cannot stay readable at the window's size is
        # SCROLLED, not squeezed. `setWidgetResizable` keeps the old
        # behavior wherever there is room -- the figure still grows to
        # fill the area -- and only starts scrolling once the area is
        # smaller than the figure's own minimum.
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Expanding)
        self._scroll.setMinimumSize(self._VIEWPORT_MINIMUM_PX,
                                     self._VIEWPORT_MINIMUM_PX)
        self._layout.addWidget(self._scroll)
        self.simple = MplCanvas(figsize=(6, 5))
        self._show(self.simple)

    def _show(self, canvas: FigureCanvasQTAgg):
        if self._scroll.widget() is not None:
            # `setWidget` DELETES the previous widget; the canvases here
            # are reused, so the outgoing one has to be taken out first.
            self._scroll.takeWidget().setParent(None)
        # NavigationToolbar2QT gives zoom (rectangle/wheel), pan, view
        # "back/forward", and the "Edit axis, curve and image
        # parameters" button (axes+curve icon), which opens a dialog
        # to edit min/max and scale (linear/log) of each axis -- this
        # is what covers "zoom in" and "change axis scale" on the
        # plots (Airfoil and Results, docs/plano_v3.md Part 7/8),
        # without reinventing the UI. Since `show_figure` swaps the
        # canvas instance on every new figure (multi-panel grids), the
        # toolbar is rebuilt here, bound to the CURRENTLY shown canvas
        # -- an old toolbar pointing at an already-removed canvas does
        # not work.
        if self._with_toolbar:
            if self._toolbar is not None:
                self._layout.removeWidget(self._toolbar)
                self._toolbar.setParent(None)
                self._toolbar.deleteLater()
            self._toolbar = NavigationToolbar2QT(canvas, self)
            self._toolbar.setIconSize(QSize(15, 15))
            # Above the drawing area, and OUTSIDE it: a toolbar that
            # scrolled away with the figure would be unreachable exactly
            # when the figure is too big for the window, which is the
            # one moment the user needs to zoom.
            self._layout.insertWidget(0, self._toolbar)
        self._scroll.setWidget(canvas)
        self._current = canvas

    def use_simple(self) -> MplCanvas:
        """Returns the single-axis canvas, already visible, ready for
        ``clear()`` + drawing on ``.ax`` + ``.draw()``."""
        self._show(self.simple)
        return self.simple

    def show_figure(self, fig: Figure):
        """Replaces the content with an entire multi-panel figure that
        is already built (returned by a ``plots.plot_*_grid``/
        ``plot_*`` function called with ``fname=None``)."""
        canvas = FigureCanvasQTAgg(fig)
        apply_figure_minimum_size(canvas, fig)
        self._show(canvas)
        canvas.draw()

    def show_message(self, text: str):
        c = self.use_simple()
        c.clear()
        # No axes in the empty state: the default 0-1 frame with ticks
        # announces a pair of quantities that does not exist and makes
        # the message look like data plotted in the middle of a real
        # chart.
        c.ax.set_axis_off()
        c.ax.text(0.5, 0.5, text, ha="center", va="center", transform=c.ax.transAxes, wrap=True)
        c.draw()


class PlotlyCanvasHost(QWidget):
    """Hosts a Plotly figure inside the Qt GUI via an embedded Chromium view.

    Mirrors CanvasHost's contract (set_figure/show_message) but renders
    interactive Plotly charts instead of static matplotlib. Requires the
    optional `interactive` dependency group (PyQt6-WebEngine + plotly).

    Known limitation: QWebEngineView hard-crashes (native crash, no
    exception) under QT_QPA_PLATFORM=offscreen. Chromium's compositor has
    no offscreen-compatible software path there. Works fine under a real
    display. Tests that instantiate this class must skip under offscreen.
    """
    def __init__(self):
        super().__init__()
        if not HAS_INTERACTIVE_PLOTS:
            raise RuntimeError(
                "Interactive plots need the 'interactive' optional dependency group "
                "(pip install \"zbemt[interactive]\"): PyQt6-WebEngine + plotly.")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._view = QWebEngineView()
        self._layout.addWidget(self._view)
        import tempfile
        self._tmp_dir = tempfile.mkdtemp(prefix="zbemt_plotly_")
        self._tmp_html = Path(self._tmp_dir) / "figure.html"
        #: plotly.js written ONCE next to the HTML -- see `set_figure`
        self._tmp_plotly_js = Path(self._tmp_dir) / "plotly.min.js"

    def _ensure_plotlyjs(self) -> None:
        """Writes plotly.js next to the figure, once per session.

        `include_plotlyjs="directory"` only WRITES that file from
        `write_html`; `to_html` assumes it is already there."""
        if self._tmp_plotly_js.exists():
            return
        from plotly.offline import get_plotlyjs
        self._tmp_plotly_js.write_text(get_plotlyjs(), encoding="utf-8")

    def set_figure(self, fig):
        """Renders a plotly.graph_objects.Figure. Named set_figure (not
        `show`) because QWidget already defines `.show()` and a method
        override there would silently shadow it.

        plotly.js is LINKED, not inlined. With `include_plotlyjs=True`
        every redraw wrote an approximately 5.5 MB page (3.5 MB of it the
        library), and Chromium re-parsed and re-executed the whole bundle on each
        load: changing the field of the 3D view froze the window for
        seconds. Written once beside the figure, the page drops to
        approximately 0.6 MB and the browser serves the library from its own cache.
        `validate=False` skips re-validating arrays that were just built
        here (another traversal of a 90x145 grid, for figures this code
        assembles itself)."""
        self._ensure_plotlyjs()
        html = fig.to_html(include_plotlyjs="directory", full_html=True,
                            validate=False, config={"displaylogo": False})
        self._tmp_html.write_text(html, encoding="utf-8")
        self._view.load(QUrl.fromLocalFile(str(self._tmp_html)))

    def show_message(self, text: str):
        html = f'<div style="display:flex;align-items:center;justify-content:center;height:100%;font-family:sans-serif;color:#666;">{text}</div>'
        self._tmp_html.write_text(html, encoding="utf-8")
        self._view.load(QUrl.fromLocalFile(str(self._tmp_html)))

    def closeEvent(self, event):
        import shutil
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        super().closeEvent(event)


#: OPTIONAL packages: feature -> (module to import, install command,
#: what stops working without it). Single source for the
#: `require_optional_package` dialog -- a new optional feature goes
#: here, not into a stray message inside a tab.
OPTIONAL_PACKAGES = {
    "neuralfoil": ("neuralfoil", "pip install neuralfoil",
                    "generating airfoil polars with NeuralFoil"),
    "pyvista": ("pyvista", "pip install pyvista",
                 "the interactive 3D rotor view"),
    "interactive": ("PyQt6.QtWebEngineWidgets", 'pip install "zbemt[interactive]"',
                     "interactive (Plotly) charts"),
}


def require_optional_package(widget: QWidget, feature: str) -> bool:
    """True if the optional package for ``feature`` is installed;
    otherwise opens a dialog with the INSTALL COMMAND and returns
    False.

    Before, each optional feature just disabled its own button and
    hid the reason in a tooltip -- anyone who did not hover exactly
    there saw only a dead button, with nothing saying a package was
    missing or which one. Now the button stays clickable and the click
    explains what to install, with the command ready to copy."""
    module_name, command, description = OPTIONAL_PACKAGES[feature]
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        pass
    QMessageBox.information(
        widget, "Optional package not installed",
        f"This feature needs the optional package '{feature}', which is not installed, "
        f"so {description} is unavailable.\n\nInstall it with:\n\n    {command}\n\n"
        "Then restart zBEMT.")
    return False


class MissingBinaryDialog(QDialog):
    """Asks the user to locate a missing external executable, after
    listing every place zBEMT already looked.

    A small QDialog local to this module on purpose:
    `QMessageBox.information` cannot host a Locate button next to
    clickable links. Headless tests drive it by patching `exec` (never
    called for real here) and `QFileDialog.getOpenFileName`.

    The caller reads `chosen_path` after `exec()` returns: it holds the
    picked executable when the user located one, or ``None`` when the
    dialog was closed without a valid pick."""

    def __init__(self, parent: QWidget | None, feature: str,
                 env_var: str) -> None:
        super().__init__(parent)
        self._feature = feature
        self.chosen_path: str | None = None

        self.setWindowTitle(f"{feature} executable not found")
        self.setMinimumWidth(560)

        # The four places resolve_xfoil_binary() already walked through,
        # each with what it found. Reaching this dialog means the whole
        # chain missed an existing file, so every state below is a miss.
        env_state = os.environ.get(env_var, "").strip() or "(not set)"
        remembered = paths.load_app_setting(XFOIL_SETTINGS_KEY)
        remembered_state = remembered.strip() if (
            isinstance(remembered, str) and remembered.strip()) else "(none)"
        folders_state = ", ".join(known_xfoil_location_names())
        message = (
            f"<p>Generating polars with <b>{feature}</b> needs the "
            f"'{feature.lower()}' executable. zBEMT looked for it in four "
            "places:</p>"
            "<ol>"
            f"<li><b>{env_var}</b> environment variable: {env_state}</li>"
            "<li><b>Remembered 'Locate…' choice</b>: "
            f"{remembered_state}</li>"
            f"<li><b>PATH</b> ('{feature.lower()}'): not found</li>"
            f"<li><b>Standard install folders</b> ({folders_state}): "
            "checked</li>"
            "</ol>"
            "<p>1. Already installed? Click <b>Locate…</b> and pick the "
            "executable. The choice is remembered.</p>"
            "<p>2. Not installed? Download XFOIL (free) from "
            '<a href="https://web.mit.edu/drela/Public/web/xfoil/">'
            "MIT Drela — XFOIL</a>, install it, then click <b>Locate…</b> "
            f"(or add its folder to PATH, or set {env_var}).</p>"
        )
        text = QLabel(message)
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setOpenExternalLinks(True)
        text.setWordWrap(True)
        # Kept as an attribute so tests can read the rendered text.
        self.message_label = text

        # Inline feedback for an invalid pick; hidden until needed.
        self._feedback = QLabel("")
        self._feedback.setWordWrap(True)

        locate_btn = QPushButton(f"Locate {feature.lower()}…")
        close_btn = QPushButton("Close")
        locate_btn.clicked.connect(self._on_locate)
        close_btn.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(locate_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addWidget(self._feedback)
        layout.addLayout(buttons)

    def _on_locate(self) -> None:
        """Opens the file picker. A valid pick is stored in
        `chosen_path` and closes the dialog with Accepted; a pick that
        fails the existence check reports inline and keeps the dialog
        open so the user can try again."""
        file_filter = ("Executables (*.exe *.bat *.cmd);;All files (*)"
                       if os.name == "nt" else "All files (*)")
        picked, _file_filter = QFileDialog.getOpenFileName(
            self, f"Locate the {self._feature.lower()} executable", "",
            file_filter)
        if not picked:
            return
        if not Path(picked).is_file():
            self._feedback.setText(
                f"The selected file does not exist:\n{picked}")
            self._feedback.setVisible(True)
            return
        self.chosen_path = picked
        self.accept()


def require_optional_binary(widget: QWidget, feature: str,
                             env_var: str, download_hint: str = "") -> bool:
    """True if the external executable for ``feature`` can be found;
    otherwise opens a dialog that offers to LOCATE it and returns False
    unless the user picks a valid executable.

    Probing uses the engine's own resolver
    (`external_solvers.resolve_xfoil_binary`): the ``env_var``
    environment variable, the remembered 'Locate…' choice, ``PATH``,
    then the standard install folders. A hit returns True before any
    dialog appears, so a user whose binary sits in the official install
    folder never sees this box at all.

    When nothing resolves, the dialog lists those four places with what
    each one held, and offers two numbered ways out: locate an already
    installed executable (the pick is saved through
    `paths.save_app_setting`, so the next lookup finds it), or follow
    the download link first. ``download_hint`` remains in the signature
    because call sites still pass it; its guidance moved into the
    numbered options."""
    if resolve_xfoil_binary() is not None:
        return True
    dialog = MissingBinaryDialog(widget, feature=feature, env_var=env_var)
    dialog.exec()
    if dialog.chosen_path and Path(dialog.chosen_path).is_file():
        paths.save_app_setting(XFOIL_SETTINGS_KEY, dialog.chosen_path)
        return True
    return False


def require_project(widget: QWidget, state: AppState) -> bool:
    if state.project is None:
        QMessageBox.warning(widget, "No project", "Create or open a project first.")
        return False
    return True


def save_project_from_tab(widget: QWidget, state: AppState) -> None:
    """"Save project" identical to `ProjectTab._save_project` -- exposed
    here so that Geometry/Airfoil/Config (where edits now write
    directly to `state.project`, with no "Apply" button) can also
    write to disk without forcing the user to switch tabs first."""
    if not require_project(widget, state):
        return
    try:
        api.save_project(state.project)
        state.mark_saved()
        QMessageBox.information(widget, "Saved", f"Project saved at {state.project.path}")
    except Exception as exc:
        show_error(widget, "Error saving project", exc)


def restore_project_from_disk(widget: QWidget, state: AppState) -> None:
    """Discards the edits in memory and reloads `state.project` from
    disk (`api.open_project` -- a full re-read, not a partial "undo").
    Confirms first if there is something unsaved (`state.unsaved`);
    without this, a click would silently lose work -- same spirit as
    the close-window warning (Q7, `app.py.unsaved_work`)."""
    if not require_project(widget, state):
        return
    if state.unsaved:
        resposta = QMessageBox.question(
            widget, "Discard unsaved changes?",
            "There are changes applied to the project but not saved to disk. "
            "Restoring reloads the project as it is on disk, discarding them.\n\n"
            "Discard and restore?")
        if resposta != QMessageBox.StandardButton.Yes:
            return
    try:
        project = api.open_project(state.project.path)
        state.set_project(project)
    except Exception as exc:
        show_error(widget, "Error restoring project", exc)


def confirm_run_despite_issues(widget: QWidget, state: AppState) -> bool:
    """validate_project + decides whether the run can proceed: blocks
    outright on 'error', asks for confirmation on 'warning'/'info'
    (Run Case/Run Batch never call the engine silently over a
    combination already known to be inconsistent)."""
    issues = api.validate_project(state.project)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        QMessageBox.critical(widget, "Invalid configuration",
                              "Cannot run with the following errors:\n\n"
                              + "\n".join(str(i) for i in errors))
        return False
    others = [i for i in issues if i.level != "error"]
    if others:
        reply = QMessageBox.question(
            widget, "Configuration warnings",
            "There are warnings in the current configuration:\n\n" + "\n".join(str(i) for i in others)
            + "\n\nRun anyway?")
        return reply == QMessageBox.StandardButton.Yes
    return True


