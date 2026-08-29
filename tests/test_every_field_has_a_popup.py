"""Every configurable field opens a popup, in EVERY window (`PR-2`).

CLAUDE.md states the rule without exception: "Every configurable field
needs a popup explaining the physics and the mathematics behind it."
The enforcement had one. `field_help.install_field_popups` was called
from `app.py` for the main window's seven tabs and from `dialogs.py`,
and nowhere else, so none of the four Tools windows was covered: 26 of
their controls carried a usable tooltip that opened nothing, and 58
more carried a tooltip with no field name at all, which the help system
cannot even see. The Stability window was at zero.

What makes a control popup-ready is a chain of three links, and all
three have to hold:

1. it has a tooltip;
2. the tooltip OPENS with the field name in quotes, because that is
   what `install_field_popups` reads to decide which field a control
   belongs to;
3. the field resolves, either to a `help_content.FIELD_HELP` entry or
   to a section of the documentation.

A control that only chooses a VIEW of results that already exist -- a
colour scale, which quantity to paint on the disk, which sample to draw
-- is exempt, and `tools/field_index.py` already states that exemption
for the Results tab. Nothing it does reaches the project or a study.
The exemption is a NAMED LIST here rather than a rule, so that a new
field cannot fall into it by accident: a control this test does not
know about has to be either equipped or added deliberately.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import HAS_QT

if HAS_QT:                                        # pragma: no branch
    from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox,
                                 QDoubleSpinBox, QLineEdit, QSpinBox)

    #: Widget kinds that hold a value the user sets.
    INPUT_KINDS = (QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit)

#: Controls that select a VIEW of existing results, not a field of the
#: project. Named one by one, with the window they live in, so that a
#: genuinely new field cannot join them silently.
VIEW_ONLY = {
    # Airfoil: the polar preview's own controls.
    "alpha_range_combo", "autoscale_y_check", "show_reverse_branch_check",
    "mach_compare_edit",
    # Run Case: picks a stored case to load into the form.
    "saved_cases_combo",
    # Results: the whole tab chooses what to draw from results that
    # already exist. This is the exemption `tools/field_index.py`
    # documents for the same tab.
    "condition_combo", "flap_effect_field_combo", "field_combo",
    "z_field_combo", "sweep_x_combo", "sweep_psi_edit", "sweep_r_edit",
    "axis_mode_xy_check", "axis_combo", "overlay_check", "xy_x_combo",
    "xy_y_combo", "xy_group_combo", "group_tol_spin", "disk_field_combo",
    "disk_color_scale_combo", "disk_color_vmin_edit", "disk_color_vmax_edit",
    "backend_combo",
    # The three Tools windows' view pickers.
    "view_combo",        # Optimization: Pareto, parallel or convergence
    "bar_output_combo",  # Stability: which output the bar chart ranks
    "disk_slider",       # Transient: which sample's disk map is drawn
}


def _named_inputs(root):
    """``{widget: attribute name}`` for every input under ``root``.

    Keyed by the attribute the source calls it, because a failure has to
    name the control in the words a reader can grep for.
    """
    from zbemt.gui.field_help_data import _NAME_IN_TOOLTIP

    by_id = {}
    for name in dir(root):
        if name.startswith("__"):
            continue
        try:
            value = getattr(root, name)
        except Exception:                          # pragma: no cover
            continue
        if isinstance(value, INPUT_KINDS):
            by_id[id(value)] = name

    found = []
    for widget in root.findChildren(INPUT_KINDS):
        # A spin box owns an internal QLineEdit and an editable combo
        # owns another; both are the same field as their parent.
        if widget.objectName() == "qt_spinbox_lineedit":
            continue
        if isinstance(widget, QLineEdit) and isinstance(widget.parent(),
                                                         QComboBox):
            continue
        # A COMPOSITE field (the flow rows: a unit dropdown and a spin
        # box in one QWidget) is equipped as a whole, on the composite.
        parent = widget.parent()
        equipped_ancestor = False
        while parent is not None:
            if getattr(parent, "_has_field_popup", False):
                equipped_ancestor = True
                break
            parent = parent.parent()
        if equipped_ancestor:
            continue
        tip = widget.toolTip() or ""
        ready = bool(_NAME_IN_TOOLTIP.match(tip))
        found.append((by_id.get(id(widget)), widget, tip, ready))
    return found


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestEveryFieldIsPopupReady(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        from zbemt.gui.app import MainWindow

        cls.window = MainWindow()

    def _check(self, title, root):
        from zbemt.gui import help_content
        from zbemt.gui.field_help_data import field_anchor, _NAME_IN_TOOLTIP

        for attribute, widget, tip, ready in _named_inputs(root):
            if attribute in VIEW_ONLY:
                continue
            label = attribute or widget.__class__.__name__
            with self.subTest(window=title, control=label):
                self.assertTrue(
                    tip.strip(),
                    f"{title}: {label} has NO TOOLTIP. Every configurable "
                    f"field needs one, and without it the field cannot "
                    f"be equipped with a popup either.")
                self.assertTrue(
                    ready,
                    f"{title}: {label} has a tooltip that does not open "
                    f'with the field name in quotes ("field" - text). '
                    f"That name is what `install_field_popups` reads, so "
                    f"without it the control opens nothing when clicked. "
                    f"Add the name, or list it in VIEW_ONLY if it only "
                    f"selects a view of existing results.")
                field = _NAME_IN_TOOLTIP.match(tip).group(1).split(".")[-1]
                self.assertTrue(
                    field_anchor(field) is not None
                    or field in help_content.FIELD_HELP,
                    f"{title}: {label} names the field {field!r}, which "
                    f"resolves to no documentation section and has no "
                    f"`help_content.FIELD_HELP` entry, so the popup would "
                    f"open nothing. Add an entry, or a section.")

    def test_every_tab_of_the_main_window(self):
        for i in range(self.window.tabs.count()):
            self._check(f"tab {self.window.tabs.tabText(i)}",
                         self.window.tabs.widget(i))

    def test_every_tools_window(self):
        """The four that were entirely outside the help system."""
        from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
        from zbemt.gui.tabs.optimizer_window import OptimizerWindow
        from zbemt.gui.tabs.stability_window import StabilityWindow
        from zbemt.gui.tabs.transient_window import TransientWindow

        for title, klass in (("Geometry Designer", GeometryDesignerWindow),
                              ("Design Optimization", OptimizerWindow),
                              ("Stability", StabilityWindow),
                              ("Transient", TransientWindow)):
            self._check(title, klass(self.window.state))

    def test_the_tools_windows_install_the_popups_at_all(self):
        """The root cause, stated on its own.

        Every field above could be perfectly named and still open
        nothing, because naming a field does not equip it: the window
        has to CALL `install_field_popups`. It did not, in any of the
        four, which is why this is checked separately from the naming.
        """
        import io
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "zbemt" / "gui" / "tabs"
        for name in ("designer_window", "optimizer_window",
                      "stability_window", "transient_window"):
            with self.subTest(window=name):
                source = io.open(root / f"{name}.py", encoding="utf-8").read()
                self.assertIn(
                    "install_field_popups(self)", source,
                    f"{name}.py never installs the field popups, so none "
                    f"of its labels opens anything when clicked.")


def tearDownModule():
    """Qt's teardown, not the interpreter's -- see the note in
    `tests/test_small_screen.py`."""
    if not HAS_QT:                                # pragma: no cover
        return
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
