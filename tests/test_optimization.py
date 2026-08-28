"""Verify the multi-objective design optimization orchestration (SC-13).

The searches themselves are exercised through ``studies.optimize_design_multi``
with a STUBBED evaluation function, so these tests run in milliseconds and pin
the CONTRACT, not the physics: constraints read raw summary values even when
the constrained quantity is a maximized objective; constraint keys ride along
in every evaluation record; front values come back in the user's own
direction; cancellation returns the partial front; parameter names replace the
searches' positional v0/v1 keys.
"""

import os
import math
import unittest
from unittest.mock import patch

import numpy as np

from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from zbemt.models import (ConstraintDef, DesignVariable,
                           FlightCondition, OptimizationDefinition,
                           ObjectiveDef, Results)
from zbemt.studies import optimize_design_multi


def _fake_results(root: float, tip: float) -> Results:
    """A smooth two-objective toy over root_chord_norm x tip_chord_norm:
    thrust grows with chord, figure of merit falls with chord."""
    ct = 0.006 + 0.10 * (root - 0.07) + 0.05 * (tip - 0.02)
    fm = 1.50 - 3.0 * (tip - 0.02) ** 2 - 0.5 * (root - 0.07) ** 2
    return Results(summary={"CT": ct, "FM": fm})


def _stub_evaluate(project, condition, params, should_cancel=None):
    return _fake_results(float(params["root_chord_norm"]),
                          float(params["tip_chord_norm"]))


def _definition(**overrides) -> OptimizationDefinition:
    base = OptimizationDefinition(
        name="contract",
        condition=FlightCondition(name="c", mu_x=0.1, collective_deg=8.0,
                                   rpm=800.0),
        variables=[DesignVariable(param="root_chord_norm", lower=0.07,
                                   upper=0.15),
                    DesignVariable(param="tip_chord_norm", lower=0.02,
                                    upper=0.09)],
        algorithm="nsga2", population=12, generations=6, seed=7)
    return replace(base, **overrides)


class TestConstraintSigns(unittest.TestCase):
    """SC-13: constraints read RAW summary values, never the negated
    view the minimization core sees."""

    def test_constraint_on_maximized_objective(self):
        # CT spans roughly 0.006..0.017 over the box, so 0.012 is
        # reachable from the initial stratified sweep.
        definition = _definition(
            objectives=[ObjectiveDef(key="CT", kind="maximize")],
            constraints=[ConstraintDef(key="CT", operator=">=", value=0.012)])
        with patch("zbemt.studies._evaluate_variant", _stub_evaluate):
            out = optimize_design_multi(_project(), definition)
        self.assertTrue(out.front_values)
        for values in out.front_values:
            # A negated sign would report CT below zero and mark every
            # design infeasible; raw reporting keeps the feasible ones.
            self.assertGreaterEqual(values["CT"], 0.012 - 1e-9)

    def test_constraint_key_not_among_objectives(self):
        definition = _definition(
            objectives=[ObjectiveDef(key="FM", kind="maximize")],
            constraints=[ConstraintDef(key="CT", operator=">=", value=0.012)])
        with patch("zbemt.studies._evaluate_variant", _stub_evaluate):
            out = optimize_design_multi(_project(), definition)
        self.assertTrue(out.front_values)
        for values in out.front_values:
            # The constraint key is not an objective; before it rode along
            # in every record, the Evaluator scored EVERY design as
            # maximally infeasible and the study silently degraded. It is
            # also REPORTED on each front member next to the objectives.
            self.assertIn("CT", values)
            self.assertGreaterEqual(values["CT"], 0.012 - 1e-9)


