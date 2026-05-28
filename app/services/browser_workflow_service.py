# app/services/browser_workflow_service.py
import json
from pathlib import Path
from typing import Dict, Any, List
from config import WORKFLOW_TEMPLATES_DIR
from app.services.browser_navigation_service import BrowserNavigationService
from app.services.browser_memory_service import BrowserMemoryService

class BrowserWorkflowService:
    """Coordinates structured sequence operations from configured automation schemas."""
    
    def __init__(self, navigation_service: BrowserNavigationService, memory_service: BrowserMemoryService):
        self.navigation_service = navigation_service
        self.memory_service = memory_service

    async def execute_browser_workflow(self, workflow_template_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        template_file = WORKFLOW_TEMPLATES_DIR / f"{workflow_template_name}.json"
        if not template_file.exists():
            return {"success": False, "error": f"Workflow profile '{workflow_template_name}' not resolved."}
            
        with open(template_file, 'r', encoding='utf-8') as f:
            workflow_schema = json.load(f)
            
        page = await self.navigation_service.get_active_page()
        execution_trace = []
        steps = workflow_schema.get("steps", [])
        
        for index, step in enumerate(steps):
            action = step.get("action")
            selector = step.get("selector", "")
            value_template = step.get("value", "")
            
            resolved_value = value_template
            for key, val in parameters.items():
                resolved_value = resolved_value.replace(f"{{{key}}}", str(val))
                
            try:
                if action == "navigate":
                    await page.goto(resolved_value, wait_until="load")
                    title = await page.title()
                    self.memory_service.log_navigation_event(resolved_value, title, f"WORKFLOW_STEP_{index}")
                    execution_trace.append(f"Step {index}: Routed to {resolved_value}")
                
                elif action == "click":
                    await page.click(selector, timeout=5000)
                    execution_trace.append(f"Step {index}: Actuated click on [{selector}]")
                
                elif action == "fill":
                    await page.fill(selector, resolved_value, timeout=5000)
                    execution_trace.append(f"Step {index}: Added query payload inside [{selector}]")
                
                # --- NEW PRESS CAPABILITY ---
                elif action == "press":
                    await page.press(selector, resolved_value, timeout=5000)
                    execution_trace.append(f"Step {index}: Pressed keyboard key '{resolved_value}' on [{selector}]")
                
                elif action == "wait":
                    wait_ms = int(resolved_value) if resolved_value.isdigit() else 2000
                    await page.wait_for_timeout(wait_ms)
                    execution_trace.append(f"Step {index}: Paused thread for {wait_ms}ms")
            
            except Exception as e:
                return {
                    "success": False,
                    "completed_steps": index,
                    "trace": execution_trace,
                    "error": f"Step breaking context at [{action}]: {str(e)}"
                }
                
        try:
            # Wait for navigation to complete after search
            await page.wait_for_load_state("networkidle", timeout=5000)
            final_url = page.url
            final_title = await page.title()
            self.memory_service.log_navigation_event(
                final_url, 
                final_title, 
                f"WORKFLOW_{workflow_template_name.upper()}_COMPLETE"
            )
        except Exception:
            pass
            
        return {"success": True, "trace": execution_trace}