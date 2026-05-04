# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >

# All rights reserved.
import sys
import asyncio
import os
import contextlib
import io
import logging
from datetime import datetime

# ─── EARLY BOOTSTRAPPING ───────────────────────────────────────
# Original stdout to avoid recursion
_original_stdout = sys.stdout

def print_boot_msg(msg):
    # Prevent double-tagging if the message already looks like a log
    if "- [Altroid-X]" in str(msg) and "[" in str(msg) and "]" in str(msg):
        _original_stdout.write(f"{msg}\n")
        _original_stdout.flush()
        return

    is_debug = os.getenv("DEBUG", "false").lower() == "true"
    if not is_debug:
        return
        
    ts_color = "\033[97;48;5;141m"
    tag_color = "\033[97;48;2;69;104;130m"
    debug_color = "\033[97;46m"
    reset = "\033[0m"
    
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    padded_debug = "DEBUG".center(8)
    
    # Format: [TS] - [Altroid-X] |»  DEBUG   «| : »  msg
    _original_stdout.write(
        f"{ts_color}[{ts}]{reset} - {tag_color}[Altroid-X]{reset} "
        f"{debug_color}|» {padded_debug} «|{reset} : » {msg}\n"
    )
    _original_stdout.flush()

# ✅ PRINT INTERCEPTOR (Fixes Pyromod and other 3rd party prints)
class PrintInterceptor:
    def write(self, data):
        clean_data = data.strip()
        if clean_data:
            print_boot_msg(clean_data)
        return len(data)
    def flush(self):
        _original_stdout.flush()

# Hook it only if not already hooked
if not isinstance(sys.stdout, PrintInterceptor):
    sys.stdout = PrintInterceptor()

# ✅ HIGH-RESOLUTION IMPORT TRACKER
# This identifies EXACTLY which library is causing the 5-minute delay.
class ImportTracker:
    def __init__(self, original_import):
        self.original_import = original_import
        self.count = 0
        self.major_packages = ["pyrogram", "httpx", "motor", "git", "yaml", "aiofiles", "psutil"]

    def __call__(self, name, globals=None, locals=None, fromlist=(), level=0):
        # Only track top-level imports that aren't already loaded
        is_new = name not in sys.modules
        start_time = None
        
        # Show progress for NEW top-level imports
        if is_debug and is_new and level == 0:
            self.count += 1
            # For major packages or every 5th module, show immediate loading status
            if any(pkg in name.lower() for pkg in self.major_packages) or self.count % 5 == 0:
                print_boot_msg(f"📦 Loading Module [{self.count}]: {name}...")
            
            import time as _time
            start_time = _time.time()
        
        module = self.original_import(name, globals, locals, fromlist, level)
        
        if start_time:
            import time as _time
            duration = _time.time() - start_time
            # If an import is exceptionally slow, flag it explicitly
            if duration > 0.5:
                print_boot_msg(f"⚠️ Slow Load: {name} took {duration:.2f}s")
        
        return module

is_debug = os.getenv("DEBUG", "false").lower() == "true"
if is_debug:
    import builtins
    import threading
    import time
    
    # 1. Install Import Tracker
    builtins.__import__ = ImportTracker(builtins.__import__)
    
    # 2. System Health Watcher Disabled to save resources

print_boot_msg("Initializing Core Engine...")

