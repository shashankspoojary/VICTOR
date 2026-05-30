# app/utils/os_utils.py
import platform
import shutil

def get_os_type() -> str:
    """Returns the host machine's operating system identifier."""
    return platform.system()

def find_executable(name: str) -> str:
    """Locates an executable in the system's PATH variable."""
    return shutil.which(name)