"""
test_example_project_roundtrip.py
=================================

Opening a project and saving it again must not change it.

`test_models.py` already round-trips dataclasses the tests themselves
construct. Those objects are clean by construction: every field set, every
type exactly what the annotation says. The files under `projects/` are not
that. They were written by earlier versions of the writer, edited by hand,
and carry the mode-dependent axis keys of `zbemt/nomenclature.py` -- and they
are the files a user copies to start from, so a field silently lost on the
first save is lost in every project descended from that copy.

The failure mode this catches is quiet by nature. A field the reader does not
know about is dropped, and the project still opens, still validates, still
solves -- with a default in place of the value the file asked for. Nothing
raises; the only symptom is a different answer.

The round trip is done into a temporary copy. Nothing under `projects/` is
written to.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from dataclasses import asdict, is_dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zbemt import api
from zbemt.models import default_project_paths

PROJECTS = ROOT / "projects"

#: Written by `save_project` from `Project.name`, which `open_project`
#: defaults to the FOLDER name. Copying a project into a temporary folder
#: therefore changes it legitimately, and it is not part of what the round
#: trip is checking.
IGNORED_FILES = ("meta.bemt",)


def _projects() -> list[Path]:
    return sorted(p for p in PROJECTS.iterdir() if p.is_dir())


def _normalize(value):
    """Puts a loaded value into a form two loads can be compared in.

    JSON has no tuples and no dataclasses, and a list of floats read back
    from disk is a plain list of plain floats. Comparing the OBJECTS after
    two loads, rather than the bytes on disk, is what makes the test about
    information rather than about formatting -- a writer that reorders keys
    or changes indentation is not a defect."""
    if is_dataclass(value) and not isinstance(value, type):
        return _normalize(asdict(value))
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, float) and value != value:
        return "nan"
    return value


def _portrait(project) -> dict:
    """Everything about a project that a save must preserve."""
    return {
        "config": _normalize(project.config),
        "geometry": _normalize(project.geometry),
        "airfoil": _normalize(project.airfoil),
        "airfoil_sections": _normalize(project.airfoil_sections),
        "batches": _normalize(project.batches),
        "saved_cases": _normalize(project.saved_cases),
    }


class TestRoundTrip(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _copy(self, source: Path) -> Path:
        dest = self.tmp / source.name
        shutil.copytree(source, dest)
        return dest

    def test_open_and_save_preserves_the_whole_project(self):
        """Load, save, load again: the two loads must describe the same
        project, field by field."""
        for source in _projects():
            with self.subTest(project=source.name):
                copy = self._copy(source)
                before = _portrait(api.open_project(str(copy)))
                api.save_project(api.open_project(str(copy)))
                after = _portrait(api.open_project(str(copy)))
                self.assertEqual(before, after,
                                  f"{source.name} changed on save/reload")

    def test_save_is_stable_the_second_time(self):
        """The second save must produce the same bytes as the first.

        A writer that is merely idempotent in CONTENT can still rewrite
        every file on every save -- which turns opening a project in the
        GUI into a diff in the user's version control, and makes a real
        change impossible to see among the noise."""
        for source in _projects():
            with self.subTest(project=source.name):
                copy = self._copy(source)
                api.save_project(api.open_project(str(copy)))
                first = {p.name: p.read_bytes()
                         for p in (copy / "inputs").glob("*.bemt")}
                api.save_project(api.open_project(str(copy)))
                second = {p.name: p.read_bytes()
                          for p in (copy / "inputs").glob("*.bemt")}
                rewritten = sorted(n for n in first
                                   if first[n] != second.get(n))
                self.assertEqual(rewritten, [],
                                 f"{source.name}: rewritten on the second save: {rewritten}")

    def test_no_key_of_the_original_file_disappears(self):
        """The direct question: is every key the file on disk carries still
        there after a save?

        The comparison above works on the loaded objects, so a key the
        reader ignores ENTIRELY is invisible to it -- dropped on load and
        therefore identical on both sides. This one reads the JSON, and a
        key that leaves has to be a deliberate removal."""
        for source in _projects():
            with self.subTest(project=source.name):
                copy = self._copy(source)
                paths = default_project_paths(str(copy))
                before = {}
                for name, path in paths.items():
                    if (path.suffix == ".bemt" and path.is_file()
                            and path.name not in IGNORED_FILES):
                        before[name] = json.loads(path.read_text(encoding="utf-8"))
                api.save_project(api.open_project(str(copy)))
                lost = []
                for name, content in before.items():
                    path = paths[name]
                    if not path.exists():
                        # `batch.bemt` is deliberately folded into
                        # `batches.bemt` and deleted; see `api.save_project`.
                        if name != "legacy_batch":
                            lost.append(f"{path.name}: file gone")
                        continue
                    after = json.loads(path.read_text(encoding="utf-8"))
                    lost += [f"{path.name}: {k}"
                             for k in self._lost_keys(content, after)]
                self.assertEqual(lost, [],
                                 f"{source.name} lost keys on save: {lost}")

    @staticmethod
    def _lost_keys(before, after, prefix="") -> list[str]:
        if isinstance(before, dict):
            if not isinstance(after, dict):
                return [prefix or "(root)"]
            missing = []
            for key, value in before.items():
                if key not in after:
                    missing.append(f"{prefix}{key}")
                else:
                    missing += TestRoundTrip._lost_keys(
                        value, after[key], f"{prefix}{key}.")
            return missing
        if isinstance(before, list) and isinstance(after, list):
            missing = []
            for i, value in enumerate(before[:len(after)]):
                missing += TestRoundTrip._lost_keys(
                    value, after[i], f"{prefix}[{i}].")
            if len(after) < len(before):
                missing.append(f"{prefix}[{len(after)}:] dropped")
            return missing
        return []


if __name__ == "__main__":
    unittest.main()
