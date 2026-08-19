"""Regenerates the nomenclature snapshot used by ``tests/test_nomenclature_parity.py``.

Why a snapshot: the rotor/propeller axis nomenclature is produced today by
several independent tables (``api._SIMBOLO_DE_COLUNA``,
``viz/plots._SUMMARY_KEY_LABELS``, ``studies._SIMBOLO_DE_VARIAVEL``,
``gui/widgets.UNIDADES_DE_CONDICAO``). Unifying them into
``zbemt/nomenclature.py`` must not silently change what the user reads, and
"must not change" is only checkable against a record of what it says TODAY.

The snapshot is therefore the oracle of the unification: after each step the
test compares the live output against this file, and any difference has to be
a deliberate, reviewed change to the file -- visible as a diff in the commit,
not as a label that quietly turned into something else.

    python tools/nomenclature_snapshot.py

Runs with zero arguments; ``DEFAULT_OUTPUT`` below is the file it writes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: Written when the script runs with no arguments.
DEFAULT_OUTPUT = ROOT / "tests" / "data" / "nomenclature_snapshot.json"

#: Value dictionaries fed to the condition-naming function. Chosen to cover
#: both slots, both angle conventions and the collective/rpm extras, so a
#: change in either mode's letters shows up here.
CONDITION_SAMPLES = [
    {"mu_x": 0.1},
    {"mu_x": 0.1, "alpha_deg": -10.0},
    {"J_x": 0.8, "alpha_disk": 2.0},
    {"mu_z": 0.05, "J_z": 0.16},
    {"Vx": 30.0, "Vz": 65.0},
    {"mu_x": 0.0, "collective_deg": 8.0, "rpm": 600.0},
]


#: Surfaces that live in the GUI layer and therefore need Qt. The engine and
#: CLI run without it on purpose (a batch on a headless server must not need
#: Qt), so on such a machine these are skipped rather than failing the run --
#: the same way every GUI test skips itself.
GUI_SURFACES = ("condition_units", "default_unit", "slot_labels")


def tem_qt() -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec("PyQt6") is not None
    except ModuleNotFoundError:
        return False


def collect(include_gui: bool = None) -> dict:
    """Every axis-nomenclature string the application can currently produce,
    in both modes, keyed so a diff points at the exact surface that moved.

    ``include_gui`` defaults to "whenever Qt is importable"; the GUI surfaces
    are simply absent from the result otherwise."""
    from zbemt import api, nomenclature, studies
    from zbemt.viz import plots

    if include_gui is None:
        include_gui = tem_qt()

    instantaneo: dict = {}

    # --- table/report column symbols and tooltips (api.py) ---
    chaves = sorted(api._SIMBOLO_DE_COLUNA)
    instantaneo["summary_symbols"] = {
        modo: {c: list(api.summary_symbol(c, is_propeller=prop)) for c in chaves}
        for modo, prop in (("rotor", False), ("propeller", True))
    }
    instantaneo["summary_units"] = {c: api._unidade_de_coluna(c) for c in chaves}
    instantaneo["primary_columns"] = {
        "rotor": list(nomenclature.primary_order(False)),
        "propeller": list(nomenclature.primary_order(True)),
        "shared": list(api._COLUNAS_PRINCIPAIS),
    }
    instantaneo["suppressed_columns"] = {
        modo: [c for c, q in nomenclature.QUANTITIES.items()
               if not q.alias_of and not q.visible(prop)]
        for modo, prop in (("rotor", False), ("propeller", True))
    }

    # --- plot axis labels (viz/plots.py), in the three render targets ---
    instantaneo["axis_labels"] = {
        modo: {
            c: {
                "mathtext": plots._summary_axis_label(c, prop),
                "text": plots.rotulo_de_summary_em_texto(c, prop),
                "html": plots.rotulo_de_summary_em_html(c, prop),
            }
            for c in chaves
        }
        for modo, prop in (("rotor", False), ("propeller", True))
    }

    # --- condition names (studies.py) ---
    instantaneo["condition_labels"] = {
        modo: [studies.nome_de_condicao(v, prop) for v in CONDITION_SAMPLES]
        for modo, prop in (("rotor", False), ("propeller", True))
    }
    instantaneo["factorial_slots"] = {
        v: studies._factorial_slot(v) for v in sorted(studies._FACTORIAL_VARIABLES)
    }

    if not include_gui:
        return instantaneo

    from zbemt.gui import widgets

    # --- input field units and their engine variables (gui/widgets.py) ---
    instantaneo["condition_units"] = {
        f"{slot}/{'propeller' if prop else 'rotor'}": [list(par) for par in pares]
        for (slot, prop), pares in sorted(
            widgets.UNIDADES_DE_CONDICAO.items(), key=lambda kv: (kv[0][0], kv[0][1])
        )
    }
    instantaneo["default_unit"] = {
        f"{slot}/{'propeller' if prop else 'rotor'}": rotulo
        for (slot, prop), rotulo in sorted(
            widgets._UNIDADE_PADRAO.items(), key=lambda kv: (kv[0][0], kv[0][1])
        )
    }

    # --- row labels and tooltips for the two slots (gui/common.py) ---
    from zbemt.gui.common import rotulo_e_dica_de_condicao
    instantaneo["slot_labels"] = {
        f"{slot}/{'propeller' if prop else 'rotor'}":
            list(rotulo_e_dica_de_condicao(prop, slot))
        for slot in ("inplane", "axial")
        for prop in (False, True)
    }

    return instantaneo


def write(destino: Path = DEFAULT_OUTPUT) -> Path:
    """Writes the snapshot. Requires Qt: the file records EVERY surface, and
    one written without the GUI ones would silently stop checking them."""
    if not tem_qt():
        raise SystemExit(
            "nomenclature_snapshot: PyQt6 is required to regenerate the "
            "snapshot -- it records the GUI's field labels too, and a file "
            "written without them would drop those surfaces from the check.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(collect(), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destino


if __name__ == "__main__":
    caminho = write()
    print(f"nomenclature snapshot written to {caminho}")
