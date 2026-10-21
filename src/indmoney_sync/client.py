"""Streamable HTTP MCP Client (MCP 2025-03-26 protocol) with SSE and direct JSON parsing."""
import json
import random
import time
from typing import Any

import httpx

ALLOWED_TOOLS = {
    "networth_snapshot",
    "networth_allocation_breakdown",
    "networth_holdings",
    "mf_sips",
    "indian_stocks_sips",
    "us_stocks_sips"
}

BLOCKED_TOOLS = {
    "save_analysis"
}


class IndMoneyMcpClient:
    def __init__(self, endpoint: str, access_token: str, session_id: str | None = None):
        self.endpoint = endpoint
        self.access_token = access_token
        self.session_id = session_id
        self._request_id = 0
        self._client = httpx.Client(timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "IndMoneyMcpClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {}
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.access_token}"
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        max_retries = 3
        base_delay = 0.5
        response = None

        for attempt in range(max_retries + 1):
            try:
                response = self._client.post(self.endpoint, json=payload, headers=headers)

                # Capture session ID if returned by server
                new_session = response.headers.get("Mcp-Session-Id")
                if new_session:
                    self.session_id = new_session

                if response.status_code == 401:
                    raise PermissionError("IndMoney token expired or invalid (401 Unauthorized)")

                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt < max_retries:
                        sleep_time = (base_delay * (2 ** attempt)) + random.uniform(0.05, 0.25)
                        time.sleep(sleep_time)
                        continue
                    response.raise_for_status()

                response.raise_for_status()
                break
            except (httpx.TransportError, httpx.TimeoutException):
                if attempt < max_retries:
                    sleep_time = (base_delay * (2 ** attempt)) + random.uniform(0.05, 0.25)
                    time.sleep(sleep_time)
                    continue
                raise

        content_type = response.headers.get("content-type", "")

        # SSE Stream Parsing (Correction E)
        if "text/event-stream" in content_type:
            rpc_result = None
            for line in response.iter_lines():
                line = line.strip()
                if line.startswith("data:"):
                    raw_data = line[len("data:"):].strip()
                    if not raw_data:
                        continue
                    try:
                        msg = json.loads(raw_data)
                        if isinstance(msg, dict) and msg.get("id") == req_id:
                            rpc_result = msg
                            break
                    except json.JSONDecodeError:
                        continue

            if rpc_result is None:
                raise ValueError("Did not find matching JSON-RPC response in SSE stream.")
            data = rpc_result
        else:
            data = response.json()

        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"MCP RPC Error [{err.get('code')}]: {err.get('message')}")

        return data.get("result", {})

    def initialize(self) -> dict[str, Any]:
        params = {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {
                "name": "inir-indmoney",
                "version": "1.0.0"
            }
        }
        return self._send_rpc("initialize", params)

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._send_rpc("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if name in BLOCKED_TOOLS:
            raise PermissionError(f"Tool '{name}' is in the blocked write operations list.")
        if name not in ALLOWED_TOOLS:
            print(f"[client] Warning: Calling tool '{name}' which is outside standard allowlist.")

        params = {
            "name": name,
            "arguments": arguments or {}
        }
        result = self._send_rpc("tools/call", params)

        raw_val = None
        if isinstance(result, dict) and "structuredContent" in result:
            raw_val = result["structuredContent"]
        elif isinstance(result, dict) and "content" in result:
            content = result.get("content", [])
            if isinstance(content, list) and len(content) > 0:
                first = content[0]
                if isinstance(first, dict) and "text" in first:
                    raw_val = str(first["text"]).strip()
        else:
            raw_val = result

        # If raw_val is a string, unwrap code fences and parse JSON
        if isinstance(raw_val, str):
            val_str = raw_val.strip()
            if val_str.startswith("```"):
                lines = val_str.split("\n")
                if len(lines) >= 2 and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                val_str = "\n".join(lines).strip()
            try:
                raw_val = json.loads(val_str)
            except Exception:
                pass

        # If raw_val is a dict with "result" containing inner JSON string, unwrap it
        if isinstance(raw_val, dict) and "result" in raw_val:
            res_inner = raw_val["result"]
            if isinstance(res_inner, str):
                try:
                    return json.loads(res_inner)
                except Exception:
                    pass
            elif isinstance(res_inner, (dict, list)):
                return res_inner

        return raw_val



