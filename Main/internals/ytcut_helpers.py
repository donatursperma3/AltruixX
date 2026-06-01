# Copyright (C) 2026 by Altruix@Github, < https://github.com/Altruix >.
# This file is part of the Altruix project.
# All rights reserved.

import copy
import hashlib
import html
import json
import logging
import os
import re
import time
import traceback
import asyncio
from typing import Any, Dict, List, Optional, Tuple

import httpx
from pyrogram import enums, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from Main import Altruix
from Main.utils.essentials import Essentials
from Main.utils.file_helpers import get_db_path, get_user_button_style
from Main.internals.ytdl_core import run_subprocess
from Main.internals.ytdl_core import extract_yt_info as _extract_yt_info

YTCUT_TEMP_DIR = os.path.join("downloads", "ytcut")
os.makedirs(YTCUT_TEMP_DIR, exist_ok=True)

YTCUT_QUALITY_CHOICES = ["360", "480", "720", "1080"]
YTCUT_DEFAULT_QUALITY = "720"
YTCUT_DEFAULT_EXTRACT = "video"
PLUGIN_VERSION = "1.0.267"
__version__ = PLUGIN_VERSION
YTCUT_CONFIG_FILE = get_db_path("xytcut_settings.json")

# ✅ VERIFICATION: Import-level check to confirm module loaded with INFO logging enabled
Altruix.log("✅ YTcut helpers module loaded with INFO-level logging enabled (v1.0.267+)", level=logging.INFO)
YTCUT_DEFAULT_CONFIG = {
    "global": {"mode": "keep", "extract": YTCUT_DEFAULT_EXTRACT, "quality": YTCUT_DEFAULT_QUALITY},
    "users": {},
}


def load_ytcut_config() -> Dict[str, Any]:
    if not os.path.exists(YTCUT_CONFIG_FILE):
        return copy.deepcopy(YTCUT_DEFAULT_CONFIG)
    try:
        with open(YTCUT_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return copy.deepcopy(YTCUT_DEFAULT_CONFIG)
        global_config = data.get("global")
        if not isinstance(global_config, dict):
            global_config = {}
        data["global"] = {**YTCUT_DEFAULT_CONFIG["global"], **global_config}
        users = data.get("users")
        if not isinstance(users, dict):
            users = {}
        data["users"] = users
        return data
    except Exception as e:
        Altruix.log(f"YTcut config load failed: {e}\n{traceback.format_exc()}")
        return copy.deepcopy(YTCUT_DEFAULT_CONFIG)


def save_ytcut_config(config: Dict[str, Any]) -> None:
    try:
        with open(YTCUT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        Altruix.log(f"YTcut config save failed: {e}\n{traceback.format_exc()}")


def get_ytcut_user_config(user_id: Optional[int]) -> Dict[str, Any]:
    config = load_ytcut_config()
    if user_id is None:
        return config["global"].copy()
    user_data = config.get("users", {}).get(str(user_id), {})
    result = config.get("global", {}).copy()
    if isinstance(user_data, dict):
        result.update(user_data)
    return result


def save_ytcut_user_config(user_id: Optional[int], patch: Dict[str, Any]) -> None:
    if user_id is None:
        return
    config = load_ytcut_config()
    users = config.setdefault("users", {})
    current = users.get(str(user_id), {})
    if not isinstance(current, dict):
        current = {}
    current.update(patch)
    users[str(user_id)] = current
    config["users"] = users
    save_ytcut_config(config)


def ensure_ytcut_state_registry() -> None:
    if not hasattr(Altruix, "YTCUT_STATE"):
        Altruix.YTCUT_STATE = {}
    if not hasattr(Altruix, "YTCUT_QUEUE"):
        Altruix.YTCUT_QUEUE = []
    if not hasattr(Altruix, "YTCUT_LOCK"):
        Altruix.YTCUT_LOCK = asyncio.Lock()


async def notify_ytcut_error_to_group_log(error: str, state: Dict[str, Any], traceback_text: str = "", stage: Optional[str] = None) -> None:
    log_chat = getattr(Altruix, "log_chat", None)
    if not log_chat:
        return
    task_id = html.escape(str(state.get("task_id", "Unknown")))
    url = html.escape(str(state.get("url", "Unknown")))
    title = html.escape(str(state.get("title", "Unknown")))
    stage_text = html.escape(str(stage or state.get("ytcut_stage", "Unknown stage")))
    user_id = state.get("user_id")
    user_field = f"<b>User ID:</b> <code>{user_id}</code>\n" if user_id is not None else ""
    traceback_snippet = ""
    if traceback_text:
        trace = traceback_text.strip().replace('`', '"')
        traceback_snippet = html.escape(trace[:900])
    log_text = (
        f"❌ <b>YTcut Error</b>\n"
        f"<b>Task:</b> <code>{task_id}</code>\n"
        f"<b>Title:</b> {title}\n"
        f"<b>Stage:</b> {stage_text}\n"
        f"<b>Source:</b> <code>{url}</code>\n"
        f"{user_field}"
        f"<blockquote expandable>{html.escape(error)}</blockquote>"
    )
    if traceback_snippet:
        log_text += f"\n<pre>{traceback_snippet}</pre>"
    try:
        await Altruix.bot.send_message(
            log_chat,
            log_text,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as send_err:
        Altruix.log(f"YTcut group log notify failed: {send_err}\n{traceback.format_exc()}")


async def sync_ytcut_task(task_id: str) -> None:
    ensure_ytcut_state_registry()
    state = Altruix.YTCUT_STATE.get(task_id)
    if not state:
        return
    clean_state = {k: v for k, v in state.items() if not str(k).startswith("_")}
    try:
        col = Altruix.local_db.make_collection("ytcut_tasks")
        await col.find_one_and_update({"_id": task_id}, {"$set": clean_state}, upsert=True)
    except Exception as e:
        Altruix.log(f"YTcut sync failed: {e}\n{traceback.format_exc()}")


async def delete_ytcut_task(task_id: str) -> None:
    try:
        col = Altruix.local_db.make_collection("ytcut_tasks")
        await col.find_one_and_delete({"_id": task_id})
    except Exception as e:
        Altruix.log(f"YTcut delete task failed: task_id={task_id} error={e}\n{traceback.format_exc()}")


async def get_ytcut_task_state(task_id: str) -> Optional[Dict[str, Any]]:
    ensure_ytcut_state_registry()
    state = Altruix.YTCUT_STATE.get(task_id)
    if state:
        return state
    try:
        col = Altruix.local_db.make_collection("ytcut_tasks")
        doc = await col.find_one({"_id": task_id})
        if not doc:
            return None
        if isinstance(doc, dict):
            doc.pop("_id", None)
            Altruix.YTCUT_STATE[task_id] = doc
            return doc
    except Exception:
        return None
    return None


def make_ytcut_task_id(url: str) -> str:
    short_hash = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:6]
    return f"YTC{short_hash}"


def parse_ytcut_timestamp(ts: str) -> float:
    cleaned = ts.strip()
    if not cleaned:
        raise ValueError("Timestamp kosong.")
    parts = [p.strip() for p in cleaned.split(":") if p.strip() != ""]
    if not parts:
        raise ValueError("Format timestamp tidak dikenali.")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    raise ValueError("Timestamp harus berupa MM:SS atau HH:MM:SS atau detik langsung.")


def format_ytcut_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds or 0.0))
    whole = int(seconds)
    frac = round(seconds - whole, 2)
    h = whole // 3600
    m = (whole % 3600) // 60
    s = whole % 60
    frac_txt = ""
    if abs(frac) >= 0.005:
        frac_txt = f"{frac:.2f}".lstrip("0")
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}{frac_txt}"
    return f"{m:02d}:{s:02d}{frac_txt}"


