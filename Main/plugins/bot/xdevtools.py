# # Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# #
# # This file is part of < https://github.com/Altruix/Altruix > project,
# # and is released under the "GNU v3.0 License Agreement".
# # Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
# #
# # All rights reserved.


# PLUGIN_VERSION = "0.0.63"
# import os
# import html
# import asyncio
# import aiofiles
# from Main import Altruix
# from logging import info
# from Main.utils.paste import Paste
# from pyrogram import Client, enums, filters
# from time import perf_counter as pc
# from Main.core.config import TGLIMITS
# from Main.core.types.message import Message
# from Main.utils.dev_func import eval_py, exec_terminal
# from Main.core.decorators import log_errors, iuser_check


# @Altruix.register_on_cmd(
#     ["json"],
#     cmd_help={
#         "help": "Get the JSON structure of a message.",
#         "usage": "/json (reply to message)",
#         "example": "/json",
#         "user_args": {
#             "p": "Paste output only",
#             "f": "Send output as file",
#             "d": "Send as file if too long"
#         }
#     },
#     group_only=False,
#     requires_input=False,
#     requires_reply=False
# )
# @log_errors
# async def get_json_message_handler(c: Client, m: Message):
#     user_args = m.user_args
#     msg_id = m.id
#     rm = m.reply_to_message
#     m_ = await m.reply("PROCESSING...")
#     # ✅ Using <pre> tags for structured JSON output to support better UI rendering
#     jsonified = f"<pre>{html.escape(str(rm or m))}</pre>"
#     cmd_ = "<b>jsonified</b>"
    
#     # Extract keys for flag checking
#     arg_keys = [a.key.lower() for a in user_args] if user_args else []
    
#     await m_.edit_msg(
#         jsonified,
#         force_paste="p" in arg_keys,
#         force_file=f"message.json;{cmd_}" if "f" in arg_keys else None,
#         too_long_as_file="message.json" if "d" in arg_keys else False,
#         reply_to_message_id=msg_id,
#     )
#     await m.delete_if_self()


# @Altruix.register_on_cmd(
#     ["ex", "exec", "eval"],
#     cmd_help={
#         "help": "Execute Python code dynamically.",
#         "usage": "/eval print('Hello World')",
#         "example": "/eval 1 + 1",
#         "user_args": {
#             "p": "Paste output",
#             "f": "Send output as file",
#             "s": "Send output to Log Channel"
#         }
#     },
#     group_only=False,
#     requires_input=True,
#     requires_reply=False
# )
# @log_errors
# async def evaluate_command_handler(c: Client, m: Message):
#     msg_id = m.id
#     m_ = await m.reply("PROCESSING...")
#     user_args = m.user_args
#     arg_keys = [a.key.lower() for a in user_args] if user_args else []
    
#     cmd = m.raw_user_input
#     if not cmd:
#         await m_.edit("INPUT_REQUIRED")
#         return
#     if "p" in arg_keys or "f" in arg_keys:
#         cmd = (cmd.replace("-p", "").replace("-f", "")).strip()

#     # ✅ Tracking performance for evaluation
#     start_time = pc()
#     results = await eval_py(c, cmd, m)
#     end_time = pc()
#     time_taken = round(end_time - start_time, 3)

#     header = f"<b>EVAL (v<code>{PLUGIN_VERSION}</code>)</b>\n"
#     header += f"🕒 <code>{time_taken}s</code>\n\n"

#     # ✅ Using <pre> for input/output blocks to support auto-detection of code types
#     final_output = f"{header}<b>INPUT:</b>\n<pre>{html.escape(cmd)}</pre>\n\n<b>OUTPUT</b>:\n<pre>{html.escape(results.strip())}</pre>"
#     cmd_ = (
#         "<b>Output Of Command</b>"
#         if len(cmd) >= 1000
#         else f"<b>OUTPUT FOR COMMAND :</b> <code>{cmd}</code>" # Keep index code for short command titles
#     )
#     if "s" in arg_keys and Altruix.log_chat:
#         if "p" in arg_keys:
#             url = await Paste(final_output).paste()
#             msg = await c.send_message(
#                 Altruix.log_chat, f"{cmd_} \n<b>Pasted to :</b> {url}"
#             )
#         elif "p" in arg_keys or len(final_output) >= TGLIMITS.MESSAGE_TEXT:
#             file_path = f"out_eval_{m.id}.txt"
#             async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
#                 await f.write(final_output)
#             msg = await c.send_document(Altruix.log_chat, file_path, caption=cmd)
#             if os.path.exists(file_path):
#                 os.remove(file_path)
#         else:
#             msg = await c.send_message(Altruix.log_chat, final_output)
#         return await m_.edit_msg(f"<b>OUTPUT :</b> <a href='{msg.link}'>VIEW</a>")
    
