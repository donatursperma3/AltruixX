# Main/plugins/bot/XStory_Reader_Pro/bot_handlers.py
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, InlineQuery, InlineQueryResultArticle, 
    InputTextMessageContent
)
from Main import Altruix
from Main.core.decorators import log_errors, iuser_check

# Import modular components from the userbot plugin folder
from Main.plugins.userbot.XStory_Reader_Pro.db_handler import db_handler, PLUGIN_VERSION
from Main.plugins.userbot.XStory_Reader_Pro.ui_builder import (
    build_dashboard, build_story_menu, build_settings_menu
)
from Main.plugins.userbot.XStory_Reader_Pro.manager import story_manager

logger = logging.getLogger("altruix.xstory.bot")

@Altruix.bot.on_inline_query(filters.regex(r"^xstory_main_(.*)"))
@log_errors
@iuser_check
async def xstory_inline_handler(c: Client, iq: InlineQuery):
    user_id = iq.from_user.id
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
    stories = await db_handler.get_feed(limit=8)
    total_pages = (total_stories + 7) // 8 or 1

    await iq.answer(
        [
            InlineQueryResultArticle(
                id="main",
                title="Story Reader Pro Dashboard",
                description="View and manage aggregated story feed.",
                input_message_content=InputTextMessageContent(text),
                reply_markup=build_dashboard(user_id, stories, 1, total_pages)
            )
        ],
        cache_time=0,
        is_personal=True
    )

