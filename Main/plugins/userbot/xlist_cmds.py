# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


PLUGIN_VERSION = "0.0.1"
from Main import Altruix
from pyrogram import Client
from Main.core.decorators import log_errors

@Altruix.register_on_cmd(["listcmds", "allcmds"], bot_mode_unsupported=True)
@log_errors
async def list_all_cmds_handler(c: Client, m):
    """Handler to list all commands across all plugins."""
    text = "<b>📜 List of All Command Triggers</b>\n\n"
    total_plugins = 0
    total_cmds = 0
    
    # Sort plugins by name
    sorted_plugins = sorted(Altruix.cmd_list.keys())
    
    for plugin in sorted_plugins:
        total_plugins += 1
        cmds = []
        for cmd_info in Altruix.cmd_list[plugin]:
            cmds.extend(cmd_info.get("commands", []))
        
        if cmds:
            # Remove duplicates and sort
            unique_cmds = sorted(set(cmds))
            total_cmds += len(unique_cmds)
            cmd_str = ", ".join([f"<code>{c}</code>" for c in unique_cmds])
            text += f"<b>Plugin:</b> <code>{plugin}</code>\n{cmd_str}\n\n"
    
    text += f"<b>Total Plugins:</b> <code>{total_plugins}</code>\n"
    text += f"<b>Total Commands:</b> <code>{total_cmds}</code>\n\n"
    text += f"<i>Use</i> <code>{Altruix.prefix_owner_user}help <plugin></code> <i>for details!</i>"
    
    await m.handle_message(text)

__MODULE__ = "Command List"
__HELP__ = f"Use <code>{Altruix.prefix_owner_user}listcmds</code> to see all available command triggers across all plugins."

