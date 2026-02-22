from Main.core.ext.ultroid_bridge import ultroid_cmd
import os
import sys

@ultroid_cmd(pattern="restart$")
async def restart_cmd(event):
    await event.eor("`Restarting...`")
    await event.client.reboot()
