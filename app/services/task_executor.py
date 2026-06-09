import asyncio
import json
import webbrowser
import re
import math
import threading
from typing import List
from rich.console import Console
from app.services.realtime_service import realtime_service
from app.services.memory_service import memory_service
import os
import sys
import subprocess
import datetime
import shutil
from urllib.parse import quote_plus
from pathlib import Path

import time

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import ctypes
except ImportError:
    ctypes = None

try:
    import comtypes
except ImportError:
    comtypes = None

try:
    import pycaw
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
except ImportError:
    pycaw = None
    AudioUtilities = None
    IAudioEndpointVolume = None

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

console = Console()

class TaskExecutor:
    async def execute_plan(self, plan: List[str], event_queue: asyncio.Queue = None):
        if hasattr(plan, "execution_plan"):
            plan = plan.execution_plan
        elif isinstance(plan, dict) and "execution_plan" in plan:
            plan = plan["execution_plan"]

        # Pre-translate steps to primitives to check for redundancy
        primitives = []
        translated_steps = []
        for step in plan:
            prim = await self._translate_step(step)
            primitives.append(prim)
            translated_steps.append(step)

        # Deduplicate redundant play_youtube primitives
        filtered_indices = []
        last_youtube_param = None
        for i, prim in enumerate(primitives):
            if prim and prim.get("action") == "play_youtube":
                param = prim.get("param", "").lower()
                if last_youtube_param is not None:
                    is_redundant = False
                    if param in ("", "found", "it", "video", "song", "music", "the video", "the song", "the music"):
                        is_redundant = True
                    words_last = set(re.findall(r'\w+', last_youtube_param))
                    words_curr = set(re.findall(r'\w+', param))
                    filler_words = {"the", "of", "and", "a", "an", "on", "in", "to", "for", "with", "video", "song", "music", "youtube"}
                    meaningful_last = words_last - filler_words
                    meaningful_curr = words_curr - filler_words
                    if meaningful_last and meaningful_curr:
                        if meaningful_last.intersection(meaningful_curr):
                            is_redundant = True
                    else:
                        is_redundant = True

                    if is_redundant:
                        continue
                last_youtube_param = param
            filtered_indices.append(i)

        for idx in filtered_indices:
            step = translated_steps[idx]
            primitive = primitives[idx]
            if not primitive:
                continue

            if event_queue:
                await event_queue.put({"type": "task_status", "step": step, "status": "running"})
            try:
                enc = console.encoding or 'utf-8'
                safe_step = step.encode(enc, errors='replace').decode(enc)
            except Exception:
                safe_step = step
            console.print(f"\n[cyan]Executing step:[/cyan] {safe_step}")
            await self._handle_primitive(primitive, event_queue)
            if event_queue:
                await event_queue.put({"type": "task_status", "step": step, "status": "completed"})

    def _activate_window(self, title: str):
        clean_title = title.replace(".exe", "").capitalize()
        for t in (title, clean_title):
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", 
                     f'(New-Object -ComObject WScript.Shell).AppActivate("{t}")'],
                    capture_output=True,
                    timeout=5
                )
            except Exception:
                pass
        time.sleep(0.5)

    def _parse_reminder(self, step: str):
        s = step.lower().strip()
        now = datetime.datetime.now()
        
        # 1. Check relative time: "in X minutes/hours/seconds"
        relative_match = re.search(r'\bin\s+(\d+)\s+(minute|hour|second|sec|min|hr)s?\b', s)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2)
            if 'min' in unit:
                delta = datetime.timedelta(minutes=amount)
            elif 'hour' in unit or 'hr' in unit:
                delta = datetime.timedelta(hours=amount)
            else:
                delta = datetime.timedelta(seconds=amount)
            
            target_dt = now + delta
            
            # Extract message
            msg = step
            msg = re.sub(r'\bin\s+(\d+)\s+(minute|hour|second|sec|min|hr)s?\b', '', msg, flags=re.IGNORECASE)
            msg = re.sub(r'^\s*(remind me to|remind me|set a reminder to|set a reminder)\s*', '', msg, flags=re.IGNORECASE).strip()
            if not msg:
                msg = "Reminder!"
                
            return target_dt, msg

        # 2. Check absolute time: e.g. "at 15:30" or "15:30"
        time_match = re.search(r'\b(\d{1,2}):(\d{2})\b', s)
        date_match = re.search(r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b', s)
        
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            
            if date_match:
                year = int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                target_dt = datetime.datetime(year, month, day, hour, minute)
            else:
                target_dt = datetime.datetime(now.year, now.month, now.day, hour, minute)
                if target_dt <= now:
                    target_dt += datetime.timedelta(days=1)
                    
            msg = step
            msg = re.sub(r'\b\d{1,2}:\d{2}\b', '', msg)
            msg = re.sub(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', '', msg)
            msg = re.sub(r'\b(?:at|on|for|to|me)\b', '', msg, flags=re.IGNORECASE)
            msg = re.sub(r'^\s*(remind to|remind|set a reminder|reminder)\s*', '', msg, flags=re.IGNORECASE).strip()
            if not msg:
                msg = "Reminder!"
                
            return target_dt, msg

        return None, None

    async def _translate_step(self, step: str) -> dict:
        """Rule-based step translator — no AI call needed for standard actions."""
        s = step.strip().lower()

        # --- Persistent Browser Actions ---
        if s.startswith("browser action:"):
            rest = step[len("browser action:"):].strip()
            parts = rest.split(None, 1)
            subcmd = parts[0].lower() if parts else ""
            if subcmd == "switch":
                target_m = re.search(r"target=['\"]([^'\"]+)['\"]", rest)
                target = target_m.group(1) if target_m else "chrome"
                return {"action": "browser_switch", "target": target}
            elif subcmd == "list_browsers":
                return {"action": "browser_list"}
            elif subcmd == "go_to":
                url_m = re.search(r"url=['\"]([^'\"]+)['\"]", rest)
                url = url_m.group(1) if url_m else ""
                return {"action": "browser_go_to", "url": url}
            elif subcmd == "search":
                query_m = re.search(r"query=['\"]([^'\"]+)['\"]", rest)
                engine_m = re.search(r"engine=['\"]([^'\"]+)['\"]", rest)
                query = query_m.group(1) if query_m else ""
                engine = engine_m.group(1) if engine_m else "google"
                return {"action": "browser_search", "query": query, "engine": engine}
            elif subcmd == "smart_click":
                desc_m = re.search(r"description=['\"]([^'\"]+)['\"]", rest)
                desc = desc_m.group(1) if desc_m else ""
                return {"action": "browser_smart_click", "description": desc}
            elif subcmd == "smart_type":
                desc_m = re.search(r"description=['\"]([^'\"]+)['\"]", rest)
                text_m = re.search(r"text=['\"]([^'\"]+)['\"]", rest)
                desc = desc_m.group(1) if desc_m else ""
                text = text_m.group(1) if text_m else ""
                return {"action": "browser_smart_type", "description": desc, "text": text}
            elif subcmd == "close_tab":
                return {"action": "browser_close_tab"}
            elif subcmd == "new_tab":
                return {"action": "browser_new_tab"}

        # --- Automated Messenger Routes ---
        if s.startswith("send message:"):
            rest = step[len("send message:"):].strip()
            platform_m = re.search(r"platform=['\"]([^'\"]+)['\"]", rest)
            receiver_m = re.search(r"receiver=['\"]([^'\"]+)['\"]", rest)
            text_m = re.search(r"text=['\"]([^'\"]+)['\"]", rest)
            platform = platform_m.group(1) if platform_m else ""
            receiver = receiver_m.group(1) if receiver_m else ""
            text = text_m.group(1) if text_m else ""
            return {"action": "send_message", "platform": platform, "receiver": receiver, "text": text}

        # --- Grid Layout Snapping ---
        if s.startswith("window action:"):
            rest = step[len("window action:"):].strip()
            if "snap_left" in rest:
                return {"action": "snap_left"}
            elif "snap_right" in rest:
                return {"action": "snap_right"}
        if "snap left" in s or "snap window left" in s:
            return {"action": "snap_left"}
        if "snap right" in s or "snap window right" in s:
            return {"action": "snap_right"}

        # --- Wallpaper & Desktop ---
        if s.startswith("system utility:"):
            rest = step[len("system utility:"):].strip()
            if "set_wallpaper_url" in rest:
                url_m = re.search(r"url=['\"]([^'\"]+)['\"]", rest)
                url = url_m.group(1) if url_m else ""
                return {"action": "set_wallpaper_url", "url": url}

        if s.startswith("desktop management:"):
            rest = step[len("desktop management:"):].strip()
            if "organize" in rest:
                mode_m = re.search(r"mode=['\"]([^'\"]+)['\"]", rest)
                mode = mode_m.group(1) if mode_m else "by_type"
                return {"action": "organize_desktop_mode", "mode": mode}

        # --- Memorize ---
        if s.startswith("memorize"):
            # Expected format: "Memorize key 'X' with value 'Y'"
            key_m = re.search(r"key\s+'?([\w_]+)'?", step, re.IGNORECASE)
            val_m = re.search(r"value\s+'?([^']+)'?", step, re.IGNORECASE)
            if key_m and val_m:
                return {"action": "memorize", "key": key_m.group(1), "value": val_m.group(1).strip()}

        # --- Reminders ---
        if "remind" in s or "reminder" in s:
            target_dt, msg = self._parse_reminder(step)
            if target_dt and msg:
                return {"action": "set_reminder", "date_time": target_dt, "message": msg}

        # --- Weather ---
        if "weather" in s:
            city = re.sub(
                r"\b(weather|in|of|for|report|check|show|get|today|tomorrow|forecast)\b",
                "", step, flags=re.IGNORECASE
            )
            city = re.sub(r'\s+', ' ', city).strip(" ,.-'\"")
            return {"action": "weather_report", "city": city or "Mumbai"}

        # --- Wallpaper & Desktop General ---
        if "wallpaper" in s:
            url_match = re.search(r'https?://[^\s]+', step)
            if url_match:
                return {"action": "set_wallpaper_url", "url": url_match.group(0)}
            
            path_match = re.search(r'(?:to|with|path)\s+[\'"]?([^\'"]+)[\'"]?', step, re.IGNORECASE)
            if path_match:
                return {"action": "set_wallpaper_path", "path": path_match.group(1).strip()}
            
            words = step.split()
            for word in words:
                if (":" in word or "/" in word or "\\" in word) and not word.startswith("http"):
                    return {"action": "set_wallpaper_path", "path": word.strip("'\"")}

        if "organize" in s and "desktop" in s:
            mode = "by_type"
            if "date" in s:
                mode = "by_date"
            return {"action": "organize_desktop_mode", "mode": mode}

        if "clean" in s and "desktop" in s:
            return {"action": "clean_desktop"}

        if "list" in s and "desktop" in s:
            return {"action": "list_desktop"}

        if "stats" in s and "desktop" in s:
            return {"action": "desktop_stats"}
        # --- Type Text / Smart Typing (from Mark-XL) ---
        type_in_app_match = re.match(r"^(?:type|write|enter)\s+['\"]?(.+?)['\"]?\s+(?:in|into|on)\s+(?:window\s+)?['\"]?(.+?)['\"]?$", step, re.IGNORECASE)
        if type_in_app_match:
            text_to_type = type_in_app_match.group(1).strip()
            app_target = type_in_app_match.group(2).strip()
            if text_to_type and app_target:
                return {"action": "type_in_app", "text": text_to_type, "app": app_target}

        type_match = re.match(r"^type\s+text:\s*['\"]?(.+?)['\"]?\s*$", step, re.IGNORECASE)
        if not type_match:
            type_match = re.match(r"^(?:type|write|enter)\s+['\"]?(.+?)['\"]?\s*$", step, re.IGNORECASE)
        if type_match:
            text_to_type = type_match.group(1).strip()
            if text_to_type:
                return {"action": "type_text", "text": text_to_type}

        # --- Focus Window (from Mark-XL PowerShell strategy) ---
        focus_match = re.match(r"^focus\s+window:\s*['\"]?(.+?)['\"]?\s*$", step, re.IGNORECASE)
        if not focus_match:
            focus_match = re.match(r"^(?:focus|activate|bring|switch\s+to)\s+(?:window\s+)?['\"]?(.+?)['\"]?(?:\s+(?:to\s+(?:the\s+)?(?:front|foreground))|\s+window)?\s*$", step, re.IGNORECASE)
        if focus_match:
            window_title = focus_match.group(1).strip()
            if window_title:
                return {"action": "focus_window", "title": window_title}

        # --- Coordinate Mouse Actions (from Mark-XL) ---
        # Drag: "Drag from coordinates: (X1, Y1) to (X2, Y2)"
        drag_match = re.match(r"^drag\s+(?:from\s+)?(?:coordinates:?\s*)?\(?\s*(\d+)\s*,\s*(\d+)\s*\)?\s*to\s*\(?\s*(\d+)\s*,\s*(\d+)\s*\)?\s*$", step, re.IGNORECASE)
        if drag_match:
            return {"action": "drag", "x1": int(drag_match.group(1)), "y1": int(drag_match.group(2)), "x2": int(drag_match.group(3)), "y2": int(drag_match.group(4))}

        # Click / Right click / Double click / Move at coordinates
        coord_match = re.match(r"^(click|right\s*click|double\s*click|move\s*(?:mouse)?(?:\s*to)?)\s+(?:at\s+)?(?:coordinates:?\s*)?\(?\s*(\d+)\s*,\s*(\d+)\s*\)?\s*$", step, re.IGNORECASE)
        if coord_match:
            action_word = coord_match.group(1).lower().strip()
            cx = int(coord_match.group(2))
            cy = int(coord_match.group(3))
            if "right" in action_word:
                return {"action": "right_click_xy", "x": cx, "y": cy}
            elif "double" in action_word:
                return {"action": "double_click_xy", "x": cx, "y": cy}
            elif "move" in action_word:
                return {"action": "move_to_xy", "x": cx, "y": cy}
            else:
                return {"action": "click_xy", "x": cx, "y": cy}

        # --- Volume ---
        if "volume" in s or "mute" in s or "unmute" in s:
            if "up" in s or "increase" in s:
                return {"action": "volume_up"}
            elif "down" in s or "decrease" in s:
                return {"action": "volume_down"}
            elif "unmute" in s:
                return {"action": "volume_unmute"}
            elif "mute" in s:
                return {"action": "volume_mute"}
            else:
                num_match = re.search(r'(\d+)', s)
                if num_match:
                    return {"action": "volume_set", "value": int(num_match.group(1))}

        # --- Brightness ---
        if "brightness" in s:
            if "up" in s or "increase" in s:
                return {"action": "brightness_up"}
            elif "down" in s or "decrease" in s:
                return {"action": "brightness_down"}
            else:
                num_match = re.search(r'(\d+)', s)
                if num_match:
                    return {"action": "brightness_set", "value": int(num_match.group(1))}

        # --- Keyboard & Input / Actions ---
        if "screenshot" in s or "screen capture" in s:
            return {"action": "take_screenshot"}
        if "lock screen" in s or "lock computer" in s or "lock pc" in s:
            return {"action": "lock_screen"}
        if "dark mode" in s or "light mode" in s or "toggle dark mode" in s:
            return {"action": "toggle_dark_mode"}
        if "toggle wifi" in s or "wifi" in s:
            return {"action": "toggle_wifi"}
        if "sleep display" in s or "turn off screen" in s:
            return {"action": "sleep_display"}
        if "restart computer" in s or "reboot" in s:
            return {"action": "restart_computer"}
        if "shutdown computer" in s or "turn off computer" in s:
            return {"action": "shutdown_computer"}

        # --- Window Actions ---
        if "close window" in s:
            return {"action": "close_window"}
        if "close app" in s or "close application" in s:
            return {"action": "close_app"}
        if "minimize window" in s or "minimize" in s:
            return {"action": "minimize_window"}
        if "maximize window" in s or "maximize" in s:
            return {"action": "maximize_window"}
        if "full screen" in s:
            return {"action": "full_screen"}
        if "show desktop" in s:
            return {"action": "show_desktop"}
        if "switch window" in s or "alt tab" in s:
            return {"action": "switch_window"}
        if "task manager" in s:
            return {"action": "open_task_manager"}
        if "open run" in s:
            return {"action": "open_run"}
        if "open settings" in s:
            return {"action": "open_settings"}
        if "file explorer" in s:
            return {"action": "open_file_explorer"}

        # --- Browser Navigation / Tabs ---
        if "new tab" in s:
            return {"action": "new_tab"}
        if "close tab" in s:
            return {"action": "close_tab"}
        if "next tab" in s:
            return {"action": "next_tab"}
        if "prev tab" in s or "previous tab" in s:
            return {"action": "prev_tab"}
        if "go back" in s:
            return {"action": "go_back"}
        if "go forward" in s:
            return {"action": "go_forward"}
        if "refresh page" in s or "reload page" in s:
            return {"action": "refresh_page"}
        if "scroll down" in s:
            return {"action": "scroll_down"}
        if "scroll up" in s:
            return {"action": "scroll_up"}
        if "zoom in" in s:
            return {"action": "zoom_in"}
        if "zoom out" in s:
            return {"action": "zoom_out"}
        if "zoom reset" in s:
            return {"action": "zoom_reset"}

        # --- Clipboard / Edit ---
        if "select all" in s:
            return {"action": "select_all"}
        if "copy" in s:
            return {"action": "copy"}
        if "paste" in s:
            return {"action": "paste"}
        if "cut" in s:
            return {"action": "cut"}
        if "undo" in s:
            return {"action": "undo"}
        if "redo" in s:
            return {"action": "redo"}
        if "save file" in s or "save" in s:
            return {"action": "save_file"}
        if "press enter" in s or "hit enter" in s:
            return {"action": "press_enter"}
        if "press escape" in s or "press esc" in s:
            return {"action": "press_escape"}

        # --- Play YouTube ---
        is_youtube_play = False
        if "youtube" in s:
            is_open_only = s in ("youtube", "open youtube", "go to youtube", "navigate to youtube", "launch youtube")
            if not is_open_only:
                is_youtube_play = True
        elif "play" in s:
            if any(media_word in s for media_word in ("video", "song", "music", "audio", "track", "playlist", "beat", "sound")):
                is_youtube_play = True

        if is_youtube_play:
            param = re.sub(
                r"\b(open|play|search\s+for|search|find|watch|show|on\s+youtube|youtube|and\s+search\s+for|and\s+play|and|video|song|music)\b",
                "", step, flags=re.IGNORECASE
            )
            param = re.sub(r'\s+', ' ', param).strip(" ,.-'\"")
            if param:
                return {"action": "play_youtube", "param": param}

        # --- Open URL / website ---
        url_match = re.search(r'https?://[^\s]+', step)
        if url_match:
            return {"action": "open_url", "param": url_match.group(0)}

        # Well-known site/app name → URL mapping
        KNOWN_SITES = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "google maps": "https://maps.google.com",
            "maps": "https://maps.google.com",
            "google drive": "https://drive.google.com",
            "drive": "https://drive.google.com",
            "github": "https://www.github.com",
            "spotify": "https://open.spotify.com",
            "netflix": "https://www.netflix.com",
            "reddit": "https://www.reddit.com",
            "twitter": "https://www.twitter.com",
            "x": "https://www.x.com",
            "instagram": "https://www.instagram.com",
            "facebook": "https://www.facebook.com",
            "whatsapp": "https://web.whatsapp.com",
            "linkedin": "https://www.linkedin.com",
            "amazon": "https://www.amazon.com",
            "wikipedia": "https://www.wikipedia.org",
            "chatgpt": "https://chat.openai.com",
            "openai": "https://www.openai.com",
        }

        open_keywords = ("open ", "go to ", "navigate to ", "launch ")
        if any(s.startswith(kw) for kw in open_keywords):
            target = re.sub(r'^(open|go to|navigate to|launch)\s+', '', step, flags=re.IGNORECASE).strip()
            target_lower = target.lower()

            # 1. Check known sites dictionary first (handles names without dots)
            if target_lower in KNOWN_SITES:
                return {"action": "open_url", "param": KNOWN_SITES[target_lower]}

            # 2. If it looks like a domain, build a URL
            if "." in target and " " not in target:
                url = target if target.startswith("http") else f"https://{target}"
                return {"action": "open_url", "param": url}

            # 3. Partial match: check if target_lower is contained in any known site key
            for site_name, site_url in KNOWN_SITES.items():
                if site_name in target_lower or target_lower in site_name:
                    return {"action": "open_url", "param": site_url}

            # 4. Fallback: it's not a known site/url, treat as a local application to open
            return {"action": "open_app", "app_name": target}

        # --- Research (default for info/search queries) ---
        query = re.sub(
            r'^(search for|search|look up|find|research|get|check|what is|tell me about)\s+',
            '', step, flags=re.IGNORECASE
        ).strip()
        return {"action": "research", "param": query or step}

    async def _handle_primitive(self, primitive: dict, event_queue: asyncio.Queue = None):
        action = primitive.get("action")
        param = primitive.get("param")
        
        if action == "memorize":
            param_key = primitive.get("key")
            param_value = primitive.get("value")
            await memory_service.update_memory(param_key, param_value)
            console.print(f"[bold green]Memory Updated:[/bold green] {param_key} -> {param_value}")
            if event_queue:
                await event_queue.put({"type": "token", "text": "Understood, Sir. I have updated my records."})
        elif action == "open_url":
            console.print(f"[green]Opening URL:[/green] {param}")
            webbrowser.open(param)
            if event_queue:
                site_name = re.sub(r'https?://(www\.)?', '', param).split('/')[0]
                await event_queue.put({"type": "token", "text": f"Opening {site_name} in your browser now, Sir."})
        elif action == "play_youtube":
            console.print(f"[magenta]Playing on YouTube:[/magenta] {param}")
            search_res = await realtime_service.search(f"site:youtube.com watch {param}")
            summary = search_res.get("summary", "")
            match = re.search(r'(https://www\.youtube\.com/watch\?v=[\w-]+)', summary)
            if match:
                target_video_url = match.group(1)
                console.print(f"[green]Direct video link found:[/green] {target_video_url}")
                webbrowser.open(target_video_url)
                if event_queue:
                    await event_queue.put({"type": "token", "text": f"Playing '{param}' on YouTube now, Sir."})
            else:
                fallback_url = f"https://www.youtube.com/results?search_query={param.replace(' ', '+')}"
                console.print(f"[yellow]No direct link found, falling back to search:[/yellow] {fallback_url}")
                webbrowser.open(fallback_url)
                if event_queue:
                    await event_queue.put({"type": "token", "text": f"Searching YouTube for '{param}', Sir."})

        elif action == "research":
            try:
                enc = console.encoding or 'utf-8'
                safe_param = param.encode(enc, errors='replace').decode(enc)
            except Exception:
                safe_param = param
            console.print(f"[magenta]Researching:[/magenta] {safe_param}")
            
            search_res = await realtime_service.search(param)
            summary = search_res.get("summary", "")
            results_list = search_res.get("results", [])
            
            try:
                enc = console.encoding or 'utf-8'
                safe_summary = summary.encode(enc, errors='replace').decode(enc)
            except Exception:
                safe_summary = "[Search results obtained but cannot be displayed in terminal due to encoding limitations]"
            console.print(f"[blue]Research Results for '{param}':[/blue]\n{safe_summary}")

            if event_queue:
                await event_queue.put({
                    "type": "search_results",
                    "query": param,
                    "answer": summary,
                    "results": results_list
                })

        # --- Volume Controls ---
        elif action == "volume_up":
            if pyautogui:
                for _ in range(5):
                    pyautogui.press("volumeup")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "I have increased the volume, Sir."})
            else:
                if event_queue:
                    await event_queue.put({"type": "token", "text": "pyautogui is not installed, Sir."})
        elif action == "volume_down":
            if pyautogui:
                for _ in range(5):
                    pyautogui.press("volumedown")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "I have decreased the volume, Sir."})
            else:
                if event_queue:
                    await event_queue.put({"type": "token", "text": "pyautogui is not installed, Sir."})
        elif action == "volume_mute":
            success = False
            if pycaw and comtypes:
                success = set_win_mute_com(True)
            if not success and pyautogui:
                pyautogui.press("volumemute")
                success = True
            if event_queue:
                if success:
                    await event_queue.put({"type": "token", "text": "Muting the volume, Sir."})
                else:
                    await event_queue.put({"type": "token", "text": "Failed to mute volume, Sir."})
        elif action == "volume_unmute":
            success = False
            if pycaw and comtypes:
                success = set_win_mute_com(False)
            if not success and pyautogui:
                pyautogui.press("volumemute")
                success = True
            if event_queue:
                if success:
                    await event_queue.put({"type": "token", "text": "Unmuting the volume, Sir."})
                else:
                    await event_queue.put({"type": "token", "text": "Failed to unmute volume, Sir."})
        elif action == "volume_set":
            val = primitive.get("value", 50)
            success = False
            if pycaw and comtypes:
                success = set_win_volume_com(val)
            if not success:
                if pyautogui:
                    old_pause = pyautogui.PAUSE
                    pyautogui.PAUSE = 0.002
                    for _ in range(50):
                        pyautogui.press("volumedown")
                    for _ in range(val // 2):
                        pyautogui.press("volumeup")
                    pyautogui.PAUSE = old_pause
                    success = True
            if event_queue:
                if success:
                    await event_queue.put({"type": "token", "text": f"Volume has been set to {val} percent, Sir."})
                else:
                    await event_queue.put({"type": "token", "text": "Failed to set volume, Sir."})

        # --- Brightness Controls ---
        elif action == "brightness_up":
            subprocess.run(
                ["powershell", "-Command",
                 "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                 ".WmiSetBrightness(1, [math]::Min(100, "
                 "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness + 10))"],
                capture_output=True, timeout=5
            )
            if event_queue:
                await event_queue.put({"type": "token", "text": "Increasing system brightness, Sir."})
        elif action == "brightness_down":
            subprocess.run(
                ["powershell", "-Command",
                 "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                 ".WmiSetBrightness(1, [math]::Max(0, "
                 "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness - 10))"],
                capture_output=True, timeout=5
            )
            if event_queue:
                await event_queue.put({"type": "token", "text": "Decreasing system brightness, Sir."})
        elif action == "brightness_set":
            val = primitive.get("value", 50)
            subprocess.run(
                ["powershell", "-Command",
                 f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                 f".WmiSetBrightness(1, {val})"],
                capture_output=True, timeout=5
            )
            if event_queue:
                await event_queue.put({"type": "token", "text": f"System brightness set to {val} percent, Sir."})

        # --- Keyboard & Input / Actions ---
        elif action == "take_screenshot":
            if pyautogui:
                pyautogui.hotkey("win", "shift", "s")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Opening Snipping Tool for screenshot, Sir."})
            else:
                if event_queue:
                    await event_queue.put({"type": "token", "text": "pyautogui is not installed, Sir."})
        elif action == "lock_screen":
            if pyautogui:
                pyautogui.hotkey("win", "l")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Locking the screen, Sir."})
            else:
                if event_queue:
                    await event_queue.put({"type": "token", "text": "pyautogui is not installed, Sir."})
        elif action == "toggle_dark_mode":
            try:
                import winreg
                key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
                current, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, 1 - current)
                winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, 1 - current)
                winreg.CloseKey(key)
                msg = "Toggled dark appearance, Sir."
            except Exception as e:
                msg = f"Failed to toggle dark mode: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})
        elif action == "toggle_wifi":
            try:
                subprocess.run(
                    ["powershell", "-Command",
                     "$adapter = Get-NetAdapter | Where-Object {$_.PhysicalMediaType -eq 'Native 802.11'};"
                     "if ($adapter.Status -eq 'Up') { Disable-NetAdapter -Name $adapter.Name -Confirm:$false }"
                     "else { Enable-NetAdapter -Name $adapter.Name -Confirm:$false }"],
                    capture_output=True, timeout=10
                )
                msg = "Toggling Wi-Fi connection, Sir."
            except Exception as e:
                msg = f"Failed to toggle Wi-Fi: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})
        elif action == "sleep_display":
            if ctypes:
                try:
                    ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
                    msg = "Putting display to sleep, Sir."
                except Exception as e:
                    msg = f"Failed to sleep display: {e}"
            else:
                msg = "ctypes is not available, Sir."
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})
        elif action == "restart_computer":
            subprocess.run(["shutdown", "/r", "/t", "10"], capture_output=True)
            if event_queue:
                await event_queue.put({"type": "token", "text": "Restarting the system in ten seconds, Sir."})
        elif action == "shutdown_computer":
            subprocess.run(["shutdown", "/s", "/t", "10"], capture_output=True)
            if event_queue:
                await event_queue.put({"type": "token", "text": "Shutting down the system in ten seconds, Sir."})

        # --- Window Actions ---
        elif action == "close_window":
            if pyautogui:
                pyautogui.hotkey("ctrl", "w")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Closing tab or window, Sir."})
        elif action == "close_app":
            if pyautogui:
                pyautogui.hotkey("alt", "f4")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Closing application, Sir."})
        elif action == "minimize_window":
            if pyautogui:
                pyautogui.hotkey("win", "down")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Minimizing window, Sir."})
        elif action == "maximize_window":
            if pyautogui:
                pyautogui.hotkey("win", "up")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Maximizing window, Sir."})
        elif action == "full_screen":
            if pyautogui:
                pyautogui.press("f11")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Toggling fullscreen mode, Sir."})
        elif action == "show_desktop":
            if pyautogui:
                pyautogui.hotkey("win", "d")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Showing desktop, Sir."})
        elif action == "switch_window":
            if pyautogui:
                pyautogui.hotkey("alt", "tab")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Switching active window, Sir."})
        elif action == "open_task_manager":
            if pyautogui:
                pyautogui.hotkey("ctrl", "shift", "esc")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Opening Task Manager, Sir."})
        elif action == "open_run":
            if pyautogui:
                pyautogui.hotkey("win", "r")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Opening Run dialog, Sir."})
        elif action == "open_settings":
            if pyautogui:
                pyautogui.hotkey("win", "i")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Opening Settings, Sir."})
        elif action == "open_file_explorer":
            if pyautogui:
                pyautogui.hotkey("win", "e")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Opening File Explorer, Sir."})

        # --- Browser Navigation / Tabs ---
        elif action == "new_tab":
            if pyautogui:
                pyautogui.hotkey("ctrl", "t")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Opening a new tab, Sir."})
        elif action == "close_tab":
            if pyautogui:
                pyautogui.hotkey("ctrl", "w")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Closing this tab, Sir."})
        elif action == "next_tab":
            if pyautogui:
                pyautogui.hotkey("ctrl", "tab")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Switching to next tab, Sir."})
        elif action == "prev_tab":
            if pyautogui:
                pyautogui.hotkey("ctrl", "shift", "tab")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Switching to previous tab, Sir."})
        elif action == "go_back":
            if pyautogui:
                pyautogui.hotkey("alt", "left")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Navigating back, Sir."})
        elif action == "go_forward":
            if pyautogui:
                pyautogui.hotkey("alt", "right")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Navigating forward, Sir."})
        elif action == "refresh_page":
            if pyautogui:
                pyautogui.press("f5")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Reloading page, Sir."})
        elif action == "scroll_down":
            if pyautogui:
                pyautogui.scroll(-500)
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Scrolling down, Sir."})
        elif action == "scroll_up":
            if pyautogui:
                pyautogui.scroll(500)
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Scrolling up, Sir."})
        elif action == "zoom_in":
            if pyautogui:
                pyautogui.hotkey("ctrl", "equal")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Zooming in, Sir."})
        elif action == "zoom_out":
            if pyautogui:
                pyautogui.hotkey("ctrl", "minus")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Zooming out, Sir."})
        elif action == "zoom_reset":
            if pyautogui:
                pyautogui.hotkey("ctrl", "0")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Resetting zoom level, Sir."})

        # --- Clipboard / Edit ---
        elif action == "select_all":
            if pyautogui:
                pyautogui.hotkey("ctrl", "a")
        elif action == "copy":
            if pyautogui:
                pyautogui.hotkey("ctrl", "c")
        elif action == "paste":
            if pyautogui:
                pyautogui.hotkey("ctrl", "v")
        elif action == "cut":
            if pyautogui:
                pyautogui.hotkey("ctrl", "x")
        elif action == "undo":
            if pyautogui:
                pyautogui.hotkey("ctrl", "z")
        elif action == "redo":
            if pyautogui:
                pyautogui.hotkey("ctrl", "y")
        elif action == "save_file":
            if pyautogui:
                pyautogui.hotkey("ctrl", "s")
        elif action == "press_enter":
            if pyautogui:
                pyautogui.press("enter")
        elif action == "press_escape":
            if pyautogui:
                pyautogui.press("escape")

        elif action == "type_text":
            text = primitive.get("text", "")
            if text:
                msg = ""
                if len(text) > 20 and pyperclip and pyautogui:
                    pyperclip.copy(text)
                    time.sleep(0.1)
                    pyautogui.hotkey("ctrl", "v")
                    msg = f"Typed text via clipboard: '{text[:20]}...'"
                elif pyautogui:
                    pyautogui.typewrite(text, interval=0.03)
                    msg = f"Typed text: '{text[:20]}...'"
                else:
                    msg = "pyautogui is not installed, cannot type."
                if event_queue:
                    await event_queue.put({"type": "token", "text": msg})

        elif action == "type_in_app":
            app = primitive.get("app", "")
            text = primitive.get("text", "")
            if app and text:
                self._activate_window(app)
                msg = ""
                if len(text) > 20 and pyperclip and pyautogui:
                    pyperclip.copy(text)
                    time.sleep(0.1)
                    pyautogui.hotkey("ctrl", "v")
                    msg = f"Focused '{app}' and typed text via clipboard: '{text[:20]}...'"
                elif pyautogui:
                    pyautogui.typewrite(text, interval=0.03)
                    msg = f"Focused '{app}' and typed text: '{text[:20]}...'"
                else:
                    msg = "pyautogui is not installed, cannot type."
                if event_queue:
                    await event_queue.put({"type": "token", "text": msg})

        elif action == "focus_window":
            title = primitive.get("title", "")
            if title:
                self._activate_window(title)
                msg = f"Focused window: '{title}', Sir."
            else:
                msg = "No window title specified to focus, Sir."
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "click_xy":
            x = primitive.get("x")
            y = primitive.get("y")
            if pyautogui and x is not None and y is not None:
                pyautogui.click(x, y)
                msg = f"Clicked at coordinates ({x}, {y})."
            else:
                msg = "pyautogui not available or coordinates invalid."
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "right_click_xy":
            x = primitive.get("x")
            y = primitive.get("y")
            if pyautogui and x is not None and y is not None:
                pyautogui.rightClick(x, y)
                msg = f"Right clicked at coordinates ({x}, {y})."
            else:
                msg = "pyautogui not available or coordinates invalid."
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "double_click_xy":
            x = primitive.get("x")
            y = primitive.get("y")
            if pyautogui and x is not None and y is not None:
                pyautogui.doubleClick(x, y)
                msg = f"Double clicked at coordinates ({x}, {y})."
            else:
                msg = "pyautogui not available or coordinates invalid."
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "move_to_xy":
            x = primitive.get("x")
            y = primitive.get("y")
            if pyautogui and x is not None and y is not None:
                pyautogui.moveTo(x, y, duration=0.2)
                msg = f"Moved mouse to coordinates ({x}, {y})."
            else:
                msg = "pyautogui not available or coordinates invalid."
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "drag":
            x1 = primitive.get("x1")
            y1 = primitive.get("y1")
            x2 = primitive.get("x2")
            y2 = primitive.get("y2")
            if pyautogui and x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                pyautogui.moveTo(x1, y1)
                time.sleep(0.1)
                pyautogui.dragTo(x2, y2, duration=0.5)
                msg = f"Dragged from ({x1}, {y1}) to ({x2}, {y2})."
            else:
                msg = "pyautogui not available or coordinates invalid."
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        # --- Reminders ---
        elif action == "set_reminder":
            dt = primitive.get("date_time")
            msg = primitive.get("message")
            
            sd = dt.strftime("%d/%m/%Y")
            st = dt.strftime("%H:%M")
            clean_msg = msg.replace('"', '').replace("'", "")
            task_name = f"VictorReminder_{dt.strftime('%Y%m%d_%H%M%S')}"
            
            python_exe = sys.executable
            pythonw = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
            if os.path.exists(pythonw):
                python_exe = pythonw
                
            tr_cmd = f'{python_exe} -c "import ctypes, winsound; winsound.Beep(1000, 500); ctypes.windll.user32.MessageBoxW(0, \'{clean_msg}\', \'VICTOR Reminder\', 0)"'
            
            cmd = [
                "schtasks", "/Create", "/SC", "ONCE",
                "/TN", task_name,
                "/TR", tr_cmd,
                "/ST", st,
                "/SD", sd,
                "/IT", "/F"
            ]
            
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                success_msg = f"Reminder set successfully for {dt.strftime('%Y-%m-%d %H:%M')}: {msg}."
            else:
                success_msg = f"Failed to set reminder: {res.stderr or res.stdout}"
            if event_queue:
                await event_queue.put({"type": "token", "text": success_msg})

        # --- Wallpaper & Desktop ---
        elif action in ("set_wallpaper_path", "set_wallpaper_url"):
            img_path = primitive.get("path")
            desktop_msg = ""
            if action == "set_wallpaper_url":
                import urllib.request
                import tempfile
                try:
                    url = primitive.get("url")
                    suffix = Path(url.split("?")[0]).suffix or ".jpg"
                    if suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                        suffix = ".jpg"
                    tmp = Path(tempfile.gettempdir()) / f"temp_wallpaper{suffix}"
                    urllib.request.urlretrieve(url, str(tmp))
                    img_path = str(tmp)
                except Exception as e:
                    img_path = None
                    desktop_msg = f"Failed to download wallpaper: {e}"
            
            if img_path:
                path = Path(img_path).expanduser().resolve()
                if path.exists():
                    if path.suffix.lower() in {".webp", ".png"}:
                        try:
                            from PIL import Image
                            bmp_path = path.with_suffix(".bmp")
                            Image.open(path).convert("RGB").save(bmp_path, "BMP")
                            path = bmp_path
                        except Exception as e:
                            print(f"PIL conversion failed: {e}")
                    if ctypes:
                        try:
                            ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 3)
                            desktop_msg = f"Wallpaper successfully set to {path.name}, Sir."
                        except Exception as e:
                            desktop_msg = f"Failed to set wallpaper: {e}"
                    else:
                        desktop_msg = "ctypes is not available, Sir."
                else:
                    desktop_msg = f"Wallpaper file not found: {img_path}"
            if event_queue:
                await event_queue.put({"type": "token", "text": desktop_msg})

        elif action in ("organize_desktop", "organize_desktop_mode"):
            mode = primitive.get("mode", "by_type")
            desktop = Path.home() / "Desktop"
            FILE_TYPE_MAP = {
                "Images":      {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"},
                "Documents":   {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"},
                "Videos":      {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"},
                "Music":       {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"},
                "Archives":    {".zip", ".rar", ".7z", ".tar", ".gz"},
                "Code":        {".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".cpp", ".java", ".cs"},
                "Executables": {".exe", ".msi", ".bat", ".cmd"},
            }
            
            moved = 0
            if desktop.exists():
                for item in desktop.iterdir():
                    if item.is_dir() or item.name.startswith("."):
                        continue
                    if item.suffix.lower() in {".lnk", ".url"}:
                        continue
                        
                    if mode == "by_date":
                        try:
                            mtime = item.stat().st_mtime
                            dt = datetime.datetime.fromtimestamp(mtime)
                            folder_name = dt.strftime("%Y-%m")
                        except Exception:
                            folder_name = "Others"
                    else:
                        ext = item.suffix.lower()
                        folder_name = "Others"
                        for folder, exts in FILE_TYPE_MAP.items():
                            if ext in exts:
                                folder_name = folder
                                break
                            
                    target_dir = desktop / folder_name
                    target_dir.mkdir(exist_ok=True)
                    new_path = target_dir / item.name
                    if not new_path.exists():
                        try:
                            shutil.move(str(item), str(new_path))
                            moved += 1
                        except Exception as e:
                            console.print(f"[red]Error organizing desktop item {item.name}: {e}[/red]")
                            
                desktop_msg = f"Desktop organized ({mode}): {moved} files categorized, Sir."
            else:
                desktop_msg = "Desktop folder not found, Sir."
            if event_queue:
                await event_queue.put({"type": "token", "text": desktop_msg})

        elif action == "clean_desktop":
            desktop = Path.home() / "Desktop"
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            archive_dir = desktop / f"Desktop Archive {today}"
            
            moved = 0
            if desktop.exists():
                archive_dir.mkdir(exist_ok=True)
                for item in desktop.iterdir():
                    if item.is_dir() or item.name.startswith("."):
                        continue
                    if item.suffix.lower() in {".lnk", ".url"}:
                        continue
                    new_path = archive_dir / item.name
                    if not new_path.exists():
                        shutil.move(str(item), str(new_path))
                        moved += 1
                desktop_msg = f"Desktop cleaned: {moved} files archived to '{archive_dir.name}', Sir."
            else:
                desktop_msg = "Desktop folder not found, Sir."
            if event_queue:
                await event_queue.put({"type": "token", "text": desktop_msg})

        elif action == "list_desktop":
            desktop = Path.home() / "Desktop"
            items = []
            if desktop.exists():
                for item in sorted(desktop.iterdir()):
                    if item.name.startswith("."):
                        continue
                    if item.is_dir():
                        items.append(f"Folder: {item.name}")
                    else:
                        items.append(f"File: {item.name}")
                desktop_msg = "Here are the items on your desktop: " + ", ".join(items) if items else "Your desktop is empty, Sir."
            else:
                desktop_msg = "Desktop folder not found, Sir."
            if event_queue:
                await event_queue.put({"type": "token", "text": desktop_msg})

        elif action == "desktop_stats":
            desktop = Path.home() / "Desktop"
            if desktop.exists():
                files = [i for i in desktop.iterdir() if i.is_file()]
                folders = [i for i in desktop.iterdir() if i.is_dir()]
                total_size = sum(f.stat().st_size for f in files if f.exists())
                size_str = f"{total_size / (1024*1024):.1f} megabytes" if total_size >= 1024*1024 else f"{total_size / 1024:.1f} kilobytes"
                desktop_msg = f"Desktop stats, Sir: you have {len(files)} files and {len(folders)} folders, with a total size of {size_str}."
            else:
                desktop_msg = "Desktop folder not found, Sir."
            if event_queue:
                await event_queue.put({"type": "token", "text": desktop_msg})

        # --- Weather Report ---
        elif action == "weather_report":
            city = primitive.get("city", "Mumbai")
            url = f"https://www.google.com/search?q=weather+in+{quote_plus(city)}"
            webbrowser.open(url)
            weather_msg = f"Showing the weather for {city} in your browser, Sir."
            if event_queue:
                await event_queue.put({"type": "token", "text": weather_msg})

        # --- Local Application Launcher ---
        elif action == "open_app":
            app_name = primitive.get("app_name", "").strip()
            normalized = app_name.lower()
            
            # Comprehensive app alias dictionary (merged from Mark-XL)
            APP_ALIASES_WIN = {
                # Browsers
                "chrome": "chrome",
                "google chrome": "chrome",
                "firefox": "firefox",
                "edge": "msedge",
                "microsoft edge": "msedge",
                "brave": "brave",
                "safari": "msedge",
                "opera": "opera",
                # Communication
                "whatsapp": "WhatsApp",
                "telegram": "Telegram",
                "discord": "Discord",
                "slack": "Slack",
                "zoom": "Zoom",
                "teams": "msteams",
                "microsoft teams": "msteams",
                "skype": "skype",
                "signal": "signal",
                # Media
                "spotify": "Spotify",
                "vlc": "vlc",
                "netflix": "Netflix",
                "itunes": "iTunes",
                # Microsoft Office
                "word": "winword",
                "microsoft word": "winword",
                "excel": "excel",
                "microsoft excel": "excel",
                "powerpoint": "powerpnt",
                "microsoft powerpoint": "powerpnt",
                "outlook": "outlook",
                "microsoft outlook": "outlook",
                "onenote": "onenote",
                "access": "msaccess",
                "publisher": "mspub",
                # Development
                "vscode": "code",
                "visual studio code": "code",
                "vs code": "code",
                "code": "code",
                "visual studio": "devenv",
                "sublime": "subl",
                "sublime text": "subl",
                "atom": "atom",
                "pycharm": "pycharm64",
                "intellij": "idea64",
                "git bash": "git-bash",
                "postman": "Postman",
                # System Tools
                "notepad": "notepad.exe",
                "notepad++": "notepad++",
                "explorer": "explorer.exe",
                "file explorer": "explorer.exe",
                "task manager": "taskmgr.exe",
                "settings": "ms-settings:",
                "calculator": "calc.exe",
                "calc": "calc.exe",
                "paint": "mspaint.exe",
                "snipping tool": "SnippingTool",
                "snip": "SnippingTool",
                "wordpad": "wordpad.exe",
                "control panel": "control",
                # Terminal variants
                "terminal": "wt",
                "windows terminal": "wt",
                "cmd": "cmd.exe",
                "command prompt": "cmd.exe",
                "powershell": "powershell.exe",
                # Utilities
                "obs": "obs64",
                "obs studio": "obs64",
                "steam": "steam",
                "blender": "blender",
                "audacity": "audacity",
                "gimp": "gimp",
                "figma": "Figma",
                "notion": "Notion",
                "obsidian": "Obsidian",
                "1password": "1Password",
                "bitwarden": "Bitwarden",
            }
            
            target_cmd = APP_ALIASES_WIN.get(normalized, app_name)
            
            launched = False
            # Layer 1: Try shutil.which to find the executable on PATH
            if shutil.which(target_cmd) or shutil.which(target_cmd.split(".")[0]):
                try:
                    subprocess.Popen(
                        target_cmd,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                except Exception:
                    pass
            
            # Layer 2: Direct Popen attempt (for executables not on PATH but still launchable)
            if not launched:
                try:
                    subprocess.Popen(
                        target_cmd,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                except Exception:
                    pass

            # Layer 3: URI scheme launch (e.g., ms-settings:)
            if not launched and ":" in target_cmd:
                try:
                    subprocess.Popen(f"start {target_cmd}", shell=True)
                    launched = True
                except Exception:
                    pass
            
            # Layer 4: Fallback — type app name into Windows Start Menu search
            if not launched and pyautogui:
                try:
                    pyautogui.press("win")
                    time.sleep(0.5)
                    pyautogui.write(app_name, interval=0.02)
                    time.sleep(0.5)
                    pyautogui.press("enter")
                    launched = True
                except Exception:
                    pass
                    
            if launched:
                msg = f"Opened {app_name}, Sir."
            else:
                msg = f"Could not open {app_name}, Sir."
                
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        # --- Persistent Browser Actions ---
        elif action == "browser_switch":
            target = primitive.get("target", "chrome")
            try:
                browser_registry.switch_target(target)
                msg = f"Switched target browser session to '{target.capitalize()}', Sir."
            except Exception as e:
                msg = f"Failed to switch browser: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "browser_list":
            try:
                browsers = browser_registry.list_browsers()
                msg = "Here are your browser sessions:\n" + "\n".join(browsers)
            except Exception as e:
                msg = f"Failed to list browsers: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "browser_go_to":
            url = primitive.get("url", "")
            try:
                browser_registry.go_to(url)
                msg = f"Navigated to '{url}' in the active browser, Sir."
            except Exception as e:
                msg = f"Failed to navigate to {url}: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "browser_search":
            query = primitive.get("query", "")
            engine = primitive.get("engine", "google")
            try:
                browser_registry.search(query, engine)
                msg = f"Searching for '{query}' using {engine.capitalize()} in the active browser, Sir."
            except Exception as e:
                msg = f"Failed to perform search: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "browser_smart_click":
            desc = primitive.get("description", "")
            try:
                success = browser_registry.smart_click(desc)
                if success:
                    msg = f"Successfully clicked on '{desc}' element, Sir."
                else:
                    msg = f"Could not find or click '{desc}' element, Sir."
            except Exception as e:
                msg = f"Smart click failed: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "browser_smart_type":
            desc = primitive.get("description", "")
            text = primitive.get("text", "")
            try:
                success = browser_registry.smart_type(desc, text)
                if success:
                    msg = f"Successfully typed text into '{desc}' element, Sir."
                else:
                    msg = f"Could not find or type into '{desc}' element, Sir."
            except Exception as e:
                msg = f"Smart type failed: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "browser_close_tab":
            try:
                browser_registry.close_tab()
                msg = "Closed the active tab, Sir."
            except Exception as e:
                msg = f"Failed to close tab: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "browser_new_tab":
            try:
                browser_registry.new_tab()
                msg = "Opened a new tab, Sir."
            except Exception as e:
                msg = f"Failed to open new tab: {e}"
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        # --- Automated Messenger Routes ---
        elif action == "send_message":
            platform = primitive.get("platform", "").lower().strip()
            receiver = primitive.get("receiver", "")
            text = primitive.get("text", "")
            
            msg = ""
            if platform in ("instagram", "messenger", "facebook messenger", "fb"):
                # Use web app fallback
                if async_playwright:
                    try:
                        async def _send_web():
                            await send_web_message(platform, receiver, text)
                        browser_registry.run_coro(_send_web())
                        msg = f"Sent {platform} message to {receiver} via browser."
                    except Exception as e:
                        msg = f"Failed to send web message: {e}"
                else:
                    msg = f"Playwright not installed, cannot send message via web fallback for {platform}."
            else:
                # Desktop App Automation (WhatsApp, Telegram, Signal, Discord)
                # 1. Bring up the app
                app_aliases = {
                    "whatsapp": "WhatsApp",
                    "telegram": "Telegram",
                    "signal": "signal",
                    "discord": "Discord"
                }
                app_name = app_aliases.get(platform, platform)
                # Use standard launcher to start & focus
                await self._handle_primitive({"action": "open_app", "app_name": app_name}, event_queue)
                time.sleep(3.0) # wait for app to open & focus
                
                if pyautogui:
                    try:
                        # 2. Focus search: ctrl+f (or ctrl+k for discord)
                        if platform == "discord":
                            pyautogui.hotkey("ctrl", "k")
                        else:
                            pyautogui.hotkey("ctrl", "f")
                        time.sleep(0.5)
                        
                        # 3. Copy recipient and paste
                        if pyperclip:
                            pyperclip.copy(receiver)
                            time.sleep(0.2)
                            pyautogui.hotkey("ctrl", "v")
                        else:
                            pyautogui.typewrite(receiver, interval=0.02)
                        time.sleep(1.0)
                        
                        # 4. Press Enter to open chat
                        pyautogui.press("enter")
                        time.sleep(1.5)
                        
                        # 5. Copy message text and paste
                        if pyperclip:
                            pyperclip.copy(text)
                            time.sleep(0.2)
                            pyautogui.hotkey("ctrl", "v")
                        else:
                            pyautogui.typewrite(text, interval=0.02)
                        time.sleep(0.5)
                        
                        # 6. Press Enter to send
                        pyautogui.press("enter")
                        msg = f"Successfully dispatched message to {receiver} on {platform.capitalize()}."
                    except Exception as e:
                        msg = f"UI automation failed during messaging: {e}"
                else:
                    msg = "pyautogui is not installed, cannot run desktop messenger automation."
            
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        # --- Grid Layout Snapping ---
        elif action == "snap_left":
            if pyautogui:
                pyautogui.hotkey("win", "left")
                msg = "Snapped window to the left, Sir."
            else:
                msg = "pyautogui not installed, cannot snap window."
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        elif action == "snap_right":
            if pyautogui:
                pyautogui.hotkey("win", "right")
                msg = "Snapped window to the right, Sir."
            else:
                msg = "pyautogui not installed, cannot snap window."
            if event_queue:
                await event_queue.put({"type": "token", "text": msg})

        else:
            console.print(f"[red]Unknown action:[/red] {action}")

task_executor = TaskExecutor()


# ==========================================
# Mark-XL Persistent Browser Engine & helpers
# ==========================================

def get_browser_profile_path(browser_name: str) -> str:
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    
    paths = {
        "chrome": os.path.join(local_appdata, r"Google\Chrome\User Data"),
        "brave": os.path.join(local_appdata, r"BraveSoftware\Brave-Browser\User Data"),
        "edge": os.path.join(local_appdata, r"Microsoft\Edge\User Data"),
        "opera": os.path.join(appdata, r"Opera Software\Opera Stable"),
        "firefox": os.path.join(appdata, r"Mozilla\Firefox\Profiles"),
    }
    
    target = browser_name.lower().strip()
    profile_path = paths.get(target)
    if profile_path and os.path.exists(profile_path):
        return profile_path
        
    fallback_root = Path.home() / ".jarvis_profiles"
    fallback_root.mkdir(parents=True, exist_ok=True)
    browser_fallback = fallback_root / target
    browser_fallback.mkdir(parents=True, exist_ok=True)
    return str(browser_fallback)

def find_browser_executable(browser_name: str) -> str:
    browser_name = browser_name.lower().strip()
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    local_appdata = os.environ.get("LOCALAPPDATA", "C:\\Users\\Default\\AppData\\Local")
    
    candidates = []
    if browser_name in ("chrome", "google chrome"):
        candidates = [
            os.path.join(program_files, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(program_files_x86, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(local_appdata, r"Google\Chrome\Application\chrome.exe"),
        ]
    elif browser_name == "brave":
        candidates = [
            os.path.join(program_files, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.join(program_files_x86, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.join(local_appdata, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
    elif browser_name in ("edge", "msedge", "microsoft edge"):
        candidates = [
            os.path.join(program_files_x86, r"Microsoft\Edge\Application\msedge.exe"),
            os.path.join(program_files, r"Microsoft\Edge\Application\msedge.exe"),
        ]
    elif browser_name == "opera":
        candidates = [
            os.path.join(local_appdata, r"Programs\Opera\launcher.exe"),
            os.path.join(program_files, r"Opera\launcher.exe"),
            os.path.join(program_files_x86, r"Opera\launcher.exe"),
        ]
    elif browser_name == "firefox":
        candidates = [
            os.path.join(program_files, r"Mozilla Firefox\firefox.exe"),
            os.path.join(program_files_x86, r"Mozilla Firefox\firefox.exe"),
        ]
        
    for path in candidates:
        if os.path.exists(path):
            return path
            
    paths_to_check = {
        "chrome": "chrome.exe",
        "brave": "brave.exe",
        "edge": "msedge.exe",
        "opera": "opera.exe",
        "firefox": "firefox.exe"
    }
    shortcut = paths_to_check.get(browser_name)
    if shortcut:
        found = shutil.which(shortcut)
        if found:
            return found
            
    return ""

class _BrowserSession:
    def __init__(self, browser_name: str, loop):
        self.browser_name = browser_name
        self.loop = loop
        self.playwright = None
        self.context = None
        self.page = None

    async def initialize(self):
        if self.playwright is not None:
            return
            
        if not async_playwright:
            raise RuntimeError("Playwright is not installed.")
            
        self.playwright = await async_playwright().start()
        
        profile_path = get_browser_profile_path(self.browser_name)
        exec_path = find_browser_executable(self.browser_name)
        
        try:
            kwargs = {
                "user_data_dir": profile_path,
                "headless": False,
            }
            if exec_path:
                kwargs["executable_path"] = exec_path
                
            if self.browser_name == "firefox":
                self.context = await self.playwright.firefox.launch_persistent_context(**kwargs)
            else:
                self.context = await self.playwright.chromium.launch_persistent_context(**kwargs)
        except Exception as e:
            console.print(f"[yellow]Failed to launch {self.browser_name} with real profile: {e}. Trying fallback...[/yellow]")
            fallback_dir = os.path.join(str(Path.home() / ".jarvis_profiles"), f"{self.browser_name}_fallback")
            os.makedirs(fallback_dir, exist_ok=True)
            kwargs = {
                "user_data_dir": fallback_dir,
                "headless": False,
            }
            if exec_path:
                kwargs["executable_path"] = exec_path
                
            if self.browser_name == "firefox":
                self.context = await self.playwright.firefox.launch_persistent_context(**kwargs)
            else:
                self.context = await self.playwright.chromium.launch_persistent_context(**kwargs)
                
        pages = self.context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = await self.context.new_page()

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        self.context = None
        self.playwright = None
        self.page = None

class _SessionRegistry:
    def __init__(self):
        self.loop = None
        self.thread = None
        self.sessions = {}
        self.active_browser = "chrome"
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self.thread is not None and self.thread.is_alive():
                return
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_coro(self, coro):
        self.start()
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    async def _get_active_session(self):
        if not self.active_browser:
            self.active_browser = "chrome"
        browser_name = self.active_browser.lower().strip()
        if browser_name not in self.sessions:
            session = _BrowserSession(browser_name, self.loop)
            self.sessions[browser_name] = session
            await session.initialize()
        return self.sessions[browser_name]

    def switch_target(self, target: str):
        self.active_browser = target.lower().strip()
        self.run_coro(self._get_active_session())

    def list_browsers(self) -> List[str]:
        supported = ["chrome", "edge", "brave", "opera", "firefox"]
        results = []
        for b in supported:
            is_active = "active" if b == self.active_browser else "inactive"
            is_init = "initialized" if b in self.sessions else "not initialized"
            results.append(f"{b.capitalize()} ({is_active}, {is_init})")
        return results

    def go_to(self, url: str):
        async def _go():
            session = await self._get_active_session()
            await session.page.goto(url)
        self.run_coro(_go())

    def search(self, query: str, engine: str = "google"):
        async def _search():
            session = await self._get_active_session()
            engine_lower = engine.lower().strip()
            if "bing" in engine_lower:
                url = f"https://www.bing.com/search?q={quote_plus(query)}"
            elif "duck" in engine_lower:
                url = f"https://duckduckgo.com/?q={quote_plus(query)}"
            else:
                url = f"https://www.google.com/search?q={quote_plus(query)}"
            await session.page.goto(url)
        self.run_coro(_search())

    def smart_click(self, description: str) -> bool:
        async def _click():
            session = await self._get_active_session()
            return await perform_smart_click(session.page, description)
        return self.run_coro(_click())

    def smart_type(self, description: str, text: str) -> bool:
        async def _type():
            session = await self._get_active_session()
            return await perform_smart_type(session.page, description, text)
        return self.run_coro(_type())

    def close_tab(self):
        async def _close():
            session = await self._get_active_session()
            if session.context:
                pages = session.context.pages
                if len(pages) > 1:
                    await session.page.close()
                    session.page = session.context.pages[-1]
                else:
                    await session.page.goto("about:blank")
        self.run_coro(_close())

    def new_tab(self):
        async def _new():
            session = await self._get_active_session()
            if session.context:
                session.page = await session.context.new_page()
        self.run_coro(_new())

browser_registry = _SessionRegistry()

async def find_element(page, description: str, roles=None):
    if roles is None:
        roles = ["button", "link", "textbox", "searchbox", "checkbox", "radio", "combobox"]
    desc_clean = description.strip()
    
    for role in roles:
        try:
            locator = page.get_by_role(role, name=re.compile(re.escape(desc_clean), re.IGNORECASE))
            if await locator.count() > 0:
                for i in range(await locator.count()):
                    el = locator.nth(i)
                    if await el.is_visible():
                        return el
        except Exception:
            pass

    try:
        locator = page.get_by_placeholder(re.compile(re.escape(desc_clean), re.IGNORECASE))
        if await locator.count() > 0:
            for i in range(await locator.count()):
                el = locator.nth(i)
                if await el.is_visible():
                    return el
    except Exception:
        pass

    try:
        locator = page.get_by_label(re.compile(re.escape(desc_clean), re.IGNORECASE))
        if await locator.count() > 0:
            for i in range(await locator.count()):
                el = locator.nth(i)
                if await el.is_visible():
                    return el
    except Exception:
        pass

    try:
        locator = page.get_by_text(re.compile(re.escape(desc_clean), re.IGNORECASE))
        if await locator.count() > 0:
            for i in range(await locator.count()):
                el = locator.nth(i)
                if await el.is_visible():
                    return el
    except Exception:
        pass

    selectors = [
        f"[title*='{desc_clean}' i]",
        f"[alt*='{desc_clean}' i]",
        f"[aria-label*='{desc_clean}' i]",
        f"[id*='{desc_clean}' i]",
        f"[name*='{desc_clean}' i]",
        f"[class*='{desc_clean}' i]",
        f"//*[contains(text(), '{desc_clean}')]",
        f"[value*='{desc_clean}' i]",
    ]
    for sel in selectors:
        try:
            locator = page.locator(sel)
            if await locator.count() > 0:
                for i in range(await locator.count()):
                    el = locator.nth(i)
                    if await el.is_visible():
                        return el
        except Exception:
            pass
    return None

async def perform_smart_click(page, description: str) -> bool:
    element = await find_element(page, description)
    if element:
        await element.scroll_into_view_if_needed()
        await element.click()
        return True
    return False

async def perform_smart_type(page, description: str, text: str) -> bool:
    element = await find_element(page, description, roles=["textbox", "searchbox"])
    if not element:
        element = await find_element(page, description)
    if element:
        await element.scroll_into_view_if_needed()
        await element.click()
        await element.fill("")
        await element.type(text, delay=50)
        return True
    return False

async def send_web_message(platform: str, receiver: str, text: str):
    session = await browser_registry._get_active_session()
    if platform == "instagram":
        url = "https://www.instagram.com/direct/new/"
    else:
        url = "https://www.facebook.com/messages/new"
        
    await session.page.goto(url)
    try:
        await session.page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    await asyncio.sleep(3)
    
    success = False
    for search_term in ["search", "to:", "to", "send message to", "type a name"]:
        success = await perform_smart_type(session.page, search_term, receiver)
        if success:
            break
            
    if not success:
        for _ in range(5):
            await session.page.keyboard.press("Tab")
            await asyncio.sleep(0.1)
        await session.page.keyboard.insert_text(receiver)
        await asyncio.sleep(1)
        
    await session.page.keyboard.press("Enter")
    await asyncio.sleep(2)
    
    success_msg = False
    for msg_term in ["message", "type a message", "write a message", "start a message"]:
        success_msg = await perform_smart_type(session.page, msg_term, text)
        if success_msg:
            break
            
    if not success_msg:
        for _ in range(5):
            await session.page.keyboard.press("Tab")
            await asyncio.sleep(0.1)
        await session.page.keyboard.insert_text(text)
        await asyncio.sleep(0.5)
        
    await session.page.keyboard.press("Enter")


# ==========================================
# Native COM Audio Control helper functions
# ==========================================

def set_win_mute_com(mute: bool) -> bool:
    if not pycaw or not comtypes:
        return False
    try:
        comtypes.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
        )
        volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        volume.SetMute(1 if mute else 0, None)
        return True
    except Exception as e:
        console.print(f"[yellow]COM Mute control failed: {e}[/yellow]")
        return False
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass

def set_win_volume_com(percent: int) -> bool:
    if not pycaw or not comtypes:
        return False
    try:
        comtypes.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
        )
        volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        if percent <= 0:
            volume.SetMute(1, None)
            min_db, _, _ = volume.GetVolumeRange()
            volume.SetMasterVolumeLevel(min_db, None)
        else:
            volume.SetMute(0, None)
            db = 20 * math.log10(percent / 100.0)
            min_db, max_db, _ = volume.GetVolumeRange()
            if db < min_db:
                db = min_db
            elif db > max_db:
                db = max_db
            volume.SetMasterVolumeLevel(db, None)
        return True
    except Exception as e:
        console.print(f"[yellow]COM Volume control failed: {e}[/yellow]")
        return False
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass
