# Main/internals/xchangelog_builder.py
# ============================================================================
# ROLE: Callback Handler for Paginated Changelog
# FRAMEWORK: Altruix / Kurigram (Powered by Bot Assistant)
# DESCRIPTION: 
#   Handles Inline Queries and Callback Queries via Bot Assistant.
#   UI Builder logic is moved to Main.utils.changelog_helpers to avoid circular imports.
# ============================================================================

import logging
from pyrogram import Client, enums, filters
from pyrogram.types import CallbackQuery, InlineQuery
from pyrogram.errors import MessageNotModified

# Use lazy imports and rely on loader injection to avoid circular dependencies
from Main.core.decorators import log_errors, iuser_check
from Main.utils.changelog_helpers import build_changelog_page

# Configuration
QUERY_PREFIX = "clog_view"
CB_PREFIX = "clog_"
logger = logging.getLogger("altruix.xchangelog.builder")

# ============================================================================
# BOT ASSISTANT HANDLERS
# ============================================================================

# NOTE: 'Altruix' and 'bot' are injected into this module's globals 
# by AltruixClient.load_from_directory during the loading process.

try:
    # Try to use the injected 'bot' instance (preferred for Kurigram/Altruix)
    target_bot = bot 
except NameError:
    # Fallback for static analysis or manual imports (not recommended during startup)
    try:
        from Main.core.client import Altruix
        target_bot = Altruix.bot
    except (ImportError, AttributeError):
        target_bot = None

if target_bot:
    @target_bot.on_inline_query(filters.regex(r"^clog_view_(\d+)_(\d+)"))
    @iuser_check
    @log_errors
    async def changelog_inline_handler(c: Client, iq: InlineQuery):
        """Handles inline queries to display the paginated changelog."""
        page = int(iq.matches[0].group(1))
        owner_id = int(iq.matches[0].group(2))
        
        text, kb = await build_changelog_page(owner_id, page=page)
        
        from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent
        results = [
            InlineQueryResultArticle(
                id=f"{QUERY_PREFIX}_{page}_{owner_id}",
                title=f"AltruixX Changelog - Entry {page + 1}",
                description=f"Klik untuk mengirim changelog (Halaman {page + 1}).",
                input_message_content=InputTextMessageContent(
                    text, parse_mode=enums.ParseMode.HTML
                ),
                reply_markup=kb,
                thumb_url="https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg"
            )
        ]
        await iq.answer(results, cache_time=0, is_personal=True)

    @target_bot.on_callback_query(filters.regex(r"^clog_"))
    @iuser_check
    @log_errors
    async def changelog_callback_handler(c: Client, cb: CallbackQuery):
        """Processes all interactions with the changelog inline menu."""
        data = cb.data.split("_")
        action = data[1] # page, close, noop
        
        try:
            if action == "page":
                page = int(data[2])
                owner_id = int(data[3])
                text, kb = await build_changelog_page(owner_id, page)
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                
            elif action == "close":
                await cb.message.delete()
                
            elif action == "noop":
                await cb.answer()
                
        except MessageNotModified:
            pass
        except Exception as e:
            logger.error(f"Changelog Callback Error: {e}", exc_info=True)
            await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
else:
    logger.warning("xchangelog_builder: Bot instance not found. Handlers could not be registered.")
