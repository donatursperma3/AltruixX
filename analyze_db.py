
import sys
import os
import json
import asyncio
from pathlib import Path

# Add Main to path
sys.path.append(os.getcwd())

async def analyze_db():
    db_path = Path("DATABASE/altruix_local_db.json")
    if not db_path.exists():
        print("DB file not found.")
        return

    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading DB: {e}")
        return

    print("--- DB ANALYZER ---")
    for col_name, docs in data.items():
        print(f"Collection: {col_name} ({len(docs)} docs)")
        for doc_id, doc in docs.items():
            for key, val in doc.items():
                if not isinstance(val, (str, int, float, bool, list, dict, type(None))):
                    print(f"  [!] Non-serializable key found: {col_name}.{doc_id}.{key} = {type(val)}")

if __name__ == "__main__":
    asyncio.run(analyze_db())
