"""Data normalization engine converting raw IndMoney MCP payloads to normalized state.json."""
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from .governor import get_market_state

ASSET_COLORS = {
    "Indian Stocks": "#38bdf8",  # Sky
    "Indian Equity": "#38bdf8",
    "IN_EQ": "#38bdf8",
    "Mutual Funds": "#818cf8",   # Indigo
    "Mutual Fund": "#818cf8",
    "MF": "#818cf8",
    "US Stocks": "#ec4899",      # Pink
    "US Equity": "#ec4899",
    "US_EQ": "#ec4899",
    "Fixed Income": "#34d399",   # Emerald
    "FD": "#34d399",
    "Gold": "#fbbf24",          # Amber
    "Other": "#94a3b8"          # Slate
}


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        if isinstance(val, str):
            val = val.replace(",", "").replace("₹", "").replace("$", "").replace("%", "").strip()
        return float(val)
    except (ValueError, TypeError):
        return default


def _parse_json_if_str(val: Any) -> Any:
    if isinstance(val, str):
        val_str = val.strip()
        if val_str.startswith("```"):
            lines = val_str.split("\n")
            if len(lines) >= 2 and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            val_str = "\n".join(lines).strip()
        try:
            return json.loads(val_str)
        except Exception:
            return val
    return val


