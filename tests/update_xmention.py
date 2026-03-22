import re

file_path = "f:/2025/DESEMBER/altruix/AltruixX/Main/plugins/userbot/xmention_logger_user.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace constants with functions
const_block = """TTL_MENTION_CACHE = 7200  # 2 jam untuk mention cache
TTL_WAITING_REPLY = 3600  # 1 jam untuk waiting replies"""

dynamic_block = """import sys

def get_mention_cache_ttl():
    try:
        import os, json
        if os.path.exists("mentions_settings.json"):
            with open("mentions_settings.json", "r") as f:
                data = json.load(f)
                return data.get("global", {}).get("cache_ttl", 86400)
    except:
        pass
    return 86400

TTL_MENTION_CACHE = 86400  # Fallback
TTL_WAITING_REPLY = 86400  # Fallback"""

content = content.replace(const_block, dynamic_block)

# 2. Update usages of TTL_MENTION_CACHE to get_mention_cache_ttl()
content = re.sub(r'ttl or TTL_MENTION_CACHE', r'ttl or get_mention_cache_ttl()', content)
content = re.sub(r'cache_set\(cache_key, data, TTL_MENTION_CACHE\)', r'cache_set(cache_key, data, get_mention_cache_ttl())', content)
content = re.sub(r'cache_set\(cache_key, data, TTL_WAITING_REPLY\)', r'cache_set(cache_key, data, get_mention_cache_ttl())', content)

# 3. Add Cache Manager Button
btn_target = """InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🚫 Haters Detector Dashboard"), callback_data=f"haters_menu_{client_id}")
             ],"""
btn_replace = """InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🚫 Haters Detector Dashboard"), callback_data=f"haters_menu_{client_id}")
             ],
             [
                 InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🗃️ Cache Manager"), callback_data=f"mnt_cache_menu_{client_id}")
             ],"""
content = content.replace(btn_target, btn_replace)

