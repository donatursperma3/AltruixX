# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


PLUGIN_VERSION = "0.0.71"
import os
import html
import asyncio
import io
import aiofiles
from Main import Altruix
from logging import info
from Main.utils.paste import Paste
from pyrogram import Client, enums, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from time import perf_counter as pc
from Main.core.config import TGLIMITS
from Main.core.types.message import Message
from Main.utils.dev_func import eval_py, exec_terminal
from Main.core.decorators import log_errors, iuser_check
from Main.utils.file_helpers import get_user_button_style
from Main.utils.essentials import Essentials


@Altruix.register_on_cmd(
    ["json"],
    cmd_help={
        "help": "Gets the json of the given message object.",
        "example": "json",
        "user_args": [
            {
                "arg": "p",
                "help": "Pastes the output to paste bin.",
                "requires_input": False,
            },
            {
                "arg": "f",
                "help": "Force sends the output as a file.",
                "requires_input": False,
            },
            {
                "arg": "s",
                "help": "Sends the output to log chat and deletes the command.",
                "requires_input": False,
            },
            {
                "arg": "d",
                "help": "Uploads the output as a document if it's too long.",
                "requires_input": False,
            },
        ],
    },
)
@log_errors
async def get_json_message_handler(c: Client, m: Message):
    user_args = m.user_args
    msg_id = m.id
    rm = m.reply_to_message
    m_ = await m.reply_msg("PROCESSING")
    # ✅ Using <pre> tags for structured JSON output to support better UI rendering
    jsonified = f"<pre>{html.escape(str(rm or m))}</pre>"
    cmd_ = "<b>jsonified</b>"
    
    # ✅ FIX: user_args is a list of Arg objects, not strings.
    # We extract keys for flag checking.
    arg_keys = [a.key.lower() for a in user_args]
    
    jsonified_raw = str(rm or m)
    if len(jsonified) > 4000 and not ("f" in arg_keys or "p" in arg_keys or "d" in arg_keys):
        try:
            log_chat_id = await Altruix.config.get_env("LOG_CHAT_ID")
            if log_chat_id:
                file = io.BytesIO(jsonified_raw.encode("utf-8"))
                file.name = "message.json"
                
                await c.send_document(
                    int(log_chat_id), 
                    document=file, 
                    caption=f"📦 <b>JSON Output Dump</b>\n\n<i>From Chat:</i> <code>{getattr(m.chat, 'title', m.chat.id)}</code>"
                )
                await m_.edit_text("⚠️ <b>MESSAGE_TOO_LONG</b>\nOutput exceeds Telegram limits. I have safely uploaded the `.json` file to your <b>Log Group</b>!")
            else:
                await m_.edit_text("❌ <b>MESSAGE_TOO_LONG</b>\n<i>Output is too long. Please configure LOG_CHAT_ID or use <code>.json -f</code>.</i>")
        except Exception as e:
            await m_.edit_text(f"❌ <b>Log Routing Failed</b>\n<code>{e}</code>")
    else:
        try:
            await m_.edit_msg(
                jsonified,
                force_paste="p" in arg_keys,
                force_file=f"message.json;{cmd_}" if "f" in arg_keys else None,
                too_long_as_file="message.json" if "d" in arg_keys else False,
                reply_to_message_id=msg_id,
            )
        except Exception as e:
            if "MESSAGE_TOO_LONG" in str(e):
                await m_.edit_text("❌ <b>MESSAGE_TOO_LONG</b>\n<i>Please use <code>.json -f</code> to send as a file.</i>")
            else:
                await m_.edit_text(f"❌ <b>Error:</b> <code>{e}</code>")

    await m.delete_if_self()


