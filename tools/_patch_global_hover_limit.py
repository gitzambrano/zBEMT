#!/usr/bin/env python3
"""Development patch: use the ordinary local solver in the zero-skew limit.

For mu_x=0 every empirical global harmonic is exactly unity. The global and
local equations are then the same problem, so iterating an extra outer Picard
loop is unnecessary and less robust than solving that exact limit with the
normal configured BEMT solver.
"""

from pathlib import Path

p = Path("zbemt/bemt.py")
text = p.read_text(encoding="utf-8")

old = '''    cfg_mean = replace(cfg, inflow_field_model="glauert_local",
                       collect_history=False)
    lam0_r = _initial_guess(rotor, airfoil, r_norm_nodes, 1)[:, 0].copy()
'''

new = '''    cfg_mean = replace(cfg, inflow_field_model="glauert_local",
                       collect_history=False)

    # Exact zero-skew limit. With mu_x=0 all empirical gradients are zero,
    # hence the global field IS the ordinary axisymmetric/local BEMT field.
    # Solve that identical equation with the configured robust element solver
    # instead of wrapping it in an unnecessary outer Picard iteration.
    if abs(mu_x) < 1e-5:
        def residual_axis(lam):
            return element_state(
                lam, R_NORM, PSI, R_DIM, CHORD, THETA, mu_x, lambda_z,
                rotor.Nb, rotor.Omega, rotor.OmegaR, airfoil, cfg_mean,
                rotor.r_root_norm_geom, rotor.r_tip_norm_geom, motion=motion)

        lam_guess = _initial_guess(rotor, airfoil, r_norm_nodes, cfg.Npsi)
        solver_fn = _SOLVERS.get(cfg.solver)
        if solver_fn is None:
            raise ValueError(f"Unknown solver: {cfg.solver}. Options: {list(_SOLVERS)}")
        lam, state, _conv, _n_iter, total_it, history, _frac = solver_fn(
            residual_axis, lam_guess, cfg_mean, R_NORM=R_NORM, PSI=PSI,
            mu_x=mu_x)
        closure_residual = float(np.max(np.abs(state["lambda_i_next"] - lam)))
        mean_r = np.mean(np.asarray(lam, dtype=float), axis=1)
        denom_area = _trapz(r_norm_nodes, r_norm_nodes)
        lam_mean = (float(np.mean(mean_r)) if abs(float(denom_area)) < 1e-12
                    else float(_trapz(mean_r * r_norm_nodes, r_norm_nodes)
                               / denom_area))
        tol_outer = max(10.0 * float(cfg.tol), 1e-6)
        info = {
            "global_inflow_converged": bool(closure_residual <= tol_outer),
            "global_inflow_iterations": int(total_it),
            "global_inflow_residual": closure_residual,
            "global_inflow_residual_history": list(history),
            "global_inflow_lambda_i_mean": lam_mean,
            "global_inflow_lambda_total_mean": lambda_z + lam_mean,
            "global_inflow_Kx": 0.0,
            "global_inflow_Ky": 0.0,
            "global_inflow_harmonic_family": harmonic_family,
        }
        return lam, state, info

    lam0_r = _initial_guess(rotor, airfoil, r_norm_nodes, 1)[:, 0].copy()
'''

if text.count(old) != 1:
    raise RuntimeError(f"hover-limit patch expected one marker, found {text.count(old)}")
text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")
print("patched zero-skew global limit")
