"""Verify model dataclasses and ``.bemt`` serialization.

The tests cover project defaults, save/load round trips, airfoil sections, project
metadata, paths, and JSON-safe handling of non-finite values. Inputs are model
objects and temporary files; outputs are reconstructed objects and serialized data.
The tests do not run the aerodynamic solver.
"""

import math
import shutil
import tempfile
import unittest
import warnings
from pathlib import Path

from zbemt.models import (
    RotorGeometryDef, AirfoilDef, ProfileGeometry, PolarSlice,
    FlightCondition, BatchDefinition, Project,
    save_bemt, load_bemt, save_bemt_list, load_bemt_list, default_project_paths,
    migrar_config_raw,
)


class TestSaveLoadRoundtrip(unittest.TestCase):
    """save_bemt/load_bemt must exactly reconstruct the saved object
    -- it is the contract used by api.save_project/open_project for ALL
    .bemt files of the project."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _path(self, name: str) -> str:
        return str(Path(self.tmp.name) / name)

    def test_rotor_geometry_def_roundtrip(self):
        geom = RotorGeometryDef(
            r_norm=[0.2, 0.5, 1.0], chord_norm=[0.08, 0.06, 0.03], twist_deg=[12.0, 6.0, 0.0],
            origin="parametric", origin_params={"kind": "tapered", "root_chord_norm": 0.08},
            n_blades=4, radius_m=1.4, root_cutout_norm=0.2143, airfoil_name="perfil 1",
        )
        path = self._path("geom.bemt")
        save_bemt(geom, path)
        loaded = load_bemt(RotorGeometryDef, path)
        self.assertEqual(loaded, geom)

    def test_airfoil_def_with_nested_objects_roundtrip(self):
        # T6: ALL fields filled with non-default values, and
        # comparison of the ENTIRE object (not field by field) -- a round-trip
        # with defaults, or a partial comparison, doesn't prove that nothing was
        # silently lost by _from_jsonable.
        airfoil = AirfoilDef(
            name="NACA2412", r_norm=0.5, source="table",
            cl_alpha=6.0, alpha0_deg=-3.0, cd0=0.02, k=0.01,
            alpha_stall_pos_deg=14.0, alpha_stall_neg_deg=-5.0,
            stall_model="enhanced", extend_full_range=False,
            viterna_blend_width_deg=5.5,
            use_dynamic_stall=True, dynamic_stall_method="time_march",
            dynamic_stall_A=7.0, dynamic_stall_fade_start_deg=35.0,
            dynamic_stall_fade_end_deg=45.0,
            dynamic_stall_time_march_revolutions=6,
            dynamic_stall_time_march_avg_last=2,
            table_slices=[
                PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.2, 0.7], cd=[0.02, 0.015, 0.02],
                           r_norm=0.5, reynolds=5e5, mach=0.1, label="raiz"),
                PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.2, 0.3, 0.8], cd=[0.018, 0.014, 0.019],
                           r_norm=0.9, reynolds=1.2e6, mach=0.2, label="ponta"),
            ],
            geometry=ProfileGeometry(
                source="cst", naca_code="2412",
                cst_upper=[0.1, 0.2, 0.3], cst_lower=[-0.1, -0.2, -0.3],
                bezier_control_points=[[0.0, 0.0], [0.5, 0.05], [1.0, 0.0]],
                imported_path="perfis/meu_perfil.dat", n_points=150,
                x=[0.0, 0.5, 1.0], y=[0.0, 0.03, 0.0],
            ),
            external_engine="neuralfoil",
            external_reynolds_list=[1e6, 2e6],
            external_mach_list=[0.1, 0.2],
            external_alpha_min_deg=-18.0, external_alpha_max_deg=18.0,
            external_alpha_step_deg=0.25,
        )
        path = self._path("airfoil.bemt")
        save_bemt(airfoil, path)
        loaded = load_bemt(AirfoilDef, path)
        self.assertEqual(loaded, airfoil)

    def test_polar_slice_roundtrip(self):
        slice_ = PolarSlice(alpha_deg=[-5, 0, 5, 10], cl=[-0.3, 0.2, 0.7, 1.1],
                             cd=[0.02, 0.015, 0.02, 0.03], r_norm=0.42,
                             reynolds=8.5e5, mach=0.15, label="seção X")
        path = self._path("polar_slice.bemt")
        save_bemt(slice_, path)
        loaded = load_bemt(PolarSlice, path)
        self.assertEqual(loaded, slice_)

    def test_profile_geometry_roundtrip(self):
        geom = ProfileGeometry(
            source="bezier", naca_code="4412",
            cst_upper=[0.15, 0.25], cst_lower=[-0.15, -0.25],
            bezier_control_points=[[0.0, 0.0], [0.3, 0.06], [1.0, 0.0]],
            imported_path="perfis/import.dat", n_points=175,
            x=[0.0, 0.25, 0.5, 0.75, 1.0], y=[0.0, 0.02, 0.03, 0.015, 0.0],
        )
        path = self._path("profile_geometry.bemt")
        save_bemt(geom, path)
        loaded = load_bemt(ProfileGeometry, path)
        self.assertEqual(loaded, geom)

    def test_flight_condition_roundtrip(self):
        cond = FlightCondition(name="caso X", mu_x=0.22, collective_deg=9.5,
                                Vz=1.5, rpm=1234.5)
        path = self._path("flight_condition.bemt")
        save_bemt(cond, path)
        loaded = load_bemt(FlightCondition, path)
        self.assertEqual(loaded, cond)

    def test_airfoil_def_defaults_survive_roundtrip(self):
        # cl_alpha default is 2*pi -- checks that "non-obvious" floats don't
        # suffer strange rounding in the JSON cycle.
        airfoil = AirfoilDef()
        path = self._path("airfoil_default.bemt")
        save_bemt(airfoil, path)
        loaded = load_bemt(AirfoilDef, path)
        self.assertAlmostEqual(loaded.cl_alpha, 2 * math.pi, places=12)

    def test_airfoil_def_migrates_old_viterna_schema(self):
        # docs/plano_v2.md Section 7: a .bemt saved by the old schema (3
        # fields: use_viterna_extension/blend_with_viterna/
        # extrapolate_full_range, + use_compressibility which doesn't exist
        # here anymore) must continue loading, with extend_full_range
        # calculated from the old intent.
        import json
        path = self._path("airfoil_old_schema.bemt")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "name": "perfil antigo", "source": "analytical",
                "use_viterna_extension": False, "blend_with_viterna": True,
                "extrapolate_full_range": False, "use_compressibility": True,
            }, f)
        loaded = load_bemt(AirfoilDef, path)
        self.assertTrue(loaded.extend_full_range)
        self.assertFalse(hasattr(loaded, "use_compressibility"))
        self.assertIsNone(loaded.geometry)

    def test_old_schema_without_stall_model_still_becomes_viterna(self):
        """The case that the migration exists to handle: old file, without
        the `stall_model` key, which expressed Viterna via extend_full_range."""
        import json
        path = self._path("airfoil_sem_stall_model.bemt")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": "antigo", "source": "analytical",
                       "extend_full_range": True}, f)
        self.assertEqual(load_bemt(AirfoilDef, path).stall_model, "viterna")

    def test_explicit_stall_model_is_not_overwritten_by_migration(self):
        """Regression: the migration also ran on files of the CURRENT schema.
        Since the AirfoilDef default has extend_full_range=True,
        any stall_model != 'viterna' was silently reverted when
        loading -- the field was impossible to change (GUI or CLI) without also
        disabling extend_full_range."""
        import json
        for modelo in ("linear", "clip", "enhanced"):
            with self.subTest(stall_model=modelo):
                path = self._path(f"airfoil_{modelo}.bemt")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"name": "atual", "source": "analytical",
                               "extend_full_range": True, "stall_model": modelo}, f)
                self.assertEqual(load_bemt(AirfoilDef, path).stall_model, modelo)

    def test_stall_model_survives_full_roundtrip(self):
        airfoil = AirfoilDef(name="p", source="analytical",
                             extend_full_range=True, stall_model="clip")
        path = self._path("airfoil_roundtrip_stall.bemt")
        save_bemt(airfoil, path)
        self.assertEqual(load_bemt(AirfoilDef, path).stall_model, "clip")

    def test_batch_definition_roundtrip(self):
        batch = BatchDefinition(
            name="mu_x sweep", sweep_kind="mu_sweep",
            conditions=[
                FlightCondition(name="c1", mu_x=0.1, collective_deg=8.0, Vz=0.5, rpm=1200.0),
                FlightCondition(name="c2", mu_x=0.2, collective_deg=10.0, Vz=-0.5, rpm=1300.0),
            ],
            sweep_params={"mu_values": [0.0, 0.1, 0.2]},
            outdir="outputs", plots=["performance", "disk_map_CT"],
        )
        path = self._path("batch.bemt")
        save_bemt(batch, path)
        loaded = load_bemt(BatchDefinition, path)
        self.assertEqual(loaded, batch)

    def test_numpy_types_are_jsonable(self):
        # save_bemt must accept numpy values (the GUI/geometry.py
        # often produces lists via .tolist(), but loose dicts
        # like origin_params can contain numpy scalars).
        import numpy as np
        geom = RotorGeometryDef(r_norm=[0.2, 1.0], chord_norm=[0.08, 0.03], twist_deg=[10.0, 0.0],
                                 origin_params={"root_chord_norm": np.float64(0.08)})
        path = self._path("geom_np.bemt")
        save_bemt(geom, path)  # must not raise TypeError
        loaded = load_bemt(RotorGeometryDef, path)
        self.assertAlmostEqual(loaded.origin_params["root_chord_norm"], 0.08)


class TestDefaultProjectPaths(unittest.TestCase):
    def test_structure(self):
        paths = default_project_paths("projects/MyProject")
        self.assertEqual(paths["inputs"], Path("projects/MyProject/inputs"))
        self.assertEqual(paths["config"], Path("projects/MyProject/inputs/config.bemt"))
        self.assertEqual(paths["geom"], Path("projects/MyProject/inputs/geom.bemt"))
        self.assertEqual(paths["airfoil"], Path("projects/MyProject/inputs/airfoil.bemt"))
        self.assertEqual(paths["airfoil_sections"], Path("projects/MyProject/inputs/airfoil_sections.bemt"))
        self.assertEqual(paths["batches"], Path("projects/MyProject/inputs/batches.bemt"))
        # `legacy_batch` -> old singular `batch.bemt`, read-only, used only
        # to migrate an old project on first open (see `api.load_project`).
        self.assertEqual(paths["legacy_batch"], Path("projects/MyProject/inputs/batch.bemt"))
        self.assertEqual(paths["outputs"], Path("projects/MyProject/outputs"))


class TestProjectDataclass(unittest.TestCase):
    def test_project_defaults(self):
        p = Project()
        self.assertEqual(p.name, "novo_projeto")
        self.assertIsInstance(p.geometry, RotorGeometryDef)
        self.assertIsInstance(p.airfoil, AirfoilDef)
        self.assertEqual(p.batches, [])
        self.assertEqual(p.airfoil_sections, [])


class TestAirfoilSectionsRoundtrip(unittest.TestCase):
    """Phase D (docs/plano.md GUI v3, Section 4): AirfoilDef.r_norm and
    Project.airfoil_sections, saved via save_bemt_list/load_bemt_list."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_airfoil_def_r_norm_defaults_to_none(self):
        a = AirfoilDef()
        self.assertIsNone(a.r_norm)

    def test_save_load_list_roundtrip(self):
        sections = [
            AirfoilDef(name="raiz", r_norm=0.15, cd0=0.02),
            AirfoilDef(name="ponta", r_norm=1.0, cd0=0.008),
        ]
        path = Path(self.tmp.name) / "airfoil_sections.bemt"
        save_bemt_list(sections, path)
        loaded = load_bemt_list(AirfoilDef, path)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].name, "raiz")
        self.assertEqual(loaded[0].r_norm, 0.15)
        self.assertEqual(loaded[1].r_norm, 1.0)
        self.assertEqual(loaded[1].cd0, 0.008)

    def test_save_load_empty_list_roundtrip(self):
        path = Path(self.tmp.name) / "empty.bemt"
        save_bemt_list([], path)
        loaded = load_bemt_list(AirfoilDef, path)
        self.assertEqual(loaded, [])