@Altruix.register_on_cmd(
    ["ex", "exec", "eval"],
    cmd_help={
        "help": (
            "Executes Python snippets. <b>Premium Feature:</b> Automatically handles Telegram's 4096 character limit "
            "by uploading results to 11.bin or sending as a .txt file. 'Processing' messages are auto-deleted."
        ),
        "example": ".eval print('Hello')\n.eval -p [code] (Force paste)\n.eval -s [code] (Send to logs)",
        "user_args": [
            {
                "arg": "p",
                "help": "Pastes the output to paste bin (11.bin) and provides a preview link.",
                "requires_input": False,
            },
            {
                "arg": "f",
                "help": "Force sends the output as a downloadable .txt file.",
                "requires_input": False,
            },
            {
                "arg": "s",
                "help": "Silent mode: Sends output to Log Chat and provides a VIEW link. Command is deleted.",
                "requires_input": False,
            },
        ],
    },
    just_exc=True,
)
@log_errors
async def evaluate_command_handler(c: Client, m: Message):
    msg_id = m.id
    m_ = await m.reply_msg("PROCESSING")
    user_args = m.user_args
    arg_keys = [a.key.lower() for a in user_args]
    cmd = m.raw_user_input
    if not cmd:
        await m_.edit_msg("INPUT_REQUIRED")
        return
    if "p" in user_args or "f" in user_args:
        cmd = (cmd.replace("paste", "").replace("file", "")).strip()

    # ✅ Tracking performance for evaluation
    start_time = pc()
    results = await eval_py(c, cmd, m)
    end_time = pc()
    time_taken = round(end_time - start_time, 3)

    header = f"<b>EVAL (v<code>{PLUGIN_VERSION}</code>)</b>\n"
    header += f"🕒 <code>{time_taken}s</code>\n\n"

    # ✅ Using <pre> for input/output blocks to support auto-detection of code types
    final_output = f"{header}<b>INPUT:</b>\n<pre>{html.escape(cmd)}</pre>\n\n<b>OUTPUT</b>:\n<pre>{html.escape(results.strip())}</pre>"
    cmd_ = (
        "<b>Output Of Command</b>"
        if len(cmd) >= 1000
        else f"<b>OUTPUT FOR COMMAND :</b> <code>{cmd}</code>" # Keep index code for short command titles
    )
    if "s" in user_args and Altruix.log_chat:
        if "p" in user_args:
            url = await Paste(final_output).paste()
            msg = await c.send_message(
                Altruix.log_chat, f"{cmd_} \n<b>Pasted to :</b> {url}"
            )
        elif "p" in user_args or len(final_output) >= TGLIMITS.MESSAGE_TEXT:
            file_path = f"out_bash_{m.id}.txt"
            async with aiofiles.open(file_path, "w") as f:
                await f.write(final_output)
            msg = await c.send_document(Altruix.log_chat, file_path, caption=cmd)
            if os.path.exists(file_path):
                os.remove(file_path)
        else:
            msg = await c.send_message(Altruix.log_chat, final_output)
        await m.reply_msg(f"<b>OUTPUT :</b> <blockquote><a href='{msg.link}'>VIEW</a></blockquote>")
        await asyncio.sleep(3)
        await m_.delete()
        return
    
    await m_.delete()
    await m.reply_msg(
        final_output,
        force_paste="p" in arg_keys,
        force_file=f"eval_output.txt;{cmd_}" if "f" in arg_keys else None,
        reply_to_message_id=msg_id,
    )
    await m.delete_if_self()


@Altruix.register_on_cmd(
    ["reval"],
    cmd_help={
        "help": (
            "Executes Python snippet from a replied message. Handles Telegram's character limits "
            "via auto-paste/file fallback. Processing messages are auto-deleted."
        ),
        "example": ".reval (replying to code)\n.reval -p (force paste result)\n.reval -s (send result to logs)",
        "user_args": [
            {
                "arg": "p",
                "help": "Pastes the output to paste bin (11.bin).",
                "requires_input": False,
            },
            {
                "arg": "s",
                "help": "Sends the output to Log Chat silently.",
                "requires_input": False,
            },
        ],
    },
)
@log_errors
async def re_evaluate_command_handler(c: Client, m: Message):
    rm = m.reply_to_message
    if not rm:
        return await m.reply_msg("REPLY_TO_MSG_REQUIRED")
    
    code = (rm.text or rm.caption or "").strip()
    if not code:
        return await m.reply_msg("NO_CODE_FOUND")

    # Start processing
    m_ = await m.reply_msg("PROCESSING")
    arg_keys = [a.key.lower() for a in m.user_args]
    
    start_time = pc()
    from pyrogram.errors import FloodWait as FW
    try:
        results = await eval_py(c, code, m)
    except FW as e:
        # Handling floodwait by waiting and retrying
        await asyncio.sleep(e.value)
        results = await eval_py(c, code, m)
    except Exception:
        import traceback
        results = traceback.format_exc()
    
    end_time = pc()
    time_taken = round(end_time - start_time, 3)
    
    header = f"<b>R-EVAL (v<code>{PLUGIN_VERSION}</code>)</b>\n"
    header += f"🕒 <code>{time_taken}s</code>\n\n"
    
    # Trim input if too long for preview
    code_preview = code[:500] + ("..." if len(code) > 500 else "")
    # ✅ Enhanced formatting for re-eval results using <pre> tags
    final_output = f"{header}<b>INPUT:</b>\n<pre>{html.escape(code_preview)}</pre>\n\n<b>OUTPUT</b>:\n<pre>{html.escape(results.strip())}</pre>"
    
    cmd_label = "<b>Re-Eval Output</b>"
    
    # Logic for sending to log chat if 's' flag is present
    if "s" in arg_keys and Altruix.log_chat:
        log_text = f"🎯 <b>R-Eval Log</b>\nUser: {m.from_user.id}\n\n{final_output}"
        try:
            if "p" in arg_keys:
                url = await Paste(log_text).paste()
                await c.send_message(Altruix.log_chat, f"{cmd_label}\n<b>Pasted to:</b> {url}")
            elif len(log_text) > TGLIMITS.MESSAGE_TEXT:
                file_name = f"reval_log_{m.id}.txt"
                async with aiofiles.open(file_name, "w", encoding="utf-8") as f:
                    await f.write(log_text)
                await c.send_document(Altruix.log_chat, file_name, caption=cmd_label)
                if os.path.exists(file_name):
                    os.remove(file_name)
            else:
                await c.send_message(Altruix.log_chat, log_text)
        except Exception as le:
            Altruix.log(f"Failed to send reval log: {le}", level=30)

    # Final response to user
    await m_.delete()
    await m.reply_msg(
        final_output,
        force_paste="p" in arg_keys,
        force_file=f"reval_output.txt;{cmd_label}" if len(final_output) > TGLIMITS.MESSAGE_TEXT else None,
        reply_to_message_id=m.id,
    )
    await m.delete_if_self()


