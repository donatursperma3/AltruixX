@echo off
REM =============================================================================
REM start.bat - Windows Native Launcher for Altruix Userbot
REM For users without Git Bash/MSYS
REM =============================================================================

setlocal enabledelayedexpansion

REM ANSI Color Codes (Windows 10+)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "MAGENTA=[95m"
set "CYAN=[96m"
set "WHITE=[97m"
set "NC=[0m"

REM =============================================================================
REM Display Banner
REM =============================================================================
echo.
echo %CYAN%╔═════════════════════════════════════════════════════════╗%NC%
echo %CYAN%║                                                         ║%NC%
echo %CYAN%║        🚀 ALTROID-X USERBOT - WINDOWS LAUNCHER          ║%NC%
echo %CYAN%║                                                         ║%NC%
echo %CYAN%╔═════════════════════════════════════════════════════════╝%NC%
echo.
echo %BLUE%💻 Platform Detected: WINDOWS (Native - CMD/PowerShell)%NC%
echo %WHITE%   Environment: Windows%NC%
echo %WHITE%   Virtual Env: venv%NC%
echo.

REM =============================================================================
REM Detect Python
REM =============================================================================
set "PYTHON_CMD=python"

where python >nul 2>&1
if %errorlevel% neq 0 (
    where python3 >nul 2>&1
    if %errorlevel% neq 0 (
        echo %RED%❌ Error: Python not found!%NC%
        echo %YELLOW%Please install Python from https://www.python.org/%NC%
        pause
        exit /b 1
    ) else (
        set "PYTHON_CMD=python3"
    )
)

echo %CYAN%🐍 Python Command: %PYTHON_CMD%%NC%
echo.

REM =============================================================================
REM Create Virtual Environment
REM =============================================================================
if not exist "venv\" (
    echo %YELLOW%⏳ Creating virtual environment: venv%NC%
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo %RED%❌ Failed to create virtual environment!%NC%
        pause
        exit /b 1
    )
    echo %GREEN%✅ Virtual environment created!%NC%
) else (
    echo %GREEN%✅ Virtual environment found: venv%NC%
)

set "VENV_PYTHON=venv\Scripts\python.exe"
echo %CYAN%🐍 Using Python: %VENV_PYTHON%%NC%
echo.

REM =============================================================================
REM Install Dependencies
REM =============================================================================
echo %YELLOW%📦 Installing/Updating dependencies...%NC%
%VENV_PYTHON% -m pip install --upgrade pip --quiet
%VENV_PYTHON% -m pip install -r requirements.txt --quiet
echo %GREEN%✅ Dependencies installed!%NC%
echo.

REM =============================================================================
REM Load Environment Variables from .env
REM =============================================================================
if exist ".env" (
    echo %YELLOW%⏳ Loading environment variables from .env...%NC%
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            if not "!line!"=="" (
                set "%%a=%%b"
            )
        )
    )
    echo %GREEN%✅ Environment variables loaded!%NC%
) else (
    echo %YELLOW%⚠️  Warning: .env file not found!%NC%
    echo %YELLOW%   Copy .env.sample to .env and configure it.%NC%
)
echo.

REM =============================================================================
REM Clean Up Existing Processes
REM =============================================================================
echo %YELLOW%🧹 Cleaning up existing Python processes...%NC%
taskkill /F /IM python.exe /T >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN%✅ Cleanup complete!%NC%
    echo %YELLOW%⏳ Waiting 3 seconds for file handles to be released...%NC%
    timeout /t 3 /nobreak >nul
) else (
    echo %CYAN%ℹ️  No existing processes found.%NC%
)
echo.

REM =============================================================================
REM Launch the Bot
REM =============================================================================
echo %GREEN%╔══════════════════════════════════════════════════════════╗%NC%
echo %GREEN%║                                                          ║%NC%
echo %GREEN%║               🚀 STARTING ALTROID-X USERBOT              ║%NC%
echo %GREEN%║                                                          ║%NC%
echo %GREEN%╚══════════════════════════════════════════════════════════╝%NC%
echo.
echo %CYAN%Platform: Windows (Native)%NC%
echo %CYAN%Python: %VENV_PYTHON%%NC%
echo %CYAN%Working Directory: %CD%%NC%
echo.
echo %YELLOW%⏳ Launching bot...%NC%
echo.

REM Run the bot
%VENV_PYTHON% -m Main

REM If bot exits, pause to see error messages
if %errorlevel% neq 0 (
    echo.
    echo %RED%❌ Bot exited with error code: %errorlevel%%NC%
    pause
)