class TestRawFrontValues(unittest.TestCase):
    def test_maximize_reports_positive_raw_values(self):
        definition = _definition(
            objectives=[ObjectiveDef(key="FM", kind="maximize")])
        with patch("zbemt.studies._evaluate_variant", _stub_evaluate):
            out = optimize_design_multi(_project(), definition)
        self.assertTrue(out.front_values)
        for values in out.front_values:
            self.assertGreater(values["FM"], 1.485)

    def test_minimize_reports_the_smallest_raw_value(self):
        definition = _definition(
            objectives=[ObjectiveDef(key="FM", kind="minimize")])
        with patch("zbemt.studies._evaluate_variant", _stub_evaluate):
            out = optimize_design_multi(_project(), definition)
        best = min(v["FM"] for v in out.front_values)
        # Minimizing FM has ONE optimum, so the front collapses onto it;
        # the direction contract is that it found the far-corner minimum.
        self.assertLess(best, 1.49)

    def test_front_parameters_use_real_names(self):
        definition = _definition(
            objectives=[ObjectiveDef(key="FM", kind="maximize"),
                         ObjectiveDef(key="CT", kind="maximize")])
        with patch("zbemt.studies._evaluate_variant", _stub_evaluate):
            out = optimize_design_multi(_project(), definition)
        self.assertEqual(out.param_names, ["root_chord_norm",
                                            "tip_chord_norm"])
        self.assertEqual(out.objective_keys, ["FM", "CT"])
        for params in out.front_params:
            self.assertEqual(set(params), {"root_chord_norm",
                                            "tip_chord_norm"})


class TestDePath(unittest.TestCase):
    def test_de_maximize_uses_signs_not_the_scalar_flag(self):
        definition = _definition(
            objectives=[ObjectiveDef(key="FM", kind="maximize")],
            algorithm="de", population=16, generations=8)
        with patch("zbemt.studies._evaluate_variant", _stub_evaluate):
            out = optimize_design_multi(_project(), definition)
        self.assertEqual(len(out.front_values), 1)
        self.assertGreater(out.front_values[0]["FM"], 1.485)


class TestCancellation(unittest.TestCase):
    def test_mid_run_cancel_returns_partial_front(self):
        definition = _definition(
            objectives=[ObjectiveDef(key="FM", kind="maximize"),
                         ObjectiveDef(key="CT", kind="maximize")],
            population=16, generations=30)
        seen = {"n": 0}

        def stop_after_a_few():
            return seen["n"] > 25

        def progress(done, _total, _values):
            seen["n"] = done

        with patch("zbemt.studies._evaluate_variant", _stub_evaluate):
            out = optimize_design_multi(_project(), definition,
                                         on_progress=progress,
                                         should_cancel=stop_after_a_few)
        self.assertEqual(out.message, "cancelled")
        self.assertGreaterEqual(out.n_evals, 25)
        self.assertGreaterEqual(len(out.front_params), 1)

    def test_cancel_after_the_first_sweep_keeps_that_sweep(self):
        # The initial stratified sweep runs BEFORE the first cancel check,
        # so even an immediate stop reports its designs instead of nothing.
        definition = _definition(population=12,
                                  objectives=[ObjectiveDef(key="FM",
                                                            kind="maximize")])
        with patch("zbemt.studies._evaluate_variant", _stub_evaluate):
            out = optimize_design_multi(_project(), definition,
                                         should_cancel=lambda: True)
        self.assertEqual(out.message, "cancelled")
        self.assertEqual(out.n_evals, 12)
        self.assertGreaterEqual(len(out.front_params), 1)

    def test_cancel_inside_the_evaluation_reports_empty_outcome(self):
        from zbemt.bemt import SolveCancelled

        def refusing_stub(project, condition, params, should_cancel=None):
            raise SolveCancelled()

        definition = _definition(
            objectives=[ObjectiveDef(key="FM", kind="maximize")])
        with patch("zbemt.studies._evaluate_variant", refusing_stub):
            out = optimize_design_multi(_project(), definition,
                                         should_cancel=lambda: True)
        self.assertEqual(out.message, "cancelled")
        self.assertEqual(out.front_params, [])


