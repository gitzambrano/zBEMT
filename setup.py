"""Copies docs/ into zbemt/docs/ before the wheel is built.

The embedded help ("?" button / F1) has to ship inside the wheel, but
`docs/` lives at the repository root and `[tool.setuptools.package-data]`
in pyproject.toml only picks up files already inside a package directory.
This copies the tree in before setuptools collects package data, so the
wheel ends up with `zbemt/docs/documentation.html` and its figures.

An editable install (`pip install -e .`) does not need this: for that case
`zbemt.paths.documentation_path()` reads `docs/documentation.html` from the
repository directly, and never looks at the packaged copy.
"""
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = Path(__file__).parent


class build_py(_build_py):
    def run(self):
        origem = ROOT / "docs"
        destino = ROOT / "zbemt" / "docs"
        if origem.is_dir():
            if destino.exists():
                shutil.rmtree(destino)
            shutil.copytree(origem, destino)
        super().run()


setup(cmdclass={"build_py": build_py})
