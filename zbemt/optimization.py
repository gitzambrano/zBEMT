"""Multi-objective search algorithms for the design optimizer (SC-13).

This module holds SEARCH ALGORITHMS and nothing else: it receives an
evaluation callable and bounds, and returns a result object. It does not
import studies, api or Qt -- that separation is what keeps it testable
against analytic functions with no solver in sight.

Every objective is MINIMIZED here. A maximize objective reaches this
module already negated by the orchestrator, which owns the user's
maximize/minimize vocabulary.

No dependency beyond numpy: scipy has no multi-objective optimizer, and
PR-7 asks that optional dependencies degrade rather than become
required; NSGA-II below is about one hundred fifty lines of numpy.

Determinism contract: the same seed, bounds and evaluation function
produce byte-for-byte the same front, because ONE
``numpy.random.default_rng(seed)`` drives every random draw in a fixed
order.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .bemt import SolveCancelled


@dataclass
class ParetoOutcome:
    """Result of one multi-objective run (in memory only)."""
    front_params: list[dict] = field(default_factory=list)
    front_values: list[dict] = field(default_factory=list)
    #: Which of the keys inside ``front_values`` are the OBJECTIVES (any
    #: further keys ride along as recorded constraint values).
    objective_keys: list[str] = field(default_factory=list)
    all_evaluations: list[dict] = field(default_factory=list)
    param_names: list[str] = field(default_factory=list)
    generations_run: int = 0
    n_evals: int = 0
    seed: int = 0
    message: str = ""
    hypervolume_history: list[float] = field(default_factory=list)
    best_history: list[float] = field(default_factory=list)


class SearchCancelled(SolveCancelled):
    """A search whose ``should_cancel`` fired mid-run (SC-13). It IS a
    ``SolveCancelled``, so every caller that treats cancellation as
    "stop here" keeps working; ``evaluations`` carries every record
    gathered up to the stop, so the caller can rebuild a partial front
    instead of throwing the whole run away."""

    def __init__(self, evaluations=None):
        super().__init__()
        self.evaluations = evaluations if evaluations is not None else []


def front_from_ledger(evaluations: list[dict],
                      objective_keys: list[str],
                      signs: np.ndarray | None = None) -> ParetoOutcome:
    """Rebuilds the first constraint-dominated front from a raw
    evaluation ledger (the records ``Evaluator`` logs). Used when a
    search stops early: the population may be gone, but what was already
    evaluated still holds a front worth reporting. ``signs`` is the same
    per-objective direction vector the search used (+1 minimize, -1
    maximize); the emitted values stay RAW."""
    sign_arr = (np.ones(len(objective_keys))
                 if signs is None else np.asarray(signs, dtype=float))
    finite_x, finite_F, finite_viol = [], [], []
    for rec in evaluations:
        values = rec.get("values") or {}
        try:
            F_row = [float(values.get(k, math.nan)) * s for k, s
                     in zip(objective_keys, sign_arr)]
            x_row = [float(v) for v in rec.get("x") or []]
            viol = float(rec.get("violation", math.inf))
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in F_row) \
                or not all(math.isfinite(v) for v in x_row):
            continue
        finite_x.append(x_row)
        finite_F.append(F_row)
        finite_viol.append(viol)
    outcome = ParetoOutcome()
    objective_keys = list(objective_keys)
    outcome.objective_keys = objective_keys
    if not finite_F:
        return outcome
    F_signed = np.asarray(finite_F, dtype=float)
    ranks, _crowd = _rank_population(F_signed, np.asarray(finite_viol))
    members = np.where(ranks == ranks.min())[0]
    n_var = len(finite_x[0])
    names = [f"v{j}" for j in range(n_var)]
    for i in members:
        outcome.front_params.append(dict(zip(names, finite_x[i])))
        outcome.front_values.append(dict(zip(objective_keys,
                                              (F_signed[i] / sign_arr).tolist())))
    return outcome


def _fast_non_dominated_sort(F: np.ndarray) -> np.ndarray:
    """Returns the FRONT INDEX of every individual (0 = first front).

    Standard Deb dominance sorting over M objectives; O(M*N^2), which is
    fine at optimizer population sizes."""
    n = F.shape[0]
    ranks = np.zeros(n, dtype=int)
    domination_count = np.zeros(n, dtype=int)
    dominated_sets: list[list[int]] = [[] for _ in range(n)]

    def dominates(a: int, b: int) -> bool:
        return bool(np.all(F[a] <= F[b]) and np.any(F[a] < F[b]))

    for a in range(n):
        for b in range(a + 1, n):
            if dominates(a, b):
                dominated_sets[a].append(b)
                domination_count[b] += 1
            elif dominates(b, a):
                dominated_sets[b].append(a)
                domination_count[a] += 1
    current = [i for i in range(n) if domination_count[i] == 0]
    rank = 0
    assigned = 0
    while current:
        nxt: list[int] = []
        for i in current:
            ranks[i] = rank
            assigned += 1
            for j in dominated_sets[i]:
                domination_count[j] -= 1
                if domination_count[j] == 0:
                    nxt.append(j)
        current = [j for j in dict.fromkeys(nxt)]
        rank += 1
    if assigned < n:                      # defensive; cannot happen
        ranks[ranks > rank] = rank - 1
    return ranks


def crowding_distance(F: np.ndarray, members: np.ndarray) -> np.ndarray:
    """Crowding distance INSIDE one front; boundary points at infinity."""
    distances = np.zeros(len(members), dtype=float)
    if len(members) <= 2:
        distances[:] = np.inf
        return distances
    block = F[members]
    for m in range(F.shape[1]):
        order = np.argsort(block[:, m])
        values = block[order, m]
        span = values[-1] - values[0]
        distances[order[0]] = math.inf
        distances[order[-1]] = math.inf
        if span > 0.0:
            distances[order[1:-1]] += (values[2:] - values[:-2]) / span
    return distances


def constrained_dominates(fi: float, fj: float, Fi: np.ndarray,
                           Fj: np.ndarray) -> bool:
    """Constraint-domination rule (Deb): a FEASIBLE individual always
    beats an infeasible one; two infeasible ones compare by total
    violation; two feasible ones compare by objective domination."""
    if fi <= 0.0 and fj <= 0.0:
        return bool(np.all(Fi <= Fj) and np.any(Fi < Fj))
    if fi <= 0.0:
        return True
    if fj <= 0.0:
        return False
    return fi < fj


def sbx_crossover(rng: np.random.Generator, p1: np.ndarray,
                   p2: np.ndarray, lower: np.ndarray, upper: np.ndarray,
                   eta: float) -> tuple[np.ndarray, np.ndarray]:
    """Simulated binary crossover with distribution index eta."""
    u = rng.random(p1.size)
    beta = np.where(u <= 0.5,
                     (2.0 * u) ** (1.0 / (eta + 1.0)),
                     (1.0 / (2.0 * (1.0 - u))) ** (1.0 / (eta + 1.0)))
    c1 = 0.5 * ((1.0 + beta) * p1 + (1.0 - beta) * p2)
    c2 = 0.5 * ((1.0 - beta) * p1 + (1.0 + beta) * p2)
    return np.clip(c1, lower, upper), np.clip(c2, lower, upper)


def polynomial_mutation(rng: np.random.Generator, x: np.ndarray,
                         lower: np.ndarray, upper: np.ndarray,
                         eta: float, rate: float) -> np.ndarray:
    """Deb's BOUNDED polynomial mutation, at the given per-gene rate.

    The step is scaled by how far the gene sits from the NEARER bound:

        d1 = (x - lower)/(upper - lower),   d2 = (upper - x)/(upper - lower)

        u < 0.5 :  delta = [2u + (1-2u)(1-d1)^(eta+1)]^(1/(eta+1)) - 1
        u >= 0.5:  delta = 1 - [2(1-u) + 2(u-0.5)(1-d2)^(eta+1)]^(1/(eta+1))

    so a gene ON a bound cannot be pushed across it and the distribution
    is already inside the box before any clipping.

    The simplified form -- delta from u alone, then clip -- was used
    here. It is the same operator in the middle of the range and a
    different one near an edge: every step that would have left the box
    landed exactly ON the bound, so the bounds collected probability
    mass that the operator was never meant to give them, and a search
    whose optimum sits at a bound looked more converged than it was.
    """
    mask = rng.random(x.size) < rate
    if not np.any(mask):
        return x
    span = np.asarray(upper, dtype=float) - np.asarray(lower, dtype=float)
    # A variable with no range left has nothing to mutate.
    safe_span = np.where(np.abs(span) < 1e-15, 1.0, span)
    d1 = np.clip((x - lower) / safe_span, 0.0, 1.0)
    d2 = np.clip((upper - x) / safe_span, 0.0, 1.0)
    u = rng.random(x.size)
    power = 1.0 / (eta + 1.0)
    delta = np.where(
        u < 0.5,
        (2.0 * u + (1.0 - 2.0 * u) * (1.0 - d1) ** (eta + 1.0)) ** power - 1.0,
        1.0 - (2.0 * (1.0 - u)
               + 2.0 * (u - 0.5) * (1.0 - d2) ** (eta + 1.0)) ** power)
    mutated = x + delta * span
    x = np.where(mask & (np.abs(span) >= 1e-15), mutated, x)
    return np.clip(x, lower, upper)


def repair_integers(x: np.ndarray, integer_mask: np.ndarray,
                     lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Rounds and clips INTEGER variables so, e.g., n_blades stays whole
    inside its bounds."""
    if not np.any(integer_mask):
        return np.asarray(x, dtype=float)
    x = np.where(integer_mask, np.round(np.asarray(x, dtype=float)), x)
    return np.clip(x, lower, upper)


