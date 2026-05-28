# app/services/workspace_service.py
import json
from pathlib import Path
from datetime import datetime
from config import BASE_DIR, DATABASE_DIR
from app.utils.validation import is_safe_path

class WorkspaceService:
    def __init__(self):
        self.workspace_root = BASE_DIR / "workspace"
        self.projects_dir = self.workspace_root / "generated_projects"
        self.temp_dir = self.workspace_root / "temporary_files"
        self.debug_dir = self.workspace_root / "debugging"
        self.logs_dir = self.workspace_root / "execution_logs"
        self.history_file = DATABASE_DIR / "coding_data" / "workspace_history.json"
        
        self._initialize_layout()

    def _initialize_layout(self):
        for path in [self.workspace_root, self.projects_dir, self.temp_dir, self.debug_dir, self.logs_dir, DATABASE_DIR / "coding_data"]:
            path.mkdir(parents=True, exist_ok=True)
        if not self.history_file.exists():
            self._save_raw_history([])

    def _load_raw_history(self) -> list:
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _save_raw_history(self, data: list):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def register_project_workspace(self, project_path_or_name: str, template: str) -> Path:
        """Configures a tracked workspace context location. 
        Supports both direct absolute paths and fallback sandbox project names.
        """
        if not is_safe_path(project_path_or_name):
            raise PermissionError("Target path string resolved to an invalid or unsafe layout state.")
            
        target_path = Path(project_path_or_name)
        
        # If the user gave a simple name, default to the local sandbox directory
        if not target_path.is_absolute():
            target_path = self.projects_dir / project_path_or_name
            
        # exist_ok=True safely handles generating files inside an existing folder structure
        target_path.mkdir(parents=True, exist_ok=True)
        
        history = self._load_raw_history()
        history.append({
            "project_name": target_path.name,
            "absolute_path": str(target_path),
            "template_used": template,
            "registered_at": datetime.now().isoformat()
        })
        self._save_raw_history(history)
        return target_path

    def get_active_workspaces(self) -> list:
        return self._load_raw_history()

    def stage_temporary_file(self, content: str, filename: str) -> Path:
        target = self.temp_dir / filename
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
        return target