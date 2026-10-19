pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.iris.style
import qs.modules.iris.components

ColumnLayout {
    id: root

    readonly property real d: IrisStyle.density
    readonly property var summary: IndMoneyService.summary
    readonly property real networth: summary.total_networth_inr ?? 0
    readonly property real invested: summary.invested_inr ?? 0
    readonly property real totalPnl: summary.total_pnl_inr ?? 0
    readonly property real totalPnlPct: summary.total_pnl_pct ?? 0
    readonly property real dayInr: summary.day_change_inr ?? 0
    readonly property real dayPct: summary.day_change_pct ?? 0
    readonly property bool isDayGain: dayPct >= 0
    readonly property bool isTotalGain: totalPnl >= 0

    property int activeTab: 0 // 0: Top Movers, 1: Holdings, 2: SIPs
    property string holdingFilter: "ALL" // "ALL", "IN_EQ", "MF", "US_EQ"
    property var hoveredAlloc: null

    spacing: Math.round(12 * root.d)
    Layout.fillWidth: true

    // --- Header ---
    CardHeader {
        glyph: "account_balance_wallet"
        tint: IrisStyle.accent
        title: "Portfolio"
        detail: {
            if (IndMoneyService.status === "auth_required") return "Authentication required"
            if (IndMoneyService.marketState === "IN_OPEN") return "NSE / BSE Open"
            if (IndMoneyService.marketState === "US_OPEN") return "US Markets Open"
            return "Markets Closed"
        }

        IrisIconButton {
            materialIcon: IndMoneyService.privacyMode ? "visibility_off" : "visibility"
            Accessible.name: "Toggle Privacy"
            onClicked: IndMoneyService.togglePrivacy()
        }

        IrisIconButton {
            materialIcon: "refresh"
            Accessible.name: "Refresh Portfolio"
            enabled: !IndMoneyService.syncing
            onClicked: IndMoneyService.refresh()

            RotationAnimation on rotation {
                running: IndMoneyService.syncing
                loops: Animation.Infinite
                from: 0
                to: 360
                duration: 1000
            }
        }
    }

    // --- Auth Required Banner ---
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: Math.round(90 * root.d)
        radius: IrisStyle.radiusTile
        color: IrisStyle.fillSecondary
        border.width: 1
        border.color: IrisStyle.outlineVariant
        visible: IndMoneyService.status === "auth_required"

        ColumnLayout {
            anchors.centerIn: parent
            spacing: Math.round(8 * root.d)

            Text {
                text: "IndMoney session expired or not connected"
                font.pixelSize: Math.round(12 * root.d)
                font.weight: Font.Medium
                color: IrisStyle.text
                Layout.alignment: Qt.AlignHCenter
            }

            IrisButton {
                text: "Connect IndMoney"
                emphasized: true
                Layout.alignment: Qt.AlignHCenter
                onClicked: IndMoneyService.reauthenticate()
            }
        }
    }

    // --- Main Portfolio Body (when authenticated or browsing cache) ---
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(12 * root.d)
        visible: IndMoneyService.status !== "auth_required"

        // --- Net Worth Overview Hero ---
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: heroCol.implicitHeight + Math.round(20 * root.d)
            radius: IrisStyle.radiusTile
            color: IrisStyle.fillSecondary
            border.width: 1
            border.color: IrisStyle.outlineVariant

            ColumnLayout {
                id: heroCol
                anchors.fill: parent
                anchors.margins: Math.round(12 * root.d)
                spacing: Math.round(6 * root.d)

                // Row: Net Worth + 1D Badge
                RowLayout {
                    Layout.fillWidth: true

                    Item {
                        implicitWidth: rawHeroNetworth.implicitWidth
                        implicitHeight: rawHeroNetworth.implicitHeight
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            id: rawHeroNetworth
                            text: IndMoneyService.formatInrFull(root.networth, false)
                            font.family: "JetBrains Mono Nerd Font"
                            font.pixelSize: Math.round(22 * root.d)
                            font.weight: Font.Bold
                            font.features: { "tnum": 1 }
                            color: IrisStyle.text
                            visible: !IndMoneyService.privacyMode
                        }

                        Text {
                            anchors.fill: parent
                            text: "₹••••••••"
                            font.family: "JetBrains Mono Nerd Font"
                            font.pixelSize: Math.round(22 * root.d)
                            font.weight: Font.Bold
                            font.features: { "tnum": 1 }
                            color: IrisStyle.muted
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
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // 1D Pill
                    Rectangle {
                        implicitWidth: dayRow.implicitWidth + Math.round(12 * root.d)
                        implicitHeight: Math.round(22 * root.d)
                        radius: height / 2
                        color: root.isDayGain ? "#1010b981" : "#10f43f5e"
                        border.width: 1
                        border.color: root.isDayGain ? "#3010b981" : "#30f43f5e"

                        RowLayout {
                            id: dayRow
                            anchors.centerIn: parent
                            spacing: Math.round(4 * root.d)

                            Text {
                                text: root.isDayGain ? "▲" : "▼"
                                font.pixelSize: Math.round(8 * root.d)
                                color: root.isDayGain ? "#10b981" : "#f43f5e"
                            }

                            Text {
                                text: (root.isDayGain ? "+" : "") + IndMoneyService.formatInrCompact(root.dayInr, IndMoneyService.privacyMode) + " (" + IndMoneyService.formatPct(root.dayPct) + ")"
                                font.family: "JetBrains Mono Nerd Font"
                                font.pixelSize: Math.round(10 * root.d)
                                font.weight: Font.DemiBold
                                font.features: { "tnum": 1 }
                                color: root.isDayGain ? "#10b981" : "#f43f5e"
                            }
                        }
                    }
                }

                // Subtitle Row: Invested vs Overall Returns
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Math.round(8 * root.d)

                    Text {
                        text: "Invested: " + IndMoneyService.formatInrCompact(root.invested, IndMoneyService.privacyMode)
                        font.family: "JetBrains Mono Nerd Font"
                        font.pixelSize: Math.round(11 * root.d)
                        font.features: { "tnum": 1 }
                        color: IrisStyle.muted
                    }

                    Text {
                        text: "•"
                        color: IrisStyle.muted
                    }

                    Text {
                        text: "Overall: " + (root.isTotalGain ? "+" : "") + IndMoneyService.formatInrCompact(root.totalPnl, IndMoneyService.privacyMode) + " (" + IndMoneyService.formatPct(root.totalPnlPct) + ")"
                        font.family: "JetBrains Mono Nerd Font"
                        font.pixelSize: Math.round(11 * root.d)
                        font.weight: Font.Medium
                        font.features: { "tnum": 1 }
                        color: root.isTotalGain ? "#10b981" : "#f43f5e"
                    }
                }
            }
        }

        // --- Interactive Asset Allocation Bar ---
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Math.round(4 * root.d)

            // Scrubber Detail Subtitle
            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: root.hoveredAlloc
                        ? (root.hoveredAlloc.asset + ": " + IndMoneyService.formatInrCompact(root.hoveredAlloc.value_inr, IndMoneyService.privacyMode) + " (" + root.hoveredAlloc.weight_pct + "%) • 1D: " + IndMoneyService.formatPct(root.hoveredAlloc.day_pct))
                        : "Asset Allocation"
                    font.family: "JetBrains Mono Nerd Font"
                    font.pixelSize: Math.round(10 * root.d)
                    font.features: { "tnum": 1 }
                    color: root.hoveredAlloc ? IrisStyle.accent : IrisStyle.muted
                }
            }

            // Proportional Multi-Segment Bar
            Row {
                id: allocBar
                Layout.fillWidth: true
                height: Math.round(10 * root.d)
                spacing: 2

                Repeater {
                    model: IndMoneyService.allocation

                    Rectangle {
                        id: segRect
                        required property var modelData
                        width: Math.max(4, (allocBar.width - ((IndMoneyService.allocation.length - 1) * 2)) * (modelData.weight_pct / 100.0))
                        height: segMouse.containsMouse ? Math.round(10 * root.d) : Math.round(5 * root.d)
                        radius: 3
                        color: modelData.color || IrisStyle.accent

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

        // --- Tab Navigation ---
        RowLayout {
            Layout.fillWidth: true
            spacing: Math.round(4 * root.d)

            Repeater {
                model: [
                    { label: "Top Movers", idx: 0 },
                    { label: "Holdings", idx: 1 },
                    { label: "SIPs (" + (IndMoneyService.sips.active_count ?? 0) + ")", idx: 2 }
                ]

                Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: Math.round(26 * root.d)
                    radius: IrisStyle.radiusSmall
                    color: root.activeTab === modelData.idx ? IrisStyle.fillHover : "transparent"
                    border.width: 1
                    border.color: root.activeTab === modelData.idx ? IrisStyle.outline : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: parent.modelData.label
                        font.pixelSize: Math.round(11 * root.d)
                        font.weight: root.activeTab === parent.modelData.idx ? Font.DemiBold : Font.Normal
                        color: root.activeTab === parent.modelData.idx ? IrisStyle.text : IrisStyle.muted
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeTab = parent.modelData.idx
                    }
                }
            }
        }

        // --- Tab 0: Top Movers ---
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Math.round(6 * root.d)
            visible: root.activeTab === 0

            Repeater {
                model: IndMoneyService.topMovers

                Rectangle {
                    id: moverRow
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: Math.round(36 * root.d)
                    radius: IrisStyle.radiusSmall
                    color: rowMouse.containsMouse ? IrisStyle.fillHover : "transparent"
                    border.width: 1
                    border.color: rowMouse.containsMouse ? IrisStyle.outlineVariant : "transparent"

                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Math.round(8 * root.d)
                        anchors.rightMargin: Math.round(8 * root.d)
                        spacing: Math.round(8 * root.d)

                        // Symbol & Name
                        ColumnLayout {
                            spacing: 0
                            Layout.fillWidth: true

                            RowLayout {
                                spacing: Math.round(4 * root.d)
                                Text {
                                    text: moverRow.modelData.symbol
                                    font.family: "JetBrains Mono Nerd Font"
                                    font.pixelSize: Math.round(11 * root.d)
                                    font.weight: Font.DemiBold
                                    color: IrisStyle.text
                                }
                                Rectangle {
                                    implicitWidth: Math.round(32 * root.d)
                                    implicitHeight: Math.round(14 * root.d)
                                    radius: 2
                                    color: IrisStyle.fillSecondary
                                    Text {
                                        anchors.centerIn: parent
                                        text: moverRow.modelData.asset
                                        font.pixelSize: Math.round(8 * root.d)
                                        font.weight: Font.Medium
                                        color: IrisStyle.muted
                                    }
                                }
                            }

                            Text {
                                text: moverRow.modelData.name
                                font.pixelSize: Math.round(9 * root.d)
                                color: IrisStyle.muted
                                elide: Text.ElideRight
                                Layout.maximumWidth: Math.round(180 * root.d)
                            }
                        }

                        // Value
                        Text {
                            text: IndMoneyService.formatInrCompact(moverRow.modelData.value_inr, IndMoneyService.privacyMode)
                            font.family: "JetBrains Mono Nerd Font"
                            font.pixelSize: Math.round(11 * root.d)
                            font.features: { "tnum": 1 }
                            color: IrisStyle.text
                        }

                        // 1D Return Chip
                        Rectangle {
                            implicitWidth: Math.round(52 * root.d)
                            implicitHeight: Math.round(20 * root.d)
                            radius: 4
                            color: moverRow.modelData.day_pct >= 0 ? "#1510b981" : "#15f43f5e"

                            Text {
                                anchors.centerIn: parent
                                text: IndMoneyService.formatPct(moverRow.modelData.day_pct)
                                font.family: "JetBrains Mono Nerd Font"
                                font.pixelSize: Math.round(10 * root.d)
                                font.weight: Font.DemiBold
                                font.features: { "tnum": 1 }
                                color: moverRow.modelData.day_pct >= 0 ? "#10b981" : "#f43f5e"
                            }
                        }
                    }
                }
            }
        }

        // --- Tab 1: All Holdings ---
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Math.round(6 * root.d)
            visible: root.activeTab === 1

            // Category Filter Pills
            RowLayout {
                Layout.fillWidth: true
                spacing: Math.round(4 * root.d)

                Repeater {
                    model: [
                        { label: "All", filter: "ALL" },
                        { label: "IN Eq", filter: "IN_EQ" },
                        { label: "MF", filter: "MF" },
                        { label: "US Eq", filter: "US_EQ" }
                    ]

                    Rectangle {
                        required property var modelData
                        implicitWidth: Math.round(46 * root.d)
                        implicitHeight: Math.round(20 * root.d)
                        radius: height / 2
                        color: root.holdingFilter === modelData.filter ? IrisStyle.accent : IrisStyle.fillSecondary

                        Text {
                            anchors.centerIn: parent
                            text: parent.modelData.label
                            font.pixelSize: Math.round(9 * root.d)
                            font.weight: Font.Medium
                            color: root.holdingFilter === parent.modelData.filter ? IrisStyle.onTint : IrisStyle.muted
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
                spacing: Math.round(4 * root.d)

                model: IndMoneyService.holdings.filter(h => {
                    if (root.holdingFilter === "ALL") return true
                    return h.asset === root.holdingFilter
                })

                delegate: Rectangle {
                    id: hRow
                    required property var modelData
                    width: ListView.view.width
                    implicitHeight: Math.round(36 * root.d)
                    radius: IrisStyle.radiusSmall
                    color: hMouse.containsMouse ? IrisStyle.fillHover : "transparent"

                    MouseArea {
                        id: hMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Math.round(6 * root.d)
                        anchors.rightMargin: Math.round(6 * root.d)
                        spacing: Math.round(8 * root.d)

                        ColumnLayout {
                            spacing: 0
                            Layout.fillWidth: true

                            Text {
                                text: hRow.modelData.name
                                font.pixelSize: Math.round(11 * root.d)
                                font.weight: Font.Medium
                                color: IrisStyle.text
                                elide: Text.ElideRight
                                Layout.maximumWidth: Math.round(170 * root.d)
                            }

                            Text {
                                text: "Invested: " + IndMoneyService.formatInrCompact(hRow.modelData.invested_inr, IndMoneyService.privacyMode)
                                font.family: "JetBrains Mono Nerd Font"
                                font.pixelSize: Math.round(9 * root.d)
                                font.features: { "tnum": 1 }
                                color: IrisStyle.muted
                            }
                        }

                        ColumnLayout {
                            spacing: 0
                            Layout.alignment: Qt.AlignRight

                            Text {
                                text: IndMoneyService.formatInrCompact(hRow.modelData.value_inr, IndMoneyService.privacyMode)
                                font.family: "JetBrains Mono Nerd Font"
                                font.pixelSize: Math.round(11 * root.d)
                                font.weight: Font.DemiBold
                                font.features: { "tnum": 1 }
                                color: IrisStyle.text
                                Layout.alignment: Qt.AlignRight
                            }

                            Text {
                                text: IndMoneyService.formatPct(hRow.modelData.total_pct)
                                font.family: "JetBrains Mono Nerd Font"
                                font.pixelSize: Math.round(9 * root.d)
                                font.features: { "tnum": 1 }
                                color: hRow.modelData.total_pct >= 0 ? "#10b981" : "#f43f5e"
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
            spacing: Math.round(8 * root.d)
            visible: root.activeTab === 2

            // Monthly Total Card
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.round(48 * root.d)
                radius: IrisStyle.radiusSmall
                color: IrisStyle.fillSecondary
                border.width: 1
                border.color: IrisStyle.outlineVariant

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Math.round(10 * root.d)

                    ColumnLayout {
                        spacing: 0
                        Text {
                            text: "Monthly Commitment"
                            font.pixelSize: Math.round(10 * root.d)
                            color: IrisStyle.muted
                        }
                        Text {
                            text: IndMoneyService.formatInrCompact(IndMoneyService.sips.monthly_total_inr ?? 0, IndMoneyService.privacyMode) + "/month"
                            font.family: "JetBrains Mono Nerd Font"
                            font.pixelSize: Math.round(14 * root.d)
                            font.weight: Font.Bold
                            font.features: { "tnum": 1 }
                            color: IrisStyle.accent
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: (IndMoneyService.sips.active_count ?? 0) + " Active SIPs"
                        font.pixelSize: Math.round(11 * root.d)
                        font.weight: Font.Medium
                        color: IrisStyle.text
                    }
                }
            }

            // Upcoming SIP list
            ListView {
                Layout.fillWidth: true
                implicitHeight: Math.min(180 * root.d, contentHeight)
                clip: true
                spacing: Math.round(4 * root.d)

                model: IndMoneyService.sips.upcoming ?? []

                delegate: Rectangle {
                    id: sipRow
                    required property var modelData
                    width: ListView.view.width
                    implicitHeight: Math.round(34 * root.d)
                    radius: IrisStyle.radiusSmall
                    color: IrisStyle.fillSecondary

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Math.round(8 * root.d)
                        anchors.rightMargin: Math.round(8 * root.d)
                        spacing: Math.round(8 * root.d)

                        // Date Pill
                        Rectangle {
                            implicitWidth: Math.round(42 * root.d)
                            implicitHeight: Math.round(18 * root.d)
                            radius: 3
                            color: IrisStyle.fillHover

                            Text {
                                anchors.centerIn: parent
                                text: (sipRow.modelData.next_date ?? "").slice(5) // MM-DD
                                font.family: "JetBrains Mono Nerd Font"
                                font.pixelSize: Math.round(9 * root.d)
                                font.features: { "tnum": 1 }
                                color: IrisStyle.text
                            }
                        }

                        // Scheme / Stock Name
                        Text {
                            text: sipRow.modelData.name
                            font.pixelSize: Math.round(11 * root.d)
                            color: IrisStyle.text
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        // Amount
                        Text {
                            text: IndMoneyService.formatInrCompact(sipRow.modelData.amount_inr, IndMoneyService.privacyMode)
                            font.family: "JetBrains Mono Nerd Font"
                            font.pixelSize: Math.round(11 * root.d)
                            font.weight: Font.DemiBold
                            font.features: { "tnum": 1 }
                            color: IrisStyle.text
                        }
                    }
                }
            }
        }
    }
}
