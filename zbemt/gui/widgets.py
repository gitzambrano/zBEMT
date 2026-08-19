"""Composite widgets reused by more than one tab.

``LongitudinalInput`` (the IN-PLANE component of the flight condition,
the engine's ``mu_x``) and ``AxialInput`` (the AXIAL component, ``Vz``):
each one has several units that are the same quantity written a
different way, so a label-dropdown switches the unit and converts the
value, instead of two fields that could diverge.

The LIST of units changes with the mode -- rotor or propeller --,
because the axes rotate: see ``UNIDADES_DE_CONDICAO`` below and
Sec.6c of ``bemt.py``.
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QDoubleSpinBox, QStyledItemDelegate,
    QStyle, QStyleOptionViewItem, QStylePainter, QStyleOptionComboBox,
    QApplication,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QDoubleValidator, QTextDocument

from .. import api


_PAPEL_SIMBOLO_DA_UNIDADE = Qt.ItemDataRole.UserRole + 1


class _DelegadoDeUnidades(QStyledItemDelegate):
    """Draws combo symbols with real subscripts and a per-item tooltip."""

    def paint(self, painter, option, index):
        simbolo = index.data(_PAPEL_SIMBOLO_DA_UNIDADE)
        if not simbolo:
            super().paint(painter, option, index)
            return
        opcao = QStyleOptionViewItem(option)
        self.initStyleOption(opcao, index)
        opcao.text = ""
        estilo = opcao.widget.style() if opcao.widget else QApplication.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opcao,
                           painter, opcao.widget)
        area = estilo.subElementRect(QStyle.SubElement.SE_ItemViewItemText,
                                     opcao, opcao.widget)
        documento = QTextDocument()
        documento.setDefaultFont(opcao.font)
        documento.setDocumentMargin(0)
        cor = opcao.palette.color(
            opcao.palette.ColorRole.HighlightedText
            if opcao.state & QStyle.StateFlag.State_Selected
            else opcao.palette.ColorRole.Text)
        documento.setHtml(f'<span style="color:{cor.name()}">{simbolo}</span>')
        painter.save()
        painter.translate(area.left(), area.top() + max(
            0.0, (area.height() - documento.size().height()) / 2))
        documento.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        simbolo = index.data(_PAPEL_SIMBOLO_DA_UNIDADE)
        if not simbolo:
            return super().sizeHint(option, index)
        opcao = QStyleOptionViewItem(option)
        self.initStyleOption(opcao, index)
        documento = QTextDocument()
        documento.setDefaultFont(opcao.font)
        documento.setDocumentMargin(0)
        documento.setHtml(simbolo)
        base = super().sizeHint(option, index)
        tamanho = documento.size()
        return base.expandedTo(tamanho.toSize())


class _ComboDeUnidades(QComboBox):
    """Also paints the combo's current item with real subscripts."""

    def paintEvent(self, event):  # noqa: N802 (API Qt)
        simbolo = self.currentData(_PAPEL_SIMBOLO_DA_UNIDADE)
        if not simbolo:
            super().paintEvent(event)
            return
        opcao = QStyleOptionComboBox()
        self.initStyleOption(opcao)
        opcao.currentText = ""
        pintor = QStylePainter(self)
        pintor.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opcao)
        area = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, opcao,
            QStyle.SubControl.SC_ComboBoxEditField, self)
        documento = QTextDocument()
        documento.setDefaultFont(self.font())
        documento.setDocumentMargin(0)
        documento.setHtml(simbolo)
        pintor.save()
        pintor.translate(area.left() + 4, area.top() + max(
            0.0, (area.height() - documento.size().height()) / 2))
        documento.drawContents(pintor)
        pintor.restore()


_SIMBOLOS_DAS_UNIDADES = {
    "μₓ": "&mu;<sub>x</sub>", "Jₓ": "J<sub>x</sub>",
    "Vₓ [m/s]": "V<sub>x</sub> [m/s]", "V_z [m/s]": "V<sub>z</sub> [m/s]",
    "μ_z": "&mu;<sub>z</sub>", "J_z": "J<sub>z</sub>",
    "αᵣₒₜₒᵣ [deg]": "&alpha;<sub>rotor</sub> [deg]",
    "α_dᵢₛₖ [deg]": "&alpha;<sub>disk</sub> [deg]",
}

