# IndMoney Portfolio Widget for iNiR / iRiS (Quickshell)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg)](https://www.python.org/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Quickshell: Compatible](https://img.shields.io/badge/Quickshell-iNiR%20%2F%20iRiS-purple.svg)](https://github.com/snowarch/iNiR)

A native, calm, privacy-first portfolio widget built strictly for the **snowarch/iNiR** and **iRiS** desktop shell on Arch Linux / CachyOS and Niri. Displays your aggregate net worth, 1D returns, asset allocation drift, upcoming SIP commitments, liquidity buffer coverage, and individual holdings within a high-performance Bento grid.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. DATA PLANE (Python CLI + systemd user timer / worker)               │
│                                                                        │
│  [libsecret / OS Keyring] <──(OAuth 2.1 PKCE + State Cache)──> [indmoney-sync]
│                                                        │               │
│  https://mcp.indmoney.com/mcp <──(Streamable HTTP)─────┘               │
│   ├── Fast Tier (15m): networth_snapshot, breakdown, holdings          │
│   └── Slow Tier (6h):  mf_sips, indian_stocks_sips, us_stocks_sips     │
│                                                        │               │
│  Atomic tmpfs write (tempfile -> os.replace, mode 0600)▼               │
│  /run/user/$UID/inir-indmoney/state.json (100% RAM, zero disk leaks)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ inotify / FileView (non-blocking)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. UI PLANE (Quickshell / iNiR QML — Zero Secrets, Zero Network I/O)   │
│                                                                        │
│  services/IndMoneyService.qml (Singleton Thin Viewer)                  │
│   ├── Watches /run/user/$UID/inir-indmoney/state.json (Schema v2)      │
│   └── Non-blocking Process: `indmoney-sync fetch --force`              │
│                                                                        │
│  modules/iris/pieces/PortfolioPiece.qml  (Calm Island Bar Pill)        │
│  modules/iris/cards/PortfolioCard.qml    (Bento Grid Stage Card)       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Bento Grid & UI Architecture

The interface follows the iRiS design language (`IrisStyle`), using slot-rolling typography, subtle micro-animations, neutral semantic palettes, and lazy progressive disclosure:

### 1. Compact Bar Pill (`PortfolioPiece.qml`)
- **Rolling Figures (`M2`):** Slot-rolling numerical transitions via `IrisNumber` with tabular numbers (`tnum: 1`), gated by `IrisStyle.motionEnabled && root.visible`.
- **Zero-Digit-Leak Privacy (`M8`, `V5`):** Complete elimination of Gaussian blur artifacts. Opacity crossfades smoothly (`IrisStyle.duration(120)`) between the live figure and a static mask (`"₹ ••••••"`) that never leaks digit count.
- **Quiet Mode by Default (`F3`):** Hides 1D % at rest to maintain visual calm; reveals smoothly on pill hover (`hoverHandler.hovered`).
- **Calm Status Indicator (`M6`):** Zero infinite pulsing at rest. Alerts appear only for actionable events (`partial` sync, `stale` cache, `auth_required`, or active `attention_items`) using strict `IrisStyle.identity` tokens (`teal`, `yellow`, `orange`, `red`).

### 2. Expanded Bento Stage Card (`PortfolioCard.qml`)
- **Card Header (`CardHeader`):** Shows NAV as-of timestamp with a live freshness badge (`FRESH`, `AGING`, `STALE`, `PARTIAL`, `AUTH_REQUIRED`), plus controls for Quiet Mode (`Q`), Privacy Mode (`P`), and Refresh (`R`).
- **Hero Platter (`M1`, `C8`, `C11`, `M9`):**
  - **Shared Basis Figure (`C8`):** Displays `investedPortfolio.current_value_inr` so the primary amount and 1D % share the identical denominator.
  - **Dual-Basis Transparency:** Secondary captions break down Net Worth (`Bank` + `EPF`) and Invested Basis (`Total Return INR` + `%`).
  - **90-Day Daily Sparkline (`C11`):** Smooth polyline curve (`QtQuick.Shapes` `ShapePath` + `PathPolyline`) rendered in calm `IrisStyle.identity.teal` with gradient fill.
  - **OLED Care / Idle Dimming (`M9`):** Binds subtle opacity dimming when `ScreenTime.userIdle` indicates user inactivity.
