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
    load_tokens,
    refresh_token,
    save_cached_state_to_keyring,
)
from .client import IndMoneyMcpClient
from .governor import get_market_state, should_fetch
from .inspector import run_inspect
from .mock_data import get_mock_state
from .normalizer import build_normalized_state

MCP_ENDPOINT = "https://mcp.indmoney.com/mcp"

# Volatile RAM-backed tmpfs path for active runtime state
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "inir-indmoney"
CACHE_DIR = Path.home() / ".cache" / "inir" / "indmoney"

STATE_FILE = RUNTIME_DIR / "state.json"
STATE_TMP_FILE = RUNTIME_DIR / "state.json.tmp"
SIPS_CACHE_FILE = CACHE_DIR / "sips_cache.json"
LEGACY_LAST_GOOD_FILE = CACHE_DIR / "last_good.json"


def ensure_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def write_atomic_state(payload: dict[str, Any]) -> None:
    """
    Atomically writes state JSON to RAM tmpfs.
    Backs up the state securely into encrypted OS Keyring (libsecret).
    Zero plaintext balance data is ever saved to persistent disk.
    """
    ensure_dirs()
    # Write to tmpfs tmp file first
    with open(STATE_TMP_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    # Atomic replace in tmpfs
    os.replace(STATE_TMP_FILE, STATE_FILE)

    # Persist backup securely into encrypted OS Keyring (zero disk leaks)
    if payload.get("status") == "ok":
        save_cached_state_to_keyring(payload)

    # Clean up legacy unencrypted disk cache if present
    if LEGACY_LAST_GOOD_FILE.exists():
        try:
            LEGACY_LAST_GOOD_FILE.unlink(missing_ok=True)
        except Exception:
            pass


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

    # First check encrypted keyring
    cached = load_cached_state_from_keyring()

    # Fallback migration check for legacy file if keyring empty
    if not cached and LEGACY_LAST_GOOD_FILE.exists():
        try:
            with open(LEGACY_LAST_GOOD_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached:
                save_cached_state_to_keyring(cached)
                LEGACY_LAST_GOOD_FILE.unlink(missing_ok=True)
        except Exception:
            pass

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
    print("[indmoney-sync] Inspecting IndMoney MCP schemas...")
    try:
        run_inspect()
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

    should_run, reason, market_state = should_fetch(state=prev_state, force=force)
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

    try:
        with IndMoneyMcpClient(MCP_ENDPOINT, access_token) as client:
            client.initialize()

            # Fast tier tools
            if verbose:
                print("[indmoney-sync] Fetching networth_snapshot...")
            snapshot = client.call_tool("networth_snapshot")

            # Extract allocation directly from snapshot assets/investments
            allocation = None
            if isinstance(snapshot, dict):
                allocation = snapshot.get("assets") or snapshot.get("investments")

            if verbose:
                print("[indmoney-sync] Fetching holdings (MF, IND_STOCK, US_STOCK)...")
            holdings = []
            for asset_type in ["MF", "IND_STOCK", "US_STOCK"]:
                try:
                    res = client.call_tool("networth_holdings", {"asset_type": asset_type})
                    if isinstance(res, dict) and "holdings" in res and isinstance(res["holdings"], list):
                        holdings.extend(res["holdings"])
                    elif isinstance(res, list):
                        holdings.extend(res)
                except Exception as e:
                    if verbose:
                        print(f"[indmoney-sync] Warning fetching {asset_type} holdings: {e}")

            # Slow tier tools (SIPs) - cache for 6 hours
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
                if verbose:
                    print("[indmoney-sync] Fetching slow-tier tools (SIPs)...")
                try:
                    mf_sips = client.call_tool("mf_sips")
                except Exception:
                    mf_sips = []
                try:
                    in_sips = client.call_tool("indian_stocks_sips")
                except Exception:
                    in_sips = []
                try:
                    us_sips = client.call_tool("us_stocks_sips")
                except Exception:
                    us_sips = []

                sips_cached = {
                    "mf": mf_sips,
                    "in": in_sips,
                    "us": us_sips
                }
                with open(SIPS_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(sips_cached, f)

            # Retrieve previous sparkline ring buffer from tmpfs state or encrypted keyring
            prev_sparkline = []
            if STATE_FILE.exists():
                try:
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        prev_data = json.load(f)
                        if isinstance(prev_data.get("sparkline"), list):
                            prev_sparkline = prev_data["sparkline"]
                except Exception:
                    pass
            if not prev_sparkline:
                cached_prev = load_cached_state_from_keyring()
                if cached_prev and isinstance(cached_prev.get("sparkline"), list):
                    prev_sparkline = cached_prev["sparkline"]

            state = build_normalized_state(
                snapshot=snapshot,
                allocation=allocation,
                holdings=holdings,
                mf_sips=sips_cached.get("mf"),
                in_sips=sips_cached.get("in"),
                us_sips=sips_cached.get("us"),
                prev_sparkline=prev_sparkline,
                prev_state=prev_state,
                status="ok"
            )

            write_atomic_state(state)
            if verbose:
                networth = state["summary"]["total_networth_inr"]
                pnl = state["summary"]["total_pnl_inr"]
                print(f"[indmoney-sync] Sync successful! Net worth: ₹{networth:,.2f} (P&L: ₹{pnl:,.2f})")
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
            s = data.get("summary", {})
            print(f"Active State (RAM):{STATE_FILE}")
            print(f"Updated At:        {time.ctime(data.get('updated_at', 0))}")
            print(f"Total Net Worth:   ₹{s.get('total_networth_inr', 0):,.2f}")
            print(f"Total Invested:    ₹{s.get('invested_inr', 0):,.2f}")
            print(f"1D Change:        ₹{s.get('day_change_inr', 0):,.2f} ({s.get('day_change_pct', 0)}%)")
            print(f"Status:           {data.get('status')}")
            spark_len = len(data.get("sparkline", []))
            print(f"Sparkline Points: {spark_len}/30")
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
    subparsers.add_parser("inspect", help="Inspect and sample MCP tool schemas")

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
