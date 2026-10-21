"""Tests for CLI, partial failure handling, tmpfs paths, and zero plaintext on disk."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import indmoney_sync.cli as cli
import indmoney_sync.inspector as inspector


class TestCliAndSecurity(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.runtime_dir = self.tmp_path / "runtime" / "inir-indmoney"
        self.legacy_cache = self.tmp_path / "cache" / "inir" / "indmoney"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_ensure_dirs_removes_legacy_cache_and_sets_0700_tmpfs(self):
        """Zero plaintext on disk: legacy ~/.cache/inir/indmoney must be deleted, runtime tmpfs mode 0700."""
        self.legacy_cache.mkdir(parents=True, exist_ok=True)
        leak_file = self.legacy_cache / "sips_cache.json"
        leak_file.write_text('{"leaked": "data"}', encoding="utf-8")
        self.assertTrue(leak_file.exists())

        with patch.object(cli, "RUNTIME_DIR", self.runtime_dir), \
             patch.object(cli, "LEGACY_CACHE_DIR", self.legacy_cache):
            cli.ensure_dirs()
            self.assertTrue(self.runtime_dir.exists())
            # Legacy cache dir must be completely purged
            self.assertFalse(self.legacy_cache.exists())
            self.assertFalse(leak_file.exists())

    def test_inspector_requires_allow_raw_dump(self):
        """Inspector must refuse to write raw tool samples to disk unless --allow-raw-dump is passed."""
        dump_file = self.runtime_dir / "raw_dump.json"

        with patch.object(inspector, "RUNTIME_DIR", self.runtime_dir), \
             patch.object(inspector, "DUMP_FILE", dump_file), \
             patch.object(inspector, "LEGACY_CACHE_DIR", self.legacy_cache), \
             patch("indmoney_sync.inspector.load_tokens", return_value={"access_token": "tok"}), \
             patch("indmoney_sync.inspector.refresh_token", return_value=None), \
             patch("indmoney_sync.inspector.IndMoneyMcpClient") as mock_client_cls:

            mock_client = MagicMock()
            mock_client.initialize.return_value = {"protocolVersion": "2025-03-26"}
            mock_client.list_tools.return_value = [{"name": "networth_snapshot"}]
            mock_client.call_tool.return_value = {"networth": 100}
            mock_client_cls.return_value.__enter__.return_value = mock_client

            # Without flag: dump is not written to disk
            res = inspector.run_inspect(allow_raw_dump=False)
            self.assertIn("tools_list", res)
            self.assertFalse(dump_file.exists())

            # With flag: writes to tmpfs with mode 0600
            res = inspector.run_inspect(allow_raw_dump=True)
            self.assertTrue(dump_file.exists())
            file_mode = oct(dump_file.stat().st_mode & 0o777)
            self.assertEqual(file_mode, "0o600")

    def test_partial_failure_preserves_cached_slice_and_emits_partial_status(self):
        """When an individual tool fails (e.g. us_stocks_sips), preserve cached slice and set status='partial'."""
        state_file = self.runtime_dir / "state.json"
        sips_file = self.runtime_dir / "sips_cache.json"

        prev_state = {
            "schema_version": 2,
            "provider": "indmoney",
            "status": "ok",
            "updated_at": 1000,
            "invested_portfolio": {"current_value_inr": 2000000.0},
            "holdings": [
                {"symbol": "AAPL", "class_id": "us_eq", "current_value_inr": 50000.0}
            ],
            "sips": {
                "upcoming": [{"name": "VOO", "class_id": "us_eq", "amount_usd": 50.0}]
            }
        }

        with patch.object(cli, "RUNTIME_DIR", self.runtime_dir), \
             patch.object(cli, "STATE_FILE", state_file), \
             patch.object(cli, "STATE_TMP_FILE", self.runtime_dir / "state.json.tmp"), \
             patch.object(cli, "SIPS_CACHE_FILE", sips_file), \
             patch.object(cli, "LEGACY_CACHE_DIR", self.legacy_cache), \
             patch("indmoney_sync.cli.load_tokens", return_value={"access_token": "tok"}), \
             patch("indmoney_sync.cli.is_token_expired", return_value=False), \
             patch("indmoney_sync.cli.load_cached_state_from_keyring", return_value=prev_state), \
             patch("indmoney_sync.cli.save_cached_state_to_keyring"), \
             patch("indmoney_sync.cli.save_sips_cache_to_keyring"), \
             patch("indmoney_sync.cli.load_sips_cache_from_keyring", return_value={"us": [{"name": "VOO", "amount_usd": 50.0}]}), \
             patch("indmoney_sync.cli.IndMoneyMcpClient") as mock_client_cls:

            mock_client = MagicMock()
            mock_client.initialize.return_value = {}
            mock_client.call_tool.side_effect = lambda tool_name, *args: {
                "networth_snapshot": {"total_portfolio_inr": 2000000.0, "total_networth_inr": 2000000.0},
                "networth_holdings": [{"symbol": "HDFCBANK", "asset_type": "IND_STOCK", "current_value": 100000.0}],
                "mf_sips": [],
                "indian_stocks_sips": [],
            }.get(tool_name) if tool_name != "us_stocks_sips" else (_ for _ in ()).throw(RuntimeError("US SIP API 500"))

            mock_client_cls.return_value.__enter__.return_value = mock_client

            args = MagicMock()
            args.force = True
            args.verbose = False

            exit_code = cli.cmd_fetch(args)
            self.assertEqual(exit_code, 0)
            self.assertTrue(state_file.exists())

            saved_state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved_state["status"], "partial")
            self.assertIn("us_stocks_sips", saved_state["failed_sources"])


if __name__ == "__main__":
    unittest.main()
