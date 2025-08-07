import random
from datetime import datetime


def generate_ticket_id():
    """
    Generate a unique ticket ID in the format TKT-YYYYMMDD-XXXX
    where XXXX is a random 4-digit number

    Returns:
        str: Unique ticket ID
    """
    # Get current date in YYYYMMDD format
    date_part = datetime.now().strftime("%Y%m%d")

    # Generate random 4-digit number
    random_part = random.randint(1000, 9999)

    # Combine to create ticket ID
    ticket_id = f"TKT-{date_part}-{random_part}"

    return ticket_id
