"""Configuration loader for indmoney-sync, managing bucket targets, polling policies, and classification overrides."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import tomllib

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "inir" / "indmoney" / "config.toml"


@dataclass
class BucketTargets:
    core: float = 50.0
    satellite: float = 30.0
    gold_silver: float = 10.0
    liquid: float = 10.0
    drift_tolerance_pct: float = 2.5

    def get_target(self, bucket_id: str) -> float:
        mapping = {
            "core": self.core,
            "satellite": self.satellite,
            "gold_silver": self.gold_silver,
            "liquid": self.liquid,
            "legacy": 0.0,
        }
        return mapping.get(bucket_id.lower(), 0.0)


@dataclass
class PollingConfig:
    intraday_equity_polling: bool = False
    equity_weight_threshold_pct: float = 5.0


@dataclass
class OverrideRule:
    class_id: str | None = None
    bucket_id: str | None = None


@dataclass
class AppConfig:
    bucket_targets: BucketTargets = field(default_factory=BucketTargets)
    polling: PollingConfig = field(default_factory=PollingConfig)
    overrides: dict[str, OverrideRule] = field(default_factory=dict)

    def find_override(
        self,
        isin: str | None = None,
        symbol: str | None = None,
        name: str | None = None,
    ) -> OverrideRule | None:
        """Find matching override by ISIN, symbol, or name substring (case-insensitive)."""
        if not self.overrides:
            return None

        # 1. Exact match on ISIN
        if isin:
            norm_isin = isin.strip().upper()
            for key, rule in self.overrides.items():
                if key.strip().upper() == norm_isin:
                    return rule

        # 2. Exact match on symbol
        if symbol:
            norm_sym = symbol.strip().upper()
            for key, rule in self.overrides.items():
                if key.strip().upper() == norm_sym:
                    return rule

        # 3. Substring match on name
        if name:
            norm_name = name.strip().lower()
            for key, rule in self.overrides.items():
                if key.strip().lower() in norm_name:
                    return rule

        return None


def get_default_config() -> AppConfig:
    return AppConfig()


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """Loads config.toml using stdlib tomllib. Falls back to default if file does not exist."""
    if config_path is None:
        env_path = os.environ.get("INDMONEY_CONFIG_PATH")
        path = Path(env_path) if env_path else DEFAULT_CONFIG_PATH
    else:
        path = Path(config_path)

    if not path.is_file():
        return get_default_config()

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        print(f"[config] Warning: Failed to parse TOML config at {path}: {e}. Using defaults.")
        return get_default_config()

    # Parse bucket targets
    raw_targets = data.get("targets", {}) or data.get("buckets", {})
    bucket_targets = BucketTargets(
        core=float(raw_targets.get("core", raw_targets.get("Core", 50.0))),
        satellite=float(raw_targets.get("satellite", raw_targets.get("Satellite", 30.0))),
        gold_silver=float(raw_targets.get("gold_silver", raw_targets.get("Gold_Silver", 10.0))),
        liquid=float(raw_targets.get("liquid", raw_targets.get("Liquid", 10.0))),
        drift_tolerance_pct=float(
            raw_targets.get("drift_tolerance_pct", raw_targets.get("tolerance_pct", 2.5))
        ),
    )

    # Parse polling
    raw_polling = data.get("polling", {})
    polling = PollingConfig(
        intraday_equity_polling=bool(raw_polling.get("intraday_equity_polling", False)),
        equity_weight_threshold_pct=float(raw_polling.get("equity_weight_threshold_pct", 5.0)),
    )

    # Parse overrides
    raw_overrides = data.get("overrides", {})
    overrides: dict[str, OverrideRule] = {}
    if isinstance(raw_overrides, dict):
        for key, val in raw_overrides.items():
            if isinstance(val, dict):
                overrides[str(key)] = OverrideRule(
                    class_id=val.get("class_id") or val.get("asset_class"),
                    bucket_id=val.get("bucket_id") or val.get("bucket"),
                )

    return AppConfig(
        bucket_targets=bucket_targets,
        polling=polling,
        overrides=overrides,
    )
