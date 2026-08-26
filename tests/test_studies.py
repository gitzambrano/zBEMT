"""Verify study orchestration around individual cases and batches.

The tests cover single runs, sweeps, factorial batches, cancellation, progress
callbacks, trim modes, saved cases, and airfoil overrides. Inputs are model objects,
callbacks, and controlled configurations; outputs are results, progress events, and
cancellation behavior. Numerical equations remain tested in the core solver suite.
"""

import os
import unittest
import unittest.mock
from dataclasses import asdict, replace

import numpy as np

from zbemt import geometry
from zbemt import studies
from zbemt.bemt import BEMTConfig, SolveCancelled
from zbemt.models import Project, AirfoilDef, FlightCondition, BatchDefinition, Results
from tests.helpers import make_studies_project as _make_project


class TestRunSingleCase(unittest.TestCase):
    def test_returns_results_with_summary_and_maps(self):
        project = _make_project()
        cond = FlightCondition(name="c1", mu_x=0.0, collective_deg=8.0, rpm=600.0)
        res = studies.run_single_case(project, cond)
        self.assertIsInstance(res, Results)
        self.assertEqual(res.condition_name, "c1")
        self.assertIn("Thrust", res.summary)
        self.assertIn("Fn", res.maps)

    def test_collective_deg_changes_thrust(self):
        project = _make_project()
        low = studies.run_single_case(project, FlightCondition(name="low", collective_deg=4.0, rpm=600.0))
        high = studies.run_single_case(project, FlightCondition(name="high", collective_deg=10.0, rpm=600.0))
        self.assertGreater(high.summary["Thrust"], low.summary["Thrust"])

    def test_explicit_rpm_overrides_placeholder(self):
        project = _make_project()
        res_slow = studies.run_single_case(project, FlightCondition(name="slow", rpm=400.0))
        res_fast = studies.run_single_case(project, FlightCondition(name="fast", rpm=1200.0))
        # more RPM -> more thrust (same geometry/collective)
        self.assertGreater(res_fast.summary["Thrust"], res_slow.summary["Thrust"])

    def test_summary_carries_collective_deg_and_rpm_aliases(self):
        """docs/plano_v3.md Part 4.2: `plots.plot_coefficients_vs_axis`
        needs `summary["collective_deg"]`/`summary["rpm"]` for the
        axes "collective_deg"/"rpm" -- `aggregate_results` doesn't expose them
        natively, so `run_single_case` adds them as aliases."""
        project = _make_project()
        cond = FlightCondition(name="c1", mu_x=0.1, collective_deg=9.5, rpm=650.0)
        res = studies.run_single_case(project, cond)
        self.assertEqual(res.summary["collective_deg"], 9.5)
        self.assertEqual(res.summary["rpm"], 650.0)

    def test_condition_without_rpm_raises(self):
        """RPM became mandatory: before, a condition without rpm fell
        into a placeholder of 1000 and returned an apparently
        plausible thrust from an invented rotation, without warning."""
        project = _make_project()
        cond = FlightCondition(name="c1", mu_x=0.1, collective_deg=8.0, rpm=None)
        with self.assertRaises(ValueError) as ctx:
            studies.run_single_case(project, cond)
        self.assertIn("RPM not provided", str(ctx.exception))

    def test_condition_with_nonpositive_rpm_raises(self):
        project = _make_project()
        for rpm in (0.0, -10.0):
            with self.subTest(rpm=rpm):
                cond = FlightCondition(name="c1", mu_x=0.1, collective_deg=8.0, rpm=rpm)
                with self.assertRaises(ValueError):
                    studies.run_single_case(project, cond)


class TestSweeps(unittest.TestCase):
    def test_mu_sweep_returns_one_result_per_value(self):
        project = _make_project()
        results = studies.run_mu_sweep(project, [0.0, 0.1, 0.2], rpm=600.0)
        self.assertEqual(len(results), 3)
        names = [r.condition_name for r in results]
        self.assertEqual(names, ["mu_x_0", "mu_x_0.1", "mu_x_0.2"])

    def test_collective_sweep_thrust_increases(self):
        project = _make_project()
        results = studies.run_collective_sweep(project, [4.0, 8.0, 12.0], rpm=600.0)
        thrusts = [r.summary["Thrust"] for r in results]
        self.assertEqual(thrusts, sorted(thrusts))

    def test_alpha_sweep_runs_and_varies_Vv(self):
        project = _make_project()
        results = studies.run_alpha_sweep(project, [-10.0, 0.0, 10.0], mu_x=0.15, rpm=600.0)
        self.assertEqual(len(results), 3)
        # alpha>0 (climb) must give Vz>0 in the internally solved condition;
        # indirect check via metadata attached to maps.
        self.assertGreater(results[-1].maps.get("Vz", results[-1].maps.get("lambda_z", 0) * 1), 0.0)


class TestRunBatch(unittest.TestCase):
    def test_explicit_conditions_take_precedence_over_sweep_kind(self):
        project = _make_project()
        batch = BatchDefinition(
            conditions=[FlightCondition(name="only_one", mu_x=0.1, rpm=600.0)],
            sweep_kind="mu_sweep", sweep_params={"mu_values": [0.0, 0.5, 1.0]},
        )
        results = studies.run_batch(project, batch)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].condition_name, "only_one")

    def test_sweep_kind_mu_sweep_used_when_no_explicit_conditions(self):
        project = _make_project()
        batch = BatchDefinition(sweep_kind="mu_sweep",
                                 sweep_params={"mu_values": [0.0, 0.1], "rpm": 600.0})
        results = studies.run_batch(project, batch)
        self.assertEqual(len(results), 2)

    def test_custom_with_no_conditions_returns_empty(self):
        project = _make_project()
        batch = BatchDefinition(sweep_kind="custom", conditions=[])
        self.assertEqual(studies.run_batch(project, batch), [])

    def test_unknown_sweep_kind_raises(self):
        project = _make_project()
        batch = BatchDefinition(sweep_kind="bogus_kind", conditions=[])
        with self.assertRaises(ValueError):
            studies.run_batch(project, batch)


