"""`Project` constructors shared across test files.

Plain functions (not pytest fixtures) because the suite also runs under
`python -m unittest tests.<file>`, where `@pytest.fixture` does not work.

The constructors below are NOT identical to each other (different meshes
and configs per source file) -- kept as named variants instead of blindly
unified, so as not to change the behavior of any existing test.
"""
from dataclasses import asdict

from zbemt import geometry
from zbemt.bemt import BEMTConfig
from zbemt.models import Project, AirfoilDef


def make_studies_project(**cfg_overrides) -> Project:
    """Project used by `tests/regression/test_studies.py` (8x12 mesh, `config` as a raw dict)."""
    geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                      twist_root_deg=14.0, twist_tip_deg=2.0,
                                      root_cutout_norm=0.15, radius_m=1.0, n_stations=12)
    airfoil = AirfoilDef(source="analytical", stall_model="clip",
                          alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
    cfg = dict(Ne=8, Npsi=12, solver="fixed_point", max_iter=150)
    cfg.update(cfg_overrides)
    return Project(name="teste", geometry=geom, airfoil=airfoil, config=cfg)


def make_api_fast_project(path: str) -> Project:
    """Project used by `tests/regression/test_api.py` (8x10 mesh, `config` via `asdict(BEMTConfig(...))`,
    requires `path` because the API tests persist the project to disk)."""
    geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                      radius_m=1.0, n_stations=10)
    airfoil = AirfoilDef(source="analytical", stall_model="clip")
    cfg = asdict(BEMTConfig(Ne=8, Npsi=10, solver="fixed_point", max_iter=150))
    # This analytical 'clip' polar carries no Viterna extension, so the
    # full-range reverse-flow model would be invalid for it -- the
    # comparison validation (Item 5) now catches exactly that pairing.
    cfg["reverse_flow_model"] = "simple_flip"
    return Project(name="teste_api", path=path, geometry=geom, airfoil=airfoil, config=cfg)


# --- patch a name across every GUI module ------------------------------------
# After splitting `zbemt/gui/app.py` into modules (item S1), each widget
# module has ITS OWN `QMessageBox`, bound at import time. Swapping the name
# only in `zbemt.gui.app` no longer reaches the tabs -- and a real
# `QMessageBox` in a headless suite hangs indefinitely waiting for a click.
# That is why the patch is applied to every module at once.

def patch_message_box_everywhere(name: str = "QMessageBox", value=None):
    """Context manager that replaces ``name`` in every GUI module that has
    it. Returns the mock used (the same object in every module, so
    assertions about calls work regardless of which tab triggered the
    dialog)."""
    import contextlib
    import importlib
    from unittest import mock

    from zbemt.gui.app import GUI_MODULES

    replacement = mock.MagicMock() if value is None else value

    @contextlib.contextmanager
    def _cm():
        with contextlib.ExitStack() as stack:
            for module_name in ("zbemt.gui.app",) + GUI_MODULES:
                module = importlib.import_module(module_name)
                if hasattr(module, name):
                    stack.enter_context(mock.patch.object(module, name, replacement))
            yield replacement

    return _cm()


# --- skipping the GUI when Qt is absent ---------------------------------------
# The engine and the CLI run without Qt ON PURPOSE (a batch on a headless
# server must not need it), and CI has a job that installs the base
# dependencies only, precisely to prove that. A test that imports a
# `zbemt.gui` module must therefore SKIP there, not fail -- a collection
# error in that job says "the engine needs Qt", which is the opposite of
# what it is checking.

try:                                     # noqa: SIM105
    import PyQt6                          # noqa: F401
    HAS_QT = True
except ModuleNotFoundError:              # pragma: no cover -- depends on the env
    HAS_QT = False


def requires_qt(target):
    """Class/method decorator: skip when PyQt6 is not installed."""
    import unittest
    return unittest.skipUnless(
        HAS_QT, "PyQt6 is not installed (the engine and CLI run without it "
                "on purpose -- see the 'engine' job in .github/workflows)")(target)
