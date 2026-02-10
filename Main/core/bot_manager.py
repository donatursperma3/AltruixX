
# Main/core/bot_manager.py
import asyncio
import logging
from pyrogram import Client
from typing import Dict, Optional
# from Main import Altruix # Removed to avoid circular import

logger = logging.getLogger("altruix.bot_manager")

class BotManager:
    def __init__(self, altruix_client):
        self.altruix = altruix_client
        self.custom_bots: Dict[int, Client] = {} # user_id -> Client
        self._bot_tokens: Dict[int, str] = {} # user_id -> token

    # ... (rest of methods use self.altruix)
    
    async def initialize(self):
        """Load custom bots from database/config."""
        try:
            # Load tokens from DB
            # We assume a collection "custom_bots" or similar
            if hasattr(self.altruix, 'db') and hasattr(self.altruix.db, 'env_col'):
                # Using a separate collection if possible, or just a key in env
                # For simplicity and to avoid schema changes, let's use a new collection 'custom_bots'
                # if db allows make_collection
                if hasattr(self.altruix.db, 'make_collection'):
                    col = self.altruix.db.make_collection("custom_bots")
                    async for doc in col.find({}):
                        user_id = doc.get("_id")
                        token = doc.get("token")
                        if user_id and token:
                            await self.start_custom_bot(user_id, token)
            else:
                logger.warning("DB not available for BotManager")
        except Exception as e:
            logger.error(f"Failed to initialize BotManager: {e}")

    async def save_token(self, user_id: int, token: str):
        if hasattr(self.altruix, 'db') and hasattr(self.altruix.db, 'make_collection'):
            col = self.altruix.db.make_collection("custom_bots")
            await col.find_one_and_update(
                {"_id": user_id},
                {"$set": {"token": token}},
                upsert=True
            )

    async def delete_token(self, user_id: int):
        if hasattr(self.altruix, 'db') and hasattr(self.altruix.db, 'make_collection'):
            col = self.altruix.db.make_collection("custom_bots")
            await col.find_one_and_delete({"_id": user_id})

    async def start_custom_bot(self, user_id: int, token: str) -> bool:
        """Start a custom bot for a user session."""
        try:
            # ✅ IDEMPOTENCY CHECK: If already running with same token, skip
            if user_id in self.custom_bots:
                existing_bot = self.custom_bots[user_id]
                # Check if connected and token matches
                if existing_bot.is_connected and self._bot_tokens.get(user_id) == token:
                    # logger.info(f"Custom bot for {user_id} is already running. Skipping...")
                    return True
                
                # If different token or not connected, restart
                await self.stop_custom_bot(user_id)

            logger.info(f"Starting custom bot for user {user_id}...")
            
            # Initialize Client
            api_id = self.altruix.config.API_ID
            api_hash = self.altruix.config.API_HASH
            
            if not api_id or not api_hash:
                logger.error("API_ID or API_HASH missing")
                return False

            # ✅ USE FILE STORAGE for stability (fixes 'Closed database' error)
            bot_client = Client(
                name=f"custom_bot_{user_id}",
                api_id=api_id,
                api_hash=api_hash,
                bot_token=token,
                workdir="cache", # Use file cache like main sessions
                loop=self.altruix.loop
            )

            await bot_client.start()
            bot_client.myself = bot_client.me
            self.custom_bots[user_id] = bot_client
            self._bot_tokens[user_id] = token
            
            if hasattr(self.altruix, 'bot'):
                 for group, handlers in self.altruix.bot.dispatcher.groups.items():
                    for handler in handlers:
                        bot_client.add_handler(handler, group)

            logger.info(f"✅ Custom bot started for {user_id}: {bot_client.me.username}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start custom bot for {user_id}: {e}")
            return False

    async def stop_custom_bot(self, user_id: int):
        if user_id in self.custom_bots:
            client = self.custom_bots[user_id]
            try:
                if client.is_connected:
                    await client.stop()
            except Exception as e:
                logger.warning(f"Error stopping custom bot for {user_id}: {e}")
            finally:
                # Remove from dicts
                self.custom_bots.pop(user_id, None)
                self._bot_tokens.pop(user_id, None)

    def get_bot(self, user_id: int) -> Client:
        """Get custom bot for user, or fallback to default Altruix.bot."""
        return self.custom_bots.get(user_id, getattr(self.altruix, 'bot', None))

    def get_bot_username(self, user_id: int) -> str:
        bot = self.get_bot(user_id)
        if bot and bot.me:
            return bot.me.username
        
        # Fallback to Altruix.bot info
        if hasattr(self.altruix, 'bot_info') and self.altruix.bot_info:
            return self.altruix.bot_info.username
        return "Unknown"

