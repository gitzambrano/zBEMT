@echo off
REM ============================================================
REM  zBEMT - Run all tests, one process per file (avoids the
REM  Windows access-violation crash from Qt/matplotlib teardown
REM  when hundreds of GUI tests share one process).
REM  Double-click this file to run.
REM  This .bat lives INSIDE tests\, next to run_all_tests.py
REM ============================================================

cd /d "%~dp0"

if not exist "run_all_tests.py" (
    echo ERRO: nao encontrei run_all_tests.py aqui: %CD%
    echo Este .bat precisa estar dentro de tests\, ao lado de run_all_tests.py
    pause
    exit /b 1
)

python run_all_tests.py

echo.
pause
