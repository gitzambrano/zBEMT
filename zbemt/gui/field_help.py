"""Per-field contextual help: clickable labels and texts open the popup.

There is no more "?" button anywhere in the GUI (neither per field nor
per block): the field's own label is clickable, and on *spanning* rows
(whole-row checkboxes, which have no label) it is the checkbox's TEXT
that opens the popup. The box itself keeps toggling normally.

Fields with no entry in ``help_content.FIELD_HELP`` get a plain QLabel
(no clickable behavior). That is a failure in the right direction:
better no interaction than an empty popup.

Anchor resolution (the destination of "Open full documentation →")
--------------------------------------------------------------
Each field's destination is DERIVED from ``docs/documentation.html``,
never kept by hand. The rule, in order of preference:

1. the deepest section of a PHYSICS chapter (2 Physics
   fundamentals, 7 Inflow models, 8 Physical corrections, 9 Numerical
   solver, 3 Hover, 4 Forward flight) that cites ``<code>field</code>``;
2. the deepest section of any other chapter that cites it (the
   per-tab sections, which at least describe the widget);
3. only then the ``id="ajuda-{field}"`` row of the field table.

Rule 3 used to be the FIRST one. Because of that every help link
fell into a table row cell instead of the physics. The field index
lists (``<!-- INDICE-DE-CAMPOS:... -->``) are removed before the
scan: they cite every field of the tab in ``<code>`` and would make any
chapter "cite" everything.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import NamedTuple

from PyQt6.QtCore import QEvent, QObject, QSize, Qt
from PyQt6.QtGui import QPainter, QTextDocument
from PyQt6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QFormLayout,
    QSizePolicy,
    QToolButton,
    QWidget,
)

# Documentation-anchor resolution (Section, documentation_sections,
# field_map, field_anchor, and the rest of the parsing) has no Qt
# dependency and lives in `field_help_data.py`, so `help_registry.py` and
# the documentation tests can use it without PyQt6 installed. Re-exported
# here under the same names for the Qt-dependent code below and for any
# existing `from .field_help import ...` caller.
from .field_help_data import (  # noqa: F401
    Section,
    _HELP_ID,
    _ancestors,
    _physics_anchors,
    _cites_field,
    _is_physics_section,
    _documentation_html,
    _field_table_rows,
    _DERIVATION_LINK,
    _BEMT_MARK,
    _GUI_MARK,
    _best_section,
    _NAME_IN_TOOLTIP,
    _ANY_LINK,
    _physics_jump,
    _TOKEN,
    _ID_ATTR,
    _FIELD_INDEX_BLOCK,
    _PHYSICS_CHAPTERS,
    field_anchor,
    field_map,
    documentation_sections,
)


def _widget_field(widget: QWidget) -> str | None:
    """Raw field name (``"n_blades"``) extracted from the widget's tooltip."""
    match = _NAME_IN_TOOLTIP.match(widget.toolTip() or "")
    return match.group(1).split(".")[-1] if match else None


def _open_popup(field: str, near: QWidget, root: QWidget) -> None:
    from .help_popup import HelpPopup
    from . import help_content
    from .common import open_help

    if field in help_content.FIELD_HELP:
        HelpPopup.instance(root).show_field(field, near)
    else:
        open_help(root, anchor=field_anchor(field))


