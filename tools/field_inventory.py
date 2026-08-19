"""The spine of the field reference in ``docs/documentation.html``.

For every field the user can set, this collects -- from the code, never from
a hand-written list -- the four things a documentation subsection has to
state:

    * where it is on screen (tab, and position within that tab);
    * what it is (dataclass, type, default);
    * which file stores it (``.bemt``);
    * how to set it from the command line (dedicated flag, or ``--set``).

``tools/field_index.py`` already derives the on-screen ORDER. This module
answers the other three questions, and joins them onto that order, so a
documentation test can assert that every settable field has a subsection and
that the subsection states the right key and flag.

The GUI part needs Qt. Without it the inventory is still produced, minus the
tab/position columns -- the engine and CLI run without Qt on purpose.

    python tools/field_inventory.py             # readable table
    python tools/field_inventory.py --json      # machine-readable
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import MISSING, fields
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Zero-argument run prints the readable table (the IDE "Run" button).
DEFAULT_JSON = False

#: dataclass -> (``--set`` namespace, file under ``inputs/`` that stores it).
#: ``None`` namespace means the field has no ``--set`` path: it is not part of
#: config/airfoil/geom but of the flight condition or the batch, which the CLI
#: reaches through its own flags instead.
ORIGEM = {
    "RotorGeometryDef": ("geom", "geom.bemt"),
    "AirfoilDef": ("airfoil", "airfoil.bemt"),
    "BEMTConfig": ("config", "config.bemt"),
    "FlightCondition": (None, "saved_cases.bemt / batches.bemt"),
    "BatchDefinition": (None, "batches.bemt"),
}


def _dataclasses_de_entrada() -> dict:
    from zbemt import models
    from zbemt.bemt import BEMTConfig
    return {
        "RotorGeometryDef": models.RotorGeometryDef,
        "AirfoilDef": models.AirfoilDef,
        "BEMTConfig": BEMTConfig,
        "FlightCondition": models.FlightCondition,
        "BatchDefinition": models.BatchDefinition,
    }


def _padrao(campo) -> str:
    """The default as the documentation should print it."""
    if campo.default is not MISSING:
        return repr(campo.default)
    if campo.default_factory is not MISSING:        # type: ignore[misc]
        try:
            return repr(campo.default_factory())    # type: ignore[misc]
        except Exception:
            return "(computed)"
    return "(required)"


def _tipo(campo) -> str:
    t = campo.type
    return t if isinstance(t, str) else getattr(t, "__name__", str(t))


#: Flags whose target cannot be derived from dest or help text.
#:
#: The flight-condition flags are named by SLOT ("inplane"/"axial"), not by
#: letter, precisely because the letter rotates between rotor and propeller
#: mode -- so no amount of string matching connects `--mu-inplane` to the
#: engine field `mu_x`. See `zbemt/nomenclature.py`.
FLAGS_EXPLICITAS = {
    "mu_x": ["--mu-inplane", "--j-inplane", "--v-inplane", "--alpha-disk-deg"],
    "Vz": ["--v-axial", "--j-axial", "--mu-axial", "--alpha-rotor-deg"],
    "collective_deg": ["--collective"],
}

#: Matches that the help-text heuristic gets wrong. `--geom-*` configure the
#: ROTOR geometry, not `AirfoilDef.geometry` (the 2D profile coordinates).
FALSOS_POSITIVOS = {("geometry", "--geom-file"), ("geometry", "--geom-preset")}


def flags_dedicadas() -> dict:
    """{field name: [--flag, ...]} for the flags cli.py exposes by name.

    Derived by asking the real parser for its actions, then matching each
    action to a field. Two signals, in this order: the action's ``dest``
    equals the field name, or the action's help text names the field
    (``BEMTConfig.max_iter``, ``radius_m.``). Anything unmatched simply has
    no dedicated flag, which is the normal case -- ``--set`` covers it.
    """
    from zbemt import cli

    todos = set()
    for dc in _dataclasses_de_entrada().values():
        todos.update(f.name for f in fields(dc))

    achados: dict = {nome: list(v) for nome, v in FLAGS_EXPLICITAS.items()}
    parser = cli._build_parser()
    for acao in parser._actions:
        if not acao.option_strings:
            continue
        opcoes = [o for o in acao.option_strings if o.startswith("--")]
        # `--set` names example fields in its own help ("config.Ne=90"); it is
        # the generic escape hatch, never a given field's dedicated flag.
        if not opcoes or acao.dest == "set":
            continue
        alvo = None
        if acao.dest in todos:
            alvo = acao.dest
        else:
            ajuda = acao.help or ""
            # longest match first: `relax_schedule` must not lose to `relax`
            for nome in sorted(todos, key=len, reverse=True):
                if f".{nome}" in ajuda or ajuda.strip().startswith(nome):
                    alvo = nome
                    break
        if alvo:
            achados.setdefault(alvo, []).extend(
                o for o in opcoes if (alvo, o) not in FALSOS_POSITIVOS)
    return {k: v for k, v in achados.items() if v}


def ordem_na_tela() -> dict:
    """{field: (tab, position)} or {} when Qt is unavailable."""
    try:
        import PyQt6  # noqa: F401
    except ModuleNotFoundError:
        return {}
    from field_index import coletar_ordem_da_tela        # same folder
    posicao = {}
    for aba, campos in coletar_ordem_da_tela().items():
        for i, (campo, _ancora) in enumerate(campos):
            posicao.setdefault(campo, (aba, i))
    return posicao


def coletar() -> list:
    """One record per settable field, ready to drive a documentation test."""
    flags = flags_dedicadas()
    posicoes = ordem_na_tela()
    registros = []
    for nome_dc, dc in _dataclasses_de_entrada().items():
        namespace, arquivo = ORIGEM[nome_dc]
        for campo in fields(dc):
            aba, indice = posicoes.get(campo.name, (None, None))
            dedicadas = sorted(set(flags.get(campo.name, [])))
            registros.append({
                "field": campo.name,
                "dataclass": nome_dc,
                "type": _tipo(campo),
                "default": _padrao(campo),
                "bemt_file": arquivo,
                "cli_flags": dedicadas,
                "cli_set": f"--set {namespace}.{campo.name}" if namespace else None,
                "tab": aba,
                "screen_index": indice,
            })
    registros.sort(key=lambda r: (r["tab"] is None, r["tab"] or "",
                                  r["screen_index"] if r["screen_index"] is not None else 999,
                                  r["field"]))
    return registros


def _imprimir(registros: list) -> None:
    larg = max(len(r["field"]) for r in registros)
    aba_atual = "\0"
    for r in registros:
        if r["tab"] != aba_atual:
            aba_atual = r["tab"]
            print(f"\n=== {aba_atual or 'not on screen (popup, table or internal)'} ===")
        cli = ", ".join(r["cli_flags"]) or (r["cli_set"] or "-")
        print(f"  {r['field']:<{larg}}  {r['dataclass']:<18} "
              f"{r['default']:<14} {r['bemt_file']:<28} {cli}")
    sem_cli = [r["field"] for r in registros if not r["cli_flags"] and not r["cli_set"]]
    print(f"\n{len(registros)} fields; {len(sem_cli)} with no CLI path: {sem_cli}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    como_json = DEFAULT_JSON or "--json" in argv
    registros = coletar()
    if como_json:
        print(json.dumps(registros, indent=1, ensure_ascii=False))
    else:
        _imprimir(registros)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
