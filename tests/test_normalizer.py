"""Unit tests for IndMoney normalizer engine, sparkline ring buffer, and SIP liquidity."""
import datetime
import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indmoney_sync.normalizer import (
    build_normalized_state,
    normalize_allocation,
    normalize_holdings,
    normalize_sips,
    normalize_summary,
    update_sparkline,
)


class TestNormalizer(unittest.TestCase):
    def test_normalize_summary_standard(self):
        raw = {
            "total_networth": 4825190.50,
            "invested_amount": 3610000.00,
            "day_change": 18420.25,
            "day_change_percentage": 0.38,
            "total_pnl": 1215190.50,
            "overall_return_pct": 33.66
        }
        res = normalize_summary(raw)
        self.assertEqual(res["total_networth_inr"], 4825190.50)
        self.assertEqual(res["invested_inr"], 3610000.00)
        self.assertEqual(res["day_change_inr"], 18420.25)
        self.assertEqual(res["day_change_pct"], 0.38)
        self.assertEqual(res["total_pnl_inr"], 1215190.50)
        self.assertEqual(res["total_pnl_pct"], 33.66)

    def test_normalize_summary_strings_with_commas(self):
        raw = {
            "net_worth": "₹48,25,190.50",
            "invested": "36,10,000",
            "one_day_return": "18,420.25",
            "one_day_return_pct": "0.38%"
        }
        res = normalize_summary(raw)
        self.assertEqual(res["total_networth_inr"], 4825190.50)
        self.assertEqual(res["invested_inr"], 3610000.00)
        self.assertEqual(res["day_change_inr"], 18420.25)
        self.assertEqual(res["day_change_pct"], 0.38)
        self.assertEqual(res["total_pnl_inr"], 1215190.50)

    def test_normalize_with_markdown_fences_and_string_json(self):
        fenced_str = "```json\n{\"total_networth\": 5000000, \"invested\": 4000000, \"day_change\": 25000, \"day_change_pct\": 0.5}\n```"
        res = normalize_summary(fenced_str)
        self.assertEqual(res["total_networth_inr"], 5000000.0)
        self.assertEqual(res["invested_inr"], 4000000.0)
        self.assertEqual(res["total_pnl_inr"], 1000000.0)

    def test_normalize_allocation(self):
        raw = [
            {"asset": "Indian Stocks", "value": 2100000, "day_pct": 0.62},
            {"asset": "Mutual Funds", "value": 1850000, "day_pct": 0.21},
            {"asset": "US Stocks", "value": 875190, "day_pct": -0.15}
        ]
        items = normalize_allocation(raw, effective_total=4825190)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["asset"], "Indian Stocks")
        self.assertAlmostEqual(items[0]["weight_pct"], 43.5, delta=0.5)

    def test_normalize_holdings_and_top_movers_with_rupee_attribution(self):
        raw = [
            {"symbol": "TATAMOTORS", "name": "Tata Motors", "asset": "IN_EQ", "value": 340000, "day_pct": 3.42, "total_pct": 64.1},
            {"symbol": "NVDA", "name": "NVIDIA", "asset": "US_EQ", "value": 290000, "day_pct": -1.85, "total_pct": 112.4},
            {"symbol": "RELIANCE", "name": "Reliance", "asset": "IN_EQ", "value": 520000, "day_pct": 0.50, "total_pct": 28.0}
        ]
        holdings, movers = normalize_holdings(raw)
        # Holdings sorted by value
        self.assertEqual(holdings[0]["symbol"], "RELIANCE")
        # Top movers sorted by abs(day_pct)
        self.assertEqual(movers[0]["symbol"], "TATAMOTORS")
        self.assertEqual(movers[1]["symbol"], "NVDA")

        # Verify 1D Rupee Attribution
        # Tata Motors day_change_inr: 340000 * (3.42 / 103.42) = 11244.25
        self.assertAlmostEqual(movers[0]["day_change_inr"], 11244.25, delta=1.0)
        # NVDA day_change_inr: 290000 * (-1.85 / 98.15) = -5466.12
        self.assertAlmostEqual(movers[1]["day_change_inr"], -5466.12, delta=5.0)

    def test_normalize_sips_with_liquidity_coverage(self):
        ref_date = datetime.date(2026, 10, 20)
        # Upcoming within 7 days (2026-10-20 to 2026-10-27):
        # 1. Oct 23: 5,000
        # 2. Oct 25: 25,000
        # -> Total next 7d = 30,000
        # Oct 30 is outside 7 days
        mf_sips = [
            {"name": "Parag Parikh Flexi Cap", "amount": 25000, "next_date": "2026-10-25"},
            {"name": "Monthly MF", "amount": 15000, "next_date": "2026-10-30"}
        ]
        in_sips = [{"name": "Tata Motors SIP", "amount": 5000, "next_date": "2026-10-23"}]
        us_sips = [{"name": "VOO SIP", "amount": 10000, "next_date": "2026-11-05"}]

        # Test case A: Bank balance >= 1.2 * 30,000 (>= 36,000) -> coverage OK
        sips_ok = normalize_sips(mf_sips, in_sips, us_sips, bank_balance_inr=50000.0, reference_date=ref_date)
        self.assertEqual(sips_ok["monthly_total_inr"], 55000.0)
        self.assertEqual(sips_ok["next_7d_sip_inr"], 30000.0)
        self.assertTrue(sips_ok["sip_coverage_ok"])

        # Test case B: Bank balance < 36,000 (e.g. 20,000) -> Low Bank Buffer
        sips_low = normalize_sips(mf_sips, in_sips, us_sips, bank_balance_inr=20000.0, reference_date=ref_date)
        self.assertEqual(sips_low["next_7d_sip_inr"], 30000.0)
        self.assertFalse(sips_low["sip_coverage_ok"])

    def test_update_sparkline_ring_buffer(self):
        base_ts = 1700000000
        sparkline = []

        # 1. Initial point
        sparkline = update_sparkline(sparkline, current_val=50000.0, current_ts=base_ts)
        self.assertEqual(len(sparkline), 1)
        self.assertEqual(sparkline[0]["v"], 50000.0)

        # 2. No value change and <15m (60s) -> should NOT append duplicate
        sparkline = update_sparkline(sparkline, current_val=50000.0, current_ts=base_ts + 60)
        self.assertEqual(len(sparkline), 1)

        # 3. Value change >= 1.0 -> should append
        sparkline = update_sparkline(sparkline, current_val=50250.0, current_ts=base_ts + 120)
        self.assertEqual(len(sparkline), 2)
        self.assertEqual(sparkline[-1]["v"], 50250.0)

        # 4. Same value but >=15m (900s) -> should append heartbeat
        sparkline = update_sparkline(sparkline, current_val=50250.0, current_ts=base_ts + 1050)
        self.assertEqual(len(sparkline), 3)

        # 5. Ring buffer capping at 30 points
        long_buffer = [{"ts": base_ts + (i * 900), "v": 50000.0 + i} for i in range(35)]
        capped = update_sparkline(long_buffer, current_val=60000.0, current_ts=base_ts + 40000, max_points=30)
        self.assertEqual(len(capped), 30)
        self.assertEqual(capped[-1]["v"], 60000.0)

    def test_build_normalized_state_integrates_sparkline(self):
        raw = {"total_networth": 1000000, "invested": 800000, "day_change": 5000, "day_change_pct": 0.5}
        state = build_normalized_state(snapshot=raw, allocation=[], holdings=[], prev_sparkline=[{"ts": 100, "v": 995000}])
        self.assertIn("sparkline", state)
        self.assertEqual(len(state["sparkline"]), 2)
        self.assertEqual(state["sparkline"][-1]["v"], 1000000.0)


    def test_build_normalized_state_unchanged_streak(self):
        from unittest.mock import patch
        raw = {"total_networth": 1000000.0, "invested": 800000.0, "day_change": 5000.0, "day_change_pct": 0.5}
        prev_state = {
            "unchanged_streak": 1,
            "summary": {"total_networth_inr": 1000000.0, "day_change_inr": 5000.0}
        }

        with patch("indmoney_sync.normalizer.get_nominal_market_state", return_value="IN_OPEN"):
            # Same values during IN_OPEN -> increment streak from 1 to 2
            state = build_normalized_state(snapshot=raw, allocation=[], holdings=[], prev_state=prev_state)
            self.assertEqual(state["unchanged_streak"], 2)
            self.assertEqual(state["market_state"], "CLOSED")  # Auto-throttled because streak >= 2

            # Value changed -> streak resets to 0
            raw_changed = {"total_networth": 1001000.0, "invested": 800000.0, "day_change": 6000.0, "day_change_pct": 0.6}
            state_changed = build_normalized_state(snapshot=raw_changed, allocation=[], holdings=[], prev_state=state)
            self.assertEqual(state_changed["unchanged_streak"], 0)
            self.assertEqual(state_changed["market_state"], "IN_OPEN")


    def test_build_normalized_state_window_transition_resets_streak(self):
        from unittest.mock import patch
        raw = {"total_networth": 1000000.0, "invested": 800000.0, "day_change": 5000.0, "day_change_pct": 0.5}

        # Previous state was recorded at 08:45 IST (nominal CLOSED) with streak=5
        prev_dt = datetime.datetime(2026, 10, 20, 8, 45, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        prev_state = {
            "updated_at": prev_dt.timestamp(),
            "unchanged_streak": 5,
            "summary": {"total_networth_inr": 1000000.0, "day_change_inr": 5000.0}
        }

        # Now at 09:15 IST (nominal IN_OPEN)
        with patch("indmoney_sync.normalizer.get_nominal_market_state") as mock_nom:
            # First call for prev_updated_at returns CLOSED, second call for now returns IN_OPEN
            def side_effect(dt=None):
                if dt is not None and dt.hour == 8:
                    return "CLOSED"
                return "IN_OPEN"
            mock_nom.side_effect = side_effect

            state = build_normalized_state(snapshot=raw, allocation=[], holdings=[], prev_state=prev_state)
            # Even with same values, streak reset from 5 -> 0, then incremented to 1 (first tick of new window)
            self.assertEqual(state["unchanged_streak"], 1)
            # Since streak is 1 (< 2), market_state is active IN_OPEN, NOT throttled
            self.assertEqual(state["market_state"], "IN_OPEN")


if __name__ == "__main__":
    unittest.main()