class TestSearchAlgorithms(unittest.TestCase):
    """Unit tests of the algorithm module against analytic functions,
    so the searches are pinned without the solver (SC-13)."""

    def test_non_dominated_sort_finds_the_known_fronts(self):
        from zbemt.optimization import _fast_non_dominated_sort
        F = np.array([[0.0, 1.0],    # front 0
                       [1.0, 0.0],    # front 0
                       [1.0, 1.0],    # dominated by both above -> front 1
                       [2.0, 2.0]])   # dominated by everything -> front 2
        ranks = _fast_non_dominated_sort(F)
        self.assertEqual(set(np.where(ranks == 0)[0]), {0, 1})
        self.assertEqual(set(np.where(ranks == 1)[0]), {2})
        self.assertEqual(set(np.where(ranks == 2)[0]), {3})

    def test_crowding_distance_boundaries_and_interior(self):
        from zbemt.optimization import crowding_distance
        F = np.array([[0.0, 2.0], [1.0, 1.0], [2.0, 0.0]])
        d = crowding_distance(F, np.array([0, 1, 2]))
        self.assertEqual(d[0], math.inf)     # boundary of the front
        self.assertEqual(d[2], math.inf)     # boundary of the front
        # Interior point: the two neighbors' spans, normalized per
        # objective: ((2-0)/2) + ((2-0)/2) = 2.
        self.assertAlmostEqual(d[1], 2.0, places=12)

    def test_constraint_domination_rule(self):
        from zbemt.optimization import constrained_dominates
        feasible = 0.0
        infeasible = 0.5
        worse = 1.5
        f_good = np.array([1.0, 1.0])
        f_bad = np.array([0.0, 0.0])   # better objectives, but INFEASIBLE
        # A feasible design beats an infeasible one regardless of values.
        self.assertTrue(constrained_dominates(feasible, infeasible,
                                               f_good, f_bad))
        # Two infeasible ones order by total violation alone.
        self.assertTrue(constrained_dominates(infeasible, worse,
                                               f_bad, f_bad))
        self.assertFalse(constrained_dominates(worse, infeasible,
                                                f_bad, f_bad))
        # Two feasible ones compare by plain objective domination.
        self.assertTrue(constrained_dominates(0.0, 0.0,
                                               np.array([1.0, 0.0]),
                                               np.array([1.0, 1.0])))
        self.assertFalse(constrained_dominates(0.0, 0.0,
                                                np.array([1.0, 1.0]),
                                                np.array([1.0, 1.0])))

    def test_integer_repair_keeps_whole_values_in_bounds(self):
        from zbemt.optimization import repair_integers
        lower = np.array([0.07, 2.0])
        upper = np.array([0.15, 6.0])
        mask = np.array([False, True])
        x = repair_integers(np.array([0.11, 3.7]), mask, lower, upper)
        self.assertAlmostEqual(x[0], 0.11)
        self.assertEqual(x[1], 4.0)
        x = repair_integers(np.array([0.11, 300.0]), mask, lower, upper)
        self.assertEqual(x[1], 6.0)   # clipped back into its bounds

    def test_nsga2_is_deterministic_for_a_fixed_seed(self):
        from zbemt.optimization import nsga2

        def evaluate(x):
            return {"a": float(x[0] ** 2), "b": float((x[0] - 1.0) ** 2)}

        bounds = np.array([0.0]), np.array([1.0])
        one = nsga2(evaluate, *bounds, objective_keys=["a", "b"],
                     population=10, generations=5, seed=11)
        two = nsga2(evaluate, *bounds, objective_keys=["a", "b"],
                     population=10, generations=5, seed=11)
        self.assertEqual(one.front_params, two.front_params)
        self.assertEqual(len(one.front_values), len(two.front_values))
        for va, vb in zip(one.front_values, two.front_values):
            self.assertEqual(va, vb)

    def test_cancellation_between_generations_raises_solvecancelled(self):
        """Plan item 7: a cancel request between generations surfaces as
        SolveCancelled -- SearchCancelled is its subclass carrying the
        ledger."""
        from zbemt.bemt import SolveCancelled
        from zbemt.optimization import nsga2

        def evaluate(x):
            return {"a": float(x[0]), "b": float(x[0])}

        with self.assertRaises(SolveCancelled):
            nsga2(evaluate, np.array([0.0]), np.array([1.0]),
                   objective_keys=["a", "b"], population=8, generations=4,
                   seed=1, should_cancel=lambda: True)

    def test_zdt1_reaches_the_analytic_front(self):
        """NSGA-II on ZDT1 (30 variables): the final front's generational
        distance to f2 = 1 - sqrt(f1) stays below the stated threshold."""
        from zbemt.optimization import nsga2

        n_var = 30

        def zdt1(x):
            g = 1.0 + 9.0 * float(np.mean(x[1:]))
            return {"f1": float(x[0]),
                     "f2": float(g * (1.0 - np.sqrt(x[0] / g)))}

        out = nsga2(zdt1, np.zeros(n_var), np.ones(n_var),
                     objective_keys=["f1", "f2"], population=40,
                     generations=50, seed=42)
        front = np.array([[v["f1"], v["f2"]]
                           for v in out.front_values if v["f1"] > 1e-8])
        self.assertGreaterEqual(len(front), 5)
        analytic = 1.0 - np.sqrt(front[:, 0])
        gd = float(np.mean(np.sqrt((front[:, 1] - analytic) ** 2)))
        # Measured 0.078 at this budget (pop 40 x 50); the threshold
        # catches collapsed or drifted fronts with room to spare.
        self.assertLess(gd, 0.12,
                         f"generational distance {gd:.4f} too far from "
                         "the analytic ZDT1 front")


