#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INIR_DIR="$HOME/.config/quickshell/inir"
MODE="install"

if [[ "${1:-}" == "--uninstall" ]] || [[ "${1:-}" == "-u" ]] || [[ "${1:-}" == "uninstall" ]]; then
    MODE="uninstall"
fi

# ==============================================================================
# UNINSTALL MODE
# ==============================================================================
if [[ "$MODE" == "uninstall" ]]; then
    echo "=== Uninstalling IndMoney Portfolio Widget from iNiR / iRiS ==="

    # 1. Stop & disable systemd units
    echo "[1/5] Stopping and removing systemd units..."
    systemctl --user stop inir-indmoney-sync.timer inir-indmoney-sync.service 2>/dev/null || true
    systemctl --user disable inir-indmoney-sync.timer inir-indmoney-sync.service 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/inir-indmoney-sync.service"
    rm -f "$HOME/.config/systemd/user/inir-indmoney-sync.timer"
    rm -f "$HOME/.config/user-tmpfiles.d/inir-indmoney.conf"
    systemctl --user daemon-reload 2>/dev/null || true

    # 2. Remove CLI symlink
    echo "[2/5] Removing CLI symlink..."
    rm -f "$HOME/.local/bin/indmoney-sync"

    # 3. Remove QML component symlinks
    echo "[3/5] Removing QML component symlinks..."
    rm -f "$INIR_DIR/services/IndMoneyService.qml"
    rm -f "$INIR_DIR/modules/iris/pieces/PortfolioPiece.qml"
    rm -f "$INIR_DIR/modules/iris/stage/PortfolioCard.qml"

    # 4. Clean qmldir registries
    echo "[4/5] Cleaning qmldir registries..."
    for qmldir in "$INIR_DIR/services/qmldir" "$INIR_DIR/modules/iris/pieces/qmldir" "$INIR_DIR/modules/iris/stage/qmldir"; do
        if [[ -f "$qmldir" ]]; then
            sed -i '/IndMoneyService/d' "$qmldir" 2>/dev/null || true
            sed -i '/PortfolioPiece/d' "$qmldir" 2>/dev/null || true
            sed -i '/PortfolioCard/d' "$qmldir" 2>/dev/null || true
        fi
    done

    # 5. Clean shell patches (revert to pristine state)
    echo "[5/5] Reverting iRiS shell patches..."
    python3 - << 'EOF'
import re
from pathlib import Path

inir_dir = Path.home() / ".config" / "quickshell" / "inir"

# A. Revert IrisPieces.qml
pieces_file = inir_dir / "modules" / "iris" / "pieces" / "IrisPieces.qml"
if pieces_file.exists():
    content = pieces_file.read_text(encoding="utf-8")
    content = re.sub(r'/\* INIR_INDMONEY_BEGIN:extras \*/.*?/\* INIR_INDMONEY_END:extras \*/\n?', '', content, flags=re.DOTALL)
    content = re.sub(r'/\* INIR_INDMONEY_BEGIN:glyph \*/.*?/\* INIR_INDMONEY_END:glyph \*/\n?', '', content, flags=re.DOTALL)
    # Legacy fallbacks
    lines = content.splitlines(keepends=True)
    filtered = []
    skip = False
    for line in lines:
        if '{ id: "portfolio"' in line:
            skip = True
            continue
        if skip:
            if '}' in line:
                skip = False
            continue
        if 'if (kind === "portfolio") return "account_balance_wallet"' in line:
            continue
        filtered.append(line)
    pieces_file.write_text("".join(filtered), encoding="utf-8")
    print("  -> Reverted IrisPieces.qml")

