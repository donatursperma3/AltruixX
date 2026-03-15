
import pyrogram.raw.functions as functions
import pyrogram.raw.types as types
import inspect

print(inspect.signature(functions.messages.SearchGlobal))
print("\nEmpty Peer type:")
print(types.InputPeerEmpty)
