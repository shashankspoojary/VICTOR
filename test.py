import uuid
import asyncio
import httpx
import re

from rich.console import Console
from rich.live import Live

from app.utils.formatter import (
    print_system_status,
    format_bot_message
)

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style

# V5: Voice System Core Infrastructure
from app.services.brain_service import BrainService
from app.services.speech_pipeline_service import SpeechPipelineService
from app.utils.voice_utils import sanitize_for_tts

# =========================================
# CONSOLE INFRASTRUCTURE
# =========================================
console = Console()
API_URL = "http://127.0.0.1:8000/api/chat"

# =========================================
# GLOBAL RUNTIME MULTIMODAL STATES
# =========================================
MODES = ["STANDARD MODE", "REALTIME SEARCH", "VOICE MODE"]
MENU_ITEMS = [
    "STANDARD MODE",
    "REALTIME SEARCH",
    "VOICE MODE",
    "TOGGLE MIC (VOICE INPUT)",
    "TOGGLE TTS (VOICE OUTPUT)"
]
current_mode_index = 0
current_selection_index = 0

voice_input_enabled = False
voice_output_enabled = False
show_mode_panel = False
hide_panel_task = None 


# =========================================
# BANNER DISPLAY
# =========================================
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
    console.print(f"[bold cyan]{banner}[/bold cyan]")


# =========================================
# SYSTEM-WIDE STREAM SPLITTER UTILITY
# =========================================
async def process_streaming_tts(buffer_text: str, output_service) -> str:
    """Analyzes accumulated text, extracts complete sentences, and passes them to TTS."""
    sentences = re.split(r'(?<=[.!?])\s+|\n', buffer_text)
    
    if sentences and not sentences[-1].endswith(('.', '!', '?')):
        remaining_buffer = sentences.pop()
    else:
        remaining_buffer = ""
        
    for sentence in sentences:
        clean = sanitize_for_tts(sentence)
        if len(clean.strip()) > 1:
            await output_service.speak(clean)
            
    return remaining_buffer


