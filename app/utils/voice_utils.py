# app/utils/voice_utils.py
import re

def sanitize_for_tts(text: str) -> str:
    """Removes markdown and code formatting to ensure clean speech synthesis."""
    # Remove markdown bold/italics
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://\S+', 'a web link', text)
    
    # Remove code blocks
    text = re.sub(r'```.*?```', 'a block of code', text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'\1', text)
    
    # Remove excessive symbols
    text = re.sub(r'[#\>\]\[\-\_]', ' ', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_sentence_end(text: str) -> bool:
    """Detects if a string ends with a sentence-terminating punctuation mark."""
    stripped = text.strip()
    if not stripped:
        return False
    return stripped[-1] in ['.', '!', '?']