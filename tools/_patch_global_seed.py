#!/usr/bin/env python3
"""Development patch: seed empirical-global closure from a solved 2-D baseline.

The global outer closure can converge slowly close to hover when it starts from
the generic radial guess. A full azimuthal Glauert/local solve has the same
blade-element physics with no empirical skew harmonic, so its radial azimuth
mean is a physically consistent and much closer initial estimate of lambda0(r).
"""

from pathlib import Path

p = Path("zbemt/bemt.py")
text = p.read_text(encoding="utf-8")

old = '''    lam0_r = _initial_guess(rotor, airfoil, r_norm_nodes, 1)[:, 0].copy()

    max_outer = max(10, min(int(cfg.max_iter), 120))
'''

new = '''    # Seed from the COMPLETE 2-D no-harmonic BEMT solution, not from the
    # generic hover-like radial guess. This preserves the forward-flight
    # azimuthal blade-speed contribution in the mean from the first global
    # iteration and removes the very slow near-hover transient of the outer
    # fixed point.
    def residual_seed(lam):
        return element_state(
            lam, R_NORM, PSI, R_DIM, CHORD, THETA, mu_x, lambda_z,
            rotor.Nb, rotor.Omega, rotor.OmegaR, airfoil, cfg_mean,
            rotor.r_root_norm_geom, rotor.r_tip_norm_geom, motion=motion)

    solver_fn = _SOLVERS.get(cfg.solver)
    if solver_fn is None:
        raise ValueError(f"Unknown solver: {cfg.solver}. Options: {list(_SOLVERS)}")
    seed_guess = _initial_guess(rotor, airfoil, r_norm_nodes, cfg.Npsi)
    seed_lam, _seed_state, _seed_conv, _seed_n_iter, _seed_total_it, _, _ = solver_fn(
        residual_seed, seed_guess, cfg_mean, R_NORM=R_NORM, PSI=PSI,
        mu_x=mu_x)
    lam0_r = np.mean(np.asarray(seed_lam, dtype=float), axis=1)

    # The global closure is a separate nonlinear fixed point. Honor the
    # configured iteration budget instead of silently capping it at 120.
    max_outer = max(10, int(cfg.max_iter))
'''

count = text.count(old)
if count != 1:
    raise RuntimeError(f"global seed patch expected one marker, found {count}")
text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")
print("patched empirical-global initial seed")