_DICAS_DAS_UNIDADES = {
    "mu_x": "<b>μ<sub>x</sub></b><br><br>Advance ratio based on the vehicle x component.<br><br>μ<sub>x</sub> = V<sub>x</sub>/(ΩR).",
    "J_x": "<b>J<sub>x</sub></b><br><br>Propeller advance ratio based on the vehicle x component.<br><br>J<sub>x</sub> = V<sub>x</sub>/(nD).",
    "Vx": "<b>V<sub>x</sub></b><br><br>Free-stream velocity component along the vehicle x-axis.<br><br>It is the forward component for a rotor and the along-shaft airspeed for a propeller.",
    "Vz": "<b>V<sub>z</sub></b><br><br>Free-stream velocity component along the vehicle z-axis.<br><br>It is climb/descent for a rotor and cross-flow for a propeller.",
    "mu_z": "<b>μ<sub>z</sub></b><br><br>Velocity ratio based on the vehicle z component.<br><br>μ<sub>z</sub> = V<sub>z</sub>/(ΩR).",
    "J_z": "<b>J<sub>z</sub></b><br><br>Velocity ratio based on the vehicle z component.<br><br>J<sub>z</sub> = V<sub>z</sub>/(nD).",
    "alpha_deg": "<b>α<sub>rotor</sub></b><br><br>Rotor inflow angle measured from the disk plane.<br><br>It is positive when the flow has a positive V<sub>z</sub> component.",
    "alpha_disk": "<b>α<sub>disk</sub></b><br><br>Propeller inflow angle measured from the shaft.<br><br>It is zero when V<sub>z</sub> is zero and the free stream is aligned with the shaft.",
}


def configurar_combo_de_unidades(combo: QComboBox, pares: list[tuple[str, str]]) -> None:
    """Populates a combo with a rich-text symbol and a per-option
    tooltip."""
    combo.setItemDelegate(_DelegadoDeUnidades(combo))
    combo.clear()
    for rotulo, variavel in pares:
        combo.addItem(rotulo)
        indice = combo.count() - 1
        simbolo = _SIMBOLOS_DAS_UNIDADES.get(rotulo, rotulo)
        combo.setItemData(indice, simbolo, _PAPEL_SIMBOLO_DA_UNIDADE)
        # `_DICAS_DAS_UNIDADES` already carries the symbol in bold as
        # the tooltip's own first line -- prefixing it again here
        # would duplicate the title ("α_rotor [deg]" followed by
        # "α_rotor" in the same tooltip). It only falls back to the
        # prefix when there is no rich entry (a variable with no
        # tooltip of its own), as a minimal title.
        dica = _DICAS_DAS_UNIDADES.get(variavel)
        if dica is None:
            dica = f"<b>{simbolo}</b>"
        combo.setItemData(indice, dica, Qt.ItemDataRole.ToolTipRole)


class SpinBoxCientifico(QDoubleSpinBox):
    """Spinbox for quantities that live in orders of magnitude, not in
    decimal places -- tolerances, residuals, thresholds.

    A regular ``QDoubleSpinBox`` shows the default tolerance 1e-6 as
    ``0.0000010000`` (ten fixed decimal places): the user has to count
    zeros to know the order of magnitude, and 1e-9 and 1e-10 become
    almost indistinguishable. Here the text is ``1e-06``, and the step
    is MULTIPLICATIVE (one decade per click), which is how a tolerance
    is actually adjusted -- the additive step of a regular spinbox,
    with a fixed increment, either does not move or jumps across the
    whole range.
    """

    #: Step per click: one decade. Half a decade (~3.16x) would be
    #: finer, but produces values like 3.16e-07, which nobody types.
    _FATOR = 10.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDecimals(12)          # only the internal precision LIMIT;
                                       # the displayed text comes from textFromValue
        self.setKeyboardTracking(False)

    def textFromValue(self, valor: float) -> str:
        return f"{valor:.6g}" if valor == 0 else f"{valor:.0e}".replace("e-0", "e-")

    def valueFromText(self, texto: str) -> float:
        try:
            return float(texto.strip())
        except ValueError:
            return self.value()

    def validate(self, texto: str, pos: int):
        # `QDoubleSpinBox.validate` only accepts the locale's decimal
        # notation; without this, typing "1e-8" would be rejected key
        # by key.
        validador = QDoubleValidator(self.minimum(), self.maximum(), 12, self)
        validador.setNotation(QDoubleValidator.Notation.ScientificNotation)
        return validador.validate(texto, pos)

    def stepBy(self, passos: int):
        valor = self.value()
        if valor <= 0:
            super().stepBy(passos)
            return
        self.setValue(valor * (self._FATOR ** passos))



