#!/usr/bin/env python3
"""Apply the inflow-global-models engine patch on the feature branch.

Temporary development helper. It edits ``zbemt/bemt.py`` by stable section
markers so the actual feature commit can be produced and tested in CI without
copying the whole large engine file through the GitHub contents API.
"""

from pathlib import Path

PATH = Path("zbemt/bemt.py")
text = PATH.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {n}")
    text = text.replace(old, new, 1)


# Public configuration documentation: add the new canonical global model.
replace_once(
    "    # Valid values: glauert_local | glauert_global | coleman_local |\n"
    "    # coleman_global | drees_local | drees_global | pitt_peters_steady |\n"
    "    # pitt_peters_unsteady (this last one is not solved by `solve_bemt` --\n",
    "    # Valid values: glauert_local | glauert_global | coleman_local |\n"
    "    # coleman_global | coleman_feingold_global | drees_local | drees_global |\n"
    "    # pitt_peters_steady | pitt_peters_unsteady (this last one is not solved\n",
    "BEMTConfig inflow options",
)

# Replace the harmonic-law function as one coherent unit.
start = text.index("def _inflow_harmonics(")
end = text.index("\n\n# =============================================================================\n# 3b.", start)
new_harmonics = r'''def _inflow_harmonics(model: str, mu_x: float, lambda_total: np.ndarray):
    """Linear inflow gradients for the empirical first-harmonic models.

    ``mu_x`` is scalar (one flight condition per call to ``solve_bemt``).
    ``lambda_total`` may be an array for the historical local coupling or a
    one-element array for the global coupling.

    The canonical laws implemented here are deliberately distinct:

    * ``coleman``: Coleman et al. skew-wake result, Kx=tan(chi/2), Ky=0.
      The signed lambda/mu form is retained for the existing local model so
      climb and descent are not collapsed into the same field.
    * ``coleman_feingold``: the Johnson/NDARC Coleman-and-Feingold gradient,
      Kx=(15*pi/32)*mu/(sqrt(mu^2+lambda^2)+|lambda|), Ky=-2*mu.  This
      model is exposed only with GLOBAL coupling because its derivation uses
      one mean wake skew angle for the disk.
    * ``drees``: Drees (1949), algebraically equivalent to
      (4/3)*(1-cos(chi)-1.8*mu^2)/sin(chi), with Ky=-2*mu.
    """
    model = model.lower()
    lam = np.asarray(lambda_total, dtype=float)
    if model == "glauert":
        return np.zeros_like(lam), np.zeros_like(lam)
    if abs(mu_x) < 1e-5:
        return np.zeros_like(lam), np.zeros_like(lam)

    if model == "coleman":
        # Preserve the SIGN of lambda_total/mu_x (legacy local behavior).
        ratio = lam / mu_x
        Kx = np.sqrt(1.0 + ratio ** 2) - ratio
        Ky = np.zeros_like(Kx)
        return Kx, Ky

    if model == "coleman_feingold":
        # Johnson/NDARC form. The absolute value is part of the published
        # mean-wake expression and makes this intentionally different from
        # the signed Coleman-local extension above.
        denominator = np.sqrt(mu_x ** 2 + lam ** 2) + np.abs(lam)
        denominator = np.maximum(denominator, 1e-12)
        Kx = (15.0 * np.pi / 32.0) * mu_x / denominator
        Ky = np.full_like(Kx, -2.0 * mu_x)
        return Kx, Ky

    if model == "drees":
        ratio = lam / mu_x
        Kx = (4.0 / 3.0) * ((1.0 - 1.8 * mu_x ** 2)
                            * np.sqrt(1.0 + ratio ** 2) - ratio)
        Ky = np.full_like(Kx, -2.0 * mu_x)
        return Kx, Ky

    raise ValueError(f"Unknown inflow_model: {model}")
'''
text = text[:start] + new_harmonics + text[end:]

