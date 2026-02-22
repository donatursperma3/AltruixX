# Main/core/ext/ultroid_bridge.py
import re
import asyncio
import logging
import inspect
from typing import Union, List, Callable, Any
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import MessageNotModified
import html

# Import Altruix to get native registration
from Main import Altruix

logger = logging.getLogger("UltroidBridge")

class UltroidEvent:
    """Wrapper to make Pyrogram Message look like a Telethon Event"""
    def __init__(self, message: Message, client: Client):
        self._message = message
        self._client = client
        self.text = message.text or message.caption or ""
        self.raw_text = self.text
        self.id = message.id
        self.chat_id = message.chat.id
        self.sender_id = message.from_user.id if message.from_user else None
        
        # Chat types mapping
        self.is_private = message.chat.type == enums.ChatType.PRIVATE
        self.is_group = message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]
        self.is_channel = message.chat.type == enums.ChatType.CHANNEL
        
        # Telethon style attributes
        self.pattern_match = None
        self.message = self # For event.message.reply()

    @property
    def sender(self):
        return self._message.from_user

    @property
    def client(self):
        return self._client

    async def reply(self, text, *args, **kwargs):
        return await self._message.reply_text(text, *args, **kwargs)

    async def edit(self, text, *args, **kwargs):
        # Telethon .edit() works on the event itself
        if self._message.from_user and self._message.from_user.is_self:
            try:
                return await self._message.edit_text(text, *args, **kwargs)
            except Exception:
                return self._message
        # If it's a reply/other, maybe the plugin wants to send a new message or we just fail gracefully
        return await self.reply(text, *args, **kwargs)

    async def delete(self):
        return await self._message.delete()

    async def respond(self, text, *args, **kwargs):
        # Respond in the same chat
        return await self._client.send_message(self.chat_id, text, *args, **kwargs)

    async def eor(self, text, **kwargs):
        """Edit or Reply"""
        if self._message.from_user and self._message.from_user.is_self:
            try:
                return await self.edit(text, **kwargs)
            except Exception:
                return self._message
            except Exception:
                pass
        return await self.reply(text, **kwargs)

    async def eod(self, text=None, time=None, **kwargs):
        """Edit or Delete"""
        m = await self.eor(text, **kwargs)
        if time:
            await asyncio.sleep(time)
            return await m.delete()
        return m

    async def get_reply_message(self):
        if self._message.reply_to_message:
            return UltroidEvent(self._message.reply_to_message, self._client)
        return None

# Shim for ultroid_cmd
def ultroid_cmd(
    pattern: str = None,
    groups_only: bool = False,
    pm_only: bool = False,
    sw: bool = True, # Sudo works (Ultroid usually allows sudo by default if configured)
    **kwargs
):
    def decorator(func: Callable):
        # Extract command name from pattern
        cmd_name = pattern
        if pattern:
            # Handle list of patterns
            if isinstance(pattern, list):
                cmd_name = pattern[0]
            
            # Clean regex markers
            cmd_name = cmd_name.replace("^", "").replace("$", "").split("(")[0].split("|")[0]
            cmd_name = cmd_name.strip()

        # Help metadata
        cmd_help = {
            "help": func.__doc__ or "Ultroid Addon Plugin",
            "example": f"{cmd_name}"
        }

        # Wrapper to convert (client, message) -> (event)
        async def altruix_wrapper(client, message):
            # Check if Ultroid Addons are enabled
            is_enabled = await Altruix.config.get_env("LOAD_ULTROID_ADDONS", default="off")
            if str(is_enabled).lower() not in ("on", "true", "1", "yes"):
                return

            try:
                event = UltroidEvent(message, client)
                # Simple pattern match simulation
                if pattern and hasattr(message, 'text') and message.text:
                    prefix = await Altruix.get_prefix(client.me.id, message, is_ultroid=True)
                    text_no_prefix = message.text[len(prefix):] if message.text.startswith(prefix) else message.text
                    event.pattern_match = re.search(pattern, text_no_prefix)
                
                return await func(event)
            except Exception as e:
                import traceback
                full_error = traceback.format_exc()
                
                # Log detailed error for debugging
                logger.error(f"Error in Ultroid Addon {func.__name__}:\n{full_error}")
                
                # Report to user (Concise)
                error_feedback = f"❌ <b>Ultroid Addon Error:</b> <code>{type(e).__name__}: {str(e)}</code>"
                try:
                    await message.reply_text(error_feedback, parse_mode=enums.ParseMode.HTML)
                except Exception:
                    pass
                
                # Send to Altruix error log system (via Bot Assistant for Log Group)
                if hasattr(Altruix, 'send_error'):
                    try:
                        await Altruix.send_error(client, cmd_name, full_error, "UltroidAddon", use_bot=True)
                    except:
                        pass

        # Register it in Altruix system
        # We manually register since we are outside the usual decorator flow
        Altruix.register_on_cmd(
            cmd=cmd_name,
            cmd_help=cmd_help,
            pm_only=pm_only,
            group_only=groups_only,
            disallow_if_sender_is_channel=kwargs.get("allow_channels", False) == False,
            is_ultroid=True
        )(altruix_wrapper)

        return func
    return decorator

