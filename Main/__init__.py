# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >

# All rights reserved.
import sys
import asyncio

# ✅ PERFORMANCE OPTIMIZATION: Set loop policy at absolute entry point
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

from pyromod import listen
from .core.client import AltruixClient


Altruix = AltruixClient()
