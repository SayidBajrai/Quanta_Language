@echo off
setlocal enabledelayedexpansion
REM Test script for Quanta Language (pytest suite)
cd /d "%~dp0"

echo ========================================
echo   Quanta Language Test Suite
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher
    pause
    exit /b 1
)

python -c "import quanta" >nul 2>&1
if errorlevel 1 (
    echo quanta not installed; using src\ on PYTHONPATH
    set "PYTHONPATH=%~dp0src"
) else (
    echo Using installed quanta package
)

echo.
echo Running pytest...
echo   - 252 tests covering the full compiler pipeline
echo   - lexer, parser, AST, semantic analysis
echo   - lowering to OpenQASM 3 (flat and structured)
echo   - numeric types, qint operator overloading
echo   - quantum arithmetic simulation (QAdd/QSub/QMult/QDiv/QMod)
echo   - fancy indexing and tensor algebra
echo   - function overloading and wildcard types
echo   - print formatting with f-string specifiers
echo   - reserved name validation
echo   - Grover's algorithm, Fidelity metric
echo.

python -m pytest tests\ -v --tb=short
set TEST_RESULT=%errorlevel%

echo.
if %TEST_RESULT% equ 0 (
    echo All tests passed.
) else (
    echo Tests FAILED.
)

pause
exit /b %TEST_RESULT%
