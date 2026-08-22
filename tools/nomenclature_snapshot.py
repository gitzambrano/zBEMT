"""Regenerates the nomenclature snapshot used by ``tests/test_nomenclature_parity.py``.

Why a snapshot: the rotor/propeller axis nomenclature is produced today by
several independent tables (``api._COLUMN_SYMBOL``,
``viz/plots._SUMMARY_KEY_LABELS``, ``studies.condition_name``,
``gui/widgets.CONDITION_UNITS``). Unifying them into
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


def has_qt() -> bool:
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
        include_gui = has_qt()

    snapshot: dict = {}

    # --- table/report column symbols and tooltips (api.py) ---
    keys = sorted(api._COLUMN_SYMBOL)
    snapshot["summary_symbols"] = {
        mode: {c: list(api.summary_symbol(c, is_propeller=prop)) for c in keys}
        for mode, prop in (("rotor", False), ("propeller", True))
    }
    snapshot["summary_units"] = {c: api._column_unit(c) for c in keys}
    snapshot["primary_columns"] = {
        "rotor": list(nomenclature.primary_order(False)),
        "propeller": list(nomenclature.primary_order(True)),
        "shared": list(api._MAIN_COLUMNS),
    }
    snapshot["suppressed_columns"] = {
        mode: [c for c, q in nomenclature.QUANTITIES.items()
               if not q.alias_of and not q.visible(prop)]
        for mode, prop in (("rotor", False), ("propeller", True))
    }

    # --- plot axis labels (viz/plots.py), in the three render targets ---
    snapshot["axis_labels"] = {
        mode: {
            c: {
                "mathtext": plots._summary_axis_label(c, prop),
                "text": plots.summary_label_text(c, prop),
                "html": plots.summary_label_html(c, prop),
            }
            for c in keys
        }
        for mode, prop in (("rotor", False), ("propeller", True))
    }

    # --- condition names (studies.py) ---
    snapshot["condition_labels"] = {
        mode: [studies.condition_name(v, prop) for v in CONDITION_SAMPLES]
        for mode, prop in (("rotor", False), ("propeller", True))
    }
    snapshot["factorial_slots"] = {
        v: studies._factorial_slot(v) for v in sorted(studies._FACTORIAL_VARIABLES)
    }

    if not include_gui:
        return snapshot

    from zbemt.gui import widgets

    # --- input field units and their engine variables (gui/widgets.py) ---
    snapshot["condition_units"] = {
        f"{slot}/{'propeller' if prop else 'rotor'}": [list(pair) for pair in pairs]
        for (slot, prop), pairs in sorted(
            widgets.CONDITION_UNITS.items(), key=lambda kv: (kv[0][0], kv[0][1])
        )
    }
    snapshot["default_unit"] = {
        f"{slot}/{'propeller' if prop else 'rotor'}": label
        for (slot, prop), label in sorted(
            widgets._DEFAULT_UNIT.items(), key=lambda kv: (kv[0][0], kv[0][1])
        )
    }

    # --- row labels and tooltips for the two slots (gui/common.py) ---
    from zbemt.gui.common import condition_label_and_tooltip
    snapshot["slot_labels"] = {
        f"{slot}/{'propeller' if prop else 'rotor'}":
            list(condition_label_and_tooltip(prop, slot))
        for slot in ("inplane", "axial")
        for prop in (False, True)
    }

    return snapshot


def write(destination: Path = DEFAULT_OUTPUT) -> Path:
    """Writes the snapshot. Requires Qt: the file records EVERY surface, and
    one written without the GUI ones would silently stop checking them."""
    if not has_qt():
        raise SystemExit(
            "nomenclature_snapshot: PyQt6 is required to regenerate the "
            "snapshot -- it records the GUI's field labels too, and a file "
            "written without them would drop those surfaces from the check.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(collect(), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


if __name__ == "__main__":
    path = write()
    print(f"nomenclature snapshot written to {path}")
