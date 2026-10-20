"""Market-aware governor determining fetch schedules and market windows."""
import datetime
import time

# Timezone offset for Indian Standard Time (UTC+5:30)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# 2026 NSE (Indian) Trading Holidays (Monday-Friday)
NSE_HOLIDAYS_2026 = {
    datetime.date(2026, 1, 26),  # Republic Day
    datetime.date(2026, 3, 3),   # Holi
    datetime.date(2026, 3, 20),  # Id-ul-Fitr (Ramzan Id)
    datetime.date(2026, 4, 3),   # Good Friday
    datetime.date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
    datetime.date(2026, 5, 1),   # Maharashtra Day
    datetime.date(2026, 5, 27),  # Bakri Id / Eid ul-Adha
    datetime.date(2026, 6, 26),  # Muharram
    datetime.date(2026, 10, 2),  # Mahatma Gandhi Jayanti
    datetime.date(2026, 10, 20), # Dussehra
    datetime.date(2026, 11, 10), # Diwali Balipratipada
    datetime.date(2026, 11, 24), # Gurunanak Jayanti
    datetime.date(2026, 12, 25), # Christmas
}

# 2026 NYSE (US) Trading Holidays (Monday-Friday)
NYSE_HOLIDAYS_2026 = {
    datetime.date(2026, 1, 1),   # New Year's Day
    datetime.date(2026, 1, 19),  # Martin Luther King Jr. Day
    datetime.date(2026, 2, 16),  # Washington's Birthday / Presidents' Day
    datetime.date(2026, 4, 3),   # Good Friday
    datetime.date(2026, 5, 25),  # Memorial Day
    datetime.date(2026, 6, 19),  # Juneteenth National Independence Day
    datetime.date(2026, 7, 3),   # Independence Day (Observed)
    datetime.date(2026, 9, 7),   # Labor Day
    datetime.date(2026, 11, 26), # Thanksgiving Day
    datetime.date(2026, 12, 25), # Christmas Day
}


def is_nse_holiday(d: datetime.date) -> bool:
    """Returns True if the given date is an official 2026 NSE trading holiday."""
    return d in NSE_HOLIDAYS_2026


def is_nyse_holiday(d: datetime.date) -> bool:
    """Returns True if the given date is an official 2026 NYSE trading holiday."""
    return d in NYSE_HOLIDAYS_2026


def get_current_ist_time() -> datetime.datetime:
    return datetime.datetime.now(IST)


def get_market_state(now_ist: datetime.datetime | None = None) -> str:
    """
    Returns IN_OPEN, US_OPEN, or CLOSED.
    Evaluates exchange windows and short-circuits to CLOSED on market holidays.
    """
    if now_ist is None:
        now_ist = get_current_ist_time()

    weekday = now_ist.weekday()  # Monday=0, Sunday=6
    hour = now_ist.hour
    minute = now_ist.minute
    time_min = hour * 60 + minute

    # 1. NSE / BSE Window: Mon-Fri, 09:00 to 16:00 IST (540 to 960 min)
    if 0 <= weekday <= 4 and 540 <= time_min < 960:
        if not is_nse_holiday(now_ist.date()):
            return "IN_OPEN"

    # 2. US Market Window in IST: Mon-Fri 19:00 to 02:00 next day
    # Mon-Fri evenings (1140 to 1440 min)
    if 0 <= weekday <= 4 and time_min >= 1140:
        if not is_nyse_holiday(now_ist.date()):
            return "US_OPEN"
    # Tue-Sat early mornings (00:00 to 02:00 IST = 0 to 120 min) -> corresponds to previous calendar day in US
    if 1 <= weekday <= 5 and time_min < 120:
        us_trade_date = (now_ist - datetime.timedelta(days=1)).date()
        if not is_nyse_holiday(us_trade_date):
            return "US_OPEN"

    return "CLOSED"


def is_market_open(now_ist: datetime.datetime | None = None) -> bool:
    """Returns True if either Indian or US markets are currently open."""
    return get_market_state(now_ist) in ("IN_OPEN", "US_OPEN")


def should_execute_fetch(last_fetch_ts: float, force: bool = False) -> tuple[bool, str, str]:
    """
    Decides whether a network fetch should run based on market hours, holidays, and cache age.
    Returns (should_fetch, reason, market_state).
    """
    now = time.time()
    now_ist = get_current_ist_time()
    state = get_market_state(now_ist)

    if force:
        return True, "forced by user request", state

    if last_fetch_ts <= 0:
        return True, "initial fetch / no previous cache", state

    age_sec = now - last_fetch_ts

    if state in ("IN_OPEN", "US_OPEN"):
        # 15 minutes during active market windows
        if age_sec >= 15 * 60:
            return True, f"market active ({state}) and cache is {int(age_sec/60)}m old", state
        return False, f"market active ({state}) but cache is fresh ({int(age_sec/60)}m old)", state
    else:
        # 60 minutes off-hours / weekends / holidays
        if age_sec >= 60 * 60:
            return True, f"off-hours and cache is {int(age_sec/60)}m old", state
        return False, f"off-hours and cache is fresh ({int(age_sec/60)}m old)", state
