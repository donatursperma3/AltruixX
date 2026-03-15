
import os
import sys
import asyncio
import logging
from pathlib import Path

# Setup basic logging to console
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("Diagnostics")

async def check_imports():
    logger.info("Checking critical imports...")
    try:
        import aiosqlite
        logger.info("✅ aiosqlite imported successfully")
        
        from PIL import Image
        logger.info("✅ Pillow imported successfully")
        
        import moviepy.editor
        logger.info("✅ MoviePy imported successfully")
        
        from googletrans import Translator
        logger.info("✅ googletrans imported successfully")
        
        import pycryptodome
        logger.info("✅ pycryptodome imported successfully")
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return False
    return True

async def check_db():
    logger.info("Checking SQLite connectivity on this mount...")
    db_path = "DATABASE/diag_test.db"
    if not os.path.exists("DATABASE"):
        os.makedirs("DATABASE")
        
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            logger.info(f"Connecting to {db_path}...")
            await db.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")
            await db.execute("INSERT INTO test DEFAULT VALUES")
            await db.commit()
            logger.info("✅ SQLite write successful")
    except Exception as e:
        logger.error(f"❌ SQLite operation failed: {e}")
        return False
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
    return True

async def main():
    logger.info("--- Altruix Startup Diagnostics ---")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"CWD: {os.getcwd()}")
    
    success = await check_imports()
    if success:
        success = await check_db()
        
    if success:
        logger.info("--- Diagnostics complete: Environment looks OK ---")
    else:
        logger.error("--- Diagnostics failed: Issues found ---")

if __name__ == "__main__":
    asyncio.run(main())