# =============================================================================
# Reusable composite widgets -- Phase 8 (docs/CHANGELOG.md): mu_x/J_x and
# alpha/Vz are pairs of INTERCHANGEABLE representations of the same
# physical quantity (longitudinal advance ratio and axial component of
# the flight condition, Sec.6c of bemt.py) -- choosing one locks the
# other (dropdown, not two independent numeric fields). Used by
# RunCaseTab and RunBatchTab (fixed fields + each factorial-analysis
# axis + the explicit list), a single implementation for all three,
# unlike the earlier attempt (a pair of QRadioButton only in
# RunCaseTab, which never converted the value when the disk angle unit
# was switched -- see changelog).
# =============================================================================

# =============================================================================
# The units offered in each slot, PER MODE
# =============================================================================
# Each entry is (label on screen, canonical engine/`studies` variable). The
# label rotates with the mode; the variable NEVER rotates -- it is always
# the engine's, in disk axes.
#
# ROTOR: advance is IN-PLANE (mu_x/J_x/V) and the axial component is
# climb/descent (`alpha_rotor`, measured from the disk PLANE -- ~0 on a
# helicopter in forward flight --, or Vz in m/s).
#
# PROPELLER: the axes rotate (see `bemt.py`, Sec.6c). The x axis becomes
# the shaft's, and with it the PRIMARY advance moves to the axial slot --
# J_x is the classic propeller J_x, V/(nD) with V along the shaft. The
# in-plane slot is left with the CROSS flow, written as a velocity
# (Vz_inf) or as the angle between the flow and the SHAFT (`alpha_disk`,
# 0° in straight cruise).
#
# THERE ARE TWO ANGLES, ONE PER MODE, and each mode offers only ITS OWN.
# `alpha_rotor` is measured from the plane and `alpha_disk` from the
# shaft; one is the complement of the other. Each is zero at its
# vehicle's NORMAL condition -- level forward flight for a helicopter,
# straight cruise for an airplane --, which is what makes the number
# readable. Offering both in either mode was the confusion to avoid.
#
# Why alpha_disk lives in the in-plane slot and not the axial one: an
# angle does not fix the velocity's scale, it only splits a known
# component into the other one. In straight cruise the known component
# is the AXIAL one, so that is the one that has to be given as a number
# (J_x/mu_x/V) and the in-plane one is the one derived from the angle --
# the opposite of the rotor, where the in-plane one is the known one. Put
# in the axial slot, alpha_disk would solve
# `Vz = V_in-plane/tan(alpha_disk)`, which is 0/0 exactly in the cruise
# flight a propeller spends 99% of its time doing.
# THE FIELD NAMES ARE THE SAME IN BOTH MODES -- x and z --, and what
# changes is which physical component each letter refers to. x is always
# the PRIMARY one (the helicopter's advance, the propeller's flight
# speed) and z the secondary one; the angle is always an alternative to
# giving `V_z`.
#
# The key `("longitudinal"/"axial", mode)` is the ENGINE's slot:
# `longitudinal` is the internal `mu_x` (in the disk plane) and `axial`
# is the internal `Vz` (along the shaft). Which one carries the letter x
# depends on the mode -- that is exactly the rotation this table encodes.
UNIDADES_DE_CONDICAO = {
    # ROTOR: vertical axis -> in-plane = x (advance), axial = z (climb)
    ("longitudinal", False): (("μₓ", "mu_x"), ("Jₓ", "J_x"), ("Vₓ [m/s]", "Vx")),
    ("axial", False): (("αᵣₒₜₒᵣ [deg]", "alpha_deg"), ("V_z [m/s]", "Vz"),
                        ("μ_z", "mu_z"), ("J_z", "J_z")),
    # PROPELLER: horizontal axis -> axial = x (flight speed), in-plane = z
    ("axial", True): (("Jₓ", "J_z"), ("μₓ", "mu_z"), ("Vₓ [m/s]", "Vz")),
    ("longitudinal", True): (("V_z [m/s]", "Vx"), ("α_dᵢₛₖ [deg]", "alpha_disk"),
                              ("μ_z", "mu_x"), ("J_z", "J_x")),
}

