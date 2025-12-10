# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

# from pyromod import listen
# from .core.client import AltruixClient


# Altruix = AltruixClient()
# -----------------------------------------

# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

from pyromod import listen
from .core.client import AltruixClient

# **JANGAN patch CLASS secara global - terlalu berisiko!**
# Altruix = AltruixClient()  # JANGAN letakkan di sini dulu

# === PATIENT INITIALIZATION - Inisialisasi yang lebih aman ===
def initialize_altruix_safely():
    """Inisialisasi Altruix dengan proteksi error yang lebih baik."""
    try:
        # 1. Buat instance Altruix
        altruix = AltruixClient()
        
        # 2. Coba patch client Pyrogram (jika module tersedia)
        try:
            from .utils.pyrogram_patch import patch_pyrogram_client
            
            clients_patched = 0
            
            # Patch userbot client (jika ada)
            if hasattr(altruix, 'userbot') and altruix.userbot:
                patch_pyrogram_client(altruix.userbot)
                altruix.log("[Pyrogram Patch] Userbot client telah di-patch", level=20)
                clients_patched += 1
            
            # Patch bot client (jika ada)
            if hasattr(altruix, 'bot') and altruix.bot:
                patch_pyrogram_client(altruix.bot)
                altruix.log("[Pyrogram Patch] Bot client telah di-patch", level=20)
                clients_patched += 1
            
            # Patch main client (jika berbeda)
            if hasattr(altruix, 'client') and altruix.client:
                # Cek apakah client berbeda dari userbot/bot
                if (altruix.client != getattr(altruix, 'userbot', None) and 
                    altruix.client != getattr(altruix, 'bot', None)):
                    patch_pyrogram_client(altruix.client)
                    altruix.log("[Pyrogram Patch] Main client telah di-patch", level=20)
                    clients_patched += 1
            
            if clients_patched > 0:
                altruix.log(f"[Pyrogram Patch] {clients_patched} client berhasil di-patch", level=20)
            else:
                altruix.log("[Pyrogram Patch] Tidak ada client yang perlu di-patch", level=30)
                
        except ImportError as e:
            altruix.log(f"[WARNING] Pyrogram patch module tidak ditemukan: {e}", level=30)
        except Exception as e:
            altruix.log(f"[ERROR] Gagal mem-patch client: {e}", level=40)
        
        return altruix
        
    except Exception as e:
        # Fallback jika semua gagal
        print(f"[CRITICAL] Gagal menginisialisasi Altruix: {e}")
        # Return minimal instance untuk menghindari crash total
        return AltruixClient()

# Inisialisasi dengan proteksi
Altruix = initialize_altruix_safely()
