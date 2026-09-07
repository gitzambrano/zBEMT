#!/usr/bin/env python3
"""Development patch: robust empirical-global closure.

Two changes are applied to the already-corrected global-inflow engine:
1. seed lambda0(r) from a solved full-azimuth no-harmonic BEMT field;
2. solve the coupled radial fixed point with SciPy Anderson mixing instead of
   plain under-relaxed Picard iteration.

The physical closure is unchanged. This patch only improves nonlinear
convergence, particularly near hover where the Picard residual stagnates just
above 1e-6 despite already-small load changes.
"""

from pathlib import Path

p = Path("zbemt/bemt.py")
text = p.read_text(encoding="utf-8")

# Anderson solver import.
old_import = "from scipy.linalg import expm\n"
new_import = "from scipy.linalg import expm\nfrom scipy.optimize import root as scipy_root\n"
if "from scipy.optimize import root as scipy_root" not in text:
    if text.count(old_import) != 1:
        raise RuntimeError("scipy.linalg import marker not found exactly once")
    text = text.replace(old_import, new_import, 1)

# Better initial estimate and honor the configured outer-iteration budget.
old_seed = '''    lam0_r = _initial_guess(rotor, airfoil, r_norm_nodes, 1)[:, 0].copy()

    max_outer = max(10, min(int(cfg.max_iter), 120))
'''
new_seed = '''    # Seed from the COMPLETE 2-D no-harmonic BEMT solution, not from the
    # generic hover-like radial guess. This preserves the forward-flight
    # azimuthal blade-speed contribution in the mean from the first global
    # iteration.
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
if text.count(old_seed) != 1:
    raise RuntimeError(f"global seed patch expected one marker, found {text.count(old_seed)}")
text = text.replace(old_seed, new_seed, 1)

# Replace the plain Picard loop by Anderson mixing. Keep `history` as actual
# max-norm closure residuals so downstream reporting remains meaningful.
old_loop = '''    last_residual = float("inf")
    for outer_it in range(1, max_outer + 1):
        lam_field, _, _, _, _, _ = field_from_mean(lam0_r)

        # Use the same 2-D aerodynamics but suppress the empirical harmonic
        # INSIDE the momentum map. lambda_i_next is then the annular baseline
        # target. Its periodic azimuth mean is the new lambda0(r).
        state_mean = element_state(
            lam_field, R_NORM, PSI, R_DIM, CHORD, THETA, mu_x, lambda_z,
            rotor.Nb, rotor.Omega, rotor.OmegaR, airfoil, cfg_mean,
            rotor.r_root_norm_geom, rotor.r_tip_norm_geom, motion=motion)
        target_r = np.mean(np.asarray(state_mean["lambda_i_next"], dtype=float), axis=1)
        target_r = np.clip(target_r, -0.5, 0.5)
        residual = float(np.max(np.abs(target_r - lam0_r)))
        history.append(residual)
        last_residual = residual

        if residual <= tol_outer:
            lam0_r = target_r
            converged = True
            break

        # Back off automatically if the nonlinear outer fixed point worsens.
        if len(history) >= 2 and history[-1] > 1.20 * history[-2]:
            relax_outer = max(0.10, 0.5 * relax_outer)
        lam0_r = (1.0 - relax_outer) * lam0_r + relax_outer * target_r
'''
new_loop = '''    last_residual = float("inf")

    def closure_residual(mean_r):
        # Anderson may probe beyond the physical trust region while building
        # its multisecant approximation. The returned residual still points
        # back toward the allowed interval, while all aerodynamic evaluations
        # stay bounded.
        mean_eval = np.clip(np.asarray(mean_r, dtype=float), -0.5, 0.5)
        lam_field, _, _, _, _, _ = field_from_mean(mean_eval)

        # Use the same 2-D aerodynamics but suppress the empirical harmonic
        # INSIDE the momentum map. lambda_i_next is then the annular baseline
        # target. Its periodic azimuth mean is the new lambda0(r).
        state_mean = element_state(
            lam_field, R_NORM, PSI, R_DIM, CHORD, THETA, mu_x, lambda_z,
            rotor.Nb, rotor.Omega, rotor.OmegaR, airfoil, cfg_mean,
            rotor.r_root_norm_geom, rotor.r_tip_norm_geom, motion=motion)
        target_r = np.mean(np.asarray(state_mean["lambda_i_next"], dtype=float), axis=1)
        target_r = np.clip(target_r, -0.5, 0.5)
        residual_vec = target_r - np.asarray(mean_r, dtype=float)
        history.append(float(np.max(np.abs(residual_vec))))
        return residual_vec

    # The global wake angle couples every radial station weakly through one
    # disk-mean lambda. Anderson mixing is designed for this kind of vector
    # fixed point: it builds a small multisecant model from recent residuals
    # without an Ne-by-Ne finite-difference Jacobian.
    try:
        opt = scipy_root(
            closure_residual,
            lam0_r,
            method="anderson",
            options={
                "maxiter": max_outer,
                "fatol": tol_outer,
                "line_search": "armijo",
                "jac_options": {"M": 6, "w0": 0.01},
            },
        )
        lam0_r = np.clip(np.asarray(opt.x, dtype=float), -0.5, 0.5)
    except Exception:
        # Conservative fallback: retain the old under-relaxed fixed point if
        # SciPy rejects a pathological iterate. This path is not expected in
        # the validated operating envelope but keeps the engine fail-soft.
        for _outer_it in range(1, max_outer + 1):
            rvec = closure_residual(lam0_r)
            if float(np.max(np.abs(rvec))) <= tol_outer:
                break
            lam0_r = np.clip(lam0_r + relax_outer * rvec, -0.5, 0.5)
'''
if text.count(old_loop) != 1:
    raise RuntimeError(f"global Picard loop expected one marker, found {text.count(old_loop)}")
text = text.replace(old_loop, new_loop, 1)

p.write_text(text, encoding="utf-8")
print("patched empirical-global seed + Anderson closure")
