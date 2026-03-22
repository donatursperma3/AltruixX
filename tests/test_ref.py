import asyncio
from Main.core.config import Config

async def check():
    cfg = Config()
    print("Init OWNER_USERS_ID:", cfg.OWNER_USERS_ID)
    print("Init SUDO_USERS_ID:", getattr(cfg, "SUDO_USERS_ID", None))
    print("Are they same object?", id(cfg.OWNER_USERS_ID) == id(getattr(cfg, "SUDO_USERS_ID", None)))

    # load vars from db
    await cfg.load_vars_from_db()
    print("After load_vars OWNER_USERS_ID:", cfg.OWNER_USERS_ID)
    print("After load_vars SUDO_USERS_ID:", getattr(cfg, "SUDO_USERS_ID", None))
    print("Are they same object?", id(cfg.OWNER_USERS_ID) == id(getattr(cfg, "SUDO_USERS_ID", None)))

    owners = await cfg.get_owners()
    sudos = await cfg.get_sudo()
    
    print("After getters OWNER_USERS_ID:", cfg.OWNER_USERS_ID)
    print("After getters SUDO_USERS_ID:", cfg.SUDO_USERS_ID)

asyncio.get_event_loop().run_until_complete(check())
