import asyncio
import json
import datetime
import random
import platform
import subprocess
import shutil
import re
import base64
import edge_tts
import psutil
# Initialize CPU usage tracking sample on module load to prevent inaccurate 0.0% readings on first telemetry check
psutil.cpu_percent(interval=None)

from typing import AsyncGenerator, Optional

import config
from app.services.ai_service import ai_service
from app.services.memory_service import memory_service
from app.services.realtime_service import realtime_service

def _extract_chat_and_sidebar_fallback(text: str) -> tuple[str, str]:
    chat_text = ""
    sidebar_markdown = ""
    
    # Try parsing as standard JSON first
    try:
        data = json.loads(text)
        chat_text = data.get("chat", "").strip()
        sidebar_markdown = data.get("sidebar", "").strip()
        if chat_text or sidebar_markdown:
            return chat_text, sidebar_markdown
    except Exception:
        pass

    # If standard JSON parsing fails, try regex extraction
    chat_match = re.search(r'"chat"\s*:\s*"(.*?)"\s*,\s*"sidebar"', text, re.DOTALL)
    if chat_match:
        chat_text = chat_match.group(1)
        try:
            chat_text = chat_text.encode().decode('unicode-escape', errors='ignore')
        except Exception:
            pass
    else:
        chat_match = re.search(r'"chat"\s*:\s*"(.*?)"', text, re.DOTALL)
        if chat_match:
            try:
                chat_text = chat_match.group(1).encode().decode('unicode-escape', errors='ignore')
            except Exception:
                chat_text = chat_match.group(1)

    sidebar_match = re.search(r'"sidebar"\s*:\s*(.*)', text, re.DOTALL)
    if sidebar_match:
        sidebar_content = sidebar_match.group(1).strip()
        if sidebar_content.endswith("}"):
            sidebar_content = sidebar_content[:-1].strip()
            
        if sidebar_content.startswith('"') and sidebar_content.endswith('"'):
            try:
                sidebar_markdown = json.loads(sidebar_content)
            except Exception:
                sidebar_markdown = sidebar_content[1:-1].strip()
        else:
            sidebar_markdown = sidebar_content
            
    # Clean up escaping in case they are still present
    chat_text = chat_text.replace('\\"', '"').replace('\\n', '\n').strip()
    sidebar_markdown = sidebar_markdown.replace('\\"', '"').replace('\\n', '\n').strip()
    
    return chat_text, sidebar_markdown

def gather_system_telemetry() -> dict:
    telemetry = {
        "os": f"{platform.system()} {platform.release()}",
        "disk_c": "Unknown",
        "disk_d": "Unknown",
        "cpu_usage": "Unknown",
        "ram_usage": "Unknown",
    }
    
    # Disk status checks
    try:
        usage_c = shutil.disk_usage("C:")
        telemetry["disk_c"] = f"{usage_c.free // (1024**3)} GB free of {usage_c.total // (1024**3)} GB"
    except Exception:
        pass
    try:
        usage_d = shutil.disk_usage("D:")
        telemetry["disk_d"] = f"{usage_d.free // (1024**3)} GB free of {usage_d.total // (1024**3)} GB"
    except Exception:
        pass
    
    # CPU status checks
    try:
        cpu_load = psutil.cpu_percent(interval=None)
        telemetry["cpu_usage"] = f"{cpu_load}%"
    except Exception:
        pass

    # RAM status checks
    try:
        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024**3)
        total_gb = mem.total / (1024**3)
        telemetry["ram_usage"] = f"{mem.percent}% ({used_gb:.1f} GB / {total_gb:.1f} GB)"
    except Exception:
        pass

    return telemetry