@Altruix.register_on_cmd(
    ["term", "terminal", "run", "bash"],
    just_exc=True,
    cmd_help={
        "help": (
            "Executes commands in terminal/bash. Automatically handles large outputs by "
            "pasting to bin or uploading file if 4096 char limit is exceeded."
        ),
        "example": "bash ls -la\nbash -p echo 'long text' (Paste result)",
        "user_args": [
            {
                "arg": "p",
                "help": "Pastes the terminal output to paste bin.",
                "requires_input": False,
            },
            {
                "arg": "f",
                "help": "Force sends the terminal output as a file.",
                "requires_input": False,
            },
            {
                "arg": "s",
                "help": "Sends the terminal output to log chat silently.",
                "requires_input": False,
            },
        ],
    },
)
@log_errors
async def terminal(c: Client, m: Message):
    user_args = m.user_args
    bash_code = m.raw_user_input
    if not bash_code:
        return await m.reply_msg("TERM_INPUT_REQUIRED")
    ms_id = m.id
    msg_ = await m.reply_msg("CMD_RUNNING")
    if "p" in user_args or "f" in user_args:
        bash_code = (bash_code.replace("-p", "").replace("-f", "")).strip()
    success, output, return_code = await exec_terminal(bash_code)
    # ✅ Using <pre> for terminal input and output to preserve formatting and support wide displays
    out_text = f"<b>Input</b>\n<pre>{html.escape(bash_code)}</pre>"
    _out_text = out_text
    _out_text += f'\n\n<b>{Altruix.get_string("OUTPUT")}</b>\n<pre>{html.escape(output or Altruix.get_string("NO_OUTPUT"))}</pre>\n'
    _out_text += "<b>Status</b>: "
    _out_text += "<i>Success</i> " if success else "<i>Failed</i> "
    _out_text += f"(<code>{return_code}</code>)"
    ttwp = out_text if len(out_text) <= 3999 else None
    caption_ = out_text if len(out_text) <= 9999 else "<b>OUTPUT OF CMD EXECUTED</b>"
    if "s" in user_args and Altruix.log_chat:
        if "p" in user_args:
            url = await Paste(_out_text).paste()
            msg = await c.send_message(
                Altruix.log_chat, f"{caption_} \n<b>Pasted to :</b> {url}"
            )
        elif "f" in user_args or len(out_text) >= TGLIMITS.MESSAGE_TEXT:
            file_path = f"out_bash_{m.id}.txt"
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(_out_text)
            msg = await c.send_document(Altruix.log_chat, file_path, caption=caption_)
            if os.path.exists(file_path):
                os.remove(file_path)
        else:
            msg = await c.send_message(Altruix.log_chat, _out_text)
        await m.reply_msg(f"<b>OUTPUT :</b> <blockquote><a href='{msg.link}'>VIEW</a></blockquote>")
        await m.delete_if_self()
        await msg_.delete()
        return
    await msg_.delete()
    await m.reply_msg(
        _out_text,
        force_paste="-paste" in user_args,
        force_file=f"bash_output.txt;{caption_}" if "-file" in user_args else None,
        reply_to_message_id=ms_id,
        ttwp=ttwp,
    )
    await m.delete_if_self()


async def paste_logs(log_path):
    async with aiofiles.open(log_path, mode="r", encoding="utf-8", errors="replace") as f:
        file_c = await f.read()
        name, link = await Paste(file_c).paste()
    if not link:
        return "<b>PASTE FAILED!</b> Could not upload logs to any service."
    return f"<b>LOGS HAS BEEN PASTED TO {name.upper()}</b> : [View]({link})"


