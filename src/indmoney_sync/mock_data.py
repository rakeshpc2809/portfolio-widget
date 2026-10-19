"""Mock data generator matching the normalized state.json schema."""
import time
from typing import Any, Dict


def get_mock_state() -> Dict[str, Any]:
    return {
        "status": "ok",
        "updated_at": int(time.time()),
        "market_state": "IN_OPEN",
        "auth_error": None,
        "summary": {
            "total_networth_inr": 4825190.50,
            "invested_inr": 3610000.00,
            "total_pnl_inr": 1215190.50,
            "total_pnl_pct": 33.66,
            "day_change_inr": 18420.25,
            "day_change_pct": 0.38
        },
        "allocation": [
            {
                "asset": "Indian Stocks",
                "value_inr": 2100000.00,
                "weight_pct": 43.5,
                "day_pct": 0.62,
                "color": "#38bdf8"  # Sky
            },
            {
                "asset": "Mutual Funds",
                "value_inr": 1850000.00,
                "weight_pct": 38.3,
                "day_pct": 0.21,
                "color": "#818cf8"  # Indigo
            },
            {
                "asset": "US Stocks",
                "value_inr": 875190.50,
                "weight_pct": 18.2,
                "day_pct": -0.15,
                "color": "#ec4899"  # Pink
            }
        ],
        "top_movers": [
            {
                "symbol": "TATAMOTORS",
                "name": "Tata Motors Ltd",
                "asset": "IN_EQ",
                "value_inr": 340000.00,
                "day_pct": 3.42,
                "total_pct": 64.10
            },
            {
                "symbol": "RELIANCE",
                "name": "Reliance Industries",
                "asset": "IN_EQ",
                "value_inr": 520000.00,
                "day_pct": 1.25,
                "total_pct": 28.40
            },
            {
                "symbol": "HDFCBANK",
                "name": "HDFC Bank Ltd",
                "asset": "IN_EQ",
                "value_inr": 410000.00,
                "day_pct": 0.85,
                "total_pct": 19.80
            },
            {
                "symbol": "AAPL",
                "name": "Apple Inc",
                "asset": "US_EQ",
                "value_inr": 310000.00,
                "day_pct": -0.65,
                "total_pct": 85.20
            },
            {
                "symbol": "NVDA",
                "name": "NVIDIA Corporation",
                "asset": "US_EQ",
                "value_inr": 290000.00,
                "day_pct": -1.85,
                "total_pct": 112.40
            }
        ],
        "holdings": [
            {
                "symbol": "PARAG_FLEXI",
                "name": "Parag Parikh Flexi Cap Fund",
                "asset": "MF",
                "value_inr": 920000.00,
                "invested_inr": 650000.00,
                "day_pct": 0.31,
                "total_pct": 41.54
            },
            {
                "symbol": "HDFC_MIDCAP",
                "name": "HDFC Mid-Cap Opportunities",
                "asset": "MF",
                "value_inr": 540000.00,
                "invested_inr": 390000.00,
                "day_pct": 0.45,
                "total_pct": 38.46
            },
            {
                "symbol": "RELIANCE",
                "name": "Reliance Industries Ltd",
                "asset": "IN_EQ",
                "value_inr": 520000.00,
                "invested_inr": 405000.00,
                "day_pct": 1.25,
                "total_pct": 28.40
            },
            {
                "symbol": "HDFCBANK",
                "name": "HDFC Bank Ltd",
                "asset": "IN_EQ",
                "value_inr": 410000.00,
                "invested_inr": 342000.00,
                "day_pct": 0.85,
                "total_pct": 19.88
            },
            {
                "symbol": "TATAMOTORS",
                "name": "Tata Motors Ltd",
                "asset": "IN_EQ",
                "value_inr": 340000.00,
                "invested_inr": 207200.00,
                "day_pct": 3.42,
                "total_pct": 64.09
            },
            {
                "symbol": "AAPL",
                "name": "Apple Inc",
                "asset": "US_EQ",
                "value_inr": 310000.00,
                "invested_inr": 167400.00,
                "day_pct": -0.65,
                "total_pct": 85.19
            },
            {
                "symbol": "NVDA",
                "name": "NVIDIA Corporation",
                "asset": "US_EQ",
                "value_inr": 290000.00,
                "invested_inr": 136500.00,
                "day_pct": -1.85,
                "total_pct": 112.45
            }
        ],
        "sips": {
            "monthly_total_inr": 65000.00,
            "active_count": 5,
            "upcoming": [
                {
                    "name": "Parag Parikh Flexi Cap Fund",
                    "amount_inr": 25000.00,
                    "next_date": "2026-10-25",
                    "type": "MF"
                },
                {
                    "name": "HDFC Mid-Cap Opportunities",
                    "amount_inr": 15000.00,
                    "next_date": "2026-10-28",
                    "type": "MF"
                },
                {
                    "name": "Mirae Asset Large Cap Fund",
                    "amount_inr": 10000.00,
                    "next_date": "2026-11-01",
                    "type": "MF"
                },
                {
                    "name": "Tata Motors Ltd (Weekly SIP)",
                    "amount_inr": 5000.00,
                    "next_date": "2026-10-23",
                    "type": "IN_EQ"
                },
                {
                    "name": "Vanguard S&P 500 ETF (VOO)",
                    "amount_inr": 10000.00,
                    "next_date": "2026-11-05",
                    "type": "US_EQ"
                }
            ]
        }
    }
