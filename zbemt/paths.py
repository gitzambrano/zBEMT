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
user projects, the output folder, and one small JSON file of remembered
user choices (`load_app_setting` / `save_app_setting`, for example the
executable path picked in the GUI's "Locate…" dialog).

The resolver distinguishes editable and installed layouts and returns the
same logical resource locations in both cases.
The resolution order is explicit environment variable, repository resources
when available, and the user data directory for installed use. The returned
paths are platform-aware and callers must handle missing optional resources."""

from __future__ import annotations

import json
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


def settings_file() -> Path:
    """The single JSON file that remembers small user choices between
    sessions (for example the XFOIL executable picked in the GUI's
    "Locate…" dialog).

    Lives inside `user_data_dir()` (``ZBEMT_HOME`` > ``~/.zbemt``), so a
    test or an isolated session redirects the whole store by setting one
    environment variable."""
    return user_data_dir() / "settings.json"


def load_app_setting(key: str, default=None):
    """Return the value stored under ``key``, or ``default``.

    The store is one JSON object. A missing file, a corrupt file, or a
    missing key all return ``default``; nothing raises to the caller."""
    try:
        with open(settings_file(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return default
    if not isinstance(data, dict):
        return default
    return data.get(key, default)


def save_app_setting(key: str, value) -> None:
    """Write ``value`` under ``key``, keeping every other stored key.

    The new content is written to a temporary file first. The temporary
    file then replaces the real file, so an interrupted write cannot
    leave half of the old and half of the new content behind. A previous
    corrupt or missing store is simply overwritten."""
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            data = loaded
    except (OSError, ValueError):
        pass
    data[key] = value
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(tmp_path, path)


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
