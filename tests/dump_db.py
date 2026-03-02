
import asyncio
import os
import sys
from os import getenv
from dotenv import load_dotenv

load_dotenv()

# Add the project root to sys.path
sys.path.append(os.getcwd())

async def dump():
    print("--- DB DUMP START ---")
    try:
        db_uri = getenv("DB_URI")
        if db_uri:
            print(f"Detected MongoDB: {db_uri[:20]}...")
            from Main.core.database import MongoDB
            db = MongoDB(db_uri)
            env_col = db.env_col
        else:
            print("Detected LocalDatabase")
            from Main.core.database import LocalDatabase
            db = LocalDatabase()
            env_col = db.env_col
        
        # Manually load data if it's LocalDatabase (though it loads in __init__)
        
        async for var in env_col.find({}):
            print(f"KEY: {var.get('_id')} | VALUE: {var.get('env_value')}")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {e}")
    print("--- DB DUMP END ---")

if __name__ == "__main__":
    asyncio.run(dump())
