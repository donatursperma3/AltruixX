#!/usr/bin/env bash
# -------------------------------------------------
# start.sh – Launch Altruix Userbot
# -------------------------------------------------

# Exit on any error
set -e

# Detect Python interpreter
PYTHON_CMD="python"
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
fi

# Fix Unicode errors on Windows
export PYTHONIOENCODING=utf-8

# Create virtual environment if it does not exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Detect venv paths (Windows 'Scripts' vs Linux 'bin')
if [ -d "venv/Scripts" ]; then
    VENV_PYTHON="./venv/Scripts/python.exe"

elif [ -d "venv/bin" ]; then
    VENV_PYTHON="./venv/bin/python"

else
    echo "Error: Could not find venv/Scripts or venv/bin. Virtual environment setup failed."
    exit 1
fi

echo "Using Python: $VENV_PYTHON"

# Upgrade pip and install dependencies using the VENV executable directly
echo "Installing dependencies..."
$VENV_PYTHON -m pip install --upgrade pip
$VENV_PYTHON -m pip install -r requirements.txt

# Load environment variables from .env if present
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    while IFS= read -r line || [ -n "$line" ]; do
        # Strip carriage return and skip comments/empty lines
        line=$(echo "$line" | tr -d '\r')
        case "$line" in
            \#*|"") continue ;;
        esac
        export "$line"
    done < ".env"
fi

# Run the bot using the VENV python executable
echo "Starting Altruix..."
$VENV_PYTHON -m Main