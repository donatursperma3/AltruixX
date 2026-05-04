# Main/core/auto_ping.py
import asyncio
import time
import logging
import html
from datetime import datetime


logger = logging.getLogger(__name__)

# ✅ Shared constant for max Telegram message length (with safety margin for HTML tags)
MAX_MSG_LEN = 3800

class AutoPingManager:
    def __init__(self, altruix):
        self.altruix = altruix
        self.is_running = False
        self._task = None

    async def start(self):
        """Starts the auto-ping background loop if enabled."""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Auto Ping Manager initialized.")

    async def stop(self):
        """Stops the auto-ping background loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Auto Ping Manager stopped.")

    async def _loop(self):
        """Background loop that periodically pings all sessions."""
        while self.is_running:
            try:
                # Fetch settings from DB/Cache
                status = await self.altruix.config.get_env("AUTO_PING_ALL")
                mode = await self.altruix.config.get_env("AUTO_PING_MODE") or "test"
                if str(status).lower() == "on":
                    await self._execute_ping_cycle(mode=mode)

                
                # Fetch interval (default 300s = 5m)
                interval = await self.altruix.config.get_env("AUTO_PING_INTERVAL")
                try:
                    interval = int(interval) if interval else 300
                    if interval < 60: interval = 60 # Min 1 minute
                except:
                    interval = 300
                
                # Wait for next cycle
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Auto Ping Loop: {e}")
                await asyncio.sleep(60) # Retry after 1 min on error

    async def _execute_ping_cycle(self, mode="test", title="SYSTEM - AUTO PING ALL"):
        """Execute pings and send report to log chat."""

        total = len(self.altruix.clients)
        if total == 0:
            return

        results = []
        success_count = 0
        failed_count = 0

        # Get log chat id
        log_chat_id = await self.altruix.config.get_env("LOG_CHAT_ID") or self.altruix.config.OWNER_ID

        for i, client in enumerate(self.altruix.clients):
            try:
                start = time.time()
                await client.get_me()
                ping_ms = round((time.time() - start) * 1000, 2)
                results.append(f"• Session {i+1}: ✅ {ping_ms}ms")
                success_count += 1
                
                # If mode is 'message', send a ping message from this session
                if mode == "message" and log_chat_id:
                    try:
                        await client.send_message(
                            chat_id=int(log_chat_id),
                            text=f"🏓 <b>Auto Ping from Session #{i+1}</b>\nLatency: <code>{ping_ms}ms</code>",
                            parse_mode=en.ParseMode.HTML if en else "HTML"
                        )
                    except Exception as me:
                        logger.warning(f"Session {i+1} failed to send ping message: {me}")
            except Exception:
                results.append(f"• Session {i+1}: ❌ Offline")
                failed_count += 1


        # Send report via Bot Assistant
        await self._send_report(results, total, success_count, failed_count, title=title)

    async def _send_report(self, results, total, success, failed, title="SYSTEM - AUTO PING ALL"):
        """Build and send the notification to Log Group, splitting by character count."""
        try:
            log_chat_id = await self.altruix.config.get_env("LOG_CHAT_ID")
            if not log_chat_id:
                # Fallback to first owner
                log_chat_id = self.altruix.config.OWNER_ID
            
            if not log_chat_id:
                return

            status_summary = "✅ SUCCESS" if failed == 0 else "⚠️ COMPLETED" if success > 0 else "❌ FAILED"
            
            # Base components for the report
            base_header = (
                f"🏓 <b>{title} REPORT</b>\n"
                f"{'━' * 18}\n"
                f"• Status: <b>{status_summary}</b>\n"
                f"• Total Sessions: <code>{total}</code>\n"
                f"• Online: <code>{success}</code>\n"
                f"• Offline: <code>{failed}</code>\n\n"
            )
            base_footer = (
                f"\n\n• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n"
                f"{'━' * 18}"
            )

            # ✅ Character-based chunking (safe for 100k+ sessions)
            # We split by accumulated character length, NOT by fixed item count.
            chunks = []
            current_chunk = []
            current_len = 0

            for line in results:
                line_len = len(line) + 1  # +1 for newline
                if current_len + line_len > MAX_MSG_LEN and current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
                    current_len = 0
                current_chunk.append(line)
                current_len += line_len
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            
            total_parts = len(chunks)

            for idx, chunk_text in enumerate(chunks):
                part_info = f" (Part {idx + 1}/{total_parts})" if total_parts > 1 else ""
                
                # First chunk gets the full header, others get a simplified one
                if idx == 0:
                    header = base_header.replace("REPORT", f"REPORT{part_info}")
                else:
                    header = f"🏓 <b>Latency Results {part_info}:</b>\n"
                
                # Only the last chunk gets the footer
                footer = base_footer if idx == total_parts - 1 else ""
                
                log_message = (
                    f"<blockquote expandable>"
                    f"{header}"
                    f"{html.escape(chunk_text)}"
                    f"{footer}"
                    f"</blockquote>"
                )

                # Use the bot assistant to send the message
                if self.altruix.bot and self.altruix.bot.is_connected:
                    await self.altruix.bot.send_message(
                        chat_id=int(log_chat_id),
                        text=log_message,
                        parse_mode=en.ParseMode.HTML if hasattr(en, 'ParseMode') else "HTML"
                    )
                
                # Small delay between parts to avoid Telegram's flood limits
                if total_parts > 1:
                    await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Failed to send auto-ping log notification: {e}")

# Import enums for ParseMode check
try:
    from pyrogram import enums as en
except ImportError:
    en = None
