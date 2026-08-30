"""styles.py
=========

"instrument blue" (inspired by avionics panels -- numbers in monospace font,
like a flight instrument, matching the app domain: BEMT/rotor). Applied once
in ``gui.main()`` via ``app.setStyleSheet(APP_QSS)`` on the base ``QStyle``
"Fusion" (flat, no native OS ornaments conflicting with QSS).

Palette (named, not "generic blue #3f6fb4 as always"):
    graphite-900        #14181f   primary text
    graphite-500        #5b6472   secondary text/legend
    graphite-200        #e2e5ea   borders
    graphite-100        #f4f5f7   window background
    white              #ffffff   card/panel background
    instrument         #1f6f78   accent (blue-teal from avionics panel)
    instrument-dark    #17565c   accent hover/pressed

Colors of the 4 status levels (gray/amber/green/red, ``STATUS_COLORS``)
are reused by the flow bar between tabs (``gui.FlowIndicatorBar``) to color
Project/Geometry/Airfoil/Config/Run Case/Run Batch/Results markers --
kept as they were, only the rest of the theme changed."""

from pathlib import Path

STATUS_COLORS = {
    "gray": "#9e9e9e",     # not configured
    "amber": "#f0ad4e",    # warnings
    "green": "#2e7d32",    # ok
    "red": "#c62828",      # blocking error
}

# --- tokens --------------------------------------------------------------
_INK = "#14181f"
_INK_MUTED = "#5b6472"
_BORDER = "#e2e5ea"
_BORDER_STRONG = "#c7cbd3"
_BG = "#f4f5f7"
_CARD = "#ffffff"
_ACCENT = "#1f6f78"
_ACCENT_HOVER = "#17565c"
_ACCENT_SOFT = "#e7f1f1"
_DISABLED_BG = "#eceef1"
_DISABLED_FG = "#a5abb5"

_MONO = '"JetBrains Mono", "Cascadia Code", "Consolas", "DejaVu Sans Mono", monospace'
_SANS = '"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif'

# --- control arrows -------------------------------------------------
# Same trap already documented for ``QCheckBox::indicator`` below,
# and for the same reason: any QSS rule targeting ``QComboBox``/``QSpinBox``
# (even just `border`/`padding`) strips Fusion of SUB-PART drawing and
# requires QSS to draw each one. Without the rules below:
#
#   * ``QComboBox`` had NO arrow at all -- seen on screen, every dropdown
#     in the app (Inflow model, Stall model, Data source, Run mode...) was
#     indistinguishable from a text field: nothing said there was a list
#     to open;
#   * ``QSpinBox``/``QDoubleSpinBox`` drew buttons as a broken glyph shaped
#     like a bracket, not like arrows.
#
# The CSS border triangle (`width:0;height:0;border-*`) does NOT work here:
# Qt ignores it and paints a solid rectangle (tested). The sub-part needs
# ``image:``, so arrows are versioned SVGs in ``gui/assets/``.
_ASSETS = Path(__file__).resolve().parent / "assets"


def _arrow(name: str) -> str:
    """QSS URL for an SVG in ``gui/assets`` (normal paths: Qt doesn't accept
    Windows backslash inside ``url()``)."""
    return (_ASSETS / f"{name}.svg").as_posix()


