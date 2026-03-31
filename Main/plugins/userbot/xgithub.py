from pyrogram import Client, filters, enums
from Main import Altruix
from Main.core.decorators import iuser_check, log_errors
from Main.core.types.message import Message as RawMessage
import aiohttp
import os
import re
import asyncio
from datetime import datetime

# Plugin Metadata
PLUGIN_VERSION = "0.0.22"
__plugin_name__ = "xgithub"

# --- HELPER FUNCTIONS ---
async def fetch(url, re_json=False, re_content=False):
    headers = {"User-Agent": "Altruix-Userbot/0.0.1"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            if re_json:
                return await response.json()
            if re_content:
                return await response.read()
            return await response.text()

def humanbytes(size):
    if not size:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

# --- COMMANDS ---

@Altruix.register_on_cmd(
    cmd="ghdl",
    cmd_help={
        "categories": ["Utility"],
        "help": "Download GitHub repository as ZIP.",
        "usage": ".ghdl <user/repo> [branch]",
        "example": ".ghdl Altruix/AltruixX main"
    }
)
@iuser_check
@log_errors
async def github_dl(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ **Format salah.** Gunakan: `.ghdl <user/repo> [branch]`")
        return await message.delete_if_self()

    repo_info = args[1].rstrip("/")
    branch_arg = args[2] if len(args) > 2 else None
    
    # Robust regex to handle: https://github.com/user/repo, user/repo, user/repo.git
    # match.group(1) = user, match.group(2) = repo
    gh_match = re.search(r"(?:github\.com/)?([^/]+)/([^/.]+)(?:\.git)?$", repo_info)
    if not gh_match:
        return await message.reply("❌ **Username/Repo atau Link tidak valid.**")
    
    user, repo = gh_match.groups()
    repo_info = f"{user}/{repo}"  # Standardized user/repo format for labels
    
    status = await message.reply(f"⏳ **Downloading {repo}...**")
    await message.delete_if_self()
    
    # Dynamic Branch Detection
    if not branch_arg:
        try:
            api_url = f"https://api.github.com/repos/{user}/{repo}"
            repo_data = await fetch(api_url, re_json=True)
            if "default_branch" in repo_data:
                branch = repo_data["default_branch"]
            else:
                branch = "main" # Fallback
        except Exception:
            branch = "main" # Fallback if API fails
    else:
        branch = branch_arg

    download_url = f"https://github.com/{user}/{repo}/archive/refs/heads/{branch}.zip"
    
    try:
        headers = {"User-Agent": "Altruix-Userbot/0.0.1"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(download_url) as response:
                if response.status != 200 and not branch_arg and branch == "main":
                    # Final fallback if main fails and was auto-detected
                    download_url = f"https://github.com/{user}/{repo}/archive/refs/heads/master.zip"
                    async with session.get(download_url) as resp2:
                        response = resp2
                        branch = "master"
                
                if response.status != 200:
                    return await status.edit(f"❌ **Gagal mendownload.** (Status: {response.status})\nPastikan repo public dan branch '{branch}' ada.")
                
                content = await response.read()
                file_path = f"{repo}_{branch}.zip"
                with open(file_path, "wb") as f:
                    f.write(content)
        
        await status.edit(f"📤 **Uploading {repo}.zip...**")
        await client.send_document(
            chat_id=message.chat.id,
            document=file_path,
            caption=f"<blockquote expandable>📦 **Repository:** `{repo_info}`\n•  **Branch:** `{branch}`\n•  **Size:** `{humanbytes(len(content))}`</blockquote>",
            reply_to_message_id=message.id
        )
        await status.delete()
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        await status.edit(f"❌ **Error:** `{str(e)}`")

@Altruix.register_on_cmd(
    cmd="ghss",
    cmd_help={
        "categories": ["Utility"],
        "help": "Screenshot GitHub code using Carbonara.",
        "usage": ".ghss <github_link>",
        "example": ".ghss https://github.com/Altruix/AltruixX/blob/main/Main/core/client.py"
    }
)
@iuser_check
@log_errors
async def github_ss(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ **Format salah.** Gunakan: `.ghss <link_github>`")
        return await message.delete_if_self()
    
    url = args[1]
    raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    
    status = await message.reply("⏳ **Processing screenshot...**")
    await message.delete_if_self()
    
    try:
        code = await fetch(raw_url)
        if not code or "404: Not Found" in code:
            return await status.edit("❌ **Gagal mengambil kode.** Pastikan link valid dan public.")
        
        # Limit code length for Carbonara
        if len(code) > 4000:
            code = code[:4000] + "\n\n// ... (truncated)"

        carbon_url = "https://carbonara.vercel.app/api/cook"
        payload = {"code": code}
        
        headers = {"User-Agent": "Altruix-Userbot/0.0.1"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(carbon_url, json=payload) as response:
                if response.status != 200:
                    return await status.edit(f"❌ **API Screenshot Error.** (Status: {response.status})")
                
                image_data = await response.read()
                temp_img = "gh_ss.png"
                with open(temp_img, "wb") as f:
                    f.write(image_data)
        
        await client.send_photo(
            chat_id=message.chat.id,
            photo=temp_img,
            caption=f"🖥 **GitHub Code Screenshot**\n🔗 [Source Link]({url})",
            reply_to_message_id=message.id
        )
        await status.delete()
        if os.path.exists(temp_img):
            os.remove(temp_img)
            
    except Exception as e:
        await status.edit(f"❌ **Error:** `{str(e)}`")

@Altruix.register_on_cmd(
    cmd="ghinfo",
    cmd_help={
        "categories": ["Utility"],
        "help": "Get GitHub user profile information.",
        "usage": ".ghinfo <username>",
        "example": ".ghinfo Altruix"
    }
)
@iuser_check
@log_errors
async def github_info(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ **Username tidak diberikan.**")
        return await message.delete_if_self()
    
    username = args[1]
    status = await message.reply(f"🔍 **Fetching info for {username}...**")
    await message.delete_if_self()
    
    try:
        data = await fetch(f"https://api.github.com/users/{username}", re_json=True)
        if "message" in data and data["message"] == "Not Found":
            return await status.edit("❌ **User tidak ditemukan.**")
        
        name = data.get("name") or username
        bio = data.get("bio") or "No bio available."
        followers = data.get("followers", 0)
        following = data.get("following", 0)
        repos = data.get("public_repos", 0)
        created_at = datetime.strptime(data["created_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")
        profile_url = data.get("html_url")
        avatar_url = data.get("avatar_url")
        
        caption = (
            f"👤 **GitHub Profile: {name}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 **Bio:** {bio}\n"
            f"👥 **Followers:** `{followers}` | **Following:** `{following}`\n"
            f"📦 **Public Repos:** `{repos}`\n"
            f"📅 **Joined:** `{created_at}`\n"
            f"🔗 **Link:** [GitHub Profile]({profile_url})\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        
        await client.send_photo(
            chat_id=message.chat.id,
            photo=avatar_url,
            caption=caption,
            reply_to_message_id=message.id
        )
        if status:
            await status.delete()
    except Exception as e:
        if status:
            await status.edit(f"❌ **Error:** `{str(e)}`")

@Altruix.register_on_cmd(
    cmd="ghraw",
    cmd_help={
        "categories": ["Utility"],
        "help": "Convert GitHub file link to raw link.",
        "usage": ".ghraw <github_link>",
        "example": ".ghraw https://github.com/Altruix/AltruixX/blob/main/Main/core/client.py"
    }
)
@iuser_check
@log_errors
async def github_raw(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ **Link tidak diberikan.**")
        return await message.delete_if_self()
    
    url = args[1]
    if "github.com" not in url:
        await message.reply("❌ **Bukan link GitHub yang valid.**")
        return await message.delete_if_self()
        
    raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    await message.reply(f"🌐 **Raw Link:**\n`{raw_url}`", disable_web_page_preview=True)
    await message.delete_if_self()

@Altruix.register_on_cmd(
    cmd="ghsearch",
    cmd_help={
        "categories": ["Utility"],
        "help": "Search for GitHub repositories.",
        "usage": ".ghsearch <query>",
        "example": ".ghsearch altruix userbot"
    }
)
@iuser_check
@log_errors
async def github_search(client, message):
    query = message.text.split(None, 1)
    if len(query) < 2:
        await message.reply("❌ **Kata kunci tidak diberikan.**")
        return await message.delete_if_self()
    
    query = query[1]
    status = await message.reply(f"🔍 **Searching for: {query}...**")
    await message.delete_if_self()
    
    try:
        search_url = f"https://api.github.com/search/repositories?q={query}&per_page=5"
        data = await fetch(search_url, re_json=True)
        
        if not data.get("items"):
            return await status.edit("❌ **Tidak ditemukan hasil untuk kata kunci tersebut.**")
            
        res = f"🔎 **GitHub Search Results for: '{query}'**\n\n"
        for i, item in enumerate(data["items"][:5], 1):
            name = item.get("full_name")
            desc = item.get("description") or "No description"
            stars = item.get("stargazers_count", 0)
            url = item.get("html_url")
            res += f"{i}. **{name}** (⭐ {stars})\n   └ _{desc}_\n   └ [Link Repo]({url})\n\n"
            
        await status.edit(res, disable_web_page_preview=True)
    except Exception as e:
        if status:
            await status.edit(f"❌ **Error:** `{str(e)}`")

@Altruix.register_on_cmd(
    cmd="gcommitgraph",
    cmd_help={
        "categories": ["Utility"],
        "help": "Get the commit graph for a GitHub user.",
        "usage": ".gcommitgraph <username>",
        "example": ".gcommitgraph Altruix"
    }
)
@iuser_check
@log_errors
async def github_commit_graph(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ **Username tidak diberikan!**")
        return await message.delete_if_self()
    
    username = args[1]
    status = await message.reply(f"📊 **Generating commit graph for {username}...**")
    await message.delete_if_self()
    
    try:
        # Use images.weserv.nl to convert SVG to JPG
        graph_url = f"https://images.weserv.nl/?url=ghchart.rshah.org/409ba5/{username}&output=jpg"
        
        await client.send_photo(
            chat_id=message.chat.id,
            photo=graph_url,
            caption=f"📊 **GitHub Commit Graph: {username}**\n🔗 [View Profile](https://github.com/{username})",
            reply_to_message_id=message.id
        )
        if status:
            await status.delete()
    except Exception as e:
        if status:
            await status.edit(f"❌ **Error:** `{str(e)}`")
