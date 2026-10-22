"""Data normalization engine converting raw IndMoney MCP payloads to normalized state v2 contract."""

import calendar
import datetime
import json
import re
import time
from typing import Any

from .config import VALID_PALETTE_KEYS, AppConfig, get_default_config
from .governor import IST, get_nominal_market_state

# Verified IrisStyle.identity keys strictly:
# blue, sky, teal, green, yellow, orange, red, pink, indigo, purple, lavender, gray
BUCKET_PALETTE = {
    "core": "blue",
    "satellite": "purple",
    "gold_silver": "yellow",
    "liquid": "teal",
    "legacy": "gray",
    "unassigned": "orange",
}

CLASS_PALETTE = {
    "mf": "indigo",
    "in_eq": "blue",
    "us_eq": "pink",
    "cash": "teal",
    "epf": "purple",
    "gold": "yellow",
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


def parse_date(date_str: str) -> datetime.date | None:
    """Parses date string supporting DD-MM-YYYY, YYYY-MM-DD, or ISO timestamps."""
    if not date_str:
        return None
    cleaned = str(date_str).strip().split("T")[0]
    for sep in ("-", "/"):
        if sep in cleaned:
            parts = cleaned.split(sep)
            if len(parts) == 3:
                try:
                    if len(parts[0]) == 4:
                        return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                    else:
                        return datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
                except ValueError:
                    return None
    return None


def project_next_sip_date(
    start_date_str: str,
    frequency: str = "monthly",
    reference_date: datetime.date | None = None,
) -> datetime.date | None:
    """
    Parses sip_start_date and projects the next deduction date strictly >= reference_date
    using calendar.monthrange for safe month-end clamping.
    """
    ref = reference_date or datetime.date.today()
    parsed = parse_date(start_date_str)
    if not parsed:
        return None

    freq = str(frequency or "monthly").lower().strip()

    if parsed >= ref:
        return parsed

    cur = parsed
    if "week" in freq:
        diff_days = (ref - cur).days
        weeks_needed = (diff_days + 6) // 7
        return cur + datetime.timedelta(days=weeks_needed * 7)

    target_day = parsed.day

    def _next_month(y: int, m: int, day: int) -> datetime.date:
        m += 1
        if m > 12:
            m = 1
            y += 1
        max_d = calendar.monthrange(y, m)[1]
        return datetime.date(y, m, min(day, max_d))

    def _next_quarter(y: int, m: int, day: int) -> datetime.date:
        for _ in range(3):
            m += 1
            if m > 12:
                m = 1
                y += 1
        max_d = calendar.monthrange(y, m)[1]
        return datetime.date(y, m, min(day, max_d))

    if "quarter" in freq:
        while cur < ref:
            cur = _next_quarter(cur.year, cur.month, target_day)
        return cur

    # Monthly default
    while cur < ref:
        cur = _next_month(cur.year, cur.month, target_day)
    return cur


def update_sparkline_90d(
    prev_sparkline: list[dict[str, Any]] | None,
    current_val: float,
    current_date_str: str,
    max_days: int = 90,
    return_pct: float | None = None,
    invested_val: float | None = None,
) -> list[dict[str, Any]]:
    """
    Maintains a 90-point daily historical series: [{'date': 'YYYY-MM-DD', 'v': float, ...}].
    Updates today's date in-place if already present, otherwise appends.
    """
    sparkline: list[dict[str, Any]] = []
    if isinstance(prev_sparkline, list):
        for pt in prev_sparkline:
            if isinstance(pt, dict) and "date" in pt and "v" in pt:
                item: dict[str, Any] = {"date": str(pt["date"]), "v": round(_safe_float(pt["v"]), 2)}
                if "return_pct" in pt:
                    item["return_pct"] = round(_safe_float(pt["return_pct"]), 2)
                if "wealth_index" in pt:
                    item["wealth_index"] = round(_safe_float(pt["wealth_index"]), 4)
                sparkline.append(item)
            elif isinstance(pt, dict) and "ts" in pt and "v" in pt:
                d_str = datetime.datetime.fromtimestamp(pt["ts"], tz=IST).strftime("%Y-%m-%d")
                sparkline.append({"date": d_str, "v": round(_safe_float(pt["v"]), 2)})

    val_rounded = round(current_val, 2)
    wealth_index = round(current_val / invested_val, 4) if (invested_val and invested_val > 0) else None
    ret_pct = round(return_pct, 2) if return_pct is not None else None

    new_pt: dict[str, Any] = {"date": current_date_str, "v": val_rounded}
    if ret_pct is not None:
        new_pt["return_pct"] = ret_pct
    if wealth_index is not None:
        new_pt["wealth_index"] = wealth_index

    if not sparkline:
        sparkline.append(new_pt)
    else:
        last_pt = sparkline[-1]
        if last_pt["date"] == current_date_str:
            last_pt["v"] = val_rounded
            if ret_pct is not None:
                last_pt["return_pct"] = ret_pct
            if wealth_index is not None:
                last_pt["wealth_index"] = wealth_index
        else:
            sparkline.append(new_pt)

    return sparkline[-max_days:]


def update_sparkline(
    prev_sparkline: list[dict[str, Any]] | None,
    current_val: float,
    current_ts: int | None = None,
    max_points: int = 30,
) -> list[dict[str, Any]]:
    """Legacy helper maintained for backward compatibility."""
    if current_ts is None:
        current_ts = int(time.time())

    sparkline = [dict(pt) for pt in prev_sparkline] if isinstance(prev_sparkline, list) else []

    if not sparkline:
        sparkline.append({"ts": current_ts, "v": round(current_val, 2)})
    else:
        last_pt = sparkline[-1]
        last_ts = int(last_pt.get("ts", 0))
        last_v = float(last_pt.get("v", 0.0))

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
        elif "asset_summary" in raw_snapshot and isinstance(raw_snapshot["asset_summary"], dict):
            raw_snapshot = raw_snapshot["asset_summary"]
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
        or raw_snapshot.get("total_invested_value")
    )

    bank_inr = _safe_float(raw_snapshot.get("bank_balance") or raw_snapshot.get("bank_inr"))
    epf_inr = _safe_float(raw_snapshot.get("epf_balance") or raw_snapshot.get("epf_inr"))

    investments_list = raw_snapshot.get("investments") or []
    assets_list = raw_snapshot.get("assets") or []

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

    if inv_curr > 0:
        total_portfolio = inv_curr
        portfolio_invested = inv_invested
    else:
        total_portfolio = total_networth - (bank_inr + epf_inr)
        portfolio_invested = total_invested - (bank_inr + epf_inr) if total_invested > (bank_inr + epf_inr) else total_invested

    # [C2]: Authoritative 1D Change
    day_change_inr = _safe_float(
        raw_snapshot.get("one_day_change")
        or raw_snapshot.get("day_change_inr")
        or raw_snapshot.get("day_change")
        or raw_snapshot.get("one_day_return")
        or raw_snapshot.get("day_pnl")
    )

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
                h_1d = _safe_float(h.get("one_day_change") or h.get("day_change_inr") or h.get("day_change"))
                if h_1d != 0.0:
                    day_change_inr += h_1d
                else:
                    day_pct = _safe_float(h.get("one_day_change_percentage") or h.get("day_pct") or h.get("day_change_pct"))
                    if day_pct != 0.0 and val > 0:
                        day_change_inr += val * (day_pct / (100.0 + day_pct))

    day_change_pct = _safe_float(
        raw_snapshot.get("one_day_change_percentage")
        or raw_snapshot.get("day_change_pct")
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
        "total_networth_inr": round(total_networth if total_networth > 0 else (total_portfolio + bank_inr + epf_inr), 2),
        "bank_inr": round(bank_inr, 2),
        "epf_inr": round(epf_inr, 2),
        "non_investment_inr": round(bank_inr + epf_inr, 2),
        "invested_inr": round(portfolio_invested, 2),
        "total_pnl_inr": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "day_change_inr": round(day_change_inr, 2),
        "day_change_pct": round(day_change_pct, 2),
    }


