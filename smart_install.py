import sys
import subprocess
import os
import datetime
import importlib.util
import urllib.request
import time
import threading
import queue
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

def log_msg(msg, end="\n", flush=True):
    ts = get_ts()
    is_debug = os.getenv("DEBUG", "false").lower() == "true"
    if is_debug:
        padded_debug = "DEBUG".center(8)
        print(f"{TS_COLOR}[{ts}]{RESET} - {TAG_COLOR}[Altroid-X]{RESET} {DEBUG_COLOR}|» {padded_debug} «|{RESET} : » {msg}", end=end, flush=flush)
    else:
        print(f"{TS_COLOR}[{ts}]{RESET} - {TAG_COLOR}[Altroid-X]{RESET} {msg}", end=end, flush=flush)

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

def download_with_progress(url, prefix):
    try:
        filename = url.split("/")[-1].split("?")[0] or "package.zip"
        if not any(filename.endswith(ext) for ext in [".zip", ".tar.gz", ".whl", ".tar"]):
            filename += ".zip"
        
        target_dir = "temp"
        os.makedirs(target_dir, exist_ok=True)
        dest = os.path.join(target_dir, filename)
        
        # Remove old file if exists
        if os.path.exists(dest):
            os.remove(dest)

        def progress_hook(count, block_size, total_size):
            if total_size <= 0: return
            downloaded = count * block_size
            percent = min(100, downloaded * 100 / total_size)
            size_mb = total_size / (1024 * 1024)
            dl_mb = min(size_mb, downloaded / (1024 * 1024))
            
            # Calculate speed (approx)
            sys.stdout.write(f"\r{TS_COLOR}[{get_ts()}]{RESET} - {TAG_COLOR}[Altroid-X]{RESET} {prefix} 📥 {CYAN}Downloading:{RESET} {dl_mb:.2f}/{size_mb:.2f} MB ({percent:.1f}%)   ")
            sys.stdout.flush()

        # Add User-Agent to avoid blocks
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        
        urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
        print() # New line after progress
        return dest
    except Exception as e:
        print() # New line if it failed mid-way
        log_msg(f"{prefix} ❌ {RED}Download failed: {e}{RESET}")
        return None

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
            if pkg_spec.startswith(("http://", "https://")):
                log_msg(f"{prefix} ⏳ {YELLOW}Preparing URL installation:{RESET} {pkg_spec}")
                downloaded_file = download_with_progress(pkg_spec, prefix)
                if downloaded_file:
                    target_to_install = downloaded_file
                else:
                    target_to_install = pkg_spec # Fallback to pip's own downloader
            else:
                log_msg(f"{prefix} ⏳ {YELLOW}Installing:{RESET} {pkg_spec}...")
                target_to_install = pkg_spec

                try:
                    # Use -v (verbose) to see background activity for heartbeat tracking
                    process = subprocess.Popen(
                        [sys.executable, "-m", "pip", "install", "-v", target_to_install],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    
                    output_queue = queue.Queue()
                    def reader(pipe, q):
                        try:
                            with pipe:
                                for line in iter(pipe.readline, ''):
                                    q.put(line)
                        except Exception:
                            pass
                    
                    t = threading.Thread(target=reader, args=(process.stdout, output_queue))
                    t.daemon = True
                    t.start()

                    file_count = 0
                    active_keywords = [
                        "Collecting", "Downloading", "Installing collected packages", 
                        "Successfully installed", "Requirement already satisfied",
                        "Running setup.py", "Building wheel", "Preparing metadata",
                        "Installing source", "Created wheel", "Using cached",
                        "Successfully uninstalled"
                    ]
                    
                    last_activity = time.time()
                    while True:
                        try:
                            # Wait for output with a 10-second timeout for the heartbeat
                            output_line = output_queue.get(timeout=10)
                            output_line = output_line.strip()
                            last_activity = time.time()
                            
                            if not output_line: continue
                            
                            # 1. Check for major milestones
                            if any(x in output_line for x in active_keywords):
                                log_msg(f"{prefix}   » {CYAN}{output_line}{RESET}")
                                continue

                            # 2. Track background file installation progress (from -v output)
                            # Expanded keywords for better heartbeat coverage
                            if any(kw in output_line for kw in ["Installing ", "Copying ", "Creating ", "Writing ", "Skipping ", "Checking "]):
                                file_count += 1
                                if file_count % 50 == 0: # More frequent heartbeat (50 files)
                                    log_msg(f"{prefix}   » {CYAN}🛠  Processing files... ({file_count} files done){RESET}")
                                continue

                            # 3. Show errors or warnings always
                            if any(x in output_line.lower() for x in ["error", "fail", "warning", "exception"]):
                                log_msg(f"{prefix}   » {RED}{output_line}{RESET}")
                        
                        except queue.Empty:
                            # If queue is empty, check if process is still running
                            if process.poll() is not None:
                                break
                            # Still running but silent for 10 seconds - show heartbeat
                            log_msg(f"{prefix}   » {CYAN}⏳ Still working... (Background process active){RESET}")
                    
                    process.wait()
                    if process.returncode == 0:
                        log_msg(f"{prefix} ✅ {GREEN}Successfully Installed:{RESET} {pkg_spec}")
                        installed_count += 1
                    else:
                        log_msg(f"{prefix} ❌ {RED}Failed to install {pkg_spec} (Code: {process.returncode}){RESET}")
                except Exception as e:
                    log_msg(f"{prefix} ❌ {RED}Error during installation: {e}{RESET}")

    log_msg(f"{GREEN}✨ All dependencies processed! ({installed_count}/{total} previously present){RESET}")

if __name__ == "__main__":
    main()
