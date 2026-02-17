# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


PLUGIN_VERSION = "0.0.2"
import sys
import asyncio
from Main import Altruix
from pyrogram import Client
from difflib import get_close_matches


@Altruix.register_on_cmd(
    ["lang", "language", "set language"], bot_mode_unsupported=True
)
async def lang_modify(c: Client, m):
    """
    ✅ ENHANCED: Added error logging for inline bot result failures.
    Shows language selection menu via inline bot result.
    """
    try:
        rm = m.reply_to_message
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        
        # ✅ Validate bot username before attempting inline query
        if not bot_username or bot_username == "Unknown":
            Altruix.log(f"Invalid bot username for user {c.me.id}: {bot_username}", level=40)
            return await m.handle_message("❌ Bot assistant not configured. Please set up custom bot first.")
        
        results = await c.get_inline_bot_results(bot_username, "change_lang")
        return await asyncio.gather(
            *[
                c.send_inline_bot_result(
                    m.chat.id,
                    query_id=results.query_id,
                    result_id=results.results[0].id,
                    reply_to_message_id=rm.id if rm else m.id,
                ),
                m.delete_if_self(),
            ]
        )
    except Exception as e:
        # ✅ Log error for debugging
        Altruix.log(f"Failed to send inline language menu: {e}", level=40)
        return await m.handle_message(f"❌ Failed to show language menu: {str(e)}")



@Altruix.register_on_cmd(["help"], bot_mode_unsupported=True)
async def help_normal(c: Client, m):
    """
    ✅ ENHANCED: Added error logging for inline bot result failures.
    Shows help menu via inline bot result (with buttons) or as text fallback.
    """
    cmd_lists = Altruix._command_help_message_data
    user_input = m.user_input
    chat = m.chat.id
    rm = m.reply_to_message

    # ✅ PERBAIKAN: Jika ada user_input (plugin target), layani secara normal tanpa paksa inline
    # Fix: Allow plugin help on userbots by removing 'and not user_input' from the inline condition
    if (not c.myself.is_bot) and "-basic" not in m.user_args and not user_input:
        try:
            bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
            
            # ✅ Validate bot username before attempting inline query
            if not bot_username or bot_username == "Unknown":
                Altruix.log(f"Invalid bot username for user {c.me.id}: {bot_username}", level=40)
                # Fallback to text help menu
                pass  # Continue to text-based help below
            else:
                results = await c.get_inline_bot_results(bot_username, f"help_{chat}")
                await c.send_inline_bot_result(
                    chat_id=chat,
                    query_id=results.query_id,
                    result_id=results.results[0].id,
                    reply_to_message_id=rm.id if rm else m.id,
                )
                return await m.delete_if_self()
        except Exception as e:
            # ✅ Log error and fallback to text help
            Altruix.log(f"Failed to send inline help menu: {e}", level=40)
            # Continue to text-based help below
    
    if user_input and (cmd_lists.get(user_input) or user_input in Altruix.cmd_list):
        help_text = cmd_lists.get(user_input, "")
        if user_input in Altruix.cmd_list:
            cmds = []
            for item in Altruix.cmd_list[user_input]:
                cmds.extend(item["commands"])
            cmd_str = ", ".join([f"<code>{c}</code>" for c in sorted(set(cmds))])
            help_text += f"\n\n<b>Commands in this plugin:</b>\n{cmd_str}"
        
        # Case-insensitive lookup for version
        version = "0.0.1"
        plugin_key = next((k for k in Altruix.cmd_list.keys() if k.lower() == user_input.lower()), None)
        if plugin_key:
            version = Altruix.cmd_list[plugin_key][0].get("version")
            if not version or version == "unknown":
                version = "0.0.1"

        header = f"<b>❇️ Help for</b> <code>{user_input.title()}</code>\n"
        header += f"<b>🏷️ Version:</b> <code>v{version}</code>\n\n"
        
        await m.handle_message(f"{header}{help_text.strip()}")
    elif not user_input:
        import sys
        import pyrogram
        
        # ✅ Check for Custom Help Message
        session_index = -1
        for i, cl in enumerate(Altruix.clients):
            if cl == c:
                session_index = i
                break
        
        custom_help = None
        parse_mode = None
        if session_index != -1:
            mode = await Altruix.config.get_env(f"HELP_INFO_{session_index}")
            if mode == "custom":
                custom_help = await Altruix.config.get_env(f"HELP_INFO_CUSTOM_MSG_{session_index}")
                if custom_help:
                    custom_help, parse_mode = await Altruix.resolve_placeholders(custom_help, index=session_index, client=c)

        if custom_help:
            cmd_list = custom_help
        else:
            import pyrogram
            from pyrogram.enums import ParseMode
            parse_mode = ParseMode.HTML
            plugin_count = len(Altruix.cmd_list)
            # Hitung total command dari semua plugin
            total_commands = 0
            for plugin_cmds in Altruix.cmd_list.values():
                for cmd_info in plugin_cmds:
                    total_commands += len(cmd_info.get("commands", []))

            # Header dengan versi info
            version_header = (
                f"<b>Altruix Help Menu</b>\n"
                f"<b>Userbot version :</b> <code>V{Altruix.__version__}</code>\n"
                f"<b>Pyrogram version :</b> <code>V{pyrogram.__version__}</code>\n"
                f"<b>Python version :</b> <code>V{sys.version.split()[0]}</code>\n"
                f"<b>Total plugin:</b> <code>{plugin_count}</code>\n\n"
            )
            
            cmd_list = f"{version_header}<i><b>Plugins Available ({plugin_count})</i></b>\n\n"
            for plugins in sorted(Altruix.cmd_list.keys()):
                cmd_list += f"<code>{plugins}</code>  "
            cmd_list = cmd_list[:-2]
            cmd_list += f"\n\n<b>Total Plugins:</b> <code>{plugin_count}</code>"
            cmd_list += f"\n<b>Total Commands:</b> <code>{total_commands}</code>"
            cmd_list += f"\n\n<i>Use</i> <code>{Altruix.prefix_owner_user}help <plugin name></code> <i>to know more!</i>"
        await m.handle_message(cmd_list, parse_mode=parse_mode)
    elif user_input and not cmd_lists.get(user_input):
        if (
            len(get_close_matches(user_input, cmd_lists.keys(), n=4, cutoff=0.3))
            > 0
        ):
            preds = "".join(
                f"{i}, "
                for i in get_close_matches(
                    user_input, cmd_lists.keys(), n=4, cutoff=0.3
                )
            )
            return await m.handle_message(
                f"<i>Command not found in the list, did you mean?</i> : <code>{preds[:-2]}</code>"
            )
        await m.handle_message("<i>This command is not in the command list!</i>")

