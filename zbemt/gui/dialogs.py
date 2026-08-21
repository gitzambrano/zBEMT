"""Define modal GUI dialogs for geometry and project operations.

Dialogs accept user-entered values through Qt widgets and return validated values or
an explicit cancellation. They delegate domain validation and persistence to the
application and model layers, do not run the aerodynamic solver, and must remain
usable in headless test construction where supported.
"""

from __future__ import annotations

import math

from PyQt6.QtWidgets import (
    QVBoxLayout, QFormLayout, QLabel, QComboBox, QDoubleSpinBox, QSpinBox, QDialog,
    QDialogButtonBox, QStyle, QWidget,
)
from PyQt6.QtCore import Qt

from .. import geometry
from ..models import RotorGeometryDef

from .common import show_error


def ajustar_largura_de_combo(combo: QComboBox, folga: int = 28) -> int:
    """Makes the combo -- and especially its POPUP -- fit the widest item.

    Without this Qt sizes the dropdown by the width of the combo itself
    (which QFormLayout squeezes), and options appear cut off or elided with
    "…": the user opens the dropdown and can't read the alternatives.
    Returns the calculated width (in px) for whoever wants to reuse it."""
    if combo.count() == 0:
        return 0
    fm = combo.fontMetrics()
    largura = max(fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count()))
    barra = combo.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
    total = largura + barra + folga
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    combo.setMinimumWidth(total)
    view = combo.view()
    if view is not None:
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setMinimumWidth(total)
        # The popup can be created before the first show and ignore only the
        # minimum width during initial geometry calculation; an explicit width
        # ensures no long option is cut off when it opens.
        view.setMinimumSize(view.minimumSize().expandedTo(combo.sizeHint()))
        # HEIGHT: Qt sizes the popup from the view's own frame, which loses
        # a couple of px to the QSS border set on QComboBox QAbstractItemView
        # (styles.py) -- with few items (e.g. 3) that is enough to make the
        # LAST row render partially cut off and a scroll indicator appear,
        # even though the popup has plenty of room to just show every item.
        # Seen on screen: "Type:" (rectangular/tapered/elliptic) in the
        # radial-table generator dialog. Summing each row's own sizeHint
        # (not a flat estimate) and padding it covers custom per-row
        # heights too.
        altura_linhas = sum(max(view.sizeHintForRow(i), 0) for i in range(combo.count()))
        moldura = 2 * view.frameWidth() + 8
        view.setMinimumHeight(altura_linhas + moldura)
    return total


# =============================================================================
# Tab 2 — Geometry (geometry = table; parametric generation is a popup)
# =============================================================================