def normalize_allocation(raw_allocation: Any, effective_total: float) -> list[dict[str, Any]]:
    raw_allocation = _parse_json_if_str(raw_allocation)
    alloc_list = []
    if isinstance(raw_allocation, list):
        alloc_list = raw_allocation
    elif isinstance(raw_allocation, dict):
        alloc_list = raw_allocation.get("items") or raw_allocation.get("allocation") or raw_allocation.get("assets") or []

    items = []
    for item in alloc_list:
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("asset")
            or item.get("asset_type")
            or item.get("assetclass_l2")
            or item.get("name")
            or "Other"
        )
        if name.upper() in {"RETIREMENT", "EPF", "PPF", "NPS", "SA", "BANK", "SAVINGS"}:
            continue

        val = _safe_float(
            item.get("value")
            or item.get("current_value")
            or item.get("value_inr")
            or item.get("amount")
        )
        if val <= 0:
            continue

        # [C3]: Never map return_percentage into day_pct
        total_ret_pct = _safe_float(item.get("return_percentage") or item.get("total_pnl_pct") or item.get("total_pct"))
        day_pct = _safe_float(item.get("day_pct") or item.get("day_change_pct") or item.get("one_day_change_percentage"))

        items.append({
            "asset": name,
            "value_inr": round(val, 2),
            "weight_pct": 0.0,
            "day_pct": round(day_pct, 2),
            "total_return_pct": round(total_ret_pct, 2),
        })

    items.sort(key=lambda x: x["value_inr"], reverse=True)
    inv_total = sum(x["value_inr"] for x in items) or effective_total
    if inv_total > 0:
        for x in items:
            x["weight_pct"] = round((x["value_inr"] / inv_total) * 100.0, 1)

    return items


