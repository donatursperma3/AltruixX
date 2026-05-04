# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

PLUGIN_VERSION = "0.0.262[BETA]"

import os
import traceback
import asyncio
import logging
import secrets
import qrcode
import io
import base64
from datetime import datetime
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from pyrogram import Client, filters, enums, raw
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, User, CallbackQuery
from pyrogram.errors import SessionPasswordNeeded, FloodWait, RPCError, AuthTokenExpired, AuthTokenInvalid
from pyrogram.handlers import RawUpdateHandler

from Main import Altruix
from Main.core.decorators import log_errors
from Main.utils.proxypass import tunnel # ✅ ProxyPass integration

logger = logging.getLogger("Altruix.LoginQR")
# Ensure the logger always captures debug info for stable diagnostics
logger.setLevel(logging.DEBUG)

# --- FastAPI Setup ---
app = FastAPI(title="Altroid-X QR Login")

# ✅ HARD LOGGING: Create a dedicated file handler that captures everything for QR Login
# This ensures we see logs even if the main Altruix logger is filtered or redirected.
_qr_fh = logging.FileHandler("qr_login.log", mode="a", encoding="utf-8")
_qr_fh.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s'))
logger.addHandler(_qr_fh)
logger.setLevel(logging.DEBUG)
logger.debug("QR Login: [LOG_INIT] Dedicated qr_login.log initialized.")

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(TEMPLATES_PATH):
    os.makedirs(TEMPLATES_PATH)

templates = Jinja2Templates(directory=TEMPLATES_PATH)

# ✅ PERSISTENCE SENTINEL: Keep auth state alive across plugin re-imports (Soft Reloads)
import sys as _sys
if not hasattr(_sys, "_altruix_qr_auth_state"):
    _sys._altruix_qr_auth_state = {}
login_attempts = _sys._altruix_qr_auth_state

