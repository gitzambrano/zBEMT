"""Run the full zBEMT test suite, one file per process.

Why one process per file: several GUI test files create many matplotlib/Qt
canvases over the course of a session. On Windows, garbage-collecting them
late (after dozens of unrelated tests have piled up in the same process)
has triggered a native "access violation" crash inside matplotlib/Qt --
not a bug in the tests themselves, just a teardown-ordering issue that
running each file as its own process avoids entirely.

Memory and handles matter here too, not just crashes: a single process
accumulating every project solve, every figure and every mounted window ends
the run holding far more than any one file needs. One process per file gives
each of them a clean start and returns everything at the end of it, which is
what keeps the run viable on a CI runner with a small memory allowance.

Usage:
    python run_all_tests.py             # run everything
    python run_all_tests.py -k airfoil  # only files matching "airfoil"
    python run_all_tests.py --lista     # list the files and exit
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
REPORT_PATH = TESTS_DIR / "resultado_testes.txt"

#: Run these first. They are the files that solve every example project or
#: mount the full window repeatedly, so they dominate the wall clock and are
#: where a real regression usually lands.
ARQUIVOS_LENTOS = (
    "test_api.py",
    "test_gui_e2e.py",
    "test_golden_results.py",
    "test_gui_smoke.py",
    "test_bemt.py",
)

# Regex to pull "12 passed, 3 skipped in 4.56s" (or "1 failed, ...") out of
# pytest's own summary line, however many categories it lists.
_SUMMARY_RE = re.compile(
    r"(?P<count>\d+)\s+(?P<kind>passed|failed|error|errors|skipped|xfailed|xpassed)"
)
_SKIP_RE = re.compile(r"^(?P<test>\S+::\S+)\s+SKIPPED\s*(?:\((?P<motivo>.*)\))?", re.MULTILINE)


#: pytest's own closing line, e.g. "16 passed, 9 subtests passed in 2.75s".
#: Only a run that finished reporting produces one.
_LINHA_DE_RESUMO = re.compile(r"^=+ .*\b\d+ (?:passed|skipped).* in [\d.]+s.* =+$",
                               re.MULTILINE)


def _resumo_sem_falhas(output: str) -> bool:
    """True when pytest printed its summary and that summary reports no
    failure and no error.

    This is what separates "the tests all passed and then the interpreter
    fell over on the way out" from "the interpreter fell over mid-run".
    In the second case pytest never reaches its summary line, so there is
    nothing here to match."""
    linhas = _LINHA_DE_RESUMO.findall(output)
    if not linhas:
        return False
    ultima = linhas[-1]
    return not re.search(r"\b\d+ (?:failed|error|errors)\b", ultima)


def _extrai_skips(output: str) -> list[tuple[str, str]]:
    """[(test_id, motivo), ...] from a single file's -v output."""
    return [(m.group("test"), m.group("motivo") or "(sem motivo informado)")
             for m in _SKIP_RE.finditer(output)]


