import asyncio
from Main import Altruix

async def dump_vars():
    owners = await Altruix.config.get_owners()
    print("Database Owners:", owners)
    print("Config OWNER_USERS_ID:", Altruix.config.OWNER_USERS_ID)
    print("Sudos:", await Altruix.config.get_sudo())
    await Altruix.refresh_sudo_cache()
    print("db_sudo_users:", Altruix.db_sudo_users)
    print("auth_users_cache:", Altruix._auth_users_cache)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(dump_vars())