class LoginManager:
    def __init__(self, token: str, admin_user):
        self.token = token
        self.admin_user = admin_user
        self.client = None
        self.status = "waiting" # waiting, scanned, verifying, 2fa, success, error, expired
        self.error_msg = ""
        self.session_string = ""
        self.password_needed = False
        self.qr_base64 = ""
        self.raw_token = b"" # To track for refreshes
        self.loop = asyncio.get_event_loop()
        self.qr_login = None
        self.websocket = None
        self.refresh_count = 0  # ✅ NEW: auto-refresh tracker
        self.scan_event = asyncio.Event()
        self.auth_result = None
        self.lock = asyncio.Lock() # ✅ Safety: Prevents race conditions during client rebuilds
        
    def _setup_client(self, dc_id=None):
        """Create a clean Client instance, optionally pinned to a specific DC."""
        temp_name = f"qr_{self.token}"
        self.client = Client(
            temp_name,
            api_id=Altruix.config.API_ID,
            api_hash=Altruix.config.API_HASH,
            workdir="cache",
            in_memory=True,
            ipv6=False # ✅ Stability: Force IPv4 to prevent Windows connect hangs
        )
        if dc_id:
            # ✅ ROBUST DC PINNING: Pyrogram's storage.dc_id() is an async method used as
            # both getter (await storage.dc_id()) and setter (await storage.dc_id(2)).
            # We must replace it with an async function, NOT a sync lambda,
            # otherwise connect() will crash with "object int can't be used in 'await' expression".
            async def _pinned_dc_id(*args):
                return dc_id  # Always return the pinned DC, ignore setter calls
            
            if callable(getattr(self.client.storage, "dc_id", None)):
                self.client.storage.dc_id = _pinned_dc_id
            else:
                self.client.storage.dc_id = dc_id
            logger.info(f"QR Login: [CLIENT_SETUP] New client instance created and pinned to DC {dc_id}")

        
    def _add_handlers(self):
        """Register all diagnostic and auth handlers to the current client."""
        async def instant_feedback(client, update, users, chats):
            if isinstance(update, raw.types.UpdateLoginToken):
                logger.info("QR Login: [INSTANT_FEEDBACK] Caught raw UpdateLoginToken. Scanning detected!")
                # ✅ STABLE: In Phase 2, the update is just a signal.
                # We do not need to extract a token from the update itself.
                # The presence of this update triggers the handshake in _wait_for_auth.
                self.scan_event.set()
                await self.update_status("verifying")
        
        async def snoop_handler(client, update, users, chats):
            logger.debug(f"QR Login: [SNOOP] Received raw update type: {type(update).__name__}")
            
        from pyrogram.handlers import RawUpdateHandler
        self.client.add_handler(RawUpdateHandler(instant_feedback), group=-1)
        self.client.add_handler(RawUpdateHandler(snoop_handler), group=-2)

    async def update_status(self, status: str, error_msg: str = "", push_qr: bool = False):
        """Push current auth state to the connected WebSocket client."""
        self.status = status
        self.error_msg = error_msg
        logger.debug(f"QR Login: [STATUS_UPDATE] Pushing status='{status}' to WebSocket (ws={'connected' if self.websocket else 'NONE'})")
        if self.websocket:
            try:
                # ✅ BUGFIX: Use getattr() for safe access — after DC migration,
                # self.qr_login.r may be LoginTokenMigrateTo which has NO .expires attribute.
                # Direct access crashed here silently, preventing 2FA status from ever reaching the UI.
                expires = 0
                try:
                    expires = self.qr_login.r.expires if self.qr_login and self.qr_login.r else 0
                except AttributeError:
                    expires = 0  # Safe fallback after migration
                
                payload = {
                    "status": self.status,
                    "error": self.error_msg,
                    "password_needed": self.password_needed,
                    "expires_at": expires
                }
                if push_qr:
                    payload["qr_base64"] = self.qr_base64
                
                await self.websocket.send_json(payload)
                logger.debug(f"QR Login: [STATUS_SENT] Payload delivered for status: {self.status}")
            except Exception as ws_err:
                # ✅ BUGFIX: NEVER use bare except:pass — it silently swallows critical errors
                logger.error(f"QR Login: [WS_SEND_FAIL] Failed to push status '{status}' to WebSocket: {ws_err}")
        else:
            logger.warning(f"QR Login: [WS_NONE] Cannot push status '{status}' — no WebSocket connected!")

    async def start_login(self):
        """Initial check and connection establishment."""
        try:
            self._setup_client()
            
            logger.info("QR Login: [CONNECT] Establishing connection to Telegram...")
            await self.client.connect()
            logger.info("QR Login: [CONNECTED] Connection successful.")
            
            # ✅ Use Kurigram's built-in QRLogin class (event-driven, not polling)
            from pyrogram.qrlogin import QRLogin as KuriQRLogin
            self.qr_login = KuriQRLogin(self.client, except_ids=[])
            
            logger.info("QR Login: [EXPORT] Requesting initial login token...")
            await self.qr_login.recreate()
            # ✅ PERSISTENCE: Store the raw token for fallback in case raw updates are missing attributes
            if hasattr(self.qr_login.r, "token"):
                self.raw_token = self.qr_login.r.token
            
            logger.info(f"QR Login: [EXPORT_DONE] Token URL: {self.qr_login.url[:30]}...")
            
            # Generate QR Image
            qr_link = self.qr_login.url
            img = qrcode.make(qr_link)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            self.qr_base64 = base64.b64encode(buf.getvalue()).decode()
            
            # Setup handlers and start dispatcher
            self._add_handlers()
            
            # ✅ DISPATCHER START (Multi-dialect support for Pyrogram/Kurigram)
            try:
                # Check if dispatcher exists and is not active
                is_active = False
                if hasattr(self.client, "dispatcher"):
                    # Check for different possible flags (is_running, is_active, _is_running)
                    is_active = getattr(self.client.dispatcher, "is_active", 
                                getattr(self.client.dispatcher, "is_running", False))
                
                if not is_active:
                    await self.client.dispatcher.start()
                    logger.info("QR Login: [DISPATCHER] MTProto dispatcher activated.")
            except Exception as e:
                # Dispatcher might already be running internally if start() was called elsewhere
                if "attribute 'is_running'" in str(e) or "attribute 'is_active'" in str(e):
                    logger.debug("QR Login: [DISPATCHER_SKIP] Unknown dispatcher state, attempting direct start...")
                    try:
                        await self.client.dispatcher.start()
                    except Exception:
                        pass
                else:
                    logger.warning(f"QR Login: [DISPATCHER_WARN] Could not start dispatcher: {e}")

            await self.update_status("waiting")
            logger.info("QR Login: [READY] QR code generated. Waiting for scan...")
            
            asyncio.create_task(self._wait_for_auth())

        except Exception as e:
            logger.error(f"QR Login: [FATAL_INIT] Failed in start_login: {e}", exc_info=True)
            await self.update_status("error", f"Startup Error: {str(e)}")

    async def refresh_qr(self, manual: bool = False):
        """Regenerate QR token and image, then push to browser."""
        # ✅ TOP-LEVEL LOCK: Ensure and protect the entire Client lifecycle during refresh/migration
        async with self.lock:
            if self.status in ["scanned", "2fa", "success"]:
                logger.debug(f"QR Login: [REFRESH_GUARD] Current status is '{self.status}'. Skipping refresh to avoid interrupting scan process.")
                return
                
            # ✅ LIMIT CHECK: Increment counter only for auto-refreshes
            if not manual:
                self.refresh_count += 1
                if self.refresh_count > 3:
                    logger.warning(f"QR Login: [REFRESH_LIMIT] Max auto-refreshes (3) reached for token {self.token[:8]}. Stopping.")
                    await self.update_status("expired", "QR has expired. Please refresh manually.")
                    return

            try:
                logger.info(f"QR Login: [REFRESH] Generating token (Count: {self.refresh_count}, Manual: {manual})...")
                if not self.qr_login:
                    logger.warning("QR Login: [REFRESH_RECOVER] QRLogin object missing. Re-initializing...")
                    from pyrogram.qrlogin import QRLogin as KuriQRLogin
                    self.qr_login = KuriQRLogin(self.client, except_ids=[])
                    
                await self.qr_login.recreate()
                
                # ✅ PERSISTENCE: Store the raw token for fallback
                if hasattr(self.qr_login.r, "token"):
                    self.raw_token = self.qr_login.r.token
                
                # ✅ BUGFIX: Telegram may return LoginTokenMigrateTo instead of a direct token during refresh.
                from pyrogram.raw.types.auth import LoginTokenMigrateTo
                if isinstance(self.qr_login.r, LoginTokenMigrateTo):
                    try:
                        logger.info(f"QR Login: [NUCLEAR_REBUILD/REFRESH] DC Migration Required! Moving to DC {self.qr_login.r.dc_id}...")
                        target_dc = self.qr_login.r.dc_id
                        
                        # Kill the old client completely (Safely)
                        try:
                            if self.client:
                                if getattr(self.client, "is_connected", False):
                                    await self.client.stop()
                                else:
                                    # Attempt low-level termination if stop() fails or is skipped
                                    self.client.terminate()
                        except Exception as stop_error:
                            logger.debug(f"QR Login: [STOP_SILENT] Ignored error during old client disposal: {stop_error}")
                        
                        # Rebuild brand new client pinned to the new DC (Pinned in _setup_client)
                        self._setup_client(dc_id=target_dc)
                        await self.client.connect() # Re-connect to new DC
                        
                        # Clear old event just in case
                        self.scan_event.clear()
                        try:
                            # Re-add handlers and ensure dispatcher is alive on new client
                            self._add_handlers()
                            if hasattr(self.client, "dispatcher"):
                                if not getattr(self.client.dispatcher, "is_active", 
                                       getattr(self.client.dispatcher, "is_running", False)):
                                    await self.client.dispatcher.start()
                        except Exception as disp_err:
                            logger.debug(f"QR Login: [REBUILD_DISP_WARN] Dispatcher start ignored in rejuvenation: {disp_err}")
                        
                        # Re-initialize Kurigram's QRLogin class on the NEW client
                        from pyrogram.qrlogin import QRLogin as KuriQRLogin
                        self.qr_login = KuriQRLogin(self.client, except_ids=[])
                        
                        # Re-fetech token from the correct datacenter
                        logger.debug("QR Login: [NUCLEAR_REBUILD/REFRESH] Requesting new token from rejuvenated client...")
                        await self.qr_login.recreate()
                        logger.info(f"QR Login: [REBUILD_DONE/REFRESH] Successfully migrated to DC {target_dc} and generated new token.")
                    except Exception as mig_err:
                        logger.error(f"QR Login: [NUCLEAR_REBUILD_FAIL/REFRESH] Migration rejuvenation failed: {mig_err}")
                        raise # Re-raise to be caught by the outer refresh-fail handler
                    
                self.password_needed = False # Reset 2FA state for new QR
                qr_link = self.qr_login.url
                img = qrcode.make(qr_link)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                self.qr_base64 = base64.b64encode(buf.getvalue()).decode()
                
                await self.update_status("waiting", push_qr=True)
                logger.info("QR Login: [REFRESH_DONE] New QR code pushed to browser.")
            except Exception as e:
                logger.error(f"QR Login: [REFRESH_FAIL] Failed to refresh QR: {e}", exc_info=True)
                raise

    async def _wait_for_auth(self):
        """Event-driven QR scan detection using Kurigram's built-in QRLogin.wait()"""
        try:
            logger.info(f"QR Login: [WAIT] Event-driven scan listener started for token {self.token[:8]}...")
            
            while True:
                try:
                    logger.info(f"QR Login: [MANUAL_LOOP] Listening for scan event (QR: {self.token[:8]})...")
                    self.scan_event.clear()
                    
                    try:
                        # ✅ HEALTH CHECK: Ensure the client is still alive before waiting
                        if not getattr(self.client, "is_connected", False):
                            logger.warning("QR Login: [HEALTH_WARN] Client disconnected during wait. Attempting re-connect...")
                            await self.client.connect()
                            
                        # Wait for the RawUpdateHandler to catch a scan
                        # ✅ SYNC: Using 30s timeout as per FRT reference
                        await asyncio.wait_for(self.scan_event.wait(), timeout=30)
                    except asyncio.TimeoutError:
                        logger.info("QR Login: [TIMEOUT] No scan detected within 30s.")
                        await self.refresh_qr()
                        continue

                    # --- MANUAL HANDSHAKE START ---
                    logger.info("QR Login: [MANUAL_AUTH] Scan detected. Performing MTProto handshake...")
                    
                    # ✅ TOP-LEVEL LOCK: Prevent REFRESH from killing the client while we are handshaking
                    async with self.lock:
                        # 1. Export Login Token
                        try:
                            r = await self.client.invoke(
                                raw.functions.auth.ExportLoginToken(
                                    api_id=self.client.api_id,
                                    api_hash=self.client.api_hash,
                                    token=self.raw_token
                                )
                            )
                            logger.debug(f"QR Login: [MANUAL_AUTH] Handshake result type: {type(r)}")
                        except RPCError as e:
                            logger.error(f"QR Login: [MANUAL_AUTH] Export error: {e}")
                            await self.update_status("error", f"Export Error: {e}")
                            return

                        # 2. Handle Data Center Migration (The "Nuclear" Rebuild Strategy)
                        if isinstance(r, raw.types.auth.LoginTokenMigrateTo):
                            try:
                                logger.info(f"QR Login: [NUCLEAR_REBUILD] DC Migration Required! Moving to DC {r.dc_id}...")
                                import_token = r.token
                                target_dc = r.dc_id
                                
                                # Kill the old client completely (Safely)
                                if self.client and self.client.is_connected:
                                    await self.client.stop()
                                
                                # Rebuild brand new client pinned to the new DC
                                self._setup_client(dc_id=target_dc)
                                await self.client.connect() # Re-connect to new DC
                                
                                # Clear old event just in case
                                self.scan_event.clear()
                                self._add_handlers() # Re-add handlers to the NEW client instance
                                
                                try:
                                    if not self.client.dispatcher.is_running:
                                        await self.client.dispatcher.start()
                                        logger.debug(f"QR Login: [REBUILD_DONE] Dispatcher started on DC {target_dc}")
                                except Exception as e:
                                    logger.debug(f"QR Login: [DISPATCHER_SYNC] Non-critical start error: {e}")
                                
                                logger.info(f"QR Login: [REBUILD_DONE] Client successfully rejuvenated on DC {target_dc}.")
                            except Exception as mig_err:
                                logger.error(f"QR Login: [NUCLEAR_REBUILD_FAIL] Handshake migration failed: {mig_err}")
                                await self.update_status("error", f"Migration Rejuvenation Failed: {str(mig_err)}")
                                return # Stop processing this broken session
                            
                            # Continue handshake on the fresh client
                            logger.info("QR Login: [MANUAL_AUTH] Importing token on reconstructed client...")
                            r = await self.client.invoke(raw.functions.auth.ImportLoginToken(token=import_token))
                        
                        # 3. Process Final Result
                        if isinstance(r, raw.types.auth.LoginTokenSuccess):
                            logger.info(f"QR Login: [MANUAL_AUTH] Success! Logged in as user ID: {r.authorization.user.id}")
                            
                            # ✅ 401 MITIGATION: Force get_me() to ensure the client knows it is authorized
                            try:
                                logger.debug("QR Login: [MANUAL_AUTH] Syncing identity...")
                                me = await self.client.get_me()
                                await self.update_status("success")
                                await self.on_success(me=me)
                            except RPCError as e:
                                logger.error(f"QR Login: [MANUAL_AUTH] Post-auth sync failure: {e}")
                                await self.update_status("error", f"Identity Sync Failed: {e.MESSAGE}")
                            return
                            
                        elif isinstance(r, raw.types.auth.LoginToken):
                            # This shouldn't normally happen after a scan, but let's be safe
                            logger.warning("QR Login: [MANUAL_AUTH] Received unexpected LoginToken (not success/2fa).")
                            await self.refresh_qr()
                        
                except SessionPasswordNeeded:
                    logger.info("QR Login: [MANUAL_AUTH] 2FA Required. Transitioning state...")
                    self.password_needed = True
                    await self.update_status("2fa")
                    return
                    
                except Exception as e:
                    logger.error(f"QR Login: [MANUAL_AUTH] Unexpected error: {e}", exc_info=True)
                    await self.refresh_qr()
                    await asyncio.sleep(2)
                    
                except RPCError as e:
                    # 🚀 DIAGNOSTIC: Log exact MTProto error details
                    logger.warning(f"QR Login: [MTPROTO_RPC_ERR] Code: {e.CODE}, Msg: {e.MESSAGE}")
                    
                    # If token expired or invalid during wait confirm, refresh instead of crashing
                    if e.MESSAGE in ["AUTH_TOKEN_EXPIRED", "AUTH_TOKEN_INVALID"]:
                        logger.info(f"QR Login: [SOFT_ERR] Token state invalid ({e.MESSAGE}), refreshing QR...")
                        await self.refresh_qr()
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"QR Login: [UNHANDLED_RPC] {e.MESSAGE}. Raising to outer handler.")
                        raise # Fatal RPC error
                    
        except Exception as e:
            logger.error(f"QR Login: [FATAL_WAIT] Error in _wait_for_auth: {e}")
            logger.error(traceback.format_exc())
            await self.update_status("error", f"Login Error: {str(e)}")



    async def handle_2fa(self, password: str):
        try:
            logger.info("QR Login: [2FA_AUTH] Attempting 2FA password verification...")
            # check_password handles the full SRP handshake internally
            await self.client.check_password(password)
            logger.info("QR Login: [2FA_OK] Password accepted. Finalizing login...")
            await self.on_success()
        except RPCError as e:
            logger.warning(f"QR Login: [2FA_FAIL] Password rejected: {e.MESSAGE}")
            await self.update_status("2fa", error_msg=f"Invalid Password: {e.MESSAGE}")
        except Exception as e:
            logger.error(f"QR Login: [2FA_ERR] Unexpected error during 2FA: {e}")
            await self.update_status("error", f"2FA Technical Error: {str(e)}")

    async def on_success(self, me=None):
        try:
            logger.info("QR Login: [AUTH_EVENT] Authorization successful. Finalizing account state...")
            
            # If me was already provided by QRLogin.wait(), skip get_me()
            # Ensure we have the latest identity and DC info synced before export
            me = await self.client.get_me()
            logger.info(f"QR Login: [GET_ME_DONE] Logged in as {me.first_name} (ID: {me.id})")
            
            # ✅ SYNC: Small sleep to allow internal auth key state to settle in the storage
            await asyncio.sleep(0.5)
            self.session_string = self.client.export_session_string()
            logger.info("QR Login: [EXPORT_SESSION] Session string exported. Integrating with System...")
            
            # ✅ UX OPTIMIZATION: Push success to UI *before* the 15+ second plugin loading freeze
            await self.update_status("success")
            
            # Integrate with Altruix
            logger.debug("QR Login: [SYSTEM_ADD] Registering session with Altruix system...")
            new_client = await Altruix.add_session(self.session_string, user=self.admin_user, skip_reload=True)
            if new_client:
                logger.info("QR Login: [SYSTEM_DONE] Session successfully integrated and active.")
                
                # ✅ CHANGE: Prioritize notifications BEFORE potentially blocking system tasks
                try:
                    log_chat_id = Altruix.log_chat or int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
                    if log_chat_id:
                        log_msg = (
                            "✅ <b>NEW QR LOGIN SUCCESSFUL</b>\n\n"
                            f"• <b>Account:</b> {me.first_name} (<code>{me.id}</code>)\n"
                            f"• <b>Added by:</b> {self.admin_user.first_name} (<code>{self.admin_user.id}</code>)\n"
                            f"• <b>Status:</b> Session integrated, awaiting restart choice.\n"
                        )
                        await Altruix.bot.send_message(log_chat_id, log_msg)
                        
                        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                        from Main.utils.file_helpers import get_user_button_style
                        user_style = get_user_button_style(self.admin_user.id)
                        await Altruix.bot.send_message(
                            self.admin_user.id,
                            "✅ **QR Session added successfully!**\n\n"
                            "Do you want to reload the system modules now to apply changes?\n"
                            "*(Choose 'No' if you want to add more sessions first to save time)*",
                            reply_markup=InlineKeyboardMarkup([
                                [
                                    InlineKeyboardButton("Yes, Reload Now", callback_data="reload_sys_yes", style=user_style),
                                    InlineKeyboardButton("No, Later", callback_data="reload_sys_no", style=user_style)
                                ]
                            ])
                        )
                except Exception as log_err:
                    logger.error(f"QR Login: [LOG_FAIL] Error sending success log: {log_err}")

                await self.update_status("waiting_restart")
                # Save metadata to DB
                try:
                    logger.debug("QR Login: [DB_SAVE] Saving login metadata...")
                    db_col = Altruix.db.make_collection("login_qr_metadata")
                    await db_col.insert_one({
                        "_id": str(me.id),
                        "first_name": me.first_name,
                        "username": me.username,
                        "added_by": self.admin_user.id,
                        "added_at": datetime.now()
                    })
                    logger.debug("QR Login: [DB_DONE] Metadata saved.")
                except Exception as db_err:
                    logger.error(f"QR Login: [DB_ERR] Failed to save metadata: {db_err}")
            else:
                logger.error("QR Login: [SYSTEM_FAIL] Altruix.add_session returned None.")
                await self.update_status("error", "Failed to add session to the system.")

        except SessionPasswordNeeded:
            logger.info("QR Login: [2FA] Cloud password is required for this account.")
            self.password_needed = True
            await self.update_status("2fa")
            # We DON'T disconnect here because we need the client for check_password later
            return
        except Exception as e:
            logger.error(f"QR Login: Error during on_success: {e}", exc_info=True)
            await self.update_status("error", f"Auth finalize error: {str(e)}")
        finally:
            if self.client and self.status not in ["2fa", "waiting"]:
                try: await self.client.disconnect()
                except: pass