async def scan_monitored_assets(session_id: str) -> tuple[str, list]:
    memory_data = {}
    memory_file = memory_service.memory_file
    if memory_file.exists():
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                memory_data = json.load(f)
        except Exception:
            pass

    assets = {}
    for k, v in memory_data.items():
        k_lower = k.lower()
        if ("website" in k_lower or "site" in k_lower or "youtube" in k_lower or "channel" in k_lower or "yt" in k_lower) and isinstance(v, str) and v.startswith("http"):
            assets[k] = v

    if not assets:
        return "No personal websites or YouTube channels are currently registered in my database, Sir.", []

    results_summary = []
    search_results_list = []
    
    async def process_asset(name: str, url: str):
        is_youtube = "youtube" in name.lower() or "youtube" in url.lower() or "yt" in name.lower()
        if is_youtube:
            query = f"latest videos subscriber count of YouTube channel {url}"
            res = await realtime_service.search(query)
            summary = res.get("summary", "No details found.")
            return f"- YouTube Channel ({name} - {url}): {summary}", {
                "title": f"YouTube Channel: {name}",
                "content": summary,
                "url": url
            }
        else:
            import requests
            def check_url_sync():
                try:
                    resp = requests.get(url, timeout=3.0)
                    if resp.status_code == 200:
                        return f"online (status 200)"
                    else:
                        return f"online but returned status {resp.status_code}"
                except Exception as e:
                    return f"unreachable ({type(e).__name__})"
                    
            status = await asyncio.to_thread(check_url_sync)
            
            query = f"status or description of website {url}"
            res = await realtime_service.search(query)
            summary = res.get("summary", "No recent web updates.")
            return f"- Website ({name} - {url}): Currently {status}. Web telemetry: {summary}", {
                "title": f"Website: {name}",
                "content": f"Status: {status}. Telemetry: {summary}",
                "url": url
            }
            
    tasks = [process_asset(k, v) for k, v in assets.items()]
    asset_responses = await asyncio.gather(*tasks)
    
    for summary_text, link_data in asset_responses:
        results_summary.append(summary_text)
        search_results_list.append(link_data)
        
    return "\n".join(results_summary), search_results_list

async def local_synthesize_speech_to_b64(text: str) -> Optional[str]:
    # 0. Scrub markdown code blocks so they are not spoken
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)

    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    if "<think>" in text:
        text = text.split("<think>")[0]
        
    # 1b. Normalize Git pronunciation (force lowercase to avoid acronym reading)
    text = re.sub(r'\bGit\b', 'git', text)
    text = re.sub(r'\bGIT\b', 'git', text)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^[|\s\-:+\u2014]+$', stripped):
            continue
        cleaned_line = stripped.replace("|", " ").strip()
        if cleaned_line:
            cleaned_lines.append(cleaned_line)
    text = " ".join(cleaned_lines)
    text = text.replace("*", "").replace("`", "").replace("#", "").strip()
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return None
    try:
        communicate = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        if audio_data:
            return base64.b64encode(audio_data).decode("utf-8")
    except Exception as e:
        print(f"Startup Speech Synthesis Error: {e}")
    return None