class TestProjectNamePersistence(unittest.TestCase):
    """Q1 (production-plan.md): `Project.name` must survive
    save/reopen even when it differs from the folder name -- before this
    fix, `api.open_project` always reconstructed the name from
    `Path(path).name`, and a project renamed in the GUI (but kept in the
    same folder) lost the custom name when reopening."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_custom_name_survives_save_and_reopen(self):
        from zbemt import api

        project_dir = Path(self.tmp.name) / "pasta_generica"
        project = api.new_project(str(project_dir), name="Meu Rotor Bonito")
        self.assertEqual(project.name, "Meu Rotor Bonito")

        reloaded = api.open_project(str(project_dir))
        self.assertEqual(reloaded.name, "Meu Rotor Bonito")
        self.assertNotEqual(reloaded.name, project_dir.name)

    def test_legacy_project_without_meta_falls_back_to_folder_name(self):
        from zbemt import api

        project_dir = Path(self.tmp.name) / "projeto_legado"
        project = api.new_project(str(project_dir), name="qualquer coisa")
        # simulates a project saved BEFORE this fix: without meta.bemt.
        paths = default_project_paths(str(project_dir))
        paths["meta"].unlink()

        reloaded = api.open_project(str(project_dir))
        self.assertEqual(reloaded.name, "projeto_legado")


if __name__ == "__main__":
    unittest.main()


class TestSerializacaoQ1(unittest.TestCase):
    """Q1 (production-plan.md): three serialization holes that lost
    data or produced invalid files, all silently."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def test_nao_finitos_geram_json_valido_e_voltam_iguais(self):
        """`json.dump` writes `NaN`/`Infinity` without quotes -- literals that
        Python rereads but that any strict parser refuses, invalidating the
        entire file for any other tool."""
        alvo = self.dir / "polar.bemt"
        slice_ = PolarSlice(alpha_deg=[0.0, 5.0],
                            cl=[float("nan"), float("inf")],
                            reynolds=float("-inf"))
        save_bemt(slice_, alvo)

        texto = alvo.read_text(encoding="utf-8")
        self.assertNotRegex(texto, r":\s*(NaN|-?Infinity)\s*[,}\]]",
                            "non-finite written as a literal: invalid JSON")

        de_volta = load_bemt(PolarSlice, alvo)
        self.assertTrue(math.isnan(de_volta.cl[0]))
        self.assertEqual(de_volta.cl[1], float("inf"))
        self.assertEqual(de_volta.reynolds, float("-inf"))

    def test_chave_desconhecida_avisa_em_vez_de_sumir(self):
        alvo = self.dir / "polar.bemt"
        alvo.write_text('{"alpha_deg": [1.0], "campo_que_foi_renomeado": 7}',
                        encoding="utf-8")
        with warnings.catch_warnings(record=True) as capturados:
            warnings.simplefilter("always")
            obj = load_bemt(PolarSlice, alvo)
        mensagens = [str(w.message) for w in capturados
                     if issubclass(w.category, UserWarning)]
        self.assertTrue(any("campo_que_foi_renomeado" in m for m in mensagens),
                        f"nenhum aviso sobre a chave descartada: {mensagens}")
        self.assertEqual(obj.alpha_deg, [1.0])   # the rest continues loading

    def test_config_legado_use_prandtl_loss_vira_prandtl_loss_mode(self):
        """The boolean became an enum. Without migration the field was discarded --
        even in the repository's reference project, which kept
        `use_prandtl_loss: true` and was running with the default."""
        self.assertEqual(
            migrar_config_raw({"use_prandtl_loss": True})["prandtl_loss_mode"], "both")
        self.assertEqual(
            migrar_config_raw({"use_prandtl_loss": False})["prandtl_loss_mode"], "off")
        self.assertNotIn("use_prandtl_loss", migrar_config_raw({"use_prandtl_loss": True}))

    def test_migracao_prandtl_desligado_produz_valor_que_o_motor_reconhece(self):
        """`False` has to become "off", not a value outside the enum.

        The engine selects the loss factor with a dict lookup whose default
        is "both", so a migrated value the enum does not contain switches the
        correction back ON for a project that had it OFF. Regression for the
        migration writing "none"."""
        from zbemt.bemt import BEMTConfig
        modos_validos = {"off", "tip", "root", "both"}
        for antigo, esperado in ((True, "both"), (False, "off")):
            with self.subTest(use_prandtl_loss=antigo):
                modo = migrar_config_raw(
                    {"use_prandtl_loss": antigo})["prandtl_loss_mode"]
                self.assertIn(modo, modos_validos)
                self.assertEqual(modo, esperado)
                # and the migrated value survives a trip through the dataclass
                self.assertEqual(BEMTConfig(prandtl_loss_mode=modo).prandtl_loss_mode,
                                 esperado)

    def test_as_duas_migracoes_de_prandtl_concordam(self):
        """`models` and `studies` both migrate the same legacy key; they
        disagreed, one writing "off" and the other "none"."""
        from zbemt.studies import _migrate_config_dict
        for antigo in (True, False):
            with self.subTest(use_prandtl_loss=antigo):
                self.assertEqual(
                    migrar_config_raw({"use_prandtl_loss": antigo})["prandtl_loss_mode"],
                    _migrate_config_dict({"use_prandtl_loss": antigo})["prandtl_loss_mode"])

    def test_migracao_nao_atropela_valor_ja_no_schema_novo(self):
        migrado = migrar_config_raw({"use_prandtl_loss": True, "prandtl_loss_mode": "tip"})
        self.assertEqual(migrado["prandtl_loss_mode"], "tip")
