"""Integrate optional external airfoil-polar generation engines.

The module accepts profile geometry, Reynolds and Mach lists, angle limits,
and engine options. It detects supported engines, validates requests, and
returns polar slices or structured errors. It does not run BEMT, and it does
not persist projects. ``airfoils.py`` consumes successful tables, ``api.py``
exposes the operation, and the Airfoil GUI supplies requests.

Two engines are supported. NeuralFoil runs in process through the optional
``neuralfoil`` package. XFOIL runs out of process through the ``xfoil``
executable: the module writes the coordinates and a command script into a
temporary directory, calls the binary there for each Reynolds number, and
parses the accumulated polar dump that the binary writes back. Unsupported
engines are rejected explicitly. Returned data inherit the external engine's
operating envelope and confidence limitations.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path

import numpy as np

from .models import ProfileGeometry, PolarSlice

SUPPORTED_ENGINES = ("neuralfoil", "xfoil")

# Wall-clock limit for one XFOIL subprocess (one Reynolds sweep).
_XFOIL_TIMEOUT_S = 120


def _xfoil_command() -> Optional[str]:
    """Resolve the XFOIL executable.

    Order: the ``ZBEMT_XFOIL_BIN`` environment variable (a full path to
    ``xfoil.exe``/``xfoil``, useful when the binary is not on PATH),
    then ``xfoil`` through ``PATH``. Returns ``None`` when neither
    resolves to an existing executable."""
    explicit = os.environ.get("ZBEMT_XFOIL_BIN", "").strip()
    if explicit and Path(explicit).is_file():
        return explicit
    return shutil.which("xfoil")


def is_available(engine: str) -> bool:
    """Used by the GUI ('f) External engine' block) and by the CLI
    (``--gen-neuralfoil``) to decide whether the corresponding button
    or flag is enabled. ``neuralfoil`` requires the package of the same
    name installed in the current environment (real check via
    ``importlib.util.find_spec``, with nothing hardcoded). ``xfoil``
    requires the ``xfoil`` executable, found either through the
    ``ZBEMT_XFOIL_BIN`` environment variable or on ``PATH``. Any other
    engine returns ``False``."""
    if engine not in SUPPORTED_ENGINES:
        return False
    if engine == "xfoil":
        return _xfoil_command() is not None
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


def _parse_xfoil_polar(text: str) -> tuple[list[float], list[float], list[float]]:
    """Parse a standard XFOIL accumulated polar dump into parallel
    (alpha_deg, cl, cd) lists. Leading '#' comment lines and the header
    block are skipped. The data block starts below the last header line
    whose first column name starts with 'alpha' (typical columns:
    ``alpha CL CD CDp CM ...``), and the first three columns of each data
    row are read as alpha, CL and CD. Rows that fail to parse or that hold
    non-finite values are skipped, and trailing blank lines are tolerated.
    An empty or unrecognizable dump raises ``ValueError``."""
    if not text or not text.strip():
        raise ValueError("XFOIL polar dump is empty.")
    lines = text.splitlines()
    header_index = None
    for position in range(len(lines)):
        tokens = lines[position].split()
        if tokens and tokens[0].lower().startswith("alpha"):
            # Keep scanning: a later column-name line wins, so the parser
            # lands on the LAST header of an accumulated dump.
            header_index = position
    if header_index is None:
        raise ValueError(
            "XFOIL polar dump has no column-header line starting with "
            "'alpha'; the content is not a recognizable polar output."
        )
    alpha_deg: list[float] = []
    cl: list[float] = []
    cd: list[float] = []
    for line in lines[header_index + 1:]:
        tokens = line.split()
        if len(tokens) < 3:
            continue
        try:
            alpha = float(tokens[0])
            lift = float(tokens[1])
            drag = float(tokens[2])
        except ValueError:
            continue
        if not (np.isfinite(alpha) and np.isfinite(lift) and np.isfinite(drag)):
            continue
        alpha_deg.append(alpha)
        cl.append(lift)
        cd.append(drag)
    if not alpha_deg:
        raise ValueError(
            "XFOIL polar dump contains a column header but no usable data row."
        )
    return alpha_deg, cl, cd


def _mach_corrected_slices(engine_name: str, alpha_valid_deg: np.ndarray,
                           cl_inc: np.ndarray, cd_inc: np.ndarray,
                           mach_list: list[float], reynolds: float,
                           label: str) -> list[PolarSlice]:
    """Tail shared by both engines: apply the Prandtl-Glauert correction
    per Mach (Cl_c = Cl / beta, Cd_c = Cd / beta, beta = sqrt(1 - M^2),
    the same correction bemt.py applies per element) and build one
    ``PolarSlice`` for each Mach that survives it. A sonic or supersonic
    Mach emits a warning and contributes no slice."""
    slices: list[PolarSlice] = []
    for mach in mach_list:
        beta = float(np.sqrt(max(0.0, 1.0 - mach ** 2)))
        if beta < 1e-3:
            warnings.warn(
                f"{engine_name}: Mach={mach:.2f} is sonic or supersonic. "
                f"Prandtl-Glauert diverges, so the slice is ignored."
            )
            continue
        slices.append(PolarSlice(
            alpha_deg=alpha_valid_deg.tolist(),
            cl=(cl_inc / beta).tolist(),
            cd=(cd_inc / beta).tolist(),
            reynolds=float(reynolds),
            mach=float(mach),
            label=label,
        ))
    return slices


def _validate_xfoil_adjustments(ncrit: float, xtr_top: float,
                                xtr_bot: float) -> None:
    """Validates the XFOIL-dedicated transition inputs before any process
    starts (a pure check: no binary resolution, no subprocess).

    ``ncrit`` accepts any finite number greater than zero; XFOIL's usual
    range is approximately 1 to 15. ``xtr_top``/``xtr_bot`` are chord
    fractions and accept the half-open interval (0, 1], where 1.0 means
    free transition over the whole surface."""
    if not (np.isfinite(ncrit) and ncrit > 0):
        raise ValueError(
            f"ncrit must be a finite number greater than 0 (got {ncrit}).")
    for name, value in (("xtr_top", xtr_top), ("xtr_bot", xtr_bot)):
        if not (np.isfinite(value) and 0.0 < value <= 1.0):
            raise ValueError(
                f"{name} must be a finite chord fraction in (0, 1], where "
                f"1.0 means free transition (got {value}).")


def _xfoil_script(reynolds: float, alpha_min_deg: float, alpha_max_deg: float,
                  alpha_step_deg: float, ncrit: float, xtr_top: float,
                  xtr_bot: float,
                  polar_name: str = "polar.dat") -> str:
    """Builds ONE XFOIL command script as text (pure function: no I/O and
    no subprocess).

    The XFOIL-dedicated adjustment inputs ride right behind ``VISC``:
    ``VPAR`` opens the boundary-layer parameter submenu, ``N`` sets the
    critical e^N amplification factor, and ``XTR`` forces transition at
    the two chord fractions (top then bottom); the empty line returns to
    OPER. These spellings are the ones XFOIL 6.99 recognizes. The
    ``NCRIT``/``XTRTOP``/``XTRBOT`` words do NOT exist in that binary:
    typed anywhere, they draw "command not recognized" and the run
    continues with the baseline transition, silently.

    Accumulation opens BEFORE the alpha sweep (the first PACC names the
    save file) and closes AFTER it (the second PACC writes the file);
    without that explicit close the process dies inside the .OPERv
    submenu and the rows are lost. ``polar_name`` is the accumulated dump
    filename; one distinct name per Reynolds prevents a later sweep from
    appending into an earlier sweep's rows."""
    return (
        "LOAD airfoil.dat\n"
        "\n"
        "OPER\n"
        f"VISC {reynolds:.6g}\n"
        "VPAR\n"
        f"N {ncrit:.4g}\n"
        f"XTR {xtr_top:.4g} {xtr_bot:.4g}\n"
        "\n"
        "ITER 100\n"
        "PACC\n"
        f"{polar_name}\n"
        "\n"
        f"ASEQ {alpha_min_deg:g} {alpha_max_deg:g} {alpha_step_deg:g}\n"
        "PACC\n"
        f"{polar_name}\n"
        "\n"
        ".\n"
        "QUIT\n"
    )


