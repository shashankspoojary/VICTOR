import json
import config
from app.models import ExecutionPlan
from app.services.ai_service import ai_service
from app.services.memory_service import memory_service
from rich.console import Console

console = Console()

class BrainService:
    def _prune_context(self, context: str, max_chars: int = 12000) -> str:
        if not context or len(context) <= max_chars:
            return context
        
        # Keep 30% from the start and 70% from the end to prioritize recent history/data
        keep_start = int(max_chars * 0.3)
        keep_end = max_chars - keep_start - 100 # safety margin and truncation message
        
        start_part = context[:keep_start]
        end_part = context[-keep_end:]
        
        return f"{start_part}\n\n... [TRUNCATED FOR CONTEXT LIMITS] ...\n\n{end_part}"

    async def classify_and_plan(self, user_input: str, session_id: str = "default") -> ExecutionPlan:
        if isinstance(session_id, str) and ("\n" in session_id or "---" in session_id):
            memory_context = session_id
        else:
            memory_context = await memory_service.get_context(session_id)
        
        # Token Pruning: slice incoming memory_context to prevent overflow
        memory_context = self._prune_context(memory_context)
        
        system_prompt = f"""You are VICTOR's cognitive router and Brain service.
Your job is to analyze the user input and return a cleanly structured JSON block parsing the core intent and a step-by-step execution plan.
If the user provides a multi-task statement like "Open Chrome, play music, and check my mail", the plan must split these into individual clear strings inside 'execution_plan'.
When a user asks to open a platform (like YouTube) and search/play/watch something on it (e.g., 'open youtube and play carryminati's video' or 'open youtube and search lo-fi beats'), DO NOT split this into two steps (like 'Open YouTube' and 'Play video'). Consolidate it into a single clear step: 'Search for carryminati's video on YouTube' or 'Search for lo-fi beats on YouTube'.
Distinct, unrelated actions (like looking up space news) must remain separate steps.

MANDATORY ACTION SPLITTING & APP NAMING RULES:
- Compound Action Splitting: Whenever a user combines opening an application with typing or editing text (e.g., "open notepad and type hello world"), you MUST split the request into two separate items in the 'execution_plan' array:
  1. "open notepad"
  2. "Type text: 'hello world'"
- Clean App Naming: Output launcher commands strictly as "open <clean_app_name>" (e.g., "open chrome", "open paint", "open copilot"). You must never emit extra text wrappers or labels like "application:", "app:", "window:", or "a new".

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
9. Application Launcher: open <clean_app_name> (e.g., notepad, calculator, chrome, word, excel, powerpoint, terminal, etc.). Output strictly as "open <clean_app_name>" without extra wrappers/labels like "application:", "app:", "window:", or "a new".
10. Input / Typing Actions: when the user asks to type, write, or enter text into a field (e.g., "type hello world", "write Dear Sir", "enter my email"), generate the step as: "Type text: '<the text to type>'". Do NOT classify typing commands as chat.
11. Window Focus Actions: when the user wants to bring a specific application window to the foreground (e.g., "focus chrome", "switch to notepad", "bring excel to front", "activate terminal"), generate the step as: "Focus window: '<Application Name>'". This is distinct from opening an application.
12. Coordinate Mouse Interactions: when the user specifies precise screen coordinates for mouse actions (e.g., "click at 450, 600", "right click at 200, 300", "double click at 100, 200", "move mouse to 500, 400", "drag from 100, 100 to 300, 300"), generate the step as: "Click at coordinates: (X, Y)" or "Right click at coordinates: (X, Y)" or "Double click at coordinates: (X, Y)" or "Move mouse to coordinates: (X, Y)" or "Drag from coordinates: (X1, Y1) to (X2, Y2)". Always extract X and Y as integers.
13. Persistent Browser Actions:
    - Switch browser target: `Browser action: switch target='<browser_name>'` (e.g., 'chrome', 'brave', 'edge', 'opera', 'firefox')
    - List active sessions: `Browser action: list_browsers`
    - Navigate to url: `Browser action: go_to url='<url>'`
    - Search query: `Browser action: search query='<query>' engine='<engine>'` (e.g., engine='google', 'bing', 'duckduckgo')
    - Fuzzy element click: `Browser action: smart_click description='<button/link/text_label>'`
    - Fuzzy element type: `Browser action: smart_type description='<input/search_label>' text='<value>'`
    - Tab management: `Browser action: close_tab` or `Browser action: new_tab`
14. Automated Messenger Routes:
    - Send message on a platform: `Send message: platform='<platform>' receiver='<name_or_username>' text='<message_body>'` (platforms: 'whatsapp', 'telegram', 'signal', 'discord', 'instagram', 'messenger')
15. Advanced OS Control / Grid Layout:
    - Snap window layout: `Window action: snap_left` or `Window action: snap_right`
    - Set desktop wallpaper: `System utility: set_wallpaper_url url='<url>'`
    - Custom desktop layout organization: `Desktop management: organize mode='by_type'` or `Desktop management: organize mode='by_date'`
16. Standalone File Manipulation: standalone file manipulation tasks—including terms like "Archive files", "Zip items", "Compress data", or "Clean up directory".

CRITICAL: Standalone file manipulation tasks—including terms like "Archive files", "Zip items", "Compress data", or "Clean up directory"—must strictly be categorized under the `task` intent and structured as operational execution steps, rather than falling back into web `research` mode.

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
                model=config.GROQ_MODEL,
                response_format={"type": "json_object"},
                temperature=0.1
            )
            data = json.loads(response_text)
            return ExecutionPlan(**data)
        except Exception as e:
            console.print(f"[bold red]Brain Service Error:[/bold red] {e}")
            return ExecutionPlan(intent="chat", execution_plan=[user_input])

brain_service = BrainService()
