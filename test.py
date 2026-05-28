import uuid
import asyncio
import httpx

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


# =========================================
# CONSOLE
# =========================================
console = Console()

API_URL = "http://127.0.0.1:8000/api/chat"


# =========================================
# GLOBAL STATES
# =========================================
search_mode_active = False
show_mode_panel = False


# =========================================
# BANNER
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

    console.print(
        f"[bold cyan]{banner}[/bold cyan]"
    )


# =========================================
# STREAM RESPONSE
# =========================================
async def stream_response(
    session_id: str,
    message: str,
    use_search: bool
):

    payload = {
        "session_id": session_id,
        "message": message,
        "use_search": use_search
    }

    full_text = ""

    try:

        async with httpx.AsyncClient(
            timeout=30.0
        ) as client:

            async with client.stream(
                "POST",
                API_URL,
                json=payload
            ) as response:

                response.raise_for_status()

                with Live(
                    format_bot_message(""),
                    refresh_per_second=20,
                    console=console
                ) as live:

                    async for chunk in response.aiter_text():

                        if chunk:

                            full_text += chunk

                            live.update(
                                format_bot_message(
                                    full_text
                                )
                            )

    except httpx.ConnectError:

        console.print(
            "[bold red]ERROR:[/bold red] "
            "Unable to connect to backend server."
        )

    except httpx.TimeoutException:

        console.print(
            "[bold red]ERROR:[/bold red] "
            "Request timed out."
        )

    except httpx.HTTPStatusError as e:

        console.print(
            f"[bold red]HTTP ERROR:[/bold red] "
            f"{e.response.status_code}"
        )

    except Exception as e:

        console.print(
            f"[bold red]Unexpected Error:[/bold red] "
            f"{str(e)}"
        )

    console.print()


# =========================================
# MAIN LOOP
# =========================================
async def main():

    global search_mode_active
    global show_mode_panel

    console.clear()

    # -------------------------------------
    # SYSTEM STARTUP
    # -------------------------------------
    print_system_status(
        "Initializing VICTOR Terminal Interface..."
    )

    print_system_status(
        "Loading Cognitive Systems..."
    )

    print_system_status(
        "Establishing Secure Session..."
    )

    session_id = str(uuid.uuid4())

    print_system_status(
        f"Session ID: {session_id}"
    )

    print_system_status(
        "System Status: ONLINE\n"
    )

    print_banner()

    # =====================================
    # KEYBINDINGS
    # =====================================
    bindings = KeyBindings()

    # -------------------------------------
    # LEFT = STANDARD MODE
    # -------------------------------------
    @bindings.add("up")
    def _(event):

        global search_mode_active
        global show_mode_panel

        # Show panel
        show_mode_panel = True

        # Select standard mode
        search_mode_active = False

        # Refresh UI
        event.app.invalidate()

        # Auto hide panel
        async def hide_panel():

            await asyncio.sleep(0.8)

            globals()["show_mode_panel"] = False

            event.app.invalidate()

        asyncio.create_task(
            hide_panel()
        )

    # -------------------------------------
    # RIGHT = REALTIME SEARCH
    # -------------------------------------
    @bindings.add("down")
    def _(event):

        global search_mode_active
        global show_mode_panel

        # Show panel
        show_mode_panel = True

        # Select realtime search
        search_mode_active = True

        # Refresh UI
        event.app.invalidate()

        # Auto hide panel
        async def hide_panel():

            await asyncio.sleep(0.8)

            globals()["show_mode_panel"] = False

            event.app.invalidate()

        asyncio.create_task(
            hide_panel()
        )

    # =====================================
    # DYNAMIC TOOLBAR
    # =====================================
    def bottom_toolbar():

        # ---------------------------------
        # COLLAPSED TOOLBAR
        # ---------------------------------
        if not show_mode_panel:

            current_mode = (
                "REALTIME SEARCH"
                if search_mode_active
                else "STANDARD MODE"
            )

            return HTML(
                '<style fg="ansibrightblack">'
                f'[UP/DOWN] MODE: '
                f'{current_mode}'
                '</style>'
            )

        # ---------------------------------
        # EXPANDED PANEL
        # ---------------------------------
        if not search_mode_active:

            line1 = (
                '<b>'
                '<style bg="ansired" '
                'fg="ansiwhite">'
                ' > STANDARD MODE '
                '</style>'
                '</b>'
            )

            line2 = (
                '<style fg="ansiwhite">'
                ' > REALTIME SEARCH'
                '</style>'
            )

        else:

            line1 = (
                '<style fg="ansiwhite">'
                ' > STANDARD MODE'
                '</style>'
            )

            line2 = (
                '<b>'
                '<style bg="ansired" '
                'fg="ansiwhite">'
                ' > REALTIME SEARCH '
                '</style>'
                '</b>'
            )

        return HTML(
            f'{line1}\n{line2}'
        )

    # =====================================
    # TOOLBAR STYLE
    # =====================================
    custom_style = Style.from_dict({
        "bottom-toolbar":
        "bg:default fg:default noreverse"
    })

    # =====================================
    # PROMPT SESSION
    # =====================================
    session = PromptSession(
        bottom_toolbar=bottom_toolbar,
        key_bindings=bindings,
        style=custom_style
    )

    # =====================================
    # CHAT LOOP
    # =====================================
    while True:

        try:

            user_input = await session.prompt_async(
                "\nUser: "
            )

            # ---------------------------------
            # EXIT COMMANDS
            # ---------------------------------
            if user_input.lower() in [
                "exit",
                "quit"
            ]:

                print_system_status(
                    "Terminating VICTOR session. Goodbye."
                )

                break

            # Ignore empty input
            if not user_input.strip():
                continue

            # ---------------------------------
            # SEND MESSAGE
            # ---------------------------------
            await stream_response(
                session_id,
                user_input,
                search_mode_active
            )

        except KeyboardInterrupt:

            print_system_status(
                "\nEmergency termination detected."
            )

            break

        except EOFError:

            print_system_status(
                "\nTerminating VICTOR session. Goodbye."
            )

            break

        except Exception as e:

            console.print(
                f"[bold red]Fatal Error:[/bold red] "
                f"{str(e)}"
            )


# =========================================
# ENTRY POINT
# =========================================
if __name__ == "__main__":

    asyncio.run(main())