class TestRunBatchProgressAndCancel(unittest.TestCase):
    """docs/plano_v3.md Part 2 — worker thread: on_case_done/should_cancel
    are optional and not part of the previous public API (default None
    preserves the always-synchronous behavior)."""

    def test_on_case_done_called_once_per_condition_in_order(self):
        project = _make_project()
        conditions = [FlightCondition(name=f"c{i}", mu_x=0.05 * i, collective_deg=8.0, rpm=600.0) for i in range(4)]
        batch = BatchDefinition(conditions=conditions)
        seen = []
        results = studies.run_batch(project, batch, on_case_done=lambda i, total, r: seen.append((i, total)))
        self.assertEqual(seen, [(i, 4) for i in range(4)])
        self.assertEqual(len(results), 4)

    def test_on_case_done_receives_exception_without_stopping_batch(self):
        # docs/plano_v3.md Part 2: an isolated case failure doesn't crash
        # the entire batch when on_case_done is set -- other cases
        # continue running, and the exception reaches the callback, not
        # propagated. Uses mock to force a deterministic failure in the
        # middle of the list (doesn't depend on any real physics breaking).
        project = _make_project()
        conditions = [
            FlightCondition(name="ok1", mu_x=0.0, collective_deg=8.0, rpm=600.0),
            FlightCondition(name="bad", mu_x=0.0, collective_deg=8.0, rpm=600.0),
            FlightCondition(name="ok2", mu_x=0.0, collective_deg=8.0, rpm=600.0),
        ]
        batch = BatchDefinition(conditions=conditions)
        real_run_single_case = studies.run_single_case

        def flaky_run(proj, cond, should_cancel=None):
            if cond.name == "bad":
                raise RuntimeError("synthetic test failure")
            return real_run_single_case(proj, cond)

        calls = []
        with unittest.mock.patch.object(studies, "run_single_case", side_effect=flaky_run):
            results = studies.run_batch(project, batch, on_case_done=lambda i, total, r: calls.append(r))

        self.assertEqual(len(calls), 3)
        self.assertIsInstance(calls[1], RuntimeError)
        self.assertEqual(len(results), 2)  # "bad" descartado, os outros 2 sobrevivem

    def test_should_cancel_stops_before_running_all_conditions(self):
        project = _make_project()
        conditions = [FlightCondition(name=f"c{i}", mu_x=0.0, collective_deg=8.0, rpm=600) for i in range(5)]
        batch = BatchDefinition(conditions=conditions)
        seen = []

        def cb(i, total, r):
            seen.append(i)

        results = studies.run_batch(
            project, batch, on_case_done=cb,
            should_cancel=lambda: len(seen) >= 2)
        self.assertEqual(len(seen), 2)
        self.assertEqual(len(results), 2)

    def test_default_behavior_unchanged_without_callback(self):
        project = _make_project()
        batch = BatchDefinition(conditions=[FlightCondition(name="c1", mu_x=0.1, collective_deg=8.0, rpm=600.0)])
        results = studies.run_batch(project, batch)
        self.assertEqual(len(results), 1)

    def test_run_factorial_batch_supports_on_case_done(self):
        project = _make_project()
        axes = [{"variable": "mu_x", "values": [0.0, 0.1, 0.2]}]
        seen = []
        results = studies.run_factorial_batch(
            project, axes, fixed={"rpm": 600},
            on_case_done=lambda i, total, r: seen.append((i, total)))
        self.assertEqual(seen, [(0, 3), (1, 3), (2, 3)])
        self.assertEqual(len(results), 3)


class TestBenchmarkSolvers(unittest.TestCase):
    def test_one_result_per_solver_with_tagged_maps(self):
        project = _make_project()
        cond = FlightCondition(name="bench", mu_x=0.0, collective_deg=8.0, rpm=600.0)
        results = studies.benchmark_solvers(project, cond, solvers=("newton", "fixed_point"))
        self.assertEqual(len(results), 2)
        solvers_used = {r.maps["benchmark_solver"] for r in results}
        self.assertEqual(solvers_used, {"newton", "fixed_point"})
        for r in results:
            self.assertIn("benchmark_elapsed", r.maps)
            self.assertTrue(r.condition_name.startswith("bench_"))

    def test_original_project_config_untouched(self):
        project = _make_project(solver="newton")
        original_solver = project.config["solver"]
        studies.benchmark_solvers(project, FlightCondition(name="c", rpm=600.0), solvers=("fixed_point",))
        self.assertEqual(project.config["solver"], original_solver)


class TestBuildConfigAirfoilOverride(unittest.TestCase):
    def test_build_config_no_longer_copies_dynamic_stall_from_airfoil(self):
        # docs/plano_v2.md Finding #1: _build_config() no longer overwrites
        # BEMTConfig.use_dynamic_stall from AirfoilDef -- this now
        # is done by attaching dynamic_stall_params to the airfoil object inside
        # airfoils.to_airfoil() (see test_airfoils.TestToAirfoilDispatch
        # .test_dynamic_stall_params_attached), and bemt.solve_bemt reading from there.
        cfg_dict = asdict(BEMTConfig(use_dynamic_stall=False))
        airfoil = AirfoilDef(use_dynamic_stall=True, dynamic_stall_A=12.0)
        cfg = studies._build_config(cfg_dict, airfoil_def=airfoil)
        self.assertFalse(cfg.use_dynamic_stall)
        self.assertEqual(cfg.dynamic_stall_A, BEMTConfig().dynamic_stall_A)

    def test_unknown_keys_in_config_dict_are_ignored(self):
        cfg_dict = asdict(BEMTConfig())
        cfg_dict["totally_unknown_field"] = 42
        cfg = studies._build_config(cfg_dict)
        self.assertIsInstance(cfg, BEMTConfig)

    def test_migrates_old_inflow_model_coupling_schema(self):
        # docs/plano_v2.md Section 7: config dict saved by the old schema
        # (inflow_model + inflow_coupling separate) must continue
        # working, migrated to the single inflow_field_model field.
        cfg_dict = asdict(BEMTConfig())
        del cfg_dict["inflow_field_model"]
        cfg_dict["inflow_model"] = "drees"
        cfg_dict["inflow_coupling"] = "global"
        cfg = studies._build_config(cfg_dict)
        self.assertEqual(cfg.inflow_field_model, "drees_global")

    def test_migrates_old_pitt_peters_coupling_schema(self):
        cfg_dict = asdict(BEMTConfig())
        del cfg_dict["inflow_field_model"]
        cfg_dict["inflow_model"] = "coleman"
        cfg_dict["inflow_coupling"] = "pitt_peters"
        cfg = studies._build_config(cfg_dict)
        self.assertEqual(cfg.inflow_field_model, "pitt_peters_steady")

    def test_migrates_old_use_prandtl_loss_bool_true(self):
        cfg_dict = asdict(BEMTConfig())
        del cfg_dict["prandtl_loss_mode"]
        cfg_dict["use_prandtl_loss"] = True
        cfg = studies._build_config(cfg_dict)
        self.assertEqual(cfg.prandtl_loss_mode, "both")

    def test_migrates_old_use_prandtl_loss_bool_false(self):
        cfg_dict = asdict(BEMTConfig())
        del cfg_dict["prandtl_loss_mode"]
        cfg_dict["use_prandtl_loss"] = False
        cfg = studies._build_config(cfg_dict)
        self.assertEqual(cfg.prandtl_loss_mode, "off")