# Add the new global-only field model to the resolution table.
replace_once(
    '    "coleman_global":       dict(harmonic="coleman", coupling="global",      unsteady=False),\n'
    '    "drees_local":          dict(harmonic="drees",   coupling="local",       unsteady=False),\n',
    '    "coleman_global":       dict(harmonic="coleman", coupling="global",      unsteady=False),\n'
    '    "coleman_feingold_global": dict(harmonic="coleman_feingold", coupling="global", unsteady=False),\n'
    '    "drees_local":          dict(harmonic="drees",   coupling="local",       unsteady=False),\n',
    "inflow resolution table",
)

# Insert the corrected empirical-global solver immediately before solve_bemt.
solve_marker = '\ndef solve_bemt(rotor: Rotor, airfoil, cfg: BEMTConfig, mu_x: float, Vz: float,\n'
if solve_marker not in text:
    raise RuntimeError("solve_bemt marker not found")

helper = r'''

def _solve_empirical_global_inflow(rotor: Rotor, airfoil, cfg: BEMTConfig,
                                   harmonic_family: str, mu_x: float,
                                   lambda_z: float, r_norm_nodes: np.ndarray,
                                   R_NORM: np.ndarray, PSI: np.ndarray,
                                   R_DIM: np.ndarray, CHORD: np.ndarray,
                                   THETA: np.ndarray, motion=None):
    """Solve a self-consistent axisymmetric mean plus one global harmonic.

    The previous ``global`` path solved the mean inflow on an artificial
    Npsi=1 strip at psi=0. That removed the azimuthal blade-speed term from
    the blade-element loading, so the mean inflow was not consistent with
    the 2-D forward-flight loads that were evaluated afterwards.

    Here the unknown mean is the radial axisymmetric field ``lambda0(r)``.
    At every outer iteration:

      1. its disk-area mean defines ONE wake angle for the whole rotor;
      2. the selected empirical law gives ONE pair (Kx, Ky);
      3. lambda_i(r,psi)=lambda0(r)*(1+Kx*r*cos(psi)+Ky*r*sin(psi));
      4. the complete 2-D blade-element state is evaluated on every azimuth;
      5. the no-harmonic annular momentum target is averaged over azimuth to
         update lambda0(r).

    This keeps the empirical harmonic genuinely global while retaining the
    annular BEMT radial resolution, Prandtl factors, compressibility and all
    other section physics in the mean-load closure.
    """
    cfg_mean = replace(cfg, inflow_field_model="glauert_local",
                       collect_history=False)
    lam0_r = _initial_guess(rotor, airfoil, r_norm_nodes, 1)[:, 0].copy()

    max_outer = max(10, min(int(cfg.max_iter), 120))
    tol_outer = max(10.0 * float(cfg.tol), 1e-6)
    relax_outer = float(np.clip(cfg.relax, 0.10, 0.60))
    history: list[float] = []
    converged = False

    def field_from_mean(mean_r):
        denom_area = _trapz(r_norm_nodes, r_norm_nodes)
        if abs(float(denom_area)) < 1e-12:
            lam_mean = float(np.mean(mean_r))
        else:
            lam_mean = float(_trapz(mean_r * r_norm_nodes, r_norm_nodes)
                             / denom_area)
        # Wake skew is defined by the TOTAL mean through-disk velocity:
        # freestream axial component plus induced component.
        lambda_total_mean = lambda_z + lam_mean
        Kx_a, Ky_a = _inflow_harmonics(
            harmonic_family, mu_x, np.array([lambda_total_mean], dtype=float))
        Kx = float(Kx_a[0])
        Ky = float(Ky_a[0])
        psi_w = np.deg2rad(float(getattr(cfg, "inflow_sideslip_deg", 0.0)))
        harmonic = (1.0 + Kx * R_NORM * np.cos(PSI - psi_w)
                    + Ky * R_NORM * np.sin(PSI - psi_w))
        lam_field = np.clip(mean_r[:, None] * harmonic, -0.5, 0.5)
        return lam_field, lam_mean, lambda_total_mean, Kx, Ky, harmonic

    last_residual = float("inf")
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

    # Rebuild from the accepted mean and evaluate one final full state. Also
    # measure the closure after that rebuild rather than reporting the previous
    # iterate's residual.
    lam, lam_mean, lambda_total_mean, Kx, Ky, _ = field_from_mean(lam0_r)
    state_closure = element_state(
        lam, R_NORM, PSI, R_DIM, CHORD, THETA, mu_x, lambda_z,
        rotor.Nb, rotor.Omega, rotor.OmegaR, airfoil, cfg_mean,
        rotor.r_root_norm_geom, rotor.r_tip_norm_geom, motion=motion)
    target_final = np.mean(np.asarray(state_closure["lambda_i_next"], dtype=float), axis=1)
    target_final = np.clip(target_final, -0.5, 0.5)
    last_residual = float(np.max(np.abs(target_final - lam0_r)))
    converged = bool(last_residual <= tol_outer)

    # Preserve the normal element-state contract for downstream aggregation.
    # Its lambda_i_next is not used to solve the global mode; the explicit
    # global closure residual below is the meaningful convergence diagnostic.
    state = element_state(
        lam, R_NORM, PSI, R_DIM, CHORD, THETA, mu_x, lambda_z,
        rotor.Nb, rotor.Omega, rotor.OmegaR, airfoil, cfg,
        rotor.r_root_norm_geom, rotor.r_tip_norm_geom, motion=motion)

    info = {
        "global_inflow_converged": converged,
        "global_inflow_iterations": int(len(history)),
        "global_inflow_residual": last_residual,
        "global_inflow_residual_history": history,
        "global_inflow_lambda_i_mean": lam_mean,
        "global_inflow_lambda_total_mean": lambda_total_mean,
        "global_inflow_Kx": Kx,
        "global_inflow_Ky": Ky,
        "global_inflow_harmonic_family": harmonic_family,
    }
    return lam, state, info
'''
text = text.replace(solve_marker, helper + solve_marker, 1)

