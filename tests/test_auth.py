import asyncio
from Main import Altruix

async def test_auth():
    print("Testing Owner Auth...")
    owners = await Altruix.config.get_owners()
    sudos = await Altruix.config.get_sudo()
    print("OWNER_USERS_ID:", Altruix.config.OWNER_USERS_ID)
    print("SUDO_USERS_ID:", Altruix.config.SUDO_USERS_ID)
    
    await Altruix.refresh_sudo_cache()
    print("db_sudo_users:", Altruix.db_sudo_users)
    print("_auth_users_cache:", Altruix._auth_users_cache)
    
    # Test a dummy owner user_id (e.g. your ID)
    if owners:
        owner_id = owners[0]
        res = await Altruix.is_sudo(owner_id)
        print(f"is_sudo({owner_id}):", res)
    else:
        print("No owners found.")

loop = asyncio.get_event_loop()
loop.run_until_complete(test_auth())