def ytcut_time_to_yt_format(seconds: float) -> str:
    seconds = max(0.0, float(seconds or 0.0))
    whole = int(seconds)
    frac = seconds - whole
    h = whole // 3600
    m = (whole % 3600) // 60
    s = whole % 60
    base = f"{h:02d}:{m:02d}:{s:02d}"
    if frac <= 0:
        return base
    ms = int(round(frac * 1000))
    if ms <= 0:
        return base
    if ms >= 1000:
        whole += 1
        h = whole // 3600
        m = (whole % 3600) // 60
        s = whole % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{base}.{ms:03d}"


def normalize_ytcut_segments(segments: List[Tuple[float, float]], duration: float) -> List[Dict[str, float]]:
    normalized: List[Dict[str, float]] = []
    for start, end in segments:
        start = max(0.0, float(start))
        end = min(float(duration), float(end))
        if start >= end - 0.001:
            continue
        normalized.append({"start": start, "end": end, "duration": end - start})
    if not normalized:
        return []
    normalized.sort(key=lambda x: x["start"])
    merged = [normalized[0].copy()]
    for seg in normalized[1:]:
        last = merged[-1]
        if seg["start"] <= last["end"] + 0.001:
            if seg["end"] > last["end"]:
                last["end"] = seg["end"]
                last["duration"] = last["end"] - last["start"]
        else:
            merged.append(seg.copy())
    return merged


def ytcut_segments_overlap(segments: List[Dict[str, float]]) -> bool:
    for i in range(1, len(segments)):
        if float(segments[i]["start"]) < float(segments[i - 1]["end"]) - 0.001:
            return True
    return False


def build_keep_segments_from_remove(remove_segments: List[Dict[str, float]], duration: float) -> List[Dict[str, float]]:
    remove_segments = normalize_ytcut_segments([(seg["start"], seg["end"]) for seg in remove_segments], duration)
    keep_segments: List[Dict[str, float]] = []
    current = 0.0
    for seg in remove_segments:
        if seg["start"] > current + 0.001:
            keep_segments.append({"start": current, "end": seg["start"], "duration": seg["start"] - current})
        current = max(current, seg["end"])
    if current < duration:
        keep_segments.append({"start": current, "end": duration, "duration": duration - current})
    return keep_segments


def find_ytcut_state_by_prompt_message_id(prompt_message_id: int) -> Optional[Dict[str, Any]]:
    ensure_ytcut_state_registry()
    for state in Altruix.YTCUT_STATE.values():
        if state.get("prompt_message_id") == prompt_message_id:
            return state
    return None


def find_ytcut_state_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    ensure_ytcut_state_registry()
    for state in Altruix.YTCUT_STATE.values():
        if state.get("user_id") == user_id and state.get("prompt_message_id") is not None:
            return state
    return None


def build_ytcut_dashboard_text(state: Dict[str, Any]) -> str:
    seg_text: List[str] = []
    if state["segments"]:
        for idx, seg in enumerate(state["segments"], start=1):
            seg_text.append(
                f"{idx}. <code>{format_ytcut_timestamp(seg['start'])} - {format_ytcut_timestamp(seg['end'])}</code> (<code>{format_ytcut_timestamp(seg['duration'])}</code>)"
            )
    else:
        seg_text.append("*Belum ada potongan yang ditambahkan.*")

    mode_label = state["mode"].upper()
    extract_label = "AUDIO ONLY" if state["extract"] == "audio" else "VIDEO"
    quality_label = f"{state['quality']}p"
    total_duration = Essentials.get_readable_time(state["duration"])

    merge_status = []
    if state.get("merge_in_progress"):
        merge_status.append("<b>Merge Status:</b> <code>In Progress</code>")
    elif state.get("merge_completed"):
        merge_status.append("<b>Merge Status:</b> <code>Completed</code>")
    elif state.get("merge_error"):
        merge_status.append(f"<b>Merge Status:</b> <code>Failed</code> | {html.escape(str(state.get('merge_error'))[:120])}")

    merge_status_text = "\n".join(merge_status) + "\n" if merge_status else ""

    return (
        f"<blockquote expandable>"
        f"🎬 <b>YouTube Multi-Cutter Dashboard</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>• Judul:</b> {html.escape(state['title'])}\n"
        f"<b>• Total Durasi:</b> {total_duration}\n"
        f"<b>• Mode:</b> <code>{mode_label}</code>\n"
        f"<b>• Ekstrak:</b> <code>{extract_label}</code>\n"
        f"<b>• Kualitas:</b> <code>{quality_label}</code>\n"
        f"{merge_status_text}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✂️ <b>Daftar Potongan (Mode: {mode_label}):</b>\n"
        f"{'\n'.join(seg_text)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Gunakan tombol di bawah untuk menambahkan durasi yang ingin diambil.\n"
        f"</blockquote>"
    )


def build_ytcut_dashboard_keyboard(state: Dict[str, Any]) -> InlineKeyboardMarkup:
    mode_label = "REMOVE" if state["mode"] == "remove" else "KEEP"
    extract_label = "AUDIO ONLY" if state["extract"] == "audio" else "VIDEO"
    quality_label = f"{state['quality']}p"

    # Resolve per-session/account button style
    try:
        user_style = get_user_button_style(state.get("user_id"))
    except Exception:
        user_style = None

    def kb_btn(text: str, cb: str):
        if user_style is not None:
            return InlineKeyboardButton(text, callback_data=cb, style=user_style)
        return InlineKeyboardButton(text, callback_data=cb)

    buttons: List[List[InlineKeyboardButton]] = [
        [
            kb_btn("➕ Tambah Potongan", f"ytcut_add_menu#{state['task_id']}"),
            kb_btn(f"⚙️ Ganti Mode ({mode_label})", f"ytcut_toggle_mode#{state['task_id']}")
        ],
        [
            kb_btn(f"🎼 Ekstrak: {extract_label}", f"ytcut_toggle_extract#{state['task_id']}"),
            kb_btn(f"🎞️ Kualitas: {quality_label}", f"ytcut_cycle_quality#{state['task_id']}")
        ],
    ]

    if len(state["segments"]) >= 2:
        buttons.append([
            kb_btn("🔄 Ubah Susunan / Urutan", f"ytcut_reorder_menu#{state['task_id']}"),
            kb_btn("🔀 Merge All Segmen", f"ytcut_merge_decision#{state['task_id']}")
        ])

    buttons.extend([
        [
            kb_btn("❌ Batalkan", f"ytcut_cancel#{state['task_id']}"),
            kb_btn("🎬 MULAI PROSES", f"ytcut_start#{state['task_id']}")
        ],
    ])

    if state["segments"]:
        for idx, seg in enumerate(state["segments"], start=1):
            buttons.append([
                kb_btn(f"✏️ Edit S{idx}", f"ytcut_edit_seg#{state['task_id']}#{idx - 1}"),
                kb_btn(f"🗑️ Hapus S{idx}", f"ytcut_remove#{state['task_id']}#{idx - 1}")
            ])
    return InlineKeyboardMarkup(buttons)