# The high-level global branch now calls the self-consistent 2-D closure.
solve_start = text.index("def solve_bemt(")
global_start = text.index('    if coupling == "global":', solve_start)
global_end = text.index('    elif coupling == "pitt_peters":', global_start)
new_global_branch = r'''    if coupling == "global":
        # Empirical skew-wake model with ONE disk wake angle and a 2-D
        # azimuthally consistent mean-load closure.
        lam, state, global_info = _solve_empirical_global_inflow(
            rotor, airfoil, cfg, spec["harmonic"], mu_x, lambda_z,
            r_norm_nodes, R_NORM, PSI, R_DIM, CHORD, THETA, motion=motion)
        ok_global = bool(global_info["global_inflow_converged"])
        n_global = int(global_info["global_inflow_iterations"])
        converged = np.full_like(lam, ok_global, dtype=bool)
        n_iter = np.full_like(lam, n_global, dtype=int)
        total_it = n_global
        history = list(global_info["global_inflow_residual_history"])
        frac_hist = [1.0 if ok_global else 0.0 for _ in history]
        pp_nu = None
'''
text = text[:global_start] + new_global_branch + text[global_end:]

# Initialize and expose the global diagnostics without changing non-global maps.
replace_once(
    "    t0 = time.perf_counter()\n\n    if coupling == \"global\":\n",
    "    t0 = time.perf_counter()\n    global_info = None\n\n    if coupling == \"global\":\n",
    "global_info initialization",
)
replace_once(
    "    maps.update(state)\n\n    cfg_ds = _resolve_dynamic_stall_config(cfg, airfoil)\n",
    "    maps.update(state)\n    if global_info is not None:\n"
    "        maps.update(global_info)\n\n"
    "    cfg_ds = _resolve_dynamic_stall_config(cfg, airfoil)\n",
    "global diagnostics export",
)

PATH.write_text(text, encoding="utf-8")
print("patched", PATH)
