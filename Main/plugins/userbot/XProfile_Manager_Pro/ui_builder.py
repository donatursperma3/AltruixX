# Main/plugins/userbot/XProfile_Manager_Pro/ui_builder.py
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.client import Altruix
from Main.utils.file_helpers import get_user_button_style

def get_style(user_id: int):
    return get_user_button_style(user_id)

def build_main_dashboard(user_id: int):
    """Main dashboard for Profile Manager Pro."""
    style = get_style(user_id)
    keyboard = [
        [
            InlineKeyboardButton("👦 Set All Boy", "xprof_conf_boy", style=style),
            InlineKeyboardButton("👧 Set All Girl", "xprof_conf_girl", style=style)
        ],
        [
            InlineKeyboardButton("🔄 Set All Random", "xprof_conf_random", style=style),
            InlineKeyboardButton("🔙 Undo All Random", "xprof_conf_undo", style=style)
        ],
        [
            InlineKeyboardButton("📱 Manage Sessions", "xprof_list_1", style=style)
        ],
        [
            InlineKeyboardButton("❌ Close", "xprof_close", style=style)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_session_list(page: int, sessions_data: list, total_pages: int, user_id: int):
    """Paginated session list for profile management."""
    style = get_style(user_id)
    keyboard = []
    
    # 2 columns for sessions
    row = []
    for i, session in enumerate(sessions_data):
        idx = session['index']
        name = session['name']
        lock_status = "🔒" if session['locked'] else "🔓"
        gender_icon = "👦" if session['gender'] == "boy" else ("👧" if session['gender'] == "girl" else "🎲")
        
        btn_text = f"{lock_status} {gender_icon} {name[:10]}"
        row.append(InlineKeyboardButton(btn_text, f"xprof_edit_{idx}_{page}", style=style))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    # Navigation Layout
    if total_pages > 1:
        # Row 1: [ « ] [n/n] [ » ]
        nav_row1 = [
            InlineKeyboardButton("«", f"xprof_list_{page-1}" if page > 1 else "xprof_noop", style=style),
            InlineKeyboardButton(f"{page}/{total_pages}", "xprof_noop", style=style),
            InlineKeyboardButton("»", f"xprof_list_{page+1}" if page < total_pages else "xprof_noop", style=style)
        ]
        keyboard.append(nav_row1)
        
        # Row 2: [First] [Last]
        nav_row2 = [
            InlineKeyboardButton("First", "xprof_list_1", style=style),
            InlineKeyboardButton("Last", f"xprof_list_{total_pages}", style=style)
        ]
        keyboard.append(nav_row2)
    
    # Row 3: [ « Back » ]
    keyboard.append([InlineKeyboardButton("« Back »", "xprof_main", style=style)])
    
    return InlineKeyboardMarkup(keyboard)

def build_edit_menu(session_idx: int, page: int, data: dict, user_id: int):
    """Individual session editing menu."""
    style = get_style(user_id)
    is_locked = data.get("is_locked", False)
    lock_text = "🔓 Unlock Persona" if is_locked else "🔒 Lock Persona"
    gender = data.get("gender", "random")
    
    keyboard = [
        [
            InlineKeyboardButton("🖼 Change Photo", f"xprof_ask_avatar_{session_idx}_{page}", style=style),
            InlineKeyboardButton("⚙️ Photo Source", f"xprof_picsrc_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("✍️ Edit Bio", f"xprof_editbio_{session_idx}_{page}", style=style),
            InlineKeyboardButton("🤖 Auto Bio", f"xprof_ask_autobio_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("👤 Auto Uname", f"xprof_ask_autousr_{session_idx}_{page}", style=style),
            InlineKeyboardButton("⚙️ Format Uname", f"xprof_usrfmt_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("👦 Set Boy", f"xprof_ask_setboy_{session_idx}_{page}", style=style),
            InlineKeyboardButton("👧 Set Girl", f"xprof_ask_setgirl_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("🎲 Set Random", f"xprof_ask_setrandom_{session_idx}_{page}", style=style),
            InlineKeyboardButton(lock_text, f"xprof_lock_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("✨ AI Randomize All", f"xprof_ask_gen_{session_idx}_{page}", style=style),
            InlineKeyboardButton("👁 Preview Identity", f"xprof_pregen_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("🔙 Undo Change", f"xprof_ask_undo_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("« Back »", f"xprof_list_{page}", style=style)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_preview_menu(session_idx: int, page: int, user_id: int, current_gender: str = "random"):
    """Menu for previewing a generated identity draft."""
    style = get_style(user_id)
    keyboard = [
        [
            InlineKeyboardButton("✅ Apply Profile", f"xprof_apply_{session_idx}_{page}", style=style),
            InlineKeyboardButton("🔄 Regen All", f"xprof_pregen_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("🖼 Regen Photo", f"xprof_regenpic_{session_idx}_{page}", style=style),
            InlineKeyboardButton("👤 Regen Name", f"xprof_regename_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("📝 Regen Bio", f"xprof_regenbio_{session_idx}_{page}", style=style),
            InlineKeyboardButton("🔗 Regen Username", f"xprof_regenusr_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton(f"{'👦' if current_gender == 'boy' else '⚪️'} Boy", f"xprof_prvgen_boy_{session_idx}_{page}", style=style),
            InlineKeyboardButton(f"{'👧' if current_gender == 'girl' else '⚪️'} Girl", f"xprof_prvgen_girl_{session_idx}_{page}", style=style),
            InlineKeyboardButton(f"{'🎲' if current_gender == 'random' else '⚪️'} Rand", f"xprof_prvgen_random_{session_idx}_{page}", style=style)
        ],
        [
            InlineKeyboardButton("❌ Cancel", f"xprof_edit_{session_idx}_{page}", style=style)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_individual_confirmation(action: str, session_idx: int, page: int, user_id: int):
    """Confirmation menu for a specific action on a single session."""
    style = get_style(user_id)
    
    # Map internal action names to human readable labels
    labels = {
        "avatar": "Update Foto Profil (AI)",
        "autobio": "Generate Bio Otomatis",
        "autousr": "Generate Username Otomatis",
        "undo": "Undo Perubahan Terakhir",
        "setboy": "Atur Gender: LAKI-LAKI",
        "setgirl": "Atur Gender: PEREMPUAN",
        "setrandom": "Atur Gender: RANDOM",
        "gen": "Update Semua Identitas (AI)"
    }
    label = labels.get(action, action.capitalize())
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Ya, Lakukan", f"xprof_do_{action}_{session_idx}_{page}", style=style),
            InlineKeyboardButton("❌ Batal", f"xprof_edit_{session_idx}_{page}", style=style)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_username_settings(session_idx: int, page: int, current_fmt: str, user_id: int):
    """Submenu to choose username structure."""
    style = get_style(user_id)
    
    def get_btn_text(fmt, label):
        return f"✅ {label}" if current_fmt == fmt else label

    keyboard = [
        [InlineKeyboardButton(get_btn_text("pattern1", "nama_xy123"), f"xprof_setfmt_pattern1_{session_idx}_{page}", style=style)],
        [InlineKeyboardButton(get_btn_text("pattern2", "real_namax12"), f"xprof_setfmt_pattern2_{session_idx}_{page}", style=style)],
        [InlineKeyboardButton(get_btn_text("pattern3", "official_nama_999"), f"xprof_setfmt_pattern3_{session_idx}_{page}", style=style)],
        [InlineKeyboardButton(get_btn_text("random", "🎲 Random Mixed"), f"xprof_setfmt_random_{session_idx}_{page}", style=style)],
        [InlineKeyboardButton("« Back to Manage Session", f"xprof_edit_{session_idx}_{page}", style=style)]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_avatar_src_settings(session_idx: int, page: int, current_src: str, user_id: int):
    """Submenu to choose avatar source."""
    style = get_style(user_id)
    
    def get_btn_text(src, label):
        return f"✅ {label}" if current_src == src else label

    keyboard = [
        [InlineKeyboardButton(get_btn_text("xsgames", "XSGames (HQ / Sync Gender)"), f"xprof_setpicsrc_xsgames_{session_idx}_{page}", style=style)],
        [InlineKeyboardButton(get_btn_text("pinterest", "📌 Pinterest (Aesthetic / Scrape)"), f"xprof_setpicsrc_pinterest_{session_idx}_{page}", style=style)],
        [InlineKeyboardButton(get_btn_text("tpdne", "ThisPersonDoesNotExist (HQ / Random)"), f"xprof_setpicsrc_tpdne_{session_idx}_{page}", style=style)],
        [InlineKeyboardButton(get_btn_text("randomuser", "RandomUser (LQ / Sync Gender)"), f"xprof_setpicsrc_randomuser_{session_idx}_{page}", style=style)],
        [InlineKeyboardButton("🏷 Set Pinterest Keyword", f"xprof_pinkey_{session_idx}_{page}", style=style)],
        [InlineKeyboardButton("« Back to Manage Session", f"xprof_edit_{session_idx}_{page}", style=style)]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_confirmation_menu(gender: str, user_id: int):
    """Confirmation menu for bulk actions."""
    style = get_style(user_id)
    keyboard = [
        [
            InlineKeyboardButton("✅ Ya, Eksekusi", f"xprof_bulk_{gender}", style=style),
            InlineKeyboardButton("❌ Batal", "xprof_main", style=style)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