async def extract_yt_info(url: str):
    try:
        return await _extract_yt_info(url)
    except Exception as e:
        Altruix.log(f"YTcut wrapper extract_yt_info failed: {e}\n{traceback.format_exc()}")
        raise


async def get_inline_bot_results_for_client(client: Any, query: str):
    # Helper to fetch inline bot results for the current bot identity.
    # This is used by ytcut_cmd to build a temporary inline dashboard result.
    # If the bot username cannot be resolved, this helper raises an exception and
    # lets the caller fall back to a regular message-based dashboard.
    try:
        user_id = None
        try:
            user_id = getattr(client, "me", None).id if getattr(client, "me", None) else None
        except Exception:
            user_id = None
        bot_username = None
        try:
            bot_username = Altruix.bot_manager.get_bot_username(user_id) if user_id is not None else None
        except Exception:
            bot_username = None
        if not bot_username or bot_username == "Unknown":
            raise Exception("Assistant bot username unavailable for inline builder")
        Altruix.log(f"YTcut inline query: bot={bot_username}, query={query}")
        results = await client.get_inline_bot_results(bot_username, query)
        Altruix.log(f"YTcut inline query returned {len(getattr(results, 'results', []))} results")
        return results
    except Exception as e:
        Altruix.log(
            f"YTcut wrapper get_inline_bot_results_for_client failed: {e}\n"
            f"bot_username={bot_username} query={query}\n"
            f"{traceback.format_exc()}"
        )
        raise


async def download_ytcut_thumbnail(url: str, dest: str) -> None:
    if not url:
        return
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                with open(dest, "wb") as f:
                    f.write(response.content)
        except Exception as e:
            Altruix.log(f"YTcut thumbnail download failed: {e}\n{traceback.format_exc()}")