class TestRunFactorialBatch(unittest.TestCase):
    """Phase C (docs/plano.md GUI v3, Section 7): factorial analysis in
    Run Batch -- Cartesian product of 1 to 3 axes."""

    def test_single_axis_produces_one_result_per_value(self):
        project = _make_project()
        axes = [{"variable": "mu_x", "values": [0.0, 0.1, 0.2]}]
        results = studies.run_factorial_batch(project, axes, fixed={"rpm": 600})
        self.assertEqual(len(results), 3)

    def test_two_axes_produces_cartesian_product(self):
        project = _make_project()
        axes = [
            {"variable": "mu_x", "values": [0.1, 0.2]},
            {"variable": "collective_deg", "values": [6.0, 8.0, 10.0]},
        ]
        results = studies.run_factorial_batch(project, axes, fixed={"rpm": 600})
        self.assertEqual(len(results), 6)

    def test_zero_axes_raises(self):
        project = _make_project()
        with self.assertRaises(ValueError):
            studies.run_factorial_batch(project, [], fixed={})

    def test_four_axes_raises(self):
        project = _make_project()
        axes = [{"variable": v, "values": [0.0]} for v in
                studies._FACTORIAL_VARIABLES] + [{"variable": "mu_x", "values": [0.1]}]
        with self.assertRaises(ValueError):
            studies.run_factorial_batch(project, axes, fixed={})

    def test_repeated_variable_across_axes_raises(self):
        project = _make_project()
        axes = [{"variable": "mu_x", "values": [0.1]}, {"variable": "mu_x", "values": [0.2]}]
        with self.assertRaises(ValueError):
            studies.run_factorial_batch(project, axes, fixed={})

    def test_unknown_variable_raises(self):
        project = _make_project()
        axes = [{"variable": "bogus", "values": [0.1]}]
        with self.assertRaises(ValueError):
            studies.run_factorial_batch(project, axes, fixed={})

    def _factorial_conditions(self, project, axes, fixed=None):
        """Captures the FlightCondition objects built by the factorial loop without
        running the engine (only the unit conversion matters here)."""
        captured = []
        original = studies._run_conditions
        studies._run_conditions = lambda proj, conds, **kw: captured.append(conds) or []
        try:
            studies.run_factorial_batch(project, axes, fixed=fixed or {})
        finally:
            studies._run_conditions = original
        return captured[0]

    def test_fixed_V_does_not_crash(self):
        """Regression: `rotor_for_omega` was used in V->mu_x conversion before
        it was created, so any `fixed={"Vx": ...}` raised
        UnboundLocalError."""
        project = _make_project()
        axes = [{"variable": "collective_deg", "values": [6.0, 8.0]}]
        conds = self._factorial_conditions(project, axes, fixed={"Vx": 20.0, "rpm": 600})
        self.assertEqual(len(conds), 2)
        self.assertGreater(conds[0].mu_x, 0.0)

    def test_V_rpm_grid_is_independent_of_axis_order(self):
        """Regression: V->mu_x conversion used the OmegaR from the PREVIOUS combination
        (the shared rotor was only updated after the conversion), so
        the same physical point gave different mu_x depending on the order of values
        on the rpm axis -- silent error, without exception."""
        project = _make_project()
        crescente = self._factorial_conditions(project, [
            {"variable": "Vx", "values": [50.0]},
            {"variable": "rpm", "values": [300.0, 600.0]},
        ])
        decrescente = self._factorial_conditions(project, [
            {"variable": "Vx", "values": [50.0]},
            {"variable": "rpm", "values": [600.0, 300.0]},
        ])
        por_rpm = lambda conds: {c.rpm: c.mu_x for c in conds}
        self.assertEqual(por_rpm(crescente), por_rpm(decrescente))

        # and mu_x must be physically coherent: V fixed, mu_x ~ 1/rpm
        mus = por_rpm(crescente)
        self.assertAlmostEqual(mus[300.0], 2.0 * mus[600.0], places=9)

    def test_fixed_V_rescales_mu_per_rpm(self):
        """`V` fixed is dimensional [m/s]: the equivalent mu_x must change with
        the rpm of each combination, not stay bound to the base rpm."""
        project = _make_project()
        conds = self._factorial_conditions(
            project, [{"variable": "rpm", "values": [300.0, 600.0]}], fixed={"Vx": 50.0})
        mus = {c.rpm: c.mu_x for c in conds}
        self.assertAlmostEqual(mus[300.0], 2.0 * mus[600.0], places=9)

    def test_alpha_deg_axis_derives_vv_from_mu(self):
        project = _make_project()
        axes = [{"variable": "alpha_deg", "values": [0.0]}]
        results = studies.run_factorial_batch(project, axes, fixed={"mu_x": 0.2, "rpm": 600})
        self.assertAlmostEqual(results[0].summary["Vz"], 0.0, places=6)

    def test_J_axis_is_equivalent_to_mu_axis(self):
        # J_x = pi*mu_x (Sec.6c of bemt.py) -- varying J_x should reproduce
        # exactly the same results as varying mu_x at the equivalent value.
        project = _make_project()
        mu_results = studies.run_factorial_batch(
            project, [{"variable": "mu_x", "values": [0.1, 0.2]}], fixed={"rpm": 600})
        J_results = studies.run_factorial_batch(
            project, [{"variable": "J_x", "values": [np.pi * 0.1, np.pi * 0.2]}], fixed={"rpm": 600})
        for r_mu, r_J in zip(mu_results, J_results):
            self.assertAlmostEqual(r_mu.summary["mu_x"], r_J.summary["mu_x"], places=9)
            self.assertAlmostEqual(r_mu.summary["CT"], r_J.summary["CT"], places=9)

    def test_Vv_axis_used_directly_without_conversion(self):
        project = _make_project()
        results = studies.run_factorial_batch(
            project, [{"variable": "Vz", "values": [1.5]}], fixed={"mu_x": 0.2, "rpm": 600})
        self.assertAlmostEqual(results[0].summary["Vz"], 1.5, places=9)

    def test_mu_and_J_as_axes_simultaneously_raises(self):
        project = _make_project()
        axes = [{"variable": "mu_x", "values": [0.1]}, {"variable": "J_x", "values": [0.3]}]
        with self.assertRaises(ValueError):
            studies.run_factorial_batch(project, axes, fixed={})

    def test_alpha_deg_and_Vv_as_axes_simultaneously_raises(self):
        project = _make_project()
        axes = [{"variable": "alpha_deg", "values": [0.0]}, {"variable": "Vz", "values": [1.0]}]
        with self.assertRaises(ValueError):
            studies.run_factorial_batch(project, axes, fixed={})

    def test_mu_and_J_as_fixed_simultaneously_raises(self):
        project = _make_project()
        axes = [{"variable": "collective_deg", "values": [8.0]}]
        with self.assertRaises(ValueError):
            studies.run_factorial_batch(project, axes, fixed={"mu_x": 0.1, "J_x": 0.3})

    def test_J_fixed_is_equivalent_to_mu_fixed(self):
        project = _make_project()
        axes = [{"variable": "collective_deg", "values": [8.0]}]
        r_mu = studies.run_factorial_batch(project, axes, fixed={"mu_x": 0.2, "rpm": 600})
        r_J = studies.run_factorial_batch(project, axes, fixed={"J_x": np.pi * 0.2, "rpm": 600})
        self.assertAlmostEqual(r_mu[0].summary["mu_x"], r_J[0].summary["mu_x"], places=9)

    def test_alpha_deg_fixed_derives_Vv_from_mu_axis(self):
        # alpha fixed + mu_x varying by axis: Vz must be recalculated
        # at each combination (cannot be a fixed pre-computed value),
        # since Vz = tan(alpha)*Vx depends on mu_x.
        project = _make_project()
        axes = [{"variable": "mu_x", "values": [0.1, 0.2]}]
        results = studies.run_factorial_batch(project, axes, fixed={"alpha_deg": 10.0, "rpm": 600})
        self.assertNotAlmostEqual(results[0].summary["Vz"], results[1].summary["Vz"], places=6)
        for r in results:
            expected_vv = np.tan(np.deg2rad(10.0)) * r.summary["mu_x"] * (600 * 2 * np.pi / 60) * project.geometry.radius_m
            self.assertAlmostEqual(r.summary["Vz"], expected_vv, places=4)

    def test_mu_or_J_as_axis_and_fixed_at_once_raises(self):
        project = _make_project()
        axes = [{"variable": "J_x", "values": [0.3]}]
        with self.assertRaises(ValueError):
            studies.run_factorial_batch(project, axes, fixed={"mu_x": 0.1})

    def test_run_batch_dispatches_factorial_sweep_kind(self):
        project = _make_project()
        batch = BatchDefinition(sweep_kind="factorial", sweep_params={
            "axes": [{"variable": "mu_x", "values": [0.0, 0.1]}],
            "fixed": {"rpm": 600},
        })
        results = studies.run_batch(project, batch)
        self.assertEqual(len(results), 2)


