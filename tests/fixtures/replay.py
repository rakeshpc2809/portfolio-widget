"""Replay script demonstrating normalized v2 output on live_shaped_raw.json fixture."""
import datetime
import json
from pathlib import Path

from indmoney_sync.config import AppConfig, BucketTargets, OverrideRule
from indmoney_sync.governor import IST
from indmoney_sync.normalizer import build_normalized_state

fixture_path = Path(__file__).resolve().parent / "live_shaped_raw.json"
raw = json.loads(fixture_path.read_text(encoding="utf-8"))

ref_time = datetime.datetime(2026, 10, 28, 11, 30, tzinfo=IST)
cfg = AppConfig(
    bucket_targets=BucketTargets(core=50.0, satellite=30.0, gold_silver=10.0, liquid=10.0, drift_tolerance_pct=2.5),
    overrides={
        "MON100": OverrideRule(class_id="us_eq", bucket_id="satellite"),
        "INF247L01AU4": OverrideRule(class_id="us_eq", bucket_id="satellite"),
        "arbitrage": OverrideRule(class_id="mf", bucket_id="liquid"),
    },
)

state = build_normalized_state(
    snapshot=raw["asset_summary"],
    allocation=raw["allocation"],
    holdings=raw["holdings"],
    mf_sips=raw["mf_sips"],
    in_sips=raw["in_sips"],
    us_sips=raw["us_sips"],
    reference_time=ref_time,
    config=cfg,
)

print("=== REPLAY SUMMARY ===")
print("Schema Version:       ", state["schema_version"])
print("Status:               ", state["status"])
print("Invested Value (INR): ", f"₹{state['invested_portfolio']['current_value_inr']:,.2f}")
print(
    "Total Return (INR):   ",
    f"₹{state['invested_portfolio']['total_return_inr']:,.2f} ({state['invested_portfolio']['total_return_pct']}%)",
)
print(
    "1D Change (INR):      ",
    f"₹{state['invested_portfolio']['one_day_change_inr']:,.2f} ({state['invested_portfolio']['one_day_change_pct']}%)",
)
print("Total Net Worth (INR):", f"₹{state['total_networth']['total_networth_inr']:,.2f}")
print("Active SIP Count:     ", state["sips"]["active_count"])
print("Monthly Total (INR):  ", f"₹{state['sips']['monthly_total_inr']:,.2f}")
print("Monthly Total (USD):  ", f"${state['sips']['monthly_total_usd']:,.2f}")
print("Next 7D SIP (INR):    ", f"₹{state['sips']['next_7d_sip_inr']:,.2f}")
print("SIP Coverage Ratio:   ", state["sips"]["sip_coverage_ratio"], "OK:", state["sips"]["sip_coverage_ok"])

print("\n=== RESOLVED UPCOMING SIPS ===")
for s in state["sips"]["upcoming"]:
    print(
        f"  - {s['name']:<40} | ₹{s['amount_inr']:>8,.2f} | Next: {s['next_date']} | Freq: {s['frequency']}"
    )

print("\n=== BUCKET ALLOCATION & DRIFT ===")
for b in state["buckets"]:
    in_band_str = "IN BAND" if b["in_band"] else "DRIFT BREACH"
    print(
        f"  - {b['label']:<18} ({b['bucket_id']:<11}): ₹{b['current_value_inr']:>11,.2f} | "
        f"Actual: {b['actual_pct']:>5.2f}% | Target: {b['target_pct']:>5.2f}% | "
        f"Drift: {b['drift_pct']:>+5.2f}% | {in_band_str} | Color: {b['palette_key']}"
    )

print("\n=== ATTENTION ITEMS ===")
if not state["attention_items"]:
    print("  (Calm - zero active alerts)")
for a in state["attention_items"]:
    print(f"  - [{a['severity'].upper()}] {a['title']}: {a['message']}")
