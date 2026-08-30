"""Verify the coverage, structure, and anchors of GUI help content.

The tests inspect the HTML documentation and block-help registry, checking that
visible fields and blocks resolve to explanatory content and valid anchors. Inputs
are the repository documentation and help registries; outputs are assertion results.
These tests enforce interface consistency rather than aerodynamic correctness.
"""
import re
import unittest

from zbemt.bemt import REVERSE_FLOW_MODELS as _REVERSE_FLOW_MODELS

from tests.helpers import HAS_QT

# Every class here reads help text out of a `zbemt.gui` module, which needs
# Qt to import -- so without it there is nothing to check, and the CI job
# that installs the base dependencies only (to prove the engine runs without
# Qt) must see this module SKIPPED, not 20 import failures.
if not HAS_QT:                                   # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")


class TestFieldHelpCoverage(unittest.TestCase):
    """Every field with id='ajuda-*' in the HTML has an entry in FIELD_HELP."""

    def setUp(self):
        from zbemt.gui import help_content
        from zbemt import paths
        self.FIELD_HELP = help_content.FIELD_HELP
        path = paths.documentation_path()
        self.html = path.read_text(encoding="utf-8") if path else ""

    def test_required_keys_in_every_entry(self):
        """Each entry in FIELD_HELP has the required keys filled in."""
        # "anchor" is no longer among them: the destination is DERIVED from
        # the document by `field_help.field_anchor`, which finds the
        # section that declares the field. A hand-kept anchor was a second
        # source of truth that went stale the moment a section moved.
        required = {"title", "definition", "unit", "equation", "effect", "range", "options"}
        for field, entry in self.FIELD_HELP.items():
            with self.subTest(field=field):
                missing = required - set(entry)
                self.assertFalse(missing, f"Missing keys in '{field}': {missing}")
                self.assertTrue(entry["title"], f"'{field}': empty title")
                self.assertTrue(entry["definition"], f"'{field}': empty definition")

    def test_html_fields_covered(self):
        """Each ajuda-* field in the HTML has a corresponding entry in FIELD_HELP."""
        if not self.html:
            self.skipTest("documentation.html not found")
        html_fields = re.findall(r'id="ajuda-([\w.]+)"', self.html)
        # excludes header sections (geometry, airfoil, config, execution)
        _HEADERS = {"geometria", "aerofolio", "config", "execucao"}
        html_fields = [c for c in html_fields if c not in _HEADERS]
        for field in html_fields:
            with self.subTest(field=field):
                self.assertIn(field, self.FIELD_HELP,
                              f"Field '{field}' exists in the HTML but not in FIELD_HELP")

    def test_enum_options_present(self):
        """Enum fields have non-empty options, and all keys are strings."""
        expected_enums = {
            "source": {"analytical", "table", "neuralfoil"},
            "stall_model": {"linear", "clip", "enhanced", "viterna"},
            "solver": {"newton", "fixed_point", "bisection", "aitken"},
            "prandtl_loss_mode": {"off", "tip", "root", "both"},
            "inflow_field_model": {
                "glauert_local", "coleman_local", "drees_local", "pitt_peters_steady"
            },
            # The popup explained 3 of the 5 options: anyone who picked
            # 'alpha_blending' or 'thin_plate_blend' in the Airfoil tab's
            # dropdown found nothing about them in the field's help.
            # The list comes from the ENGINE (see `test_ajuda_cobre_os_modelos_do_motor`).
            "reverse_flow_model": set(_REVERSE_FLOW_MODELS),
        }
        for field, expected_options in expected_enums.items():
            with self.subTest(field=field):
                entry = self.FIELD_HELP.get(field)
                self.assertIsNotNone(entry, f"'{field}' missing from FIELD_HELP")
                opts = entry.get("options")
                self.assertIsNotNone(opts, f"'{field}' should have options")
                for opt in expected_options:
                    self.assertIn(opt, opts, f"Option '{opt}' missing from '{field}.options'")

    def test_ajuda_cobre_os_modelos_do_motor(self):
        """The field's help explains EXACTLY the reverse flow models
        that the engine implements -- neither fewer (the popup explained 3
        of 5) nor an extra one that doesn't exist in the code."""
        opcoes = self.FIELD_HELP["reverse_flow_model"]["options"]
        self.assertEqual(set(opcoes), set(_REVERSE_FLOW_MODELS))
        for modelo, texto in opcoes.items():
            with self.subTest(modelo=modelo):
                self.assertGreater(len(texto), 60,
                                    f"'{modelo}': explanation too short to say what it does")

    def test_config_visible_fields_have_action_physics_and_boundary(self):
        """Every visible Config control has actionable help and physics documentation."""
        block = self.html.split("<!-- INDICE-DE-CAMPOS:config -->", 1)[1]
        block = block.split("<!-- /INDICE-DE-CAMPOS:config -->", 1)[0]
        fields = re.findall(r"<code>([^<]+)</code>", block)
        self.assertEqual(len(fields), 26)
        for field in fields:
            with self.subTest(field=field):
                entry = self.FIELD_HELP[field]
                for key in ("definition", "equation", "effect", "range"):
                    self.assertTrue(entry[key], f"{field} without {key} in the popup")

    def test_config_destinations_cover_physics_and_implementation_boundary(self):
        """The critical destinations state what to do, the physics, and the code boundary."""
        from zbemt.gui.field_help import field_anchor

        requirements = {
            "inflow_field_model": ("harmonic", "Pitt-Peters", "does not change the airfoil polar"),
            "prandtl_loss_mode": ("finite", "f_{tip}", "elemental thrust"),
            "use_rotational_augmentation": ("centrifugal", "C_l", "empirical"),
            "use_radial_flow_correction": ("boundary-layer", "U_R", "drag"),
            "use_dynamic_stall": ("separation", "tau", "post-processing"),
            "reverse_flow_model": ("U_t", "flat_plate", "element"),
            "use_compressibility": ("Mach", "Prandtl", "coefficients"),
            "solver": ("residual", "Newton", "relaxation"),
            "max_iter": ("safety", "residual", "convergence"),
            "tol": ("residual", "tol", "element"),
        }
        for field, terms in requirements.items():
            anchor = field_anchor(field)
            # The physics destination and the operational subsection live in
            # the same CHAPTER, but can be separated by long figures and
            # derivations -- so the scope is the whole chapter, delimited by
            # the surrounding `<h2>`s. The previous version used a 40000-byte
            # window starting at the anchor, which sometimes leaked into the
            # next chapter, sometimes cut off its own: adding a paragraph to
            # a section pushed a term outside the window and broke a test
            # that had nothing to do with the edit.
            excerpt = self._chapter_of_anchor(anchor).lower()
            self.assertTrue(excerpt, field)
            for term in terms:
                self.assertIn(term.lower(), excerpt, f"{field}: missing term: {term}")

    def _chapter_of_anchor(self, anchor: str) -> str:
        """Text of the chapter (`<h2>` to `<h2>`) that contains ``anchor``."""
        start = self.html.find(f'id="{anchor}"')
        if start < 0:
            return ""
        bounds = [m.start() for m in re.finditer(r"<h2[ >]", self.html)]
        before = [x for x in bounds if x <= start]
        after = [x for x in bounds if x > start]
        return self.html[before[-1] if before else 0:
                         after[0] if after else len(self.html)]

    def test_anchors_exist_in_html(self):
        """Every anchor referenced in FIELD_HELP exists in the HTML."""
        if not self.html:
            self.skipTest("documentation.html not found")
        for field, dados in self.FIELD_HELP.items():
            anchor = dados.get("anchor")
            if not anchor:
                continue
            with self.subTest(field=field, anchor=anchor):
                self.assertIn(f'id="{anchor}"', self.html,
                              f"Anchor '{anchor}' (from '{field}') not found in the HTML")

    def test_help_opens_the_fields_own_section(self):
        """The help must open the field's OWN section.

        The documentation is one chapter per GUI tab, and a field's section
        carries everything about it: the physics, the mathematics, the
        options and how to set it in the GUI, in `.bemt` and in the CLI.
        So the destination is that section -- not a physics chapter
        somewhere else, and never the generic table at the end.

        This replaces an older rule that required the destination to be a
        physics chapter. That was right while the per-field sections were
        thin and delegated the derivation; now the derivation is in the
        field's section, and jumping onward would take the reader away
        from the explanation.
        """
        from zbemt.gui.field_help import (field_anchor, documentation_sections,
                                          _cites_field, _BEMT_MARK)

        by_anchor = {}
        for s in documentation_sections():
            for a in set(s.aliases) | {s.anchor}:
                by_anchor[a] = s

        for field in self.FIELD_HELP:
            with self.subTest(field=field):
                anchor = field_anchor(field)
                self.assertIsNotNone(anchor, f"{field} has no destination")
                self.assertFalse(anchor.startswith("ajuda-"),
                                 f"{field} falls back to the index table")
                section = by_anchor.get(anchor)
                self.assertIsNotNone(section, f"{field} points at an unknown anchor")
                self.assertTrue(_cites_field(section, field),
                                f"{field} opens a section that does not mention it")
                self.assertIn(_BEMT_MARK, section.body,
                              f"{field} opens a section that does not say how to set it")

        # A loose `<a id=...>` sitting just above a heading starts marking a
        # different section as soon as anything is inserted between them, and
        # nothing about the page looks wrong when it happens. (It did happen:
        # `cap-11`, the mesh, was captured by a section inserted in front of
        # it, and `Ne`/`Npsi` began opening the chord distribution.) This is
        # the lock against that.
        expected = {
            "extend_full_range": "cap-3-2-4",
            "use_dynamic_stall": "cap-3-3-1",
            "dynamic_stall_method": "cap-3-3-2",
            "mask_reverse_flow_plots": "cap-3-4-4",
            "use_compressibility": "cap-3-5",
            "inflow_field_model": "cap-4-2",
            "rho": "cap-4-1-2",
            "a_sound": "cap-4-1-3",
            "chord_norm": "cap-2-3",
            "twist_deg": "cap-2-3",
            "root_cutout_norm": "cap-2-5",
            "rpm": "cap-5-4",
            "collective_deg": "cap-5-3",
            "stall_model": "cap-3-2-2",
            "reverse_flow_model": "cap-3-4-1",
            "is_propeller": "cap-projeto-1",
            "Ne": "cap-4-1-1",
            "Npsi": "cap-4-1-1",
            "integration_offset": "cap-4-1-4",
        }
        for field, expected_anchor in expected.items():
            with self.subTest(field=field):
                self.assertEqual(field_anchor(field), expected_anchor)

    def test_no_field_lands_in_a_stub_section(self):
        """Every field must open in a section that ACTUALLY explains it.

        The owner's request is literal -- "each variable" needs physical
        and mathematical detail --, and the silent way to violate that is
        not writing badly: it's the link landing in a two-sentence section
        that just announces the subject and delegates. That was happening
        with `mu_x` (307 B), `inflow_field_model` (708 B), and the three
        reverse-flow blending parameters.

        The floor is deliberately low: it does not gauge text quality, it
        only catches the stub -- a section shorter than it has no room to
        say what the quantity is, what the model does with it, what changes
        in the result, and where it stops being valid.
        """
        from zbemt.gui.field_help import field_map, documentation_sections

        FLOOR = 900
        length_by_anchor = {}
        for section in documentation_sections():
            for anchor in set(section.aliases) | {section.anchor}:
                length_by_anchor[anchor] = len(section.body)

        stubs = []
        for field, anchor in sorted(field_map().items()):
            n = length_by_anchor.get(anchor, 0)
            if n < FLOOR:
                stubs.append(f"{field} -> {anchor} ({n} B)")
        self.assertEqual(stubs, [],
                          "field whose help target is a stub: " + str(stubs))

    def test_every_internal_link_of_the_html_has_a_destination(self):
        """Audits internal links, including the ones used by the help pages."""
        destinations = set(re.findall(r'id="([\w.\-]+)"', self.html))
        links = re.findall(r'href="#([\w.\-]+)"', self.html)
        missing = sorted(set(links) - destinations)
        self.assertEqual(missing, [], f"internal links without an anchor: {missing}")

    def test_geometry_airfoil_have_field_level_physics_destinations(self):
        """Geometry/Airfoil must not land in a generic physics chapter."""
        from zbemt.gui.field_help import field_anchor, documentation_sections

        geometry = {"n_blades", "radius_m"}
        airfoil = {
            "external_reynolds_list", "external_mach_list",
            "external_alpha_min_deg", "external_alpha_max_deg",
            "external_alpha_step_deg", "extend_full_range",
            "viterna_blend_width_deg", "name", "source", "cl_alpha",
            "alpha0_deg", "cd0", "k", "stall_model",
            "alpha_stall_pos_deg", "alpha_stall_neg_deg",
            "dynamic_stall_A", "dynamic_stall_fade_start_deg",
            "dynamic_stall_fade_end_deg", "reverse_flow_model",
            "reverse_flow_blend_factor", "thin_plate_blend_center_deg",
            "thin_plate_blend_width_deg", "mask_reverse_flow_plots",
            "use_compressibility",
        }
        for field in geometry | airfoil:
            with self.subTest(field=field):
                entry = self.FIELD_HELP[field]
                self.assertTrue(entry["equation"])
                self.assertTrue(entry["range"])
                destination = field_anchor(field)
                self.assertIsNotNone(destination)
                # It must be a SECTION, not a whole chapter: landing on an
                # `<h2>` drops the reader at the top of a tab's chapter and
                # leaves them to find the field themselves.
                level = next((x.level for x in documentation_sections()
                              if destination in set(x.aliases) | {x.anchor}), None)
                self.assertIsNotNone(level, f"{field}: unknown anchor {destination}")
                self.assertGreaterEqual(level, 3, f"{field} opens a whole chapter")

        # SELECTOR fields: the right destination is the section that
        # compares the options, not the first of them.
        self.assertEqual(field_anchor("reverse_flow_model"), "cap-3-4-1")
        self.assertEqual(field_anchor("stall_model"), "cap-3-2-2")

        self.assertEqual(field_anchor("n_blades"), "cap-2-1")
        self.assertEqual(field_anchor("radius_m"), "cap-2-1")
        for field in {"source", "cl_alpha", "alpha0_deg", "cd0", "k", "name"}:
            with self.subTest(field=field):
                self.assertEqual(field_anchor(field), "cap-3-2-1")

    def test_visible_geometry_airfoil_fields_have_tooltip_tokens(self):
        """Every audited visible field has a tooltip that identifies its parameter."""
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[1]
        geometry_text = (raiz / "zbemt" / "gui" / "tabs" / "geometry_tab.py").read_text(
            encoding="utf-8")
        airfoil_text = (raiz / "zbemt" / "gui" / "tabs" / "airfoil.py").read_text(
            encoding="utf-8")
        geometry_fields = {"n_blades", "radius_m"}
        airfoil_fields = {
            "external_reynolds_list", "external_mach_list",
            "external_alpha_min_deg", "external_alpha_max_deg",
            "external_alpha_step_deg", "extend_full_range",
            "viterna_blend_width_deg", "name", "source", "cl_alpha",
            "alpha0_deg", "cd0", "k", "stall_model",
            "alpha_stall_pos_deg", "alpha_stall_neg_deg", "dynamic_stall_A",
            "dynamic_stall_fade_start_deg", "dynamic_stall_fade_end_deg",
            "reverse_flow_model", "reverse_flow_blend_factor",
            "thin_plate_blend_center_deg", "thin_plate_blend_width_deg",
            "use_compressibility",
        }
        # `mask_reverse_flow_plots` does NOT belong here: it left the
        # Airfoil tab (owner's item 10). It's a display choice -- it hides
        # the Ut<0 region in the disk maps, without touching physics, force,
        # or CSV -- and now lives only in the Results tab, next to the plot
        # it changes.
        self.assertNotIn("mask_reverse_flow_plots", airfoil_text,
                          "the mask control should live only in the Results tab")
        for field in geometry_fields:
            with self.subTest(field=field):
                self.assertRegex(geometry_text, rf'setToolTip\([^\n]*"{field}"')
        for field in airfoil_fields:
            with self.subTest(field=field):
                self.assertTrue(
                    f'"{field}"' in airfoil_text
                    or f'"airfoil.{field}"' in airfoil_text)
                self.assertRegex(
                    airfoil_text,
                    rf'setToolTip\([\s\S]{{0,300}}"(?:airfoil\.)?{field}"')


