# app/services/command_service.py
from app.services.groq_service import GroqService
from app.services.chat_service import ChatService

class CommandService:
    def __init__(self, groq_service: GroqService):
        self.groq_service = groq_service
        self.chat_service = ChatService()

    async def parse(self, session_id: str, message: str) -> dict:
        """Converts natural language coding, local system, or browser execution commands into a structured JSON payload."""
        history = self.chat_service.get_history(session_id)
        recent_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-4:]]) if history else "No previous history."

        system_prompt = (
            "You are VICTOR's Core Command, Development & Browser Parser. Extract the precise action and parameters from the user's message.\n\n"
            "SUPPORTED BASE ACTIONS (V1/V2):\n"
            "- create_folder: Simple directory building. 'target' is the folder path.\n"
            "- create_file: Simple atomic file creations. 'target' is the filepath, 'content' is the file body.\n"
            "- execute_terminal: Low-level terminal actions. 'target' is the command string.\n\n"
            "SUPPORTED DEVELOPMENT OPERATIONS (V3):\n"
            "- create_project: Build a structured codebase workspace. 'target' is the project name. 'content' MUST be the template type ('fastapi', 'cli', 'python', 'api_structure').\n"
            "- analyze_code: Conduct static parsing/analysis. 'target' is the project name or path. 'content' is the relative file path to analyze.\n"
            "- test_run: Safely run test commands or scripts. 'target' is the exact shell command to run. 'content' is an optional directory path.\n\n"
            "SUPPORTED BROWSER AUTOMATION OPERATIONS (V4):\n"
            "- browser_search: Performs an automated web search. 'target' is the raw search query string. 'content' is an OPTIONAL absolute directory path where results should be saved. Leave 'content' empty if no path is mentioned.\n"
            "- browser_navigate: Directs the browser context to a specific URL. 'target' is the full clean web destination address.\n"
            "- web_extract: Scrapes the text layer of the current active page layout. 'target' is a required short unique filename slug for saving the output markdown file.\n"
            "- web_analyze: Audits the DOM structural interactive element matrix of a web application page. 'target' is the target URL to review.\n\n"
            "CRITICAL LOCATION & PATH RULES:\n"
            "1. If the user explicitly requests a specific drive or location, map it to 'content' for browser searches, or 'target' for local file tasks.\n"
            "2. ESCAPE BACKSLASHES: If a Windows path contains backslashes (\\), you MUST convert them to forward slashes (e.g., 'D:/Quantum_Research/Data') or use double backslashes (e.g., 'D:\\\\Quantum_Research\\\\Data') so the JSON does not break.\n"
            "3. If referencing a previous location from context, inspect the CHAT HISTORY to resolve paths.\n\n"
            "Output strictly as a valid JSON object containing exactly:\n"
            "- 'action': The selected action string.\n"
            "- 'target': The primary structural target path, address, query, or command.\n"
            "- 'content': The secondary configuration string, template type, body text, or custom save path.\n\n"
            "Format your output as a raw JSON object only. Do not wrap in markdown codeblocks."
        )
        
        try:
            return await self.groq_service.get_json_response(system_prompt, message)
        except Exception as e:
            print(f"[CommandService V4 Parsing Exception] {e}")
            return {"action": "unknown", "error": str(e)}