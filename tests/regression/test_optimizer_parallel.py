"""`SC-13`/`PA-1`: the optimizer's worker count does something, and it
does not change the answer.

`parallel_workers` was persisted, offered as a spin box and parsed from
`--workers`, while the search evaluated one design after another. A
control that is real, saved and inert is worse than an absent one: the
user sets it, sees no change, and cannot tell whether the setting or the
machine is at fault.

Two properties matter and they pull against each other.

The search must actually be spread out, which the first class checks by
counting the blocks the evaluator is asked for -- NSGA-II asks for a
whole population at a time, so a population IS a block.

And the answer must not move. NSGA-II is deterministic for a fixed seed
only if the population keeps its ORDER: selection is positional and so
is the evaluation ledger the front is rebuilt from. Collecting futures
as they complete and writing each into the slot it was submitted from is
what preserves that, and the second class is what would catch its loss
-- a front that came back in completion order would differ run to run on
any machine with more than one core.

The engine is not exercised here. These tests drive the search core with
an analytic function, so they are fast and they fail for one reason.
"""
import unittest

import numpy as np

from zbemt.optimization import Evaluator, nsga2, repair_integers


def _zdt1(x):
    """A two-objective test function with a known concave front."""
    f1 = float(x[0])
    g = 1.0 + 9.0 * float(np.mean(x[1:])) if x.size > 1 else 1.0
    f2 = g * (1.0 - np.sqrt(max(f1, 0.0) / g))
    return {"f1": f1, "f2": float(f2)}


class TestTheBatchPathIsUsed(unittest.TestCase):

    def _run(self, mapper=None, population=8, generations=3):
        calls = {"blocks": 0, "designs": 0}

        def evaluate(x):
            calls["designs"] += 1
            return _zdt1(np.asarray(x, dtype=float))

        if mapper is not None:
            def map_many(xs):
                calls["blocks"] += 1
                calls["designs"] += len(xs)
                return [_zdt1(np.asarray(x, dtype=float)) for x in xs]

            evaluate.map_many = map_many

        lower = np.zeros(3)
        upper = np.ones(3)
        outcome = nsga2(evaluate, lower, upper, objective_keys=["f1", "f2"],
                        population=population, generations=generations,
                        seed=7)
        return outcome, calls

    def test_without_a_mapper_every_design_goes_one_at_a_time(self):
        _outcome, calls = self._run(mapper=None)
        self.assertEqual(calls["blocks"], 0)
        self.assertGreater(calls["designs"], 0)

    def test_with_a_mapper_the_search_asks_in_blocks(self):
        """One block for the initial population, one per generation."""
        _outcome, calls = self._run(mapper=True, generations=3)
        self.assertEqual(calls["blocks"], 4)

    def test_the_block_is_a_whole_population(self):
        _outcome, calls = self._run(mapper=True, population=8, generations=3)
        self.assertEqual(calls["designs"], 8 * 4)


class TestTheAnswerDoesNotMove(unittest.TestCase):
    """The property that makes the parallel path safe to use at all."""

    def _front(self, mapper, seed=11):
        def evaluate(x):
            return _zdt1(np.asarray(x, dtype=float))

        if mapper:
            def map_many(xs):
                return [_zdt1(np.asarray(x, dtype=float)) for x in xs]

            evaluate.map_many = map_many

        outcome = nsga2(evaluate, np.zeros(3), np.ones(3),
                        objective_keys=["f1", "f2"], population=12,
                        generations=5, seed=seed)
        return outcome

    def test_the_front_is_identical_with_and_without_the_mapper(self):
        serial = self._front(mapper=False)
        batched = self._front(mapper=True)
        self.assertEqual(len(serial.front_values), len(batched.front_values))
        for a, b in zip(serial.front_values, batched.front_values):
            for key in ("f1", "f2"):
                self.assertAlmostEqual(a[key], b[key], places=12)

    def test_the_evaluation_count_is_identical(self):
        self.assertEqual(self._front(mapper=False).n_evals,
                          self._front(mapper=True).n_evals)

    def test_a_mapper_that_returns_out_of_order_would_be_a_defect(self):
        """States the contract the pool code has to honour.

        `map_many` must return one row PER INPUT, in the input's order.
        A mapper that reverses its block produces a different front, and
        that is exactly the failure a completion-ordered pool would
        introduce silently.
        """
        def evaluate(x):
            return _zdt1(np.asarray(x, dtype=float))

        def reversed_map(xs):
            return [_zdt1(np.asarray(x, dtype=float)) for x in xs][::-1]

        evaluate.map_many = reversed_map
        scrambled = nsga2(evaluate, np.zeros(3), np.ones(3),
                          objective_keys=["f1", "f2"], population=12,
                          generations=5, seed=11)
        ordered = self._front(mapper=True, seed=11)
        differs = (len(scrambled.front_values) != len(ordered.front_values)
                   or any(abs(a["f1"] - b["f1"]) > 1e-12
                          for a, b in zip(scrambled.front_values,
                                           ordered.front_values)))
        self.assertTrue(differs,
                         "order does not matter here, so this test no longer "
                         "guards anything -- check why before deleting it")


class TestTheBatchScoresLikeTheSingleCall(unittest.TestCase):
    """`Evaluator.batch` and `Evaluator.__call__` must agree, because two
    definitions of "feasible" would mean only one of them is tested."""

    def _evaluator(self, log=None):
        return Evaluator(lambda x: _zdt1(np.asarray(x, dtype=float)),
                          np.zeros(2), np.ones(2),
                          np.array([False, False]), ["f1", "f2"], [], log)

    def test_same_F_and_violation(self):
        xs = np.array([[0.1, 0.2], [0.7, 0.9], [0.0, 1.0]])
        one = self._evaluator()
        singles = [one(x) for x in xs]
        many = self._evaluator()
        _rep, F, viol = many.batch(xs)
        for i, (_x, f_single, v_single) in enumerate(singles):
            np.testing.assert_allclose(F[i], f_single, rtol=0, atol=1e-12)
            self.assertAlmostEqual(float(viol[i]), float(v_single), places=12)

    def test_the_batch_records_one_ledger_row_per_design(self):
        log = []
        evaluator = self._evaluator(log=log)
        evaluator.batch(np.array([[0.1, 0.2], [0.7, 0.9]]))
        self.assertEqual(len(log), 2)

    def test_integer_variables_are_repaired_in_the_batch_too(self):
        mask = np.array([True, False])
        evaluator = Evaluator(lambda x: _zdt1(np.asarray(x, dtype=float)),
                               np.zeros(2), np.array([5.0, 1.0]), mask,
                               ["f1", "f2"], [], None)
        repaired, _F, _v = evaluator.batch(np.array([[2.4, 0.5],
                                                      [3.6, 0.5]]))
        self.assertEqual(list(repaired[:, 0]),
                          list(repair_integers(np.array([2.4, 3.6]),
                                                np.array([True, True]),
                                                np.zeros(2),
                                                np.array([5.0, 5.0]))))


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
