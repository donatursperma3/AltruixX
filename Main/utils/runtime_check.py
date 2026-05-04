# ©️ Altruix, 2024
# Part of Altroid-X project
# JS Runtime Auto-Detection & Helper

import shutil
import os
import sys
import subprocess
import logging
import zipfile
import httpx
import time

logger = logging.getLogger("Altruix.JS_Runtime")

def get_js_runtime():
    """Returns the path to a valid JS runtime or None."""
    # 1. Check system PATH
    for cmd in ["node", "deno"]:
        if shutil.which(cmd):
            return cmd
            
    # 2. Check local assets bin
    local_bin = os.path.join(os.getcwd(), "Main", "assets", "bin")
    if os.path.exists(local_bin):
        for cmd in ["node", "deno", "node.exe", "deno.exe"]:
            path = os.path.join(local_bin, cmd)
            if os.path.exists(path):
                return path
                
    return None

def get_install_command():
    """Returns the install command based on OS."""
    if sys.platform == "win32":
        return "Winget: 'winget install OpenJS.NodeJS' atau download dari nodejs.org"
    elif sys.platform == "linux":
        # Check for package manager
        if shutil.which("apt"):
            return "sudo apt update && sudo apt install -y nodejs"
        elif shutil.which("yum"):
            return "sudo yum install -y nodejs"
        elif shutil.which("pacman"):
            return "sudo pacman -S nodejs"
    return "Silakan install Node.js (https://nodejs.org/)"

def check_and_alert():
    """Checks for runtime and tries auto-install if missing."""
    runtime = get_js_runtime()
    if not runtime:
        logger.info("⚠️ JS Runtime missing. Attempting auto-installation of portable Deno...")
        try:
            runtime = auto_install_runtime()
        except Exception as e:
            logger.error(f"❌ Auto-install failed: {e}")
            logger.warning(f"💡 Manual install required: {get_install_command()}")
            return False
            
    if runtime:
        # Add local bin to PATH for the current process
        local_bin = os.path.join(os.getcwd(), "Main", "assets", "bin")
        if os.path.exists(local_bin) and local_bin not in os.environ["PATH"]:
            os.environ["PATH"] = local_bin + os.pathsep + os.environ["PATH"]
            
    return True

def auto_install_runtime():
    """Downloads and extracts a portable Deno binary."""
    local_bin = os.path.join(os.getcwd(), "Main", "assets", "bin")
    os.makedirs(local_bin, exist_ok=True)
    
    target_exe = "deno.exe" if sys.platform == "win32" else "deno"
    target_path = os.path.join(local_bin, target_exe)
    
    if os.path.exists(target_path):
        return target_path
        
    # Determine URL
    if sys.platform == "win32":
        url = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"
    else:
        url = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip"
        
    tmp_zip = os.path.join(local_bin, "deno_tmp.zip")
    
    # Download
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        r = client.get(url)
        r.raise_for_status()
        with open(tmp_zip, "wb") as f:
            f.write(r.content)
            
    # Extract
    with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
        zip_ref.extractall(local_bin)
        
    # Cleanup
    if os.path.exists(tmp_zip):
        os.remove(tmp_zip)
        
    # Set permissions on Linux
    if sys.platform != "win32":
        os.chmod(target_path, 0o755)
        
    logger.info(f"✅ Portable Deno installed successfully at: {target_path}")
    return target_path
