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
    base_inv = 3000000.00
    sparkline_90d = []
    for day_idx in range(90, 0, -1):
        dt = today_date - datetime.timedelta(days=day_idx)
        val = base_val + (90 - day_idx) * 15000.0 + ((day_idx * 13) % 25000)
        inv = base_inv + (90 - day_idx) * 6500.0
        ret_pct = round(((val - inv) / inv) * 100.0, 2)
        w_idx = round(val / inv, 4)
        sparkline_90d.append({
            "date": dt.strftime("%Y-%m-%d"),
            "v": round(val, 2),
            "return_pct": ret_pct,
            "wealth_index": w_idx,
        })
    sparkline_90d.append({
        "date": today_date.strftime("%Y-%m-%d"),
        "v": 4825190.50,
        "return_pct": 33.66,
        "wealth_index": round(4825190.50 / 3610000.00, 4),
    })

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
                "band_pct": 5.0,
                "drift_pct": 0.15,
                "rebalance_inr": -7404.75,
                "in_band": True,
                "palette_key": "blue",
            },
            {
                "bucket_id": "satellite",
                "label": "Growth / Alpha",
                "current_value_inr": 1455190.50,
                "actual_pct": 30.16,
                "target_pct": 30.0,
                "band_pct": 3.0,
                "drift_pct": 0.16,
                "rebalance_inr": -7633.35,
                "in_band": True,
                "palette_key": "purple",
            },
            {
                "bucket_id": "gold_silver",
                "label": "Precious Metals",
                "current_value_inr": 480000.00,
                "actual_pct": 9.95,
                "target_pct": 10.0,
                "band_pct": 2.5,
                "drift_pct": -0.05,
                "rebalance_inr": 2519.05,
                "in_band": True,
                "palette_key": "yellow",
            },
            {
                "bucket_id": "liquid",
                "label": "Cash & Arbitrage",
                "current_value_inr": 470000.00,
                "actual_pct": 9.74,
                "target_pct": 10.0,
                "band_pct": 2.5,
                "drift_pct": -0.26,
                "rebalance_inr": 12519.05,
                "in_band": True,
                "palette_key": "teal",
            },
        ],
        "attention_items": [],
        "holdings": [
            {
                "symbol": "PARAG_FLEXI",
                "name": "Parag Parikh Flexi Cap Fund Direct Growth",
                "isin": "INF879O01019",
                "class_id": "mf",
                "bucket_id": "core",
                "current_value_inr": 1420000.00,
                "invested_value_inr": 1050000.00,
                "one_day_change_inr": 5843.10,
                "one_day_change_pct": 0.41,
                "total_return_pct": 35.24,
                "palette_key": "blue",
            },
            {
                "symbol": "ICICI_LARGEMID",
                "name": "ICICI Prudential Nifty LargeMidcap 250 Index Fund Direct Growth",
                "isin": "INF109K012R6",
                "class_id": "mf",
                "bucket_id": "core",
                "current_value_inr": 1000000.00,
                "invested_value_inr": 800000.00,
                "one_day_change_inr": 3150.00,
                "one_day_change_pct": 0.32,
                "total_return_pct": 25.00,
                "palette_key": "blue",
            },
            {
                "symbol": "ICICI_VALUE30",
                "name": "ICICI Prudential Nifty200 Value 30 Index Fund Direct Growth",
                "isin": "INF109K01UT7",
                "class_id": "mf",
                "bucket_id": "satellite",
                "current_value_inr": 555190.50,
                "invested_value_inr": 400000.00,
                "one_day_change_inr": 2419.10,
                "one_day_change_pct": 0.44,
                "total_return_pct": 38.80,
                "palette_key": "purple",
            },
            {
                "symbol": "EDELWEISS_MOM50",
                "name": "Edelweiss Nifty500 Multicap Momentum Quality 50 Index Fund Direct Growth",
                "isin": "INF754K01AU4",
                "class_id": "mf",
                "bucket_id": "satellite",
                "current_value_inr": 500000.00,
                "invested_value_inr": 380000.00,
                "one_day_change_inr": 2850.00,
                "one_day_change_pct": 0.57,
                "total_return_pct": 31.58,
                "palette_key": "purple",
            },
            {
                "symbol": "MON100",
                "name": "Motilal Oswal NASDAQ 100 ETF",
                "isin": "INF247L01AU4",
                "class_id": "us_eq",
                "bucket_id": "satellite",
                "current_value_inr": 400000.00,
                "invested_value_inr": 250000.00,
                "one_day_change_inr": 2400.00,
                "one_day_change_pct": 0.60,
                "total_return_pct": 60.00,
                "palette_key": "purple",
            },
            {
                "symbol": "MOSL_GOLDFOF",
                "name": "Motilal Oswal Gold and Silver Passive Fund of Funds Direct Growth",
                "isin": "INF247L01GS2",
                "class_id": "gold",
                "bucket_id": "gold_silver",
                "current_value_inr": 480000.00,
                "invested_value_inr": 380000.00,
                "one_day_change_inr": 1100.00,
                "one_day_change_pct": 0.23,
                "total_return_pct": 26.32,
                "palette_key": "yellow",
            },
            {
                "symbol": "INVESCO_ARB",
                "name": "Invesco India Arbitrage Fund Direct Plan Growth Option",
                "isin": "INF209K01157",
                "class_id": "mf",
                "bucket_id": "liquid",
                "current_value_inr": 470000.00,
                "invested_value_inr": 350000.00,
                "one_day_change_inr": 658.05,
                "one_day_change_pct": 0.14,
                "total_return_pct": 34.29,
                "palette_key": "teal",
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
