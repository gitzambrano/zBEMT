"""`zbemt/nomenclature.py` -- the single source of the axis nomenclature.

The rotor/propeller letter swap used to be re-implemented by hand in ten
places (`api._SIMBOLO_DE_COLUNA_HELICE`, `plots._SUMMARY_KEY_LABELS_HELICE`,
`studies._SIMBOLO_DE_VARIAVEL_HELICE`, `widgets.UNIDADES_DE_CONDICAO`,
`common._ROTULOS_DE_CONDICAO`, ...), each claiming to be the single source
for its own surface. These tests lock in the properties that make ONE table
able to replace all of them.
"""
import unittest

from zbemt import nomenclature as nm


class TestAxisQuantityTable(unittest.TestCase):
    """Every axis quantity the engine emits has an entry, in both modes."""

    #: Keys of `Results.summary` whose letter depends on the mode, plus the
    #: ones that deliberately do NOT rotate but still belong to the flight
    #: condition (so a missing entry is a failure, not a silent fallback).
    CHAVES_DE_EIXO = (
        "mu_x", "J_x", "Vx",
        "mu_z", "J_z", "Vz", "lambda_z", "Vz_total",
        "alpha_rotor_deg", "alpha_disk_deg",
        "Vi", "lambda_i", "lambda_total",
    )

    #: Variable names used by the factorial sweep and the GUI unit combos.
    #: `alpha_deg`/`alpha_disk` are the input spellings of
    #: `alpha_rotor_deg`/`alpha_disk_deg`.
    VARIAVEIS_DE_ENTRADA = (
        "mu_x", "J_x", "Vx", "alpha_disk",
        "alpha_deg", "Vz", "mu_z", "J_z",
    )

    def test_every_axis_key_has_an_entry(self):
        for chave in self.CHAVES_DE_EIXO:
            with self.subTest(chave=chave):
                self.assertIn(chave, nm.QUANTITIES)

    def test_every_input_variable_has_an_entry(self):
        for variavel in self.VARIAVEIS_DE_ENTRADA:
            with self.subTest(variavel=variavel):
                self.assertIn(variavel, nm.QUANTITIES)

    def test_every_accessor_resolves_in_both_modes(self):
        for chave in self.CHAVES_DE_EIXO + self.VARIAVEIS_DE_ENTRADA:
            for prop in (False, True):
                with self.subTest(chave=chave, propeller=prop):
                    self.assertTrue(nm.symbol_latex(chave, prop))
                    self.assertTrue(nm.symbol_mathtext(chave, prop))
                    self.assertTrue(nm.symbol_html(chave, prop))
                    self.assertTrue(nm.symbol_text(chave, prop))
                    self.assertIsInstance(nm.unit(chave), str)
                    self.assertIsInstance(nm.is_visible(chave, prop), bool)
                    self.assertIn(nm.slot_of(chave),
                                  ("inplane", "axial", "invariant"))

    def test_unknown_key_never_raises(self):
        """A new engine key must degrade to its own name, not crash the
        report -- the same fallback the old tables had."""
        self.assertEqual(nm.symbol_text("cfg_brand_new", False), "cfg_brand_new")
        self.assertEqual(nm.unit("cfg_brand_new"), "")
        self.assertTrue(nm.is_visible("cfg_brand_new", True))
        self.assertEqual(nm.display_key("cfg_brand_new", True), "cfg_brand_new")

    def test_each_mode_shows_exactly_one_angle(self):
        self.assertTrue(nm.is_visible("alpha_rotor_deg", False))
        self.assertFalse(nm.is_visible("alpha_disk_deg", False))
        self.assertFalse(nm.is_visible("alpha_rotor_deg", True))
        self.assertTrue(nm.is_visible("alpha_disk_deg", True))

    def test_units_do_not_rotate(self):
        """The letters rotate; the physics does not. A velocity is in m/s
        in both modes."""
        self.assertEqual(nm.unit("Vz"), "m/s")
        self.assertEqual(nm.unit("mu_x"), "-")
        self.assertEqual(nm.unit("alpha_disk_deg"), "deg")


