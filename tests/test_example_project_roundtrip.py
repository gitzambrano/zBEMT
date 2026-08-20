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

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from zbemt import api
from zbemt.models import default_project_paths

PROJECTS = RAIZ / "projects"

#: Written by `save_project` from `Project.name`, which `open_project`
#: defaults to the FOLDER name. Copying a project into a temporary folder
#: therefore changes it legitimately, and it is not part of what the round
#: trip is checking.
ARQUIVOS_IGNORADOS = ("meta.bemt",)


def _projetos() -> list[Path]:
    return sorted(p for p in PROJECTS.iterdir() if p.is_dir())


def _normalizar(valor):
    """Puts a loaded value into a form two loads can be compared in.

    JSON has no tuples and no dataclasses, and a list of floats read back
    from disk is a plain list of plain floats. Comparing the OBJECTS after
    two loads, rather than the bytes on disk, is what makes the test about
    information rather than about formatting -- a writer that reorders keys
    or changes indentation is not a defect."""
    if is_dataclass(valor) and not isinstance(valor, type):
        return _normalizar(asdict(valor))
    if isinstance(valor, dict):
        return {k: _normalizar(v) for k, v in sorted(valor.items())}
    if isinstance(valor, (list, tuple)):
        return [_normalizar(v) for v in valor]
    if isinstance(valor, float) and valor != valor:
        return "nan"
    return valor


def _retrato(projeto) -> dict:
    """Everything about a project that a save must preserve."""
    return {
        "config": _normalizar(projeto.config),
        "geometry": _normalizar(projeto.geometry),
        "airfoil": _normalizar(projeto.airfoil),
        "airfoil_sections": _normalizar(projeto.airfoil_sections),
        "batches": _normalizar(projeto.batches),
        "saved_cases": _normalizar(projeto.saved_cases),
    }


class TestIdaEVolta(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _copiar(self, origem: Path) -> Path:
        destino = self.tmp / origem.name
        shutil.copytree(origem, destino)
        return destino

    def test_abrir_e_salvar_preserva_todo_o_projeto(self):
        """Load, save, load again: the two loads must describe the same
        project, field by field."""
        for origem in _projetos():
            with self.subTest(projeto=origem.name):
                copia = self._copiar(origem)
                antes = _retrato(api.open_project(str(copia)))
                api.save_project(api.open_project(str(copia)))
                depois = _retrato(api.open_project(str(copia)))
                self.assertEqual(antes, depois,
                                 f"{origem.name} changed on save/reload")

    def test_salvar_e_estavel_na_segunda_vez(self):
        """The second save must produce the same bytes as the first.

        A writer that is merely idempotent in CONTENT can still rewrite
        every file on every save -- which turns opening a project in the
        GUI into a diff in the user's version control, and makes a real
        change impossible to see among the noise."""
        for origem in _projetos():
            with self.subTest(projeto=origem.name):
                copia = self._copiar(origem)
                api.save_project(api.open_project(str(copia)))
                primeiro = {p.name: p.read_bytes()
                            for p in (copia / "inputs").glob("*.bemt")}
                api.save_project(api.open_project(str(copia)))
                segundo = {p.name: p.read_bytes()
                           for p in (copia / "inputs").glob("*.bemt")}
                mudaram = sorted(n for n in primeiro
                                 if primeiro[n] != segundo.get(n))
                self.assertEqual(mudaram, [],
                                 f"{origem.name}: rewritten on the second save: {mudaram}")

    def test_nenhuma_chave_do_arquivo_original_desaparece(self):
        """The direct question: is every key the file on disk carries still
        there after a save?

        The comparison above works on the loaded objects, so a key the
        reader ignores ENTIRELY is invisible to it -- dropped on load and
        therefore identical on both sides. This one reads the JSON, and a
        key that leaves has to be a deliberate removal."""
        for origem in _projetos():
            with self.subTest(projeto=origem.name):
                copia = self._copiar(origem)
                caminhos = default_project_paths(str(copia))
                antes = {}
                for nome, caminho in caminhos.items():
                    if (caminho.suffix == ".bemt" and caminho.is_file()
                            and caminho.name not in ARQUIVOS_IGNORADOS):
                        antes[nome] = json.loads(caminho.read_text(encoding="utf-8"))
                api.save_project(api.open_project(str(copia)))
                perdidas = []
                for nome, conteudo in antes.items():
                    caminho = caminhos[nome]
                    if not caminho.exists():
                        # `batch.bemt` is deliberately folded into
                        # `batches.bemt` and deleted; see `api.save_project`.
                        if nome != "legacy_batch":
                            perdidas.append(f"{caminho.name}: file gone")
                        continue
                    depois = json.loads(caminho.read_text(encoding="utf-8"))
                    perdidas += [f"{caminho.name}: {c}"
                                 for c in self._chaves_perdidas(conteudo, depois)]
                self.assertEqual(perdidas, [],
                                 f"{origem.name} lost keys on save: {perdidas}")

    @staticmethod
    def _chaves_perdidas(antes, depois, prefixo="") -> list[str]:
        if isinstance(antes, dict):
            if not isinstance(depois, dict):
                return [prefixo or "(root)"]
            faltando = []
            for chave, valor in antes.items():
                if chave not in depois:
                    faltando.append(f"{prefixo}{chave}")
                else:
                    faltando += TestIdaEVolta._chaves_perdidas(
                        valor, depois[chave], f"{prefixo}{chave}.")
            return faltando
        if isinstance(antes, list) and isinstance(depois, list):
            faltando = []
            for i, valor in enumerate(antes[:len(depois)]):
                faltando += TestIdaEVolta._chaves_perdidas(
                    valor, depois[i], f"{prefixo}[{i}].")
            if len(depois) < len(antes):
                faltando.append(f"{prefixo}[{len(depois)}:] dropped")
            return faltando
        return []


if __name__ == "__main__":
    unittest.main()
