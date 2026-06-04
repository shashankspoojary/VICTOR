import json
import logging
from app.services.ai_service import AIService
from app.services.memory_service import MemoryService
from app.services.personality_service import PersonalityService
from app.services.realtime_service import RealtimeService
from app.services.task_executor import TaskExecutor
from app.services.vision_service import VisionService

logger = logging.getLogger(__name__)

class BrainService:
    def __init__(self):
        self.ai_service = AIService()
        self.memory_service = MemoryService()
        self.personality_service = PersonalityService()
        self.realtime_service = RealtimeService()
        self.task_executor = TaskExecutor()
        self.vision_service = VisionService()

    def check_deterministic_guards(self, query: str) -> dict | None:
        """
        Checks the user query against deterministic guards.
        Returns a pre-configured routing packet if a guard matches, otherwise None.
        """
        if 'TTCAMTOKENTT' in query:
            return {
                "capability": "vision",
                "mode": "VICTOR_MODE",
                "bypass_classifier": True,
                "cleaned_query": query.replace('TTCAMTOKENTT', '').strip()
            }
        return None

    async def route_intent(self, session_id: str, query: str) -> dict:
        """
        Routes the user's intent to the appropriate capability and mode via AI classifier.
        Falls back to a default configuration safely if processing fails.
        """
        # 1. Check deterministic guards first
        guard_result = self.check_deterministic_guards(query)
        if guard_result:
            return guard_result

        # 2. Fetch compiled background payload
        context = self.memory_service.build_context(session_id, query)
        
        # 3. Prepare highly optimized routing system prompt
        routing_system_prompt = f"""You are the Cognitive Routing Brain for VICTOR.
Your sole purpose is to analyze the user's query and determine the best capability and mode to handle it.
You MUST respond with RAW JSON ONLY containing exactly two keys: "capability" and "mode". No other text or markdown blocks.

Available Capabilities:
- chat: For general conversation, greeting, answering basic or abstract questions.
- research: For looking up current events, facts, or performing web searches.
- coding: For writing, explaining, modifying, or reviewing programming code.
- script_writing: For generating long-form texts, stories, or scripts.
- vision: For analyzing visual input or images.
- task: For executing system tasks, background processes, or scanning/checking local directories and filesystem paths.

Available Modes:
- VICTOR_MODE: Standard tactical, concise, AI assistant mode.
- KNOWLEDGE_MODE: For deep, informative, detailed explanations.
- RESEARCH_MODE: For browsing/researching external information.

Context / Background Payload:
{context.get('system_prompt', '')}

Example Expected Output:
{{"capability": "chat", "mode": "VICTOR_MODE"}}
"""

        # 4. Call AIService to get the classification
        try:
            response_text = await self.ai_service.generate_text(
                prompt=query,
                system_prompt=routing_system_prompt
            )
            
            # Clean up the response safely
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_text)
            
            capability = result.get("capability", "chat")
            mode = result.get("mode", "VICTOR_MODE")
            
            return {
                "capability": capability,
                "mode": mode
            }
            
        except Exception as e:
            logger.error(f"Intent routing failed: {e}. Defaulting to safe fallback.")
            # 5. Default gracefully if parsing or generation fails
            return {
                "capability": "chat",
                "mode": "VICTOR_MODE"
            }

    async def execute_query(self, session_id: str, query: str, base64_image: str = None, mode: str = None) -> str:
        """
        The Master Interaction Loop.
        Routes the intent, builds context, triggers capabilities like research if needed,
        generates the AI response, logs history, and returns the response.
        """
        # Step A: Run route_intent
        route = await self.route_intent(session_id, query)
        capability = route.get("capability")
        mode = mode or route.get("mode")
        cleaned_query = route.get("cleaned_query", query)

        # Intercept Vision Capability Payload
        if capability == "vision":
            try:
                # Delegate generation directly to VisionService.analyze_image
                response_text = await self.vision_service.analyze_image(cleaned_query, base64_image)
                # Log history
                self.memory_service.add_message(session_id, "user", f"[Vision Input]: {cleaned_query}")
                self.memory_service.add_message(session_id, "assistant", response_text)
                return response_text
            except Exception as e:
                logger.error(f"Vision routing failed: {e}")
                return f"Error analyzing visual stream: {e}"

        # Intercept Task Capability Payload
        if capability == "task":
            try:
                task_extraction_prompt = """You are a Task Parameter Extractor.
Extract the intended action and target from the user's query.
Return RAW JSON ONLY containing "action" (must be "open_url", "launch_tool", or "scan_directory") and "target" (the URL, tool executable name, or folder path).
Example 1: {"action": "open_url", "target": "https://github.com"}
Example 2: {"action": "launch_tool", "target": "code"}
Example 3: {"action": "scan_directory", "target": "./workspace"}
If the user asks to "check a project folder", "scan directory", or analyze filesystem layout, the action MUST be "scan_directory"."""
                task_json_str = await self.ai_service.generate_text(
                    prompt=cleaned_query,
                    system_prompt=task_extraction_prompt
                )
                
                clean_json_str = task_json_str.replace("```json", "").replace("```", "").strip()
                command_data = json.loads(clean_json_str)

                if command_data.get("action") == "scan_directory":
                    target_path = command_data.get("target")
                    task_result = await self.task_executor.scan_workspace_directory(target_path)
                    
                    self.memory_service.add_message(session_id, "user", f"[System Task - Scan Directory]: {cleaned_query}")
                    self.memory_service.add_message(session_id, "assistant", task_result)
                    return task_result
                
                task_result = await self.task_executor.execute_task(command_data)
                
                # Log the occurrence
                self.memory_service.add_message(session_id, "user", f"[System Task]: {cleaned_query}")
                self.memory_service.add_message(session_id, "system", task_result)
                
                # Feed confirmation back to personality layer
                context_data = self.memory_service.build_context(session_id, query, mode=mode)
                base_context = context_data.get("system_prompt", "")
                personality_prompt = self.personality_service.get_behavior_prompt(base_context)
                
                notification_prompt = f"{personality_prompt}\n\nThe system executed a task. The result was: {task_result}\nNotify the user concisely."
                
                response_text = await self.ai_service.generate_text(
                    prompt="Acknowledge the task execution.",
                    system_prompt=notification_prompt
                )
                self.memory_service.add_message(session_id, "assistant", response_text)
                return response_text
            except Exception as e:
                logger.error(f"Task routing failed: {e}")
                return f"Error executing task: {e}"

        # Step B: Fetch the structural background context
        context_data = self.memory_service.build_context(session_id, query, mode=mode)
        base_context = context_data.get("system_prompt", "")
        chat_history = context_data.get("chat_history", [])

        # Step C: Realtime search if appropriate
        research_context = ""
        if capability == "research" or mode == "RESEARCH_MODE":
            try:
                search_results = await self.realtime_service.search_web(query)
                research_context = f"\n\n--- Internet Research Context ---\n{search_results}"
            except Exception as e:
                logger.error(f"Realtime search failed: {e}")

        # Step D: Combine into single master system prompt payload
        master_system_prompt = self.personality_service.get_behavior_prompt(base_context)
        if research_context:
            master_system_prompt += research_context
            
        if chat_history:
            history_str = "\n\n--- Chat History ---\n"
            for msg in chat_history[-5:]:
                history_str += f"{msg['role'].capitalize()}: {msg['content']}\n"
            master_system_prompt += history_str

        # Log user query into history
        self.memory_service.add_message(session_id, "user", query)

        # Step E: Hand payload and original query to AIService
        response_text = await self.ai_service.generate_text(
            prompt=query,
            system_prompt=master_system_prompt
        )

        # Step F: Log assistant's final response and return
        self.memory_service.add_message(session_id, "assistant", response_text)
        return response_text
