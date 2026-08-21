"""Implement GUI tab 7, Results.

Purpose: inspect, compare, export, and report completed runs. Inputs are the
result history and active project from ``AppState``; outputs are plots and
delegated export/report requests, not new solver results. Selection helpers
choose compatible views, while ``api.py`` and visualization modules perform
serialization and rendering.

Labels follow ``nomenclature.py`` and plot titles state the operating
condition. A visualization is a view of an existing solution, so integrated
coefficients do not replace local convergence and physical plausibility checks.
"""

from __future__ import annotations

import io
from collections import OrderedDict
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QDialogButtonBox,
    QStackedWidget,
    QSizePolicy,
    QRadioButton,
    QButtonGroup,
    QProgressDialog,
    QAbstractItemView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QStyle,
    QStyleOptionHeader,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QStylePainter,
    QStyledItemDelegate,
)
from PyQt6.QtCore import Qt, QEvent, QTimer, QRect, QRectF, QSize, QThread
from PyQt6.QtGui import QCursor, QPalette, QTextDocument, QImage

import numpy as np
from matplotlib import cm as plt_cm, colors as plt_colors
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ... import api
from ... import paths
from ...viz import visualization
from ...viz import plots

from typing import TYPE_CHECKING

from ..common import (require_optional_package,
                      parse_list, AppState, show_error, CanvasHost, HAS_INTERACTIVE_PLOTS,
                      PlotlyCanvasHost, symbol_to_plain_text, describe_case_settings,
                      ALINHAMENTO_DE_NUMERO, uniformizar_largura_de_botoes)
from .. import instant_tooltip as _instant_tooltip
from ..instant_tooltip import install_instant_tooltip
from ..workers import ReportWorker, launch_worker


# Data role where widgets in this tab store the symbol as HTML
# ("C<sub>T</sub>") alongside the plain text ("C_T", which remains the
# `text()`/`currentText()` seen by anyone reading the widget from code).
_PAPEL_HTML = int(Qt.ItemDataRole.UserRole) + 11


def _parece_numero(texto: str) -> bool:
    """Is the formatted value numeric (and therefore right-aligned)?"""
    try:
        float(texto)
    except (TypeError, ValueError):
        return False
    return True

#: `QTextDocument` is expensive to build; the header repaints each section
#: on every paint event (dozens of columns, on every scroll). One document
#: per distinct HTML, reused.
_DOCS_DE_HTML: dict[tuple[str, str], QTextDocument] = {}


def _documento_de_html(html: str, cor_nome: str) -> QTextDocument:
    doc = _DOCS_DE_HTML.get((html, cor_nome))
    if doc is None:
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(f'<span style="color:{cor_nome};white-space:pre;">{html}</span>')
        _DOCS_DE_HTML[(html, cor_nome)] = doc
    return doc


def _pintar_html(painter, rect, html: str, cor, alinhar_esquerda: bool = False) -> None:
    """Draws `html` (real subscripts, entities like `&mu;`)
    centered -- or flush left -- within `rect`.

    This is what makes the table header and the field combo show
    "C<sub>T</sub>" as C with a subscript T, instead of the flattened
    "C_T" from `symbol_to_plain_text` (which remains the item's text: it is
    what goes to the clipboard and to anyone reading the widget from code).
    """
    doc = _documento_de_html(html, cor.name())
    largura = doc.idealWidth()
    altura = doc.size().height()
    x = rect.x() + 4 if alinhar_esquerda else rect.x() + max((rect.width() - largura) / 2.0, 2.0)
    y = rect.y() + max((rect.height() - altura) / 2.0, 0.0)
    painter.save()
    painter.translate(x, y)
    doc.drawContents(painter, QRectF(0, 0, max(rect.width() - 4, 1), max(rect.height(), 1)))
    painter.restore()


class _CabecalhoDeSimbolos(QHeaderView):
    """Horizontal header that PAINTS the symbol as rich text.

    A `QTableWidgetItem` does not render HTML, so `C<sub>T</sub>` used to
    arrive here flattened into `C_T` (and `&mu;` into `μ`) via
    `common.symbol_to_plain_text`. This header draws the real subscript
    from the HTML stored in `_PAPEL_HTML`, while keeping the plain text in
    `DisplayRole` -- anyone reading the header from code (tests, "Copy
    table") still sees `C_T`.

    It also fixes the SAME width for every column: the symbols are short
    by construction, and content-based widths made the table uneven
    (besides, `ResizeToContents` measures every cell on each repopulation
    -- expensive with dozens of columns).
    """

    LARGURA_DE_COLUNA = 84

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.setDefaultSectionSize(self.LARGURA_DE_COLUNA)
        self.setHighlightSections(False)

    def _html_da_secao(self, indice_logico: int) -> str | None:
        modelo = self.model()
        if modelo is None:
            return None
        return modelo.headerData(indice_logico, self.orientation(), _PAPEL_HTML)

    def paintSection(self, painter, rect, indice_logico):   # noqa: N802 (API Qt)
        html = self._html_da_secao(indice_logico)
        if not html:
            super().paintSection(painter, rect, indice_logico)
            return
        # Background/border via the style (respects the QSS in
        # `gui/styles.py`), but with EMPTY text -- the text is the rich
        # text drawn right below. Without clearing `opt.text`, the symbol
        # would appear twice, one on top of the other.
        opt = QStyleOptionHeader()
        opt.rect = rect
        opt.section = indice_logico
        opt.text = ""
        opt.orientation = self.orientation()
        opt.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Horizontal
        opt.palette = self.palette()
        painter.save()
        self.style().drawControl(QStyle.ControlElement.CE_Header, opt, painter, self)
        painter.restore()
        _pintar_html(painter, rect, html, self.palette().color(QPalette.ColorRole.WindowText))


class _CabecalhoVerticalDeSimbolos(QHeaderView):
    """Vertical table header that paints the condition labels.

    Condition names are display text, not internal keys: so ``mu_x`` and
    ``alpha_rotor`` need the same rich conversion as the horizontal
    headers.
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.setHighlightSections(False)

    def sectionSizeFromContents(self, indice_logico):  # noqa: N802 (API Qt)
        # `ResizeToContents` measures by DisplayRole by default -- which
        # here is only the short label ("Case 1 - c1"), never the rich
        # HTML that `paintSection` actually draws (longer, with the
        # condition's parameters). Without this the column ended up wide
        # enough for the wrong text and clipped the right one ("Case 2 -
        # μₓ=0.3 (μₓ...").
        modelo = self.model()
        html = (modelo.headerData(indice_logico, self.orientation(), _PAPEL_HTML)
                if modelo is not None else None)
        if not html:
            return super().sectionSizeFromContents(indice_logico)
        doc = _documento_de_html(html, self.palette().color(QPalette.ColorRole.WindowText).name())
        base = super().sectionSizeFromContents(indice_logico)
        largura = max(int(doc.idealWidth()) + 10, base.width())
        altura = max(int(doc.size().height()) + 6, base.height())
        return QSize(largura, altura)

    def paintSection(self, painter, rect, indice_logico):  # noqa: N802 (API Qt)
        modelo = self.model()
        html = (modelo.headerData(indice_logico, self.orientation(), _PAPEL_HTML)
                if modelo is not None else None)
        if not html:
            super().paintSection(painter, rect, indice_logico)
            return
        opt = QStyleOptionHeader()
        opt.rect = rect
        opt.section = indice_logico
        opt.text = ""
        opt.orientation = self.orientation()
        opt.state = QStyle.StateFlag.State_Enabled
        opt.palette = self.palette()
        painter.save()
        self.style().drawControl(QStyle.ControlElement.CE_Header, opt, painter, self)
        painter.restore()
        _pintar_html(painter, rect, html,
                     self.palette().color(QPalette.ColorRole.WindowText),
                     alinhar_esquerda=True)


class _DelegadoDeSimbolos(QStyledItemDelegate):
    """Paints the items of a combo's dropdown LIST as rich text (the
    closed field is painted by `_ComboDeSimbolos.paintEvent`)."""

    def paint(self, painter, option, index):
        html = index.data(_PAPEL_HTML)
        if not html:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget = opt.widget
        estilo = widget.style() if widget is not None else QApplication.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        cor = opt.palette.color(QPalette.ColorGroup.Normal,
                                 QPalette.ColorRole.HighlightedText
                                 if (opt.state & QStyle.StateFlag.State_Selected)
                                 else QPalette.ColorRole.Text)
        # Qt's style reserves the checkbox indicator inside the same
        # rectangle as the text. The previous delegate started at x=4 and
        # painted the description underneath the box; shift the text past
        # the indicator only for items that are actually checkable.
        rect_texto = opt.rect
        if index.flags() & Qt.ItemFlag.ItemIsUserCheckable:
            indicador = estilo.subElementRect(
                QStyle.SubElement.SE_ItemViewItemCheckIndicator,
                opt, widget)
            rect_texto = QRect(
                max(rect_texto.left(), indicador.right() + 8),
                rect_texto.top(),
                max(1, rect_texto.right() - indicador.right() - 8),
                rect_texto.height(),
            )
        _pintar_html(painter, rect_texto, html, cor, alinhar_esquerda=True)


class _ComboDeSimbolos(QComboBox):
    """`QComboBox` whose visible text is rich text (symbol with subscript),
    while `currentText()` still returns the field's raw KEY -- nothing in
    `ResultsTab` needs to know the combo's appearance changed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_DelegadoDeSimbolos(self))

    def adicionar(self, chave: str, html: str, dica: str = "", dado=None) -> None:
        """``chave`` is the RAW text (what `currentText()` returns), ``html``
        the painted symbol, ``dica`` the text shown when hovering the mouse
        over the item, and ``dado`` the `userData` (read via `currentData()`,
        which is how the X/Y/grouping combos identify the quantity)."""
        self.addItem(chave, dado)
        i = self.count() - 1
        self.setItemData(i, html, _PAPEL_HTML)
        if dica:
            self.setItemData(i, dica, Qt.ItemDataRole.ToolTipRole)

    def setCurrentText(self, texto: str) -> None:  # noqa: N802 (API Qt)
        # Compatibility with scripts/tests that used the old labels of the
        # 3D selector; the visible list stays the same as the 2D map's.
        texto = {"Fn (thrust)": "Fn", "Ft (torque)": "Ft"}.get(texto, texto)
        super().setCurrentText(texto)

    def paintEvent(self, event):   # noqa: N802 (API Qt)
        pintor = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        html = self.currentData(_PAPEL_HTML)
        opt.currentText = "" if html else opt.currentText
        pintor.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        if not html:
            pintor.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)
            return
        rect = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, opt,
                                            QStyle.SubControl.SC_ComboBoxEditField, self)
        _pintar_html(pintor, rect, html,
                     self.palette().color(QPalette.ColorRole.Text), alinhar_esquerda=True)


class _CanvasComCache(CanvasHost):
    """`CanvasHost` that KEEPS the already-drawn figures.

    Measured (2 cases, 30x48 mesh, `scratchpad/bench_results_tab.py`):
    building the 11-panel "Coefficients vs axis" grid costs ~384 ms and
    drawing it ~213 ms. Since every mode/selection change called `plot_*`
    again, going back and forth between two plots cost ~600 ms EVERY time
    -- that is the reported "stutter". Here, each combination (mode +
    options + selection) becomes a key: the figure is built once and
    shown again instantly afterwards.

    It also avoids rebuilding the `NavigationToolbar2QT` when the
    displayed canvas has not changed (`CanvasHost._show` destroys and
    recreates it on every call, even for the same canvas).
    """

    _MAX_EM_CACHE = 8

    def __init__(self, with_toolbar: bool = True):
        self._pilha = None
        super().__init__(with_toolbar=with_toolbar)
        self._cache: "OrderedDict[tuple, FigureCanvasQTAgg]" = OrderedDict()

    def _show(self, canvas):
        """Switches the visible canvas WITHOUT removing/re-adding it to
        the layout.

        `CanvasHost._show` does `removeWidget`/`addWidget`: the canvas
        that comes back arrives with new geometry, Qt emits `resize`, and
        matplotlib redraws the whole figure -- meaning the figure cache
        would lose most of its benefit right when re-displaying. A
        `QStackedWidget` keeps every canvas's geometry, and switching
        pages redraws nothing.
        """
        if canvas is self._current:
            return
        if self._pilha is None:
            self._pilha = QStackedWidget(self)
            self._layout.addWidget(self._pilha)
        if self._pilha.indexOf(canvas) < 0:
            self._pilha.addWidget(canvas)
        self._pilha.setCurrentWidget(canvas)
        if self._with_toolbar:
            # The toolbar is bound to ONE canvas; when switching pages it
            # needs to point at the new one (a stale toolbar controls
            # nothing).
            if self._toolbar is not None:
                self._layout.removeWidget(self._toolbar)
                self._toolbar.setParent(None)
                self._toolbar.deleteLater()
            from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
            from PyQt6.QtCore import QSize
            self._toolbar = NavigationToolbar2QT(canvas, self)
            self._toolbar.setIconSize(QSize(15, 15))
            self._layout.insertWidget(0, self._toolbar)
        self._current = canvas

    def limpar_cache(self) -> None:
        """Discards the stored figures -- called when the DATA behind
        them may have changed (history altered, project switched).
        Without this, an entry `id` reused after `clear_history` would
        show the previous project's figure."""
        for canvas in list(self._cache.values()):
            self._descartar(canvas)
        self._cache.clear()

    def _descartar(self, canvas) -> None:
        if self._pilha is not None and self._pilha.indexOf(canvas) >= 0:
            self._pilha.removeWidget(canvas)
        if canvas is self._current:
            self._current = None
        canvas.setParent(None)

    def mostrar_figura(self, chave: tuple, fabrica) -> None:
        """Shows the figure for `chave`, building it with `fabrica()` only
        the first time."""
        canvas = self._cache.get(chave)
        if canvas is not None:
            self._cache.move_to_end(chave)
            self._show(canvas)
            return
        fig = fabrica()
        canvas = FigureCanvasQTAgg(fig)
        self._cache[chave] = canvas
        while len(self._cache) > self._MAX_EM_CACHE:
            _, velho = self._cache.popitem(last=False)
            self._descartar(velho)
        self._show(canvas)
        canvas.draw()

if TYPE_CHECKING:            # only for annotations: a real import would be a cycle
    from .geometria import GeometryTab
    from .aerofolio import AirfoilTab


