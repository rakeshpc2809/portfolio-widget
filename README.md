# IndMoney Portfolio Widget for iNiR / iRiS (Quickshell)

A real-time, privacy-conscious portfolio widget built natively for **snowarch/iNiR** and the **iRiS** desktop shell on Arch Linux / CachyOS and Niri.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. DATA PLANE (Python CLI + systemd user timer / worker)               │
│                                                                        │
│  [libsecret / OS Keyring] <──(OAuth 2.1 PKCE)──> [indmoney-sync]       │
│                                                        │               │
│  https://mcp.indmoney.com/mcp <──(Streamable HTTP)─────┘               │
│   ├── Fast Tier (15m): networth_snapshot, breakdown, holdings          │
│   └── Slow Tier (6h):  mf_sips, indian_stocks_sips, us_stocks_sips     │
│                                                        │               │
│  Atomic tmpfs write (tempfile -> os.replace)           ▼               │
│  /run/user/$UID/inir-indmoney/state.json (& ~/.cache/.../last_good.json)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ inotify / FileView (non-blocking)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. UI PLANE (Quickshell / iNiR QML — Zero Secrets, Zero Network I/O)   │
│                                                                        │
│  services/IndMoneyService.qml (Singleton)                              │
│   ├── Watches /run/user/$UID/inir-indmoney/state.json                  │
│   └── Non-blocking Process: `indmoney-sync fetch --force`              │
│                                                                        │
│  modules/iris/pieces/PortfolioPiece.qml  (Island Bubble / Pill)        │
│  modules/iris/cards/PortfolioCard.qml    (Expanded Island Card)        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

1. **Strict Secret Isolation & Keyring Security:**
   - OAuth 2.1 PKCE authorization flow via RFC 8414 metadata discovery and dynamic client registration.
   - Tokens stored exclusively in the Linux kernel keyring / Secret Service via `libsecret` under service name `inir-indmoney-mcp`.
   - Zero secrets stored in plaintext on disk or in QML memory.

2. **Non-Blocking UI Thread:**
   - Background Python sync process triggered by `systemd --user` timer.
   - Quickshell reads local state via non-blocking `FileView` watching tmpfs (`/run/user/$UID/inir-indmoney/state.json`).

3. **Market-Aware Polling Governor:**
   - **NSE / BSE Window (09:00–16:00 IST Mon–Fri):** 15-minute polling.
   - **US Market Window (19:00–02:00 IST Mon–Fri):** 15-minute polling.
   - **Off-Hours / Weekends:** Skips network calls if cache is younger than 60 minutes (bypassed with `--force`).

4. **Aesthetic & Modern UX Upgrades:**
   - **Tabular Figures:** Monospace numerals using `JetBrains Mono Nerd Font` with `font.features: { "tnum": 1 }` to eliminate horizontal jitter.
   - **Gaussian Blur Privacy Transition:** `QtQuick.Effects` `MultiEffect` Gaussian blur condensing over sensitive numbers on middle-click (`blur: 1.0` over 180ms cubic bezier).
   - **Interactive Hover Scrubbing:** Proportional multi-segment asset allocation bar where hovering dynamically expands segment height (`SpringAnimation`) and morphs live allocation metrics.
   - **Ambient Market Status Dot:** Emerald pulsing indicator when markets are open (`IN_OPEN` / `US_OPEN`), dimmed when closed, and amber when offline or auth required.

---

## Installation & Setup

### Quick Install

```bash
cd ~/Projects/portfolio-widget
make install
```

This will:
1. Symlink `indmoney-sync` to `~/.local/bin/indmoney-sync`.
2. Configure `~/.config/user-tmpfiles.d/inir-indmoney.conf` to guarantee runtime dir existence.
3. Install and activate systemd user service `inir-indmoney-sync.service` and timer `inir-indmoney-sync.timer`.
4. Link QML components into `~/.config/quickshell/inir/`.
5. Register `IndMoneyService` in `services/qmldir`.
6. Register the `portfolio` piece into `IrisPieces.qml`, `IrisBubbleFace.qml`, and `IrisCardContent.qml`.
7. Generate initial offline mock state.

---

## CLI Usage

| Command | Description |
|---|---|
| `indmoney-sync auth` | Opens browser for IndMoney login (Mobile + OTP + MPIN) via loopback OAuth 2.1 PKCE. |
| `indmoney-sync inspect` | Dumps raw MCP tool schemas and responses to `~/.cache/inir/indmoney/raw_dump.json`. |
| `indmoney-sync fetch` | Headless worker run by systemd (governed by market hours). |
| `indmoney-sync fetch --force` | Bypasses market governor to immediately refresh live data. |
| `indmoney-sync mock` | Writes realistic mock portfolio data for testing without live login. |
| `indmoney-sync status` | Displays keyring token status, market state, and last sync timestamp. |

---

## Widget Interactions

### Compact Bubble / Pill (`PortfolioPiece.qml`)
* **Left-Click:** Morphs/expands the Island stage into `PortfolioCard.qml`.
* **Middle-Click:** Toggles **Privacy Mode** (smooth Gaussian blur condensation over currency amounts).
* **Right-Click:** Triggers an immediate background sync (`indmoney-sync fetch --force`) with a pulsing indicator dot.

### Expanded Card (`PortfolioCard.qml`)
* **Header:** Net worth hero, 1D change badge, invested vs returns, manual sync button `[↻]`, privacy toggle `[👁]`.
* **Interactive Allocation Bar:** Proportional bar with hover scrubbing showing exact INR amounts and weights.
* **Top Movers Tab:** Top 5 gainers and losers today with percentage chips.
* **All Holdings Tab:** Category filter chips (`All`, `IN Eq`, `MF`, `US Eq`) with invested and current values.
* **Active SIPs Tab:** Monthly aggregate commitment and chronological list of upcoming deductions.
* **Session Fallback:** Direct "Connect IndMoney" button if session ever expires.

---

## Testing & Quality Assurance

Run the test suite:
```bash
make test
```

Runs:
- `test_normalizer.py`: Math, schema mapping, and top movers selection.
- `test_governor.py`: IST and US market window calculations and off-hours scheduling.
- Validated against iNiR's `test-iris-defaults.py` and `test-iris-performance-contract.py`.