#: Pre-selected unit of each slot per mode -- the one the user almost
#: always wants. On a rotor: advance in mu_x and climb as an angle. On a
#: propeller: flight speed in J_x and the cross component at zero.
_UNIDADE_PADRAO = {
    ("longitudinal", False): "μₓ", ("longitudinal", True): "V_z [m/s]",
    ("axial", False): "αᵣₒₜₒᵣ [deg]", ("axial", True): "Jₓ",
}

#: Variables whose spinbox is an ANGLE (±90 range) rather than a velocity
#: or a ratio -- used by both widgets to adjust the range when the unit
#: is switched.
_VARIAVEIS_DE_ANGULO = ("alpha_deg", "alpha_disk")


def _rotulos_de_unidade(slot: str, is_propeller: bool) -> list:
    return [rotulo for rotulo, _var in UNIDADES_DE_CONDICAO[(slot, bool(is_propeller))]]


def variavel_de_rotulo_de_unidade(slot: str, rotulo: str) -> str:
    """Canonical variable for a label, searching in BOTH modes.

    In both because switching modes rebuilds the combo, and between
    the `clear()` and the `addItems()` the current text is from one
    mode and the list is already from the other; without the broad
    search, that instant would return the wrong variable for whoever
    was reading the field."""
    for (s, _modo), pares in UNIDADES_DE_CONDICAO.items():
        if s != slot:
            continue
        for r, var in pares:
            if r == rotulo:
                return var
    return ""


