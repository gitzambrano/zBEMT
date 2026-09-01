"""The Run Batch queue: typing into it, and saving it (`PR-11`, `PA-4`).

Two defects met the user on the same tab, and both are pinned here.

The first closed the application. `parse_list` ran on `textChanged`, so
it saw every number in every half-typed state it passes through, and it
called `float()` on each one. A list of disk angles normally starts with
a minus sign; `float("-")` raises inside a Qt slot, and PyQt6 aborts the
process rather than propagate it. "The window closed while I typed the
first alpha" was a `ValueError` two keystrokes deep.

The second changed the data. The queue table shows five of the ten
fields of a `FlightCondition` and used to REBUILD the condition from
those five cells, so saving a queue under a name rounded the three it
showed, turned an absent RPM into an RPM of zero, and reset the cyclic
pitch, the sideslip and both hub rates to their defaults -- seven of ten
fields, with no message.
"""
import unittest

from tests.helpers import HAS_QT as _HAS_QT, patch_message_box_everywhere

if not _HAS_QT:                                  # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from PyQt6.QtWidgets import QApplication, QTableWidgetItem

from zbemt.gui.common import parse_list, parse_list_reporting
from zbemt.models import BatchDefinition, FlightCondition


class TestParseListNeverRaises(unittest.TestCase):
    """`PR-11`. Every one of these is a state a number passes THROUGH
    while it is being typed, so none of them may raise."""

    HALF_TYPED = ["-", "+", ".", "0.", "-0.", "1e", "1e-", "1e+", "-,", "e"]

    def test_no_half_typed_number_raises(self):
        for text in self.HALF_TYPED:
            with self.subTest(text=text):
                parse_list(text)          # must simply not raise

    def test_the_minus_sign_of_the_first_alpha(self):
        """The exact keystroke sequence of "-5, -2, 0"."""
        typed = ""
        for char in "-5, -2, 0":
            typed += char
            parse_list(typed)
        self.assertEqual(parse_list(typed), [-5.0, -2.0, 0.0])

    def test_a_readable_value_is_still_read(self):
        self.assertEqual(parse_list("0.1, 0.2, 0.3"), [0.1, 0.2, 0.3])

    def test_what_it_could_not_read_is_reported_not_hidden(self):
        """Tolerance on the live path must not become silence on the
        path that BUILDS a batch: a queue quietly missing a case the
        user wrote is worse than a refusal."""
        values, rejected = parse_list_reporting("1, x, 3")
        self.assertEqual(values, [1.0, 3.0])
        self.assertEqual(rejected, ["x"])


#: The one main window of this module, built on first use.
#:
#: `setUpClass` runs once per CLASS, so building it there gives one
#: window per subclass -- four, each with seven tabs and four tool
#: windows. Closing them again was not enough: the process hung at the
#: end of the file, which is the Qt teardown problem `CLAUDE.md` already
#: describes for the suite as a whole. One window, never closed, and the
#: runner's one-process-per-file rule keeps it from outliving the file.
_WINDOW = None
_TAB = None


def _shared_window():
    global _WINDOW, _TAB
    if _WINDOW is None:
        from zbemt.gui.app import MainWindow
        from zbemt.gui.tabs import RunBatchTab

        _WINDOW = MainWindow()
        for i in range(_WINDOW.tabs.count()):
            widget = _WINDOW.tabs.widget(i)
            if isinstance(widget, RunBatchTab):
                _TAB = widget
        assert _TAB is not None, "the Run Batch tab was not found"
    return _WINDOW, _TAB


class RunBatchBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        cls.window, cls.tab = _shared_window()

    def setUp(self):
        from zbemt import api

        # No dialog may open. Under the offscreen platform a modal box
        # has nobody to dismiss it, so a test that reaches one does not
        # fail -- it hangs, and the whole suite reports nothing.
        box = patch_message_box_everywhere()
        self.message_box = box.__enter__()
        self.addCleanup(box.__exit__, None, None, None)

        self.window.state.set_project(api.open_project("projects/starter_rotor"))
        self.tab._fill_queue([], replace=True)
        self.tab._refresh_saved_batches_combo()

    #: A condition using every field the table does NOT show, plus values
    #: with more figures than the cells are formatted with.
    RICH = FlightCondition(name="rich", mu_x=0.123456, collective_deg=7.891234,
                            Vz=-12.3456, rpm=None, cyclic_c_deg=1.5,
                            cyclic_s_deg=-0.75, sideslip_deg=20.0,
                            p_rate_deg_s=2.5, q_rate_deg_s=3.0)