@Altruix.register_on_cmd(
    "logs",
    cmd_help={
        "help": "Retrieve logs of the bot.",
        "example": "logs",
        "user_args": [
            {
                "arg": "p",
                "help": "Pastes the logs to paste bin.",
                "requires_input": False,
            },
            {
                "arg": "s",
                "help": "Silently sends logs to log chat.",
                "requires_input": False,
            },
            {"arg": "r", "help": "Resets logs.", "requires_input": False},
        ],
    },
)
@log_errors
async def logs(c: Client, m: Message):
    log_file_ = "altruix.log"
    start = pc()
    log__args_ = m.user_args
    MSG = await m.handle_message("PROCESSING")
    if not os.path.exists(log_file_):
        with open(log_file_, "w") as log_file:
            log_file.write("A log file has been created!")
        info("A log file has been created!")
        return await MSG.edit_msg("ERROR_404_NO_LOG_FILE")
    file_size_ = os.stat(log_file_).st_size
    if file_size_ == 0:
        return await MSG.edit_msg("ERROR_404_NO_LOG_FILE")
    if "r" in log__args_:
        with open(log_file_, "w") as log_file:
            log_file.write("")
        info("Logs have been reset!")
        return await MSG.edit_msg("LOGS_RESET")
    if "s" in log__args_ and Altruix.log_chat:
        msg = (
            await c.send_document(
                Altruix.log_chat,
                log_file_,
                file_name="AltruiX_logs.txt",
                caption="LOGS of your Altruix Userbot.",
            )
            if "p" not in log__args_
            else await c.send_message(Altruix.log_chat, (await paste_logs(log_file_)))
        )
        return await MSG.edit_msg(
            f"**LOGS HERE :** [VIEW]({msg.link})", parse_mode=enums.ParseMode.MARKDOWN
        )
    if "p" in log__args_:
        return await MSG.edit_msg(await paste_logs(log_file_))
    msg = await c.send_document(
        m.chat.id,
        log_file_,
        reply_to_message_id=m.id,
        file_name="AltruiX_logs.txt",
    )
    end = pc()
    time_taken = round(end - start, 2)
    await MSG.delete()
    await msg.edit_msg(f"Retrieved logs in <code>{time_taken}</code>s.")



# ==================== EVAL/REVAL DOCUMENTATION ====================

