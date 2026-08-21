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


def _seta(nome: str) -> str:
    """QSS URL for an SVG in ``gui/assets`` (normal paths: Qt doesn't accept
    Windows backslash inside ``url()``)."""
    return (_ASSETS / f"{nome}.svg").as_posix()


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
    /* 520px, não 360px: o Qt (QStyleSheetStyle) clampa o sizeHint calculado
       a partir de max-width -- não é só um teto de layout, ele CORTA o
       texto do botão mais longo do app ("Check airfoil (live preview on
       the right)", ~492px de texto) se o valor for menor que isso. */
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

/* Garante que inputs dentro de diálogos/popups fiquem legíveis (fundo branco, texto escuro)
   e com padding reduzido (evita cortar campos em layouts apertados como o do Matplotlib).
   min-width: evita que os QDoubleSpinBox do SubplotTool sejam comprimidos a ponto de cortar. */
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
/* Seta do dropdown: ver o bloco `_seta` no topo do módulo. Sem estas duas
   regras o combo fica visualmente idêntico a um QLineEdit. */
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
    background: transparent;
}}
/* `width`/`height` REPETIDOS em cada estado, de propósito: o Qt não herda
   essas duas de uma regra menos específica para a sub-parte, e sem elas o
   SVG é desenhado no tamanho natural do widget -- visto na tela, o chevron
   do estado aberto saía gigante, no meio do combo, POR CIMA do texto da
   opção ("Tip + root (both)" ficava cortado atrás dele). */
QComboBox::down-arrow {{ image: url({_seta("chevron-down")}); width: 10px; height: 7px; }}
QComboBox::down-arrow:on {{
    image: url({_seta("chevron-down-accent")}); width: 10px; height: 7px;
}}
QComboBox::down-arrow:disabled {{
    image: url({_seta("chevron-down-disabled")}); width: 10px; height: 7px;
}}
/* espaço à direita para a seta não encostar no texto da opção */
QComboBox {{ padding-right: 24px; }}

/* Botões de passo do spinbox: mesma razão que a seta acima. */
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
    image: url({_seta("spin-up")}); width: 8px; height: 5px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({_seta("spin-down")}); width: 8px; height: 5px;
}}
QSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off,
QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:off {{
    image: url({_seta("spin-up-disabled")});
}}
QSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off,
QDoubleSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:off {{
    image: url({_seta("spin-down-disabled")});
}}
QSpinBox, QDoubleSpinBox {{ padding-right: 20px; }}

QComboBox QAbstractItemView {{
    background: {_CARD};
    border: 1px solid {_BORDER_STRONG};
    selection-background-color: {_ACCENT_SOFT};
    selection-color: {_INK};
}}

/* `padding` vertical, não só `spacing`: uma linha de QFormLayout ocupada
   só por um QCheckBox é mais BAIXA que uma linha de campo (o indicador
   mede menos que um spinbox), e o Qt espaça as linhas pela altura delas
   -- "Enable dynamic stall (Øye)" encostava em "Lag constant A:", e as
   três linhas de "3D rotational effects" liam como um bloco só. */
QCheckBox, QRadioButton {{ spacing: 6px; padding: 4px 0; }}

/* Qualquer regra QSS que mire QCheckBox/QRadioButton (mesmo só
   `spacing`, acima) tira do estilo nativo (Fusion) o desenho do
   indicador e passa a exigir que o QSS desenhe TODAS as sub-partes --
   sem uma regra ``::indicator`` explícita, o indicador sai transparente
   e sem borda: o quadradinho do checkbox desmarcado sumia por completo,
   sem deixar pista de que ali havia um campo marcável. */
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