async def run_ytcut_download(state: Dict[str, Any], temp_dir: str, client: Any) -> List[str]:
    sections: List[str] = []
    if state["mode"] == "keep":
        if not state["segments"]:
            raise ValueError("Tambahkan setidaknya satu potongan pada mode KEEP.")
        for seg in state["segments"]:
            sections.append(f"*{ytcut_time_to_yt_format(seg['start'])}-{ytcut_time_to_yt_format(seg['end'])}")
    else:
        keep_segments = build_keep_segments_from_remove(state["segments"], state["duration"])
        if not keep_segments:
            raise ValueError("Semua video terhapus. Tidak ada durasi tersisa untuk diproses.")
        for seg in keep_segments:
            sections.append(f"*{ytcut_time_to_yt_format(seg['start'])}-{ytcut_time_to_yt_format(seg['end'])}")

    if not sections:
        raise ValueError("Tidak ada segmen yang valid untuk didownload.")

    out_template = os.path.join(temp_dir, "part_%(section_number)03d.%(ext)s")
    cmd = [
        "yt-dlp",
        "--newline", # Ensure newline for line-by-line parsing
        "--no-warnings",
        "--no-call-home",
        "--no-playlist",
        "--retries", "3",
        "--output", out_template,
        "--merge-output-format", "mp4",
    ]
    for section in sections:
        cmd.extend(["--download-sections", section])
    
    cmd.append(state["url"])

    if state["extract"] == "audio":
        cmd.extend(["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"])
    else:
        quality = state["quality"]
        if quality and quality.isdigit():
            cmd.extend(["-f", f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]" if quality != "1080" else "bestvideo+bestaudio/best"])
        else:
            cmd.extend(["-f", "bestvideo+bestaudio/best"])

    Altruix.log(
        f"YTcut download starting: task={state.get('task_id')} url={state.get('url')} temp_dir={temp_dir} "
        f"mode={state.get('mode')} sections_count={len(sections)} sections={sections}",
        level=logging.INFO,
    )

    # Regex for yt-dlp percentage: [download]  10.5% of ...
    prog_regex = re.compile(r"\[download\]\s+(\d+\.\d+)%")
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    last_update = 0
    full_stdout: List[str] = []
    stderr_lines: List[str] = []
    # Watchdog for inactivity: if no stdout/stderr seen for this many seconds, kill process
    idle_timeout = 300  # 5 minutes
    last_output_time = time.time()
    killed_by_watchdog = False
    # Track current percentage parsed from yt-dlp output for heartbeat updates
    current_percentage: Optional[float] = None

    async def _watchdog():
        nonlocal killed_by_watchdog
        try:
            while True:
                await asyncio.sleep(5)
                # If process finished, stop watchdog
                if process.returncode is not None:
                    return
                now = time.time()
                if now - last_output_time > idle_timeout:
                    Altruix.log(
                        f"YTcut watchdog: killing process due to {int(now-last_output_time)}s inactivity: task={state.get('task_id')}",
                        level=logging.INFO,
                    )
                    try:
                        process.kill()
                    except Exception as kill_err:
                        Altruix.log(
                            f"YTcut watchdog process.kill failed: task={state.get('task_id')} error={kill_err}",
                            level=logging.INFO,
                        )
                    killed_by_watchdog = True
                    return
        except asyncio.CancelledError:
            return

    watchdog_task = asyncio.create_task(_watchdog())

    async def _download_heartbeat():
        # Periodically update dashboard to show activity even when yt-dlp emits no output
        start_time = time.time()
        try:
            while True:
                await asyncio.sleep(6)
                if process.returncode is not None:
                    return
                elapsed = int(time.time() - start_time)
                try:
                    await edit_ytcut_dashboard_status(
                        client,
                        state,
                        "Step 1/3: Mendownload segmen...",
                        f"Proses download sedang berjalan. Elapsed: {elapsed}s",
                        progress=current_percentage,
                    )
                except Exception:
                    # Non-fatal: keep heartbeat running
                    pass
        except asyncio.CancelledError:
            return

    heartbeat_task = asyncio.create_task(_download_heartbeat())

    async def _drain_stream(stream, collector):
        nonlocal last_update
        nonlocal last_output_time
        nonlocal current_percentage
        while True:
            line = await stream.readline()
            if not line:
                break
            line_str = line.decode(errors="replace").strip()
            if not line_str:
                continue
            collector.append(line_str)
            Altruix.log(
                f"YTcut stderr: {line_str}",
                level=logging.INFO,
            )
            last_output_time = time.time()
            match = prog_regex.search(line_str)
            if match:
                percentage = float(match.group(1))
                current_percentage = percentage
                now = time.time()
                if now - last_update >= 6:
                    last_update = now
                    asyncio.create_task(edit_ytcut_dashboard_status(
                        client, state,
                        "Step 1/3: Mendownload segmen...",
                        "Proses download sedang berjalan.",
                        progress=percentage
                    ))

    stderr_task = asyncio.create_task(_drain_stream(process.stderr, stderr_lines))
    try:
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode(errors="replace").strip()
            if not line_str:
                continue
            full_stdout.append(line_str)
            Altruix.log(
                f"YTcut stdout: {line_str}",
                level=logging.INFO,
            )
            last_output_time = time.time()
            match = prog_regex.search(line_str)
            if match:
                percentage = float(match.group(1))
                current_percentage = percentage
                now = time.time()
                if now - last_update >= 6:
                    last_update = now
                    asyncio.create_task(edit_ytcut_dashboard_status(
                        client, state,
                        "Step 1/3: Mendownload segmen...",
                        "Proses download sedang berjalan.",
                        progress=percentage
                    ))

        await stderr_task
        await process.wait()
        ret = process.returncode
        out = "\n".join(full_stdout)
        err = "\n".join(stderr_lines)
        Altruix.log(
            f"YTcut download finished: task={state.get('task_id')} ret={ret} stdout_lines={len(full_stdout)} stderr_lines={len(stderr_lines)} killed_by_watchdog={killed_by_watchdog}",
            level=logging.INFO,
        )
        try:
            files_after = sorted(os.listdir(temp_dir))
        except Exception:
            files_after = []
        Altruix.log(
            f"YTcut temp dir contents after download: task={state.get('task_id')} files={files_after}",
            level=logging.INFO,
        )
        # Cancel watchdog if still running
        try:
            watchdog_task.cancel()
        except Exception:
            pass
        try:
            heartbeat_task.cancel()
        except Exception:
            pass
    except Exception as e:
            try:
                process.kill()
            except Exception as kill_err:
                Altruix.log(
                f"YTcut process kill on exception failed: task={state.get('task_id')} error={kill_err}",
                level=logging.INFO,
            )
            raise e

    if ret != 0:
        if killed_by_watchdog:
            raise RuntimeError("YT-DLP Error: process killed due to inactivity (no output).")
        raise RuntimeError(f"YT-DLP Error:\n{err or out or 'Unknown error'}")

    # Explicitly find downloaded parts in correct numerical order
    downloaded_files: List[str] = []
    # yt-dlp section_number starts at 1
    Altruix.log(
        f"YTcut expected sections: {len(sections)} sections_list={sections}",
        level=logging.INFO,
    )
    for i in range(1, len(sections) + 1):
        # We search for files matching part_00i.* (could be .mp4, .mkv, .webm before merging)
        # But we requested --merge-output-format mp4, so it should be .mp4
        pattern = f"part_{i:03d}."
        found = False
        for filename in sorted(os.listdir(temp_dir)):
            if filename.startswith(pattern):
                downloaded_files.append(os.path.abspath(os.path.join(temp_dir, filename)))
                found = True
                break
    
    # BUG FIX: Fallback if partial match occurred (found < expected sections)
    # Note: yt-dlp with --merge-output-format mp4 may auto-merge all sections into ONE final file
    # (instead of creating per-section files). Fallback handles both cases:
    # 1. Multiple part_NNN files (sections kept separate)
    # 2. Single output file (yt-dlp auto-merged)
    if len(downloaded_files) < len(sections):
        Altruix.log(
            f"YTcut download partial match detected: task={state.get('task_id')} "
            f"expected={len(sections)} found={len(downloaded_files)} - using fallback"
        )
        downloaded_files.clear()
        # Fallback to any part_* files if the above precise matching fails
        for filename in sorted(os.listdir(temp_dir)):
            if filename.startswith("part_"):
                path = os.path.abspath(os.path.join(temp_dir, filename))
                downloaded_files.append(path)
        Altruix.log(
            f"YTcut fallback files used: task={state.get('task_id')} fallback_files={downloaded_files}",
            level=logging.INFO,
        )

        # Additional heuristic: parse yt-dlp stdout for 'Destination:' or merge messages
        try:
            dest_re = re.compile(r"Destination:\s*(.+)$")
            merge_re = re.compile(r"Merging formats into\s*'(.+)'")
            for line in full_stdout:
                m = dest_re.search(line)
                if m:
                    fname = m.group(1).strip()
                    if os.path.exists(os.path.join(temp_dir, fname)):
                        ab = os.path.abspath(os.path.join(temp_dir, fname))
                        if ab not in downloaded_files:
                            downloaded_files.append(ab)
                m2 = merge_re.search(line)
                if m2:
                    fname = m2.group(1).strip()
                    if os.path.exists(os.path.join(temp_dir, fname)):
                        ab = os.path.abspath(os.path.join(temp_dir, fname))
                        if ab not in downloaded_files:
                            downloaded_files.append(ab)
        except Exception as e:
            Altruix.log(f"YTcut download fallback parsing failed: {e}\n{traceback.format_exc()}")
            pass
    
    if not downloaded_files:
        raise RuntimeError("Tidak ada segmen yang didownload oleh yt-dlp.")

    # Special case: if fallback found only 1 file (and we wanted multiple sections),
    # yt-dlp likely auto-merged them into 1 output. Use it directly without re-concat.
    if len(downloaded_files) == 1 and len(sections) > 1:
        Altruix.log(
            f"YTcut download auto-merge detected: task={state.get('task_id')} "
            f"expected={len(sections)} sections, got 1 merged file. Using directly."
        )
        # Mark state so process_ytcut_task knows to skip ffmpeg concat
        state["skip_ffmpeg_concat"] = True
        await sync_ytcut_task(state.get("task_id"))
        return downloaded_files
    
    if len(downloaded_files) != len(sections):
        Altruix.log(
            f"YTcut download file count mismatch: task={state.get('task_id')} "
            f"expected={len(sections)} found={len(downloaded_files)} files={downloaded_files}"
        )
        raise RuntimeError(
            f"Jumlah file segmen yang ditemukan tidak sesuai: dibutuhkan {len(sections)} file tetapi hanya ditemukan {len(downloaded_files)}. "
            "Periksa log dan coba lagi."
        )
    
    Altruix.log(
        f"YTcut download completed: task={state.get('task_id')} "
        f"sections={len(sections)} files_found={len(downloaded_files)}"
    )
    Altruix.log(f"YTcut final downloaded files list: task={state.get('task_id')} {downloaded_files}")
    return downloaded_files


async def run_ytcut_ffmpeg_concat(parts: List[str], output_path: str, extract: str, client: Any, state: Dict[str, Any], thumb_path: Optional[str] = None) -> str:
    concat_file = os.path.splitext(output_path)[0] + "_list.txt"
    concat_dir = os.path.dirname(concat_file)
    with open(concat_file, "w", encoding="utf-8") as handle:
        for part in parts:
            # Use absolute paths so FFmpeg resolves files correctly on Windows
            abs_part = os.path.abspath(part)
            esc = abs_part.replace("'", "'\\'\\'")
            handle.write(f"file '{esc}'\n")

    # Start a heartbeat task for FFmpeg
    stop_heartbeat = asyncio.Event()
    async def heartbeat():
        start_time = time.time()
        while not stop_heartbeat.is_set():
            await asyncio.sleep(6)
            if stop_heartbeat.is_set(): break
            elapsed = int(time.time() - start_time)
            asyncio.create_task(edit_ytcut_dashboard_status(
                client, state, 
                "Step 2/3: Menggabungkan segmen...", 
                f"Sedang memproses FFmpeg concat ({elapsed}s)..."
            ))
    
    hb_task = asyncio.create_task(heartbeat())

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_path,
    ]
    
    try:
        ret, out, err = await run_subprocess(cmd)
        if ret != 0:
            if extract == "video":
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_file,
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-preset", "fast",
                    output_path,
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_file,
                    "-c:a", "libmp3lame",
                    "-q:a", "2",
                    output_path,
                ]
            ret, out, err = await run_subprocess(cmd)
            if ret != 0:
                raise RuntimeError(f"FFmpeg concat error:\n{err or out or 'Unknown error'}")
    except Exception as ff_err:
        tb = traceback.format_exc()
        Altruix.log(
            f"YTcut ffmpeg concat exception: task_id={state.get('task_id')} error={ff_err}\n{tb}",
            level=logging.INFO,
        )
        try:
            out_snip = (out[:1000] if isinstance(out, str) else str(out))
            err_snip = (err[:1000] if isinstance(err, str) else str(err))
            Altruix.log(
                f"YTcut ffmpeg concat outputs: out={out_snip} err={err_snip}",
                level=logging.INFO,
            )
        except Exception:
            pass
        raise
    finally:
        stop_heartbeat.set()
        hb_task.cancel()

    if thumb_path and os.path.exists(thumb_path):
        embed_path = os.path.splitext(output_path)[0] + ("_thumb.mp4" if extract == "video" else "_thumb.mp3")
        if extract == "video":
            embed_cmd = [
                "ffmpeg",
                "-y",
                "-i", output_path,
                "-i", thumb_path,
                "-map", "0",
                "-map", "1",
                "-c:v", "copy",
                "-c:a", "aac",
                "-disposition:1", "attached_pic",
                embed_path,
            ]
        else:
            embed_cmd = [
                "ffmpeg",
                "-y",
                "-i", output_path,
                "-i", thumb_path,
                "-map", "0:0",
                "-map", "1:0",
                "-c", "copy",
                "-id3v2_version", "3",
                embed_path,
            ]
        ret, out, err = await run_subprocess(embed_cmd)
        if ret == 0:
            os.replace(embed_path, output_path)
        else:
            Altruix.log(
                f"YTcut thumbnail embed failed: {err or out}",
                level=logging.INFO,
            )

    if os.path.exists(output_path):
        Altruix.log(
            f"YTcut ffmpeg concat completed: task_id={state.get('task_id')} output_path={output_path} "
            f"size={os.path.getsize(output_path)}",
            level=logging.INFO,
        )
    else:
        Altruix.log(f"YTcut ffmpeg concat completed but output missing: task_id={state.get('task_id')} output_path={output_path}")

    return output_path


