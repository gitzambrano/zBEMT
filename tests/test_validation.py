"""Verify validation of airfoils, configurations, projects, and flight conditions.

The tests supply valid and invalid combinations and assert error, warning, and
informational records, including extrapolation, multi-section, Mach, and zero-speed
limits. Validation is expected to be pure: no solver run or persistent file is
required.
"""

import unittest
from dataclasses import asdict

from zbemt import airfoils
from zbemt import bemt
from zbemt import validation
from zbemt.models import AirfoilDef, FlightCondition, PolarSlice, ProfileGeometry
from zbemt.bemt import BEMTConfig


def levels(issues):
    return [i.level for i in issues]


class TestValidateAirfoilDef(unittest.TestCase):
    def test_clean_default_has_no_errors(self):
        # default: source='analytical', stall_model='linear', tudo desligado
        issues = validation.validate_airfoil_def(AirfoilDef())
        self.assertNotIn("error", levels(issues))

    def test_dynamic_stall_with_linear_model_is_error(self):
        a = AirfoilDef(use_dynamic_stall=True, source="analytical", stall_model="linear")
        issues = validation.validate_airfoil_def(a)
        self.assertIn("error", levels(issues))

    def test_dynamic_stall_with_clip_model_is_clean(self):
        a = AirfoilDef(use_dynamic_stall=True, source="analytical", stall_model="clip",
                        alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        issues = validation.validate_airfoil_def(a)
        self.assertNotIn("error", levels(issues))

    def test_extend_full_range_on_analytical_is_clean(self):
        a = AirfoilDef(source="analytical", extend_full_range=True)
        issues = validation.validate_airfoil_def(a)
        self.assertNotIn("error", levels(issues))

    def test_extend_full_range_on_external_is_info(self):
        a = AirfoilDef(source="external", extend_full_range=True,
                        geometry=ProfileGeometry(source="naca4", naca_code="0012"))
        issues = validation.validate_airfoil_def(a)
        self.assertIn("info", levels(issues))

    def test_table_source_without_slices_is_error(self):
        a = AirfoilDef(source="table", table_slices=[])
        issues = validation.validate_airfoil_def(a)
        self.assertIn("error", levels(issues))

    def test_external_engine_without_geometry_is_error(self):
        a = AirfoilDef(external_engine="neuralfoil", geometry=None)
        issues = validation.validate_airfoil_def(a)
        self.assertIn("error", levels(issues))

    def test_external_engine_with_geometry_ok(self):
        a = AirfoilDef(external_engine="neuralfoil", geometry=ProfileGeometry(source="naca4", naca_code="0012"))
        issues = validation.validate_airfoil_def(a)
        self.assertNotIn("error", levels(issues))

    def test_time_march_params_edited_but_frequency_active_is_info(self):
        a = AirfoilDef(use_dynamic_stall=True, stall_model="clip", dynamic_stall_method="frequency",
                        dynamic_stall_time_march_revolutions=20)
        issues = validation.validate_airfoil_def(a)
        self.assertIn("info", levels(issues))

    def test_fade_start_after_fade_end_is_error(self):
        a = AirfoilDef(use_dynamic_stall=True, stall_model="clip",
                        dynamic_stall_fade_start_deg=60.0, dynamic_stall_fade_end_deg=50.0)
        issues = validation.validate_airfoil_def(a)
        self.assertIn("error", levels(issues))

    def test_stall_angles_wrong_sign_is_warning(self):
        a = AirfoilDef(stall_model="clip", alpha_stall_pos_deg=-15.0, alpha_stall_neg_deg=6.0)
        issues = validation.validate_airfoil_def(a)
        self.assertIn("warning", levels(issues))


class TestValidateConfig(unittest.TestCase):
    def test_pitt_peters_steady_is_clean(self):
        cfg = asdict(BEMTConfig(inflow_field_model="pitt_peters_steady"))
        issues = validation.validate_config(cfg, AirfoilDef())
        self.assertEqual(levels(issues), [])

    def test_local_coupling_with_coleman_is_clean(self):
        cfg = asdict(BEMTConfig(inflow_field_model="coleman_local"))
        issues = validation.validate_config(cfg, AirfoilDef())
        self.assertEqual(levels(issues), [])

    def test_dynamic_stall_with_pitt_peters_unsteady_is_error(self):
        cfg = asdict(BEMTConfig(inflow_field_model="pitt_peters_unsteady"))
        a = AirfoilDef(use_dynamic_stall=True, stall_model="clip")
        issues = validation.validate_config(cfg, a)
        self.assertIn("error", levels(issues))

    def test_compressibility_with_mach_varying_table_is_warning(self):
        a = AirfoilDef(source="table", table_slices=[
            PolarSlice(alpha_deg=[0], cl=[0], cd=[0.01], mach=0.0),
            PolarSlice(alpha_deg=[0], cl=[0], cd=[0.01], mach=0.5),
        ])
        cfg = asdict(BEMTConfig(use_compressibility=True))
        issues = validation.validate_config(cfg, a)
        self.assertIn("warning", levels(issues))

    def test_viterna_full_range_without_extended_airfoil_is_error(self):
        cfg = asdict(BEMTConfig(reverse_flow_model="viterna_full_range"))
        issues = validation.validate_config(cfg, AirfoilDef(stall_model="linear"))
        self.assertIn("error", levels(issues))

    def test_viterna_full_range_with_extension_is_clean(self):
        cfg = asdict(BEMTConfig(reverse_flow_model="viterna_full_range"))
        issues = validation.validate_config(cfg, AirfoilDef(extend_full_range=True))
        self.assertNotIn("error", levels(issues))

    def test_pitt_peters_states_5_is_error_not_implemented(self):
        cfg = asdict(BEMTConfig(pitt_peters_states=5))
        issues = validation.validate_config(cfg, AirfoilDef())
        self.assertIn("error", levels(issues))

    def test_pitt_peters_states_invalid_value_is_error(self):
        cfg = asdict(BEMTConfig())
        cfg["pitt_peters_states"] = 4
        issues = validation.validate_config(cfg, AirfoilDef())
        self.assertIn("error", levels(issues))

    def test_pitt_peters_states_3_is_clean(self):
        cfg = asdict(BEMTConfig(pitt_peters_states=3))
        issues = validation.validate_config(cfg, AirfoilDef())
        self.assertNotIn("error", levels(issues))

    def test_is_propeller_with_external_engine_is_info(self):
        cfg = asdict(BEMTConfig(is_propeller=True))
        a = AirfoilDef(external_engine="neuralfoil", geometry=ProfileGeometry())
        issues = validation.validate_config(cfg, a)
        self.assertIn("info", levels(issues))


class TestValidateProject(unittest.TestCase):
    def test_combines_both_lists(self):
        cfg = asdict(BEMTConfig(pitt_peters_states=5))
        a = AirfoilDef(source="table", table_slices=[])
        issues = validation.validate_project(cfg, a)
        # ao menos um erro de cada lado (airfoil: table sem slices; config: pp_states=5)
        messages = " ".join(i.message for i in issues)
        self.assertIn("table_slices", messages)
        self.assertIn("Peters-He", messages)

    def test_issue_str_has_level_tag(self):
        issue = validation.Issue("error", "algo deu errado")
        self.assertTrue(str(issue).startswith("[ERROR]"))


class TestExtendFullRangeMultiSectionTable(unittest.TestCase):
    """extend_full_range with multi-section table: supported since the fix
    in bemt.ViternaExtendedAirfoil (a Viterna extrapolation per radial section,
    anchored to the Cl_stall/Cd_stall of that section) -- should no longer
    be blocked by validate_airfoil_def."""

    def _multi_section_slices(self):
        return [
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.2, 0.7], cd=[0.02, 0.015, 0.02], r_norm=0.3),
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.2, 0.3, 0.8], cd=[0.018, 0.014, 0.019], r_norm=0.9),
        ]

    def test_multi_section_with_extend_full_range_is_clean(self):
        a = AirfoilDef(source="table", extend_full_range=True, table_slices=self._multi_section_slices())
        issues = validation.validate_airfoil_def(a)
        self.assertNotIn("error", levels(issues))

    def test_multi_section_without_extend_full_range_is_clean(self):
        a = AirfoilDef(source="table", extend_full_range=False, table_slices=self._multi_section_slices())
        issues = validation.validate_airfoil_def(a)
        self.assertNotIn("error", levels(issues))

    def test_single_section_with_extend_full_range_is_clean(self):
        a = AirfoilDef(source="table", extend_full_range=True, table_slices=[
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.2, 0.7], cd=[0.02, 0.015, 0.02]),
        ])
        issues = validation.validate_airfoil_def(a)
        self.assertNotIn("error", levels(issues))


