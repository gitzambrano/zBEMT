"""In-app contextual help popup (Layer 2 and 3 of the documentation plan).

Singleton per root window: opening a second popup closes the first one.
Closes with Escape or a click outside the popup.
"""
from __future__ import annotations

import re

from PyQt6.QtCore import Qt, QEvent, QObject, QPoint, QSize
from PyQt6.QtGui import QKeyEvent, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .common import open_help


#: Space between paragraphs, in pixels.
_ESPACO_ENTRE_PARAGRAFOS = 6


def em_paragrafos(texto: str) -> str:
    """Converts the double line breaks in the help text into real
    PARAGRAPHS.

    This window's `QLabel`s are `RichText`, and RichText collapses
    whitespace: a `\\n\\n` in the middle of the explanation separated
    nothing -- rotor and propeller came out glued together in the same
    run-on block, which is exactly the hardest text in the help to read
    (two different conventions, one spliced onto the other).

    A lone `\\n` is still just whitespace, as in any HTML: only the blank
    line marks a paragraph. Text without a double break passes through
    intact, without gaining a `<p>` -- the `<p>` adds margin, and in a
    one-line text that would only push neighboring fields apart."""
    if not texto:
        return ""
    partes = [p.strip() for p in re.split(r"\n[ \t]*\n", texto) if p.strip()]
    if len(partes) <= 1:
        return texto
    return "".join(
        f'<p style="margin:0 0 {_ESPACO_ENTRE_PARAGRAFOS}px 0">{p}</p>'
        for p in partes)

# Fixed popup width in pixels. A larger width reduces unnecessary line
# breaks and lowers the popup's total height.
#
# This value NEVER had a real effect until this session: `_scroll` (the
# body's QScrollArea) had no width of its own fixed, and since `outer`
# uses SetFixedSize, it was QScrollArea's small, fixed sizeHint (~256px)
# that decided the popup's real width, not this constant -- see the
# comment in `_posicionar`. The popup always rendered much narrower than
# the design value (which is why the minimum-width test never caught the
# regression: it only read the CONSTANT, not the real screen width).
# With `_posicionar` fixed (`self._scroll.setFixedWidth(...)`), the value
# started to take effect for the first time -- and 1285 (the original
# number) turned out too wide on a real screen. 560 -> 504 (-10%), at the
# user's request after seeing the popup at its real width for the first
# time.
_LARGURA = 504
# Minimum margin from the screen edge
_MARGEM_BORDA = 12
#: Gap between the body's last line and the footer separator, in px.
#: Zero leaves the text touching the rule; the value equals about one
#: line of text -- it is breathing room, not the two-or-three-line empty
#: band that the `sizeHint()` calculation used to produce (see
#: `_posicionar`).
_RESPIRO_NO_FIM = 10
#: Font size of the rendered equation, in points (aligns with the text
#: font). An attempt to raise it to 10.5 (matplotlib's mathtext has a
#: cap-height/nominal size a bit smaller than Qt's font, so "10pt" on
#: both back-ends does not produce the same x-height in pixels) caused a
#: worse problem: the equation image is not resized to fit the popup's
#: width (`_adicionar_equacao` only uses the pixmap at its rendered
#: size), so the widest equation in the file started getting cut off at
#: the popup's right edge -- the requirement "never cut off an equation"
#: outweighs matching the surrounding text's size exactly. Reverted to
#: the original value.
_PONTOS_EQUACAO = 9.5


def _cache_de_equacoes() -> dict:
    """Pixmap cache keyed by (latex, dpr) -- rendering with mathtext costs
    a few milliseconds and the same popup reopens many times."""
    if not hasattr(_cache_de_equacoes, "_d"):
        _cache_de_equacoes._d = {}
    return _cache_de_equacoes._d


