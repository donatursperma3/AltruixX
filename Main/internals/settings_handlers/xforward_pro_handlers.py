"""
Auxiliary handler registrar for Forward Pro — ensures the inline and callback
handlers are registered on the assistant bot (main or custom) and any
custom assistant bots managed by `Altruix.bot_manager`.

This module is safe to import multiple times: it checks existing handlers
(before adding) and uses retries to cope with late-starting custom bots.

It intentionally does not change business logic or DB handling; it only
ensures handler registration and improves observability when handlers
are missing.
"""

import asyncio
import logging
import traceback
import inspect

from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, InlineQueryHandler
from Main import Altruix

logger = logging.getLogger("altruix.xforward_pro.handlers")
logger.setLevel(logging.DEBUG)


def _has_handler(bot, target_func):
    try:
        if not hasattr(bot, 'dispatcher') or not hasattr(bot.dispatcher, 'groups'):
            return False
        for handlers in bot.dispatcher.groups.values():
            for h in handlers:
                try:
                    cb = getattr(h, 'callback', None)
                    # Direct compare or via unwrap
                    if cb is target_func:
                        return True
                    try:
                        un = inspect.unwrap(cb) if cb else None
                    except Exception:
                        un = getattr(cb, '__wrapped__', None) if cb else None
                    if un is target_func:
                        return True

                    # Fallback: compare function name (some wrappers hide original object)
                    try:
                        cb_name = getattr(un, '__name__', None) or getattr(cb, '__name__', None)
                        if cb_name and target_func.__name__ in str(cb_name):
                            return True
                    except Exception:
                        pass

                    # Fallback: detect by filters repr containing our fwd patterns
                    try:
                        h_filters = getattr(h, 'filters', None)
                        if h_filters and ("fwd_menu_uid" in repr(h_filters) or "fwd_" in repr(h_filters)):
                            return True
                    except Exception:
                        pass
                except Exception:
                    continue
    except Exception:
        logger.debug("[ForwardProHandlers] _has_handler check failed:\n" + traceback.format_exc())
    return False


def _register_handlers_on_bot(bot, inline_handler, callback_handler):
    if not bot:
        return
    try:
        added = False
        if not _has_handler(bot, callback_handler):
            try:
                bot.add_handler(CallbackQueryHandler(callback_handler, filters=filters.regex(r"^fwd_(.+)$")), group=0)
                logger.debug(f"[ForwardProHandlers] Added CallbackQueryHandler to bot {getattr(bot,'username',None)}")
                added = True
            except Exception as e:
                logger.error(f"[ForwardProHandlers] Failed adding CallbackQueryHandler to {getattr(bot,'username',None)}: {e}")
        else:
            logger.debug(f"[ForwardProHandlers] CallbackQueryHandler already present on {getattr(bot,'username',None)}")

        if not _has_handler(bot, inline_handler):
            try:
                bot.add_handler(InlineQueryHandler(inline_handler, filters=filters.regex(r"^fwd_menu_uid_(?P<uid>\\d+)$")), group=0)
                logger.debug(f"[ForwardProHandlers] Added InlineQueryHandler to bot {getattr(bot,'username',None)}")
                added = True
            except Exception as e:
                logger.error(f"[ForwardProHandlers] Failed adding InlineQueryHandler to {getattr(bot,'username',None)}: {e}")
        else:
            logger.debug(f"[ForwardProHandlers] InlineQueryHandler already present on {getattr(bot,'username',None)}")

        if added:
            try:
                # Dump registered handlers for visibility
                if hasattr(bot, 'dispatcher') and hasattr(bot.dispatcher, 'groups'):
                    handler_list = []
                    for g, hs in bot.dispatcher.groups.items():
                        for h in hs:
                            handler_list.append({'group': g, 'callback': getattr(getattr(h,'callback', None),'__name__', repr(getattr(h,'callback', None)))})
                    logger.debug(f"[ForwardProHandlers] Handlers for {getattr(bot,'username',None)}: {handler_list}")
            except Exception:
                logger.debug("[ForwardProHandlers] Failed to dump handlers after adding")

    except Exception:
        logger.error("[ForwardProHandlers] _register_handlers_on_bot failed:\n" + traceback.format_exc())


async def _try_register(inline_handler, callback_handler):
    # 1) Register on main assistant if available
    try:
        bot_main = getattr(Altruix, 'bot', None)
        if bot_main:
            _register_handlers_on_bot(bot_main, inline_handler, callback_handler)
    except Exception:
        logger.debug("[ForwardProHandlers] Failed to register on main bot:\n" + traceback.format_exc())

    # 2) Register on all custom bots (if bot_manager present)
    try:
        if hasattr(Altruix, 'bot_manager'):
            custom_bots = getattr(Altruix.bot_manager, 'custom_bots', {}) or {}
            for b in list(custom_bots.values()):
                _register_handlers_on_bot(b, inline_handler, callback_handler)
    except Exception:
        logger.debug("[ForwardProHandlers] Failed to register on custom bots:\n" + traceback.format_exc())


def schedule_registration(retries=(1, 5, 15, 60)):
    try:
        # Import handlers from xforward_pro lazily to avoid circular import issues
        from Main.plugins.userbot.xforward_pro import fwd_inline_handler, fwd_callback_handler
    except Exception:
        logger.error("[ForwardProHandlers] Could not import xforward_pro handlers:\n" + traceback.format_exc())
        return

    async def _runner():
        for sec in retries:
            try:
                await _try_register(fwd_inline_handler, fwd_callback_handler)
            except Exception:
                logger.error("[ForwardProHandlers] Registration attempt failed:\n" + traceback.format_exc())
            await asyncio.sleep(sec)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_runner())
        else:
            loop.call_soon(lambda: asyncio.create_task(_runner()))
    except Exception:
        logger.error("[ForwardProHandlers] schedule_registration failed:\n" + traceback.format_exc())


# Kick off registration attempts on import
schedule_registration()
