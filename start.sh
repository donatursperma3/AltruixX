#!/usr/bin/env bash
# =============================================================================
# start.sh – Multi-Platform Altruix Userbot Launcher
# Supports: Windows, WSL, Linux, VPS, Termux, Heroku, Sevalla
# =============================================================================

set -e  # Exit on any error

# =============================================================================
# ANSI Color Codes for Pretty Output
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color
TS_COLOR='\033[97;48;5;141m'
TAG_COLOR='\033[97;48;2;69;104;130m'

# =============================================================================
# Helper: Timestamped Logging
# =============================================================================
log_msg() {
    local msg=$1
    # Standard format: HH:MM:SS.mmm
    local ts=$(date +"%H:%M:%S.%3N")
    if [[ "$ts" == *"%3N" ]]; then ts=$(date +"%H:%M:%S.000"); fi
    
    # Premium Colors
    local TS_COLOR='\033[97;48;5;141m'
    local TAG_COLOR='\033[97;48;2;69;104;130m'
    local DEBUG_COLOR='\033[97;46m'
    local NC='\033[0m'
    
    # Check DEBUG mode
    if [[ "${DEBUG,,}" == "true" ]]; then
        local padded_debug=" DEBUG  "
        echo -e "${TS_COLOR}[${ts}]${NC} - ${TAG_COLOR}[Altroid-X]${NC} ${DEBUG_COLOR}|» ${padded_debug} «|${NC} : » ${msg}${NC}"
    else
        echo -e "${TS_COLOR}[${ts}]${NC} - ${TAG_COLOR}[Altroid-X]${NC} ${msg}${NC}"
    fi
}

# =============================================================================
# Platform Detection
# =============================================================================
detect_platform() {
    local platform="unknown"
    local venv_name="venv"
    
    # Check for Heroku
    if [ -n "$DYNO" ]; then
        platform="heroku"
        venv_name="venv"  # Heroku doesn't use venv, but we set it for consistency
        
    # Check for Sevalla (Railway, Render, or similar)
    elif [ -n "$SVL_DEPLOYMENT_BRANCH" ] || [ -n "$RAILWAY_ENVIRONMENT" ] || [ -n "$RENDER" ]; then
        platform="sevalla"
        venv_name="venv"
        
    # Check for Termux
    elif [ -d "/data/data/com.termux" ]; then
        platform="termux"
        venv_name=".venv_termux"
        
    # Check for WSL (Windows Subsystem for Linux)
    elif grep -qi microsoft /proc/version 2>/dev/null || grep -qi wsl /proc/version 2>/dev/null; then
        platform="wsl"
        venv_name=".venv_wsl"
        
    # Check for Windows (Git Bash, MSYS, Cygwin)
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        platform="windows"
        venv_name="venv"
        
    # Check for Linux VPS (check for common VPS indicators)
    elif [ -f /proc/version ]; then
        if grep -qi "linux" /proc/version 2>/dev/null; then
            # Check if it's a VPS (has virtualization indicators)
            if grep -qi "kvm\|xen\|vmware\|virtualbox\|qemu" /proc/cpuinfo 2>/dev/null || \
               [ -d /proc/vz ] || [ -d /proc/bc ] || \
               systemd-detect-virt >/dev/null 2>&1; then
                platform="vps"
                venv_name=".venv_vps"
            else
                platform="linux"
                venv_name=".venv_linux"
            fi
        fi
    
    # Fallback to generic Linux
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        platform="linux"
        venv_name=".venv_linux"
        
    # macOS
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        platform="macos"
        venv_name=".venv_macos"
    fi
    
    echo "$platform:$venv_name"
}

# =============================================================================
# Detect Python Command
# =============================================================================
detect_python() {
    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
    elif command -v python >/dev/null 2>&1; then
        echo "python"
    else
        echo -e "${RED}❌ Error: Python not found!${NC}"
        exit 1
    fi
}

