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
_PARAGRAPH_SPACING = 6


def in_paragraphs(text: str) -> str:
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
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"\n[ \t]*\n", text) if p.strip()]
    if len(parts) <= 1:
        return text
    return "".join(
        f'<p style="margin:0 0 {_PARAGRAPH_SPACING}px 0">{p}</p>'
        for p in parts)

# Fixed popup width in pixels. A larger width reduces unnecessary line
# breaks and lowers the popup's total height.
#
# This value NEVER had a real effect until this session: `_scroll` (the
# body's QScrollArea) had no width of its own fixed, and since `outer`
# uses SetFixedSize, it was QScrollArea's small, fixed sizeHint of about 256px
# that decided the popup's real width, not this constant -- see the
# comment in `_position`. The popup always rendered much narrower than
# the design value (which is why the minimum-width test never caught the
# regression: it only read the CONSTANT, not the real screen width).
# With `_position` fixed (`self._scroll.setFixedWidth(...)`), the value
# started to take effect for the first time -- and 1285 (the original
# number) turned out too wide on a real screen. 560 -> 504 (-10%), at the
# user's request after seeing the popup at its real width for the first
# time.
_WIDTH = 504
# Upper bounds for the popup's width, applied wherever the size is
# decided (`_position`, the only path): the smaller of 92% of the
# current monitor's available width and this hard readability cap.
# Without them the natural width follows the content, and long
# unbreakable tokens (grammar strings like "cst:a1,a2,...", equations)
# can push the popup past the screen edge.
_MAX_PIXEL_WIDTH = 760
_MAX_WIDTH_FRACTION = 0.92
# Minimum margin from the screen edge
_SCREEN_MARGIN = 12
#: Gap between the body's last line and the footer separator, in px.
#: Zero leaves the text touching the rule; the value equals about one
#: line of text -- it is breathing room, not the two-or-three-line empty
#: band that the `sizeHint()` calculation used to produce (see
#: `_position`).
_BOTTOM_BREATHING_ROOM = 10
#: Font size of the rendered equation, in points (aligns with the text
#: font). An attempt to raise it to 10.5 (matplotlib's mathtext has a
#: cap-height/nominal size a bit smaller than Qt's font, so "10pt" on
#: both back-ends does not produce the same x-height in pixels) caused a
#: worse problem: the equation image is not resized to fit the popup's
#: width (`_add_equation` only uses the pixmap at its rendered
#: size), so the widest equation in the file started getting cut off at
#: the popup's right edge -- the requirement "never cut off an equation"
#: outweighs matching the surrounding text's size exactly. Reverted to
#: the original value.
_EQUATION_FONT_POINTS = 9.5


def _equation_cache() -> dict:
    """Pixmap cache keyed by (latex, dpr): rendering with mathtext costs
    a few milliseconds and the same popup reopens many times."""
    if not hasattr(_equation_cache, "_d"):
        _equation_cache._d = {}
    return _equation_cache._d


