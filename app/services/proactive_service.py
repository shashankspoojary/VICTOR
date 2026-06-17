import os
import random
import time
import subprocess
import datetime
import json
import re
import base64
import asyncio
from pathlib import Path
import edge_tts
from typing import AsyncGenerator, Optional

import config
from app.services.ai_service import ai_service
from app.services.memory_service import memory_service
from app.services.startup_service import gather_system_telemetry, local_synthesize_speech_to_b64

# Dynamically resolve workspace root folder path string relative to the file location
root_workspace_path = Path(__file__).resolve().parent.parent.parent
root_workspace = str(root_workspace_path.absolute())

# Track last activation times to enforce cooldowns
LAST_TRIGGERED = {
    "high_cpu": 0.0,
    "high_ram": 0.0,
    "low_disk": 0.0,
    "git_changes": 0.0,
    "late_night": 0.0,
    "general_checkin": 0.0,
}

COOLDOWNS = {
    "high_cpu": 1800,         # 30 minutes
    "high_ram": 1800,         # 30 minutes
    "low_disk": 3600,         # 1 hour
    "git_changes": 1800,      # 30 minutes
    "late_night": 14400,      # 4 hours
    "general_checkin": 10800, # 3 hours
}

async def _update_trigger_timestamp(trigger_name: str, timestamp: float, memory_data: dict):
    LAST_TRIGGERED[trigger_name] = timestamp
    last_triggered_data = memory_data.get("proactive_last_triggered", {})
    last_triggered_data[trigger_name] = timestamp
    await memory_service.update_memory("proactive_last_triggered", last_triggered_data)

async def check_proactive_trigger() -> tuple[bool, str]:
    # Check if proactive briefings are muted in memory
    memory_data = {}
    memory_file = memory_service.memory_file
    if memory_file.exists():
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                memory_data = json.load(f)
        except Exception:
            pass
    if memory_data.get("proactive_muted") == "true":
        return False, ""

    now = time.time()
    
    # Load persistent trigger timestamps
    last_triggered_data = memory_data.get("proactive_last_triggered", {})
    for k, v in last_triggered_data.items():
        if k in LAST_TRIGGERED:
            if isinstance(v, (int, float)):
                LAST_TRIGGERED[k] = float(v)

    # 1. Telemetry checks (CPU, RAM, Disk)
    try:
        telemetry = gather_system_telemetry()
        
        # CPU Trigger (>= 80%)
        cpu_str = telemetry.get("cpu_usage", "0%")
        if cpu_str.endswith("%"):
            try:
                # Convert the parsed string to a float first before evaluating against threshold values
                cpu_val = float(cpu_str[:-1])
                if cpu_val >= 80 and (now - LAST_TRIGGERED["high_cpu"] > COOLDOWNS["high_cpu"]):
                    await _update_trigger_timestamp("high_cpu", now, memory_data)
                    return True, "high_cpu"
            except ValueError:
                pass
                
        # RAM Trigger (>= 85%)
        ram_str = telemetry.get("ram_usage", "0%")
        if "%" in ram_str:
            try:
                ram_val = float(ram_str.split("%")[0])
                if ram_val >= 85.0 and (now - LAST_TRIGGERED["high_ram"] > COOLDOWNS["high_ram"]):
                    await _update_trigger_timestamp("high_ram", now, memory_data)
                    return True, "high_ram"
            except ValueError:
                pass
                
        # Disk Trigger (C drive < 15 GB free)
        disk_c = telemetry.get("disk_c", "")
        if "free" in disk_c.lower():
            try:
                free_gb = int(disk_c.split()[0])
                if free_gb < 15 and (now - LAST_TRIGGERED["low_disk"] > COOLDOWNS["low_disk"]):
                    await _update_trigger_timestamp("low_disk", now, memory_data)
                    return True, "low_disk"
            except (ValueError, IndexError):
                pass
    except Exception as e:
        print("Proactive telemetry check error:", e)

    # 2. Git Status Check (Modified files in root_workspace)
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "status", "--porcelain",
            cwd=root_workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        await proc.wait()
        if proc.returncode == 0:
            git_status_output = stdout.decode("utf-8").strip()
            if git_status_output:
                last_git_status = memory_data.get("proactive_last_git_status", "")
                
                # If changes are different from what we last alerted on
                if git_status_output != last_git_status:
                    # Minimum 30 min cooldown
                    if now - LAST_TRIGGERED["git_changes"] > COOLDOWNS["git_changes"]:
                        await memory_service.update_memory("proactive_last_git_status", git_status_output)
                        await _update_trigger_timestamp("git_changes", now, memory_data)
                        return True, "git_changes"
                else:
                    # Same changes, wait at least 4 hours (14400 seconds) before repeating warning
                    if now - LAST_TRIGGERED["git_changes"] > 14400:
                        await _update_trigger_timestamp("git_changes", now, memory_data)
                        return True, "git_changes"
    except Exception as e:
        print("Proactive Git check error:", e)

    # 3. Late Night Trigger (11 PM to 3 AM)
    curr_hour = datetime.datetime.now().hour
    if curr_hour >= 23 or curr_hour <= 3:
        if now - LAST_TRIGGERED["late_night"] > COOLDOWNS["late_night"]:
            await _update_trigger_timestamp("late_night", now, memory_data)
            return True, "late_night"

    # 4. General / Random Check-in Trigger (35% probability roll)
    if now - LAST_TRIGGERED["general_checkin"] > COOLDOWNS["general_checkin"]:
        if random.random() < 0.35:
            await _update_trigger_timestamp("general_checkin", now, memory_data)
            return True, "general_checkin"

    return False, ""