class TestRunSingleCaseMultiSectionAirfoil(unittest.TestCase):
    """Phase D (docs/plano.md GUI v3, Section 4): run_single_case uses
    to_blade_airfoil, which activates Project.airfoil_sections when present."""

    def test_empty_sections_uses_single_airfoil_unchanged(self):
        project = _make_project()
        project.airfoil_sections = []
        cond = FlightCondition(name="c", mu_x=0.0, collective_deg=8.0, Vz=0.0, rpm=600)
        result = studies.run_single_case(project, cond)
        self.assertTrue(np.isfinite(result.summary["CT"]))

    def test_two_sections_runs_end_to_end(self):
        project = _make_project()
        project.airfoil_sections = [
            AirfoilDef(name="raiz", r_norm=0.15, source="analytical", cd0=0.02),
            AirfoilDef(name="ponta", r_norm=1.0, source="analytical", cd0=0.008),
        ]
        cond = FlightCondition(name="c", mu_x=0.0, collective_deg=8.0, Vz=0.0, rpm=600)
        result = studies.run_single_case(project, cond)
        self.assertTrue(np.isfinite(result.summary["CT"]))
        self.assertGreater(result.summary["CT"], 0.0)


class TestBatchesSavedCasesRoundTrip(unittest.TestCase):
    """docs/plano_v3.md Part 3.1: Project.batches/saved_cases survive
    save_bemt_list -> load_bemt_list identically (dataclasses.asdict
    compared)."""

    def test_batches_round_trip(self):
        import tempfile
        from zbemt.models import save_bemt_list, load_bemt_list
        batches = [
            BatchDefinition(name="hover_sweep",
                             conditions=[FlightCondition(name="c1", mu_x=0.0, rpm=600.0),
                                         FlightCondition(name="c2", mu_x=0.1, rpm=650)],
                             sweep_kind="factorial", sweep_params={"mu_x": [0.0, 0.1]},
                             outdir="out", plots=["performance"]),
            BatchDefinition(name="forward_flight_grid"),
        ]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "batches.bemt")
            save_bemt_list(batches, path)
            loaded = load_bemt_list(BatchDefinition, path)
        self.assertEqual([asdict(b) for b in loaded], [asdict(b) for b in batches])

    def test_saved_cases_round_trip(self):
        import tempfile
        from zbemt.models import save_bemt_list, load_bemt_list
        cases = [
            FlightCondition(name="takeoff_hover", mu_x=0.0, collective_deg=10.0, Vz=0.0, rpm=None),
            FlightCondition(name="cruise", mu_x=0.25, collective_deg=6.0, Vz=1.5, rpm=650.0),
        ]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "saved_cases.bemt")
            save_bemt_list(cases, path)
            loaded = load_bemt_list(FlightCondition, path)
        self.assertEqual([asdict(c) for c in loaded], [asdict(c) for c in cases])

    def test_project_batches_and_saved_cases_survive_save_open(self):
        from zbemt import api
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            project_path = os.path.join(d, "proj")
            project = api.new_project(project_path)
            project.batches = [BatchDefinition(name="b1", conditions=[FlightCondition(name="c", mu_x=0.1, rpm=600.0)])]
            project.saved_cases = [FlightCondition(name="s1", mu_x=0.05, collective_deg=9.0, rpm=600.0)]
            api.save_project(project)
            reloaded = api.open_project(project_path)
        self.assertEqual([b.name for b in reloaded.batches], ["b1"])
        self.assertEqual(reloaded.batches[0].conditions[0].mu_x, 0.1)
        self.assertEqual([c.name for c in reloaded.saved_cases], ["s1"])
        self.assertEqual(reloaded.saved_cases[0].collective_deg, 9.0)


