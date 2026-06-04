from datetime import datetime

def get_temporal_string() -> str:
    """
    Returns a highly descriptive temporal context string for prompt injection.
    Example output: 'Current Date: Thursday, June 04, 2026. Local Time: 19:22:34'
    """
    now = datetime.now()
    # %A: Full weekday name
    # %B: Full month name
    # %d: Day of the month as a zero-padded decimal number
    # %Y: Year with century as a decimal number
    # %H:%M:%S: Hour:Minute:Second in 24-hour format
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%H:%M:%S")
    
    return f"Current Date: {date_str}. Local Time: {time_str}"
