"""Configuration loader for indmoney-sync, managing dynamic buckets, ISIN maps, and polling policies."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import tomllib

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "inir" / "indmoney" / "config.toml"

VALID_PALETTE_KEYS = {
    "blue", "sky", "teal", "green", "yellow", "orange",
    "red", "pink", "indigo", "purple", "lavender", "gray",
}


@dataclass
class BucketSpec:
    id: str
    label: str
    target: float
    band: float = 2.5
    color: str = "blue"


@dataclass
class BucketTargets:
    enabled: bool = True
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
            "unassigned": 0.0,
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


def default_bucket_specs(targets: BucketTargets | None = None) -> list[BucketSpec]:
    t = targets or BucketTargets()
    tol = t.drift_tolerance_pct
    return [
        BucketSpec(id="core", label="Core Wealth", target=t.core, band=tol, color="blue"),
        BucketSpec(id="satellite", label="Satellite / Factor", target=t.satellite, band=tol, color="purple"),
        BucketSpec(id="gold_silver", label="Precious Metals", target=t.gold_silver, band=tol, color="yellow"),
        BucketSpec(id="liquid", label="Liquid & Arbitrage", target=t.liquid, band=tol, color="teal"),
        BucketSpec(id="legacy", label="Legacy", target=0.0, band=0.0, color="gray"),
    ]


@dataclass
class AppConfig:
    bucket_targets: BucketTargets = field(default_factory=BucketTargets)
    buckets: list[BucketSpec] = field(default_factory=default_bucket_specs)
    isin_map: dict[str, str] = field(default_factory=dict)
    strict_map: bool = False
    emergency_buffer_inr: float = 0.0
    polling: PollingConfig = field(default_factory=PollingConfig)
    overrides: dict[str, OverrideRule] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Synchronize buckets list if initialized with custom BucketTargets only
        if self.buckets == default_bucket_specs(BucketTargets()) and self.bucket_targets != BucketTargets():
            self.buckets = default_bucket_specs(self.bucket_targets)

    def valid_bucket_ids(self) -> set[str]:
        return {b.id.lower() for b in self.buckets} | {"unassigned"}

    def find_override(
        self,
        isin: str | None = None,
        symbol: str | None = None,
        name: str | None = None,
    ) -> OverrideRule | None:
        """Find matching override by [map] ISIN first, then [overrides] ISIN, symbol, or name substring."""
        valid_ids = self.valid_bucket_ids()

        # 0. Check explicit [map] table by ISIN or symbol
        if isin:
            norm_isin = isin.strip().upper()
            if norm_isin in self.isin_map:
                b_id = self.isin_map[norm_isin].lower()
                return OverrideRule(bucket_id=b_id if b_id in valid_ids else "unassigned")

        if symbol:
            norm_sym = symbol.strip().upper()
            if norm_sym in self.isin_map:
                b_id = self.isin_map[norm_sym].lower()
                return OverrideRule(bucket_id=b_id if b_id in valid_ids else "unassigned")

        if not self.overrides:
            return None

        # 1. Exact match on ISIN
        if isin:
            norm_isin = isin.strip().upper()
            for key, rule in self.overrides.items():
                if key.strip().upper() == norm_isin:
                    b_id = rule.bucket_id.lower() if rule.bucket_id else None
                    if b_id and b_id not in valid_ids:
                        return OverrideRule(class_id=rule.class_id, bucket_id="unassigned")
                    return rule

        # 2. Exact match on symbol
        if symbol:
            norm_sym = symbol.strip().upper()
            for key, rule in self.overrides.items():
                if key.strip().upper() == norm_sym:
                    b_id = rule.bucket_id.lower() if rule.bucket_id else None
                    if b_id and b_id not in valid_ids:
                        return OverrideRule(class_id=rule.class_id, bucket_id="unassigned")
                    return rule

        # 3. Substring match on name
        if name:
            norm_name = name.strip().lower()
            for key, rule in self.overrides.items():
                if key.strip().lower() in norm_name:
                    b_id = rule.bucket_id.lower() if rule.bucket_id else None
                    if b_id and b_id not in valid_ids:
                        return OverrideRule(class_id=rule.class_id, bucket_id="unassigned")
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

    # Parse bucket targets (dict format [targets] or [buckets])
    raw_targets = data.get("targets", {})
    if not raw_targets and isinstance(data.get("buckets"), dict):
        raw_targets = data.get("buckets")
    if not isinstance(raw_targets, dict):
        raw_targets = {}

    bucket_targets = BucketTargets(
        enabled=bool(raw_targets.get("enabled", True)),
        core=float(raw_targets.get("core", raw_targets.get("Core", 50.0))),
        satellite=float(raw_targets.get("satellite", raw_targets.get("Satellite", 30.0))),
        gold_silver=float(raw_targets.get("gold_silver", raw_targets.get("Gold_Silver", 10.0))),
        liquid=float(raw_targets.get("liquid", raw_targets.get("Liquid", 10.0))),
        drift_tolerance_pct=float(
            raw_targets.get("drift_tolerance_pct", raw_targets.get("tolerance_pct", 2.5))
        ),
    )

    # Parse dynamic buckets [[buckets]] if provided as a list
    raw_bucket_list = data.get("buckets")
    buckets: list[BucketSpec] = []
    if isinstance(raw_bucket_list, list):
        for b in raw_bucket_list:
            if isinstance(b, dict) and "id" in b:
                b_id = str(b["id"]).lower()
                label = str(b.get("label") or b_id.title())
                target = float(b.get("target", 0.0))
                band = float(b.get("band", b.get("drift_tolerance_pct", bucket_targets.drift_tolerance_pct)))
                color = str(b.get("color", "blue")).lower()
                if color not in VALID_PALETTE_KEYS:
                    color = "blue"
                buckets.append(BucketSpec(id=b_id, label=label, target=target, band=band, color=color))
    if not buckets:
        buckets = default_bucket_specs(bucket_targets)

    # Parse [map] table (ISIN/symbol -> bucket_id)
    raw_map = data.get("map", {}) or data.get("isin_map", {})
    isin_map: dict[str, str] = {}
    if isinstance(raw_map, dict):
        for k, v in raw_map.items():
            if isinstance(v, str):
                isin_map[str(k).strip().upper()] = v.strip().lower()

    # Parse strict_map & emergency_buffer (support top-level or under [map])
    strict_map = bool(data.get("strict_map", raw_map.get("strict_map", False)))
    emergency_buffer_inr = float(data.get("emergency_buffer_inr", raw_map.get("emergency_buffer_inr", 0.0)))

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
        buckets=buckets,
        isin_map=isin_map,
        strict_map=strict_map,
        emergency_buffer_inr=emergency_buffer_inr,
        polling=polling,
        overrides=overrides,
    )
