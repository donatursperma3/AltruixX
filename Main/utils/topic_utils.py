# Main/utils/topic_utils.py
import json
import os
from pathlib import Path
import logging
from pyrogram import Client
from typing import Optional

logger = logging.getLogger("altruix.topic_utils")

CACHE_FILE = Path("topic_cache.json")

def load_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save topic cache: {e}")

async def get_or_create_topic(bot_client: Client, chat_id: int, title: str, userbot_client: Optional[Client] = None):
    """
    Get existing topic ID from cache or create a new one.
    
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
        
    cache = load_cache()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in cache:
        cache[chat_id_str] = {}
    
    # Check cache first
    if title in cache[chat_id_str]:
        logger.debug(f"Topic '{title}' found in cache: {cache[chat_id_str][title]}")
        return cache[chat_id_str][title]
    
    # Check if the chat is a forum
    try:
        chat = await bot_client.get_chat(chat_id)
        if not getattr(chat, "is_forum", False):
            logger.debug(f"Chat {chat_id} is not a forum")
            return None
    except Exception as e:
        logger.debug(f"Could not verify if chat {chat_id} is a forum: {e}")
        return None

    # Search for existing topics with this title
    try:
        logger.debug(f"Searching for existing topic '{title}' in {chat_id}")
        async for topic in bot_client.get_forum_topics(chat_id, query=title):
            if topic.title.lower() == title.lower():
                logger.info(f"Found existing topic '{title}' with ID {topic.id}")
                cache[chat_id_str][title] = topic.id
                save_cache(cache)
                return topic.id
    except Exception as e:
        logger.debug(f"Could not search topics: {e}")

    # Try to create it using userbot if available, otherwise use bot
    client_to_use = userbot_client if userbot_client else bot_client
    
    try:
        logger.info(f"Creating new topic '{title}' in {chat_id} using {'userbot' if userbot_client else 'bot'}")
        topic = await client_to_use.create_forum_topic(chat_id, title)
        topic_id = topic.id
        cache[chat_id_str][title] = topic_id
        save_cache(cache)
        logger.info(f"Successfully created topic '{title}' with ID {topic_id}")
        return topic_id
    except Exception as e:
        logger.warning(f"Failed to create forum topic '{title}' in {chat_id}: {e}")
        return None
