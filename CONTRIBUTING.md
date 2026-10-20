# Contributing to IndMoney Portfolio Widget

Thank you for your interest in contributing to the **IndMoney Portfolio Widget for iNiR / iRiS**!

We welcome contributions of all kinds: bug reports, documentation enhancements, UI/UX polish, and feature additions.

---

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rakeshpc2809/portfolio-widget.git
   cd portfolio-widget
   ```

2. **Create and activate a virtual environment (optional, or use system python):**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

3. **Run tests:**
   ```bash
   make test
   # or
   pytest
   ```

4. **Code style & linting:**
   ```bash
   ruff check .
   ```

---

## Project Structure

```
.
├── src/
│   ├── indmoney-sync               # Entrypoint launcher script
│   └── indmoney_sync/              # Core sync engine
│       ├── auth.py                 # OAuth 2.1 PKCE authorization & keyring management
│       ├── client.py               # Streamable HTTP MCP client
│       ├── cli.py                  # CLI argument parser and commands
│       ├── governor.py             # Market-aware polling scheduler (IST & US hours)
│       ├── inspector.py            # Diagnostic schema inspector
│       ├── mock_data.py            # Synthetic offline portfolio fixtures
│       └── normalizer.py           # Data normalization & schema transformation
├── qml/
│   ├── services/
│   │   └── IndMoneyService.qml     # Quickshell singleton service (FileView watcher)
│   └── modules/iris/
│       ├── pieces/
│       │   └── PortfolioPiece.qml  # Compact Island bubble / pill
│       └── cards/
│           └── PortfolioCard.qml   # Expanded Island stage card
├── systemd/
│   ├── inir-indmoney.conf          # tmpfiles.d configuration for /run/user/$UID/inir-indmoney
│   ├── inir-indmoney-sync.service  # systemd user service
│   └── inir-indmoney-sync.timer    # systemd user timer
├── tests/
│   ├── test_governor.py            # Governor window & holiday logic tests
│   └── test_normalizer.py          # Data normalization unit tests
├── install.sh                      # One-step installer for iNiR / iRiS
├── Makefile                        # Common developer targets
└── pyproject.toml                  # Python package metadata & tool configuration
```

---

## Privacy & Security Guidelines

- **Zero Plaintext Credentials:** Never log, print, or commit auth tokens, refresh tokens, passwords, cookies, or OTPs. All tokens must strictly go through `keyring` (Secret Service / libsecret).
- **Zero Network I/O in UI Plane:** The QML components must never make network requests or read secrets directly. All communication with external services occurs exclusively through the headless CLI runner writing to non-blocking tmpfs.
- **Privacy Mode:** Any new UI components displaying balances or sensitive quantities must support the privacy toggle / Gaussian blur masking (`IndMoneyService.privacyMode`).

---

## Pull Request Process

1. Fork the repo and create a new feature branch from `master`.
2. Ensure all unit tests pass (`make test`).
3. Ensure no linting errors are reported (`ruff check .`).
4. Commit your changes with clear, descriptive commit messages adhering to Conventional Commits (e.g. `feat: ...`, `fix: ...`, `docs: ...`).
5. Open a Pull Request detailing your changes and any relevant screenshots or testing instructions.