@Altruix.bot.on_callback_query(filters.regex(r"^xstory_(.*)"))
@log_errors
async def xstory_callback_handler(c: Client, cb: CallbackQuery):
    data = cb.data.split("_")
    action = data[1]
    user_id = cb.from_user.id
    
    # Auth Check
    if not await Altruix.is_sudo(user_id):
        return await cb.answer("Anda tidak memiliki izin!", show_alert=True)

    if action == "page":
        page = int(data[2])
        filter_type = data[3] if len(data) > 3 else "all"
        acc_page = int(data[4]) if len(data) > 4 else 1
        limit = 8
        skip = (page - 1) * limit
        
        stories = await db_handler.get_feed(limit=limit, skip=skip, filter_type=filter_type)
        total_stories = await db_handler.count_stories(filter_type=filter_type)
        total_pages = (total_stories + limit - 1) // limit or 1
        
        text = (
            f"<blockquote expandable>"
            "<b>📸 Story Reader Pro Dashboard</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Filter: <code>{filter_type.upper()}</code>\n"
            f"Page: <code>{page}/{total_pages}</code>"
            f"</blockquote>"
        )
        await cb.edit_message_text(text, reply_markup=build_dashboard(user_id, stories, page, total_pages, filter_type, acc_page))

    elif action == "filter":
        filter_type = data[2]
        acc_page = int(data[3]) if len(data) > 3 else 1
        await cb.answer(f"Filtering by: {filter_type}")
        # Reuse page logic for page 1
        stories = await db_handler.get_feed(limit=8, skip=0, filter_type=filter_type)
        total_stories = await db_handler.count_stories(filter_type=filter_type)
        total_pages = (total_stories + 7) // 8 or 1
        
        text = (
            f"<blockquote expandable>"
            "<b>📸 Story Reader Pro Dashboard</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Filter: <code>{filter_type.upper()}</code>\n"
            f"Page: <code>1/{total_pages}</code>"
            f"</blockquote>"
        )
        await cb.edit_message_text(text, reply_markup=build_dashboard(user_id, stories, 1, total_pages, filter_type, acc_page))

    elif action == "accpage":
        acc_page = int(data[2])
        page = int(data[3])
        filter_type = data[4] if len(data) > 4 else "all"
        
        limit = 8
        skip = (page - 1) * limit
        stories = await db_handler.get_feed(limit=limit, skip=skip, filter_type=filter_type)
        total_stories = await db_handler.count_stories(filter_type=filter_type)
        total_pages = (total_stories + limit - 1) // limit or 1
        
        text = (
            f"<blockquote expandable>"
            "<b>📸 Story Reader Pro Dashboard</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Filter: <code>{filter_type.upper()}</code>\n"
            f"Page: <code>{page}/{total_pages}</code>"
            f"</blockquote>"
        )
        await cb.edit_message_text(text, reply_markup=build_dashboard(user_id, stories, page, total_pages, filter_type, acc_page))

    elif action == "view":
        peer_id = int(data[2])
        story_id = int(data[3])
        page = int(data[4])
        acc_page = int(data[5]) if len(data) > 5 else 1
        
        is_archived = False # Should check in DB
        is_whitelisted = await db_handler.is_whitelisted(peer_id)
        
        text = (
            f"<blockquote expandable>"
            "<b>📸 Story Details</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Peer ID: <code>{peer_id}</code>\n"
            f"Story ID: <code>{story_id}</code>\n"
            f"Whitelist: {'✅' if is_whitelisted else '❌'}"
            f"</blockquote>"
        )
        await cb.edit_message_text(text, reply_markup=build_story_menu(peer_id, story_id, page, is_archived, is_whitelisted, acc_page))

    elif action == "ghost":
        peer_id = int(data[2])
        story_id = int(data[3])
        await cb.answer("👁 Ghost View: Fetching story...")
        
        # We use the first active client to fetch
        for client in Altruix.clients:
            if client.is_connected:
                story = await story_manager.ghost_read(client, peer_id, story_id)
                if story:
                    # Download and send to user
                    file_path = await story_manager.download_story(client, peer_id, story_id)
                    if file_path:
                        try:
                            if story.video:
                                await c.send_video(user_id, file_path, caption=f"👁 Ghost View: {peer_id} (#{story_id})")
                            else:
                                await c.send_photo(user_id, file_path, caption=f"👁 Ghost View: {peer_id} (#{story_id})")
                            await cb.answer("✅ Media story telah dikirim ke Private Message (Japri) Anda!", show_alert=True)
                        except Exception as e:
                            logger.error(f"Failed to send ghost view to {user_id}: {e}")
                            await cb.answer(f"❌ Gagal mengirim media: {e}", show_alert=True)
                        return
        await cb.answer("❌ Gagal mengambil story!", show_alert=True)

    elif action == "react":
        peer_id = int(data[2])
        story_id = int(data[3])
        await cb.answer("Reaching out with ❤️...")
        
        # Apply reaction from all sessions? Or just one? 
        # Usually user wants all sessions to react.
        success_count = 0
        for client in Altruix.clients:
            if client.is_connected:
                try:
                    # Kurigram reaction method
                    await client.send_reaction(peer_id, "❤️", story_id=story_id)
                    success_count += 1
                except: pass
        await cb.answer(f"✅ Reacted from {success_count} accounts!")
        # Refresh story menu
        await xstory_callback_handler(c, cb) # Recursive call to refresh (careful with data format)

    elif action == "dl":
        peer_id = int(data[2])
        story_id = int(data[3])
        await cb.answer("Downloading media...")
        # Trigger download logic

    elif action == "wl":
        peer_id = int(data[2])
        story_id = int(data[3])
        page = int(data[4])
        if await db_handler.is_whitelisted(peer_id):
            await db_handler.remove_from_whitelist(peer_id)
            await cb.answer("Removed from Whitelist")
        else:
            await db_handler.add_to_whitelist(peer_id)
            await cb.answer("Added to Whitelist")
        # Refresh story menu
        await xstory_callback_handler(c, cb) # Recursive call to refresh (careful with data format)

    elif action == "settings":
        await cb.edit_message_text("<b>⚙️ Story Reader Pro Settings</b>", reply_markup=build_settings_menu())

    elif action == "close":
        await cb.edit_message_text("<b>Dashboard Closed.</b>")
        
    elif action == "noop":
        await cb.answer()

    elif action == "acc":
        acc_index = int(data[2])
        acc_page = int(data[3]) if len(data) > 3 else 1
        
        if acc_index < len(Altruix.clients):
            session_id = Altruix.clients[acc_index].me.id
            filter_type = f"acc_{session_id}"
            acc_name = Altruix.clients[acc_index].me.first_name
        else:
            return await cb.answer("Akun tidak ditemukan!", show_alert=True)
            
        await cb.answer(f"Filter: Story {acc_name}")
        
        # Reuse page logic for page 1
        stories = await db_handler.get_feed(limit=8, skip=0, filter_type=filter_type)
        total_stories = await db_handler.count_stories(filter_type=filter_type)
        total_pages = (total_stories + 7) // 8 or 1
        
        text = (
            f"<blockquote expandable>"
            "<b>📸 Story Reader Pro Dashboard</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Filter: <code>ACC: {acc_name.upper()}</code>\n"
            f"Page: <code>1/{total_pages}</code>"
            f"</blockquote>"
        )
        await cb.edit_message_text(text, reply_markup=build_dashboard(user_id, stories, 1, total_pages, filter_type, acc_page))

    elif action == "refresh":
        await cb.answer("Memperbarui feed...")
        # Reuse page logic for page 1
        stories = await db_handler.get_feed(limit=8, skip=0, filter_type="all")
        total_stories = await db_handler.count_stories(filter_type="all")
        total_pages = (total_stories + 7) // 8 or 1
        
        text = (
            f"<blockquote expandable>"
            "<b>📸 Story Reader Pro Dashboard</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Filter: <code>ALL</code>\n"
            f"Page: <code>1/{total_pages}</code>"
            f"</blockquote>"
        )
        await cb.edit_message_text(text, reply_markup=build_dashboard(user_id, stories, 1, total_pages, "all"))
        
    elif action == "arc":
        peer_id = int(data[2])
        story_id = int(data[3])
        new_status = await db_handler.toggle_archive(peer_id, story_id)
        await cb.answer(f"Story Archive Status: {'ARCHIVED' if new_status else 'UN-ARCHIVED'}")
        await xstory_callback_handler(c, cb) # Recursive call to refresh menu

    elif action == "set":
        await cb.answer("Pengaturan fitur sedang dalam pengembangan.", show_alert=True)

    elif action == "flush":
        await cb.answer("Menghapus cache story... (Belum diimplementasikan sepenuhnya)", show_alert=True)
        
    else:
        logger.warning(f"Unhandled xstory callback action: {action}")
        await cb.answer("Fitur ini belum diimplementasikan.", show_alert=True)
