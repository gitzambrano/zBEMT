"""Records the numbers every example project produces, so that a change to
the physics shows up as a diff instead of as silence.

WHY THIS EXISTS
---------------
The suite locks a handful of hand-written values (`CT = 0.027625` and a few
more). Everything else about the engine's OUTPUT was unguarded: a change to
an inflow model, a loss factor or an integration rule could shift every
coefficient of every project by a few percent and no test would notice,
because no test knew what those coefficients were supposed to be.

This script solves every saved case of every project under `projects/` with
the project's own configuration and writes the results to
`tests/data/golden_results.json`. `tests/test_golden_results.py` compares the
live run against that file.

The point is NOT that the recorded numbers are right in an absolute sense --
they are what the code produces today. The point is that changing them has to
be deliberate: the diff of this file is the change to the physics, stated in
the units the user reads.

CHANGING A NUMBER ON PURPOSE
----------------------------
    python tools/golden_snapshot.py

and read the diff before committing it. A one-line physics fix that moves
forty numbers is telling you something.

USAGE
-----
    python tools/golden_snapshot.py            # every project
    python tools/golden_snapshot.py starter_rotor
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from zbemt import api                                        # noqa: E402
from zbemt.models import Project                             # noqa: E402

DEFAULT_PROJECTS_DIR = None          # None means RAIZ / "projects"

DESTINO = RAIZ / "tests" / "data" / "golden_results.json"

#: The summary keys recorded. Deliberately the OUTPUTS a reader of the
#: results table looks at first, not every one of the ninety-odd columns:
#: the `cfg_*` echo repeats the input, and the timings are machine
#: dependent. A key absent from a given run (propeller coefficients on a
#: rotor project) is simply not recorded for it.
CHAVES = (
    "Thrust", "Torque", "Power", "Power_i", "Power_p",
    "CT", "CQ", "CP", "CPi", "CPp", "CH", "CY", "CMx", "CMy", "FM",
    "CT_prop", "CQ_prop", "CP_prop", "eta_prop",
    "Vi", "lambda_i", "lambda_total", "convergence_pct",
)

#: Digits kept. Ten significant digits would turn every platform difference
#: in the last bit of a `numpy` reduction into a test failure; six is far
#: tighter than any physically meaningful change and survives a different
#: BLAS.
DIGITOS = 6


def _arredondar(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return valor
    if valor != valor:                                    # NaN
        return "nan"
    return round(float(valor), DIGITOS)


def coletar_projeto(pasta: Path) -> dict:
    """``{case name: {summary key: value}}`` for one project."""
    projeto: Project = api.open_project(str(pasta))
    registro = {}
    for condicao in projeto.saved_cases:
        resultado = api.run_case(projeto, condicao)
        registro[condicao.name] = {
            chave: _arredondar(resultado.summary[chave])
            for chave in CHAVES if chave in resultado.summary
        }
    return registro


def coletar(pasta_de_projetos: Path | None = None, apenas: str | None = None) -> dict:
    raiz = pasta_de_projetos or DEFAULT_PROJECTS_DIR or (RAIZ / "projects")
    tudo = {}
    for pasta in sorted(Path(raiz).iterdir()):
        if not pasta.is_dir() or (apenas and pasta.name != apenas):
            continue
        tudo[pasta.name] = coletar_projeto(pasta)
    return tudo


def main() -> int:
    apenas = sys.argv[1] if len(sys.argv) > 1 else None
    if apenas:
        apenas = Path(apenas).name
    tudo = coletar(apenas=apenas)
    if apenas and DESTINO.exists():
        completo = json.loads(DESTINO.read_text(encoding="utf-8"))
        completo.update(tudo)
        tudo = completo
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(tudo, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    casos = sum(len(v) for v in tudo.values())
    print(f"golden results written to {DESTINO}")
    print(f"  {len(tudo)} project(s), {casos} case(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
