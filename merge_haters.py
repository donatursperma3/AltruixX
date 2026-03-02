import os

source_file = r"f:\2025\DESEMBER\altruix\AltruixX\Main\plugins\userbot\xdetect_haters.py.disabled"
target_file = r"f:\2025\DESEMBER\altruix\AltruixX\Main\plugins\userbot\xmention_logger_user.py"

with open(source_file, "r", encoding="utf-8") as f:
    source_lines = f.readlines()

# Extract from `STORAGE_FILE = Path(get_db_path("detect_haters_settings.json"))` to the bottom
start_index = -1
for i, line in enumerate(source_lines):
    if 'STORAGE_FILE = Path(get_db_path("detect_haters_settings.json"))' in line:
        start_index = i
        break

if start_index != -1:
    hater_code = source_lines[start_index:]
    hater_code_str = "".join(hater_code)
    
    ui_code = """

# ==================== HATERS DETECTOR DASHBOARD UI ====================
async def generate_haters_menu_async(client_id):
    s = get_settings(client_id)
    
    status_text = "ENABLED ✅" if s.get("enabled", False) else "DISABLED ❌"
    log_text = "ON" if s.get("log_detections", True) else "OFF"
    random_text = "ON" if s.get("random_response", True) else "OFF"
    delay = s.get("response_delay", 0)
    
    haters = s.get("detected_haters", {})
    responses = s.get("responses", [])
    total_haters = len(haters)
    total_responses = len(responses)
    
    buttons = [
        [
            InlineKeyboardButton(f"Status: {status_text}", callback_data=f"haters_toggle_{client_id}"),
            InlineKeyboardButton(f"Log: {log_text}", callback_data=f"haters_log_{client_id}")
        ],
        [
            InlineKeyboardButton(f"Mode (Rand): {random_text}", callback_data=f"haters_random_{client_id}"),
            InlineKeyboardButton(f"Delay: {delay}s", callback_data=f"haters_delay_{client_id}")
        ],
        [
            InlineKeyboardButton(f"Responses ({total_responses})", callback_data=f"haters_responses_{client_id}"),
            InlineKeyboardButton(f"Total Haters ({total_haters})", callback_data=f"haters_list_{client_id}")
        ],
        [
            InlineKeyboardButton("🗑 Clear Haters List", callback_data=f"haters_clear_{client_id}")
        ],
        [
            InlineKeyboardButton("🔙 Back to Mentions", callback_data=f"open_mentions_settings_owner")
        ]
    ]
    
    text = (
        f"🚫 **Haters Detector Dashboard (ID: {client_id})**\\n"
        f"━━━━━━━━━━━━━━━━━━━━\\n"
        f"• Automatically detects and replies to users who mention/reply to you but have blocked you.\\n"
        f"• **Status:** {status_text}\\n"
        f"• **Detected Haters:** {total_haters}\\n"
        f"• **Custom Responses:** {total_responses}\\n"
        f"• **Delay:** {delay}s | **Random:** {random_text}\\n\\n"
        f"<i>Note: Adding/Deleting responses currently require manual commands like <code>.hateraddresponse</code>.</i>"
    )
    return text, InlineKeyboardMarkup(buttons)

@Altruix.bot.on_callback_query(filters.regex(r"^haters_(menu|toggle|log|random|delay|responses|list|clear)(?:_(\d+))?$"))
@log_errors
@iuser_check
async def haters_menu_callback(c, cb):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
            
        action = cb.matches[0].group(1)
        client_id_str = cb.matches[0].group(2)
        client_id = int(client_id_str) if client_id_str else cb.from_user.id
        
        s = get_settings(client_id)
        
        if action == "toggle":
            s["enabled"] = not s.get("enabled", False)
            save_settings(client_id, s)
            await cb.answer(f"Haters Detector {'ENABLED' if s['enabled'] else 'DISABLED'}")
        elif action == "log":
            s["log_detections"] = not s.get("log_detections", True)
            save_settings(client_id, s)
            await cb.answer(f"Logging {'ENABLED' if s['log_detections'] else 'DISABLED'}")
        elif action == "random":
            s["random_response"] = not s.get("random_response", True)
            save_settings(client_id, s)
            await cb.answer(f"Random Mode {'ON' if s['random_response'] else 'OFF'}")
        elif action == "delay":
            await cb.answer("Use command '.haterdelay <seconds>' in chat to change delay.", show_alert=True)
            return
        elif action == "responses":
            responses = s.get("responses", [])
            if not responses:
                await cb.answer("No custom responses configured.", show_alert=True)
            else:
                lines = []
                for i, resp in enumerate(responses, 1):
                    lines.append(f"{i}. {resp.get('message', '')[:40]}...")
                text = "📝 Custom Responses\\n\\n" + "\\n".join(lines) + "\\n\\nUse .hateraddresponse to add or .haterdelresponse to remove."
                await cb.answer(text[:800], show_alert=True)
            return
        elif action == "list":
            haters = s.get("detected_haters", {})
            if not haters:
                await cb.answer("No haters detected yet.", show_alert=True)
            else:
                lines = [f"{fname} ({uid})" for uid, info in haters.items() for fname in [info.get("first_name", "User")]]
                text = "📋 Detected Haters\\n\\n" + "\\n".join(lines)
                await cb.answer(text[:800], show_alert=True)
            return
        elif action == "clear":
            cnt = len(s.get("detected_haters", {}))
            s["detected_haters"] = {}
            save_settings(client_id, s)
            await cb.answer(f"Cleared {cnt} haters.", show_alert=True)
            
        text, markup = await generate_haters_menu_async(client_id)
        if markup:
            await cb.message.edit_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        logger.error(f"Haters UI Error: {e}")
        await cb.answer(f"Error: {e}", show_alert=True)
"""
    
    with open(target_file, "r", encoding="utf-8") as f:
        target_lines = f.readlines()
        
    # Check if we already injected earlier
    has_haters = False
    for line in target_lines:
        if "HATERS DETECTOR DASHBOARD UI" in line:
            has_haters = True
            break
            
    if not has_haters:
        # We also need to add the imports at the top
        # Insert at line 17
        import_index = 0
        for i, line in enumerate(target_lines):
            if "from pyrogram.enums import ChatAction" in line:
                import_index = i
                break
        
        target_lines.insert(import_index + 1, "from pyrogram.errors import UserIsBlocked, PeerIdInvalid, RPCError, FloodWait\\n")
        
        # Add the button
        for i, line in enumerate(target_lines):
            if 'InlineKeyboardButton("❌ Close", callback_data="bot_controls_menu")' in line:
                target_lines.insert(i, '             [\\n                 InlineKeyboardButton("🚫 Haters Detector Dashboard", callback_data=f"haters_menu_{client_id}")\\n             ],\\n')
                break
                
        # Insert logic at bottom
        insert_point = len(target_lines)
        for i, line in enumerate(target_lines):
            if "# ============================================================================" in line and "# 🔥 FINAL LOG" in target_lines[min(len(target_lines)-1, i+1)]:
                insert_point = i
                break
                
        # To avoid escaping issues in UI code, write UI code
        target_lines.insert(insert_point, "\\n" + hater_code_str + "\\n" + ui_code + "\\n")
        
        with open(target_file, "w", encoding="utf-8") as f:
            f.writelines(target_lines)
            
        print("Integration successful!")
    else:
        print("Already integrated!")
else:
    print("Could not find start index in source file.")
