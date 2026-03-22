
import os
from pathlib import Path

def check_env():
    # Read .env manually
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("LOG_CHAT_ID"):
                    print(f"DEBUG: .env {line.strip()}")
    else:
        print("DEBUG: .env not found")
    
    # Also check os.environ (if loaded by process)
    print(f"DEBUG: os.environ LOG_CHAT_ID = {os.environ.get('LOG_CHAT_ID')}")

if __name__ == "__main__":
    check_env()
