
import sys
import os
import asyncio
import logging

# Setup minimal logging to avoid noise
logging.basicConfig(level=logging.ERROR)

async def check_log_chat():
    from Main.config import Config
    config = Config()
    
    # Try to get from .env directly first
    import os
    env_id = os.getenv("LOG_CHAT_ID")
    print(f"DEBUG: .env LOG_CHAT_ID = {env_id}")
    
    # Try to resolve via Config (which might load from DB if initialized)
    # But initializing the full Altruix might be too much for a script.
    
if __name__ == "__main__":
    asyncio.run(check_log_chat())