def renderizar_equacao(latex: str, dpr: float | None = None):
    """LaTeX -> QPixmap via matplotlib's mathtext.

    The popup used to show the equation as `<code>` -- raw text, with the
    same look as a variable name, and without a real fraction, exponent,
    subscript, or integral. Since the rest of the project already draws
    math labels with mathtext (it is what the HTML report uses for the
    column symbols), the same machinery serves here without adding a
    dependency.

    Returns ``None`` when there is no matplotlib or when mathtext rejects
    the expression -- the caller falls back to plain text. Never raises:
    a malformed equation in `help_content` must not bring down the help.
    """
    if not latex:
        return None
    # Not every `help_content` entry is an equation: some are prose
    # ("origin ∈ {preset, import, manual} (metadata only)"). mathtext
    # ACCEPTS prose and returns an italic with the spaces collapsed
    # ("origin∈preset, import, manual(metadataonly)") -- worse than plain
    # text. Every real expression carries at least one LaTeX command;
    # without a backslash, it is prose and goes down the text path.
    if "\\" not in latex and "_" not in latex and "^" not in latex:
        return None
    if dpr is None:
        tela = QApplication.primaryScreen()
        dpr = tela.devicePixelRatio() if tela else 1.0
    chave = (latex, round(float(dpr), 2))
    cache = _cache_de_equacoes()
    if chave in cache:
        return cache[chave]

    pixmap = None
    try:
        import io

        import matplotlib
        matplotlib.use("Agg", force=False)
        from matplotlib import figure as _figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        from PyQt6.QtGui import QImage, QPixmap

        expressao = latex if latex.strip().startswith("$") else f"${latex}$"
        fig = _figure.Figure(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0.0)
        FigureCanvasAgg(fig)
        texto = fig.text(0, 0, expressao, fontsize=_PONTOS_EQUACAO, color="#1a2030")
        buf = io.BytesIO()
        # `bbox_inches="tight"` with a small pad crops the figure to the
        # exact rectangle of the text -- without it the whole figure's
        # slack remains.
        fig.savefig(buf, format="png", dpi=96 * dpr, transparent=True,
                    bbox_inches="tight", pad_inches=0.02)
        del texto
        buf.seek(0)
        imagem = QImage.fromData(buf.getvalue(), "PNG")
        if not imagem.isNull():
            imagem.setDevicePixelRatio(dpr)
            pixmap = QPixmap.fromImage(imagem)
    except Exception:
        pixmap = None

    cache[chave] = pixmap
    return pixmap


class _FiltroFechamento(QObject):
    """Application-installed event filter: closes the popup on the first
    click outside it."""

    def __init__(self, popup: "HelpPopup"):
        super().__init__(popup)
        self._popup = popup

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = QApplication.instance().activeWindow()
            # closes if the click was not inside the popup
            if not self._popup.geometry().contains(
                self._popup.mapFromGlobal(
                    QApplication.widgetAt(
                        event.globalPosition().toPoint()  # type: ignore[attr-defined]
                    ).mapToGlobal(QPoint(0, 0))
                    if QApplication.widgetAt(event.globalPosition().toPoint())  # type: ignore[attr-defined]
                    else QPoint(-9999, -9999)
                )
            ):
                self._popup.fechar()
        return False


