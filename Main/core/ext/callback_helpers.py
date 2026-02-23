# Copyright (C) 2021-present by Altruix@Github, <https://github.com/Altruix>
#
# This file is part of <https://github.com/Altruix/Altruix> project,
# and is released under the "GNU v3.0 License Agreement".
# Please see <https://github.com/Altriux/Altruix/blob/main/LICENSE>
#
# All rights reserved.

import hashlib

# 🗂️ Global Callback data cache to bypass 64-byte limit
# Accessible by both help menu and global callback logger
CALLBACK_DATA_CACHE = {}

def create_callback_id(data: str) -> str:
    """Create a short hash ID for callback data and cache it."""
    # Use first 12 chars of SHA256 hash for uniqueness
    hash_id = hashlib.sha256(data.encode()).hexdigest()[:12]
    CALLBACK_DATA_CACHE[hash_id] = data
    return hash_id

def get_callback_data(hash_id: str) -> str:
    """Retrieve original callback data from hash ID."""
    return CALLBACK_DATA_CACHE.get(hash_id, "")
