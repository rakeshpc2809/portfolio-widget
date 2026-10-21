"""Unit tests for config loader and schema v2 validation."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import jsonschema

from indmoney_sync.config import (
    get_default_config,
    load_config,
)


class TestConfig(unittest.TestCase):
    def test_default_config_fallback(self):
        """Verifies default values when no config file exists."""
        cfg = get_default_config()
        self.assertEqual(cfg.bucket_targets.core, 50.0)
        self.assertEqual(cfg.bucket_targets.satellite, 30.0)
        self.assertEqual(cfg.bucket_targets.gold_silver, 10.0)
        self.assertEqual(cfg.bucket_targets.liquid, 10.0)
        self.assertEqual(cfg.bucket_targets.drift_tolerance_pct, 2.5)
        self.assertFalse(cfg.polling.intraday_equity_polling)
        self.assertEqual(cfg.polling.equity_weight_threshold_pct, 5.0)
        self.assertEqual(len(cfg.overrides), 0)

        # get_target helper
        self.assertEqual(cfg.bucket_targets.get_target("core"), 50.0)
        self.assertEqual(cfg.bucket_targets.get_target("Satellite"), 30.0)
        self.assertEqual(cfg.bucket_targets.get_target("gold_silver"), 10.0)
        self.assertEqual(cfg.bucket_targets.get_target("liquid"), 10.0)
        self.assertEqual(cfg.bucket_targets.get_target("legacy"), 0.0)
        self.assertEqual(cfg.bucket_targets.get_target("unknown"), 0.0)

    def test_custom_toml_parsing(self):
        """Verifies loading custom TOML with targets, polling, and overrides."""
        toml_content = b"""
[targets]
Core = 55.0
Satellite = 25.0
Gold_Silver = 10.0
Liquid = 10.0
drift_tolerance_pct = 3.0

[polling]
intraday_equity_polling = true
equity_weight_threshold_pct = 8.5

