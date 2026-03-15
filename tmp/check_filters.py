
import pyrogram.raw.types as types
filters = [d for d in dir(types) if "Filter" in d]
for f in filters:
    if "Mention" in f:
        print(f)
