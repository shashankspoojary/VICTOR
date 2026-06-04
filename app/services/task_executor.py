import asyncio
import logging
import webbrowser
import subprocess

logger = logging.getLogger(__name__)

class TaskExecutor:
    def __init__(self):
        pass

    async def execute_task(self, command_data: dict) -> str:
        """
        Executes a background system task or tool securely.
        """
        try:
            action = command_data.get("action")
            target = command_data.get("target")

            if not action or not target:
                return "System action failed: Missing action or target parameters."

            if action == "open_url":
                logger.info(f"Opening URL: {target}")
                webbrowser.open(target)
                return f"System action executed successfully: Launched URL target '{target}'."
                
            elif action == "launch_tool":
                logger.info(f"Launching tool: {target}")
                # Initiate a non-blocking background process safely
                process = await asyncio.create_subprocess_shell(
                    target,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                return f"System action executed successfully: Launched primary developer tool '{target}'."
                
            else:
                return f"System action failed: Unknown action '{action}'."

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return f"System action failed: {str(e)}"
