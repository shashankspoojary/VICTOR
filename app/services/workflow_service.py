# app/services/workflow_service.py
import json
from config import WORKFLOW_TEMPLATES_DIR
from app.services.execution_service import ExecutionService

class WorkflowService:
    def __init__(self, execution_service: ExecutionService):
        self.execution_service = execution_service

    def get_workflow_template(self, workflow_name: str) -> dict:
        path = WORKFLOW_TEMPLATES_DIR / f"{workflow_name}.json"
        if not path.exists():
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def execute_workflow(self, workflow_name: str, target: str) -> list:
        """Executes a multi-step workflow. Formats the target into variables."""
        template = self.get_workflow_template(workflow_name)
        if not template:
            return [f"Error: Workflow template '{workflow_name}' not found."]

        results = []
        steps = template.get("steps", [])
        
        for step in steps:
            action = step.get("action")
            # Replace placeholder variables with actual target names
            step_target = step.get("target", "").replace("{target}", target)
            step_content = step.get("content", "").replace("{target}", target)
            
            res = self.execution_service.execute(action, step_target, step_content)
            results.append(res)
            
            # Stop execution if a step fails
            if res.startswith("Error:") or res.startswith("Execution Failed:"):
                results.append("Workflow aborted due to previous error.")
                break
                
        return results