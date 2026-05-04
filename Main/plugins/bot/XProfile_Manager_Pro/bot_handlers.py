# Main/plugins/bot/XProfile_Manager_Pro/bot_handlers.py
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, InlineQuery, InlineQueryResultArticle, 
    InputTextMessageContent, Message, ForceReply,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from Main import Altruix
from Main.core.decorators import log_errors, iuser_check

# Import modular components from the userbot plugin folder
from Main.plugins.userbot.XProfile_Manager_Pro.db_handler import db_handler
from Main.plugins.userbot.XProfile_Manager_Pro.identity_gen import generate_identity, get_avatar_url, generate_username
from Main.plugins.userbot.XProfile_Manager_Pro.ui_builder import (
    build_main_dashboard, build_session_list, 
    build_edit_menu, build_confirmation_menu,
    build_username_settings, build_individual_confirmation,
    build_preview_menu, build_avatar_src_settings
)
import aiohttp
import asyncio
import random
from PIL import Image
import io

logger = logging.getLogger("altruix.xprofile.bot")

# Shared Background Task Logic (duplicated or imported)
# To keep it consistent, we'll use the same queue if possible, 
# but Altruix plugins usually handle their own state.
# However, since we're in the same process, we can import it.
from Main.plugins.userbot.XProfile_Manager_Pro.main import (
    UPDATE_QUEUE, profile_update_task, STATE, PLUGIN_VERSION
)

async def get_profile_preview_text(client, me, db_data):
    """Helper to generate the profile preview text."""
    try:
        full_me = await client.get_me()
        curr_name = f"{full_me.first_name} {full_me.last_name or ''}".strip()
        curr_bio = full_me.bio or "Tidak ada bio"
        curr_username = f"@{full_me.username}" if full_me.username else "Tidak ada"
    except Exception:
        curr_name = me.first_name or "Unknown"
        curr_bio = "Gagal memuat bio"
        curr_username = "Unknown"
        
    return (
        f"<blockquote expandable>"
        f"<b>👤 Manage Session:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"• Account:  {me.first_name or ''} {me.last_name or ''}\n"
        f"• ID: <code>{me.id}</code>\n"
        f"• Username: {curr_username}\n\n"
        f"<b>📝 Profile Preview:</b>\n"
        f"• <b>Name:</b> <code>{curr_name}</code>\n"
        f"• <b>Bio:</b> <i>{curr_bio}</i>\n\n"
        f"<b>⚙️ Status:</b>\n"
        f"• <b>Lock:</b> {'🔒 LOCKED' if db_data.get('is_locked') else '🔓 UNLOCKED'}\n"
        f"• <b>Pref Gender:</b> <code>{db_data.get('gender', 'random').upper()}</code>"
        f"</blockquote>"
    )

