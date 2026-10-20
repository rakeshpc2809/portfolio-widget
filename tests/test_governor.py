"""Unit tests for market-aware governor and holiday short-circuiting."""
import datetime
import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indmoney_sync.governor import (
    IST,
    get_market_state,
    is_market_open,
    is_nse_holiday,
    is_nyse_holiday,
    should_execute_fetch,
)


class TestGovernor(unittest.TestCase):
    def test_indian_market_hours_normal_day(self):
        # Tuesday, Oct 20, 2026 at 11:30 AM IST (Normal trading day) -> IN_OPEN
        tue_1130 = datetime.datetime(2026, 10, 20, 11, 30, tzinfo=IST)
        self.assertEqual(get_market_state(tue_1130), "IN_OPEN")
        self.assertTrue(is_market_open(tue_1130))

    def test_indian_market_holiday_short_circuit(self):
        # Wednesday, Oct 21, 2026 is Dussehra (NSE Holiday)
        # Even at 11:30 AM IST, market must be CLOSED
        dussehra_1130 = datetime.datetime(2026, 10, 21, 11, 30, tzinfo=IST)
        self.assertTrue(is_nse_holiday(dussehra_1130.date()))
        self.assertEqual(get_market_state(dussehra_1130), "CLOSED")
        self.assertFalse(is_market_open(dussehra_1130))

        # Monday, Jan 26, 2026 is Republic Day
        republic_day = datetime.datetime(2026, 1, 26, 10, 0, tzinfo=IST)
        self.assertTrue(is_nse_holiday(republic_day.date()))
        self.assertEqual(get_market_state(republic_day), "CLOSED")

    def test_us_market_hours_normal_day(self):
        # Tuesday, Oct 20, 2026 at 21:30 IST (9:30 PM) -> US_OPEN
        tue_2130 = datetime.datetime(2026, 10, 20, 21, 30, tzinfo=IST)
        self.assertEqual(get_market_state(tue_2130), "US_OPEN")
        self.assertTrue(is_market_open(tue_2130))

    def test_us_market_holiday_short_circuit(self):
        # Thursday, Nov 26, 2026 is Thanksgiving Day (NYSE Holiday)
        thanksgiving_ist = datetime.datetime(2026, 11, 26, 21, 30, tzinfo=IST)
        self.assertTrue(is_nyse_holiday(thanksgiving_ist.date()))
        self.assertEqual(get_market_state(thanksgiving_ist), "CLOSED")

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

    def test_force_always_fetches(self):
        should_run, reason, _ = should_execute_fetch(last_fetch_ts=10000000000, force=True)
        self.assertTrue(should_run)
        self.assertIn("forced", reason)


if __name__ == "__main__":
    unittest.main()
