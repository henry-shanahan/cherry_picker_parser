import re
from datetime import datetime, timedelta

# By storing known data in a central utility file, it's easier to manage and update.
# Any part of your program can import this list.
KNOWN_CHARTERERS = [
    "P66", "Neste", "Bunge", "Cargill", "Nova", "Olam", "ENI",
    "SK Energy", "ICOF", "Kolmar", "Petroineos", "Wilmar", "GAM", "Aramco"
]


def normalize_laycan(laycan_str: str) -> dict:
    """
    Converts a variety of laycan date strings into a standardized dictionary
    with start and end dates in 'YYYY-MM-DD' format.

    Args:
        laycan_str: The raw laycan string (e.g., "2H June", "10-20 Jul").

    Returns:
        A dictionary with 'start_date' and 'end_date' keys.
    """
    if not laycan_str or laycan_str == "N/A":
        return {"start_date": None, "end_date": None}

    now = datetime.now()
    # Assume the current year unless the data suggests otherwise.
    # This can be adjusted if your data spans multiple years.
    year = now.year

    # Standardize month abbreviations for the datetime parser
    laycan_str = laycan_str.replace("–", "-").strip()
    month_map = {
        'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April',
        'may': 'May', 'jun': 'June', 'jul': 'July', 'aug': 'August',
        'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
    }
    for k, v in month_map.items():
        laycan_str = laycan_str.lower().replace(k, v)

    start_date, end_date = None, None

    # Case 1: Date range (e.g., "06-10 June" or "25 June - 5 July")
    range_match = re.match(r'(\d{1,2})\s*-\s*(\d{1,2})\s+([a-zA-Z]+)', laycan_str)
    cross_month_match = re.match(r'(\d{1,2})\s+([a-zA-Z]+)\s*-\s*(\d{1,2})\s+([a-zA-Z]+)', laycan_str)

    if range_match:
        start_day, end_day, month_str = range_match.groups()
        start_date = datetime.strptime(f"{start_day} {month_str} {year}", "%d %B %Y")
        end_date = datetime.strptime(f"{end_day} {month_str} {year}", "%d %B %Y")

    elif cross_month_match:
        start_day, start_month, end_day, end_month = cross_month_match.groups()
        start_date = datetime.strptime(f"{start_day} {start_month} {year}", "%d %B %Y")
        end_date = datetime.strptime(f"{end_day} {end_month} {year}", "%d %B %Y")
        # Handle year change for ranges like "end December - ely January"
        if end_date < start_date:
            end_date = end_date.replace(year=year + 1)

    # Case 2: Vague terms (e.g., "Early June", "2H June")
    else:
        try:
            month_str = re.search(r'[a-zA-Z]+', laycan_str).group(0)
            month = datetime.strptime(month_str, "%B").month

            if "early" in laycan_str or "ely" in laycan_str:
                start_date = datetime(year, month, 1)
                end_date = datetime(year, month, 10)

            elif "2h" in laycan_str:
                start_date = datetime(year, month, 16)
                # Find the last day of the month
                next_month = start_date.replace(day=28) + timedelta(days=4)
                end_date = next_month - timedelta(days=next_month.day)

            elif "end" in laycan_str:
                # Find the last day of the month
                next_month_first_day = (datetime(year, month, 1) + timedelta(days=32)).replace(day=1)
                last_day_of_month = next_month_first_day - timedelta(days=1)
                start_date = last_day_of_month - timedelta(days=6)  # Assume "end" means last 7 days
                end_date = last_day_of_month

        except (AttributeError, ValueError):
            # If parsing fails, return None
            return {"start_date": None, "end_date": None}

    return {
        "start_date": start_date.strftime('%Y-%m-%d') if start_date else None,
        "end_date": end_date.strftime('%Y-%m-%d') if end_date else None
    }


if __name__ == '__main__':
    # This section allows you to test the utils file directly
    print("--- Testing utils.py ---")

    # Test Charterer List
    print(f"Known Charterers: {KNOWN_CHARTERERS}")

    # Test Laycan Normalization
    test_laycans = [
        "06-10 June",
        "Ely Jun",
        "2H June",
        "end June",
        "25 Jun - 5 July",
        "1-10 Jul"
    ]

    for laycan in test_laycans:
        normalized = normalize_laycan(laycan)
        print(f"'{laycan}' -> Start: {normalized['start_date']}, End: {normalized['end_date']}")