# =========================================
# STREAM RESPONSE (Standard & Realtime)
# =========================================
async def stream_response(
    session_id: str,
    message: str,
    use_search: bool,
    output_service,
    voice_output_enabled: bool
):
    payload = {
        "session_id": session_id,
        "message": message,
        "use_search": use_search
    }

    full_text = ""
    sentence_buffer = ""

    try:
        timeout_config = httpx.Timeout(180.0, connect=15.0, read=165.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream("POST", API_URL, json=payload) as response:
                response.raise_for_status()

                with Live(format_bot_message(""), refresh_per_second=20, console=console) as live:
                    async for chunk in response.aiter_text():
                        if chunk:
                            full_text += chunk
                            live.update(format_bot_message(full_text))

                            if voice_output_enabled and output_service:
                                sentence_buffer += chunk
                                sentence_buffer = await process_streaming_tts(sentence_buffer, output_service)

        if voice_output_enabled and output_service and sentence_buffer.strip():
            clean_text = sanitize_for_tts(sentence_buffer)
            if len(clean_text) > 1:
                await output_service.speak(clean_text)

    except httpx.ConnectError:
        console.print("[bold red]ERROR:[/bold red] Unable to connect to VICTOR backend server.")
    except Exception as e:
        console.print(f"[bold red]System Processing Error:[/bold red] {str(e)}")

    console.print()


# =========================================
# ASYNC CONCURRENT MICROPHONE MONITOR
# =========================================
async def continuous_mic_monitor(session, speech_pipeline):
    """Monitors incoming background voice queries concurrently without blocking user text input."""
    while True:
        try:
            if MODES[current_mode_index] == "VOICE MODE" or voice_input_enabled:
                speech_pipeline.input_service.start_continuous_listening()
                phrase = await speech_pipeline.input_service.get_next_phrase()
                
                if phrase and phrase.strip():
                    if session.app and session.app.is_running:
                        session.app.exit(result=f"__voice_phrase__:{phrase}")
            else:
                speech_pipeline.input_service.stop_continuous_listening()
        except Exception:
            pass
        await asyncio.sleep(0.05)


# =========================================
# FUZZY NATURAL SYSTEM COMMAND INTERCEPTOR
# =========================================
async def intercept_system_state_command(user_input: str, speech_pipeline) -> str:
    """
    Parses conversational phrasings flexibly using keyword matching heuristic paths.
    Executes changes client-side instantly and requests unique system report phrasing from the brain.
    """
    global current_mode_index, voice_input_enabled, voice_output_enabled
    clean = user_input.lower().strip().replace("-", " ")

    # 1. Check for Exit/Quit Request
    if clean in ["exit", "quit", "exit system", "quit system"]:
        speech_pipeline.output_service.stop()
        return "EXIT"

    event_context = None

    # 2. Check for Realtime Search Mode Requests
    if ("realtime" in clean or "real time" in clean) and ("mode" in clean or "search" in clean or "switch" in clean or "activate" in clean or "enable" in clean):
        current_mode_index = 1
        event_context = "User switched the execution layout to Realtime Internet Search Mode."

    # 3. Check for Standard Mode Requests
    elif "standard" in clean and ("mode" in clean or "switch" in clean or "revert" in clean or "activate" in clean or "enable" in clean):
        current_mode_index = 0
        event_context = "User reverted system operations back to Standard Processing Mode."

    # 4. Check for Voice Mode Override Requests
    elif "voice" in clean and ("mode" in clean or "switch" in clean or "activate" in clean or "enable" in clean):
        current_mode_index = 2
        voice_input_enabled = True
        voice_output_enabled = True
        event_context = "User locked operations into full interactive Voice Mode, initializing continuous microphone tracking and audio speech synthesis."

    # 5. Check for Voice Input/Microphone Toggles
    elif "mic" in clean or "microphone" in clean or "voice input" in clean:
        if any(act in clean for act in ["on", "enable", "activate", "start", "turn on"]):
            if current_mode_index == 2:
                console.print("[bold yellow]Action Denied: Microphone locked ON while inside Voice Mode.[/bold yellow]")
                return "HANDLED"
            voice_input_enabled = True
            event_context = "User turned on the microphone array to enable continuous voice input processing."
        elif any(act in clean for act in ["off", "disable", "stop", "deactivate", "turn off"]):
            if current_mode_index == 2:
                console.print("[bold yellow]Action Denied: Microphone locked ON while inside Voice Mode.[/bold yellow]")
                return "HANDLED"
            voice_input_enabled = False
            speech_pipeline.input_service.stop_continuous_listening()
            event_context = "User deactivated the microphone array, shutting down background voice listening loops."

    # 6. Check for Voice Output/TTS Toggles
    elif "tts" in clean or "speaker" in clean or "voice output" in clean or "reading" in clean:
        if any(act in clean for act in ["on", "enable", "activate", "start", "turn on"]):
            voice_output_enabled = True
            event_context = "User enabled the speaker array and text-to-speech audio feedback feedback loop."
        elif any(act in clean for act in ["off", "disable", "stop", "deactivate", "turn off"]):
            if current_mode_index == 2:
                console.print("[bold yellow]Action Denied: Voice Output locked ON while inside Voice Mode.[/bold yellow]")
                return "HANDLED"
            voice_output_enabled = False
            speech_pipeline.output_service.stop()
            event_context = "User turned off text-to-speech feedback, siloncing vocal outputs."

    # Process Dynamic Evaluation if an Event Match hit
    if event_context:
        speech_pipeline.output_service.stop()
        dynamic_report = await speech_pipeline.brain_service.generate_system_report(event_context)
        
        # Output colorization matching action intent
        prefix = "🔊" if voice_output_enabled else "🔇"
        console.print(f"[bold green]{prefix} {dynamic_report}[/bold green]")
        
        if voice_output_enabled:
            asyncio.create_task(speech_pipeline.output_service.speak(dynamic_report))
        return "HANDLED"

    return "PROCESS_LLM"


# =========================================
# APPLICATION CORE ENTRY INTERFACE
# =========================================
async def main():
    global current_mode_index, current_selection_index, voice_input_enabled, voice_output_enabled, show_mode_panel, hide_panel_task

    console.clear()
    print_system_status("Initializing VICTOR Terminal Interface...")
    print_system_status("Loading Cognitive Systems...")
    print_system_status("Establishing Secure Session...")

    session_id = str(uuid.uuid4())
    print_system_status(f"Session ID: {session_id}")
    print_system_status("System Status: ONLINE\n")

    print_banner()

    brain = BrainService()
    speech_pipeline = SpeechPipelineService(brain)

    bindings = KeyBindings()

    def reset_hide_timer(event):
        global hide_panel_task
        if hide_panel_task:
            hide_panel_task.cancel()
            
        async def _hide_timer():
            try:
                await asyncio.sleep(4.5)
                global show_mode_panel
                show_mode_panel = False
                event.app.invalidate()
            except asyncio.CancelledError:
                pass
                
        hide_panel_task = asyncio.create_task(_hide_timer())

    @bindings.add("up")
    def _(event):
        global current_selection_index, show_mode_panel
        if not show_mode_panel:
            show_mode_panel = True
        else:
            current_selection_index = (current_selection_index - 1) % len(MENU_ITEMS)
        event.app.invalidate()
        reset_hide_timer(event)

    @bindings.add("down")
    def _(event):
        global current_selection_index, show_mode_panel
        if not show_mode_panel:
            show_mode_panel = True
        else:
            current_selection_index = (current_selection_index + 1) % len(MENU_ITEMS)
        event.app.invalidate()
        reset_hide_timer(event)

    @bindings.add("enter")
    def _(event):
        global current_selection_index, show_mode_panel, current_mode_index, voice_input_enabled, voice_output_enabled
        
        if show_mode_panel:
            selection = MENU_ITEMS[current_selection_index]
            show_mode_panel = False
            # Route layout configurations directly down into the event breakout string parser
            event.app.exit(result=f"__v5_menu_selection__:{selection}")
        else:
            event.app.current_buffer.validate_and_handle()

    def bottom_toolbar():
        mode_str = MODES[current_mode_index]
        mic_str = "ON" if voice_input_enabled else "OFF"
        tts_str = "ON" if voice_output_enabled else "OFF"

        if not show_mode_panel:
            return HTML(
                f'<style fg="ansibrightblack">'
                f'[UP/DOWN] Open Cursor Menu  |  MODE: {mode_str}  |  MIC: {mic_str}  |  TTS: {tts_str}'
                f'</style>'
            )

        lines = [f'<style fg="ansiyellow">=== VICTOR INTERACTIVE SELECTION CURSOR ===</style>']
        for i, item in enumerate(MENU_ITEMS):
            status_suffix = ""
            if item == "TOGGLE MIC (VOICE INPUT)":
                status_suffix = f" (Current: {'ON' if voice_input_enabled else 'OFF'})"
            elif item == "TOGGLE TTS (VOICE OUTPUT)":
                status_suffix = f" (Current: {'ON' if voice_output_enabled else 'OFF'})"
            elif item == "STANDARD MODE" and current_mode_index == 0:
                status_suffix = " [ACTIVE]"
            elif item == "REALTIME SEARCH" and current_mode_index == 1:
                status_suffix = " [ACTIVE]"
            elif item == "VOICE MODE" and current_mode_index == 2:
                status_suffix = " [ACTIVE]"

            if i == current_selection_index:
                lines.append(f'<b><style bg="ansired" fg="ansiwhite"> > {item}{status_suffix} [Press ENTER] </style></b>')
            else:
                lines.append(f'<style fg="ansiwhite">   {item}{status_suffix}</style>')
                
        return HTML("\n".join(lines))

    custom_style = Style.from_dict({"bottom-toolbar": "bg:default fg:default noreverse"})
    session = PromptSession(bottom_toolbar=bottom_toolbar, key_bindings=bindings, style=custom_style)

    asyncio.create_task(continuous_mic_monitor(session, speech_pipeline))

    # =====================================
    # CONTINUOUS PROCESSING INTERFACE LOOP
    # =====================================
    while True:
        try:
            user_input = await session.prompt_async("\nUser: ")

            if not user_input or not user_input.strip():
                continue

            if user_input == "__v5_state_change__":
                continue

            # Intercept layout cursor changes, translate to direct action commands
            if user_input.startswith("__v5_menu_selection__:"):
                target_item = user_input.replace("__v5_menu_selection__:", "")
                if target_item == "STANDARD MODE":
                    user_input = "switch to standard mode"
                elif target_item == "REALTIME SEARCH":
                    user_input = "switch to real time search mode"
                elif target_item == "VOICE MODE":
                    user_input = "switch to voice mode"
                elif target_item == "TOGGLE MIC (VOICE INPUT)":
                    user_input = "turn off mic" if voice_input_enabled else "turn on mic"
                elif target_item == "TOGGLE TTS (VOICE OUTPUT)":
                    user_input = "turn off voice output" if voice_output_enabled else "turn on voice output"

            # Process voice phrases extracted via concurrent background queue monitor
            if user_input.startswith("__voice_phrase__:"):
                user_input = user_input.replace("__voice_phrase__:", "")
                console.print(f"\n[bold cyan]User (Voice):[/bold cyan] {user_input}")

            # Smart Heuristic Intercept Evaluation Pass
            status = await intercept_system_state_command(user_input, speech_pipeline)
            
            if status == "HANDLED":
                continue  
            elif status == "EXIT":
                speech_pipeline.output_service.stop()
                print_system_status("Terminating VICTOR session. Goodbye.")
                break

            # Core Request Route Distribution with Persistent Barge-In Hooks
            if MODES[current_mode_index] in ["STANDARD MODE", "REALTIME SEARCH"]:
                speech_pipeline.output_service.stop()

                await stream_response(
                    session_id=session_id,
                    message=user_input,
                    use_search=(MODES[current_mode_index] == "REALTIME SEARCH"),
                    output_service=speech_pipeline.output_service,
                    voice_output_enabled=voice_output_enabled
                )

            elif MODES[current_mode_index] == "VOICE MODE":
                try:
                    speech_pipeline.output_service.stop()

                    # Direct execution bypass to enforce voice system constraints natively
                    response_generator = speech_pipeline.brain_service.process_chat(
                        session_id=session_id,
                        user_message=user_input,
                        use_search=False,
                        is_voice=True
                    )

                    full_text = ""
                    sentence_buffer = ""

                    with Live(format_bot_message(""), refresh_per_second=20, console=console) as live:
                        async for chunk in response_generator:
                            if chunk:
                                full_text += chunk
                                live.update(format_bot_message(full_text))
                                
                                if voice_output_enabled:
                                    sentence_buffer += chunk
                                    sentence_buffer = await process_streaming_tts(sentence_buffer, speech_pipeline.output_service)

                    if voice_output_enabled and sentence_buffer.strip():
                        clean_text = sanitize_for_tts(sentence_buffer)
                        if len(clean_text) > 1:
                            await speech_pipeline.output_service.speak(clean_text)
                            
                except Exception as e:
                    console.print(f"[bold red]Voice Pipeline Execution Error:[/bold red] {str(e)}")

        except KeyboardInterrupt:
            speech_pipeline.output_service.stop()
            print_system_status("\nEmergency termination instruction registered.")
            break
        except Exception as e:
            console.print(f"[bold red]Fatal System Loop Error:[/bold red] {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())