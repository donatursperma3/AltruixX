# Main/plugins/userbot/XStory_Reader_Pro/manager.py
import asyncio
import logging
import os
from datetime import datetime
from pyrogram import Client, enums
from pyrogram.errors import FloodWait
from Main.core.client import Altruix
from .db_handler import db_handler

PLUGIN_VERSION = "1.0.0"

logger = logging.getLogger("altruix.xstory.manager")

class StoryManager:
    def __init__(self):
        self.is_archiving = False
        self._archive_lock = asyncio.Lock()

    async def fetch_global_feed(self):
        """Fetch stories from all active sessions and sync to DB."""
        for client in Altruix.clients:
            if not client.is_connected:
                continue
            
            try:
                async for story in client.get_all_stories():
                    peer_id = None
                    if getattr(story, "chat", None):
                        peer_id = story.chat.id
                    elif getattr(story, "from_user", None):
                        peer_id = story.from_user.id
                    elif getattr(story, "sender_chat", None):
                        peer_id = story.sender_chat.id
                        
                    if not peer_id:
                        continue
                        
                    media_type = "video" if getattr(story, "video", None) else "photo"
                    await db_handler.add_story(
                        peer_id=peer_id,
                        story_id=story.id,
                        session_id=client.me.id,
                        media_type=media_type,
                        caption=getattr(story, "caption", "") or "",
                        expiry_ts=getattr(story, "expire_date", None)
                    )
            except Exception as e:
                logger.error(f"StoryManager: Error fetching feed for {client.name}: {e}")

    async def ghost_read(self, client: Client, peer_id: int, story_id: int):
        """Retrieve story media without marking it as read."""
        try:
            # We just fetch the story object. 
            # Crucially, we DO NOT call client.read_stories()
            story = await client.get_stories(peer_id, story_id)
            return story
        except Exception as e:
            logger.error(f"StoryManager: Ghost read failed: {e}")
            return None

    async def download_story(self, client: Client, peer_id: int, story_id: int, path: str = "cache/stories/"):
        """Download story media to local storage."""
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            
        try:
            story = await client.get_stories(peer_id, story_id)
            if not story:
                return None
            
            ext = ".mp4" if getattr(story, "video", None) else ".jpg"
            file_path = await client.download_media(story, file_name=f"{path}{peer_id}_{story_id}{ext}")
            return file_path
        except FloodWait as e:
            await asyncio.sleep(e.value)
            return await self.download_story(client, peer_id, story_id, path)
        except Exception as e:
            logger.error(f"StoryManager: Download failed: {e}")
            return None

    async def auto_archive_task(self):
        """Background task to monitor whitelist and auto-archive."""
        if self.is_archiving:
            return
        
        async with self._archive_lock:
            self.is_archiving = True
            logger.info("StoryManager: Auto-Archiver task started.")
            
            while self.is_archiving:
                try:
                    whitelist = await db_handler.get_whitelist()
                    for user in whitelist:
                        peer_id = int(user["_id"])
                        # Find an active client to check stories
                        for client in Altruix.clients:
                            if not client.is_connected: continue
                            
                            try:
                                async for story in client.get_chat_stories(peer_id):
                                    # Check if already archived
                                    if not await self.is_story_processed(peer_id, story.id):
                                        logger.info(f"Auto-Archiver: Found new story {story.id} from {peer_id}")
                                        
                                        # Download
                                        file_path = await self.download_story(client, peer_id, story.id)
                                        if file_path:
                                            # Store in DB
                                            await db_handler.add_story(
                                                peer_id=peer_id,
                                                story_id=story.id,
                                                session_id=client.me.id,
                                                media_type="video" if getattr(story, 'video', None) else "photo",
                                                caption=getattr(story, 'caption', '') or "",
                                                expiry_ts=getattr(story, 'expire_date', None)
                                            )
                                            # Mark as archived in DB
                                            await db_handler.toggle_archive(peer_id, story.id)
                                            
                                            # Hook for Trimmer (Optional)
                                            await self.trigger_trimmer_hook(file_path)
                            except Exception as e:
                                logger.debug(f"StoryManager: Auto-Archiver failed to get stories for {peer_id}: {e}")
                                        
                except Exception as e:
                    logger.error(f"StoryManager: Auto-Archiver loop error: {e}")
                
                await asyncio.sleep(300) # Check every 5 minutes

    async def is_story_processed(self, peer_id: int, story_id: int) -> bool:
        """Check if a story has already been handled."""
        # Check in DB if it exists and is archived
        # This is a simplified check
        return False # Placeholder

    async def trigger_trimmer_hook(self, file_path: str):
        """Trigger XTrimmer plugin if available."""
        # Placeholder for integration with XTrimmer
        pass

    def start_background_tasks(self):
        """Start all background loops."""
        asyncio.create_task(self.auto_archive_task())

story_manager = StoryManager()