class TestValidateAirfoilSections(unittest.TestCase):
    """Phase D (docs/plano.md GUI v3, Section 4): checks for
    Project.airfoil_sections (multi-section airfoil)."""

    def test_empty_list_is_clean(self):
        self.assertEqual(validation.validate_airfoil_sections([]), [])

    def test_single_section_is_error(self):
        issues = validation.validate_airfoil_sections([AirfoilDef(name="raiz", r_norm=0.15)])
        self.assertIn("error", levels(issues))

    def test_two_valid_sections_is_clean(self):
        sections = [
            AirfoilDef(name="raiz", r_norm=0.15, extend_full_range=False),
            AirfoilDef(name="ponta", r_norm=1.0, extend_full_range=False),
        ]
        issues = validation.validate_airfoil_sections(sections)
        self.assertNotIn("error", levels(issues))

    def test_missing_r_norm_is_error(self):
        sections = [
            AirfoilDef(name="raiz", r_norm=0.15),
            AirfoilDef(name="ponta", r_norm=None),
        ]
        issues = validation.validate_airfoil_sections(sections)
        self.assertIn("error", levels(issues))

    def test_duplicate_r_norm_is_error(self):
        sections = [
            AirfoilDef(name="a", r_norm=0.5),
            AirfoilDef(name="b", r_norm=0.5),
        ]
        issues = validation.validate_airfoil_sections(sections)
        self.assertIn("error", levels(issues))

    def test_r_norm_out_of_range_is_warning(self):
        sections = [
            AirfoilDef(name="a", r_norm=-0.1, extend_full_range=False),
            AirfoilDef(name="b", r_norm=1.0, extend_full_range=False),
        ]
        issues = validation.validate_airfoil_sections(sections)
        self.assertIn("warning", levels(issues))
        self.assertNotIn("error", levels(issues))

    def test_dynamic_stall_in_section_is_supported_no_warning(self):
        """Dynamic stall per section is supported (see bemt.py
        apply_dynamic_stall/_dynamic_stall_section_param) -- should not generate
        a "ignored" warning as in previous versions."""
        sections = [
            AirfoilDef(name="a", r_norm=0.15, stall_model="clip", use_dynamic_stall=True,
                       extend_full_range=False),
            AirfoilDef(name="b", r_norm=1.0, extend_full_range=False),
        ]
        issues = validation.validate_airfoil_sections(sections)
        self.assertFalse(any("ignorado" in i.message for i in issues))

    def test_validate_project_uses_sections_when_present(self):
        sections = [
            AirfoilDef(name="a", r_norm=0.5),
            AirfoilDef(name="b", r_norm=0.5),   # duplicado -> erro
        ]
        issues = validation.validate_project({}, AirfoilDef(), sections)
        self.assertIn("error", levels(issues))

    def test_validate_project_falls_back_to_single_airfoil_when_no_sections(self):
        issues = validation.validate_project({}, AirfoilDef(), [])
        issues_direct = validation.validate_project({}, AirfoilDef())
        self.assertEqual([str(i) for i in issues], [str(i) for i in issues_direct])