class TestBlockHelpCoverage(unittest.TestCase):
    """BLOCK_HELP has correct structure and valid anchors."""

    def setUp(self):
        from zbemt.gui import help_blocks
        from zbemt import paths
        self.BLOCK_HELP = help_blocks.BLOCK_HELP
        path = paths.documentation_path()
        self.html = path.read_text(encoding="utf-8") if path else ""

    def test_required_keys(self):
        for block, entry in self.BLOCK_HELP.items():
            with self.subTest(block=block):
                self.assertIn("title", entry)
                self.assertIn("body", entry)
                self.assertIn("anchor", entry)
                self.assertTrue(entry["title"])
                self.assertIsInstance(entry["body"], list)
                self.assertGreater(len(entry["body"]), 0)

    def test_anchors_exist_in_html(self):
        if not self.html:
            self.skipTest("documentation.html not found")
        for block, entry in self.BLOCK_HELP.items():
            anchor = entry.get("anchor")
            if not anchor:
                continue
            with self.subTest(block=block):
                self.assertIn(f'id="{anchor}"', self.html,
                              f"Anchor '{anchor}' (block '{block}') not found in the HTML")


    def test_workflow_blocks_cover_results_and_user_actions(self):
        """Execution blocks explain the action and how to read the result."""
        for block in ("run_case", "run_batch", "results"):
            with self.subTest(block=block):
                entry = self.BLOCK_HELP.get(block)
                self.assertIsNotNone(entry)
                text = " ".join(entry["body"]).lower()
                self.assertRegex(text, r"(choose|select|use|interpret)")
                self.assertRegex(text, r"(result|case|batch)")

    def test_run_tabs_have_dedicated_operating_sections(self):
        """The documentation does not reduce the controls to a generic table."""
        for anchor in ("run-case-controls", "run-batch-controls", "results-controls"):
            with self.subTest(anchor=anchor):
                self.assertIn(f'id="{anchor}"', self.html)
        for term in ("replace queue", "fixed-thrust", "Batch condition", "overlay", "convergence"):
            with self.subTest(term=term):
                self.assertIn(term.lower(), self.html.lower())