def render_equation(latex: str, dpr: float | None = None):
    """LaTeX -> QPixmap via matplotlib's mathtext.

    The popup used to show the equation as `<code>` -- raw text, with the
    same look as a variable name, and without a real fraction, exponent,
    subscript, or integral. Since the rest of the project already draws
    math labels with mathtext (it is what the HTML report uses for the
    column symbols), the same machinery serves here without adding a
    dependency.

    Returns ``None`` when there is no matplotlib or when mathtext rejects
    the expression. The caller falls back to plain text. Never raises:
    a malformed equation in `help_content` must not bring down the help.
    """
    if not latex:
        return None
    # Not every `help_content` entry is an equation: some are prose
    # ("origin ∈ {preset, import, manual} (metadata only)"). mathtext
    # ACCEPTS prose and returns an italic with the spaces collapsed
    # ("origin∈preset, import, manual(metadataonly)"), which is worse
    # than plain text. Every real expression carries at least one LaTeX command;
    # without a backslash, it is prose and goes down the text path.
    if "\\" not in latex and "_" not in latex and "^" not in latex:
        return None
    if dpr is None:
        screen = QApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
    key = (latex, round(float(dpr), 2))
    cache = _equation_cache()
    if key in cache:
        return cache[key]

    pixmap = None
    try:
        import io

        import matplotlib
        matplotlib.use("Agg", force=False)
        from matplotlib import figure as _figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        from PyQt6.QtGui import QImage, QPixmap

        expression = latex if latex.strip().startswith("$") else f"${latex}$"
        fig = _figure.Figure(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0.0)
        FigureCanvasAgg(fig)
        text = fig.text(0, 0, expression, fontsize=_EQUATION_FONT_POINTS, color="#1a2030")
        buf = io.BytesIO()
        # `bbox_inches="tight"` with a small pad crops the figure to the
        # exact rectangle of the text -- without it the whole figure's
        # slack remains.
        fig.savefig(buf, format="png", dpi=96 * dpr, transparent=True,
                    bbox_inches="tight", pad_inches=0.02)
        del text
        buf.seek(0)
        image = QImage.fromData(buf.getvalue(), "PNG")
        if not image.isNull():
            image.setDevicePixelRatio(dpr)
            pixmap = QPixmap.fromImage(image)
    except Exception:
        pixmap = None

    cache[key] = pixmap
    return pixmap


class _CloseFilter(QObject):
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
                self._popup.close_popup()
        return False