class LongitudinalInput(QWidget):
    """The IN-PLANE component of the flight condition (the engine's
    `mu_x`), in the unit the current mode makes natural.

    In ROTOR mode it is the advance: mu_x, J_x or V [m/s]. In
    PROPELLER mode it is the CROSS flow: Vz_inf [m/s], the angle
    alpha_disk measured from the shaft, or the ratios mu_z/J_z (see
    `UNIDADES_DE_CONDICAO`).

    The dropdown is positioned on the left and serves as the field's
    own label: clicking it switches the unit, converting the
    displayed value. For the mu_x<->V conversion (which depends on
    rpm and radius), a ``context_provider`` must be registered via
    ``set_context_provider`` (same as AxialInput); without a
    provider, mu_x<->V does not convert the value (it only switches
    the label), which is acceptable in the factorial context where
    the values are entered manually."""
    changed = pyqtSignal()

    _SLOT = "longitudinal"

    def __init__(self, default_mu: float = 0.2):
        super().__init__()
        self._is_propeller = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.unit_combo = _ComboDeUnidades()
        configurar_combo_de_unidades(
            self.unit_combo, UNIDADES_DE_CONDICAO[(self._SLOT, False)])
        self.spin = QDoubleSpinBox()
        self.spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.spin.setRange(-10000.0, 10000.0)
        self.spin.setDecimals(4)
        self.spin.setSingleStep(0.01)
        self.spin.setValue(default_mu)
        layout.addWidget(self.unit_combo)   # combo = label, on the left
        layout.addWidget(self.spin)
        # The slack goes to the END, not to the field. With
        # `addWidget(spin, 1)` the spinbox got all the row's leftover
        # space; after `common.compactar_campos_de_formulario` started
        # limiting the numeric field's width, that space became a gap
        # of several hundred pixels BETWEEN the label-dropdown and the
        # value -- the two pieces of the same field ended up at
        # opposite ends of the window.
        layout.addStretch(1)
        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        self.spin.valueChanged.connect(self.changed.emit)
        self._context_provider = None  # callable() -> (rpm, radius_m) | None
        self._prev_unit = self.unit_combo.currentText()

    def set_context_provider(self, fn):
        """Registers a callable that returns (rpm, radius_m) --
        needed to convert between mu_x/J_x and V when the unit is
        switched."""
        self._context_provider = fn

    def _on_unit_changed(self, _index: int):
        old_text = self._prev_unit if hasattr(self, '_prev_unit') else None
        new_text = self.unit_combo.currentText()
        self.spin.blockSignals(True)
        self._ajustar_faixa()
        # convert the value when the unit changes: normalizes the old
        # value to mu_x and rewrites it in the new unit. `_mu_de`
        # returns None when context is missing (or when the angle
        # needs a Vz this widget does not know) -- in that case the
        # number stays as it is, which is the old behavior for
        # mu_x<->V without context.
        if old_text is not None:
            mu_val = self._mu_de(old_text, self.spin.value())
            if mu_val is not None:
                novo = self._valor_em(new_text, mu_val)
                if novo is not None:
                    self.spin.setValue(novo)
        self._prev_unit = new_text
        self.spin.blockSignals(False)
        self.changed.emit()

    # --- conversions (current unit <-> mu_x) --------------------------------

    def _ctx(self):
        return self._context_provider() if self._context_provider is not None else None

    def _ajustar_faixa(self):
        """An angle lives in ±90; an advance ratio or a velocity does
        not. Without this, choosing `alpha_disk [deg]` would keep the
        wide range (the spinbox would accept 300°) and switching back
        to V [m/s] would leave the range stuck at ±90 (a propeller at
        120 m/s would not fit)."""
        if self.variable_name() in _VARIAVEIS_DE_ANGULO:
            self.spin.setRange(-90.0, 90.0)
        else:
            self.spin.setRange(-10000.0, 10000.0)

    def _mu_de(self, rotulo: str, valor: float):
        var = variavel_de_rotulo_de_unidade(self._SLOT, rotulo)
        if var == "mu_x":
            return valor
        if var == "J_x":
            return api.J_to_mu(valor)
        if var == "V":
            ctx = self._ctx()
            if ctx is None:
                return None
            rpm, radius_m = ctx
            return api.V_to_mu(valor, rpm, radius_m)
        return None       # alpha_disk: depends on Vz, known only by the tab

    def _valor_em(self, rotulo: str, mu_x: float):
        var = variavel_de_rotulo_de_unidade(self._SLOT, rotulo)
        if var == "mu_x":
            return mu_x
        if var == "J_x":
            return api.mu_to_J(mu_x)
        if var == "V":
            ctx = self._ctx()
            if ctx is None:
                return None
            rpm, radius_m = ctx
            return api.mu_to_V(mu_x, rpm, radius_m)
        return None       # alpha_disk: same

    # --- read / write -------------------------------------------------------

    def is_mu(self) -> bool:
        return self.variable_name() == "mu_x"

    def is_alpha_disk(self) -> bool:
        """This unit DERIVES the in-plane component from the axial
        one, instead of reporting it -- whoever builds the condition
        has to resolve the axial one first (see
        `common.resolver_par_de_condicao`)."""
        return self.variable_name() == "alpha_disk"

    def variable_name(self) -> str:
        """Canonical engine variable (`mu_x`/`J_x`/`V`/`alpha_disk`)
        -- NEVER the screen label, which rotates with the mode."""
        return variavel_de_rotulo_de_unidade(self._SLOT, self.unit_combo.currentText()) or "mu_x"

    def raw_value(self) -> float:
        """Displayed value, in the current unit -- used as an
        AXIS/fixed factorial value (`studies.build_factorial_conditions`
        accepts every variable in `UNIDADES_DE_CONDICAO`)."""
        return self.spin.value()

    def mu_x(self, Vz: float = 0.0) -> float:
        """``mu_x`` corresponding to the displayed value.

        ``Vz`` is only used when the unit is `alpha_disk` (the only
        one that derives this component from the other):
        mu_x = tan(alpha_disk)*Vz/(Omega*R)."""
        v = self.spin.value()
        if self.is_alpha_disk():
            ctx = self._ctx()
            if ctx is None:
                return 0.0
            rpm, radius_m = ctx
            return api.V_to_mu(float(np.tan(np.deg2rad(v))) * Vz, rpm, radius_m)
        convertido = self._mu_de(self.unit_combo.currentText(), v)
        return v if convertido is None else convertido

    def set_mu(self, mu_x: float, Vz: float = 0.0):
        self.spin.blockSignals(True)
        if self.is_alpha_disk():
            ctx = self._ctx()
            Vinf_long = 0.0
            if ctx is not None:
                rpm, radius_m = ctx
                Vinf_long = api.mu_to_V(mu_x, rpm, radius_m)
            self.spin.setValue(float(np.degrees(np.arctan2(Vinf_long, Vz)))
                                if abs(Vz) > 1e-9 else 0.0)
        else:
            novo = self._valor_em(self.unit_combo.currentText(), mu_x)
            self.spin.setValue(mu_x if novo is None else novo)
        self.spin.blockSignals(False)

    def set_default_unit(self, is_propeller: bool):
        """Rebuilds the unit list in the mode's convention,
        PRESERVING the physical quantity.

        What changes between modes is not just which unit comes
        pre-selected: it is the whole list. In propeller mode this
        field stops being the advance and becomes the cross flow (see
        `UNIDADES_DE_CONDICAO`), and offering "mu_x"/"J_x" there would
        keep inviting the user to type the aircraft's speed into the
        wrong field -- which was the original bug.

        If the user already chose a unit by hand WITHIN the current
        mode, that choice is respected; a mode switch is not: the old
        list has stopped existing."""
        is_propeller = bool(is_propeller)
        if is_propeller == self._is_propeller:
            return
        mu_antes = self.mu_x()
        self._is_propeller = is_propeller
        rotulos = _rotulos_de_unidade(self._SLOT, is_propeller)
        self.unit_combo.blockSignals(True)
        configurar_combo_de_unidades(
            self.unit_combo, UNIDADES_DE_CONDICAO[(self._SLOT, is_propeller)])
        alvo = _UNIDADE_PADRAO[(self._SLOT, is_propeller)]
        self.unit_combo.setCurrentText(alvo if alvo in rotulos else rotulos[0])
        self.unit_combo.blockSignals(False)
        self._prev_unit = self.unit_combo.currentText()
        self._ajustar_faixa()
        self.set_mu(mu_antes)