class _RichToolButton(QToolButton):
    """A `QToolButton` whose text is HTML.

    `QToolButton.setText` does NOT render markup: a label carrying a
    rendered symbol reached the screen as the literal string
    ``&psi;<sub>w</sub>``. Since every documented field has its `QLabel`
    swapped for one of these buttons, that turned `PR-4` on its head
    exactly on the fields that DO carry mathematics.

    The text is kept on the button itself (so `text()`, size policy and
    every existing caller still work) and drawn through a
    `QTextDocument`, which is the same way the results table paints its
    subscripts.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._doc = QTextDocument(self)
        self._doc.setDocumentMargin(0)
        self._doc.setDefaultFont(self.font())

    def setText(self, text: str) -> None:                    # noqa: N802
        super().setText(text)
        self._doc.setDefaultFont(self.font())
        self._doc.setHtml(text)
        self.updateGeometry()

    def sizeHint(self) -> QSize:                             # noqa: N802
        size = self._doc.size()
        return QSize(int(size.width()) + 2,
                     max(int(size.height()), self.minimumHeight()))

    def minimumSizeHint(self) -> QSize:                      # noqa: N802
        return self.sizeHint()

    def paintEvent(self, event) -> None:                     # noqa: N802
        painter = QPainter(self)
        self._doc.setDefaultFont(self.font())
        # The stylesheet colours the button (and recolours it on hover);
        # the document inherits that colour instead of a hard-coded one.
        painter.setPen(self.palette().color(self.foregroundRole()))
        ctx = self._doc.documentLayout().PaintContext()
        ctx.palette = self.palette()
        y = max(0, (self.height() - int(self._doc.size().height())) // 2)
        painter.translate(0, y)
        self._doc.documentLayout().draw(painter, ctx)
        painter.end()


def _clickable_label(field: str, original_text: str, root: QWidget) -> QToolButton:
    """QToolButton that looks like a QLabel and opens the HelpPopup on click."""
    btn = _RichToolButton()
    btn.setText(original_text)
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    btn.setAutoRaise(True)
    btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    btn.setMinimumHeight(30)
    btn.setStyleSheet(
        "QToolButton { border: none; padding: 0; margin: 0;"
        " text-align: left; color: palette(windowText); }"
        "QToolButton:hover { color: #3a6dbd; text-decoration: underline; }"
    )
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Click the label for help on this field")

    btn.clicked.connect(lambda: _open_popup(field, btn, root))
    return btn


class _CheckboxTextClick(QObject):
    """Clicking a checkbox's TEXT opens help; clicking the BOX toggles it.

    Replaces the old "?" button on *spanning* rows: the widget is not
    wrapped in any container, so the form's layout (and what
    ``tools/field_index.py`` reads from it) stays exactly as it was.
    """

    def __init__(self, button: QAbstractButton, field: str, root: QWidget):
        super().__init__(button)
        self._button = button
        self._field = field
        self._root = root
        button.installEventFilter(self)

    def _box_width(self) -> int:
        """End of the checkbox's mark region, in widget pixels."""
        from PyQt6.QtWidgets import QStyle
        style = self._button.style()
        width = style.pixelMetric(
            QStyle.PixelMetric.PM_IndicatorWidth, None, self._button)
        spacing = style.pixelMetric(
            QStyle.PixelMetric.PM_CheckBoxLabelSpacing, None, self._button)
        margin = style.pixelMetric(
            QStyle.PixelMetric.PM_FocusFrameHMargin, None, self._button)
        return width + spacing + 2 * max(margin, 1)

    def click_is_on_text(self, x: int) -> bool:
        return x > self._box_width()

    def _set_underline(self, enabled: bool) -> None:
        """Toggles the checkbox text's underline on/off.

        A regular field's label gets underlined on hover (that is what
        announces "this is clickable"); the checkbox had the click and
        the hand cursor, but no VISUAL cue -- and a cursor only appears
        after the mouse is already there. QSS does not solve it:
        `text-decoration` does not apply to `QCheckBox` text, which the
        style draws itself. Changing the widget's font works and does
        not depend on the stylesheet.
        """
        font = self._button.font()
        if font.underline() != enabled:
            font.setUnderline(enabled)
            self._button.setFont(font)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            try:
                x = int(event.position().x())
            except AttributeError:                     # pragma: no cover
                return False
            if self.click_is_on_text(x):
                _open_popup(self._field, self._button, self._root)
                return True        # consume: the box does NOT toggle
        elif kind in (QEvent.Type.HoverMove, QEvent.Type.HoverEnter):
            # Underlines only when the cursor is over the TEXT -- over the
            # box the click toggles, and underlining there would promise
            # help that click doesn't open.
            try:
                x = int(event.position().x())
            except AttributeError:                     # pragma: no cover
                return False
            self._set_underline(self.click_is_on_text(x))
        elif kind == QEvent.Type.HoverLeave:
            self._set_underline(False)
        return False


def _install_on_checkbox(widget: QWidget, field: str, root: QWidget) -> bool:
    """Makes a checkbox's text clickable. Returns True if it installed."""
    if not isinstance(widget, QCheckBox):
        return False
    filter_obj = _CheckboxTextClick(widget, field, root)
    widget._help_filter = filter_obj
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    # Without `setAttribute(WA_Hover)` Qt only sends HoverMove to widgets
    # that already use hover in the style -- and the text underline would
    # never appear.
    widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    tooltip = widget.toolTip() or ""
    marker = "Click the text for help. Click the box to toggle."
    if marker not in tooltip:
        widget.setToolTip(f"{tooltip}\n\n{marker}" if tooltip else marker)
    return True