def _run_polar_xfoil(geometry: ProfileGeometry,
                     reynolds_list: list[float], mach_list: list[float],
                     alpha_min_deg: float, alpha_max_deg: float,
                     alpha_step_deg: float,
                     ncrit: float = 9.0, xtr_top: float = 1.0,
                     xtr_bot: float = 1.0) -> list[PolarSlice]:
    """Run XFOIL over ``geometry`` for each Reynolds in ``reynolds_list``.

    For each Reynolds the function writes one command script built by
    `_xfoil_script` (``LOAD`` / ``OPER`` / ``VISC`` / ``VPAR`` with the
    ``N``/``XTR`` adjustment inputs / ``ITER 100`` / ``ASEQ`` / ``PACC``
    / ``QUIT``), executes the binary with the script, and parses each
    accumulated polar file the binary leaves behind. ``ncrit``,
    ``xtr_top`` and ``xtr_bot`` are the XFOIL-dedicated adjustment inputs
    (see `_validate_xfoil_adjustments`); other engines ignore them.

    A Reynolds whose polar file is missing or empty is reported with a
    warning and skipped, matching how the BEMT solver treats points that
    do not converge. If no Reynolds produces any point, the function
    raises ``RuntimeError``. Output is captured; nothing is printed."""
    command = _xfoil_command()
    if command is None:
        raise RuntimeError(
            "The 'xfoil' executable was not found. Install XFOIL and either add its "
            "folder to PATH or set the ZBEMT_XFOIL_BIN environment variable to the "
            "full path of the executable (alternatively: import a CSV/experimental "
            "table instead of using an external engine)."
        )

    coordinates = _coordinates_from_geometry(geometry)

    label_suffix = f" {geometry.naca_code}" if geometry.source in ("naca4", "naca5") else ""
    label = f"xfoil:{geometry.source}{label_suffix}"

    slices: list[PolarSlice] = []

    with tempfile.TemporaryDirectory(prefix="zbemt_xfoil_") as tmpdir:
        dat_path = os.path.join(tmpdir, "airfoil.dat")
        with open(dat_path, "w", encoding="ascii") as handle:
            for x, y in coordinates:
                handle.write("%f %f\n" % (float(x), float(y)))

        for index, reynolds in enumerate(reynolds_list):
            polar_path = os.path.join(tmpdir, f"polar_{index}.dat")
            script_path = os.path.join(tmpdir, f"commands_{index}.txt")
            script_text = _xfoil_script(
                reynolds, alpha_min_deg, alpha_max_deg, alpha_step_deg,
                ncrit, xtr_top, xtr_bot, polar_name=f"polar_{index}.dat")
            with open(script_path, "w", encoding="ascii", newline="\r\n") as handle:
                handle.write(script_text)

            try:
                # XFOIL reads its command stream from STDIN; the script
                # is piped in rather than passed as an argument.
                with open(script_path, "rb") as script_handle:
                    subprocess.run(
                        [command],
                        stdin=script_handle,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=_XFOIL_TIMEOUT_S,
                        cwd=tmpdir,
                        check=False,
                    )
            except (OSError, subprocess.TimeoutExpired):
                warnings.warn(f"XFOIL: no converged points for Re={reynolds:.3g}")
                continue

            text = ""
            if os.path.isfile(polar_path):
                with open(polar_path, "r", errors="replace") as handle:
                    text = handle.read()
            try:
                alpha_vals, cl_vals, cd_vals = _parse_xfoil_polar(text)
            except ValueError:
                warnings.warn(f"XFOIL: no converged points for Re={reynolds:.3g}")
                continue

            slices.extend(_mach_corrected_slices(
                engine_name="XFOIL",
                alpha_valid_deg=np.asarray(alpha_vals, dtype=float),
                cl_inc=np.asarray(cl_vals, dtype=float),
                cd_inc=np.asarray(cd_vals, dtype=float),
                mach_list=mach_list,
                reynolds=reynolds,
                label=label,
            ))

    if not slices:
        raise RuntimeError(
            "XFOIL produced no usable polar points for any Reynolds in the "
            "requested sweep. Check the airfoil geometry and the requested "
            "Reynolds/alpha ranges."
        )
    return slices

