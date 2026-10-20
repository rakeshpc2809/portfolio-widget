"""Data normalization engine converting raw IndMoney MCP payloads to normalized state.json."""
import json
import time
from typing import Any

from .governor import get_market_state

ASSET_COLORS = {
    "Equity": "#38bdf8",         # Sky
    "Indian Stocks": "#38bdf8",
    "Indian Equity": "#38bdf8",
    "IN_EQ": "#38bdf8",
    "STOCK": "#38bdf8",
    "Mutual Funds": "#818cf8",   # Indigo
    "Mutual Fund": "#818cf8",
    "MF": "#818cf8",
    "US Stocks": "#ec4899",      # Pink
    "US Equity": "#ec4899",
    "US_EQ": "#ec4899",
    "Gold": "#fbbf24",          # Amber
    "Retirement": "#a855f7",    # Purple
    "EPF": "#a855f7",
    "Liquid": "#34d399",        # Emerald
    "Fixed Income": "#34d399",
    "FD": "#34d399",
    "SA": "#2dd4bf",            # Teal
    "Others": "#94a3b8",        # Slate
    "Other": "#94a3b8"
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
            parsed = json.loads(val_str)
            if isinstance(parsed, dict) and "result" in parsed and isinstance(parsed["result"], str):
                try:
                    return json.loads(parsed["result"])
                except Exception:
                    return parsed["result"]
            return parsed
        except Exception:
            return val
    elif isinstance(val, dict) and "result" in val and isinstance(val["result"], str):
        try:
            return json.loads(val["result"])
        except Exception:
            pass
    return val


NON_INVESTMENT_CATEGORIES = {"RETIREMENT", "EPF", "PPF", "NPS", "LIQUID", "SA", "BANK", "SAVINGS", "CASH"}


def normalize_summary(raw_snapshot: Any, raw_holdings: Any = None) -> dict[str, Any]:
    raw_snapshot = _parse_json_if_str(raw_snapshot)
    if isinstance(raw_snapshot, dict):
        if "data" in raw_snapshot and isinstance(raw_snapshot["data"], dict):
            raw_snapshot = raw_snapshot["data"]
        elif "snapshot" in raw_snapshot and isinstance(raw_snapshot["snapshot"], dict):
            raw_snapshot = raw_snapshot["snapshot"]
    else:
        raw_snapshot = {}

    total_networth = _safe_float(
        raw_snapshot.get("total_networth")
        or raw_snapshot.get("total_current_value")
        or raw_snapshot.get("net_worth")
        or raw_snapshot.get("total_value")
        or raw_snapshot.get("current_value")
    )
    total_invested = _safe_float(
        raw_snapshot.get("total_invested")
        or raw_snapshot.get("invested")
        or raw_snapshot.get("invested_amount")
        or raw_snapshot.get("total_investment")
        or raw_snapshot.get("invested_value")
    )

    # Detect EPF / Bank Account (Savings) / Retirement / Liquid to separate from market investments
    investments_list = raw_snapshot.get("investments") or []
    assets_list = raw_snapshot.get("assets") or []

    bank_inr = 0.0
    epf_inr = 0.0
    inv_curr = 0.0
    inv_invested = 0.0

    if investments_list and isinstance(investments_list, list):
        for inv in investments_list:
            if not isinstance(inv, dict):
                continue
            atype = str(inv.get("asset_type") or "").upper()
            c_val = _safe_float(inv.get("current_value") or inv.get("value"))
            i_val = _safe_float(inv.get("invested_value") or inv.get("invested"))
            if atype in ("EPF", "PPF", "NPS", "RETIREMENT"):
                epf_inr += c_val
            elif atype in ("SA", "BANK", "SAVINGS", "LIQUID"):
                bank_inr += c_val
            else:
                inv_curr += c_val
                inv_invested += i_val
    elif assets_list and isinstance(assets_list, list):
        for a in assets_list:
            if not isinstance(a, dict):
                continue
            cat = str(a.get("assetclass_l2") or a.get("asset") or "").upper()
            c_val = _safe_float(a.get("current_value") or a.get("value"))
            i_val = _safe_float(a.get("invested_value") or a.get("invested"))
            if "RETIREMENT" in cat or "EPF" in cat:
                epf_inr += c_val
            elif "LIQUID" in cat or "BANK" in cat or "SAVINGS" in cat:
                bank_inr += c_val
            else:
                inv_curr += c_val
                inv_invested += i_val

    # If separate investments were found, calculate pure investment portfolio totals
    if inv_curr > 0:
        total_portfolio = inv_curr
        portfolio_invested = inv_invested
    else:
        # Fallback if no detailed breakdown available
        total_portfolio = total_networth - (bank_inr + epf_inr)
        portfolio_invested = total_invested - (bank_inr + epf_inr) if total_invested > (bank_inr + epf_inr) else total_invested

    # 1D change
    day_change_inr = _safe_float(
        raw_snapshot.get("day_change_inr")
        or raw_snapshot.get("day_change")
        or raw_snapshot.get("one_day_return")
        or raw_snapshot.get("day_pnl")
    )

    # If day_change not in snapshot, sum from holdings
    if day_change_inr == 0.0 and raw_holdings:
        holding_items = []
        raw_holdings = _parse_json_if_str(raw_holdings)
        if isinstance(raw_holdings, list):
            holding_items = raw_holdings
        elif isinstance(raw_holdings, dict):
            holding_items = raw_holdings.get("holdings") or raw_holdings.get("data") or []
        day_change_inr = sum(_safe_float(h.get("one_day_change") or h.get("day_change")) for h in holding_items if isinstance(h, dict))

    base_for_pct = total_portfolio if total_portfolio > 0 else total_networth
    day_change_pct = _safe_float(
        raw_snapshot.get("day_change_pct")
        or raw_snapshot.get("day_change_percentage")
        or raw_snapshot.get("one_day_return_pct")
    )
    if day_change_pct == 0.0 and base_for_pct > 0 and day_change_inr != 0.0:
        day_change_pct = round((day_change_inr / base_for_pct) * 100.0, 2)

    total_pnl_inr = _safe_float(
        raw_snapshot.get("total_pnl_inr")
        or raw_snapshot.get("total_pnl")
        or raw_snapshot.get("overall_return")
        or raw_snapshot.get("gain_loss")
    )
    if total_pnl_inr == 0.0 and total_portfolio > 0 and portfolio_invested > 0:
        total_pnl_inr = total_portfolio - portfolio_invested

    total_pnl_pct = _safe_float(
        raw_snapshot.get("total_pnl_pct")
        or raw_snapshot.get("overall_return_pct")
        or raw_snapshot.get("returns_percentage")
    )
    if total_pnl_pct == 0.0 and portfolio_invested > 0:
        total_pnl_pct = round((total_pnl_inr / portfolio_invested) * 100.0, 2)

    return {
        "total_networth_inr": round(total_networth, 2),
        "total_portfolio_inr": round(total_portfolio, 2),
        "invested_inr": round(portfolio_invested, 2),
        "total_pnl_inr": round(total_pnl_inr, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "day_change_inr": round(day_change_inr, 2),
        "day_change_pct": round(day_change_pct, 2),
        "bank_inr": round(bank_inr, 2),
        "epf_inr": round(epf_inr, 2),
        "non_investment_inr": round(bank_inr + epf_inr, 2)
    }


def normalize_allocation(raw_alloc: Any, total_portfolio: float = 0.0, total_networth: float = 0.0) -> list[dict[str, Any]]:
    raw_alloc = _parse_json_if_str(raw_alloc)
    items: list[dict[str, Any]] = []
    effective_total = total_portfolio if total_portfolio > 0 else total_networth

    alloc_list = []
    if isinstance(raw_alloc, list):
        alloc_list = raw_alloc
    elif isinstance(raw_alloc, dict):
        if "assets" in raw_alloc and isinstance(raw_alloc["assets"], list):
            alloc_list = raw_alloc["assets"]
        elif "investments" in raw_alloc and isinstance(raw_alloc["investments"], list):
            alloc_list = raw_alloc["investments"]
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
        name = (
            item.get("assetclass_l2")
            or item.get("asset")
            or item.get("asset_type")
            or item.get("name")
            or item.get("category")
            or "Other"
        )
        # Exclude Bank, Savings, EPF and Retirement from investment allocation
        if name.upper() in NON_INVESTMENT_CATEGORIES:
            continue

        val = _safe_float(
            item.get("current_value")
            or item.get("value")
            or item.get("value_inr")
            or item.get("amount")
        )
        if val <= 0:
            continue

        day_pct = _safe_float(
            item.get("return_percentage")
            or item.get("day_pct")
            or item.get("day_change_pct")
        )

        color = ASSET_COLORS.get(name, "#94a3b8")
        items.append({
            "asset": name,
            "value_inr": round(val, 2),
            "weight_pct": 0.0,
            "day_pct": round(day_pct, 2),
            "color": color
        })

    # Sort descending by value
    items.sort(key=lambda x: x["value_inr"], reverse=True)

    # Recalculate weights based on the investment portfolio
    inv_total = sum(x["value_inr"] for x in items) or effective_total
    if inv_total > 0:
        for x in items:
            x["weight_pct"] = round((x["value_inr"] / inv_total) * 100.0, 1)

    return items


def normalize_holdings(raw_holdings: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_holdings = _parse_json_if_str(raw_holdings)
    holding_list = []
    if isinstance(raw_holdings, list):
        holding_list = raw_holdings
    elif isinstance(raw_holdings, dict):
        holding_list = raw_holdings.get("holdings") or raw_holdings.get("data") or raw_holdings.get("items") or []

    normalized_all: list[dict[str, Any]] = []

    for h in holding_list:
        if not isinstance(h, dict):
            continue
        symbol = str(h.get("investment_code") or h.get("symbol") or h.get("ticker") or h.get("isin") or h.get("id") or "")
        name = str(h.get("investment") or h.get("name") or h.get("scheme_name") or h.get("company_name") or symbol)
        asset_type = str(h.get("asset_type") or h.get("asset") or h.get("asset_class") or h.get("type") or "MF").upper()

        if "MF" in asset_type or "MUTUAL" in asset_type:
            asset = "MF"
        elif "US" in asset_type:
            asset = "US_EQ"
        elif "STOCK" in asset_type or "EQ" in asset_type:
            asset = "IN_EQ"
        elif "EPF" in asset_type:
            asset = "EPF"
        else:
            asset = asset_type

        val = _safe_float(h.get("market_value") or h.get("value_inr") or h.get("current_value") or h.get("value"))
        invested = _safe_float(h.get("invested_amount") or h.get("invested_inr") or h.get("invested_value") or h.get("buy_value"))
        day_pct = _safe_float(h.get("one_day_change_percentage") or h.get("day_pct") or h.get("day_change_pct") or h.get("one_day_return_pct"))
        total_pct = _safe_float(h.get("pnl_per") or h.get("total_pct") or h.get("total_pnl_pct") or h.get("returns_pct") or h.get("return_percentage"))

        if total_pct == 0.0 and invested > 0 and val > 0:
            total_pct = round(((val - invested) / invested) * 100.0, 2)

        if val > 0 or invested > 0:
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


def normalize_sips(raw_mf_sips: Any, raw_in_sips: Any, raw_us_sips: Any) -> dict[str, Any]:
    all_sips: list[dict[str, Any]] = []

    def _collect(sips: Any, sip_type: str) -> None:
        sips = _parse_json_if_str(sips)
        items = []
        if isinstance(sips, list):
            items = sips
        elif isinstance(sips, dict):
            items = sips.get("mf_sips") or sips.get("indian_stocks_sips") or sips.get("us_stocks_sips") or sips.get("sips") or sips.get("data") or []

        for s in items:
            if not isinstance(s, dict):
                continue

            # Check if this item is a fund object containing active_sips list
            if "active_sips" in s and isinstance(s["active_sips"], list):
                fund_name = str(s.get("name") or "MF SIP")
                for sub_sip in s["active_sips"]:
                    if isinstance(sub_sip, dict):
                        amt = _safe_float(sub_sip.get("amount") or sub_sip.get("amount_inr"))
                        next_date = str(sub_sip.get("sip_start_date") or sub_sip.get("next_date") or "")
                        all_sips.append({
                            "name": fund_name,
                            "amount_inr": round(amt, 2),
                            "next_date": next_date,
                            "type": sip_type
                        })
            else:
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
    auth_error: str | None = None
) -> dict[str, Any]:
    snapshot_parsed = _parse_json_if_str(snapshot)
    summary = normalize_summary(snapshot_parsed, holdings)

    # If allocation not explicitly passed, take from snapshot assets
    if not allocation and isinstance(snapshot_parsed, dict):
        allocation = snapshot_parsed.get("assets") or snapshot_parsed.get("investments")

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