class HelpPopup(QFrame):
    """Frameless popup with contextual help for a field or a block.

    Usage:
        popup = HelpPopup.instancia(janela_pai)
        popup.mostrar_campo("n_blades", referencia_widget)
        popup.mostrar_bloco("aerodynamic_model", referencia_widget)
    """

    # Singleton per root window
    _instancias: dict[int, "HelpPopup"] = {}

    @classmethod
    def instancia(cls, pai: QWidget) -> "HelpPopup":
        raiz = pai.window()
        chave = id(raiz)
        if chave not in cls._instancias:
            cls._instancias[chave] = cls(raiz)
        return cls._instancias[chave]

    def __init__(self, pai: QWidget):
        super().__init__(pai, Qt.WindowType.ToolTip)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setFixedWidth(_LARGURA)
        self.setStyleSheet(
            "HelpPopup { background: #fefefe; border: 1px solid #c0c8d8;"
            " border-radius: 6px; }"
        )
        self._filtro: _FiltroFechamento | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)
        # The popup must measure only the current content. A free size
        # policy lets QLayout retain the previous content's height and
        # creates empty bands before/after the title on quick swaps.
        outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # Title (bold). The VERTICAL size policy needs to be Fixed: with
        # the default Preferred, the title was the only widget willing to
        # grow and it absorbed all the slack left over from the body
        # (just removed, with sizeHint still stale), showing up as a huge
        # empty band above and below the text.
        self._lbl_titulo = QLabel()
        fonte_titulo = QFont()
        fonte_titulo.setBold(True)
        fonte_titulo.setPointSize(10)
        self._lbl_titulo.setFont(fonte_titulo)
        self._lbl_titulo.setWordWrap(True)
        self._lbl_titulo.setSizePolicy(QSizePolicy.Policy.Preferred,
                                       QSizePolicy.Policy.Fixed)
        self._lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignLeft
                                      | Qt.AlignmentFlag.AlignTop)
        outer.addWidget(self._lbl_titulo, 0)

        # Separator
        sep1 = QFrame(); sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #d0d8e8;")
        outer.addWidget(sep1)

        # Body (content rows assembled dynamically).
        self._corpo_widget = QWidget()
        self._corpo = QVBoxLayout(self._corpo_widget)
        self._corpo.setContentsMargins(0, 0, 0, 0)
        self._corpo.setSpacing(5)
        self._corpo.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._corpo_widget)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Preferred)
        self._scroll.setMinimumHeight(0)
        # The definitive limit is recomputed for each monitor's screen in
        # `_posicionar`; this initial value avoids a short window before
        # the first positioning.
        self._scroll.setMaximumHeight(1000)
        outer.addWidget(self._scroll, 1)

        # Separator
        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #d0d8e8;")
        outer.addWidget(sep2)

        # "Open full documentation →" button
        self._btn_doc = QPushButton("Open full documentation →")
        self._btn_doc.setFlat(True)
        self._btn_doc.setStyleSheet(
            "QPushButton { color: #3a6dbd; text-align: left; padding: 0; border: none; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self._btn_doc.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ancora_atual: str | None = None
        self._btn_doc.clicked.connect(self._abrir_doc)
        outer.addWidget(self._btn_doc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mostrar_campo(self, campo: str, perto_de: QWidget) -> None:
        """Shows a popup with the field's information (from
        `help_content.FIELD_HELP`)."""
        from .. import api
        from . import help_content
        from .field_help import ancora_do_campo
        dados = help_content.FIELD_HELP.get(campo)
        if not dados:
            return
        # The anchor is DERIVED from the documentation (physics section
        # that explains the field); `FIELD_HELP["anchor"]` is just a
        # fallback — it points to the field table row, which is the
        # "generic box" the user complained about.
        self._ancora_atual = ancora_do_campo(campo) or dados.get("anchor")
        self._lbl_titulo.setText(api._descricao_com_simbolos(dados.get("title", campo)))
        self._limpar_corpo()

        self._adicionar_linha(dados.get("definition", ""))

        if dados.get("unit"):
            self._adicionar_par("Unit", dados["unit"])
        if dados.get("equation"):
            self._adicionar_equacao(dados["equation"])
        if dados.get("effect"):
            self._adicionar_par("Effect", dados["effect"])
        if dados.get("range"):
            self._adicionar_par("Typical range", dados["range"])

        # Enum options: each option as a bullet
        options = dados.get("options")
        if options:
            self._adicionar_linha("<b>Options:</b>")
            for chave, desc in options.items():
                self._adicionar_linha(f"  <b>{chave}</b> — {desc}", indent=8)

        self._posicionar(perto_de)
        self._instalar_filtro()
        self.show()

    def mostrar_bloco(self, bloco: str, perto_de: QWidget) -> None:
        """Shows a popup with the conceptual explanation of a block (from
        `help_blocks.BLOCK_HELP`)."""
        from .. import api
        from . import help_blocks
        dados = help_blocks.BLOCK_HELP.get(bloco)
        if not dados:
            return
        self._ancora_atual = dados.get("anchor")
        self._lbl_titulo.setText(api._descricao_com_simbolos(dados.get("title", bloco)))
        self._limpar_corpo()

        for paragrafo in dados.get("body", []):
            self._adicionar_linha(paragrafo)

        self.setFixedWidth(max(_LARGURA, 500))
        self._posicionar(perto_de)
        self._instalar_filtro()
        self.show()

    def fechar(self) -> None:
        try:
            self.hide()
            self.setFixedWidth(_LARGURA)  # reset for field (block may have widened it)
        except RuntimeError:
            pass  # widget destroyed by Qt — nothing to do
        if self._filtro:
            app = QApplication.instance()
            if app:
                try:
                    app.removeEventFilter(self._filtro)
                except RuntimeError:
                    pass
            self._filtro = None

    # ------------------------------------------------------------------
    # Escape key
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.fechar()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _limpar_corpo(self) -> None:
        """Empties the body NOW, not on the next event cycle."""
        while self._corpo.count():
            item = self._corpo.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                try:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
                except RuntimeError:
                    pass  # widget already destroyed by Qt

    def _adicionar_linha(self, texto: str, indent: int = 0) -> None:
        if "$$" in texto:
            partes = texto.split("$$")
            for i, parte in enumerate(partes):
                parte_limpa = parte.strip()
                if not parte_limpa:
                    continue
                if i % 2 == 1:
                    # LaTeX equation block between $$
                    self._adicionar_equacao(parte_limpa)
                else:
                    self._adicionar_linha_texto(parte_limpa, indent=indent)
        else:
            self._adicionar_linha_texto(texto, indent=indent)

    def _adicionar_linha_texto(self, texto: str, indent: int = 0) -> None:
        from .. import api
        lbl = QLabel(em_paragrafos(api._descricao_com_simbolos(texto)))
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        if indent:
            lbl.setContentsMargins(indent, 0, 0, 0)
        self._corpo.addWidget(lbl)

    def _adicionar_par(self, rotulo: str, valor: str) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.setAlignment(Qt.AlignmentFlag.AlignTop)
        lbl_r = QLabel(f"<b>{rotulo}:</b>")
        lbl_r.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        lbl_r.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        from .. import api
        lbl_v = QLabel(em_paragrafos(api._descricao_com_simbolos(valor)))
        lbl_v.setWordWrap(True)
        lbl_v.setTextFormat(Qt.TextFormat.RichText)
        lbl_v.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl_v.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        row.addWidget(lbl_r)
        row.addWidget(lbl_v)
        container = QWidget()
        container.setLayout(row)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._corpo.addWidget(container)

    def _adicionar_equacao(self, eq: str) -> None:
        lbl = QLabel()
        pixmap = renderizar_equacao(eq)
        if pixmap is not None:
            lbl.setPixmap(pixmap)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        else:
            lbl.setText(f"<code>{eq}</code>")
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setStyleSheet("background: transparent; padding: 1px 0px; margin: 1px 0px;")
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._corpo.addWidget(lbl)

    def _posicionar(self, ref: QWidget) -> None:
        """Positions the popup to the right of the reference widget;
        flips to the left if close to the edge."""
        janela = ref.window().windowHandle()
        tela_obj = (janela.screen() if janela is not None else None) \
            or QApplication.primaryScreen()
        tela = tela_obj.availableGeometry()

        # ── Step 1: fix the width ────────────────────────────────────────
        # Must come before any sizeHint query, since the width affects
        # the height computed by the text layout.
        #
        # `outer` uses `SetFixedSize` (comment in `__init__`): Qt does not
        # merely SUGGEST the popup's size from `layout.sizeHint()`, it
        # LOCKS minimumSize/maximumSize to that value every time the
        # layout is activated (`layout.activate()`, called in Step 2 and
        # Step 4) -- even over an explicit `setFixedWidth()` on the outer
        # widget. And `QScrollArea.sizeHint()` returns a small, fixed
        # value (~256px) regardless of content -- so the popup's real
        # width was always that, and `self.setFixedWidth(largura)` alone
        # never had any effect (which is why raising `_LARGURA` from 1285
        # to 2005 changed nothing on screen: the value never even got
        # used). The `_scroll` width needs to be fixed TOO, so that the
        # outer layout's `sizeHint()` -- what `SetFixedSize` actually
        # uses -- is already correct from the start.
        largura = min(_LARGURA, max(390, tela.width() - 2 * _MARGEM_BORDA))
        self.setFixedWidth(largura)
        margens = self.layout().contentsMargins()
        self._scroll.setFixedWidth(largura - margens.left() - margens.right())

        # ── Step 2: force layout propagation at the new width ───────────
        layout = self.layout()
        if layout is not None:
            layout.invalidate()
            layout.activate()

        # ── Step 3: compute the content's real height ────────────────────
        # QScrollArea.sizeHint() returns a fixed ~256×192 px, regardless
        # of content. The inner widget must be queried directly.
        #
        # `outer.activate()` (step 2) resizes the QScrollArea and, in
        # turn, the `_corpo_widget` (widgetResizable=True resizes the
        # inner widget synchronously). But the *layout recalculation* of
        # that widget -- the QLabel line wrapping at the new width, which
        # is what determines each paragraph's real height -- is scheduled
        # by Qt as a LayoutRequest and only runs on the next event-loop
        # turn. Without forcing that recalculation here, `sizeHint()`
        # below still reflects the PREVIOUS popup's wrap width (singleton
        # reopened for a different field), the real text ends up taller
        # than the reserved height, and the tail of every long paragraph
        # gets overlapped by the next widget in the column -- read by the
        # user as "cut-off text".
        # The body widgets need to be VISIBLE before measuring. A
        # `QLayoutItem` whose widget is hidden counts as empty, and the
        # layout's `heightForWidth`/`sizeHint` return -1/0 -- the entire
        # body "measuring zero". Not hypothetical: `_posicionar` runs
        # BEFORE `self.show()` in `mostrar_bloco`/`mostrar_campo`, and on
        # popup REOPEN (singleton, already hidden by `fechar()`) the
        # freshly-created rows inherited that state. The symptom would be
        # the popup opening at minimum height with all the text behind
        # the scrollbar.
        for i in range(self._corpo.count()):
            item = self._corpo.itemAt(i)
            w = item.widget() if item is not None else None
            if w is not None:
                w.show()
        self._corpo.invalidate()
        self._corpo.activate()
        max_scroll_h = max(600, tela.height() - 40)
        # HEIGHT FROM THE REAL WIDTH, not from sizeHint. A `QLabel` with
        # `wordWrap` returns in `sizeHint()` the height of an IDEAL line
        # wrap that Qt picks on its own (close to a square rectangle),
        # not the one for the width the label will actually be drawn at:
        # in the "Dynamic Stall (Øye)" block the first paragraph asks for
        # 154 px of sizeHint against 98 px real at 480 px of width. Added
        # across the twelve widgets, the body reserved ~790 px for 618 px
        # of text -- the two-to-three-line empty band left over below
        # EVERY popup. `QBoxLayout.heightForWidth` walks the same items
        # asking for the height AT the given width, which is the correct
        # number. The width comes from the value FIXED in step 1, not
        # from `_corpo_widget.width()`: the real geometry is only applied
        # on the next event-loop turn, and reading it here brings in the
        # PREVIOUS popup's width -- the same lag that already forced the
        # `invalidate()/activate()` calls above.
        #
        # The vertical scrollbar is not part of the count, and that is
        # not an oversight: while the content FITS there is no scrollbar
        # at all, and that is exactly the case where the height needs to
        # be exact (it is what decides the popup's size). When it does
        # not fit, the height becomes `max_scroll_h` regardless and the
        # width error does not change the outcome.
        # ALWAYS subtracts the vertical scrollbar. It does not always
        # appear, but `QScrollArea` reserves its strip in the viewport
        # regardless (measured: 466 px viewport for a 480 px area), and
        # it is in the viewport that the text wraps. Measuring at 480 px
        # underestimates the height by a few dozen pixels in long blocks
        # -- the last line ended up behind the border. The error in the
        # other direction costs a few pixels of slack and hides nothing.
        barra = self._scroll.verticalScrollBar().sizeHint().width()
        content_h = self._corpo.heightForWidth(
            max(120, self._scroll.width() - barra))
        if content_h <= 0:                       # no item with wordWrap
            content_h = self._corpo_widget.sizeHint().height()
        # scroll_h = what the content needs (+ breathing room), capped to screen.
        scroll_h = min(max(content_h + _RESPIRO_NO_FIM, 40), max_scroll_h)
        # `setFixedHeight`, not `setMinimumHeight` + loose maximum: for the
        # same reason as width in step 1, `QScrollArea.sizeHint()` is a
        # default value (~288 px height) that ignores the content, and the
        # external layout's `SetFixedSize` sizes the popup by this sizeHint
        # whenever it is GREATER than the minimum asked for. A short block
        # would then stretch to 288 px, and the difference appeared as an
        # empty band below the text. Locking both ends, the requested height
        # is used; when content exceeds the screen, `scroll_h` is already
        # `max_scroll_h` and the scrollbar takes over.
        self._scroll.setFixedHeight(scroll_h)

        # ── Step 4: adjust total popup size ────────────────────────
        if layout is not None:
            layout.invalidate()
            layout.activate()
        self.adjustSize()

        # ── Step 5: position on screen ────────────────────────────
        pos_global = ref.mapToGlobal(QPoint(ref.width() + 4, 0))
        if pos_global.x() + self.width() + _MARGEM_BORDA > tela.right():
            pos_global = ref.mapToGlobal(QPoint(-self.width() - 4, 0))
        pos_global.setX(max(tela.left() + _MARGEM_BORDA,
                            min(pos_global.x(),
                                tela.right() - self.width() - _MARGEM_BORDA)))
        pos_global.setY(
            max(tela.top() + _MARGEM_BORDA,
                min(pos_global.y(), tela.bottom() - self.height() - _MARGEM_BORDA))
        )
        self.move(pos_global)

    def _instalar_filtro(self) -> None:
        if self._filtro:
            QApplication.instance().removeEventFilter(self._filtro)
        self._filtro = _FiltroFechamento(self)
        QApplication.instance().installEventFilter(self._filtro)

    def _abrir_doc(self) -> None:
        if self._ancora_atual:
            open_help(self, anchor=self._ancora_atual)
        self.fechar()
