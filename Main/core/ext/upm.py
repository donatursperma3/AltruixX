# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

"""
    Ultroid Package Manager (UPM)
    Handles synchronization of Ultroid Addons from GitHub.
"""

import os
import shlex
import shutil
import asyncio
import logging
import httpx
from typing import Any, Tuple, List

class UPM:
    def __init__(self, altruix):
        self.Altruix = altruix
        self.addons_path = "Main/plugins/addons"

    async def sync_addons(self):
        """✅ Centralized helper to SYNC Ultroid Addons from GitHub repository."""
        self.Altruix.log("📦 [UPM] Syncing Addons from GitHub...", level=logging.INFO)
        repo_url = await self.Altruix.config.get_env("ULTROID_ADDONS_REPO", default="https://github.com/sukri369/UltroidAddons")
        current_branch = await self.Altruix.config.get_env("ULTROID_ADDONS_BRANCH", default="main")
        
        if not os.path.exists(self.addons_path):
            os.makedirs(self.addons_path, exist_ok=True)
            
        # Check if already a git repo
        is_git = os.path.isdir(os.path.join(self.addons_path, ".git"))
        
        try:
            if not is_git:
                self.Altruix.log(f"📦 [UPM] First time sync. Cloning {repo_url} (branch: {current_branch})...", level=logging.INFO)
                if os.listdir(self.addons_path):
                    shutil.rmtree(self.addons_path)
                    os.makedirs(self.addons_path)
                
                out, err, code, _ = await self.Altruix.run_cmd_async(f"git clone --depth 1 -b {current_branch} {repo_url} {self.addons_path}")
                if code != 0:
                    # Fallback to master if main doesn't exist on first clone attempt
                    if "main" in current_branch:
                        out, err, code, _ = await self.Altruix.run_cmd_async(f"git clone --depth 1 -b master {repo_url} {self.addons_path}")
                    
                    if code != 0:
                        self.Altruix.log(f"❌ [UPM] Git Clone Failed ({code}): {err or out}", level=logging.ERROR)
                        return False
            else:
                self.Altruix.log(f"📦 [UPM] Updating existing addons (branch: {current_branch})...", level=logging.INFO)
                out, err, code, _ = await self.Altruix.run_cmd_async(f"git -C {self.addons_path} fetch origin")
                if code == 0:
                    out, err, code, _ = await self.Altruix.run_cmd_async(f"git -C {self.addons_path} reset --hard origin/{current_branch}")
                    
                    # ✅ Fallback resilience: If 'main' fails, try 'master' as a smart guess
                    if code != 0 and current_branch == "main":
                        self.Altruix.log("⚠️ [UPM] 'main' branch failed, trying 'master' as fallback...", level=logging.INFO)
                        out, err, code, _ = await self.Altruix.run_cmd_async(f"git -C {self.addons_path} reset --hard origin/master")
                
                if code != 0:
                    self.Altruix.log(f"❌ [UPM] Git Update Failed ({code}): {err or out}", level=logging.ERROR)
                    return False
            
            self.Altruix.log("✅ [UPM] Addons synchronized successfully.", level=logging.INFO)
            return True
        except Exception as e:
            self.Altruix.log(f"❌ [UPM] Sync Error: {e}", level=logging.ERROR)
            return False

    async def switch_branch(self, branch_name: str):
        """✅ Switch repository branch and sync."""
        if not os.path.isdir(os.path.join(self.addons_path, ".git")):
            return False, "Not a git repository."
        
        out, err, code, _ = await self.Altruix.run_cmd_async(f"git -C {self.addons_path} fetch origin")
        if code != 0:
            return False, f"Fetch failed: {err}"
            
        out, err, code, _ = await self.Altruix.run_cmd_async(f"git -C {self.addons_path} checkout {branch_name}")
        if code != 0:
            return False, f"Checkout failed: {err}"

        await self.Altruix.config.sync_env_to_db("ULTROID_ADDONS_BRANCH", branch_name, upsert=True)
        return True, f"Successfully switched to {branch_name} branch."

    async def install_plugin(self, url: str) -> Tuple[bool, str]:
        """✅ Download a single .py plugin from a URL."""
        if not url.endswith(".py"):
            return False, "URL must point to a .py file."
            
        name = url.split("/")[-1]
        target_path = os.path.join(self.addons_path, name)
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return False, f"Download failed: {resp.status_code}"
                
                with open(target_path, "wb") as f:
                    f.write(resp.content)
            return True, f"Plugin {name} installed successfully."
        except Exception as e:
            return False, f"Error: {e}"

    async def uninstall_plugin(self, name: str) -> bool:
        """✅ Delete a specific addon file."""
        target_path = os.path.join(self.addons_path, name)
        if os.path.exists(target_path):
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            return True
        return False

    def list_addons(self) -> List[str]:
        """✅ List all .py files in addons directory."""
        if not os.path.exists(self.addons_path):
            return []
        # Return only filename, ignoring hidden files and directories
        return [f for f in os.listdir(self.addons_path) if f.endswith(".py") and not f.startswith(".")]
