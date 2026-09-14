"""Fast regression smoke test suite for zBEMT.

Runs core sanity checks in under 15 seconds:
1. Validates all versioned project configurations.
2. Solves a hover condition and a forward flight condition with the BEMT solver.
3. Tests the public CLI validation entrypoint.
4. Verifies repository instruction parity (CLAUDE.md and AGENTS.md).
5. Instantiates the main GUI window in headless offscreen mode.

Usage:
    python tests/smoke_test.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _check(name: str, fn) -> bool:
    print(f"  [..] {name} ... ", end="", flush=True)
    t0 = time.time()
    try:
        fn()
        dt = time.time() - t0
        print(f"OK ({dt:.2f}s)")
        return True
    except Exception as exc:
        dt = time.time() - t0
        print(f"FAILED ({dt:.2f}s): {exc}")
        return False


def test_instruction_parity():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").split("\n")[1:]
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8").split("\n")[1:]
    if "\n".join(agents) != "\n".join(claude):
        raise RuntimeError("CLAUDE.md and AGENTS.md instruction bodies differ")


def test_project_configs():
    from zbemt.api import open_project
    from zbemt.paths import projects_root
    from zbemt.validation import validate_project

    root = projects_root()
    for item in sorted(root.iterdir()):
        if item.is_dir() and (item / "meta.bemt").exists():
            project = open_project(item)
            issues = validate_project(project)
            errors = [i for i in issues if i.severity == "error"]
            if errors:
                raise RuntimeError(f"{item.name} has validation errors: {errors}")


def test_physics_solve():
    from zbemt.api import open_project, run_case
    from zbemt.models import FlightCondition
    from zbemt.paths import projects_root

    root = projects_root()
    # Test starter rotor in hover
    rotor_proj = open_project(root / "starter_rotor")
    res_hover = run_case(rotor_proj, FlightCondition(name="hover", mu_x=0.0, collective_deg=8.0, rpm=600.0))
    if res_hover.summary.get("convergence_pct", 0.0) < 99.0 or float(res_hover.summary.get("Thrust", 0.0)) <= 0.0:
        raise RuntimeError("Hover solve did not converge with positive thrust")

    # Test starter propeller in cruise
    prop_proj = open_project(root / "starter_propeller")
    res_prop = run_case(prop_proj, FlightCondition(name="cruise", mu_x=0.2, collective_deg=18.0, rpm=2200.0))
    if res_prop.summary.get("convergence_pct", 0.0) < 99.0:
        raise RuntimeError("Propeller cruise solve did not converge")


def test_cli_entrypoint():
    cmd = [
        sys.executable, "-m", "zbemt.cli",
        "--project", "projects/starter_rotor",
        "--rpm", "600",
        "--validate-only",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"CLI exit {proc.returncode}: {proc.stderr}")


def test_gui_initialization():
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        # Pass silently in environments without Qt
        return

    app = QApplication.instance() or QApplication([])
    from zbemt.gui.app import MainWindow
    window = MainWindow()
    window.show()
    for _ in range(5):
        app.processEvents()
    window.hide()


def main() -> int:
    print("=" * 60)
    print(" zBEMT Fast Smoke Test")
    print("=" * 60)

    checks = [
        ("Instruction parity (AGENTS.md / CLAUDE.md)", test_instruction_parity),
        ("Project configurations validation", test_project_configs),
        ("Core BEMT physics solve (hover and cruise)", test_physics_solve),
        ("CLI validate-only entrypoint", test_cli_entrypoint),
        ("Headless GUI instantiation", test_gui_initialization),
    ]

    passed = 0
    t_start = time.time()
    for name, fn in checks:
        if _check(name, fn):
            passed += 1

    total = len(checks)
    duration = time.time() - t_start
    print("=" * 60)
    print(f" Result: {passed}/{total} smoke checks passed ({duration:.2f}s)")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
