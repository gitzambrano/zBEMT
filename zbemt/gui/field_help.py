"""Per-field contextual help: clickable labels and texts open the popup.

There is no more "?" button anywhere in the GUI (neither per field nor
per block): the field's own label is clickable, and on *spanning* rows
(whole-row checkboxes, which have no label) it is the checkbox's TEXT
that opens the popup — the box itself keeps toggling normally.

Fields with no entry in ``help_content.FIELD_HELP`` get a plain QLabel
(no clickable behavior) — a failure in the right direction: better no
interaction than an empty popup.

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

Rule 3 used to be the FIRST one — and because of that every help link
fell into a table row cell instead of the physics. The field index
lists (``<!-- INDICE-DE-CAMPOS:... -->``) are removed before the
scan: they cite every field of the tab in ``<code>`` and would make any
chapter "cite" everything.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import NamedTuple

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QFormLayout,
    QSizePolicy,
    QToolButton,
    QWidget,
)

# Documentation-anchor resolution (Secao, secoes_da_documentacao,
# mapa_de_campos, ancora_do_campo, and the rest of the parsing) has no Qt
# dependency and lives in `field_help_data.py`, so `help_registry.py` and
# the documentation tests can use it without PyQt6 installed. Re-exported
# here under the same names for the Qt-dependent code below and for any
# existing `from .field_help import ...` caller.
from .field_help_data import (  # noqa: F401
    Secao,
    _AJUDA_ID,
    _ancestrais,
    _ancoras_de_fisica,
    _ancora_do_campo,
    _cita,
    _e_secao_de_fisica,
    _html_da_documentacao,
    _linhas_da_tabela_de_campos,
    _LINK_DE_DERIVACAO,
    _MARCA_BEMT,
    _MARCA_GUI,
    _melhor_secao,
    _NOME_NO_TOOLTIP,
    _QUALQUER_LINK,
    _salto_para_fisica,
    _TOKEN,
    _ID_ATTR,
    _INDICE_DE_CAMPOS,
    _CAPITULOS_DE_FISICA,
    ancora_do_campo,
    mapa_de_campos,
    secoes_da_documentacao,
)


def _campo_do_widget(widget: QWidget) -> str | None:
    """Raw field name (``"n_blades"``) extracted from the widget's tooltip."""
    achado = _NOME_NO_TOOLTIP.match(widget.toolTip() or "")
    return achado.group(1).split(".")[-1] if achado else None


def _abrir_popup(campo: str, perto_de: QWidget, raiz: QWidget) -> None:
    from .help_popup import HelpPopup
    from . import help_content
    from .common import open_help

    if campo in help_content.FIELD_HELP:
        HelpPopup.instancia(raiz).mostrar_campo(campo, perto_de)
    else:
        open_help(raiz, anchor=ancora_do_campo(campo))


def _label_clicavel(campo: str, texto_original: str, raiz: QWidget) -> QToolButton:
    """QToolButton that looks like a QLabel and opens the HelpPopup on click."""
    btn = QToolButton()
    btn.setText(texto_original)
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

    btn.clicked.connect(lambda: _abrir_popup(campo, btn, raiz))
    return btn


class _CliqueNoTextoDoCheck(QObject):
    """Clicking a checkbox's TEXT opens help; clicking the BOX toggles it.

    Replaces the old "?" button on *spanning* rows: the widget is not
    wrapped in any container, so the form's layout (and what
    ``tools/field_index.py`` reads from it) stays exactly as it was.
    """

    def __init__(self, botao: QAbstractButton, campo: str, raiz: QWidget):
        super().__init__(botao)
        self._botao = botao
        self._campo = campo
        self._raiz = raiz
        botao.installEventFilter(self)

    def _largura_da_caixa(self) -> int:
        """End of the checkbox's mark region, in widget pixels."""
        from PyQt6.QtWidgets import QStyle
        estilo = self._botao.style()
        largura = estilo.pixelMetric(
            QStyle.PixelMetric.PM_IndicatorWidth, None, self._botao)
        espaco = estilo.pixelMetric(
            QStyle.PixelMetric.PM_CheckBoxLabelSpacing, None, self._botao)
        margem = estilo.pixelMetric(
            QStyle.PixelMetric.PM_FocusFrameHMargin, None, self._botao)
        return largura + espaco + 2 * max(margem, 1)

    def clique_e_no_texto(self, x: int) -> bool:
        return x > self._largura_da_caixa()

    def _sublinhar(self, ligado: bool) -> None:
        """Toggles the checkbox text's underline on/off.

        A regular field's label gets underlined on hover (that's what
        announces "this is clickable"); the checkbox had the click and
        the hand cursor, but no VISUAL cue -- and a cursor only appears
        after the mouse is already there. QSS does not solve it:
        `text-decoration` does not apply to `QCheckBox` text, which the
        style draws itself. Changing the widget's font works and does
        not depend on the stylesheet.
        """
        fonte = self._botao.font()
        if fonte.underline() != ligado:
            fonte.setUnderline(ligado)
            self._botao.setFont(fonte)

    def eventFilter(self, obj: QObject, evento: QEvent) -> bool:
        tipo = evento.type()
        if tipo == QEvent.Type.MouseButtonPress:
            try:
                x = int(evento.position().x())
            except AttributeError:                     # pragma: no cover
                return False
            if self.clique_e_no_texto(x):
                _abrir_popup(self._campo, self._botao, self._raiz)
                return True        # consume: the box does NOT toggle
        elif tipo in (QEvent.Type.HoverMove, QEvent.Type.HoverEnter):
            # Underlines only when the cursor is over the TEXT -- over the
            # box the click toggles, and underlining there would promise
            # help that click doesn't open.
            try:
                x = int(evento.position().x())
            except AttributeError:                     # pragma: no cover
                return False
            self._sublinhar(self.clique_e_no_texto(x))
        elif tipo == QEvent.Type.HoverLeave:
            self._sublinhar(False)
        return False


