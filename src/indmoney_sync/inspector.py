"""Schema inspector dumping live MCP tool schemas and responses for grounding normalizer."""
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .auth import load_tokens, refresh_token
from .client import ALLOWED_TOOLS, IndMoneyMcpClient

RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "inir-indmoney"
DUMP_FILE = RUNTIME_DIR / "raw_dump.json"
LEGACY_CACHE_DIR = Path.home() / ".cache" / "inir" / "indmoney"
MCP_ENDPOINT = "https://mcp.indmoney.com/mcp"


def purge_legacy_cache_dir() -> None:
    """Removes legacy unencrypted cache directory from persistent disk if present."""
    if LEGACY_CACHE_DIR.exists():
        try:
            shutil.rmtree(LEGACY_CACHE_DIR, ignore_errors=True)
        except Exception:
            pass


def run_inspect(allow_raw_dump: bool = False) -> dict[str, Any]:
    purge_legacy_cache_dir()
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(RUNTIME_DIR, 0o700)
    except Exception:
        pass

    tokens = load_tokens()
    if not tokens:
        raise RuntimeError("No tokens found in keyring. Run 'indmoney-sync auth' first.")

    # Refresh if expired
    refreshed = refresh_token(tokens)
    if refreshed:
        tokens = refreshed

    access_token = tokens["access_token"]
    print(f"[inspect] Connecting to MCP endpoint: {MCP_ENDPOINT}")

    dump_payload: dict[str, Any] = {
        "tools_list": [],
        "tool_samples": {}
    }

    with IndMoneyMcpClient(MCP_ENDPOINT, access_token) as client:
        print("[inspect] Initializing MCP protocol...")
        init_res = client.initialize()
        dump_payload["init_result"] = init_res

        print("[inspect] Querying tools/list...")
        tools = client.list_tools()
        dump_payload["tools_list"] = tools
        print(f"[inspect] Found {len(tools)} available MCP tools:")
        for t in tools:
            print(f"  - {t.get('name')}: {t.get('description', '')[:70]}...")

        print("\n[inspect] Sampling read-only allowlisted tools...")
        for tool_name in ALLOWED_TOOLS:
            try:
                print(f"  Calling '{tool_name}'...")
                res = client.call_tool(tool_name)
                dump_payload["tool_samples"][tool_name] = res
            except Exception as e:
                print(f"  Warning: Call to '{tool_name}' failed: {e}")
                dump_payload["tool_samples"][tool_name] = {"error": str(e)}

    # Privacy gate: Raw dump requires explicit flag and writes strictly to tmpfs with 0600 mode
    if not allow_raw_dump:
        print("\n[inspect] Inspection completed in-memory. Raw dump omitted for privacy.")
        print("          Pass '--allow-raw-dump' to write raw responses to tmpfs.")
        return dump_payload

    # Atomic write to tmpfs with 0600 permissions
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(DUMP_FILE), flags, 0o600)
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(dump_payload, f, indent=2)

    print("\n[inspect] Successfully dumped raw tool schemas & samples to tmpfs:")
    print(f"          {DUMP_FILE} (mode 0600)")
    return dump_payload