# B. Revert IrisBubbleFace.qml
bubble_file = inir_dir / "modules" / "iris" / "components" / "IrisBubbleFace.qml"
if bubble_file.exists():
    content = bubble_file.read_text(encoding="utf-8")
    content = re.sub(r'/\* INIR_INDMONEY_BEGIN:import \*/.*?/\* INIR_INDMONEY_END:import \*/\n?', '', content, flags=re.DOTALL)
    content = re.sub(r'/\* INIR_INDMONEY_BEGIN:face \*/.*?/\* INIR_INDMONEY_END:face \*/\n\n?', '', content, flags=re.DOTALL)
    content = re.sub(r'/\* INIR_INDMONEY_BEGIN:accessible \*/.*?/\* INIR_INDMONEY_END:accessible \*/', '    Accessible.name: root.kind === "controls" ? Translation.tr("Quick controls")', content, flags=re.DOTALL)
    # Legacy fallbacks
    content = re.sub(r'^\s*PortfolioPiece\s*\{\s*id:\s*portfolioPiece.*?^\s*\}\n?', '', content, flags=re.DOTALL | re.MULTILINE)
    content = re.sub(r'^\s*Item\s*\{\s*id:\s*portfolioFace.*?^\s*\}\n?', '', content, flags=re.DOTALL | re.MULTILINE)
    content = content.replace('Accessible.name: root.kind === "portfolio" ? Translation.tr("Portfolio")\n        : root.kind === "controls"', 'Accessible.name: root.kind === "controls"')
    content = content.replace('Accessible.name: root.kind === "portfolio" ? Translation.tr("Portfolio") : root.kind === "controls"', 'Accessible.name: root.kind === "controls"')
    bubble_file.write_text(content, encoding="utf-8")
    print("  -> Reverted IrisBubbleFace.qml")

# C. Revert IrisCardContent.qml
card_file = inir_dir / "modules" / "iris" / "stage" / "IrisCardContent.qml"
if card_file.exists():
    content = card_file.read_text(encoding="utf-8")
    content = re.sub(r'/\* INIR_INDMONEY_BEGIN:light \*/.*?/\* INIR_INDMONEY_END:light \*/\n?', '', content, flags=re.DOTALL)
    content = re.sub(r'/\* INIR_INDMONEY_BEGIN:card \*/.*?/\* INIR_INDMONEY_END:card \*/\n?', '', content, flags=re.DOTALL)
    content = re.sub(r'/\* INIR_INDMONEY_BEGIN:component \*/.*?/\* INIR_INDMONEY_END:component \*/\n?', '', content, flags=re.DOTALL)
    # Legacy fallbacks
    content = re.sub(r'^\s*case "portfolio": return IrisStyle\.identity\.teal\n?', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*case "portfolio": return portfolioCard\n?', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*Component\s*\{\s*id:\s*portfolioCard.*?^\s*\}\n?', '', content, flags=re.DOTALL | re.MULTILINE)
    card_file.write_text(content, encoding="utf-8")
    print("  -> Reverted IrisCardContent.qml")
EOF

    # Clean tmpfs runtime directory & cache
    rm -rf "/run/user/$(id -u)/inir-indmoney" 2>/dev/null || true
    rm -rf "$HOME/.cache/inir/indmoney" 2>/dev/null || true

    # Reload quickshell if running
    if command -v quickshell &>/dev/null && pgrep -x qs &>/dev/null; then
        quickshell ipc -c inir call dev reload 2>/dev/null || true
    fi

    echo ""
    echo "=== Uninstallation Complete! ==="
    echo "IndMoney Portfolio Widget has been completely removed from iNiR / iRiS."
    exit 0
fi

# ==============================================================================
# INSTALL MODE
# ==============================================================================
echo "=== Installing IndMoney Portfolio Widget for iNiR / iRiS ==="

# 1. Directories
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.config/user-tmpfiles.d"
mkdir -p "$HOME/.config/systemd/user"
mkdir -p "/run/user/$(id -u)/inir-indmoney"
chmod 0700 "/run/user/$(id -u)/inir-indmoney" 2>/dev/null || true
rm -rf "$HOME/.cache/inir/indmoney"

# 2. Link CLI binary
echo "[1/6] Installing indmoney-sync CLI to ~/.local/bin/..."
ln -sf "$SCRIPT_DIR/src/indmoney-sync" "$HOME/.local/bin/indmoney-sync"
chmod +x "$SCRIPT_DIR/src/indmoney-sync"

# 3. Systemd & tmpfiles
echo "[2/6] Configuring user-tmpfiles.d and systemd units..."
cp "$SCRIPT_DIR/systemd/inir-indmoney.conf" "$HOME/.config/user-tmpfiles.d/inir-indmoney.conf"
cp "$SCRIPT_DIR/systemd/inir-indmoney-sync.service" "$HOME/.config/systemd/user/inir-indmoney-sync.service"
cp "$SCRIPT_DIR/systemd/inir-indmoney-sync.timer" "$HOME/.config/systemd/user/inir-indmoney-sync.timer"

