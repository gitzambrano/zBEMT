#!/usr/bin/env python3
"""Development patch for global inflow GUI/help integration.

This script is intentionally temporary.  It patches the feature branch in CI,
where the full Qt and regression environment is available, and the workflow
commits only the product files after all gates pass.
"""
from pathlib import Path
import re


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return out


# ---------------------------------------------------------------------------
# Engine: honor the configured outer-iteration budget.  The old 120-iteration
# cap was the only reason the last Coleman-Feingold envelope point stopped at
# residual ~4e-6; the same fixed point reaches <1e-6 at iteration 132.
# ---------------------------------------------------------------------------
p = Path("zbemt/bemt.py")
s = p.read_text(encoding="utf-8")
old = "max_outer = max(10, min(int(cfg.max_iter), 120))"
new = "max_outer = max(10, int(cfg.max_iter))"
if s.count(old) != 1:
    raise RuntimeError(f"bemt outer cap: expected one marker, found {s.count(old)}")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# GUI: restore the coupling selector and expose every steady empirical global
# model, including Coleman-Feingold (global-only).  Critically, loading a
# global project must round-trip the exact inflow_field_model rather than
# silently downgrading it to local.
# ---------------------------------------------------------------------------
p = Path("zbemt/gui/tabs/config.py")
s = p.read_text(encoding="utf-8")

coupling_block = '''    # Empirical inflow families may be solved either with their local
    # element/ring coupling or with a disk-wide GLOBAL first-harmonic field.
    # Coleman-Feingold exists only as a global empirical model. Pitt-Peters
    # keeps its own finite-state formulation and is steady on the case path.
    _AVAILABLE_COUPLINGS = {
        "glauert": ("local", "global"),
        "coleman": ("local", "global"),
        "coleman_feingold": ("global",),
        "drees": ("local", "global"),
        "pitt_peters": ("steady",),
    }
'''
s = sub_once(
    s,
    r'    # Inflow coupling is today FIXED per family\..*?    _FIXED_COUPLING = \{.*?\n    \}\n',
    coupling_block,
    "config coupling map",
)
s = s.replace("        self._warned_global_fallback = False\n", "", 1)

# Hide/show Pitt-Peters correctly immediately after its box is constructed.
needle = '''        self.pitt_peters_box = self._build_pitt_peters_box()\n        left.addWidget(self.pitt_peters_box)\n'''
replacement = '''        self.pitt_peters_box = self._build_pitt_peters_box()\n        left.addWidget(self.pitt_peters_box)\n        self._update_pitt_peters_visibility(self.cfg_inflow_family.currentText())\n'''
if s.count(needle) != 1:
    raise RuntimeError(f"config pitt box insertion: expected one marker, found {s.count(needle)}")
s = s.replace(needle, replacement, 1)

build_inflow = '''    def _build_inflow_box(self) -> QGroupBox:
        box = QGroupBox("Inflow model")
        form = QFormLayout(box)

        self.cfg_inflow_family = QComboBox()
        self.cfg_inflow_family.addItems([
            "glauert", "coleman", "coleman_feingold", "drees", "pitt_peters"
        ])
        self.cfg_inflow_family.setToolTip(
            '\"inflow_field_model\"<br><br>'
            'Selects the empirical/dynamic inflow family.<br><br>'
            '<b>glauert</b>: no first-harmonic wake-skew gradient.<br>'
            '<b>coleman</b>: classical longitudinal wake-skew gradient.<br>'
            '<b>coleman_feingold</b>: Coleman-Feingold global gradient, including lateral tilt.<br>'
            '<b>drees</b>: Drees longitudinal and lateral empirical gradients.<br>'
            '<b>pitt_peters</b>: finite-state dynamic inflow.')
        form.addRow("Inflow family:", self.cfg_inflow_family)

        self.cfg_inflow_coupling = QComboBox()
        self.cfg_inflow_coupling.setToolTip(
            '\"inflow_field_model\" coupling<br><br>'
            '<b>Local</b>: the empirical law is coupled to the local BEMT inflow solution.<br>'
            '<b>Global</b>: one disk-wide harmonic pair Kx, Ky is obtained from a '
            'global wake condition and the radial mean inflow is closed against the full 2D loading.<br>'
            '<b>Steady</b>: steady finite-state Pitt-Peters solution.')
        form.addRow("Formulation:", self.cfg_inflow_coupling)

        self._populate_inflow_coupling(self.cfg_inflow_family.currentText())
        self.cfg_inflow_family.currentTextChanged.connect(self._on_inflow_family_changed)
        return box

'''
s = sub_once(
    s,
    r'    def _build_inflow_box\(self\) -> QGroupBox:.*?(?=    def _build_prandtl_box\(self\) -> QGroupBox:)',
    build_inflow,
    "config inflow builder",
)

