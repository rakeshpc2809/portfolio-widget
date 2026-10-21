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


def is_nav_window(now_ist: datetime.datetime | None = None) -> bool:
    """
    Returns True if current IST time falls within Indian mutual fund T+1 NAV publication windows:
    - Morning window: 07:30 to 09:30 IST
    - Evening window: 21:30 to 23:30 IST
    """
    if now_ist is None:
        now_ist = get_current_ist_time()

    time_min = now_ist.hour * 60 + now_ist.minute
    # Morning: 07:30 (450m) to 09:30 (570m)
    if 450 <= time_min < 570:
        return True
    # Evening: 21:30 (1290m) to 23:30 (1410m)
    if 1290 <= time_min < 1410:
        return True

    return False


def get_direct_equity_weight(state: dict[str, Any] | None) -> float:
    """Calculates direct equity weight percentage (Indian stocks + US stocks) from state."""
    if not isinstance(state, dict):
        return 0.0

    # 1. From v2 allocations.items
    allocations = state.get("allocations")
    if isinstance(allocations, dict):
        items = allocations.get("items", [])
        if isinstance(items, list):
            eq_weight = 0.0
            found = False
            for it in items:
                if isinstance(it, dict) and it.get("id") in ("indian_stocks", "us_stocks", "stocks", "in_eq", "us_eq"):
                    eq_weight += float(it.get("weight_pct", 0.0))
                    found = True
            if found:
                return eq_weight

    # 2. From v1 allocation list or dict
    alloc_v1 = state.get("allocation")
    if isinstance(alloc_v1, list):
        eq_weight = 0.0
        found = False
        for item in alloc_v1:
            if isinstance(item, dict) and str(item.get("asset", "")).lower() in ("indian stocks", "us stocks", "stocks", "in_eq", "us_eq"):
                eq_weight += float(item.get("weight_pct", 0.0))
                found = True
        if found:
            return eq_weight
    elif isinstance(alloc_v1, dict):
        eq_weight = 0.0
        found = False
        for k, v in alloc_v1.items():
            if str(k).lower() in ("indian stocks", "us stocks", "stocks", "indian_stocks", "us_stocks", "in_eq", "us_eq"):
                if isinstance(v, dict):
                    eq_weight += float(v.get("percentage", 0.0))
                    found = True
        if found:
            return eq_weight

    # 3. Direct equity weight if explicitly stored
    if "direct_equity_weight_pct" in state:
        return float(state["direct_equity_weight_pct"])

    return 0.0


def should_fetch(
    state: dict[str, Any] | None = None,
    force: bool = False,
    now: float | None = None,
    config: Any = None,
) -> tuple[bool, str, str]:
    """
    Decides whether a fetch should occur based on state, unchanged_streak, NAV windows, and market hours.
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
    market_state = get_market_state(now_ist, unchanged_streak=unchanged_streak)

    if force:
        return True, "forced by user request", market_state

    if last_fetch_ts <= 0:
        return True, "initial fetch / no previous cache", market_state

    # Check NAV-aware window vs intraday equity polling
    if config is None:
        try:
            from indmoney_sync.config import load_config
            cfg = load_config()
        except Exception:
            cfg = None
    else:
        cfg = config

    is_nav = is_nav_window(now_ist)

    # Determine if intraday high-frequency polling is active for market hours
    intraday_equity_active = False
    if cfg is not None and getattr(cfg, "polling", None) is not None:
        p_cfg = cfg.polling
        if getattr(p_cfg, "intraday_equity_polling", False):
            eq_weight = get_direct_equity_weight(state)
            thresh = getattr(p_cfg, "equity_weight_threshold_pct", 5.0)
            if eq_weight > thresh and nominal_state in ("IN_OPEN", "US_OPEN"):
                intraday_equity_active = True

    high_freq_active = is_nav or intraday_equity_active

    # Check nominal window transition from previous sync (e.g. CLOSED -> IN_OPEN)
    window_transition_bell = False
    prev_nominal = None
    if last_fetch_ts > 0:
        prev_ist = datetime.datetime.fromtimestamp(last_fetch_ts, tz=IST)
        prev_nominal = get_nominal_market_state(prev_ist)
        if prev_nominal != nominal_state:
            unchanged_streak = 0
            if nominal_state in ("IN_OPEN", "US_OPEN"):
                window_transition_bell = True

    market_state = get_market_state(now_ist, unchanged_streak=unchanged_streak)

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

    if high_freq_active:
        prefix = "NAV window active" if is_nav else f"market active ({market_state})"
        if age_sec >= 15 * 60:
            return True, f"{prefix} and cache is {int(age_sec/60)}m old", market_state
        return False, f"{prefix} but cache is fresh ({int(age_sec/60)}m old)", market_state
    else:
        # Off-window / off-hours / mutual-fund-only holding outside NAV windows: 60 minutes
        if age_sec >= 60 * 60:
            return True, f"off-window cadence and cache is {int(age_sec/60)}m old", market_state
        return False, f"off-window cadence and cache is fresh ({int(age_sec/60)}m old)", market_state


def should_execute_fetch(
    last_fetch_ts: float,
    force: bool = False,
    unchanged_streak: int = 0,
    now: float | None = None,
    config: Any = None,
) -> tuple[bool, str, str]:
    """Compatibility wrapper for should_fetch."""
    state = {"updated_at": last_fetch_ts, "unchanged_streak": unchanged_streak}
    return should_fetch(state=state, force=force, now=now, config=config)

