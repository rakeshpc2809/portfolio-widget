"""Data normalization engine converting raw IndMoney MCP payloads to normalized state.json."""
import datetime
import json
import time
from typing import Any

from .governor import IST, get_market_state, get_nominal_market_state

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


def update_sparkline(
    prev_sparkline: list[dict[str, Any]] | None,
    current_val: float,
    current_ts: int | None = None,
    max_points: int = 30
) -> list[dict[str, Any]]:
    """
    Appends {ts, v} to the ring buffer when value changes or >15m (900s) has elapsed.
    Caps the buffer at max_points (30).
    """
    if current_ts is None:
        current_ts = int(time.time())

    sparkline = [dict(pt) for pt in prev_sparkline] if isinstance(prev_sparkline, list) else []

    if not sparkline:
        sparkline.append({"ts": current_ts, "v": round(current_val, 2)})
    else:
        last_pt = sparkline[-1]
        last_ts = int(last_pt.get("ts", 0))
        last_v = float(last_pt.get("v", 0.0))

        # Append when value changes by >= 1 rupee or >= 15m has elapsed
        if abs(current_val - last_v) >= 1.0 or (current_ts - last_ts) >= 900:
            sparkline.append({"ts": current_ts, "v": round(current_val, 2)})

    return sparkline[-max_points:]


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
            holding_items = raw_holdings.get("holdings") or raw_holdings.get("data") or raw_holdings.get("items") or []

        for h in holding_items:
            if isinstance(h, dict):
                val = _safe_float(h.get("market_value") or h.get("value_inr") or h.get("current_value") or h.get("value"))
                day_pct = _safe_float(h.get("one_day_change_percentage") or h.get("day_pct") or h.get("day_change_pct") or h.get("one_day_return_pct"))
                if day_pct != 0.0 and val > 0:
                    day_change_inr += val * (day_pct / (100.0 + day_pct))

    day_change_pct = _safe_float(
        raw_snapshot.get("day_change_pct")
        or raw_snapshot.get("day_change_percentage")
        or raw_snapshot.get("one_day_return_pct")
    )

    if day_change_pct == 0.0 and total_portfolio > 0:
        prev_portfolio = total_portfolio - day_change_inr
        if prev_portfolio > 0:
            day_change_pct = (day_change_inr / prev_portfolio) * 100.0

    total_pnl = total_portfolio - portfolio_invested if (total_portfolio > 0 and portfolio_invested > 0) else 0.0
    total_pnl_pct = (total_pnl / portfolio_invested * 100.0) if portfolio_invested > 0 else 0.0

    return {
        "total_portfolio_inr": round(total_portfolio, 2),
        "total_networth_inr": round(total_networth if total_networth > 0 else total_portfolio, 2),
        "bank_inr": round(bank_inr, 2),
        "epf_inr": round(epf_inr, 2),
        "non_investment_inr": round(bank_inr + epf_inr, 2),
        "invested_inr": round(portfolio_invested, 2),
        "total_pnl_inr": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "day_change_inr": round(day_change_inr, 2),
        "day_change_pct": round(day_change_pct, 2)
    }


def normalize_allocation(raw_allocation: Any, effective_total: float) -> list[dict[str, Any]]:
    raw_allocation = _parse_json_if_str(raw_allocation)
    alloc_list = []
    if isinstance(raw_allocation, list):
        alloc_list = raw_allocation
    elif isinstance(raw_allocation, dict):
        alloc_list = raw_allocation.get("allocation") or raw_allocation.get("assets") or raw_allocation.get("items") or []

    items = []
    for item in alloc_list:
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("asset")
            or item.get("assetclass_l2")
            or item.get("asset_class")
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

        # 1D Rupee Attribution
        day_change_inr = _safe_float(
            h.get("day_change_inr")
            or h.get("day_change")
            or h.get("one_day_return")
            or h.get("day_pnl")
        )
        if day_change_inr == 0.0 and day_pct != 0.0 and val > 0:
            if (100.0 + day_pct) > 0:
                day_change_inr = round(val * (day_pct / (100.0 + day_pct)), 2)

        if val > 0 or invested > 0:
            normalized_all.append({
                "symbol": symbol,
                "name": name,
                "asset": asset,
                "value_inr": round(val, 2),
                "invested_inr": round(invested, 2),
                "day_pct": round(day_pct, 2),
                "day_change_inr": round(day_change_inr, 2),
                "total_pct": round(total_pct, 2)
            })

    # Sort holdings descending by value
    normalized_all.sort(key=lambda x: x["value_inr"], reverse=True)

    # Top movers: top 5 by absolute day_pct change
    movers = sorted(normalized_all, key=lambda x: abs(x["day_pct"]), reverse=True)[:5]

    return normalized_all, movers


