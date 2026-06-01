# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.
YTDL_CORE_VERSION = "0.0.265"

import os
import time
import shutil
import asyncio
import sys
import traceback
import subprocess
import re
from pyrogram import enums
from Main import Altruix
from Main.utils.runtime_check import check_and_alert, get_js_runtime # ✅ Added get_js_runtime
from Main.utils.essentials import Essentials
from pyrogram.errors import MessageNotModified, FloodWait

TEMP_DIR = "downloads/ytdl"
os.makedirs(TEMP_DIR, exist_ok=True)

# Shared state initialized on Altruix instance
if not hasattr(Altruix, "YTDL_STATE"):
    Altruix.YTDL_STATE = {}

def get_readable_bytes(size: int) -> str:
    return Essentials.humanbytes(size)

def format_count(count: int) -> str:
    """Formats large numbers into K, M, B strings."""
    if not count: return "0"
    try:
        count = int(count)
    except (ValueError, TypeError):
        return "0"
        
    if count < 1000:
        return str(count)
    elif count < 1000000:
        return f"{count/1000:.1f}K".replace(".0K", "K")
    elif count < 1000000000:
        return f"{count/1000000:.1f}M".replace(".0M", "M")
    else:
        return f"{count/1000000000:.1f}B".replace(".0B", "B")

def format_yt_date(date_str: str) -> str:
    """Formats YYYYMMDD to DD/MM/YYYY."""
    if not date_str or len(date_str) != 8:
        return "Unknown"
    return f"{date_str[6:8]}/{date_str[4:6]}/{date_str[0:4]}"

def parse_volume_to_ffmpeg(val: str) -> str:
    try:
        if not val or val == "Original":
            return None
        if "%" in val:
            percent_str = val.split("%")[0].strip()
            try:
                percent_val = float(percent_str)
                return f"{percent_val / 100:.2f}"
            except:
                pass
        return None
    except Exception as ex:
        Altruix.log(f"parse_volume_to_ffmpeg Error: {ex}\n{traceback.format_exc()}")
        return None

async def sync_ytdl_task(task_id: str):
    """Syncs the current YTDL task state to the local database."""
    state = Altruix.YTDL_STATE.get(task_id)
    if not state:
        return
    
    # We create a persistent copy of the state
    # Exclude non-serializable objects like Clients/Tasks if any
    clean_state = {k: v for k, v in state.items() if not k.startswith("_")}
    
    try:
        col = Altruix.local_db.make_collection("ytdl_tasks")
        # Check for JS runtime at least once
        check_and_alert()

        # yt-dlp options
        await col.find_one_and_update(
            {"_id": task_id},
            {"$set": clean_state},
            upsert=True
        )
    except Exception as e:
        Altruix.log(f"YTDL Sync Error: {e}")

async def run_subprocess(cmd: list):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode(errors="replace").strip(), stderr.decode(errors="replace").strip()
    except asyncio.CancelledError:
        try:
            process.kill()
        except:
            pass
        raise
    
async def get_ffmpeg_version() -> str:
    try:
        ret, stdout, stderr = await run_subprocess(["ffmpeg", "-version"])
        if ret == 0 and stdout:
            first_line = stdout.splitlines()[0]
            match = re.search(r"version\s+([^\s,]+)", first_line)
            if match:
                return match.group(1)
            return first_line.replace("ffmpeg version ", "").split(" Copyright")[0].strip()
    except Exception as e:
        Altruix.log(f"Get FFmpeg Version Fail: {e}")
    return "Unknown"

async def get_ytdl_engine_info() -> tuple:
    # Detects if yt-dlp or youtube-dl is used and returns (engine_name, version)
    try:
        ret, stdout, stderr = await run_subprocess(["yt-dlp", "--version"])
        if ret == 0 and stdout:
            return "yt-dlp", stdout.strip()
    except:
        pass
        
    try:
        ret, stdout, stderr = await run_subprocess(["youtube-dl", "--version"])
        if ret == 0 and stdout:
            return "youtube-dl", stdout.strip()
    except:
        pass
        
    return "yt-dlp", "Unknown"

async def _get_ytdl_cookie_args() -> list:
    args = []
    try:
        cookies_file = await Altruix.config.get_env("YTDL_COOKIES_FILE") or await Altruix.config.get_env("YTDL_COOKIE_FILE")
        if cookies_file:
            cookies_file = str(cookies_file).strip().strip('"').strip("'")
            if os.path.exists(cookies_file):
                args.extend(["--cookies", cookies_file])
            else:
                Altruix.log(f"YTDL cookies file not found: {cookies_file}", level=10)
                cookies_file = None

        if not cookies_file:
            # Check default cookies.txt in root or Main
            # prioritize root, then Main
            for path in ["cookies.txt", "Main/cookies.txt"]:
                if os.path.exists(path):
                    args.extend(["--cookies", path])
                    cookies_file = path
                    break

        if not cookies_file:
            cookies_browser = (
                await Altruix.config.get_env("YTDL_COOKIES_FROM_BROWSER")
                or await Altruix.config.get_env("YTDL_COOKIES_BROWSER")
            )
            if cookies_browser:
                cookies_browser = str(cookies_browser).strip()
                args.extend(["--cookies-from-browser", cookies_browser])
    except Exception as e:
        Altruix.log(f"YTDL cookie args error: {e}\n{traceback.format_exc()}", level=10)
    return args
    
async def run_yt_dlp_with_progress(cmd: list, status_msg, task_id, state):
    """Runs yt-dlp and parses stdout to report progress via progress_callback."""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    start_time = time.time()
    last_update = 0
    full_stdout = []
    
    is_video = state.get("format") == "video"
    qual_suffix = "p" if is_video else "kbps"
    media_type = "Video" if is_video else "Audio"
    media_quality = f"{state['quality']}{qual_suffix}"
    media_name = state.get('title', 'Unknown')
    a_lang = state.get("audio_lang", "Default")
    sender_name = state.get("sender_name", "Userbot")

    # Regex for yt-dlp percentage: [download]  10.5% of ...
    prog_regex = re.compile(r"\[download\]\s+(\d+\.\d+)%")

    try:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            line_str = line.decode(errors="replace").strip()
            if not line_str: continue
            full_stdout.append(line_str)
            
            match = prog_regex.search(line_str)
            if match:
                percentage = float(match.group(1))
                # We pass percentage as current and 100 as total
                last_update = await progress_callback(
                    percentage, 100, status_msg, start_time, last_update, 
                    "Downloading", sender_name, media_type, media_quality, 
                    media_name, task_id=task_id, audio_lang=a_lang
                )
                    
        await process.wait()
        stderr_data = await process.stderr.read()
        return process.returncode, "\n".join(full_stdout), stderr_data.decode(errors="replace").strip()
    except Exception as e:
        try: process.kill()
        except: pass
        raise e

def get_progress_bar(percentage: float) -> str:
    """Standard Altruix Progress Bar: █▋░"""
    done = int(percentage / 10)
    remain = 10 - done
    return f"█{'█' * max(0, done-1)}{'▋' if done > 0 else ''}{'░' * remain}"


