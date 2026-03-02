# Copyright (C) 2021-present by Altruix@Github, <https://github.com/Altruix>
#
# This file is part of <https://github.com/Altruix/Altruix> project,
# and is released under the "GNU v3.0 License Agreement".
# Please see <https://github.com/Altriux/Altruix/blob/main/LICENSE>
#
# All rights reserved.

import hashlib


# 🗂️ Persistent Callback data cache to bypass 64-byte limit
# Uses the database (MongoDB/LocalDB) for cross-restart persistence.

async def create_callback_id(data: str) -> str:
    """Create a short hash ID for callback data and cache it in the database."""
    from Main.core.client import Altruix
    # Use first 12 chars of SHA256 hash for uniqueness
    hash_id = hashlib.sha256(data.encode()).hexdigest()[:12]
    
    # Store in database
    await Altruix.db.callback_col.find_one_and_update(
        {"_id": hash_id},
        {"$set": {"_id": hash_id, "data": data}},
        upsert=True
    )
    return hash_id

async def get_callback_data(hash_id: str) -> str:
    """Retrieve original callback data from hash ID in the database."""
    from Main.core.client import Altruix
    res = await Altruix.db.callback_col.find_one({"_id": hash_id})
    return res.get("data", "") if res else ""
