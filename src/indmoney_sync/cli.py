"""CLI entrypoint for IndMoney MCP synchronizer."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .auth import (
    clear_tokens,
    execute_browser_auth_flow,
    is_token_expired,
    load_cached_state_from_keyring,
    load_sips_cache_from_keyring,
    load_tokens,
    refresh_token,
    save_cached_state_to_keyring,
    save_sips_cache_to_keyring,
)
from .client import IndMoneyMcpClient
from .config import load_config
from .governor import get_market_state, should_fetch
from .inspector import run_inspect
from .mock_data import get_mock_state
from .normalizer import build_normalized_state

MCP_ENDPOINT = "https://mcp.indmoney.com/mcp"

# Volatile RAM-backed tmpfs path for active runtime state (mode 0700)
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "inir-indmoney"
LEGACY_CACHE_DIR = Path.home() / ".cache" / "inir" / "indmoney"

STATE_FILE = RUNTIME_DIR / "state.json"
STATE_TMP_FILE = RUNTIME_DIR / "state.json.tmp"
SIPS_CACHE_FILE = RUNTIME_DIR / "sips_cache.json"


def ensure_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(RUNTIME_DIR, 0o700)
    except Exception:
        pass
    if LEGACY_CACHE_DIR.exists():
        import shutil
        shutil.rmtree(LEGACY_CACHE_DIR, ignore_errors=True)


def _write_private_json(path: Path, data: Any, indent: int | None = None) -> None:
    """Atomically writes JSON with 0o600 permissions using a temporary file in the same directory."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(tmp_path), flags, 0o600)
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
    os.replace(tmp_path, path)


def write_atomic_state(payload: dict[str, Any]) -> None:
    """
    Atomically writes state JSON to RAM tmpfs with 0o600 private permissions.
    Backs up the state securely into encrypted OS Keyring (libsecret).
    Zero plaintext balance data is ever saved to persistent disk.
    """
    ensure_dirs()
    _write_private_json(STATE_FILE, payload, indent=2)

    # Persist backup securely into encrypted OS Keyring (zero disk leaks)
    if payload.get("status") in ("ok", "partial"):
        save_cached_state_to_keyring(payload)


def hydrate_state() -> bool:
    """
    Cold-boot tmpfs hydration:
    If state.json does not exist in tmpfs, loads the last known state from
    the encrypted OS keyring (libsecret) and atomically writes to tmpfs
    with "market_state": "CACHED".
    Zero plaintext files on persistent disk.
    """
    if STATE_FILE.exists():
        return False

    cached = load_cached_state_from_keyring()
    if not cached:
        return False

    try:
        cached["market_state"] = "CACHED"
        write_atomic_state(cached)
        return True
    except Exception as e:
        print(f"[indmoney-sync] Hydration failed: {e}", file=sys.stderr)
        return False


