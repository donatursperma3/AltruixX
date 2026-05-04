
import asyncio
import os
import sys

# Add the workspace root to sys.path
sys.path.append(os.getcwd())

from Main import Altruix

async def check_bot_access():
    print("Checking bot access to LOG_CHAT_ID...")
    try:
        # Altruix instance might not be fully initialized or connected
        # But we can check the config
        log_chat_id = Altruix.config.digit_wrap(os.getenv("LOG_CHAT_ID"))
        print(f"LOG_CHAT_ID from .env: {log_chat_id}")
        
        if not log_chat_id:
            print("LOG_CHAT_ID is not set in .env")
            return

        # We can't easily start the bot here without interference
        # But we can check if Altruix.log_chat is set (if it was initialized)
        print(f"Altruix.log_chat value: {getattr(Altruix, 'log_chat', 'Not set')}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_bot_access())
