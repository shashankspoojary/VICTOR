import datetime

def get_current_time_context() -> str:
    """
    Returns the current real-world year, date, time, and timezone
    in a clean string format to be injected into system prompts.
    """
    now = datetime.datetime.now()
    local_tz = now.astimezone().tzinfo
    
    current_year = now.year
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    timezone_name = str(local_tz)

    return f"Year: {current_year} | Date: {current_date} | Time: {current_time} | Timezone: {timezone_name}"