def hypervolume_2d(points: np.ndarray, reference: np.ndarray) -> float:
    """Exact hypervolume of a 2-D minimization front against a reference
    point; points outside contribute nothing."""
    pts = points[(points[:, 0] < reference[0])
                  & (points[:, 1] < reference[1])]
    if len(pts) == 0:
        return 0.0
    pts = pts[np.argsort(pts[:, 0])]
    volume = 0.0
    prev_y = reference[1]
    for x, y in pts:
        volume += (reference[0] - x) * (prev_y - y)
        prev_y = min(prev_y, y)
    return float(volume)


class Evaluator:
    """Wraps the caller's callable into the normalized form the search
    consumes: repair, evaluate, split objectives/constraints, count.

    ``evaluate_raw`` returns RAW summary values -- the user's own
    direction, not the search's. ``signs`` carries the per-objective
    direction (+1 minimize, -1 maximize) and is applied ONLY when the F
    matrix is built, so constraints and every record kept for reporting
    always see raw values."""

    def __init__(self, evaluate, lower: np.ndarray, upper: np.ndarray,
                  integer_mask: np.ndarray, objective_keys: list[str],
                  constraints: list | None = None, log=None,
                  signs: np.ndarray | None = None):
        self.evaluate_raw = evaluate
        self.lower = lower
        self.upper = upper
        self.integer_mask = integer_mask
        self.objective_keys = objective_keys
        self.constraints = constraints or []
        self.log = log
        self.signs = (np.ones(len(objective_keys))
                       if signs is None else np.asarray(signs, dtype=float))

    def _score(self, x: np.ndarray, values: dict):
        """Turns one design's RAW summary values into (F, violation).

        Split out of `__call__` so the batch path scores exactly the same
        way. Two copies of this arithmetic would be two definitions of
        what "feasible" means, and only one of them would be tested.
        """
        F = np.array([float(values.get(k, math.nan)) * s
                       for k, s in zip(self.objective_keys, self.signs)],
                      dtype=float)
        violation = 0.0
        for constraint in self.constraints:
            actual = values.get(constraint.key)
            if actual is None or not math.isfinite(actual):
                violation = math.inf
                break
            op = constraint.operator
            if op == ">=":
                violation += max(0.0, constraint.value - actual)
            elif op == "<=":
                violation += max(0.0, actual - constraint.value)
            elif op == "==":
                violation += max(0.0, abs(actual - constraint.value)
                                  - constraint.tolerance)
        if not np.all(np.isfinite(F)):
            # A failed evaluation is MAXIMALLY infeasible -- never a
            # magic penalty number pretending to be a fitness.
            violation = math.inf
        record = {"x": np.asarray(x, dtype=float).tolist(), "values": {
            k: (float(v) if math.isfinite(v) else None)
            for k, v in values.items()}, "violation": violation}
        if self.log is not None:
            self.log.append(record)
        return F, np.float64(violation)

    def batch(self, xs: np.ndarray, should_cancel=None):
        """Evaluates a whole block of designs, in parallel when it can.

        Returns ``(repaired_xs, F, violation)`` for the block. The order
        of the returned rows is the order of `xs`, whatever order the
        designs actually finished in: the search's arithmetic and the
        evaluation log both depend on it, and a search whose answer
        depended on which worker won a race would not be reproducible
        from its seed.

        The parallel path is used only when `evaluate_raw` carries a
        `map_many`. Without one this is exactly the serial loop it
        replaces, which is what keeps the single-worker answer identical
        to the answer before this existed.
        """
        xs = np.asarray(xs, dtype=float)
        repaired = np.array([repair_integers(x, self.integer_mask,
                                              self.lower, self.upper)
                             for x in xs])
        mapper = getattr(self.evaluate_raw, "map_many", None)
        if mapper is None:
            F = np.zeros((len(repaired), len(self.objective_keys)))
            violation = np.zeros(len(repaired))
            for i, x in enumerate(repaired):
                if should_cancel is not None and should_cancel():
                    raise SearchCancelled(self.log if self.log is not None
                                           else [])
                repaired[i], F[i], violation[i] = self(x)
            return repaired, F, violation

        if should_cancel is not None and should_cancel():
            raise SearchCancelled(self.log if self.log is not None else [])
        results = mapper([x.copy() for x in repaired])
        F = np.zeros((len(repaired), len(self.objective_keys)))
        violation = np.zeros(len(repaired))
        for i, values in enumerate(results):
            F[i], violation[i] = self._score(repaired[i], values)
        return repaired, F, violation

    def __call__(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
        x = repair_integers(x, self.integer_mask, self.lower, self.upper)
        result = self.evaluate_raw(x)
        values = result[0] if isinstance(result, tuple) else result
        F, violation = self._score(x, values)
        return x, F, violation


def _rank_population(F: np.ndarray, violations: np.ndarray):
    """Ranks the WHOLE population under constraint-domination, plus a
    tiebreak value: crowding distance for the feasible, minus total
    violation for the infeasible."""
    n = len(F)
    finite = np.isfinite(violations) & (violations <= 0.0)
    ranks = np.full(n, 10 ** 9, dtype=int)
    crowd = np.full(n, -np.inf)
    if np.any(finite):
        idx = np.where(finite)[0]
        ranks[idx] = _fast_non_dominated_sort(F[idx])
        for r in np.unique(ranks[idx]):
            members = idx[ranks[idx] == r]
            crowd[members] = crowding_distance(F, members)
    infeasible = ~finite
    if np.any(infeasible):
        idx = np.where(infeasible)[0]
        order = np.argsort(violations[idx])
        for position, member in enumerate(idx[order]):
            ranks[member] = 10 ** 9 + position
            crowd[member] = -float(violations[member])
    return ranks, crowd


def nsga2(evaluate, lower, upper, *, objective_keys: list[str],
          constraints: list | None = None, integer_mask=None,
          population: int = 40, generations: int = 25, seed: int = 0,
          crossover_eta: float = 15.0, mutation_eta: float = 20.0,
          mutation_rate: float = 0.0, on_generation=None,
          should_cancel=None, signs: np.ndarray | None = None) -> ParetoOutcome:
    """NSGA-II over bounded variables.

    ``evaluate(x)`` returns the RAW summary-values dict of ONE design;
    the ordered ``objective_keys`` pick what the search sees and
    ``signs`` (+1 minimize, -1 maximize) turns each into a quantity the
    pure-minimization core handles. Deterministic for a fixed seed."""
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    integer_mask = np.zeros(lower.size, dtype=bool) \
        if integer_mask is None else np.asarray(integer_mask, dtype=bool)
    # Contract of OptimizationDefinition.mutation_rate: 0 means ONE OVER
    # THE VARIABLE COUNT (the NSGA-II default); without it SBX alone
    # contracts the population into a corner and kills the front.
    rate = mutation_rate if mutation_rate > 0 else 1.0 / max(lower.size, 1)
    rng = np.random.default_rng(seed)
    evaluations: list[dict] = []
    evaluator = Evaluator(evaluate, lower, upper, integer_mask,
                           list(objective_keys), constraints, evaluations,
                           signs=signs)

    # --- initial population: deterministic stratified spread ------------
    xs = np.empty((population, lower.size))
    for j in range(lower.size):
        xs[:, j] = lower[j] + (upper[j] - lower[j]) * (
            (np.arange(population) + 0.5) / population)
    xs += (upper - lower) * 0.05 * (rng.random((population, lower.size))
                                     - 0.5)
    xs = np.clip(xs, lower, upper)

    # The population IS the batch: with a `map_many` on the evaluator this
    # is where the process pool earns its keep, and without one it is the
    # same serial loop it replaces.
    #
    # NO cancel check here, deliberately, and that is the behaviour this
    # replaced: the initial stratified sweep runs to completion so that
    # even an immediate stop reports its designs instead of an empty
    # front (`tests/test_optimization.py::TestCancellation`). The
    # offspring loop below checks per design, where a cancel can save
    # real time.
    xs, F, viol = evaluator.batch(xs)
    n_evals = population

    hypervolume_history: list[float] = []
    best_history: list[float] = []
    generations_run = 0

    for generation in range(max(int(generations), 1)):
        if should_cancel is not None and should_cancel():
            raise SearchCancelled(evaluations)
        ranks, crowd = _rank_population(F, viol)

        feasible = viol <= 0.0
        if np.any(feasible):
            ref = np.nanmax(F[feasible], axis=0) * 1.1
            if len(objective_keys) == 2:
                # Hypervolume needs an actual FRONT: feeding the whole
                # (dominated-including) population would sum negative
                # slabs and produce nonsense.
                feas_idx = np.where(feasible)[0]
                fr = _fast_non_dominated_sort(F[feasible])
                front_F = F[feas_idx][fr == 0]
                hypervolume_history.append(
                    hypervolume_2d(front_F, ref))
            col = F[feasible][:, 0]
            best_history.append(float(np.nanmin(col)))
        else:
            hypervolume_history.append(0.0)
            best_history.append(float("nan"))
        if on_generation is not None:
            on_generation(generation + 1, n_evals)

        # --- offspring through tournament + SBX + mutation -------------
        def _better(a: int, b: int) -> int:
            """Binary tournament: LOWER constraint-rank wins; on a tie,
            LARGER crowding distance wins."""
            if ranks[a] != ranks[b]:
                return a if ranks[a] < ranks[b] else b
            return a if crowd[a] >= crowd[b] else b

        children = np.empty((population, lower.size))
        for i in range(population):
            p1 = _better(*rng.choice(population, size=2, replace=False))
            p2 = _better(*rng.choice(population, size=2, replace=False))
            c1, _c2 = sbx_crossover(rng, xs[p1], xs[p2], lower, upper,
                                     crossover_eta)
            children[i] = polynomial_mutation(
                rng, c1, lower, upper, mutation_eta, rate)

        children, child_F, child_viol = evaluator.batch(
            children, should_cancel=should_cancel)
        n_evals += population

        # --- environmental selection over the union --------------------
        union_x = np.vstack([xs, children])
        union_F = np.vstack([F, child_F])
        union_viol = np.concatenate([viol, child_viol])
        u_ranks, u_crowd = _rank_population(union_F, union_viol)

        chosen: list[int] = []
        for r in sorted(set(u_ranks.tolist())):
            members = np.where(u_ranks == r)[0]
            if len(chosen) + len(members) <= population:
                chosen.extend(members.tolist())
                continue
            crowd_m = crowding_distance(union_F, members)
            order = members[np.argsort(-_finite_first(crowd_m))]
            chosen.extend(order[:population - len(chosen)].tolist())
            break
        chosen = chosen[:population]
        xs, F, viol = union_x[chosen], union_F[chosen], union_viol[chosen]
        generations_run += 1

    # --- extract the first front of the FINAL population ----------------
    ranks, _crowd = _rank_population(F, viol)
    first_rank = min(ranks)
    members = np.where(ranks == first_rank)[0]

    outcome = ParetoOutcome()
    outcome.generations_run = generations_run
    outcome.n_evals = n_evals
    outcome.seed = seed
    outcome.objective_keys = list(objective_keys)
    outcome.hypervolume_history = hypervolume_history
    outcome.best_history = best_history
    names = [f"v{j}" for j in range(lower.size)]
    sign_arr = evaluator.signs
    for i in members:
        outcome.front_params.append(dict(zip(names, xs[i].tolist())))
        # F is the search's signed view; report RAW user-direction values.
        outcome.front_values.append(
            {k: v / s for k, v, s in zip(objective_keys, F[i].tolist(),
                                          sign_arr)})
    outcome.all_evaluations = evaluations
    outcome.message = f"{generations_run} generations, {n_evals} evaluations"
    return outcome


def _finite_first(values: np.ndarray) -> np.ndarray:
    """Sort key that pushes NaN/inf crowding to the END (they mean
    'boundary' only when positive infinity)."""
    out = np.where(np.isnan(values), -np.inf, values)
    return out


def differential_evolution(evaluate, lower, upper, *,
                            objective_keys: list[str],
                            minimize: bool = False,
                            constraints: list | None = None,
                            integer_mask=None, population: int = 40,
                            generations: int = 25, seed: int = 0,
                            should_cancel=None,
                            signs: np.ndarray | None = None) -> ParetoOutcome:
    """Single-objective GLOBAL search backed by scipy's differential
    evolution, exposed through this same interface. The objective is the
    FIRST key's value; ``signs`` (+1 minimize, -1 maximize) selects the
    direction, with ``minimize`` as the scalar fallback."""
    from scipy.optimize import differential_evolution as scipy_de

    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    integer_mask = (np.zeros(lower.size, dtype=bool)
                     if integer_mask is None
                     else np.asarray(integer_mask, dtype=bool))
    evaluations: list[dict] = []
    effective_signs = (np.asarray(signs, dtype=float) if signs is not None
                        else np.full(len(objective_keys),
                                     1.0 if minimize else -1.0))
    evaluator = Evaluator(evaluate, lower, upper, integer_mask,
                           list(objective_keys), constraints, evaluations,
                           signs=effective_signs)

    def cost(x: np.ndarray) -> float:
        if should_cancel is not None and should_cancel():
            raise SearchCancelled(evaluations)
        _x, F, violation = evaluator(x)
        # F[0] is ALREADY the search's signed view (Evaluator applied
        # ``signs``); scipy minimizes it as-is.
        value = float(F[0])
        if not math.isfinite(value):
            return math.inf
        return value + min(float(violation), 1e12)

    result = scipy_de(cost, list(zip(lower, upper)), seed=seed,
                       maxiter=max(int(generations), 1),
                       popsize=max(int(population), 8) // 2, polish=False)

    outcome = ParetoOutcome()
    outcome.seed = seed
    outcome.objective_keys = list(objective_keys)
    outcome.n_evals = len(evaluations)
    outcome.generations_run = int(result.nit)
    best_x = repair_integers(np.asarray(result.x, dtype=float),
                              integer_mask, lower, upper)
    outcome.front_params.append(dict(zip(
        [f"v{i}" for i in range(lower.size)], best_x.tolist())))
    _x, F_best, _v = evaluator(best_x)
    # F is the search's signed view; report RAW user-direction values.
    outcome.front_values.append(
        {k: v / s for k, v, s in zip(objective_keys, F_best.tolist(),
                                      evaluator.signs)})
    outcome.best_history = ([float(b) for b in result.population_energies]
                             if hasattr(result, "population_energies") else [])
    outcome.message = str(result.message)
    return outcome