class EarlyColoredFormatter(logging.Formatter):
    """Simple formatter for adding colors during early boot."""
    COLORS = {
        logging.DEBUG: "\033[97;46m",    # White text, Cyan BG
        logging.INFO: "\033[97;42m",     # White text, Green BG
        logging.WARNING: "\033[97;43m",  # White text, Yellow BG
        logging.ERROR: "\033[97;41m",    # White text, Red BG
        logging.CRITICAL: "\033[97;1;41m" # White text, Bold, Red BG
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        # ✅ Center-pad levelname to uniform width (longest = CRITICAL = 8 chars)
        original_levelname = record.levelname
        record.levelname = record.levelname.center(8)
        formatted = super().format(record)
        record.levelname = original_levelname  # Restore original
        
        # Caller Info
        caller_info = f" [📍 {record.module}.{record.funcName}]"
        
        # Timestamp Color Update
        timestamp_color = "\033[97;48;5;141m"
        if formatted.startswith("["):
            end_bracket = formatted.find("]")
            if end_bracket != -1:
                ts = formatted[1:end_bracket]
                formatted = f"{timestamp_color}[{ts}]{self.RESET}{formatted[end_bracket+1:]}"

        # Tag Color Update
        tag_color = "\033[97;48;2;69;104;130m"
        formatted = formatted.replace("[Altroid-X]", f"{tag_color}[Altroid-X]{self.RESET}", 1)
        
        padded_level = original_levelname.center(8)
        target = f"|» {padded_level} «|"
        if target in formatted:
            colored_target = f"{color}{target}{self.RESET}"
            if record.levelno == logging.DEBUG:
                colored_target = f"{colored_target} : » "
            formatted = formatted.replace(target, colored_target, 1)
            
        return f"{formatted}{caller_info}"

def setup_early_logging():
    """Configures basic root logging immediately at startup."""
    log_format = "[%(asctime)s.%(msecs)03d] - [Altroid-X] |» %(levelname)s «| %(message)s"
    date_format = "%H:%M:%S"
    
    is_debug = os.getenv("DEBUG", "false").lower() == "true"
    
    class EarlyDemoterFilter(logging.Filter):
        def filter(self, record):
            demote_list = ["pyrogram.connection", "pyrogram.crypto", "pyromod", "uvicorn"]
            if any(target in record.name for target in demote_list):
                if not is_debug:
                    return False
                record.levelno = logging.DEBUG
                record.levelname = "DEBUG"
            return True

    # Root logger setup
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(EarlyColoredFormatter(log_format, date_format))
        handler.addFilter(EarlyDemoterFilter())
        root.addHandler(handler)
        root.setLevel(logging.INFO)

# Initialize logging as the ABSOLUTE FIRST STEP
setup_early_logging()


# ✅ SILENCE EXTERNAL LOGS: Masking noisy startup messages from pyromod/pyrogram
# Only silence if DEBUG mode is OFF to allow full visibility for developers
is_debug = os.getenv("DEBUG", "false").lower() == "true"
if not is_debug:
    os.environ["PYROMOD_LOG_LEVEL"] = "ERROR"
    os.environ["PYROMOD_SILENT"] = "1"
    os.environ["PYROGRAM_LOGGER_LEVEL"] = "ERROR"
    # Silence all verbose internal loggers
    for logger_name in [
        "pyrogram", "pyrogram.connection", "pyrogram.session", 
        "pyrogram.connection.connection", "pyrogram.session.session",
        "websockets", "websockets.server", "websockets.legacy.server"
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

print_boot_msg("Configuring Event Loop...")
# ✅ PERFORMANCE OPTIMIZATION: Set loop policy at absolute entry point
# Only import if not already set to avoid redundant imports
if not isinstance(asyncio.get_event_loop_policy(), (asyncio.DefaultEventLoopPolicy if sys.platform != "win32" else asyncio.WindowsProactorEventLoopPolicy)):
    try:
        if sys.platform == "win32":
            import winloop
            asyncio.set_event_loop_policy(winloop.EventLoopPolicy())
        else:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        if sys.platform == "win32" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

print_boot_msg("Loading Pyromod...")
# ✅ PERFORMANCE: Lazy import pyromod - only imported when needed by client
# Capture and redirect the noisy "Pyromod is working!" message to the standard logger
try:
    with contextlib.redirect_stdout(io.StringIO()) as f:
        from pyromod import listen
    
    # If pyromod printed its greeting, log it properly
    pyromod_msg = f.getvalue().strip()
    if pyromod_msg:
        logging.getLogger("pyromod").info(pyromod_msg)
except ImportError:
    pass

print_boot_msg("Importing Altruix Client (Loading Libraries)...")
from .core.client import AltruixClient, Altruix
# Ensure subpackages are exposed for test imports
from . import core