# --- FastAPI Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, token: str = None):
    if not token or token not in login_attempts:
        return HTMLResponse("<h1>Invalid or Expired Token</h1>", status_code=403)
    
    manager = login_attempts[token]
    try:
        # ✅ Starlette 1.0.0+ API: TemplateResponse(request, name, context)
        return templates.TemplateResponse(request, "login.html", {
            "token": token,
            "qr_base64": manager.qr_base64,
            "status": manager.status,
            "version": PLUGIN_VERSION,
            "expires_at": getattr(manager.qr_login.r, 'expires', 0) if manager.qr_login and manager.qr_login.r else 0
        })
    except Exception as e:
        logger.error(f"Template render error: {e}")
        return HTMLResponse(f"<h1>Error: {e}</h1>", status_code=500)

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    await websocket.accept()
    if token not in login_attempts:
        logger.warning(f"QR Login: [WS] Closure for invalid token {token[:8]}")
        await websocket.close(code=4003)
        return
    
    manager = login_attempts[token]
    manager.websocket = websocket
    
    # ✅ STATE SYNC: Push current status immediately after connection.
    # This ensures that if the browser reloads or reconnects, it immediately 
    # knows if it should show 'Verifying' or '2FA' mode.
    logger.info(f"QR Login: [WS_SYNC] Pushing initial state '{manager.status}' to new connection for token {token[:8]}")
    await manager.update_status(manager.status)
    
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            logger.debug(f"QR Login: [WS_ACTION] {action} received.")
            if action == "submit_2fa":
                password = data.get("password")
                await manager.handle_2fa(password)
            elif action == "manual_refresh":
                logger.info(f"QR Login: [MANUAL_REFRESH] User clicked refresh for token {token[:8]}")
                manager.refresh_count = 0  # Reset counter on manual action
                await manager.refresh_qr(manual=True)
            elif action == "ping":
                # Respond ASAP for latency monitoring
                await websocket.send_json({"status": "pong", "ts": data.get("ts")})
            elif action == "apply_restart":
                logger.info(f"QR Login: [RESTART_CMD] User requested restart for token {token[:8]}")
                await manager.update_status("success") # Final status before reboot
                await asyncio.sleep(1)
                await Altruix.reboot()
            elif action == "skip_restart":
                logger.info(f"QR Login: [SKIP_RESTART] User skipped restart for token {token[:8]}")
                await manager.update_status("success")
    except WebSocketDisconnect:
        logger.info(f"QR Login: [WS_DISCONNECT] Client disconnected for token {token[:8]}")
        manager.websocket = None

