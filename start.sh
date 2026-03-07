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

# =============================================================================
# Helper: Timestamped Logging
# =============================================================================
log_msg() {
    local color=$1
    local msg=$2
    echo -e "${WHITE}[$(date +%H:%M:%S)]${NC} ${color}${msg}${NC}"
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
    
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════╗"
    echo "║       🚀 ALTROID-X - MULTI-LAUNCHER       ║"
    echo "╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
    
    case $platform in
        heroku)
            log_msg "${MAGENTA}" "Platform: HEROKU"
            echo -e "${WHITE}   Env: Cloud (Dyno)${NC}"
            ;;
        sevalla)
            log_msg "${MAGENTA}" "Platform: SEVALLA / RAILWAY / RENDER"
            echo -e "${WHITE}   Env: Cloud Platform${NC}"
            ;;
        termux)
            log_msg "${GREEN}" "Platform: TERMUX (Android/iOS)"
            echo -e "${WHITE}   Env: Mobile Linux | Venv: $venv_name${NC}"
            ;;
        wsl)
            log_msg "${BLUE}" "Platform: WSL (Windows Linux Subsystem)"
            echo -e "${WHITE}   Env: Linux on Windows | Venv: $venv_name${NC}"
            ;;
        windows)
            log_msg "${CYAN}" "Platform: WINDOWS (Native)"
            echo -e "${WHITE}   Env: Windows Native | Venv: $venv_name${NC}"
            ;;
        vps)
            log_msg "${YELLOW}" "Platform: VPS (Private Server)"
            echo -e "${WHITE}   Env: Linux VPS | Venv: $venv_name${NC}"
            ;;
        linux)
            log_msg "${GREEN}" "Platform: LINUX (Native)"
            echo -e "${WHITE}   Env: Linux Desktop | Venv: $venv_name${NC}"
            ;;
        macos)
            log_msg "${WHITE}" "Platform: macOS"
            echo -e "${WHITE}   Env: Apple macOS | Venv: $venv_name${NC}"
            ;;
        *)
            log_msg "${RED}" "Platform: UNKNOWN"
            echo -e "${WHITE}   Env: Unknown | Venv: $venv_name${NC}"
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
    echo -e "${YELLOW}⏩ Skipping venv creation (Cloud platform uses system Python)${NC}"
    VENV_PYTHON="$PYTHON_CMD"
else
    # Create virtual environment if it does not exist
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}⏳ Creating virtual environment: $VENV_DIR${NC}"
        $PYTHON_CMD -m venv "$VENV_DIR"
        echo -e "${GREEN}✅ Virtual environment created!${NC}"
    else
        echo -e "${GREEN}✅ Virtual environment found: $VENV_DIR${NC}"
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
    
    echo -e "${CYAN}🐍 Using Python: $VENV_PYTHON${NC}"
fi

# =============================================================================
# Install Dependencies
# =============================================================================
echo ""
log_msg "${YELLOW}" "📦 Pip: Updating core and dependencies..."
$VENV_PYTHON -m pip install --upgrade pip --quiet
$VENV_PYTHON -m pip install -r requirements.txt --quiet
log_msg "${GREEN}" "✅ Pip: Dependencies processed successfully."

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
    echo -e "${GREEN}✅ Environment variables loaded!${NC}"
fi

# =============================================================================
# Clean Up Existing Processes (Release Database Locks)
# =============================================================================
echo ""
log_msg "${YELLOW}" "🧹 Process: Cleaning up existing instances..."
has_killed=false

if [[ "$PLATFORM" == "windows" ]]; then
    # Windows (Git Bash / MSYS / Cygwin)
    if taskkill //F //IM python.exe //T 2>/dev/null; then
        has_killed=true
    fi
elif [[ "$PLATFORM" == "heroku" || "$PLATFORM" == "sevalla" ]]; then
    # Cloud platforms - skip process killing
    echo -e "${CYAN}⏩ Skipping process cleanup (Cloud platform)${NC}"
else
    # Linux / VPS / WSL / macOS / Termux
    if pkill -9 -f "python.* -m Main" 2>/dev/null; then
        has_killed=true
    fi
    
    # Fallback: kill processes locking session files
    if command -v fuser >/dev/null 2>&1; then
        if fuser -k cache/*.session 2>/dev/null; then
            has_killed=true
        fi
    fi
fi

# Wait for file handles to be released
if [ "$has_killed" = true ]; then
    echo -e "${YELLOW}⏳ Waiting 3 seconds for file handles to be released...${NC}"
    sleep 3
    echo -e "${GREEN}✅ Cleanup complete!${NC}"
else
    echo -e "${CYAN}ℹ️  No existing processes found.${NC}"
fi

# =============================================================================
# Launch the Bot
# =============================================================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗"
echo -e "║        🚀 STARTING ALTROID-X BOT          ║"
echo -e "╚═══════════════════════════════════════════╝${NC}"
echo ""
log_msg "${CYAN}" "Info: Platform -> $PLATFORM"
log_msg "${CYAN}" "Info: Python   -> $VENV_PYTHON"
log_msg "${YELLOW}" "⏳ Launching Altroid-X engine..."
echo ""

# Run the bot
$VENV_PYTHON -m Main

