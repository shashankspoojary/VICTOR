import os
import sys
import subprocess
import webbrowser
import re
import logging
import urllib.parse
from typing import Dict, Any

try:
    import config
except ImportError:
    config = None

logger = logging.getLogger(__name__)

class TaskExecutor:
    def __init__(self):
        self.programs = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "cmd": "cmd.exe",
            "paint": "mspaint.exe"
        }

    def execute_task(self, task_type: str, clean_query: str) -> dict:
        result = {
            "status": "success",
            "task": task_type,
            "detail": ""
        }
        
        try:
            if task_type == "open":
                query_lower = clean_query.strip().lower()
                
                # Check if it represents a website link
                if re.search(r'\.|www|http|com|org|net', query_lower):
                    url = query_lower
                    if not url.startswith('http'):
                        url = f"https://{url}"
                    webbrowser.open(url)
                    result["detail"] = f"Opened website: {url}"
                
                # Check if it matches a key in the program lookup dictionary
                elif query_lower in self.programs:
                    executable_path = self.programs[query_lower]
                    subprocess.Popen([executable_path], start_new_session=True)
                    result["detail"] = f"Launched program: {executable_path}"
                
                # Unrecognized, attempt direct fallback
                else:
                    subprocess.Popen(clean_query, shell=True)
                    result["detail"] = f"Executed fallback command: {clean_query}"
                    
            elif task_type == "play":
                encoded_query = urllib.parse.quote(clean_query)
                url = f"https://www.youtube.com/results?search_query={encoded_query}"
                webbrowser.open(url)
                result["detail"] = f"Playing on YouTube: {clean_query}"
                
            elif task_type == "google_search":
                encoded_query = urllib.parse.quote(clean_query)
                url = f"https://www.google.com/search?q={encoded_query}"
                webbrowser.open(url)
                result["detail"] = f"Google search for: {clean_query}"
                
            elif task_type == "youtube_search":
                encoded_query = urllib.parse.quote(clean_query)
                url = f"https://www.youtube.com/results?search_query={encoded_query}"
                webbrowser.open(url)
                result["detail"] = f"YouTube search for: {clean_query}"
            
            else:
                result["status"] = "failed"
                result["detail"] = f"Unknown task type: {task_type}"

        except Exception as e:
            logger.error(f"Execution failed for task '{task_type}' with query '{clean_query}': {e}")
            result["status"] = "failed"
            result["detail"] = str(e)
            
        return result

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor = TaskExecutor()
    
    print("Testing TaskExecutor...")
    
    # Dry-run test attempting to open 'google.com'
    print("Testing open website (google.com):")
    res1 = executor.execute_task("open", "google.com")
    print(res1)
    
    # Dry-run test launching a non-blocking instance of 'notepad'
    print("\nTesting open program (notepad):")
    res2 = executor.execute_task("open", "notepad")
    print(res2)