# Documentation pages (~1000 chars per page for better readability)
# Documentation pages (~1000 chars per page for better readability)
EVAL_DOC_PAGES = [
    # Page 1: Import
    """<b>📚 Eval & Reval Guide</b>
<b>Page 1/23: Import Altruix</b>

<b>Import Core:</b>
<pre language="python">from Main.core.client import Altruix</pre>

Ini memberikan akses ke semua client (userbot & bot).

<i>→ .evaldoc 2</i>""",

    # Page 2: Bot Assistant
    """<b>📚 Eval & Reval Guide</b>
<b>Page 2/23: Bot Assistant</b>

<b>Altruix.bot</b> = Bot utama dari .env

<b>Contoh:</b>
<pre language="python"># Kirim pesan via bot
await Altruix.bot.send_message(
    12345678,
    "Halo!"
)</pre>

<i>→ .evaldoc 3</i>""",

    # Page 3: Userbot List
    """<b>📚 Eval & Reval Guide</b>
<b>Page 3/23: Userbot List</b>

<b>Altruix.clients</b> = List semua userbot

<b>Contoh:</b>
<pre language="python"># Userbot pertama
c = Altruix.clients[0]
await c.send_message(
    12345678,
    "Halo!"
)</pre>

<i>→ .evaldoc 4</i>""",

    # Page 4: Multiple Sessions
    """<b>📚 Eval & Reval Guide</b>
<b>Page 4/23: Multiple Sessions</b>

<b>Akses session lain:</b>
<pre language="python"># Session kedua
if len(Altruix.clients) > 1:
    c2 = Altruix.clients[1]
    await c2.send_message(
        12345678,
        "Dari session 2!"
    )</pre>

<i>→ .evaldoc 5</i>""",

    # Page 5: Client Aktif (PENTING!)
    """<b>📚 Eval & Reval Guide</b>
<b>Page 5/23: Client Aktif ⭐</b>

<b>CARA TERMUDAH:</b>
Gunakan <code>client</code> dari handler!

<b>Contoh di eval:</b>
<pre language="python"># 'client' = session aktif
await client.send_message(
    "me",
    "Dari session yang aktif!"
)</pre>

Client otomatis terdeteksi!

<i>→ .evaldoc 6</i>""",

    # Page 6: Contoh Client Aktif Detail
    """<b>📚 Eval & Reval Guide</b>
<b>Page 6/23: Contoh Client Aktif</b>

<b>Dalam eval/reval:</b>
<pre language="python"># Kirim ke diri sendiri
await client.send_message(
    "me", "Test"
)

# Kirim ke chat lain
await client.send_message(
    -1001234567890,
    "Test ke grup"
)

# Info session
me = await client.get_me()
print(f"Nama: {me.first_name}")
print(f"ID: {me.id}")</pre>

<i>→ .evaldoc 7</i>""",

    # Page 7: Get Index
    """<b>📚 Eval & Reval Guide</b>
<b>Page 7/23: Deteksi Index</b>

<b>Cari tahu session ke berapa:</b>
<pre language="python"># Dapatkan index
idx = Altruix.clients.index(client)

# Tampilkan (mulai dari 1)
print(f"Session ke-{idx + 1}")</pre>

<i>→ .evaldoc 8</i>""",

    # Page 8: Find by User ID
    """<b>📚 Eval & Reval Guide</b>
<b>Page 8/23: Cari by User ID</b>

<b>Cari client berdasarkan ID:</b>
<pre language="python">def get_client(uid):
    for c in Altruix.clients:
        if c.me.id == uid:
            return c
    return None

# Gunakan
c = get_client(987654321)
if c:
    await c.send_message(
        "me", "Found!"
    )</pre>

<i>→ .evaldoc 9</i>""",

    # Page 9: Bot Manager
    """<b>📚 Eval & Reval Guide</b>
<b>Page 9/23: Bot Manager</b>

<b>Support Custom Bot:</b>
<pre language="python"># Auto pilih bot
uid = client.me.id
bot = Altruix.bot_manager.get_bot(uid)

await bot.send_message(
    12345678,
    "Dari bot (custom/default)"
)</pre>

<i>→ .evaldoc 10</i>""",

    # Page 10: Plugin Example
    """<b>📚 Eval & Reval Guide</b>
<b>Page 10/23: Plugin Example</b>

<pre language="python">@Altruix.on_message(
    filters.command("test", ".")
)
async def test(client, message):
    # Balas via userbot
    await message.reply("OK!")
    
    # Log via bot
    await Altruix.bot.send_message(
        Altruix.config.OWNER_ID,
        f"User {message.from_user.id}"
    )</pre>

<i>→ .evaldoc 11</i>""",

    # Page 11: Handler Best Practice
    """<b>📚 Eval & Reval Guide</b>
<b>Page 11/23: Best Practice</b>

<b>Dalam handler:</b>
<pre language="python">async def handler(client, message):
    # ✅ BENAR: Gunakan client
    await client.send_message(
        message.chat.id, "OK"
    )
    
    # ✅ ATAU via message
    await message.reply("OK")
    
    # ❌ JANGAN hardcode index
    # await Altruix.clients[0]...</pre>

<i>→ .evaldoc 12</i>""",

    # Page 12: Prefix Handling
    """<b>📚 Eval & Reval Guide</b>
<b>Page 12/23: Prefix</b>

<b>Owner:</b> Hanya respond ke CMD_HANDLER
<b>Sudo:</b> Hanya respond ke SUDO_CMD_HANDLER

Ini cegah dual response.

<i>→ .evaldoc 13</i>""",

    # Page 13: De-duplication
    """<b>📚 Eval & Reval Guide</b>
<b>Page 13/23: De-duplication</b>
Hanya satu session yang akan memproses pesan jika multiple session aktif di grup yang sama.
Ini otomatis ditangani oleh <code>xpm_logger_user</code>.

<i>→ .evaldoc 14</i>""",

    # Page 14: Config & LOG_CHAT_ID
    """<b>📚 Eval & Reval Guide</b>
<b>Page 14/23: Config & Log ID</b>

<b>Cara akses config & LOG_CHAT_ID:</b>
<pre language="python">from Main import Altruix

# Akses Config
conf = Altruix.config

# Dapatkan LOG_CHAT_ID
log_id = conf.LOG_CHAT_ID
print(f"Log Chat: {log_id}")</pre>

<b>Akses via ENV (Asynchronous):</b>
<pre language="python">env = await Altruix.db.env_col.find_one(
    {"_id": "ENV"}
)
token = env.get("BOT_TOKEN")</pre>

<i>→ .evaldoc 15</i>""",

    # Page 15: Database Persistence
    """<b>📚 Eval & Reval Guide</b>
<b>Page 15/23: Database Persistence</b>

<b>Simpan data permanen:</b>
<pre language="python">from Main import Altruix

# Gunakan DATA collection
await Altruix.db.data_col.find_one_and_update(
    {"_id": "MY_KEY"},
    {"$set": {"val": 123}},
    upsert=True
)

# Ambil data
res = await Altruix.db.data_col.find_one(
    {"_id": "MY_KEY"}
)
print(res.get("val"))</pre>

<i>→ .evaldoc 16</i>""",

    # Page 16: Additional Examples - Delay & Delete
    """<b>📚 Eval & Reval Guide</b>
<b>Page 16/23: Delay & Hapus Pesan</b>

<b>Delay (Tidur/Jeda):</b>
<pre language="python">import asyncio

await message.reply("Tunggu 3 detik...")
# HARUS pakai asyncio, jangan time.sleep()
await asyncio.sleep(3) 
await message.reply("Selesai!")</pre>

<b>Hapus Pesan:</b>
<pre language="python"># Hapus pesan pengguna
try:
    await message.delete()
except Exception: pass

# Hapus banyak pesan
await client.delete_messages(
    chat_id=message.chat.id,
    message_ids=[msg1.id, msg2.id]
)</pre>

<i>→ .evaldoc 17</i>""",

    # Page 17: Format HTML & Markdown
    """<b>📚 Eval & Reval Guide</b>
<b>Page 17/23: Markdown & HTML</b>

<b>Format Standar Telegram (HTML):</b>
<pre language="python">text = (
    "&lt;b&gt;Tebal&lt;/b&gt;\\n"
    "&lt;i&gt;Miring&lt;/i&gt;\\n"
    "&lt;u&gt;Garis bawah&lt;/u&gt;\\n"
    "&lt;s&gt;Coret&lt;/s&gt;\\n"
    "&lt;code&gt;Monospace&lt;/code&gt;\\n"
    "&lt;pre&gt;Blok Kode&lt;/pre&gt;\\n"
    "&lt;a href='t.me/'&gt;Link&lt;/a&gt;\\n"
    "&lt;tg-spoiler&gt;Rahasia&lt;/tg-spoiler&gt;"
)
await message.reply(text, parse_mode=enums.ParseMode.HTML)</pre>

<b>Markdown V2 (Butuh escape karakter khusus!):</b>
<pre language="python">text = "*Tebal* _Miring_ ~Coret~ ||Rahasia||"
await message.reply(text, parse_mode=enums.ParseMode.MARKDOWN)</pre>

<i>→ .evaldoc 18</i>""",

    # Page 18: Inline Buttons (Bot)
    """<b>📚 Eval & Reval Guide</b>
<b>Page 18/23: Inline Buttons</b>

<b>HANYA Bot Assistant yang bisa kirim tombol:</b>
<pre language="python">from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton
)

# Buat Layout Tombol
kb = InlineKeyboardMarkup([
    [InlineKeyboardButton("Pilihan 1", callback_data="cb_1")],
    [InlineKeyboardButton("Link", url="t.me/")]
])

# Kirim menggunakan bot
await Altruix.bot.send_message(
    chat_id=message.chat.id,
    text="Silakan klik:",
    reply_markup=kb
)</pre>

<i>→ .evaldoc 19</i>""",

    # Page 19: Inline Builder (Tag via@bot)
    """<b>📚 Eval & Reval Guide</b>
<b>Page 19/23: Mengirim Pesan (via@bot)</b>

<b>Fitur Builder (Ekosistem Altruix):</b>
<pre language="python"># 1. Dapatkan nama bot kamu
bot_usr = Altruix.bot_manager.get_bot_username(client.me.id)

# 2. Panggil Inline Query dari bot kamu
# (Harus ada handler @bot.on_inline_query di pluginnya)
query_str = f"my_menu_{client.me.id}"
res = await client.get_inline_bot_results(bot_usr, query_str)

# 3. Userbot "menekan" hasil inline & kirim ke chat
if res.results:
    await client.send_inline_bot_result(
        chat_id=message.chat.id,
        query_id=res.query_id,
        result_id=res.results[0].id,
        reply_to_message_id=message.id
    )</pre>

<i>→ .evaldoc 20</i>""",

    # Page 20: Quick Reference
    """<b>📚 Eval & Reval Guide</b>
<b>Page 20/23: Quick Reference</b>

<code>Altruix.bot</code>
→ Bot utama

<code>Altruix.clients</code>
→ List userbot

<code>Altruix.clients[0]</code>
→ Userbot pertama

<code>client</code> (dalam handler)
→ Session aktif ⭐

<code>Altruix.bot_manager.get_bot(uid)</code>
→ Bot (custom/default)

<i>→ .evaldoc 21</i>""",

    # Page 21: Tips
    """<b>📚 Eval & Reval Guide</b>
<b>Page 21/23: Tips Eval/Reval</b>

<b>💡 Tips:</b>

1. Gunakan <code>client</code> dari handler
   (auto-detect session aktif)

2. Untuk userbot utama:
   <code>Altruix.clients[0]</code>

3. Untuk bot assistant:
   <code>Altruix.bot</code>

4. Check jumlah session:
   <code>len(Altruix.clients)</code>

5. Info session aktif:
   <code>await client.get_me()</code>

<i>→ .evaldoc 22</i>""",

    # Page 22: Alliance Voice Chat API
    """<b>📚 Eval & Reval Guide</b>
<b>Page 22/23: Alliance Voice Chat API ⭐</b>

<b>VoiceChatManager:</b>
<pre language="python">from Main.plugins.userbot.xalliance_vc import vc_manager

# Mendapatkan instance pytgcalls
call = await vc_manager.get_call(client)

# Join & Play Audio
from pytgcalls.types import AudioPiped
await call.join_group_call(
    "chat_username", 
    AudioPiped("audio.mp3")
)</pre>

Mendukung Automasi & Eval!

<i>→ .evaldoc 23</i>""",

    # Page 23: Akhir
    """<b>📚 Eval & Reval Guide</b>
<b>Page 23/23: Penutup</b>

Semua dokumentasi ini tersedia juga di file <code>DEVELOPER_GUIDE.md</code> di repo utama.

Gunakan standar ekosistem Altruix untuk memastikan module Anda bebas bug dan aman diletakkan dalam Loop asyncio!

<b>Selesai!</b> Gunakan <code>.evaldoc 1</code> untuk kembali ke awal."""
]


