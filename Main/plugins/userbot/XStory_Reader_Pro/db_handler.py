# Main/plugins/userbot/XStory_Reader_Pro/db_handler.py
import logging
from datetime import datetime, timedelta
from Main.core.client import Altruix

PLUGIN_VERSION = "1.0.10"

logger = logging.getLogger("altruix.xstory.db")

class StoryDB:
    def __init__(self):
        self.db = Altruix.db
        self.col = self.db.make_collection("XSTORIES_PRO")
        self.wl_col = self.db.make_collection("XSTORY_WHITELIST")
        self._initialized = False

    async def _init_db(self):
        """Initialize indexes, including TTL for 24-hour expiry."""
        if self._initialized:
            return
        try:
            if hasattr(self.col, "create_index"):
                # Create TTL index on 'expiry' field
                # expireAfterSeconds=0 means it expires at the exact datetime in the field
                await self.col.create_index("expiry", expireAfterSeconds=0)
                # Index for faster lookup by peer and story id
                await self.col.create_index([("peer_id", 1), ("story_id", 1)], unique=True)
            self._initialized = True
            logger.info("XStoryDB: Indexes initialized successfully.")
        except Exception as e:
            logger.error(f"XStoryDB: Failed to initialize indexes: {e}")

    async def add_story(self, peer_id: int, story_id: int, session_id: int, media_type: str, caption: str = "", expiry_ts=None):
        """Add or update a story in the cache."""
        await self._init_db()
        
        # Calculate expiry (default 24h from now if not provided)
        if isinstance(expiry_ts, datetime):
            expiry_dt = expiry_ts
        elif expiry_ts:
            expiry_dt = datetime.fromtimestamp(expiry_ts)
        else:
            expiry_dt = datetime.utcnow() + timedelta(hours=24)

        doc = {
            "_id": f"{peer_id}_{story_id}",
            "peer_id": peer_id,
            "story_id": story_id,
            "session_id": session_id,
            "media_type": media_type,
            "caption": caption,
            "expiry": expiry_dt,
            "added_at": datetime.utcnow(),
            "is_viewed": False,
            "is_archived": False
        }

        try:
            await self.col.update_one(
                {"_id": f"{peer_id}_{story_id}"},
                {"$set": doc},
                upsert=True
            )
        except Exception as e:
            logger.error(f"XStoryDB: Error adding story: {e}")

    async def get_feed(self, limit: int = 50, skip: int = 0, filter_type: str = "all"):
        """Get paginated story feed."""
        await self._init_db()
        query = {}
        if filter_type == "archived":
            query["is_archived"] = True
        elif filter_type == "unread":
            query["is_viewed"] = False
        elif filter_type.startswith("acc_"):
            try:
                query["session_id"] = int(filter_type.split("_")[1])
            except ValueError:
                pass
            
        cursor = self.col.find(query)
        if hasattr(cursor, "sort"):
            # Motor AsyncIOMotorCursor
            cursor = cursor.sort("added_at", -1).skip(skip).limit(limit)
            return await cursor.to_list(length=limit)
        else:
            # LocalCollection._Cursor fallback
            all_results = await cursor.to_list()
            # Sort manually by added_at desc
            all_results.sort(key=lambda x: str(x.get("added_at", "")), reverse=True)
            # Manual pagination
            return all_results[skip : skip + limit]

    async def count_stories(self, filter_type: str = "all"):
        """Count total stories in feed."""
        await self._init_db()
        query = {}
        if filter_type == "archived":
            query["is_archived"] = True
        elif filter_type == "unread":
            query["is_viewed"] = False
        elif filter_type.startswith("acc_"):
            try:
                query["session_id"] = int(filter_type.split("_")[1])
            except ValueError:
                pass
        return await self.col.count_documents(query)

    async def set_viewed(self, peer_id: int, story_id: int):
        """Mark a story as viewed."""
        await self.col.update_one(
            {"peer_id": peer_id, "story_id": story_id},
            {"$set": {"is_viewed": True}}
        )

    async def toggle_archive(self, peer_id: int, story_id: int):
        """Toggle archive status of a story."""
        story = await self.col.find_one({"peer_id": peer_id, "story_id": story_id})
        if story:
            new_status = not story.get("is_archived", False)
            await self.col.update_one(
                {"peer_id": peer_id, "story_id": story_id},
                {"$set": {"is_archived": new_status}}
            )
            return new_status
        return False

    # --- Whitelist Management ---
    
    async def add_to_whitelist(self, peer_id: int, name: str = ""):
        """Add a user to the auto-archive whitelist."""
        await self.wl_col.update_one(
            {"_id": str(peer_id)},
            {"$set": {"name": name, "added_at": datetime.utcnow()}},
            upsert=True
        )

    async def remove_from_whitelist(self, peer_id: int):
        """Remove a user from the whitelist."""
        await self.wl_col.delete_one({"_id": str(peer_id)})

    async def is_whitelisted(self, peer_id: int) -> bool:
        """Check if a user is whitelisted."""
        doc = await self.wl_col.find_one({"_id": str(peer_id)})
        return doc is not None

    async def get_whitelist(self):
        """Get all whitelisted users."""
        return await self.wl_col.find({}).to_list(length=1000)

db_handler = StoryDB()