helpers = '''    def _populate_inflow_coupling(self, family: str, preferred: str | None = None):
        """Populate only physically implemented couplings for *family*.

        Signals are blocked while rebuilding the combo so a family change
        produces one coherent project-config write, never an intermediate
        or silently downgraded inflow_field_model.
        """
        choices = self._AVAILABLE_COUPLINGS.get(family, ())
        labels = {
            "local": "Local",
            "global": "Global",
            "steady": "Steady",
        }
        self.cfg_inflow_coupling.blockSignals(True)
        try:
            self.cfg_inflow_coupling.clear()
            for coupling in choices:
                self.cfg_inflow_coupling.addItem(labels.get(coupling, coupling), coupling)
            target = preferred if preferred in choices else (choices[0] if choices else None)
            if target is not None:
                idx = self.cfg_inflow_coupling.findData(target)
                self.cfg_inflow_coupling.setCurrentIndex(max(idx, 0))
        finally:
            self.cfg_inflow_coupling.blockSignals(False)

    def _on_inflow_family_changed(self, family: str):
        self._populate_inflow_coupling(family)
        self._update_pitt_peters_visibility(family)

    def _update_pitt_peters_visibility(self, family: str):
        """Pitt-Peters parameters have meaning only for that family."""
        self.pitt_peters_box.setVisible(family == "pitt_peters")

    def _inflow_field_model_from_widgets(self) -> str:
        family = self.cfg_inflow_family.currentText()
        coupling = self.cfg_inflow_coupling.currentData()
        if not coupling:
            choices = self._AVAILABLE_COUPLINGS.get(family, ())
            if not choices:
                raise ValueError(f"Unknown inflow family: {family!r}")
            coupling = choices[0]
        return f"{family}_{coupling}"

    def _set_inflow_widgets_from_field_model(self, inflow_field_model: str):
        if inflow_field_model.startswith("pitt_peters_"):
            family = "pitt_peters"
            coupling = inflow_field_model[len("pitt_peters_"):]
        else:
            family, coupling = inflow_field_model.rsplit("_", 1)

        choices = self._AVAILABLE_COUPLINGS.get(family)
        if choices is None or coupling not in choices:
            # Do not silently reinterpret a project. Unknown/inapplicable
            # values belong to validation; the GUI may show them but must not
            # rewrite a recognized GLOBAL model as local.
            raise ValueError(
                f"inflow_field_model={inflow_field_model!r} is not available in the case Config tab")

        self.cfg_inflow_family.blockSignals(True)
        try:
            self.cfg_inflow_family.setCurrentText(family)
        finally:
            self.cfg_inflow_family.blockSignals(False)
        self._populate_inflow_coupling(family, preferred=coupling)
        self._update_pitt_peters_visibility(family)

'''
s = sub_once(
    s,
    r'    def _update_pitt_peters_visibility\(self, family: str\):.*?(?=    # --- 7-8\) Snel \+ radial flow)',
    helpers,
    "config inflow helpers",
)
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# Block help: distinguish local vs global coupling and document all three
# requested global empirical laws explicitly.
# ---------------------------------------------------------------------------
p = Path("zbemt/gui/help_blocks.py")
s = p.read_text(encoding="utf-8")
new_block = r'''    "inflow": {
        "title": "Inflow Model: local and global empirical wake fields",
        "body": [
            "The empirical inflow families use a mean induced inflow plus a first harmonic over the rotor disk. In a global formulation the field is written as:"
            "\n\n"
            r"$$\lambda_i(r,\psi)=\lambda_0(r)\left[1+K_x\,x\cos\psi+K_y\,x\sin\psi\right],\qquad x=r/R$$",
            "<b>Local versus global.</b> In a local formulation, the empirical wake-skew law is coupled to the local BEMT inflow field. In a global formulation, one disk-wide pair (K<sub>x</sub>, K<sub>y</sub>) is computed from one global wake condition. The radial mean λ<sub>0</sub>(r) is then closed iteratively against the loads evaluated on the complete two-dimensional (r,ψ) disk. The global model therefore does not compute a different K at every element.",
            "<b>Glauert.</b> K<sub>x</sub>=K<sub>y</sub>=0. Local and global forms are available; with no harmonic gradient they provide the axisymmetric reference coupling.",
            "<b>Coleman global.</b> Uses the classical Coleman longitudinal first harmonic and K<sub>y</sub>=0. The same disk-wide K<sub>x</sub> applies at every radial/azimuthal station.",
            "<b>Coleman-Feingold global.</b> This is a distinct global model, not an alias of Coleman:"
            "\n\n"
            r"$$K_x=\frac{15\pi}{32}\frac{\mu}{\sqrt{\mu^2+\lambda^2}+|\lambda|},\qquad K_y=-2\mu$$",
            "<b>Drees global.</b> Uses the Drees wake-skew relation with both longitudinal and lateral gradients:"
            "\n\n"
            r"$$K_x=\frac{4}{3}\left[\frac{1-\cos\chi-1.8\mu^2}{\sin\chi}\right],\qquad K_y=-2\mu,\qquad \chi=\operatorname{atan2}(\mu,\lambda)$$",
            "All empirical global models collapse to the axisymmetric solution in hover because the skew gradients vanish. The global closure uses the normal BEMT solver for the complete 2D loading and honors the configured maximum iteration count and convergence tolerance.",
            "<b>Pitt-Peters</b> is different: it solves a finite-state inflow model rather than imposing one of these empirical harmonic laws."
        ],
        "anchor": "cap-4-2",
    },
'''
s = sub_once(
    s,
    r'    "inflow": \{.*?(?=    "tip_root_loss": \{)',
    new_block,
    "block inflow help",
)
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# Field-level help opened from the input control itself.
# ---------------------------------------------------------------------------
p = Path("zbemt/gui/help_content.py")
s = p.read_text(encoding="utf-8")
field_block = r'''    "inflow_field_model": {
        "title": "Inflow Field Model",
        "definition": (
            "Selects both the inflow family and the coupling used to build the induced-velocity field.\n\n"
            "Local empirical variants couple the wake law to the local BEMT inflow. Global variants use one disk-wide wake-skew condition and close the radial mean inflow against the full two-dimensional disk loading."
        ),
        "unit": "—",
        "equation": r"\lambda_i(r,\psi)=\lambda_0(r)\,[1+K_x(r/R)\cos\psi+K_y(r/R)\sin\psi]",
        "effect": "The choice changes the azimuthal induced-velocity distribution and therefore the integrated hub forces, moments, induced power and local blade loading in forward flight. All empirical global variants reduce to the axisymmetric solution in hover.",
        "range": "one of the implemented inflow_field_model values",
        "options": {
            "glauert_local": "Axisymmetric Glauert/annular BEMT with local coupling.",
            "glauert_global": "Axisymmetric Glauert law evaluated through the global radial closure.",
            "coleman_local": "Coleman wake-skew correction coupled to the local BEMT field.",
            "coleman_global": "Classical Coleman longitudinal gradient using one disk-wide Kx and Ky=0.",
            "coleman_feingold_global": "Coleman-Feingold global law: Kx=(15π/32) μ/(sqrt(μ²+λ²)+|λ|), Ky=-2μ.",
            "drees_local": "Drees longitudinal/lateral empirical law coupled to the local BEMT field.",
            "drees_global": "Drees global law using one disk-wide Kx and Ky=-2μ, closed against the full 2D loading.",
            "pitt_peters_steady": "Steady three-state Pitt-Peters finite-state inflow.",
            "pitt_peters_unsteady": "Time-marching Pitt-Peters finite-state inflow; used by the maneuver/transient path, not an isolated case."
        },
        "anchor": "cap-4-2",
    },
'''
s = sub_once(
    s,
    r'    "inflow_field_model": \{.*?(?=    "prandtl_loss_mode": \{)',
    field_block,
    "field inflow help",
)
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# Persistent GUI regression: every requested global model must be selectable
# and round-trip to the exact engine enum. Coleman-Feingold must never expose
# a fictitious local variant.
# ---------------------------------------------------------------------------
p = Path("tests/regression/test_option_discoverability.py")
s = p.read_text(encoding="utf-8")
marker = '''    def test_an_option_blocked_by_the_mode_stays_disabled_and_does_not_vanish(self):\n'''
insert = '''    def test_global_empirical_inflow_models_are_selectable_and_round_trip(self):\n        config = self._tab("Config")\n        cases = {\n            "glauert_global": ("glauert", "global"),\n            "coleman_global": ("coleman", "global"),\n            "coleman_feingold_global": ("coleman_feingold", "global"),\n            "drees_global": ("drees", "global"),\n        }\n        for field_model, (family, coupling) in cases.items():\n            with self.subTest(field_model=field_model):\n                config._set_inflow_widgets_from_field_model(field_model)\n                self.assertEqual(config.cfg_inflow_family.currentText(), family)\n                self.assertEqual(config.cfg_inflow_coupling.currentData(), coupling)\n                self.assertEqual(config._inflow_field_model_from_widgets(), field_model)\n\n    def test_coleman_feingold_does_not_offer_a_fictitious_local_variant(self):\n        config = self._tab("Config")\n        config.cfg_inflow_family.setCurrentText("coleman_feingold")\n        self.app.processEvents()\n        values = [config.cfg_inflow_coupling.itemData(i)\n                  for i in range(config.cfg_inflow_coupling.count())]\n        self.assertEqual(values, ["global"])\n        self.assertEqual(config._inflow_field_model_from_widgets(),\n                         "coleman_feingold_global")\n\n'''
if s.count(marker) != 1:
    raise RuntimeError(f"option discoverability marker: expected one, found {s.count(marker)}")
s = s.replace(marker, insert + marker, 1)
p.write_text(s, encoding="utf-8")

print("patched global inflow engine budget, GUI, help, and regression tests")
