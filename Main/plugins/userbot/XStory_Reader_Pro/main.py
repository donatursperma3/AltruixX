# Main/plugins/userbot/XStory_Reader_Pro/main.py
import asyncio
import logging
from pyrogram import Client, filters
from Main.core.client import Altruix
from Main.core.decorators import log_errors, iuser_check
from Main.core.types.message import Message as AltruixMessage

# Modular Imports
from .db_handler import db_handler, PLUGIN_VERSION
from .manager import story_manager
from .ui_builder import build_dashboard

logger = logging.getLogger("altruix.xstory")

# --- Background Task State ---
_bg_started = False

async def _ensure_background_tasks():
    """Lazily start background tasks on first use."""
    global _bg_started
    if not _bg_started:
        _bg_started = True
        story_manager.start_background_tasks()
        logger.info("XStory_Reader_Pro: Background tasks initialized.")

# --- COMMAND HANDLER ---

@Altruix.register_on_cmd(
    ["story", "sfeed"],
    cmd_help={
        "help": "Membuka Dashboard Story Reader Pro.",
        "usage": ".story",
        "detail": (
            "Dashboard interaktif untuk memantau story dari semua akun yang terhubung.\n"
            "Mendukung Ghost Viewing (melihat tanpa centang dua), auto-archiving, "
            "dan filter kategori (Contacts, Channels, Close Friends)."
        ),
        "example": ".story"
    },
)
@log_errors
@iuser_check
async def xstory_cmd_handler(c: Client, m: AltruixMessage):
    """Command to launch the story dashboard."""
    # Ensure background tasks are running
    await _ensure_background_tasks()
    
    try:
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        # We trigger the bot assistant via inline query
        results = await c.get_inline_bot_results(bot_username, f"xstory_main_{c.me.id}")
        await c.send_inline_bot_result(
            chat_id=m.chat.id,
            query_id=results.query_id,
            result_id=results.results[0].id,
            reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id,
        )
        await m.delete_if_self()
    except Exception as e:
        logger.error(f"Failed to send inline story dashboard: {e}")
        # Fallback to normal reply if inline fails
        total_stories = await db_handler.count_stories()
        text = (
            f"<blockquote expandable>"
            f"<b>📸 Story Reader Pro Dashboard [v{PLUGIN_VERSION}]</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Stories Cached: <code>{total_stories}</code>\n"
            "<i>Use the menu below to manage your feed:</i>"
            f"</blockquote>"
        )
        # Fetch initial stories for dashboard
        stories = await db_handler.get_feed(limit=5)
        await m.reply_msg(text, reply_markup=build_dashboard(m.from_user.id, stories, 1, 1))

# --- STORY FETCH COMMAND ---

@Altruix.register_on_cmd(
    ["sfetch"],
    cmd_help={
        "help": "Fetch & cache stories dari semua akun secara manual.",
        "usage": ".sfetch [user_id]",
        "detail": (
            "Memaksa pengambilan story dari semua sesi atau dari user tertentu, "
            "lalu menyimpannya ke cache MongoDB."
        ),
        "example": ".sfetch 123456789"
    },
)
@log_errors
@iuser_check
async def sfetch_cmd_handler(c: Client, m: AltruixMessage):
    """Manually fetch and cache stories from all sessions or a specific user."""
    await _ensure_background_tasks()
    
    target = m.user_input.strip() if m.user_input else None
    status_msg = await m.reply_msg("<b>🔄 Fetching stories...</b>")
    
    cached_count = 0
    
    for client in Altruix.clients:
        if not client.is_connected:
            continue
        try:
            if target and target.lstrip("-").isdigit():
                # Fetch stories from a specific peer
                peer_id = int(target)
                try:
                    async for story in client.get_chat_stories(peer_id):
                        media_type = "video" if story.video else "photo"
                        await db_handler.add_story(
                            peer_id=peer_id,
                            story_id=story.id,
                            session_id=client.me.id,
                            media_type=media_type,
                            caption=story.caption or "",
                            expiry_ts=getattr(story, "expire_date", None)
                        )
                        cached_count += 1
                except Exception as e:
                    logger.warning(f"Failed to fetch stories from {peer_id} via {client.me.id}: {e}")
            else:
                # Broad fetch: get all stories from the feed
                try:
                    async for story in client.get_all_stories():
                        peer_id = None
                        if getattr(story, "chat", None):
                            peer_id = story.chat.id
                        elif getattr(story, "from_user", None):
                            peer_id = story.from_user.id
                        elif getattr(story, "sender_chat", None):
                            peer_id = story.sender_chat.id
                            
                        if not peer_id:
                            continue
                            
                        media_type = "video" if getattr(story, "video", None) else "photo"
                        await db_handler.add_story(
                            peer_id=peer_id,
                            story_id=story.id,
                            session_id=client.me.id,
                            media_type=media_type,
                            caption=getattr(story, "caption", "") or "",
                            expiry_ts=getattr(story, "expire_date", None)
                        )
                        cached_count += 1
                except Exception as e:
                    logger.warning(f"Failed broad fetch via {client.me.id}: {e}")
        except Exception as e:
            logger.error(f"Session error during fetch: {e}")
    
    await status_msg.edit(
        f"<b>✅ Fetch Complete</b>\n"
        f"Stories cached: <code>{cached_count}</code>"
    )

# --- WHITELIST COMMAND ---

@Altruix.register_on_cmd(
    ["swl", "storywhitelist"],
    cmd_help={
        "help": "Kelola whitelist untuk auto-archive story.",
        "usage": ".swl <add/remove/list> [user_id]",
        "detail": "Menambah, menghapus, atau melihat daftar user yang akan di-auto-archive storynya.",
        "example": ".swl add 123456789",
        "user_args": {
            "add <user_id>": "Tambahkan user ke whitelist.",
            "remove <user_id>": "Hapus user dari whitelist.",
            "list": "Tampilkan semua user yang di-whitelist.",
        }
    },
)
@log_errors
@iuser_check
async def swl_cmd_handler(c: Client, m: AltruixMessage):
    """Manage the auto-archive whitelist."""
    args = m.user_input.strip().split() if m.user_input else []
    
    if not args:
        return await m.reply_msg("<b>Usage:</b> <code>.swl add/remove/list [user_id]</code>")
    
    action = args[0].lower()
    
    if action == "add" and len(args) > 1:
        peer_id = int(args[1])
        # Try to resolve name
        name = ""
        for client in Altruix.clients:
            try:
                user = await client.get_users(peer_id)
                name = f"{user.first_name} {user.last_name or ''}".strip()
                break
            except Exception:
                continue
        await db_handler.add_to_whitelist(peer_id, name)
        await m.reply_msg(f"✅ <b>{name or peer_id}</b> added to story whitelist.")
    
    elif action == "remove" and len(args) > 1:
        peer_id = int(args[1])
        await db_handler.remove_from_whitelist(peer_id)
        await m.reply_msg(f"✅ <code>{peer_id}</code> removed from story whitelist.")
    
    elif action == "list":
        wl = await db_handler.get_whitelist()
        if not wl:
            return await m.reply_msg("<b>📋 Whitelist is empty.</b>")
        text = "<b>📋 Story Auto-Archive Whitelist:</b>\n\n"
        for i, user in enumerate(wl, 1):
            name = user.get("name", "Unknown")
            uid = user["_id"]
            text += f"<code>{i}.</code> <b>{name}</b> (<code>{uid}</code>)\n"
        await m.reply_msg(text)
    else:
        await m.reply_msg("<b>Usage:</b> <code>.swl add/remove/list [user_id]</code>")
