"""Mock data generator matching the normalized state.json schema v2."""
import datetime
from typing import Any

from .governor import IST


def get_mock_state(reference_time: datetime.datetime | None = None) -> dict[str, Any]:
    if reference_time is not None:
        now_ist = reference_time.astimezone(IST)
    else:
        now_ist = datetime.datetime.now(IST)

    now_ts = int(now_ist.timestamp())
    today_date = now_ist.date()

    # Generate 90 realistic daily historical sparkline points leading up to today
    base_val = 3450000.00
    sparkline_90d = []
    for day_idx in range(90, 0, -1):
        dt = today_date - datetime.timedelta(days=day_idx)
        val = base_val + (90 - day_idx) * 15000.0 + ((day_idx * 13) % 25000)
        sparkline_90d.append({"date": dt.strftime("%Y-%m-%d"), "v": round(val, 2)})
    sparkline_90d.append({"date": today_date.strftime("%Y-%m-%d"), "v": 4825190.50})

    return {
        "schema_version": 2,
        "provider": "indmoney",
        "status": "ok",
        "freshness": "fresh",
        "nav_as_of": "21 Oct 2026",
        "market_state": "IN_OPEN",
        "failed_sources": [],
        "updated_at": now_ts,
        "invested_portfolio": {
            "current_value_inr": 4825190.50,
            "invested_value_inr": 3610000.00,
            "total_return_inr": 1215190.50,
            "total_return_pct": 33.66,
            "one_day_change_inr": 18420.25,
            "one_day_change_pct": 0.38,
        },
        "total_networth": {
            "total_networth_inr": 5425190.50,
            "bank_balance_inr": 150000.00,
            "epf_inr": 450000.00,
        },
        "buckets": [
            {
                "bucket_id": "core",
                "label": "Core Wealth",
                "current_value_inr": 2420000.00,
                "actual_pct": 50.15,
                "target_pct": 50.0,
                "drift_pct": 0.15,
                "in_band": True,
                "palette_key": "blue",
            },
            {
                "bucket_id": "satellite",
                "label": "Growth / Alpha",
                "current_value_inr": 1455190.50,
                "actual_pct": 30.16,
                "target_pct": 30.0,
                "drift_pct": 0.16,
                "in_band": True,
                "palette_key": "purple",
            },
            {
                "bucket_id": "gold_silver",
                "label": "Precious Metals",
                "current_value_inr": 480000.00,
                "actual_pct": 9.95,
                "target_pct": 10.0,
                "drift_pct": -0.05,
                "in_band": True,
                "palette_key": "yellow",
            },
            {
                "bucket_id": "liquid",
                "label": "Cash & Arbitrage",
                "current_value_inr": 470000.00,
                "actual_pct": 9.74,
                "target_pct": 10.0,
                "drift_pct": -0.26,
                "in_band": True,
                "palette_key": "teal",
            },
        ],
        "attention_items": [],
        "holdings": [
            {
                "symbol": "PARAG_FLEXI",
                "name": "Parag Parikh Flexi Cap Fund",
                "isin": "INF879O01019",
                "class_id": "mf",
                "bucket_id": "core",
                "current_value_inr": 920000.00,
                "invested_value_inr": 650000.00,
                "one_day_change_inr": 2843.10,
                "one_day_change_pct": 0.31,
                "total_return_pct": 41.54,
                "palette_key": "indigo",
            },
            {
                "symbol": "HDFC_MIDCAP",
                "name": "HDFC Mid-Cap Opportunities Fund",
                "isin": "INF179K01BE2",
                "class_id": "mf",
                "bucket_id": "satellite",
                "current_value_inr": 540000.00,
                "invested_value_inr": 390000.00,
                "one_day_change_inr": 2419.10,
                "one_day_change_pct": 0.45,
                "total_return_pct": 38.46,
                "palette_key": "indigo",
            },
            {
                "symbol": "RELIANCE",
                "name": "Reliance Industries Ltd",
                "isin": "INE002A01018",
                "class_id": "in_eq",
                "bucket_id": "core",
                "current_value_inr": 520000.00,
                "invested_value_inr": 405000.00,
                "one_day_change_inr": 6420.00,
                "one_day_change_pct": 1.25,
                "total_return_pct": 28.40,
                "palette_key": "blue",
            },
            {
                "symbol": "HDFCBANK",
                "name": "HDFC Bank Ltd",
                "isin": "INE040A01034",
                "class_id": "in_eq",
                "bucket_id": "core",
                "current_value_inr": 410000.00,
                "invested_value_inr": 342000.00,
                "one_day_change_inr": 3455.60,
                "one_day_change_pct": 0.85,
                "total_return_pct": 19.88,
                "palette_key": "blue",
            },
            {
                "symbol": "TATAMOTORS",
                "name": "Tata Motors Ltd",
                "isin": "INE155A01022",
                "class_id": "in_eq",
                "bucket_id": "satellite",
                "current_value_inr": 340000.00,
                "invested_value_inr": 207200.00,
                "one_day_change_inr": 11244.25,
                "one_day_change_pct": 3.42,
                "total_return_pct": 64.09,
                "palette_key": "blue",
            },
            {
                "symbol": "AAPL",
                "name": "Apple Inc",
                "isin": "US0378331005",
                "class_id": "us_eq",
                "bucket_id": "satellite",
                "current_value_inr": 310000.00,
                "invested_value_inr": 167400.00,
                "one_day_change_inr": -2028.10,
                "one_day_change_pct": -0.65,
                "total_return_pct": 85.19,
                "palette_key": "pink",
            },
            {
                "symbol": "NVDA",
                "name": "NVIDIA Corporation",
                "isin": "US67066G1040",
                "class_id": "us_eq",
                "bucket_id": "satellite",
                "current_value_inr": 290000.00,
                "invested_value_inr": 136500.00,
                "one_day_change_inr": -5461.50,
                "one_day_change_pct": -1.85,
                "total_return_pct": 112.45,
                "palette_key": "pink",
            },
        ],
        "sips": {
            "monthly_total_inr": 65000.00,
            "monthly_total_usd": 120.00,
            "active_count": 5,
            "next_7d_sip_inr": 40000.00,
            "sip_coverage_ratio": 3.75,
            "sip_coverage_ok": True,
            "upcoming": [
                {
                    "name": "Parag Parikh Flexi Cap Fund",
                    "amount_inr": 25000.00,
                    "amount_usd": None,
                    "next_date": (today_date + datetime.timedelta(days=4)).strftime("%Y-%m-%d"),
                    "frequency": "monthly",
                    "class_id": "mf",
                },
                {
                    "name": "HDFC Mid-Cap Opportunities Fund",
                    "amount_inr": 15000.00,
                    "amount_usd": None,
                    "next_date": (today_date + datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
                    "frequency": "monthly",
                    "class_id": "mf",
                },
                {
                    "name": "Mirae Asset Large Cap Fund",
                    "amount_inr": 10000.00,
                    "amount_usd": None,
                    "next_date": (today_date + datetime.timedelta(days=11)).strftime("%Y-%m-%d"),
                    "frequency": "monthly",
                    "class_id": "mf",
                },
                {
                    "name": "Tata Motors Ltd (Weekly SIP)",
                    "amount_inr": 5000.00,
                    "amount_usd": None,
                    "next_date": (today_date + datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
                    "frequency": "weekly",
                    "class_id": "in_eq",
                },
                {
                    "name": "Vanguard S&P 500 ETF (VOO)",
                    "amount_inr": 10000.00,
                    "amount_usd": 120.00,
                    "next_date": (today_date + datetime.timedelta(days=15)).strftime("%Y-%m-%d"),
                    "frequency": "monthly",
                    "class_id": "us_eq",
                },
            ],
        },
        "sparkline_90d": sparkline_90d,
        "portfolio_os": {
            "enabled": False,
            "xirr_pct": 21.8,
            "rebalance_action": None,
        },
        "summary": {
            "total_portfolio_inr": 4825190.50,
            "total_networth_inr": 5425190.50,
            "bank_inr": 150000.00,
            "epf_inr": 450000.00,
            "non_investment_inr": 600000.00,
            "invested_inr": 3610000.00,
            "total_pnl_inr": 1215190.50,
            "total_pnl_pct": 33.66,
            "day_change_inr": 18420.25,
            "day_change_pct": 0.38,
        },
        "allocation": {
            "total_inr": 5425190.50,
            "items": [
                {
                    "id": "mutual_funds",
                    "label": "Mutual Funds",
                    "value_inr": 1460000.00,
                    "weight_pct": 26.91,
                    "palette_key": "indigo",
                },
                {
                    "id": "indian_stocks",
                    "label": "Indian Stocks",
                    "value_inr": 1270000.00,
                    "weight_pct": 23.41,
                    "palette_key": "blue",
                },
                {
                    "id": "us_stocks",
                    "label": "US Stocks",
                    "value_inr": 600000.00,
                    "weight_pct": 11.06,
                    "palette_key": "pink",
                },
            ],
        },
        "top_movers": [
            {
                "symbol": "TATAMOTORS",
                "name": "Tata Motors Ltd",
                "class_id": "in_eq",
                "value_inr": 340000.00,
                "day_pct": 3.42,
                "day_change_inr": 11244.25,
                "total_pct": 64.09,
                "palette_key": "blue",
            }
        ],
    }