# --- Bot Command Handler ---

@Altruix.bot.on_message(filters.command("login_qr", "/") & Altruix.is_sudo_filter)
@log_errors
async def login_qr_handler(_, m: Message, user: User = None):
    # ✅ STEP 1: Reply IMMEDIATELY so user knows the bot is responding
    actual_user = user or m.from_user
    logger.info(f"QR Login: [CMD] Command received from {actual_user.id}")
    status_msg = await m.reply("⏳ Preparing QR Login session...")
    
    # Unique token for security
    token = secrets.token_urlsafe(16)
    
    # Port from ENV or default
    port = int(os.getenv("FASTAPI_PORT", 8080))
    web_url = os.getenv("WEB_URL", "").strip()
    
    if not web_url:
        web_url = f"http://localhost:{port}"
    
    # Ensure protocol
    if not web_url.startswith(("http://", "https://")):
        web_url = f"http://{web_url}"
    
    # Remove trailing slash for consistent joining
    web_url = web_url.rstrip("/")
    
    login_url = f"{web_url}/?token={token}"
    logger.info(f"Generated QR Login URL: {login_url}")
    
    manager = LoginManager(token, actual_user)
    login_attempts[token] = manager
    
    # ✅ STEP 2: Start ProxyPass Tunnel (Smooth accessibility)
    # If successful, this providing a public URL reachable from mobile phone
    tunnel_url = None
    try:
        await status_msg.edit("⏳ Preparing QR Login session...\n🌐 <i>Establishing secure tunnel...</i>")
        tunnel_url = await tunnel.get_url(port=port)
        if tunnel_url:
            logger.info(f"QR Login: [TUNNEL] Public URL obtained: {tunnel_url}")
            # Overlay token on tunnel URL
            login_url = f"{tunnel_url.rstrip('/')}/?token={token}"
    except Exception as tunnel_err:
        logger.warning(f"QR Login: [TUNNEL_FAIL] Could not start ProxyPass: {tunnel_err}")

    # ✅ STEP 3: Start login flow in background (don't block the handler)
    asyncio.create_task(manager.start_login())
    
    # ✅ STEP 3: Send to LOG Group with error handling
    log_chat_id = Altruix.log_chat or int(os.getenv("LOG_CHAT_ID", 0)) or m.chat.id
    
    log_text = (
        f"🔐 <b>ALTRUIX SYSTEM AUTHORIZATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Requested By:</b> {actual_user.mention}\n"
        f"🎫 <b>Auth Token:</b> <code>{token}</code>\n"
        f"📌 <b>Status:</b> 🕒 <i>Waiting for Scan...</i>\n"
        f"🤖 <b>Version:</b> <code>{PLUGIN_VERSION}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Access Links:</b>\n"
        f"• <a href='{login_url}'>Public Link (Tunnel)</a>\n"
        f"• <code>http://localhost:{port}/?token={token}</code> (Local)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Please click the authentication button below to proceed securely.</i>"
    )
    
    fallback_text = (
        f"🔐 <b>ALTRUIX SYSTEM AUTHORIZATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Requested By:</b> {actual_user.mention}\n"
        f"🎫 <b>Auth Token:</b> <code>{token}</code>\n"
        f"📌 <b>Status:</b> 🕒 <i>Waiting for Scan...</i>\n"
        f"🤖 <b>Version:</b> <code>{PLUGIN_VERSION}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Secure URL:</b>\n<code>{login_url}</code>\n\n"
        f"<i>Copy the link above to your browser to proceed securely.</i>"
    )
    
    try:
        # Try sending with inline button first (Fails if URL is localhost/invalid to Telegram)
        btn = InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Authenticate QR Login", url=login_url)
        ]])
        await Altruix.bot.send_message(
            log_chat_id,
            log_text,
            reply_markup=btn,
            parse_mode=enums.ParseMode.HTML
        )
    except RPCError as e:
        logger.warning(f"Button URL rejected by Telegram ({e.MESSAGE}), sending premium fallback.")
        await Altruix.bot.send_message(
            log_chat_id,
            fallback_text,
            parse_mode=enums.ParseMode.HTML
        )
    try:
        await status_msg.edit("✅ Login link has been sent to the LOG group.")
    except Exception:
        await m.reply("✅ Login link has been sent to the LOG group.")