systemd-tmpfiles --user --create
systemctl --user daemon-reload
systemctl --user enable --now inir-indmoney-sync.timer

# 4. QML Components
echo "[3/6] Installing QML components..."
mkdir -p "$INIR_DIR/services"
mkdir -p "$INIR_DIR/modules/iris/pieces"
mkdir -p "$INIR_DIR/modules/iris/stage"

ln -sf "$SCRIPT_DIR/qml/services/IndMoneyService.qml" "$INIR_DIR/services/IndMoneyService.qml"
ln -sf "$SCRIPT_DIR/qml/modules/iris/pieces/PortfolioPiece.qml" "$INIR_DIR/modules/iris/pieces/PortfolioPiece.qml"
ln -sf "$SCRIPT_DIR/qml/modules/iris/cards/PortfolioCard.qml" "$INIR_DIR/modules/iris/stage/PortfolioCard.qml"

# 5. Register in qmldir files
echo "[4/6] Updating qmldir registries..."
QMLDIR="$INIR_DIR/services/qmldir"
if ! grep -q "IndMoneyService" "$QMLDIR" 2>/dev/null; then
    echo "singleton IndMoneyService 1.0 IndMoneyService.qml" >> "$QMLDIR"
fi

PIECES_QMLDIR="$INIR_DIR/modules/iris/pieces/qmldir"
if ! grep -q "PortfolioPiece" "$PIECES_QMLDIR" 2>/dev/null; then
    echo "PortfolioPiece 1.0 PortfolioPiece.qml" >> "$PIECES_QMLDIR"
fi

STAGE_QMLDIR="$INIR_DIR/modules/iris/stage/qmldir"
if ! grep -q "PortfolioCard" "$STAGE_QMLDIR" 2>/dev/null; then
    echo "PortfolioCard 1.0 PortfolioCard.qml" >> "$STAGE_QMLDIR"
fi

# 6. Patch IrisPieces.qml, IrisBubbleFace.qml, and IrisCardContent.qml using clean text markers
echo "[5/6] Patching iRiS registries (idempotent, text-marker-based)..."
python3 - << 'EOF'
import re
from pathlib import Path

inir_dir = Path.home() / ".config" / "quickshell" / "inir"

EXTRA_BLOCK = """/* INIR_INDMONEY_BEGIN:extras */
        { id: "portfolio", label: "Portfolio", description: "IndMoney net worth, P&L, allocation and holdings.", card: true,
            keywords: ["portfolio", "stocks", "mutual funds", "investments", "indmoney", "networth", "shares", "sip"] },
/* INIR_INDMONEY_END:extras */"""

GLYPH_BLOCK = """/* INIR_INDMONEY_BEGIN:glyph */
        if (kind === "portfolio") return "account_balance_wallet"
/* INIR_INDMONEY_END:glyph */"""

IMPORT_BLOCK = """/* INIR_INDMONEY_BEGIN:import */
import qs.modules.iris.pieces
/* INIR_INDMONEY_END:import */"""

FACE_BLOCK = """/* INIR_INDMONEY_BEGIN:face */
    PortfolioPiece {
        id: portfolioPiece
        visible: root.kind === "portfolio"
        anchors.centerIn: parent
        screenName: root.screenName
        plated: root.plated
        hovered: root.hovered
        pressed: root.pressed
        onActivated: root.clicked()
    }
/* INIR_INDMONEY_END:face */"""

ACCESSIBLE_BLOCK = """/* INIR_INDMONEY_BEGIN:accessible */
    Accessible.name: root.kind === "portfolio" ? Translation.tr("Portfolio")
        : root.kind === "controls" ? Translation.tr("Quick controls")
/* INIR_INDMONEY_END:accessible */"""

LIGHT_BLOCK = """/* INIR_INDMONEY_BEGIN:light */
        case "portfolio": return IrisStyle.identity.teal
/* INIR_INDMONEY_END:light */"""

