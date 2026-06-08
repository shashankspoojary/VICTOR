import asyncio
import json
import webbrowser
import re
from typing import List
from rich.console import Console
from app.services.ai_service import ai_service
from app.services.realtime_service import realtime_service
from app.services.memory_service import memory_service

console = Console()

class TaskExecutor:
    async def execute_plan(self, plan: List[str], event_queue: asyncio.Queue = None):
        if hasattr(plan, "execution_plan"):
            plan = plan.execution_plan
        elif isinstance(plan, dict) and "execution_plan" in plan:
            plan = plan["execution_plan"]
        for step in plan:
            if event_queue:
                await event_queue.put({"type": "task_status", "step": step, "status": "running"})
            console.print(f"\n[cyan]Executing step:[/cyan] {step}")
            primitive = await self._translate_step(step)
            if primitive:
                await self._handle_primitive(primitive, event_queue)
            if event_queue:
                await event_queue.put({"type": "task_status", "step": step, "status": "completed"})

    async def _translate_step(self, step: str) -> dict:
        prompt = (
            f"Translate the following step into a strict execution primitive.\n"
            f"Supported primitives:\n"
            f"- {{\"action\": \"open_url\", \"param\": \"URL_STRING\"}}\n"
            f"- {{\"action\": \"research\", \"param\": \"SEARCH_QUERY\"}}\n"
            f"- {{\"action\": \"play_youtube\", \"param\": \"SEARCH_QUERY\"}}\n"
            f"- {{\"action\": \"memorize\", \"key\": \"FIELD_NAME\", \"value\": \"DATA_STRING\"}}\n\n"
            f"CRITICAL INSTRUCTION: If the task text explicitly requests to 'play' music, a song, or a video on YouTube, select the 'play_youtube' action instead of a standard 'open_url' search page.\n"
            f"Instruct the translator model to convert any explicit step starting with 'Memorize' into the 'memorize' structural JSON primitive.\n"
            f"Look at the consolidated step text. If it just says 'on YouTube' but not 'play', it must output:\n"
            f"{{\"action\": \"open_url\", \"param\": \"https://www.youtube.com/results?search_query=lo-fi+beats\"}}\n"
            f"If a step does not mention a specific browser platform (e.g., 'Look up current news on space exploration'), it must be routed as a background intelligence action:\n"
            f"{{\"action\": \"research\", \"param\": \"current news on space exploration\"}}\n\n"
            f"Step: {step}\n\n"
            f"Output ONLY valid JSON. Your response must be a single JSON object."
        )
        messages = [{"role": "user", "content": prompt}]
        response_format = {"type": "json_object"}
        
        try:
            result = await ai_service.get_chat_completion(
                messages=messages, 
                response_format=response_format,
                temperature=0.1
            )
            return json.loads(result)
        except Exception as e:
            console.print(f"[red]Error translating step: {e}[/red]")
            return None

    async def _handle_primitive(self, primitive: dict, event_queue: asyncio.Queue = None):
        action = primitive.get("action")
        param = primitive.get("param")
        
        if action == "memorize":
            param_key = primitive.get("key")
            param_value = primitive.get("value")
            await memory_service.update_memory(param_key, param_value)
            console.print(f"[bold green]✓ Memory Updated:[/bold green] {param_key} -> {param_value}")
            if event_queue:
                await event_queue.put({"type": "token", "text": "Understood, Sir. I have updated my records."})
        elif action == "open_url":
            console.print(f"[green]Opening URL:[/green] {param}")
            webbrowser.open(param)
        elif action == "play_youtube":
            console.print(f"[magenta]Playing on YouTube:[/magenta] {param}")
            results = await realtime_service.search(f"site:youtube.com watch {param}")
            match = re.search(r'(https://www\.youtube\.com/watch\?v=[\w-]+)', str(results))
            if match:
                target_video_url = match.group(1)
                console.print(f"[green]Direct video link found:[/green] {target_video_url}")
                webbrowser.open(target_video_url)
            else:
                fallback_url = f"https://www.youtube.com/results?search_query={param.replace(' ', '+')}"
                console.print(f"[yellow]No direct link found, falling back to search:[/yellow] {fallback_url}")
                webbrowser.open(fallback_url)
        elif action == "research":
            console.print(f"[magenta]Researching:[/magenta] {param}")
            results = await realtime_service.search(param)
            console.print(f"[blue]Research Results for '{param}':[/blue]\n{results}")

            # Synthesize clean tactical answer from raw results debris
            summary_prompt = (
                f"Analyze the following raw search results and extract a clean, concise, direct answer to the query: '{param}'.\n"
                f"Strip out all webpage navigation links, raw markdown tables, website cookies text, and bracket crumbs. "
                f"Present only the definitive numerical values or core data points beautifully and professionaly."
                f"\n\nRaw Search Data:\n{results}"
            )
            try:
                clean_answer = await ai_service.get_chat_completion(
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.2
                )
            except Exception:
                clean_answer = results

            if event_queue:
                await event_queue.put({
                    "type": "search_results",
                    "query": param,
                    "answer": clean_answer,
                    "results": []
                })
        else:
            console.print(f"[red]Unknown action:[/red] {action}")

task_executor = TaskExecutor()
