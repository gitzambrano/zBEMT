"""Temporary branch helper for already-queued patch materializers.

Older queued workflows run ``python tools/apply_flight_sign_fix.py`` directly.
That migration had one escaping-level error in two documentation literals.
Python imports ``sitecustomize`` from the script directory before executing the
main script, so repair only those two HTML fragments when that migration is the
entry point. This file is branch scaffolding and is not part of the product
commit promoted to main.
"""
from __future__ import annotations

from pathlib import Path
import sys

if Path(sys.argv[0]).name == "apply_flight_sign_fix.py":
    path = Path(__file__).resolve().parents[1] / "docs" / "documentation.html"
    text = path.read_text(encoding="utf-8")
    pairs = [
        (r"$\alpha_{rotor}=\operatorname{atan2}(V_z,V_x)$",
         r"$\alpha_{rotor}=-\operatorname{atan2}(V_z,V_x)$"),
        (r"$\mu_x=\tan(\alpha_{disk})\,|V_z|/(\Omega R)$",
         r"$\mu_x=-\tan(\alpha_{disk})\,|V_z|/(\Omega R)$"),
    ]
    changed = False
    for old, new in pairs:
        if new in text and old not in text:
            continue
        count = text.count(old)
        if count != 1:
            raise RuntimeError(
                f"documentation replacement cardinality for {old!r}: {count}")
        text = text.replace(old, new)
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