- **Tile 1 — Asset Allocation & Bucket Drift Strip (`F1`, `M3`, `V2`):**
  - Displays target buckets (`Core Wealth 50%`, `Growth / Alpha 30%`, `Precious Metals 10%`, `Cash & Arbitrage 10%`) as bullet bars with shaded `±2.5%` tolerance bands and 2px target tick markers.
  - Smooth bar animations powered by `IrisSpring { springSpec: IrisStyle.springFor("standard", "card") }`.
  - Calm color semantics: Neutral palette keys (`blue`, `purple`, `yellow`, `teal`) when within tolerance; ramps to `IrisStyle.identity.orange` only when drifted beyond band.
  - Interactive hover scrubbing displaying exact INR value, actual %, target %, and drift %.
- **Tile 2 — Attention Feed (`F2`, `C6`):**
  - Actionable alert feed highlighting drift breaches, partial sync issues, or low SIP buffers.
  - Calm empty state when everything is on track: *"All buckets in band · Nothing needs you"*.
- **Tile 3 — Upcoming SIPs & Liquidity Coverage (`F4`, `C1`, `C7`):**
  - Next upcoming SIP deduction with calendar-safe day projection (`calendar.monthrange`).
  - Total monthly commitment (`INR` + `USD`).
  - 7-day liquidity coverage badge (`sip_coverage_ratio`x vs liquid bank balance, colored `teal` when covered, `orange` when deficient).
- **Lazy-Loaded Drill-Down Drawer (`V1`, `M8`):**
  - Gated by `Loader { active: root.visible && root.drillDownOpen }` so hidden list delegates consume zero memory at rest.
  - **View 1 (Holdings):** Full portfolio holdings filterable by category chips (`ALL`, `CORE`, `SATELLITE`, `GOLD_SILVER`, `LIQUID`).
  - **View 2 (SIP Schedule):** Chronological upcoming schedule with frequency, date, amount, and asset class badges.
- **Keyboard Navigation (`M7`):**
  - `1`: Switch to Holdings View
  - `2`: Switch to SIP Schedule View
  - `3` / `D`: Toggle Drill-Down Drawer
  - `Tab`: Cycle bucket category filters
  - `Q`: Toggle Quiet Mode
  - `P`: Toggle Privacy Mode
  - `R`: Trigger immediate background sync

---

## Privacy & Security Architecture

1. **Zero Plaintext on Disk (`0700` Tmpfs):**
   - Active portfolio state resides exclusively in volatile RAM (`/run/user/$UID/inir-indmoney/state.json`) with strict `0700` directory and `0600` file permissions.
   - All state is destroyed immediately upon session logout or system shutdown.
   - The legacy `~/.cache/inir/indmoney` disk cache has been completely eliminated.
2. **Kernel Keyring Integration (`libsecret`):**
   - OAuth 2.1 PKCE tokens and cold-boot state fallback are stored encrypted in the Linux Secret Service / Keyring under `inir-indmoney-mcp`.
   - On boot, `indmoney-sync hydrate` reconstitutes state in tmpfs at millisecond zero without exposing credentials.
3. **Protected Diagnostic Inspection:**
   - Raw API dumps require the explicit `--allow-raw-dump` flag.
   - Dumps write strictly to RAM-backed tmpfs (`/run/user/$UID/inir-indmoney/raw_dump.json`) with `0600` permissions and never to persistent disk.

---

## Strategy Configuration (`config.toml`)

Customize asset allocation targets, tolerances, and governor behavior via `~/.config/inir/indmoney.toml` (copy from `config.example.toml`):