# =============================================================================
# Tab 7 -- Results: single hub for 2D/3D/Results visualization (docs/plano.md
# Section 8). The only tab that draws on screen (principle 5).
# =============================================================================

class ResultsTab(QWidget):
    """"Results" tab -- Results hub (docs/plano_v3.md Part 4). Replaces
    the old `PlotsTab`, which only saw `AppState.last_results` (the most
    recent result, overwritten on every Run Case/Run Batch): now the list
    on the left shows the ENTIRE result history of this session
    (`AppState.results_history`), with multiple selection via checkbox,
    and the plot modes on the right enable/disable depending on whether
    the selection is valid for each one (progressive disclosure,
    docs/plano.md principle 3).

    "Airfoil" migrated to the Airfoil tab's own embedded canvas
    (docs/plano_v3.md Part 5) and was removed from here. "Geometry"
    migrated to the Geometry tab's embedded canvas (docs/plano_v3.md Part
    6) and was also removed from here -- same logic: INPUT tabs have a
    live preview of what they are defining; Results is dedicated to
    SIMULATION RESULTS (needs the engine to have run to have anything to
    show).
    """
    # "Convergence" goes at the END of the list on purpose:
    # `_MODES.index(...)` is used by tests and by the `options_stack`
    # order, and inserting in the middle would silently shift every
    # existing index.
    #: "Insufficient selection" messages, in ONE place only: they used to
    #: appear hand-written in four spots (tooltip of the disabled mode and
    #: text on the canvas), which had already left two of them in
    #: Portuguese while the rest of the window was in English.
    _AVISO_AO_MENOS_UM = (
        "Select at least one result in the list on the left.")

    _MODES = ["Disk map", "Coefficients vs axis", "Azimuth / Radius", "3D", "Table", "Convergence"]
    _SINGLE_RESULT_MODES = {"Disk map", "Azimuth / Radius", "3D", "Convergence"}
    _FACTORIAL_AXES = ["mu_x", "alpha_deg", "collective_deg", "rpm"]

    # Bug 4: names aligned with the actual keys of result.maps and with
    # plots._DISK_GRID_FIELDS — "alpha" → "alpha_eff", "lambda" → "lambda_z_field".
    _DISK_FIELDS = ["lambda_i", "Fn", "Ft", "Cl", "Cd", "Vi", "Up", "Ut", "W", "alpha_eff", "phi",
                     "lambda_z_field", "Ft_i", "Ft_p", "Mach", "q"]
    _EXPORT_FIELD_KEYS = {
        "Fn (thrust)": "fn", "Ft (torque)": "ft", "alpha_eff": "alpha",
        "lambda_i": "lambda_i", "Cl": "cl", "Cd": "cd", "Mach": "mach",
    }
    #: Item of the HEIGHT selector that gives the flat disc (no relief) --
    #: replaces the old "raise the disc by the field value" checkbox.
    _SEM_RELEVO_3D = "(flat disc)"

    # --- axis convention for the columns (rotor vs. propeller) -----------
    def _modo_helice(self) -> bool:
        return bool(self.state.is_propeller()) if self.state is not None else False

    def _simbolos(self) -> dict:
        """Symbols/descriptions of the columns in the mode's axis
        convention.

        In propeller mode the x axis is the rotor's, so `Vz` reads as
        V_inf,x and `J_z` reads as J_x (see `api.summary_symbols`). The
        on-screen table and the report's read from the SAME source -- two
        different answers for the same column would be worse than one
        wrong one."""
        return {
            chave: (simbolo, api._descricao_com_simbolos(descricao))
            for chave, (simbolo, descricao)
            in api.summary_symbols(self._modo_helice()).items()
        }

    def __init__(self, state: AppState, geometry_tab: GeometryTab, airfoil_tab: AirfoilTab):
        super().__init__()
        self.state = state
        self._geometry_tab = geometry_tab
        self._airfoil_tab = airfoil_tab
        self._report_thread = None
        self._report_worker = None

        outer = QHBoxLayout(self)

        # --- left panel: result history + modes ---------------------------
        # `QGroupBox`, not a bold `QLabel`: block help matches the TITLE of
        # a groupbox, and while this panel was a loose label the written
        # content about how to read the results had nowhere to open from
        # in the window.
        selecao_box = QGroupBox("Results from this session")
        left = QVBoxLayout(selecao_box)
        # Debounce the redraw when checking/unchecking cases -- same
        # pattern (~150ms, single-shot) that `_preview_timer` already uses
        # in the Geometry/Airfoil tabs for the live preview.
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(150)
        self._selection_timer.timeout.connect(self._on_selection_changed)

        self.history_list = QListWidget()
        # The list keeps the raw label for selection/copy, but paints the
        # mathematical notation with the same delegate as the combos.
        self.history_list.setItemDelegate(_DelegadoDeSimbolos(self.history_list))
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.history_list.itemChanged.connect(self._on_history_item_changed)
        # Delete history entry/entries: right-click (context menu) or the
        # Delete/Backspace key with one or more rows selected (normal Qt
        # selection -- different from the checkboxes, which decide what
        # goes into the plot). Without this the history only grows (this
        # was intentional at first, Part 4.1, but a long session with many
        # experimental cases accumulates clutter that cannot be cleared
        # without closing the whole project).
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._show_history_context_menu)
        self.history_list.installEventFilter(self)
        left.addWidget(self.history_list)
        hist_btn_row = QHBoxLayout()
        btn_sel_all = QPushButton("Select all")
        btn_sel_all.setToolTip("Selects every entry in the list — nothing is added or removed")
        btn_sel_all.clicked.connect(self._select_all_history)
        # "Clear" and "Delete" side by side did not say which deselected
        # and which deleted: the two labels now name the object of the
        # action.
        btn_clear_sel = QPushButton("Clear selection")
        btn_clear_sel.setToolTip(
            "Deselects everything — the entries stay in the list")
        btn_clear_sel.clicked.connect(self._clear_history_selection)
        btn_delete = QPushButton("Delete entries")
        btn_delete.setToolTip(
            "Removes the selected entries from this session's history for good "
            "(the Delete key does the same)")
        btn_delete.clicked.connect(self._delete_selected_history_entries)
        hist_btn_row.addWidget(btn_sel_all)
        hist_btn_row.addWidget(btn_clear_sel)
        hist_btn_row.addWidget(btn_delete)
        hist_btn_row.addStretch(1)
        left.addLayout(hist_btn_row)
        #: the three read as a set (they act on the same list): same
        #: width, applied in `showEvent` -- see
        #: `common.uniformizar_largura_de_botoes`.
        self._botoes_de_historico = (btn_sel_all, btn_clear_sel, btn_delete)

        left.addWidget(QLabel("<b>What to view</b>"))
        self.mode_list = QListWidget()
        for m in self._MODES:
            self.mode_list.addItem(QListWidgetItem(m))
        self.mode_list.setCurrentRow(0)
        self.mode_list.currentRowChanged.connect(self._on_mode_changed)
        left.addWidget(self.mode_list)
        outer.addWidget(selecao_box, stretch=1)

        # --- right panel: sub-selection + mode options + canvas -----------
        right = QVBoxLayout()

        # CONDITION selector (progressive disclosure): appears whenever
        # the current selection holds 2+ conditions -- whether from a
        # batch, several Run Cases, or a mix of both -- and the current
        # mode draws one condition at a time. Before, it only existed for
        # ONE selected batch, and so checking six Run Cases disabled the
        # disk/azimuth/3D/convergence modes instead of letting the user
        # choose which one to plot.
        self.condition_row = QWidget()
        bs_layout = QHBoxLayout(self.condition_row)
        bs_layout.setContentsMargins(0, 0, 0, 0)
        bs_layout.addWidget(QLabel("Choose condition to plot:"))
        self.condition_combo = _ComboDeSimbolos()
        self.condition_combo.setToolTip(
            "Which single condition of the current selection is shown. Views "
            "that draw one disc or one blade at a time need one condition; "
            "this picks it without re-running anything.")
        # A large selection (a whole factorial) arrives here with
        # hundreds of items. `combobox-popup: 0` restores the SCROLLABLE
        # LIST behavior to the dropdown, respecting `maxVisibleItems` --
        # without it the native style tries to open a menu with every
        # item, which on a long list turns into a screen-sized popup.
        self.condition_combo.setStyleSheet("QComboBox { combobox-popup: 0; }")
        self.condition_combo.setMaxVisibleItems(20)
        self.condition_combo.currentIndexChanged.connect(self._agendar_redesenho)
        bs_layout.addWidget(self.condition_combo)
        # The `stretch` sits in the SPACE TO THE RIGHT, not on the combo:
        # with it on the combo the widget was pushed to the far right of
        # the panel, away from its own label (the combo's width is fixed
        # by `_ajustar_largura_da_combo_de_condicao`, from the items' text).
        bs_layout.addStretch(1)
        self.condition_row.setVisible(False)
        #: Labels currently in the combo -- avoids repopulating (and
        #: losing the user's choice) when the selection has not changed.
        self._rotulos_de_condicao: list[str] = []
        right.addWidget(self.condition_row)

        self.options_stack = QStackedWidget()
        for builder in (self._build_disk_options, self._build_axis_options,
                        self._build_azrad_options, self._build_3d_options,
                        self._build_table_options, self._build_convergence_options):
            self.options_stack.addWidget(builder())
        # The options strip occupies the height of the CURRENT panel, not
        # the tallest one. A `QStackedWidget` requests the height of the
        # tallest of all its children, and the tallest panel here (the
        # "Coefficients vs axis" mode, with two blocks of controls)
        # reserved a ~200px blank strip above the plot in EVERY other mode
        # -- the disk maps ended up squeezed under an empty gap. `Ignored`
        # vertically does the filtering: the hidden widget stops having a
        # say on the height.
        for i in range(self.options_stack.count()):
            self.options_stack.widget(i).setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.options_stack.setSizePolicy(QSizePolicy.Policy.Preferred,
                                          QSizePolicy.Policy.Maximum)
        self.options_stack.currentChanged.connect(self._ajustar_altura_das_opcoes)
        right.addWidget(self.options_stack)

        # Canvas stacked widget: matplotlib (eager, always available) + Plotly (lazy) + Table
        self.canvas_host = _CanvasComCache(with_toolbar=True)
        self.plotly_host = None  # Lazily initialized in _refresh_axis if HAS_INTERACTIVE_PLOTS
        self.table_widget = QTableWidget()
        self.table_widget.setHorizontalHeader(_CabecalhoDeSimbolos(self.table_widget))
        self.table_widget.setVerticalHeader(_CabecalhoVerticalDeSimbolos(self.table_widget))
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setWordWrap(False)
        header = self.table_widget.horizontalHeader()
        header.setMinimumSectionSize(_CabecalhoDeSimbolos.LARGURA_DE_COLUNA)
        # Instant header tooltip: installed ONCE (before it was
        # reinstalled on every `_refresh_table`, stacking an event filter
        # per repopulation -- 10 refreshes = 10 filters firing on every
        # mouse move, and balloons that outlived the previous one).
        self._dica_watchdog = QTimer(self)
        self._dica_watchdog.setSingleShot(True)
        self._dica_watchdog.setInterval(400)
        self._dica_watchdog.timeout.connect(self._esconder_dica_se_o_mouse_saiu)
        install_instant_tooltip(self.table_widget.horizontalHeader(), self._dica_do_cabecalho)
        self.canvas_stack = QStackedWidget()
        self.canvas_stack.addWidget(self.canvas_host)  # Index 0: matplotlib
        # Plotly's own index is captured dynamically where it's lazily added
        # (`self._plotly_stack_index`) instead of a hardcoded "1" -- adding
        # Table here would otherwise silently claim that slot and break
        # every `setCurrentIndex(1)  # Show Plotly` call site.
        self._plotly_stack_index = None
        self._table_stack_index = self.canvas_stack.addWidget(self.table_widget)
        right.addWidget(self.canvas_stack, stretch=1)

        # Batch export of disk maps (Part 4.3): visible whenever there is
        # at least 1 checked condition -- the entire selection is treated
        # as a batch (item 27).
        export_row = QHBoxLayout()
        export_row.addWidget(QLabel("Plot backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Matplotlib", "matplotlib")
        self.backend_combo.addItem("Plotly", "plotly")
        self.backend_combo.view().setMinimumWidth(self.backend_combo.sizeHint().width())
        # Stays ENABLED without the package: choosing "Plotly" opens the
        # dialog with the install command (`_on_backend_changed`) and
        # reverts to Matplotlib. Disabled, the combo only stated the
        # reason in a tooltip.
        #
        # The BASE tooltip is always written, and the restriction is
        # APPENDED to it (same fix already made for the dynamic-stall
        # box): before, with the package installed, the combo had no
        # tooltip at all -- the only silent field in the window.
        dica_de_backend = (
            "Renderer for the plots on the right. Matplotlib draws a static "
            "figure; Plotly draws an interactive one (zoom, pan, hover, and "
            "clicking a legend entry hides that curve).")
        if not HAS_INTERACTIVE_PLOTS:
            dica_de_backend += ("\n\nPlotly needs an optional package — select it "
                                "for install instructions.")
        self.backend_combo.setToolTip(dica_de_backend)
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        export_row.addWidget(self.backend_combo)
        # The old name ("Export batch disk maps…") promised less than the
        # button does: it exports the maps of EVERY checked condition,
        # whether they came from a batch or not. The "(selection)" that
        # came after it is also gone: the button only exists when there
        # is a selection, and the dialog it opens already shows how many
        # cases will be exported -- the word in parentheses only bloated
        # the label.
        # ONE export button, which exports WHAT IS ON SCREEN. It used to
        # be "Export disk maps…", present in every mode: in 3D mode, in
        # Azimuth/Radius, or in the table, the tab's only export button
        # offered disk maps -- the plot the user was NOT looking at. The
        # label now names what comes out (see `_EXPORTACAO_POR_MODO`), and
        # the same applies to "Copy".
        self.btn_export = QPushButton("Export…")
        self.btn_export.setVisible(False)
        self.btn_export.clicked.connect(self._exportar_da_tela)
        export_row.addWidget(self.btn_export)

        # "Generate report" / "Copy table": 1 click -> single, self-
        # contained HTML. The assembly lives in `api.generate_report`, so
        # this button, the CLI's `--report`, and a Python script produce
        # the same file.
        self.btn_generate_report = QPushButton("Generate report…")
        self.btn_generate_report.clicked.connect(self._generate_report)
        export_row.addWidget(self.btn_generate_report)
        self.btn_copy = QPushButton("Copy")
        self.btn_copy.clicked.connect(self._copiar_da_tela)
        export_row.addWidget(self.btn_copy)
        #: the three in the bottom strip with the SAME width -- measured
        #: in `showEvent`, once the QSS has already been applied (see
        #: `common.uniformizar_largura_de_botoes`)
        self._botoes_de_exportacao = (self.btn_export, self.btn_generate_report,
                                       self.btn_copy)
        export_row.addStretch(1)
        right.addLayout(export_row)

        outer.addLayout(right, stretch=3)

        self.state.history_changed.connect(self._on_history_changed)
        self.state.project_changed.connect(self._on_project_changed)
        # `mask_reverse_flow_plots` lives in the project's `config`: the
        # checkbox has to reflect what was loaded from the `.bemt` (or
        # whatever the CLI/another tab has changed), not a screen default.
        self.state.config_changed.connect(self._sincronizar_mascara_com_o_projeto)

        self._sincronizar_mascara_com_o_projeto()
        self._refresh_history_list()
        self._update_mode_availability()
        self._refresh_current()

    # --- default destination for EVERY export in this tab ----------------

    def _pasta_de_saida_padrao(self, criar: bool = True) -> Path:
        """`outputs/` folder of the open project -- DEFAULT destination
        for every export in this tab (report, disk maps, 3D screenshots).

        Every dialog here used to open wherever the previous one had
        stopped (or the process's working directory, which on a Windows
        shortcut is `C:\\Windows\\System32`): a project's figures ended
        up scattered outside it. The path is NOT assembled by hand -- it
        is the same `"outputs"` entry from `models.default_project_paths`,
        re-exported by `api`, that the CLI and `api.export_results` use;
        this way the GUI and CLI cannot disagree about where a project's
        outputs live.

        With no project open it falls back to `paths.outputs_dir()`
        (`ZBEMT_OUTPUTS` > `<repo>/outputs` > `~/.zbemt/outputs`), which is
        the CLI's same default in that situation.
        """
        projeto = self.state.project
        if projeto is not None and projeto.path:
            destino = Path(api.default_project_paths(projeto.path)["outputs"])
        else:
            destino = paths.outputs_dir()
        if criar:
            # Failing to create it (full disk, read-only folder) must not
            # bring the dialog down: it still opens at the path, and
            # whoever actually writes (`api.export_results`) reports the
            # real error.
            try:
                destino.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        return destino

    def _current_mode(self) -> str:
        return self._MODES[max(self.mode_list.currentRow(), 0)]

    def _maybe_refresh(self, mode: str):
        if self._current_mode() == mode:
            self._refresh_current()

    def _on_project_changed(self):
        # New project: the stored figures describe the PREVIOUS project's
        # results (and `clear_history` resets the id counter, so a cache
        # key could even coincide).
        self.canvas_host.limpar_cache()
        self._refresh_current()

    def _assinatura_da_selecao(self) -> tuple:
        """Cache key identifying WHAT is selected: ids of the checked
        entries + the condition chosen in the combo."""
        return (tuple(e.id for e in self._selected_entries()),
                self.condition_combo.currentIndex())

    def _on_backend_changed(self, _index: int):
        if (self.backend_combo.currentData() == "plotly"
                and not require_optional_package(self, "interactive")):
            self.backend_combo.blockSignals(True)
            self.backend_combo.setCurrentIndex(0)   # falls back to Matplotlib
            self.backend_combo.blockSignals(False)
        self._agendar_redesenho()

    def _wants_plotly(self) -> bool:
        return HAS_INTERACTIVE_PLOTS and self.backend_combo.currentData() == "plotly"

    def _on_mode_changed(self, row: int):
        self.options_stack.setCurrentIndex(max(row, 0))
        self._update_condition_selector()
        # Export/Copy name what comes out of THIS mode -- see
        # `_EXPORTACAO_POR_MODO`.
        self._atualizar_botoes_de_exportacao()
        # The table is cheap and keeps appearing immediately. The other
        # modes can build a heavy Matplotlib/Plotly figure; when switching
        # rapidly between modes, showing an intermediate state and
        # coalescing the redraw avoids blocking the window once per click.
        if self._current_mode() == "Table":
            self._refresh_current()
        else:
            self.canvas_host.show_message("Rendering selected result…")
            self._agendar_redesenho()

    def _agendar_redesenho(self, *_args):
        """Schedules a single redraw for mode/option changes.

        The history selection already uses this same timer. Reusing it
        here makes a sequence of clicks on mode, backend, or batch
        condition result in a single figure build, with no intermediate
        work discarded right after.
        """
        self._selection_timer.start()

    def _refresh_current(self):
        mode = self._current_mode()
        try:
            if mode == "Disk map":
                self._refresh_disk()
            elif mode == "Coefficients vs axis":
                self._refresh_axis()
            elif mode == "Azimuth / Radius":
                self._refresh_azrad()
            elif mode == "3D":
                self._refresh_3d_preview()
            elif mode == "Table":
                self.canvas_stack.setCurrentIndex(self._table_stack_index)
                self._refresh_table()
            elif mode == "Convergence":
                self._refresh_convergence()
        except Exception as exc:
            self.canvas_host.show_message(f"Could not draw this view: {exc}")

    # --- result history (Part 4.1) ----------------------------------------

    def _refresh_history_list(self):
        checked_ids = {
            self.history_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.history_list.count())
            if self.history_list.item(i).checkState() == Qt.CheckState.Checked
        }
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for entry in self.state.results_history:
            texto = f"{entry.label}   ·   {entry.timestamp}"
            item = QListWidgetItem(texto)
            item.setData(_PAPEL_HTML, api._descricao_com_simbolos(texto))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            item.setCheckState(Qt.CheckState.Checked if entry.id in checked_ids
                                else Qt.CheckState.Unchecked)
            self.history_list.addItem(item)
        self.history_list.blockSignals(False)

    def _on_history_changed(self):
        # New run: automatically checks the newly arrived entry (see the
        # result that just ran right away), preserving the checks already
        # set from previous runs.
        prev_count = self.history_list.count()
        self.canvas_host.limpar_cache()   # history changed: nothing in cache is valid
        self._refresh_history_list()
        if self.history_list.count() > prev_count:
            self.history_list.blockSignals(True)
            self.history_list.item(self.history_list.count() - 1).setCheckState(Qt.CheckState.Checked)
            self.history_list.blockSignals(False)
        self._on_selection_changed()

    def _select_all_history(self):
        self.history_list.blockSignals(True)
        for i in range(self.history_list.count()):
            self.history_list.item(i).setCheckState(Qt.CheckState.Checked)
        self.history_list.blockSignals(False)
        self._on_selection_changed()

    def _clear_history_selection(self):
        self.history_list.blockSignals(True)
        for i in range(self.history_list.count()):
            self.history_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.history_list.blockSignals(False)
        self._on_selection_changed()

    def _delete_selected_history_entries(self):
        """Removes from the history the HIGHLIGHTED rows (normal Qt
        selection via click/Ctrl+click) -- independent of the checkboxes,
        which decide what goes into the plot. With nothing highlighted,
        does nothing (avoids deleting everything by accident when
        clicking "Delete selected" unintentionally)."""
        ids = {item.data(Qt.ItemDataRole.UserRole)
               for item in self.history_list.selectedItems()}
        if not ids:
            return
        for entry_id in ids:
            self.state.remove_history_entry(entry_id)

    def _ajustar_altura_das_opcoes(self, *_args):
        """Makes the options strip shrink/grow to fit the current panel.

        With `Ignored` vertically on every panel (see the construction of
        `options_stack`), the only one that can dictate the height is the
        VISIBLE one -- so it goes back to `Preferred` and the others
        become `Ignored`. Without this, the `QStackedWidget` would keep
        requesting the height of the tallest panel and stealing space from
        the plot."""
        atual = self.options_stack.currentWidget()
        for i in range(self.options_stack.count()):
            w = self.options_stack.widget(i)
            w.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Preferred if w is atual else QSizePolicy.Policy.Ignored)
        if atual is not None:
            atual.adjustSize()
        self.options_stack.adjustSize()
        self.options_stack.updateGeometry()

    def showEvent(self, event):
        """Equalizes the width of the three history buttons on the FIRST
        display -- it is only after the QSS polish that a button's
        `sizeHint` reflects the theme's padding (see
        `common.uniformizar_largura_de_botoes`)."""
        super().showEvent(event)
        if not getattr(self, "_larguras_revistas", False):
            self._larguras_revistas = True
            uniformizar_largura_de_botoes(self._botoes_de_historico)
            # ...and the three export/copy/report ones, for the same
            # reason: "Export plots…" and "Copy figure" have different
            # lengths and change text with the mode, so the width has to
            # be that of the LONGEST label of any mode, not the current
            # one.
            uniformizar_largura_de_botoes(
                self._botoes_de_exportacao,
                rotulos_extras=self._rotulos_de_exportacao())
            # The first display is also when the options strip can
            # finally measure the current panel (before the theme polish
            # the `sizeHint` is not valid yet).
            self._ajustar_altura_das_opcoes()

    def eventFilter(self, obj, event):
        if obj is self.history_list and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self._delete_selected_history_entries()
                return True
        return super().eventFilter(obj, event)

    def _show_history_context_menu(self, pos):
        item = self.history_list.itemAt(pos)
        if item is None:
            return
        if item not in self.history_list.selectedItems():
            self.history_list.setCurrentItem(item)
        menu = QMenu(self)
        n = len(self.history_list.selectedItems())
        acao = menu.addAction(f"Delete {n} entrie(s)" if n > 1 else "Delete")
        if menu.exec(self.history_list.mapToGlobal(pos)) == acao:
            self._delete_selected_history_entries()

    def _on_history_item_changed(self, _item):
        """Checking/unchecking a history box used to redraw the WHOLE
        canvas right away, synchronously (~30ms). Checking five cases =
        five full matplotlib redraws, one per click, each freezing the
        window -- that was the "stutter" when choosing what to plot.

        Whatever is CHEAP (enabling/disabling modes, showing buttons)
        stays synchronous, otherwise the mode list would momentarily lie
        about what can be plotted; only the REDRAW is deferred, and
        successive clicks restart the timer, so a burst becomes a single
        draw."""
        self._atualizar_estado_da_selecao()
        self._selection_timer.start()

    def _atualizar_estado_da_selecao(self):
        """Cheap part of `_on_selection_changed`: only enables/disables
        controls according to the selection, without drawing anything."""
        self._update_mode_availability()
        self._update_condition_selector()
        # Item 27: several checked conditions -- whether from a batch,
        # loose Run Cases, or a mix -- are treated AS ONE BATCH: the whole
        # set is exported. The button used to appear only when there was
        # a literal entry of type "batch" in the selection.
        self._atualizar_botoes_de_exportacao()
        has_single = self._resolve_single_result() is not None
        self.btn_export_load.setEnabled(visualization.is_available() and has_single)

    def _on_selection_changed(self):
        self._atualizar_estado_da_selecao()
        self._refresh_current()

    def _selected_entries(self) -> list:
        """``ResultEntry`` checked in the history list, in the order they
        appear in it (execution order)."""
        by_id = {e.id: e for e in self.state.results_history}
        out = []
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                entry = by_id.get(item.data(Qt.ItemDataRole.UserRole))
                if entry is not None:
                    out.append(entry)
        return out

    def _update_mode_availability(self):
        """Enables/disables (never hides) each mode according to whether
        the current selection is valid for it.

        The boundary CHANGED (item 13.1): what separates the modes is no
        longer "how many entries are checked" but "is there at least one
        condition to draw". The modes that show one condition at a time
        (disk, azimuth/radius, 3D, convergence) draw the condition chosen
        in the `condition_combo`, which is populated with EVERY condition
        of the selection -- batches, loose cases, or a mix of both.
        Before, they required exactly 1 checked entry, and so six checked
        Run Cases plotted nothing."""
        ok = len(self._condicoes_selecionadas()[0]) >= 1
        dica = "" if ok else self._AVISO_AO_MENOS_UM
        for name in self._MODES:
            self._set_mode_item_enabled(name, ok, dica)

    def _set_mode_item_enabled(self, name: str, enabled: bool, tooltip: str):
        for i in range(self.mode_list.count()):
            item = self.mode_list.item(i)
            if item.text() != name:
                continue
            flags = item.flags()
            item.setFlags((flags | Qt.ItemFlag.ItemIsEnabled) if enabled
                           else (flags & ~Qt.ItemFlag.ItemIsEnabled))
            item.setToolTip(tooltip)

    def _condicoes_selecionadas(self) -> tuple[list, list[str]]:
        """Flattens the selection -- loose cases, batches, or the two
        mixed together -- into a SINGLE list of ``Results``, with a
        readable label per condition.

        This is the list that feeds the condition combo and every
        one-condition-at-a-time mode. The numbering comes from
        `api.condition_labels` (which only appends the name when it
        actually distinguishes the conditions -- the GUI names every Run
        Case "case"); with 2+ checked entries the history's label is
        joined in as well, otherwise two identically-named conditions from
        different runs would be indistinguishable in the combo."""
        entries = self._selected_entries()
        flat = plots.flatten_selection(entries)
        if not flat:
            return [], []
        rotulos = api.condition_labels(flat)
        if len(entries) > 1:
            origem = []
            for e in entries:
                n = len(e.results) if e.kind == "batch" else 1
                origem.extend([e.label] * n)
            rotulos = [f"{r}  ·  {o}" for r, o in zip(rotulos, origem)]
        return flat, rotulos

    def _update_condition_selector(self):
        """Syncs the condition combo with the current selection.

        Idempotent and cheap when nothing has changed (compares the
        labels), which allows calling it from `_resolve_single_result`
        at no cost."""
        flat, rotulos = self._condicoes_selecionadas()
        # With a single condition there is nothing to choose; the row
        # disappears (progressive disclosure) but the combo stays
        # consistent.
        self.condition_row.setVisible(
            self._current_mode() in self._SINGLE_RESULT_MODES and len(flat) > 1)
        if rotulos == self._rotulos_de_condicao:
            return
        anterior = self.condition_combo.currentText()
        self._rotulos_de_condicao = rotulos
        self.condition_combo.blockSignals(True)
        self.condition_combo.clear()
        for rotulo in rotulos:
            simbolo = api._descricao_com_simbolos(rotulo)
            dica = (
                f"<b>{simbolo}</b><br><br>"
                "Selects this flight condition for the single-condition "
                "plotting views. The displayed symbols follow the vehicle-fixed "
                "x/z convention."
            )
            self.condition_combo.adicionar(rotulo, simbolo, dica, dado=rotulo)
        idx = self.condition_combo.findText(anterior)
        self.condition_combo.setCurrentIndex(idx if idx >= 0 else (0 if rotulos else -1))
        self.condition_combo.blockSignals(False)
        self._ajustar_largura_da_combo_de_condicao(rotulos)

    #: Ceiling for the condition combo's width, in pixels. A very long
    #: label cannot push the rest of the panel off the screen; past this
    #: point the text elides and the tooltip/dropdown show the whole
    #: label.
    _LARGURA_MAXIMA_DA_COMBO = 620
    #: Labels measured to size the combo. With a large factorial the list
    #: has hundreds of items and measuring all of them would be wasted
    #: work -- the labels have a fixed format, the first ones already
    #: give the measure.
    _ROTULOS_MEDIDOS = 120

    def _ajustar_largura_da_combo_de_condicao(self, rotulos: list[str]) -> None:
        """Gives the combo enough width to SHOW the condition's text.

        Without this it stayed at the minimum size and elided exactly the
        part that identifies the condition. The dropdown list gets the
        same width, for the same reason."""
        if not rotulos:
            return
        fm = self.condition_combo.fontMetrics()
        largura = max(fm.horizontalAdvance(r) for r in rotulos[:self._ROTULOS_MEDIDOS])
        # Margin for the combo's arrow, the borders, and the dropdown
        # list's scrollbar (which appears once there are many items).
        largura = min(largura + 60, self._LARGURA_MAXIMA_DA_COMBO)
        self.condition_combo.setMinimumWidth(largura)
        self.condition_combo.view().setMinimumWidth(largura)

    def _resolve_single_result(self):
        """``Results`` of the condition CHOSEN in the combo, for the
        modes that draw one condition at a time (disk, azimuth/radius,
        3D, convergence); `None` only when the selection has no
        condition at all (nothing checked, or only empty batches).

        The combo is synced here on purpose: any path that resolves the
        active condition goes through this method, so none of them can
        read an index from a stale list."""
        self._update_condition_selector()
        flat, _ = self._condicoes_selecionadas()
        if not flat:
            return None
        idx = min(max(self.condition_combo.currentIndex(), 0), len(flat) - 1)
        return flat[idx]

    # --- 3) Disk map -----------------------------------------------------

    def _build_disk_options(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Field:"))
        # Combo with the short SYMBOL rendered (λ_i, F_n, C_L…), not the
        # field's raw key; the key remains `currentText()`, and the
        # spelled-out name goes into each item's tooltip.
        self.disk_field_combo = _ComboDeSimbolos()
        self.disk_field_combo.adicionar("(grid with all fields)",
                                         "All fields",
                                         "Every disk map at once on one screen")
        for campo in self._DISK_FIELDS:
            # The tip is the quantity in PROSE (the raw key is already
            # the item's text; repeating it in the tip would say nothing
            # to someone who does not already know it).
            self.disk_field_combo.adicionar(
                campo, plots.disk_field_symbol_html(campo),
                self._dica_de_campo_de_disco(campo))
        self.disk_field_combo.setMinimumWidth(150)
        self.disk_field_combo.setToolTip(
            "'(grid with all fields)' shows every disk map at once on one screen; picking a "
            "single field gives that one disc the whole canvas, with the colour-scale controls "
            "next to it enabled (log scale, manual min/max).")
        row1.addWidget(self.disk_field_combo)
        # Item 10: this is the ONLY home of `mask_reverse_flow_plots` in
        # the GUI. It used to also appear in the Airfoil tab, among
        # physics options -- and it is not physics: it masks ONLY THE
        # DRAWING (`viz/plots.py`), never the computed forces nor the
        # exported CSV/report. A drawing control belongs in the tab that
        # draws.
        self.disk_mask_check = QCheckBox("Mask reverse flow in disk plots")
        self.disk_mask_check.setToolTip(
            '"mask_reverse_flow_plots" — hides the region Ut<0 in disk maps. '
            "Purely visual: forces, summary and exported data are identical "
            "either way. The setting is stored in the project's .bemt config.")
        self.disk_mask_check.setChecked(True)
        row1.addWidget(self.disk_mask_check)
        btn = QPushButton("Refresh")
        btn.clicked.connect(self._refresh_disk)
        row1.addWidget(btn)
        row1.addStretch(1)
        layout.addLayout(row1)

        # COLOUR scale of the contour (not the same thing as x/y axis
        # zoom/scale -- that part already comes for free from
        # matplotlib's toolbar on each canvas, see
        # `CanvasHost(with_toolbar=True)`; a `tricontourf`'s colour bar
        # does not appear in matplotlib's "Edit axis" dialog, so it needs
        # its own control here).
        # Only applies to a single field -- in the grid with all 12
        # fields each one has a different quantity/range, a single
        # min/max would not make sense there.
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Color scale:"))
        self.disk_color_scale_combo = QComboBox()
        self.disk_color_scale_combo.addItems(["linear", "log"])
        self.disk_color_scale_combo.setToolTip(
            "How field values map to colour. A logarithmic scale spreads the "
            "low end of the range and is what makes a field whose extreme "
            "values sit in a handful of elements — a tip vortex, a reverse-flow "
            "pocket — readable instead of a single bright spot on a flat "
            "background. It needs values of one sign.")
        row2.addWidget(self.disk_color_scale_combo)
        row2.addWidget(QLabel("min.:"))
        self.disk_color_vmin_edit = QLineEdit()
        self.disk_color_vmin_edit.setPlaceholderText("auto")
        self.disk_color_vmin_edit.setMaximumWidth(80)
        self.disk_color_vmin_edit.setToolTip(
            "Value pinned to the bottom of the colour scale. Left on auto it "
            "follows the data; set by hand it lets two conditions be compared "
            "on the same scale, which auto-scaling would otherwise hide.")
        row2.addWidget(self.disk_color_vmin_edit)
        row2.addWidget(QLabel("max.:"))
        self.disk_color_vmax_edit = QLineEdit()
        self.disk_color_vmax_edit.setPlaceholderText("auto")
        self.disk_color_vmax_edit.setMaximumWidth(80)
        self.disk_color_vmax_edit.setToolTip(
            "Value pinned to the top of the colour scale. Set it below the "
            "data maximum to keep a few extreme elements from flattening the "
            "rest of the disc; the colour bar grows an arrow to show that the "
            "range was clipped.")
        row2.addWidget(self.disk_color_vmax_edit)
        color_note = QLabel("Applies to a single field; the all-fields grid scales each map on its own.")
        color_note.setStyleSheet("color: gray; font-size: 10px;")
        row2.addStretch(1)
        layout.addLayout(row2)
        layout.addWidget(color_note)

        self.disk_field_combo.currentTextChanged.connect(self._update_disk_color_controls_enabled)
        # Switching field/mask redraws right away: with the figure cache
        # (`_CanvasComCache`) going back and forth between fields is
        # instantaneous, so there is no reason to require a click on
        # "Refresh" for every switch.
        self.disk_field_combo.currentTextChanged.connect(self._refresh_disk)
        self.disk_mask_check.toggled.connect(self._on_disk_mask_toggled)
        self._update_disk_color_controls_enabled()
        return box

    def _on_disk_mask_toggled(self, marcado: bool):
        """Writes the choice to the project's `config` and redraws.

        The checkbox owns the `.bemt` field `mask_reverse_flow_plots`, not
        a screen-only state: without writing it, the setting would vanish
        when the project is saved, and GUI/`.bemt`/CLI parity would be
        lost right on the field that just moved out of the Airfoil tab."""
        projeto = self.state.project
        if projeto is not None and bool(
                projeto.config.get("mask_reverse_flow_plots", True)) != marcado:
            projeto.config["mask_reverse_flow_plots"] = marcado
            self.state.notify_config()
        self._refresh_disk()

    def _sincronizar_mascara_com_o_projeto(self):
        """Reads `mask_reverse_flow_plots` from the project into the checkbox.

        `blockSignals` on purpose: without it, loading a project would
        trigger `_on_disk_mask_toggled`, which would write back the same
        value and mark the project "unsaved" right after opening it."""
        projeto = self.state.project
        if projeto is None:
            return
        valor = bool(projeto.config.get("mask_reverse_flow_plots", True))
        if valor == self.disk_mask_check.isChecked():
            return
        self.disk_mask_check.blockSignals(True)
        self.disk_mask_check.setChecked(valor)
        self.disk_mask_check.blockSignals(False)

    def _update_disk_color_controls_enabled(self, *_args):
        enabled = self.disk_field_combo.currentText() != "(grid with all fields)"
        for w in (self.disk_color_scale_combo, self.disk_color_vmin_edit, self.disk_color_vmax_edit):
            w.setEnabled(enabled)

    def _refresh_disk(self):
        self.canvas_stack.setCurrentIndex(0)  # Always show matplotlib for disk maps
        result = self._resolve_single_result()
        if result is None:
            self.canvas_host.show_message(self._AVISO_AO_MENOS_UM)
            return
        # Bug 4: check whether result.maps has disk data before trying to plot it
        if not result.maps:
            self.canvas_host.show_message(
                "This result does not contain disk maps (Npsi=1 or data unavailable).")
            return
        mask = self.disk_mask_check.isChecked()
        field = self.disk_field_combo.currentText()

        def _parse_bound(edit: QLineEdit):
            txt = edit.text().strip()
            if not txt:
                return None
            try:
                return float(txt)
            except ValueError:
                return None

        log_color = self.disk_color_scale_combo.currentText() == "log"
        vmin = _parse_bound(self.disk_color_vmin_edit)
        vmax = _parse_bound(self.disk_color_vmax_edit)
        chave = ("disk", self._assinatura_da_selecao(), field, mask, log_color, vmin, vmax)
        try:
            if field == "(grid with all fields)":
                self.canvas_host.mostrar_figura(
                    chave, lambda: plots.plot_disk_map_grid(result.maps, mask_reverse=mask))
            else:
                def _fabricar():
                    fig = Figure(figsize=(6, 5), tight_layout=True)
                    plots.plot_disk_map(result.maps, field=field, ax=fig.add_subplot(111),
                                         mask_reverse=mask, log_color=log_color,
                                         vmin=vmin, vmax=vmax)
                    return fig
                self.canvas_host.mostrar_figura(chave, _fabricar)
        except Exception as exc:
            self.canvas_host.show_message(
                f"Could not draw the disk map for '{field}':\n{exc}")

    # --- 5) Parameter table (all of Results.summary, 1 row per case) -----

    def _build_table_options(self) -> QWidget:
        """The table ALWAYS shows every column.

        There used to be a "Show configuration echo columns" here: the
        `cfg_*`/`rotor_*` columns (the run's technical sheet) were hidden
        behind a box the user had to discover. With a short-symbol header,
        fixed width, and an instant tooltip, they no longer get in the
        way -- and a table that hides part of the result by default is
        worse than a wide table.
        """
        box = QWidget()
        layout = QHBoxLayout(box)
        # The note used to describe the table's obvious format ("one row
        # per case, each quantity is a column") -- the header already says
        # so by itself.
        titulo = QLabel("<b>Results</b>")
        layout.addWidget(titulo)
        layout.addStretch(1)
        return box

    # --- instant header tooltip -------------------------------------------

    def _dica_do_cabecalho(self, pos):
        header = self.table_widget.horizontalHeader()
        col = header.logicalIndexAt(pos)
        item = self.table_widget.horizontalHeaderItem(col) if col >= 0 else None
        texto = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if texto:
            # Safety net for the "stuck" tooltip: the `Leave` that would
            # hide it may never arrive (mouse leaving fast, window losing
            # focus, a popup on top). While the mouse roams the header the
            # timer keeps restarting; once movement stops, it fires and
            # checks whether the cursor is really still there.
            self._dica_watchdog.start()
        return texto

    def _esconder_dica_se_o_mouse_saiu(self):
        header = self.table_widget.horizontalHeader()
        try:
            local = header.mapFromGlobal(QCursor.pos())
            ainda_dentro = header.rect().contains(local) and header.isVisible()
        except RuntimeError:
            ainda_dentro = False
        if ainda_dentro:
            self._dica_watchdog.start()   # still under the cursor: keep watching
            return
        # `instant_tooltip` only hides on `Leave`; until it gets its own
        # watchdog (see report), this tab closes the balloon itself.
        _instant_tooltip._InstantTooltip.instancia(header).hide()

    def _refresh_table(self):
        entries = self._selected_entries()
        if not entries:
            self.table_widget.setRowCount(0)
            self.table_widget.setColumnCount(0)
            return
        flat = plots.flatten_selection(entries)
        principais, cfg = api.summary_keys_union(flat, self._modo_helice())
        colunas = principais + cfg

        self.table_widget.setRowCount(len(flat))
        self.table_widget.setColumnCount(len(colunas))
        self.table_widget.setHorizontalHeaderLabels([
            symbol_to_plain_text(self._simbolos().get(c, (c.removeprefix("cfg_"), c))[0])
            for c in colunas
        ])
        for col, chave in enumerate(colunas):
            simbolo, descricao = self._simbolos().get(chave, (chave.removeprefix("cfg_"), chave))
            unidade = api.SUMMARY_UNITS.get(chave, "")
            dica = f"<b>{simbolo}</b>{f' [{unidade}]' if unidade else ''}<br>{descricao}"
            item = self.table_widget.horizontalHeaderItem(col)
            item.setToolTip(descricao)  # native fallback (with a delay) besides the instant one
            item.setData(Qt.ItemDataRole.UserRole, dica)
            # HTML symbol so the header paints the real subscript
            # (`_CabecalhoDeSimbolos`); `text()` stays "C_T".
            item.setData(_PAPEL_HTML, simbolo)

        # Numbering comes from `api.condition_labels`: the name alone
        # distinguishes nothing when the GUI generates every Run Case
        # condition with the SAME name -- the table used to read "case,
        # case, case...". The label only appends the name when it
        # actually separates the rows.
        rotulos = api.condition_labels(flat)
        for row, r in enumerate(flat):
            nome_item = QTableWidgetItem(rotulos[row])
            nome_item.setFlags(nome_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            # `rotulos[row]` is just "Case N" / "Case N - name": the NAME
            # saved for the condition, not its physical parameters --
            # that is why it almost never has "mu_x" for
            # `_descricao_com_simbolos` to convert, and the vertical
            # header used to come out with no symbol at all despite
            # `_CabecalhoVerticalDeSimbolos` already knowing how to paint
            # rich text.
            # `describe_case_settings` is the same function that names the
            # results history (`run_case.py::_on_run_finished`) -- reused
            # here so the row states the real μ_x/θ₀/rpm, not just the
            # case number. But the saved NAME of the condition is already
            # that same summary in most real flows (Run Batch names every
            # condition this way) -- appending it again duplicated it
            # ("μₓ=0.3 (μₓ=0.3, ...)"). An "=" already present in the name
            # is the sign that it is already descriptive.
            resumo = describe_case_settings(r.summary)
            ja_descritivo = "=" in rotulos[row]
            texto_rico = (rotulos[row] if ja_descritivo or not resumo
                          else f"{rotulos[row]} ({resumo})")
            nome_item.setData(_PAPEL_HTML, api._descricao_com_simbolos(texto_rico))
            self.table_widget.setVerticalHeaderItem(row, nome_item)
            for col, chave in enumerate(colunas):
                valor = api.format_summary_value(r.summary.get(chave, ""))
                cell = QTableWidgetItem(valor)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                # Numbers right-aligned so the decimal places line up
                # across rows; the configuration echo (`newton`, `drees`…)
                # is text and stays left-aligned.
                if _parece_numero(valor):
                    cell.setTextAlignment(ALINHAMENTO_DE_NUMERO)
                self.table_widget.setItem(row, col, cell)

    # --- 4) Coefficients vs axis (generalizes "Polar (batch)") -----------

    def _build_axis_options(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)

        # Mode: fixed grid (original behavior, 11/9 panels) or free X-Y
        # (user request: "plot anything against anything, with several
        # curves, one per grouping variable"). Default stays the grid --
        # nothing changes for anyone who already used this tab. A single
        # QCheckBox (not a QRadioButton/QButtonGroup pair) -- same pattern
        # already used by `overlay_check` in this tab; a QRadioButton/
        # QButtonGroup here, embedded in this specific layout hierarchy,
        # hangs (a deadlock, not an exception) under
        # QT_QPA_PLATFORM=offscreen, even outside any real event loop --
        # reproduced in isolation with faulthandler before this change.
        mode_row = QHBoxLayout()
        self.axis_mode_xy_check = QCheckBox("Custom X-Y (instead of coefficient grid)")
        self.axis_mode_xy_check.toggled.connect(self._on_axis_mode_changed)
        mode_row.addWidget(self.axis_mode_xy_check)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        # --- grid mode (original) ---------------------------------------
        self.axis_grid_options = QWidget()
        grid_layout = QVBoxLayout(self.axis_grid_options)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("X axis:"))
        self.axis_combo = _ComboDeSimbolos()
        for chave in self._FACTORIAL_AXES:
            simbolo = plots.rotulo_de_summary_em_html(chave, self._modo_helice())
            _simbolo, descricao = self._simbolos().get(chave, (chave, chave))
            unidade = api.SUMMARY_UNITS.get(chave, "")
            dica = (
                f"<b>{simbolo}</b>{f' [{unidade}]' if unidade else ''}"
                f"<br><br>{descricao}"
            )
            self.axis_combo.adicionar(chave, simbolo, dica, dado=chave)
        self.axis_combo.setToolTip(
            "Flight-condition quantity spread along the horizontal axis of "
            "every panel. The selected results are sorted by it, so it should "
            "be the quantity that actually varied across the batch.")
        row1.addWidget(self.axis_combo)
        row1.addStretch(1)
        grid_layout.addLayout(row1)
        # On by default: with 2+ entries checked, concatenating everything
        # into a single curve produces a meaningless zigzag line (two
        # different batches spliced together point by point). Grouped,
        # each family becomes a curve sorted by the chosen axis.
        self.overlay_check = QCheckBox(
            "one curve per result set (uncheck to combine everything into a single curve)")
        self.overlay_check.setChecked(True)
        self.overlay_check.setToolTip(
            "Keeps each selected batch as its own curve, and the individual "
            "cases together as one; unchecking merges every point into a "
            "single curve sorted along the X axis.")
        self.overlay_check.toggled.connect(self._refresh_axis)
        self.overlay_check.setVisible(False)
        grid_layout.addWidget(self.overlay_check)
        layout.addWidget(self.axis_grid_options)

        # --- free X-Y mode -----------------------------------------------
        self.axis_xy_options = QWidget()
        xy_layout = QVBoxLayout(self.axis_xy_options)
        xy_layout.setContentsMargins(0, 0, 0, 0)
        xy_row = QHBoxLayout()
        xy_row.addWidget(QLabel("X:"))
        # `_ComboDeSimbolos` on all three: the item is painted as a SYMBOL
        # (μ, C_T with the T below the line), and the tooltip that appears
        # on hover carries the spelled-out name, in prose.
        self.xy_x_combo = _ComboDeSimbolos()
        self.xy_x_combo.setToolTip(
            "Quantity on the horizontal axis. The list holds every summary "
            "quantity present in the current selection, so any result can be "
            "plotted against any other.")
        xy_row.addWidget(self.xy_x_combo)
        xy_row.addWidget(QLabel("Y:"))
        self.xy_y_combo = _ComboDeSimbolos()
        self.xy_y_combo.setToolTip("Quantity on the vertical axis, from the same list.")
        xy_row.addWidget(self.xy_y_combo)
        xy_row.addWidget(QLabel("Group curves by:"))
        self.xy_group_combo = _ComboDeSimbolos()
        self.xy_group_combo.setToolTip(
            "Splits the points into one curve per distinct value of this "
            "quantity — the way to read a family of conditions (one curve per "
            "collective, say) instead of a single cloud of points.")
        xy_row.addWidget(self.xy_group_combo)
        xy_row.addStretch(1)
        xy_layout.addLayout(xy_row)
        layout.addWidget(self.axis_xy_options)
        self.axis_xy_options.setVisible(False)

        # Grouping tolerance: applies to BOTH modes (the grid
        # auto-detects series from the secondary axes, X-Y groups by the
        # chosen quantity), so it lives outside both blocks.
        # Without it, a nominal sweep of alpha = -10, -5, 0, 5, 10 showed
        # up as ~18 curves: alpha is reconstructed via atan2 and every
        # combination with the other axis returned -10.001, -9.999,
        # -10.002…
        tol_row = QHBoxLayout()
        tol_row.addWidget(QLabel("Group tolerance:"))
        self.group_tol_spin = QDoubleSpinBox()
        self.group_tol_spin.setDecimals(4)
        self.group_tol_spin.setRange(0.0, 1000.0)
        self.group_tol_spin.setSingleStep(0.01)
        self.group_tol_spin.setValue(plots.TOLERANCIA_DE_AGRUPAMENTO_PADRAO)
        self.group_tol_spin.setToolTip(
            "Two values of the grouping quantity closer than this belong to the "
            "same curve. Raise it when one nominal value shows up as several "
            "near-identical curves (floating-point noise from a derived quantity "
            "such as the disk angle); lower it to separate a genuinely fine sweep. "
            "0 disables the tolerance.")
        self.group_tol_spin.valueChanged.connect(self._refresh_axis)
        tol_row.addWidget(self.group_tol_spin)
        tol_row.addStretch(1)
        layout.addLayout(tol_row)

        btn = QPushButton("Refresh")
        btn.clicked.connect(self._refresh_axis)
        layout.addWidget(btn)
        layout.addStretch(1)
        return box

    def _on_axis_mode_changed(self, *_args):
        is_grid = not self.axis_mode_xy_check.isChecked()
        self.axis_grid_options.setVisible(is_grid)
        self.axis_xy_options.setVisible(not is_grid)
        if not is_grid:
            self._populate_xy_combos()
        self._refresh_axis()

    def _populate_xy_combos(self):
        """Populates X/Y/Group-by with the UNION of `summary` keys present
        in the current selection (excluding `cfg_*`, which are the run's
        "technical sheet", not quantities to plot) -- shows the user only
        what actually exists in the selected results."""
        flat = plots.flatten_selection(self._selected_entries())
        keys = []
        seen = set()
        for r in flat:
            for k in r.summary.keys():
                if k.startswith("cfg_") or k in seen:
                    continue
                seen.add(k)
                keys.append(k)

        # Preserves the current selection (by key, via userData) across refreshes.
        prev_x = self.xy_x_combo.currentData()
        prev_y = self.xy_y_combo.currentData()
        prev_group = self.xy_group_combo.currentData()

        for combo in (self.xy_x_combo, self.xy_y_combo, self.xy_group_combo):
            combo.blockSignals(True)
            combo.clear()
        self.xy_group_combo.adicionar("(none)", "", "No grouping: every point in a single curve.",
                                       dado=None)
        for k in keys:
            # The item is painted as a SYMBOL (`_ComboDeSimbolos`): raw
            # mathtext ("mu_x  ($\mu_x$ [-])") is what used to appear,
            # because a plain QComboBox does not render any LaTeX.
            html = plots.rotulo_de_summary_em_html(k, self._modo_helice())
            # RAW text of the item = the key: still searchable by typing
            # "CT" with the combo open, even without knowing the symbol by
            # heart. The tooltip is the spelled-out name, in prose -- the
            # same description the report uses in the summary table's
            # header, so the same explanation is not written twice.
            _simbolo, descricao = self._simbolos().get(k, (k, ""))
            unidade = api.SUMMARY_UNITS.get(k, "")
            dica = descricao + (f" [{unidade}]" if unidade else "")
            for combo in (self.xy_x_combo, self.xy_y_combo, self.xy_group_combo):
                combo.adicionar(k, html, dica, dado=k)
        for combo in (self.xy_x_combo, self.xy_y_combo, self.xy_group_combo):
            combo.blockSignals(False)

        def _restore(combo, prev_key, fallback_idx):
            if prev_key is not None:
                idx = combo.findData(prev_key)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    return
            combo.setCurrentIndex(fallback_idx)

        _restore(self.xy_x_combo, prev_x, 0 if self.xy_x_combo.count() else -1)
        _restore(self.xy_y_combo, prev_y,
                 1 if self.xy_y_combo.count() > 1 else 0 if self.xy_y_combo.count() else -1)
        _restore(self.xy_group_combo, prev_group, 0)

    #: Label of the series that gathers loose Run Cases in a mixed selection.
    _SERIE_DE_CASOS_AVULSOS = "Individual cases"

    def _series_por_familia(self, entries) -> list[str]:
        """SERIES label per condition, parallel to
        `plots.flatten_selection(entries)`.

        The family is the condition's origin: each batch is a series (the
        history entry's label) and ALL loose Run Cases form a single one
        -- they are points of the same sweep done by hand, and a series
        per case would produce N curves of one point each, with a legend
        larger than the panels. Within each series
        `plots.plot_coefficients_vs_axis` sorts the points by the chosen
        axis."""
        rotulos = []
        for e in entries:
            if e.kind == "batch":
                rotulos.extend([e.label] * len(e.results))
            else:
                rotulos.append(self._SERIE_DE_CASOS_AVULSOS)
        return rotulos

    def _refresh_axis(self):
        entries = self._selected_entries()
        if not entries:
            self.overlay_check.setVisible(False)
            self.canvas_stack.setCurrentIndex(0)  # Show matplotlib
            self.canvas_host.show_message(self._AVISO_AO_MENOS_UM)
            return

        if self.axis_mode_xy_check.isChecked():
            self._refresh_axis_xy(entries)
            return

        # Overlay/combine toggle only makes sense with 2+ selections (Part 4.2).
        self.overlay_check.setVisible(len(entries) >= 2)
        flat = plots.flatten_selection(entries)
        labels = (self._series_por_familia(entries)
                  if (self.overlay_check.isChecked() and len(entries) >= 2) else None)
        if not flat:
            self.canvas_stack.setCurrentIndex(0)  # Show matplotlib
            self.canvas_host.show_message("Empty selection (batch with no results).")
            return

        axis = self.axis_combo.currentText()

        # Lazy-initialize Plotly if not yet attempted and the user picked it
        # in the backend dropdown. Skip if overlay mode (series_labels not
        # yet supported in Plotly).
        if self.plotly_host is None and self._wants_plotly() and labels is None:
            try:
                self.plotly_host = PlotlyCanvasHost()
                self._plotly_stack_index = self.canvas_stack.addWidget(self.plotly_host)
            except Exception:
                # Creation failed (e.g., offscreen crash under QT_QPA_PLATFORM=offscreen):
                # stay matplotlib-only
                self.plotly_host = None

        # Use Plotly only if the user selected it and it's available/not overlay.
        if self.plotly_host is not None and self._wants_plotly() and labels is None:
            try:
                from ...viz import plots_interactive
                fig_plotly = plots_interactive.coefficients_vs_axis(
                    flat, axis=axis, group_tol=self._group_tol())
                self.plotly_host.set_figure(fig_plotly)
                self.canvas_stack.setCurrentIndex(self._plotly_stack_index)
                return
            except Exception:
                # If Plotly render fails, fall through to matplotlib
                pass

        # Matplotlib fallback (always available; also used for overlay mode)
        self.canvas_stack.setCurrentIndex(0)  # Show matplotlib
        tol = self._group_tol()
        chave = ("axis", self._assinatura_da_selecao(), axis, tuple(labels or ()), tol)
        self.canvas_host.mostrar_figura(
            chave, lambda: plots.plot_coefficients_vs_axis(
                flat, axis=axis, series_labels=labels, group_tol=tol))

    def _group_tol(self) -> float:
        """Current grouping tolerance (control above the plot).
        It enters the figure cache's KEY: without this, changing the
        control would redraw nothing (the old figure would come back from
        the cache)."""
        return float(self.group_tol_spin.value())

    def _refresh_axis_xy(self, entries):
        """"Custom X-Y" mode (progressive disclosure of the grid mode):
        plots `plots.plot_xy`/`plots_interactive.xy_plot` (Plotly when
        available, the same choice as the grid mode) from the X/Y/
        Group-by combos, populated with the summary keys of the current
        selection."""
        self.overlay_check.setVisible(False)
        flat = plots.flatten_selection(entries)
        if not flat:
            self.canvas_stack.setCurrentIndex(0)
            self.canvas_host.show_message("Empty selection (batch with no results).")
            return
        self._populate_xy_combos()
        if self.xy_x_combo.count() == 0:
            self.canvas_stack.setCurrentIndex(0)
            self.canvas_host.show_message("No summary field available in this selection.")
            return

        x_key = self.xy_x_combo.currentData()
        y_key = self.xy_y_combo.currentData()
        group_key = self.xy_group_combo.currentData()
        if x_key is None or y_key is None:
            self.canvas_stack.setCurrentIndex(0)
            self.canvas_host.show_message("Choose an X and a Y field.")
            return

        if self.plotly_host is None and self._wants_plotly():
            try:
                self.plotly_host = PlotlyCanvasHost()
                self._plotly_stack_index = self.canvas_stack.addWidget(self.plotly_host)
            except Exception:
                self.plotly_host = None

        if self.plotly_host is not None and self._wants_plotly():
            try:
                from ...viz import plots_interactive
                fig_plotly = plots_interactive.xy_plot(flat, x_key=x_key, y_key=y_key,
                                                          group_by=group_key,
                                                          group_tol=self._group_tol())
                self.plotly_host.set_figure(fig_plotly)
                self.canvas_stack.setCurrentIndex(self._plotly_stack_index)
                return
            except Exception:
                pass

        # `plot_xy` draws on a single `ax` (same pattern as
        # `plot_disk_map`), it does not return a ready `Figure` -- the
        # figure is assembled here so it can enter the `_CanvasComCache`
        # cache like any other.
        self.canvas_stack.setCurrentIndex(0)

        tol = self._group_tol()

        def _fabricar():
            fig = Figure(figsize=(6, 5), tight_layout=True)
            plots.plot_xy(flat, x_key=x_key, y_key=y_key, group_by=group_key,
                          ax=fig.add_subplot(111), group_tol=tol,
                          is_propeller=self._modo_helice())
            return fig
        self.canvas_host.mostrar_figura(
            ("xy", self._assinatura_da_selecao(), x_key, y_key, group_key, tol), _fabricar)

    # --- 5) Azimuth / Radius ---------------------------------------------

    #: Items of the X-axis combo. Constants because `_refresh_azrad`
    #: decides by comparing against the selected text -- it used to
    #: compare against the literal prefix "Raio", which would break
    #: silently (always falling into the azimuthal branch) the first time
    #: the label changed.
    _AZRAD_X_RAIO = "Radius (r/R)"
    _AZRAD_X_AZIMUTE = "Azimuth [deg]"

    def _update_azrad_visibility(self, *_args):
        """Shows only the list that the chosen X axis actually uses."""
        por_raio = self.azrad_x_combo.currentText() == self._AZRAD_X_RAIO
        self.azrad_psi_label.setVisible(por_raio)
        self.azrad_psi_edit.setVisible(por_raio)
        self.azrad_r_label.setVisible(not por_raio)
        self.azrad_r_edit.setVisible(not por_raio)

    def _build_azrad_options(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("X axis:"))
        self.azrad_x_combo = QComboBox()
        self.azrad_x_combo.addItems([self._AZRAD_X_RAIO, self._AZRAD_X_AZIMUTE])
        self.azrad_x_combo.setToolTip(
            "Radius: one curve per fixed azimuth, showing how the load is "
            "distributed along the blade.\n"
            "Azimuth: one curve per fixed radial station, showing how that "
            "station is loaded around one revolution.")
        row1.addWidget(self.azrad_x_combo)
        row1.addStretch(1)
        layout.addLayout(row1)
        row2 = QHBoxLayout()
        self.azrad_psi_label = QLabel("Azimuths to hold fixed [deg]:")
        row2.addWidget(self.azrad_psi_label)
        self.azrad_psi_edit = QLineEdit("0, 90, 180, 270")
        self.azrad_psi_edit.setToolTip(
            "One spanwise curve is drawn per azimuth listed here "
            "(0° = downstream/tail, 90° = advancing side).")
        row2.addWidget(self.azrad_psi_edit)
        layout.addLayout(row2)
        row3 = QHBoxLayout()
        self.azrad_r_label = QLabel("Radial stations to hold fixed [r/R]:")
        row3.addWidget(self.azrad_r_label)
        self.azrad_r_edit = QLineEdit("0.25, 0.5, 0.75, 0.95")
        self.azrad_r_edit.setToolTip(
            "One azimuthal curve is drawn per radial station listed here, "
            "as a fraction of the rotor radius.")
        row3.addWidget(self.azrad_r_edit)
        layout.addLayout(row3)
        # Only ONE of the two lists acts at a time: the other is ignored
        # by the chosen X axis. Both used to always stay on screen, and
        # the label spelled out the condition in words ("if X=Radius") --
        # the user had to resolve the conditional in their head to know
        # which of the two fields was being read.
        self.azrad_x_combo.currentTextChanged.connect(self._update_azrad_visibility)
        self._update_azrad_visibility()
        btn = QPushButton("Refresh")
        btn.clicked.connect(self._refresh_azrad)
        layout.addWidget(btn)
        return box

    def _refresh_azrad(self):
        self.canvas_stack.setCurrentIndex(0)  # Always show matplotlib for azimuth/radial
        result = self._resolve_single_result()
        if result is None:
            self.canvas_host.show_message(self._AVISO_AO_MENOS_UM)
            return
        por_raio = self.azrad_x_combo.currentText() == self._AZRAD_X_RAIO
        if por_raio:
            alvos = parse_list(self.azrad_psi_edit.text()) or [0, 90, 180, 270]
            fabrica = lambda: plots.plot_blade_loads_vs_span(   # noqa: E731
                result.maps, psi_targets_deg=alvos)
        else:
            alvos = parse_list(self.azrad_r_edit.text()) or [0.25, 0.5, 0.75, 0.95]
            fabrica = lambda: plots.plot_loads_vs_azimuth(      # noqa: E731
                result.maps, r_norm_targets=alvos)
        self.canvas_host.mostrar_figura(
            ("azrad", self._assinatura_da_selecao(), por_raio, tuple(alvos)), fabrica)

    # --- 6) 3D --------------------------------------------------------

    def _build_3d_options(self) -> QWidget:
        pyvista_ok = visualization.is_available()
        # The title used to be "3D View (PyVista) — exports screenshot via
        # api.export_results()": a library name and an internal function
        # signature in an on-screen label. None of that is actionable for
        # whoever uses the window -- what they need to know (that the
        # button saves an image) goes in the button's tooltip, in plain
        # human language.
        box = QGroupBox("3D view")
        form = QFormLayout(box)
        note = QLabel(
            "Blades and rotor disc drawn in 3D. Colour and height are chosen "
            "independently below — pick the same quantity for both to read one "
            "field as relief, or two different ones to see them at once. "
            "Rotate and zoom with the mouse." + (
                "" if pyvista_ok else
                " The image exports below need the optional PyVista package "
                "(pip install pyvista), which is not installed on this machine — "
                "the view above does not."
            ))
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        form.addRow(note)
        self.field_combo = _ComboDeSimbolos()
        for campo in self._DISK_FIELDS:
            self.field_combo.adicionar(campo, plots.disk_field_symbol_html(campo),
                                       self._dica_de_campo_de_disco(campo))
        self.field_combo.setToolTip(
            "Quantity painted on the disc in the 3D view and on the blade "
            "surface in the 3D load export. It chooses what is coloured, not "
            "what is computed — every field is already solved on the same mesh.")
        self.field_combo.currentTextChanged.connect(self._maybe_refresh_3d)
        form.addRow("Colour (field on the disc):", self.field_combo)
        # Height SEPARATE from colour (owner's request). There used to be
        # a single selector here plus a checkbox "raise the disc by the
        # field value": height was mandatorily the SAME quantity as the
        # colour, and the only alternative was to turn it off.
        # `build_disk_grid` always accepted separate `field=` and
        # `z_field=` -- it was only the GUI that tied the two together.
        # Same SYMBOL combo as the colour one: the two selectors show the
        # same quantities, and one of them painting "F_n" while the other
        # showed raw "Fn" made the pair look like two different lists.
        self.z_field_combo = _ComboDeSimbolos()
        self.z_field_combo.adicionar(
            self._SEM_RELEVO_3D, self._SEM_RELEVO_3D,
            "Leaves the disc flat: colour only, no relief.")
        for campo in self._DISK_FIELDS:
            self.z_field_combo.adicionar(campo, plots.disk_field_symbol_html(campo),
                                          self._dica_de_campo_de_disco(campo))
        self.z_field_combo.setToolTip(
            "Quantity that raises the disc out of its own plane. Leave it equal "
            f"to the colour field to read one quantity as relief, choose another "
            f"to compare two at once, or pick '{self._SEM_RELEVO_3D}' for a flat, "
            "colour-only disc.")
        # Default: SAME quantity as the colour -- whoever opened the tab
        # before saw the relief of the chosen field, and keeps seeing it.
        self.z_field_combo.setCurrentText(self.field_combo.currentText())
        self.z_field_combo.currentTextChanged.connect(self._maybe_refresh_3d)
        form.addRow("Height (field raising the disc):", self.z_field_combo)
        self.btn_export_load = QPushButton("Export 3D load distribution")
        self.btn_export_load.clicked.connect(lambda: self._export_3d("load_3d"))
        form.addRow(self.btn_export_load)
        # Without PyVista the buttons stay clickable: `_export_3d` opens
        # the dialog with `pip install pyvista`. `btn_export_load` stays
        # tied to the selection (not to the missing package) -- exporting
        # the load with no case selected would have nothing to export.
        self.btn_export_load.setEnabled(False)   # enabled by _on_selection_changed
        return box

    @staticmethod
    def _dica_de_campo_de_disco(campo: str) -> str:
        """Item tooltip for a disk-map field: what the quantity MEANS, in
        prose, with the unit at the end -- not the raw key from
        `Results.maps`, which is what the combo already shows as text."""
        descricao = plots.disk_field_description(campo)
        unidade = plots.disk_field_unit(campo)
        if unidade and unidade != "-":
            descricao = f"{descricao} [{unidade}]" if descricao else f"[{unidade}]"
        return descricao

    def _maybe_refresh_3d(self):
        """Redraws only if the 3D mode is the one on screen.

        The 3D block's controls (painted field, relief) exist even while
        another mode is open; without this guard, touching them would
        redraw over the plot the user is currently looking at.
        """
        self._maybe_refresh("3D")

    def _refresh_3d_preview(self):
        """Draws the disc in THREE dimensions, coloured by the chosen field.

        This function used to call `plot_planform` -- the PLANFORM view, a
        2D outline of the blades -- and it still forced the matplotlib
        canvas. In other words: the "3D" mode never showed anything in
        3D, and picking the Plotly backend changed nothing here, because
        the stack index was fixed before ever looking at the backend. The
        real 3D only existed as a FILE, through the export buttons
        (PyVista).

        The mesh comes from `visualization.build_disk_grid`, which is pure
        NumPy and does not depend on PyVista (CLAUDE.md: the mesh
        builders degrade without error when it is not installed) -- so
        the embedded 3D view works on any installation, and PyVista
        remains just the high-quality export path.
        """
        if self.state.project is None:
            self.canvas_host.show_message("No project open.")
            self.canvas_stack.setCurrentIndex(0)
            return
        result = self._resolve_single_result()
        if result is None or not getattr(result, "maps", None):
            # No result yet: the blade planform is what there is to show,
            # and it is better than an empty screen -- but said in plain
            # words, so no one confuses it with the 3D view.
            self.canvas_stack.setCurrentIndex(0)
            geom = self.state.project.geometry

            def _planta():
                fig = Figure(figsize=(5, 5), tight_layout=True)
                ax = fig.add_subplot(111)
                plots.plot_planform(geom, ax=ax)
                ax.set_title("Blade planform — run a case to see the 3D disc")
                return fig
            self.canvas_host.mostrar_figura(
                ("planform", id(geom), len(geom.r_norm)), _planta)
            return

        campo = self._campo_3d_selecionado()
        relevo = self._campo_3d_de_altura()
        assinatura = ("3d", self._assinatura_da_selecao(), campo, relevo,
                      self._wants_plotly())

        if self._wants_plotly():
            self.canvas_stack.setCurrentIndex(1)
            self.plotly_host = self.plotly_host or PlotlyCanvasHost()
            try:
                self.plotly_host.set_figure(
                    self._figura_3d_plotly(result.maps, campo, relevo))
            except Exception as exc:                       # pragma: no cover
                self.plotly_host.show_message(f"3D view failed: {exc}")
            return

        self.canvas_stack.setCurrentIndex(0)

        def _fabricar():
            return self._figura_3d_matplotlib(result.maps, campo, relevo)
        self.canvas_host.mostrar_figura(assinatura, _fabricar)

    #: Label of the field combo -> key in `Results.maps`. The combo shows
    #: a readable name ("Fn (thrust)"); `build_disk_grid` wants the raw key.
    _CAMPO_3D_POR_ROTULO = {campo: campo for campo in _DISK_FIELDS}

    def _campo_3d_selecionado(self) -> str:
        """`maps` key of the field that COLOURS the surface."""
        return self._CAMPO_3D_POR_ROTULO.get(self.field_combo.currentText(), "Fn")

    def _campo_3d_de_altura(self) -> str | None:
        """`maps` key of the field that gives the surface's HEIGHT, or
        `None` for a flat disc (`_SEM_RELEVO_3D`).

        Independent of `_campo_3d_selecionado`: the two selectors can
        point to different quantities -- that is exactly why
        `visualization.build_disk_grid` separates `field=` from
        `z_field=`."""
        rotulo = self.z_field_combo.currentText()
        if rotulo == self._SEM_RELEVO_3D:
            return None
        return self._CAMPO_3D_POR_ROTULO.get(rotulo, "Fn")

    @staticmethod
    def _rotulo_de_campo_3d(campo: str, desenhado: bool = True) -> str:
        """`"$\\lambda_i$ [-]"` -- SYMBOL of the field with the unit, for
        the colour bar and the z axis.

        It used to be the key's raw name (`"lambda_i [-]"`): the same
        quantity that this tab's selectors, the 2D maps and the table
        already show as λ_i appeared in the 3D view in `snake_case`, and a
        reader who had just chosen "λᵢ" in the combo found "lambda_i" in
        the plot. The symbol comes from `plots._DISK_FIELD_META`, the same
        source as the 2D maps -- no second list.

        ``desenhado=False`` returns the plain-text (Unicode) version, for
        surfaces that do NOT render mathtext: Plotly would print
        ``$\\lambda_i$`` raw."""
        simbolo = plots.disk_field_label(campo)
        unidade = plots.disk_field_unit(campo)
        rotulo = f"{simbolo} [{unidade}]" if unidade and unidade != "-" else simbolo
        return rotulo if desenhado else plots.rotulo_em_texto(rotulo)

    def _figura_3d_matplotlib(self, maps: dict, campo: str, relevo: str | None):
        X, Y, Z, valores = visualization.build_disk_grid(
            maps, field=campo, z_field=relevo)
        fig = Figure(figsize=(6, 5), tight_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        normal = plt_colors.Normalize(
            vmin=float(np.nanmin(valores)), vmax=float(np.nanmax(valores)))
        cores = plt_cm.viridis(normal(valores))
        ax.plot_surface(X, Y, Z, facecolors=cores, rstride=1, cstride=1,
                        linewidth=0, antialiased=False, shade=False)
        mapeavel = plt_cm.ScalarMappable(norm=normal, cmap="viridis")
        mapeavel.set_array(valores)
        # Only the SYMBOL, without the word "colour": it sits right next
        # to the colour bar itself, which already says what it is. The
        # same applies to the z axis below -- see `_legenda_de_par_3d`.
        fig.colorbar(mapeavel, ax=ax, shrink=0.6, pad=0.08,
                     label=self._rotulo_de_campo_3d(campo))
        # `build_disk_grid` returns the DIMENSIONAL radius (`R_DIM`, in
        # metres), not r/R -- labeling the axes with "/ R" said the tip
        # was at 8 radii.
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        # The z axis is the HEIGHT, which can be a different quantity
        # than the colour -- naming it is what stops the relief from
        # being read as if it were the colour bar's field. The ticks are
        # omitted because `build_disk_grid` normalizes the extrusion by
        # `z_scale * R_max` (drawing metres, not the quantity's own
        # units); whoever wants the VALUE reads the colour bar or the 2D
        # map.
        ax.set_zlabel("" if relevo is None
                      else self._rotulo_de_campo_3d(relevo), labelpad=-8)
        ax.set_zticks([])
        # With no relief the disc is flat: flattening the z axis avoids a
        # tall, empty 3D box around a surface of zero thickness.
        ax.set_box_aspect((1, 1, 0.45 if relevo else 0.12))
        ax.view_init(elev=32, azim=-58)
        titulo = plots.describe_condition(maps)
        legenda = self._legenda_de_par_3d(campo, relevo)
        ax.set_title(f"{titulo}\n{legenda}" if legenda else titulo)
        return fig

    def _legenda_de_par_3d(self, campo: str, relevo: str | None,
                            desenhado: bool = True) -> str:
        """Second title line -- only when colour and height are DIFFERENT
        quantities; empty otherwise.

        With the disc flattened and seen from above, the z axis label
        sits behind the 3D box at most angles, and then a reader who only
        glanced at the colour bar would end up thinking the relief is the
        same quantity. This is the only situation where the words
        "colour"/"height" earn their keep: when the two symbols are the
        SAME (the common case), the line just repeated a third time what
        the colour bar and the z axis already say next to themselves.

        ``desenhado=False``: plain text, for Plotly."""
        if relevo is None or relevo == campo:
            return ""
        return (f"colour: {self._rotulo_de_campo_3d(campo, desenhado)}"
                f"  ·  height: {self._rotulo_de_campo_3d(relevo, desenhado)}")

    def _figura_3d_plotly(self, maps: dict, campo: str, relevo: str | None):
        import plotly.graph_objects as go
        X, Y, Z, valores = visualization.build_disk_grid(
            maps, field=campo, z_field=relevo)
        # `desenhado=False` everywhere: Plotly does not render matplotlib
        # mathtext -- it would print `$\lambda_i$` raw --, so the symbol
        # goes in Unicode (`plots.rotulo_em_texto`). Without the word
        # "colour"/"height": each symbol sits right next to what it
        # describes.
        fig = go.Figure(data=[go.Surface(
            x=X, y=Y, z=Z, surfacecolor=valores, colorscale="Viridis",
            colorbar=dict(title=self._rotulo_de_campo_3d(campo, False)))])
        legenda = self._legenda_de_par_3d(campo, relevo, desenhado=False)
        fig.update_layout(
            scene=dict(xaxis_title="x [m]", yaxis_title="y [m]",
                       zaxis_title=("" if relevo is None else
                                    self._rotulo_de_campo_3d(relevo, False)),
                       aspectratio=dict(
                           x=1, y=1, z=0.45 if relevo else 0.12)),
            # No `describe_condition` here: it returns matplotlib mathtext
            # (`$\mu_x$`), which Plotly would print raw. Only the
            # colour/height pair, and only when the two quantities differ.
            title=dict(text=legenda),
            margin=dict(l=0, r=0, t=50 if legenda else 10, b=0))
        return fig

    # --- 7) Solver convergence -------------------------------------------

    def _build_convergence_options(self) -> QWidget:
        """Options for the "Convergence" mode.

        The convergence plot used to exist only in the report/CLI and
        depended on `BEMTConfig.collect_history`, which was NOT editable
        anywhere in the GUI -- in a project saved with
        `collect_history: false` (the case of `projects/starter_rotor`),
        the report showed a panel saying "run with collect_history =
        True" with nowhere to turn it on: a dead end. Here the mode
        exists in the tab and the button below turns the option on in the
        open project.
        """
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        self.convergence_note = QLabel(
            "Converged fraction of the mesh and max residual per solver iteration.")
        self.convergence_note.setStyleSheet("color: gray;")
        layout.addWidget(self.convergence_note)
        self.btn_enable_history = QPushButton("Enable convergence history")
        self.btn_enable_history.setToolTip(
            '"collect_history" — records the per-iteration residual of the inflow solver. '
            "Turn it on and run the case again to get this plot.")
        self.btn_enable_history.clicked.connect(self._habilitar_historico_de_convergencia)
        self.btn_enable_history.setVisible(False)
        layout.addWidget(self.btn_enable_history)
        layout.addStretch(1)
        return box

    def _refresh_convergence(self):
        self.canvas_stack.setCurrentIndex(0)
        result = self._resolve_single_result()
        if result is None:
            self.btn_enable_history.setVisible(False)
            self.canvas_host.show_message(self._AVISO_AO_MENOS_UM)
            return
        # The result already contains the aggregated diagnostics even when
        # the per-iteration history was not requested. So the absence of
        # `collect_history` must not stop the user from opening the plot.
        # `plot_convergence` draws these diagnostics as a summary when
        # there are no time series.
        self.btn_enable_history.setVisible(False)
        # No `ax=`: `plot_convergence` assembles the figure in the format
        # it itself demands (landscape ~11x4.4 when there is disk+history,
        # shorter when there is only the card strip). Handing it a ready
        # `Figure(6, 4)` squeezed the three panels into a square area --
        # the disc shrank and the card strip overflowed.
        def _fabricar():
            return plots.plot_convergence(result)
        self.canvas_host.mostrar_figura(
            ("convergence", self._assinatura_da_selecao(),
             result.summary.get("convergence_pct"),
             result.summary.get("mean_iter")), _fabricar)

    def _habilitar_historico_de_convergencia(self):
        if self.state.project is None:
            QMessageBox.warning(self, "No project", "Create or open a project first.")
            return
        self.state.project.config["collect_history"] = True
        self.state.notify_config()
        self.btn_enable_history.setVisible(False)
        QMessageBox.information(
            self, "Convergence history enabled",
            'The project now records the solver\'s convergence history '
            '("collect_history" in the .bemt config).\n\n'
            "Run the case again (Run Case / Run Batch) and this plot will be filled in. "
            "Save the project to keep the setting.")
        self._refresh_convergence()

    def _export_3d(self, kind: str):
        if not require_optional_package(self, "pyvista"):
            return
        if self.state.project is None:
            QMessageBox.warning(self, "No project", "Create or open a project first.")
            return
        if kind == "load_3d":
            result = self._resolve_single_result()
            if result is None:
                QMessageBox.warning(self, "No result",
                                     "Select exactly 1 result in the list on the left.")
                return
            field_key = self._campo_3d_selecionado()
            results, plot_kind = result, f"load_3d_{field_key}"
        else:
            # rotor_3d draws only from project.geometry -- it does not
            # depend on any Results, so an empty list is enough.
            results, plot_kind = [], "rotor_3d"

        outdir = QFileDialog.getExistingDirectory(
            self, "Output folder for the 3D screenshot",
            str(self._pasta_de_saida_padrao()))
        if not outdir:
            return
        try:
            written = api.export_results(results, outdir, plots=[plot_kind], save_csv=False,
                                          project=self.state.project)
            if written:
                QMessageBox.information(self, "Exported", "File generated:\n" + "\n".join(written))
            else:
                QMessageBox.warning(self, "Nothing generated", "PyVista may not be installed, or the requested "
                                     "field is not available in this result.")
        except Exception as exc:
            show_error(self, "Error exporting 3D view", exc)

    # --- batch export of disk maps (Part 4.3) -----------------------------

    def _export_disk_maps_da_selecao(self):
        """Exports the disk maps for the WHOLE selection (item 27).

        The previous filter (`e.kind == "batch"`) silently discarded
        loose Run Cases: with six cases checked the button warned that
        there was no batch at all. Several checked conditions ARE a batch
        for export purposes, whatever run produced them."""
        entries = self._selected_entries()
        if not entries:
            QMessageBox.warning(self, "Nothing to export", self._AVISO_AO_MENOS_UM)
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Export disk maps")
        form = QFormLayout(dlg)

        field_list = QListWidget()
        field_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        grid_item = QListWidgetItem("(grid with all fields)")
        grid_item.setFlags(grid_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        grid_item.setCheckState(Qt.CheckState.Checked)
        field_list.addItem(grid_item)
        for f in plots._DISK_GRID_FIELDS:
            item = QListWidgetItem(f)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            field_list.addItem(item)
        form.addRow("Field(s):", field_list)

        radio_flat = QRadioButton("One file per case, self-explanatory name")
        radio_flat.setChecked(True)
        radio_per_case = QRadioButton("One folder per case")
        radio_group = QButtonGroup(dlg)
        radio_group.addButton(radio_flat)
        radio_group.addButton(radio_per_case)
        form.addRow("Organization:", radio_flat)
        form.addRow("", radio_per_case)

        outdir_edit = QLineEdit()
        outdir_edit.setText(str(self._pasta_de_saida_padrao()))
        btn_browse = QPushButton("…")

        def _browse():
            # "Browse" also starts from the project's output folder (or
            # whatever is already written in the field), not from the
            # last directory the process visited.
            inicio = outdir_edit.text().strip() or str(self._pasta_de_saida_padrao())
            p = QFileDialog.getExistingDirectory(dlg, "Destination folder", inicio)
            if p:
                outdir_edit.setText(p)
        btn_browse.clicked.connect(_browse)
        outdir_row = QHBoxLayout()
        outdir_row.addWidget(outdir_edit)
        outdir_row.addWidget(btn_browse)
        form.addRow("Destination folder:", outdir_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        use_grid = grid_item.checkState() == Qt.CheckState.Checked
        selected_fields = [field_list.item(i).text() for i in range(1, field_list.count())
                            if field_list.item(i).checkState() == Qt.CheckState.Checked]
        if not use_grid and not selected_fields:
            QMessageBox.warning(self, "No field", "Select at least 1 disk map field.")
            return
        outdir = outdir_edit.text().strip()
        if not outdir:
            QMessageBox.warning(self, "No folder", "Choose a destination folder.")
            return
        layout_kind = "per_case" if radio_per_case.isChecked() else "flat"
        plot_kinds = ["disk_map"] if use_grid else [f"disk_map_{f}" for f in selected_fields]

        # VISIBLE progress (same rationale as `_generate_report`): this
        # export runs synchronously on the GUI thread and, with the full
        # grid (16 fields since Ft_i/Ft_p/Mach/q were added) times every
        # condition of every selected batch, it can take dozens of
        # seconds -- without this the button would just freeze, with no
        # sign that it is still running.
        flat, _ = self._condicoes_selecionadas()
        progresso = QProgressDialog(
            f"Exporting disk maps ({len(flat)} case(s))...\n"
            "This can take a moment for large batches.",
            None, 0, 0, self)
        progresso.setWindowTitle("Exporting disk maps")
        progresso.setWindowModality(Qt.WindowModality.ApplicationModal)
        progresso.setMinimumDuration(0)
        progresso.setCancelButton(None)
        progresso.show()
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        QApplication.processEvents()
        try:
            # ONE call with the whole selection, not one per entry: it is
            # `api.export_results` that resolves file names by POSITION
            # in the list (`nomes_de_arquivo_de_condicao`), so two
            # identically-named conditions coming from different runs get
            # distinct files without needing a subfolder per entry --
            # which, with loose Run Cases, created one folder per file.
            written = api.export_results(flat, outdir, plots=plot_kinds,
                                          save_csv=False, layout=layout_kind)
            progresso.close()
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Exported", f"{len(written)} file(s) generated in:\n{outdir}")
        except Exception as exc:
            progresso.close()
            QApplication.restoreOverrideCursor()
            show_error(self, "Error exporting disk maps", exc)

    # =====================================================================
    # Export / copy WHAT IS ON SCREEN
    # =====================================================================
    #: Per mode: (Export button label, Export tooltip, Copy label,
    #: Copy tooltip). The label names the OUTPUT, not the plot: whoever is on the
    #: table reads "Export table…", whoever is on a plot reads "Export plots…".
    _EXPORTACAO_POR_MODO = {
        "Disk map": (
            "Export plots…",
            "Writes the disk maps of every condition currently selected — "
            "batches and individual cases alike — to a folder. The next "
            "dialog chooses which fields (or the full grid) and how the "
            "files are organised.",
            "Copy figure",
            "Copies the disk map on screen to the clipboard as an image, "
            "ready to paste into a document or a slide."),
        "Coefficients vs axis": (
            "Export plots…",
            "Saves the panel grid on screen as one image file. It covers the "
            "whole selection, so there is a single figure to write.",
            "Copy figure",
            "Copies the panel grid on screen to the clipboard as an image."),
        "Azimuth / Radius": (
            "Export plots…",
            "Saves this plot for EVERY condition currently selected, one "
            "file per case, into a folder — not just the condition on "
            "screen. Same station list shown above.",
            "Copy figure",
            "Copies the plot on screen (the condition currently chosen) to "
            "the clipboard as an image."),
        "3D": (
            "Export plots…",
            "Saves the 3D view for EVERY condition currently selected, one "
            "image per case, with the colour and height fields chosen above. "
            "Needs the optional PyVista package.",
            "Copy figure",
            "Copies the 3D view on screen to the clipboard as an image. With "
            "the Plotly backend the view is interactive and cannot be "
            "copied as a bitmap — switch the backend to Matplotlib first."),
        "Table": (
            "Export table…",
            "Writes the table on screen to a file: CSV (comma) or TSV (tab), "
            "chosen by the extension in the save dialog. One row per "
            "condition, every summary column — the same table the report "
            "shows.",
            "Copy table",
            "Copies the table on screen to the clipboard as TSV — paste "
            "straight into a spreadsheet."),
        "Convergence": (
            "Export plots…",
            "Saves the convergence history for EVERY condition currently "
            "selected, one file per case, into a folder.",
            "Copy figure",
            "Copies the convergence plot on screen to the clipboard as an "
            "image."),
    }

    #: Modes whose export is ONE FILE PER CONDITION -- the screen shows
    #: one condition at a time, but the button exports the whole selection.
    _EXPORTACAO_POR_CONDICAO = {
        "Azimuth / Radius": None,          # rendered here (no type in api)
        "3D": "load_3d",                   # resolved with the chosen field
        "Convergence": "convergence",
    }

    @classmethod
    def _rotulos_de_exportacao(cls) -> tuple:
        """Every text the Export/Copy buttons can take on.

        The width has to fit the LONGEST of any mode: measured only from
        the current label, the button would change size on every mode
        switch and the three would stop being aligned exactly when the
        user looks at them."""
        textos = []
        for exp, _d1, cop, _d2 in cls._EXPORTACAO_POR_MODO.values():
            textos += [exp, cop]
        return tuple(textos)

    def _atualizar_botoes_de_exportacao(self):
        """Label, tooltip, and visibility of the three buttons, according to the mode."""
        modo = self._current_mode()
        rotulos = self._EXPORTACAO_POR_MODO.get(modo)
        tem_selecao = len(self._condicoes_selecionadas()[0]) >= 1
        if rotulos is None:
            self.btn_export.setVisible(False)
            return
        exp_texto, exp_dica, copy_texto, copy_dica = rotulos
        self.btn_export.setText(exp_texto)
        self.btn_export.setToolTip(exp_dica)
        self.btn_export.setVisible(tem_selecao)
        self.btn_copy.setText(copy_texto)
        self.btn_copy.setToolTip(copy_dica)
        self.btn_copy.setEnabled(tem_selecao)
        uniformizar_largura_de_botoes(self._botoes_de_exportacao,
                                       rotulos_extras=self._rotulos_de_exportacao())

    def _figura_da_tela(self):
        """The matplotlib `Figure` currently visible, or ``None``.

        ``None`` when the screen is in Plotly (the figure is HTML in a
        WebEngine, not a bitmap) or when the canvas shows a message
        instead of a plot -- the two cases "copy figure" needs to
        distinguish from an error."""
        if self.canvas_stack.currentIndex() != 0:
            return None
        canvas = getattr(self.canvas_host, "_current", None)
        return getattr(canvas, "figure", None) if canvas is not None else None

    def _copiar_da_tela(self):
        """Ctrl+C of what is on screen: the TABLE as TSV, or the FIGURE as
        an image. A single "Copy table" button on a tab where five of the
        six modes are plots used to copy what was not even in view."""
        if self._current_mode() == "Table":
            self._copy_table()
            return
        fig = self._figura_da_tela()
        if fig is None:
            QMessageBox.information(
                self, "Nothing to copy",
                "This view is not a static image right now. Interactive "
                "(Plotly) plots cannot be copied as a bitmap — switch the "
                "plot backend to Matplotlib, or use Export.")
            return
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=200,
                    facecolor=fig.get_facecolor())
        imagem = QImage.fromData(buffer.getvalue(), "PNG")
        if imagem.isNull():
            QMessageBox.warning(self, "Could not copy",
                                 "The figure could not be rendered to an image.")
            return
        QApplication.clipboard().setImage(imagem)
        self._avisar_na_barra("Figure copied to the clipboard.")

    def _avisar_na_barra(self, texto: str, ms: int = 4000):
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(texto, ms)

    def _exportar_da_tela(self):
        """Dispatches to the export for the CURRENT MODE (see
        `_EXPORTACAO_POR_MODO`)."""
        modo = self._current_mode()
        try:
            if modo == "Disk map":
                self._export_disk_maps_da_selecao()
            elif modo == "Table":
                self._exportar_tabela()
            elif modo in self._EXPORTACAO_POR_CONDICAO:
                self._exportar_por_condicao(modo)
            else:
                self._exportar_figura_unica()
        except Exception as exc:
            show_error(self, "Error exporting", exc)

    def _exportar_tabela(self):
        """CSV or TSV -- the separator comes from the CHOSEN EXTENSION,
        not from a second dialog asking again what the extension already said."""
        entries = self._selected_entries()
        if not entries:
            QMessageBox.warning(self, "Nothing selected", self._AVISO_AO_MENOS_UM)
            return
        destino, _filtro = QFileDialog.getSaveFileName(
            self, "Save table", str(self._pasta_de_saida_padrao() / "summary.csv"),
            "Comma-separated (*.csv);;Tab-separated (*.tsv *.txt)")
        if not destino:
            return
        sep = "\t" if Path(destino).suffix.lower() in (".tsv", ".txt") else ","
        rows, header = self._summary_rows(plots.flatten_selection(entries))
        with open(destino, "w", encoding="utf-8", newline="") as f:
            f.write(sep.join(header) + "\n")
            for row in rows:
                f.write(sep.join(row) + "\n")
        QMessageBox.information(self, "Exported",
                                 f"{len(rows)} row(s) written to:\n{destino}")

    def _exportar_figura_unica(self):
        """Aggregate modes (one plot for the whole selection): saves the
        figure that is on screen, exactly as it is."""
        fig = self._figura_da_tela()
        if fig is None:
            QMessageBox.information(
                self, "Nothing to export",
                "This view is not a static image right now. Interactive "
                "(Plotly) plots cannot be saved from here — use the plot's "
                "own camera icon, or switch the backend to Matplotlib.")
            return
        destino, _filtro = QFileDialog.getSaveFileName(
            self, "Save plot", str(self._pasta_de_saida_padrao() / "plot.png"),
            "PNG image (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not destino:
            return
        fig.savefig(destino, dpi=200, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        QMessageBox.information(self, "Exported", f"File written:\n{destino}")

    def _exportar_por_condicao(self, modo: str):
        """Modes that show ONE condition at a time: exports the WHOLE
        selection, one file per case.

        It is the explicit request -- "it will export every plot of that
        screen". The screen shows one case because only one fits; the
        export has no such limitation, and exporting only what is visible
        would force repeating the gesture once per condition of a batch."""
        flat, _ = self._condicoes_selecionadas()
        if not flat:
            QMessageBox.warning(self, "Nothing to export", self._AVISO_AO_MENOS_UM)
            return
        if modo == "3D" and not require_optional_package(self, "pyvista"):
            return
        outdir = QFileDialog.getExistingDirectory(
            self, "Destination folder", str(self._pasta_de_saida_padrao()))
        if not outdir:
            return

        if modo == "Azimuth / Radius":
            escritos = self._salvar_azrad_de_cada_condicao(flat, outdir)
        else:
            tipo = self._EXPORTACAO_POR_CONDICAO[modo]
            if modo == "3D":
                tipo = f"load_3d_{self._campo_3d_selecionado()}"
            escritos = api.export_results(flat, outdir, plots=[tipo],
                                           save_csv=False,
                                           project=self.state.project)
        if escritos:
            QMessageBox.information(
                self, "Exported",
                f"{len(escritos)} file(s) generated in:\n{outdir}")
        else:
            QMessageBox.warning(
                self, "Nothing generated",
                "No file could be produced for this view. For 3D this "
                "usually means PyVista is missing or the chosen field is "
                "not in these results; for convergence, that the runs were "
                "made with history collection off.")

    def _salvar_azrad_de_cada_condicao(self, flat: list, outdir: str) -> list:
        """One azimuth/radius PNG per condition, with the SAME stations
        that are on screen (not a default list)."""
        por_raio = self.azrad_mode_combo.currentText().startswith("Loads vs radius")
        if por_raio:
            alvos = parse_list(self.azrad_psi_edit.text()) or [0.0, 90.0, 180.0, 270.0]
        else:
            alvos = parse_list(self.azrad_r_edit.text()) or [0.25, 0.5, 0.75, 0.95]
        nomes = api.nomes_de_arquivo_de_condicao(flat)
        prefixo = "loads_vs_radius" if por_raio else "loads_vs_azimuth"
        escritos = []
        for resultado, nome in zip(flat, nomes):
            fig = (plots.plot_loads_vs_radius(resultado.maps, psi_targets_deg=alvos)
                   if por_raio else
                   plots.plot_loads_vs_azimuth(resultado.maps, r_norm_targets=alvos))
            caminho = str(Path(outdir) / f"{prefixo}_{nome}.png")
            fig.savefig(caminho, dpi=150, bbox_inches="tight")
            escritos.append(caminho)
        return escritos

    # --- exportable report / copy table (Part 6.5) ------------------------

    def _copy_table(self):
        """TSV via QApplication.clipboard() -- one row per Results in the
        current selection (`flatten_selection`), columns = union of every
        `Results.summary` key seen (the same table the report uses)."""
        entries = self._selected_entries()
        if not entries:
            QMessageBox.warning(self, "Nothing selected",
                                 "Select at least 1 result in the list on the left.")
            return
        flat = plots.flatten_selection(entries)
        rows, header = self._summary_rows(flat)
        lines = ["\t".join(header)]
        for row in rows:
            lines.append("\t".join(row))
        QApplication.clipboard().setText("\n".join(lines))
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(f"{len(rows)} row(s) copied (TSV).", 4000)

    def _summary_rows(self, flat: list):
        principais, cfg = api.summary_keys_union(flat, self._modo_helice())
        keys = principais + cfg
        header = ["condition_name"] + keys
        rows = []
        for r in flat:
            row = [r.condition_name or ""]
            for k in keys:
                v = r.summary.get(k, "")
                row.append(api.format_summary_value(v) if isinstance(v, float) else str(v))
            rows.append(row)
        return rows, header

    def _generate_report(self):
        """One-click "Generate report" (docs/plano_v3.md Part 6.5): a
        single HTML with a summary table + plots applicable to the
        selection, reusing `flatten_selection` + `api.export_results`.
        When the selection has batches, embeds the batch disk maps from
        Part 4.3 as an appendix (not just as loose PNGs)."""
        entries = self._selected_entries()
        if not entries:
            QMessageBox.warning(self, "Nothing selected",
                                 "Select at least 1 result in the list on the left.")
            return
        default_path = str(self._pasta_de_saida_padrao() / "report.html")
        # `getSaveFileName` confirms before overwriting (Qt's default,
        # and nothing here passes `DontConfirmOverwrite`): an existing
        # `report.html` never disappears without the user saying yes.
        path, _ = QFileDialog.getSaveFileName(self, "Save report", default_path,
                                                "HTML (*.html)")
        if not path:
            return
        flat = plots.flatten_selection(entries)
        dlg = QDialog(self)
        dlg.setWindowTitle("Report export settings")
        form = QFormLayout(dlg)
        dpi_combo = QComboBox()
        for dpi in (72, 100, 150, 200, 300):
            dpi_combo.addItem(f"{dpi} DPI", dpi)
        dpi_combo.setCurrentIndex(2)
        form.addRow("Figure resolution:", dpi_combo)
        checks = []
        for key, label, checked in (("blade_geometry", "Blade geometry", True),
                                    ("airfoil_polar", "Airfoil polars", True),
                                    ("coefficients", "Performance coefficients", len(flat) > 1),
                                    ("azimuth", "Loads along azimuth", True),
                                    ("span", "Loads along blade span", True),
                                    ("disk_map", "Disk maps (13 figures per case)", len(flat) <= 12),
                                    ("convergence", "Convergence", True)):
            box = QCheckBox(label)
            box.setChecked(checked)
            checks.append((key, box))
            form.addRow("", box)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Generate")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        dpi = int(dpi_combo.currentData())
        plot_kinds = [key for key, box in checks if box.isChecked()]
        # Visible progress while the report is generated. The heavy work
        # runs in `ReportWorker` on a QThread; this window stays on the
        # main thread and keeps the interface responsive.
        progresso = QProgressDialog(
            f"Generating report ({len(flat)} case(s))...\n"
            "The application remains usable while the report is generated.",
            None, 0, 0, self)
        progresso.setWindowTitle("Generating report")
        progresso.setWindowModality(Qt.WindowModality.NonModal)
        progresso.setMinimumDuration(0)
        progresso.setCancelButton(None)
        progresso.show()
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            # The HTML assembly lives in `api.generate_report`: it writes
            # to disk (layering rule) and, by living there, the button
            # here, the CLI's `--report`, and a Python script all produce
            # the SAME report. `project` goes along so the header can
            # record the mesh/solver/rotor -- that is what makes the
            # report reproducible.
            # No `notes=`: the automatic note used to be just "Selection: "
            # followed by the concatenation of EVERY condition, printed
            # right above the summary table that already lists those same
            # conditions, one per row and readable. The `notes` parameter
            # still exists for a genuine note (the CLI's
            # `--report-notes`, a script).
            self._report_progress = progresso
            self.btn_generate_report.setEnabled(False)
            worker = ReportWorker(flat, path, project=self.state.project,
                                  plots=plot_kinds, dpi=dpi)
            worker.finished.connect(self._on_report_finished)
            worker.failed.connect(self._on_report_failed)
            self._report_worker = worker
            self._report_thread = launch_worker(worker)
            return
        except Exception as exc:
            progresso.close()
            QApplication.restoreOverrideCursor()
            show_error(self, "Error generating report", exc)
            return
        progresso.close()
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "Report generated", f"Report saved in:\n{path}")

    def _encerrar_exportacao_de_relatorio(self):
        progresso = getattr(self, "_report_progress", None)
        if progresso is not None:
            progresso.close()
            self._report_progress = None
        QApplication.restoreOverrideCursor()
        self.btn_generate_report.setEnabled(True)
        self._report_thread = None
        self._report_worker = None

    def _on_report_finished(self, path: str):
        self._encerrar_exportacao_de_relatorio()
        QMessageBox.information(self, "Report generated", f"Report saved in:\n{path}")

    def _on_report_failed(self, mensagem: str):
        self._encerrar_exportacao_de_relatorio()
        show_error(self, "Error generating report", mensagem)