# =============================================================================
# Display Platform Banner
# =============================================================================
display_banner() {
    local platform=$1
    local venv_name=$2
    
    log_msg "${CYAN}╔═══════════════════════════════════════════╗"
    log_msg "${CYAN}║       🚀 ALTROID-X - MULTI-LAUNCHER       ║"
    log_msg "${CYAN}╚═══════════════════════════════════════════╝"
    echo ""
    
    case $platform in
        heroku)
            log_msg "${MAGENTA}Platform: HEROKU"
            log_msg "${WHITE}   Env: Cloud (Dyno)"
            ;;
        sevalla)
            log_msg "${MAGENTA}Platform: SEVALLA / RAILWAY / RENDER"
            log_msg "${WHITE}   Env: Cloud Platform"
            ;;
        termux)
            log_msg "${GREEN}Platform: TERMUX (Android/iOS)"
            log_msg "${WHITE}   Env: Mobile Linux | Venv: $venv_name"
            ;;
        wsl)
            log_msg "${BLUE}Platform: WSL (Windows Linux Subsystem)"
            log_msg "${WHITE}   Env: Linux on Windows | Venv: $venv_name"
            ;;
        windows)
            log_msg "${CYAN}Platform: WINDOWS (Native)"
            log_msg "${WHITE}   Env: Windows Native | Venv: $venv_name"
            ;;
        vps)
            log_msg "${YELLOW}Platform: VPS (Private Server)"
            log_msg "${WHITE}   Env: Linux VPS | Venv: $venv_name"
            ;;
        linux)
            log_msg "${GREEN}Platform: LINUX (Native)"
            log_msg "${WHITE}   Env: Linux Desktop | Venv: $venv_name"
            ;;
        macos)
            log_msg "${WHITE}Platform: macOS"
            log_msg "${WHITE}   Env: Apple macOS | Venv: $venv_name"
            ;;
        *)
            log_msg "${RED}Platform: UNKNOWN"
            log_msg "${WHITE}   Env: Unknown | Venv: $venv_name"
            ;;
    esac
    echo ""
}

# =============================================================================
# Main Execution
# =============================================================================

# Detect platform and venv name
PLATFORM_INFO=$(detect_platform)
PLATFORM=$(echo "$PLATFORM_INFO" | cut -d':' -f1)
VENV_DIR=$(echo "$PLATFORM_INFO" | cut -d':' -f2)

# Detect Python command
PYTHON_CMD=$(detect_python)

# Display banner
display_banner "$PLATFORM" "$VENV_DIR"

# Fix Unicode errors on Windows
export PYTHONIOENCODING=utf-8

# =============================================================================
# Virtual Environment Setup (Skip for Heroku/Sevalla)
# =============================================================================
if [[ "$PLATFORM" == "heroku" || "$PLATFORM" == "sevalla" ]]; then
    log_msg "${YELLOW}⏩ Skipping venv creation (Cloud platform uses system Python)"
    VENV_PYTHON="$PYTHON_CMD"
else
    # Create virtual environment if it does not exist
    if [ ! -d "$VENV_DIR" ]; then
        log_msg "${YELLOW}⏳ Creating virtual environment: $VENV_DIR"
        $PYTHON_CMD -m venv "$VENV_DIR"
        log_msg "${GREEN}✅ Virtual environment created!"
    else
        log_msg "${GREEN}✅ Virtual environment found: $VENV_DIR"
    fi

    # Detect venv Python executable path
    if [ -d "$VENV_DIR/Scripts" ] && [[ "$PLATFORM" == "windows" ]]; then
        # Windows venv structure
        VENV_PYTHON="./$VENV_DIR/Scripts/python.exe"
    elif [ -d "$VENV_DIR/bin" ]; then
        # Linux/WSL/macOS venv structure
        VENV_PYTHON="./$VENV_DIR/bin/python"
    else
        # Fallback
        VENV_PYTHON="./$VENV_DIR/Scripts/python.exe"
    fi
    
fi
# Ensure VENV_PYTHON is never empty for the logger pipe
VENV_PYTHON="${VENV_PYTHON:-$PYTHON_CMD}"
log_msg "${CYAN}🐍 Using Python: $VENV_PYTHON"

# =============================================================================
# Install Dependencies
# =============================================================================
echo ""
log_msg "${YELLOW}📦 Pip: Updating core and dependencies..."
log_msg "${YELLOW}⏳ This process installs 60+ libraries and may take several minutes. Please do not close the terminal..."
$VENV_PYTHON smart_install.py

