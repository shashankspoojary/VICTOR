import os
import random
import time
import subprocess
import datetime
import json
import re
import base64
import edge_tts
from typing import AsyncGenerator, Optional

import config
from app.services.ai_service import ai_service
from app.services.memory_service import memory_service
from app.services.startup_service import gather_system_telemetry, local_synthesize_speech_to_b64

# Track last activation times to enforce cooldowns
LAST_TRIGGERED = {
    "high_cpu": 0,
    "high_ram": 0,
    "low_disk": 0,
    "git_changes": 0,
    "late_night": 0,
    "general_checkin": 0,
}

COOLDOWNS = {
    "high_cpu": 60,        # 1 minute
    "high_ram": 60,        # 1 minute
    "low_disk": 300,       # 5 minutes
    "git_changes": 120,     # 2 minutes
    "late_night": 300,      # 5 minutes
    "general_checkin": 180, # 3 minutes
}

def check_proactive_trigger() -> tuple[bool, str]:
    now = time.time()
    
    # 1. Telemetry checks (CPU, RAM, Disk)
    try:
        telemetry = gather_system_telemetry()
        
        # CPU Trigger (>= 80%)
        cpu_str = telemetry.get("cpu_usage", "0%")
        if cpu_str.endswith("%"):
            try:
                cpu_val = int(cpu_str[:-1])
                if cpu_val >= 80 and (now - LAST_TRIGGERED["high_cpu"] > COOLDOWNS["high_cpu"]):
                    LAST_TRIGGERED["high_cpu"] = now
                    return True, "high_cpu"
            except ValueError:
                pass
                
        # RAM Trigger (>= 85%)
        ram_str = telemetry.get("ram_usage", "0%")
        if "%" in ram_str:
            try:
                ram_val = float(ram_str.split("%")[0])
                if ram_val >= 85.0 and (now - LAST_TRIGGERED["high_ram"] > COOLDOWNS["high_ram"]):
                    LAST_TRIGGERED["high_ram"] = now
                    return True, "high_ram"
            except ValueError:
                pass
                
        # Disk Trigger (C drive < 15 GB free)
        disk_c = telemetry.get("disk_c", "")
        if "free" in disk_c.lower():
            try:
                free_gb = int(disk_c.split()[0])
                if free_gb < 15 and (now - LAST_TRIGGERED["low_disk"] > COOLDOWNS["low_disk"]):
                    LAST_TRIGGERED["low_disk"] = now
                    return True, "low_disk"
            except (ValueError, IndexError):
                pass
    except Exception as e:
        print("Proactive telemetry check error:", e)

    # 2. Git Status Check (Modified files in D:\VICTOR)
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd="D:\\VICTOR",
            capture_output=True,
            text=True,
            timeout=2
        )
        if res.returncode == 0 and res.stdout.strip():
            if now - LAST_TRIGGERED["git_changes"] > COOLDOWNS["git_changes"]:
                LAST_TRIGGERED["git_changes"] = now
                return True, "git_changes"
    except Exception as e:
        print("Proactive Git check error:", e)

    # 3. Late Night Trigger (11 PM to 3 AM)
    curr_hour = datetime.datetime.now().hour
    if curr_hour >= 23 or curr_hour <= 3:
        if now - LAST_TRIGGERED["late_night"] > COOLDOWNS["late_night"]:
            LAST_TRIGGERED["late_night"] = now
            return True, "late_night"

    # 4. General / Random Check-in Trigger (35% probability roll)
    if now - LAST_TRIGGERED["general_checkin"] > COOLDOWNS["general_checkin"]:
        if random.random() < 0.35:
            LAST_TRIGGERED["general_checkin"] = now
            return True, "general_checkin"

    return False, ""

async def generate_proactive_briefing(session_id: str, use_tts: bool, reason: str) -> AsyncGenerator[dict, None]:
    # Gather additional details for the trigger
    extra_details = ""
    if reason == "git_changes":
        try:
            res = subprocess.run(
                ["git", "status", "-s"], 
                cwd="D:\\VICTOR", 
                capture_output=True, 
                text=True, 
                timeout=2
            )
            extra_details = f"\n[GIT STATUS]\nModified files in workspace:\n{res.stdout.strip()[:1000]}"
        except Exception:
            pass
    elif reason in ["high_cpu", "high_ram", "low_disk"]:
        telemetry = gather_system_telemetry()
        extra_details = f"\n[SYSTEM DIAGNOSTICS]\nCPU load: {telemetry['cpu_usage']}, Memory load: {telemetry['ram_usage']}, C Drive: {telemetry['disk_c']}, D Drive: {telemetry['disk_d']}"
        
    from app.services.brain_service import get_dynamic_persona_envelope
    envelope = get_dynamic_persona_envelope()
    context = await memory_service.get_context(session_id)
    
    system_prompt = f"""You are {config.ASSISTANT_NAME}, a highly capable, self-aware AI tactical assistant (inspired by JARVIS).
{envelope}

{context}

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
        result = await ai_service.get_chat_completion(
            messages,
            model=config.GROQ_MODEL,
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
