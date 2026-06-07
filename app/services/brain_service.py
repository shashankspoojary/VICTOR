import json
from app.models import ExecutionPlan
from app.services.ai_service import ai_service
from app.services.memory_service import memory_service
from rich.console import Console

console = Console()

class BrainService:
    async def classify_and_plan(self, user_input: str, session_id: str = "default") -> ExecutionPlan:
        memory_context = await memory_service.get_context(session_id)
        
        system_prompt = f"""You are VICTOR's cognitive router and Brain service.
Your job is to analyze the user input and return a cleanly structured JSON block parsing the core intent and a step-by-step execution plan.
If the user provides a multi-task statement like "Open Chrome, play music, and check my mail", the plan must split these into individual clear strings inside 'execution_plan'.
When a user asks to open a platform and search/play something on it (e.g., 'Open YouTube and search lo-fi beats'), DO NOT split this into two steps. Consolidate it into a single clear step: 'Search for lo-fi beats on YouTube'.
Distinct, unrelated actions (like looking up space news) must remain separate steps.
If the user explicitly tells you a personal fact, preference, name, or instructs you to 'remember' a specific detail, DO NOT classify it as research or task. Set the intent to 'task' and generate a structural 'memorize' execution step.
The step format must look like this: "Memorize key 'user_owner_name' with value 'Shashank'" or "Memorize key 'user_preference' with value 'X'".
The 'intent' should be one of: chat, research, vision, task.

{memory_context}

Return ONLY valid JSON matching this schema:
{{
  "intent": "string",
  "execution_plan": ["step 1", "step 2"]
}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Input: {user_input}"}
        ]

        try:
            response_text = await ai_service.get_chat_completion(
                messages=messages,
                model="qwen/qwen3-32b",
                response_format={"type": "json_object"}
            )
            data = json.loads(response_text)
            return ExecutionPlan(**data)
        except Exception as e:
            console.print(f"[bold red]Brain Service Error:[/bold red] {e}")
            return ExecutionPlan(intent="chat", execution_plan=[user_input])

brain_service = BrainService()