# 4. Add Cache Manager Handlers before open_mentions_settings_handler
cache_logic = """
# ============================================================================
# 🗃️ CACHE MANAGER MENU & HANDLERS
# ============================================================================
async def generate_mnt_cache_menu(client_id):
    try:
        user_id_str = str(client_id)
        current_ttl = get_mention_cache_ttl()
        ttl_hours = current_ttl // 3600
        
        # Calculate Sizes
        import sys
        mentions_count = len(MENTION_LOG_CACHE)
        waiting_count = len(REPLY_AS_MENTIONED_WAITING)
        user_counts = len(USER_REPLY_COUNTS)
        block_count = len(BLOCK_STATUS_CACHE)
        
        # Deep size estimation
        def get_size(obj, seen=None):
            size = sys.getsizeof(obj)
            if seen is None: seen = set()
            obj_id = id(obj)
            if obj_id in seen: return 0
            seen.add(obj_id)
            if isinstance(obj, dict):
                size += sum([get_size(v, seen) for v in obj.values()])
                size += sum([get_size(k, seen) for k in obj.keys()])
            elif hasattr(obj, '__dict__'):
                size += get_size(obj.__dict__, seen)
            elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
                size += sum([get_size(i, seen) for i in obj])
            return size
            
        total_size_bytes = get_size(MENTION_LOG_CACHE) + get_size(REPLY_AS_MENTIONED_WAITING) + get_size(USER_REPLY_COUNTS) + get_size(BLOCK_STATUS_CACHE)
        size_kb = total_size_bytes / 1024
        size_mb = size_kb / 1024
        size_str = f"{size_mb:.2f} MB" if size_kb > 1024 else f"{size_kb:.2f} KB"
        
        # Check Next TTL Value
        next_ttls = [43200, 86400, 172800, 259200]  # 12h, 24h, 48h, 72h
        next_ttl = next_ttls[0]
        for t in next_ttls:
            if t > current_ttl:
                next_ttl = t
                break
        
        buttons = [
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"🕒 Cache TTL: {ttl_hours}h"), callback_data="mnt_cache_noop"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"📝 Change to {next_ttl//3600}h"), callback_data=f"mnt_cache_set_ttl_{client_id}_{next_ttl}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"🗑️ Mentions ({mentions_count})"), callback_data=f"mnt_cache_clear_mentions_{client_id}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"🗑️ Waiting ({waiting_count})"), callback_data=f"mnt_cache_clear_waiting_{client_id}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"🗑️ Users Count ({user_counts})"), callback_data=f"mnt_cache_clear_users_{client_id}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"🗑️ Block/Hater ({block_count})"), callback_data=f"mnt_cache_clear_blocks_{client_id}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🔙 Back to Settings"), callback_data=f"open_mentions_settings_{client_id}")
            ]
        ]
        
        res = (
            f"🗃️ **Mention Logger Cache Manager**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• **Cache Expiration Timer:** `{ttl_hours} hours`\n"
            f"• **Estimated RAM Usage:** `{size_str}`\n\n"
            f"📊 **Data Statistics:**\n"
            f"• Mention Logs Cached: `{mentions_count}`\n"
            f"• Waiting Replies: `{waiting_count}`\n"
            f"• Rate Limit/User Counts: `{user_counts}`\n"
            f"• Block / Hater Validation: `{block_count}`\n\n"
            f"<i>Select an option below to manage memory.</i>"
        )
        return res, InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Cache Menu Gen Error: {e}")
        return f"Error: {e}", None

@Altruix.bot.on_callback_query(filters.regex(r"^mnt_cache_menu_(\d+)$"))
@log_errors
@iuser_check
async def mnt_cache_menu_handler(c: Client, cb: CallbackQuery):
    try:
        client_id = int(cb.data.split("_")[-1])
        text, markup = await generate_mnt_cache_menu(client_id)
        if markup:
            await Altruix.edit_cb(cb, text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^mnt_cache_set_ttl_(\d+)_(\d+)$"))
@log_errors
@iuser_check
async def mnt_cache_set_ttl_handler(c: Client, cb: CallbackQuery):
    try:
        parts = cb.data.split("_")
        client_id = int(parts[-2])
        new_ttl = int(parts[-1])
        
        settings_file = "mentions_settings.json"
        data = {"settings": {}, "global": {}}
        import os, json
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                data = json.load(f)
        
        if "global" not in data:
            data["global"] = {}
        data["global"]["cache_ttl"] = new_ttl
        
        with open(settings_file, "w") as f:
            json.dump(data, f, indent=4)
            
        await cb.answer(f"✅ Cache TTL adjusted to {new_ttl//3600} hours!", show_alert=True)
        
        # Refresh Menu
        text, markup = await generate_mnt_cache_menu(client_id)
        if markup:
            await Altruix.edit_cb(cb, text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^mnt_cache_clear_(mentions|waiting|users|blocks)_(\d+)$"))
@log_errors
@iuser_check
async def mnt_cache_clear_handler(c: Client, cb: CallbackQuery):
    try:
        action = cb.matches[0].group(1)
        client_id = int(cb.matches[0].group(2))
        
        cleared_count = 0
        if action == "mentions":
            cleared_count = len(MENTION_LOG_CACHE)
            MENTION_LOG_CACHE.clear()
        elif action == "waiting":
            cleared_count = len(REPLY_AS_MENTIONED_WAITING)
            REPLY_AS_MENTIONED_WAITING.clear()
        elif action == "users":
            cleared_count = len(USER_REPLY_COUNTS)
            USER_REPLY_COUNTS.clear()
        elif action == "blocks":
            from Main.plugins.userbot.xmention_logger_user import BLOCK_STATUS_CACHE
            cleared_count = len(BLOCK_STATUS_CACHE)
            BLOCK_STATUS_CACHE.clear()
            
        await cb.answer(f"✅ Cleared {cleared_count} items from {action} cache!", show_alert=True)
        
        # Refresh Menu
        text, markup = await generate_mnt_cache_menu(client_id)
        if markup:
            await Altruix.edit_cb(cb, text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^mnt_cache_noop$"))
async def mnt_cache_noop_handler(c, cb):
    await cb.answer("Current Cache TTL Duration", show_alert=False)

"""

handler_target = "@Altruix.bot.on_callback_query(filters.regex(r\"^open_mentions_settings_(\d+|owner|self)$\"))"
content = content.replace(handler_target, cache_logic + "\n" + handler_target)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Update xmention applied successfully.")
