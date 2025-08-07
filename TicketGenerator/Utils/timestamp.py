from datetime import datetime

def get_current_timestamp_str():
    """
    Get the current UTC timestamp as a formatted string without timezone info

    Returns:
        str: Current timestamp in ISO format without timezone info
    """
    current_timestamp = datetime.utcnow()
    current_timestamp_str = current_timestamp.isoformat()
    return current_timestamp_str