async def handle_startup_sequence(session_id: str, use_tts: bool) -> AsyncGenerator[dict, None]:
    # Check if we have already run the daily report today
    today_str = datetime.date.today().isoformat()
    last_report_date = None
    memory_file = memory_service.memory_file
    if memory_file.exists():
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                memory_data = json.load(f)
                last_report_date = memory_data.get("last_daily_report_date")
        except Exception:
            pass

    # Determine the time-of-day greeting
    now = datetime.datetime.now()
    hour = now.hour
    if hour < 12:
        time_greeting = "Good morning"
    elif hour < 17:
        time_greeting = "Good afternoon"
    elif hour < 22:
        time_greeting = "Good evening"
    else:
        time_greeting = "Late night protocol active"

    if last_report_date == today_str:
        # Welcome back / standard boot sequence greeting without compiling the report
        welcome_back_choices = [
            f"{time_greeting if hour < 22 else 'Welcome back'}, Sir. All systems are operational. Today's intelligence briefing has already been delivered.",
            "All systems are online, Sir. Let me know what you need.",
            "Systems active, Sir. Ready for your instructions.",
            f"{time_greeting if hour < 22 else 'Welcome back'}, Sir. Global grids are stable. How can I assist you today?"
        ]
        greeting = random.choice(welcome_back_choices)
        yield {"chunk": greeting + "\n\n"}
        if use_tts:
            g_audio = await local_synthesize_speech_to_b64(greeting)
            if g_audio:
                yield {"audio": g_audio}
        return

    # 1. Immediate greeting response
    greeting_choices = [
        f"{time_greeting}, Sir. All primary systems are online. Initializing global scans and pulling today's telemetry now.",
        "Boot sequence complete, Sir. Syncing data logs and compiling today's intelligence report.",
        "Online and ready, Sir. Checking global grids and scanning the network for today's developments.",
        "Systems initialized, Sir. Connecting to news archives and gathering today's global updates."
    ]
    greeting = random.choice(greeting_choices)
    yield {"chunk": greeting + "\n\n"}
    if use_tts:
        g_audio = await local_synthesize_speech_to_b64(greeting)
        if g_audio:
            yield {"audio": g_audio}

    # 2. Telemetry Step
    yield {"activity": {"event": "telemetry", "message": "Gathering system telemetry..."}}
    telemetry = gather_system_telemetry()
    await asyncio.sleep(0.1)

    # 3. Global News Step
    yield {"activity": {"event": "global_news", "message": "Scanning global headlines..."}}
    world_news_task = realtime_service.search("today's top global news headlines")
    
    # 4. AI Releases Step
    yield {"activity": {"event": "ai_developments", "message": "Checking latest AI model releases..."}}
    # Query for open-code models, OpenCode Zen, OpenRouter free models, Blackbox AI, and Kilo Code AI
    ai_opencode_zen_task = realtime_service.search("new OpenCode AI models and free availability of Zen AI")
    ai_openrouter_task = realtime_service.search("OpenRouter new AI models and free availability")
    ai_blackbox_task = realtime_service.search("Blackbox AI coding assistant updates and free availability")
    ai_kilocode_task = realtime_service.search("Kilo Code AI extension releases and free availability")
    ai_general_task = realtime_service.search("latest open source AI models released today")
    
    # 5. Assets Step
    yield {"activity": {"event": "asset_status", "message": "Scanning registered personal assets..."}}
    assets_task = scan_monitored_assets(session_id)

    # Gather data concurrently
    world_res, res_zen, res_openrouter, res_blackbox, res_kilocode, res_general, (assets_summary, assets_links) = await asyncio.gather(
        world_news_task,
        ai_opencode_zen_task,
        ai_openrouter_task,
        ai_blackbox_task,
        ai_kilocode_task,
        ai_general_task,
        assets_task
    )

    # Combine AI search summaries and results
    ai_summary_parts = []
    ai_results_list = []
    
    for label, res in [
        ("OpenCode & Zen", res_zen),
        ("OpenRouter", res_openrouter),
        ("Blackbox AI", res_blackbox),
        ("Kilo Code AI", res_kilocode),
        ("General Open Source", res_general),
    ]:
        summary_text = res.get('summary', '').strip()
        if summary_text and summary_text != "No results found.":
            ai_summary_parts.append(f"[{label} Data]\n{summary_text}")
        ai_results_list.extend(res.get('results', []))
        
    ai_res = {
        "summary": "\n\n".join(ai_summary_parts) if ai_summary_parts else "No results",
        "results": ai_results_list
    }

    # 6. Synthesis Step
    yield {"activity": {"event": "synthesis", "message": "Compiling intelligence briefing..."}}
    
    from app.services.brain_service import get_dynamic_persona_envelope
    envelope = get_dynamic_persona_envelope()
    context = await memory_service.get_context(session_id)
    
    system_prompt = f"""You are {config.ASSISTANT_NAME}, a highly capable, self-aware AI tactical assistant (inspired by JARVIS).
{envelope}

{context}

You are compiling the daily startup intelligence briefing.
Here is the live data gathered from our telemetry and web scanners:

[SYSTEM METRICS]
- OS: {telemetry['os']}
- CPU Load: {telemetry['cpu_usage']}
- RAM Usage: {telemetry['ram_usage']}
- C Drive Space: {telemetry['disk_c']}
- D Drive Space: {telemetry['disk_d']}

[WORLD NEWS INTEL]
{world_res.get('summary', 'No results')}

[AI & TECHNOLOGY NEWS]
{ai_res.get('summary', 'No results')}

[MONITORED PERSONAL ASSETS]
{assets_summary}

Generate a briefing that is dynamic, engaging, and premium.

MANDATORY DIRECTIVES:
1. **Dynamic Tone**: Do not use standard templates or repetitive scripts. Let your tone be natural, direct, and conversational. Refer to the Focus Trait Angle in the envelope to guide your style.
2. **Proactive Diagnostics**: Mention system stats. If CPU is high, RAM is tight, or disk space is low, warn the user and suggest an action or a solution (e.g. "C Drive is running a bit heavy, Sir. I can clean up some temp caches if you'd like").
3. **AI Models & Free Access**: Detail recently released open-source and open-code models and their free availability. Explicitly identify and discuss the free availability and new models/updates on Zen (OpenCode Zen), OpenRouter (including their free models), Blackbox AI (the free coding assistant), and Kilo Code AI (the open-source extension, free credits, and local model support). Detail exactly how the user can access them for free.
4. **Personal Life & Assets**: Address the monitored assets. If there are none, note this fact proactively and explain how the user can register a website or YouTube channel for future briefings (e.g., "No custom sites are registered in my grid yet, Sir. Let me know when you launch one so I can initialize status telemetry"). If there are registered assets, summarize their status.
5. **Agency**: Suggest solutions to current user issues, mention what you can do (e.g., snap windows, set reminders, clean desktop, search files), and offer to perform a specific action right now.

Return ONLY a valid JSON object matching the following structure. Do not output raw markdown directly under key names; wrap all markdown inside a standard JSON string.

{{
  "chat": "A clean, highly conversational text block that will be read aloud. Must NOT contain any markdown, bullet points, asterisks, or bold tags. Keep it fluid, natural, and premium.",
  "sidebar": "A beautifully structured markdown report (max 300 words) with headers, lists, or tables for quick reading. IMPORTANT: This must be a single, valid JSON-escaped string with all newlines escaped as \\n and double quotes escaped as \\\"."
}}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the startup briefing now, Sir."}
    ]
    
    chat_text = ""
    sidebar_markdown = ""
    try:
        result = await ai_service.get_chat_completion(
            messages,
            model=config.GROQ_MODEL,
            response_format={"type": "json_object"},
            temperature=0.7
        )
        chat_text, sidebar_markdown = _extract_chat_and_sidebar_fallback(result or "{}")
    except Exception as e:
        # Check if the error has a failed_generation field (which is common in 400 Json Validate errors)
        failed_gen = None
        if hasattr(e, "body") and isinstance(e.body, dict):
            failed_gen = e.body.get("error", {}).get("failed_generation")
        
        if not failed_gen:
            # Try to extract from string representation of exception
            err_str = str(e)
            match = re.search(r"'failed_generation':\s*'(.*?)'\s*(?:}|\n)", err_str, re.DOTALL)
            if match:
                failed_gen = match.group(1)
            else:
                match_double = re.search(r'"failed_generation":\s*"(.*?)"\s*(?:}|\n)', err_str, re.DOTALL)
                if match_double:
                    failed_gen = match_double.group(1)
                    
        if failed_gen:
            try:
                # Normalize double-escaped newlines and double-quotes
                failed_gen_normalized = failed_gen.replace('\\\\n', '\\n').replace('\\\\"', '\\"')
                failed_gen_clean = failed_gen_normalized.encode().decode('unicode-escape', errors='ignore')
                chat_text, sidebar_markdown = _extract_chat_and_sidebar_fallback(failed_gen_clean)
            except Exception as parse_err:
                print(f"Failed to parse failed_generation fallback: {parse_err}")
                
        if not chat_text or not sidebar_markdown:
            chat_text = f"Apologies, Sir. I encountered an issue compiling the intelligence briefing: {e}"
            sidebar_markdown = f"### System Error\nFailed to compile briefing.\n\nError: {e}"
        
    if not chat_text:
        chat_text = "Briefing compiled, Sir. Check the sidebar for details."
    if not sidebar_markdown:
        sidebar_markdown = chat_text

    # Yield chat response chunks
    yield {"chunk": chat_text}
    
    # Yield sidebar results
    all_links = world_res.get("results", []) + ai_res.get("results", []) + assets_links
    yield {
        "search_results": {
            "query": "Startup Telemetry & Intelligence Briefing",
            "answer": sidebar_markdown,
            "results": all_links
        }
    }
    
    # Save the interaction to memory
    await memory_service.save_interaction(session_id, "INIT_AUTONOMOUS_STARTUP_SEQUENCE", chat_text)
    
    # Update last daily report date in memory
    try:
        await memory_service.update_memory("last_daily_report_date", today_str)
    except Exception as e:
        print(f"Error updating last daily report date in memory: {e}")
    
    # Yield TTS audio for the briefing text
    if use_tts and chat_text:
        sentences = re.split(
            r'(?<!\d\.)(?<!\d\!)(?<!\d\?)'
            r'(?<!\b[a-zA-Z]\.)'
            r'(?<!\b[dD][rR]\.)(?<!\b[mM][rR]\.)(?<!\b[mM][rR][sS]\.)'
            r'(?<=[.!?])(?:\s+|\n+)|\n\n+', 
            chat_text
        )
        for sentence in sentences:
            clean_sentence = sentence.replace("*", "").replace("#", "").strip()
            if clean_sentence:
                s_audio = await local_synthesize_speech_to_b64(clean_sentence)
                if s_audio:
                    yield {"audio": s_audio}