class AxialInput(QWidget):
    """The AXIAL component of the flight condition (the engine's
    `Vz`), in the unit the current mode makes natural.

    In ROTOR mode it is climb/descent: the disk angle alpha, or
    Vz [m/s]. In PROPELLER mode it is the flight speed, and comes
    non-dimensionalized as the classic propeller advance: J_x, mu_x
    or Vx_inf [m/s] (see `UNIDADES_DE_CONDICAO`).

    The combo sits on the left and serves as a clickable label. The
    alpha<->Vz conversion depends on mu_x/rpm/radius, so a
    context_provider must be registered for the conversion to be
    automatic when switching."""
    changed = pyqtSignal()

    _SLOT = "axial"

    def __init__(self, default_value: float = 0.0):
        super().__init__()
        self._is_propeller = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.unit_combo = _ComboDeUnidades()
        configurar_combo_de_unidades(
            self.unit_combo, UNIDADES_DE_CONDICAO[(self._SLOT, False)])
        self.spin = QDoubleSpinBox()
        self.spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.spin.setRange(-90, 90)
        self.spin.setDecimals(3)
        self.spin.setSingleStep(0.5)
        self.spin.setValue(default_value)
        layout.addWidget(self.unit_combo)   # combo = label, on the left
        layout.addWidget(self.spin)
        # The slack goes to the END, not to the field. With
        # `addWidget(spin, 1)` the spinbox got all the row's leftover
        # space; after `common.compactar_campos_de_formulario` started
        # limiting the numeric field's width, that space became a gap
        # of several hundred pixels BETWEEN the label-dropdown and the
        # value -- the two pieces of the same field ended up at
        # opposite ends of the window.
        layout.addStretch(1)
        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        self.spin.valueChanged.connect(self.changed.emit)
        self._context_provider = None   # callable() -> (mu_x, rpm, radius_m) | None
        #: once the user switches the combo by hand, `set_default_unit`
        #: stops overriding their choice WITHIN the same mode
        self._unidade_escolhida_pelo_usuario = False
        #: label the next conversion starts from -- with 3 units in
        #: propeller mode, "the other one" stopped being deducible
        self._prev_unit = self.unit_combo.currentText()

    def set_context_provider(self, fn):
        self._context_provider = fn

    def set_default_unit(self, is_propeller: bool):
        """Rebuilds the unit list in the mode's convention.

        A propeller's flight speed is AXIAL: it goes in this field.
        And on a propeller it is written non-dimensionalized as
        J_x = V/(nD) -- the J_x of the propeller charts --, not as a
        climb angle. Offering "alpha [deg]" here in propeller mode was
        worse than useless: the disk angle solves
        `Vz = tan(alpha)*V_in-plane`, which is ZERO in every straight
        axial flight, so the field could not express a propeller's
        most common condition.

        The user's manual choice is respected WITHIN a mode; a mode
        switch rebuilds the list (the old one has stopped
        existing)."""
        is_propeller = bool(is_propeller)
        if is_propeller == self._is_propeller:
            return
        ctx = self._ctx()
        mu_x, rpm, radius_m = ctx if ctx is not None else (0.0, 0.0, 0.0)
        Vv_antes = self.vv(mu_x, rpm, radius_m)
        self._is_propeller = is_propeller
        self._unidade_escolhida_pelo_usuario = False
        rotulos = _rotulos_de_unidade(self._SLOT, is_propeller)
        self.unit_combo.blockSignals(True)
        configurar_combo_de_unidades(
            self.unit_combo, UNIDADES_DE_CONDICAO[(self._SLOT, is_propeller)])
        alvo = _UNIDADE_PADRAO[(self._SLOT, is_propeller)]
        self.unit_combo.setCurrentText(alvo if alvo in rotulos else rotulos[0])
        self.unit_combo.blockSignals(False)
        # with signals blocked `_on_unit_changed` does not run, and it
        # is normally the one that adjusts the spinbox's range: without
        # this call the field would stay labeled "J_x" and stuck at
        # ±90.
        self._update_range()
        self.set_vv(Vv_antes, mu_x, rpm, radius_m)

    def is_alpha(self) -> bool:
        return self.variable_name() == "alpha_deg"

    def variable_name(self) -> str:
        """Canonical engine variable (`alpha_deg`/`Vz`/`mu_z`/`J_z`)."""
        return variavel_de_rotulo_de_unidade(self._SLOT, self.unit_combo.currentText()) or "Vz"

    def _ctx(self):
        return self._context_provider() if self._context_provider is not None else None

    def _on_unit_changed(self, _index: int):
        self._unidade_escolhida_pelo_usuario = True
        ctx = self._ctx()
        if ctx is not None:
            mu_x, rpm, radius_m = ctx
            # the Vz that the OLD value represented -- read before the
            # new unit takes effect, otherwise the conversion starts
            # from the wrong number
            anterior = getattr(self, "_prev_unit", None)
            Vz = self._vv_de(anterior, self.spin.value(), mu_x, rpm, radius_m) \
                if anterior is not None else self.spin.value()
            self.spin.blockSignals(True)
            self._update_range()
            self.set_vv(Vz, mu_x, rpm, radius_m)
            self.spin.blockSignals(False)
        else:
            self._update_range()
        self._prev_unit = self.unit_combo.currentText()
        self.changed.emit()

    def _update_range(self):
        if self.is_alpha():
            self.spin.setRange(-90, 90)
        elif self.variable_name() in ("mu_z", "J_z"):
            self.spin.setRange(-100, 100)
        else:
            self.spin.setRange(-1000, 1000)

    def raw_value(self) -> float:
        return self.spin.value()

    def _vv_de(self, rotulo: str, valor: float, mu_x: float, rpm: float,
                radius_m: float) -> float:
        var = variavel_de_rotulo_de_unidade(self._SLOT, rotulo)
        if var == "alpha_deg":
            return api.vv_from_alpha_deg(valor, mu_x, rpm, radius_m)
        if var == "mu_z":
            return api.mu_to_V(valor, rpm, radius_m)
        if var == "J_z":
            return api.mu_to_V(api.J_to_mu(valor), rpm, radius_m)
        return valor

    def vv(self, mu_x: float, rpm: float, radius_m: float) -> float:
        """``Vz`` [m/s] corresponding to the displayed value.

        ``mu_x`` only comes into play in the disk-angle branch -- the
        propeller units (J_x/mu_x/Vx_inf) report the axial component
        directly, without depending on the in-plane one. That is why
        `alpha_disk` does NOT live here."""
        return self._vv_de(self.unit_combo.currentText(), self.spin.value(),
                            mu_x, rpm, radius_m)

    def set_vv(self, Vz: float, mu_x: float, rpm: float, radius_m: float):
        var = self.variable_name()
        self.spin.blockSignals(True)
        if var == "alpha_deg":
            self.spin.setValue(api.alpha_deg_from_vv(Vz, mu_x, rpm, radius_m))
        elif var == "mu_z":
            self.spin.setValue(api.V_to_mu(Vz, rpm, radius_m))
        elif var == "J_z":
            self.spin.setValue(api.mu_to_J(api.V_to_mu(Vz, rpm, radius_m)))
        else:
            self.spin.setValue(Vz)
        self.spin.blockSignals(False)


