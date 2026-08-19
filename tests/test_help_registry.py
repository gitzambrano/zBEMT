"""`zbemt/gui/help_registry.py` -- field-level context popup (Part 1
of the documentation redesign plan).

Derives the short explanation for each field from the SAME "Parameters by
tab" table that `field_help.mapa_de_campos()` already uses for the anchor
-- without a second source of content. See the module's docstring for the
full reasoning.
"""
import unittest

try:
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except ImportError:                                   # pragma: no cover
    _HAS_QT = False


class TestRegistroDeCampos(unittest.TestCase):
    def test_cobre_campos_conhecidos(self):
        from zbemt.gui.help_registry import registro_de_campos
        reg = registro_de_campos()
        self.assertIn("n_blades", reg)
        self.assertIn("stall_model", reg)
        self.assertIn("collective_deg", reg)

    def test_descricao_curta_bate_com_o_html(self):
        from zbemt.gui.help_registry import descricao_curta
        desc = descricao_curta("n_blades")
        self.assertIsNotNone(desc)
        self.assertIn("Number of blades", desc)

    def test_aceita_nome_qualificado_com_prefixo(self):
        """`field_help._campo_do_widget` returns the suffix, but a
        caller may pass `"geometry.n_blades"` by mistake -- it must not
        break, just fall through to the same field."""
        from zbemt.gui.help_registry import descricao_curta
        self.assertEqual(descricao_curta("n_blades"), descricao_curta("geometry.n_blades"))

    def test_campo_desconhecido_devolve_none(self):
        from zbemt.gui.help_registry import descricao_curta
        self.assertIsNone(descricao_curta("campo_que_nao_existe_xyz"))


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestLabelClicavelNaGeometria(unittest.TestCase):
    """The new system uses QToolButton as clickable label -- no '?' button per field."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import tempfile, shutil
        from tests import helpers
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        with helpers.patch_em_toda_gui("PROJECTS_ROOT", self._tmp):
            from zbemt.gui import app as gui
            self.win = gui.MainWindow()
        self.addCleanup(self.win.deleteLater)

    def test_aba_geometry_tem_labels_clicaveis(self):
        """Documented fields in the Geometry tab gain QToolButton label (hand cursor)."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QToolButton
        aba = self.win.tabs.widget(1)   # Geometry
        clicaveis = [b for b in aba.findChildren(QToolButton)
                     if b.cursor().shape() == Qt.CursorShape.PointingHandCursor]
        self.assertTrue(clicaveis, "Geometry tab has no clickable field labels")
        # default tooltip for clickable labels
        # The exact string comes from `field_help._label_clicavel`. This test
        # searched for "Click for help", which never existed -- the tooltip is
        # "Click the label for help on this field" --, so it has failed since
        # it was written. Matching by stable substring ("for help") instead of
        # the whole phrase prevents a copy rewrite from breaking the test
        # without anything actually breaking.
        self.assertTrue(any("for help" in b.toolTip() for b in clicaveis),
                        f"tooltips: {[b.toolTip() for b in clicaveis][:3]}")


if __name__ == "__main__":
    unittest.main()
