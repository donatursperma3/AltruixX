# Main/internals/settings_handlers/purgeme_handlers.py
import os
import logging
import traceback
from Main.utils.file_helpers import get_db_path as _get_db_path
import json as _json

logger = logging.getLogger("altruix.purgeme.handlers")
logger.setLevel(logging.INFO)

# Default Configuration
DEFAULT_PURGEME_CONFIG = {
    "count": 20,
    "delay": 1.0,
    "batch_size": 30,
    "batch_delay": 0, # in seconds
    "mode": "oldest",
    "from_id": "me",
    "notify": False,
    "forward_log": "off", # options: off, group_log, pm_bot, saved
    "fwd_delay": 0.5, # delay between forward and delete
    "keep_recent": 0,
    "max_scan": 500,
    "offset": 0,
    "min_id": 0,
    "max_id": 0,
    "min_days": 0,
    "max_days": 0,
    "types": ["all"]
}

_USER_PURGEME_CONFIG_FILE = _get_db_path("xpurgeme_user_configs.json")

def save_user_purgeme_config(user_id: int, config: dict):
    """Save user's Purgeme config to persistent JSON storage."""
    try:
        data = {}
        # Read existing data if file exists
        if os.path.exists(_USER_PURGEME_CONFIG_FILE):
            with open(_USER_PURGEME_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = _json.load(f)
        
        # Update specific user's config
        data[str(user_id)] = config
        
        # Write to temporary file first to prevent corruption during crash
        tmp = f"{_USER_PURGEME_CONFIG_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Atomic replace to final destination
        os.replace(tmp, _USER_PURGEME_CONFIG_FILE)
    except Exception as e:
        logger.error(f"Failed to save user Purgeme config: {e}\n{traceback.format_exc()}")

def load_user_purgeme_config(user_id: int) -> dict:
    """Load user's saved Purgeme config, or return system defaults."""
    try:
        # Check if persistent storage exists
        if os.path.exists(_USER_PURGEME_CONFIG_FILE):
            with open(_USER_PURGEME_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = _json.load(f)
            
            # Retrieve specific user configuration
            saved = data.get(str(user_id))
            if saved:
                # Merge saved settings with current defaults to handle new keys
                merged = DEFAULT_PURGEME_CONFIG.copy()
                merged.update(saved)
                return merged
    except Exception as e:
        logger.error(f"Failed to load user Purgeme config: {e}\n{traceback.format_exc()}")
    
    # Fallback to system defaults if loading fails or no config exists
    return DEFAULT_PURGEME_CONFIG.copy()
