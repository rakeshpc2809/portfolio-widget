"""Unit tests for market-aware governor, dynamic holiday resolution, and stagnant-market auto-backoff."""
import datetime
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import indmoney_sync.governor as gov  # noqa: E402
from indmoney_sync.governor import (  # noqa: E402
    IST,
    get_in_holidays,
    get_market_state,
    get_nominal_market_state,
    get_nyse_holidays,
    is_market_open,
    is_nse_holiday,
    is_nyse_holiday,
    should_execute_fetch,
    should_fetch,
)


class TestGovernor(unittest.TestCase):
    def setUp(self):
        # Clear caches before each test
        gov._IN_HOLIDAYS_CACHE.clear()
        gov._NYSE_HOLIDAYS_CACHE.clear()

    def test_no_hardcoded_year_constants_in_governor(self):
        """Verify that no hardcoded year constants (e.g. 2026, NSE_HOLIDAYS_2026) remain in governor.py."""
        governor_path = SRC_DIR / "indmoney_sync" / "governor.py"
        content = governor_path.read_text(encoding="utf-8")

        # Must not contain hardcoded year sets (e.g. NSE_HOLIDAYS_2026) or year-suffixed sets
        self.assertNotIn("NSE_HOLIDAYS_2026", content)
        self.assertNotIn("NYSE_HOLIDAYS_2026", content)
        self.assertIsNone(re.search(r"HOLIDAYS_\d{4}", content))

        # Regex check for 4-digit years (e.g. 2025, 2026, 2027) in governor code
        matches = re.findall(r"\b202\d\b", content)
        self.assertEqual(
            matches,
            [],
            f"Found hardcoded year numbers in governor.py: {matches}"
        )

    def test_indian_market_hours_normal_day(self):
        # Tuesday at 11:30 AM IST (Normal trading day) -> IN_OPEN
        tue_1130 = datetime.datetime(2026, 10, 20, 11, 30, tzinfo=IST)
        self.assertEqual(get_nominal_market_state(tue_1130), "IN_OPEN")
        self.assertEqual(get_market_state(tue_1130), "IN_OPEN")
        self.assertTrue(is_market_open(tue_1130))

    def test_us_market_hours_normal_day(self):
        # Tuesday at 21:30 IST (9:30 PM) -> US_OPEN
        tue_2130 = datetime.datetime(2026, 10, 20, 21, 30, tzinfo=IST)
        self.assertEqual(get_nominal_market_state(tue_2130), "US_OPEN")
        self.assertEqual(get_market_state(tue_2130), "US_OPEN")
        self.assertTrue(is_market_open(tue_2130))

    def test_market_closed_off_hours(self):
        # Wednesday at 17:30 IST (5:30 PM) -> CLOSED (Between Indian close 16:00 and US open 19:00)
        wed_1730 = datetime.datetime(2026, 10, 21, 17, 30, tzinfo=IST)
        self.assertEqual(get_market_state(wed_1730), "CLOSED")
        self.assertFalse(is_market_open(wed_1730))

    def test_weekend_hours(self):
        # Sunday at 12:00 IST -> CLOSED
        sun_1200 = datetime.datetime(2026, 10, 25, 12, 0, tzinfo=IST)
        self.assertEqual(get_market_state(sun_1200), "CLOSED")
        self.assertFalse(is_market_open(sun_1200))

    def test_unchanged_streak_auto_backoff_in_market(self):
        """If unchanged_streak >= 2 during nominal IN_OPEN, throttle back to 60m and display CLOSED."""
        tue_1130 = datetime.datetime(2026, 10, 20, 11, 30, tzinfo=IST)
        now_ts = tue_1130.timestamp()

        # Streak 0: Normal active trading
        self.assertEqual(get_market_state(tue_1130, unchanged_streak=0), "IN_OPEN")
        # 20 min old: Should fetch under 15m cadence
        state_streak0 = {"updated_at": now_ts - 20 * 60, "unchanged_streak": 0}
        should_run, _, m_state = should_fetch(state=state_streak0, force=False, now=now_ts)
        self.assertTrue(should_run)
        self.assertEqual(m_state, "IN_OPEN")

        # Streak 1: Still active
        self.assertEqual(get_market_state(tue_1130, unchanged_streak=1), "IN_OPEN")

        # Streak 2: Auto-backoff activates -> market_state becomes CLOSED
        self.assertEqual(get_market_state(tue_1130, unchanged_streak=2), "CLOSED")
        self.assertFalse(is_market_open(tue_1130, unchanged_streak=2))

        # At age 20 min: Should NOT fetch (throttled to 60m)
        state_streak2_fresh = {"updated_at": now_ts - 20 * 60, "unchanged_streak": 2}
        should_run, reason, m_state = should_fetch(state=state_streak2_fresh, force=False, now=now_ts)
        self.assertFalse(should_run)
        self.assertEqual(m_state, "CLOSED")
        self.assertIn("stagnant market backoff", reason)

        # At age 65 min: Should fetch under 60m backoff cadence
        state_streak2_stale = {"updated_at": now_ts - 65 * 60, "unchanged_streak": 2}
        should_run, reason, m_state = should_fetch(state=state_streak2_stale, force=False, now=now_ts)
        self.assertTrue(should_run)
        self.assertEqual(m_state, "CLOSED")
        self.assertIn("stagnant market backoff", reason)

    def test_unchanged_streak_auto_backoff_us_market(self):
        """If unchanged_streak >= 2 during nominal US_OPEN, throttle back to 60m and display CLOSED."""
        tue_2130 = datetime.datetime(2026, 10, 20, 21, 30, tzinfo=IST)
        now_ts = tue_2130.timestamp()

        # Streak 0: Normal active trading
        self.assertEqual(get_market_state(tue_2130, unchanged_streak=0), "US_OPEN")

        # Streak >= 2: Auto-backoff activates
        self.assertEqual(get_market_state(tue_2130, unchanged_streak=2), "CLOSED")

        # At age 25 min: Should NOT fetch
        state_streak2 = {"updated_at": now_ts - 25 * 60, "unchanged_streak": 2}
        should_run, reason, m_state = should_fetch(state=state_streak2, force=False, now=now_ts)
        self.assertFalse(should_run)
        self.assertEqual(m_state, "CLOSED")

        # At age 65 min: Should fetch
        state_streak2_old = {"updated_at": now_ts - 65 * 60, "unchanged_streak": 2}
        should_run, _, m_state = should_fetch(state=state_streak2_old, force=False, now=now_ts)
        self.assertTrue(should_run)
        self.assertEqual(m_state, "CLOSED")

    def test_dynamic_holiday_lookup_without_holidays_pkg(self):
        """When holidays package is unavailable, returns empty set gracefully without error."""
        with patch.object(gov, "_HAS_HOLIDAYS", False), patch.object(gov, "holidays", None):
            in_hols = get_in_holidays(2028)
            nyse_hols = get_nyse_holidays(2028)
            self.assertEqual(in_hols, set())
            self.assertEqual(nyse_hols, set())

    def test_dynamic_holiday_lookup_with_holidays_mock(self):
        """When holidays package is available, dynamically queries and caches for any year."""
        mock_holidays_pkg = MagicMock()
        mock_in_holidays = {datetime.date(2028, 1, 26): "Republic Day"}
        mock_nyse_holidays = {datetime.date(2028, 11, 23): "Thanksgiving"}

        mock_holidays_pkg.country_holidays.return_value = mock_in_holidays
        mock_holidays_pkg.financial_holidays.return_value = mock_nyse_holidays

        with patch.object(gov, "_HAS_HOLIDAYS", True), patch.object(gov, "holidays", mock_holidays_pkg):
            in_hols = get_in_holidays(2028)
            self.assertIn(datetime.date(2028, 1, 26), in_hols)
            mock_holidays_pkg.country_holidays.assert_called_once_with("IN", years=2028)

            nyse_hols = get_nyse_holidays(2028)
            self.assertIn(datetime.date(2028, 11, 23), nyse_hols)
            mock_holidays_pkg.financial_holidays.assert_called_once_with("NYSE", years=2028)

            # Test short-circuit behavior with mocked holiday
            republic_day_2028 = datetime.datetime(2028, 1, 26, 11, 30, tzinfo=IST)
            self.assertTrue(is_nse_holiday(republic_day_2028.date()))
            self.assertEqual(get_nominal_market_state(republic_day_2028), "CLOSED")
            self.assertEqual(get_market_state(republic_day_2028), "CLOSED")

            thanksgiving_2028 = datetime.datetime(2028, 11, 23, 21, 30, tzinfo=IST)
            self.assertTrue(is_nyse_holiday(thanksgiving_2028.date()))
            self.assertEqual(get_nominal_market_state(thanksgiving_2028), "CLOSED")
            self.assertEqual(get_market_state(thanksgiving_2028), "CLOSED")

    def test_opening_bell_window_transition_resets_streak_and_fetches(self):
        """
        If unchanged_streak >= 2 from a previous market/off-hours session,
        transitioning into a new active window (e.g. CLOSED -> IN_OPEN at 09:15 IST)
        must reset the streak and immediately trigger an opening-bell fetch.
        """
        # Previous off-hours fetch at 08:45 IST (nominal CLOSED) with streak=5
        prev_fetch_dt = datetime.datetime(2026, 10, 20, 8, 45, tzinfo=IST)
        prev_fetch_ts = prev_fetch_dt.timestamp()

        # Morning bell at 09:15 IST (nominal IN_OPEN) - only 30m after last fetch
        open_dt = datetime.datetime(2026, 10, 20, 9, 15, tzinfo=IST)
        open_ts = open_dt.timestamp()

        state = {"updated_at": prev_fetch_ts, "unchanged_streak": 5}
        should_run, reason, m_state = should_fetch(state=state, force=False, now=open_ts)

        self.assertTrue(should_run, "Opening bell must trigger an immediate fetch")
        self.assertEqual(m_state, "IN_OPEN")
        self.assertIn("opening bell", reason.lower())

    def test_force_always_fetches(self):
        should_run, reason, _ = should_execute_fetch(last_fetch_ts=10000000000, force=True)
        self.assertTrue(should_run)
        self.assertIn("forced", reason)


if __name__ == "__main__":
    unittest.main()
