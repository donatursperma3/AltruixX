import sys
import subprocess
import os
import datetime
import importlib.util
from importlib.metadata import version, PackageNotFoundError

# Premium Colors
TS_COLOR = "\033[97;48;5;141m"
TAG_COLOR = "\033[97;48;2;69;104;130m"
DEBUG_COLOR = "\033[97;46m"
RESET = "\033[0m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"

def get_ts():
    now = datetime.datetime.now()
    return now.strftime("%H:%M:%S.%f")[:-3]

def log_msg(msg):
    ts = get_ts()
    is_debug = os.getenv("DEBUG", "false").lower() == "true"
    if is_debug:
        padded_debug = "DEBUG".center(8)
        print(f"{TS_COLOR}[{ts}]{RESET} - {TAG_COLOR}[Altroid-X]{RESET} {DEBUG_COLOR}|» {padded_debug} «|{RESET} : » {msg}", flush=True)
    else:
        print(f"{TS_COLOR}[{ts}]{RESET} - {TAG_COLOR}[Altroid-X]{RESET} {msg}", flush=True)

def is_installed(package_name):
    # If it's a URL dependency, we can't easily check it manually, let pip handle it
    if package_name.startswith(("http://", "https://", "git+", "git://")):
        return False

    # Standardize package name: remove versions, extras [standard], and normalize dashes
    # Example: "uvicorn[standard]>=0.20" -> "uvicorn"
    clean_name = package_name.split('>=')[0].split('==')[0].split('~=')[0].split('<')[0].split('[')[0].strip()
    
    try:
        # Check by metadata name (most reliable)
        version(clean_name)
        return True
    except PackageNotFoundError:
        # Fallback: check if it can be imported (normalize name to module name)
        module_name = clean_name.replace('-', '_')
        return importlib.util.find_spec(module_name) is not None

def main():
    # 1. Update pip
    log_msg(f"{YELLOW}⏳ Checking for pip updates...{RESET}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_msg(f"{GREEN}✅ Pip is up to date.{RESET}")
    except Exception:
        log_msg(f"{YELLOW}⚠️  Could not update pip, continuing anyway...{RESET}")

    req_file = "requirements.txt"
    if not os.path.exists(req_file):
        log_msg(f"{RED}❌ {req_file} not found!{RESET}")
        return

    with open(req_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    total = len(lines)
    log_msg(f"{CYAN}📦 Found {total} dependencies in {req_file}{RESET}")
    
    installed_count = 0
    for i, line in enumerate(lines, 1):
        pkg_spec = line
        pkg_name = pkg_spec.split('>=')[0].split('==')[0].split('[')[0].strip()
        prefix = f"[{i}/{total}]"
        
        if is_installed(pkg_name):
            log_msg(f"{prefix} ✅ {GREEN}Already Satisfied:{RESET} {pkg_spec}")
            installed_count += 1
        else:
            log_msg(f"{prefix} ⏳ {YELLOW}Installing:{RESET} {pkg_spec}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_spec], 
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log_msg(f"{prefix} ✅ {GREEN}Successfully Installed:{RESET} {pkg_spec}")
            except Exception:
                log_msg(f"{prefix} ❌ {RED}Failed to install {pkg_spec}{RESET}")

    log_msg(f"{GREEN}✨ All dependencies processed! ({installed_count}/{total} previously present){RESET}")

if __name__ == "__main__":
    main()
