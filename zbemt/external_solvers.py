"""Integrate optional external airfoil-polar generation engines.

The module accepts profile geometry, Reynolds and Mach lists, angle limits, and
engine options. It detects supported engines, validates requests, and returns
polar slices or structured errors; it does not run BEMT or persist projects.
``airfoils.py`` consumes successful tables, ``api.py`` exposes the operation, and the
Airfoil GUI supplies requests. NeuralFoil is the supported engine; unsupported
engines are rejected explicitly. Returned data inherit the external engine's
operating envelope and confidence limitations.
"""

from __future__ import annotations

import importlib.util
import warnings

import numpy as np

from .models import ProfileGeometry, PolarSlice

SUPPORTED_ENGINES = ("neuralfoil",)


def is_available(engine: str) -> bool:
    """Used by the GUI ('f) External engine' block) and by the CLI
    (``--gen-neuralfoil``) to decide whether the corresponding
    button or flag is enabled. Only ``True`` when ``engine == 'neuralfoil'``
    **and** the ``neuralfoil`` package is installed in the current
    environment (real check via ``importlib.util.find_spec``, with nothing
    hardcoded)."""
    if engine not in SUPPORTED_ENGINES:
        return False
    return importlib.util.find_spec("neuralfoil") is not None


def _coordinates_from_geometry(geometry: ProfileGeometry) -> np.ndarray:
    """NeuralFoil expects an Nx2 (x,y) mesh in Selig format: upper
    trailing edge -> leading edge -> lower trailing edge. That is
    exactly the convention already used by
    ``airfoils.generate_naca4/generate_naca5/generate_cst/generate_bezier/
    load_profile_dat`` (``ProfileGeometry.x``/``.y``)."""
    if not geometry.x or not geometry.y:
        raise ValueError(
            f"ProfileGeometry (source={geometry.source!r}) has no generated coordinates "
            f"(.x/.y empty). Generate the geometry first, for example: "
            f"airfoils.generate_naca4('2412') or airfoils.resolve_geometry_spec('naca2412')."
        )
    return np.column_stack([
        np.asarray(geometry.x, dtype=float),
        np.asarray(geometry.y, dtype=float),
    ])


def run_polar(engine: str, geometry: ProfileGeometry,
              reynolds_list: list[float], mach_list: list[float],
              alpha_min_deg: float, alpha_max_deg: float,
              alpha_step_deg: float) -> list[PolarSlice]:
    """Run NeuralFoil over ``geometry`` for each (Reynolds, Mach)
    combination in ``reynolds_list`` x ``mach_list``, over the requested
    alpha range, and return a list of ``PolarSlice`` ready to be
    appended to ``AirfoilDef.table_slices`` (same structure used by
    tables imported from CSV/experimental data, because the import pipeline
    does not distinguish the origin once generated).

    Robustness (same pattern as ``bemt.py`` for points that do not
    converge in the inflow solver): a specific alpha point that
    NeuralFoil cannot resolve with confidence (low ``analysis_confidence``
    or NaN in Cl/Cd) is silently dropped from that slice. An aggregate
    warning is emitted at the end, but the whole sweep is not brought down
    because of a few outlier points.
    """
    if engine not in SUPPORTED_ENGINES:
        raise ValueError(
            f"Unknown external engine: {engine!r} (expected one of {SUPPORTED_ENGINES}). "
            f"XFOIL is not supported in this version. Only NeuralFoil is supported."
        )
    if not reynolds_list or not mach_list:
        raise ValueError(
            "run_polar('neuralfoil', ...) needs at least one value in reynolds_list "
            "and in mach_list to define the sweep."
        )
    if alpha_step_deg <= 0:
        raise ValueError(f"alpha_step_deg must be positive (got {alpha_step_deg}).")
    if not is_available(engine):
        raise RuntimeError(
            "The 'neuralfoil' package is not installed in this environment. "
            "Install with `pip install neuralfoil` to generate polars via NeuralFoil "
            "(alternatively: import a CSV/experimental table instead of using external engine)."
        )

    import neuralfoil as nf

    coordinates = _coordinates_from_geometry(geometry)
    alpha_deg = np.arange(alpha_min_deg, alpha_max_deg + alpha_step_deg / 2, alpha_step_deg)

    label_suffix = f" {geometry.naca_code}" if geometry.source in ("naca4", "naca5") else ""
    label = f"neuralfoil:{geometry.source}{label_suffix}"

    slices: list[PolarSlice] = []
    n_total = 0
    n_dropped = 0

    for reynolds in reynolds_list:
        # NeuralFoil >=0.3.x no longer accepts the 'mach' argument. Run
        # incompressible and apply Prandtl-Glauert manually per Mach.
        try:
            aero = nf.get_aero_from_coordinates(
                coordinates=coordinates,
                alpha=alpha_deg,
                Re=reynolds,
            )
        except Exception as exc:
            raise RuntimeError(
                f"NeuralFoil falhou para Re={reynolds:.3g}: {exc}"
            ) from exc

        cl_inc = np.asarray(aero["CL"], dtype=float)
        cd_inc = np.asarray(aero["CD"], dtype=float)
        confidence = np.asarray(
            aero.get("analysis_confidence", np.ones_like(cl_inc)), dtype=float
        )

        valid_base = np.isfinite(cl_inc) & np.isfinite(cd_inc) & (confidence > 0.1)
        n_total += len(alpha_deg) * len(mach_list)
        n_dropped += int((~valid_base).sum()) * len(mach_list)

        if not valid_base.any():
            continue

        for mach in mach_list:
            # Prandtl-Glauert correction: Cl_c = Cl / β, Cd_c = Cd / β
            # where β = sqrt(1 - M²), same as bemt.py does in element_state.
            # For Mach 0 or very low, β ≈ 1 and the correction is a no-op.
            beta = float(np.sqrt(max(0.0, 1.0 - mach ** 2)))
            if beta < 1e-3:
                warnings.warn(
                    f"NeuralFoil: Mach={mach:.2f} is sonic or supersonic. "
                    f"Prandtl-Glauert diverges, so the slice is ignored."
                )
                continue
            cl = cl_inc[valid_base] / beta
            cd = cd_inc[valid_base] / beta

            slices.append(PolarSlice(
                alpha_deg=alpha_deg[valid_base].tolist(),
                cl=cl.tolist(),
                cd=cd.tolist(),
                reynolds=float(reynolds),
                mach=float(mach),
                label=label,
            ))

    if n_dropped:
        warnings.warn(
            f"NeuralFoil: {n_dropped} of {n_total} alpha points did not converge "
            f"with sufficient confidence and were omitted."
        )
    return slices
