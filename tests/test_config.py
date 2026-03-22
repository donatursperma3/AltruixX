import asyncio
from Main.core.config import Config

async def dump_config():
    print("Initializing config...")
    cfg = Config()
    
    # Force DB connection
    # It might take a moment
    print("BaseConfig OWNER_USERS_ID:", cfg.OWNER_USERS_ID)
    
    owners = await cfg.get_owners()
    print("DB get_owners():", owners)
    try:
        print("cfg.OWNER_USERS_ID type:", type(cfg.OWNER_USERS_ID))
        print("cfg.OWNER_USERS_ID value:", cfg.OWNER_USERS_ID)
    except Exception as e:
        print("Error reading cfg.OWNER_USERS_ID:", e)

    sudos = await cfg.get_sudo()
    print("DB get_sudo():", sudos)

loop = asyncio.get_event_loop()
loop.run_until_complete(dump_config())