def _project():
    from tests.helpers import make_studies_project
    return make_studies_project()


class TestPolynomialMutationIsBounded(unittest.TestCase):
    """`SC-13`. Deb's polynomial mutation scales its step by the distance
    to the NEARER bound, so the mutated value is inside the box by
    construction.

    The simplified form -- draw the step from u alone, then clip -- was
    used here. In the middle of the range the two are the same operator.
    Near an edge they are not: every step that would have left the box
    landed exactly ON the bound, so the bounds collected probability
    mass the operator never meant to give them. A search whose optimum
    sits at a bound then looks converged because the operator kept
    putting designs there, not because the search found them.
    """

    def _samples(self, start, n=4000, eta=20.0, seed=0):
        import numpy as np
        from zbemt.optimization import polynomial_mutation

        rng = np.random.default_rng(seed)
        lower, upper = np.array([0.0]), np.array([1.0])
        return np.array([
            polynomial_mutation(rng, np.array([start]), lower, upper,
                                 eta, 1.0)[0] for _ in range(n)])

    def test_no_mass_piles_on_a_bound(self):
        for start in (0.001, 0.02, 0.98, 0.999):
            with self.subTest(x=start):
                values = self._samples(start)
                on_bound = ((values <= 1e-12) | (values >= 1.0 - 1e-12)).mean()
                self.assertLess(on_bound, 0.01,
                                 "the clip is doing the operator's job")

    def test_it_stays_inside_the_box(self):
        values = self._samples(0.02)
        self.assertGreaterEqual(values.min(), 0.0)
        self.assertLessEqual(values.max(), 1.0)

    def test_it_is_symmetric_in_the_middle(self):
        """Away from both bounds the operator has no reason to prefer a
        direction, so the mean stays on the starting point."""
        values = self._samples(0.5, n=8000)
        self.assertAlmostEqual(float(values.mean()), 0.5, delta=0.01)

    def test_it_leans_away_from_a_near_bound(self):
        """At x = 0.02 there is far more room above than below, and the
        bounded operator uses it. The clipped form could not: it drew
        the same symmetric step and lost half of it to the bound."""
        values = self._samples(0.02, n=8000)
        self.assertGreater(float(values.mean()), 0.02)

    def test_a_zero_rate_changes_nothing(self):
        import numpy as np
        from zbemt.optimization import polynomial_mutation

        rng = np.random.default_rng(3)
        x = np.array([0.3, 0.7])
        out = polynomial_mutation(rng, x, np.array([0.0, 0.0]),
                                   np.array([1.0, 1.0]), 20.0, 0.0)
        np.testing.assert_allclose(out, x)

    def test_a_variable_with_no_range_survives(self):
        """lower == upper is a pinned variable, not a division by zero."""
        import numpy as np
        from zbemt.optimization import polynomial_mutation

        rng = np.random.default_rng(4)
        out = polynomial_mutation(rng, np.array([2.0]), np.array([2.0]),
                                   np.array([2.0]), 20.0, 1.0)
        self.assertTrue(np.all(np.isfinite(out)))
        self.assertAlmostEqual(float(out[0]), 2.0)


if __name__ == "__main__":
    unittest.main()
