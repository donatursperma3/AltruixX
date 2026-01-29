# Main/utils/topic_utils.py
import json
import os
import asyncio
from pathlib import Path
import logging
from pyrogram import Client
from typing import Optional

# Import Cache Manager
try:
    from Main.utils.cache_manager import cache_manager, init_cache
    CACHE_MANAGER_AVAILABLE = True
except ImportError:
    CACHE_MANAGER_AVAILABLE = False
    cache_manager = None

logger = logging.getLogger("altruix.topic_utils")

# Constants
CACHE_PREFIX_TOPIC = "topic:"

async def get_cache_manager():
    """Ensure cache manager is initialized."""
    if not CACHE_MANAGER_AVAILABLE:
        return None
        
    global cache_manager
    if cache_manager is None:
        # Initialize with same logic as mentions plugin
        cache_config = {
            "cache_backend": "json", 
            "json_cache_path": "topics_cache.json"
        }
        
        if os.environ.get("REDIS_URL"):
            cache_config["cache_backend"] = "redis"
            cache_config["redis_url"] = os.environ.get("REDIS_URL")
        elif os.environ.get("MONGO_URI"):
            cache_config["cache_backend"] = "mongodb"
            cache_config["mongo_uri"] = os.environ.get("MONGO_URI")
            cache_config["mongo_db"] = os.environ.get("MONGO_DB", "altruix")
            cache_config["mongo_collection"] = os.environ.get("MONGO_COLLECTION_TOPICS", "topics_cache")
            
        cache_manager = await init_cache(cache_config)
        
    return cache_manager

async def get_or_create_topic(bot_client: Client, chat_id: int, title: str, userbot_client: Optional[Client] = None):
    """
    Get existing topic ID from persistent cache or create a new one.
    
    Args:
        bot_client: Bot client (used for searching topics)
        chat_id: Chat ID where the topic should be
        title: Topic title (e.g., "pm logger", "tag logger")
        userbot_client: Userbot client (used for creating topics if bot doesn't have permission)
    
    Returns:
        topic_id or None
    """
    if not chat_id:
        return None
        
    cm = await get_cache_manager()
    cache_key = f"{CACHE_PREFIX_TOPIC}{chat_id}:{title.lower().replace(' ', '_')}"
    
    # 1. Check persistent cache first
    if cm:
        cached_id = await cm.get(cache_key)
        if cached_id:
            logger.debug(f"Topic '{title}' found in persistent cache: {cached_id}")
            return int(cached_id)
            
    # 2. Check if the chat is a forum
    try:
        chat = await bot_client.get_chat(chat_id)
        if not getattr(chat, "is_forum", False):
            logger.debug(f"Chat {chat_id} is not a forum")
            return None
    except Exception as e:
        logger.debug(f"Could not verify if chat {chat_id} is a forum: {e}")
        return None

    # Try to determine which client to use for searching/creating
    client_to_use = userbot_client if userbot_client else bot_client

    # 3. Search for existing topics with this title (if not in cache)
    try:
        logger.debug(f"Searching for existing topic '{title}' in {chat_id}")
        async for topic in client_to_use.get_forum_topics(chat_id, query=title):
            if topic.title.lower() == title.lower():
                logger.info(f"Found existing topic '{title}' with ID {topic.id}")
                
                # Save to persistent cache
                if cm:
                    await cm.set(cache_key, topic.id, ttl=31536000) # 1 year TTL
                    
                return topic.id
    except Exception as e:
        logger.debug(f"Could not search topics using {'userbot' if userbot_client else 'bot'}: {e}")

    # 4. Create new topic
    try:
        logger.info(f"Creating new topic '{title}' in {chat_id} using {'userbot' if userbot_client else 'bot'}")
        topic = await client_to_use.create_forum_topic(chat_id, title)
        topic_id = topic.id
        
        # Save to persistent cache
        if cm:
            await cm.set(cache_key, topic_id, ttl=31536000) # 1 year TTL
            
        logger.info(f"Successfully created topic '{title}' with ID {topic_id}")
        return topic_id
    except Exception as e:
        logger.warning(f"Failed to create forum topic '{title}' in {chat_id}: {e}")
        return None
