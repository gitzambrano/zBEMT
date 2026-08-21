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
        caminho = paths.documentation_path()
        self.html = caminho.read_text(encoding="utf-8") if caminho else ""

    def test_required_keys_in_every_entry(self):
        """Each entry in FIELD_HELP has the required keys filled in."""
        # "anchor" is no longer among them: the destination is DERIVED from
        # the document by `field_help.ancora_do_campo`, which finds the
        # section that declares the field. A hand-kept anchor was a second
        # source of truth that went stale the moment a section moved.
        obrigatorios = {"title", "definition", "unit", "equation", "effect", "range", "options"}
        for campo, dados in self.FIELD_HELP.items():
            with self.subTest(campo=campo):
                faltando = obrigatorios - set(dados)
                self.assertFalse(faltando, f"Chaves ausentes em '{campo}': {faltando}")
                self.assertTrue(dados["title"], f"'{campo}': title vazio")
                self.assertTrue(dados["definition"], f"'{campo}': definition vazio")

    def test_html_fields_covered(self):
        """Each ajuda-* field in the HTML has a corresponding entry in FIELD_HELP."""
        if not self.html:
            self.skipTest("documentation.html not found")
        campos_html = re.findall(r'id="ajuda-([\w.]+)"', self.html)
        # excludes header sections (geometry, airfoil, config, execution)
        _CABECALHOS = {"geometria", "aerofolio", "config", "execucao"}
        campos_html = [c for c in campos_html if c not in _CABECALHOS]
        for campo in campos_html:
            with self.subTest(campo=campo):
                self.assertIn(campo, self.FIELD_HELP,
                              f"Field '{campo}' exists in the HTML but not in FIELD_HELP")

    def test_enum_options_present(self):
        """Enum fields have non-empty options, and all keys are strings."""
        enum_esperados = {
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
        for campo, opcoes_esperadas in enum_esperados.items():
            with self.subTest(campo=campo):
                dados = self.FIELD_HELP.get(campo)
                self.assertIsNotNone(dados, f"'{campo}' ausente em FIELD_HELP")
                opts = dados.get("options")
                self.assertIsNotNone(opts, f"'{campo}' deveria ter options")
                for opt in opcoes_esperadas:
                    self.assertIn(opt, opts, f"Option '{opt}' missing from '{campo}.options'")

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
        bloco = self.html.split("<!-- INDICE-DE-CAMPOS:config -->", 1)[1]
        bloco = bloco.split("<!-- /INDICE-DE-CAMPOS:config -->", 1)[0]
        campos = re.findall(r"<code>([^<]+)</code>", bloco)
        self.assertEqual(len(campos), 27)
        for campo in campos:
            with self.subTest(campo=campo):
                dados = self.FIELD_HELP[campo]
                for chave in ("definition", "equation", "effect", "range"):
                    self.assertTrue(dados[chave], f"{campo} sem {chave} no popup")

    def test_config_destinations_cover_physics_and_implementation_boundary(self):
        """The critical destinations state what to do, the physics, and the code boundary."""
        from zbemt.gui.field_help import ancora_do_campo

        exigencias = {
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
        for campo, termos in exigencias.items():
            ancora = ancora_do_campo(campo)
            # The physics destination and the operational subsection live in
            # the same CHAPTER, but can be separated by long figures and
            # derivations -- so the scope is the whole chapter, delimited by
            # the surrounding `<h2>`s. The previous version used a 40000-byte
            # window starting at the anchor, which sometimes leaked into the
            # next chapter, sometimes cut off its own: adding a paragraph to
            # a section pushed a term outside the window and broke a test
            # that had nothing to do with the edit.
            trecho = self._capitulo_da_ancora(ancora).lower()
            self.assertTrue(trecho, campo)
            for termo in termos:
                self.assertIn(termo.lower(), trecho, f"{campo}: termo ausente: {termo}")

    def _capitulo_da_ancora(self, ancora: str) -> str:
        """Text of the chapter (`<h2>` to `<h2>`) that contains ``ancora``."""
        inicio = self.html.find(f'id="{ancora}"')
        if inicio < 0:
            return ""
        limites = [m.start() for m in re.finditer(r"<h2[ >]", self.html)]
        antes = [x for x in limites if x <= inicio]
        depois = [x for x in limites if x > inicio]
        return self.html[antes[-1] if antes else 0:
                         depois[0] if depois else len(self.html)]

    def test_anchors_exist_in_html(self):
        """Every anchor referenced in FIELD_HELP exists in the HTML."""
        if not self.html:
            self.skipTest("documentation.html not found")
        for campo, dados in self.FIELD_HELP.items():
            ancora = dados.get("anchor")
            if not ancora:
                continue
            with self.subTest(campo=campo, ancora=ancora):
                self.assertIn(f'id="{ancora}"', self.html,
                              f"Anchor '{ancora}' (from '{campo}') not found in the HTML")

    def test_help_abre_a_secao_do_proprio_campo(self):
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
        from zbemt.gui.field_help import (ancora_do_campo, secoes_da_documentacao,
                                          _cita, _MARCA_BEMT)

        por_ancora = {}
        for s in secoes_da_documentacao():
            for a in set(s.apelidos) | {s.ancora}:
                por_ancora[a] = s

        for campo in self.FIELD_HELP:
            with self.subTest(campo=campo):
                ancora = ancora_do_campo(campo)
                self.assertIsNotNone(ancora, f"{campo} has no destination")
                self.assertFalse(ancora.startswith("ajuda-"),
                                 f"{campo} falls back to the index table")
                secao = por_ancora.get(ancora)
                self.assertIsNotNone(secao, f"{campo} points at an unknown anchor")
                self.assertTrue(_cita(secao, campo),
                                f"{campo} opens a section that does not mention it")
                self.assertIn(_MARCA_BEMT, secao.corpo,
                              f"{campo} opens a section that does not say how to set it")

        # A loose `<a id=...>` sitting just above a heading starts marking a
        # different section as soon as anything is inserted between them, and
        # nothing about the page looks wrong when it happens. (It did happen:
        # `cap-11`, the mesh, was captured by a section inserted in front of
        # it, and `Ne`/`Npsi` began opening the chord distribution.) This is
        # the lock against that.
        esperados = {
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
        for campo, ancora_esperada in esperados.items():
            with self.subTest(campo=campo):
                self.assertEqual(ancora_do_campo(campo), ancora_esperada)

    def test_nenhum_campo_cai_numa_secao_talo(self):
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
        from zbemt.gui.field_help import mapa_de_campos, secoes_da_documentacao

        PISO = 900
        tamanho = {}
        for secao in secoes_da_documentacao():
            for ancora in set(secao.apelidos) | {secao.ancora}:
                tamanho[ancora] = len(secao.corpo)

        talos = []
        for campo, ancora in sorted(mapa_de_campos().items()):
            n = tamanho.get(ancora, 0)
            if n < PISO:
                talos.append(f"{campo} -> {ancora} ({n} B)")
        self.assertEqual(talos, [],
                          "field whose help target is a stub: " + str(talos))

    def test_todos_os_links_internos_do_html_tem_destino(self):
        """Audits internal links, including the ones used by the help pages."""
        destinos = set(re.findall(r'id="([\w.\-]+)"', self.html))
        links = re.findall(r'href="#([\w.\-]+)"', self.html)
        faltantes = sorted(set(links) - destinos)
        self.assertEqual(faltantes, [], f"internal links without an anchor: {faltantes}")

    def test_geometry_airfoil_have_field_level_physics_destinations(self):
        """Geometry/Airfoil must not land in a generic physics chapter."""
        from zbemt.gui.field_help import ancora_do_campo, secoes_da_documentacao

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
        for campo in geometry | airfoil:
            with self.subTest(campo=campo):
                dados = self.FIELD_HELP[campo]
                self.assertTrue(dados["equation"])
                self.assertTrue(dados["range"])
                destino = ancora_do_campo(campo)
                self.assertIsNotNone(destino)
                # It must be a SECTION, not a whole chapter: landing on an
                # `<h2>` drops the reader at the top of a tab's chapter and
                # leaves them to find the field themselves.
                nivel = next((x.nivel for x in secoes_da_documentacao()
                              if destino in set(x.apelidos) | {x.ancora}), None)
                self.assertIsNotNone(nivel, f"{campo}: unknown anchor {destino}")
                self.assertGreaterEqual(nivel, 3, f"{campo} opens a whole chapter")

        # SELECTOR fields: the right destination is the section that
        # compares the options, not the first of them.
        self.assertEqual(ancora_do_campo("reverse_flow_model"), "cap-3-4-1")
        self.assertEqual(ancora_do_campo("stall_model"), "cap-3-2-2")

        self.assertEqual(ancora_do_campo("n_blades"), "cap-2-1")
        self.assertEqual(ancora_do_campo("radius_m"), "cap-2-1")
        for campo in {"source", "cl_alpha", "alpha0_deg", "cd0", "k", "name"}:
            with self.subTest(campo=campo):
                self.assertEqual(ancora_do_campo(campo), "cap-3-2-1")

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
        for campo in geometry_fields:
            with self.subTest(campo=campo):
                self.assertRegex(geometry_text, rf'setToolTip\([^\n]*"{campo}"')
        for campo in airfoil_fields:
            with self.subTest(campo=campo):
                self.assertTrue(
                    f'"{campo}"' in airfoil_text
                    or f'"airfoil.{campo}"' in airfoil_text)
                self.assertRegex(
                    airfoil_text,
                    rf'setToolTip\([\s\S]{{0,300}}"(?:airfoil\.)?{campo}"')


class TestBlockHelpCoverage(unittest.TestCase):
    """BLOCK_HELP has correct structure and valid anchors."""

    def setUp(self):
        from zbemt.gui import help_blocks
        from zbemt import paths
        self.BLOCK_HELP = help_blocks.BLOCK_HELP
        caminho = paths.documentation_path()
        self.html = caminho.read_text(encoding="utf-8") if caminho else ""

    def test_required_keys(self):
        for bloco, dados in self.BLOCK_HELP.items():
            with self.subTest(bloco=bloco):
                self.assertIn("title", dados)
                self.assertIn("body", dados)
                self.assertIn("anchor", dados)
                self.assertTrue(dados["title"])
                self.assertIsInstance(dados["body"], list)
                self.assertGreater(len(dados["body"]), 0)

    def test_anchors_exist_in_html(self):
        if not self.html:
            self.skipTest("documentation.html not found")
        for bloco, dados in self.BLOCK_HELP.items():
            ancora = dados.get("anchor")
            if not ancora:
                continue
            with self.subTest(bloco=bloco):
                self.assertIn(f'id="{ancora}"', self.html,
                              f"Anchor '{ancora}' (block '{bloco}') not found in the HTML")


    def test_workflow_blocks_cover_results_and_user_actions(self):
        """Execution blocks explain the action and how to read the result."""
        for bloco in ("run_case", "run_batch", "results"):
            with self.subTest(bloco=bloco):
                dados = self.BLOCK_HELP.get(bloco)
                self.assertIsNotNone(dados)
                texto = " ".join(dados["body"]).lower()
                self.assertRegex(texto, r"(choose|select|use|interpret)")
                self.assertRegex(texto, r"(result|case|batch)")

    def test_run_tabs_have_dedicated_operating_sections(self):
        """The documentation does not reduce the controls to a generic table."""
        for ancora in ("run-case-controls", "run-batch-controls", "results-controls"):
            with self.subTest(ancora=ancora):
                self.assertIn(f'id="{ancora}"', self.html)
        for termo in ("replace queue", "fixed-thrust", "Batch condition", "overlay", "convergence"):
            with self.subTest(termo=termo):
                self.assertIn(termo.lower(), self.html.lower())


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
        self.janela = QWidget()
        self.janela.resize(800, 600)
        self.janela.show()
        # Clears the singleton from previous tests to avoid dangling pointers
        HelpPopup._instancias.clear()

    def tearDown(self):
        from zbemt.gui.help_popup import HelpPopup
        HelpPopup._instancias.clear()

    def test_popup_abre_para_campo_existente(self):
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instancia(self.janela)
        popup.mostrar_campo("n_blades", self.janela)
        self.assertTrue(popup.isVisible())

    def test_popup_fecha_ao_chamar_fechar(self):
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instancia(self.janela)
        popup.mostrar_campo("n_blades", self.janela)
        popup.fechar()
        self.assertFalse(popup.isVisible())

    def test_popup_campo_inexistente_nao_abre(self):
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instancia(self.janela)
        popup.fechar()  # ensures it was closed before
        self.assertFalse(popup.isVisible(), "popup deveria estar fechado antes do teste")
        popup.mostrar_campo("campo_que_nao_existe_nunca_xyz", self.janela)
        self.assertFalse(popup.isVisible())

    def test_popup_bloco_existente(self):
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instancia(self.janela)
        popup.mostrar_bloco("inflow", self.janela)
        self.assertTrue(popup.isVisible())
        popup.fechar()

    def test_singleton_por_janela(self):
        from zbemt.gui.help_popup import HelpPopup
        p1 = HelpPopup.instancia(self.janela)
        p2 = HelpPopup.instancia(self.janela)
        self.assertIs(p1, p2)

    def test_popup_fecha_com_tecla_escape(self):
        """doc-plan.md Section 7, `test_popup_closes_on_escape` -- the
        `keyPressEvent` calls `fechar()` only for Key_Escape; without
        this test, a refactor that swapped the key or removed the
        handler would not be caught (`test_popup_fecha_ao_chamar_fechar`
        calls `fechar()` directly, never exercising `keyPressEvent`)."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instancia(self.janela)
        popup.mostrar_campo("n_blades", self.janela)
        self.assertTrue(popup.isVisible())
        evento = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        popup.keyPressEvent(evento)
        self.assertFalse(popup.isVisible())

    def test_popup_nao_reserva_faixa_vazia_no_titulo(self):
        """Switching field must recompute the height without ghost space."""
        from zbemt.gui.help_popup import HelpPopup
        popup = HelpPopup.instancia(self.janela)
        popup.mostrar_campo("n_blades", self.janela)
        popup.mostrar_campo("dynamic_stall_method", self.janela)
        self.assertLessEqual(popup._lbl_titulo.sizeHint().height(), 32)
        self.assertLess(popup._lbl_titulo.height(), popup.height())
        # The popup's height must be EXPLAINED by the content, not fixed
        # to a number. The absolute limit that used to be here (`< 180`)
        # went stale the day the equations started being drawn as math
        # (an image via mathtext) instead of a line of text: legitimate
        # content grew and the test flagged a regression where there was
        # an improvement. What it exists to catch -- leftover empty
        # space from the previous entry -- is the SLACK between the
        # popup and what is inside it, and that is what is measured now.
        conteudo = (popup._lbl_titulo.height()
                    + sum(popup._corpo.itemAt(i).widget().height()
                          for i in range(popup._corpo.count())
                          if popup._corpo.itemAt(i).widget() is not None)
                    + popup._btn_doc.height())
        self.assertLess(popup.height() - conteudo, 120,
                         "popup reservando faixa vazia: "
                         f"altura={popup.height()} conteudo={conteudo}")


class TestInstalarPopupsDeCampo(unittest.TestCase):
    """instalar_popups_de_campo does not break existing layouts."""

    def setUp(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        import sys
        self.app = QApplication.instance() or QApplication(sys.argv)

    def test_spanning_rows_permanecem_spanning(self):
        """Spanning rows remain spanning after instalar_popups_de_campo."""
        from PyQt6.QtWidgets import QWidget, QFormLayout, QCheckBox
        from zbemt.gui.field_help import instalar_popups_de_campo

        w = QWidget()
        form = QFormLayout(w)
        cb = QCheckBox("Enable something")
        cb.setToolTip('"use_dynamic_stall" — enables dynamic stall model')
        form.addRow(cb)  # spanning row

        instalar_popups_de_campo(w)

        # row 0 must remain without LabelRole (it is spanning)
        self.assertIsNone(form.itemAt(0, QFormLayout.ItemRole.LabelRole))

    def test_campo_documentado_recebe_label_clicavel(self):
        """Field with an entry in FIELD_HELP has its QLabel replaced by a QToolButton."""
        from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QSpinBox, QToolButton
        from zbemt.gui.field_help import instalar_popups_de_campo

        w = QWidget()
        form = QFormLayout(w)
        lbl = QLabel("Number of blades:")
        spin = QSpinBox()
        spin.setToolTip('"n_blades" — number of rotor blades')
        form.addRow(lbl, spin)

        instalar_popups_de_campo(w)

        item = form.itemAt(0, QFormLayout.ItemRole.LabelRole)
        self.assertIsNotNone(item)
        self.assertIsInstance(item.widget(), QToolButton)

    def test_campo_nao_documentado_sem_alteracao(self):
        """Field without an entry in FIELD_HELP does not get a clickable label."""
        from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QLineEdit
        from zbemt.gui.field_help import instalar_popups_de_campo

        w = QWidget()
        form = QFormLayout(w)
        lbl = QLabel("Unknown field:")
        le = QLineEdit()
        # no tooltip → unknown field
        form.addRow(lbl, le)

        instalar_popups_de_campo(w)

        item = form.itemAt(0, QFormLayout.ItemRole.LabelRole)
        self.assertIsNotNone(item)
        self.assertIsInstance(item.widget(), QLabel)  # remains a QLabel


if __name__ == "__main__":
    unittest.main()


class TestTooltipDeEstolDinamicoSobrevive(unittest.TestCase):
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

    def _aba(self):
        from tests import helpers
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.airfoil import AirfoilTab
        state = AppState()
        state.project = helpers.make_studies_project()
        aba = AirfoilTab(state)
        self.addCleanup(aba.deleteLater)
        return aba

    def test_tooltip_identifica_o_campo_nos_dois_estados(self):
        from zbemt.gui.field_help import _campo_do_widget

        aba = self._aba()
        caixa = aba.use_dynamic_stall
        for bloqueado in (False, True):
            # 'analytical' + 'linear' is the combination that locks the option
            aba.source_combo.setCurrentText("analytical")
            aba.stall_model_combo.setCurrentText("linear" if bloqueado else "clip")
            aba._update_dynamic_stall_enabled()
            with self.subTest(bloqueado=bloqueado):
                self.assertTrue(caixa.toolTip(), "tooltip apagado")
                self.assertEqual(_campo_do_widget(caixa), "use_dynamic_stall")

    def test_estado_bloqueado_explica_o_motivo_sem_perder_o_nome(self):
        aba = self._aba()
        aba.source_combo.setCurrentText("analytical")
        aba.stall_model_combo.setCurrentText("linear")
        aba._update_dynamic_stall_enabled()
        dica = aba.use_dynamic_stall.toolTip()
        self.assertIn("use_dynamic_stall", dica)
        self.assertIn("static stall", dica)


class TestParagrafosNaAjudaDeCampo(unittest.TestCase):
    """Field help explains the SAME quantity in both modes, and the two
    texts used to come out stuck together in one running block.

    The popup's `QLabel`s are RichText, and RichText collapses
    whitespace: the `\n\n` that separates "in the rotor..." from "in
    the propeller..." separated nothing on screen. `help_popup.em_paragrafos`
    turns the double break into a real `<p>`; without it, the hardest
    text in the help (two conventions, one spliced onto the other)
    stayed illegible."""

    def test_quebra_dupla_vira_paragrafo(self):
        from zbemt.gui.help_popup import em_paragrafos
        html = em_paragrafos("Rotor: climbs and descends.\n\nPropeller: flight speed.")
        self.assertEqual(html.count("<p"), 2)
        self.assertIn("Rotor: climbs and descends.", html)
        self.assertIn("Propeller: flight speed.", html)

    def test_texto_de_um_paragrafo_nao_ganha_p(self):
        """`<p>` adds margin: on a text of a single line, it would only
        push the neighboring fields further apart."""
        from zbemt.gui.help_popup import em_paragrafos
        self.assertEqual(em_paragrafos("Just one line."), "Just one line.")
        self.assertEqual(em_paragrafos(""), "")

    def test_quebra_simples_continua_sendo_espaco(self):
        """As in any HTML: only the BLANK line marks a paragraph."""
        from zbemt.gui.help_popup import em_paragrafos
        self.assertNotIn("<p", em_paragrafos("uma\nquebra simples"))

    def test_o_popup_e_largo_o_bastante_para_paragrafos(self):
        """At 360px each paragraph turned into a narrow, tall column --
        more scrolling than text. The threshold used to be 1200, but the
        popup NEVER actually rendered at that width -- a bug in
        `_posicionar` let the internal QScrollArea lock its width to its
        own small, fixed sizeHint, ignoring `_LARGURA` entirely (fixed
        in this session). With the bug fixed, 1200+ became too wide on
        the real screen; the user asked for a moderate increase over the
        previous width, not the original design width."""
        from zbemt.gui.help_popup import _LARGURA
        self.assertGreaterEqual(_LARGURA, 500)

    def test_a_ajuda_que_cobre_os_dois_modos_esta_em_paragrafos(self):
        """These fields change meaning with the mode, so their help MUST
        carry both texts separately."""
        from zbemt.gui.help_content import FIELD_HELP
        for campo in ("mu_x", "Vz", "is_propeller"):
            with self.subTest(campo=campo):
                dados = FIELD_HELP[campo]
                texto = str(dados.get("definition", "")) + str(dados.get("effect", ""))
                texto += "".join(str(v) for v in (dados.get("options") or {}).values())
                self.assertIn("\n\n", texto,
                               f"the help for {campo} explains both modes in a single block")

    def test_dynamic_stall_equations_render_pixmap(self):
        """The dynamic stall equations in FIELD_HELP render as QPixmap."""
        from zbemt.gui.help_content import FIELD_HELP
        from zbemt.gui.help_popup import renderizar_equacao
        campos_ds = [
            "use_dynamic_stall",
            "dynamic_stall_method",
            "dynamic_stall_A",
            "dynamic_stall_fade_start_deg",
            "dynamic_stall_fade_end_deg",
        ]
        for c in campos_ds:
            eq = FIELD_HELP[c].get("equation", "")
            with self.subTest(campo=c, eq=eq):
                pixmap = renderizar_equacao(eq)
                self.assertIsNotNone(pixmap, f"Failed to render equation for {c}")
                self.assertFalse(pixmap.isNull())

    def test_all_block_help_equations_render(self):
        """All $$...$$ equations in BLOCK_HELP render successfully as QPixmap."""
        from zbemt.gui.help_blocks import BLOCK_HELP
        from zbemt.gui.help_popup import renderizar_equacao
        for bloco, dados in BLOCK_HELP.items():
            for p in dados.get("body", []):
                if "$$" in p:
                    partes = p.split("$$")
                    for i, parte in enumerate(partes):
                        if i % 2 == 1 and parte.strip():
                            eq = parte.strip()
                            with self.subTest(bloco=bloco, eq=eq):
                                pixmap = renderizar_equacao(eq, dpr=1.0)
                                self.assertIsNotNone(pixmap, f"Failed to render equation in block '{bloco}': {eq}")
                                self.assertFalse(pixmap.isNull())