if __name__ == "__main__":
    unittest.main()


class TestCancelamentoDentroDoCaso(unittest.TestCase):
    """The old semantics was 'cancel BETWEEN cases': a single case in production mesh
    ignored the Cancel button until it finished by itself -- which is
    exactly when you want to cancel. Now the engine consults
    `should_cancel` once per solver iteration."""

    def setUp(self):
        # high max_iter and impossible tol: without cancellation this solve
        # would waste all 400 iterations
        self.project = _make_project(solver="fixed_point", max_iter=400, tol=1e-14)
        self.condition = FlightCondition(name="long", mu_x=0.2, collective_deg=8.0, rpm=600.0)

    def test_cancelling_mid_solve_raises_solvecancelled(self):
        iterations = {"n": 0}

        def cancel_on_third():
            iterations["n"] += 1
            return iterations["n"] >= 3

        with self.assertRaises(SolveCancelled):
            studies.run_single_case(self.project, self.condition,
                                     should_cancel=cancel_on_third)
        # stopped at the 3rd query, not at 400 iterations
        self.assertLess(iterations["n"], 10)

    def test_without_cancellation_the_solve_runs_normally(self):
        calls = {"n": 0}

        def never_cancels():
            calls["n"] += 1
            return False

        result = studies.run_single_case(self.project, self.condition,
                                          should_cancel=never_cancels)
        self.assertIn("CT", result.summary)
        self.assertGreater(calls["n"], 1, "should_cancel should be polled once per iteration")

    def test_should_cancel_none_is_the_untouched_default_path(self):
        result = studies.run_single_case(self.project, self.condition)
        self.assertIn("CT", result.summary)

    def test_batch_stops_at_the_running_case_and_returns_the_completed_ones(self):
        """The interrupted case is DISCARDED: a solve that didn't converge
        returned halfway would pass as a valid result."""
        batch = BatchDefinition(sweep_kind="mu_sweep",
                                sweep_params={"mu_values": [0.1, 0.2, 0.3], "rpm": 600.0})
        completed = []

        calls_after_case1 = {"n": 0}

        def cancel_inside_second():
            """Let the 1st case finish completely. After it, the FIRST
            query is the between-case check -- returning False there,
            we guarantee that the 2nd case really STARTS to solve, and the
            cancellation happens inside the solve, not before it."""
            if not completed:
                return False
            calls_after_case1["n"] += 1
            return calls_after_case1["n"] > 1

        results = studies.run_batch(
            self.project, batch,
            on_case_done=lambda i, total, r: completed.append(r),
            should_cancel=cancel_inside_second)

        self.assertGreaterEqual(calls_after_case1["n"], 2,
                                 "the cancellation never made it into the 2nd case's solve")
        self.assertEqual(len(results), 1, "the interrupted case must not be returned")
        # cancellation is not a failure: no exception delivered as "case with error"
        self.assertFalse([c for c in completed if isinstance(c, Exception)])


class TestRunCaseTrimmed(unittest.TestCase):
    """`run_case_trimmed` fixes RPM or collective (the other stays free) and
    solves by bisection until `summary["Thrust"]`/`summary["CT"]` matches a
    target -- see `TestRunSingleCase.test_collective_deg_changes_thrust`
    (more collective -> more thrust at fixed rpm), the same monotonicity that
    makes bisection safe here."""

    def setUp(self):
        self.project = _make_project()

    def test_solve_collective_hits_target_thrust(self):
        cond = FlightCondition(name="c1", mu_x=0.0, rpm=600.0)
        baseline = studies.run_single_case(self.project, replace(cond, collective_deg=8.0))
        target = baseline.summary["Thrust"]

        res = studies.run_case_trimmed(
            self.project, cond, trim_mode="solve_collective",
            target_kind="thrust", target_value=target)

        self.assertAlmostEqual(res.summary["Thrust"], target, delta=abs(target) * 1e-3 + 1e-6)
        self.assertAlmostEqual(res.summary["collective_deg"], 8.0, places=2)

    def test_solve_rpm_hits_target_ct(self):
        cond = FlightCondition(name="c1", mu_x=0.0, collective_deg=8.0, rpm=600.0)
        baseline = studies.run_single_case(self.project, cond)
        target = baseline.summary["CT"]

        res = studies.run_case_trimmed(
            self.project, FlightCondition(name="c1", mu_x=0.0, collective_deg=8.0, rpm=900.0),
            trim_mode="solve_rpm", target_kind="CT", target_value=target,
            bracket=(200.0, 2000.0))

        self.assertAlmostEqual(res.summary["CT"], target, delta=abs(target) * 1e-3 + 1e-9)
        self.assertAlmostEqual(res.summary["rpm"], 600.0, delta=5.0)

    def test_target_outside_bracket_raises_with_actionable_message(self):
        cond = FlightCondition(name="c1", mu_x=0.0, rpm=600.0)
        with self.assertRaises(ValueError) as ctx:
            studies.run_case_trimmed(
                self.project, cond, trim_mode="solve_collective",
                target_kind="thrust", target_value=1e9, bracket=(-10.0, 30.0))
        self.assertIn("not bracketed", str(ctx.exception))
        self.assertIn("Widen", str(ctx.exception))

    def test_unknown_trim_mode_raises(self):
        cond = FlightCondition(name="c1", mu_x=0.0, rpm=600.0)
        with self.assertRaises(ValueError):
            studies.run_case_trimmed(
                self.project, cond, trim_mode="bogus", target_kind="thrust", target_value=10.0)

    def test_should_cancel_raises_solvecancelled_between_iterations(self):
        cond = FlightCondition(name="c1", mu_x=0.0, rpm=600.0)
        chamadas = {"n": 0}

        def cancelar_logo():
            chamadas["n"] += 1
            return chamadas["n"] > 2

        with self.assertRaises(SolveCancelled):
            studies.run_case_trimmed(
                self.project, cond, trim_mode="solve_collective",
                target_kind="thrust", target_value=50.0, should_cancel=cancelar_logo)