class TestKeyRotation(unittest.TestCase):
    """The swap is a SIMULTANEOUS remap, and it is reversible."""

    def test_rotor_mode_is_the_identity(self):
        for chave in TestAxisQuantityTable.CHAVES_DE_EIXO:
            with self.subTest(chave=chave):
                self.assertEqual(nm.display_key(chave, False), chave)

    def test_propeller_rotates_the_letter(self):
        self.assertEqual(nm.display_key("Vz", True), "Vx")
        self.assertEqual(nm.display_key("Vx", True), "Vz")
        self.assertEqual(nm.display_key("mu_x", True), "mu_z")
        self.assertEqual(nm.display_key("mu_z", True), "mu_x")
        self.assertEqual(nm.display_key("J_x", True), "J_z")
        self.assertEqual(nm.display_key("J_z", True), "J_x")
        self.assertEqual(nm.display_key("lambda_z", True), "lambda_x")
        self.assertEqual(nm.display_key("Vz_total", True), "Vx_total")

    def test_induced_quantities_never_rotate(self):
        """`v_i` is along the shaft in both modes -- only the letter naming
        that shaft changes, and `Vi` does not carry a letter."""
        for chave in ("Vi", "lambda_i", "lambda_total", "CT", "FM", "cfg_rho"):
            with self.subTest(chave=chave):
                self.assertEqual(nm.display_key(chave, True), chave)

    def test_swap_is_simultaneous_not_sequential(self):
        """The collision case: applying `mu_x -> mu_z` and then
        `mu_z -> mu_x` key by key would collapse both onto one value.
        Both must survive, with their own numbers."""
        engine = {"mu_x": 0.05, "mu_z": 0.30, "Vx": 3.0, "Vz": 65.0}
        display = nm.to_display_keys(engine, True)
        self.assertEqual(display, {"mu_z": 0.05, "mu_x": 0.30,
                                   "Vz": 3.0, "Vx": 65.0})

    def test_round_trip_is_lossless(self):
        engine = {"mu_x": 0.05, "mu_z": 0.30, "J_x": 0.16, "J_z": 0.94,
                  "Vx": 3.0, "Vz": 65.0, "Vz_total": 70.0, "lambda_z": 0.30,
                  "Vi": 5.0, "lambda_i": 0.02, "CT": 0.008, "cfg_rho": 1.225}
        for prop in (False, True):
            with self.subTest(propeller=prop):
                self.assertEqual(
                    nm.from_display_keys(nm.to_display_keys(engine, prop), prop),
                    engine)

    def test_rotation_does_not_mutate_its_input(self):
        engine = {"mu_x": 0.05, "Vz": 65.0}
        copia = dict(engine)
        nm.to_display_keys(engine, True)
        self.assertEqual(engine, copia)

    def test_engine_key_of_inverts_display_key(self):
        for chave in TestAxisQuantityTable.CHAVES_DE_EIXO:
            for prop in (False, True):
                with self.subTest(chave=chave, propeller=prop):
                    self.assertEqual(
                        nm.engine_key_of(nm.display_key(chave, prop), prop), chave)


class TestRenderTargets(unittest.TestCase):
    """One LaTeX source, three renderings -- the reason a second (and third)
    label list does not need to exist."""

    def test_latex_is_the_source(self):
        self.assertEqual(nm.symbol_latex("mu_x", False), r"\mu_x")
        self.assertEqual(nm.symbol_latex("mu_x", True), r"\mu_z")

    def test_html_matches_the_old_hand_written_entities(self):
        self.assertEqual(nm.symbol_html("mu_x", False), "&mu;<sub>x</sub>")
        self.assertEqual(nm.symbol_html("mu_x", True), "&mu;<sub>z</sub>")
        self.assertEqual(nm.symbol_html("alpha_rotor_deg", False),
                         "&alpha;<sub>rotor</sub>")
        self.assertEqual(nm.symbol_html("Vz_total", False), "V<sub>z,total</sub>")
        self.assertEqual(nm.symbol_html("Vi", False), "v<sub>i</sub>")

    def test_mathtext_matches_the_old_plot_labels(self):
        self.assertEqual(nm.symbol_mathtext("mu_x", False), r"$\mu_x$ [-]")
        self.assertEqual(nm.symbol_mathtext("Vz", True), r"$V_x$ [m/s]")
        self.assertEqual(nm.symbol_mathtext("alpha_disk_deg", True),
                         r"$\alpha_{disk}$ [deg]")

    def test_a_name_keeps_letter_subscripts_on_the_line(self):
        """A condition name becomes a file name through
        `api.sanitize_filename`, whose ASCII transcription knows Greek and
        subscript digits but not "ₓ"."""
        self.assertEqual(nm.symbol_name("mu_x", False), "μ_x")
        self.assertEqual(nm.symbol_name("collective_deg", False), "θ₀")
        self.assertTrue(nm.symbol_name("alpha_deg", False).endswith("_rotor"))

    def test_unicode_text_for_plain_widgets(self):
        self.assertEqual(nm.symbol_text("mu_x", False), "μₓ")
        self.assertEqual(nm.symbol_text("J_z", True), "Jₓ")

    def test_every_entry_renders_without_leftover_latex(self):
        """A stray `$` or backslash reaching a QLabel is the bug this
        conversion exists to prevent."""
        for chave in nm.QUANTITIES:
            for prop in (False, True):
                with self.subTest(chave=chave, propeller=prop):
                    self.assertNotIn("$", nm.symbol_text(chave, prop))
                    self.assertNotIn("\\", nm.symbol_text(chave, prop))
                    self.assertNotIn("$", nm.symbol_html(chave, prop))
                    self.assertNotIn("\\", nm.symbol_html(chave, prop))


