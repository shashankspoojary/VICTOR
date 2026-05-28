# app/services/file_editor_service.py
import os
import shutil
from pathlib import Path
from typing import Optional

class FileEditorService:
    """Performs atomic disk operations, modifications, and replacements on source targets."""

    def read_target_file(self, path: Path) -> Optional[str]:
        """Reads content from specified target paths securely."""
        if not path.exists() or not path.is_file():
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_target_file(self, path: Path, content: str, auto_backup: bool = True) -> bool:
        """Safely commits content changes to disk using atomic temporary updates and optional rollbacks."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Enforce historical safety backup constraints
            if path.exists() and auto_backup:
                backup_target = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, backup_target)
                
            temp_target = path.with_suffix(path.suffix + ".tmp")
            with open(temp_target, 'w', encoding='utf-8') as f:
                f.write(content)
                
            # Perform atomic replacement switch across standard filesystems
            os.replace(temp_target, path)
            return True
        except Exception:
            if 'temp_target' in locals() and Path(temp_target).exists():
                os.remove(temp_target)
            return False

    def modify_target_block(self, path: Path, old_block: str, new_block: str) -> bool:
        """Locates specific old logic structures inside a file and updates them precisely."""
        current_data = self.read_target_file(path)
        if not current_data or old_block not in current_data:
            return False
            
        updated_data = current_data.replace(old_block, new_block)
        return self.write_target_file(path, updated_data)

    def append_to_file(self, path: Path, extra_content: str) -> bool:
        """Appends definitions or implementations cleanly to structural file conclusions."""
        current_data = self.read_target_file(path) or ""
        delimiter = "\n\n" if current_data else ""
        return self.write_target_file(path, current_data + delimiter + extra_content)