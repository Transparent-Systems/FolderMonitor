"""
Version: v1.0

This script contains utility static methods
"""

def convert_to_seconds(time_str) -> int:
    """
    Converts a time string (e.g., "1m", "5s", "1h", "2d") to seconds.

    Args:
        time_str (str): The time string to convert.

    Returns:
        int: The time in seconds.
    """
    if time_str is None:
        return 0

    if not isinstance(time_str, str) or not time_str:
        return 0
    
    # Convert to lowercase
    time_str = time_str.strip().lower()

    # If time_str is an integer, the return that value
    if time_str.isdigit():
        return int(time_str)

    seconds = 0
    if time_str == "":
        seconds =  0
    elif time_str.endswith("s"):
        seconds = int(time_str[:-1])
    elif time_str.endswith("m"):
        seconds = int(time_str[:-1]) * 60
    elif time_str.endswith("h"):
        seconds = int(time_str[:-1]) * 3600
    elif time_str.endswith("d"):
        seconds = int(time_str[:-1]) * 86400
    
    return seconds