async def edit_status(target, text, **kwargs):
    """Universal status updater for Message or CallbackQuery (including inline)."""
    try:
        if hasattr(target, "edit_message_text"):
            # Handles CallbackQuery (Normal or Inline)
            try:
                await target.edit_message_text(text, **kwargs)
            except:
                # If editing text fails, it's likely a media message (e.g. Photo)
                # We update the caption instead
                if "caption" not in kwargs:
                    kwargs["caption"] = text
                await target.edit_message_caption(**kwargs)
        else:
            # Handles Message or other objects with edit_text
            try:
                await target.edit_text(text, **kwargs)
            except:
                if "caption" not in kwargs:
                    kwargs["caption"] = text
                await target.edit_caption(**kwargs)
    except (MessageNotModified, FloodWait):
        pass
    except Exception as e:
        Altruix.log(f"Edit Status Error: {e}")

async def progress_callback(current, total, msg, start_time, last_update_time, task_name="Uploading", sender_name=None, media_type=None, media_quality=None, media_name=None, task_id=None, audio_lang=None):
    """Throttled progress bar update (4-6s) to avoid floodwait."""
    now = time.time()
    # ✅ Optimized throttle: 10s to avoid floodwait as requested
    if now - last_update_time < 10:
        return last_update_time
        
    diff = now - start_time
    percentage = (current * 100) / total
    speed = current / diff if diff > 0 else 0
    eta = round((total - current) / speed) if speed > 0 else 0
    
    elapsed_str = Essentials.get_readable_time(round(diff))
    eta_str = Essentials.get_readable_time(eta)
    
    bar = get_progress_bar(percentage)
    
    text = f"<b>⚡️ {task_name}...</b>\n"
    if media_name:
        text += f"<b>•  Title:</b> <code>{media_name}</code>\n"
    if media_type and media_quality:
        text += f"<b>•  Type:</b> <code>{media_type} ({media_quality})</code>\n"
    if audio_lang:
        text += f"<b>•  Audio Track:</b> <code>{audio_lang}</code>\n"
        
    text += (
        f"<b>•</b> <code>{bar}</code> {percentage:.1f}%\n"
        f"<b>•  Size:</b> {get_readable_bytes(current)} / {get_readable_bytes(total)}\n"
        f"<b>•  Speed:</b> {get_readable_bytes(int(speed))}/s\n"
        f"<b>•  ETA:</b> {eta_str} | <b>⏱ Elapsed:</b> {elapsed_str}\n"
    )
    if task_id:
        text += f"<b>•  Task ID:</b> <code>{task_id}</code>\n"
    if sender_name:
        text += f"\n<b>👤 Uploader:</b> <code>{sender_name}</code>"
    
    await edit_status(msg, text, parse_mode=enums.ParseMode.HTML)
    return now