@Altruix.bot.on_callback_query(filters.regex(r"^login_qr$"))
@log_errors
async def login_qr_cb_handler(c: Client, cb: CallbackQuery):
    """Callback wrapper for QR Login button."""
    await cb.answer("⏳ Preparing QR Login...", show_alert=False)
    return await login_qr_handler(c, cb.message, user=cb.from_user)

# --- Background Task to run FastAPI ---

# ✅ PROTECTION: Use a sentinel in sys to persist state across plugin re-imports (Soft Reloads)
import sys as _sys
_SENTINEL = "_altruix_qr_initialized"

async def run_fastapi():
    try:
        port = int(os.getenv("FASTAPI_PORT", 8080))
        is_debug = os.getenv("DEBUG", "false").lower() == "true"
        logger.debug(f"QR Login Server: [START_ATTEMPT] Starting FastAPI on port {port} (Debug: {is_debug})...")
        
        # --- Custom Uvicorn Logging Format ---
        # Matching [15/04/2026, 20:46:20.590] - [Altroid-X] |» DEBUG «| message
        log_format = "[%(asctime)s.%(msecs)03d] - [Altroid-X] |» %(levelname)s «| %(message)s"
        date_format = "%H:%M:%S"
        
        from Main.core.client import ColoredStreamFormatter
        
        log_config = uvicorn.config.LOGGING_CONFIG
        
        # Apply ColoredStreamFormatter to support colors and the [📍 module.function] indicator when DEBUG=True
        log_config["formatters"]["default"] = {
            "()": ColoredStreamFormatter,
            "fmt": log_format,
            "datefmt": date_format,
            "config": Altruix.config
        }
        log_config["formatters"]["access"] = {
            "()": ColoredStreamFormatter,
            "fmt": log_format,
            "datefmt": date_format,
            "config": Altruix.config
        }
        
        config = uvicorn.Config(
            app, 
            host="0.0.0.0", 
            port=port, 
            log_level="debug" if is_debug else "info",
            log_config=log_config
        )
        server = uvicorn.Server(config)
        logger.debug(f"QR Login Server: [RUNNING] Server listening at http://0.0.0.0:{port}")
        await server.serve()
    except Exception as e:
        logger.error(f"FastAPI Server error: {e}")

# Hook into Altruix startup
def init_login_qr():
    # ✅ DOUBLE-INIT PROTECTION: 
    # client.load_all_modules() unconditionally re-imports all plugins when a new session is added.
    # We use a _sys attribute as a persistent memory marker that survives module reloads.
    if hasattr(_sys, _SENTINEL):
        # The web server is already running on the event loop.
        # We don't log "Already running" here because it triggers on every scan-reload, 
        # creating noisy logs that confuse the user. We just silently skip.
        return
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
        
    loop.create_task(run_fastapi())
    setattr(_sys, _SENTINEL, True)
    logger.debug("FastAPI server for QR Login initiated.")

# Automatically start on import
init_login_qr()
