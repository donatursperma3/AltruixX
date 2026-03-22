import json
db = json.load(open("DATABASE/altruix_local_db.json"))
print("LOAD_ENV_TO_DB:", db.get("ENV", {}).get("LOAD_ENV_TO_DB"))
