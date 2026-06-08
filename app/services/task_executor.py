import asyncio
import json
import webbrowser
import re
from typing import List
from rich.console import Console
from app.services.realtime_service import realtime_service
from app.services.memory_service import memory_service

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

        # --- Research (default for info/search queries) ---
        # Strip common filler prefixes to get a clean search query
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
                # Derive a friendly site name from the URL for the confirmation message
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
        else:
            console.print(f"[red]Unknown action:[/red] {action}")

task_executor = TaskExecutor()