```toml
[strategy]
# Total target allocations must equal 100%
tolerance_pct = 2.5 # Band threshold (e.g. ±2.5%)

[[strategy.buckets]]
id = "core"
label = "Core Wealth"
target_pct = 50.0
palette_key = "blue" # Verified IrisStyle.identity key

[[strategy.buckets]]
id = "satellite"
label = "Growth / Alpha"
target_pct = 30.0
palette_key = "purple"

[[strategy.buckets]]
id = "gold_silver"
label = "Precious Metals"
target_pct = 10.0
palette_key = "yellow"

[[strategy.buckets]]
id = "liquid"
label = "Cash & Arbitrage"
target_pct = 10.0
palette_key = "teal"

[governor]
# Market-hours polling configuration
nav_morning_window = "07:30-09:30"
nav_evening_window = "21:30-23:30"
equity_weight_threshold_pct = 15.0 # Minimum equity weight to poll during active market hours
```

---

## Installation & Setup

### 1. Install Widget & Systemd Service

From the repository root:
```bash
git clone https://github.com/rakeshpc2809/portfolio-widget.git
cd portfolio-widget
make install
```

The installer will:
1. Symlink `indmoney-sync` to `~/.local/bin/indmoney-sync`.
2. Configure `~/.config/user-tmpfiles.d/inir-indmoney.conf` to guarantee `0700` tmpfs setup on boot.
3. Install and activate systemd user timer `inir-indmoney-sync.timer`.
4. Symlink QML components into `~/.config/quickshell/inir/`.
5. Register entries in `services/qmldir`, `modules/iris/pieces/qmldir`, and `modules/iris/stage/qmldir`.
6. Apply clean, marker-based patches (`/* INIR_INDMONEY_BEGIN:... */`) to `IrisPieces.qml`, `IrisBubbleFace.qml`, and `IrisCardContent.qml`.
7. Generate initial mock state so the widget renders immediately.

### 2. Connect Your Live Account (Optional)

To link your live IndMoney account via OAuth 2.1 PKCE:
```bash
indmoney-sync auth
```
This opens your browser for secure login (Mobile + OTP + MPIN). Upon authorization, tokens are stored directly in your encrypted OS keyring.

---

## Clean Uninstallation

To cleanly and reversibly uninstall the widget:
```bash
make uninstall
# or
./install.sh --uninstall
```

This performs a 100% complete rollback:
1. Stops and disables systemd user timers and services.
2. Removes CLI and QML component symlinks.
3. Cleans entries from all `qmldir` files.
4. Strips marker blocks from `IrisPieces.qml`, `IrisBubbleFace.qml`, and `IrisCardContent.qml`, restoring them byte-for-byte to their pristine upstream state.
5. Removes tmpfs runtime state and reloads Quickshell.

---

## CLI Reference

| Command | Description |
|---|---|
| `indmoney-sync auth` | Authenticate via loopback OAuth 2.1 PKCE into OS keyring. |
| `indmoney-sync mock` | Generates canonical Schema v2 mock state for offline testing. |
| `indmoney-sync fetch` | Headless worker invoked by systemd timer (governed by market hours). |
| `indmoney-sync fetch --force` | Bypasses market governor to immediately refresh live figures. |
| `indmoney-sync hydrate` | Restores encrypted cached state from keyring to tmpfs on boot. |
| `indmoney-sync status` | Displays keyring token status, freshness, and market schedule. |
| `indmoney-sync inspect --allow-raw-dump` | Dumps raw MCP tool responses to tmpfs (`0600`) for debugging. |

---

## Testing & Quality Assurance

Run the test suite:
```bash
make test
# or
pytest -v
```

Run code formatting and linting:
```bash
make lint
# or
ruff check .
```

Validate iRiS performance contracts and defaults:
```bash
python3 ~/.config/quickshell/inir/scripts/test-iris-performance-contract.py
python3 ~/.config/quickshell/inir/scripts/test-iris-defaults.py
```

---

## License

This project is licensed under the [MIT License](LICENSE).