def normalize_summary(raw_snapshot: Any) -> Dict[str, Any]:
    raw_snapshot = _parse_json_if_str(raw_snapshot)
    if isinstance(raw_snapshot, dict):
        if "data" in raw_snapshot and isinstance(raw_snapshot["data"], dict):
            raw_snapshot = raw_snapshot["data"]
        elif "snapshot" in raw_snapshot and isinstance(raw_snapshot["snapshot"], dict):
            raw_snapshot = raw_snapshot["snapshot"]
    else:
        raw_snapshot = {}

    # Extract or infer standard fields
    total_networth = _safe_float(
        raw_snapshot.get("total_networth")
        or raw_snapshot.get("net_worth")
        or raw_snapshot.get("total_value")
        or raw_snapshot.get("current_value")
    )
    invested = _safe_float(
        raw_snapshot.get("invested")
        or raw_snapshot.get("invested_amount")
        or raw_snapshot.get("total_investment")
        or raw_snapshot.get("invested_value")
    )
    day_change_inr = _safe_float(
        raw_snapshot.get("day_change_inr")
        or raw_snapshot.get("day_change")
        or raw_snapshot.get("one_day_return")
        or raw_snapshot.get("day_pnl")
    )
    day_change_pct = _safe_float(
        raw_snapshot.get("day_change_pct")
        or raw_snapshot.get("day_change_percentage")
        or raw_snapshot.get("one_day_return_pct")
    )

    total_pnl_inr = _safe_float(
        raw_snapshot.get("total_pnl_inr")
        or raw_snapshot.get("total_pnl")
        or raw_snapshot.get("overall_return")
        or raw_snapshot.get("gain_loss")
    )
    if total_pnl_inr == 0.0 and total_networth > 0 and invested > 0:
        total_pnl_inr = total_networth - invested

    total_pnl_pct = _safe_float(
        raw_snapshot.get("total_pnl_pct")
        or raw_snapshot.get("overall_return_pct")
        or raw_snapshot.get("returns_percentage")
    )
    if total_pnl_pct == 0.0 and invested > 0:
        total_pnl_pct = round((total_pnl_inr / invested) * 100.0, 2)

    return {
        "total_networth_inr": round(total_networth, 2),
        "invested_inr": round(invested, 2),
        "total_pnl_inr": round(total_pnl_inr, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "day_change_inr": round(day_change_inr, 2),
        "day_change_pct": round(day_change_pct, 2)
    }


def normalize_allocation(raw_alloc: Any, total_networth: float) -> List[Dict[str, Any]]:
    raw_alloc = _parse_json_if_str(raw_alloc)
    items: List[Dict[str, Any]] = []

    alloc_list = []
    if isinstance(raw_alloc, list):
        alloc_list = raw_alloc
    elif isinstance(raw_alloc, dict):
        if "data" in raw_alloc and isinstance(raw_alloc["data"], (list, dict)):
            raw_alloc = raw_alloc["data"]

        if isinstance(raw_alloc, list):
            alloc_list = raw_alloc
        elif "allocations" in raw_alloc and isinstance(raw_alloc["allocations"], list):
            alloc_list = raw_alloc["allocations"]
        else:
            for k, v in raw_alloc.items():
                if isinstance(v, dict):
                    alloc_list.append({"asset": k, **v})
                else:
                    alloc_list.append({"asset": k, "value": v})

    for item in alloc_list:
        if not isinstance(item, dict):
            continue
        name = item.get("asset") or item.get("name") or item.get("category") or "Other"
        val = _safe_float(item.get("value") or item.get("value_inr") or item.get("amount") or item.get("current_value"))
        weight = _safe_float(item.get("weight_pct") or item.get("percentage") or item.get("weight"))
        if weight == 0.0 and total_networth > 0:
            weight = round((val / total_networth) * 100.0, 1)
        day_pct = _safe_float(item.get("day_pct") or item.get("day_change_pct"))

        color = ASSET_COLORS.get(name, "#94a3b8")
        items.append({
            "asset": name,
            "value_inr": round(val, 2),
            "weight_pct": round(weight, 1),
            "day_pct": round(day_pct, 2),
            "color": color
        })

    # Sort descending by value
    items.sort(key=lambda x: x["value_inr"], reverse=True)
    return items


def normalize_holdings(raw_holdings: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    raw_holdings = _parse_json_if_str(raw_holdings)
    holding_list = []
    if isinstance(raw_holdings, list):
        holding_list = raw_holdings
    elif isinstance(raw_holdings, dict):
        holding_list = raw_holdings.get("holdings") or raw_holdings.get("data") or raw_holdings.get("items") or []

    normalized_all: List[Dict[str, Any]] = []

    for h in holding_list:
        if not isinstance(h, dict):
            continue
        symbol = str(h.get("symbol") or h.get("ticker") or h.get("isin") or h.get("id") or "")
        name = str(h.get("name") or h.get("scheme_name") or h.get("company_name") or symbol)
        asset_type = str(h.get("asset") or h.get("asset_class") or h.get("type") or "IN_EQ").upper()

        if "MF" in asset_type or "MUTUAL" in asset_type:
            asset = "MF"
        elif "US" in asset_type:
            asset = "US_EQ"
        else:
            asset = "IN_EQ"

        val = _safe_float(h.get("value_inr") or h.get("current_value") or h.get("value"))
        invested = _safe_float(h.get("invested_inr") or h.get("invested_value") or h.get("buy_value"))
        day_pct = _safe_float(h.get("day_pct") or h.get("day_change_pct") or h.get("one_day_return_pct"))
        total_pct = _safe_float(h.get("total_pct") or h.get("total_pnl_pct") or h.get("returns_pct"))

        if total_pct == 0.0 and invested > 0 and val > 0:
            total_pct = round(((val - invested) / invested) * 100.0, 2)

        normalized_all.append({
            "symbol": symbol,
            "name": name,
            "asset": asset,
            "value_inr": round(val, 2),
            "invested_inr": round(invested, 2),
            "day_pct": round(day_pct, 2),
            "total_pct": round(total_pct, 2)
        })

    # Sort holdings descending by value
    normalized_all.sort(key=lambda x: x["value_inr"], reverse=True)

    # Top movers: top 5 by absolute day_pct change
    movers = sorted(normalized_all, key=lambda x: abs(x["day_pct"]), reverse=True)[:5]

    return normalized_all, movers


def normalize_sips(raw_mf_sips: Any, raw_in_sips: Any, raw_us_sips: Any) -> Dict[str, Any]:
    all_sips: List[Dict[str, Any]] = []

    def _collect(sips: Any, sip_type: str) -> None:
        sips = _parse_json_if_str(sips)
        if isinstance(sips, list):
            items = sips
        elif isinstance(sips, dict):
            items = sips.get("sips") or sips.get("data") or sips.get("items") or []
        else:
            items = []

        for s in items:
            if not isinstance(s, dict):
                continue
            name = str(s.get("name") or s.get("scheme_name") or s.get("symbol") or "SIP")
            amt = _safe_float(s.get("amount") or s.get("amount_inr") or s.get("installment_amount"))
            next_date = str(s.get("next_date") or s.get("next_installment_date") or s.get("deduction_date") or "")
            all_sips.append({
                "name": name,
                "amount_inr": round(amt, 2),
                "next_date": next_date,
                "type": sip_type
            })

    _collect(raw_mf_sips, "MF")
    _collect(raw_in_sips, "IN_EQ")
    _collect(raw_us_sips, "US_EQ")

    monthly_total = sum(s["amount_inr"] for s in all_sips)
    # Sort upcoming chronologically
    all_sips.sort(key=lambda s: s["next_date"] or "9999-99-99")

    return {
        "monthly_total_inr": round(monthly_total, 2),
        "active_count": len(all_sips),
        "upcoming": all_sips[:10]
    }


def build_normalized_state(
    snapshot: Any,
    allocation: Any,
    holdings: Any,
    mf_sips: Any = None,
    in_sips: Any = None,
    us_sips: Any = None,
    status: str = "ok",
    auth_error: Optional[str] = None
) -> Dict[str, Any]:
    summary = normalize_summary(snapshot)
    alloc_items = normalize_allocation(allocation, summary["total_networth_inr"])
    all_holdings, top_movers = normalize_holdings(holdings)
    sips_data = normalize_sips(mf_sips, in_sips, us_sips)

    return {
        "status": status,
        "updated_at": int(time.time()),
        "market_state": get_market_state(),
        "auth_error": auth_error,
        "summary": summary,
        "allocation": alloc_items,
        "top_movers": top_movers,
        "holdings": all_holdings,
        "sips": sips_data
    }
