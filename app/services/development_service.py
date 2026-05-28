# app/services/development_service.py
import json
from pathlib import Path
from datetime import datetime
from config import DATABASE_DIR

from app.services.coding_service import CodingService
from app.services.project_service import ProjectService
from app.services.file_editor_service import FileEditorService
from app.services.code_analysis_service import CodeAnalysisService
from app.services.terminal_service import TerminalService
from app.services.workspace_service import WorkspaceService
from app.services.debugging_service import DebuggingService

class DevelopmentService:
    """Central orchestration hub coordinating project creation, file edits, analysis, and execution tasks."""

    def __init__(self):
        self.coding_service = CodingService()
        self.project_service = ProjectService()
        self.editor_service = FileEditorService()
        self.analysis_service = CodeAnalysisService()
        self.terminal_service = TerminalService()
        self.workspace_service = WorkspaceService()
        self.debugging_service = DebuggingService()
        self.history_file = DATABASE_DIR / "coding_data" / "coding_history.json"

    def _log_workflow_event(self, task_type: str, details: dict):
        try:
            if not self.history_file.exists():
                with open(self.history_file, 'w', encoding='utf-8') as f: json.dump([], f)
            with open(self.history_file, 'r', encoding='utf-8') as f: history = json.load(f)
            history.append({
                "timestamp": datetime.now().isoformat(),
                "type": task_type,
                "details": details
            })
            with open(self.history_file, 'w', encoding='utf-8') as f: json.dump(history, f, indent=4)
        except Exception:
            pass

    def provision_new_project(self, target_identifier: str, structural_scaffold: str) -> str:
        """High-level orchestration route to safely build and verify structural applications."""
        result = self.project_service.scaffold_from_template(target_identifier, structural_scaffold)
        self._log_workflow_event("project_provisioning", {"name": target_identifier, "status": result})
        
        if not result["success"]:
            return f"Execution Blocked: Project generation setup hit system constraints: {result.get('error')}"
            
        return (
            f"Initialization Succeeded: Core layouts for '{target_identifier}' are configured inside workspaces.\n"
            f"Elements established on disk:\n" + "\n".join([f" - {el}" for el in result["elements_generated"]])
        )

    def execute_and_analyze_file(self, project_name: str, relative_file_path: str) -> str:
        """Performs precise structural static checking assessments on target components."""
        target_path = self.workspace_service.projects_dir / project_name / relative_file_path
        if not target_path.exists():
            return f"Error Encountered: Component could not be mapped at destination: {relative_file_path}"
            
        report = self.analysis_service.analyze_source_file(target_path)
        if not report["success"]:
            return f"Structural Fault Discovered: static validation warning: {report.get('error')}"
            
        return (
            f"Static Scan Report for [{relative_file_path}]:\n"
            f" - Discovered Module Imports: {', '.join(report['imports']) if report['imports'] else 'None'}\n"
            f" - Classes Implemented: {', '.join(report['classes']) if report['classes'] else 'None'}\n"
            f" - Defined Functions: {', '.join(report['functions']) if report['functions'] else 'None'}\n"
            f" - Metric Lines Detected: {report['metrics']['lines_discovered']}"
        )

    def test_run_script(self, script_execution_command: str, execution_context_dir: str = None) -> str:
        """Safely dispatches target systems execution checks and monitors tracking metrics."""
        result = self.terminal_service.run_development_command(script_execution_command, execution_context_dir)
        if not result["success"]:
            return f"Execution Diagnostics Warning (Return Code: {result['returncode']}):\n{result['stderr']}"
        return f"Process Completed Smoothly:\n{result['stdout']}"