# Common Helpers
async def eor(event, text, **kwargs):
    """Edit or Reply"""
    if hasattr(event, 'edit') and event._message.from_user and event._message.from_user.is_self:
        try:
            return await event.edit(text, **kwargs)
        except Exception:
            pass
    return await event.reply(text, **kwargs)

async def eod(event, text=None, time=None, **kwargs):
    """Edit or Delete"""
    m = await eor(event, text, **kwargs)
    if time:
        await asyncio.sleep(time)
        return await m.delete()
    return m

# Database Shim
class udB:
    class LazyAwaitable:
        """Helper to allow 'if udB.get_key(x)' and 'await udB.get_key(x)'"""
        def __init__(self, value):
            self._val = value
        def __bool__(self):
            return bool(self._val)
        def __await__(self):
            async def _dummy(): return self._val
            return _dummy().__await__()
        def __str__(self):
            return str(self._val)
        def __repr__(self):
            return repr(self._val)
        def __iter__(self):
            return iter(self._val if isinstance(self._val, (list, tuple, dict)) else [])
        def __getitem__(self, item):
            return self._val[item]
        def get(self, k, d=None):
            return self._val.get(k, d) if isinstance(self._val, dict) else d
        def update(self, *a, **kw):
            if hasattr(self._val, 'update'): return self._val.update(*a, **kw)

    @staticmethod
    def get_key(key):
        from Main import Altruix
        # Access cache directly for sync truthiness
        val = Altruix.config._env_cache.get(f"ULTROID_{key}")
        return udB.LazyAwaitable(val)
    
    @staticmethod
    async def set_key(key, value):
        return await Altruix.config.set_env(f"ULTROID_{key}", value)

    @staticmethod
    async def del_key(key):
        return await Altruix.config.del_env(f"ULTROID_{key}")

# Extra Symbols
as_commas = lambda x: ", ".join(map(str, x))
get_string = lambda x: Altruix.get_string(x)

# ✅ LATEST SHIMS for Inline Addons
LOGS = logging.getLogger("UltroidAddons")

# Delayed import-like access for asst
def _get_asst():
    class AsstWrapper:
        @property
        def bot(self):
            try:
                from Main import Altruix
                return Altruix.bot
            except:
                return None
        
        def __getattr__(self, name):
            bot = self.bot
            if bot:
                if name == "username":
                    # Pyrogram Client has .me.username
                    return getattr(getattr(bot, "me", None), "username", None) or "BotAssistant"
                return getattr(bot, name)
            
            # Fallback if bot is not yet initialized
            if name == "username":
                return "BotAssistant"
            return type("DummyAsst", (), {"username": "BotAssistant"})()

    return AsstWrapper()

asst = _get_asst()

class InlinePlugin:
    """Robust Dummy for InlinePlugin to handle .update() calls"""
    @classmethod
    def update(cls, mapping: dict):
        pass
    
    # Also support dictionary-like behavior if needed
    def __getattr__(self, name):
        return lambda *a, **k: None

# Keep as class so type(InlinePlugin) and InlinePlugin itself work consistently

async def async_searcher(url, re_json=False, **kwargs):
    """Functional async searcher using requests + executor"""
    loop = asyncio.get_event_loop()
    def _fetch():
        try:
            res = requests.get(url, **kwargs)
            return res.json() if re_json else res.text
        except Exception as e:
            LOGS.error(f"async_searcher error: {e}")
            return {} if re_json else ""
    return await loop.run_in_executor(None, _fetch)

Button = type("Button", (), {
    "inline": lambda text, data=None: [text, data],
    "url": lambda text, url=None: [text, url],
    "switch_inline": lambda text, query="", same_peer=False: [text, query]
})

def in_pattern(pattern, owner=False, **kwargs):
    """Dummy decorator for inline patterns"""
    def decorator(func):
        return func
    return decorator

def callback(data, **kwargs):
    """Dummy decorator for callbacks"""
    def decorator(func):
        return func
    return decorator

# ✅ Missing Utility Shims
async def bash(cmd):
    """Execution shim for bash commands (used in some addons)"""
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode().strip(), stderr.decode().strip()

def inline_mention(user):
    """Shim for inline mention formatting"""
    if hasattr(user, 'id'):
        name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or "User"
        return f"<a href='tg://user?id={user.id}'>{html.escape(name)}</a>"
    return str(user)

def mediainfo(file):
    """Dummy mediainfo for addons"""
    return type("Mediainfo", (), {
        "duration": 0,
        "width": 0,
        "height": 0,
        "mime_type": "video/mp4"
    })()
