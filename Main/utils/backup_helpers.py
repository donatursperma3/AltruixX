# Main/utils/backup_helpers.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

import os
import shutil
import asyncio
import logging
from datetime import datetime
from Main.utils.file_helpers import get_db_path

logger = logging.getLogger("altruix.backup")

async def create_db_zip() -> str:
    """
    Creates a ZIP archive of the DATABASE directory.
    Returns:
        str: Absolute path to the created ZIP file.
    """
    db_dir = get_db_path("") # This should point to the DATABASE directory
    if not os.path.exists(db_dir):
        logger.error(f"DATABASE directory does not exist: {db_dir}")
        return ""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"altruix_db_backup_{timestamp}"
    zip_path = os.path.join(os.getcwd(), zip_name) # Temporarily in root
    
    try:
        # Run shutil.make_archive in a thread to keep async happy
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: shutil.make_archive(zip_path, 'zip', db_dir))
        return f"{zip_path}.zip"
    except Exception as e:
        logger.error(f"Failed to create database backup: {e}")
        return ""

async def upload_db_backup(client, chat_id: int):
    """
    Creates and uploads a database backup to the specified chat.
    
    Args:
        client: The pyrogram client to use (usually the bot).
        chat_id: The ID of the log chat.
    """
    from Main import Altruix
    
    zip_file = await create_db_zip()
    if not zip_file:
        return False
    
    try:
        caption = Altruix.get_string("backup_caption").format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            Altruix.__version__
        )
        
        await client.send_document(
            chat_id,
            zip_file,
            caption=caption
        )
        return True
    except Exception as e:
        logger.error(f"Failed to upload database backup: {e}")
        return False
    finally:
        if os.path.exists(zip_file):
            os.remove(zip_file)
