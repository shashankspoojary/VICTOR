# app/services/project_service.py
import json
from pathlib import Path
from config import WORKFLOW_TEMPLATES_DIR, DATABASE_DIR
from app.services.workspace_service import WorkspaceService

class ProjectService:
    def __init__(self):
        self.workspace_service = WorkspaceService()
        self.registry_manifest = DATABASE_DIR / "coding_data" / "generated_projects.json"
        self._ensure_manifest()

    def _ensure_manifest(self):
        if not self.registry_manifest.exists():
            with open(self.registry_manifest, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def scaffold_from_template(self, project_name_or_path: str, template_type: str) -> dict:
        """Instantiates project scaffolding at a local sandbox name or an explicit external absolute path."""
        template_file = WORKFLOW_TEMPLATES_DIR / f"create_{template_type}_project.json"
        if not template_file.exists():
            template_file = WORKFLOW_TEMPLATES_DIR / f"{template_type}.json"
            if not template_file.exists():
                return {"success": False, "error": f"Template mapping '{template_type}' was not found."}

        with open(template_file, 'r', encoding='utf-8') as f:
            template_data = json.load(f)

        # Resolve path safely (could be standard name or raw absolute disk path)
        resolved_project_path = self.workspace_service.register_project_workspace(project_name_or_path, template_type)
        project_path_str = str(resolved_project_path)
        created_elements = []

        steps = template_data.get("steps", [])
        for step in steps:
            action = step.get("action")
            
            # Expand variables using the absolute path string
            target_rel = step.get("target", "").replace("{target}", project_path_str)
            content = step.get("content", "").replace("{target}", project_path_str)
            
            # Instantly maps to the absolute destination path cleanly
            resolved_target = Path(target_rel)
            
            if action == "create_folder":
                resolved_target.mkdir(parents=True, exist_ok=True)
                created_elements.append(f"Directory: {resolved_target}")
            elif action == "create_file":
                resolved_target.parent.mkdir(parents=True, exist_ok=True)
                # Writes content safely without wiping out surrounding files in an existing directory
                with open(resolved_target, 'w', encoding='utf-8') as fl:
                    fl.write(content)
                created_elements.append(f"File: {resolved_target}")

        self._log_manifest(resolved_project_path.name, project_path_str, template_type)

        return {
            "success": True,
            "root_path": project_path_str,
            "elements_generated": created_elements
        }

    def _log_manifest(self, name: str, path: str, template: str):
        try:
            with open(self.registry_manifest, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            manifest[name] = {
                "absolute_path": path,
                "scaffold": template,
                "verified": True
            }
            with open(self.registry_manifest, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=4)
        except Exception:
            pass