"""
Access Control Utilities for Bot Assistant Features
Provides helper functions for checking reply access permissions across all loggers.
"""

from typing import Optional, List
from pyrogram.types import User
import logging

logger = logging.getLogger("altruix.access_control")

# Access modes
ACCESS_MODE_ALL = "all"
ACCESS_MODE_SUDO = "sudo"
ACCESS_MODE_OWNER = "owner"
ACCESS_MODE_MENTIONED = "mentioned"

def check_reply_access(
    user: User,
    mode: str,
    owner_id: int,
    sudo_users: List[int],
    mentioned_userbot_id: Optional[int] = None
) -> tuple[bool, str]:
    """
    Check if a user has permission to use reply buttons based on access mode.
    """
    user_id = user.id
    from Main.core.client import Altruix
    
    # ✅ Optimized Check: If user is in centralized cache, they are authorized for SUDO/OWNER tasks
    # (Altruix._auth_users_cache includes OWNER_ID, Session IDs, and all Sudo users)
    is_globally_auth = user_id in Altruix._auth_users_cache

    # Mode: ALL - anyone can reply
    if mode == ACCESS_MODE_ALL:
        return True, "Access granted (ALL mode)"
    
    # Mode: OWNER - only owner
    if mode == ACCESS_MODE_OWNER:
        if user_id == owner_id or user_id in getattr(Altruix.config, "OWNER_USERS_ID", []):
            return True, "Access granted (OWNER)"
            
        # ✅ Support Custom Alert Settings
        from Main.utils.file_helpers import get_user_custom_alert
        alert_data = get_user_custom_alert(owner_id)
        if alert_data.get("mode") == "custom":
            return False, alert_data.get("text", Altruix.get_string("AUTH_OWNER_ONLY"))
            
        return False, Altruix.get_string("AUTH_OWNER_ONLY")
    
    # Mode: SUDO - owner + sudo users
    if mode == ACCESS_MODE_SUDO:
        if is_globally_auth:
            return True, f"Access granted (SUDO)"
        if user_id == owner_id or user_id in sudo_users or user_id in getattr(Altruix.config, "OWNER_USERS_ID", []):
            return True, f"Access granted (SUDO - legacy fallback)"
            
        # ✅ Support Custom Alert Settings
        from Main.utils.file_helpers import get_user_custom_alert
        alert_data = get_user_custom_alert(owner_id)
        if alert_data.get("mode") == "custom":
            return False, alert_data.get("text", Altruix.get_string("AUTH_SUDO_ONLY"))
            
        return False, Altruix.get_string("AUTH_SUDO_ONLY")
    
    # Mode: MENTIONED - only the specific userbot account
    if mode == ACCESS_MODE_MENTIONED:
        if mentioned_userbot_id is None:
            logger.warning("MENTIONED mode used but no mentioned_userbot_id provided")
            return False, "⛔ Error: Userbot ID tidak ditemukan"
        
        if user_id == mentioned_userbot_id:
            return True, "Access granted (MENTIONED userbot)"
            
        # ✅ Support Custom Alert Settings
        from Main.utils.file_helpers import get_user_custom_alert
        alert_data = get_user_custom_alert(owner_id)
        if alert_data.get("mode") == "custom":
            return False, alert_data.get("text", Altruix.get_string("AUTH_MENTIONED_ONLY"))
            
        return False, Altruix.get_string("AUTH_MENTIONED_ONLY")
    
    # Unknown mode - deny by default
    logger.error(f"Unknown access mode: {mode}")
    return False, f"⛔ Error: Mode akses tidak valid ({mode})"


def is_authorized_user(user_id: int, owner_id: int, sudo_users: List[int]) -> bool:
    """
    Simple check if user is authorized (owner or sudo).
    Supports dynamic cache from Altruix.
    """
    from Main.core.client import Altruix
    if user_id in Altruix._auth_users_cache:
        return True
    return user_id == owner_id or user_id in sudo_users or user_id in getattr(Altruix.config, "OWNER_USERS_ID", [])


def get_access_mode_display(mode: str, lang: str = "id") -> str:
    """
    Get display name for access mode.
    
    Args:
        mode: Access mode string
        lang: Language code (id/en)
    
    Returns:
        str: Display name for the mode
    """
    modes_id = {
        ACCESS_MODE_ALL: "Semua Orang",
        ACCESS_MODE_SUDO: "Sudo Users",
        ACCESS_MODE_OWNER: "Owner Saja",
        ACCESS_MODE_MENTIONED: "Userbot Disebutkan"
    }
    
    modes_en = {
        ACCESS_MODE_ALL: "Everyone",
        ACCESS_MODE_SUDO: "Sudo Users",
        ACCESS_MODE_OWNER: "Owner Only",
        ACCESS_MODE_MENTIONED: "Mentioned Userbot"
    }
    
    modes = modes_id if lang == "id" else modes_en
    return modes.get(mode, mode.upper())
