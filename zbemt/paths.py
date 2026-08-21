"""Resolve repository, documentation, project, and output paths.

Purpose: centralize filesystem locations so GUI, CLI, reports, and generators
use the same offline resources. Inputs are optional base paths and project
names; outputs are ``Path`` objects and validated directories. Functions do
not run the solver or interpret project physics. ``api.py`` owns project I/O,
while documentation and screenshot tools consume the resolved paths. Paths are
platform-aware; missing optional resources are reported to callers rather than

paths.py
========

Resolves where the data that is NOT code lives: embedded documentation,
user projects, and the output folder.

The resolver distinguishes editable and installed layouts and returns the
same logical resource locations in both cases.
The resolution order is explicit environment variable, repository resources
when available, and the user data directory for installed use. The returned
paths are platform-aware and callers must handle missing optional resources."""

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
