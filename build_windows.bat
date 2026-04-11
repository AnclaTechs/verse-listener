@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHON_ARGS="
if exist "%CD%\.venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%CD%\venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\venv\Scripts\python.exe"

if not defined PYTHON_EXE (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3"
    )
)

if not defined PYTHON_EXE (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    )
)

if not defined PYTHON_EXE (
    echo Could not find a Python interpreter. Install Python 3.10+ or create a local venv first.
    exit /b 1
)

echo Using Python: "%PYTHON_EXE%" %PYTHON_ARGS%

set "BUILD_PYTHON_VERSION="
set "BUILD_PYTHON_VERSION_FILE=%TEMP%\verse_listener_python_version_%RANDOM%%RANDOM%.txt"
call "%PYTHON_EXE%" %PYTHON_ARGS% -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" > "%BUILD_PYTHON_VERSION_FILE%"
if errorlevel 1 goto :cleanup_error
set /p BUILD_PYTHON_VERSION=<"%BUILD_PYTHON_VERSION_FILE%"
del "%BUILD_PYTHON_VERSION_FILE%" >nul 2>nul
if not defined BUILD_PYTHON_VERSION (
    echo Could not determine the build Python version.
    exit /b 1
)

echo Build Python version: %BUILD_PYTHON_VERSION%

call "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade pip
if errorlevel 1 goto :error

call "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r requirements-build.txt
if errorlevel 1 goto :error

call "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r requirements-windows-openai.txt
if errorlevel 1 goto :error

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

set "HELPER_RUNTIME_SOURCE="
if defined VERSE_LISTENER_HELPER_PYTHON_DIR (
    if exist "%VERSE_LISTENER_HELPER_PYTHON_DIR%\python.exe" (
        set "HELPER_RUNTIME_SOURCE=%VERSE_LISTENER_HELPER_PYTHON_DIR%"
    )
)

if not defined HELPER_RUNTIME_SOURCE (
    if exist "%CD%\windows_runtime\python\python.exe" (
        set "HELPER_RUNTIME_SOURCE=%CD%\windows_runtime\python"
    )
)

if not defined HELPER_RUNTIME_SOURCE (
    if exist "%CD%\scripts\prepare_windows_runtime.ps1" (
        echo Preparing helper runtime so target PCs can install add-ons without Python...
        powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\prepare_windows_runtime.ps1" -PythonVersion "%BUILD_PYTHON_VERSION%" -TargetDir "%CD%\windows_runtime\python" -Force
        if errorlevel 1 goto :error
        if exist "%CD%\windows_runtime\python\python.exe" (
            set "HELPER_RUNTIME_SOURCE=%CD%\windows_runtime\python"
        )
    )
)

if not defined HELPER_RUNTIME_SOURCE (
    echo Helper runtime is required for bundled in-app add-on installs, but none was found.
    echo Run scripts\prepare_windows_runtime.ps1 first or set VERSE_LISTENER_HELPER_PYTHON_DIR.
    exit /b 1
)

call "%HELPER_RUNTIME_SOURCE%\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
    echo Helper runtime was found at "%HELPER_RUNTIME_SOURCE%" but pip is not ready.
    echo Rebuild it with scripts\prepare_windows_runtime.ps1 and try again.
    exit /b 1
)

call "%PYTHON_EXE%" %PYTHON_ARGS% -m PyInstaller --noconfirm --clean VerseListener.spec
if errorlevel 1 goto :error

echo Bundling helper Python runtime from "%HELPER_RUNTIME_SOURCE%"
robocopy "%HELPER_RUNTIME_SOURCE%" "dist\VerseListener\runtime\python" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :error

echo.
echo Build complete:
echo   dist\VerseListener\VerseListener.exe
echo   dist\VerseListener\runtime\python\python.exe
exit /b 0

:cleanup_error
del "%BUILD_PYTHON_VERSION_FILE%" >nul 2>nul
echo Could not determine the build Python version.
exit /b 1

:error
del "%BUILD_PYTHON_VERSION_FILE%" >nul 2>nul
echo.
echo Windows build failed.
exit /b 1
