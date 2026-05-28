# app/services/local_actions_service.py
from app.utils.file_utils import safe_create_folder, safe_create_file
from app.utils.command_utils import safe_run_command

class LocalActionsService:
    """Executes actions on the local PC safely."""
    
    def create_folder(self, target_path: str) -> str:
        return safe_create_folder(target_path)

    def create_file(self, target_path: str, content: str) -> str:
        return safe_create_file(target_path, content)

    def execute_terminal(self, command: str) -> str:
        # V2 strictly limits this, but provides the pipe
        return safe_run_command(command)