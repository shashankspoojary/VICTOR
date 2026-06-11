import re

def prune_file_blocks(text: str, max_len: int = 1000) -> str:
    """
    Finds file upload blocks like:
    --- Start of File: filename ---
    [content]
    --- End of File: filename ---
    and truncates the content to max_len characters if it exceeds it.
    """
    if "--- Start of File:" not in text:
        return text
        
    def replace_match(match):
        filename = match.group(1)
        content = match.group(2)
        content_len = len(content)
        if content_len > max_len:
            return (
                f"--- Start of File: {filename} ---\n"
                f"{content[:max_len]}\n"
                f"... [TRUNCATED {content_len - max_len} CHARACTERS FOR CONTEXT AND RATE LIMITS] ...\n"
                f"--- End of File: {filename} ---"
            )
        return match.group(0)
        
    return re.sub(r'--- Start of File: (.*?) ---\n(.*?)\n--- End of File: \1 ---', replace_match, text, flags=re.DOTALL)

def prune_context(context: str, max_chars: int = 12000) -> str:
    """
    Slices incoming memory_context/history to prevent token/request overflows.
    """
    if not context or len(context) <= max_chars:
        return context
        
    # Keep 30% from the start and 70% from the end to prioritize recent history/data
    keep_start = int(max_chars * 0.3)
    keep_end = max_chars - keep_start - 100 # safety margin and truncation message
    
    start_part = context[:keep_start]
    end_part = context[-keep_end:]
    
    return f"{start_part}\n\n... [TRUNCATED FOR CONTEXT LIMITS] ...\n\n{end_part}"
