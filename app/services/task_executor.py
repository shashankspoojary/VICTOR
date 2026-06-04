import asyncio
import logging
import webbrowser
import subprocess
import os
import ast
from pathlib import Path

logger = logging.getLogger(__name__)

class TaskExecutor:
    def __init__(self):
        pass

    async def scan_workspace_directory(self, folder_path: str) -> str:
        """
        Safely scans a local directory, generating a file map and running
        structural health checks on any python files found in the root.
        """
        try:
            target_dir = Path(folder_path).resolve()
            if not target_dir.exists() or not target_dir.is_dir():
                return f"System Action Failed: Directory '{folder_path}' does not exist or is invalid."
            
            ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv'}
            file_map = []
            py_files_root = []
            
            total_files = 0
            total_dirs = 0
            extensions = {}
            
            for root, dirs, files in os.walk(target_dir):
                # Ignore typical massive build or tracking paths
                dirs[:] = [d for d in dirs if d not in ignore_dirs and not (d == 'temp' and Path(root).name == 'workspace')]
                total_dirs += len(dirs)
                
                level = str(Path(root).resolve()).replace(str(target_dir), '').count(os.sep)
                indent = ' ' * 4 * level
                file_map.append(f"{indent}📁 {Path(root).name}/")
                sub_indent = ' ' * 4 * (level + 1)
                for f in files:
                    total_files += 1
                    ext = Path(f).suffix.lower() or "no_extension"
                    extensions[ext] = extensions.get(ext, 0) + 1
                    file_map.append(f"{sub_indent}📄 {f}")
                    if level == 0 and f.endswith('.py'):
                        py_files_root.append(Path(root) / f)

            tree_output = "\n".join(file_map)
            
            compilation_diagnostics = []
            for py_file in py_files_root:
                try:
                    with open(py_file, 'r', encoding='utf-8') as pf:
                        content = pf.read()
                    ast.parse(content, filename=py_file.name)
                    compilation_diagnostics.append(f"✅ {py_file.name}: Syntax OK")
                except SyntaxError as e:
                    compilation_diagnostics.append(f"❌ {py_file.name}: SyntaxError at line {e.lineno} - {e.msg}")
                except Exception as e:
                    compilation_diagnostics.append(f"⚠️ {py_file.name}: Could not read or parse ({e})")
            
            diag_str = "\n".join(compilation_diagnostics) if compilation_diagnostics else "No Python files found in root."
            stats_str = f"- **Total Directories:** {total_dirs}\n- **Total Files:** {total_files}\n- **Extensions Breakdown:** {', '.join([f'`{k}`: {v}' for k, v in extensions.items()])}"
            
            result_md = (
                f"### Directory Map: `{folder_path}`\n"
                f"```text\n{tree_output}\n```\n\n"
                f"### File Statistics\n"
                f"{stats_str}\n\n"
                f"### Root level Compilation Health Checks\n"
                f"```text\n{diag_str}\n```"
            )
            return result_md
            
        except Exception as e:
            logger.error(f"Workspace directory scan failed: {e}")
            return f"System Action Failed: Error scanning directory: {e}"

    async def execute_task(self, command_data: dict) -> str:
        """
        Executes a background system task or tool securely.
        """
        try:
            action = command_data.get("action")
            target = command_data.get("target")

            if not action or not target:
                return "System action failed: Missing action or target parameters."

            if action == "open_url":
                logger.info(f"Opening URL: {target}")
                webbrowser.open(target)
                return f"System action executed successfully: Launched URL target '{target}'."
                
            elif action == "launch_tool":
                logger.info(f"Launching tool: {target}")
                # Initiate a non-blocking background process safely
                process = await asyncio.create_subprocess_shell(
                    target,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                return f"System action executed successfully: Launched primary developer tool '{target}'."
                
            else:
                return f"System action failed: Unknown action '{action}'."

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return f"System action failed: {str(e)}"