async def strip_metadata(image_bytes: bytes) -> bytes:
    """Remove metadata from image using Pillow."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        data = list(img.getdata())
        img_without_exif = Image.new(img.mode, img.size)
        img_without_exif.putdata(data)
        
        output = io.BytesIO()
        img_without_exif.save(output, format="JPEG", quality=95)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Error stripping metadata: {e}")
        return image_bytes

@Altruix.bot.on_inline_query(filters.regex(r"^xprof_main_(.*)"))
@log_errors
@iuser_check
async def xprof_inline_handler(c: Client, iq: InlineQuery):
    user_id = iq.from_user.id
    text = (
        f"<blockquote expandable>"
        f"<b>💎 Profile Manager Pro v{PLUGIN_VERSION}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Kelola identitas semua sesi Anda dengan mudah.\n"
        "Gunakan fitur bulk untuk update massal atau edit per sesi.\n\n"
        "<i>Pilih menu di bawah ini:</i>"
        f"</blockquote>"
    )
    
    await iq.answer(
        [
            InlineQueryResultArticle(
                id="main",
                title="Profile Manager Pro Dashboard",
                description="Manage your userbot identities.",
                input_message_content=InputTextMessageContent(text),
                reply_markup=build_main_dashboard(user_id)
            )
        ],
        cache_time=0,
        is_personal=True
    )

@Altruix.bot.on_callback_query(filters.regex(r"^xprof_(.*)"))
@log_errors
async def xprof_callback_handler(c: Client, cb: CallbackQuery):
    data = cb.data.split("_")
    action = data[1]
    user_id = cb.from_user.id
    
    # Auth Check (Only Owner/Sudo)
    if not await Altruix.is_sudo(user_id):
        return await cb.answer("Anda tidak memiliki izin!", show_alert=True)

    if action == "main":
        text = (
            f"<blockquote expandable>"
            f"<b>💎 Profile Manager Pro v{PLUGIN_VERSION}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Kelola identitas semua sesi Anda dengan mudah.\n"
            "Gunakan fitur bulk untuk update massal atau edit per sesi.\n\n"
            "<i>Pilih menu di bawah ini:</i>"
            f"</blockquote>"
        )
        await cb.edit_message_text(text, reply_markup=build_main_dashboard(user_id))

    elif action == "conf":
        gender = data[2]
        if gender == "undo":
            text = (
                f"<blockquote expandable>"
                f"<b>⚠️ KONFIRMASI UNDO MASSAL</b>\n\n"
                f"Apakah Anda yakin ingin membatalkan perubahan massal sebelumnya?\n"
                f"Tindakan ini akan mengembalikan Nama dan Bio ke versi sebelum diubah (jika backup tersedia)."
                f"</blockquote>"
            )
        else:
            text = (
                f"<blockquote expandable>"
                f"<b>⚠️ KONFIRMASI UPDATE MASSAL</b>\n\n"
                f"Apakah Anda yakin ingin memperbarui profil semua sesi ke mode <b>{gender.upper()}</b>?\n"
                f"Proses ini akan memakan waktu tergantung jumlah sesi Anda."
                f"</blockquote>"
            )
        await cb.edit_message_text(text, reply_markup=build_confirmation_menu(gender, user_id))

    elif action == "list":
        page = int(data[2])
        sessions_per_page = 10
        total_sessions = len(Altruix.clients)
        total_pages = (total_sessions + sessions_per_page - 1) // sessions_per_page
        
        start = (page - 1) * sessions_per_page
        end = start + sessions_per_page
        
        sessions_list = []
        for i in range(start, min(end, total_sessions)):
            client = Altruix.clients[i]
            me = getattr(client, 'myself', None)
            if not me: continue
            
            db_data = await db_handler.get_profile_data(me.id)
            sessions_list.append({
                "index": i,
                "name": me.first_name,
                "locked": db_data.get("is_locked", False),
                "gender": db_data.get("gender", "random")
            })
            
        await cb.edit_message_text(
            f"<b>📱 Daftar Sesi ({total_sessions})</b>\nHalaman {page}/{total_pages}",
            reply_markup=build_session_list(page, sessions_list, total_pages, user_id)
        )

    elif action == "edit":
        idx = int(data[2])
        page = int(data[3])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        db_data = await db_handler.get_profile_data(me.id)
        text = await get_profile_preview_text(client, me, db_data)
        
        if cb.message and getattr(cb.message, 'media', None):
            try: await cb.message.delete()
            except: pass
            await c.send_message(cb.message.chat.id, text, reply_markup=build_edit_menu(idx, page, db_data, user_id))
        else:
            await cb.edit_message_text(text, reply_markup=build_edit_menu(idx, page, db_data, user_id))

    elif action == "lock":
        idx = int(data[2])
        page = int(data[3])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        new_status = await db_handler.toggle_lock(me.id)
        await cb.answer(f"Status Lock: {'LOCKED' if new_status else 'UNLOCKED'}")
        
        # Refresh Menu
        db_data = await db_handler.get_profile_data(me.id)
        text = await get_profile_preview_text(client, me, db_data)
        await cb.edit_message_text(text, reply_markup=build_edit_menu(idx, page, db_data, user_id))

    elif action == "ask":
        # xprof_ask_{sub_action}_{idx}_{page}
        sub_action = data[2]
        idx = int(data[3])
        page = int(data[4])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        labels = {
            "avatar": "Update Foto Profil (AI)",
            "autobio": "Generate Bio Otomatis",
            "autousr": "Generate Username Otomatis",
            "setboy": "Atur Gender: LAKI-LAKI",
            "setgirl": "Atur Gender: PEREMPUAN",
            "setrandom": "Atur Gender: RANDOM",
            "gen": "Update Semua Identitas (AI)"
        }
        label = labels.get(sub_action, sub_action.capitalize())
        
        text = (
            f"<b>⚠️ KONFIRMASI TINDAKAN</b>\n\n"
            f"Sesi: <b>{me.first_name}</b> (<code>{me.id}</code>)\n"
            f"Tindakan: <b>{label}</b>\n\n"
            f"Apakah Anda yakin ingin melanjutkan?"
        )
        await cb.edit_message_text(text, reply_markup=build_individual_confirmation(sub_action, idx, page, user_id))

    elif action == "do":
        # xprof_do_{sub_action}_{idx}_{page}
        sub_action = data[2]
        idx = int(data[3])
        page = int(data[4])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        if await db_handler.is_locked(me.id) and sub_action != "unlock":
            return await cb.answer("Sesi ini terkunci!", show_alert=True)

        # Save Backup before changes (only for profile-modifying actions, excluding undo)
        if sub_action in ["avatar", "autobio", "autousr", "gen", "setboy", "setgirl", "setrandom"]:
            try:
                full_me = await client.get_me()
                await db_handler.save_backup(
                    me.id,
                    full_me.first_name,
                    full_me.last_name or "",
                    full_me.bio or ""
                )
            except Exception as eb:
                logger.warning(f"Failed to save backup for {me.id}: {eb}")

        if sub_action == "undo":
            backup = await db_handler.get_backup(me.id)
            if not backup:
                return await cb.answer("Tidak ada data backup untuk sesi ini!", show_alert=True)
            
            try:
                await client.update_profile(
                    first_name=backup.get('first_name', ''),
                    last_name=backup.get('last_name', ''),
                    bio=backup.get('bio', '')
                )
            except Exception as e:
                return await cb.answer(f"❌ Gagal Undo: {e}", show_alert=True)

        elif sub_action == "setboy":
            await db_handler.set_gender(me.id, "boy")
            await cb.answer("Sesi diatur ke mode LAKI-LAKI")
            # Immediate update
            name, bio, username = generate_identity("boy")
            names = name.split(" ", 1)
            first, last = names[0], names[1] if len(names) > 1 else ""
            await client.update_profile(first_name=first, last_name=last, bio=bio)

        elif sub_action == "setgirl":
            await db_handler.set_gender(me.id, "girl")
            await cb.answer("Sesi diatur ke mode PEREMPUAN")
            name, bio, username = generate_identity("girl")
            names = name.split(" ", 1)
            first, last = names[0], names[1] if len(names) > 1 else ""
            await client.update_profile(first_name=first, last_name=last, bio=bio)

        elif sub_action == "setrandom":
            await db_handler.set_gender(me.id, "random")
            await cb.answer("Sesi diatur ke mode RANDOM")
            name, bio, username = generate_identity("random")
            names = name.split(" ", 1)
            first, last = names[0], names[1] if len(names) > 1 else ""
            await client.update_profile(first_name=first, last_name=last, bio=bio)

        elif sub_action == "autobio":
            await cb.answer("Menghasilkan bio otomatis...")
            db_data = await db_handler.get_profile_data(me.id)
            gender = db_data.get("gender", "random")
            _, new_bio, _ = generate_identity(gender)
            await client.update_profile(bio=new_bio)

        elif sub_action == "autousr":
            await cb.answer("Menghasilkan username otomatis...")
            db_data = await db_handler.get_profile_data(me.id)
            fmt = db_data.get("usr_format", "random")
            new_username = generate_username(me.first_name, usr_format=fmt)
            try:
                await client.set_username(new_username)
            except Exception as e:
                return await cb.answer(f"Gagal ubah username: {e}", show_alert=True)

        elif sub_action == "avatar":
            await cb.answer("Mengunduh avatar baru...")
            db_data = await db_handler.get_profile_data(me.id)
            gender = db_data.get("gender", "random")
            avatar_src = db_data.get("avatar_src", "xsgames")
            pin_keyword = db_data.get("pinterest_keyword")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(await get_avatar_url(gender, avatar_src, keyword=pin_keyword)) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            clean_img = await strip_metadata(img_data)
                            temp_path = f"cache/avatar_{me.id}.jpg"
                            with open(temp_path, "wb") as f: f.write(clean_img)
                            await client.set_profile_photo(photo=temp_path)
                        else:
                            return await cb.answer(f"❌ API {avatar_src} error (Status: {resp.status})", show_alert=True)
            except Exception as e:
                return await cb.answer(f"❌ Gagal koneksi ke {avatar_src}: {e}", show_alert=True)

        elif sub_action == "gen":
            await cb.answer("Menghasilkan identitas baru...")
            db_data = await db_handler.get_profile_data(me.id)
            gender = db_data.get("gender", "random")
            name, bio, username = generate_identity(gender)
            names = name.split(" ", 1)
            first, last = names[0], names[1] if len(names) > 1 else ""
            await client.update_profile(first_name=first, last_name=last, bio=bio)

        # Finalize
        await cb.answer("✅ Berhasil dieksekusi!", show_alert=True)
        db_data = await db_handler.get_profile_data(me.id)
        text = await get_profile_preview_text(client, me, db_data)
        await cb.edit_message_text(text, reply_markup=build_edit_menu(idx, page, db_data, user_id))

    elif action == "pregen":
        idx = int(data[2])
        page = int(data[3])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        await cb.answer("Menghasilkan draf identitas...")
        
        db_data = await db_handler.get_profile_data(me.id)
        gender = db_data.get("gender", "random")
        fmt = db_data.get("usr_format", "random")
        avatar_src = db_data.get("avatar_src", "xsgames")
        pin_keyword = db_data.get("pinterest_keyword")
        
        name, bio, _ = generate_identity(gender)
        # Generate username based on draft name and preferred format
        username = generate_username(name.split()[0], usr_format=fmt)
        
        draft = {
            "name": name,
            "bio": bio,
            "username": username,
            "avatar": await get_avatar_url(gender, avatar_src, keyword=pin_keyword),
            "avatar_src": avatar_src
        }
        
        await db_handler.update_profile_data(me.id, {"persona": draft})
        
        text = (
            f"<b>👁 PREVIEW IDENTITAS BARU</b>\n"
            f"  Sesi: {me.first_name}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"  • <b>Name:</b> <code>{name}</code>\n"
            f"  • <b>Bio:</b> <i>{bio}</i>\n"
            f"  • <b>Username:</b> @{username}\n"
            f"  • <b>Gender:</b> <code>{gender.upper()}</code>\n"
            f"  • <b>Source Photo:</b> <code>{avatar_src.upper()}</code>\n\n"
            f"<i>Apakah Anda ingin menerapkan identitas ini?</i>"
        )
        
        try:
            # Send as photo message for better UX
            chat_id = cb.message.chat.id if cb.message else user_id
            if cb.message:
                try: await cb.message.delete()
                except: pass
            await c.send_photo(
                chat_id=chat_id,
                photo=draft['avatar'],
                caption=text,
                reply_markup=build_preview_menu(idx, page, user_id, current_gender=gender)
            )
        except Exception:
            # Fallback to text if photo fails
            await cb.edit_message_text(text + f"\n\n🖼 <a href='{draft['avatar']}'>Avatar Link ({draft.get('avatar_src', 'xsgames').upper()})</a>", reply_markup=build_preview_menu(idx, page, user_id, current_gender=gender))

    elif action == "prvgen":
        new_gender = data[2]
        idx = int(data[3])
        page = int(data[4])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        await cb.answer(f"Gender diubah ke: {new_gender.capitalize()}! Memperbarui draf...")
        
        await db_handler.update_profile_data(me.id, {"gender": new_gender})
        db_data = await db_handler.get_profile_data(me.id)
        fmt = db_data.get("usr_format", "random")
        avatar_src = db_data.get("avatar_src", "xsgames")
        pin_keyword = db_data.get("pinterest_keyword")
        
        name, bio, _ = generate_identity(new_gender)
        username = generate_username(name.split()[0], usr_format=fmt)
        
        draft = {
            "name": name,
            "bio": bio,
            "username": username,
            "avatar": await get_avatar_url(new_gender, avatar_src, keyword=pin_keyword),
            "avatar_src": avatar_src
        }
        await db_handler.update_profile_data(me.id, {"persona": draft})
        
        text = (
            f"<b>👁 PREVIEW IDENTITAS BARU</b>\n"
            f"  Sesi: {me.first_name}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"  • <b>Name:</b> <code>{draft['name']}</code>\n"
            f"  • <b>Bio:</b> <i>{draft['bio']}</i>\n"
            f"  • <b>Username:</b> @{draft['username']}\n"
            f"  • <b>Gender:</b> <code>{new_gender.upper()}</code>\n"
            f"  • <b>Source Photo:</b> <code>{avatar_src.upper()}</code>\n\n"
            f"<i>Apakah Anda ingin menerapkan identitas ini?</i>"
        )
        
        try:
            chat_id = cb.message.chat.id if cb.message else user_id
            if cb.message:
                try: await cb.message.delete()
                except: pass
            await c.send_photo(
                chat_id=chat_id,
                photo=draft['avatar'],
                caption=text,
                reply_markup=build_preview_menu(idx, page, user_id, current_gender=new_gender)
            )
        except Exception:
            await cb.edit_message_text(text + f"\n\n🖼 <a href='{draft['avatar']}'>Avatar Link ({draft.get('avatar_src', 'xsgames').upper()})</a>", 
                                     reply_markup=build_preview_menu(idx, page, user_id, current_gender=new_gender))

    elif action in ["regenpic", "regename", "regenbio", "regenusr"]:
        idx = int(data[2])
        page = int(data[3])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        await cb.answer("Memperbarui draf identitas...")
        
        db_data = await db_handler.get_profile_data(me.id)
        gender = db_data.get("gender", "random")
        fmt = db_data.get("usr_format", "random")
        draft = db_data.get("persona", {})
        
        if not draft:
            return await cb.answer("Tidak ada draf identitas!", show_alert=True)
            
        if action == "regenpic":
            avatar_src = db_data.get("avatar_src", "xsgames")
            pin_keyword = db_data.get("pinterest_keyword")
            draft["avatar"] = await get_avatar_url(gender, avatar_src, keyword=pin_keyword)
            draft["avatar_src"] = avatar_src
        elif action == "regename":
            new_name, _, _ = generate_identity(gender)
            draft["name"] = new_name
        elif action == "regenbio":
            _, new_bio, _ = generate_identity(gender)
            draft["bio"] = new_bio
        elif action == "regenusr":
            # Generate new username based on the CURRENT draft name
            draft["username"] = generate_username(draft["name"].split()[0], usr_format=fmt)
            
        await db_handler.update_profile_data(me.id, {"persona": draft})
        
        text = (
            f"<b>👁 PREVIEW IDENTITAS BARU</b>\n"
            f"  Sesi: {me.first_name}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"  • <b>Name:</b> <code>{draft['name']}</code>\n"
            f"  • <b>Bio:</b> <i>{draft['bio']}</i>\n"
            f"  • <b>Username:</b> @{draft['username']}\n"
            f"  • <b>Gender:</b> <code>{gender.upper()}</code>\n"
            f"  • <b>Source Photo:</b> <code>{draft.get('avatar_src', 'xsgames').upper()}</code>\n\n"
            f"<i>Apakah Anda ingin menerapkan identitas ini?</i>"
        )
        
        try:
            chat_id = cb.message.chat.id if cb.message else user_id
            if cb.message:
                try: await cb.message.delete()
                except: pass
            await c.send_photo(
                chat_id=chat_id,
                photo=draft['avatar'],
                caption=text,
                reply_markup=build_preview_menu(idx, page, user_id, current_gender=gender)
            )
        except Exception:
            await cb.edit_message_text(text + f"\n\n🖼 <a href='{draft['avatar']}'>Avatar Link ({draft.get('avatar_src', 'xsgames').upper()})</a>", reply_markup=build_preview_menu(idx, page, user_id, current_gender=gender))

    elif action == "apply":
        idx = int(data[2])
        page = int(data[3])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        db_data = await db_handler.get_profile_data(me.id)
        draft = db_data.get("persona", {})
        
        if not draft:
            return await cb.answer("Tidak ada draf untuk diterapkan!", show_alert=True)
            
        await cb.answer("Menerapkan identitas...")
        
        # Save Backup first
        full_me = await client.get_me()
        await db_handler.save_backup(me.id, full_me.first_name, full_me.last_name or "", full_me.bio or "")
        
        try:
            # 1. Profile
            names = draft['name'].split(" ", 1)
            first = names[0]
            last = names[1] if len(names) > 1 else ""
            await client.update_profile(first_name=first, last_name=last, bio=draft['bio'])
            
            # 2. Username
            try:
                await client.set_username(draft['username'])
            except Exception: pass
            
            # 3. Avatar
            async with aiohttp.ClientSession() as session:
                async with session.get(draft['avatar']) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        clean_img = await strip_metadata(img_data)
                        temp_path = f"cache/avatar_{me.id}.jpg"
                        with open(temp_path, "wb") as f: f.write(clean_img)
                        await client.set_profile_photo(photo=temp_path)
            
            await cb.answer("✅ Identitas berhasil diterapkan!", show_alert=True)
            # Clear Draft
            await db_handler.update_profile_data(me.id, {"persona": {}})
            
            # Refresh Menu
            db_data = await db_handler.get_profile_data(me.id)
            text = await get_profile_preview_text(client, me, db_data)
            
            if cb.message and getattr(cb.message, 'media', None):
                try: await cb.message.delete()
                except: pass
                await c.send_message(cb.message.chat.id, text, reply_markup=build_edit_menu(idx, page, db_data, user_id))
            else:
                await cb.edit_message_text(text, reply_markup=build_edit_menu(idx, page, db_data, user_id))
            
        except Exception as e:
            await cb.answer(f"❌ Gagal menerapkan: {e}", show_alert=True)

    elif action == "usrfmt":
        idx = int(data[2])
        page = int(data[3])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        db_data = await db_handler.get_profile_data(me.id)
        fmt = db_data.get("usr_format", "random")
        
        await cb.edit_message_text(
            f"<b>⚙️ Username Format Settings</b>\nSession: <code>{me.id}</code>\n\n"
            f"Pilih struktur username yang diinginkan untuk sesi ini:",
            reply_markup=build_username_settings(idx, page, fmt, user_id)
        )

    elif action == "setfmt":
        fmt = data[2]
        idx = int(data[3])
        page = int(data[4])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        await db_handler.set_username_format(me.id, fmt)
        await cb.answer(f"Format username diatur ke: {fmt}")
        
        # Refresh Menu
        await cb.edit_message_text(
            f"<b>⚙️ Username Format Settings</b>\nSession: <code>{me.id}</code>\n\n"
            f"Pilih struktur username yang diinginkan untuk sesi ini:",
            reply_markup=build_username_settings(idx, page, fmt, user_id)
        )

    elif action == "picsrc":
        idx = int(data[2])
        page = int(data[3])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        db_data = await db_handler.get_profile_data(me.id)
        current_src = db_data.get("avatar_src", "xsgames")
        
        await cb.edit_message_text(
            f"<b>⚙️ Photo Source Settings</b>\nSession: <code>{me.id}</code>\n\n"
            f"Pilih sumber website/API untuk menghasilkan Avatar profil:",
            reply_markup=build_avatar_src_settings(idx, page, current_src, user_id)
        )

    elif action == "setpicsrc":
        src = data[2]
        idx = int(data[3])
        page = int(data[4])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        await db_handler.set_avatar_src(me.id, src)
        await cb.answer(f"Sumber avatar diatur ke: {src}")
        
        await cb.edit_message_text(
            f"<b>⚙️ Photo Source Settings</b>\nSession: <code>{me.id}</code>\n\n"
            f"Pilih sumber website/API untuk menghasilkan Avatar profil:",
            reply_markup=build_avatar_src_settings(idx, page, src, user_id)
        )

    elif action == "pinkey":
        if not cb.message:
            return await cb.answer("❌ Fitur ini hanya tersedia jika bot ditambahkan ke grup atau di Private Chat. Silakan buka bot secara langsung.", show_alert=True)
            
        idx = int(data[2])
        page = int(data[3])
        client = Altruix.clients[idx]
        me = getattr(client, 'myself', None)
        
        db_data = await db_handler.get_profile_data(me.id)
        current = db_data.get("pinterest_keyword") or "Default (Gender Based)"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel Input", f"xprof_cancelpin_{me.id}")]
        ])
        
        await cb.answer("Silakan balas pesan instruksi yang muncul.", show_alert=False)
        await cb.message.reply_text(
            f"📌 <b>Pinterest Keyword</b>\nSession: <code>{me.id}</code>\n"
            f"Keyword saat ini: <code>{current}</code>\n\n"
            f"Silakan <b>Balas (Reply)</b> pesan ini dengan keyword baru untuk pencarian Pinterest.\n\n"
            f"Ketik <code>reset</code> untuk mengembalikan ke default.",
            reply_markup=keyboard
        )

    elif action == "cancelpin":
        if cb.message:
            await cb.message.delete()
        await cb.answer("❌ Input dibatalkan.", show_alert=True)

    elif action == "bulk":
        gender = data[2]
        if STATE["is_processing"]:
            return await cb.answer("Masih ada proses update yang berjalan!", show_alert=True)
            
        count = 0
        for i in range(len(Altruix.clients)):
            await UPDATE_QUEUE.put((i, gender, user_id))
            count += 1
            
        asyncio.create_task(profile_update_task())
        await cb.answer(f"Memulai update massal untuk {count} sesi...", show_alert=True)

    elif action == "close":
        if cb.message:
            await cb.message.delete()
        
    elif action == "noop":
        await cb.answer()

@Client.on_message(filters.reply & filters.user(Altruix.config.OWNER_USERS_ID))
async def handle_pinkey_input(c: Client, m: Message):
    if not m.reply_to_message or not m.reply_to_message.text:
        return
    
    if "Pinterest Keyword" not in m.reply_to_message.text:
        return
    
    # Extract session ID from the reply text
    import re
    session_match = re.search(r"Session: <code>(\d+)</code>", m.reply_to_message.text)
    if not session_match:
        return
    
    session_id = int(session_match.group(1))
    keyword = m.text.strip()
    
    if keyword.lower() == "reset":
        await db_handler.set_pinterest_keyword(session_id, None)
        await m.reply_text(f"✅ Pinterest keyword untuk sesi <code>{session_id}</code> telah di-reset ke default.")
    else:
        await db_handler.set_pinterest_keyword(session_id, keyword)
        await m.reply_text(f"✅ Pinterest keyword untuk sesi <code>{session_id}</code> diatur ke: <code>{keyword}</code>")