def run_polar(engine: str, geometry: ProfileGeometry,
              reynolds_list: list[float], mach_list: list[float],
              alpha_min_deg: float, alpha_max_deg: float,
              alpha_step_deg: float, *, ncrit: float = 9.0,
              xtr_top: float = 1.0, xtr_bot: float = 1.0) -> list[PolarSlice]:
    """Run an external engine over ``geometry`` for each (Reynolds, Mach)
    combination in ``reynolds_list`` x ``mach_list``, over the requested
    alpha range, and return a list of ``PolarSlice`` ready to be
    appended to ``AirfoilDef.table_slices`` (same structure used by
    tables imported from CSV/experimental data, because the import pipeline
    does not distinguish the origin once generated).

    Supported engines: ``"neuralfoil"`` runs the NeuralFoil package in
    process; ``"xfoil"`` drives the ``xfoil`` executable as a subprocess
    (see ``_run_polar_xfoil``).

    Keyword-only adjustment inputs (XFOIL-dedicated): ``ncrit`` is the
    critical e^N amplification factor of the transition criterion, and
    ``xtr_top``/``xtr_bot`` force transition at a chord fraction (1.0 =
    free transition). They reach only the XFOIL binary; the NeuralFoil
    path ignores them. All three are validated here, before any process
    starts: an invalid value raises ``ValueError``.

    Robustness (same pattern as ``bemt.py`` for points that do not
    converge in the inflow solver): a specific alpha point that
    NeuralFoil cannot resolve with confidence (low ``analysis_confidence``
    or NaN in Cl/Cd) is silently dropped from that slice. An aggregate
    warning is emitted at the end, but the whole sweep is not brought down
    because of a few outlier points. XFOIL applies the same philosophy per
    Reynolds number.
    """
    if engine not in SUPPORTED_ENGINES:
        raise ValueError(
            f"Unknown external engine: {engine!r} (expected one of "
            f"{SUPPORTED_ENGINES})."
        )
    if not reynolds_list or not mach_list:
        raise ValueError(
            f"run_polar({engine!r}, ...) needs at least one value in reynolds_list "
            "and in mach_list to define the sweep."
        )
    if alpha_step_deg <= 0:
        raise ValueError(f"alpha_step_deg must be positive (got {alpha_step_deg}).")
    _validate_xfoil_adjustments(ncrit, xtr_top, xtr_bot)

    if engine == "xfoil":
        return _run_polar_xfoil(geometry, reynolds_list, mach_list,
                                alpha_min_deg, alpha_max_deg, alpha_step_deg,
                                ncrit=ncrit, xtr_top=xtr_top, xtr_bot=xtr_bot)

    # --- NeuralFoil path (in-process package), unchanged below ----------
    if not is_available("neuralfoil"):
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

        # Prandtl-Glauert per Mach + PolarSlice construction, shared with
        # the XFOIL path (see _mach_corrected_slices).
        slices.extend(_mach_corrected_slices(
            engine_name="NeuralFoil",
            alpha_valid_deg=alpha_deg[valid_base],
            cl_inc=cl_inc[valid_base],
            cd_inc=cd_inc[valid_base],
            mach_list=mach_list,
            reynolds=reynolds,
            label=label,
        ))

    if n_dropped:
        warnings.warn(
            f"NeuralFoil: {n_dropped} of {n_total} alpha points did not converge "
            f"with sufficient confidence and were omitted."
        )
    return slices
