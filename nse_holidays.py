"""
NSE Trading Holiday Calendar & Market Schedule Validator.
Prevents bot execution, Telegram alerts, and web updates on weekends and official NSE holidays.
"""
from datetime import datetime, date
from typing import Optional, Tuple

# Official NSE Trading Holidays (Cash Market & Derivatives)
# Formatted as YYYY-MM-DD
NSE_HOLIDAYS = {
    # 2026 NSE Holidays
    "2026-01-26": "Republic Day",
    "2026-02-17": "Mahashivratri",
    "2026-03-03": "Holi",
    "2026-03-20": "Id-Ul-Fitr (Ramzan Id)",
    "2026-03-27": "Ram Navami",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-27": "Bakri Id / Eid ul-Adha",
    "2026-08-15": "Independence Day",
    "2026-08-26": "Milad-un-Nabi",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-08": "Diwali (Laxmi Pujan)",
    "2026-11-10": "Diwali Balipratipada",
    "2026-11-24": "Gurunanak Jayanti",
    "2026-12-25": "Christmas",

    # 2025 NSE Holidays (Reference)
    "2025-01-26": "Republic Day",
    "2025-02-26": "Mahashivratri",
    "2025-03-14": "Holi",
    "2025-03-31": "Id-Ul-Fitr",
    "2025-04-10": "Mahavir Jayanti",
    "2025-04-14": "Dr. Ambedkar Jayanti",
    "2025-04-18": "Good Friday",
    "2025-05-01": "Maharashtra Day",
    "2025-08-15": "Independence Day",
    "2025-08-27": "Ganesh Chaturthi",
    "2025-10-02": "Gandhi Jayanti / Dussehra",
    "2025-10-21": "Diwali",
    "2025-10-22": "Diwali Balipratipada",
    "2025-11-05": "Gurunanak Jayanti",
    "2025-12-25": "Christmas",
}

def is_market_holiday(target_date: Optional[date] = None) -> Tuple[bool, str]:
    """
    Checks if a given date is a weekend or an official NSE trading holiday.
    Returns: (is_closed: bool, reason: str)
    """
    if target_date is None:
        target_date = datetime.now().date()
        
    date_str = target_date.strftime("%Y-%m-%d")
    weekday = target_date.weekday() # 0 = Mon, 5 = Sat, 6 = Sun
    
    # 1. Check Weekend (Saturday or Sunday)
    if weekday == 5:
        return True, "Saturday (Weekend)"
    elif weekday == 6:
        return True, "Sunday (Weekend)"
        
    # 2. Check NSE Official Holiday List
    if date_str in NSE_HOLIDAYS:
        return True, f"NSE Holiday: {NSE_HOLIDAYS[date_str]}"
        
    return False, "Market is Open"

if __name__ == '__main__':
    today = datetime.now().date()
    closed, reason = is_market_holiday(today)
    print(f"Today ({today}): Closed={closed} | Reason={reason}")