def classify_holding(
    symbol: str,
    name: str,
    isin: str,
    raw_asset_type: str,
    config: AppConfig | None = None,
) -> tuple[str, str]:
    cfg = config or get_default_config()

    override = cfg.find_override(isin=isin, symbol=symbol, name=name)
    ov_class = override.class_id if override else None
    ov_bucket = override.bucket_id if override else None

    raw_type_up = raw_asset_type.upper()
    name_low = name.lower()

    if ov_class:
        class_id = ov_class.lower()
    elif "US" in raw_type_up or "NASDAQ" in raw_type_up or "VOO" in symbol or any(k in name_low for k in ("nasdaq", "s&p 500", "sp500", "us tech", "fang")):
        class_id = "us_eq"
    elif "GOLD" in raw_type_up or "SILVER" in raw_type_up or "SGB" in raw_type_up or "gold" in name_low or "silver" in name_low:
        class_id = "gold"
    elif "MF" in raw_type_up or "MUTUAL" in raw_type_up or "fund" in name_low:
        class_id = "mf"
    elif "STOCK" in raw_type_up or "EQ" in raw_type_up or "SHARE" in raw_type_up:
        class_id = "in_eq"
    elif "EPF" in raw_type_up or "PPF" in raw_type_up:
        class_id = "epf"
    elif "LIQUID" in raw_type_up or "CASH" in raw_type_up:
        class_id = "cash"
    else:
        class_id = "mf"

    if ov_bucket:
        bucket_id = ov_bucket.lower()
        if bucket_id not in cfg.valid_bucket_ids():
            bucket_id = "unassigned"
    elif cfg.strict_map:
        bucket_id = "unassigned"
    elif "legacy" in name_low:
        bucket_id = "legacy"
    elif any(k in name_low for k in ("liquid", "arbitrage", "overnight", "money market", "ultra short", "cash")):
        bucket_id = "liquid"
    elif class_id == "gold" or any(k in name_low for k in ("gold", "silver", "sgb")):
        bucket_id = "gold_silver"
    elif any(k in name_low for k in ("large & mid", "large and mid", "large mid", "largemid", "large-mid")):
        bucket_id = "core"
    # Check Satellite / Factor / Sectoral BEFORE generic "index" so factor index funds don't leak into Core
    elif (
        class_id in ("in_eq", "us_eq")
        or any(
            k in name_low
            for k in (
                "nasdaq", "small", "micro", "momentum", "value", "quality",
                "alpha", "tech", "healthcare", "pharma", "us stock", "mid cap", "midcap",
            )
        )
    ):
        bucket_id = "satellite"
    elif any(k in name_low for k in ("flexi", "large", "nifty 50", "sensex", "index", "bluechip", "focused", "multi asset")):
        bucket_id = "core"
    else:
        bucket_id = "core"

    return class_id, bucket_id