#: Anything `nomenclature.to_html` can emit into a label: an entity such as
#: ``&gamma;`` or ``&mdash;``, or a tag such as ``<sub>``.
_MARKUP = re.compile(r"&[a-zA-Z]+;|&#\d+;|<[a-zA-Z/][^>]*>")


def render_markup_in_labels(root: QWidget) -> int:
    """Forces every form label under ``root`` that carries markup to be
    drawn as rich text. Returns how many labels were corrected.

    A `QLabel` left on `AutoText` decides by looking for a TAG, so a label
    whose only markup is an ENTITY (``&gamma; -- Lock number:``) was
    classified as plain text and showed the entity verbatim. Worse, a
    label with a buddy treats ``&`` as a mnemonic, which ate the
    ampersand and underlined the next letter: ``&gamma;`` reached the
    screen as ``gamma;``. Both break `PR-4` on exactly the fields that
    carry mathematics.
    """
    from PyQt6.QtWidgets import QLabel

    fixed = 0
    for form in root.findChildren(QFormLayout):
        for row_idx in range(form.rowCount()):
            item = form.itemAt(row_idx, QFormLayout.ItemRole.LabelRole)
            label = item.widget() if item is not None else None
            if not isinstance(label, QLabel):
                continue
            if not _MARKUP.search(label.text()):
                continue
            if label.textFormat() == Qt.TextFormat.RichText:
                continue
            label.setTextFormat(Qt.TextFormat.RichText)
            fixed += 1
    return fixed


def install_field_popups(root: QWidget) -> int:
    """Makes the label (or checkbox text) of every documented field
    under ``root`` clickable. Returns how many fields were equipped.
    Idempotent: an already-equipped field does not get double treatment.

    Also normalizes every remaining form label that carries markup, so an
    UNdocumented field (which keeps its `QLabel`) renders its symbol too.
    """
    from . import help_content

    count = 0
    for form in root.findChildren(QFormLayout):
        for row_idx in range(form.rowCount()):
            is_spanning = form.itemAt(row_idx, QFormLayout.ItemRole.LabelRole) is None
            field_role = (QFormLayout.ItemRole.SpanningRole if is_spanning
                          else QFormLayout.ItemRole.FieldRole)
            item_field = form.itemAt(row_idx, field_role)
            if item_field is None:
                continue
            widget = item_field.widget()
            if widget is None or getattr(widget, "_has_field_popup", False):
                continue

            field = _widget_field(widget)
            if field is None:
                continue

            anchor = field_anchor(field)
            if anchor is None and field not in help_content.FIELD_HELP:
                continue  # undocumented field — no interaction

            if is_spanning:
                # No label: the checkbox's own text opens the help.
                if not _install_on_checkbox(widget, field, root):
                    continue
            else:
                item_label = form.itemAt(row_idx, QFormLayout.ItemRole.LabelRole)
                label_widget = item_label.widget() if item_label else None
                if label_widget is None:
                    continue
                text = label_widget.text() if hasattr(label_widget, "text") else field
                # The row may already be HIDDEN by the tab's progressive
                # disclosure (`common.set_row_visible`, called in
                # the constructor -- therefore before this point).
                # `QFormLayout` does not reapply the row's visibility to a
                # widget inserted later: the new label would be born
                # visible over a hidden field, which is exactly the
                # orphan label that `set_row_visible` exists to avoid.
                #
                # Seen on screen in five rows at once ("Viterna
                # transition width", "Lag constant A", "Fade-out start/end",
                # "Maximum skew angle") -- all from blocks that start
                # switched off. Inheriting the replaced label's visibility
                # is what keeps the row coherent.
                was_visible = not label_widget.isHidden()
                label_widget.hide()
                label_widget.setParent(None)  # remove from the scene
                new_label = _clickable_label(field, text, root)
                new_label.setVisible(was_visible)
                form.setWidget(row_idx, QFormLayout.ItemRole.LabelRole, new_label)

            widget._has_field_popup = True
            count += 1

    # Checkboxes outside a QFormLayout (loose boxes in a QVBoxLayout, and so on)
    for cb in root.findChildren(QCheckBox):
        if getattr(cb, "_has_field_popup", False):
            continue
        field = _widget_field(cb)
        if field is None:
            continue
        if field_anchor(field) is None and field not in help_content.FIELD_HELP:
            continue
        if _install_on_checkbox(cb, field, root):
            cb._has_field_popup = True
            count += 1

    # Runs LAST: the loop above replaces documented labels with a
    # `_RichToolButton` (which paints its own markup), so what is left as a
    # QLabel is the undocumented rows, and those are the ones to normalize.
    render_markup_in_labels(root)

    return count