class TestValidateFlightCondition(unittest.TestCase):
    """Missing RPM falls back to a 1000 placeholder and zero RPM breaks the
    Omega*R nondimensionalization -- neither is visible looking only at
    config/airfoil, so it needs its own check."""

    def test_rpm_positivo_nao_gera_issue(self):
        cond = FlightCondition(name="ok", mu_x=0.1, collective_deg=8.0, rpm=300.0)
        self.assertEqual(validation.validate_flight_condition(cond), [])

    def test_rpm_ausente_e_erro(self):
        """RPM is required -- there is no physically defensible default,
        because BEMT nondimensionalizes everything by Omega*R."""
        cond = FlightCondition(name="sem_rpm", mu_x=0.1, collective_deg=8.0)
        issues = validation.validate_flight_condition(cond)
        self.assertEqual(levels(issues), ["error"])

    def test_rpm_zero_ou_negativo_e_erro(self):
        for rpm in (0.0, -5.0):
            with self.subTest(rpm=rpm):
                cond = FlightCondition(name="ruim", mu_x=0.1, collective_deg=8.0, rpm=rpm)
                issues = validation.validate_flight_condition(cond)
                self.assertEqual(levels(issues), ["error"])

    def test_rpm_nao_finito_e_erro(self):
        cond = FlightCondition(name="nan", mu_x=0.1, collective_deg=8.0, rpm=float("nan"))
        self.assertEqual(levels(validation.validate_flight_condition(cond)), ["error"])

    def test_validate_project_inclui_condicoes_quando_fornecidas(self):
        conds = [FlightCondition(name="hover", mu_x=0.0, collective_deg=8.0, rpm=0.0)]
        sem = validation.validate_project({}, AirfoilDef())
        com = validation.validate_project({}, AirfoilDef(), conditions=conds)
        self.assertEqual(len(com), len(sem) + 1)
        self.assertIn("[condition hover]", com[-1].message)


