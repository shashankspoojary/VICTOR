import asyncio
import json
import webbrowser
import re
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

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import ctypes
except ImportError:
    ctypes = None

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

        # --- Wallpaper & Desktop ---
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
            return {"action": "organize_desktop"}

        if "clean" in s and "desktop" in s:
            return {"action": "clean_desktop"}

        if "list" in s and "desktop" in s:
            return {"action": "list_desktop"}

        if "stats" in s and "desktop" in s:
            return {"action": "desktop_stats"}

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
            if pyautogui:
                pyautogui.press("volumemute")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Muting the volume, Sir."})
            else:
                if event_queue:
                    await event_queue.put({"type": "token", "text": "pyautogui is not installed, Sir."})
        elif action == "volume_unmute":
            if pyautogui:
                pyautogui.press("volumemute")
                if event_queue:
                    await event_queue.put({"type": "token", "text": "Unmuting the volume, Sir."})
            else:
                if event_queue:
                    await event_queue.put({"type": "token", "text": "pyautogui is not installed, Sir."})
        elif action == "volume_set":
            val = primitive.get("value", 50)
            if pyautogui:
                old_pause = pyautogui.PAUSE
                pyautogui.PAUSE = 0.002
                for _ in range(50):
                    pyautogui.press("volumedown")
                for _ in range(val // 2):
                    pyautogui.press("volumeup")
                pyautogui.PAUSE = old_pause
                if event_queue:
                    await event_queue.put({"type": "token", "text": f"Volume has been set to {val} percent, Sir."})
            else:
                if event_queue:
                    await event_queue.put({"type": "token", "text": "pyautogui is not installed, Sir."})

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

        elif action == "organize_desktop":
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
                        shutil.move(str(item), str(new_path))
                        moved += 1
                desktop_msg = f"Desktop organized: {moved} files categorized, Sir."
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
            
            APP_ALIASES_WIN = {
                "chrome": "chrome",
                "google chrome": "chrome",
                "firefox": "firefox",
                "edge": "msedge",
                "brave": "brave",
                "safari": "msedge",
                "opera": "opera",
                "whatsapp": "WhatsApp",
                "telegram": "Telegram",
                "discord": "Discord",
                "slack": "Slack",
                "zoom": "Zoom",
                "teams": "msteams",
                "spotify": "Spotify",
                "vlc": "vlc",
                "vscode": "code",
                "visual studio code": "code",
                "code": "code",
                "notepad": "notepad.exe",
                "explorer": "explorer.exe",
                "file explorer": "explorer.exe",
                "task manager": "taskmgr.exe",
                "settings": "ms-settings:",
                "calculator": "calc.exe",
                "paint": "mspaint.exe",
            }
            
            target_cmd = APP_ALIASES_WIN.get(normalized, app_name)
            
            launched = False
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
            
            if not launched and ":" in target_cmd:
                try:
                    subprocess.Popen(f"start {target_cmd}", shell=True)
                    launched = True
                except Exception:
                    pass
                    
            if not launched and pyautogui:
                try:
                    pyautogui.press("win")
                    import time
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

        else:
            console.print(f"[red]Unknown action:[/red] {action}")

task_executor = TaskExecutor()
