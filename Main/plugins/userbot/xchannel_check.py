# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

PLUGIN_VERSION = "1.0.0"

import asyncio
import traceback
from typing import Union
from pyrogram import Client
from pyrogram.types import Message
from Main import Altruix
from Main.core.types.message import Message as MMessage
from pyrogram.raw.functions.channels import GetAdminedPublicChannels
from pyrogram.raw.functions.messages import SaveDefaultSendAs

@Altruix.register_on_cmd(
    "chcheck",
    cmd_help={
        "help": "Memeriksa daftar channel publik (yang Anda admin) yang terkena banned di dalam suatu grup.",
        "example": "chcheck @CherrygramSupport\nchcheck -10012414672",
    },
    requires_input=True,
)
async def chcheck_cmd(c: Client, m: Union[Message, MMessage]):
    _m = await m.reply_msg("PROCESSING")
    try:
        target_chat = m.user_input.strip()
        
        if not target_chat:
            return await _m.edit_msg("Please specify a target group!")

        if target_chat.lstrip("-").isdigit():
            target_id = int(target_chat)
        else:
            target_id = target_chat
            
        try:
            target_peer = await c.resolve_peer(target_id)
        except Exception as e:
            return await _m.edit_msg(f"Invalid target chat: {e}")

        try:
            # Get public admined channels
            k = await c.invoke(GetAdminedPublicChannels(by_location=False, check_limit=False))
        except Exception as e:
            return await _m.edit_msg(f"Failed to get admined channels: {e}")
        
        chats = getattr(k, 'chats', [])
        if not chats:
            return await _m.edit_msg("You don't have any public admined channels.")

        ttl = len(chats)
        _ss = 1
        _gg = 1
        _ms_notif = []
        _ms_notifb = []
        
        # Resolving target group username/id for display
        try:
            chat_obj = await c.get_chat(target_chat)
            _ev = chat_obj.username or str(chat_obj.id)
        except:
            _ev = target_chat
        
        for x in chats:
            try:
                # x is a raw pyrogram.raw.types.Chat or Channel
                _mode = getattr(x, "username", str(x.id))
                
                try:
                    channel_peer = await c.resolve_peer(_mode)
                except Exception:
                    channel_peer = await c.resolve_peer(x.id)
                
                try:
                    result = await c.invoke(
                        SaveDefaultSendAs(
                            peer=target_peer,
                            send_as=channel_peer
                        )
                    )
                    if result:
                        _notif = f"{_ss}. @{_mode} = is ok!"
                        _ss += 1
                        if _notif not in _ms_notif:
                            _ms_notif.append(_notif)
                    else:
                        _gg += 1
                except Exception as e:
                    # Banned or not allowed
                    _notifb = f"{_gg}. @{_mode} = is banned!"
                    if _notifb not in _ms_notifb:
                        _ms_notifb.append(_notifb)
                    _gg += 1
                    
                await asyncio.sleep(0.5)
            except Exception as e:
                continue
                
        _fix_notif = ("\n".join(_ms_notif)) if _ms_notif else "None"
        _fix_notifb = ("\n".join(_ms_notifb)) if _ms_notifb else "None"
        
        msg = (
            f"<blockquote expandable>"
            f"**Total :** {ttl} channel(s)\n"
            f"**Available :** {_ss - 1} channel(s)\n"
            f"**Banned :** {_gg - 1} channel(s)\n"
            f"**Target :** @{_ev}\n\n"
            f"**Available channel(s) :** \n{_fix_notif}\n\n"
            f"**Banned channel(s) :** \n{_fix_notifb}"
            f"</blockquote>"
        )
        
        await _m.edit_msg(msg)
    except Exception as e:
        Altruix.log(f"CHCheck Error: {e}\n{traceback.format_exc()}", level=40)
        await _m.edit_msg(f"**An error occurred:** `{e}`")
    finally:
        await m.delete_if_self()