def _instalar_no_checkbox(widget: QWidget, campo: str, raiz: QWidget) -> bool:
    """Makes a checkbox's text clickable. Returns True if it installed."""
    if not isinstance(widget, QCheckBox):
        return False
    filtro = _CliqueNoTextoDoCheck(widget, campo, raiz)
    widget._filtro_de_ajuda = filtro
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    # Without `setAttribute(WA_Hover)` Qt only sends HoverMove to widgets
    # that already use hover in the style -- and the text underline would
    # never appear.
    widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    tooltip = widget.toolTip() or ""
    marca = "Click the text for help; click the box to toggle."
    if marca not in tooltip:
        widget.setToolTip(f"{tooltip}\n\n{marca}" if tooltip else marca)
    return True


def instalar_popups_de_campo(raiz: QWidget) -> int:
    """Makes the label (or checkbox text) of every documented field
    under ``raiz`` clickable. Returns how many fields were equipped.
    Idempotent: an already-equipped field does not get double treatment.
    """
    from . import help_content

    criados = 0
    for form in raiz.findChildren(QFormLayout):
        for linha in range(form.rowCount()):
            eh_spanning = form.itemAt(linha, QFormLayout.ItemRole.LabelRole) is None
            field_role = (QFormLayout.ItemRole.SpanningRole if eh_spanning
                          else QFormLayout.ItemRole.FieldRole)
            item_field = form.itemAt(linha, field_role)
            if item_field is None:
                continue
            widget = item_field.widget()
            if widget is None or getattr(widget, "_tem_popup_de_campo", False):
                continue

            campo = _campo_do_widget(widget)
            if campo is None:
                continue

            ancora = ancora_do_campo(campo)
            if ancora is None and campo not in help_content.FIELD_HELP:
                continue  # undocumented field — no interaction

            if eh_spanning:
                # No label: the checkbox's own text opens the help.
                if not _instalar_no_checkbox(widget, campo, raiz):
                    continue
            else:
                item_label = form.itemAt(linha, QFormLayout.ItemRole.LabelRole)
                label_widget = item_label.widget() if item_label else None
                if label_widget is None:
                    continue
                texto = label_widget.text() if hasattr(label_widget, "text") else campo
                # The row may already be HIDDEN by the tab's progressive
                # disclosure (`common.definir_linha_visivel`, called in
                # the constructor -- therefore before this point).
                # `QFormLayout` does not reapply the row's visibility to a
                # widget inserted later: the new label would be born
                # visible over a hidden field, which is exactly the
                # orphan label that `definir_linha_visivel` exists to avoid.
                #
                # Seen on screen in five rows at once ("Viterna
                # transition width", "Lag constant A", "Fade-out start/end",
                # "Maximum skew angle") -- all from blocks that start
                # switched off. Inheriting the replaced label's visibility
                # is what keeps the row coherent.
                estava_visivel = not label_widget.isHidden()
                label_widget.hide()
                label_widget.setParent(None)  # remove from the scene
                novo_label = _label_clicavel(campo, texto, raiz)
                novo_label.setVisible(estava_visivel)
                form.setWidget(linha, QFormLayout.ItemRole.LabelRole, novo_label)

            widget._tem_popup_de_campo = True
            criados += 1

    # Checkboxes outside a QFormLayout (loose boxes in QVBoxLayout etc.)
    for cb in raiz.findChildren(QCheckBox):
        if getattr(cb, "_tem_popup_de_campo", False):
            continue
        campo = _campo_do_widget(cb)
        if campo is None:
            continue
        if ancora_do_campo(campo) is None and campo not in help_content.FIELD_HELP:
            continue
        if _instalar_no_checkbox(cb, campo, raiz):
            cb._tem_popup_de_campo = True
            criados += 1

    return criados


# Compatibilidade: alguns módulos ainda chamam `anexar_ajuda_de_campo`.
anexar_ajuda_de_campo = instalar_popups_de_campo