def notify_user(title: str, message: str, urgency: str = "normal") -> None:
    try:
        subprocess.run(
            ["notify-send", "-a", "IndMoney", "-u", urgency, title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def get_cached_or_default_state() -> dict[str, Any]:
    cached = load_cached_state_from_keyring()
    if cached:
        return cached
    return get_mock_state()


def cmd_hydrate(args: argparse.Namespace) -> int:
    ensure_dirs()
    hydrated = hydrate_state()
    if hydrated:
        print(f"[indmoney-sync] Hydrated {STATE_FILE} from secure keyring (market_state: CACHED)")
    else:
        if STATE_FILE.exists():
            print(f"[indmoney-sync] State file already exists at {STATE_FILE}, skipping hydration.")
        else:
            print("[indmoney-sync] No cached state found in keyring.")
    return 0


def cmd_auth(args: argparse.Namespace) -> int:
    print("[indmoney-sync] Starting OAuth 2.1 PKCE interactive authentication...")
    try:
        execute_browser_auth_flow()
        print("[indmoney-sync] Auth completed successfully! Running initial fetch...")
        return cmd_fetch(argparse.Namespace(force=True, verbose=True))
    except Exception as e:
        print(f"[indmoney-sync] Authentication failed: {e}", file=sys.stderr)
        notify_user("IndMoney Login Failed", str(e), urgency="critical")
        return 1


def cmd_inspect(args: argparse.Namespace) -> int:
    allow_raw_dump = getattr(args, "allow_raw_dump", False)
    print(f"[indmoney-sync] Inspecting IndMoney MCP schemas (allow_raw_dump={allow_raw_dump})...")
    try:
        run_inspect(allow_raw_dump=allow_raw_dump)
        return 0
    except Exception as e:
        print(f"[indmoney-sync] Inspect failed: {e}", file=sys.stderr)
        return 1


def cmd_mock(args: argparse.Namespace) -> int:
    print("[indmoney-sync] Writing mock portfolio data...")
    state = get_mock_state()
    write_atomic_state(state)
    print(f"[indmoney-sync] Wrote mock state to {STATE_FILE}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    ensure_dirs()
    force = getattr(args, "force", False)
    verbose = getattr(args, "verbose", False)

    # Auto-hydrate on cold boot before any network activity
    if not STATE_FILE.exists():
        hydrated = hydrate_state()
        if hydrated and verbose:
            print("[indmoney-sync] Cold boot detected: pre-hydrated state.json from secure keyring.")

    # Check last state for governor check and unchanged_streak tracking
    prev_state = None
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                prev_state = json.load(f)
        except Exception:
            pass
    if not prev_state:
        prev_state = load_cached_state_from_keyring()

    cfg = load_config()
    should_run, reason, market_state = should_fetch(state=prev_state, force=force, config=cfg)
    if verbose:
        print(f"[indmoney-sync] Governor check: should_run={should_run} ({reason}), market={market_state}")

    if not should_run:
        if verbose:
            print("[indmoney-sync] Skipping fetch as cache is fresh and market is off-hours.")
        return 0

    tokens = load_tokens()
    if not tokens:
        print("[indmoney-sync] No tokens found in keyring. Auth required.")
        state = get_cached_or_default_state()
        state["status"] = "auth_required"
        state["auth_error"] = "Please connect IndMoney"
        write_atomic_state(state)
        notify_user("IndMoney Session Required", "Please connect your IndMoney account from the widget.", urgency="critical")
        return 2

    # Refresh token if needed
    if is_token_expired(tokens):
        if verbose:
            print("[indmoney-sync] Token expired or expiring soon, refreshing...")
        refreshed = refresh_token(tokens)
        if not refreshed:
            print("[indmoney-sync] Token refresh failed with invalid_grant.")
            clear_tokens()
            state = get_cached_or_default_state()
            state["status"] = "auth_required"
            state["auth_error"] = "Session expired, please re-authenticate"
            write_atomic_state(state)
            notify_user("IndMoney Session Expired", "Please re-authenticate your IndMoney account.", urgency="critical")
            return 2
        tokens = refreshed

    access_token = tokens["access_token"]
    failed_sources: list[str] = []

    try:
        with IndMoneyMcpClient(MCP_ENDPOINT, access_token) as client:
            client.initialize()

            # Fast tier tools
            if verbose:
                print("[indmoney-sync] Fetching networth_snapshot...")
            snapshot = None
            try:
                snapshot = client.call_tool("networth_snapshot")
            except Exception as e:
                failed_sources.append("networth_snapshot")
                if verbose:
                    print(f"[indmoney-sync] Warning fetching networth_snapshot: {e}")
                if prev_state and isinstance(prev_state.get("snapshot"), (dict, list)):
                    snapshot = prev_state["snapshot"]

            # Extract allocation directly from snapshot assets/investments
            allocation = None
            if isinstance(snapshot, dict):
                allocation = snapshot.get("assets") or snapshot.get("investments")

            if verbose:
                print("[indmoney-sync] Fetching holdings (MF, IND_STOCK, US_STOCK)...")
            holdings = []
            class_map = {"MF": "mf", "IND_STOCK": "in_eq", "US_STOCK": "us_eq"}
            for asset_type in ["MF", "IND_STOCK", "US_STOCK"]:
                try:
                    res = client.call_tool("networth_holdings", {"asset_type": asset_type})
                    if isinstance(res, dict) and "holdings" in res and isinstance(res["holdings"], list):
                        holdings.extend(res["holdings"])
                    elif isinstance(res, list):
                        holdings.extend(res)
                except Exception as e:
                    tool_id = f"networth_holdings_{asset_type.lower()}"
                    failed_sources.append(tool_id)
                    if verbose:
                        print(f"[indmoney-sync] Warning fetching {asset_type} holdings: {e}")
                    # Preserve cached slice from prev_state if available
                    if prev_state and isinstance(prev_state.get("holdings"), list):
                        target_class = class_map.get(asset_type)
                        prev_slice = [h for h in prev_state["holdings"] if h.get("class_id") == target_class]
                        holdings.extend(prev_slice)

            # Slow tier tools (SIPs) - cache for 6 hours in tmpfs & keyring
            now = time.time()
            sips_cached = None
            if SIPS_CACHE_FILE.exists():
                try:
                    mtime = SIPS_CACHE_FILE.stat().st_mtime
                    if (now - mtime) < (6 * 3600) and not force:
                        with open(SIPS_CACHE_FILE, "r", encoding="utf-8") as f:
                            sips_cached = json.load(f)
                except Exception:
                    pass
            if not sips_cached:
                sips_cached = load_sips_cache_from_keyring()

            if not sips_cached or force:
                if verbose:
                    print("[indmoney-sync] Fetching slow-tier tools (SIPs)...")
                existing_sips = sips_cached or {}
                sips_cached = dict(existing_sips)

                try:
                    sips_cached["mf"] = client.call_tool("mf_sips")
                except Exception as e:
                    failed_sources.append("mf_sips")
                    if "mf" not in sips_cached or sips_cached["mf"] is None:
                        sips_cached["mf"] = []
                    if verbose:
                        print(f"[indmoney-sync] Warning fetching mf_sips: {e}")

                try:
                    sips_cached["in"] = client.call_tool("indian_stocks_sips")
                except Exception as e:
                    failed_sources.append("indian_stocks_sips")
                    if "in" not in sips_cached or sips_cached["in"] is None:
                        sips_cached["in"] = []
                    if verbose:
                        print(f"[indmoney-sync] Warning fetching indian_stocks_sips: {e}")

                try:
                    sips_cached["us"] = client.call_tool("us_stocks_sips")
                except Exception as e:
                    failed_sources.append("us_stocks_sips")
                    if "us" not in sips_cached or sips_cached["us"] is None:
                        sips_cached["us"] = []
                    if verbose:
                        print(f"[indmoney-sync] Warning fetching us_stocks_sips: {e}")

                # Save sips to tmpfs and keyring
                try:
                    _write_private_json(SIPS_CACHE_FILE, sips_cached)
                    save_sips_cache_to_keyring(sips_cached)
                except Exception:
                    pass

            # Retrieve previous sparkline ring buffer from tmpfs state or encrypted keyring
            prev_sparkline = []
            if STATE_FILE.exists():
                try:
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        prev_data = json.load(f)
                        if isinstance(prev_data.get("sparkline_90d"), list):
                            prev_sparkline = prev_data["sparkline_90d"]
                        elif isinstance(prev_data.get("sparkline"), list):
                            prev_sparkline = prev_data["sparkline"]
                except Exception:
                    pass
            if not prev_sparkline:
                cached_prev = load_cached_state_from_keyring()
                if cached_prev:
                    if isinstance(cached_prev.get("sparkline_90d"), list):
                        prev_sparkline = cached_prev["sparkline_90d"]
                    elif isinstance(cached_prev.get("sparkline"), list):
                        prev_sparkline = cached_prev["sparkline"]

            sync_status = "partial" if failed_sources else "ok"

            state = build_normalized_state(
                snapshot=snapshot,
                allocation=allocation,
                holdings=holdings,
                mf_sips=sips_cached.get("mf"),
                in_sips=sips_cached.get("in"),
                us_sips=sips_cached.get("us"),
                prev_sparkline=prev_sparkline,
                prev_state=prev_state,
                status=sync_status,
                failed_sources=failed_sources,
                config=cfg,
            )

            write_atomic_state(state)
            if verbose:
                inv = state.get("invested_portfolio", {})
                curr_val = inv.get("current_value_inr", 0)
                ret_inr = inv.get("total_return_inr", 0)
                print(f"[indmoney-sync] Sync successful ({sync_status})! Invested: ₹{curr_val:,.2f} (Return: ₹{ret_inr:,.2f})")
            return 0

    except PermissionError as e:
        print(f"[indmoney-sync] Permission/Auth error: {e}")
        state = get_cached_or_default_state()
        state["status"] = "auth_required"
        state["auth_error"] = str(e)
        write_atomic_state(state)
        notify_user("IndMoney Auth Error", str(e), urgency="critical")
        return 2
    except Exception as e:
        print(f"[indmoney-sync] Fetch failed: {e}", file=sys.stderr)
        state = get_cached_or_default_state()
        state["status"] = "error"
        state["auth_error"] = str(e)
        write_atomic_state(state)
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    tokens = load_tokens()
    has_token = tokens is not None
    expired = is_token_expired(tokens) if tokens else True
    market = get_market_state()
    cached_keyring = load_cached_state_from_keyring()

    print("=== IndMoney Sync Status ===")
    print(f"Keyring Tokens:    {'Configured' if has_token else 'Missing'}")
    if has_token:
        print(f"Token Validity:    {'Expired (needs refresh)' if expired else 'Active'}")
    print(f"Keyring Cache:     {'Populated' if cached_keyring else 'Empty'}")
    print(f"Market State:      {market}")

    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            inv = data.get("invested_portfolio", {})
            net = data.get("total_networth", {})
            print(f"Active State (RAM):{STATE_FILE}")
            print(f"Updated At:        {time.ctime(data.get('updated_at', 0))}")
            print(f"Total Net Worth:   ₹{net.get('total_networth_inr', 0):,.2f}")
            print(f"Invested Value:    ₹{inv.get('current_value_inr', 0):,.2f}")
            print(f"1D Change:        ₹{inv.get('one_day_change_inr', 0):,.2f} ({inv.get('one_day_change_pct', 0)}%)")
            print(f"Status:           {data.get('status')}")
            if data.get("failed_sources"):
                print(f"Failed Sources:   {data.get('failed_sources')}")
            spark_len = len(data.get("sparkline_90d", data.get("sparkline", [])))
            print(f"Sparkline Points: {spark_len}/90")
        except Exception as e:
            print(f"Error reading state file: {e}")
    else:
        print(f"Active State:      Not yet initialized in tmpfs ({STATE_FILE})")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IndMoney MCP Sync CLI for iNiR / iRiS")
    subparsers = parser.add_subparsers(dest="command")

    # auth
    subparsers.add_parser("auth", help="Interactive OAuth 2.1 PKCE authorization")

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect and sample MCP tool schemas")
    inspect_parser.add_argument(
        "--allow-raw-dump",
        action="store_true",
        help="Allow writing raw MCP tool responses to tmpfs (/run/user/$UID/inir-indmoney/raw_dump.json with 0600 mode)",
    )

    # hydrate
    subparsers.add_parser("hydrate", help="Cold-boot tmpfs hydration from encrypted keyring")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Headless sync worker")
    fetch_parser.add_argument("--force", action="store_true", help="Bypass governor and force refresh")
    fetch_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    # mock
    subparsers.add_parser("mock", help="Write realistic mock state for testing")

    # status
    subparsers.add_parser("status", help="Show current sync and token status")

    args = parser.parse_args()

    if args.command == "auth":
        return cmd_auth(args)
    elif args.command == "inspect":
        return cmd_inspect(args)
    elif args.command == "hydrate":
        return cmd_hydrate(args)
    elif args.command == "fetch":
        return cmd_fetch(args)
    elif args.command == "mock":
        return cmd_mock(args)
    elif args.command == "status":
        return cmd_status(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

