
import sys
import os
import asyncio
import logging

# Set up Altruix environment
sys.path.append(os.getcwd())

async def check_db_config():
    from Main.config import Config
    config = Config()
    
    # Manually check DB if possible
    try:
        from Main.core.ext.upm import MongoDB
        if config.DB_URI:
            db = MongoDB(config.DB_URI)
            # Find the env variable in DB
            # Collection name is usually 'env' or similar
            col = db.make_collection("env")
            doc = await col.find_one({"_id": "LOG_CHAT_ID"})
            if doc:
                print(f"DEBUG: DB LOG_CHAT_ID = {doc.get('value')}")
            else:
                print("DEBUG: DB LOG_CHAT_ID not found")
        else:
             print("DEBUG: No DB_URI found")
    except Exception as e:
        print(f"DEBUG: Error checking DB: {e}")

if __name__ == "__main__":
    asyncio.run(check_db_config())