def normalize_holdings(
    raw_holdings: Any,
    config: AppConfig | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_holdings = _parse_json_if_str(raw_holdings)
    holding_list = []
    if isinstance(raw_holdings, list):
        holding_list = raw_holdings
    elif isinstance(raw_holdings, dict):
        holding_list = raw_holdings.get("holdings") or raw_holdings.get("data") or raw_holdings.get("items") or []

    # Consolidate multiple folios by isin (or symbol if isin is empty)
    merged_map: dict[str, dict[str, Any]] = {}

    for h in holding_list:
        if not isinstance(h, dict):
            continue
        symbol = str(h.get("symbol") or h.get("investment_code") or h.get("ticker") or h.get("isin") or "")
        name = str(h.get("name") or h.get("investment") or h.get("scheme_name") or h.get("company_name") or symbol)
        # Strip trailing (Folio ...) from display name
        clean_name = re.sub(r"\s*\(Folio\s*[^)]+\)", "", name, flags=re.IGNORECASE).strip()
        isin = str(h.get("isin") or "")
        raw_type = str(h.get("asset_type") or h.get("asset") or h.get("asset_class") or "MF")

        class_id, bucket_id = classify_holding(symbol, clean_name, isin, raw_type, config)

        val = _safe_float(h.get("market_value") or h.get("value_inr") or h.get("current_value") or h.get("value"))
        invested = _safe_float(h.get("invested_amount") or h.get("invested_inr") or h.get("invested_value") or h.get("buy_value"))

        day_change_inr = _safe_float(
            h.get("one_day_change")
            or h.get("day_change_inr")
            or h.get("day_change")
            or h.get("one_day_return")
            or h.get("day_pnl")
        )
        day_pct = _safe_float(h.get("one_day_change_percentage") or h.get("day_pct") or h.get("day_change_pct"))
        if day_change_inr == 0.0 and day_pct != 0.0 and val > 0 and (100.0 + day_pct) > 0:
            day_change_inr = round(val * (day_pct / (100.0 + day_pct)), 2)

        raw_total_pct = _safe_float(h.get("pnl_per") or h.get("total_pct") or h.get("total_pnl_pct") or h.get("return_percentage"))

        if val <= 0 and invested <= 0:
            continue

        group_key = isin.strip().upper() if isin.strip() else symbol.strip().upper()
        if not group_key:
            group_key = clean_name.strip().lower()

        if group_key in merged_map:
            entry = merged_map[group_key]
            entry["current_value_inr"] += val
            entry["invested_value_inr"] += invested
            entry["one_day_change_inr"] += day_change_inr
        else:
            merged_map[group_key] = {
                "symbol": symbol,
                "name": clean_name,
                "isin": isin,
                "class_id": class_id,
                "bucket_id": bucket_id,
                "current_value_inr": val,
                "invested_value_inr": invested,
                "one_day_change_inr": day_change_inr,
                "raw_total_pct": raw_total_pct,
            }

    cfg = config or get_default_config()
    custom_palette = {b.id: b.color for b in cfg.buckets if b.color in VALID_PALETTE_KEYS}

    normalized_all: list[dict[str, Any]] = []
    for entry in merged_map.values():
        val = round(entry["current_value_inr"], 2)
        invested = round(entry["invested_value_inr"], 2)
        day_change_inr = round(entry["one_day_change_inr"], 2)

        day_pct = 0.0
        if val > 0 and (val - day_change_inr) > 0:
            day_pct = round((day_change_inr / (val - day_change_inr)) * 100.0, 2)

        total_pct = 0.0
        if invested > 0:
            total_pct = round(((val - invested) / invested) * 100.0, 2)
        elif entry.get("raw_total_pct"):
            total_pct = round(entry["raw_total_pct"], 2)

        b_id = entry["bucket_id"]
        palette_key = custom_palette.get(b_id) or BUCKET_PALETTE.get(b_id, "blue")

        item = {
            "symbol": entry["symbol"],
            "name": entry["name"],
            "isin": entry["isin"],
            "class_id": entry["class_id"],
            "bucket_id": entry["bucket_id"],
            "current_value_inr": val,
            "invested_value_inr": invested,
            "one_day_change_inr": day_change_inr,
            "one_day_change_pct": day_pct,
            "total_return_pct": total_pct,
            "palette_key": palette_key,
            # Legacy compatibility aliases
            "asset": entry["class_id"].upper(),
            "value_inr": val,
            "invested_inr": invested,
            "day_pct": day_pct,
            "day_change_inr": day_change_inr,
        }
        normalized_all.append(item)

    normalized_all.sort(key=lambda x: x["current_value_inr"], reverse=True)
    movers = sorted(normalized_all, key=lambda x: abs(x["one_day_change_pct"]), reverse=True)[:5]

    return normalized_all, movers


def normalize_sips(
    raw_mf_sips: Any,
    raw_in_sips: Any,
    raw_us_sips: Any,
    bank_balance_inr: float = 0.0,
    reference_date: datetime.date | None = None,
) -> dict[str, Any]:
    ref = reference_date or datetime.date.today()
    all_sips: list[dict[str, Any]] = []

    def _collect(sips: Any, default_class: str) -> None:
        sips = _parse_json_if_str(sips)
        items = []
        if isinstance(sips, list):
            items = sips
        elif isinstance(sips, dict):
            items = (
                sips.get("active_sips")
                or sips.get("indian_stocks_sips")
                or sips.get("us_stocks_sips")
                or sips.get("mf_sips")
                or sips.get("sips")
                or sips.get("data")
                or []
            )

        for s in items:
            if not isinstance(s, dict):
                continue

            if "active_sips" in s and isinstance(s["active_sips"], list):
                fund_name = str(s.get("name") or s.get("scheme_name") or "MF SIP")
                for sub in s["active_sips"]:
                    if isinstance(sub, dict):
                        amt = _safe_float(sub.get("amount") or sub.get("amount_inr"))
                        freq = str(sub.get("sip_frequency") or sub.get("frequency") or "monthly")
                        raw_d = str(sub.get("sip_start_date") or sub.get("next_date") or "")
                        proj_d = project_next_sip_date(raw_d, freq, ref)
                        all_sips.append({
                            "name": fund_name,
                            "amount_inr": amt,
                            "amount_usd": None,
                            "frequency": "weekly" if "week" in freq else "quarterly" if "quarter" in freq else "monthly",
                            "next_date": proj_d.strftime("%Y-%m-%d") if proj_d else "9999-12-31",
                            "next_date_obj": proj_d,
                            "class_id": default_class,
                        })
            else:
                name = str(s.get("name") or s.get("scheme_name") or s.get("symbol") or "SIP")
                freq = str(s.get("sip_frequency") or s.get("frequency") or "monthly")
                raw_d = str(s.get("next_date") or s.get("sip_start_date") or s.get("next_installment_date") or "")
                proj_d = project_next_sip_date(raw_d, freq, ref)

                is_usd = str(s.get("currency") or "").upper() == "USD" or "amount_usd" in s
                amt = _safe_float(s.get("amount") or s.get("amount_inr") or s.get("installment_amount"))
                usd_amt = _safe_float(s.get("amount_usd") or (amt if is_usd else 0.0))

                all_sips.append({
                    "name": name,
                    "amount_inr": 0.0 if is_usd else amt,
                    "amount_usd": usd_amt if is_usd else None,
                    "frequency": "weekly" if "week" in freq else "quarterly" if "quarter" in freq else "monthly",
                    "next_date": proj_d.strftime("%Y-%m-%d") if proj_d else "9999-12-31",
                    "next_date_obj": proj_d,
                    "class_id": default_class,
                })

    _collect(raw_mf_sips, "mf")
    _collect(raw_in_sips, "in_eq")
    _collect(raw_us_sips, "us_eq")

    all_sips.sort(key=lambda s: s["next_date_obj"] or datetime.date(9999, 12, 31))

    monthly_inr = 0.0
    monthly_usd = 0.0
    next_7d_sip_inr = 0.0

    end_7d = ref + datetime.timedelta(days=7)

    for s in all_sips:
        freq = s["frequency"]
        inr_amt = s["amount_inr"]
        usd_amt = s["amount_usd"] or 0.0

        factor = 52.0 / 12.0 if freq == "weekly" else (1.0 / 3.0 if freq == "quarterly" else 1.0)
        monthly_inr += inr_amt * factor
        monthly_usd += usd_amt * factor

        d_obj = s.get("next_date_obj")
        if d_obj and ref <= d_obj <= end_7d:
            next_7d_sip_inr += inr_amt

    coverage_ratio = (bank_balance_inr / next_7d_sip_inr) if next_7d_sip_inr > 0 else 999.0
    coverage_ok = bool(coverage_ratio >= 1.2) if next_7d_sip_inr > 0 else True

    upcoming_cleaned = []
    for s in all_sips[:10]:
        upcoming_cleaned.append({
            "name": s["name"],
            "amount_inr": round(s["amount_inr"], 2),
            "amount_usd": round(s["amount_usd"], 2) if s["amount_usd"] is not None else None,
            "next_date": s["next_date"],
            "frequency": s["frequency"],
            "class_id": s["class_id"],
            "type": s["class_id"].upper(),
        })

    return {
        "monthly_total_inr": round(monthly_inr, 2),
        "monthly_total_usd": round(monthly_usd, 2),
        "active_count": len(all_sips),
        "next_7d_sip_inr": round(next_7d_sip_inr, 2),
        "sip_coverage_ratio": round(coverage_ratio, 2),
        "sip_coverage_ok": coverage_ok,
        "upcoming": upcoming_cleaned,
    }


def compute_buckets(
    holdings: list[dict[str, Any]],
    invested_total_inr: float,
    config: AppConfig | None = None,
) -> list[dict[str, Any]]:
    cfg = config or get_default_config()
    specs = cfg.buckets

    totals: dict[str, float] = {b.id: 0.0 for b in specs}
    unassigned_val = 0.0

    for h in holdings:
        b_id = h.get("bucket_id", "core")
        val = h.get("current_value_inr", 0.0)
        if b_id in totals:
            totals[b_id] += val
        else:
            unassigned_val += val
            h["bucket_id"] = "unassigned"

    out = []
    for spec in specs:
        val = totals.get(spec.id, 0.0)
        actual_pct = round((val / invested_total_inr * 100.0), 1) if invested_total_inr > 0 else 0.0
        target_pct = spec.target
        band_pct = spec.band
        drift_pct = round(actual_pct - target_pct, 1)
        in_band = abs(drift_pct) <= band_pct if target_pct > 0 else (val == 0.0)
        rebalance_inr = round(((target_pct / 100.0) * invested_total_inr) - val, 2) if target_pct > 0 else -round(val, 2)

        out.append({
            "bucket_id": spec.id,
            "label": spec.label,
            "current_value_inr": round(val, 2),
            "actual_pct": actual_pct,
            "target_pct": target_pct,
            "band_pct": band_pct,
            "drift_pct": drift_pct,
            "rebalance_inr": rebalance_inr,
            "in_band": in_band,
            "palette_key": spec.color if spec.color in VALID_PALETTE_KEYS else BUCKET_PALETTE.get(spec.id, "blue"),
        })

    if unassigned_val > 0:
        actual_pct = round((unassigned_val / invested_total_inr * 100.0), 1) if invested_total_inr > 0 else 0.0
        out.append({
            "bucket_id": "unassigned",
            "label": "Unassigned",
            "current_value_inr": round(unassigned_val, 2),
            "actual_pct": actual_pct,
            "target_pct": 0.0,
            "band_pct": 0.0,
            "drift_pct": actual_pct,
            "rebalance_inr": -round(unassigned_val, 2),
            "in_band": False,
            "palette_key": "orange",
        })

    return out


def compute_attention_items(
    buckets: list[dict[str, Any]],
    sips_data: dict[str, Any],
    bank_balance_inr: float,
    status: str,
    freshness: str,
    failed_sources: list[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for b in buckets:
        if b.get("bucket_id") == "unassigned" and b.get("current_value_inr", 0) > 0:
            items.append({
                "type": "band_breach",
                "severity": "warning",
                "title": "Unassigned Holdings Alert",
                "message": f"₹{b['current_value_inr']:,.0f} in holdings are unassigned to any strategic bucket.",
                "palette_key": "orange",
            })
        elif not b["in_band"] and b["target_pct"] > 0:
            direction = "Overweight" if b["drift_pct"] > 0 else "Underweight"
            items.append({
                "type": "band_breach",
                "severity": "warning",
                "title": f"{b['label']} Drift Breach",
                "message": f"{b['label']} is {direction} by {abs(b['drift_pct'])}% (Target: {b['target_pct']}%, Actual: {b['actual_pct']}%).",
                "palette_key": "orange",
            })

    if not sips_data.get("sip_coverage_ok", True):
        next_7d = sips_data.get("next_7d_sip_inr", 0.0)
        items.append({
            "type": "sip_low_buffer",
            "severity": "alert",
            "title": "Low Bank Buffer for SIPs",
            "message": f"Bank balance (₹{bank_balance_inr:,.0f}) is below 1.2x of upcoming 7-day SIPs (₹{next_7d:,.0f}).",
            "palette_key": "orange",
        })

    if status == "partial":
        items.append({
            "type": "partial_sync",
            "severity": "warning",
            "title": "Partial Sync Warning",
            "message": f"Sync succeeded with partial data. Failed tools: {', '.join(failed_sources)}.",
            "palette_key": "yellow",
        })

    if freshness == "stale":
        items.append({
            "type": "stale_data",
            "severity": "warning",
            "title": "Stale Portfolio Quotes",
            "message": "Portfolio data has not updated in over 24 hours.",
            "palette_key": "yellow",
        })

    legacy_bucket = next((b for b in buckets if b["bucket_id"] == "legacy"), None)
    if legacy_bucket and legacy_bucket["current_value_inr"] > 0:
        items.append({
            "type": "legacy_holding",
            "severity": "info",
            "title": "Legacy Holdings Present",
            "message": f"Legacy holdings amount to ₹{legacy_bucket['current_value_inr']:,.0f} ({legacy_bucket['actual_pct']}%).",
            "palette_key": "sky",
        })

    return items


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
    auth_error: str | None = None,
    failed_sources: list[str] | None = None,
    reference_time: datetime.datetime | None = None,
    config: AppConfig | None = None,
) -> dict[str, Any]:
    cfg = config or get_default_config()

    if reference_time is not None:
        now_ist = reference_time.astimezone(IST)
    elif isinstance(prev_state, dict) and "reference_time" in prev_state:
        now_ist = prev_state["reference_time"]
    else:
        now_ist = datetime.datetime.now(IST)

    updated_at = int(now_ist.timestamp())
    today_date = now_ist.date()
    today_str = today_date.strftime("%Y-%m-%d")

    failed_srcs = failed_sources or []
    if failed_srcs and status == "ok":
        status = "partial"

    snapshot_parsed = _parse_json_if_str(snapshot)
    summary = normalize_summary(snapshot_parsed, holdings)

    all_holdings, top_movers = normalize_holdings(holdings, config=cfg)

    invested_holdings = [h for h in all_holdings if h["class_id"] in ("mf", "in_eq", "us_eq", "gold")]
    if invested_holdings:
        invested_curr = sum(h["current_value_inr"] for h in invested_holdings)
        invested_inv = sum(h["invested_value_inr"] for h in invested_holdings)
    else:
        invested_curr = summary["total_portfolio_inr"]
        invested_inv = summary["invested_inr"]

    one_day_chg_inr = summary["day_change_inr"]
    prev_invested = invested_curr - one_day_chg_inr
    one_day_chg_pct = round((one_day_chg_inr / prev_invested) * 100.0, 2) if prev_invested > 0 else summary["day_change_pct"]
    total_ret_inr = round(invested_curr - invested_inv, 2)
    total_ret_pct = round((total_ret_inr / invested_inv) * 100.0, 2) if invested_inv > 0 else 0.0

    invested_portfolio = {
        "current_value_inr": round(invested_curr, 2),
        "invested_value_inr": round(invested_inv, 2),
        "total_return_inr": total_ret_inr,
        "total_return_pct": total_ret_pct,
        "one_day_change_inr": round(one_day_chg_inr, 2),
        "one_day_change_pct": round(one_day_chg_pct, 2),
    }

    total_networth = {
        "total_networth_inr": round(invested_curr + summary["bank_inr"] + summary["epf_inr"], 2),
        "bank_balance_inr": round(summary["bank_inr"], 2),
        "epf_inr": round(summary["epf_inr"], 2),
    }

    buckets = compute_buckets(all_holdings, invested_curr, config=cfg)

    sips_data = normalize_sips(
        raw_mf_sips=mf_sips,
        raw_in_sips=in_sips,
        raw_us_sips=us_sips,
        bank_balance_inr=summary["bank_inr"],
        reference_date=today_date,
    )

    if prev_sparkline is None and isinstance(prev_state, dict):
        prev_sparkline = prev_state.get("sparkline_90d") or prev_state.get("sparkline")

    sparkline_90d = update_sparkline_90d(
        prev_sparkline=prev_sparkline,
        current_val=invested_curr,
        current_date_str=today_str,
        max_days=90,
        return_pct=total_ret_pct,
        invested_val=invested_inv,
    )

    nav_as_of = None
    if isinstance(snapshot_parsed, dict):
        nav_as_of = snapshot_parsed.get("nav_as_of") or snapshot_parsed.get("last_updated_at")

    if auth_error or status == "auth_required":
        freshness = "auth_required"
    elif status == "partial":
        freshness = "partial"
    else:
        nav_date = parse_date(str(nav_as_of)) if nav_as_of else None
        if nav_date:
            nav_age_days = (today_date - nav_date).days
            if nav_age_days > 5:
                freshness = "stale"
            elif nav_age_days > 3:
                freshness = "aging"
            else:
                freshness = "fresh"
        else:
            freshness = "fresh"

    attention_items = compute_attention_items(
        buckets=buckets,
        sips_data=sips_data,
        bank_balance_inr=summary["bank_inr"],
        status=status,
        freshness=freshness,
        failed_sources=failed_srcs,
    )

    unchanged_streak = 0
    if isinstance(prev_state, dict):
        prev_streak = int(prev_state.get("unchanged_streak", 0))
        prev_inv = _safe_float(prev_state.get("invested_portfolio", {}).get("current_value_inr") or prev_state.get("summary", {}).get("total_networth_inr"))
        prev_1d = _safe_float(prev_state.get("invested_portfolio", {}).get("one_day_change_inr") or prev_state.get("summary", {}).get("day_change_inr"))
        prev_ts = _safe_float(prev_state.get("updated_at", 0))

        nominal_state = get_nominal_market_state(now_ist)
        prev_nominal = (
            get_nominal_market_state(datetime.datetime.fromtimestamp(prev_ts, tz=IST))
            if prev_ts > 0
            else nominal_state
        )

        if prev_nominal != nominal_state:
            prev_streak = 0

        if nominal_state in ("IN_OPEN", "US_OPEN"):
            if abs(invested_curr - prev_inv) < 0.01 and abs(one_day_chg_inr - prev_1d) < 0.01:
                unchanged_streak = prev_streak + 1
            else:
                unchanged_streak = 0
        else:
            if abs(invested_curr - prev_inv) >= 0.01 or abs(one_day_chg_inr - prev_1d) >= 0.01:
                unchanged_streak = 0
            else:
                unchanged_streak = prev_streak
    else:
        nominal_state = get_nominal_market_state(now_ist)

    # Market state respects unchanged streak throttle
    if nominal_state in ("IN_OPEN", "US_OPEN") and unchanged_streak >= 2:
        market_state = "CLOSED"
    else:
        market_state = nominal_state

    if not allocation and isinstance(snapshot_parsed, dict):
        allocation = snapshot_parsed.get("assets") or snapshot_parsed.get("investments")
    alloc_items = normalize_allocation(allocation, total_networth["total_networth_inr"])

    return {
        "schema_version": 2,
        "provider": "indmoney",
        "status": status,
        "freshness": freshness,
        "nav_as_of": str(nav_as_of) if nav_as_of else None,
        "market_state": market_state,
        "failed_sources": failed_srcs,
        "updated_at": updated_at,
        "invested_portfolio": invested_portfolio,
        "total_networth": total_networth,
        "buckets": buckets,
        "buckets_enabled": bool(getattr(cfg.bucket_targets, "enabled", False)),
        "attention_items": attention_items,
        "holdings": all_holdings,
        "sips": sips_data,
        "sparkline_90d": sparkline_90d,
        "portfolio_os": {
            "enabled": bool(getattr(cfg.bucket_targets, "enabled", False)),
            "xirr_pct": None,
            "rebalance_action": None,
        },
        # Legacy compatibility aliases
        "summary": summary,
        "allocation": alloc_items,
        "top_movers": top_movers,
        "sparkline": sparkline_90d,
        "unchanged_streak": unchanged_streak,
        "auth_error": auth_error,
    }