class TestSolverRejectsZeroRotation(unittest.TestCase):
    """The equivalent guard inside the engine: without it, `lambda_z = Vz/OmegaR`
    produced inf/nan that propagated through all maps with no error."""

    def test_solve_bemt_raises_on_zero_rpm(self):
        from zbemt import studies
        from zbemt.models import RotorGeometryDef
        geom = RotorGeometryDef(radius_m=5.0, n_blades=4,
                                r_norm=[0.2, 0.6, 1.0], chord_norm=[0.1, 0.1, 0.1],
                                twist_deg=[8.0, 4.0, 0.0])
        rotor = studies._to_rotor(geom)
        rotor.Omega_rpm = 0.0
        with self.assertRaises(ValueError) as ctx:
            bemt.solve_bemt(rotor, airfoils.to_airfoil(AirfoilDef()),
                            bemt.BEMTConfig(Ne=6, Npsi=8), mu_x=0.1, Vz=0.0)
        self.assertIn("Omega*R", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


class TestAvisoDeMachDePonta(unittest.TestCase):
    """An 8.18 m rotor at 600 RPM has 514 m/s at the tip: Mach 1.5, and 1.8
    on the advancing side with mu_x=0.2. The solver ran this silently -- the
    Prandtl-Glauert correction divided Cl by sqrt(1-M^2) ~ 0.004 on two
    elements and returned Cl=599 (99th percentile = 2.5), with nothing in the
    result revealing that the case was outside the model's scope."""

    def _condicao(self, rpm, mu_x=0.2):
        from zbemt.models import FlightCondition
        return FlightCondition(name="c", mu_x=mu_x, collective_deg=8.0, Vz=0.0, rpm=rpm)

    def test_ponta_supersonica_avisa(self):
        from zbemt.validation import _validar_mach_de_ponta
        issues = _validar_mach_de_ponta(self._condicao(600.0), 8.178,
                                         {"a_sound": 340.29})
        self.assertTrue(issues, "supersonic rotor passed without a warning")
        self.assertEqual(issues[0].level, "warning")
        self.assertIn("Supersonic", issues[0].message)

    def test_ponta_subsonica_normal_nao_avisa(self):
        """The real UH-60: 258 RPM at the same radius, Mach 0.65 at the tip."""
        from zbemt.validation import _validar_mach_de_ponta
        self.assertEqual(
            _validar_mach_de_ponta(self._condicao(258.0), 8.178,
                                    {"a_sound": 340.29}), [])

    def test_transonico_avisa_sem_dizer_supersonico(self):
        from zbemt.validation import _validar_mach_de_ponta
        # ~0.9 Mach on advancing side
        issues = _validar_mach_de_ponta(self._condicao(300.0, mu_x=0.15), 8.178,
                                         {"a_sound": 340.29})
        self.assertTrue(issues)
        self.assertIn("Transonic", issues[0].message)

    def test_sem_rpm_ou_sem_raio_nao_inventa_aviso(self):
        from zbemt.validation import _validar_mach_de_ponta
        self.assertEqual(_validar_mach_de_ponta(self._condicao(None), 8.178, {}), [])
        self.assertEqual(_validar_mach_de_ponta(self._condicao(600.0), 0.0, {}), [])


class TestPolarFullRangeVersusFluxoReverso(unittest.TestCase):
    """Item 11 from the owner: "if I choose Viterna, the reverse flow model
    should only be viterna, right? and vice-versa?"

    Half correct, and the difference matters:

    * `reverse_flow_model='viterna_full_range'` WITHOUT extended polar is
      ERROR -- the engine receives a polar that does not cover ±180 and the
      result in the reverse region means nothing. This was already checked.
    * the reverse path (extended polar + other reverse model) is WARNING,
      not error: there is real data in the reverse region and the other model
      replaces it with a flat plate, which is almost never desired -- but is a
      legitimate choice to COMPARE treatments, which is what section 8.2 of
      the manual offers. Prohibiting it would erase that comparison.
    """

    def _aerofolio(self, estendida: bool) -> AirfoilDef:
        return AirfoilDef(source="analytical",
                          stall_model="viterna" if estendida else "clip")

    def _niveis(self, config, aerofolio):
        from zbemt.validation import validate_config
        return [(i.level, str(i)) for i in validate_config(config, aerofolio)]

    def test_viterna_reverso_sem_polar_estendida_e_erro(self):
        achados = self._niveis({"reverse_flow_model": "viterna_full_range"},
                                self._aerofolio(estendida=False))
        self.assertTrue(any(n == "error" and "viterna_full_range" in t
                            for n, t in achados), achados)

    def test_polar_estendida_com_outro_modelo_e_apenas_aviso(self):
        achados = self._niveis({"reverse_flow_model": "flat_plate"},
                                self._aerofolio(estendida=True))
        avisos = [t for n, t in achados if n == "warning" and "+/-180" in t]
        self.assertTrue(avisos, f"faltou o aviso de dado descartado: {achados}")
        self.assertFalse([t for n, t in achados if n == "error"],
                          "combination is suboptimal, not forbidden")

    def test_par_consistente_nao_gera_nada(self):
        achados = self._niveis({"reverse_flow_model": "viterna_full_range"},
                                self._aerofolio(estendida=True))
        self.assertFalse([t for n, t in achados
                          if "viterna" in t.lower() or "+/-180" in t], achados)