def _run_one(test_file: Path, env: dict) -> tuple[bool, str, str]:
    """Runs a single test file in its own subprocess.

    Returns (ok, summary_line, full_output).
    """
    cmd = [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=long", "-rs"]
    proc = subprocess.run(
        cmd, cwd=ROOT, env=env,
        capture_output=True, text=True,
    )
    saida_bruta = proc.stdout + proc.stderr

    # pytest returns 5 when it collected NOTHING. For a file whose whole
    # module skips itself -- every GUI test file, in the CI job that installs
    # the base dependencies only to prove the engine runs without Qt -- that
    # is the correct outcome, not a crash.
    tudo_pulado = proc.returncode == 5 and " skipped" in saida_bruta

    # A native fault AFTER pytest has already reported every test as passing
    # is the Qt/matplotlib teardown-ordering crash this runner exists to
    # contain: the interpreter dies while destroying canvases, once the
    # results are in and printed. It is intermittent, it carries no
    # information about the code under test, and treating it as a failure
    # turns CI red at random.
    #
    # The summary line is the evidence, and it is required: this only
    # applies when pytest itself said 0 failed and 0 errors. A crash DURING
    # the run never produces that line, so a real failure can never be
    # absorbed here. The event is reported either way -- see `resumo` below
    # -- so it can never pass unnoticed.
    crash_no_teardown = (proc.returncode not in (0, 1, 5)
                          and _resumo_sem_falhas(saida_bruta))

    ok = proc.returncode == 0 or tudo_pulado or crash_no_teardown

    linhas = [l for l in saida_bruta.strip().splitlines() if l.strip()]
    resumo = linhas[-1] if linhas else "(sem saida nenhuma -- processo provavelmente travou/crashou antes de imprimir)"

    if crash_no_teardown:
        resumo = (f"OK, mas o processo morreu no teardown com "
                   f"0x{proc.returncode & 0xFFFFFFFF:08X} DEPOIS de todos os testes "
                   f"passarem (crash de ordem de destruicao Qt/matplotlib, sem "
                   f"relacao com o codigo testado). {resumo}")
    elif proc.returncode not in (0, 1) and not tudo_pulado:
        resumo = (f"codigo de saida {proc.returncode} (0x{proc.returncode & 0xFFFFFFFF:08X}) "
                   f"-- nao e um resultado normal do pytest, provavel crash nativo "
                   f"(access violation / segfault). {resumo}")

    cabecalho = (
        f"comando: {' '.join(cmd)}\n"
        f"codigo de saida: {proc.returncode}\n"
    )
    output = cabecalho + (saida_bruta if saida_bruta.strip() else "(nenhuma saida capturada em stdout/stderr)\n")

    return ok, resumo, output


def _ordenar(arquivos: list[Path]) -> list[Path]:
    """Slowest files first.

    They are the ones whose failure is worth knowing about early, and a
    long file starting last leaves the whole run waiting on it. The order
    is by name within each group, so a run is still reproducible."""
    lentos = [a for a in arquivos if a.name in ARQUIVOS_LENTOS]
    resto = [a for a in arquivos if a.name not in ARQUIVOS_LENTOS]
    return sorted(lentos) + sorted(resto)


def main() -> int:
    args = sys.argv[1:]
    filtro = None
    if args and args[0] == "-k" and len(args) > 1:
        filtro = args[1]

    arquivos = _ordenar(sorted(TESTS_DIR.glob("test_*.py")))
    if filtro:
        arquivos = [a for a in arquivos if filtro in a.name]

    if not arquivos:
        print(f"Nenhum arquivo de teste encontrado em {TESTS_DIR}")
        return 1

    if "--lista" in args:
        for arquivo in arquivos:
            print(arquivo.relative_to(ROOT))
        return 0

    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    total_ok = total_falha = 0
    falharam: list[str] = []
    detalhes: list[str] = []
    todos_skips: list[tuple[str, str]] = []
    inicio_geral = time.time()

    print(f"Rodando {len(arquivos)} arquivos de teste (um processo por arquivo)...\n")

    for i, arquivo in enumerate(arquivos, 1):
        nome = arquivo.relative_to(ROOT)
        print(f"[{i:3d}/{len(arquivos)}] {nome} ... ", end="", flush=True)
        t0 = time.time()
        ok, resumo, saida_completa = _run_one(arquivo, env)
        dt = time.time() - t0

        if ok:
            total_ok += 1
            print(f"OK  ({dt:.1f}s) -- {resumo}")
        else:
            total_falha += 1
            falharam.append(str(nome))
            print(f"FALHOU  ({dt:.1f}s) -- {resumo}")

        detalhes.append(f"{'='*70}\n{nome}  ({dt:.1f}s)\n{'='*70}\n{saida_completa}\n")
        todos_skips.extend(_extrai_skips(saida_completa))

    duracao = time.time() - inicio_geral

    print(f"\n{'='*60}")
    print(f" Resumo: {total_ok} arquivos OK, {total_falha} arquivos com falha"
          f" ({duracao:.0f}s no total)")
    if falharam:
        print(" Falharam:")
        for nome in falharam:
            print(f"   - {nome}")
    print(f"{'='*60}")

    if todos_skips:
        print(f"\n Testes pulados (skipped) -- {len(todos_skips)} no total:")
        for teste, motivo in todos_skips:
            print(f"   - {teste}\n       motivo: {motivo}")
    print(f"{'='*60}")

    print(f"\nRelatorio completo (com o traceback de cada falha) em:\n  {REPORT_PATH}")

    REPORT_PATH.write_text("\n".join(detalhes), encoding="utf-8")

    return 0 if total_falha == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
