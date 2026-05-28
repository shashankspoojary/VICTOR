import os
# Force Windows to process ANSI escape sequences properly
os.system("")

import asyncio
import httpx
import re
import sys
from datetime import datetime

from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.patch_stdout import patch_stdout

# =========================================
# CONSOLE & CONFIG
# =========================================
API_BASE = "http://127.0.0.1:8000/api"
CHAT_URL = f"{API_BASE}/chat"
WAKE_URL = f"{API_BASE}/v5/voice/wake"
LISTEN_URL = f"{API_BASE}/v5/voice/listen"
SPEAK_URL = f"{API_BASE}/v5/voice/speak"

# =========================================
# GLOBAL STATES & ASYNC QUEUES
# =========================================
MODES = ["STANDARD MODE", "REALTIME SEARCH", "AUTONOMOUS VOICE"]
current_mode_index = 0
show_mode_panel = False
session_id = "victor_master_session" 

audio_queue = asyncio.Queue()
voice_task = None

# =========================================
# HELPER FUNCTIONS
# =========================================
def sys_print(message: str):
    """Native glitch-free status printing."""
    print_formatted_text(HTML(f'<ansiyellow><b>System:</b> {message}</ansiyellow>'))

def print_banner():
    banner = r"""
██╗   ██╗██╗ ██████╗████████╗ ██████╗ ██████╗
██║   ██║██║██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗
██║   ██║██║██║        ██║   ██║   ██║██████╔╝
╚██╗ ██╔╝██║██║        ██║   ██║   ██║██╔══██╗
 ╚████╔╝ ██║╚██████╗   ██║   ╚██████╔╝██║  ██║
  ╚═══╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝

Versatile Intelligent Cognitive Tactical Operational Response
"""
    print_formatted_text(HTML(f'<ansicyan><b>{banner}</b></ansicyan>'))

