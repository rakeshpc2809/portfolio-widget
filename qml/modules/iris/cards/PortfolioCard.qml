pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import QtQuick.Shapes
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.iris.style
import qs.modules.iris.components
import qs.modules.iris.stage

ColumnLayout {
    id: root

    readonly property real d: IrisStyle.density
    readonly property var summary: IndMoneyService.summary ?? ({})
    readonly property real portfolioVal: summary.total_portfolio_inr ?? summary.total_networth_inr ?? 0
    readonly property real networth: summary.total_networth_inr ?? 0
    readonly property real bankVal: summary.bank_inr ?? 0
    readonly property real epfVal: summary.epf_inr ?? 0
    readonly property real invested: summary.invested_inr ?? 0
    readonly property real totalPnl: summary.total_pnl_inr ?? 0
    readonly property real totalPnlPct: summary.total_pnl_pct ?? 0
    readonly property real dayInr: summary.day_change_inr ?? 0
    readonly property real dayPct: summary.day_change_pct ?? 0
    readonly property bool isDayGain: dayPct >= 0
    readonly property bool isTotalGain: totalPnl >= 0

    // Theme-resilient contrast tokens using dynamic IrisStyle palette
    readonly property color fgMain: IrisStyle.light ? IrisStyle.text : (root.isDarkHex(IrisStyle.text) ? IrisStyle.inkOnDark : IrisStyle.text)
    readonly property color fgMuted: IrisStyle.subtext
    readonly property color rowBg: IrisStyle.fillSecondary
    readonly property color rowBgHover: IrisStyle.fillHover

    function isDarkHex(c: color): bool {
        return (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) < 0.4
    }

    // Dynamic asset class color mapping using IrisStyle.identity tokens
    function getAssetColor(assetName: string): color {
        const name = (assetName || "").toLowerCase()
        if (name.includes("mutual") || name.includes("mf")) return IrisStyle.identity.indigo || IrisStyle.accent
        if (name.includes("us")) return IrisStyle.identity.magenta || IrisStyle.identity.teal
        if (name.includes("indian") || name.includes("in_eq") || name.includes("stock") || name.includes("equity")) return IrisStyle.identity.sky
        if (name.includes("fixed") || name.includes("fd") || name.includes("deposit") || name.includes("gold")) return IrisStyle.identity.amber
        if (name.includes("epf") || name.includes("retirement")) return IrisStyle.identity.orange
        return IrisStyle.identity.teal
    }

    property int activeTab: 0 // 0: Top Movers, 1: Holdings, 2: SIPs
    property string holdingFilter: "ALL" // "ALL", "MF", "IN_EQ", "US_EQ"
    property string topMoversSort: "PCT" // "PCT" or "INR"
    property var hoveredAlloc: null

    spacing: Math.round(10 * root.d)
    Layout.fillWidth: true
    focus: true

    // --- Keyboard-First Navigation ---
    Keys.onPressed: event => {
        if (event.key === Qt.Key_1) {
            root.activeTab = 0
            event.accepted = true
        } else if (event.key === Qt.Key_2) {
            root.activeTab = 1
            event.accepted = true
        } else if (event.key === Qt.Key_3) {
            root.activeTab = 2
            event.accepted = true
        } else if (event.key === Qt.Key_Tab) {
            const filters = ["ALL", "MF", "IN_EQ", "US_EQ"]
            const idx = filters.indexOf(root.holdingFilter)
            const nextIdx = (idx + 1) % filters.length
            root.holdingFilter = filters[nextIdx]
            event.accepted = true
        } else if (event.key === Qt.Key_P) {
            IndMoneyService.togglePrivacy()
            event.accepted = true
        } else if (event.key === Qt.Key_R) {
            IndMoneyService.refresh()
            event.accepted = true
        }
    }

    // Sorted Top Movers by % Change or ₹ Impact
    readonly property var sortedTopMovers: {
        const list = (IndMoneyService.topMovers || []).slice()
        if (root.topMoversSort === "INR") {
            return list.sort((a, b) => Math.abs(b.day_change_inr ?? 0) - Math.abs(a.day_change_inr ?? 0))
        } else {
            return list.sort((a, b) => Math.abs(b.day_pct ?? 0) - Math.abs(a.day_pct ?? 0))
        }
    }

    // Helper to calculate polyline points for sparkline shape
    function generateSparklinePoints(pts: var, w: real, h: real): var {
        if (!pts || pts.length < 2) return { line: [], fill: [] }
        let minVal = pts[0].v
        let maxVal = pts[0].v
        for (let i = 1; i < pts.length; i++) {
            if (pts[i].v < minVal) minVal = pts[i].v
            if (pts[i].v > maxVal) maxVal = pts[i].v
        }
        let range = maxVal - minVal
        if (range <= 0.001) range = 1.0

        const padTop = h * 0.18
        const padBottom = h * 0.12
        const availH = h - padTop - padBottom

        const linePoints = []
        const fillPoints = []
        const stepX = w / (pts.length - 1)

        fillPoints.push(Qt.point(0, h))

        for (let i = 0; i < pts.length; i++) {
            const x = i * stepX
            const normalized = (pts[i].v - minVal) / range
            const y = padTop + availH * (1.0 - normalized)
            const pt = Qt.point(x, y)
            linePoints.push(pt)
            fillPoints.push(pt)
        }

        fillPoints.push(Qt.point(w, h))
        return { line: linePoints, fill: fillPoints }
    }

    // --- Header ---
    CardHeader {
        glyph: "account_balance_wallet"
        tint: IrisStyle.identity.teal
        title: Translation.tr("Portfolio")
        detail: {
            if (IndMoneyService.status === "auth_required") return Translation.tr("Authentication required")
            if (IndMoneyService.marketState === "IN_OPEN") return Translation.tr("NSE / BSE Open")
            if (IndMoneyService.marketState === "US_OPEN") return Translation.tr("US Markets Open")
            if (IndMoneyService.marketState === "CACHED") return Translation.tr("Cached State")
            return Translation.tr("Markets Closed")
        }

        IrisIconButton {
            materialIcon: IndMoneyService.privacyMode ? "visibility_off" : "visibility"
            Accessible.name: Translation.tr("Toggle Privacy")
            onClicked: IndMoneyService.togglePrivacy()
        }

        IrisIconButton {
            id: refreshBtn
            materialIcon: "refresh"
            Accessible.name: Translation.tr("Refresh Portfolio")
            enabled: !IndMoneyService.syncing
            onClicked: IndMoneyService.refresh()

            RotationAnimation on rotation {
                running: IndMoneyService.syncing && root.visible
                loops: Animation.Infinite
                from: 0
                to: 360
                duration: 900
            }
        }
    }

    // --- Auth Required Banner ---
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: Math.round(72 * root.d)
        radius: IrisStyle.radiusTile
        color: root.rowBg
        border.width: 1
        border.color: IrisStyle.hairline
        visible: IndMoneyService.status === "auth_required"

        ColumnLayout {
            anchors.centerIn: parent
            spacing: Math.round(8 * root.d)

            Text {
                text: Translation.tr("IndMoney session expired or not connected")
                font.pixelSize: IrisStyle.typeMeta
                color: root.fgMuted
                Layout.alignment: Qt.AlignHCenter
            }

            IrisButton {
                text: Translation.tr("Connect IndMoney")
                emphasized: true
                Layout.alignment: Qt.AlignHCenter
                onClicked: IndMoneyService.reauthenticate()
            }
        }
    }

    // --- Main Portfolio Body ---
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(10 * root.d)
        visible: IndMoneyService.status !== "auth_required"

        // --- Investment Portfolio Hero Platter with Intraday Sparkline ---
        Rectangle {
            id: heroPlatter
            Layout.fillWidth: true
            implicitHeight: heroCol.implicitHeight + Math.round(22 * root.d)
            radius: IrisStyle.radiusTile
            color: root.rowBg
            clip: true

            // Intraday Net-Worth Background Sparkline
            Item {
                id: sparklineArea
                anchors.fill: parent
                opacity: IndMoneyService.privacyMode ? 0.0 : 0.85
                visible: opacity > 0.01 && IndMoneyService.sparkline && IndMoneyService.sparkline.length > 1

                Behavior on opacity {
                    NumberAnimation {
                        duration: 180
                        easing.type: Easing.InOutCubic
                    }
                }

                readonly property var pathData: root.generateSparklinePoints(
                    IndMoneyService.sparkline,
                    sparklineArea.width,
                    sparklineArea.height
                )

                Shape {
                    anchors.fill: parent
                    layer.enabled: true
                    layer.samples: 4
                    asynchronous: false

                    // Gradient Fill Beneath Line
                    ShapePath {
                        strokeColor: "transparent"
                        fillGradient: LinearGradient {
                            x1: 0; y1: 0
                            x2: 0; y2: sparklineArea.height
                            GradientStop {
                                position: 0.0
                                color: Qt.alpha(root.isDayGain ? IrisStyle.identity.green : IrisStyle.identity.red, 0.20)
                            }
                            GradientStop {
                                position: 1.0
                                color: Qt.alpha(root.isDayGain ? IrisStyle.identity.green : IrisStyle.identity.red, 0.0)
                            }
                        }
                        PathPolyline {
                            path: sparklineArea.pathData.fill
                        }
                    }

                    // Stroke Curve
                    ShapePath {
                        strokeWidth: 1.5
                        strokeColor: root.isDayGain ? IrisStyle.identity.green : IrisStyle.identity.red
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        PathPolyline {
                            path: sparklineArea.pathData.line
                        }
                    }
                }
            }

            ColumnLayout {
                id: heroCol
                anchors.fill: parent
                anchors.margins: Math.round(12 * root.d)
                spacing: Math.round(6 * root.d)

                // Row: Investments Label & 1D Badge
                RowLayout {
                    Layout.fillWidth: true

                    Item {
                        implicitWidth: rawHeroNetworth.implicitWidth
                        implicitHeight: rawHeroNetworth.implicitHeight
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            id: rawHeroNetworth
                            text: IndMoneyService.formatInrFull(root.portfolioVal, false)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(22 * root.d)
                            font.weight: IrisStyle.weight(Font.Bold)
                            font.features: ({ "tnum": 1 })
                            color: root.fgMain
                            visible: !IndMoneyService.privacyMode
                        }

                        Text {
                            anchors.fill: parent
                            text: "₹••••••••"
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(22 * root.d)
                            font.weight: IrisStyle.weight(Font.Bold)
                            font.features: ({ "tnum": 1 })
                            color: root.fgMuted
                            visible: IndMoneyService.privacyMode
                        }

                        MultiEffect {
                            source: rawHeroNetworth
                            anchors.fill: rawHeroNetworth
                            blurEnabled: true
                            blur: IndMoneyService.privacyMode ? 1.0 : 0.0
                            opacity: IndMoneyService.privacyMode ? 0.2 : 1.0
                            visible: IndMoneyService.privacyMode
                            Behavior on blur { NumberAnimation { duration: 180; easing.type: Easing.InOutCubic } }
                            Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.InOutCubic } }
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // 1D Return Pill
                    Rectangle {
                        implicitWidth: dayRow.implicitWidth + Math.round(10 * root.d)
                        implicitHeight: Math.round(22 * root.d)
                        radius: height / 2
                        color: root.isDayGain ? Qt.alpha(IrisStyle.identity.green, 0.15) : Qt.alpha(IrisStyle.identity.red, 0.15)

                        RowLayout {
                            id: dayRow
                            anchors.centerIn: parent
                            spacing: Math.round(2 * root.d)

                            MaterialSymbol {
                                text: root.isDayGain ? "arrow_drop_up" : "arrow_drop_down"
                                iconSize: Math.round(15 * root.d)
                                color: root.isDayGain ? IrisStyle.identity.green : IrisStyle.identity.red
                            }

                            Text {
                                text: (root.isDayGain ? "+" : "") + IndMoneyService.formatInrCompact(root.dayInr, IndMoneyService.privacyMode) + " (" + IndMoneyService.formatPct(root.dayPct) + ")"
                                font.family: IrisStyle.fontNumbers
                                font.pixelSize: Math.round(10.5 * root.d)
                                font.weight: IrisStyle.weight(Font.DemiBold)
                                font.features: ({ "tnum": 1 })
                                color: root.isDayGain ? IrisStyle.identity.green : IrisStyle.identity.red
                            }
                        }
                    }
                }

                // Subtitle Row: Invested vs Overall Returns
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Math.round(6 * root.d)

                    Text {
                        text: Translation.tr("Invested: %1").arg(IndMoneyService.formatInrCompact(root.invested, IndMoneyService.privacyMode))
                        font.pixelSize: IrisStyle.typeMeta
                        color: root.fgMuted
                    }

                    Text {
                        text: "·"
                        font.pixelSize: IrisStyle.typeMeta
                        color: root.fgMuted
                    }

                    Text {
                        text: Translation.tr("Overall: %1%2 (%3)").arg(root.isTotalGain ? "+" : "").arg(IndMoneyService.formatInrCompact(root.totalPnl, IndMoneyService.privacyMode)).arg(IndMoneyService.formatPct(root.totalPnlPct))
                        font.pixelSize: IrisStyle.typeMeta
                        color: root.isTotalGain ? IrisStyle.identity.green : IrisStyle.identity.red
                        font.weight: IrisStyle.weight(Font.Medium)
                    }
                }
            }
        }

        // --- Bank & Other Assets Split Chips ---
        RowLayout {
            Layout.fillWidth: true
            spacing: Math.round(6 * root.d)
            visible: root.bankVal > 0 || root.epfVal > 0

            // Bank Account Chip
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.round(38 * root.d)
                radius: IrisStyle.radiusTile
                color: root.rowBg

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Math.round(8 * root.d)
                    anchors.rightMargin: Math.round(8 * root.d)
                    spacing: Math.round(6 * root.d)

                    MaterialSymbol {
                        text: "account_balance"
                        iconSize: Math.round(14 * root.d)
                        color: IrisStyle.identity.sky
                        Layout.alignment: Qt.AlignVCenter
                    }

                    ColumnLayout {
                        spacing: 0
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            text: Translation.tr("Bank")
                            font.pixelSize: IrisStyle.typeFootnote
                            color: root.fgMuted
                            elide: Text.ElideRight
                        }

                        Text {
                            text: IndMoneyService.formatInrCompact(root.bankVal, IndMoneyService.privacyMode)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(11 * root.d)
                            font.weight: IrisStyle.weight(Font.DemiBold)
                            font.features: ({ "tnum": 1 })
                            color: root.fgMain
                        }
                    }
                }
            }

            // EPF Chip
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.round(38 * root.d)
                radius: IrisStyle.radiusTile
                color: root.rowBg

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Math.round(8 * root.d)
                    anchors.rightMargin: Math.round(8 * root.d)
                    spacing: Math.round(6 * root.d)

                    MaterialSymbol {
                        text: "savings"
                        iconSize: Math.round(14 * root.d)
                        color: IrisStyle.identity.orange
                        Layout.alignment: Qt.AlignVCenter
                    }

                    ColumnLayout {
                        spacing: 0
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            text: Translation.tr("EPF")
                            font.pixelSize: IrisStyle.typeFootnote
                            color: root.fgMuted
                            elide: Text.ElideRight
                        }

                        Text {
                            text: IndMoneyService.formatInrCompact(root.epfVal, IndMoneyService.privacyMode)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(11 * root.d)
                            font.weight: IrisStyle.weight(Font.DemiBold)
                            font.features: ({ "tnum": 1 })
                            color: root.fgMain
                        }
                    }
                }
            }

            // Net Worth Chip
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.round(38 * root.d)
                radius: IrisStyle.radiusTile
                color: root.rowBg

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Math.round(8 * root.d)
                    anchors.rightMargin: Math.round(8 * root.d)
                    spacing: Math.round(6 * root.d)

                    MaterialSymbol {
                        text: "pie_chart"
                        iconSize: Math.round(14 * root.d)
                        color: IrisStyle.identity.teal
                        Layout.alignment: Qt.AlignVCenter
                    }

                    ColumnLayout {
                        spacing: 0
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            text: Translation.tr("Total Net")
                            font.pixelSize: IrisStyle.typeFootnote
                            color: root.fgMuted
                            elide: Text.ElideRight
                        }

                        Text {
                            text: IndMoneyService.formatInrCompact(root.networth, IndMoneyService.privacyMode)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(11 * root.d)
                            font.weight: IrisStyle.weight(Font.DemiBold)
                            font.features: ({ "tnum": 1 })
                            color: root.fgMain
                        }
                    }
                }
            }
        }

        // --- Proportional Asset Allocation Bar ---
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Math.round(4 * root.d)

            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: root.hoveredAlloc
                        ? (root.hoveredAlloc.asset + ": " + IndMoneyService.formatInrCompact(root.hoveredAlloc.value_inr, IndMoneyService.privacyMode) + " (" + root.hoveredAlloc.weight_pct + "%)")
                        : Translation.tr("Asset Allocation")
                    font.pixelSize: IrisStyle.typeMeta
                    color: root.hoveredAlloc ? IrisStyle.identity.teal : root.fgMuted
                }
            }

            Row {
                id: allocBar
                Layout.fillWidth: true
                height: Math.round(7 * root.d)
                spacing: 2

                Repeater {
                    model: IndMoneyService.allocation

                    Rectangle {
                        id: segRect
                        required property var modelData
                        width: Math.max(3, (allocBar.width - ((IndMoneyService.allocation.length - 1) * 2)) * (modelData.weight_pct / 100.0))
                        height: segMouse.containsMouse ? Math.round(9 * root.d) : Math.round(5 * root.d)
                        radius: 2.5
                        color: root.getAssetColor(modelData.asset)

                        Behavior on height {
                            SpringAnimation {
                                spring: 3.5
                                damping: 0.35
                            }
                        }

                        MouseArea {
                            id: segMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            onEntered: root.hoveredAlloc = segRect.modelData
                            onExited: {
                                if (root.hoveredAlloc === segRect.modelData) root.hoveredAlloc = null
                            }
                        }
                    }
                }
            }
        }

        // --- Native iRiS Segmented Tab Navigation ---
        IrisSegmented {
            Layout.fillWidth: true
            options: [
                { value: 0, label: "Top Movers" },
                { value: 1, label: "Holdings (" + IndMoneyService.holdings.length + ")" },
                { value: 2, label: "SIPs (" + (IndMoneyService.sips.active_count ?? 0) + ")" }
            ]
            current: root.activeTab
            onPicked: val => root.activeTab = val
        }

        // --- Tab 0: Top Movers ---
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Math.round(4 * root.d)
            visible: root.activeTab === 0

            // Header Row with Sort Attribution Pill
            RowLayout {
                Layout.fillWidth: true
                spacing: Math.round(6 * root.d)

                Text {
                    text: Translation.tr("Daily Leaders")
                    font.pixelSize: IrisStyle.typeMeta
                    color: root.fgMuted
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    implicitWidth: sortRow.implicitWidth + Math.round(10 * root.d)
                    implicitHeight: Math.round(20 * root.d)
                    radius: height / 2
                    color: sortMouse.containsMouse ? IrisStyle.fillHover : root.rowBg

                    RowLayout {
                        id: sortRow
                        anchors.centerIn: parent
                        spacing: Math.round(3 * root.d)

                        MaterialSymbol {
                            text: "sort"
                            iconSize: Math.round(11 * root.d)
                            color: IrisStyle.identity.teal
                        }

                        Text {
                            text: root.topMoversSort === "PCT" ? Translation.tr("Sort: % Change") : Translation.tr("Sort: ₹ Impact")
                            font.pixelSize: Math.round(9.5 * root.d)
                            font.weight: IrisStyle.weight(Font.Medium)
                            color: IrisStyle.identity.teal
                        }
                    }

                    MouseArea {
                        id: sortMouse
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        hoverEnabled: true
                        onClicked: root.topMoversSort = (root.topMoversSort === "PCT" ? "INR" : "PCT")
                    }
                }
            }

            Repeater {
                model: root.sortedTopMovers

                Rectangle {
                    id: moverRow
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: Math.round(38 * root.d)
                    radius: IrisStyle.radiusTile
                    color: rowMouse.containsMouse ? root.rowBgHover : root.rowBg

                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Math.round(10 * root.d)
                        anchors.rightMargin: Math.round(10 * root.d)
                        spacing: Math.round(8 * root.d)

                        ColumnLayout {
                            spacing: 1
                            Layout.fillWidth: true

                            Text {
                                text: moverRow.modelData.name
                                font.pixelSize: IrisStyle.typeLabel
                                font.weight: IrisStyle.weight(Font.Medium)
                                color: root.fgMain
                                elide: Text.ElideRight
                                Layout.maximumWidth: Math.round(180 * root.d)
                            }

                            Text {
                                text: moverRow.modelData.asset + " · " + IndMoneyService.formatInrCompact(moverRow.modelData.value_inr, IndMoneyService.privacyMode)
                                font.pixelSize: IrisStyle.typeFootnote
                                color: root.fgMuted
                            }
                        }

                        // Attribution Chip with both Rupee Impact and Percentage Change
                        Rectangle {
                            implicitWidth: moverBadgeText.implicitWidth + Math.round(10 * root.d)
                            implicitHeight: Math.round(20 * root.d)
                            radius: 3
                            color: moverRow.modelData.day_pct >= 0 ? Qt.alpha(IrisStyle.identity.green, 0.15) : Qt.alpha(IrisStyle.identity.red, 0.15)

                            Text {
                                id: moverBadgeText
                                anchors.centerIn: parent
                                text: (moverRow.modelData.day_change_inr >= 0 ? "+" : "") + IndMoneyService.formatInrCompact(moverRow.modelData.day_change_inr, IndMoneyService.privacyMode) + " · " + IndMoneyService.formatPct(moverRow.modelData.day_pct)
                                font.family: IrisStyle.fontNumbers
                                font.pixelSize: Math.round(9.5 * root.d)
                                font.weight: IrisStyle.weight(Font.Bold)
                                font.features: ({ "tnum": 1 })
                                color: moverRow.modelData.day_pct >= 0 ? IrisStyle.identity.green : IrisStyle.identity.red
                            }
                        }
                    }
                }
            }
        }

        // --- Tab 1: All Holdings ---
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Math.round(4 * root.d)
            visible: root.activeTab === 1

            // Category Filter Pills (Cycleable via Tab key)
            RowLayout {
                Layout.fillWidth: true
                spacing: Math.round(6 * root.d)

                Repeater {
                    model: [
                        { label: "All", filter: "ALL" },
                        { label: "Mutual Funds", filter: "MF" },
                        { label: "Indian Stocks", filter: "IN_EQ" },
                        { label: "US Stocks", filter: "US_EQ" }
                    ]

                    Rectangle {
                        required property var modelData
                        implicitWidth: filterText.implicitWidth + Math.round(12 * root.d)
                        implicitHeight: Math.round(20 * root.d)
                        radius: height / 2
                        color: root.holdingFilter === modelData.filter ? IrisStyle.identity.teal : root.rowBg

                        Text {
                            id: filterText
                            anchors.centerIn: parent
                            text: parent.modelData.label
                            font.pixelSize: Math.round(9.5 * root.d)
                            font.weight: IrisStyle.weight(Font.Medium)
                            color: root.holdingFilter === parent.modelData.filter ? IrisStyle.onTint : root.fgMuted
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.holdingFilter = parent.modelData.filter
                        }
                    }
                }
            }

            // Holdings List
            ListView {
                Layout.fillWidth: true
                implicitHeight: Math.min(220 * root.d, contentHeight)
                clip: true
                spacing: Math.round(3 * root.d)

                model: IndMoneyService.holdings.filter(h => {
                    if (root.holdingFilter === "ALL") return true
                    return h.asset === root.holdingFilter
                })

                delegate: Rectangle {
                    id: hRow
                    required property var modelData
                    width: ListView.view.width
                    implicitHeight: Math.round(38 * root.d)
                    radius: IrisStyle.radiusTile
                    color: hMouse.containsMouse ? root.rowBgHover : root.rowBg

                    MouseArea {
                        id: hMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Math.round(10 * root.d)
                        anchors.rightMargin: Math.round(10 * root.d)
                        spacing: Math.round(8 * root.d)

                        ColumnLayout {
                            spacing: 1
                            Layout.fillWidth: true

                            Text {
                                text: hRow.modelData.name
                                font.pixelSize: IrisStyle.typeLabel
                                font.weight: IrisStyle.weight(Font.Medium)
                                color: root.fgMain
                                elide: Text.ElideRight
                                Layout.maximumWidth: Math.round(180 * root.d)
                            }

                            Text {
                                text: Translation.tr("Invested: %1").arg(IndMoneyService.formatInrCompact(hRow.modelData.invested_inr, IndMoneyService.privacyMode))
                                font.pixelSize: IrisStyle.typeFootnote
                                color: root.fgMuted
                            }
                        }

                        ColumnLayout {
                            spacing: 1
                            Layout.alignment: Qt.AlignRight

                            Text {
                                text: IndMoneyService.formatInrCompact(hRow.modelData.value_inr, IndMoneyService.privacyMode)
                                font.family: IrisStyle.fontNumbers
                                font.pixelSize: Math.round(11 * root.d)
                                font.weight: IrisStyle.weight(Font.Bold)
                                font.features: ({ "tnum": 1 })
                                color: root.fgMain
                                Layout.alignment: Qt.AlignRight
                            }

                            Text {
                                text: IndMoneyService.formatPct(hRow.modelData.total_pct)
                                font.family: IrisStyle.fontNumbers
                                font.pixelSize: Math.round(9.5 * root.d)
                                font.features: ({ "tnum": 1 })
                                color: hRow.modelData.total_pct >= 0 ? IrisStyle.identity.green : IrisStyle.identity.red
                                Layout.alignment: Qt.AlignRight
                            }
                        }
                    }
                }
            }
        }

        // --- Tab 2: SIPs ---
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Math.round(6 * root.d)
            visible: root.activeTab === 2

            // Monthly Total Card with Liquidity Coverage Badge
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.round(48 * root.d)
                radius: IrisStyle.radiusTile
                color: root.rowBg

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Math.round(10 * root.d)

                    ColumnLayout {
                        spacing: 0
                        Text {
                            text: Translation.tr("Monthly Commitment")
                            font.pixelSize: IrisStyle.typeFootnote
                            color: root.fgMuted
                        }
                        Text {
                            text: IndMoneyService.formatInrCompact(IndMoneyService.sips.monthly_total_inr ?? 0, IndMoneyService.privacyMode) + "/month"
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(13 * root.d)
                            font.weight: IrisStyle.weight(Font.Bold)
                            font.features: ({ "tnum": 1 })
                            color: IrisStyle.identity.teal
                        }
                    }

                    Item { Layout.fillWidth: true }

                    ColumnLayout {
                        spacing: Math.round(2 * root.d)
                        Layout.alignment: Qt.AlignRight

                        Text {
                            text: Translation.tr("%1 Active SIPs").arg(IndMoneyService.sips.active_count ?? 0)
                            font.pixelSize: IrisStyle.typeLabel
                            font.weight: IrisStyle.weight(Font.Medium)
                            color: root.fgMain
                            Layout.alignment: Qt.AlignRight
                        }

                        // 7-Day Liquidity Coverage Badge
                        Rectangle {
                            readonly property bool hasUpcoming: (IndMoneyService.sips.next_7d_sip_inr ?? 0) > 0
                            readonly property bool covered: IndMoneyService.sips.sip_coverage_ok ?? true
                            visible: hasUpcoming
                            implicitWidth: covRow.implicitWidth + Math.round(8 * root.d)
                            implicitHeight: Math.round(18 * root.d)
                            radius: height / 2
                            color: covered ? Qt.alpha(IrisStyle.identity.green, 0.15) : Qt.alpha(IrisStyle.identity.orange, 0.15)
                            Layout.alignment: Qt.AlignRight

                            RowLayout {
                                id: covRow
                                anchors.centerIn: parent
                                spacing: Math.round(3 * root.d)

                                MaterialSymbol {
                                    text: parent.parent.covered ? "check_circle" : "warning"
                                    iconSize: Math.round(11 * root.d)
                                    color: parent.parent.covered ? IrisStyle.identity.green : IrisStyle.identity.orange
                                }

                                Text {
                                    text: parent.parent.covered ? Translation.tr("7D Covered") : Translation.tr("Low Bank Buffer")
                                    font.pixelSize: Math.round(9 * root.d)
                                    font.weight: IrisStyle.weight(Font.DemiBold)
                                    color: parent.parent.covered ? IrisStyle.identity.green : IrisStyle.identity.orange
                                }
                            }
                        }
                    }
                }
            }

            // Upcoming SIP list
            ListView {
                Layout.fillWidth: true
                implicitHeight: Math.min(180 * root.d, contentHeight)
                clip: true
                spacing: Math.round(3 * root.d)

                model: IndMoneyService.sips.upcoming ?? []

                delegate: Rectangle {
                    id: sipRow
                    required property var modelData
                    width: ListView.view.width
                    implicitHeight: Math.round(36 * root.d)
                    radius: IrisStyle.radiusTile
                    color: sipMouse.containsMouse ? root.rowBgHover : root.rowBg

                    MouseArea {
                        id: sipMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Math.round(10 * root.d)
                        anchors.rightMargin: Math.round(10 * root.d)
                        spacing: Math.round(8 * root.d)

                        // Date Pill
                        Rectangle {
                            implicitWidth: Math.round(42 * root.d)
                            implicitHeight: Math.round(18 * root.d)
                            radius: 3
                            color: IrisStyle.fillHover

                            Text {
                                anchors.centerIn: parent
                                text: String(sipRow.modelData.next_date ?? "").slice(0, 5)
                                font.family: IrisStyle.fontNumbers
                                font.pixelSize: Math.round(9 * root.d)
                                font.features: ({ "tnum": 1 })
                                color: root.fgMain
                            }
                        }

                        // Scheme / Stock Name
                        Text {
                            text: sipRow.modelData.name
                            font.pixelSize: IrisStyle.typeLabel
                            color: root.fgMain
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        // Amount
                        Text {
                            text: IndMoneyService.formatInrCompact(sipRow.modelData.amount_inr, IndMoneyService.privacyMode)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(11 * root.d)
                            font.weight: IrisStyle.weight(Font.Bold)
                            font.features: ({ "tnum": 1 })
                            color: root.fgMain
                        }
                    }
                }
            }
        }
    }
}