CARD_BLOCK = """/* INIR_INDMONEY_BEGIN:card */
            case "portfolio": return portfolioCard
/* INIR_INDMONEY_END:card */"""

COMP_BLOCK = """/* INIR_INDMONEY_BEGIN:component */
    Component {
        id: portfolioCard
        PortfolioCard {
            Layout.fillWidth: true
        }
    }
/* INIR_INDMONEY_END:component */"""

# A. Patch IrisPieces.qml
pieces_file = inir_dir / "modules" / "iris" / "pieces" / "IrisPieces.qml"
if pieces_file.exists():
    content = pieces_file.read_text(encoding="utf-8")
    if '/* INIR_INDMONEY_BEGIN:extras */' in content:
        content = re.sub(r'/\* INIR_INDMONEY_BEGIN:extras \*/.*?/\* INIR_INDMONEY_END:extras \*/', EXTRA_BLOCK, content, flags=re.DOTALL)
    elif '{ id: "portfolio"' in content:
        lines = content.splitlines(keepends=True)
        filtered = []
        skip = False
        for line in lines:
            if '{ id: "portfolio"' in line:
                skip = True
                continue
            if skip:
                if '}' in line:
                    skip = False
                continue
            filtered.append(line)
        content = "".join(filtered)
        content = content.replace('readonly property var extras: [\n', 'readonly property var extras: [\n' + EXTRA_BLOCK + '\n', 1)
    else:
        content = content.replace('readonly property var extras: [\n', 'readonly property var extras: [\n' + EXTRA_BLOCK + '\n', 1)

    if '/* INIR_INDMONEY_BEGIN:glyph */' in content:
        content = re.sub(r'/\* INIR_INDMONEY_BEGIN:glyph \*/.*?/\* INIR_INDMONEY_END:glyph \*/', GLYPH_BLOCK, content, flags=re.DOTALL)
    elif 'kind === "portfolio"' in content and 'return "account_balance_wallet"' in content:
        lines = content.splitlines(keepends=True)
        filtered = [l for l in lines if 'if (kind === "portfolio") return "account_balance_wallet"' not in l]
        content = "".join(filtered)
        content = content.replace('function defaultGlyph(kind: string): string {\n', 'function defaultGlyph(kind: string): string {\n' + GLYPH_BLOCK + '\n', 1)
    else:
        content = content.replace('function defaultGlyph(kind: string): string {\n', 'function defaultGlyph(kind: string): string {\n' + GLYPH_BLOCK + '\n', 1)

    pieces_file.write_text(content, encoding="utf-8")
    print("  -> Patched IrisPieces.qml (marker-based)")

# B. Patch IrisBubbleFace.qml
bubble_file = inir_dir / "modules" / "iris" / "components" / "IrisBubbleFace.qml"
if bubble_file.exists():
    content = bubble_file.read_text(encoding="utf-8")
    if '/* INIR_INDMONEY_BEGIN:import */' in content:
        content = re.sub(r'/\* INIR_INDMONEY_BEGIN:import \*/.*?/\* INIR_INDMONEY_END:import \*/', IMPORT_BLOCK, content, flags=re.DOTALL)
    elif 'import qs.modules.iris.pieces' not in content:
        content = content.replace('import qs.modules.iris.style\n', 'import qs.modules.iris.style\n' + IMPORT_BLOCK + '\n', 1)

    if '/* INIR_INDMONEY_BEGIN:face */' in content:
        content = re.sub(r'/\* INIR_INDMONEY_BEGIN:face \*/.*?/\* INIR_INDMONEY_END:face \*/', FACE_BLOCK, content, flags=re.DOTALL)
    elif 'PortfolioPiece {' in content and 'id: portfolioPiece' in content:
        content = re.sub(r'^\s*PortfolioPiece\s*\{\s*id:\s*portfolioPiece.*?^\s*\}\n?', FACE_BLOCK + '\n', content, flags=re.DOTALL | re.MULTILINE)
    elif 'id: portfolioFace' in content:
        content = re.sub(r'^\s*Item\s*\{\s*id:\s*portfolioFace.*?^\s*\}\n?', FACE_BLOCK + '\n', content, flags=re.DOTALL | re.MULTILINE)
    else:
        content = content.replace('    ResourceUsageMonitor { target: root; active: root.kind === "vitals" }', FACE_BLOCK + '\n\n    ResourceUsageMonitor { target: root; active: root.kind === "vitals" }', 1)

    if '/* INIR_INDMONEY_BEGIN:accessible */' in content:
        content = re.sub(r'/\* INIR_INDMONEY_BEGIN:accessible \*/.*?/\* INIR_INDMONEY_END:accessible \*/', ACCESSIBLE_BLOCK, content, flags=re.DOTALL)
    elif 'Accessible.name: root.kind === "portfolio"' in content:
        content = re.sub(r'^\s*Accessible\.name:\s*root\.kind\s*===\s*"portfolio".*?:\s*root\.kind\s*===\s*"controls"\s*\?\s*Translation\.tr\("Quick controls"\)\n?', ACCESSIBLE_BLOCK + '\n', content, flags=re.DOTALL | re.MULTILINE)
    else:
        content = content.replace('    Accessible.name: root.kind === "controls" ? Translation.tr("Quick controls")', ACCESSIBLE_BLOCK, 1)

    bubble_file.write_text(content, encoding="utf-8")
    print("  -> Patched IrisBubbleFace.qml (marker-based)")

