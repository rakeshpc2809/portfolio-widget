"""Tests for IndMoney MCP client exponential backoff, jitter, and error handling."""
import unittest
from unittest.mock import MagicMock, patch

import httpx

from indmoney_sync.client import IndMoneyMcpClient


class TestIndMoneyMcpClient(unittest.TestCase):
    def setUp(self):
        self.endpoint = "https://mcp.indmoney.com/mcp"
        self.token = "test_access_token"

    @patch("time.sleep")
    def test_send_rpc_retries_on_429_and_succeeds(self, mock_sleep):
        client = IndMoneyMcpClient(self.endpoint, self.token)

        # Mock responses: 429 first, then 200 with result
        mock_resp_429 = MagicMock(spec=httpx.Response)
        mock_resp_429.status_code = 429
        mock_resp_429.headers = {}
        mock_resp_429.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_resp_429
        )

        mock_resp_200 = MagicMock(spec=httpx.Response)
        mock_resp_200.status_code = 200
        mock_resp_200.headers = {"content-type": "application/json"}
        mock_resp_200.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": [{"name": "networth_snapshot"}]}
        }

        with patch.object(client._client, "post", side_effect=[mock_resp_429, mock_resp_200]):
            res = client._send_rpc("tools/list")
            self.assertEqual(res, {"tools": [{"name": "networth_snapshot"}]})
            self.assertEqual(mock_sleep.call_count, 1)

    @patch("time.sleep")
    def test_send_rpc_retries_on_503_and_exhausts_retries(self, mock_sleep):
        client = IndMoneyMcpClient(self.endpoint, self.token)

        mock_resp_503 = MagicMock(spec=httpx.Response)
        mock_resp_503.status_code = 503
        mock_resp_503.headers = {}
        mock_resp_503.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable", request=MagicMock(), response=mock_resp_503
        )

        with patch.object(client._client, "post", return_value=mock_resp_503):
            with self.assertRaises(httpx.HTTPStatusError):
                client._send_rpc("tools/list")
            # Should have retried 3 times (attempts 0, 1, 2 sleep; attempt 3 raises)
            self.assertEqual(mock_sleep.call_count, 3)

    def test_send_rpc_raises_401_immediately_without_retry(self):
        client = IndMoneyMcpClient(self.endpoint, self.token)

        mock_resp_401 = MagicMock(spec=httpx.Response)
        mock_resp_401.status_code = 401
        mock_resp_401.headers = {}

        with patch.object(client._client, "post", return_value=mock_resp_401):
            with self.assertRaises(PermissionError):
                client._send_rpc("tools/list")

    def test_blocked_tools_raise_permission_error(self):
        client = IndMoneyMcpClient(self.endpoint, self.token)
        with self.assertRaises(PermissionError):
            client.call_tool("save_analysis")


if __name__ == "__main__":
    unittest.main()
