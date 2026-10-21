#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INIR_DIR="$HOME/.config/quickshell/inir"

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
if ! grep -q "IndMoneyService" "$QMLDIR"; then
    echo "singleton IndMoneyService 1.0 IndMoneyService.qml" >> "$QMLDIR"
fi

PIECES_QMLDIR="$INIR_DIR/modules/iris/pieces/qmldir"
if ! grep -q "PortfolioPiece" "$PIECES_QMLDIR"; then
    echo "PortfolioPiece 1.0 PortfolioPiece.qml" >> "$PIECES_QMLDIR"
fi

STAGE_QMLDIR="$INIR_DIR/modules/iris/stage/qmldir"
if ! grep -q "PortfolioCard" "$STAGE_QMLDIR"; then
    echo "PortfolioCard 1.0 PortfolioCard.qml" >> "$STAGE_QMLDIR"
fi

# 6. Patch IrisPieces.qml, IrisBubbleFace.qml, and IrisCardContent.qml
echo "[5/6] Patching iRiS registries..."
python3 - << 'EOF'
import re
from pathlib import Path

inir_dir = Path.home() / ".config" / "quickshell" / "inir"

# A. Patch IrisPieces.qml
pieces_file = inir_dir / "modules" / "iris" / "pieces" / "IrisPieces.qml"
if pieces_file.exists():
    content = pieces_file.read_text(encoding="utf-8")
    if '"portfolio"' not in content:
        # Add to extras
        portfolio_extra = '        { id: "portfolio", label: "Portfolio", description: "IndMoney net worth, P&L, allocation and holdings.", card: true,\n            keywords: ["portfolio", "stocks", "mutual funds", "investments", "indmoney", "networth", "shares", "sip"] },\n'
        content = content.replace('readonly property var extras: [\n', 'readonly property var extras: [\n' + portfolio_extra, 1)
        # Add to defaultGlyph
        content = content.replace('function defaultGlyph(kind: string): string {\n', 'function defaultGlyph(kind: string): string {\n        if (kind === "portfolio") return "account_balance_wallet"\n', 1)
        pieces_file.write_text(content, encoding="utf-8")
        print("  -> Patched IrisPieces.qml (added portfolio extra & defaultGlyph)")
    else:
        print("  -> IrisPieces.qml already contains portfolio")

# B. Patch IrisBubbleFace.qml
bubble_file = inir_dir / "modules" / "iris" / "components" / "IrisBubbleFace.qml"
if bubble_file.exists():
    content = bubble_file.read_text(encoding="utf-8")
    if 'PortfolioPiece' not in content:
        portfolio_comp = '''PortfolioPiece {
            id: portfolioPiece
            visible: root.kind === "portfolio"
            anchors.centerIn: parent
            screenName: root.screenName
            plated: root.plated
            hovered: root.hovered
            pressed: root.pressed
            onActivated: root.clicked()
        }'''
        if 'id: portfolioFace' in content:
            content = re.sub(r'Item\s*\{\s*id:\s*portfolioFace.*?^\s*\}', portfolio_comp, content, flags=re.DOTALL | re.MULTILINE)
        else:
            content = re.sub(r'(ResourceUsageMonitor\s*\{)', '        ' + portfolio_comp + '\n' + r'\1', content, count=1)
        if 'import qs.modules.iris.pieces' not in content:
            content = "import qs.modules.iris.pieces\n" + content
        if 'Accessible.name: root.kind === "portfolio"' not in content:
            content = content.replace('Accessible.name: root.kind === "controls"', 'Accessible.name: root.kind === "portfolio" ? Translation.tr("Portfolio")\n        : root.kind === "controls"')
        bubble_file.write_text(content, encoding="utf-8")
        print("  -> Patched IrisBubbleFace.qml (added PortfolioPiece)")
    else:
        print("  -> IrisBubbleFace.qml already contains PortfolioPiece")

# C. Patch IrisCardContent.qml
card_file = inir_dir / "modules" / "iris" / "stage" / "IrisCardContent.qml"
if card_file.exists():
    content = card_file.read_text(encoding="utf-8")
    if 'case "portfolio":' not in content:
        # Add to light color switch
        content = content.replace('case "weather": return IrisStyle.skyLight', 'case "portfolio": return IrisStyle.identity.teal\n        case "weather": return IrisStyle.skyLight', 1)
        # Add to sourceComponent switch
        content = content.replace('case "weather": return weatherCard', 'case "portfolio": return portfolioCard\n            case "weather": return weatherCard', 1)
        # Add Component definition
        comp_def = '''    Component {
        id: portfolioCard
        PortfolioCard {
            Layout.fillWidth: true
        }
    }
'''
        content = content.replace('    Component {\n        id: weatherCard', comp_def + '    Component {\n        id: weatherCard', 1)
        card_file.write_text(content, encoding="utf-8")
        print("  -> Patched IrisCardContent.qml (added portfolio card loader)")
    else:
        print("  -> IrisCardContent.qml already contains portfolio card")
EOF

# 7. Generate Initial Mock State
echo "[6/6] Populating initial state..."
"$HOME/.local/bin/indmoney-sync" mock

echo ""
echo "=== Installation Complete! ==="
echo "The IndMoney Portfolio Piece is now installed in iNiR / iRiS."
echo "You can add it to your Island or Frame in iNiR Settings -> Bar -> Bubbles in the Island."
echo "To link your live IndMoney account, run:"
echo "    indmoney-sync auth"