#     await m_.edit_msg(
#         final_output,
#         force_paste="p" in arg_keys,
#         force_file=f"eval_output.txt;{cmd_}" if "f" in arg_keys else None,
#         reply_to_message_id=msg_id,
#     )
#     pass


# @Altruix.register_on_cmd(
#     ["reval"],
#     cmd_help={
#         "help": "Execute Python code from a replied message.",
#         "usage": "/reval (reply to code)",
#         "example": "/reval",
#         "user_args": {
#             "p": "Paste output",
#             "s": "Send output to Log Channel"
#         }
#     },
#     group_only=False,
#     requires_input=False,
#     requires_reply=True
# )
# @log_errors
# async def re_evaluate_command_handler(c: Client, m: Message):
#     rm = m.reply_to_message
#     if not rm:
#         return await m.reply("REPLY_TO_MSG_REQUIRED")
    
#     code = (rm.text or rm.caption or "").strip()
#     if not code:
#         return await m.reply("NO_CODE_FOUND")

#     # Start processing
#     m_ = await m.reply("PROCESSING...")
#     user_args = m.user_args
#     arg_keys = [a.key.lower() for a in user_args] if user_args else []
    
#     start_time = pc()
#     from pyrogram.errors import FloodWait as FW
#     try:
#         results = await eval_py(c, code, m)
#     except FW as e:
#         # Handling floodwait by waiting and retrying
#         await asyncio.sleep(e.value)
#         results = await eval_py(c, code, m)
#     except Exception:
#         import traceback
#         results = traceback.format_exc()
    
#     end_time = pc()
#     time_taken = round(end_time - start_time, 3)
    
#     header = f"<b>R-EVAL (v<code>{PLUGIN_VERSION}</code>)</b>\n"
#     header += f"🕒 <code>{time_taken}s</code>\n\n"
    
#     # Trim input if too long for preview
#     code_preview = code[:500] + ("..." if len(code) > 500 else "")
#     # ✅ Enhanced formatting for re-eval results using <pre> tags
#     final_output = f"{header}<b>INPUT:</b>\n<pre>{html.escape(code_preview)}</pre>\n\n<b>OUTPUT</b>:\n<pre>{html.escape(results.strip())}</pre>"
    
#     cmd_label = "<b>Re-Eval Output</b>"
    
#     # Logic for sending to log chat if 's' flag is present
#     if "s" in arg_keys and Altruix.log_chat:
#         log_text = f"🎯 <b>Re-Eval Log</b>\nUser: {m.from_user.id}\n\n{final_output}"
#         try:
#             if "p" in arg_keys:
#                 url = await Paste(log_text).paste()
#                 await c.send_message(Altruix.log_chat, f"{cmd_label}\n<b>Pasted to:</b> {url}")
#             elif len(log_text) > TGLIMITS.MESSAGE_TEXT:
#                 file_name = f"reval_log_{m.id}.txt"
#                 async with aiofiles.open(file_name, "w", encoding="utf-8") as f:
#                     await f.write(log_text)
#                 await c.send_document(Altruix.log_chat, file_name, caption=cmd_label)
#                 if os.path.exists(file_name):
#                     os.remove(file_name)
#             else:
#                 await c.send_message(Altruix.log_chat, log_text)
#         except Exception as le:
#             Altruix.log(f"Failed to send reval log: {le}", level=30)

#     # Final response to user
#     await m_.edit_msg(
#         final_output,
#         force_paste="p" in arg_keys,
#         force_file=f"reval_output.txt;{cmd_label}" if len(final_output) > TGLIMITS.MESSAGE_TEXT else None,
#         reply_to_message_id=m.id,
#     )


# @Altruix.register_on_cmd(
#     ["term", "terminal", "run", "bash", "sh"],
#     cmd_help={
#         "help": "Execute Terminal/Bash commands.",
#         "usage": "/term [command]",
#         "example": "/term ls -la",
#         "user_args": {
#             "p": "Paste output",
#             "f": "Send output as file",
#             "s": "Send output to Log Channel"
#         }
#     },
#     group_only=False,
#     requires_input=True,
#     requires_reply=False
# )
# @log_errors
# async def terminal(c: Client, m: Message):
#     user_args = m.user_args
#     arg_keys = [a.key.lower() for a in user_args] if user_args else []
    
#     bash_code = m.raw_user_input
#     if not bash_code:
#         return await m.reply("TERM_INPUT_REQUIRED")
    
#     ms_id = m.id
#     msg_ = await m.reply("CMD_RUNNING...")
    
#     if "p" in arg_keys or "f" in arg_keys:
#         bash_code = (bash_code.replace("-p", "").replace("-f", "")).strip()
    
