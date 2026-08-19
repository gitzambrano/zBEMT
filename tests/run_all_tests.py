"""Run the full zBEMT test suite, one file per process.

Why one process per file: several GUI test files create many matplotlib/Qt
canvases over the course of a session. On Windows, garbage-collecting them
late (after dozens of unrelated tests have piled up in the same process)
has triggered a native "access violation" crash inside matplotlib/Qt --
not a bug in the tests themselves, just a teardown-ordering issue that
running each file as its own process avoids entirely.

Usage:
    python run_all_tests.py            # run everything
    python run_all_tests.py -k airfoil # only files matching "airfoil"
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

# Regex to pull "12 passed, 3 skipped in 4.56s" (or "1 failed, ...") out of
# pytest's own summary line, however many categories it lists.
_SUMMARY_RE = re.compile(
    r"(?P<count>\d+)\s+(?P<kind>passed|failed|error|errors|skipped|xfailed|xpassed)"
)
_SKIP_RE = re.compile(r"^(?P<test>\S+::\S+)\s+SKIPPED\s*(?:\((?P<motivo>.*)\))?", re.MULTILINE)


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

    ok = proc.returncode == 0

    linhas = [l for l in saida_bruta.strip().splitlines() if l.strip()]
    resumo = linhas[-1] if linhas else "(sem saida nenhuma -- processo provavelmente travou/crashou antes de imprimir)"

    if proc.returncode not in (0, 1):
        resumo = (f"codigo de saida {proc.returncode} (0x{proc.returncode & 0xFFFFFFFF:08X}) "
                   f"-- nao e um resultado normal do pytest, provavel crash nativo "
                   f"(access violation / segfault). {resumo}")

    cabecalho = (
        f"comando: {' '.join(cmd)}\n"
        f"codigo de saida: {proc.returncode}\n"
    )
    output = cabecalho + (saida_bruta if saida_bruta.strip() else "(nenhuma saida capturada em stdout/stderr)\n")

    return ok, resumo, output


def main() -> int:
    args = sys.argv[1:]
    filtro = None
    if args and args[0] == "-k" and len(args) > 1:
        filtro = args[1]

    arquivos = sorted(TESTS_DIR.glob("test_*.py"))
    if filtro:
        arquivos = [a for a in arquivos if filtro in a.name]

    if not arquivos:
        print(f"Nenhum arquivo de teste encontrado em {TESTS_DIR}")
        return 1

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
