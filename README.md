# IndMoney Portfolio Widget for iNiR / iRiS (Quickshell)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-3776ab.svg)](https://www.python.org/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Quickshell: Compatible](https://img.shields.io/badge/Quickshell-iNiR%20%2F%20iRiS-purple.svg)](https://github.com/snowarch/iNiR)

A real-time, privacy-first portfolio widget built natively for **snowarch/iNiR** and the **iRiS** desktop shell on Arch Linux / CachyOS and Niri. Displays your aggregate net worth, daily P&L, asset allocation, top movers, individual holdings, and active SIP schedules with a smooth, glassmorphic UI.

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
│  Atomic tmpfs write (tempfile -> os.replace)           ▼               │
│  /run/user/$UID/inir-indmoney/state.json (100% RAM, zero disk leaks)   │
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
   - **OAuth 2.1 PKCE:** RFC 8414 metadata discovery and dynamic client registration with short-lived access tokens and refresh rotation.
   - **Kernel Keyring Integration:** Tokens are stored exclusively in the Linux kernel keyring / Secret Service via `libsecret` under service name `inir-indmoney-mcp`.
   - **Zero Secrets on Disk or in QML:** Neither plaintext passwords, tokens, nor session cookies are ever saved on disk or exposed to the UI process.

2. **Non-Blocking UI Thread:**
   - The UI process does zero HTTP calls or cryptographic operations.
   - Quickshell reads local state via non-blocking `FileView` watching RAM-backed tmpfs (`/run/user/$UID/inir-indmoney/state.json`).
   - Manual refreshes spawn an asynchronous background worker without stalling frame rates.

3. **Market-Aware Polling Governor:**
   - **NSE / BSE Market Window (09:00–16:00 IST Mon–Fri):** 15-minute polling.
   - **US Market Window (19:00–02:00 IST Mon–Fri):** 15-minute polling.
   - **Off-Hours / Weekends:** Reuses cached state if younger than 60 minutes (bypassed on-demand with `--force`).

4. **Aesthetic & Modern UX Upgrades:**
   - **Tabular Figures:** Monospace numerals using `JetBrains Mono Nerd Font` / `IrisStyle.fontNumbers` with `font.features: { "tnum": 1 }` to eliminate horizontal jitter.
   - **Gaussian Blur Privacy Mode:** `QtQuick.Effects` `MultiEffect` Gaussian blur condensing over sensitive numbers on middle-click or eye button toggle (`blur: 1.0` over 180ms cubic bezier).
   - **Interactive Hover Scrubbing:** Proportional multi-segment asset allocation bar where hovering dynamically expands segment height (`SpringAnimation`) and morphs live allocation metrics.
   - **Ambient Market Status Dot:** Pulsing emerald indicator when Indian or US markets are open, dimmed when closed, and amber when offline or auth is needed.

---

## Prerequisites

- **Linux OS:** Arch Linux, CachyOS, Fedora, or Ubuntu with Wayland (e.g. Niri, Hyprland, Sway).
- **Python:** 3.10 or higher.
- **System Dependencies:**
  ```bash
  # Arch Linux / CachyOS
  sudo pacman -S python-httpx python-keyring libsecret
  # Or install via pip
  pip install -r requirements.txt
  ```
- **Desktop Shell:** [Quickshell](https://outfoxxed.me/quickshell/) with the [iNiR desktop configuration](https://github.com/snowarch/iNiR).

---

## Installation & Setup

### 1. Install Widget & Systemd Service

Run the installer from the repository root:
```bash
git clone https://github.com/rakeshpc2809/portfolio-widget.git
cd portfolio-widget
make install
```

This automated script will:
1. Symlink `indmoney-sync` to `~/.local/bin/indmoney-sync`.
2. Configure `~/.config/user-tmpfiles.d/inir-indmoney.conf` to guarantee runtime directory creation on boot.
3. Install and activate systemd user service `inir-indmoney-sync.service` and timer `inir-indmoney-sync.timer`.
4. Link QML components into `~/.config/quickshell/inir/`.
5. Register `IndMoneyService` in `services/qmldir`.
6. Register the `portfolio` piece into `IrisPieces.qml`, `IrisBubbleFace.qml`, and `IrisCardContent.qml`.
7. Generate initial offline mock state so the widget renders immediately.

### 2. Connect Your Live Account (Optional)

To link your live IndMoney account via OAuth 2.1 PKCE:
```bash
indmoney-sync auth
```
This opens your default web browser for secure login (Mobile + OTP + MPIN). Upon approval, tokens are saved directly to your encrypted OS keyring.

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
* **Left-Click:** Morphs and expands the Island stage into `PortfolioCard.qml`.
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

## Privacy & Security Model

- **No Hardcoded Credentials:** No credentials or API secrets are stored in the codebase or git history.
- **100% Volatile RAM Storage for Financial Balances:** Active portfolio state resides exclusively in tmpfs (`/run/user/$UID/inir-indmoney/state.json`) which is destroyed on logout or shutdown. Zero plaintext balance files are saved to `~/.cache` or persistent disk.
- **Secure Encrypted Keyring:** OAuth 2.1 tokens and the persistent cold-boot state cache are stored strictly as encrypted secrets in `libsecret` (GNOME Keyring / KWallet).
- **Instant Cold-Boot Hydration:** Quickshell triggers `indmoney-sync hydrate` on boot to reconstitute state into RAM tmpfs at millisecond 0 without waiting for scheduled timers.
- **Auditable & Offline Testing:** Fully functional offline mode via `indmoney-sync mock` without requiring network access or personal data.

---

## Testing & Quality Assurance

Run the test suite:
```bash
make test
# or
pytest
```

Run code formatting and linting:
```bash
ruff check .
```

---

## Troubleshooting

- **Keyring is locked or unavailable:**
  Ensure a Secret Service daemon (such as `gnome-keyring` or `keepassxc`) is running and unlocked in your desktop session.
  ```bash
  python3 -c "import keyring; print(keyring.get_keyring())"
  ```
- **Force an immediate update:**
  ```bash
  indmoney-sync fetch --force -v
  ```
- **Inspect systemd sync timer:**
  ```bash
  systemctl --user status inir-indmoney-sync.timer
  journalctl --user -u inir-indmoney-sync.service -e
  ```

---

## License

This project is licensed under the [MIT License](LICENSE).
