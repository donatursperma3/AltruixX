
import pyrogram.raw.functions as functions
print("Mention functions in raw.functions:")
print([d for d in dir(functions.messages) if "mention" in d.lower()])