# =========================================
# BACKGROUND AUDIO WORKER
# =========================================
async def audio_worker():
    """Monitors the queue and sends phrases to the backend API instantly."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        while True:
            try:
                text = await audio_queue.get()
                if text.strip():
                    await client.post(SPEAK_URL, json={"text": text})
                audio_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                pass 

# =========================================
# GLITCH-FREE TEXT & VOICE PIPELINE
# =========================================
async def stream_response(sess_id: str, message: str, use_search: bool):
    """Streams text naturally and queues rapid-fire phrases to the audio worker."""
    payload = {
        "session_id": sess_id,
        "message": message,
        "use_search": use_search
    }
    full_text = ""
    sentence_buffer = ""
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", CHAT_URL, json=payload) as response:
                response.raise_for_status()
                
                # Start on a fresh line with NO headers/prefixes
                print_formatted_text("\n", end="")
                
                async for chunk in response.aiter_text():
                    if chunk:
                        full_text += chunk
                        sentence_buffer += chunk
                        
                        # Use prompt_toolkit's native printer to guarantee visibility without garbage text
                        print_formatted_text(chunk, end="")
                        
                        match = re.search(r'([.!?\n])', sentence_buffer)
                        if match:
                            split_idx = match.end()
                            chunk_to_speak = sentence_buffer[:split_idx]
                            sentence_buffer = sentence_buffer[split_idx:]
                            
                            if len(chunk_to_speak.strip()) > 2:
                                audio_queue.put_nowait(chunk_to_speak.strip())
                                
            if len(sentence_buffer.strip()) > 2:
                audio_queue.put_nowait(sentence_buffer.strip())
                
    except httpx.ConnectError:
        print_formatted_text(HTML('\n<ansired><b>ERROR:</b> Unable to connect to backend server. Is run.py running?</ansired>'))
    except (KeyboardInterrupt, asyncio.CancelledError):
        print_formatted_text(HTML('\n<ansiyellow><b>⚡ Process interrupted by user.</b></ansiyellow>'))
    except Exception as e:
        print_formatted_text(HTML(f'\n<ansired><b>Unexpected Error:</b> {str(e)}</ansired>'))
    
    print_formatted_text("\n") 

# =========================================
# AUTONOMOUS VOICE STATE MACHINE
# =========================================
async def voice_worker(sess_id: str):
    print_formatted_text(HTML('\n<ansigreen><b>=======================================================</b></ansigreen>'))
    print_formatted_text(HTML('<ansigreen><b> 🎙️ AUTONOMOUS VOICE MODE ACTIVATED </b></ansigreen>'))
    print_formatted_text(HTML('<ansigreen><b> Speak "Victor" to wake him up. (Press UP/DOWN arrows to exit) </b></ansigreen>'))
    print_formatted_text(HTML('<ansigreen><b>=======================================================</b></ansigreen>\n'))

    state = "SLEEPING"
    silence_count = 0

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            while True:
                if state == "SLEEPING":
                    response = await client.post(WAKE_URL)
                    if response.status_code == 200 and response.json().get("woke_up"):
                        print_formatted_text(HTML('\n\n<ansiyellow><b>[!] WAKE WORD DETECTED! Victor is listening...</b></ansiyellow>'))
                        state = "AWAKE"
                        silence_count = 0
                    else:
                        await asyncio.sleep(0.5)

                elif state == "AWAKE":
                    response = await client.get(LISTEN_URL)
                    if response.status_code == 200:
                        user_text = response.json().get("text", "").lower()
                        
                        if user_text:
                            silence_count = 0
                            print_formatted_text(HTML(f'\n<ansiblue><b>👤 You (Voice):</b></ansiblue> {user_text}'))

                            sleep_commands = ["go to sleep", "sleep", "stop listening", "goodbye"]
                            if any(cmd in user_text for cmd in sleep_commands):
                                print_formatted_text(HTML('<ansicyan>🌙 Victor is returning to sleep mode.</ansicyan>'))
                                audio_queue.put_nowait("Going to sleep mode. Standing by.")
                                state = "SLEEPING"
                                continue

                            await stream_response(sess_id, user_text, use_search=False)
                            
                        else:
                            silence_count += 1
                            if silence_count >= 3:
                                print_formatted_text(HTML('<ansicyan>🌙 No voice activity. Returning to sleep.</ansicyan>'))
                                state = "SLEEPING"
                    else:
                        await asyncio.sleep(2)
                        
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print_formatted_text(HTML(f'<ansired><b>Voice Error:</b> {e}</ansired>'))

# =========================================
# MODE SWITCHER LOGIC
# =========================================
def handle_mode_switch():
    global voice_task
    if current_mode_index == 2:
        if voice_task is None or voice_task.done():
            voice_task = asyncio.create_task(voice_worker(session_id))
    else:
        if voice_task and not voice_task.done():
            voice_task.cancel()
            print_formatted_text(HTML('\n<ansiyellow><b>🎙️ Voice Mode Deactivated.</b></ansiyellow>'))

# =========================================
# MAIN LOOP
# =========================================
async def main():
    global current_mode_index, show_mode_panel

    asyncio.create_task(audio_worker())

    # Clear terminal safely
    print('\033c', end='')
    
    sys_print("Initializing VICTOR Terminal Interface...")
    sys_print("Loading Multimodal Systems...")
    
    # Generate a brand new, unique session file for every run using a timestamp
    global session_id
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    sys_print(f"Session ID: {session_id}")
    sys_print("System Status: ONLINE\n")

    print_banner()

    bindings = KeyBindings()

    @bindings.add("up")
    def _(event):
        global current_mode_index, show_mode_panel
        show_mode_panel = True
        current_mode_index = (current_mode_index - 1) % len(MODES)
        handle_mode_switch()
        event.app.invalidate()
        asyncio.create_task(hide_panel(event))

    @bindings.add("down")
    def _(event):
        global current_mode_index, show_mode_panel
        show_mode_panel = True
        current_mode_index = (current_mode_index + 1) % len(MODES)
        handle_mode_switch()
        event.app.invalidate()
        asyncio.create_task(hide_panel(event))

    async def hide_panel(event):
        await asyncio.sleep(1.2)
        globals()["show_mode_panel"] = False
        event.app.invalidate()

    def bottom_toolbar():
        if show_mode_panel:
            lines = []
            for i, mode in enumerate(MODES):
                if i == current_mode_index:
                    lines.append(f'<b><style bg="ansired" fg="ansiwhite"> > {mode} </style></b>')
                else:
                    lines.append(f'<style fg="ansiwhite">   {mode} </style>')
            return HTML('\n'.join(lines))
        else:
            return HTML(f'<style fg="ansibrightblack">[UP/DOWN] MODE: {MODES[current_mode_index]}</style>')

    custom_style = Style.from_dict({"bottom-toolbar": "bg:default fg:default noreverse"})
    
    session = PromptSession(
        bottom_toolbar=bottom_toolbar,
        key_bindings=bindings,
        style=custom_style
    )

    with patch_stdout():
        while True:
            try:
                if current_mode_index == 2:
                    prompt_text = "\n[VOICE ACTIVE] Speak out loud, or type here: "
                elif current_mode_index == 1:
                    prompt_text = "\n[SEARCH MODE] User: "
                else:
                    prompt_text = "\nUser: "

                user_input = await session.prompt_async(prompt_text)

                if user_input.lower() in ["exit", "quit"]:
                    sys_print("\nTerminating VICTOR session. Goodbye.")
                    break

                if not user_input.strip():
                    continue

                await stream_response(
                    sess_id=session_id,
                    message=user_input,
                    use_search=(current_mode_index == 1)
                )

            except KeyboardInterrupt:
                sys_print("\n[bold yellow]⚡ System shutdown initiated by user (Ctrl+C). Goodbye.[/bold yellow]")
                break
            except EOFError:
                break
            except Exception as e:
                print_formatted_text(HTML(f'<ansired><b>Fatal Error:</b> {str(e)}</ansired>'))

if __name__ == "__main__":
    asyncio.run(main())