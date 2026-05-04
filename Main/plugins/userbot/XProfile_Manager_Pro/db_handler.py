# Main/plugins/userbot/XProfile_Manager_Pro/db_handler.py
import logging
from Main.core.client import Altruix

logger = logging.getLogger("altruix.xprofile.db")

class ProfileDB:
    def __init__(self):
        # We use the existing DB connection from Altruix
        self.db = Altruix.db
        self.col = self.db.make_collection("PROFILE_MANAGER")

    async def get_profile_data(self, user_id: int):
        """Get profile data for a specific session."""
        data = await self.col.find_one({"_id": str(user_id)})
        if not data:
            # Default data
            return {
                "_id": str(user_id),
                "is_locked": False,
                "gender": "random", # boy, girl, random
                "usr_format": "random", # random, pattern1, pattern2, pattern3
                "avatar_src": "xsgames", # xsgames, tpdne, randomuser, pinterest
                "pinterest_keyword": None, # Manual keyword for pinterest
                "last_update": None,
                "backup": {}, # {first_name, last_name, bio}
                "persona": {}
            }
        return data

    async def update_profile_data(self, user_id: int, update_dict: dict):
        """Update profile data for a session."""
        await self.col.update_one(
            {"_id": str(user_id)},
            {"$set": update_dict},
            upsert=True
        )

    async def is_locked(self, user_id: int) -> bool:
        """Check if a session is persona-locked."""
        data = await self.get_profile_data(user_id)
        return data.get("is_locked", False)

    async def toggle_lock(self, user_id: int):
        """Toggle persona lock for a session."""
        current = await self.is_locked(user_id)
        await self.update_profile_data(user_id, {"is_locked": not current})
        return not current

    async def set_gender(self, user_id: int, gender: str):
        """Set preferred gender for a session."""
        await self.update_profile_data(user_id, {"gender": gender})

    async def set_username_format(self, user_id: int, usr_format: str):
        """Set preferred username format for a session."""
        await self.update_profile_data(user_id, {"usr_format": usr_format})

    async def set_avatar_src(self, user_id: int, src: str):
        """Set preferred avatar source for a session."""
        await self.update_profile_data(user_id, {"avatar_src": src})

    async def set_pinterest_keyword(self, user_id: int, keyword: str):
        """Set manual keyword for Pinterest scraping."""
        await self.update_profile_data(user_id, {"pinterest_keyword": keyword})

    async def save_backup(self, user_id: int, first_name: str, last_name: str, bio: str):
        """Save current profile as backup before making changes."""
        await self.update_profile_data(user_id, {
            "backup": {
                "first_name": first_name,
                "last_name": last_name,
                "bio": bio
            }
        })

    async def get_backup(self, user_id: int):
        """Get the stored backup data."""
        data = await self.get_profile_data(user_id)
        return data.get("backup", {})

    async def get_all_profiles(self):
        """Get all stored profiles."""
        return await self.col.find({}).to_list(length=1000)

db_handler = ProfileDB()