async def cleanup_ytcut_temp(temp_dir: str) -> None:
    try:
        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
    except Exception as e:
        Altruix.log(f"YTcut cleanup failed: {e}\n{traceback.format_exc()}")


async def merge_ytcut_segments(state: Dict[str, Any], client: Any) -> str:
    """
    Merge all downloaded segments into a single video file without re-encoding.
    Used when user chooses to merge all segments instead of individual processing.
    
    Args:
        state: YTcut task state dictionary
        client: Pyrogram client for status updates
        
    Returns:
        Path to merged output file
        
    Raises:
        ValueError: If segments or task configuration is invalid
        RuntimeError: If FFmpeg merge fails
    """
    task_id = state.get("task_id")
    
    try:
        Altruix.log(
            f"YTcut merge_ytcut_segments entry: task_id={task_id} user_id={state.get('user_id')} "
            f"chat_id={state.get('chat_id')} segments_count={len(state.get('segments', []))} "
            f"extract={state.get('extract')}"
        )
        
        # Validate segments
        segments = state.get("segments", [])
        if not segments:
            raise ValueError("Tidak ada segmen untuk digabungkan.")
        
        if len(segments) < 2:
            raise ValueError("Minimal 2 segmen diperlukan untuk merge.")
        
        # Get temp directory or create new one
        temp_dir = os.path.join(YTCUT_TEMP_DIR, task_id, "merge")
        os.makedirs(temp_dir, exist_ok=True)
        
        ext = "mp4" if state["extract"] == "video" else "mp3"
        merge_output = os.path.join(temp_dir, f"ytcut_merged_{task_id}.{ext}")
        
        # Create concat list file
        concat_file = os.path.splitext(merge_output)[0] + "_list.txt"
        task_tmp_dir = os.path.join(YTCUT_TEMP_DIR, task_id)
        
        # Debug: list available files
        if not os.path.exists(task_tmp_dir):
            raise ValueError(
                "File segmen belum ada. Jalankan 'MULAI PROSES' terlebih dahulu untuk membuat file segmen, "
                "kemudian Anda bisa merge hasilnya."
            )
        
        available_files = []
        try:
            available_files = sorted(os.listdir(task_tmp_dir))
        except Exception as list_err:
            raise RuntimeError(f"Gagal membaca direktori segmen: {list_err}")
        
        # Filter out merge-specific files and look for part_* files
        part_files = [f for f in available_files if f.startswith("part_")]
        
        if not part_files:
            raise ValueError(
                "File segmen tidak ditemukan. Jalankan 'MULAI PROSES' terlebih dahulu untuk membuat file segmen "
                f"({task_tmp_dir}), kemudian Anda bisa merge hasilnya."
            )
        
        Altruix.log(
            f"YTcut merge available files: task_id={task_id} dir={task_tmp_dir} "
            f"part_files={part_files} total_files={len(available_files)}"
        )
        
        with open(concat_file, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, start=1):
                # Each segment file is expected to be part_00i.*
                expected_prefix = f"part_{i:03d}"
                seg_file = os.path.join(task_tmp_dir, f"{expected_prefix}.mp4")
                
                if not os.path.exists(seg_file):
                    # Try to find any matching part file regardless of extension
                    found = False
                    for filename in available_files:
                        if filename.startswith(expected_prefix):
                            seg_file = os.path.join(task_tmp_dir, filename)
                            found = True
                            break
                    
                    if not found:
                        raise RuntimeError(
                            f"Segmen file #{i} tidak ditemukan (cari: {expected_prefix}*). "
                            f"File yang tersedia: {part_files}. "
                            f"Pastikan sudah menjalankan 'MULAI PROSES' sebelum merge."
                        )
                
                abs_path = os.path.abspath(seg_file)
                esc_path = abs_path.replace("'", "'\\'\\'")
                f.write(f"file '{esc_path}'\n")
        
        Altruix.log(
            f"YTcut merge concat list created: task_id={task_id} concat_file={concat_file} "
            f"segments={len(segments)}"
        )
        
        # Prepare FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            merge_output,
        ]
        
        # Add status update
        await edit_ytcut_dashboard_status(
            client, state,
            "Merge: Menggabungkan segmen...",
            "Sedang concat semua file segmen dengan FFmpeg."
        )
        
        Altruix.log(
            f"YTcut merge ffmpeg starting: task_id={task_id} cmd={' '.join(cmd)}",
            level=logging.INFO,
        )
        
        # Run FFmpeg
        ret, out, err = await run_subprocess(cmd)
        
        if ret != 0:
            error_msg = f"FFmpeg merge error: {err or out}"
            Altruix.log(
                f"YTcut merge ffmpeg failed: task_id={task_id} ret={ret} error={error_msg}",
                level=logging.INFO,
            )
            raise RuntimeError(error_msg)
        
        if not os.path.exists(merge_output):
            raise RuntimeError(f"Output merge file tidak ditemukan: {merge_output}")
        
        Altruix.log(
            f"YTcut merge ffmpeg completed: task_id={task_id} output_file={merge_output} "
            f"size_bytes={os.path.getsize(merge_output)}",
            level=logging.INFO,
        )
        
        # Update state with new merged file
        state["merged_file"] = merge_output
        state["is_merged"] = True
        state["merge_timestamp"] = time.time()
        
        # Save state to database
        try:
            await sync_ytcut_task(task_id)
            Altruix.log(
                f"YTcut merge state synced: task_id={task_id}",
                level=logging.INFO,
            )
        except Exception as sync_err:
            Altruix.log(
                f"YTcut merge state sync failed (non-critical): task_id={task_id} error={sync_err}",
                level=logging.INFO,
            )
        
        Altruix.log(
            f"YTcut merge_ytcut_segments exit: task_id={task_id} merge_output={merge_output} "
            f"success=true",
            level=logging.INFO,
        )
        
        return merge_output
        
    except Exception as e:
        tb_text = traceback.format_exc()
        Altruix.log(
            f"YTcut merge_ytcut_segments exception: task_id={task_id} user_id={state.get('user_id')} "
            f"chat_id={state.get('chat_id')} error={e}\n{tb_text}"
        )
        raise