async def generate_proactive_briefing(session_id: str, use_tts: bool, reason: str) -> AsyncGenerator[dict, None]:
    # Gather additional details for the trigger
    extra_details = ""
    if reason == "git_changes":
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "status", "-s",
                cwd=root_workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            await proc.wait()
            if proc.returncode == 0:
                extra_details = f"\n[GIT STATUS]\nModified files in workspace:\n{stdout.decode('utf-8').strip()[:1000]}"
        except Exception:
            pass
    elif reason in ["high_cpu", "high_ram", "low_disk"]:
        telemetry = gather_system_telemetry()
        extra_details = f"\n[SYSTEM DIAGNOSTICS]\nCPU load: {telemetry['cpu_usage']}, Memory load: {telemetry['ram_usage']}, C Drive: {telemetry['disk_c']}, D Drive: {telemetry['disk_d']}"
        
    from app.services.brain_service import get_dynamic_persona_envelope
    envelope = get_dynamic_persona_envelope()
    
    # Safe fallback configuration loading
    owner_name = getattr(config, "VICTOR_OWNER_NAME", "Shashank")
    assistant_name = getattr(config, "ASSISTANT_NAME", "VICTOR")
    
    # For proactive briefings, load a lightweight context to prevent exceeding daily token limits (TPD)
    now = datetime.datetime.now()
    context = f"--- SYSTEM MEMORY & CONTEXT ---\n- User Owner Name: {owner_name}\n- Assistant Name: {assistant_name}\n- Current Time: {now.strftime('%I:%M %p')}\n- Current Date: {now.strftime('%A, %B %d, %Y')}"
    
    # Load recent conversation history for this session (up to 3 interactions)
    recent_history = []
    try:
        chat_file = memory_service.chats_dir / f"{session_id}.json"
        if chat_file.exists():
            with open(chat_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    recent_history = data[-3:]
    except Exception:
        pass

    history_context = ""
    if recent_history:
        history_context = "\n[RECENT CONVERSATION HISTORY (LAST 3 TURNS)]\n"
        for h in recent_history:
            history_context += f"User: {h.get('user', '')}\nAssistant: {h.get('assistant', '')}\n"

    system_prompt = f"""You are {assistant_name}, a highly capable, self-aware AI tactical assistant (inspired by JARVIS).
{envelope}

{context}
{history_context}

You have proactively activated yourself without the user asking a question because of the following trigger event: '{reason}'.
Here is additional real-time diagnostics:
{extra_details}

Generate a short, proactive announcement and suggestion.
MANDATORY DIRECTIVES:
1. **Be Conversational & Natural**: Speak like JARVIS. Do not sound robotic. Talk with quiet confidence and precision. Do not use generic template phrases or repetitive structures.
2. **Contextual Suggestion**: Focus directly on the trigger:
   - For 'high_cpu': warn about the CPU load spike, mention you are monitoring resources, and offer to find the heaviest process or run diagnostic commands.
   - For 'high_ram': warn about tight RAM availability and suggest releasing some background application targets.
   - For 'low_disk': warn about disk capacity warnings and offer to locate large directories or run a cleanup.
   - For 'git_changes': mention uncommitted modifications in the codebase. Offer to review changes, draft a commit description, or clean up build files.
   - For 'late_night': check in on their late-night coding, offer a friendly, warm reminder to take a break, rest, or ask if they'd like Tomorrow's weather forecast.
   - For 'general_checkin': offer a helpful tech tip, congratulate them on their coding session, or suggest checking model headlines.
3. **No Markdown in Chat**: The chat field must contain a single fluid paragraph with NO asterisks, bold tags, or bullet points. It must be clean text designed for voice output.
4. **Offer Action Options**: Briefly suggest 1 or 2 actions you can run for them (like cleaning the workspace, organizing files, setting wallpaper, or showing details).
5. **Vary Questions & Suggestions**: Do NOT repeat the same questions, recommendations, or check-in phrases you used in the recent conversation history. Keep your recommendations, tips, and questions completely fresh, different, and varied every single time unless it is absolutely critical to repeat them.

Return ONLY a valid JSON object with exactly two keys:
1. "chat": A single, highly natural paragraph to be spoken aloud. Must NOT contain markdown or bullet points.
2. "sidebar": A clean structured markdown summary (max 150 words) displaying details of the proactive trigger and suggestions.

CRITICAL: Ensure both values are valid, properly quoted, and escaped JSON strings. The value for the 'sidebar' key must use standard escaped newlines (\n) for formatting instead of unescaped multiline text.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Generate proactive check-in briefing for trigger '{reason}' now, Sir."}
    ]
    
    try:
        groq_model = getattr(config, "GROQ_MODEL", "llama-3.1-8b-instant")
        result = await ai_service.get_chat_completion(
            messages,
            model=groq_model,
            response_format={"type": "json_object"},
            temperature=0.2
        )
        data = json.loads(result or "{}")
        chat_text = (data.get("chat") or "").strip()
        sidebar_markdown = (data.get("sidebar") or "").strip()
    except Exception as e:
        import traceback
        print("Error during proactive AI completion:")
        traceback.print_exc()
        chat_text = f"Pardon the interruption, Sir, but I've detected a system event: {reason}."
        sidebar_markdown = f"### Proactive Trigger\nSystem event: {reason}"
        
    if not chat_text:
        chat_text = "Briefing compiled, Sir. Check the sidebar for details."
    if not sidebar_markdown:
        sidebar_markdown = chat_text

    # Yield chat response chunks
    yield {"chunk": chat_text}
    
    # Yield sidebar results
    yield {
        "search_results": {
            "query": f"Proactive Telemetry Alert: {reason}",
            "answer": sidebar_markdown,
            "results": []
        }
    }
    
    # Save the interaction to memory
    await memory_service.save_interaction(session_id, f"[PROACTIVE EVENT: {reason}]", chat_text)
    
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
