@echo off
REM Publish script for quanta-lang package
REM This script builds and uploads the package to PyPI or TestPyPI

setlocal enabledelayedexpansion

echo ========================================
echo   Quanta Language - Package Publisher
echo ========================================
echo.

REM Clean previous builds
echo Cleaning previous builds...
if exist dist rmdir /s /q dist 2>nul
if exist build rmdir /s /q build 2>nul
for /d %%d in (*.egg-info) do rmdir /s /q "%%d" 2>nul
echo Clean complete.
echo.

REM Install build tools if not already installed
echo Installing/upgrading build tools...
python -m pip install --upgrade build twine --quiet
if errorlevel 1 (
    echo Failed to install build tools!
    pause
    exit /b 1
)
echo.

REM Build the package
echo Building wheel and source distribution...
python -m build
if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Build successful! Files created in dist/
dir /b dist
echo.

REM Ask which repository to publish to
:select_repo
echo Select repository to publish to:
echo   1. TestPyPI (for testing)
echo   2. PyPI (production)
set /p repo_choice="Enter choice (1 or 2): "

if "%repo_choice%"=="1" (
    set REPO_URL=--repository testpypi
    set REPO_NAME=TestPyPI
    set REPO_URL_FULL=https://test.pypi.org/legacy/
) else if "%repo_choice%"=="2" (
    set REPO_URL=
    set REPO_NAME=PyPI
    set REPO_URL_FULL=https://upload.pypi.org/legacy/
) else (
    echo Invalid choice. Please enter 1 or 2.
    echo.
    goto select_repo
)

echo.
echo You selected: %REPO_NAME%
echo.

REM Check for token file, otherwise ask for credentials
echo ========================================
echo   Credentials for %REPO_NAME%
echo ========================================
echo.

if exist "ignore\token.txt" (
    echo Reading API token from ignore\token.txt...
    REM Validate token file exists and is valid (Python script will handle reading)
    python -c "import sys, os; token=open('ignore/token.txt').read().strip(); sys.exit(0 if token and token.startswith('pypi-') else 1)" >nul 2>nul
    if errorlevel 1 (
        echo Warning: Token file exists but is empty or invalid!
        echo.
        goto ask_token
    )
    REM Set a dummy value for api_token (actual token reading happens in upload_with_token.py)
    set "api_token=from_file"
    echo Token file found and validated.
    echo.
) else (
    :ask_token
    echo PyPI now requires API tokens (username/password no longer supported)
    echo.
    echo To get an API token:
    echo   - PyPI: https://pypi.org/manage/account/token/
    echo   - TestPyPI: https://test.pypi.org/manage/account/token/
    echo.
    echo Enter your API token (starts with pypi-):
    set /p api_token="API Token: "
    if "!api_token!"=="" (
        echo API Token cannot be empty!
        pause
        exit /b 1
    )
)

REM For API tokens, username must be __token__
REM Note: Token is read directly by upload_with_token.py to avoid batch expansion issues
set pypi_username=__token__

echo.
echo ========================================
echo   Publishing to %REPO_NAME%
echo ========================================
echo.

REM Retry loop
set MAX_RETRIES=3
set RETRY_COUNT=0

:retry_upload
set /a RETRY_COUNT+=1
echo Attempt %RETRY_COUNT% of %MAX_RETRIES%...

REM Upload using twine with API token and --skip-existing to handle existing files
echo Uploading to %REPO_NAME%...
REM Use Python script to pass token to twine to avoid batch expansion issues with special characters
python upload_with_token.py %REPO_URL% > upload_output.txt 2>&1
set UPLOAD_ERROR=!errorlevel!

REM Check output for specific error messages
findstr /C:"File already exists" upload_output.txt >nul
if not errorlevel 1 (
    set IS_FILE_EXISTS=1
) else (
    set IS_FILE_EXISTS=0
)

REM Display the output
type upload_output.txt
del upload_output.txt