class TestCompareGeometriesTrim(unittest.TestCase):
    """`compare_geometries(trim=...)` holds Thrust/CT CONSTANT across the
    variants: the first label is the reference, and every other variant is
    bisected onto its per-condition target by `run_case_trimmed`. The
    degree of freedom follows the project convention (propeller -> rpm,
    rotor -> collective)."""

    def setUp(self):
        self.project = _make_project()

    def _variants(self):
        fat = studies.variant_geometry(
            self.project.geometry,
            {"root_chord_norm": 0.16, "tip_chord_norm": 0.08})
        return {"base": self.project.geometry, "fat": fat}

    def test_thrust_trim_matches_reference_per_condition(self):
        conditions = [FlightCondition(name="hover", mu_x=0.0, rpm=600.0),
                      FlightCondition(name="edge", mu_x=0.1, rpm=600.0)]
        results = studies.compare_geometries(
            self.project, self._variants(), conditions, trim="thrust")
        self.assertEqual(len(results), 4)
        by_label = {}
        for res in results:
            by_label.setdefault(res.summary["geometry_label"], []).append(res)
        for base_res, fat_res in zip(by_label["base"], by_label["fat"]):
            self.assertEqual(fat_res.condition_name, base_res.condition_name)
            target = base_res.summary["Thrust"]
            self.assertAlmostEqual(fat_res.summary["Thrust"], target,
                                   delta=abs(target) * 2e-3 + 1e-9)
            self.assertEqual(fat_res.summary["trim_dof"], "collective_deg")
            self.assertAlmostEqual(fat_res.summary["trim_target"], target, places=9)
            self.assertGreaterEqual(fat_res.summary["trim_dof_value"], -10.0)
        for res in by_label["base"]:
            self.assertTrue(res.summary.get("trim_reference"))
            self.assertNotIn("trim_target", res.summary)

    def test_ct_trim_matches_coefficient(self):
        results = studies.compare_geometries(
            self.project, self._variants(),
            [FlightCondition(name="hover", mu_x=0.0, rpm=600.0)], trim="CT")
        base, fat = results[0], results[-1]
        self.assertAlmostEqual(fat.summary["CT"], base.summary["CT"],
                               delta=abs(base.summary["CT"]) * 2e-3 + 1e-12)

    def test_invalid_trim_rejected_before_any_solve(self):
        with unittest.mock.patch.object(studies, "run_single_case") as spy:
            with self.assertRaises(ValueError):
                studies.compare_geometries(
                    self.project, self._variants(),
                    [FlightCondition(name="c", mu_x=0.0, rpm=600.0)],
                    trim="lift")
            spy.assert_not_called()

    def test_unreachable_target_error_names_variant_and_condition(self):
        conditions = [FlightCondition(name="hover", mu_x=0.0, rpm=600.0)]
        boom = ValueError("not bracketed between collective_deg=-10.0 and 30.0")
        with unittest.mock.patch.object(studies, "run_case_trimmed",
                                        side_effect=boom):
            with self.assertRaises(ValueError) as ctx:
                studies.compare_geometries(
                    self.project, self._variants(), conditions, trim="thrust")
        message = str(ctx.exception)
        for fragment in ("fat", "hover", "Thrust"):
            self.assertIn(fragment, message)

    def test_propeller_convention_solves_rpm(self):
        """cfg_is_propeller in the reference summary selects solve_rpm."""
        recorded = {}

        def fake_trimmed(project, condition, *, trim_mode, target_kind,
                         target_value, **kwargs):
            recorded["trim_mode"] = trim_mode
            return studies.run_single_case(project, condition)

        project = replace(self.project)
        project.config = dict(self.project.config, is_propeller=True)
        with unittest.mock.patch.object(studies, "run_case_trimmed",
                                        side_effect=fake_trimmed):
            studies.compare_geometries(
                project, self._variants(),
                [FlightCondition(name="cruise", mu_x=0.1, rpm=600.0)],
                trim="thrust")
        self.assertEqual(recorded["trim_mode"], "solve_rpm")


class TestPlanformMetricsInComparison(unittest.TestCase):
    """Every comparison result carries the classic planform metrics of
    its geometry (AR = 1/∫c d(r/R), solidity σ = n·I/π) so the ranking,
    overlays and CSV can compare SHAPE, not only operating points."""

    def test_metrics_match_the_trapezoid_integral(self):
        geom = geometry.generate_tapered(root_chord_norm=0.10,
                                          tip_chord_norm=0.04,
                                          twist_root_deg=8.0,
                                          twist_tip_deg=2.0,
                                          radius_m=1.0, n_blades=3,
                                          n_stations=12)
        metrics = studies._blade_planform_metrics(geom)
        r = np.asarray(geom.r_norm)
        c = np.asarray(geom.chord_norm)
        # getattr's default is evaluated eagerly, so `getattr(np,
        # "trapezoid", np.trapz)` touches np.trapz even when trapezoid
        # exists -- and numpy >= 2.x raises for the expired alias.
        if hasattr(np, "trapezoid"):
            trapz = np.trapezoid
        else:                                   # pragma: no cover
            trapz = np.trapz
        integral = float(trapz(c, r))
        self.assertAlmostEqual(metrics["aspect_ratio"], 1.0 / integral, places=9)
        self.assertAlmostEqual(metrics["solidity"], 3 * integral / np.pi, places=9)

    def test_compare_geometries_summaries_carry_metrics(self):
        project = _make_project()
        base = project.geometry
        fat = studies.variant_geometry(base, {"tip_chord_norm": 0.12})
        results = studies.compare_geometries(
            project, {"base": base, "fat": fat},
            [FlightCondition(name="hover", mu_x=0.0, rpm=600.0)])
        for res in results:
            self.assertIn("aspect_ratio", res.summary)
            self.assertIn("solidity", res.summary)
        self.assertLess(results[-1].summary["aspect_ratio"],
                        results[0].summary["aspect_ratio"],
                        "a fatter tip means more blade area, hence lower AR")


