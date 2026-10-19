"""Unit tests for IndMoney normalizer engine."""
import unittest
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indmoney_sync.normalizer import (
    normalize_summary,
    normalize_allocation,
    normalize_holdings,
    normalize_sips,
    build_normalized_state
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

    def test_normalize_allocation(self):
        raw = [
            {"asset": "Indian Stocks", "value": 2100000, "day_pct": 0.62},
            {"asset": "Mutual Funds", "value": 1850000, "day_pct": 0.21},
            {"asset": "US Stocks", "value": 875190, "day_pct": -0.15}
        ]
        items = normalize_allocation(raw, total_networth=4825190)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["asset"], "Indian Stocks")
        self.assertAlmostEqual(items[0]["weight_pct"], 43.5, delta=0.5)
        self.assertIn("#38bdf8", items[0]["color"])

    def test_normalize_holdings_and_top_movers(self):
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

    def test_normalize_sips(self):
        mf_sips = [{"name": "Parag Parikh Flexi Cap", "amount": 25000, "next_date": "2026-10-25"}]
        in_sips = [{"name": "Tata Motors SIP", "amount": 5000, "next_date": "2026-10-23"}]
        us_sips = [{"name": "VOO SIP", "amount": 10000, "next_date": "2026-11-05"}]

        sips = normalize_sips(mf_sips, in_sips, us_sips)
        self.assertEqual(sips["monthly_total_inr"], 40000.0)
        self.assertEqual(sips["active_count"], 3)
        # Check upcoming sorted chronologically
        self.assertEqual(sips["upcoming"][0]["name"], "Tata Motors SIP")


if __name__ == "__main__":
    unittest.main()
