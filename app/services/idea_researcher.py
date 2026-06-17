import os
import re
import json
import datetime
import asyncio
import config
from app.services.realtime_service import realtime_service
from app.services.ai_service import ai_service
from rich.console import Console

console = Console()

class IdeaResearcher:
    async def run_research(self, focus: str = "", event_queue: asyncio.Queue = None) -> str:
        """
        Runs multiple searches targeting app/website ideas, pain points, and successful copies.
        Returns a single conversational markdown explanation string.
        """
        focus_label = focus.strip() if focus else "General app/website ideas"
        console.print(f"[cyan][Idea Researcher] Starting scan for focus: '{focus_label}'[/cyan]")

        current_year = datetime.datetime.now().year # 2026
        # 1. Prepare search queries focusing on the current year 2026/recent reports
        queries = []
        if focus:
            queries.append(f'site:reddit.com "any app for" OR "is there an app" OR "someone should build" "{focus}" {current_year}')
            queries.append(f'site:reddit.com/r/startup OR site:reddit.com/r/SideProject OR site:reddit.com/r/Entrepreneur "pain point" OR "solve" "{focus}" {current_year}')
            queries.append(f'profitable "{focus}" micro-saas OR apps making money low competition {current_year}')
            queries.append(f'site:indiehackers.com "{focus}" revenue OR mrr OR "making money" {current_year}')
        else:
            queries.append(f'site:reddit.com "any app for" OR "is there an app" OR "someone should build" "ideas" OR "pain point" {current_year}')
            queries.append(f'site:reddit.com/r/SideProject OR site:reddit.com/r/Entrepreneur "pain point" OR "wish there was" {current_year}')
            queries.append(f'successful niche micro-saas apps making money low competition {current_year}')
            queries.append(f'site:indiehackers.com "profitable side projects" OR "revenue" OR "mrr" {current_year}')

        # 2. Run searches in parallel
        tasks = [realtime_service.search(q) for q in queries]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. Aggregate results and build source reference list (strictly truncated to prevent rate limits)
        combined_text = ""
        
        for idx, res in enumerate(search_results):
            query_used = queries[idx]
            if isinstance(res, Exception):
                console.print(f"[red][Idea Researcher] Search failed for '{query_used}': {res}[/red]")
                continue
            
            # Truncate each query summary to 1500 chars to stay well within token limits (avoiding TPM rate limits)
            summary = res.get("summary", "")[:1500]
            combined_text += f"--- Search Results for Query: {query_used} ---\n{summary}\n\n"

        # 4. Request AI distillation to generate conversational response
        now_str = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")
        system_prompt = f"""You are VICTOR's Premium App and Website Idea Researcher and Distillation Engine.
Your goal is to parse raw search results from Reddit, Quora, IndieHackers, and elsewhere, and generate a comprehensive, highly professional, and easy-to-understand explanation of app/website opportunities that the user can build or copy.

CRITICAL REQUIREMENTS:
- CONVERSATIONAL & EASY-TO-UNDERSTAND: Do not output HTML code. Output structured, easy-to-read markdown. Explain everything clearly so it can be read aloud by VICTOR's voice system.
- ZERO TRIVIAL OR GENERIC IDEAS: Do NOT suggest simple, generic, tutorial-level, or basic ideas. This includes simple calculators, basic portfolio builders, to-do lists, notes apps, blog platforms, basic habit trackers, password generators, or generic AI wrappers.
- IN-DEPTH TELEMETRY ANALYSIS: Every idea MUST stem directly from a specific, real-world pain point or complaint extracted from the provided search results (e.g., a specific Reddit thread, a Quora user's frustration, or a verified IndieHackers case study).
- TARGET UNMET OR UNDER-CLONED NEEDS: The concept must represent a powerful, realistic solution to a problem that people are actively seeking help for, but which has few, low-quality, or outdated solutions.

For each idea, explain:
1. The Concept & The Core Problem (referencing real user complaints).
2. How the App/Website Works (simple workflow explanation).
3. Step-by-Step Developer Implementation Guide (how to set it up, database structure, and key logic).
4. Code Starter Snippet or Database Schema (provide a small, realistic code template or schema script).
5. Suggested Tech Stack & Monetization Model.

Maintain VICTOR's JARVIS-like persona. Talk directly with quiet intelligence, quiet confidence, and clarity.
"""

        user_content = f"""Current Scan Focus: {focus_label}
Scan Date: {now_str}

Sources Collected:
{combined_text[:5000]}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            explanation = await ai_service.get_chat_completion(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.3
            )
            return explanation.strip()
        except Exception as e:
            console.print(f"[red][Idea Researcher] AI Completion failed: {e}[/red]")
            return f"I encountered an error during distillation, Sir: {e}. However, my search telemetry indicates the following raw points:\n\n{combined_text[:1200]}"

idea_researcher = IdeaResearcher()
