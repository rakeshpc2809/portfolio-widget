"""Unit tests for market-aware governor."""
import datetime
import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indmoney_sync.governor import IST, get_market_state, should_execute_fetch


class TestGovernor(unittest.TestCase):
    def test_indian_market_hours(self):
        # Wednesday at 11:30 AM IST -> IN_OPEN
        wed_1130 = datetime.datetime(2026, 10, 21, 11, 30, tzinfo=IST)
        self.assertEqual(get_market_state(wed_1130), "IN_OPEN")

    def test_us_market_hours(self):
        # Wednesday at 21:30 IST (9:30 PM) -> US_OPEN
        wed_2130 = datetime.datetime(2026, 10, 21, 21, 30, tzinfo=IST)
        self.assertEqual(get_market_state(wed_2130), "US_OPEN")

    def test_market_closed_hours(self):
        # Wednesday at 17:30 IST (5:30 PM) -> CLOSED (Between Indian close 16:00 and US open 19:00)
        wed_1730 = datetime.datetime(2026, 10, 21, 17, 30, tzinfo=IST)
        self.assertEqual(get_market_state(wed_1730), "CLOSED")

    def test_weekend_hours(self):
        # Sunday at 12:00 IST -> CLOSED
        sun_1200 = datetime.datetime(2026, 10, 25, 12, 0, tzinfo=IST)
        self.assertEqual(get_market_state(sun_1200), "CLOSED")

    def test_force_always_fetches(self):
        should_run, reason, _ = should_execute_fetch(last_fetch_ts=10000000000, force=True)
        self.assertTrue(should_run)
        self.assertIn("forced", reason)


if __name__ == "__main__":
    unittest.main()