# =============================================================================
# Load Environment Variables from .env
# =============================================================================
if [ -f ".env" ]; then
    echo -e "${YELLOW}⏳ Loading environment variables from .env...${NC}"
    while IFS= read -r line || [ -n "$line" ]; do
        # Strip carriage return and skip comments/empty lines
        line=$(echo "$line" | tr -d '\r')
        case "$line" in
            \#*|"") continue ;;
        esac
        
        # Split into key and value, stripping quotes from value
        key=$(echo "$line" | cut -d '=' -f 1)
        value=$(echo "$line" | cut -d '=' -f 2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        export "$key=$value"
    done < ".env"
    log_msg "${GREEN}✅ Environment variables loaded!"
fi

# =============================================================================
# Clean Up Existing Processes & Stale Locks (DISABLED - Allows Multi-Instance)
# =============================================================================
echo ""
log_msg "${CYAN}ℹ️  Multi-instance support enabled (Cleanup disabled)."
# log_msg "${RED}" "🧹 Process: Cleaning up existing instances & stale locks..."
# has_killed=false
#
# # 1. Kill existing Python processes (Kill FIRST to release file locks)
# if [[ "$PLATFORM" == "windows" ]]; then
#     # Native Windows
#     if taskkill //F //IM python.exe //T 2>/dev/null; then
#         has_killed=true
#     fi
# elif [[ "$PLATFORM" == "wsl" ]]; then
#     # WSL: Kill both WSL processes and Windows processes (Windows processes can lock NTFS files)
#     if pkill -9 -f "python.* -m Main" 2>/dev/null; then
#         has_killed=true
#     fi
#     # Also attempt to kill Windows python processes if they are locking the F: drive files
#     if command -v taskkill.exe >/dev/null 2>&1; then
#         if taskkill.exe /F /IM python.exe /T 2>/dev/null; then
#             has_killed=true
#         fi
#     fi
# elif [[ "$PLATFORM" == "heroku" || "$PLATFORM" == "sevalla" ]]; then
#     # Cloud platforms
#     echo -e "${CYAN}⏩ Skipping process cleanup (Cloud platform)${NC}"
# else
#     # Linux / VPS / macOS / Termux
#     if pkill -9 -f "python.* -m Main" 2>/dev/null; then
#         has_killed=true
#     fi
#     
#     # Fallback: kill processes locking session files
#     if command -v fuser >/dev/null 2>&1; then
#         if fuser -k cache/*.session 2>/dev/null; then
#             has_killed=true
#         fi
#     fi
# fi
#
# # 2. Wait for handles to release & then clean stale SQLite journal/WAL files
# if [ "$has_killed" = true ]; then
#     echo -e "${YELLOW}⏳ Waiting 3 seconds for file handles to be released...${NC}"
#     sleep 3
# fi

# if [ "$has_killed" = true ]; then
#     echo -e "${GREEN}✅ Cleanup complete!${NC}"
# else
#     echo -e "${CYAN}ℹ️  No existing processes found.${NC}"
# fi

# 3. Clean up stale journal files safely
if ls cache/*.session-journal >/dev/null 2>&1 || ls cache/*.session-wal >/dev/null 2>&1; then
    log_msg "${CYAN}🧹 Cache: Removing stale journal/WAL files..."
    rm -f cache/*.session-journal cache/*.session-wal
fi

# =============================================================================
# Launch the Bot
# =============================================================================
echo ""
log_msg "${GREEN}╔═══════════════════════════════════════════╗"
log_msg "${GREEN}║        🚀 STARTING ALTROID-X BOT          ║"
log_msg "${GREEN}╚═══════════════════════════════════════════╝"
echo ""

log_msg "${CYAN}Platform: ${PLATFORM} (${VENV_DIR})"
log_msg "${CYAN}Python: ${PYTHON_CMD}"
echo ""
log_msg "${YELLOW}⏳ Launching Altroid-X engine..."
log_msg "${YELLOW}⏳ Please be patient, it will take a few minutes..."
echo ""

# Run the bot
$VENV_PYTHON -m Main