class TestHelpPopupWidget(unittest.TestCase):
    """HelpPopup opens and closes without crashing."""

    def setUp(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication, QWidget
        import sys
        # QApplication must exist before `zbemt.gui.help_popup` is imported:
        # that import pulls in `zbemt.gui.common`, which sets matplotlib's
        # backend to QtAgg, and matplotlib picks the wrong Qt platform
        # plugin if no QApplication is running yet.
        self.app = QApplication.instance() or QApplication(sys.argv)
        from zbemt.gui.help_popup import HelpPopup
        self.window = QWidget()
        self.window.resize(800, 600)
        self.window.show()
        # Clears the singleton from previous tests to avoid dangling pointers
        HelpPopup._instances.clear()

    def tearDown(self):
        from zbemt.gui.help_popup import HelpPopup
        HelpPopup._instances.clear()

    def test_popup_opens_for_an_existing_field(self):
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instance(self.window)
        popup.show_field("n_blades", self.window)
        self.assertTrue(popup.isVisible())

    def test_popup_closes_when_close_is_called(self):
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instance(self.window)
        popup.show_field("n_blades", self.window)
        popup.close_popup()
        self.assertFalse(popup.isVisible())

    def test_popup_for_nonexistent_field_does_not_open(self):
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instance(self.window)
        popup.close_popup()  # ensures it was closed before
        self.assertFalse(popup.isVisible(), "popup should be closed before the test")
        popup.show_field("field_that_never_exists_xyz", self.window)
        self.assertFalse(popup.isVisible())

    def test_popup_existing_block(self):
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instance(self.window)
        popup.show_block("inflow", self.window)
        self.assertTrue(popup.isVisible())
        popup.close_popup()

    def test_singleton_per_window(self):
        from zbemt.gui.help_popup import HelpPopup
        p1 = HelpPopup.instance(self.window)
        p2 = HelpPopup.instance(self.window)
        self.assertIs(p1, p2)

    def test_popup_closes_with_the_escape_key(self):
        """doc-plan.md Section 7, `test_popup_closes_on_escape` -- the
        `keyPressEvent` calls `close_popup()` only for Key_Escape; without
        this test, a refactor that swapped the key or removed the
        handler would not be caught (`test_popup_closes_when_close_is_called`
        calls `close_popup()` directly, never exercising `keyPressEvent`)."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instance(self.window)
        popup.show_field("n_blades", self.window)
        self.assertTrue(popup.isVisible())
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        popup.keyPressEvent(event)
        self.assertFalse(popup.isVisible())

    def test_popup_does_not_reserve_empty_space_in_the_title(self):
        """Switching field must recompute the height without ghost space."""
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instance(self.window)
        popup.show_field("n_blades", self.window)
        popup.show_field("dynamic_stall_method", self.window)
        self.assertLessEqual(popup._title_label.sizeHint().height(), 32)
        self.assertLess(popup._title_label.height(), popup.height())
        # The popup's height must be EXPLAINED by the content, not fixed
        # to a number. The absolute limit that used to be here (`< 180`)
        # went stale the day the equations started being drawn as math
        # (an image via mathtext) instead of a line of text: legitimate
        # content grew and the test flagged a regression where there was
        # an improvement. What it exists to catch -- leftover empty
        # space from the previous entry -- is the SLACK between the
        # popup and what is inside it, and that is what is measured now.
        content = (popup._title_label.height()
                   + sum(popup._body_layout.itemAt(i).widget().height()
                         for i in range(popup._body_layout.count())
                         if popup._body_layout.itemAt(i).widget() is not None)
                   + popup._btn_doc.height())
        self.assertLess(popup.height() - content, 120,
                         "popup reserving empty space: "
                         f"height={popup.height()} content={content}")


class TestInstallFieldPopups(unittest.TestCase):
    """install_field_popups does not break existing layouts."""

    def setUp(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        import sys
        self.app = QApplication.instance() or QApplication(sys.argv)

    def test_spanning_rows_stay_spanning(self):
        """Spanning rows remain spanning after install_field_popups."""
        from PyQt6.QtWidgets import QWidget, QFormLayout, QCheckBox
        from zbemt.gui.field_help import install_field_popups

        w = QWidget()
        form = QFormLayout(w)
        cb = QCheckBox("Enable something")
        cb.setToolTip('"use_dynamic_stall" — enables dynamic stall model')
        form.addRow(cb)  # spanning row

        install_field_popups(w)

        # row 0 must remain without LabelRole (it is spanning)
        self.assertIsNone(form.itemAt(0, QFormLayout.ItemRole.LabelRole))

    def test_documented_field_gets_a_clickable_label(self):
        """Field with an entry in FIELD_HELP has its QLabel replaced by a QToolButton."""
        from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QSpinBox, QToolButton
        from zbemt.gui.field_help import install_field_popups

        w = QWidget()
        form = QFormLayout(w)
        lbl = QLabel("Number of blades:")
        spin = QSpinBox()
        spin.setToolTip('"n_blades" — number of rotor blades')
        form.addRow(lbl, spin)

        install_field_popups(w)

        item = form.itemAt(0, QFormLayout.ItemRole.LabelRole)
        self.assertIsNotNone(item)
        self.assertIsInstance(item.widget(), QToolButton)

    def test_every_help_equation_actually_renders(self):
        """`PR-4`: the popup renders the equation with mathtext and, when
        that FAILS, silently falls back to showing the raw LaTeX source.

        So an unsupported macro does not raise -- it just puts
        `\\tfrac{3}{2}` on screen as text. Eleven equations were in that
        state (`\\tfrac`, `\\big`, `\\mathrel`, `\\le`, and two entries that
        held prose rather than mathematics). This walks every entry so a
        new one cannot join them unnoticed."""
        from zbemt.gui.help_popup import render_equation
        from zbemt.gui.help_content import FIELD_HELP
        from zbemt.gui import help_blocks

        broken = []

        def check(where, equation):
            equation = (equation or "").strip()
            if not equation:
                return
            try:
                rendered = render_equation(equation)
            except Exception as exc:                       # pragma: no cover
                broken.append(f"{where}: raised {exc!r}")
                return
            if rendered is None:
                broken.append(f"{where}: {equation}")

        def check_embedded(where, text):
            """`_add_line` splits prose on `$$` and renders the odd parts,
            so an equation buried in a paragraph reaches mathtext too."""
            if not isinstance(text, str) or "$$" not in text:
                return
            for i, part in enumerate(text.split("$$")):
                if i % 2 == 1:
                    check(where, part)

        for key, data in FIELD_HELP.items():
            check(f"FIELD_HELP[{key}].equation", data.get("equation"))
            for prose_key in ("definition", "effect", "range", "unit"):
                check_embedded(f"FIELD_HELP[{key}].{prose_key}",
                                data.get(prose_key))
            options = data.get("options")
            if isinstance(options, dict):
                for name, text in options.items():
                    check_embedded(f"FIELD_HELP[{key}].options[{name}]", text)

        # The block popups render through the SAME path, and were not
        # covered when this test only walked FIELD_HELP.
        for key, data in help_blocks.BLOCK_HELP.items():
            for i, paragraph in enumerate(data.get("body", [])):
                check_embedded(f"BLOCK_HELP[{key}].body[{i}]", paragraph)

        self.assertEqual(broken, [],
                          "these equations fall back to raw LaTeX on screen")

    def test_clickable_label_renders_the_symbol_instead_of_the_markup(self):
        """`PR-4`: a documented field whose label carries a rendered symbol
        must SHOW the symbol, not the markup.

        `QToolButton.setText` does not render HTML, so swapping the
        `QLabel` for a plain button put the literal string
        `&psi;<sub>w</sub>` on screen -- exactly on the fields that carry
        mathematics. The button paints its text through a QTextDocument,
        so the markup must never reach the painted output."""
        from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QDoubleSpinBox
        from zbemt.gui.field_help import install_field_popups

        w = QWidget()
        form = QFormLayout(w)
        lbl = QLabel("&psi;<sub>w</sub> — Sideslip [deg]:")
        spin = QDoubleSpinBox()
        spin.setToolTip('"sideslip_deg" — sideslip angle of the free stream')
        form.addRow(lbl, spin)

        install_field_popups(w)

        button = form.itemAt(0, QFormLayout.ItemRole.LabelRole).widget()
        # What the button PAINTS comes from its document, not from text().
        painted = button._doc.toPlainText()
        self.assertNotIn("<sub>", painted)
        self.assertNotIn("&psi;", painted)
        self.assertIn("ψ", painted)
        self.assertIn("Sideslip", painted)

    def test_campo_nao_documentado_sem_alteracao(self):
        """Field without an entry in FIELD_HELP does not get a clickable label."""
        from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QLineEdit
        from zbemt.gui.field_help import install_field_popups

        w = QWidget()
        form = QFormLayout(w)
        lbl = QLabel("Unknown field:")
        le = QLineEdit()
        # no tooltip → unknown field
        form.addRow(lbl, le)

        install_field_popups(w)

        item = form.itemAt(0, QFormLayout.ItemRole.LabelRole)
        self.assertIsNotNone(item)
        self.assertIsInstance(item.widget(), QLabel)  # remains a QLabel


if __name__ == "__main__":
    unittest.main()


class TestDynamicStallTooltipSurvives(unittest.TestCase):
    """Owner's item 2: "Enable dynamic stall checkbox has no popup help
    (and no tooltip also)".

    The cause was not a lack of content -- the entry in FIELD_HELP
    existed -- but `_update_dynamic_stall_enabled`, which REPLACED the
    tooltip with "" whenever the box was not locked. Since that method
    runs while the tab is being built, the field was born without a
    tooltip; and `field_help` derives the field's NAME from the first
    token between quotes in the tooltip, so the help popup vanished
    along with it. A tooltip is, here, infrastructure: erasing it turns
    off help silently.
    """

    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import matplotlib
        matplotlib.use("Agg")
        from PyQt6.QtWidgets import QApplication
        import sys
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _tab(self):
        from tests import helpers
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.airfoil import AirfoilTab
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = AirfoilTab(state)
        self.addCleanup(tab.deleteLater)
        return tab

    def test_tooltip_identifies_the_field_in_both_states(self):
        from zbemt.gui.field_help import _widget_field

        tab = self._tab()
        checkbox = tab.use_dynamic_stall
        for blocked in (False, True):
            # 'analytical' + 'linear' is the combination that locks the option
            tab.source_combo.setCurrentText("analytical")
            tab.stall_model_combo.setCurrentText("linear" if blocked else "clip")
            tab._update_dynamic_stall_enabled()
            with self.subTest(blocked=blocked):
                self.assertTrue(checkbox.toolTip(), "tooltip erased")
                self.assertEqual(_widget_field(checkbox), "use_dynamic_stall")

    def test_blocked_state_explains_the_reason_without_losing_the_name(self):
        tab = self._tab()
        tab.source_combo.setCurrentText("analytical")
        tab.stall_model_combo.setCurrentText("linear")
        tab._update_dynamic_stall_enabled()
        tooltip = tab.use_dynamic_stall.toolTip()
        self.assertIn("use_dynamic_stall", tooltip)
        self.assertIn("static stall", tooltip)


class TestParagraphsInFieldHelp(unittest.TestCase):
    """Field help explains the SAME quantity in both modes, and the two
    texts used to come out stuck together in one running block.

    The popup's `QLabel`s are RichText, and RichText collapses
    whitespace: the `\n\n` that separates "in the rotor..." from "in
    the propeller..." separated nothing on screen. `help_popup.in_paragraphs`
    turns the double break into a real `<p>`; without it, the hardest
    text in the help (two conventions, one spliced onto the other)
    stayed illegible."""

    def test_double_break_becomes_a_paragraph(self):
        from zbemt.gui.help_popup import in_paragraphs
        html = in_paragraphs("Rotor: climbs and descends.\n\nPropeller: flight speed.")
        self.assertEqual(html.count("<p"), 2)
        self.assertIn("Rotor: climbs and descends.", html)
        self.assertIn("Propeller: flight speed.", html)

    def test_single_paragraph_text_gains_no_p(self):
        """`<p>` adds margin: on a text of a single line, it would only
        push the neighboring fields further apart."""
        from zbemt.gui.help_popup import in_paragraphs
        self.assertEqual(in_paragraphs("Just one line."), "Just one line.")
        self.assertEqual(in_paragraphs(""), "")

    def test_single_break_stays_a_space(self):
        """As in any HTML: only the BLANK line marks a paragraph."""
        from zbemt.gui.help_popup import in_paragraphs
        self.assertNotIn("<p", in_paragraphs("one\nsimple break"))

    def test_the_popup_is_wide_enough_for_paragraphs(self):
        """At 360px each paragraph turned into a narrow, tall column --
        more scrolling than text. The threshold used to be 1200, but the
        popup NEVER actually rendered at that width -- a bug in
        `_posicionar` let the internal QScrollArea lock its width to its
        own small, fixed sizeHint, ignoring `_WIDTH` entirely (fixed
        in this session). With the bug fixed, 1200+ became too wide on
        the real screen; the user asked for a moderate increase over the
        previous width, not the original design width."""
        from zbemt.gui.help_popup import _WIDTH
        self.assertGreaterEqual(_WIDTH, 500)

    def test_help_covering_both_modes_is_in_paragraphs(self):
        """These fields change meaning with the mode, so their help MUST
        carry both texts separately."""
        from zbemt.gui.help_content import FIELD_HELP
        for field in ("mu_x", "Vz", "is_propeller"):
            with self.subTest(field=field):
                entry = FIELD_HELP[field]
                text = str(entry.get("definition", "")) + str(entry.get("effect", ""))
                text += "".join(str(v) for v in (entry.get("options") or {}).values())
                self.assertIn("\n\n", text,
                               f"the help for {field} explains both modes in a single block")

    def test_dynamic_stall_equations_render_pixmap(self):
        """The dynamic stall equations in FIELD_HELP render as QPixmap."""
        from zbemt.gui.help_content import FIELD_HELP
        from zbemt.gui.help_popup import render_equation
        ds_fields = [
            "use_dynamic_stall",
            "dynamic_stall_method",
            "dynamic_stall_A",
            "dynamic_stall_fade_start_deg",
            "dynamic_stall_fade_end_deg",
        ]
        for c in ds_fields:
            eq = FIELD_HELP[c].get("equation", "")
            with self.subTest(field=c, eq=eq):
                pixmap = render_equation(eq)
                self.assertIsNotNone(pixmap, f"Failed to render equation for {c}")
                self.assertFalse(pixmap.isNull())

    def test_all_block_help_equations_render(self):
        """All $$...$$ equations in BLOCK_HELP render successfully as QPixmap."""
        from zbemt.gui.help_blocks import BLOCK_HELP
        from zbemt.gui.help_popup import render_equation
        for block, entry in BLOCK_HELP.items():
            for p in entry.get("body", []):
                if "$$" in p:
                    parts = p.split("$$")
                    for i, part in enumerate(parts):
                        if i % 2 == 1 and part.strip():
                            eq = part.strip()
                            with self.subTest(block=block, eq=eq):
                                pixmap = render_equation(eq, dpr=1.0)
                                self.assertIsNotNone(pixmap, f"Failed to render equation in block '{block}': {eq}")
                                self.assertFalse(pixmap.isNull())