class TestTableSpaceOverrides(unittest.TestCase):
    """On a base without a parametric generator, planform parameters are
    applied IN TABLE SPACE — and shape-preservingly: an elliptic blade
    swept in tip chord stays elliptic, with only the scale factor
    varying linearly from root to tip."""

    def _custom_elliptic(self):
        r = np.linspace(0.2, 1.0, 15)
        c = 0.12 * np.sqrt(np.clip(1.0 - ((r - 0.5) / 0.6) ** 2, 0.0, 1.0))
        t = 10.0 - 6.0 * (r - 0.2) / 0.8
        return geometry.generate_custom(r.tolist(), c.tolist(), t.tolist(),
                                         radius_m=1.0, n_blades=4)

    def test_tip_chord_target_preserves_the_shape(self):
        base = self._custom_elliptic()
        target_tip = 0.08
        out = studies.variant_geometry(base, {"tip_chord_norm": target_tip})
        new = np.asarray(out.chord_norm)
        old = np.asarray(base.chord_norm)
        r = np.asarray(base.r_norm)
        x = (r - r[0]) / (r[-1] - r[0])
        f_tip = target_tip / old[-1]
        expected = old * (1.0 + (f_tip - 1.0) * x)
        self.assertAlmostEqual(new[-1], target_tip, places=12)
        np.testing.assert_allclose(new, expected, rtol=1e-12)

    def test_root_and_tip_targets_match_both_endpoints(self):
        base = self._custom_elliptic()
        out = studies.variant_geometry(base, {"root_chord_norm": 0.15,
                                               "tip_chord_norm": 0.05})
        self.assertAlmostEqual(out.chord_norm[0], 0.15, places=12)
        self.assertAlmostEqual(out.chord_norm[-1], 0.05, places=12)

    def test_twist_shift_preserves_the_shape(self):
        base = self._custom_elliptic()
        out = studies.variant_geometry(base, {"twist_root_deg": 12.0,
                                               "twist_tip_deg": 6.0})
        old = np.asarray(base.twist_deg)
        new = np.asarray(out.twist_deg)
        self.assertAlmostEqual(new[0], 12.0, places=12)
        self.assertAlmostEqual(new[-1], 6.0, places=12)
        delta = new - old
        # the offset itself is linear in x: second difference ~ 0
        self.assertLess(float(np.max(np.abs(np.diff(delta, 2)))), 1e-12)

    def test_uniform_scales_hit_mean_and_peak(self):
        base = self._custom_elliptic()
        out_mean = studies.variant_geometry(base, {"chord_norm": 0.09})
        self.assertAlmostEqual(float(np.mean(out_mean.chord_norm)), 0.09, places=12)
        out_peak = studies.variant_geometry(base, {"max_chord_norm": 0.15})
        self.assertAlmostEqual(float(np.max(out_peak.chord_norm)), 0.15, places=12)

    def test_parametric_base_still_regenerates_exactly(self):
        base = geometry.generate_tapered(root_chord_norm=0.10,
                                          tip_chord_norm=0.04,
                                          twist_root_deg=8.0,
                                          twist_tip_deg=2.0,
                                          n_stations=10)
        out = studies.variant_geometry(base, {"tip_chord_norm": 0.06})
        self.assertEqual(out.origin_params.get("kind"), "tapered")
        self.assertAlmostEqual(out.chord_norm[-1], 0.06, places=12)


class TestOptimizeDesignPathsAgree(unittest.TestCase):
    """SC-8 vs SC-13 on the same single-objective study: the
    derivative-free search and the evolutionary search must land within
    two percent of each other, and a binding constraint must hold."""

    def _project(self):
        return _make_project()

    def test_one_objective_two_paths_within_two_percent(self):
        from dataclasses import replace as dc_replace
        from zbemt.models import (FlightCondition, OptimizationDefinition,
                                   DesignVariable)
        condition = FlightCondition(name="opt", mu_x=0.0,
                                     collective_deg=8.0, rpm=600.0)
        base = OptimizationDefinition(
            name="fm",
            objective_kind="maximize",
            objective_key="FM",
            variables=[DesignVariable(param="tip_chord_norm", lower=0.03,
                                       upper=0.06)],
            method="powell", max_evals=40,
            condition=condition)
        project = self._project()
        single = studies.optimize_design(project, base)

        pareto_def = dc_replace(base, algorithm="nsga2", population=8,
                                 generations=6, seed=3)
        multi = studies.optimize_design_multi(project, pareto_def)
        best_multi = max(v["FM"] for v in multi.front_values)
        # The absolute level depends on the condition; what must hold is
        # that both searches agree on it.
        rel = abs(best_multi - single.best_value) / single.best_value
        self.assertLess(rel, 0.02,
                         f"paths disagree: powell {single.best_value:.5f} "
                         f"vs nsga2 {best_multi:.5f}")

    def test_a_constraint_binds_every_front_member(self):
        from dataclasses import replace as dc_replace
        from zbemt.models import (ConstraintDef, DesignVariable,
                                   FlightCondition, ObjectiveDef,
                                   OptimizationDefinition)
        condition = FlightCondition(name="opt", mu_x=0.0,
                                     collective_deg=8.0, rpm=600.0)
        definition = OptimizationDefinition(
            name="bound",
            objectives=[ObjectiveDef(key="FM", kind="maximize")],
            constraints=[ConstraintDef(key="CT", operator=">=", value=0.008)],
            variables=[DesignVariable(param="root_chord_norm", lower=0.07,
                                       upper=0.15),
                        DesignVariable(param="tip_chord_norm", lower=0.02,
                                        upper=0.09)],
            algorithm="nsga2", population=10, generations=4, seed=5,
            condition=condition)
        out = studies.optimize_design_multi(self._project(), definition)
        self.assertTrue(out.front_values)
        self.assertNotIn("no design satisfied the constraints",
                          out.message)
        for values in out.front_values:
            # The floor sits above what the minimum-chord corner reaches,
            # so satisfaction proves the constraint actually binds.
            self.assertGreaterEqual(values["CT"], 0.008 - 1e-9)

    def test_an_unreachable_constraint_is_reported_as_such(self):
        from dataclasses import replace as dc_replace
        from zbemt.models import (ConstraintDef, DesignVariable,
                                   FlightCondition, ObjectiveDef,
                                   OptimizationDefinition)
        condition = FlightCondition(name="opt", mu_x=0.0,
                                     collective_deg=8.0, rpm=600.0)
        definition = OptimizationDefinition(
            name="impossible",
            objectives=[ObjectiveDef(key="FM", kind="maximize")],
            constraints=[ConstraintDef(key="CT", operator=">=", value=99.0)],
            variables=[DesignVariable(param="tip_chord_norm", lower=0.03,
                                       upper=0.06)],
            algorithm="nsga2", population=8, generations=2, seed=5,
            condition=condition)
        out = studies.optimize_design_multi(self._project(), definition)
        self.assertIn("no design satisfied the constraints", out.message)