async def extract_yt_info(url: str):
    """Extraction using yt-dlp subprocess with single-JSON output."""
    # ✅ Check for JS runtime at least once
    check_and_alert()

    # We use -J (--dump-single-json) to ensure we get a single JSON object
    # even for playlists, which makes parsing much more reliable.
    cmd = ["yt-dlp", "-J", "--flat-playlist", "--extractor-args", "youtube:player_client=default"]
    
    # ✅ Enable remote solvers to fix 'n' challenge with Deno/Node
    cmd.extend(["--remote-components", "ejs:github"])
    
    # ✅ Explicitly use detected JS runtime
    runtime = get_js_runtime()
    if runtime:
        cmd.extend(["--js-runtimes", runtime])

    cmd.extend(await _get_ytdl_cookie_args())
        
    cmd.append(url)
    ret, out, err = await run_subprocess(cmd)
    if not out or ret != 0:
        error_msg = err or out or "Output kosong dari YT-DLP."
        err_lower = error_msg.lower()
        if any(x in err_lower for x in ["sign in to confirm", "confirm you're not a bot", "confirm youre not a bot", "bot detection"]):
            raise Exception(
                "YT-DLP Error: YouTube meminta verifikasi anti-bot.\n\n"
                "🛠 **Solusi:**\n"
                "1. Letakkan file <code>cookies.txt</code> di folder utama (Main).\n"
                "2. Atau set ENV <code>YTDL_COOKIES_FILE</code> dengan path cookies.\n"
                "3. Atau set ENV <code>YTDL_COOKIES_FROM_BROWSER</code> (contoh: chrome).\n\n"
                "<i>Gunakan ekstensi 'Get cookies.txt LOCALLY' di browser untuk export cookies.</i>"
            )
        raise Exception(f"YT-DLP Error: {error_msg}")
    
    import json
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        # Fallback for very rare cases where -J might produce multi-line
        try: 
            data = json.loads(out.splitlines()[0])
        except Exception:
            Altruix.log(f"YT-DLP JSON Error:\n{traceback.format_exc()}")
            raise Exception(f"Gagal memparsing JSON dari YT-DLP.")

    # 1. Handle Playlist
    if data.get("_type") == "playlist":
        entries = []
        for entry in data.get("entries", []):
            if not entry: continue
            # Find best thumb for entry
            e_thumb = entry.get("thumbnail")
            e_thumbs = entry.get("thumbnails", [])
            if e_thumbs:
                # Sort by height or width, some have only width
                e_thumbs.sort(key=lambda x: (x.get("height") or 0) * (x.get("width") or 0), reverse=True)
                e_thumb = e_thumbs[0].get("url") or e_thumb
            
            entries.append({
                "id": entry.get("id"),
                "title": entry.get("title") or "Unknown Title",
                "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
                "duration": entry.get("duration", 0),
                "views": entry.get("view_count") or 0,
                "thumbnail": e_thumb
            })
            
        # Best thumb for the playlist dashboard
        pl_thumb = data.get("thumbnail")
        pl_thumbs = data.get("thumbnails", [])
        if pl_thumbs:
            pl_thumbs.sort(key=lambda x: (x.get("height") or 0) * (x.get("width") or 0), reverse=True)
            pl_thumb = pl_thumbs[0].get("url") or pl_thumb
            
        return {
            "type": "playlist",
            "id": data.get("id"),
            "title": data.get("title") or "YouTube Playlist",
            "entries": entries,
            "count": len(entries),
            "thumbnail": pl_thumb,
            "description": data.get("description"),
            "uploader": data.get("uploader") or data.get("channel") or data.get("uploader_id") or "Unknown Channel",
            "subscribers": data.get("channel_follower_count") or data.get("subscriber_count") or 0,
            "views": data.get("view_count") or data.get("playlist_count") or 0,
            "upload_date": data.get("upload_date"),
            "extractor": data.get("extractor_key") or data.get("extractor") or "YouTube"
        }

    # 2. Handle Video (or URL reference)
    # If it's not a playlist, we need full info (formats, etc.) 
    # because the first call used --flat-playlist which hides formats.
    if data.get("_type") != "playlist":
        target_url = data.get("webpage_url") or data.get("url") or url
        # Use -J and --no-playlist to ensure we get a single video object with formats
        cmd_full = ["yt-dlp", "-J", "--no-playlist", "--extractor-args", "youtube:player_client=default"]
        
        # ✅ Enable remote solvers to fix 'n' challenge with Deno/Node
        cmd_full.extend(["--remote-components", "ejs:github"])
        
        runtime = get_js_runtime()
        if runtime:
            cmd_full.extend(["--js-runtimes", runtime])

        cmd_full.extend(await _get_ytdl_cookie_args())
            
        cmd_full.append(target_url)
        ret, out, err = await run_subprocess(cmd_full)
        if out and ret == 0:
             try: data = json.loads(out)
             except: pass

    formats = data.get("formats", [])
    if not formats:
        # Final attempt: check if it's a specific extractor result or just missing formats
        raise Exception(f"Gagal mengambil metadata video (format tidak ditemukan). URL: {url}")

    v_res = set()
    res_sizes = {}
    
    # Extract audio size
    a_sizes = [f.get("filesize") or f.get("filesize_approx") or 0 for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
    best_audio_sz = max(a_sizes) if a_sizes else 0
    
    for f in formats:
        if f.get("vcodec") != "none" and f.get("height"):
            h = f["height"]
            v_res.add(h)
            sz = f.get("filesize") or f.get("filesize_approx") or 0
            if sz > res_sizes.get(h, 0):
                res_sizes[h] = sz
                
    for h in res_sizes:
        if res_sizes[h] > 0:
            res_sizes[h] += best_audio_sz
            
    # Pick the best thumbnail from the list
    best_thumb = data.get("thumbnail")
    thumbs = data.get("thumbnails", [])
    if thumbs:
        thumbs.sort(key=lambda x: (x.get("height") or 0) * (x.get("width") or 0), reverse=True)
        best_thumb = thumbs[0].get("url") or best_thumb

    # 3. Detect Audio Languages (For Multi-Audio/Dubbing support)
    # Filter formats that have audio and collect unique languages
    languages = []
    seen_langs = set()
    for f in formats:
        if f.get("acodec") != "none":
            # Check for language code and optional note (e.g. "English (Original)")
            lang_code = f.get("language")
            lang_note = f.get("language_note")
            
            
            # Be aggressive: pick up anything that looks like a language
            lang_label = None
            if lang_code and lang_code != "none":
                # Combine code and note if available for better UI
                lang_label = lang_code
                if lang_note and lang_note != lang_code:
                    lang_label = f"{lang_code} ({lang_note})"
            elif lang_note:
                lang_label = lang_note
                
            if lang_label and lang_label not in seen_langs:
                languages.append(lang_label)
                seen_langs.add(lang_label)
    
    # Sort languages for consistent UI
    languages.sort()
    Altruix.log(f"✅ Extracted {len(languages)} audio tracks for: {data.get('title')}")

    return {
        "type": "video",
        "id": data.get("id"),
        "title": data.get("title") or "YouTube Video",
        "duration": data.get("duration", 0),
        "thumbnail": best_thumb,
        "resolutions": sorted(list(v_res), reverse=True),
        "res_sizes": res_sizes,
        "languages": languages, # ✅ Added languages list
        "chapters": data.get("chapters", []), # ✅ Added chapters list
        "description": data.get("description"), # ✅ Added description
        "url": data.get("webpage_url") or url,
        "uploader": data.get("uploader") or data.get("channel") or data.get("author") or data.get("uploader_id") or "Unknown Channel",
        "artist": data.get("artist"),
        "track": data.get("track"),
        "subscribers": data.get("channel_follower_count") or data.get("subscriber_count") or 0,
        "views": data.get("view_count") or 0,
        "upload_date": data.get("upload_date"),
        "extractor": data.get("extractor_key") or data.get("extractor") or "YouTube"
    }

async def ytdl_engine(msg, task_id):
    state = Altruix.YTDL_STATE.get(task_id) # Don't pop yet, we need it for persistence
    if not state: return
    
    # Init persistence status
    state["status"] = "running"
    await sync_ytdl_task(task_id)

    # Register with Universal Task Manager
    try:
        from Main.plugins.userbot.xtaskmanager import register_task, unregister_task
        register_task(
            task_id, asyncio.current_task(), "YouTube Tool", "xyt_tools", 
            state.get("user_id"), f"🎬 {state['title'][:30]}..."
        )
    except: unregister_task = None
    
    async def _try_return_to_dashboard() -> bool:
        try:
            from Main.plugins.bot.xyt_tools_bot import ytdl_inline_menu
        except Exception:
            return False
        try:
            if not hasattr(msg, "from_user") or not getattr(msg, "from_user", None):
                return False
            client = getattr(msg, "client", None) or getattr(msg, "_client", None) or getattr(Altruix, "bot", None)
            if not client:
                return False
            await ytdl_inline_menu(client, msg, task_id)
            return True
        except Exception:
            return False
    
    def _schedule_done_cleanup(done_at: int) -> None:
        async def _cleanup():
            await asyncio.sleep(1800)
            st = Altruix.YTDL_STATE.get(task_id)
            if st and st.get("status") == "done" and st.get("done_at") == done_at:
                Altruix.YTDL_STATE.pop(task_id, None)
        asyncio.create_task(_cleanup())

    try:
        if state.get("auto_batch") and state.get("entries"):
            entries = state["entries"]
            count = len(entries)
            start_idx = state.get("current_index", 0)
            
            if start_idx > 0:
                 await edit_status(msg, f"<b>🔄 Melanjutkan Batch Playlist ({start_idx+1}/{count})...</b>")
            else:
                 await edit_status(msg, f"<b>🚀 Menjalankan Batch Playlist ({count} items)...</b>")
            
            for i in range(start_idx, count):
                entry = entries[i]
                state["current_index"] = i
                await sync_ytdl_task(task_id)

                # Check for Task Status (Cancelled/Paused)
                while True:
                    registry = getattr(Altruix, "_TASK_REGISTRY", {})
                    if task_id not in registry: 
                         return # Task cancelled
                    if registry.get(task_id, {}).get("paused"):
                         await asyncio.sleep(2); continue # Paused
                    break
                
                await edit_status(msg, f"<b>⏳ Memproses {i+1} dari {count}:</b>\n<code>{entry['title'][:50]}...</code>")
                
                # Fetch full info for this entry
                try:
                    info = await extract_yt_info(entry["url"])
                    # Create a temporary sub-state for this unit
                    unit_state = state.copy()
                    unit_state.update({
                        "title": info["title"],
                        "url": entry["url"],
                        "duration": info["duration"],
                        "thumb": info["thumbnail"],
                        "uploader": info.get("uploader"),
                        "subscribers": info.get("subscribers"),
                        "views": info.get("views"),
                        "upload_date": info.get("upload_date"),
                        "resolutions": info.get("resolutions", []),
                        "res_sizes": info.get("res_sizes", {}),
                        "start": 0,
                        "end": info["duration"]
                        # format and quality are already set by ytdl_pl_go_cb
                    })
                    await _ytdl_single_unit(msg, task_id, unit_state)
                except Exception as e:
                    Altruix.log(f"Batch Item Fail ({i+1}): {e}\n{traceback.format_exc()}")
                    continue
            
            # Remove from DB when batch is fully done
            try:
                col = Altruix.local_db.make_collection("ytdl_tasks")
                await col.find_one_and_delete({"_id": task_id})
            except Exception:
                Altruix.log(f"YTDL DB Delete Error (Batch):\n{traceback.format_exc()}")
            
            state = Altruix.YTDL_STATE.get(task_id)
            if state:
                state["status"] = "done"
                done_at = int(time.time())
                state["done_at"] = done_at
                _schedule_done_cleanup(done_at)
            if not await _try_return_to_dashboard():
                await edit_status(msg, f"<b>✅ Batch Selesai! {count} media telah diproses.</b>")
        else:
            # Single Media Processing
            await _ytdl_single_unit(msg, task_id, state)
            
            # Remove from DB when unit is done
            try:
                col = Altruix.local_db.make_collection("ytdl_tasks")
                await col.find_one_and_delete({"_id": task_id})
            except Exception:
                Altruix.log(f"YTDL DB Delete Error (Unit):\n{traceback.format_exc()}")
            
            state = Altruix.YTDL_STATE.get(task_id)
            if state:
                state["status"] = "done"
                done_at = int(time.time())
                state["done_at"] = done_at
                _schedule_done_cleanup(done_at)
            if not await _try_return_to_dashboard():
                await edit_status(msg, "<b>✅ Done! File sent.</b>")
            
    except asyncio.CancelledError:
        await edit_status(msg, "<b>🛑 Task dibatalkan.</b>")
        raise
    except Exception:
        err_msg = traceback.format_exc()
        Altruix.log(f"YTDL Engine Crash:\n{err_msg}", level=40)
        await edit_status(msg, f"❌ <b>Error:</b> <code>{err_msg.splitlines()[-1]}</code>")
    finally:
        if "unregister_task" in locals() and unregister_task:
            unregister_task(task_id)

async def _ytdl_single_unit(status_msg, task_id, state):
    """Core logic to process and upload a single YouTube media unit."""
    temp_path = os.path.join(TEMP_DIR, f"unit_{task_id.replace('#', '')}_{int(time.time())}")
    os.makedirs(temp_path, exist_ok=True)
    
    try:
        url = state["url"]
        is_video = state["format"] == "video"
        quality = state["quality"]
        
        await edit_status(status_msg, f"<b>📥 Downloading...</b>\n<code>{state['title'][:50]}</code>")
        
        # Check for Pause
        while True:
            registry = getattr(Altruix, "_TASK_REGISTRY", {})
            if registry.get(task_id, {}).get("paused"):
                await asyncio.sleep(2); continue
            break

        # Download spec
        audio_lang = state.get("audio_lang", "Default")
        
        if is_video:
            final_name = "output.mp4"
            if audio_lang != "Default":
                clean_lang = audio_lang.split(" (")[0] if " (" in audio_lang else audio_lang
                # Fallback chain without strict extension to catch all dubbed formats
                format_spec = (
                    f"bestvideo[height<={quality}]+bestaudio[language*='{clean_lang}']/"
                    f"bestvideo[height<={quality}]+bestaudio[language_note*='{clean_lang}']/"
                    f"bestvideo[height<={quality}]+bestaudio/"
                    f"best[height<={quality}]/best"
                )
            else:
                format_spec = f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best"
        else:
            final_name = "output.mp3"
            if audio_lang != "Default":
                clean_lang = audio_lang.split(" (")[0] if " (" in audio_lang else audio_lang
                format_spec = f"bestaudio[language*='{clean_lang}']/bestaudio[language_note*='{clean_lang}']/bestaudio/best"
            else:
                format_spec = "bestaudio/best"
            
        raw_pattern = os.path.join(temp_path, "raw.%(ext)s")
        dl_cmd = ["yt-dlp", "-f", format_spec, "-o", raw_pattern, "--no-playlist", "--merge-output-format", "mp4", "--extractor-args", "youtube:player_client=default"]
        
        # ✅ Enable remote solvers for download too
        dl_cmd.extend(["--remote-components", "ejs:github"])
        
        # ✅ Use detected JS runtime for download too
        runtime = get_js_runtime()
        if runtime:
            dl_cmd.extend(["--js-runtimes", runtime])

        dl_cmd.extend(await _get_ytdl_cookie_args())
            
        dl_cmd.append(url)
        
        if not is_video:
             dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--audio-quality", f"{quality}K"])
             
        ret, out, err = await run_yt_dlp_with_progress(dl_cmd, status_msg, task_id, state)
        if ret != 0:
            err_msg = err.strip()
            if not err_msg and out:
                # Scan stdout for ERROR: lines
                lines = [line.strip() for line in out.splitlines() if line.strip()]
                for line in reversed(lines):
                    if "ERROR:" in line or "error:" in line.lower():
                        err_msg = line
                        break
                if not err_msg and lines:
                    err_msg = lines[-1]
            if not err_msg:
                err_msg = "Unknown yt-dlp error"

            err_lower = err_msg.lower()
            if any(x in err_lower for x in ["sign in to confirm", "confirm you're not a bot", "confirm youre not a bot", "bot detection"]):
                raise Exception(
                    "YT-DLP Error: YouTube meminta verifikasi anti-bot.\n\n"
                    "🛠 **Solusi:**\n"
                    "1. Letakkan file <code>cookies.txt</code> di folder utama (Main).\n"
                    "2. Atau set ENV <code>YTDL_COOKIES_FILE</code> dengan path cookies.\n"
                    "3. Atau set ENV <code>YTDL_COOKIES_FROM_BROWSER</code> (contoh: chrome).\n\n"
                    "<i>Gunakan ekstensi 'Get cookies.txt LOCALLY' di browser untuk export cookies.</i>"
                )
            raise Exception(f"Download Fail: {err_msg}")
        
        actual_raw = None
        for f in os.listdir(temp_path):
             if f.startswith("raw"):
                 actual_raw = os.path.join(temp_path, f)
                 break
        if not actual_raw: raise Exception("File raw tidak ditemukan.")
        
        target_file = os.path.join(temp_path, final_name)
        thumb_file = os.path.join(temp_path, "thumb.jpg")
        
        # Thumbnail
        thumb_url = state.get("thumb")
        if thumb_url:
            if thumb_url.startswith("//"): thumb_url = f"https:{thumb_url}"
            try:
                # Use httpx to download to avoid ffmpeg network issues
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(thumb_url)
                    if resp.status_code == 200:
                        temp_thumb = os.path.join(temp_path, "raw_thumb")
                        with open(temp_thumb, "wb") as f:
                            f.write(resp.content)
                        
                        # Process with ffmpeg to ensure compatibility (Max 320px side, maintain aspect ratio)
                        cmd_thumb = ["ffmpeg", "-i", temp_thumb, "-vf", "scale='if(gt(iw,ih),320,-1)':'if(gt(iw,ih),-1,320)'", "-vframes", "1", thumb_file, "-y"]
                        await run_subprocess(cmd_thumb)
                        if os.path.exists(temp_thumb): os.remove(temp_thumb)
            except Exception as te:
                Altruix.log(f"Thumbnail Download/Process Error: {te}")
            
        # Trim & Watermark Execution
        try:
            start_s = float(state.get("start", 0) or 0)
        except Exception:
            start_s = 0.0
        try:
            end_s = float(state.get("end", state.get("duration", 0)) or 0)
        except Exception:
            end_s = 0.0
        try:
            total_s = float(state.get("duration", 0) or 0)
        except Exception:
            total_s = 0.0
        if end_s <= 0 and total_s > 0:
            end_s = total_s
        if start_s < 0:
            start_s = 0.0
        if total_s > 0 and end_s > total_s:
            end_s = total_s
        if end_s < start_s:
            end_s = start_s
        duration = max(0.0, end_s - start_s)
        is_trimmed = (start_s != 0 or (total_s > 0 and end_s != total_s))
        wm_enabled = state.get("watermark", False)
        
        v_bitrate = state.get("video_bitrate", "Original")
        speed_val = state.get("speed", "1.0x")
        volume_val = state.get("volume", "Original")
        try: speed_float = float(speed_val.replace("x", ""))
        except: speed_float = 1.0
        if speed_float <= 0:
            speed_float = 1.0
        try:
            fade_in = float(state.get("fade_in", 0) or 0)
        except Exception:
            fade_in = 0.0
        try:
            fade_out = float(state.get("fade_out", 0) or 0)
        except Exception:
            fade_out = 0.0
        if fade_in < 0:
            fade_in = 0.0
        if fade_out < 0:
            fade_out = 0.0
        has_fade = (fade_in > 0 or fade_out > 0)
        
        # Chapters Split Branch
        split_chapters = state.get("split_chapters", False)
        chapters = state.get("chapters") or []
        if split_chapters and chapters:
            await edit_status(status_msg, f"<b>✂️ Membagi video menjadi {len(chapters)} bab...</b>")
            for idx, chap in enumerate(chapters):
                chap_start = chap.get("start_time", 0.0)
                chap_end = chap.get("end_time", state["duration"])
                chap_duration = chap_end - chap_start
                chap_title = chap.get("title", f"Bab {idx+1}")
                
                # Check for Task Status (Cancelled/Paused)
                while True:
                    registry = getattr(Altruix, "_TASK_REGISTRY", {})
                    if task_id not in registry: 
                        return # Task cancelled
                    if registry.get(task_id, {}).get("paused"):
                        await asyncio.sleep(2); continue # Paused
                    break
                
                await edit_status(status_msg, f"<b>✂️ Memproses Bab {idx+1}/{len(chapters)}:</b>\n<code>{chap_title}</code>")
                
                # Clean title for filename
                import re
                clean_title = re.sub(r'[\\/*?:"<>|]', '', chap_title)
                ext = "mp4" if is_video else "mp3"
                chap_final_name = f"{idx+1:02d}. {clean_title}.{ext}"
                chap_target_file = os.path.join(temp_path, chap_final_name)
                
                # Build FFmpeg command to cut chap_start to chap_end
                trim_cmd = ["ffmpeg", "-ss", str(chap_start), "-to", str(chap_end), "-i", actual_raw]
                
                # Apply Speed, Watermark, Volume filters to this chapter cut if they are active
                v_filters = []
                if speed_float != 1.0:
                    v_filters.append(f"setpts={1/speed_float:.4f}*PTS")
                if wm_enabled and is_video:
                    v_filters.append("drawtext=text='Altroid-X':fontcolor=white:fontsize=h/20:box=1:boxcolor=black@0.5:x=w-tw-20:y=20")
                    
                if is_video:
                    if v_filters:
                        trim_cmd.extend(["-vf", ",".join(v_filters), "-c:v", "libx264", "-preset", "veryfast"])
                    else:
                        trim_cmd.extend(["-c:v", "libx264", "-preset", "veryfast"])
                        
                    if v_bitrate != "Original":
                        v_bitrate_arg = None
                        if "Mbps" in v_bitrate:
                            v_bitrate_arg = v_bitrate.replace(" Mbps", "M")
                        elif "Kbps" in v_bitrate:
                            v_bitrate_arg = v_bitrate.replace(" Kbps", "k")
                        if v_bitrate_arg:
                            trim_cmd.extend(["-b:v", v_bitrate_arg])
                            
                    # Audio Filters
                    a_filters = []
                    if speed_float != 1.0:
                        atempo_chain = []
                        current = speed_float
                        while current > 2.0:
                            atempo_chain.append("atempo=2.0")
                            current /= 2.0
                        while current < 0.5:
                            atempo_chain.append("atempo=0.5")
                            current /= 0.5
                        atempo_chain.append(f"atempo={current:.2f}")
                        a_filters.extend(atempo_chain)
                        
                    vol_arg = parse_volume_to_ffmpeg(volume_val)
                    if vol_arg:
                        a_filters.append(f"volume={vol_arg}")
                    
                    out_dur = chap_duration / speed_float if speed_float else chap_duration
                    if out_dur < 0:
                        out_dur = 0.0
                    if fade_in > 0 and out_dur > 0:
                        d_in = min(fade_in, out_dur)
                        a_filters.append(f"afade=t=in:st=0:d={d_in:.3f}")
                    if fade_out > 0 and out_dur > 0:
                        d_out = min(fade_out, out_dur)
                        st_out = max(0.0, out_dur - d_out)
                        a_filters.append(f"afade=t=out:st={st_out:.3f}:d={d_out:.3f}")
                        
                    if a_filters:
                        trim_cmd.extend(["-af", ",".join(a_filters), "-c:a", "aac"])
                    else:
                        trim_cmd.extend(["-c:a", "copy"])
                        
                    trim_cmd.extend([chap_target_file, "-y"])
                else:
                    # Audio MP3 format
                    a_filters = []
                    if speed_float != 1.0:
                        atempo_chain = []
                        current = speed_float
                        while current > 2.0:
                            atempo_chain.append("atempo=2.0")
                            current /= 2.0
                        while current < 0.5:
                            atempo_chain.append("atempo=0.5")
                            current /= 0.5
                        atempo_chain.append(f"atempo={current:.2f}")
                        a_filters.extend(atempo_chain)
                        
                    vol_arg = parse_volume_to_ffmpeg(volume_val)
                    if vol_arg:
                        a_filters.append(f"volume={vol_arg}")
                    
                    out_dur = chap_duration / speed_float if speed_float else chap_duration
                    if out_dur < 0:
                        out_dur = 0.0
                    if fade_in > 0 and out_dur > 0:
                        d_in = min(fade_in, out_dur)
                        a_filters.append(f"afade=t=in:st=0:d={d_in:.3f}")
                    if fade_out > 0 and out_dur > 0:
                        d_out = min(fade_out, out_dur)
                        st_out = max(0.0, out_dur - d_out)
                        a_filters.append(f"afade=t=out:st={st_out:.3f}:d={d_out:.3f}")
                        
                    if a_filters:
                        trim_cmd.extend(["-af", ",".join(a_filters)])
                        
                    trim_cmd.extend(["-acodec", "libmp3lame", "-ab", f"{quality}k", chap_target_file, "-y"])
                    
                # Run FFmpeg to cut and filter
                await run_subprocess(trim_cmd)
                
                # Check that cut file exists
                if not os.path.exists(chap_target_file):
                    Altruix.log(f"Chapter Cut Fail for {chap_title}")
                    continue
                
                # Audio Metadata & Cover Embedding for MP3 chapters
                if not is_video:
                    meta_file = os.path.join(temp_path, "meta_" + chap_final_name)
                    meta_cmd = ["ffmpeg", "-i", chap_target_file]
                    if os.path.exists(thumb_file):
                        meta_cmd.extend(["-i", thumb_file, "-map", "0:0", "-map", "1:0", "-disposition:v", "attached_pic"])
                    
                    meta_cmd.extend([
                        "-c", "copy",
                        "-id3v2_version", "3",
                        "-metadata", f"title={chap_title}",
                        "-metadata", f"artist={state.get('uploader', 'Unknown Channel')}",
                        "-metadata", f"album={state['title']}",
                        meta_file, "-y"
                    ])
                    m_ret, _, _ = await run_subprocess(meta_cmd)
                    if m_ret == 0 and os.path.exists(meta_file):
                        os.remove(chap_target_file)
                        os.rename(meta_file, chap_target_file)
                
                # Let's adjust duration for speed
                actual_duration = chap_duration
                if speed_float != 1.0:
                    actual_duration = int(actual_duration / speed_float)
                    
                # Upload chapter file
                f_size = os.path.getsize(chap_target_file)
                
                # Build custom caption for this chapter
                v_bit_str = f" ({v_bitrate})" if (is_video and v_bitrate != "Original") else ""
                speed_str = f"\n<b>• Speed:</b> <code>{speed_val}</code>" if speed_val != "1.0x" else ""
                volume_str_cap = f"\n<b>• Volume:</b> <code>{volume_val}</code>" if volume_val != "Original" else ""
                fade_str_cap = ""
                if has_fade:
                    fade_str_cap = f"\n<b>• Fade:</b> <code>IN {fade_in:.2f}s | OUT {fade_out:.2f}s</code>".replace(".00s", "s").replace(".0s", "s")
                
                qual_suffix = "p" if is_video else "kbps"
                
                chap_caption = (
                    f"<blockquote expandable>"
                    f"<b>• {state['title']}</b>\n"
                    f"<b>• Bab {idx+1}/{len(chapters)}:</b> {chap_title}\n"
                    f"<b>• Channel:</b> {state.get('uploader', 'Unknown')} ({format_count(state.get('subscribers'))} subs)\n"
                    f"<b>• Upload:</b> {format_yt_date(state.get('upload_date'))}\n"
                    f"<b>• Platform:</b> {state.get('extractor', 'YouTube').capitalize()}\n"
                    f"<b>• Durasi:</b> {Essentials.get_readable_time(actual_duration)}\n"
                    f"<b>• Size:</b> {Essentials.humanbytes(f_size)}\n"
                    f"<b>• {'Resolusi' if is_video else 'Bitrate'}:</b> {state['quality']}{qual_suffix}{v_bit_str}\n"
                    f"<b>• Audio Lang:</b> {state.get('audio_lang', 'Default').upper()}"
                    f"{speed_str}"
                    f"{volume_str_cap}"
                    f"{fade_str_cap}"
                )
                if state.get("show_link", True):
                    chap_caption += f"\n<b>• Source:</b> {state['url']}"
                
                if state.get("show_desc") and state.get("description"):
                    # Limit description length to avoid hitting caption limits (max 1024)
                    desc = state["description"]
                    if len(desc) > 300:
                        desc = desc[:300] + "..."
                    chap_caption += f"\n<b>• Description:</b> <code>{desc}</code>"
                    
                chap_caption += f"</blockquote>"
                
                thumb_p = thumb_file if os.path.exists(thumb_file) else None
                
                # Perform uploader sending/backup logic
                c_idx = state.get("client_idx", 0)
                if c_idx == -1:
                    uploader = Altruix.bot
                    sender_name = "Assistant Bot"
                else:
                    uploader = Altruix.clients[c_idx] if c_idx < len(Altruix.clients) else Altruix.clients[0]
                    sender_name = state.get("sender_name", "Userbot")
                
                start_time, last_update = time.time(), 0
                media_type = "Video" if is_video else "Audio"
                media_quality = f"{state['quality']}{qual_suffix}"
                
                async def chap_up_progress(curr, total):
                    nonlocal last_update
                    a_lang = state.get("audio_lang", "Default")
                    last_update = await progress_callback(
                        curr, total, status_msg, start_time, last_update, 
                        f"Uploading {idx+1}/{len(chapters)}", sender_name, 
                        media_type, media_quality, chap_title, task_id=task_id, audio_lang=a_lang
                    )
                
                reply_id = state.get("reply_to")
                
                log_chat_id = getattr(Altruix, "log_chat", None)
                auto_backup = state.get("auto_backup", True)
                
                if auto_backup and log_chat_id:
                    backup_as_bot = state.get("backup_mode") == "bot"
                    b_client = Altruix.bot if backup_as_bot else uploader
                    backup_caption = f"{chap_caption}\n\n#backup"
                    
                    await edit_status(status_msg, f"<b>📥 Backup Bab {idx+1}/{len(chapters)} (via {'Bot' if backup_as_bot else 'Userbot'})...</b>")
                    if is_video:
                        sent_msg = await b_client.send_video(chat_id=log_chat_id, video=chap_target_file, caption=backup_caption, duration=int(actual_duration), thumb=thumb_p, supports_streaming=True, progress=chap_up_progress)
                    else:
                        sent_msg = await b_client.send_audio(chat_id=log_chat_id, audio=chap_target_file, caption=backup_caption, duration=int(actual_duration), thumb=thumb_p, title=f"Part {idx+1:02d}: {chap_title}", performer=state.get("uploader", "Unknown Channel"), file_name=chap_final_name, progress=chap_up_progress)
                    
                    await edit_status(status_msg, f"<b>📤 Forwarding Bab {idx+1}/{len(chapters)}...</b>")
                    try:
                        if b_client == uploader:
                            await sent_msg.copy(chat_id=state["chat_id"], caption=chap_caption, reply_to_message_id=reply_id)
                        else:
                            await uploader.copy_message(chat_id=state["chat_id"], from_chat_id=log_chat_id, message_id=sent_msg.id, caption=chap_caption, reply_to_message_id=reply_id)
                    except Exception as e:
                        Altruix.log(f"Chapter Backup Forward Fail: {e}")
                        if is_video:
                            await uploader.send_video(chat_id=state["chat_id"], video=chap_target_file, caption=chap_caption, duration=int(actual_duration), thumb=thumb_p, supports_streaming=True, reply_to_message_id=reply_id)
                        else:
                            await uploader.send_audio(chat_id=state["chat_id"], audio=chap_target_file, caption=chap_caption, duration=int(actual_duration), thumb=thumb_p, title=f"Part {idx+1:02d}: {chap_title}", performer=state.get("uploader", "Unknown Channel"), file_name=chap_final_name, reply_to_message_id=reply_id)
                else:
                    await edit_status(status_msg, f"<b>📤 Sending Bab {idx+1}/{len(chapters)}...</b>")
                    if is_video:
                        await uploader.send_video(chat_id=state["chat_id"], video=chap_target_file, caption=chap_caption, duration=int(actual_duration), thumb=thumb_p, supports_streaming=True, progress=chap_up_progress, reply_to_message_id=reply_id)
                    else:
                        await uploader.send_audio(chat_id=state["chat_id"], audio=chap_target_file, caption=chap_caption, duration=int(actual_duration), thumb=thumb_p, title=f"Part {idx+1:02d}: {chap_title}", performer=state.get("uploader", "Unknown Channel"), file_name=chap_final_name, progress=chap_up_progress, reply_to_message_id=reply_id)
                
                # Cleanup chapter file
                if os.path.exists(chap_target_file):
                    os.remove(chap_target_file)
            
            # Since we completed all chapters, we return successfully!
            return
            
        needs_ffmpeg = is_trimmed or (speed_float != 1.0) or (volume_val != "Original") or has_fade or (is_video and (wm_enabled or v_bitrate != "Original"))
        
        if needs_ffmpeg:
            if is_trimmed:
                act_text = "Memotong"
            elif speed_float != 1.0:
                act_text = "Mengubah Kecepatan"
            elif volume_val != "Original":
                act_text = "Menyesuaikan Volume"
            elif has_fade:
                act_text = "Menerapkan Fade"
            elif is_video and v_bitrate != "Original":
                act_text = "Mengompresi Video"
            else:
                act_text = "Merender Watermark"
            await edit_status(status_msg, f"<b>✂️ {act_text} ({Essentials.get_readable_time(int(duration))})...</b>")
            
            if is_video:
                 trim_cmd = ["ffmpeg"]
                 if is_trimmed:
                      trim_cmd.extend(["-ss", str(start_s), "-to", str(end_s)])
                 trim_cmd.extend(["-i", actual_raw])
                 
                 # Video Filters: Speed & Watermark
                 v_filters = []
                 if speed_float != 1.0:
                     v_filters.append(f"setpts={1/speed_float:.4f}*PTS")
                 if wm_enabled:
                     v_filters.append("drawtext=text='Altroid-X':fontcolor=white:fontsize=h/20:box=1:boxcolor=black@0.5:x=w-tw-20:y=20")
                     
                 need_v_encode = bool(v_filters) or is_trimmed or (v_bitrate != "Original")
                 if need_v_encode:
                      if v_filters:
                           trim_cmd.extend(["-vf", ",".join(v_filters), "-c:v", "libx264", "-preset", "veryfast"])
                      else:
                           trim_cmd.extend(["-c:v", "libx264", "-preset", "veryfast"])
                 else:
                      trim_cmd.extend(["-c:v", "copy"])
                      
                 if v_bitrate != "Original":
                      v_bitrate_arg = None
                      if "Mbps" in v_bitrate:
                          v_bitrate_arg = v_bitrate.replace(" Mbps", "M")
                      elif "Kbps" in v_bitrate:
                          v_bitrate_arg = v_bitrate.replace(" Kbps", "k")
                      if v_bitrate_arg:
                          trim_cmd.extend(["-b:v", v_bitrate_arg])
                 
                 # Audio Filters: Tempo Speed, Volume Boost & Codec Selection
                 a_filters = []
                 if speed_float != 1.0:
                     atempo_chain = []
                     current = speed_float
                     while current > 2.0:
                         atempo_chain.append("atempo=2.0")
                         current /= 2.0
                     while current < 0.5:
                         atempo_chain.append("atempo=0.5")
                         current /= 0.5
                     atempo_chain.append(f"atempo={current:.2f}")
                     a_filters.extend(atempo_chain)
                     
                 vol_arg = parse_volume_to_ffmpeg(volume_val)
                 if vol_arg:
                     a_filters.append(f"volume={vol_arg}")
                 
                 out_dur = duration / speed_float if speed_float else duration
                 if out_dur < 0:
                      out_dur = 0.0
                 if fade_in > 0 and out_dur > 0:
                      d_in = min(fade_in, out_dur)
                      a_filters.append(f"afade=t=in:st=0:d={d_in:.3f}")
                 if fade_out > 0 and out_dur > 0:
                      d_out = min(fade_out, out_dur)
                      st_out = max(0.0, out_dur - d_out)
                      a_filters.append(f"afade=t=out:st={st_out:.3f}:d={d_out:.3f}")
                     
                 if a_filters:
                     trim_cmd.extend(["-af", ",".join(a_filters), "-c:a", "aac"])
                 else:
                     trim_cmd.extend(["-c:a", "copy"])
                       
                 trim_cmd.extend([target_file, "-y"])
            else:
                 trim_cmd = ["ffmpeg"]
                 if is_trimmed: trim_cmd.extend(["-ss", str(start_s), "-to", str(end_s)])
                 trim_cmd.extend(["-i", actual_raw])
                 
                 # Audio Filters: Tempo Speed & Volume Boost
                 a_filters = []
                 if speed_float != 1.0:
                     atempo_chain = []
                     current = speed_float
                     while current > 2.0:
                         atempo_chain.append("atempo=2.0")
                         current /= 2.0
                     while current < 0.5:
                         atempo_chain.append("atempo=0.5")
                         current /= 0.5
                     atempo_chain.append(f"atempo={current:.2f}")
                     a_filters.extend(atempo_chain)
                     
                 vol_arg = parse_volume_to_ffmpeg(volume_val)
                 if vol_arg:
                     a_filters.append(f"volume={vol_arg}")
                 
                 out_dur = duration / speed_float if speed_float else duration
                 if out_dur < 0:
                      out_dur = 0.0
                 if fade_in > 0 and out_dur > 0:
                      d_in = min(fade_in, out_dur)
                      a_filters.append(f"afade=t=in:st=0:d={d_in:.3f}")
                 if fade_out > 0 and out_dur > 0:
                      d_out = min(fade_out, out_dur)
                      st_out = max(0.0, out_dur - d_out)
                      a_filters.append(f"afade=t=out:st={st_out:.3f}:d={d_out:.3f}")
                     
                 if a_filters:
                     trim_cmd.extend(["-af", ",".join(a_filters)])
                     
                 trim_cmd.extend(["-acodec", "libmp3lame", "-ab", f"{quality}k", target_file, "-y"])
                 
            await run_subprocess(trim_cmd)
            
        if speed_float != 1.0 and duration > 0:
            duration = duration / speed_float
        duration = int(duration)
        
        # Audio Metadata & Cover Embedding (Premium Feature)
        if not is_video:
            await edit_status(status_msg, "<b>🏷 Menyematkan Metadata & Cover...</b>")
            artist_src = state.get("audio_artist_src", "channel")
            final_performer = state.get("uploader", "Unknown Channel")
            final_title = state["title"]
            if artist_src == "meta":
                if state.get("artist"): final_performer = state["artist"]
                if state.get("track"): final_title = state["track"]
            elif artist_src == "none":
                final_performer = ""

            # Temporary file for metadata pass
            meta_file = os.path.join(temp_path, "meta_" + final_name)
            meta_cmd = ["ffmpeg", "-i", target_file if os.path.exists(target_file) else actual_raw]
            
            # Add thumbnail as cover if exists
            if os.path.exists(thumb_file):
                meta_cmd.extend(["-i", thumb_file, "-map", "0:0", "-map", "1:0", "-disposition:v", "attached_pic"])
            
            meta_cmd.extend([
                "-c", "copy", 
                "-id3v2_version", "3",
                "-metadata", f"title={final_title}",
                "-metadata", f"artist={final_performer}",
                "-metadata", f"album={state.get('uploader', 'Altruix YTDL')}",
                meta_file, "-y"
            ])
            
            ret, _, _ = await run_subprocess(meta_cmd)
            if ret == 0 and os.path.exists(meta_file):
                if os.path.exists(target_file): os.remove(target_file)
                os.rename(meta_file, target_file)
            elif not os.path.exists(target_file):
                # Fallback if no ffmpeg pass was done and meta pass failed
                target_file = actual_raw
        
        if not os.path.exists(target_file):
             target_file = actual_raw
             duration = state["duration"]

        # Upload Selection
        c_idx = state.get("client_idx", 0)
        if c_idx == -1:
            uploader = Altruix.bot
            sender_name = "Assistant Bot"
        else:
            uploader = Altruix.clients[c_idx] if c_idx < len(Altruix.clients) else Altruix.clients[0]
            sender_name = state.get("sender_name", "Userbot")

        f_size = os.path.getsize(target_file)
        if f_size > 2 * 1024 * 1024 * 1024:
             return await edit_status(status_msg, "<b>❌ File > 2GB.</b>")
             
        start_time, last_update = time.time(), 0
        qual_suffix = "p" if is_video else "kbps"
        
        v_bit = state.get("video_bitrate", "Original")
        v_bit_str = f" ({v_bit})" if (is_video and v_bit != "Original") else ""
        speed_val = state.get("speed", "1.0x")
        speed_str = f"\n<b>• Speed:</b> <code>{speed_val}</code>" if speed_val != "1.0x" else ""
        volume_val = state.get("volume", "Original")
        volume_str = f"\n<b>• Volume:</b> <code>{volume_val}</code>" if volume_val != "Original" else ""
        fade_str = ""
        if has_fade:
            fade_str = f"\n<b>• Fade:</b> <code>IN {fade_in:.2f}s | OUT {fade_out:.2f}s</code>".replace(".00s", "s").replace(".0s", "s")
        
        caption = (
            f"<blockquote expandable>"
            f"<b>• {state['title']}</b>\n"
            f"<b>• Channel:</b> {state.get('uploader', 'Unknown')} ({format_count(state.get('subscribers'))} subs)\n"
            f"<b>• Views:</b> {format_count(state.get('views'))}\n"
            f"<b>• Upload:</b> {format_yt_date(state.get('upload_date'))}\n"
            f"<b>• Platform:</b> {state.get('extractor', 'YouTube').capitalize()}\n"
            f"<b>• Durasi:</b> {Essentials.get_readable_time(duration)}\n"
            f"<b>• Size:</b> {Essentials.humanbytes(f_size)}\n"
            f"<b>• {'Resolusi' if is_video else 'Bitrate'}:</b> {state['quality']}{qual_suffix}{v_bit_str}\n"
            f"<b>• Audio Lang:</b> {state.get('audio_lang', 'Default').upper()}"
            f"{speed_str}"
            f"{volume_str}"
            f"{fade_str}"
        )
        if state.get("show_link", True):
             caption += f"\n<b>• Source:</b> {state['url']}"
             
        if state.get("show_desc") and state.get("description"):
             # Limit description length to avoid hitting caption limits (max 1024)
             desc = state["description"]
             if len(desc) > 300:
                 desc = desc[:300] + "..."
             caption += f"\n<b>• Description:</b> <code>{desc}</code>"
             
        caption += f"</blockquote>"
        
        thumb_p = thumb_file if os.path.exists(thumb_file) else None
        media_type = "Video" if is_video else "Audio"
        media_quality = f"{state['quality']}{qual_suffix}"
        
        # Audio Metadata Logic
        final_performer = state.get("uploader", "Unknown Channel")
        final_title = state["title"]
        file_name_arg = None
        
        if not is_video:
            artist_src = state.get("audio_artist_src", "channel")
            if artist_src == "meta":
                if state.get("artist"): final_performer = state["artist"]
                if state.get("track"): final_title = state["track"]
            elif artist_src == "none":
                final_performer = ""
                
            fmt = state.get("audio_name_fmt", "title_artist")
            if not final_performer:
                final_title_str = final_title
            else:
                if fmt == "artist_title":
                    final_title_str = f"{final_performer} - {final_title}"
                else:
                    final_title_str = f"{final_title} - {final_performer}"
                
            wm_enabled = state.get("watermark", False)
            if wm_enabled:
                final_title += " (Altroid-X)"
                final_title_str += " (Altroid-X)"
                
                
            import re
            clean_str = re.sub(r'[\\/*?:"<>|]', '', final_title_str)
            file_name_arg = f"{clean_str}.mp3"
            
            # Enforce strict Telegram compliance by physically renaming the file before upload
            new_target = os.path.join(temp_path, file_name_arg)
            if os.path.exists(target_file):
                os.rename(target_file, new_target)
                target_file = new_target
            
        media_name = final_title if is_video else clean_str

        async def up_progress(curr, total):
            nonlocal last_update
            a_lang = state.get("audio_lang", "Default")
            last_update = await progress_callback(curr, total, status_msg, start_time, last_update, "Uploading", sender_name, media_type, media_quality, media_name, task_id=task_id, audio_lang=a_lang)

        log_chat_id = getattr(Altruix, "log_chat", None)
        auto_backup = state.get("auto_backup", True)
        
        # Backup Logic
        if auto_backup and log_chat_id:
            backup_as_bot = state.get("backup_mode") == "bot"
            b_client = Altruix.bot if backup_as_bot else uploader
            
            # Add #backup hashtag for log group only
            backup_caption = f"{caption}\n\n#backup"
            
            await edit_status(status_msg, f"<b>📥 Backup (via {'Bot' if backup_as_bot else 'Userbot'})...</b>")
            if is_video:
                sent_msg = await b_client.send_video(chat_id=log_chat_id, video=target_file, caption=backup_caption, duration=int(duration), thumb=thumb_p, supports_streaming=True, progress=up_progress)
            else:
                sent_msg = await b_client.send_audio(chat_id=log_chat_id, audio=target_file, caption=backup_caption, duration=int(duration), thumb=thumb_p, title=final_title, performer=final_performer, file_name=file_name_arg, progress=up_progress)
            
            await edit_status(status_msg, "<b>📤 Forward to Chat...</b>")
            reply_id = state.get("reply_to")
            try:
                if b_client == uploader:
                    await sent_msg.copy(chat_id=state["chat_id"], caption=caption, reply_to_message_id=reply_id)
                else:
                    await uploader.copy_message(chat_id=state["chat_id"], from_chat_id=log_chat_id, message_id=sent_msg.id, caption=caption, reply_to_message_id=reply_id)
            except Exception as e:
                Altruix.log(f"Backup Forward Fail (Fallback to Direct): {e}\n{traceback.format_exc()}")
                if is_video: await uploader.send_video(chat_id=state["chat_id"], video=target_file, caption=caption, duration=int(duration), thumb=thumb_p, supports_streaming=True, reply_to_message_id=reply_id)
                else: await uploader.send_audio(chat_id=state["chat_id"], audio=target_file, caption=caption, duration=int(duration), thumb=thumb_p, title=final_title, performer=final_performer, file_name=file_name_arg, reply_to_message_id=reply_id)
        else:
            reply_id = state.get("reply_to")
            if is_video: await uploader.send_video(chat_id=state["chat_id"], video=target_file, caption=caption, duration=int(duration), thumb=thumb_p, supports_streaming=True, progress=up_progress, reply_to_message_id=reply_id)
            else: await uploader.send_audio(chat_id=state["chat_id"], audio=target_file, caption=caption, duration=int(duration), thumb=thumb_p, title=final_title, performer=final_performer, file_name=file_name_arg, progress=up_progress, reply_to_message_id=reply_id)
            
    finally:
        if os.path.exists(temp_path): shutil.rmtree(temp_path)
