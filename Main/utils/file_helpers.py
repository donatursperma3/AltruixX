# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


import os
import random
import string
import asyncio
import multiprocessing
from functools import wraps
from concurrent.futures.thread import ThreadPoolExecutor


executor = ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() * 5)


def run_in_exc(func_):
    @wraps(func_)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, lambda: func_(*args, **kwargs))

    return wrapper


@run_in_exc
def make_file_from_text(input_: str, file_name=None, file_suffix=".txt"):
    letters = string.ascii_lowercase
    file_name = (
        file_name or "".join(random.choice(letters) for _ in range(5)) + file_suffix
    )

    if os.path.exists(file_name):
        os.remove(file_name)
    open(file_name, "w", encoding="utf-8").write(input_)
    return file_name


@run_in_exc
def rename_file(file_name, new_file_name):
    if not os.path.exists(file_name):
        return False
    os.rename(file_name, new_file_name)
    if not os.path.exists(new_file_name):
        return False
    return True


@run_in_exc
def make_folder(folder_name=None):
    letters = string.ascii_letters
    folder_name = folder_name or "".join(random.choice(letters) for _ in range(5))
    if os.path.exists(folder_name) and not os.path.isdir(folder_name):
         os.remove(folder_name)
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    return os.path.exists(folder_name)


DATABASE_DIR = "DATABASE"

def get_db_path(filename: str) -> str:
    """Returns the path of a database file within the centralized DATABASE directory."""
    if not os.path.exists(DATABASE_DIR):
        os.makedirs(DATABASE_DIR, exist_ok=True)
    
    # Ensure filename doesn't already have the directory prefix
    if filename.startswith(f"{DATABASE_DIR}{os.sep}") or filename.startswith(f"{DATABASE_DIR}/"):
        return filename
        
    return os.path.join(DATABASE_DIR, filename)


def migrate_db_files(filenames: list):
    """Migrates specified JSON files from root to the DATABASE directory if they exist."""
    if not os.path.exists(DATABASE_DIR):
        os.makedirs(DATABASE_DIR, exist_ok=True)
        
    for filename in filenames:
        old_path = filename
        new_path = get_db_path(filename)
        
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                os.rename(old_path, new_path)
                print(f"[Migration] Moved {old_path} to {new_path}")
            except Exception as e:
                print(f"[Migration] Failed to move {old_path}: {e}")

# ====================== CUSTOM ALERT HELPERS ======================
import json
CUSTOM_ALERT_FILE = get_db_path("custom_alert_settings.json")

def get_custom_alert_data():
    if not os.path.exists(CUSTOM_ALERT_FILE):
        return {"global": {"mode": "default", "text": "⛔️ You are not allowed to use this button."}, "sessions": {}, "apply_types": {}}
    with open(CUSTOM_ALERT_FILE, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return {"global": {"mode": "default", "text": "⛔️ You are not allowed to use this button."}, "sessions": {}, "apply_types": {}}

def save_custom_alert_data(data):
    with open(CUSTOM_ALERT_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

def get_user_custom_alert(user_id):
    data = get_custom_alert_data()
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    if apply_type == "per_account" and str(user_id) in data.get("sessions", {}):
        return data["sessions"][str(user_id)]
    return data["global"]

# ====================== BUTTON STYLE HELPERS ======================
BUTTON_STYLE_FILE = get_db_path("button_style_settings.json")
_BUTTON_STYLE_CACHE = None

def get_button_style_data():
    """Returns the full button style config (cached in memory)."""
    global _BUTTON_STYLE_CACHE
    if _BUTTON_STYLE_CACHE is not None:
        return _BUTTON_STYLE_CACHE
        
    default = {"global": {"style": "DEFAULT"}, "sessions": {}, "apply_types": {}}
    if not os.path.exists(BUTTON_STYLE_FILE):
        _BUTTON_STYLE_CACHE = default
        return default
        
    with open(BUTTON_STYLE_FILE, "r", encoding="utf-8") as f:
        try: 
            _BUTTON_STYLE_CACHE = json.load(f)
            return _BUTTON_STYLE_CACHE
        except: 
            _BUTTON_STYLE_CACHE = default
            return default

def save_button_style_data(data):
    global _BUTTON_STYLE_CACHE
    _BUTTON_STYLE_CACHE = data
    with open(BUTTON_STYLE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_user_button_style(user_id):
    """Resolve the ButtonStyle enum for a given session user_id."""
    from pyrogram.enums import ButtonStyle
    STYLE_MAP = {
        "DEFAULT": ButtonStyle.DEFAULT,
        "PRIMARY": ButtonStyle.PRIMARY,
        "DANGER": ButtonStyle.DANGER,
        "SUCCESS": ButtonStyle.SUCCESS,
    }
    data = get_button_style_data()
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    if apply_type == "per_account" and str(user_id) in data.get("sessions", {}):
        style_key = data["sessions"][str(user_id)].get("style", "DEFAULT")
    else:
        style_key = data["global"].get("style", "DEFAULT")
    return STYLE_MAP.get(style_key, ButtonStyle.DEFAULT)