[overrides]
"INF247L01AU4" = { class_id = "us_eq", bucket_id = "satellite" }
"MON100" = { class_id = "us_eq", bucket_id = "satellite" }
"arbitrage" = { class_id = "mf", bucket_id = "liquid" }
"""
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
            tmp.write(toml_content)
            tmp_path = Path(tmp.name)

        try:
            cfg = load_config(tmp_path)
            self.assertEqual(cfg.bucket_targets.core, 55.0)
            self.assertEqual(cfg.bucket_targets.satellite, 25.0)
            self.assertEqual(cfg.bucket_targets.drift_tolerance_pct, 3.0)
            self.assertTrue(cfg.polling.intraday_equity_polling)
            self.assertEqual(cfg.polling.equity_weight_threshold_pct, 8.5)
            self.assertEqual(len(cfg.overrides), 3)

            # Override matching by ISIN
            rule_isin = cfg.find_override(isin="INF247L01AU4")
            self.assertIsNotNone(rule_isin)
            self.assertEqual(rule_isin.class_id, "us_eq")
            self.assertEqual(rule_isin.bucket_id, "satellite")

            # Override matching by Symbol
            rule_sym = cfg.find_override(symbol="mon100")
            self.assertIsNotNone(rule_sym)
            self.assertEqual(rule_sym.class_id, "us_eq")
            self.assertEqual(rule_sym.bucket_id, "satellite")

            # Override matching by Substring in fund name
            rule_sub = cfg.find_override(name="Kotak Equity Arbitrage Fund - Direct Growth")
            self.assertIsNotNone(rule_sub)
            self.assertEqual(rule_sub.class_id, "mf")
            self.assertEqual(rule_sub.bucket_id, "liquid")

            # No match returns None
            self.assertIsNone(cfg.find_override(isin="INF000000000", symbol="UNKNOWN", name="Random Fund"))
        finally:
            tmp_path.unlink()

    def test_nonexistent_config_falls_back_gracefully(self):
        cfg = load_config("/path/that/definitely/does/not/exist/config.toml")
        self.assertEqual(cfg.bucket_targets.core, 50.0)
        self.assertEqual(len(cfg.overrides), 0)


class TestSchemaV2Validation(unittest.TestCase):
    def setUp(self):
        schema_path = Path(__file__).resolve().parent.parent / "docs" / "schema-v2.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    def test_schema_validates_canonical_v2_payload(self):
        """Verifies that a well-formed v2 payload with zero hex colors passes schema validation."""
        sample_payload = {
            "schema_version": 2,
            "provider": "indmoney",
            "status": "ok",
            "freshness": "fresh",
            "nav_as_of": "21 Oct 2026",
            "market_state": "CLOSED",
            "failed_sources": [],
            "updated_at": 1792600000,
            "invested_portfolio": {
                "current_value_inr": 2500000.0,
                "invested_value_inr": 2000000.0,
                "total_return_inr": 500000.0,
                "total_return_pct": 25.0,
                "one_day_change_inr": -14906.05,
                "one_day_change_pct": -0.59
            },
            "total_networth": {
                "total_networth_inr": 2925000.0,
                "bank_balance_inr": 75000.0,
                "epf_inr": 350000.0
            },
            "buckets": [
                {
                    "bucket_id": "core",
                    "label": "Core",
                    "current_value_inr": 1250000.0,
                    "actual_pct": 50.0,
                    "target_pct": 50.0,
                    "drift_pct": 0.0,
                    "in_band": True,
                    "palette_key": "blue"
                },
                {
                    "bucket_id": "satellite",
                    "label": "Satellite",
                    "current_value_inr": 750000.0,
                    "actual_pct": 30.0,
                    "target_pct": 30.0,
                    "drift_pct": 0.0,
                    "in_band": True,
                    "palette_key": "purple"
                },
                {
                    "bucket_id": "gold_silver",
                    "label": "Gold & Silver",
                    "current_value_inr": 250000.0,
                    "actual_pct": 10.0,
                    "target_pct": 10.0,
                    "drift_pct": 0.0,
                    "in_band": True,
                    "palette_key": "yellow"
                },
                {
                    "bucket_id": "liquid",
                    "label": "Liquid / Cash",
                    "current_value_inr": 250000.0,
                    "actual_pct": 10.0,
                    "target_pct": 10.0,
                    "drift_pct": 0.0,
                    "in_band": True,
                    "palette_key": "teal"
                }
            ],
            "attention_items": [],
            "holdings": [
                {
                    "symbol": "MON100",
                    "name": "Motilal Oswal Nasdaq 100 ETF",
                    "isin": "INF247L01AU4",
                    "class_id": "us_eq",
                    "bucket_id": "satellite",
                    "current_value_inr": 150000.0,
                    "invested_value_inr": 120000.0,
                    "one_day_change_inr": -890.5,
                    "one_day_change_pct": -0.59,
                    "total_return_pct": 25.0,
                    "palette_key": "purple"
                }
            ],
            "sips": {
                "monthly_total_inr": 22500.0,
                "monthly_total_usd": 50.0,
                "active_count": 4,
                "next_7d_sip_inr": 17500.0,
                "sip_coverage_ratio": 4.28,
                "sip_coverage_ok": True,
                "upcoming": [
                    {
                        "name": "Parag Parikh Flexi Cap Fund",
                        "amount_inr": 10000.0,
                        "amount_usd": None,
                        "next_date": "2026-11-02",
                        "frequency": "monthly",
                        "class_id": "mf"
                    }
                ]
            },
            "sparkline_90d": [
                {
                    "date": "2026-10-21",
                    "v": 2500000.0
                }
            ],
            "portfolio_os": {
                "enabled": False,
                "xirr_pct": None,
                "rebalance_action": None
            }
        }

        # Should validate without raising jsonschema.ValidationError
        jsonschema.validate(instance=sample_payload, schema=self.schema)

    def test_schema_rejects_unverified_palette_keys(self):
        """Verifies that invalid palette keys (like 'amber' or hex codes) fail schema validation."""
        invalid_payload = {
            "schema_version": 2,
            "provider": "indmoney",
            "status": "ok",
            "freshness": "fresh",
            "updated_at": 1792600000,
            "invested_portfolio": {
                "current_value_inr": 1000.0,
                "invested_value_inr": 900.0,
                "total_return_inr": 100.0,
                "total_return_pct": 11.1,
                "one_day_change_inr": 10.0,
                "one_day_change_pct": 1.0
            },
            "total_networth": {
                "total_networth_inr": 1000.0,
                "bank_balance_inr": 0.0,
                "epf_inr": 0.0
            },
            "buckets": [
                {
                    "bucket_id": "core",
                    "label": "Core",
                    "current_value_inr": 1000.0,
                    "actual_pct": 100.0,
                    "target_pct": 50.0,
                    "drift_pct": 50.0,
                    "in_band": False,
                    "palette_key": "amber"  # Invalid! Must be one of 12 verified keys
                }
            ],
            "attention_items": [],
            "holdings": [],
            "sips": {
                "monthly_total_inr": 0.0,
                "monthly_total_usd": 0.0,
                "active_count": 0,
                "next_7d_sip_inr": 0.0,
                "sip_coverage_ratio": 999.0,
                "sip_coverage_ok": True,
                "upcoming": []
            },
            "sparkline_90d": []
        }

        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_payload, schema=self.schema)

    def test_live_shaped_fixture_contains_all_connector_quirks(self):
        """Verifies tests/fixtures/live_shaped_raw.json contains all required edge case shapes."""
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "live_shaped_raw.json"
        self.assertTrue(fixture_path.exists())
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # 1. Authoritative one_day_change on asset_summary
        self.assertIn("one_day_change", raw["asset_summary"])
        self.assertEqual(raw["asset_summary"]["one_day_change"], -14906.05)

        # 2. Allocation return_percentage (overall return, not 1D)
        alloc_items = raw["allocation"]["items"]
        self.assertTrue(any("return_percentage" in item for item in alloc_items))

        # 3. Nasdaq-100 ETF returning as STOCK and small cap
        nasdaq = next((h for h in raw["holdings"] if h.get("symbol") == "MON100"), None)
        self.assertIsNotNone(nasdaq)
        self.assertEqual(nasdaq["asset_type"], "STOCK")
        self.assertEqual(nasdaq["market_cap"], "small")

        # 4. Arbitrage fund returning as category/asset 'Others'
        arbitrage = next((h for h in raw["holdings"] if "Arbitrage" in h.get("name", "")), None)
        self.assertIsNotNone(arbitrage)
        self.assertEqual(arbitrage["asset_type"], "Others")

        # 5. Multi-folio mutual fund entries
        ppfas_folios = [h for h in raw["holdings"] if h.get("isin") == "INF879O01019"]
        self.assertEqual(len(ppfas_folios), 2)

        # 6. SIP shapes: bse_sip, flexi_sip, mixed dates, weekly frequency, USD wallet SIP
        mf_active = raw["mf_sips"]["active_sips"]
        bse = next(s for f in mf_active for s in f.get("active_sips", []) if s.get("sip_type") == "bse_sip")
        self.assertEqual(bse["sip_start_date"], "02-09-2026")

        flexi = next(s for f in mf_active for s in f.get("active_sips", []) if s.get("sip_type") == "flexi_sip")
        self.assertEqual(flexi["sip_start_date"], "03-09-2026")

        iso_date = next(s for f in mf_active for s in f.get("active_sips", []) if s.get("sip_start_date") == "2026-09-04")
        self.assertIsNotNone(iso_date)

        weekly = raw["in_sips"]["indian_stocks_sips"][0]
        self.assertEqual(weekly["sip_frequency"], "weekly")

        usd_sip = raw["us_sips"]["us_stocks_sips"][0]
        self.assertEqual(usd_sip["currency"], "USD")
        self.assertEqual(usd_sip["amount_usd"], 50.0)


if __name__ == "__main__":
    unittest.main()
