from datetime import datetime, timezone

def get_current_timestamp() -> str:
    """Returns ISO 8601 formatted UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()

def get_formatted_time() -> str:
    """Returns human-readable current time for AI context."""
    return datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")