APP_QSS = f"""
* {{
    font-family: {_SANS};
    color: {_INK};
    outline: none;
}}

QMainWindow {{ background: {_BG}; }}
QWidget {{ background: transparent; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: {_BG}; }}

/* -----------------------------------------------------------------------
   Popups (QMessageBox, QDialog) — explicit background to avoid black
   The problem: child QWidgets inherit `transparent`, which Qt renders
   as black when there is no opaque ancestor in the native context (Windows).
   Matplotlib dialogs (e.g. SubplotTool, Figure options) use native QGroupBox
   and QDoubleSpinBox -- they need explicit background and text here.
   ----------------------------------------------------------------------- */
QDialog {{ background: {_BG}; }}
QDialog QWidget  {{ background: {_BG}; color: {_INK}; }}
QDialog QGroupBox {{
    background: {_CARD};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    color: {_INK};
}}
QDialog QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {_INK};
    background: transparent;
}}
QDialog QLabel {{ background: transparent; color: {_INK}; }}
QDialog QPushButton {{ background: {_CARD}; }}

QMessageBox {{
    background: {_CARD};
}}
QMessageBox QLabel {{
    color: {_INK};
    background: transparent;
}}
QMessageBox QTextEdit {{
    background: {_CARD};
    color: {_INK};
    border: 1px solid {_BORDER};
    border-radius: 4px;
}}
/* NO "max-width: none" here: Qt (QStyleSheetStyle) doesn't handle the
   "none" value well in this property -- instead of removing the limit, it
   collapses ALL sibling buttons to a uniform width smaller than the text
   itself (reproduced: "Discard"/"Cancel" cut to ~69px width even needing
   84/72px). The 360px from the `QPushButton` base above never restricts a
   real dialog button (the longest in the app, "Generate and replace table",
   measures ~342px) -- so there is no reason to override here, just
   background. */
QInputDialog QWidget {{ background: {_BG}; }}
QInputDialog QLabel {{ background: transparent; color: {_INK}; }}
QInputDialog QLineEdit {{ background: {_CARD}; }}

QLabel {{ color: {_INK}; }}

QGroupBox {{
    background: {_CARD};
    font-weight: 600;
    border: 1px solid {_BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {_INK};
}}

QTabWidget::pane {{
    border: 1px solid {_BORDER};
    border-radius: 6px;
    background: {_CARD};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {_INK_MUTED};
    padding: 8px 16px;
    margin-right: 2px;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {_ACCENT};
    font-weight: 700;
    border-bottom: 2px solid {_ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {_INK};
}}

QPushButton {{
    background: {_CARD};
    border: 1px solid {_BORDER_STRONG};
    border-radius: 5px;
    padding: 5px 14px;
    /* 520px, not 360px. Qt (QStyleSheetStyle) clamps the computed
       sizeHint to max-width. This is not only a layout ceiling. It CUTS
       the text of the longest button in the app ("Check airfoil (live
       preview on the right)", approximately 492px of text) when the value
       is smaller than that. */
    max-width: 520px;
}}
QPushButton:hover {{ border-color: {_ACCENT}; }}
QPushButton:pressed {{ background: {_ACCENT_SOFT}; }}
QPushButton:disabled {{ background: {_DISABLED_BG}; color: {_DISABLED_FG}; border-color: {_BORDER}; }}
QPushButton:default, QPushButton#primary {{
    background: {_ACCENT};
    border-color: {_ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton:default:hover, QPushButton#primary:hover {{ background: {_ACCENT_HOVER}; }}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox,
QSpinBox, QDoubleSpinBox {{
    background: {_CARD};
    border: 1px solid {_BORDER_STRONG};
    border-radius: 4px;
    padding: 3px 6px;
    selection-background-color: {_ACCENT};
    selection-color: white;
}}
QSpinBox, QDoubleSpinBox {{ font-family: {_MONO}; }}

/* Keeps inputs inside dialogs and popups readable, with a white
   background and dark text, and with reduced padding. The reduced padding
   stops fields from being cut in a tight layout such as the Matplotlib
   one. min-width stops the QDoubleSpinBox controls of SubplotTool from
   being compressed until they cut. */
QDialog QLineEdit, QDialog QPlainTextEdit, QDialog QTextEdit, QDialog QComboBox,
QDialog QSpinBox, QDialog QDoubleSpinBox {{
    background: {_CARD};
    color: {_INK};
    border: 1px solid {_BORDER_STRONG};
    padding: 1px 3px;
    min-width: 70px;
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {_ACCENT};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background: {_DISABLED_BG}; color: {_DISABLED_FG};
}}
/* Dropdown arrow: see the `_arrow` block at the top of the module.
   Without these two rules the combo looks identical to a QLineEdit. */
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
    background: transparent;
}}
/* `width` and `height` are REPEATED in each state on purpose. Qt does not
   inherit these two from a less specific rule for the sub-part. Without
   them, the SVG is drawn at the natural size of the widget. On screen, the
   chevron of the open state came out huge, in the middle of the combo, ON
   TOP of the option text ("Tip + root (both)" was cut behind it). */
QComboBox::down-arrow {{ image: url({_arrow("chevron-down")}); width: 10px; height: 7px; }}
QComboBox::down-arrow:on {{
    image: url({_arrow("chevron-down-accent")}); width: 10px; height: 7px;
}}
QComboBox::down-arrow:disabled {{
    image: url({_arrow("chevron-down-disabled")}); width: 10px; height: 7px;
}}
/* Space on the right, so the arrow does not touch the option text. */
QComboBox {{ padding-right: 24px; }}

/* Spinbox step buttons, for the same reason as the arrow above. */
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid {_BORDER};
    border-top-right-radius: 4px;
    background: transparent;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid {_BORDER};
    border-bottom-right-radius: 4px;
    background: transparent;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {_ACCENT_SOFT};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({_arrow("spin-up")}); width: 8px; height: 5px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({_arrow("spin-down")}); width: 8px; height: 5px;
}}
QSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off,
QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:off {{
    image: url({_arrow("spin-up-disabled")});
}}
QSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off,
QDoubleSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:off {{
    image: url({_arrow("spin-down-disabled")});
}}
QSpinBox, QDoubleSpinBox {{ padding-right: 20px; }}

QComboBox QAbstractItemView {{
    background: {_CARD};
    border: 1px solid {_BORDER_STRONG};
    selection-background-color: {_ACCENT_SOFT};
    selection-color: {_INK};
}}

/* The Tools menu. A QMenu is a POPUP WINDOW, so it never inherited the
   light colors this sheet gives the widgets, and it fell back to the
   platform palette instead. Under Windows in dark mode that palette is
   dark, so the menu opened as a black panel with near-black entries: the
   four Tools windows were on screen and unreadable. The popup of a
   QComboBox was styled here and the menu was not, which is why only one
   of the two was affected. */
QMenu {{
    background: {_CARD};
    color: {_INK};
    border: 1px solid {_BORDER_STRONG};
    padding: 4px;
}}
QMenu::item {{
    background: transparent;
    color: {_INK};
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {_ACCENT_SOFT};
    color: {_INK};
}}
QMenu::item:disabled {{ color: {_DISABLED_FG}; }}
QMenu::separator {{
    height: 1px;
    background: {_BORDER};
    margin: 4px 8px;
}}

/* Vertical `padding`, not only `spacing`. A QFormLayout row that holds
   only a QCheckBox is SHORTER than a field row, because the indicator
   measures less than a spinbox. Qt spaces the rows by their height.
   Therefore, "Enable dynamic stall (Øye)" touched "Lag constant A:", and
   the three rows of "3D rotational effects" read as one block. */
QCheckBox, QRadioButton {{ spacing: 6px; padding: 4px 0; }}

/* Any QSS rule that targets QCheckBox or QRadioButton, even only
   `spacing` above, takes the indicator drawing away from the native
   (Fusion) style. It then requires QSS to draw EVERY sub-part. Without an
   explicit ``::indicator`` rule, the indicator comes out transparent and
   with no border. The small square of the cleared checkbox disappeared
   completely, and left no sign that a checkable field was there. */
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {_BORDER_STRONG};
    border-radius: 3px;
    background: {_CARD};
}}
QRadioButton::indicator {{ border-radius: 7px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {_ACCENT};
}}
QCheckBox::indicator:checked, QCheckBox::indicator:indeterminate,
QRadioButton::indicator:checked {{
    background: {_ACCENT};
    border-color: {_ACCENT};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {_DISABLED_BG};
    border-color: {_BORDER};
}}

QListWidget, QTableWidget, QTreeWidget {{
    background: {_CARD};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    gridline-color: {_BORDER};
    alternate-background-color: {_BG};
}}
QHeaderView::section {{
    background: {_BG};
    color: {_INK_MUTED};
    padding: 4px 6px;
    border: none;
    border-bottom: 1px solid {_BORDER_STRONG};
    font-weight: 600;
}}
QListWidget::item:selected, QTableWidget::item:selected {{
    background: {_ACCENT_SOFT};
    color: {_INK};
}}

QSplitter::handle {{ background: {_BORDER}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}
QSplitter::handle:hover {{ background: {_ACCENT}; }}

QStatusBar {{ background: {_CARD}; border-top: 1px solid {_BORDER}; color: {_INK_MUTED}; }}
QProgressBar {{
    background: {_BG};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    text-align: center;
}}
QProgressBar::chunk {{ background: {_ACCENT}; border-radius: 3px; }}

QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {_BORDER_STRONG}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {_ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {_BORDER_STRONG}; border-radius: 5px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: {_ACCENT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QToolTip {{
    background: {_INK};
    color: white;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}}

QToolBar {{ background: {_BG}; border: none; spacing: 2px; }}
"""
