import json
from app.models import ExecutionPlan
from app.services.ai_service import ai_service
from app.services.memory_service import memory_service
from rich.console import Console

console = Console()

class BrainService:
    async def classify_and_plan(self, user_input: str, session_id: str = "default") -> ExecutionPlan:
        if isinstance(session_id, str) and ("\n" in session_id or "---" in session_id):
            memory_context = session_id
        else:
            memory_context = await memory_service.get_context(session_id)
        
        system_prompt = f"""You are VICTOR's cognitive router and Brain service.
Your job is to analyze the user input and return a cleanly structured JSON block parsing the core intent and a step-by-step execution plan.
If the user provides a multi-task statement like "Open Chrome, play music, and check my mail", the plan must split these into individual clear strings inside 'execution_plan'.
When a user asks to open a platform (like YouTube) and search/play/watch something on it (e.g., 'open youtube and play carryminati's video' or 'open youtube and search lo-fi beats'), DO NOT split this into two steps (like 'Open YouTube' and 'Play video'). Consolidate it into a single clear step: 'Search for carryminati's video on YouTube' or 'Search for lo-fi beats on YouTube'.
Distinct, unrelated actions (like looking up space news) must remain separate steps.
If the user explicitly tells you a personal fact, preference, name, or instructs you to 'remember' a specific detail, DO NOT classify it as research or task. Set the intent to 'task' and generate a structural 'memorize' execution step.
The step format must look like this: "Memorize key 'user_owner_name' with value 'Shashank'" or "Memorize key 'user_preference' with value 'X'".

You support the following automated OS and browser control tasks:
1. System Volume & Brightness: increase/decrease/mute/unmute volume, set volume to X percent, increase/decrease brightness, set brightness to X percent.
2. OS / Window Control: close window, close application, minimize window, maximize window, toggle full screen, show desktop, switch window, open task manager, open settings, open file explorer.
3. Browser Navigation: open new tab, close tab, next tab, previous tab, go back, go forward, refresh/reload page, scroll up/down, zoom in/out/reset.
4. Input / Edit: select all, copy, paste, cut, undo, redo, save file, press enter, press escape.
5. System Utilities: take screenshot, lock screen, toggle dark mode, toggle wifi, sleep display, restart computer, shutdown computer.
6. Desktop Management: set wallpaper to <url/local-path>, organize desktop, clean desktop, list desktop items, show desktop stats.
7. Reminders: set a reminder for YYYY-MM-DD HH:MM to <message>. (Always resolve relative times like 'in 10 minutes' to target YYYY-MM-DD HH:MM format).
8. Weather: show weather in <city>.
9. Application Launcher: open <app name> (e.g., notepad, calculator, chrome, etc.).

If the user request matches any of these, set the intent to 'task' and write a clear step in 'execution_plan'.
If the user request asks a question requiring real-time info, web search, current facts, or research (e.g., 'what is the value of one dollar in rupees?', 'who won the match yesterday?'), set the intent to 'research' and populate the 'execution_plan' with a step search query (e.g., 'Search for <query>').
If the user uploads a file (indicated by '--- Start of File: <filename> ---' blocks) with no explicit instructions, or asks to explain/summarize/discuss the file content, set the intent to 'chat' and leave 'execution_plan' empty. DO NOT classify file uploads as 'research' or try to search the web for the file name or file content.
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
                model="llama-3.1-8b-instant",
                response_format={"type": "json_object"},
                temperature=0.1
            )
            data = json.loads(response_text)
            return ExecutionPlan(**data)
        except Exception as e:
            console.print(f"[bold red]Brain Service Error:[/bold red] {e}")
            return ExecutionPlan(intent="chat", execution_plan=[user_input])

brain_service = BrainService()
