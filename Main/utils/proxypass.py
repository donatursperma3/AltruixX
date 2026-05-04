# ©️ Altruix, 2024
# Part of Altroid-X project
# Exclusively implementing ProxyPass for QR Login stability

import asyncio
import logging
import re
import os
import atexit
from typing import Optional

logger = logging.getLogger("Altruix.ProxyPass")

class ProxyPasser:
    """
    Manages a secure tunnel to expose a local port to the internet.
    Uses ssh -R via localhost.run (Safe and Dependency-Free).
    """
    def __init__(self):
        self._tunnel_url: Optional[str] = None
        self._sproc: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()

    async def _read_stdout(self):
        """Parse SSH output to find the tunnel URL."""
        if not self._sproc or not self._sproc.stdout:
            return

        # Regex for localhost.run URLs
        # Examples: https://8589c3ac3674d8.lhr.life or https://user-123.localhost.run
        url_pattern = re.compile(r"https?://[a-zA-Z0-9-]+\.(?:lhr\.life|localhost\.run)")

        try:
            while not self._stop_event.is_set():
                line = await self._sproc.stdout.readline()
                if not line:
                    break
                
                decoded_line = line.decode("utf-8", errors="ignore").strip()
                logger.debug(f"ProxyPass SSH: {decoded_line}")

                match = url_pattern.search(decoded_line)
                if match:
                    self._tunnel_url = match.group(0)
                    logger.info(f"ProxyPass Tunnel URL: {self._tunnel_url}")
                    # Keep reading to avoid buffer overflow, but we found the URL
        except Exception as e:
            logger.error(f"ProxyPass stdout reader error: {e}")

    async def get_url(self, port: int, timeout: int = 15) -> Optional[str]:
        """
        Starts the tunnel if not running and returns the public URL.
        """
        async with self._lock:
            # If already running and process is still alive
            if self._tunnel_url and self._sproc and self._sproc.returncode is None:
                return self._tunnel_url

            logger.info(f"Starting ProxyPass tunnel for port {port}...")
            self._stop_event.clear()
            self._tunnel_url = None

            # Command: ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:{port} nokey@localhost.run
            # -o StrictHostKeyChecking=no: Bypass fingerprint prompts
            # -R 80:127.0.0.1:{port}: Remote forward port 80 to our local port
            cmd = f"ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:{port} nokey@localhost.run"

            try:
                self._sproc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE
                )

                # Wait for URL in background
                asyncio.create_task(self._read_stdout())

                # Wait for the URL to be populated with a timeout
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < timeout:
                    if self._tunnel_url:
                        return self._tunnel_url
                    await asyncio.sleep(0.5)

                    # Check if process died early
                    if self._sproc.returncode is not None:
                        stderr_data = await self._sproc.stderr.read()
                        logger.error(f"ProxyPass SSH process died: {stderr_data.decode()}")
                        break

                logger.warning("ProxyPass tunnel timeout or failed to obtain URL.")
                return None

            except Exception as e:
                logger.error(f"Failed to initiate ProxyPass tunnel: {e}")
                return None

    async def stop(self):
        """Cleanly terminate the SSH process."""
        async with self._lock:
            self._stop_event.set()
            if self._sproc:
                try:
                    self._sproc.terminate()
                    # Give it a moment to die gracefully
                    try:
                        await asyncio.wait_for(self._sproc.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        self._sproc.kill()
                    logger.info("ProxyPass tunnel terminated.")
                except Exception as e:
                    logger.debug(f"Error while stopping ProxyPass: {e}")
                finally:
                    self._sproc = None
                    self._tunnel_url = None

# Global Instance for easy access
tunnel = ProxyPasser()

# Register cleanup at exit
def _sync_cleanup():
    if tunnel._sproc:
        try:
            tunnel._sproc.terminate()
        except:
            pass

atexit.register(_sync_cleanup)
