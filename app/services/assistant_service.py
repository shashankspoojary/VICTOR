# app/services/assistant_service.py
import asyncio
from typing import AsyncGenerator
from app.services.groq_service import GroqService
from app.services.command_service import CommandService
from app.services.execution_service import ExecutionService
from app.services.workflow_service import WorkflowService
from app.services.chat_service import ChatService
from app.services.vision_service import VisionService
from app.utils.time_info import get_formatted_time

class AssistantService:
    def __init__(self):
        self.groq_service = GroqService()
        self.command_service = CommandService(self.groq_service)
        self.execution_service = ExecutionService()
        self.workflow_service = WorkflowService(self.execution_service)
        self.chat_service = ChatService()
        self.vision_service = VisionService()

    async def execute_pipeline(self, session_id: str, user_message: str, is_voice: bool = False) -> AsyncGenerator[str, None]:
        cmd_payload = await self.command_service.parse(session_id, user_message)
        
        action = cmd_payload.get("action", "unknown")
        target = cmd_payload.get("target", "unknown")
        content = cmd_payload.get("content", "")

        execution_results = ""

        if action.startswith("workflow:") or action == "create_python_project":
            workflow_name = action.replace("workflow:", "") if "workflow:" in action else action
            results = self.workflow_service.execute_workflow(workflow_name, target)
            execution_results = "\n".join(results)
        else:
            result = await self.execution_service.execute(action, target, content)
            execution_results = result

        vision_context = ""
        # Automatic visual debugging integration when task logic faults
        if "fail" in execution_results.lower() or "error" in execution_results.lower() or "exception" in execution_results.lower():
            print("[ASSISTANT] Task error detected. Triggering visual debugging...")
            vision_report = await self.vision_service.analyze_current_screen(f"The command '{action}' failed. Identify any visible errors, tracebacks, or blockers on screen.")
            vision_context = f"\n--- VISUAL DEBUGGING DATA ---\n{vision_report}\n--- END VISUAL DATA ---\n"

        current_time = get_formatted_time()
        
        voice_rules = ""
        if is_voice:
            voice_rules = "6. YOU ARE SPEAKING TO THE USER. Keep your summary extremely brief. Do not dictate code blocks or raw terminal outputs."

        system_prompt = (
            f"You are VICTOR (Virtual Intelligent Cognitive Task-Oriented Resource). "
            f"Current Time: {current_time}\n\n"
            f"You have just executed a system task.\n"
            f"Task Action: {action}\n"
            f"Target System Result: {execution_results}\n"
            f"{vision_context}\n\n"
            f"PERSONALITY OVERRIDE: Behave EXACTLY like J.A.R.V.I.S. from the Iron Man films. "
            f"You are a sophisticated, highly competent AI butler with a dry wit and formal elegance. "
            f"Address the user as 'Sir'.\n\n"
            f"INSTRUCTIONS FOR RESPONSE:\n"
            f"1. Acknowledge the completed action with JARVIS-like flair (e.g., 'I have taken the liberty of...', 'Right away, sir.').\n"
            f"2. IF the execution result contains 'EXTRACTED PAGE CONTENT FOR SUMMARY', you MUST provide a detailed, highly readable bulleted summary of the key findings.\n"
            f"3. IF visual debugging data is present, analyze the screen tracebacks and propose a practical fix.\n"
            f"4. IF the execution result contains 'SYSTEM RESOURCE STATUS' or 'ENVIRONMENT AWARENESS', provide a professional summary of the telemetry.\n"
            f"5. Do NOT simply dump raw file paths or dictionary logs. Describe what was accomplished elegantly.\n"
            f"{voice_rules}"
        )

        messages = self.chat_service.prepare_messages_for_ai(
            session_id=session_id,
            system_prompt=system_prompt,
            new_user_message=user_message
        )

        full_response = ""
        async for token in self.groq_service.stream_chat(messages):
            full_response += token
            yield token

        self.chat_service.append_message(session_id, "user", user_message)
        self.chat_service.append_message(session_id, "assistant", full_response)