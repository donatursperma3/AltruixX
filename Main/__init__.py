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

# ─── EARLY LOGGING ──────────────────────────────────────────
def setup_early_logging():
    """Configures basic root logging immediately at startup."""
    log_format = "[%(asctime)s.%(msecs)03d] - [Altroid-X] >> %(levelname)s << %(message)s"
    date_format = "%d/%m/%Y, %H:%M:%S"
    
    # Root logger setup
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO, format=log_format, datefmt=date_format)

# Initialize logging as the ABSOLUTE FIRST STEP
setup_early_logging()


# ✅ SILENCE EXTERNAL LOGS: Masking noisy startup messages from pyromod/pyrogram
# Only silence if DEBUG mode is OFF to allow full visibility for developers
is_debug = os.getenv("DEBUG", "false").lower() == "true"
if not is_debug:
    os.environ["PYROMOD_LOG_LEVEL"] = "ERROR"
    os.environ["PYROMOD_SILENT"] = "1"
    os.environ["PYROGRAM_LOGGER_LEVEL"] = "ERROR"

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

# ✅ PERFORMANCE: Lazy import pyromod - only imported when needed by client
# Mask stdout during noisy imports (silences "Pyromod is working!" and TgCrypto warnings)
# Skip redirection if DEBUG is True to reveal hidden startup details
if not is_debug:
    dummy_out = io.StringIO()
    with contextlib.redirect_stdout(dummy_out), contextlib.redirect_stderr(dummy_out):
        try:
            from pyromod import listen
        except ImportError:
            pass
else:
    try:
        from pyromod import listen
    except ImportError:
        pass

from .core.client import AltruixClient, Altruix
# Ensure subpackages are exposed for test imports
from . import core
