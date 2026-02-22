# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

PLUGIN_VERSION = "0.1.0"
import os
import html
from Main import Altruix
from pyrogram import Client, filters
from Main.core.types.message import Message
from Main.core.decorators import log_errors

@Altruix.register_on_cmd(
    ["findaddon", "searchaddon", "saddon"],
    cmd_help={
        "help": "Search for Ultroid addons and commands.",
        "usage": ".findaddon <query>",
        "example": ".findaddon fun",
        "detail": "Searches through installed Ultroid addons' filenames, documentation, and specific commands for matches."
    },
)
@log_errors
async def find_addon_cmd(c: Client, m: Message):
    query = m.user_input.lower() if m.user_input else ""
    if not query:
        return await m.reply("❌ <b>Gagal:</b> Masukkan kata kunci pencarian.\n<i>Example: .findaddon fun</i>")
        
    msg = await m.handle_message("PROCESSING")
    results = []
    
    # Search in cmd_list and _module_helps
    for plugin_name, category in Altruix.plugin_categories.items():
        if category != "ultroid":
            continue
            
        plugin_matches = False
        if query in plugin_name.lower():
            plugin_matches = True
            
        doc = Altruix._module_helps.get(plugin_name, "").lower()
        if query in doc:
            plugin_matches = True
            
        # Search commands in that plugin
        cmds = Altruix.cmd_list.get(plugin_name, [])
        matching_cmds = []
        for cmd_data in cmds:
            command_triggers = cmd_data.get("commands", [])
            help_text = cmd_data.get("help", "").lower()
            
            if any(query in str(t).lower() for t in command_triggers) or (query in help_text):
                trig_str = "/".join(f"<code>{t}</code>" for t in command_triggers)
                matching_cmds.append(trig_str)
                plugin_matches = True
                
        if plugin_matches:
            results.append({
                "name": plugin_name,
                "doc": Altruix._module_helps.get(plugin_name, "No documentation"),
                "cmds": matching_cmds
            })

    if not results:
        return await msg.edit(f"🔍 <b>Pencarian:</b> <code>{query}</code>\n❌ Tidak ditemukan addon yang cocok.")
        
    res = f"🔍 <b>Hasil Pencarian Addon:</b> <code>{query}</code>\n\n"
    for item in results:
        res += f"📦 <b>Addon:</b> <code>{item['name']}</code>\n"
        if item['cmds']:
            res += f" ➥ <b>Cmds:</b> {', '.join(item['cmds'])}\n"
        
        # Clean doc (max 100 chars)
        clean_doc = item['doc'].split('\n')[0][:100]
        if len(item['doc']) > 100: clean_doc += "..."
        res += f" ➥ <b>Info:</b> <i>{html.escape(clean_doc)}</i>\n\n"
        
    # Split if too long
    if len(res) > 4000:
        res = res[:4000] + "\n\n...(Hasil lainnya dipotong karena terlalu panjang)"
        
    await msg.edit(res)

@Altruix.register_on_cmd(
    ["addonlist"],
    cmd_help={
        "help": "List all installed Ultroid addons.",
        "usage": ".addonlist",
        "example": ".addonlist",
        "detail": "Displays a complete list of all currently loaded Ultroid addons."
    },
)
@log_errors
async def list_addons_cmd(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    # Identify Ultroid category from client
    addons = [p for p, cat in Altruix.plugin_categories.items() if cat == "ultroid"]
    addons.sort()
    
    if not addons:
        return await msg.edit("📭 <b>Tidak ada Ultroid addon yang terinstal.</b>")
        
    res = f"📦 <b>Ultroid Addons List ({len(addons)}):</b>\n\n"
    res += ", ".join([f"<code>{a}</code>" for a in addons])
    
    if len(res) > 4096:
        # Save to file
        with open("addons_list.txt", "w", encoding="utf-8") as f:
            f.write(res.replace("<code>", "").replace("</code>", "").replace("<b>", "").replace("</b>", ""))
        await msg.delete()
        return await c.send_document(m.chat.id, "addons_list.txt", caption=f"📋 <b>Addons List ({len(addons)})</b>")
        
    await msg.edit(res)
