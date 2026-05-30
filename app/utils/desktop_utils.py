# app/utils/desktop_utils.py
import platform
import subprocess

def open_application(app_name: str) -> str:
    """Attempts to launch an application natively based on the host OS."""
    os_type = platform.system()
    try:
        if os_type == "Windows":
            # Uses the Windows 'start' command which automatically resolves registered software mapping
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
            return f"Attempted to launch '{app_name}' via Windows shell protocol."
        elif os_type == "Darwin":
            # macOS native application opening procedure
            subprocess.Popen(["open", "-a", app_name])
            return f"Attempted to launch '{app_name}' via macOS native open."
        else:
            # Standard Linux daemon launch
            subprocess.Popen([app_name])
            return f"Attempted to launch '{app_name}'."
    except Exception as e:
        return f"Failed to execute launch sequence for '{app_name}': {str(e)}"