# app/services/execution_service.py
import inspect
from app.services.action_service import ActionService
from app.services.task_service import TaskService

class ExecutionService:
    def __init__(self):
        self.action_service = ActionService()
        self.task_service = TaskService()

    async def execute(self, action: str, target: str, content: str = None) -> str:
        """Executes targeted single actions or complex operations by handling synchronous or asynchronous calls."""
        task_id = self.task_service.create_task(action, target, content)
        
        handler = self.action_service.get_handler(action)
        if not handler:
            error_msg = f"Unknown or unauthorized action requested: {action}"
            self.task_service.fail_task(task_id, error_msg)
            return f"Error: {error_msg}"

        try:
            # Check if the registered target is an asynchronous routine function
            if inspect.iscoroutinefunction(handler):
                if action == "browser_navigate" or action == "web_extract":
                    result = await handler(target)
                elif action == "browser_search":
                    # Pass the custom path (content) into the search handler
                    result = await handler(target, content)
                elif action == "web_analyze":
                    analysis_payload = await handler(target)
                    result = f"DOM Parsing Complete: Elements found count: {analysis_payload.get('metrics', {}).get('interactive_count', 0)}"
                else:
                    result = await handler(target, content)
            else:
                # Sync Execution router mapping
                if action == "create_file":
                    result = handler(target, content or "")
                elif action in ("create_folder", "execute_terminal"):
                    result = handler(target)
                elif action == "create_project":
                    result = handler(target, content or "python")
                elif action == "analyze_code":
                    result = handler(target, content or "main.py")
                elif action == "test_run":
                    result = handler(target, content)
                else:
                    result = handler()

            str_result = str(result)
            self.task_service.complete_task(task_id, str_result)
            return str_result
            
        except Exception as e:
            error_msg = str(e)
            self.task_service.fail_task(task_id, error_msg)
            return f"Execution Failed: {error_msg}"