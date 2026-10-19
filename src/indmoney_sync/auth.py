"""OAuth 2.1 PKCE authorization flow & secure keyring management."""
import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import subprocess
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

import httpx
import keyring

SERVICE_NAME = "inir-indmoney-mcp"
KEYRING_ACCOUNT = "oauth_tokens"
DEFAULT_DISCOVERY_URL = "https://mcp.indmoney.com/.well-known/oauth-authorization-server"


def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def generate_pkce_pair() -> Tuple[str, str]:
    verifier_bytes = secrets.token_bytes(32)
    verifier = base64url_encode(verifier_bytes)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64url_encode(digest)
    return verifier, challenge


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def load_tokens() -> Optional[Dict[str, Any]]:
    try:
        raw = keyring.get_password(SERVICE_NAME, KEYRING_ACCOUNT)
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"[auth] Error loading tokens from keyring: {e}")
    return None


def save_tokens(tokens: Dict[str, Any]) -> None:
    try:
        raw = json.dumps(tokens)
        keyring.set_password(SERVICE_NAME, KEYRING_ACCOUNT, raw)
    except Exception as e:
        print(f"[auth] Error saving tokens to keyring: {e}")
        raise


def clear_tokens() -> None:
    try:
        keyring.delete_password(SERVICE_NAME, KEYRING_ACCOUNT)
    except Exception:
        pass


def is_token_expired(tokens: Dict[str, Any], buffer_sec: int = 60) -> bool:
    expires_at = tokens.get("expires_at", 0)
    return time.time() >= (expires_at - buffer_sec)


def discover_endpoints() -> Dict[str, Any]:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(DEFAULT_DISCOVERY_URL)
        resp.raise_for_status()
        return resp.json()


def refresh_token(tokens: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Attempts to refresh token using refresh_token grant."""
    refresh_token_val = tokens.get("refresh_token")
    client_id = tokens.get("client_id")
    if not refresh_token_val:
        return None

    if not metadata:
        metadata = discover_endpoints()

    token_endpoint = metadata.get("token_endpoint", "https://mcp.indmoney.com/token")

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token_val,
        "client_id": client_id
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(token_endpoint, data=payload)
            if resp.status_code == 200:
                data = resp.json()
                new_tokens = dict(tokens)
                new_tokens["access_token"] = data.get("access_token", tokens.get("access_token"))
                if "refresh_token" in data:
                    new_tokens["refresh_token"] = data["refresh_token"]
                expires_in = data.get("expires_in", 3600)
                new_tokens["expires_at"] = time.time() + expires_in
                save_tokens(new_tokens)
                return new_tokens
            else:
                print(f"[auth] Refresh failed with status {resp.status_code}: {resp.text}")
                return None
    except Exception as e:
        print(f"[auth] Exception during token refresh: {e}")
        return None


def register_client(registration_endpoint: str, redirect_uri: str) -> str:
    """Performs RFC 7591 dynamic client registration."""
    payload = {
        "client_name": "inir-indmoney",
        "redirect_uris": [redirect_uri],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": "portfolio:read market:read"
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(registration_endpoint, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["client_id"]


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    auth_code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Quiet logging

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            OAuthCallbackHandler.state = params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = (
                "<!DOCTYPE html><html><body style='font-family:sans-serif;text-align:center;padding:40px;'>"
                "<h1 style='color:#10b981;'>✓ Authorization Successful</h1>"
                "<p>You can close this tab and return to your desktop shell.</p>"
                "</body></html>"
            )
            self.wfile.write(html.encode("utf-8"))
        elif "error" in params:
            OAuthCallbackHandler.error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = f"<!DOCTYPE html><body><h1>Authorization Failed</h1><p>{OAuthCallbackHandler.error}</p></body></html>"
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def execute_browser_auth_flow() -> Dict[str, Any]:
    print("[auth] Discovering OAuth authorization server metadata...")
    metadata = discover_endpoints()
    auth_endpoint = metadata["authorization_endpoint"]
    token_endpoint = metadata["token_endpoint"]
    registration_endpoint = metadata.get("registration_endpoint")

    port = find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    print(f"[auth] Registering client with redirect URI: {redirect_uri}")
    client_id = register_client(registration_endpoint, redirect_uri)

    code_verifier, code_challenge = generate_pkce_pair()
    expected_state = secrets.token_hex(16)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "portfolio:read market:read",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": expected_state
    }
    auth_url = f"{auth_endpoint}?{urllib.parse.urlencode(params)}"

    print(f"[auth] Opening browser for IndMoney login...")
    print(f"[auth] URL: {auth_url}")

    # Launch browser via xdg-open
    try:
        subprocess.Popen(["xdg-open", auth_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[auth] Failed to open browser with xdg-open: {e}")

    server = http.server.HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
    server.timeout = 180.0  # 3 minutes for OTP/MPIN entry

    OAuthCallbackHandler.auth_code = None
    OAuthCallbackHandler.error = None

    print("[auth] Waiting for authorization callback on loopback listener...")
    while not OAuthCallbackHandler.auth_code and not OAuthCallbackHandler.error:
        server.handle_request()

    server.server_close()

    if OAuthCallbackHandler.error:
        raise RuntimeError(f"OAuth error: {OAuthCallbackHandler.error}")

    auth_code = OAuthCallbackHandler.auth_code
    if not auth_code:
        raise RuntimeError("No authorization code received.")

    print("[auth] Exchanging authorization code for tokens...")
    token_payload = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier
    }

    with httpx.Client(timeout=15.0) as client:
        resp = client.post(token_endpoint, data=token_payload)
        resp.raise_for_status()
        token_data = resp.json()

    expires_in = token_data.get("expires_in", 3600)
    tokens = {
        "client_id": client_id,
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "token_type": token_data.get("token_type", "Bearer"),
        "scope": token_data.get("scope", "portfolio:read market:read"),
        "expires_at": time.time() + expires_in
    }

    save_tokens(tokens)
    print(f"[auth] Tokens saved successfully to keyring under '{SERVICE_NAME}'.")
    return tokens
