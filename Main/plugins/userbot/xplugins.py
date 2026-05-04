# xplugins.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import os
import logging
from Main import Altruix
from pyrogram import Client, filters
from Main.core.types.message import Message
from Main.core.decorators import log_errors

plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xplugins"
PLUGIN_VERSION = "0.1.0"

logger = logging.getLogger("altruix.xplugins")
logger.setLevel(logging.INFO)

@Altruix.register_on_cmd(
    ["plugup"],
    cmd_help={
        "help": "Upload a plugin file from the server's userbot or bot directory to the current chat.",
        "usage": ".plugup <plugin_name>",
        "example": ".plugup xspamxr",
        "user_args": {
            "plugin_name": "The name of the plugin file (with or without .py extension) to upload."
        },
        "detail": "This allows you to quickly share or backup your local plugin files directly through the userbot."
    }
)
@log_errors
async def plugup_cmd(c: Client, m: Message):
    args = m.text.split(" ", 1)
    if len(args) < 2:
        await m.reply("❌ <b>Usage:</b> <code>!plugup [plugin_name]</code>\n\nExample: <code>!plugup xspamxr</code>")
        return
    
    name = args[1].strip()
    if not name.endswith(".py"):
        name += ".py"
        
    # Search paths (Relative to project root, assuming cwd is project root)
    base_path = os.getcwd()
    paths = [
        os.path.join(base_path, "Main", "plugins", "userbot"),
        os.path.join(base_path, "Main", "plugins", "bot")
    ]
    
    found_path = None
    for path in paths:
        target = os.path.join(path, name)
        if os.path.exists(target):
            found_path = target
            break
            
    if found_path:
        try:
            await m.reply_document(
                document=found_path, 
                caption=f"📦 <b>Plugin:</b> <code>{name}</code>\n📂 <b>Path:</b> <code>{found_path}</code>"
            )
        except Exception as e:
            await m.reply(f"❌ Failed to upload plugin: {e}")
    else:
        await m.reply(f"❌ Plugin <code>{name}</code> not found in userbot or bot directories.")

@Altruix.register_on_cmd(
    ["pluglist"],
    cmd_help={
        "help": "List all installed userbot and bot plugins currently loaded.",
        "usage": ".pluglist",
        "example": ".pluglist",
        "detail": "Displays a complete list of all .py files in the Main/plugins/userbot and Main/plugins/bot directories."
    }
)
@log_errors
async def pluglist_cmd(c: Client, m: Message):
    base_path = os.getcwd()
    ub_path = os.path.join(base_path, "Main", "plugins", "userbot")
    bot_path = os.path.join(base_path, "Main", "plugins", "bot")
    
    ub_files = []
    if os.path.exists(ub_path):
        ub_files = sorted([f for f in os.listdir(ub_path) if f.endswith(".py") and not f.startswith("__")])
        
    bot_files = []
    if os.path.exists(bot_path):
        bot_files = sorted([f for f in os.listdir(bot_path) if f.endswith(".py") and not f.startswith("__")])
    
    msg = f"<b>📦 Altruix Plugins List</b>\n\n"
    
    msg += f"<b>👤 Userbot Plugins ({len(ub_files)}):</b>\n"
    if ub_files:
        msg += ", ".join([f"<code>{f.replace('.py', '')}</code>" for f in ub_files])
    else:
        msg += "<i>None</i>"
    msg += "\n\n"
    
    msg += f"<b>🤖 Bot Plugins ({len(bot_files)}):</b>\n"
    if bot_files:
        msg += ", ".join([f"<code>{f.replace('.py', '')}</code>" for f in bot_files])
    else:
        msg += "<i>None</i>"
        
    try:
        await m.reply(msg)
    except Exception as e:
        # Fallback if message too long
        if "MESSAGE_TOO_LONG" in str(e):
            with open("plugins_list.txt", "w") as f:
                f.write(msg.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
            await m.reply_document("plugins_list.txt", caption="📋 <b>Plugins List</b> (File too long for text)")
            os.remove("plugins_list.txt")
        else:
            await m.reply(f"❌ Error displaying list: {e}")

# Log loaded
# try:
#     Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
# except Exception:
#     pass
