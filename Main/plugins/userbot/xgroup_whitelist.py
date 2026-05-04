# Main/plugins/bot/xgroup_whitelist.py
# Implementation of Group Whitelist management commands.

PLUGIN_VERSION = "0.0.111"

import time
import html
from pyrogram import Client, filters, enums
from Main import Altruix
from Main.core.decorators import log_errors, iuser_check, send_log_message

@Altruix.register_on_cmd(
    ["groupwl", "gwl", "groupwhitelist", "GROUPWL", "GWL"], 
    bot_mode_unsupported=False,
    cmd_help={
        "help": "❇️ <b>Manage Group Whitelist.</b>\nAllow members of specific groups to add their own sessions.",
        "usage": "{i}groupwl &lt;on/off/add/del/list/status&gt;",
        "example": "{i}groupwl add @groupusername",
        "user_args": {
        "on/off": "Enable or disable the global whitelist.",
        "status": "View the global whitelist status.",
        "add <id/username>": "Add a group to the whitelist.",
        "del <id/username>": "Remove a group from the whitelist.",
        "check <id/username>": "Check the status of a whitelisted group.",
        "list": "View all whitelisted groups."
        }
    }
)
@iuser_check
@log_errors
async def group_whitelist_handler(c: Client, m):
    """
    ❇️ Manage whitelisted groups.
    Usage:
    .groupwl add <id/username>
    .groupwl del <id/username>
    .groupwl list
    .groupwl check <id/username>
    .groupwl on/off
    .groupwl status
    """
    # Restrict to REAL sudo/owners (avoiding loopback from whitelisted members if desired)
    # But for now, let's follow standard sudo check unless user specifies otherwise.
    
    # ✅ REFACTOR: Use robust split for subcommands (Universal for Bot & Userbot)
    input_args = m.text.split()
    if len(input_args) < 2:
        return await m.handle_message(
            "<b>ℹ️ Group Whitelist Usage:</b>\n\n"
            "• <code>{i}groupwl add &lt;id/username&gt;</code> - Add group to whitelist\n"
            "• <code>{i}groupwl del &lt;id/username&gt;</code> - Remove group from whitelist\n"
            "• <code>{i}groupwl list</code> - List whitelisted groups\n"
            "• <code>{i}groupwl check &lt;id/username&gt;</code> - Check status\n"
            "• <code>{i}groupwl status</code> - Check system status\n"
            "• <code>{i}groupwl on/off</code> - Global Toggle"
        )

    # input_args[0] is the command (.groupwl), input_args[1] is the subcommand
    cmd = input_args[1].lower()
    
    if cmd == "on":
        await Altruix.toggle_group_wl(True)
        await send_log_message(f"🟢 <b>Group Whitelist Feature enabled globally!</b>\n<b>By:</b> <a href='tg://user?id={m.from_user.id}'>{html.escape(m.from_user.first_name)}</a>")
        return await m.handle_message("✅ <b>Group Whitelist enabled!</b>")
    
    if cmd == "off":
        await Altruix.toggle_group_wl(False)
        await send_log_message(f"🔴 <b>Group Whitelist Feature disabled globally!</b>\n<b>By:</b> <a href='tg://user?id={m.from_user.id}'>{html.escape(m.from_user.first_name)}</a>")
        return await m.handle_message("🔴 <b>Group Whitelist disabled!</b>")
        
    if cmd == "status":
        status = await Altruix.is_group_wl_enabled()
        text = "✅ <b>Enabled</b>" if status else "🔴 <b>Disabled</b>"
        return await m.handle_message(f"📊 <b>Group Whitelist Status:</b> {text}")

    if cmd == "add":
        if len(input_args) < 3:
            return await m.handle_message("❌ <b>Specify a group ID or username!</b>")
        
        target = input_args[2]
        
        # ✅ FIX: Cast numeric ID to int to avoid PHONE_NOT_OCCUPIED error
        if target.startswith("-") or target.isdigit():
            try:
                target = int(target)
            except ValueError:
                pass
                
        try:
            chat = await c.get_chat(target)
            if chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                return await m.handle_message("❌ <b>Only groups/supergroups can be whitelisted!</b>")
            
            await Altruix.add_group_wl(chat.id, chat.title)
            await send_log_message(f"➕ <b>Group Whitelisted:</b>\n<b>Title:</b> {chat.title}\n<b>ID:</b> <code>{chat.id}</code>\n<b>By:</b> <a href='tg://user?id={m.from_user.id}'>{html.escape(m.from_user.first_name)}</a>")
            return await m.handle_message(f"✅ <b>Whitelisted:</b> <code>{chat.title}</code> (<code>{chat.id}</code>)")
        except Exception as e:
            return await m.handle_message(f"❌ <b>Error:</b> <code>{str(e)}</code>")

    if cmd == "del":
        if len(input_args) < 3:
            return await m.handle_message("❌ <b>Specify a group ID or username!</b>")
        
        target = input_args[2]
        
        # ✅ FIX: Cast numeric ID to int
        if target.startswith("-") or target.isdigit():
            try:
                target_int = int(target)
            except ValueError:
                target_int = target
        else:
            target_int = target

        try:
            # Try to resolve title for a better message
            title = "Target"
            try: 
                chat = await c.get_chat(target_int)
                title = chat.title
                target_id = chat.id
            except: 
                target_id = target_int
            
            res = await Altruix.del_group_wl(target_id)
            if res:
                await send_log_message(f"➖ <b>Group Removed from Whitelist:</b>\n<b>ID:</b> <code>{target}</code>\n<b>By:</b> <a href='tg://user?id={m.from_user.id}'>{html.escape(m.from_user.first_name)}</a>")
                return await m.handle_message(f"✅ <b>Removed:</b> <code>{title}</code> (<code>{target}</code>)")
            return await m.handle_message(f"❌ <b>Group not found in whitelist:</b> <code>{target}</code>")
        except Exception as e:
            return await m.handle_message(f"❌ <b>Error:</b> <code>{str(e)}</code>")

    if cmd == "check":
        if len(input_args) < 3:
            return await m.handle_message("❌ <b>Specify a group ID or username!</b>")
        
        target = input_args[2]
        
        # ✅ FIX: Cast numeric ID to int
        if target.startswith("-") or target.isdigit():
            try:
                target_int = int(target)
            except ValueError:
                target_int = target
        else:
            target_int = target

        try:
            try: 
                chat = await c.get_chat(target_int)
                target_final = chat.id
            except: 
                target_final = target_int
            
            is_wl = await Altruix.is_group_whitelisted(target_final)
            status = "✅ <b>Whitelisted</b>" if is_wl else "❌ <b>NOT whitelisted</b>"
            return await m.handle_message(f"🔍 <b>Status for {target}:</b> {status}")
        except Exception as e:
            return await m.handle_message(f"❌ <b>Error:</b> <code>{str(e)}</code>")

    if cmd == "list":
        groups = await Altruix.get_group_wl_list()
        if not groups:
            return await m.handle_message("📭 <b>Group whitelist is empty.</b>")
            
        text = "📜 <b>Whitelisted Groups:</b>\n\n"
        for i, g in enumerate(groups, 1):
            gid = g.get("_id")
            stored_title = g.get("title", "Unknown")
            
            # ✅ FIX: Fetch live title from Telegram API to reflect name changes
            link = None
            try:
                live_chat = await c.get_chat(int(gid))
                live_title = live_chat.title or stored_title
                # Build clickable link (username > invite_link > plain)
                if live_chat.username:
                    link = f"https://t.me/{live_chat.username}"
                elif live_chat.invite_link:
                    link = live_chat.invite_link
                # Update DB if title has changed
                if live_title != stored_title:
                    await Altruix.add_group_wl(int(gid), live_title)
            except Exception:
                live_title = stored_title
            
            title = html.escape(live_title)
            if link:
                text += f"{i}. <b><a href='{link}'>{title}</a></b> (<code>{gid}</code>)\n"
            else:
                text += f"{i}. <b>{title}</b> (<code>{gid}</code>)\n"
        
        return await m.handle_message(text, disable_web_page_preview=True)

    await m.handle_message("❌ <b>Unknown command.</b> Use <code>{i}groupwl</code> for help.")
