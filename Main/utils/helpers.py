# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import random
from typing import List


def arrange_buttons(array: list, no=3) -> List[list]:
    n = int(no)
    return [array[i * n : (i + 1) * n] for i in range((len(array) + n - 1) // n)]


def random_hash(length=8) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(length))

# === MAGIC: SELALU BISA PAKAI "ChatPrivileges" DI SEMUA KODEMU ===
# Walaupun Pyrogram versi lama atau baru → tetap pakai nama yang SAMA!

try:
    # Pyrogram 2.0+ → sudah ada ChatPrivileges
    from pyrogram.types import ChatPrivileges
except ImportError:
    # Pyrogram lama → kita buat "ChatPrivileges" palsu yang mirip banget
    from pyrogram.types import ChatPermissions, ChatAdministratorRights

    class ChatPrivileges:
        """
        Fake ChatPrivileges untuk Pyrogram lama.
        Tetap bisa dipakai: ChatPrivileges(can_send_messages=False, ...)
        """
        def __init__(
            self,
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_change_info=False,
            can_invite_users=True,
            can_pin_messages=False,
            # Admin rights (akan diabaikan di restrict, dipakai di promote)
            is_anonymous=False,
            can_manage_chat=False,
            can_delete_messages=False,
            can_manage_video_chats=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_post_messages=None,
            can_edit_messages=None,
            **kwargs  # biar tidak error kalau ada argumen baru
        ):
            # Simpan semua argumen
            self.__dict__.update(locals())
            del self.__dict__["self"]
            del self.__dict__["kwargs"]
            self.__dict__.update(kwargs)

            # Buat objek asli Pyrogram sesuai kebutuhan nanti
            self._permissions = ChatPermissions(
                can_send_messages=can_send_messages,
                can_send_media_messages=can_send_media_messages,
                can_send_polls=can_send_polls,
                can_send_other_messages=can_send_other_messages,
                can_add_web_page_previews=can_add_web_page_previews,
                can_change_info=can_change_info,
                can_invite_users=can_invite_users,
                can_pin_messages=can_pin_messages,
            )

            self._admin_rights = ChatAdministratorRights(
                is_anonymous=is_anonymous,
                can_manage_chat=can_manage_chat,
                can_delete_messages=can_delete_messages,
                can_manage_video_chats=can_manage_video_chats,
                can_restrict_members=can_restrict_members,
                can_promote_members=can_promote_members,
                can_change_info=can_change_info,
                can_invite_users=can_invite_users,
                can_pin_messages=can_pin_messages,
                can_post_messages=can_post_messages,
                can_edit_messages=can_edit_messages,
            )

    print("[PRIVILEGES] Menggunakan ChatPrivileges (kompatibel mode)")

# Sekarang di semua kode kamu → SELALU PAKAI INI:
# ChatPrivileges(can_send_messages=False, can_restrict_members=True, ...)