async def get_evaldoc_keyboard(page: int, user_id: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard for evaldoc pagination."""
    total_pages = len(EVAL_DOC_PAGES)
    btn_style = get_user_button_style(user_id)
    
    # Row 1: Prev | Page X/Total | Next
    row1 = []
    if page > 1:
        row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "◀️ Prev"), callback_data=f"evaldoc_page_{page-1}", style=btn_style))
    else:
        row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "◀️"), callback_data="evaldoc_noop", style=btn_style))
    
    row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, f"📄 {page}/{total_pages}"), callback_data="evaldoc_noop", style=btn_style))
    
    if page < total_pages:
        row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "Next ▶️"), callback_data=f"evaldoc_page_{page+1}", style=btn_style))
    else:
        row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "▶️"), callback_data="evaldoc_noop", style=btn_style))
    
    # Row 2: First | Client (jump to page 5) | Last
    row2 = [
        InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "⏮️ First"), callback_data="evaldoc_page_1", style=btn_style),
        InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "⭐ Client"), callback_data="evaldoc_page_5", style=btn_style),
        InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "Last ⏭️"), callback_data=f"evaldoc_page_{total_pages}", style=btn_style)
    ]
    
    # Row 3: Close
    row3 = [InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "❌ Close"), callback_data="evaldoc_close", style=btn_style)]
    
    return InlineKeyboardMarkup([row1, row2, row3])


# ==================== HELPER FUNCTIONS FOR SAFE CALLBACK HANDLING ====================

async def safe_evaldoc_answer(cb: CallbackQuery, text: str, show_alert: bool = False):
    """Answer callback query safely, ignoring expired queries."""
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass

async def safe_evaldoc_edit(cb: CallbackQuery, text: str, reply_markup=None):
    """
    Safely edit callback message, handling both regular and inline mode messages.
    Uses cb.edit_message_text() which automatically handles inline messages.
    """
    try:
        # Use cb.edit_message_text() - it automatically handles both regular and inline messages
        await cb.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return True
    except Exception as e:
        Altruix.log(f"[evaldoc] Error editing message: {e}", level=40)
        await safe_evaldoc_answer(cb, f"❌ Error: {str(e)[:50]}", show_alert=True)
        return False

async def safe_evaldoc_delete(cb: CallbackQuery):
    """
    Safely delete callback message.
    For inline messages, uses delete_message() instead of message.delete().
    """
    try:
        # Try to delete using callback query method (works for both inline and regular)
        await cb.message.delete()
        return True
    except AttributeError:
        # If cb.message is None (inline mode), try alternative method
        try:
            # For inline messages, we can't delete, so we edit to show "closed" message
            await cb.edit_message_text(
                "❌ <b>Menu Closed</b>",
                parse_mode=enums.ParseMode.HTML
            )
            return True
        except Exception as e:
            Altruix.log(f"[evaldoc] Error closing message: {e}", level=40)
            return False
    except Exception as e:
        Altruix.log(f"[evaldoc] Error deleting message: {e}", level=40)
        return False


# ==================== CALLBACK HANDLER ====================

@Altruix.bot.on_callback_query(filters.regex(r"^evaldoc_"))
@iuser_check
@log_errors
async def evaldoc_callback_handler(c: Client, q: CallbackQuery):
    """Handle evaldoc inline keyboard callbacks.
    Protected by @iuser_check for auth verification."""
    data = q.data
    
    # Handle close button
    if data == "evaldoc_close":
        success = await safe_evaldoc_delete(q)
        if success:
            await safe_evaldoc_answer(q, "Menu closed.", show_alert=False)
        return
    
    # Handle noop (disabled buttons)
    if data == "evaldoc_noop":
        await safe_evaldoc_answer(q, "⚠️ Already at boundary", show_alert=False)
        return
    
    # Handle page navigation
    if data.startswith("evaldoc_page_"):
        try:
            page_num = int(data.split("_")[-1])
        except ValueError:
            await safe_evaldoc_answer(q, "❌ Invalid page", show_alert=True)
            return
        
        # Validate page number
        if page_num < 1 or page_num > len(EVAL_DOC_PAGES):
            await safe_evaldoc_answer(q, f"❌ Page must be 1-{len(EVAL_DOC_PAGES)}", show_alert=True)
            return
        
        # Get page content and keyboard
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, q.from_user.id)
        
        # Update message
        success = await safe_evaldoc_edit(q, page_content, reply_markup=keyboard)
        if success:
            await safe_evaldoc_answer(q, f"📄 Page {page_num}/{len(EVAL_DOC_PAGES)}", show_alert=False)



# ==================== INLINE HANDLER (for dashboard mode via @bot) ====================

@Altruix.bot.on_inline_query(filters.regex(r"^evaldoc(?:_page_)?(\d+)?"))
@iuser_check
@log_errors
async def evaldoc_inline_handler(client: Client, query: InlineQuery):
    """
    Responds to inline query for evaldoc (triggered by @bot evaldoc).
    Allows opening the evaldoc dashboard in ANY chat via inline mode.
    Protected by @iuser_check for auth verification.
    """
    try:
        # Extract page number from query
        match = query.matches[0]
        page_str = match.group(1)
        page_num = int(page_str) if page_str else 1
        
        # Validate page number
        if page_num < 1 or page_num > len(EVAL_DOC_PAGES):
            page_num = 1
        
        # Get page content and keyboard
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, query.from_user.id)
        
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    title=f"📚 Eval & Reval Guide - Page {page_num}/23",
                    description=f"Comprehensive documentation for eval/reval usage",
                    input_message_content=InputTextMessageContent(
                        page_content,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    ),
                    reply_markup=keyboard
                )
            ],
            cache_time=0
        )
    except Exception as e:
        Altruix.log(f"Evaldoc Inline Handler Error: {e}", level=40)


# Update the eval_documentation_handler to support inline mode
@Altruix.register_on_cmd(
    ["evaldoc", "evalhelp", "evalguide"],
    cmd_help={
        "help": "Show comprehensive documentation for eval/reval usage with client access.",
        "example": "evaldoc 1",
        "user_input": {
            "required": False,
            "placeholder": f"page number (1-{len(EVAL_DOC_PAGES)})"
        }
    },
)
@log_errors
async def eval_documentation_handler_inline(c: Client, m: Message):
    """Show eval/reval documentation with inline keyboard pagination via bot assistant."""
    # Get page number from user input
    page_input = m.user_input.strip() if m.user_input else "1"
    
    try:
        page_num = int(page_input)
    except ValueError:
        return await m.reply_msg(
            "❌ <b>Invalid page number.</b>\n\n"
            f"Usage: <code>.evaldoc [1-{len(EVAL_DOC_PAGES)}]</code>\n"
            f"Example: <code>.evaldoc 1</code>"
        )
    
    # Validate page number
    if page_num < 1 or page_num > len(EVAL_DOC_PAGES):
        return await m.reply_msg(
            f"❌ <b>Page not found.</b>\n\n"
            f"Available pages: <b>1-{len(EVAL_DOC_PAGES)}</b>\n"
            f"Usage: <code>.evaldoc [page]</code>"
        )
    
    user_id = c.me.id
    
    # Get bot assistant
    bot = None
    bot_username = None
    if hasattr(Altruix, 'bot_manager'):
        bot = Altruix.bot_manager.get_bot(user_id)
        bot_username = Altruix.bot_manager.get_bot_username(user_id)
    if not bot:
        bot = Altruix.bot
        if hasattr(Altruix.bot, 'me') and Altruix.bot.me:
            bot_username = Altruix.bot.me.username
    
    if not bot:
        # No bot assistant found - fallback to direct message
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, m.from_user.id) # Pass user_id
        await m.edit_msg(page_content, reply_markup=keyboard)
        return
    
    # Try Inline mode first (works in ANY chat, even without bot present)
    if bot_username:
        try:
            results = await c.get_inline_bot_results(bot_username, f"evaldoc_page_{page_num}")
            if results.results:
                sent = await c.send_inline_bot_result(
                    m.chat.id,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=m.id  # ✅ Reply to command message
                )
                if sent:
                    await m.delete_if_self()
                    Altruix.log(f"[evaldoc] Dashboard opened via inline mode (page {page_num})", level=20)
                    return
        except Exception as e:
            Altruix.log(f"[evaldoc] Inline mode failed: {e}, falling back to direct message", level=30)
    
    # Fallback to direct bot message (only works if bot is in the chat)
    try:
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, m.from_user.id)
        await bot.send_message(
            m.chat.id, 
            page_content, 
            reply_markup=keyboard, 
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=m.id  # ✅ Reply to command message
        )
        await m.delete_if_self()
        Altruix.log(f"[evaldoc] Dashboard opened via direct message (page {page_num})", level=20)
    except Exception as e:
        Altruix.log(f"[evaldoc] Error sending dashboard: {e}", level=40)
        # Final fallback - edit original message
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, m.from_user.id)
        await m.edit_msg(page_content, reply_markup=keyboard)
