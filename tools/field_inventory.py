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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Zero-argument run prints the readable table (the IDE "Run" button).
DEFAULT_JSON = False

#: dataclass -> (``--set`` namespace, file under ``inputs/`` that stores it).
#: ``None`` namespace means the field has no ``--set`` path: it is not part of
#: config/airfoil/geom but of the flight condition or the batch, which the CLI
#: reaches through its own flags instead.
ORIGIN = {
    "RotorGeometryDef": ("geom", "geom.bemt"),
    "AirfoilDef": ("airfoil", "airfoil.bemt"),
    "BEMTConfig": ("config", "config.bemt"),
    "FlightCondition": (None, "saved_cases.bemt / batches.bemt"),
    "BatchDefinition": (None, "batches.bemt"),
}


def _input_dataclasses() -> dict:
    from zbemt import models
    from zbemt.bemt import BEMTConfig
    return {
        "RotorGeometryDef": models.RotorGeometryDef,
        "AirfoilDef": models.AirfoilDef,
        "BEMTConfig": BEMTConfig,
        "FlightCondition": models.FlightCondition,
        "BatchDefinition": models.BatchDefinition,
    }


def _default(field) -> str:
    """The default as the documentation should print it."""
    if field.default is not MISSING:
        return repr(field.default)
    if field.default_factory is not MISSING:        # type: ignore[misc]
        try:
            return repr(field.default_factory())    # type: ignore[misc]
        except Exception:
            return "(computed)"
    return "(required)"


def _type_name(field) -> str:
    t = field.type
    return t if isinstance(t, str) else getattr(t, "__name__", str(t))


#: Flags whose target cannot be derived from dest or help text.
#:
#: The flight-condition flags are named by SLOT ("inplane"/"axial"), not by
#: letter, precisely because the letter rotates between rotor and propeller
#: mode -- so no amount of string matching connects `--mu-inplane` to the
#: engine field `mu_x`. See `zbemt/nomenclature.py`.
EXPLICIT_FLAGS = {
    "mu_x": ["--mu-inplane", "--j-inplane", "--v-inplane", "--alpha-disk-deg"],
    "Vz": ["--v-axial", "--j-axial", "--mu-axial", "--alpha-rotor-deg"],
    "collective_deg": ["--collective"],
}

#: Matches that the help-text heuristic gets wrong. `--geom-*` configure the
#: ROTOR geometry, not `AirfoilDef.geometry` (the 2D profile coordinates).
FALSE_POSITIVES = {("geometry", "--geom-file"), ("geometry", "--geom-preset")}


def dedicated_flags() -> dict:
    """{field name: [--flag, ...]} for the flags cli.py exposes by name.

    Derived by asking the real parser for its actions, then matching each
    action to a field. Two signals, in this order: the action's ``dest``
    equals the field name, or the action's help text names the field
    (``BEMTConfig.max_iter``, ``radius_m.``). Anything unmatched simply has
    no dedicated flag, which is the normal case -- ``--set`` covers it.
    """
    from zbemt import cli

    all_fields = set()
    for dc in _input_dataclasses().values():
        all_fields.update(f.name for f in fields(dc))

    found: dict = {name: list(v) for name, v in EXPLICIT_FLAGS.items()}
    parser = cli._build_parser()
    for action in parser._actions:
        if not action.option_strings:
            continue
        options = [o for o in action.option_strings if o.startswith("--")]
        # `--set` names example fields in its own help ("config.Ne=90"); it is
        # the generic escape hatch, never a given field's dedicated flag.
        if not options or action.dest == "set":
            continue
        target = None
        if action.dest in all_fields:
            target = action.dest
        else:
            help_text = action.help or ""
            # longest match first: `relax_schedule` must not lose to `relax`
            for name in sorted(all_fields, key=len, reverse=True):
                if f".{name}" in help_text or help_text.strip().startswith(name):
                    target = name
                    break
        if target:
            found.setdefault(target, []).extend(
                o for o in options if (target, o) not in FALSE_POSITIVES)
    return {k: v for k, v in found.items() if v}


def screen_order() -> dict:
    """{field: (tab, position)} or {} when Qt is unavailable."""
    try:
        import PyQt6  # noqa: F401
    except ModuleNotFoundError:
        return {}
    from field_index import collect_screen_order          # same folder
    position = {}
    for tab, tab_fields in collect_screen_order().items():
        for i, (field_name, _anchor) in enumerate(tab_fields):
            position.setdefault(field_name, (tab, i))
    return position


def collect() -> list:
    """One record per settable field, ready to drive a documentation test."""
    flag_map = dedicated_flags()
    positions = screen_order()
    records = []
    for dc_name, dc in _input_dataclasses().items():
        namespace, bemt_file = ORIGIN[dc_name]
        for field in fields(dc):
            tab, index = positions.get(field.name, (None, None))
            dedicated = sorted(set(flag_map.get(field.name, [])))
            records.append({
                "field": field.name,
                "dataclass": dc_name,
                "type": _type_name(field),
                "default": _default(field),
                "bemt_file": bemt_file,
                "cli_flags": dedicated,
                "cli_set": f"--set {namespace}.{field.name}" if namespace else None,
                "tab": tab,
                "screen_index": index,
            })
    records.sort(key=lambda r: (r["tab"] is None, r["tab"] or "",
                                r["screen_index"] if r["screen_index"] is not None else 999,
                                r["field"]))
    return records


def _print_table(records: list) -> None:
    width = max(len(r["field"]) for r in records)
    current_tab = "\0"
    for r in records:
        if r["tab"] != current_tab:
            current_tab = r["tab"]
            print(f"\n=== {current_tab or 'not on screen (popup, table or internal)'} ===")
        cli = ", ".join(r["cli_flags"]) or (r["cli_set"] or "-")
        print(f"  {r['field']:<{width}}  {r['dataclass']:<18} "
              f"{r['default']:<14} {r['bemt_file']:<28} {cli}")
    without_cli = [r["field"] for r in records if not r["cli_flags"] and not r["cli_set"]]
    print(f"\n{len(records)} fields; {len(without_cli)} with no CLI path: {without_cli}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = DEFAULT_JSON or "--json" in argv
    records = collect()
    if as_json:
        print(json.dumps(records, indent=1, ensure_ascii=False))
    else:
        _print_table(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
