import asyncio
import os
import sys

# Append Main path to ensure imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

async def check_db():
    try:
        from Main.core.bot import AltruixBase
        from Main.utils.database import MongoDB
        
        # Manually init db to peek inside
        db = MongoDB()
        await db._init()
        
        # Inline col
        docs = []
        if db.type != "mongodb":
            docs = db.inline_col.all()
        else:
            cursor = db.inline_col.find({})
            async for doc in cursor:
                docs.append(doc)
                
        print(f"Total inline cache entries: {len(docs)}")
        has_chat_title = 0
        for i, d in enumerate(docs[:10]):
            print(f"[{i}] _id: {d.get('_id')}")
            print(f"      chat_id: {d.get('chat_id')}")
            print(f"      chat_title: {d.get('chat_title', 'MISSING')}")
            if "chat_title" in d:
                has_chat_title += 1
                
        print(f"\nStats: {has_chat_title} out of {min(10, len(docs))} sampled have chat_title")
    except Exception as e:
        print(f"Error checking DB: {e}")

if __name__ == "__main__":
    asyncio.run(check_db())