if !UPLOAD_ERROR! neq 0 (
    echo.
    echo Upload attempt %RETRY_COUNT% failed!
    
    if !IS_FILE_EXISTS! equ 1 (
        echo.
        echo ========================================
        echo   File Already Exists
        echo ========================================
        echo.
        echo The package version already exists on %REPO_NAME%.
        echo PyPI does not allow overwriting existing files.
        echo.
        echo Current version in pyproject.toml:
        findstr /C:"version" pyproject.toml
        echo.
        echo.
        echo Would you like to bump the version and retry?
        echo   1. Bump patch version (0.1.0 -^> 0.1.1)
        echo   2. Bump minor version (0.1.0 -^> 0.2.0)
        echo   3. Bump major version (0.1.0 -^> 1.0.0)
        echo   4. Cancel and exit
        set /p bump_choice="Enter choice (1-4): "
        
        if "!bump_choice!"=="4" (
            echo.
            echo Cancelled. Exiting...
            pause
            exit /b 1
        )
        
        if "!bump_choice!"=="1" (
            call :bump_version patch
            set SHOULD_REBUILD=1
        ) else if "!bump_choice!"=="2" (
            call :bump_version minor
            set SHOULD_REBUILD=1
        ) else if "!bump_choice!"=="3" (
            call :bump_version major
            set SHOULD_REBUILD=1
        ) else (
            echo Invalid choice. Exiting...
            pause
            exit /b 1
        )
        
        if !SHOULD_REBUILD! equ 1 (
            echo.
            echo Rebuilding with new version...
            REM Clean and rebuild
            if exist dist rmdir /s /q dist 2>nul
            if exist build rmdir /s /q build 2>nul
            for /d %%d in (*.egg-info) do rmdir /s /q "%%d" 2>nul
            python -m build
            if errorlevel 1 (
                echo Build failed after version bump!
                pause
                exit /b 1
            )
            echo.
            echo New version built successfully. Retrying upload...
            echo.
            REM Reset retry counter and try again
            set RETRY_COUNT=0
            goto retry_upload
        )
    )
    
    if %RETRY_COUNT% LSS %MAX_RETRIES% (
        echo.
        echo Retrying in 3 seconds...
        timeout /t 3 /nobreak >nul
        echo.
        goto retry_upload
    ) else (
        echo.
        echo ========================================
        echo   Upload Failed After %MAX_RETRIES% Attempts
        echo ========================================
        echo.
        echo Possible issues:
        echo   - Incorrect username or password/token
        echo   - Network connectivity issues
        echo   - Repository server issues
        echo   - File already exists (bump version to update)
        echo.
        echo You can try manually with:
        echo   twine upload %REPO_URL% dist/* --username __token__ --password YOUR_API_TOKEN --skip-existing
        echo.
        pause
        exit /b 1
    )
) else (
    echo.
    echo ========================================
    echo   SUCCESS! Published to %REPO_NAME%
    echo ========================================
    echo.
    echo Note: If files were skipped, they already exist with the same content.
    echo       To publish changes, update the version in pyproject.toml first.
    echo.
    echo Package URL:
    if "%REPO_NAME%"=="TestPyPI" (
        echo   https://test.pypi.org/project/quanta-lang/
    ) else (
        echo   https://pypi.org/project/quanta-lang/
    )
    echo.
    echo You can install it with:
    if "%REPO_NAME%"=="TestPyPI" (
        echo   pip install -i https://test.pypi.org/simple/ quanta-lang
    ) else (
        echo   pip install quanta-lang
    )
    echo.
    pause
    exit /b 0
)

REM Function to bump version in pyproject.toml using Python script
:bump_version
setlocal
set BUMP_TYPE=%~1

REM Use Python script to bump version
python bump_version.py %BUMP_TYPE%
if errorlevel 1 (
    echo Error: Failed to bump version
    endlocal
    exit /b 1
)

endlocal
exit /b 0