class GeometryGeneratorDialog(QDialog):
    """Modal popup (docs/plano.md Section 3) that generates a new radial
    table from parameters.

    Number of blades and Radius are EDITABLE here (item 2): they were just
    constants passed in, which forced closing the popup, fixing the number
    of blades in the Geometry tab, and reopening -- precisely the parameter
    the solidity shown below depends on. Editing them here updates solidity
    and aspect ratio live, and the final value returns to the Geometry tab
    along with the generated table (``generated_geom.n_blades``/``radius_m``,
    see ``GeometryTab._open_generator``). Confirm replaces the main table;
    cancel does nothing."""

    def __init__(self, parent, n_blades: int, radius_m: float, airfoil_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Generate radial table")
        self._airfoil_name = airfoil_name
        self.generated_geom: RotorGeometryDef | None = None
        # Reentrancy between chord<->solidity/AR (all derive from the same
        # normalized blade area, see `_blade_area_norm`) -- without this guard,
        # `_on_param_changed` rewriting the chord fields would fire it again
        # via the `valueChanged` signals themselves.
        self._syncing_solidity_ar = False

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._form = form

        # Number of blades and radius: the two global rotor constants, now
        # inside the popup ("all in one place") -- see the class docstring.
        self.n_blades = QSpinBox(); self.n_blades.setRange(1, 12); self.n_blades.setValue(int(n_blades))
        self.n_blades.setToolTip('"n_blades" — number of rotor/propeller blades; '
                                  'solidity σ below scales directly with it')
        self.radius_m = QDoubleSpinBox(); self.radius_m.setRange(0.01, 100.0)
        self.radius_m.setDecimals(4); self.radius_m.setSingleStep(0.1)
        self.radius_m.setValue(float(radius_m))
        self.radius_m.setToolTip('"radius_m" — rotor/propeller radius [m]; '
                                  'chords below are dimensionless by it (c/R)')
        form.addRow("Number of blades:", self.n_blades)
        form.addRow("Rotor radius [m]:", self.radius_m)

        self.kind_combo = QComboBox()
        self.kind_combo.addItems(["rectangular", "tapered", "elliptic"])
        self.kind_combo.setToolTip('"kind" — chord distribution type along the radius')
        self.kind_combo.currentTextChanged.connect(self._update_kind_fields)
        ajustar_largura_de_combo(self.kind_combo)
        form.addRow("Type:", self.kind_combo)

        self.root_cutout = QDoubleSpinBox(); self.root_cutout.setRange(0.0, 0.9)
        self.root_cutout.setSingleStep(0.01); self.root_cutout.setValue(0.15)
        self.root_cutout.setToolTip('"root_cutout_norm" — dimensionless root cutout (r/R)')
        self.n_stations = QSpinBox(); self.n_stations.setRange(3, 200); self.n_stations.setValue(25)
        self.n_stations.setToolTip('"n_stations" — number of discretization stations along the blade')
        form.addRow("Root cutout (r/R):", self.root_cutout)
        form.addRow("Number of stations:", self.n_stations)

        self.chord_a = QDoubleSpinBox(); self.chord_a.setRange(0.001, 2.0)
        self.chord_a.setDecimals(4)
        self.chord_a.setSingleStep(0.01); self.chord_a.setValue(0.10)
        self.chord_a.setToolTip('"chord_norm" or "root_chord_norm" — chord dimensionless by radius (c/R)')
        self.chord_b = QDoubleSpinBox(); self.chord_b.setRange(0.001, 2.0)
        self.chord_b.setDecimals(4)
        self.chord_b.setSingleStep(0.01); self.chord_b.setValue(0.04)
        self.chord_b.setToolTip('"tip_chord_norm" — chord dimensionless by radius at tip (c/R)')
        self.twist_root = QDoubleSpinBox(); self.twist_root.setRange(-30, 60); self.twist_root.setValue(14.0)
        self.twist_root.setSingleStep(0.5)
        self.twist_root.setToolTip('"twist_root_deg" — twist angle at blade root [degrees]')
        self.twist_tip = QDoubleSpinBox(); self.twist_tip.setRange(-30, 60); self.twist_tip.setValue(2.0)
        self.twist_tip.setSingleStep(0.5)
        self.twist_tip.setToolTip('"twist_tip_deg" — twist angle at blade tip [degrees]')

        self.chord_a_label = QLabel("Root chord (c/R):")
        self.chord_b_label = QLabel("Tip chord (c/R):")
        form.addRow(self.chord_a_label, self.chord_a)
        form.addRow(self.chord_b_label, self.chord_b)

        # Solidity/AR are just another way to see the same blade area that
        # the chord fields above define -- editing any of the four recalculates
        # the others in real time (all linked to `_on_param_changed`).
        self.solidity = QDoubleSpinBox(); self.solidity.setRange(0.0001, 2.0)
        self.solidity.setDecimals(4); self.solidity.setSingleStep(0.005)
        self.solidity.setToolTip('"solidity" — σ = Nb·S_blade/(π·R²), blade area fraction of the disk; '
                                  'alternate way to set the chord fields above (they stay linked)')
        self.aspect_ratio = QDoubleSpinBox(); self.aspect_ratio.setRange(0.1, 1000.0)
        self.aspect_ratio.setDecimals(2); self.aspect_ratio.setSingleStep(0.5)
        self.aspect_ratio.setToolTip('"aspect_ratio" — AR = R²/S_blade, blade planform aspect ratio; '
                                      'alternate way to set the chord fields above (they stay linked)')
        form.addRow("Solidity σ:", self.solidity)
        form.addRow("Blade aspect ratio:", self.aspect_ratio)

        form.addRow("Root twist [deg]:", self.twist_root)
        form.addRow("Tip twist [deg]:", self.twist_tip)
        layout.addLayout(form)

        buttons = QDialogButtonBox()
        btn_ok = buttons.addButton("Generate and replace table", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_ok.setToolTip("Replace current radial geometry data with the parametrized distribution above")
        buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        btn_ok.clicked.connect(self._on_confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # `garantir_botoes_legiveis` is applied by TAB in `app.MainWindow`;
        # a dialog is its own window and never went through there, so
        # "Generate and replace table" stayed elided by `QDialogButtonBox`,
        # which splits the width among buttons.
        from .common import garantir_botoes_legiveis, alinhar_rotulos_de_formulario
        garantir_botoes_legiveis(self)
        # Same reason: label alignment is a window policy and the dialog
        # does not go through the tab scan -- without this labels are
        # justified right and initials misalign.
        alinhar_rotulos_de_formulario(self)
        # Besides fitting, this is the dialog's main button; a larger width
        # makes the entire action readable even with high screen scaling.
        btn_ok.setMinimumWidth(max(btn_ok.minimumWidth(), 330))
        # QDialogButtonBox redistributes available width among buttons;
        # the isolated button's floor does not prevent text from being elided
        # when the box itself becomes narrow.
        largura_botoes = sum(b.minimumWidth() for b in buttons.buttons()) + 32
        buttons.setMinimumWidth(largura_botoes)
        # And the dialog needs to be wide enough from birth to fit the button
        # row already with this floor -- otherwise the text fits in the button,
        # but the button doesn't fit in the window.
        # The extra slack is an explicit owner request ("expand this window
        # horizontally a little wider"): with strict minimum width the dialog
        # opened with fields flush against the edges.
        self.setMinimumWidth(max(self.sizeHint().width(),
                                  buttons.minimumSizeHint().width() + 48) + 140)

        self.chord_a.valueChanged.connect(lambda _v: self._on_param_changed("chord_a"))
        self.chord_b.valueChanged.connect(lambda _v: self._on_param_changed("chord_b"))
        self.root_cutout.valueChanged.connect(lambda _v: self._on_param_changed("root_cutout"))
        self.solidity.valueChanged.connect(lambda _v: self._on_param_changed("solidity"))
        self.aspect_ratio.valueChanged.connect(lambda _v: self._on_param_changed("aspect_ratio"))
        self.kind_combo.currentTextChanged.connect(lambda _k: self._on_param_changed("kind"))
        # Number of blades enters σ = Nb·S/π: changing blades must move solidity
        # (and AR stays the same, because it's per-blade) at the same time.
        self.n_blades.valueChanged.connect(lambda _v: self._on_param_changed("n_blades"))

        self._update_kind_fields(self.kind_combo.currentText())
        self._on_param_changed("chord_a")
        # The window is created outside the main tabs; so the application's
        # global help installation doesn't reach its fields. Equip here
        # the documented labels with the same contextual popup as the interface.
        from .field_help import instalar_popups_de_campo
        instalar_popups_de_campo(self)

    def _label_atual(self, campo_widget) -> QWidget:
        """Returns whatever widget currently sits in `campo_widget`'s row,
        LabelRole -- NOT `self.chord_a_label`/`self.chord_b_label`.

        `instalar_popups_de_campo` (called at the end of `__init__`)
        replaces every field's label QLabel with a clickable QToolButton
        (`field_help._label_clicavel`), inserted via `form.setWidget(...)`.
        That leaves `self.chord_a_label`/`self.chord_b_label` pointing at
        orphaned widgets no longer in the layout -- `.setText()`/
        `.setVisible()` on them silently do nothing after that point.
        Looking the label up by the (never-replaced) FIELD widget's row,
        every time, is what survives the swap.
        """
        row, _role = self._form.getWidgetPosition(campo_widget)
        item = self._form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        return item.widget() if item is not None else campo_widget

    def _update_kind_fields(self, kind: str):
        from .common import definir_linha_visivel
        label_a = self._label_atual(self.chord_a)
        label_b = self._label_atual(self.chord_b)
        if kind == "rectangular":
            label_a.setText("Chord (c/R):")
            definir_linha_visivel(self._form, self.chord_b, False)
        elif kind == "elliptic":
            label_a.setText("Max chord (c/R):")
            definir_linha_visivel(self._form, self.chord_b, False)
        else:  # tapered
            label_a.setText("Root chord (c/R):")
            label_b.setText("Tip chord (c/R):")
            definir_linha_visivel(self._form, self.chord_b, True)

    def _blade_area_norm(self, kind: str, chord_a: float, chord_b: float, root_cutout: float) -> float:
        """Single blade area normalized by R² (S_blade/R²), integrating
        chord_norm(r) from root_cutout to 1 -- the single source from which
        solidity (σ = Nb·S/π) and blade AR (= 1/S) are derived, see the
        class docstring."""
        span = max(0.0, 1.0 - root_cutout)
        if kind == "rectangular":
            return chord_a * span
        if kind == "tapered":
            return 0.5 * (chord_a + chord_b) * span
        # elliptic: chord(r) = max_chord_norm * sqrt(1-r^2) / sqrt(1-rc^2)
        # (the denominator is the same peak rescaling done in
        # geometry.generate_elliptic, see its docstring).
        rc = min(max(root_cutout, 0.0), 0.999999)
        denom = math.sqrt(max(1e-12, 1.0 - rc ** 2))
        integral = (math.pi / 4.0) - 0.5 * (rc * math.sqrt(max(0.0, 1.0 - rc ** 2)) + math.asin(rc))
        return (chord_a / denom) * integral

    def _invert_chords_for_area(self, kind: str, target_area: float, chord_a: float,
                                 chord_b: float, root_cutout: float) -> tuple[float, float]:
        """Inverts `_blade_area_norm`: given the target area, solves for the
        chord fields. Tapered is underdetermined (1 equation, 2 unknowns)
        -- solved by scaling root/tip proportionally, preserving the current
        shape (tip/root ratio)."""
        target_area = max(0.0, target_area)
        span = max(1e-9, 1.0 - root_cutout)
        if kind == "rectangular":
            return target_area / span, chord_b
        if kind == "tapered":
            current = self._blade_area_norm(kind, chord_a, chord_b, root_cutout)
            if current <= 1e-9:
                flat = target_area / span
                return flat, flat
            k = target_area / current
            return chord_a * k, chord_b * k
        # elliptic
        rc = min(max(root_cutout, 0.0), 0.999999)
        denom = math.sqrt(max(1e-12, 1.0 - rc ** 2))
        integral = (math.pi / 4.0) - 0.5 * (rc * math.sqrt(max(0.0, 1.0 - rc ** 2)) + math.asin(rc))
        if integral <= 1e-9:
            return chord_a, chord_b
        return target_area * denom / integral, chord_b

    def _on_param_changed(self, source: str):
        if self._syncing_solidity_ar:
            return
        self._syncing_solidity_ar = True
        try:
            kind = self.kind_combo.currentText()
            rc = self.root_cutout.value()
            if source in ("solidity", "aspect_ratio"):
                if source == "solidity":
                    area = self.solidity.value() * math.pi / max(self.n_blades.value(), 1)
                else:
                    ar = self.aspect_ratio.value()
                    area = 1.0 / ar if ar > 1e-9 else 0.0
                new_a, new_b = self._invert_chords_for_area(
                    kind, area, self.chord_a.value(), self.chord_b.value(), rc)
                self.chord_a.setValue(new_a)
                if kind == "tapered":
                    self.chord_b.setValue(new_b)
            area = self._blade_area_norm(kind, self.chord_a.value(), self.chord_b.value(), rc)
            self.solidity.setValue(self.n_blades.value() * area / math.pi)
            self.aspect_ratio.setValue(1.0 / area if area > 1e-9 else self.aspect_ratio.maximum())
        finally:
            self._syncing_solidity_ar = False

    def _on_confirm(self):
        kind = self.kind_combo.currentText()
        kwargs = dict(
            root_cutout_norm=self.root_cutout.value(), radius_m=self.radius_m.value(),
            n_blades=self.n_blades.value(), n_stations=self.n_stations.value(),
            twist_root_deg=self.twist_root.value(), twist_tip_deg=self.twist_tip.value(),
            airfoil_name=self._airfoil_name,
        )
        try:
            if kind == "rectangular":
                geom = geometry.generate_rectangular(chord_norm=self.chord_a.value(), **kwargs)
            elif kind == "elliptic":
                geom = geometry.generate_elliptic(max_chord_norm=self.chord_a.value(), **kwargs)
            else:
                geom = geometry.generate_tapered(root_chord_norm=self.chord_a.value(),
                                                  tip_chord_norm=self.chord_b.value(), **kwargs)
        except Exception as exc:
            show_error(self, "Error generating geometry", exc)
            return
        self.generated_geom = geom
        self.accept()