def normalize_sips(
    raw_mf_sips: Any,
    raw_in_sips: Any,
    raw_us_sips: Any,
    bank_balance_inr: float = 0.0,
    reference_date: datetime.date | None = None
) -> dict[str, Any]:
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

    # 7-Day Liquidity Coverage Calculation
    today = reference_date or datetime.date.today()
    next_7d_sip_inr = 0.0

    for s in all_sips:
        date_str = str(s.get("next_date", "")).strip()
        if date_str:
            try:
                # Handle YYYY-MM-DD or DD-MM-YYYY
                clean_date = date_str.split("T")[0]
                if "-" in clean_date:
                    parts = clean_date.split("-")
                    if len(parts) == 3:
                        if len(parts[0]) == 4:
                            sip_date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                        else:
                            sip_date = datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
                        diff_days = (sip_date - today).days
                        if 0 <= diff_days <= 7:
                            next_7d_sip_inr += s["amount_inr"]
            except Exception:
                pass

    # Coverage OK if bank balance >= 1.2 * next_7d_sip_inr (or no upcoming SIPs in 7 days)
    sip_coverage_ok = (bank_balance_inr >= next_7d_sip_inr * 1.2) if next_7d_sip_inr > 0 else True

    return {
        "monthly_total_inr": round(monthly_total, 2),
        "active_count": len(all_sips),
        "next_7d_sip_inr": round(next_7d_sip_inr, 2),
        "sip_coverage_ok": bool(sip_coverage_ok),
        "upcoming": all_sips[:10]
    }


def build_normalized_state(
    snapshot: Any,
    allocation: Any,
    holdings: Any,
    mf_sips: Any = None,
    in_sips: Any = None,
    us_sips: Any = None,
    prev_sparkline: list[dict[str, Any]] | None = None,
    prev_state: dict[str, Any] | None = None,
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
    sips_data = normalize_sips(
        raw_mf_sips=mf_sips,
        raw_in_sips=in_sips,
        raw_us_sips=us_sips,
        bank_balance_inr=summary["bank_inr"]
    )

    updated_at = int(time.time())
    if prev_sparkline is None and isinstance(prev_state, dict):
        prev_sparkline = prev_state.get("sparkline")

    sparkline = update_sparkline(
        prev_sparkline=prev_sparkline,
        current_val=summary["total_networth_inr"],
        current_ts=updated_at,
        max_points=30
    )

    # Track unchanged_streak
    unchanged_streak = 0
    if isinstance(prev_state, dict):
        prev_streak = int(prev_state.get("unchanged_streak", 0))
        prev_summary = prev_state.get("summary", {})
        prev_networth = _safe_float(prev_summary.get("total_networth_inr"))
        prev_day_change = _safe_float(prev_summary.get("day_change_inr"))
        prev_updated_at = _safe_float(prev_state.get("updated_at", 0))

        curr_networth = summary["total_networth_inr"]
        curr_day_change = summary["day_change_inr"]

        nominal_state = get_nominal_market_state()
        prev_nominal = (
            get_nominal_market_state(datetime.datetime.fromtimestamp(prev_updated_at, tz=IST))
            if prev_updated_at > 0
            else nominal_state
        )

        # Reset streak if nominal market window transitioned (e.g. CLOSED -> IN_OPEN)
        if prev_nominal != nominal_state:
            prev_streak = 0

        if nominal_state in ("IN_OPEN", "US_OPEN"):
            # If values are identical during active hours, increment streak
            if abs(curr_networth - prev_networth) < 0.01 and abs(curr_day_change - prev_day_change) < 0.01:
                unchanged_streak = prev_streak + 1
            else:
                unchanged_streak = 0
        else:
            # During off-hours, reset if values change, otherwise maintain
            if abs(curr_networth - prev_networth) >= 0.01 or abs(curr_day_change - prev_day_change) >= 0.01:
                unchanged_streak = 0
            else:
                unchanged_streak = prev_streak

    market_state = get_market_state(unchanged_streak=unchanged_streak)

    return {
        "status": status,
        "updated_at": updated_at,
        "market_state": market_state,
        "unchanged_streak": unchanged_streak,
        "auth_error": auth_error,
        "summary": summary,
        "allocation": alloc_items,
        "top_movers": top_movers,
        "holdings": all_holdings,
        "sips": sips_data,
        "sparkline": sparkline
    }
