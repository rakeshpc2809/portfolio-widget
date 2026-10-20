"""Market-aware governor determining fetch schedules and market windows with zero-maintenance dynamic holiday resolution."""
import datetime
import time
from typing import Any

# Timezone offset for Indian Standard Time (UTC+5:30)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# Dynamic holiday lookup via Python's `holidays` library
try:
    import holidays

    _HAS_HOLIDAYS = True
except ImportError:
    holidays = None
    _HAS_HOLIDAYS = False

_IN_HOLIDAYS_CACHE: dict[int, set[datetime.date]] = {}
_NYSE_HOLIDAYS_CACHE: dict[int, set[datetime.date]] = {}


def get_in_holidays(year: int) -> set[datetime.date]:
    """Dynamically resolves Indian public/exchange holidays for any given year."""
    if year not in _IN_HOLIDAYS_CACHE:
        if _HAS_HOLIDAYS and holidays is not None:
            try:
                _IN_HOLIDAYS_CACHE[year] = set(holidays.country_holidays("IN", years=year).keys())
            except Exception:
                _IN_HOLIDAYS_CACHE[year] = set()
        else:
            _IN_HOLIDAYS_CACHE[year] = set()
    return _IN_HOLIDAYS_CACHE[year]


def get_nyse_holidays(year: int) -> set[datetime.date]:
    """Dynamically resolves NYSE financial trading holidays for any given year."""
    if year not in _NYSE_HOLIDAYS_CACHE:
        if _HAS_HOLIDAYS and holidays is not None:
            try:
                _NYSE_HOLIDAYS_CACHE[year] = set(holidays.financial_holidays("NYSE", years=year).keys())
            except Exception:
                _NYSE_HOLIDAYS_CACHE[year] = set()
        else:
            _NYSE_HOLIDAYS_CACHE[year] = set()
    return _NYSE_HOLIDAYS_CACHE[year]


def is_nse_holiday(d: datetime.date) -> bool:
    """Returns True if the given date is an official Indian public/exchange holiday."""
    return d in get_in_holidays(d.year)


def is_nyse_holiday(d: datetime.date) -> bool:
    """Returns True if the given date is an official NYSE financial holiday."""
    return d in get_nyse_holidays(d.year)


def get_current_ist_time() -> datetime.datetime:
    return datetime.datetime.now(IST)


def get_nominal_market_state(now_ist: datetime.datetime | None = None) -> str:
    """
    Returns the nominal market window (IN_OPEN, US_OPEN, or CLOSED)
    based on day of week, time of day, and calendar holidays.
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


def get_market_state(now_ist: datetime.datetime | None = None, unchanged_streak: int = 0) -> str:
    """
    Returns IN_OPEN, US_OPEN, or CLOSED.
    If unchanged_streak >= 2 during nominal market hours (stagnant/frozen data),
    auto-throttles to CLOSED.
    """
    nominal = get_nominal_market_state(now_ist)
    if nominal in ("IN_OPEN", "US_OPEN") and unchanged_streak >= 2:
        return "CLOSED"
    return nominal


def is_market_open(now_ist: datetime.datetime | None = None, unchanged_streak: int = 0) -> bool:
    """Returns True if either Indian or US markets are currently open and active."""
    return get_market_state(now_ist, unchanged_streak=unchanged_streak) in ("IN_OPEN", "US_OPEN")


def should_fetch(
    state: dict[str, Any] | None = None,
    force: bool = False,
    now: float | None = None
) -> tuple[bool, str, str]:
    """
    Decides whether a fetch should occur based on state, unchanged_streak, and market hours.
    Returns (should_fetch, reason, market_state).
    """
    if now is None:
        now = time.time()

    now_ist = datetime.datetime.fromtimestamp(now, tz=IST)
    last_fetch_ts = 0.0
    unchanged_streak = 0

    if isinstance(state, dict):
        unchanged_streak = int(state.get("unchanged_streak", 0))
        if "updated_at" in state:
            last_fetch_ts = float(state["updated_at"])

    nominal_state = get_nominal_market_state(now_ist)

    # Check nominal window transition from previous sync (e.g. CLOSED -> IN_OPEN)
    window_transition_bell = False
    prev_nominal = None
    if last_fetch_ts > 0:
        prev_ist = datetime.datetime.fromtimestamp(last_fetch_ts, tz=IST)
        prev_nominal = get_nominal_market_state(prev_ist)
        if prev_nominal != nominal_state:
            unchanged_streak = 0
            # If entering an active market window, schedule immediate opening bell sync
            if nominal_state in ("IN_OPEN", "US_OPEN"):
                window_transition_bell = True

    market_state = get_market_state(now_ist, unchanged_streak=unchanged_streak)

    if force:
        return True, "forced by user request", market_state

    if last_fetch_ts <= 0:
        return True, "initial fetch / no previous cache", market_state

    if window_transition_bell:
        return True, f"opening bell window transition ({prev_nominal} -> {nominal_state})", nominal_state

    age_sec = now - last_fetch_ts

    # Stagnant-Market Auto-Backoff:
    # If unchanged_streak >= 2 during nominal trading hours, throttle back to 60-minute interval
    # and display "CLOSED" for market_state.
    if nominal_state in ("IN_OPEN", "US_OPEN") and unchanged_streak >= 2:
        if age_sec >= 60 * 60:
            return True, f"stagnant market backoff (streak={unchanged_streak}) and cache is {int(age_sec/60)}m old", "CLOSED"
        return False, f"stagnant market backoff (streak={unchanged_streak}) and cache is fresh ({int(age_sec/60)}m old)", "CLOSED"

    if market_state in ("IN_OPEN", "US_OPEN"):
        # 15 minutes during active market windows
        if age_sec >= 15 * 60:
            return True, f"market active ({market_state}) and cache is {int(age_sec/60)}m old", market_state
        return False, f"market active ({market_state}) but cache is fresh ({int(age_sec/60)}m old)", market_state
    else:
        # 60 minutes off-hours / weekends / holidays
        if age_sec >= 60 * 60:
            return True, f"off-hours and cache is {int(age_sec/60)}m old", market_state
        return False, f"off-hours and cache is fresh ({int(age_sec/60)}m old)", market_state


def should_execute_fetch(
    last_fetch_ts: float,
    force: bool = False,
    unchanged_streak: int = 0,
    now: float | None = None,
) -> tuple[bool, str, str]:
    """Compatibility wrapper for should_fetch."""
    state = {"updated_at": last_fetch_ts, "unchanged_streak": unchanged_streak}
    return should_fetch(state=state, force=force, now=now)