class TestTheQueueKeepsWhatItWasGiven(RunBatchBase):

    def test_a_round_trip_through_the_table_changes_nothing(self):
        self.tab._fill_queue([self.RICH], replace=True)
        back = self.tab._queue_conditions()
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0], self.RICH)

    def test_an_absent_rpm_stays_absent(self):
        """`rpm=None` means "use the speed the configuration carries".
        Written into the cell as "0" it read back as a rotor commanded
        to stand still."""
        self.tab._fill_queue([self.RICH], replace=True)
        self.assertIsNone(self.tab._queue_conditions()[0].rpm)

    def test_the_fields_the_table_does_not_show_survive(self):
        self.tab._fill_queue([self.RICH], replace=True)
        got = self.tab._queue_conditions()[0]
        for field in ("cyclic_c_deg", "cyclic_s_deg", "sideslip_deg",
                      "p_rate_deg_s", "q_rate_deg_s"):
            with self.subTest(field=field):
                self.assertAlmostEqual(getattr(got, field),
                                       getattr(self.RICH, field), places=12)

    def test_full_precision_survives_its_own_rounded_display(self):
        self.tab._fill_queue([self.RICH], replace=True)
        got = self.tab._queue_conditions()[0]
        self.assertAlmostEqual(got.mu_x, 0.123456, places=12)
        self.assertAlmostEqual(got.Vz, -12.3456, places=12)
        self.assertAlmostEqual(got.collective_deg, 7.891234, places=12)

    def test_an_edit_the_user_really_makes_is_taken(self):
        """The stored condition is a starting point, not a lock."""
        self.tab._fill_queue([self.RICH], replace=True)
        self.tab.batch_table.setItem(0, self.tab._COL_MU,
                                      QTableWidgetItem("0.42"))
        got = self.tab._queue_conditions()[0]
        self.assertAlmostEqual(got.mu_x, 0.42, places=12)
        # ...and it changes only what was edited
        self.assertAlmostEqual(got.sideslip_deg, 20.0, places=12)
        self.assertAlmostEqual(got.Vz, -12.3456, places=12)

    def test_an_unreadable_cell_is_reported_instead_of_crashing(self):
        self.tab._fill_queue([self.RICH], replace=True)
        self.tab.batch_table.setItem(0, self.tab._COL_MU,
                                      QTableWidgetItem("abc"))
        conditions, rejected = self.tab._queue_conditions_and_rejects()
        self.assertTrue(rejected, "an unreadable cell must be named")
        self.assertAlmostEqual(conditions[0].mu_x, self.RICH.mu_x, places=12)

    def test_removing_a_row_does_not_disturb_the_others(self):
        second = FlightCondition(name="b", mu_x=0.3, sideslip_deg=11.0,
                                  rpm=600.0)
        self.tab._fill_queue([self.RICH, second], replace=True)
        self.tab.batch_table.removeRow(0)
        self.tab._renumber()
        got = self.tab._queue_conditions()
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0].sideslip_deg, 11.0, places=12)


class TestSavingAQueueDoesNotChangeIt(RunBatchBase):

    def _save(self, name):
        """`_save_current_as_batch` without its input dialog."""
        conditions, rejected = self.tab._queue_conditions_and_rejects()
        self.assertEqual(rejected, [])
        self.window.state.project.batches.append(
            BatchDefinition(name=name, conditions=conditions))
        self.window.state.notify_config()
        self.tab._refresh_saved_batches_combo()
        self.tab.batches_combo.blockSignals(True)
        self.tab.batches_combo.setCurrentText(name)
        self.tab.batches_combo.blockSignals(False)

    def test_the_queue_on_screen_is_unchanged_by_saving_it(self):
        self.tab._fill_queue([self.RICH], replace=True)
        before = self.tab._queue_conditions()
        self._save("meu conjunto")
        self.assertEqual(self.tab._queue_conditions(), before)

    def test_what_was_stored_is_what_was_shown(self):
        self.tab._fill_queue([self.RICH], replace=True)
        self._save("meu conjunto")
        stored = self.window.state.project.batches[-1].conditions
        self.assertEqual(stored, [self.RICH])

    def test_loading_it_back_returns_the_same_conditions(self):
        """`PA-4`: the batch is savable AND loadable, and the pair is the
        identity."""
        self.tab._fill_queue([self.RICH], replace=True)
        self._save("meu conjunto")
        self.tab._fill_queue([], replace=True)
        self.assertEqual(self.tab.batch_table.rowCount(), 0)
        index = self.tab.batches_combo.findText("meu conjunto")
        self.assertGreater(index, 0, "the saved batch is not in the list")
        self.tab.batches_combo.setCurrentIndex(index)
        self.tab._load_selected_batch()
        self.assertEqual(self.tab._queue_conditions(), [self.RICH])


class TestTheLoadButtonExists(RunBatchBase):
    """The batch WAS loadable -- by changing the combo -- but nothing on
    screen said so, and the combo cannot reload the entry it already
    shows."""

    def test_there_is_a_load_button(self):
        from PyQt6.QtWidgets import QPushButton

        labels = [b.text().lower() for b in self.tab.findChildren(QPushButton)]
        self.assertIn("load", labels)

    def test_it_reloads_the_entry_already_selected(self):
        self.tab._fill_queue([self.RICH], replace=True)
        conditions = self.tab._queue_conditions()
        self.window.state.project.batches.append(
            BatchDefinition(name="again", conditions=conditions))
        self.tab._refresh_saved_batches_combo()
        index = self.tab.batches_combo.findText("again")
        self.tab.batches_combo.setCurrentIndex(index)
        # Edit the queue, then reload the SAME name to discard the edit.
        self.tab.batch_table.setItem(0, self.tab._COL_MU,
                                      QTableWidgetItem("0.99"))
        self.assertAlmostEqual(self.tab._queue_conditions()[0].mu_x, 0.99)
        self.tab._load_selected_batch()
        self.assertAlmostEqual(self.tab._queue_conditions()[0].mu_x,
                               self.RICH.mu_x, places=12)



def tearDownModule():
    """Hand the shared windows back to QT while it can still take them.

    `hide()` then `deleteLater()` is the pattern the other GUI test
    files use. Left to the interpreter instead, the last reference was
    dropped in an order Qt does not control and the process exited with
    a native access violation on roughly half the runs -- with every
    test having PASSED, which is the worst way for a suite to fail.
    """
    global _WINDOW, _TAB
    for window in (_WINDOW,):
        if window is not None:
            window.hide()
            window.deleteLater()
    _WINDOW, _TAB = None, None
    app = QApplication.instance()
    if app is not None:
        app.processEvents()

if __name__ == "__main__":   # pragma: no cover
    unittest.main()
