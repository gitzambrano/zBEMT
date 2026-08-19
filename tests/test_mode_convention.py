"""The convention of the two flight-speed components changes with MODE.

The engine always decomposes the velocity the same way -- ``mu_x`` in the
disk plane, ``Vz`` along the shaft. What changes between rotor and
propeller is which component carries the flight speed: for a helicopter
in forward flight it is the in-plane one; for a propeller in straight
flight it is the AXIAL one.

Labeled "Advance"/"Axial flow" in both modes, the longitudinal field used
to invite the propeller user to put the aircraft's speed there -- which
enters as edgewise flow and produces the solution of an edgewise rotor
that no propeller in straight flight ever experiences. Plausible and
wrong, with nothing on screen saying otherwise.

In a second pass, the AXES rotated along with it (see
`tests/test_propeller_axes_convention.py`): in propeller mode x is the
rotor axis, the dimensionless advance ratio J_x lives in the AXIAL field,
and the in-plane field becomes the cross-flow -- with the angle measured
from the AXIS (alpha_disk, 0° in straight cruise), not from the plane.
"""
import unittest

from tests.helpers import HAS_QT as _HAS_QT

# `zbemt.gui.common` itself needs Qt, so the import below cannot be reached
# without it -- and the CI job that installs the base dependencies only (to
# prove the engine runs without Qt) must see this module SKIPPED, not a
# collection error.
if not _HAS_QT:                                  # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from PyQt6.QtWidgets import QApplication, QFormLayout

from zbemt.gui.common import rotulo_e_dica_de_condicao


