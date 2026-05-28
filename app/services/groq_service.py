# app/services/groq_service.py
import json
import httpx
from typing import AsyncGenerator, List, Dict
from config import MAIN_MODEL, ROUTING_MODEL
from app.utils.key_rotation import groq_key_manager
from app.utils.retry import async_retry

class GroqService:
    def __init__(self):
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    @async_retry(max_retries=3)
    async def _execute_request(self, payload: dict, stream: bool = False) -> httpx.Response:
        current_key = groq_key_manager.get_current_key()
        headers = {
            "Authorization": f"Bearer {current_key}",
            "Content-Type": "application/json"
        }
        
        client = httpx.AsyncClient()
        try:
            if stream:
                request = client.build_request("POST", self.base_url, headers=headers, json=payload)
                response = await client.send(request, stream=True)
                if response.status_code == 429:
                    groq_key_manager.rotate_key()
                    response.raise_for_status() 
                response.raise_for_status()
                return response 
            else:
                response = await client.post(self.base_url, headers=headers, json=payload, timeout=20.0)
                if response.status_code == 429:
                    groq_key_manager.rotate_key()
                    response.raise_for_status()
                response.raise_for_status()
                await client.aclose()
                return response
        except Exception as e:
            await client.aclose()
            raise e

    async def get_classification(self, prompt: str) -> str:
        payload = {
            "model": ROUTING_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 10
        }
        response = await self._execute_request(payload, stream=False)
        data = response.json()
        return data["choices"][0]["message"]["content"].strip().upper()
        
    async def get_json_response(self, system_prompt: str, user_prompt: str) -> dict:
        """New V2 utility for structured JSON generation."""
        payload = {
            "model": MAIN_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        response = await self._execute_request(payload, stream=False)
        data = response.json()
        try:
            return json.loads(data["choices"][0]["message"]["content"])
        except json.JSONDecodeError:
            return {}

    async def stream_chat(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        payload = {
            "model": MAIN_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "stream": True
        }
        response = await self._execute_request(payload, stream=True)
        try:
            in_thought_block = False
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "reasoning_content" in delta: continue
                        content = delta.get("content", "")
                        if not content: continue
                        if "<think>" in content:
                            in_thought_block = True
                            content = content.replace("<think>", "")
                        if "</think>" in content:
                            in_thought_block = False
                            content = content.split("</think>")[-1]
                        if not in_thought_block and content:
                            yield content
                    except json.JSONDecodeError:
                        continue
        finally:
            await response.aclose()