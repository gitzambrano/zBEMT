"""
test_gui_layout.py
==================

LAYOUT defects that only appear with the window actually mounted --
none of them break a logic test, and all of them were seen on screen
before becoming a test here.

Deliberately does NOT check style pixels (exact width, color, font):
that ages badly and blocks the next redesign (CLAUDE.md, rule 3). What
is checked here is the *structural invariant*:

  * orphan label -- visible label whose field was hidden;
  * stretched field -- numeric/enum input stretched to the end of the
    form row (the ~1370px box to type "72");
  * mute field -- value widget without a tooltip, which as a
    consequence also does not get a clickable help label (`field_help`
    derives one from the other).
"""
from __future__ import annotations

import unittest

try:
    from PyQt6.QtWidgets import (
        QApplication, QAbstractSpinBox, QComboBox, QFormLayout, QGroupBox,
        QLabel, QLineEdit, QPlainTextEdit, QScrollArea, QStackedWidget,
        QTabWidget, QTextEdit, QToolButton,
    )
    _HAS_QT = True
except Exception:                                    # pragma: no cover
    _HAS_QT = False

if _HAS_QT:
    from zbemt.gui import styles

    #: Every widget through which the user enters a VALUE. The tooltip
    #: sweep uses this list instead of walking `QFormLayout`: seven real
    #: fields escaped the previous version by being text fields or by
    #: living in a `QHBoxLayout`.
    VALUE_FIELD_TYPES = (QAbstractSpinBox, QComboBox, QLineEdit,
                         QPlainTextEdit, QTextEdit)

    #: Where the search for "container that explains the field" must stop.
    SCREEN_GROUPERS = (QGroupBox, QScrollArea, QStackedWidget, QTabWidget)


WINDOW_WIDTH = 1400

#: Fields whose content is free text of unpredictable size: stretching is
#: the right behavior there (folder path, list "0, 0.1, 0.2").
#: `compact_form_fields` does not touch them, and neither does
#: this test.


def _is_editable_field(w) -> bool:
    """Discards what is not really an input field.

    An editable `QComboBox` and a `QAbstractSpinBox` contain an internal
    `QLineEdit` that the sweep would find as an independent field; and a
    read-only field is not where anything gets entered.
    """
    if isinstance(w, QLineEdit):
        if w.isReadOnly():
            return False
        parent = w.parentWidget()
        if isinstance(parent, (QComboBox, QAbstractSpinBox)):
            return False
    if isinstance(w, (QPlainTextEdit, QTextEdit)) and w.isReadOnly():
        return False
    return True


def _has_explanation(w, root) -> bool:
    """The widget explains itself, either on its own or via the container
    that composes it.

    A compound field (`widgets.LongitudinalInput`: unit dropdown +
    spinbox) is ONE field from the user's and `field_help`'s point of
    view -- the tooltip lives on the container, and requiring it from
    every internal piece would mean requiring the same sentence three
    times.
    """
    if (w.toolTip() or "").strip():
        return True
    current = w.parentWidget()
    # The climb stops at the first SCREEN grouper: a tooltip on the
    # `QGroupBox` explains the block, not each field inside it, and
    # accepting it here would let an entire block of mute fields pass.
    while (current is not None and current is not root
           and not isinstance(current, SCREEN_GROUPERS)):
        if (current.toolTip() or "").strip():
            return True
        current = current.parentWidget()
    return False


