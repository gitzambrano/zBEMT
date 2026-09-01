"""
test_option_discoverability.py
==============================

An option the user cannot find is an option the software does not have.

Two ways that happens, one for each half of PR-2 and one for the dropdowns:

  * A dropdown opens showing ten of its seventeen entries. The popup looks
    complete -- it ends in a row, not in an ellipsis -- so the seven below
    are found only by someone who thinks to scroll a list that gave no sign
    of continuing. This was seen on screen with the disk-map field
    selectors in the Results tab.
  * An option that exists but does not apply to the current mode is HIDDEN
    rather than DISABLED. The user then cannot learn that the option
    exists, or why it is unavailable; the field simply is not there, which
    reads as "this software cannot do that".

The distinction PR-2 draws is between the two cases. A control that is
meaningless in the current configuration -- a Pitt-Peters parameter with
Glauert selected -- is hidden, because it has nothing to say. A control
that is real but blocked -- a choice the current mode forbids -- is shown
disabled, because its presence is the information.
"""
from __future__ import annotations

import os
import unittest

try:
    from PyQt6.QtWidgets import QApplication, QComboBox
    _HAS_QT = True
except Exception:                                        # pragma: no cover
    _HAS_QT = False


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestTodaOpcaoAparece(unittest.TestCase):
    """Every dropdown in the assembled window."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from zbemt.gui.app import MainWindow

        cls.app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()
        cls.window.resize(1400, 900)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.window.deleteLater()

    def test_no_combo_hides_options_behind_scrolling(self):
        """`maxVisibleItems` must cover the whole list.

        Qt's default is 10 and applies silently, so this only shows up
        once a list crosses that length -- which is exactly when the list
        is long enough that the user cannot guess what is missing."""
        from zbemt.gui.common import MAX_OPTIONS_WITHOUT_SCROLL

        hidden = []
        for combo in self.window.findChildren(QComboBox):
            if combo.count() > combo.maxVisibleItems():
                hidden.append(
                    f"{combo.count()} options, {combo.maxVisibleItems()} visible: "
                    f"{[combo.itemText(i) for i in range(combo.count())][:4]}")
        self.assertEqual(
            hidden, [],
            "dropdown that opens without showing every option "
            f"(the cap is {MAX_OPTIONS_WITHOUT_SCROLL}): " + str(hidden))

    def test_a_combo_filled_later_also_shows_everything(self):
        """The lists that overflowed were filled from results, long after
        the window was built, so the cap has to survive a later change of
        contents rather than being computed once from the count."""
        combos = self.window.findChildren(QComboBox)
        self.assertTrue(combos, "no combo found in the window")
        target = combos[0]
        before = target.count()
        target.addItems([f"extra {i}" for i in range(20)])
        try:
            self.assertGreaterEqual(
                target.maxVisibleItems(), target.count(),
                "a combo filled after construction went back to hiding options")
        finally:
            while target.count() > before:
                target.removeItem(target.count() - 1)


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestProgressiveDisclosure(unittest.TestCase):
    """PR-2's second half. The hidden-row half -- a hidden field must not
    leave its label behind -- is checked in `test_gui_layout.py`; what is
    checked here is that hiding is used for the right reason."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from zbemt.gui.app import MainWindow

        cls.app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()
        cls.window.resize(1400, 900)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.window.deleteLater()

    def _tab(self, title):
        for i in range(self.window.tabs.count()):
            if self.window.tabs.tabText(i).startswith(title):
                return self.window.tabs.widget(i)
        self.fail(f"tab '{title}' not found")

    def test_the_pitt_peters_block_disappears_with_another_inflow_model(self):
        """The canonical case for HIDING: with Glauert selected, the
        Pitt-Peters parameters have no meaning at all -- there is no
        value the user could usefully read or set. Showing them disabled
        would be four rows of noise on every configuration that does not
        use them."""
        config = self._tab("Config")
        combo = config.cfg_inflow_family
        index = combo.findText("pitt_peters")
        self.assertGreaterEqual(index, 0, "the pitt_peters family is not offered")

        combo.setCurrentIndex(index)
        self.app.processEvents()
        self.assertTrue(config.pitt_peters_box.isVisibleTo(config),
                        "the Pitt-Peters block did not appear for its own model")

        glauert = combo.findText("glauert")
        self.assertGreaterEqual(glauert, 0, "the glauert family is not offered")
        combo.setCurrentIndex(glauert)
        self.app.processEvents()
        self.assertFalse(config.pitt_peters_box.isVisibleTo(config),
                         "the Pitt-Peters block stayed on screen under Glauert")

    def test_an_option_blocked_by_the_mode_stays_disabled_and_does_not_vanish(self):
        """The canonical case for HIDING: with Glauert selected, the
        Pitt-Peters parameters have no meaning at all -- there is no
        value the user could usefully read or set. Showing them disabled
        would be four rows of noise on every configuration that does not
        use them."""
        config = self._tab("Config")
        combo = config.cfg_inflow_family
        index = combo.findText("pitt_peters")
        self.assertGreaterEqual(index, 0, "the pitt_peters family is not offered")

        combo.setCurrentIndex(index)
        self.app.processEvents()
        self.assertTrue(config.pitt_peters_box.isVisibleTo(config),
                        "the Pitt-Peters block did not appear for its own model")

        glauert = combo.findText("glauert")
        self.assertGreaterEqual(glauert, 0, "the glauert family is not offered")
        combo.setCurrentIndex(glauert)
        self.app.processEvents()
        self.assertFalse(config.pitt_peters_box.isVisibleTo(config),
                         "the Pitt-Peters block stayed on screen under Glauert")

    def test_uma_opcao_bloqueada_pelo_modo_fica_desabilitada_e_nao_some(self):
        """The canonical case for DISABLING. `viterna_full_range` needs a
        polar extended to the full circle, which the current airfoil
        source may not produce -- so it must not be selectable. But it
        must stay in the list: removed, the user has no way to learn that
        the model exists, nor that the airfoil source is what blocks it.

        This is the defect PR-2 names. The option used to be deleted from
        the dropdown, leaving a note underneath as the only evidence that
        there was anything to look for."""
        airfoil = self._tab("Airfoil")
        combo = airfoil.cfg_reverse_flow_model
        labels = [combo.itemText(i) for i in range(combo.count())]
        self.assertIn(
            "viterna_full_range", labels,
            "an option unavailable in the current configuration was removed "
            "from the list instead of being disabled")

    def test_the_blocked_option_is_in_fact_disabled(self):
        """Present is only half of it. Listed and still selectable, the
        user picks a model the airfoil cannot feed and the run fails
        later, with the cause several steps behind."""
        airfoil = self._tab("Airfoil")
        combo = airfoil.cfg_reverse_flow_model
        index = combo.findText("viterna_full_range")
        self.assertGreaterEqual(index, 0)
        item = combo.model().item(index)
        self.assertIsNotNone(item, "the combo does not use an item model")

        # The default project's airfoil does not extend to the full range.
        self.assertFalse(airfoil._airfoil_extend_full_range(),
                         "this test needs a starting state where the option is blocked")
        self.assertFalse(item.isEnabled(),
                         "the unavailable option is offered as selectable")

        # Turning the extension on must unlock it, in the same list.
        airfoil.stall_model_combo.setCurrentText("viterna")
        self.app.processEvents()
        index = combo.findText("viterna_full_range")
        self.assertTrue(combo.model().item(index).isEnabled(),
                        "the option stayed blocked after the extension was enabled")

    def test_no_combo_stays_visible_and_empty(self):
        """A visible dropdown with nothing in it is the worst of both: it
        announces a choice and offers none. Either it has options or it
        should not be on screen."""
        empty = []
        for combo in self.window.findChildren(QComboBox):
            if combo.isVisibleTo(self.window) and combo.count() == 0:
                empty.append(combo.objectName() or combo.toolTip()[:50] or "(unnamed)")
        self.assertEqual(empty, [], "visible combo with no options: " + str(empty))


if __name__ == "__main__":
    unittest.main()
