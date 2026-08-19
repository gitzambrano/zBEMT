"""
paths.py
========

Resolves where the data that is NOT code lives: embedded documentation,
user projects, and the output folder.

Why this exists: up to now the GUI computed everything as
``Path(__file__).parents[2]``, which gives the repository root in an
editable install (``pip install -e .``) but the ``site-packages`` folder
in a real installed wheel -- there's no ``projects/`` or ``docs/`` there,
and the GUI would try to create projects inside the Python installation.

The three functions below handle both cases, in this priority order:

1. explicit environment variable (the user said so, obey);
2. the repository, when running from inside it (development mode --
   this is what keeps `projects/starter_rotor` showing up in the GUI
   for anyone who cloned it);
3. the user data directory (``~/.zbemt``), for a real installation.

No new dependency: `platformdirs` would handle case 3 more precisely
per OS, but ``~/.zbemt`` is predictable, works the same on
Windows/Linux/macOS, and doesn't cost the engine a dependency, which is
deliberately lean (see `pyproject.toml`).
"""

from __future__ import annotations

import os
from pathlib import Path

#: Root of the installed package (``.../zbemt``).
_PACKAGE_DIR = Path(__file__).resolve().parent

#: Candidate repository root: only the real root if the repository's
#: working directories exist alongside the package.
_MAYBE_REPO_ROOT = _PACKAGE_DIR.parent


def _repo_root_or_none() -> Path | None:
    """Return the repository root if we're running from inside it.

    The marker is ``pyproject.toml`` next to the package: present in an
    editable install / clone, absent in ``site-packages``."""
    if (_MAYBE_REPO_ROOT / "pyproject.toml").is_file():
        return _MAYBE_REPO_ROOT
    return None


def user_data_dir() -> Path:
    """Base for user data when zBEMT is really installed.
    Overridable via ``ZBEMT_HOME``."""
    env = os.environ.get("ZBEMT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".zbemt"


def projects_root(create: bool = False) -> Path:
    """Where the user's projects live.

    ``ZBEMT_PROJECTS`` > ``<repo>/projects`` > ``<user_data_dir>/projects``.
    """
    env = os.environ.get("ZBEMT_PROJECTS")
    if env:
        root = Path(env).expanduser().resolve()
    else:
        repo = _repo_root_or_none()
        root = (repo / "projects") if repo else (user_data_dir() / "projects")
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def outputs_dir(create: bool = False) -> Path:
    """Default destination for reports and exports.

    ``ZBEMT_OUTPUTS`` > ``<repo>/outputs`` > ``<user_data_dir>/outputs``.
    """
    env = os.environ.get("ZBEMT_OUTPUTS")
    if env:
        out = Path(env).expanduser().resolve()
    else:
        repo = _repo_root_or_none()
        out = (repo / "outputs") if repo else (user_data_dir() / "outputs")
    if create:
        out.mkdir(parents=True, exist_ok=True)
    return out


def documentation_path() -> Path | None:
    """Path to ``documentation.html`` (embedded help, "?" button / F1).

    Looks first in ``<repo>/docs`` and only then inside the package.

    The order matters and isn't the intuitive one. ``setup.py`` copies
    ``docs/`` into ``zbemt/docs/`` when packaging, and an editable install
    (``pip install -e .``) leaves that copy in the working directory: if
    the packaged copy came first, anyone editing the docs would hit F1 and
    read the copy frozen at the last ``build``, without understanding why
    the change didn't show up. Outside a repository -- the case of a wheel
    install -- ``_repo_root_or_none()`` returns ``None`` and the packaged
    copy is used, which is exactly what it's there for.

    Returns ``None`` if neither is found, so the GUI can warn instead of
    crashing."""
    repo = _repo_root_or_none()
    if repo:
        no_repo = repo / "docs" / "documentation.html"
        if no_repo.is_file():
            return no_repo

    empacotado = _PACKAGE_DIR / "docs" / "documentation.html"
    if empacotado.is_file():
        return empacotado
    return None