async def update_ytcut_dashboard_message(client: Any, state: Dict[str, Any]) -> None:
    if not state.get("dashboard_message_id") and not state.get("inline_message_id"):
        return
    
    # Avoid flooding if called too rapidly
    now = time.time()
    if state.get("_last_dashboard_update", 0) > now - 0.3:
        return
    state["_last_dashboard_update"] = now

    text = build_ytcut_dashboard_text(state)
    kb = build_ytcut_dashboard_keyboard(state)
    inline_id = state.get("inline_message_id")

    async def _safe_edit(method, **kwargs):
        from pyrogram import errors
        try:
            return await method(**kwargs)
        except errors.FloodWait as e:
            if e.value <= 3:
                await asyncio.sleep(e.value + 0.1)
                try: return await method(**kwargs)
                except: pass
            return None
        except Exception:
            return None

    try:
        if inline_id:
            if hasattr(client, "edit_inline_caption"):
                res = await _safe_edit(client.edit_inline_caption, inline_message_id=inline_id, caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            else:
                try:
                    res = await client.edit_message_caption(None, None, text, inline_id, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
                except:
                    res = await _safe_edit(client.edit_message_caption, inline_message_id=inline_id, caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
        else:
            res = await _safe_edit(client.edit_message_caption, chat_id=state["chat_id"], message_id=state["dashboard_message_id"], caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
        
        if res: return
    except Exception:
        pass

    try:
        if inline_id:
            if hasattr(client, "edit_inline_text"):
                res = await _safe_edit(client.edit_inline_text, inline_message_id=inline_id, text=text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            else:
                try:
                    res = await client.edit_message_text(None, None, text, inline_id, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
                except:
                    res = await _safe_edit(client.edit_message_text, inline_message_id=inline_id, text=text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
        else:
            res = await _safe_edit(client.edit_message_text, chat_id=state["chat_id"], message_id=state["dashboard_message_id"], text=text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
    except Exception as e:
        Altruix.log(f"YTcut dashboard update failed: {e}\n{traceback.format_exc()}")


async def edit_ytcut_dashboard_status(client: Any, state: Dict[str, Any], title: str, details: str, progress: Optional[float] = None) -> None:
    if not state.get("dashboard_message_id") and not state.get("inline_message_id"):
        return
    
    prog_text = ""
    if progress is not None:
        from Main.internals.ytdl_core import get_progress_bar
        bar = get_progress_bar(progress)
        prog_text = f"\n<b>📊 Progress:</b> {bar} <code>{progress:.1f}%</code>"

    status_text = (
        f"⏳ <b>Sedang Memproses...</b>\n"
        f"<b>• {title}</b>\n"
        f"<b>• {details}</b>{prog_text}"
    )
    inline_id = state.get("inline_message_id")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⌛️ Mohon tunggu", callback_data="ytcut_busy")]])

    async def _safe_edit(method, **kwargs):
        from pyrogram import errors
        try:
            return await method(**kwargs)
        except errors.FloodWait as e:
            if e.value <= 3:
                await asyncio.sleep(e.value + 0.1)
                try: return await method(**kwargs)
                except: pass
            return None
        except Exception:
            return None

    try:
        if inline_id:
            if hasattr(client, "edit_inline_caption"):
                res = await _safe_edit(client.edit_inline_caption, inline_message_id=inline_id, caption=status_text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            else:
                try:
                    res = await client.edit_message_caption(None, None, status_text, inline_id, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
                except:
                    res = await _safe_edit(client.edit_message_caption, inline_message_id=inline_id, caption=status_text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
        else:
            res = await _safe_edit(client.edit_message_caption, chat_id=state["chat_id"], message_id=state["dashboard_message_id"], caption=status_text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
        
        if res: return
    except Exception:
        pass

    try:
        if inline_id:
            if hasattr(client, "edit_inline_text"):
                res = await _safe_edit(client.edit_inline_text, inline_message_id=inline_id, text=status_text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            else:
                try:
                    res = await client.edit_message_text(None, None, status_text, inline_id, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
                except:
                    res = await _safe_edit(client.edit_message_text, inline_message_id=inline_id, text=status_text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
        else:
            res = await _safe_edit(client.edit_message_text, chat_id=state["chat_id"], message_id=state["dashboard_message_id"], text=status_text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
    except Exception as e:
        Altruix.log(f"YTcut dashboard status update failed: {e}\n{traceback.format_exc()}")


async def enqueue_ytcut_run(task_id: str, client: Any) -> None:
    ensure_ytcut_state_registry()
    state = Altruix.YTCUT_STATE.get(task_id)
    if not state:
        # Try to load state from persistent DB if in-memory state is missing
        state = await get_ytcut_task_state(task_id)
        if state:
            Altruix.log(
            f"YTcut enqueue_ytcut_run recovered state from DB: task_id={task_id}",
            level=logging.INFO,
        )
    if not state:
        Altruix.log(
            f"YTcut enqueue_ytcut_run missing state: task_id={task_id}",
            level=logging.INFO,
        )
        return
    if state.get("processing"):
        Altruix.log(
            f"YTcut enqueue_ytcut_run skipped: already processing task_id={task_id}",
            level=logging.INFO,
        )
        return
    
    # Add entry logging after state retrieval
    Altruix.log(
        f"YTcut enqueue_ytcut_run entry: task_id={task_id} user_id={state.get('user_id')} "
        f"chat_id={state.get('chat_id')} lock_locked={Altruix.YTCUT_LOCK.locked()} "
        f"queue_length={len(Altruix.YTCUT_QUEUE)}",
        level=logging.INFO,
    )
    
    state["processing"] = True
    asyncio.create_task(sync_ytcut_task(task_id))
    position = 0
    if Altruix.YTCUT_LOCK.locked():
        Altruix.YTCUT_QUEUE.append(task_id)
        position = len(Altruix.YTCUT_QUEUE)
    if position:
        await client.send_message(
            chat_id=state["chat_id"],
            text=f"⏳ Server sedang sibuk. Posisi antrean Anda: {position}",
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=state.get("reply_to"),
        )
    
    # Add lock wait logging before lock acquisition
    if task_id in Altruix.YTCUT_QUEUE:
        Altruix.log(
            f"YTcut waiting for lock: task_id={task_id} queue_position={Altruix.YTCUT_QUEUE.index(task_id) + 1}",
            level=logging.INFO,
        )
        await Altruix.YTCUT_LOCK.acquire()
        if task_id in Altruix.YTCUT_QUEUE:
            Altruix.YTCUT_QUEUE.remove(task_id)
    else:
        await Altruix.YTCUT_LOCK.acquire()
    
    # Add lock acquired logging
    Altruix.log(
        f"YTcut lock acquired: task_id={task_id} user_id={state.get('user_id')} chat_id={state.get('chat_id')}",
        level=logging.INFO,
    )
    
    try:
        await process_ytcut_task(state, client)
    except Exception as e:
        Altruix.log(
            f"YTcut enqueue_ytcut_run exception: task_id={task_id} user_id={state.get('user_id')} "
            f"chat_id={state.get('chat_id')} error={e}\n{traceback.format_exc()}"
        )
        raise
    finally:
        # Add exit logging before state["processing"] = False
        Altruix.log(
            f"YTcut enqueue_ytcut_run exit: task_id={task_id} processing={state.get('processing')} "
            f"lock_locked={Altruix.YTCUT_LOCK.locked()}",
            level=logging.INFO,
        )
        state["processing"] = False
        if Altruix.YTCUT_LOCK.locked():
            Altruix.YTCUT_LOCK.release()


async def process_ytcut_task(state: Dict[str, Any], client: Any) -> None:
    task_id = state.get("task_id")
    
    # Add entry logging after task_id extraction
    Altruix.log(
        f"YTcut process_ytcut_task entry: task_id={task_id} user_id={state.get('user_id')} "
        f"chat_id={state.get('chat_id')} url={state.get('url')} mode={state.get('mode')} "
        f"extract={state.get('extract')} segments_count={len(state.get('segments', []))}",
        level=logging.INFO,
    )
    
    # Register with Universal Task Manager
    try:
        from Main.plugins.userbot.xtaskmanager import register_task
        register_task(
            task_id, asyncio.current_task(), "YT Multi-Cut", "xytcut_tools",
            state.get("user_id"), f"✂️ {state.get('title', 'Unknown')[:30]}..."
        )
    except Exception:
        pass

    temp_dir = os.path.join(YTCUT_TEMP_DIR, task_id)
    os.makedirs(temp_dir, exist_ok=True)
    thumb_path = os.path.join(temp_dir, "thumb.jpg")
    current_stage = "Initializing"
    try:
        current_stage = "Step 1/3: Mendownload segmen..."
        state["ytcut_stage"] = current_stage
        # Add stage transition logging
        Altruix.log(
            f"YTcut stage transition: task_id={task_id} user_id={state.get('user_id')} "
            f"chat_id={state.get('chat_id')} stage='{current_stage}'",
            level=logging.INFO,
        )
        await edit_ytcut_dashboard_status(client, state, current_stage, "Tunggu hingga yt-dlp selesai.")
        
        # Wrap download_ytcut_thumbnail call with try-except
        try:
            await download_ytcut_thumbnail(state.get("thumbnail", ""), thumb_path)
            Altruix.log(f"YTcut thumbnail downloaded: task_id={task_id} thumb_path={thumb_path}")
        except Exception as thumb_err:
            Altruix.log(
                f"YTcut thumbnail download failed (non-critical): task_id={task_id} "
                f"error={thumb_err}\n{traceback.format_exc()}"
            )
        
        try:
            downloaded_parts = await run_ytcut_download(state, temp_dir, client)
            Altruix.log(
                f"YTcut download completed: task_id={task_id} parts_count={len(downloaded_parts)} "
                f"parts={downloaded_parts}"
            )
        except Exception as dl_err:
            Altruix.log(
                f"YTcut download failed: task_id={task_id} user_id={state.get('user_id')} "
                f"chat_id={state.get('chat_id')} stage='Step 1/3: Mendownload segmen...' "
                f"error={dl_err}\n{traceback.format_exc()}"
            )
            raise

        current_stage = "Step 2/3: Menggabungkan segmen..."
        state["ytcut_stage"] = current_stage
        # Add stage transition logging
        Altruix.log(
            f"YTcut stage transition: task_id={task_id} user_id={state.get('user_id')} "
            f"chat_id={state.get('chat_id')} stage='{current_stage}'",
            level=logging.INFO,
        )
        await edit_ytcut_dashboard_status(client, state, current_stage, "Proses concat dengan FFmpeg.")
        ext = "mp4" if state["extract"] == "video" else "mp3"
        output_file = os.path.join(temp_dir, f"ytcut_{state['task_id']}.{ext}")
        
        # Check if yt-dlp already auto-merged (skip_ffmpeg_concat flag)
        if state.get("skip_ffmpeg_concat"):
            # yt-dlp auto-merged all sections into 1 file; use it directly
            if downloaded_parts:
                output_file = downloaded_parts[0]
                Altruix.log(f"YTcut skipping concat: yt-dlp auto-merged into {output_file}")
        else:
            try:
                await run_ytcut_ffmpeg_concat(downloaded_parts, output_file, state["extract"], client, state, thumb_path if os.path.exists(thumb_path) else None)
                if os.path.exists(output_file):
                    Altruix.log(
                        f"YTcut concat completed: task_id={task_id} output_file={output_file} "
                        f"size={os.path.getsize(output_file)}"
                    )
                else:
                    Altruix.log(
                        f"YTcut concat completed: task_id={task_id} output_file={output_file} does not exist after concat"
                    )
            except Exception as concat_err:
                Altruix.log(
                    f"YTcut concat failed: task_id={task_id} user_id={state.get('user_id')} "
                    f"chat_id={state.get('chat_id')} stage='Step 2/3: Menggabungkan segmen...' "
                    f"error={concat_err}\n{traceback.format_exc()}"
                )
                raise

        current_stage = "Step 3/3: Mengirim hasil..."
        state["ytcut_stage"] = current_stage
        # Add stage transition logging
        Altruix.log(
            f"YTcut stage transition: task_id={task_id} user_id={state.get('user_id')} "
            f"chat_id={state.get('chat_id')} stage='{current_stage}'",
            level=logging.INFO,
        )
        await edit_ytcut_dashboard_status(client, state, current_stage, "Finishing upload ke Telegram.")
        Altruix.log(
            f"YTcut stage 3 send starting: task_id={task_id} chat_id={state.get('chat_id')} user_id={state.get('user_id')} output_file={output_file}",
            level=logging.INFO,
        )

        caption = (
            f"🎬 <b>YT Multi-Cut Selesai</b>\n"
            f"<b>• Judul:</b> {html.escape(state['title'])}\n"
            f"<b>• Mode:</b> <code>{state['mode'].upper()}</code>\n"
            f"<b>• Ekstrak:</b> <code>{'VIDEO' if state['extract']=='video' else 'AUDIO ONLY'}</code>\n"
            f"<b>• Segmen:</b> {len(state['segments']) if state['segments'] else '0'}\n"
            f"<b>• Source:</b> <code>{html.escape(state['url'])}</code>\n"
        )
        try:
            if state["extract"] == "video":
                await client.send_video(
                    chat_id=state["chat_id"],
                    video=output_file,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    supports_streaming=True,
                    thumb=thumb_path if os.path.exists(thumb_path) else None,
                    reply_to_message_id=state.get("reply_to"),
                )
            else:
                await client.send_audio(
                    chat_id=state["chat_id"],
                    audio=output_file,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    thumb=thumb_path if os.path.exists(thumb_path) else None,
                    reply_to_message_id=state.get("reply_to"),
                )
        except Exception as send_exc:
            if isinstance(send_exc, errors.PeerIdInvalid) and state.get("user_id"):
                fallback_chat = state["user_id"]
                Altruix.log(
                    f"YTcut stage 3 peer invalid: task_id={task_id} chat_id={state.get('chat_id')} user_id={state.get('user_id')} "
                    f"fallback_user_id={fallback_chat} exception={send_exc}"
                )
                if state["extract"] == "video":
                    await client.send_video(
                        chat_id=fallback_chat,
                        video=output_file,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        supports_streaming=True,
                        thumb=thumb_path if os.path.exists(thumb_path) else None,
                    )
                else:
                    await client.send_audio(
                        chat_id=fallback_chat,
                        audio=output_file,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        thumb=thumb_path if os.path.exists(thumb_path) else None,
                    )
            else:
                raise
    except Exception as e:
        tb_text = traceback.format_exc()
        Altruix.log(f"YTcut process failed: {e}\n{tb_text}")
        err_text = str(e).replace('`', "'")
        try:
            await notify_ytcut_error_to_group_log(err_text, state, tb_text, current_stage)
        except Exception:
            pass
        try:
            # Inform user on dashboard about failure
            await edit_ytcut_dashboard_status(client, state, "❌ Gagal memproses", f"{html.escape(err_text[:100])}...")
        except:
            pass
        try:
            await client.send_message(
                chat_id=state["chat_id"],
                text=f"❌ <b>Gagal memproses YTcut:</b> <code>{html.escape(err_text)}</code>",
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=state.get("reply_to"),
            )
        except errors.PeerIdInvalid as peer_exc:
            fallback_chat = get_ytcut_fallback_chat(state)
            Altruix.log(
                f"YTcut error notice peer invalid: task_id={task_id} chat_id={state.get('chat_id')} user_id={state.get('user_id')} "
                f"fallback_chat={fallback_chat} exception={peer_exc}"
            )
            if fallback_chat and fallback_chat != state.get("chat_id"):
                Altruix.log(f"YTcut error notice peer invalid for chat_id={state.get('chat_id')}; sending failure notice to fallback user_id={fallback_chat}")
                await client.send_message(
                    chat_id=fallback_chat,
                    text=f"❌ <b>Gagal memproses YTcut:</b> <code>{html.escape(err_text)}</code>",
                    parse_mode=enums.ParseMode.HTML,
                )
            else:
                raise
    finally:
        # Add exit logging before cleanup
        Altruix.log(
            f"YTcut process_ytcut_task exit: task_id={task_id} user_id={state.get('user_id')} "
            f"chat_id={state.get('chat_id')} final_stage='{current_stage}'"
        )
        
        # Update dashboard back to menu state instead of deleting it
        # This allows user to "revise" or "repeat" the process
        try:
            await update_ytcut_dashboard_message(client, state)
        except Exception as ex:
            Altruix.log(f"YTcut failed to restore dashboard: {ex}")

        # Unregister from xtaskmanager
        try:
            from Main.plugins.userbot.xtaskmanager import unregister_task
            unregister_task(state.get("task_id"))
        except:
            pass

        await cleanup_ytcut_temp(temp_dir)
        # We NO LONGER delete the task from database/memory here
        # so it stays available for revisions.
        # await delete_ytcut_task(state.get("task_id"))
        # Altruix.YTCUT_STATE.pop(state["task_id"], None)
