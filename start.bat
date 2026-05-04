@echo off
REM =============================================================================
REM start.bat - Windows Native Launcher for Altruix Userbot
REM For users without Git Bash/MSYS
REM =============================================================================

setlocal enabledelayedexpansion
chcp 65001 >nul

REM ANSI Color Codes (Windows 10+)
for /F "delims=#" %%a in ('"prompt #$E# & for %%b in (1) do rem"') do set "ESC=%%a"
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "BLUE=%ESC%[94m"
set "MAGENTA=%ESC%[95m"
set "CYAN=%ESC%[96m"
set "WHITE=%ESC%[97m"
set "NC=%ESC%[0m"

REM Premium Colors (Matched with Python Core)
set "TS_COLOR=%ESC%[97;48;5;141m"
set "TAG_COLOR=%ESC%[97;48;2;69;104;130m"
set "DEBUG_COLOR=%ESC%[97;46m"

REM =============================================================================
REM Display Banner
REM =============================================================================
echo.
call :log_msg "%CYAN%╔═══════════════════════════════════════════╗"
call :log_msg "%CYAN%║       🚀 ALTROID-X - WINDOWS LAUNCHER     ║"
call :log_msg "%CYAN%╚═══════════════════════════════════════════╝"
echo.
call :log_msg "%BLUE%💻 Platform Detected: WINDOWS (Native - CMD/PowerShell)"
call :log_msg "%WHITE%   Environment: Windows"
call :log_msg "%WHITE%   Virtual Env: venv"
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

call :log_msg "%CYAN%🐍 Python Command: %PYTHON_CMD%"
echo.

REM =============================================================================
REM Create Virtual Environment
REM =============================================================================
if not exist "venv\" (
    call :log_msg "%YELLOW%⏳ Creating virtual environment: venv"
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        call :log_msg "%RED%❌ Failed to create virtual environment!"
        pause
        exit /b 1
    )
    call :log_msg "%GREEN%✅ Virtual environment created!"
) else (
    call :log_msg "%GREEN%✅ Virtual environment found: venv"
)

set "VENV_PYTHON=venv\Scripts\python.exe"
call :log_msg "%CYAN%🐍 Using Python: %VENV_PYTHON%"
echo.

REM =============================================================================
REM Install Dependencies
REM =============================================================================
call :log_msg "%YELLOW%📦 Installing/Updating dependencies..."
call :log_msg "%YELLOW%⏳ This process installs 60+ libraries and may take several minutes. Please do not close the terminal..."
%VENV_PYTHON% smart_install.py
echo.

REM =============================================================================
REM Load Environment Variables from .env
REM =============================================================================
if exist ".env" (
    call :log_msg "%YELLOW%⏳ Loading environment variables from .env..."
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            if not "!line!"=="" (
                set "%%a=%%b"
            )
        )
    )
    call :log_msg "%GREEN%✅ Environment variables loaded!"
) else (
    call :log_msg "%YELLOW%⚠️  Warning: .env file not found!"
    echo %YELLOW%   Copy .env.sample to .env and configure it.%NC%
)
echo.

REM =============================================================================
REM Clean Up Existing Processes (DISABLED - Allows Multi-Instance)
REM =============================================================================
call :log_msg "%CYAN%ℹ️  Multi-instance support enabled (Cleanup disabled)."
echo.

REM =============================================================================
REM Launch the Bot
REM =============================================================================
call :log_msg "%GREEN%╔═══════════════════════════════════════════╗"
call :log_msg "%GREEN%║        🚀 STARTING ALTROID-X BOT          ║"
call :log_msg "%GREEN%╚═══════════════════════════════════════════╝"
echo.
call :log_msg "%CYAN%Platform: Windows (Native)"
call :log_msg "%CYAN%Python: %VENV_PYTHON%"
echo.
call :log_msg "%YELLOW%⏳ Launching Altroid-X engine..."
echo.

REM Run the bot
%VENV_PYTHON% -m Main

REM If bot exits, pause to see error messages
if %errorlevel% neq 0 (
    echo.
    echo %RED%❌ Bot exited with error code: %errorlevel%%NC%
    pause
)
exit /b %errorlevel%

:log_msg
set "msg_content=%~1"
for /f "usebackq tokens=*" %%t in (`powershell -NoProfile -Command "Get-Date -Format 'HH:mm:ss.fff'"`) do set "ts=%%t"
if /i "%DEBUG%"=="true" (
    set "padded_debug= DEBUG  "
    echo %TS_COLOR%[!ts!]%NC% - %TAG_COLOR%[Altroid-X]%NC% %DEBUG_COLOR%^|» !padded_debug! «^|%NC% : » !msg_content!%NC%
) else (
    echo %TS_COLOR%[!ts!]%NC% - %TAG_COLOR%[Altroid-X]%NC% !msg_content!%NC%
)
goto :eof