class TestDescriptions(unittest.TestCase):
    def test_every_quantity_has_a_description_in_both_modes(self):
        for chave in TestAxisQuantityTable.CHAVES_DE_EIXO:
            for prop in (False, True):
                with self.subTest(chave=chave, propeller=prop):
                    self.assertTrue(nm.description_html(chave, prop).strip())

    def test_description_uses_symbols_not_raw_field_names(self):
        """The description is user-facing text: `mu_x` must reach the screen
        as a symbol, never as a snake_case field name."""
        for chave in TestAxisQuantityTable.CHAVES_DE_EIXO:
            for prop in (False, True):
                texto = nm.description_html(chave, prop)
                with self.subTest(chave=chave, propeller=prop):
                    self.assertNotIn("mu_x", texto)
                    self.assertNotIn("alpha_rotor_deg", texto)


class TestSlots(unittest.TestCase):
    def test_slot_membership_matches_the_engine_decomposition(self):
        for chave in ("mu_x", "J_x", "Vx", "alpha_disk"):
            with self.subTest(chave=chave):
                self.assertEqual(nm.slot_of(chave), "inplane")
        for chave in ("mu_z", "J_z", "Vz", "lambda_z", "alpha_deg", "Vz_total"):
            with self.subTest(chave=chave):
                self.assertEqual(nm.slot_of(chave), "axial")

    def test_both_slots_are_labelled_in_both_modes(self):
        for slot in ("inplane", "axial"):
            for prop in (False, True):
                with self.subTest(slot=slot, propeller=prop):
                    rotulo, dica = nm.slot_label(slot, prop)
                    self.assertTrue(rotulo.strip())
                    self.assertTrue(dica.strip())

    def test_the_in_plane_slot_is_named_for_what_it_carries(self):
        """A propeller's in-plane slot is the CROSS flow, not the advance --
        naming it "advance" is what used to make users put the airspeed
        there and silently solve an edgewise rotor."""
        self.assertIn("edgewise", nm.slot_label("inplane", False)[0].lower())
        self.assertIn("cross", nm.slot_label("inplane", True)[0].lower())


class TestPrimaryOrder(unittest.TestCase):
    def test_primary_order_leads_with_the_x_component_of_each_mode(self):
        """x is the mode's PRIMARY component: a helicopter's advance, a
        propeller's airspeed. It reads first in both."""
        self.assertEqual(nm.primary_order(False)[0], "mu_x")
        self.assertEqual(nm.primary_order(True)[0], "mu_z")

    def test_primary_order_hides_the_other_mode_angle(self):
        self.assertIn("alpha_rotor_deg", nm.primary_order(False))
        self.assertNotIn("alpha_disk_deg", nm.primary_order(False))
        self.assertIn("alpha_disk_deg", nm.primary_order(True))
        self.assertNotIn("alpha_rotor_deg", nm.primary_order(True))


class TestConditionLabel(unittest.TestCase):
    def test_rotor_names_the_in_plane_component_x(self):
        self.assertEqual(nm.condition_label({"mu_x": 0.1}, False), "μ_x=0.1")

    def test_propeller_names_the_axial_component_x(self):
        self.assertEqual(nm.condition_label({"mu_z": 0.3}, True), "μ_x=0.3")
        self.assertEqual(nm.condition_label({"mu_x": 0.05}, True), "μ_z=0.05")

    def test_units_are_appended(self):
        self.assertEqual(nm.condition_label({"Vz": 65.0}, False), "V_z=65 m/s")
        self.assertEqual(nm.condition_label({"alpha_deg": -10.0}, False),
                         "α_rotor=-10°")

    def test_each_mode_names_only_its_own_angle(self):
        """`alpha_deg` and `alpha_disk` are the same angle from different
        references, and each mode names only its own."""
        self.assertEqual(nm.condition_label({"alpha_disk": 2.0}, True),
                         "α_disk=2°")
        self.assertEqual(nm.condition_label({"alpha_deg": -10.0}, False),
                         "α_rotor=-10°")

    def test_unknown_variable_falls_back_to_its_own_name(self):
        self.assertEqual(nm.condition_label({"novo_eixo": 3}, False),
                         "novo_eixo=3")

    def test_order_follows_the_caller(self):
        self.assertEqual(
            nm.condition_label({"mu_x": 0.1, "collective_deg": 8.0}, False),
            "μ_x=0.1, θ₀=8°")


if __name__ == "__main__":
    unittest.main()