def _describe_field(w) -> str:
    """Identifies the field in the failure message (label, name or class)."""
    for attribute in ("placeholderText", "currentText", "objectName"):
        value = getattr(w, attribute, None)
        text = (value() if callable(value) else value) or ""
        if text:
            return f"{type(w).__name__} {text!r}"
    return f"{type(w).__name__} without a label"


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestMountedWindowLayout(unittest.TestCase):
    """Mounts the real `MainWindow` (not loose tabs): the width and field
    help adjustments are applied from OUTSIDE, by the window, so a tab
    instantiated alone would not have them and the test would pass by
    mistake."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(styles.APP_QSS)

        from zbemt.gui.app import MainWindow
        cls.win = MainWindow()
        cls.win.resize(WINDOW_WIDTH, 900)
        cls.win.show()
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def _tabs(self):
        """Each tab with it ACTIVE in the `QTabWidget`.

        `QWidget.isVisible()` is false for everything in a tab that is not
        selected -- iterating the tabs without switching the current one
        makes every visibility test here pass vacuously (observed: the
        previous version of this file passed with the orphan-label bug
        deliberately reintroduced). Switching the tab is what gives the
        widgets real geometry and visibility.
        """
        for i in range(self.win.tabs.count()):
            self.win.tabs.setCurrentIndex(i)
            self.app.processEvents()
            yield self.win.tabs.tabText(i), self.win.tabs.widget(i)

    def test_no_label_is_orphaned_from_its_own_field(self):
        """Real bug: in "Run Batch" > "3. Run", the "Entered values" mode
        hid the trim fields with `setVisible(False)` -- which hides only
        the FIELD. "Trim variable:" and "Target:" stayed on screen
        pointing at nothing. `common.set_row_visible` exists exactly
        for this and was not being used there."""
        orphans = []
        for tab_name, tab in self._tabs():
            for form in tab.findChildren(QFormLayout):
                for row in range(form.rowCount()):
                    item_label = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                    item_field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                    if item_label is None or item_field is None:
                        continue
                    label = item_label.widget()
                    field = item_field.widget()
                    if label is None or field is None:
                        continue
                    if label.isVisible() and not field.isVisible():
                        text = label.text() if hasattr(label, "text") else "?"
                        orphans.append(f"{tab_name}: {text!r}")
        self.assertEqual(
            orphans, [],
            "visible label with hidden field -- use "
            "`common.set_row_visible`, not `setVisible`: " + str(orphans))

    def test_no_numeric_or_enum_field_becomes_a_strip(self):
        """A `QFormLayout` stretches the field to the end of the row; in a
        1400px window this gave a ~1370px box to type "72", and the same
        quantity came out with a different width in each tab.
        `common.compact_form_fields` sets a ceiling by content
        TYPE -- number, enum -- and it is that ceiling this test
        protects."""
        from zbemt.gui.common import NUMBER_WIDTH, ENUM_MAX_WIDTH

        stretched = []
        for tab_name, tab in self._tabs():
            for w in tab.findChildren(QAbstractSpinBox):
                if w.isVisible() and w.width() > max(NUMBER_WIDTH,
                                                      w.minimumSizeHint().width()):
                    stretched.append(f"{tab_name}: number field {w.width()}px")
            for w in tab.findChildren(QComboBox):
                # Deliberate exemption (vertical-alignment rule): a combo
                # flagged `_form_width_stretch` shares the column edges of
                # the free-text editors around it (the Airfoil Source
                # dropdowns). There the strip look is the POINT -- the user
                # reported the short combo as the defect -- so the enum
                # heuristic stands down, exactly like
                # `common.compact_form_fields` already does.
                if w.property("_form_width_stretch"):
                    continue
                # The floor is the minimum the combo itself requests: a
                # combo whose longest option does not fit in
                # `ENUM_MAX_WIDTH` asks for more (see
                # `dialogs.adjust_combo_width`), and squeezing it
                # would elide the option with "…" -- the generic ceiling
                # cannot override that concrete need. What this test
                # forbids is the field stretched BEYOND what it needs,
                # which is the real defect (a 1370px box to type "72").
                ceiling = max(ENUM_MAX_WIDTH, w.minimumWidth(),
                              w.minimumSizeHint().width())
                if w.isVisible() and w.width() > ceiling:
                    stretched.append(f"{tab_name}: enum at {w.width()}px "
                                     f"({w.currentText()!r})")
        self.assertEqual(stretched, [], "field stretched to the end of the row: "
                                        + str(stretched))

    def test_no_visible_block_is_squeezed_below_its_own_minimum(self):
        """Real bug: "Run Batch" was the only tab without a
        `QScrollArea`. The four stacked steps add up to more height than
        the window, and Qt squeezed the "1. Generate cases" box 89px
        below its own `minimumSizeHint` -- the four "Fixed values" rows
        were flattened to ~14px, with the label text cut off in the
        middle and the spinboxes reduced to a horizontal dash.

        A widget smaller than its own minimum is always a defect: it
        means the content is being cut off, not reorganized. The correct
        answer is to scroll, not to shrink.
        """
        from PyQt6.QtWidgets import QGroupBox

        squeezed_blocks = []
        for tab_name, tab in self._tabs():
            for gb in tab.findChildren(QGroupBox):
                if not gb.isVisible():
                    continue
                min_height = gb.minimumSizeHint().height()
                # 2px tolerance: rounding of border/margin from the QSS.
                if min_height > 0 and gb.height() < min_height - 2:
                    squeezed_blocks.append(
                        f"{tab_name}: {gb.title()!r} at {gb.height()}px, "
                        f"needs {min_height}px")
        self.assertEqual(squeezed_blocks, [],
                          "block squeezed below the minimum: " + str(squeezed_blocks))

    def test_every_visible_value_field_has_a_tooltip(self):
        """Without a tooltip the field is mute on two levels: it does not
        explain itself on hover AND does not get a clickable help label --
        `field_help` extracts the field NAME from the tooltip itself, so a
        missing tooltip silently drops the help popup too.

        The sweep also covers `QLineEdit`/`QPlainTextEdit` and widgets
        OUTSIDE `QFormLayout`: seven fields escaped the previous version
        of this test precisely because they were text fields ("Project
        Name", "NACA code", "CST upper/lower", "Bézier") or because they
        lived in a `QHBoxLayout` ("Field", in the Results tab).
        """
        mute = []
        for tab_name, tab in self._tabs():
            for w in tab.findChildren(VALUE_FIELD_TYPES):
                # No visibility filter: a field revealed only when "cst"
                # is chosen still needs a tooltip, and five of the mute
                # fields found on screen were exactly in these
                # progressive-reveal blocks.
                if not _is_editable_field(w) or _has_explanation(w, tab):
                    continue
                mute.append(f"{tab_name}: {_describe_field(w)}")
        self.assertEqual(mute, [], "value field without a tooltip: " + str(mute))

    def test_tooltip_names_the_field_in_the_format_the_help_expects(self):
        """`field_help._widget_field` reads the field name from the
        FIRST quoted token of the tooltip (`"n_blades" — ...`). A tooltip
        that does not start like that is loose text: the field has no way
        to resolve the documentation anchor, and the clickable label is
        never born.

        Not every value widget corresponds to a `.bemt` field (there are
        display-only controls), so what is required here is the converse:
        if the tooltip names a field, that name has to actually exist --
        either as a field persisted in the project dataclasses, as an
        API execution parameter (trim, for example, is not saved in the
        `.bemt`: it is an argument of `api.run_case_trimmed`), or as one
        of the GUI-only controls with a defined contract (the geometry
        spec string resolves through the same entry point as the CLI's
        `--airfoil-geometry`)."""
        import inspect

        from zbemt import api
        from zbemt.bemt import BEMTConfig
        from zbemt.gui.field_help import _widget_field
        from zbemt.models import (AirfoilDef, BatchDefinition, FlightCondition,
                                  OptimizationDefinition, DesignVariable,
                                  ProfileGeometry, Project, RotorGeometryDef)

        known: set = set(inspect.signature(
            api.run_case_trimmed).parameters)
        for cls in (BEMTConfig, AirfoilDef, RotorGeometryDef, FlightCondition,
                    BatchDefinition, ProfileGeometry, Project,
                    OptimizationDefinition, DesignVariable):
            known |= set(cls.__dataclass_fields__)
        # GUI-only controls: not persisted under these names, but real
        # contracts documented in FIELD_HELP and in the manual.
        known |= {"geometry_spec"}

        invented = []
        for tab_name, tab in self._tabs():
            for w in tab.findChildren(VALUE_FIELD_TYPES):
                field = _widget_field(w)
                if field is not None and field not in known:
                    invented.append(f"{tab_name}: {field!r}")
        self.assertEqual(invented, [],
                         "tooltip names a nonexistent field: " + str(invented))

    def test_no_button_stretches_much_beyond_its_own_text(self):
        """In a `QHBoxLayout` without a trailing stretch, the buttons absorb
        all the row's slack: "- Remove" (80px of text) measured 550px, the
        width ceiling of the stylesheet, and the whole row turned into a
        bar of giant buttons.

        `setSizePolicy(Fixed)` does NOT fix it -- with the QSS applied the
        button grows up to `max-width` even with Fixed policy (measured on
        the mounted window). What fixes it is `addStretch(1)` at the end of
        the row, and that is what this test protects.

        Full-row action buttons (a `Run Case` that occupies the row for
        that purpose) are excluded: they are not on a row WITH other
        widgets, which is where the defect shows up.
        """
        from PyQt6.QtWidgets import QHBoxLayout, QPushButton

        stretched = []
        for tab_name, tab in self._tabs():
            for row in tab.findChildren(QHBoxLayout):
                buttons = [row.itemAt(i).widget() for i in range(row.count())]
                buttons = [b for b in buttons
                           if isinstance(b, QPushButton) and b.isVisible()]
                if len(buttons) < 2:
                    continue
                for b in buttons:
                    # GROUP width is deliberate, not layout slack: the
                    # four Run Batch action buttons share the width of the
                    # longest label by explicit request, and "Clear" is
                    # wide for its own text because of that (see
                    # `RunBatchTab._equalize_action_buttons`).
                    if getattr(b, "_group_width", None) is not None:
                        continue
                    slack = b.width() - b.sizeHint().width()
                    if slack > 40:
                        stretched.append(
                            f"{tab_name}: {b.text()!r} at {b.width()}px "
                            f"for {b.sizeHint().width()}px of content")
        self.assertEqual(stretched, [],
                          "button stretched by the row's slack -- missing a "
                          "trailing `addStretch(1)`: " + str(stretched))

    def test_every_help_block_reaches_a_real_groupbox(self):
        """`app._BLOCKS` matches the groupbox TITLE as a string. A renamed
        title (several were, in this very session) leaves the entry
        orphaned and that block's help vanishes with no error at all --
        it just disappears.

        The check runs both ways: no `BLOCK_HELP` entry is left without a
        groupbox, and no visible groupbox is left without a clickable
        title.
        """
        from PyQt6.QtWidgets import QGroupBox

        from zbemt.gui.common import _ClickableBlockTitle
        from zbemt.gui.help_blocks import BLOCK_HELP

        reached: set = set()
        mute: list = []
        # The Geometry Designer is a separate top-level window parented
        # to the main one; its groupboxes carry block titles through the
        # same map and belong in this check.
        roots = [(name, tab) for name, tab in self._tabs()]
        roots.append(("Geometry Designer", self.win.geometry_designer))
        for source_name, root in roots:
            for gb in root.findChildren(QGroupBox):
                clickable = next((c for c in gb.children()
                                  if isinstance(c, _ClickableBlockTitle)), None)
                if clickable is None:
                    mute.append(f"{source_name}: {gb.title()!r}")
                else:
                    reached.add(clickable._block_id)

        self.assertEqual(mute, [],
                         "groupbox without block help: " + str(mute))
        # Retired with the Design tab (product decision): optimization
        # runs from the CLI/library only, so no groupbox carries this
        # block anymore. Drop the entry from BLOCK_HELP when the
        # documentation pass rewrites the design-tools chapter.
        RETIRED_BLOCKS = {"design_optimization"}
        self.assertEqual(sorted(set(BLOCK_HELP) - reached - RETIRED_BLOCKS),
                         [],
                         "BLOCK_HELP entry that no groupbox reaches "
                         "-- title renamed without updating `app._BLOCOS`")

    def test_every_field_with_a_tooltip_gained_a_clickable_help_label(self):
        """The tooltip names the field (`"n_blades" — ...`) and it is from
        that name that `field_help.install_field_popups` derives the
        clickable label. A field that HAS the name in the tooltip but did
        not become a clickable label means the help never reached it --
        the user is left without the popup and without the link to the
        full documentation."""
        from zbemt.gui.field_help import _widget_field, field_anchor
        from zbemt.gui import help_content

        without_help = []
        for tab_name, tab in self._tabs():
            for form in tab.findChildren(QFormLayout):
                for row in range(form.rowCount()):
                    item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                    item_label = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                    if item is None or item_label is None:
                        continue
                    w, label = item.widget(), item_label.widget()
                    if w is None or label is None or not w.isVisible():
                        continue
                    field = _widget_field(w)
                    if field is None:
                        continue
                    documented = (field in help_content.FIELD_HELP
                                  or field_anchor(field) is not None)
                    if documented and not isinstance(label, QToolButton):
                        without_help.append(f"{tab_name}: {field!r}")
        self.assertEqual(without_help, [],
                         "documented field without a clickable label: " + str(without_help))

    def test_no_unit_combo_elides_its_own_option(self):
        """Real bug: "alpha [deg]" came out cut off ("alpha [deg") in the
        condition combos of Run Case and Run Batch, which had a fixed
        110px.

        This is not a pixel assertion (rule 3): the floor is the widget's
        own FONT METRIC, so it keeps holding if the font, the theme, or
        the language changes."""
        from zbemt.gui.widgets import LongitudinalInput, AxialInput

        clipped = []
        for tab_name, tab in self._tabs():
            for field in tab.findChildren((LongitudinalInput, AxialInput)):
                combo = field.unit_combo
                if not combo.isVisible():
                    continue
                fm = combo.fontMetrics()
                longest = max((combo.itemText(i) for i in range(combo.count())),
                              key=fm.horizontalAdvance, default="")
                # the dropdown arrow eats ~22px (styles.py) + padding
                if combo.width() < fm.horizontalAdvance(longest) + 24:
                    clipped.append(f"{tab_name}: {longest!r} at {combo.width()}px")
        self.assertEqual(clipped, [], "unit combo elided: " + str(clipped))

    def test_condition_fields_start_in_the_same_column(self):
        """Run Case and Run Batch put the NUMBER of every condition row in
        the same column -- the compound rows (mu_x/J_x, alpha/Vz) have a
        combo-label before the number, and the simple ones (Collective,
        RPM) are indented up to that point by `_with_unit_indent`.
        Different widths between the two tabs misaligned the column
        within each one."""
        from zbemt.gui.widgets import LongitudinalInput, AxialInput

        for tab_name, tab in self._tabs():
            if tab_name.replace("*", "").strip() not in ("Run Case", "Run Batch"):
                continue
            widths = {c.unit_combo.width()
                      for c in tab.findChildren((LongitudinalInput, AxialInput))
                      if c.unit_combo.isVisible()}
            with self.subTest(tab=tab_name):
                self.assertLessEqual(len(widths), 1,
                                      f"{tab_name}: unit combos with widths {widths}")

    def test_neighboring_boxes_do_not_stick_to_each_other(self):
        """Real bug: in Run Batch > export, the "Coefficients" label
        touched the "Azimuthal loads" checkbox -- four checkboxes on one
        row with the style's default spacing read as a single block, and
        the eye cannot tell which box each word belongs to."""
        from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QRadioButton
        from zbemt.gui.common import MIN_CHECKBOX_SPACING

        stuck = []
        for tab_name, tab in self._tabs():
            for row in tab.findChildren(QHBoxLayout):
                boxes = [row.itemAt(i).widget() for i in range(row.count())
                         if isinstance(row.itemAt(i).widget(), (QCheckBox, QRadioButton))]
                boxes = [c for c in boxes if c.isVisible()]
                for left, right in zip(boxes, boxes[1:]):
                    gap = (right.mapTo(tab, right.rect().topLeft()).x()
                           - (left.mapTo(tab, left.rect().topLeft()).x()
                              + left.width()))
                    if gap < MIN_CHECKBOX_SPACING:
                        stuck.append(
                            f"{tab_name}: {left.text()!r} and {right.text()!r} "
                            f"{gap}px apart")
        self.assertEqual(stuck, [], "adjacent checkboxes stuck together: " + str(stuck))

    def test_factorial_axis_rows_start_in_the_same_column(self):
        """The three factorial axes have a unit combo with a different
        NATURAL width ("mu_x" versus "alpha [deg]"), and the disabled
        axis has no combo at all -- each row started the "values:" field
        at a different x. The column is reserved across all three."""
        tab = None
        for tab_name, widget in self._tabs():
            if tab_name.replace("*", "").strip() == "Run Batch":
                tab = widget
        self.assertIsNotNone(tab, "Run Batch tab not found")

        # one longitudinal axis, one axial, and one disabled: the case
        # where the three natural widths are different
        for index, wanted_slot in ((0, "inplane"), (1, "axial")):
            combo = tab.axis_rows[index][0]
            combo.setCurrentIndex(next(i for i, (_r, s) in enumerate(tab._AXIS_SLOTS)
                                       if s == wanted_slot))
        self.app.processEvents()

        xs = {edit.mapTo(tab, edit.rect().topLeft()).x()
              for _slot, _unit, edit in tab.axis_rows}
        self.assertEqual(len(xs), 1,
                          f"'values:' fields starting at different x: {sorted(xs)}")

    def test_the_options_row_shrinks_for_the_current_mode(self):
        """Real bug: the control strip above the Results tab's plot
        reserved the height of the TALLEST panel (the "3D" mode's) in
        every mode -- 216px measured, with a blank gap of more than a
        hundred pixels above the disk maps, which ended up squeezed
        beneath it.

        What is measured is the RATIO, not the pixel (rule 3): a mode
        with few controls must leave more screen for the plot than a
        mode with many."""
        tab = None
        for tab_name, widget in self._tabs():
            if tab_name.replace("*", "").strip() == "Results":
                tab = widget
        self.assertIsNotNone(tab, "Results tab not found")

        def plot_height(mode: str) -> int:
            rows = [i for i in range(tab.mode_list.count())
                    if tab.mode_list.item(i).text() == mode]
            self.assertTrue(rows, f"mode {mode!r} does not exist in the list")
            tab.mode_list.setCurrentRow(rows[0])
            self.app.processEvents()
            self.app.processEvents()
            return tab.canvas_stack.height()

        thin = plot_height("Convergence")   # panel practically empty
        tall = plot_height("3D")            # the tallest panel in the tab
        self.assertGreater(
            thin, tall,
            "the options row did not shrink: the plot has the same height in a "
            "mode without controls and in the mode with most of them")

    def test_a_checkbox_row_does_not_stick_to_the_next_row(self):
        """Real bug: "Enable dynamic stall (Øye)" touched "Lag
        constant A:", and the three rows of "3D rotational effects" read
        as a single block. The policy lives in the `common` module
        (`ensure_row_spacing`), applied by the window -- what is checked
        here is that it reached EVERY form."""
        from zbemt.gui.common import MIN_ROW_SPACING

        cramped = []
        for tab_name, tab in self._tabs():
            for form in tab.findChildren(QFormLayout):
                if form.rowCount() < 2:
                    continue
                if form.verticalSpacing() < MIN_ROW_SPACING:
                    cramped.append(f"{tab_name}: {form.verticalSpacing()}px")
        self.assertEqual(cramped, [], "cramped form: " + str(cramped))

    def test_the_seven_top_stages_have_the_same_width(self):
        """"Project" and "Config/Engine" differ by dozens of pixels: seven
        colored pills of different sizes read as seven different things,
        not as seven steps of the same flow."""
        bar = self.win.flow_bar
        bar._equalize_stage_widths()
        widths = {b.width() or b.minimumWidth() for b in bar._buttons}
        self.assertEqual(len(widths), 1, f"different widths: {widths}")

    def test_the_top_stages_stay_centered_in_the_strip(self):
        """Without a fixed height the pill stretches vertically and
        touches both edges of the dark strip -- the colored rectangle
        turns into a bar."""
        bar = self.win.flow_bar
        for btn in bar._buttons:
            with self.subTest(stage=btn.text()):
                self.assertEqual(btn.height(), bar.STAGE_HEIGHT)
        # and margin is left over on top and bottom (the strip is taller
        # than the pill), which is what "centered" means here
        self.assertGreaterEqual(
            bar.height(), bar.STAGE_HEIGHT + 2 * bar.VERTICAL_MARGIN)


if __name__ == "__main__":
    unittest.main()