class TestTextosPorModo(unittest.TestCase):
    """The texts themselves -- pure table, no GUI assembled."""

    def test_rotulo_longitudinal_muda_de_convencao(self):
        rotor, _ = rotulo_e_dica_de_condicao(False, "inplane")
        helice, _ = rotulo_e_dica_de_condicao(True, "inplane")
        self.assertNotEqual(rotor, helice)
        self.assertIn("in-plane", rotor.lower())
        self.assertIn("cross", helice.lower())
        self.assertIn("in-plane", helice.lower())

    def test_rotulo_axial_vira_o_avanco_da_helice(self):
        """On the rotor this field is climb/descent; on the propeller it
        is THE advance ratio.

        The row LABEL ("Axial (along-shaft) Flow:") does not change text
        between modes -- it describes the AXIS, not the unit chosen
        within it. What brings the Jₓ the user is looking for is the unit
        combo (`UNIDADES_DE_CONDICAO[("axial", True)]`), not the label."""
        rotor, _ = rotulo_e_dica_de_condicao(False, "axial")
        helice, _ = rotulo_e_dica_de_condicao(True, "axial")
        self.assertIn("axial", rotor.lower())
        self.assertIn("axial", helice.lower())

    def test_dicas_mantem_o_nome_do_campo_para_a_ajuda(self):
        """`field_help` derives the field from the first quoted token of
        the tooltip: without it, the "?" popup disappears from the row."""
        for modo in (False, True):
            for slot, campo in (("inplane", '"mu_x"'), ("axial", '"Vz"')):
                with self.subTest(propeller=modo, slot=slot):
                    _rotulo, dica = rotulo_e_dica_de_condicao(modo, slot)
                    self.assertTrue(dica.startswith(campo), dica[:40])

    def test_dica_de_helice_diz_que_o_campo_cruzado_e_zero_em_cruzeiro(self):
        """The mistake this help exists to prevent: putting the
        aircraft's speed in the in-plane field. It has to say that field
        is zero in straight cruise -- and where the speed goes instead."""
        _rotulo, dica = rotulo_e_dica_de_condicao(True, "inplane")
        # The requirement is what the sentence SAYS, not how it opens:
        # the text comes from `nomenclature`, which may word it as
        # "In straight cruise ...".
        self.assertIn("straight cruise", dica.lower())
        self.assertIn("V<sub>z</sub> = 0", dica)
        self.assertIn("axial field below", dica)

    def test_dica_de_helice_traz_o_J_classico_no_campo_axial(self):
        """J_x = V/(nD) with V AXIAL is the J_x from propeller charts --
        and it is the field's default. The help has to bring the formula,
        otherwise the user does not know whether this is it or the
        in-plane pi*mu_x."""
        _rotulo, dica = rotulo_e_dica_de_condicao(True, "axial")
        self.assertIn("V/(nD)", dica)
        self.assertIn("AXIAL", dica)

    def test_dica_de_helice_explica_alpha_a_partir_do_EIXO(self):
        """In propeller axes the angle is measured from the AXIS: 0° is
        aligned cruise. It lives in the in-plane field because it is the
        one that, from the known axial value, produces the cross-flow
        one."""
        _rotulo, dica = rotulo_e_dica_de_condicao(True, "inplane")
        self.assertIn("&alpha;<sub>disk</sub>", dica)
        self.assertIn("shaft", dica)
        # The tooltip is rich text, so the degree sign may be the entity.
        self.assertTrue("0°" in dica or "0&deg;" in dica,
                        "the tooltip does not state that 0 degrees is aligned flow")


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRotulosNaJanela(unittest.TestCase):
    """The real labels, on the assembled window, switching mode."""

    @classmethod
    def setUpClass(cls):
        from zbemt.gui.app import MainWindow
        from tests.helpers import make_studies_project
        cls.app = QApplication.instance() or QApplication([])
        cls.win = MainWindow()
        cls.win.state.set_project(make_studies_project())
        cls.abas = {cls.win.tabs.tabText(i).replace("*", "").strip(): cls.win.tabs.widget(i)
                    for i in range(cls.win.tabs.count())}

    @classmethod
    def tearDownClass(cls):
        # see `tests/test_airfoil_geometry.py`: `close()` on a window
        # that went through several state changes freezes the process on
        # this machine; hiding it is enough to not interfere with the next
        # test file. But `hide()` alone leaves the actual C++-side teardown
        # to whatever order Python's interpreter-shutdown GC happens to run
        # in -- which is what crashed the process (access violation) right
        # after the last test here. Force it now instead, while the
        # QApplication and event loop are still in a known-good state.
        cls.win.hide()
        win, cls.win = cls.win, None
        win.deleteLater()
        cls.app.processEvents()
        del win
        import gc
        gc.collect()

    def _redefinir_modo(self, propeller: bool):
        """Enters the mode coming from the OTHER one, so that the unit
        combos get rebuilt.

        The window is shared by the whole class (`setUpClass`), and
        `set_default_unit` purposely respects the unit the user chose by
        hand within a mode: without the round trip, an earlier test that
        changed the unit leaves its choice still in effect here."""
        self._definir_modo(not propeller)
        self._definir_modo(propeller)

    def _definir_modo(self, propeller: bool):
        self.win.state.project.config["is_propeller"] = propeller
        self.win.state.mode_changed.emit()
        self.app.processEvents()

    def _rotulo(self, form, campo) -> str:
        alvo = getattr(campo, "_container_de_ajuda", None) or campo
        linha, _papel = form.getWidgetPosition(alvo)
        item = form.itemAt(linha, QFormLayout.ItemRole.LabelRole)
        return item.widget().text() if item is not None and item.widget() else ""

    def test_run_case_troca_os_dois_rotulos(self):
        """The row LABEL describes the axis (fixed by design); it is the
        unit combo within it that brings Jₓ/Cross etc. -- see
        `test_o_avanco_da_helice_e_oferecido_no_campo_AXIAL`."""
        aba = self.abas["Run Case"]
        self._definir_modo(False)
        rotor = (self._rotulo(aba._condition_form, aba.advance),
                 self._rotulo(aba._condition_form, aba.axial))
        self._definir_modo(True)
        helice = (self._rotulo(aba._condition_form, aba.advance),
                  self._rotulo(aba._condition_form, aba.axial))
        self.assertNotEqual(rotor, helice)
        self.assertIn("axial", helice[1].lower())
        self.assertIn("Cross", helice[0])

    def test_run_batch_troca_valores_fixos_e_linha_avulsa(self):
        aba = self.abas["Run Batch"]
        self._definir_modo(True)
        self.assertIn("axial", self._rotulo(aba._fixed_form, aba.fixed_axial).lower())
        self.assertIn("axial", self._rotulo(aba._avulso_form, aba.add_row_axial).lower())
        self.assertIn("Cross", self._rotulo(aba._fixed_form, aba.fixed_advance))

    def test_slots_de_eixo_seguem_a_convencao(self):
        """`axis_rows[i]` is (slot_combo, unit_combo, values_edit) -- what
        brings Jₓ/μₓ is the UNIT combo of the "axial" slot, not the slot
        combo itself (which only lists the axis NAMES -- "Axial
        (along-shaft) Flow" in both modes, see
        `test_run_case_troca_os_dois_rotulos`). This test used to check
        `axis_rows[0][0]` (the slot combo) instead of `axis_rows[0][1]`
        (the unit combo) and could never have passed, in either mode --
        this is not a regression from this session."""
        aba = self.abas["Run Batch"]
        slot_combo, unit_combo, _valores = aba.axis_rows[0]
        indice_axial = next(i for i, (_r, s) in enumerate(aba._AXIS_SLOTS)
                             if s == "axial")
        self._definir_modo(True)
        slot_combo.setCurrentIndex(indice_axial)
        textos = [unit_combo.itemText(i) for i in range(unit_combo.count())]
        self.assertTrue(any("Jₓ" in t for t in textos), textos)
        self._definir_modo(False)
        slot_combo.setCurrentIndex(indice_axial)
        textos = [unit_combo.itemText(i) for i in range(unit_combo.count())]
        self.assertTrue(any(t.startswith("α") for t in textos), textos)

    def test_o_avanco_da_helice_e_oferecido_no_campo_AXIAL(self):
        """The bug this batch fixes: in propeller mode, J_x used to be in
        the IN-PLANE field. There J_x = pi*mu_x is the edgewise ratio --
        anyone typing 0.8 expecting the J_x from propeller charts would
        get an entirely different condition, and no velocity along the
        shaft at all.

        The unit labels use real unicode subscripts
        (`widgets.UNIDADES_DE_CONDICAO`): Jₓ/μₓ/Vₓ on the x axis, but
        V_z/μ_z/J_z with a literal underscore on the z axis -- the same
        asymmetry that prompted the report to the user in this session."""
        aba = self.abas["Run Case"]
        self._redefinir_modo(True)
        axiais = [aba.axial.unit_combo.itemText(i)
                  for i in range(aba.axial.unit_combo.count())]
        planos = [aba.advance.unit_combo.itemText(i)
                  for i in range(aba.advance.unit_combo.count())]
        self.assertIn("Jₓ", axiais)
        self.assertEqual(aba.axial.unit_combo.currentText(), "Jₓ")
        self.assertNotIn("Jₓ", planos)        # the axial J_x does not live here
        self.assertIn("V_z [m/s]", planos)

    def test_o_campo_axial_da_helice_nao_oferece_angulo(self):
        """`Vz = tan(alpha)*V_in-plane` is ZERO in every straight axial
        flight: the disk angle cannot express a propeller's most common
        condition. Whoever wants an angle uses alpha_disk, in the
        in-plane field."""
        aba = self.abas["Run Case"]
        self._redefinir_modo(True)
        axiais = [aba.axial.unit_combo.itemText(i)
                  for i in range(aba.axial.unit_combo.count())]
        self.assertFalse([t for t in axiais if t.startswith("alpha")
                           or t.startswith("α")], axiais)
        planos = [aba.advance.unit_combo.itemText(i)
                  for i in range(aba.advance.unit_combo.count())]
        self.assertIn("α_dᵢₛₖ [deg]", planos)

    def test_J_x_no_campo_axial_produz_velocidade_axial(self):
        """The end-to-end test of the inversion: J_x=0.8 has to turn into
        a positive `Vz` and a null `mu_x` -- not the other way around."""
        aba = self.abas["Run Case"]
        self._redefinir_modo(True)
        aba.axial.unit_combo.setCurrentText("J_x")
        aba.axial.spin.setValue(0.8)
        aba.advance.spin.setValue(0.0)
        cond = aba._current_condition()
        self.assertAlmostEqual(cond.mu_x, 0.0, places=9)
        self.assertGreater(cond.Vz, 0.0)

    def test_alpha_disk_deriva_o_cruzado_do_axial(self):
        """With alpha_disk in the in-plane field, it is the axial one
        that fixes the scale -- so the resolution order inverts
        (`resolver_par_de_condicao`). Solved in the old order, mu_x would
        come from a Vz not yet read.

        `setCurrentText` with the old ASCII text ("Vx [m/s]") used to
        fail SILENTLY against the real item ("Vₓ [m/s]", unicode
        subscript): the combo stayed at the default (Jₓ) instead of
        changing, and the rest of the test read the wrong field -- the
        real cause of the 1200.0 != 60.0 this test used to give."""
        aba = self.abas["Run Case"]
        self._redefinir_modo(True)
        aba.axial.unit_combo.setCurrentText("Vₓ [m/s]")
        aba.axial.spin.setValue(60.0)
        aba.advance.unit_combo.setCurrentText("α_dᵢₛₖ [deg]")
        aba.advance.spin.setValue(0.0)
        self.assertAlmostEqual(aba._current_condition().mu_x, 0.0, places=9)
        aba.advance.spin.setValue(10.0)
        cond = aba._current_condition()
        self.assertGreater(cond.mu_x, 0.0)
        self.assertAlmostEqual(cond.Vz, 60.0, places=6)

    def test_voltar_para_rotor_restaura_as_unidades_de_rotor(self):
        aba = self.abas["Run Case"]
        self._redefinir_modo(True)
        self._definir_modo(False)
        planos = [aba.advance.unit_combo.itemText(i)
                  for i in range(aba.advance.unit_combo.count())]
        axiais = [aba.axial.unit_combo.itemText(i)
                  for i in range(aba.axial.unit_combo.count())]
        self.assertEqual(planos, ["μₓ", "Jₓ", "Vₓ [m/s]"])
        self.assertEqual(axiais, ["αᵣₒₜₒᵣ [deg]", "V_z [m/s]",
                                   "μ_z", "J_z"])

    def test_trocar_de_modo_preserva_a_condicao_fisica(self):
        """Rotating the letters cannot move the velocity from one axis to
        the other: the same (mu_x, Vz) before and after -- to 3 places,
        not 6: the mode round-trip goes through the spinbox's displayed
        text (few decimal places), so a difference on the order of 1e-4
        is display quantization, not loss of physical precision."""
        aba = self.abas["Run Case"]
        self._definir_modo(False)
        aba.advance.set_mu(0.15)
        antes = aba._current_condition()
        self._definir_modo(True)
        depois = aba._current_condition()
        self.assertAlmostEqual(depois.mu_x, antes.mu_x, places=3)
        self.assertAlmostEqual(depois.Vz, antes.Vz, places=3)

    def test_eixo_axial_da_helice_varre_J_x(self):
        aba = self.abas["Run Batch"]
        self._redefinir_modo(True)
        slot_combo, unit_combo, _valores = aba.axis_rows[0]
        slot_combo.setCurrentIndex(next(i for i, (_r, s) in enumerate(aba._AXIS_SLOTS)
                                         if s == "axial"))
        unidades = [unit_combo.itemText(i) for i in range(unit_combo.count())]
        self.assertEqual(unidades, ["Jₓ", "μₓ", "Vₓ [m/s]"])
        # and the variable that goes to `studies` is the ENGINE's, not the label
        self.assertEqual(aba._axis_variable(slot_combo, unit_combo), "J_z")

    def test_trocar_de_modo_nao_perde_a_escolha_do_eixo(self):
        """Only the LABEL changes: the slot chosen on each row stays the
        same (it is what decides what goes into the condition)."""
        aba = self.abas["Run Batch"]
        combo = aba.axis_rows[0][0]
        self._definir_modo(False)
        combo.setCurrentIndex(next(i for i, (_r, s) in enumerate(aba._AXIS_SLOTS)
                                   if s == "axial"))
        antes = aba._slot_do_combo(combo)
        self._definir_modo(True)
        self.assertEqual(aba._slot_do_combo(combo), antes)


if __name__ == "__main__":
    unittest.main()
