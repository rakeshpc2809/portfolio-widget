"""Market-aware governor determining fetch schedules and market windows."""
import datetime
import time

# Timezone offset for Indian Standard Time (UTC+5:30)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def get_current_ist_time() -> datetime.datetime:
    return datetime.datetime.now(IST)


def get_market_state(now_ist: datetime.datetime = None) -> str:
    """Returns IN_OPEN, US_OPEN, or CLOSED."""
    if now_ist is None:
        now_ist = get_current_ist_time()

    weekday = now_ist.weekday()  # Monday=0, Sunday=6
    hour = now_ist.hour
    minute = now_ist.minute
    time_min = hour * 60 + minute

    # NSE / BSE Window: Mon-Fri, 09:00 to 16:00 IST (540 to 960 min)
    if 0 <= weekday <= 4:
        if 540 <= time_min < 960:
            return "IN_OPEN"

    # US Market Window in IST: Mon-Fri 19:00 to 02:00 next day
    # Mon-Fri evenings (1140 to 1440 min)
    if 0 <= weekday <= 4 and time_min >= 1140:
        return "US_OPEN"
    # Tue-Sat early mornings (00:00 to 02:00 IST = 0 to 120 min)
    if 1 <= weekday <= 5 and time_min < 120:
        return "US_OPEN"

    return "CLOSED"


def should_execute_fetch(last_fetch_ts: float, force: bool = False) -> tuple[bool, str, str]:
    """
    Decides whether a network fetch should run based on market hours and cache age.
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
        # 60 minutes off-hours / weekends
        if age_sec >= 60 * 60:
            return True, f"off-hours and cache is {int(age_sec/60)}m old", state
        return False, f"off-hours and cache is fresh ({int(age_sec/60)}m old)", state