class TestTableSpaceGuards(unittest.TestCase):
    """Item 5, findings 3 and 4: the table-space planform applier must
    refuse what it cannot honor instead of silently keeping a fallback
    factor or letting the last chord target win."""

    def _table_geometry(self, chords):
        from zbemt import geometry as geometry_gen
        n = len(chords)
        r = [0.2 + 0.8 * i / (n - 1) for i in range(n)]
        return geometry_gen.generate_custom(r, list(chords),
                                             [8.0] * n, radius_m=1.0)

    def test_near_zero_endpoint_raises_naming_everything(self):
        from zbemt import studies
        geom = self._table_geometry([0.0, 0.05, 0.08])
        with self.assertRaises(ValueError) as ctx:
            studies._apply_table_space_planform(
                geom, {"root_chord_norm": 0.10})
        message = str(ctx.exception)
        for fragment in ("root", "requested", "0.1"):
            self.assertIn(fragment, message)

    def test_two_absolute_chord_targets_are_rejected(self):
        from zbemt import studies
        geom = self._table_geometry([0.10, 0.07, 0.05])
        with self.assertRaises(ValueError) as ctx:
            studies._apply_table_space_planform(
                geom, {"chord_norm": 0.09, "max_chord_norm": 0.12})
        message = str(ctx.exception)
        self.assertIn("chord_norm", message)
        self.assertIn("max_chord_norm", message)

    def test_endpoint_pair_cannot_combine_with_an_absolute_target(self):
        from zbemt import studies
        geom = self._table_geometry([0.10, 0.07, 0.05])
        with self.assertRaises(ValueError) as ctx:
            studies._apply_table_space_planform(
                geom, {"root_chord_norm": 0.11,
                        "max_chord_norm": 0.12})
        self.assertIn("max_chord_norm", str(ctx.exception))

    def test_single_targets_still_apply(self):
        from zbemt import studies
        geom = self._table_geometry([0.10, 0.07, 0.05])
        out = studies._apply_table_space_planform(
            geom, {"max_chord_norm": 0.12})
        self.assertAlmostEqual(max(out.chord_norm), 0.12, places=12)


class TestCompareValidatesVariants(unittest.TestCase):
    """Item 5, finding 1: a variant that cannot fly physically must stop
    the comparison BEFORE the first solve, with its label attached."""

    def test_negative_chord_variant_raises_before_any_solve(self):
        import unittest.mock
        from zbemt import geometry as geometry_gen
        from zbemt import studies
        geom = geometry_gen.generate_custom(
            [0.2, 0.6, 1.0], [-0.05, 0.07, 0.05], [8.0] * 3, radius_m=1.0)
        project = _make_project()
        calls = []
        with unittest.mock.patch.object(
                studies, "run_single_case",
                side_effect=lambda *a, **k: calls.append(1)):
            with self.assertRaises(ValueError) as ctx:
                studies.compare_geometries(
                    project, {"bad": geom}, conditions=[])
        self.assertIn("bad", str(ctx.exception))
        self.assertEqual(calls, [], "no solve may run on an invalid "
                                     "variant")


class TestVariantDefPayload(unittest.TestCase):
    """SC-7a: a variant may carry its own airfoil; such results are
    marked non_geometry_variant so the fairness caveat can be shown."""

    def test_variant_with_own_airfoil_is_flagged_and_runs(self):
        import unittest.mock
        from dataclasses import replace
        from zbemt import geometry as geometry_gen
        from zbemt import studies
        from zbemt.models import FlightCondition, VariantDef
        geom_a = geometry_gen.generate_tapered(root_chord_norm=0.10,
                                                 tip_chord_norm=0.05,
                                                 radius_m=1.0, n_stations=6)
        geom_b = geometry_gen.generate_tapered(root_chord_norm=0.12,
                                                 tip_chord_norm=0.06,
                                                 radius_m=1.0, n_stations=6)
        project = _make_project()
        own_airfoil = replace(project.airfoil)
        variants = {
            "base": geom_a,
            "wide": VariantDef(geometry=geom_b, airfoil=own_airfoil),
        }
        conditions = [FlightCondition(name="h", mu_x=0.0,
                                       collective_deg=8.0, rpm=600.0)]

        results = studies.compare_geometries(variants=variants,
                                              project=project,
                                              conditions=conditions)
        by_label = {}
        for res in results:
            by_label.setdefault(res.summary["geometry_label"],
                                []).append(res)
        self.assertFalse(any("non_geometry_variant" in r.summary
                              for r in by_label["base"]))
        self.assertTrue(all(r.summary.get("non_geometry_variant")
                             for r in by_label["wide"]))


class TestCompareParallel(unittest.TestCase):
    """Item 5, phase 5.2: workers > 1 runs the UNTRIMMED sweep on a
    process pool with the same ordered results as the serial path; the
    trimmed path stays serial (every case depends on the reference
    targets)."""

    def _variants(self, project):
        from dataclasses import replace as dc_replace
        a = project.geometry
        b = dc_replace(a, n_blades=a.n_blades + 1)
        return {"base": a, "other": b}

    def _conditions(self):
        from zbemt.models import FlightCondition
        return [FlightCondition(name="h", mu_x=0.0, collective_deg=8.0,
                                 rpm=600.0),
                 FlightCondition(name="f", mu_x=0.1, collective_deg=8.0,
                                  rpm=600.0)]

    def test_pool_matches_serial_in_order_and_values(self):
        project = _make_project()
        variants = self._variants(project)
        conditions = self._conditions()
        serial = studies.compare_geometries(project, dict(variants),
                                             conditions=conditions,
                                             workers=1)
        parallel = studies.compare_geometries(project, dict(variants),
                                               conditions=conditions,
                                               workers=2)
        self.assertEqual(len(serial), len(parallel))
        for s_res, p_res in zip(serial, parallel):
            self.assertEqual(s_res.summary["geometry_label"],
                              p_res.summary["geometry_label"])
            self.assertEqual(s_res.condition_name, p_res.condition_name)
            self.assertAlmostEqual(s_res.summary["Thrust"],
                                    p_res.summary["Thrust"], places=9)

    def test_trimmed_run_with_workers_stays_correct(self):
        project = _make_project()
        variants = self._variants(project)
        results = studies.compare_geometries(
            project, dict(variants), conditions=self._conditions(),
            trim="thrust", workers=4)
        labels = [r.summary["geometry_label"] for r in results]
        self.assertEqual(labels, ["base", "base", "other", "other"])
