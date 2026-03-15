import asyncio
from Main.core.client import Altruix

async def test_inline_error():
    if not Altruix.clients:
        print("No clients connected.")
        return
        
    client = Altruix.clients[0]
    bot_username = await Altruix.bot_manager.get_bot_username(client.me.id)
    chat_id = client.me.id
    user_id = client.me.id
    
    print(f"Testing against Bot: {bot_username}")
    
    # Simulate the exact query that fails in rap_executor when edit is ON
    slug = "test-slug-123"
    i = 0
    lines_per_msg = 1
    
    # This is the exact string currently used:
    inline_query = f"line_{slug}_{i}_s{lines_per_msg}_e_uid{user_id}_cid{chat_id}"
    print(f"Query length: {len(inline_query)} | Query: {inline_query}")
    
    try:
        results = await client.get_inline_bot_results(bot_username, inline_query)
        print(f"Success! Got {len(results.results)} results.")
    except Exception as e:
        import traceback
        traceback.print_exc()

# Since Altruix clients need the event loop, we'll run this as a standalone script
# that initializes the client just enough to test.
