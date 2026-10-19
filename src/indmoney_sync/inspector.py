"""Schema inspector dumping live MCP tool schemas and responses for grounding normalizer."""
import json
import os
from pathlib import Path
from typing import Any, Dict

from .auth import load_tokens, refresh_token
from .client import ALLOWED_TOOLS, IndMoneyMcpClient

CACHE_DIR = Path.home() / ".cache" / "inir" / "indmoney"
DUMP_FILE = CACHE_DIR / "raw_dump.json"
MCP_ENDPOINT = "https://mcp.indmoney.com/mcp"


def run_inspect() -> Dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tokens = load_tokens()
    if not tokens:
        raise RuntimeError("No tokens found in keyring. Run 'indmoney-sync auth' first.")

    # Refresh if expired
    refreshed = refresh_token(tokens)
    if refreshed:
        tokens = refreshed

    access_token = tokens["access_token"]
    print(f"[inspect] Connecting to MCP endpoint: {MCP_ENDPOINT}")

    dump_payload: Dict[str, Any] = {
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

    # Save to file
    with open(DUMP_FILE, "w", encoding="utf-8") as f:
        json.dump(dump_payload, f, indent=2)

    print(f"\n[inspect] Successfully dumped raw tool schemas & samples to:")
    print(f"          {DUMP_FILE}")
    return dump_payload
