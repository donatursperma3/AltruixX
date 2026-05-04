# Copyright (C) 2021-2025 AltruixX project
# Ported from Ultroid - UserBot
# 
# This file is a part of AltruixX ecosystem.

"""
✘ Commands Available -

• `{i}getlink`
    Get group/channel invite link and send it ONLY to this chat.
    
• `{i}getlinkf`
    Get group/channel invite link and send it to THIS chat AND the log chat.

Options for both commands:
- `r` / `request`: Enable admin approval mode (Join Request).
- `[number]`: Set usage limit (e.g. 10).
- `[string]`: Set a custom label for the link.

Examples:
.getlink
.getlinkf r 5 "Promo Link"
.getlink 10 OnlyTitle
"""

import html
import asyncio
import logging
from typing import Union
from Main import Altruix
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup
from Main.internals.settings import check_authorization, send_log_notification
from Main.core.decorators import log_errors
from pyrogram.types import LinkPreviewOptions

PLUGIN_VERSION = "0.0.5"

GETLINK_HELP = (
    "<b>🛠 Get/Create Invite Link</b>\n\n"
    "<b>Perintah:</b>\n"
    "• <code>{i}getlink</code>: Dapatkan link & kirim di chat ini saja.\n"
    "• <code>{i}getlinkf</code>: Dapatkan link, kirim di chat ini, & forward ke Log Group.\n\n"
    "<b>Argument (Opsional):</b>\n"
    "• <code>r</code> atau <code>request</code>: Mengaktifkan mode persetujuan admin (Join Request).\n"
    "• <code>[Angka]</code>: Batas maksimal penggunaan link (misal: <code>5</code>).\n"
    "• <code>[Teks]</code>: Judul/Label untuk link tersebut.\n\n"
    "<b>Contoh Penggunaan:</b>\n"
    "• <code>{i}getlinkf r 10 Group VIP</code>\n"
    "• <code>{i}getlink 5</code>\n"
    "• <code>{i}getlink Limited Link</code>"
)

async def process_getlink_logic(c: Client, m: Message, should_log: bool):
    """Core logic for retrieving or creating invite links."""
    input_text = m.text.split(None, 1)[1].strip() if len(m.text.split()) > 1 else ""
    
    request_needed = False
    usage_limit = None
    title = "Created by AltruixX"
    
    # Robust Argument Parsing
    if input_text:
        # Check for request flag
        words = input_text.split()
        if words[0].lower() in ["r", "request"]:
            request_needed = True
            input_text = " ".join(words[1:]).strip()
        
        # Check for limit
        if input_text:
            words = input_text.split()
            if words[0].isdigit():
                usage_limit = int(words[0])
                input_text = " ".join(words[1:]).strip()
            
            # Remaining is title
            if input_text:
                title = input_text

    try:
        chat = m.chat
        
        # Decide: Create New or Get Existing
        if request_needed or usage_limit or (title and title != "Created by AltruixX"):
            invite_link_obj = await c.create_chat_invite_link(
                chat_id=chat.id,
                label=title,
                usage_limit=usage_limit,
                creates_join_request=request_needed
            )
            link = invite_link_obj.invite_link
            created_new = True
        else:
            # Try to get existing primary link first
            full_chat = await c.get_chat(chat.id)
            link = full_chat.invite_link
            created_new = False
            
            if not link:
                # Fallback to creating a basic one
                invite_link_obj = await c.create_chat_invite_link(chat.id, label="AltruixX Default Link")
                link = invite_link_obj.invite_link
                created_new = True

        if link:
            # Update user message
            status_text = f"✅ <b>Invite Link:</b> {link}"
            if request_needed:
                status_text += "\n👤 <i>Admin approval: ON</i>"
            if usage_limit:
                status_text += f"\n🔢 <i>Usage Limit: {usage_limit} members</i>"
            if created_new:
                status_text += f"\n🏷 <i>Label: {title}</i>"
                
            await m.edit(status_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            
            # Handle Logging if requested
            if should_log:
                session_index = -1
                for i, client in enumerate(Altruix.clients):
                    if client.me.id == c.me.id:
                        session_index = i
                        break
                
                if session_index != -1:
                    log_data = {
                        "Chat": f"{chat.title} ({chat.id})",
                        "Link": link,
                        "Type": "Manual Request" if created_new else "Existing Link",
                        "Note": title if created_new else "Primary Link"
                    }
                    if request_needed: log_data["Mode"] = "Admin Approval Required"
                    if usage_limit: log_data["Limit"] = f"{usage_limit} uses"
                    
                    await send_log_notification(
                        c=c,
                        action="getlinkf",
                        session_index=session_index,
                        user=m.from_user,
                        success=True,
                        additional_info=log_data
                    )
        else:
            await m.edit("❌ <b>Gagal mendapatkan invite link.</b>\nPastikan Anda memiliki izin admin.", parse_mode=enums.ParseMode.HTML)

    except Exception as e:
        error_msg = str(e)
        await m.edit(f"❌ <b>Error:</b> <code>{html.escape(error_msg)}</code>", parse_mode=enums.ParseMode.HTML)
        
        if should_log:
            session_index = -1
            for i, client in enumerate(Altruix.clients):
                if client.me.id == c.me.id:
                    session_index = i
                    break
            if session_index != -1:
                await send_log_notification(
                    c=c,
                    action="getlinkf",
                    session_index=session_index,
                    user=m.from_user,
                    success=False,
                    error_msg=error_msg
                )

@Altruix.register_on_cmd(
    "getlink",
    cmd_help={
        "help": "Get or create group/channel invite link (local only).",
        "example": "{i}getlink [r] [limit] [label]",
        "full_help": GETLINK_HELP
    },
    group_only=True,
)
@log_errors
async def getlink_local_handler(c: Client, m: Message):
    await process_getlink_logic(c, m, should_log=False)

@Altruix.register_on_cmd(
    "getlinkf",
    cmd_help={
        "help": "Get or create group/channel invite link and forward to Log Group.",
        "example": "{i}getlinkf [r] [limit] [label]",
        "full_help": GETLINK_HELP
    },
    group_only=True,
)
@log_errors
async def getlink_logged_handler(c: Client, m: Message):
    await process_getlink_logic(c, m, should_log=True)

