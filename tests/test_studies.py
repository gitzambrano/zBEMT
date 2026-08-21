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
        self.condition = FlightCondition(name="longo", mu_x=0.2, collective_deg=8.0, rpm=600.0)

    def test_cancelar_no_meio_do_solve_levanta_solvecancelled(self):
        iteracoes = {"n": 0}

        def cancelar_na_terceira():
            iteracoes["n"] += 1
            return iteracoes["n"] >= 3

        with self.assertRaises(SolveCancelled):
            studies.run_single_case(self.project, self.condition,
                                     should_cancel=cancelar_na_terceira)
        # stopped at the 3rd query, not at 400 iterations
        self.assertLess(iteracoes["n"], 10)

    def test_sem_cancelamento_o_solve_roda_normalmente(self):
        chamadas = {"n": 0}

        def nunca_cancela():
            chamadas["n"] += 1
            return False

        resultado = studies.run_single_case(self.project, self.condition,
                                             should_cancel=nunca_cancela)
        self.assertIn("CT", resultado.summary)
        self.assertGreater(chamadas["n"], 1, "should_cancel should be polled once per iteration")

    def test_should_cancel_none_e_o_caminho_default_intocado(self):
        resultado = studies.run_single_case(self.project, self.condition)
        self.assertIn("CT", resultado.summary)

    def test_batch_para_no_caso_em_andamento_e_devolve_os_concluidos(self):
        """The interrupted case is DISCARDED: a solve that didn't converge
        returned halfway would pass as a valid result."""
        batch = BatchDefinition(sweep_kind="mu_sweep",
                                sweep_params={"mu_values": [0.1, 0.2, 0.3], "rpm": 600.0})
        concluidos = []

        chamadas_pos_caso1 = {"n": 0}

        def cancelar_dentro_do_segundo():
            """Let the 1st case finish completely. After it, the FIRST
            query is the between-case check -- returning False there,
            we guarantee that the 2nd case really STARTS to solve, and the
            cancellation happens inside the solve, not before it."""
            if not concluidos:
                return False
            chamadas_pos_caso1["n"] += 1
            return chamadas_pos_caso1["n"] > 1

        resultados = studies.run_batch(
            self.project, batch,
            on_case_done=lambda i, total, r: concluidos.append(r),
            should_cancel=cancelar_dentro_do_segundo)

        self.assertGreaterEqual(chamadas_pos_caso1["n"], 2,
                                 "the cancellation never made it into the 2nd case's solve")
        self.assertEqual(len(resultados), 1, "the interrupted case must not be returned")
        # cancellation is not a failure: no exception delivered as "case with error"
        self.assertFalse([c for c in concluidos if isinstance(c, Exception)])


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
