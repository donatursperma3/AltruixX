import re

file_path = "f:/2025/DESEMBER/altruix/AltruixX/Main/plugins/userbot/xpm_logger_user.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update SessionManager load TTL
dynamic_ttl_sm = """        ttl_seconds = 86400 # 24 Hours
        
        # Try load dynamic TTL
        try:
            if STORAGE_FILE.exists():
                with open(STORAGE_FILE, 'r', encoding='utf-8') as fs:
                    ts = json.load(fs)
                    ttl_seconds = ts.get("global_config", {}).get("cache_ttl", 86400)
        except:
            pass"""
content = content.replace("        ttl_seconds = 86400 # 24 Hours", dynamic_ttl_sm)

# 2. Update cleanup_pmlu_cache
cleanup_target = """async def cleanup_pmlu_cache():
    while True:
        if len(PM_LOG_CACHE) > 1000:
            # Simple cleanup: remove oldest 200
            keys = list(PM_LOG_CACHE.keys())[:200]
            for k in keys:
                PM_LOG_CACHE.pop(k, None)
        await asyncio.sleep(3600)"""

cleanup_replace = """async def cleanup_pmlu_cache():
    while True:
        try:
            ttl_seconds = 86400
            if STORAGE_FILE.exists():
                with open(STORAGE_FILE, 'r', encoding='utf-8') as fs:
                    ts = json.load(fs)
                    ttl_seconds = ts.get("global_config", {}).get("cache_ttl", 86400)
                    
            # Use size heuristic based on TTL (approx 100 items per 12 hours)
            max_cache_len = max(1000, int((ttl_seconds / 86400) * 1500))
            if len(PM_LOG_CACHE) > max_cache_len:
                keys = list(PM_LOG_CACHE.keys())[:200]
                for k in keys:
                    PM_LOG_CACHE.pop(k, None)
        except:
            pass
        await asyncio.sleep(3600)"""
content = content.replace(cleanup_target, cleanup_replace)

# 3. Add Cache Manager Button
btn_target = """InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "❌ Close"), callback_data="bot_controls_menu") # Back to Bot Controls if opened from there
             ]"""
btn_replace = """InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "❌ Close"), callback_data="bot_controls_menu")
             ],
             [
                 InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🗃️ Cache Manager"), callback_data=f"pmlu_cache_menu_{client_id}")
             ]"""
content = content.replace(btn_target, btn_replace)

# 4. Add Cache Manager Handlers before open_pmlu_settings_owner_handler
cache_logic = """
# ============================================================================
# 🗃️ CACHE MANAGER MENU & HANDLERS
# ============================================================================
async def generate_pmlu_cache_menu(client_id):
    try:
        user_id_str = str(client_id)
        current_ttl = 86400
        try:
            if STORAGE_FILE.exists():
                with open(STORAGE_FILE, 'r', encoding='utf-8') as fs:
                    ts = json.load(fs)
                    current_ttl = ts.get("global_config", {}).get("cache_ttl", 86400)
        except:
            pass
            
        ttl_hours = current_ttl // 3600
        
        # Calculate Sizes
        pm_count = len(PM_LOG_CACHE)
        session_count = len(Altruix.REPLY_AS_MENTIONED_WAITING)
        
        # Disk Size Estimation
        disk_size_bytes = 0
        cache_file = Path(get_db_path("pm_logger_cache.json"))
        if cache_file.exists():
            disk_size_bytes += cache_file.stat().st_size
        if SESSION_FILE.exists():
            disk_size_bytes += SESSION_FILE.stat().st_size
            
        size_kb = disk_size_bytes / 1024
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
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"🕒 Cache TTL: {ttl_hours}h"), callback_data="pmlu_cache_noop"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"📝 Change to {next_ttl//3600}h"), callback_data=f"pmlu_cache_set_ttl_{client_id}_{next_ttl}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"🗑️ PM Logs ({pm_count})"), callback_data=f"pmlu_cache_clear_logs_{client_id}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, f"🗑️ Active Sessions ({session_count})"), callback_data=f"pmlu_cache_clear_sessions_{client_id}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🔙 Back to Settings"), callback_data=f"open_pmlu_settings_owner")
            ]
        ]
        
        res = (
            f"🗃️ **PM Logger Cache Manager**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• **Cache Expiration Timer:** `{ttl_hours} hours`\n"
            f"• **Estimated Disk Usage:** `{size_str}`\n\n"
            f"📊 **Data Statistics:**\n"
            f"• Valid PM Logs Cached: `{pm_count}`\n"
            f"• Active Waiting Sessions: `{session_count}`\n\n"
            f"<i>Select an option below to manage memory.</i>"
        )
        return res, InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"PMLU Cache Menu Gen Error: {e}")
        return f"Error: {e}", None

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_cache_menu_(\d+)$"))
@log_errors
@iuser_check
async def pmlu_cache_menu_handler(c: Client, cb: CallbackQuery):
    try:
        client_id = int(cb.data.split("_")[-1])
        text, markup = await generate_pmlu_cache_menu(client_id)
        if markup:
            await Altruix.edit_cb(cb, text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_cache_set_ttl_(\d+)_(\d+)$"))
@log_errors
@iuser_check
async def pmlu_cache_set_ttl_handler(c: Client, cb: CallbackQuery):
    try:
        parts = cb.data.split("_")
        client_id = int(parts[-2])
        new_ttl = int(parts[-1])
        
        data = {}
        if STORAGE_FILE.exists():
            with open(STORAGE_FILE, "r") as f:
                data = json.load(f)
        
        if "global_config" not in data:
            data["global_config"] = {}
        data["global_config"]["cache_ttl"] = new_ttl
        
        with open(STORAGE_FILE, "w") as f:
            json.dump(data, f, indent=4)
            
        await load_settings()
        
        await cb.answer(f"✅ Cache TTL adjusted to {new_ttl//3600} hours!", show_alert=True)
        
        # Refresh Menu
        text, markup = await generate_pmlu_cache_menu(client_id)
        if markup:
            await Altruix.edit_cb(cb, text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_cache_clear_(logs|sessions)_(\d+)$"))
@log_errors
@iuser_check
async def pmlu_cache_clear_handler(c: Client, cb: CallbackQuery):
    try:
        action = cb.matches[0].group(1)
        client_id = int(cb.matches[0].group(2))
        
        cleared_count = 0
        if action == "logs":
            cleared_count = len(PM_LOG_CACHE)
            PM_LOG_CACHE.clear()
        elif action == "sessions":
            cleared_count = len(Altruix.REPLY_AS_MENTIONED_WAITING)
            Altruix.REPLY_AS_MENTIONED_WAITING.clear()
            
        SessionManager.save()
            
        await cb.answer(f"✅ Cleared {cleared_count} items from {action} cache!", show_alert=True)
        
        # Refresh Menu
        text, markup = await generate_pmlu_cache_menu(client_id)
        if markup:
            await Altruix.edit_cb(cb, text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_cache_noop$"))
async def pmlu_cache_noop_handler(c, cb):
    await cb.answer("Current Cache TTL Duration", show_alert=False)

"""

handler_target = "@Altruix.bot.on_callback_query(filters.regex(r\"^open_pmlu_settings_owner$\"))"
content = content.replace(handler_target, cache_logic + "\n" + handler_target)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Update xpm applied successfully.")
