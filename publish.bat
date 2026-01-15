@echo off
REM Publish script for quanta-lang package
REM This script builds and uploads the package to PyPI

echo Building quanta-lang package...

REM Clean previous builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist *.egg-info rmdir /s /q *.egg-info

REM Install build tools if not already installed
python -m pip install --upgrade build twine

REM Build the package
echo.
echo Building wheel and source distribution...
python -m build

if errorlevel 1 (
    echo Build failed!
    exit /b 1
)

echo.
echo Build successful! Files created in dist/
echo.
echo To upload to PyPI, run:
echo   twine upload dist/*
echo.
echo To upload to Test PyPI first, run:
echo   twine upload --repository testpypi dist/*
echo.

REM Ask if user wants to upload now
set /p upload="Upload to PyPI now? (y/n): "
if /i "%upload%"=="y" (
    echo.
    echo Uploading to PyPI...
    twine upload dist/*
    if errorlevel 1 (
        echo Upload failed!
        exit /b 1
    )
    echo.
    echo Upload successful!
) else (
    echo.
    echo Skipping upload. Run 'twine upload dist/*' manually when ready.
)

pause