#     success, output, return_code = await exec_terminal(bash_code)
#     # ✅ Using <pre> for terminal input and output to preserve formatting and support wide displays
#     out_text = f"<b>Input</b>\n<pre>{html.escape(bash_code)}</pre>"
#     _out_text = out_text
#     _out_text += f'\n\n<b>{Altruix.get_string("OUTPUT")}</b>\n<pre>{html.escape(output or Altruix.get_string("NO_OUTPUT"))}</pre>\n'
#     _out_text += "<b>Status</b>: "
#     _out_text += "<i>Success</i> " if success else "<i>Failed</i> "
#     _out_text += f"(<code>{return_code}</code>)"
    
#     ttwp = out_text if len(out_text) <= 3999 else None
#     caption_ = out_text if len(out_text) <= 9999 else "<b>OUTPUT OF CMD EXECUTED</b>"
    
#     if "s" in arg_keys and Altruix.log_chat:
#         if "p" in arg_keys:
#             url = await Paste(_out_text).paste()
#             msg = await c.send_message(
#                 Altruix.log_chat, f"{caption_} \n<b>Pasted to :</b> {url}"
#             )
#         elif "f" in arg_keys or len(out_text) >= TGLIMITS.MESSAGE_TEXT:
#             file_path = f"out_bash_{m.id}.txt"
#             async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
#                 await f.write(_out_text)
#             msg = await c.send_document(Altruix.log_chat, file_path, caption=caption_)
#             if os.path.exists(file_path):
#                 os.remove(file_path)
#         else:
#             msg = await c.send_message(Altruix.log_chat, _out_text)
#         await msg_.edit_msg(f"<b>OUTPUT :</b> <a href='{msg.link}'>VIEW</a>")
#         return

#     await msg_.edit_msg(
#         _out_text,
#         force_paste="-paste" in user_args, # user_args is Args object, check containment string? No, updated logic uses arg_keys
#         force_file=f"bash_output.txt;{caption_}" if "-file" in user_args else None, # Compatibility check
#         reply_to_message_id=ms_id,
#         ttwp=ttwp,
#     )


# async def paste_logs(log_path):
#     async with aiofiles.open(log_path, mode="r", encoding="utf-8", errors="replace") as f:
#         file_c = await f.read()
#         name, link = await Paste(file_c).paste()
#     if not link:
#         return "<b>PASTE FAILED!</b> Could not upload logs to any service."
#     return f"<b>LOGS HAS BEEN PASTED TO {name.upper()}</b> : [View]({link})"


# @Altruix.register_on_cmd(
#     ["logs", "log"],
#     cmd_help={
#         "help": "Get the application logs.",
#         "usage": "/logs",
#         "example": "/logs",
#         "user_args": {
#             "p": "Paste logs to web",
#             "r": "Reset logs",
#             "s": "Send to Log Channel"
#         }
#     },
#     group_only=False,
#     requires_input=False,
#     requires_reply=False
# )
# @log_errors
# async def logs(c: Client, m: Message):
#     log_file_ = "altruix.log"
#     start = pc()
#     user_args = m.user_args
#     arg_keys = [a.key.lower() for a in user_args] if user_args else []
    
#     MSG = await m.reply("PROCESSING...")
    
#     if not os.path.exists(log_file_):
#         with open(log_file_, "w") as log_file:
#             log_file.write("A log file has been created!")
#         info("A log file has been created!")
#         return await MSG.edit("ERROR_404_NO_LOG_FILE")
    
#     file_size_ = os.stat(log_file_).st_size
#     if file_size_ == 0:
#         return await MSG.edit("ERROR_404_NO_LOG_FILE")
    
#     if "r" in arg_keys:
#         with open(log_file_, "w") as log_file:
#             log_file.write("")
#         info("Logs have been reset!")
#         return await MSG.edit("LOGS_RESET")
    
#     if "s" in arg_keys and Altruix.log_chat:
#         msg = (
#             await c.send_document(
#                 Altruix.log_chat,
#                 log_file_,
#                 file_name="AltruiX_logs.txt",
#                 caption="LOGS of your Altruix Userbot.",
#             )
#             if "p" not in arg_keys
#             else await c.send_message(Altruix.log_chat, (await paste_logs(log_file_)))
#         )
#         return await MSG.edit_msg(
#             f"**LOGS HERE :** [VIEW]({msg.link})", parse_mode=enums.ParseMode.MARKDOWN
#         )
    
#     if "p" in arg_keys:
#         return await MSG.edit_msg(await paste_logs(log_file_))
    
#     msg = await c.send_document(
#         m.chat.id,
#         log_file_,
#         reply_to_message_id=m.id,
#         file_name="AltruiX_logs.txt",
#     )
#     end = pc()
#     time_taken = round(end - start, 2)
#     await MSG.delete()
#     await msg.edit_msg(f"Retrieved logs in <code>{time_taken}</code>s.")