class HelpPopup(QFrame):
    """Frameless popup with contextual help for a field or a block.

    Usage:
        popup = HelpPopup.instance(parent_window)
        popup.show_field("n_blades", reference_widget)
        popup.show_block("aerodynamic_model", reference_widget)
    """

    # Singleton per root window
    _instances: dict[int, "HelpPopup"] = {}

    @classmethod
    def instance(cls, parent: QWidget) -> "HelpPopup":
        root = parent.window()
        key = id(root)
        if key not in cls._instances:
            cls._instances[key] = cls(root)
        return cls._instances[key]

    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.WindowType.ToolTip)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setFixedWidth(_WIDTH)
        self.setStyleSheet(
            "HelpPopup { background: #fefefe; border: 1px solid #c0c8d8;"
            " border-radius: 6px; }"
        )
        self._close_filter: _CloseFilter | None = None
        # Equation labels of the CURRENT body, kept so `_position` can
        # shrink any rendered equation wider than the viewport (a QLabel
        # with a pixmap cannot wrap -- see `_fit_equations`).
        self._eq_labels: list[QLabel] = []

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
        self._title_label = QLabel()
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        self._title_label.setFont(title_font)
        self._title_label.setWordWrap(True)
        self._title_label.setSizePolicy(QSizePolicy.Policy.Preferred,
                                       QSizePolicy.Policy.Fixed)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignLeft
                                      | Qt.AlignmentFlag.AlignTop)
        outer.addWidget(self._title_label, 0)

        # Separator
        sep1 = QFrame(); sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #d0d8e8;")
        outer.addWidget(sep1)

        # Body (content rows assembled dynamically).
        self._body_widget = QWidget()
        self._body_layout = QVBoxLayout(self._body_widget)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(5)
        self._body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._body_widget)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Preferred)
        self._scroll.setMinimumHeight(0)
        # The definitive limit is recomputed for each monitor's screen in
        # `_position`; this initial value avoids a short window before
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
        self._current_anchor: str | None = None
        self._btn_doc.clicked.connect(self._open_docs)
        outer.addWidget(self._btn_doc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_field(self, field: str, near: QWidget) -> None:
        """Shows a popup with the field's information (from
        `help_content.FIELD_HELP`)."""
        from .. import api
        from . import help_content
        from .field_help import field_anchor
        data = help_content.FIELD_HELP.get(field)
        if not data:
            return
        # The anchor is DERIVED from the documentation (physics section
        # that explains the field); `FIELD_HELP["anchor"]` is just a
        # fallback — it points to the field table row, which is the
        # "generic box" the user complained about.
        self._current_anchor = field_anchor(field) or data.get("anchor")
        self._title_label.setText(api._description_with_symbols(data.get("title", field)))
        self._clear_body()

        self._add_line(data.get("definition", ""))

        if data.get("unit"):
            self._add_pair("Unit", data["unit"])
        if data.get("equation"):
            self._add_equation(data["equation"])
        if data.get("effect"):
            self._add_pair("Effect", data["effect"])
        if data.get("range"):
            self._add_pair("Typical range", data["range"])

        # Enum options: each option as a bullet
        options = data.get("options")
        if options:
            self._add_line("<b>Options:</b>")
            for key, desc in options.items():
                self._add_line(f"  <b>{key}</b> — {desc}", indent=8)

        self._position(near)
        self._install_filter()
        self.show()

    def show_block(self, block: str, near: QWidget) -> None:
        """Shows a popup with the conceptual explanation of a block (from
        `help_blocks.BLOCK_HELP`)."""
        from .. import api
        from . import help_blocks
        data = help_blocks.BLOCK_HELP.get(block)
        if not data:
            return
        self._current_anchor = data.get("anchor")
        self._title_label.setText(api._description_with_symbols(data.get("title", block)))
        self._clear_body()

        for paragraph in data.get("body", []):
            self._add_line(paragraph)

        # The width is decided in ONE place, `_position` (it needs the
        # screen to apply the 92%/760 px cap). This path used to widen
        # the popup here first, outside any clamp.
        self._position(near)
        self._install_filter()
        self.show()

    def close_popup(self) -> None:
        try:
            self.hide()
            self.setFixedWidth(_WIDTH)  # reset for field (block may have widened it)
        except RuntimeError:
            pass  # widget destroyed by Qt — nothing to do
        if self._close_filter:
            app = QApplication.instance()
            if app:
                try:
                    app.removeEventFilter(self._close_filter)
                except RuntimeError:
                    pass
            self._close_filter = None

    # ------------------------------------------------------------------
    # Escape key
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_popup()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clear_body(self) -> None:
        """Empties the body NOW, not on the next event cycle."""
        self._eq_labels = []
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                try:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
                except RuntimeError:
                    pass  # widget already destroyed by Qt

    def _add_line(self, text: str, indent: int = 0) -> None:
        if "$$" in text:
            parts = text.split("$$")
            for i, parte in enumerate(parts):
                clean_part = parte.strip()
                if not clean_part:
                    continue
                if i % 2 == 1:
                    # LaTeX equation block between $$
                    self._add_equation(clean_part)
                else:
                    self._add_text_line(clean_part, indent=indent)
        else:
            self._add_text_line(text, indent=indent)

    def _add_text_line(self, text: str, indent: int = 0) -> None:
        from .. import api
        lbl = QLabel(in_paragraphs(api._description_with_symbols(text)))
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        if indent:
            lbl.setContentsMargins(indent, 0, 0, 0)
        self._body_layout.addWidget(lbl)

    def _add_pair(self, label: str, value: str) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.setAlignment(Qt.AlignmentFlag.AlignTop)
        lbl_r = QLabel(f"<b>{label}:</b>")
        lbl_r.setWordWrap(True)
        lbl_r.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        lbl_r.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        from .. import api
        lbl_v = QLabel(in_paragraphs(api._description_with_symbols(value)))
        lbl_v.setWordWrap(True)
        lbl_v.setTextFormat(Qt.TextFormat.RichText)
        lbl_v.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl_v.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        row.addWidget(lbl_r)
        row.addWidget(lbl_v)
        container = QWidget()
        container.setLayout(row)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._body_layout.addWidget(container)

    def _add_equation(self, eq: str) -> None:
        lbl = QLabel()
        pixmap = render_equation(eq)
        if pixmap is not None:
            lbl.setPixmap(pixmap)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            # A pixmap cannot wrap; the label is registered so
            # `_fit_equations` can shrink it inside the viewport.
            self._eq_labels.append(lbl)
        else:
            lbl.setText(f"<code>{eq}</code>")
            lbl.setTextFormat(Qt.TextFormat.RichText)
        # WordWrap on a pixmap-only QLabel changes nothing visually, but
        # it keeps ONE invariant for every body label: text never widens
        # its row -- it wraps (house rule: no clipped or overflowing text).
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent; padding: 1px 0px; margin: 1px 0px;")
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._body_layout.addWidget(lbl)

    def _fit_equations(self, avail_w: int) -> None:
        """Shrinks any rendered equation wider than `avail_w` to fit.

        A QLabel showing a pixmap cannot wrap: without this, an equation
        wider than the viewport loses its right side silently (three
        analytic families packed into one mathtext image measured 533 px
        against a 480 px viewport). The device pixel ratio is restored
        after scaling, so the image stays crisp on high-DPI screens.
        """
        kept: list[QLabel] = []
        for lbl in self._eq_labels:
            try:
                pm = lbl.pixmap()
                if pm is None or pm.isNull():
                    kept.append(lbl)
                    continue
                dpr = float(pm.devicePixelRatio()) or 1.0
                logical_w = pm.width() / dpr
                if logical_w > avail_w:
                    f = avail_w / logical_w
                    scaled = pm.scaled(
                        max(1, int(pm.width() * f)),
                        max(1, int(pm.height() * f)),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                    # QPixmap.scaled() drops the ratio; put it back.
                    scaled.setDevicePixelRatio(dpr)
                    lbl.setPixmap(scaled)
            except RuntimeError:
                continue  # label already destroyed with an old body
            kept.append(lbl)
        self._eq_labels = kept

    def _position(self, ref: QWidget) -> None:
        """Positions the popup to the right of the reference widget.
        Flips to the left if close to the edge."""
        window = ref.window().windowHandle()
        screen_obj = (window.screen() if window is not None else None) \
            or QApplication.primaryScreen()
        screen = screen_obj.availableGeometry()

        # ── Step 1: fix the width ────────────────────────────────────────
        # Must come before any sizeHint query, since the width affects
        # the height computed by the text layout.
        #
        # The width is `_WIDTH` capped by the smaller of 92% of THIS
        # monitor's available width and the hard readability cap: on any
        # monitor the popup stays inside the screen. (The old formula,
        # `min(_WIDTH, max(390, screen.width() - 2 * margin))`, had a
        # floor that could push the width PAST the cap on a small
        # screen; the cap now always wins.)
        #
        # `outer` uses `SetFixedSize` (comment in `__init__`): Qt does not
        # merely SUGGEST the popup's size from `layout.sizeHint()`, it
        # LOCKS minimumSize/maximumSize to that value every time the
        # layout is activated (`layout.activate()`, called in Step 2 and
        # Step 4) -- even over an explicit `setFixedWidth()` on the outer
        # widget. And `QScrollArea.sizeHint()` returns a small, fixed
        # value (about 256px) regardless of content -- so the popup's real
        # width was always that, and `self.setFixedWidth(width)` alone
        # never had any effect (which is why raising `_WIDTH` from 1285
        # to 2005 changed nothing on screen: the value never even got
        # used). The `_scroll` width needs to be fixed TOO, so that the
        # outer layout's `sizeHint()` -- what `SetFixedSize` actually
        # uses -- is already correct from the start.
        width_cap = min(int(screen.width() * _MAX_WIDTH_FRACTION),
                        _MAX_PIXEL_WIDTH)
        width = min(_WIDTH, width_cap)
        self.setFixedWidth(width)
        margins = self.layout().contentsMargins()
        self._scroll.setFixedWidth(width - margins.left() - margins.right())

        # Equations are images and cannot wrap; any one wider than the
        # viewport would be cut at the right edge (the horizontal
        # scrollbar is off by design). Shrink them NOW, so Steps 2-4
        # measure the fitted heights. The scrollbar strip is reserved
        # either way (measured below, at Step 3) and it is in the
        # viewport that content lays out.
        scrollbar_w = self._scroll.verticalScrollBar().sizeHint().width()
        self._fit_equations(
            max(120, self._scroll.width() - scrollbar_w))

        # ── Step 2: force layout propagation at the new width ───────────
        layout = self.layout()
        if layout is not None:
            layout.invalidate()
            layout.activate()

        # ── Step 3: compute the content's real height ────────────────────
        # QScrollArea.sizeHint() returns a fixed value of about 256×192 px, regardless
        # of content. The inner widget must be queried directly.
        #
        # `outer.activate()` (step 2) resizes the QScrollArea and, in
        # turn, the `_body_widget` (widgetResizable=True resizes the
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
        # body "measuring zero". Not hypothetical: `_position` runs
        # BEFORE `self.show()` in `show_block`/`show_field`, and on
        # popup REOPEN (singleton, already hidden by `close_popup()`) the
        # freshly-created rows inherited that state. The symptom would be
        # the popup opening at minimum height with all the text behind
        # the scrollbar.
        for i in range(self._body_layout.count()):
            item = self._body_layout.itemAt(i)
            w = item.widget() if item is not None else None
            if w is not None:
                w.show()
        self._body_layout.invalidate()
        self._body_layout.activate()
        max_scroll_h = max(120, screen.height() - 40)
        # HEIGHT FROM THE REAL WIDTH, not from sizeHint. A `QLabel` with
        # `wordWrap` returns in `sizeHint()` the height of an IDEAL line
        # wrap that Qt picks on its own (close to a square rectangle),
        # not the one for the width the label will actually be drawn at:
        # in the "Dynamic Stall (Øye)" block the first paragraph asks for
        # 154 px of sizeHint against 98 px real at 480 px of width. Added
        # across the twelve widgets, the body reserved about 790 px for 618 px
        # of text -- the two-to-three-line empty band left over below
        # EVERY popup. `QBoxLayout.heightForWidth` walks the same items
        # asking for the height AT the given width, which is the correct
        # number. The width comes from the value FIXED in step 1, not
        # from `_body_widget.width()`: the real geometry is only applied
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
        content_h = self._body_layout.heightForWidth(
            max(120, self._scroll.width() - scrollbar_w))
        if content_h <= 0:                       # no item with wordWrap
            content_h = self._body_widget.sizeHint().height()
        # scroll_h = what the content needs (+ breathing room), capped to screen.
        scroll_h = min(max(content_h + _BOTTOM_BREATHING_ROOM, 40), max_scroll_h)
        # `setFixedHeight`, not `setMinimumHeight` + loose maximum: for the
        # same reason as width in step 1, `QScrollArea.sizeHint()` is a
        # default value (about 288 px height) that ignores the content, and the
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
        # Last-resort guard: `SetFixedSize` re-derives min/max from the
        # layout's sizeHint on every activation, so the width decided in
        # Step 1 is only a request until it is re-checked HERE, after
        # the final activation. Nothing may reopen wider than the cap.
        if self.width() > width_cap:
            self.setFixedWidth(width_cap)

        # ── Step 5: position on screen ────────────────────────────
        pos_global = ref.mapToGlobal(QPoint(ref.width() + 4, 0))
        if pos_global.x() + self.width() + _SCREEN_MARGIN > screen.right():
            pos_global = ref.mapToGlobal(QPoint(-self.width() - 4, 0))
        # `max(lo, hi)` keeps the clamp sane when the popup is nearly as
        # wide as the screen: with plain `hi`, `max(lo, min(x, hi))`
        # pins the popup to `lo` and lets it run past the right edge.
        lo_x = screen.left() + _SCREEN_MARGIN
        hi_x = max(lo_x, screen.right() - self.width() - _SCREEN_MARGIN)
        pos_global.setX(max(lo_x, min(pos_global.x(), hi_x)))
        lo_y = screen.top() + _SCREEN_MARGIN
        hi_y = max(lo_y,
                   screen.bottom() - self.height() - _SCREEN_MARGIN)
        pos_global.setY(max(lo_y, min(pos_global.y(), hi_y)))
        self.move(pos_global)

    def _install_filter(self) -> None:
        if self._close_filter:
            QApplication.instance().removeEventFilter(self._close_filter)
        self._close_filter = _CloseFilter(self)
        QApplication.instance().installEventFilter(self._close_filter)

    def _open_docs(self) -> None:
        if self._current_anchor:
            open_help(self, anchor=self._current_anchor)
        self.close_popup()