# C. Patch IrisCardContent.qml
card_file = inir_dir / "modules" / "iris" / "stage" / "IrisCardContent.qml"
if card_file.exists():
    content = card_file.read_text(encoding="utf-8")
    if '/* INIR_INDMONEY_BEGIN:light */' in content:
        content = re.sub(r'/\* INIR_INDMONEY_BEGIN:light \*/.*?/\* INIR_INDMONEY_END:light \*/', LIGHT_BLOCK, content, flags=re.DOTALL)
    elif 'case "portfolio": return IrisStyle.identity.teal' in content:
        content = re.sub(r'^\s*case "portfolio": return IrisStyle\.identity\.teal\n?', LIGHT_BLOCK + '\n', content, flags=re.MULTILINE)
    else:
        content = content.replace('        case "weather": return IrisStyle.skyLight', LIGHT_BLOCK + '\n        case "weather": return IrisStyle.skyLight', 1)

    if '/* INIR_INDMONEY_BEGIN:card */' in content:
        content = re.sub(r'/\* INIR_INDMONEY_BEGIN:card \*/.*?/\* INIR_INDMONEY_END:card \*/', CARD_BLOCK, content, flags=re.DOTALL)
    elif 'case "portfolio": return portfolioCard' in content:
        content = re.sub(r'^\s*case "portfolio": return portfolioCard\n?', CARD_BLOCK + '\n', content, flags=re.MULTILINE)
    else:
        content = content.replace('            case "weather": return weatherCard', CARD_BLOCK + '\n            case "weather": return weatherCard', 1)

    if '/* INIR_INDMONEY_BEGIN:component */' in content:
        content = re.sub(r'/\* INIR_INDMONEY_BEGIN:component \*/.*?/\* INIR_INDMONEY_END:component \*/', COMP_BLOCK, content, flags=re.DOTALL)
    elif 'id: portfolioCard' in content:
        content = re.sub(r'^\s*Component\s*\{\s*id:\s*portfolioCard.*?^\s*\}\n?', COMP_BLOCK + '\n', content, flags=re.DOTALL | re.MULTILINE)
    else:
        content = content.replace('    Component {\n        id: weatherCard', COMP_BLOCK + '\n    Component {\n        id: weatherCard', 1)

    card_file.write_text(content, encoding="utf-8")
    print("  -> Patched IrisCardContent.qml (marker-based)")
EOF

# 7. Generate Initial Mock State
echo "[6/6] Populating initial state..."
"$HOME/.local/bin/indmoney-sync" mock

# 8. Reload quickshell if running
if command -v quickshell &>/dev/null && pgrep -x qs &>/dev/null; then
    quickshell ipc -c inir call dev reload 2>/dev/null || true
fi

echo ""
echo "=== Installation Complete! ==="
echo "The IndMoney Portfolio Piece is now installed in iNiR / iRiS."
echo "You can add it to your Island or Frame in iNiR Settings -> Bar -> Bubbles in the Island."
echo "To link your live IndMoney account, run:"
echo "    indmoney-sync auth"
