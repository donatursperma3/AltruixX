
import pyrogram
from pyrogram import Client
print("Methods in Client:")
print([d for d in dir(Client) if "mention" in d.lower()])
