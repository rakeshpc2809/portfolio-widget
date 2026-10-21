pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import Quickshell
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.iris.style
import qs.modules.iris.components
import qs.modules.iris.stage

ColumnLayout {
    id: root

    readonly property real d: IrisStyle.density
    readonly property real investedVal: IndMoneyService.investedValue
    readonly property real networthVal: IndMoneyService.networthValue
    readonly property real bankVal: IndMoneyService.bankBalanceValue
    readonly property real epfVal: IndMoneyService.epfValue
    readonly property real totalReturnInr: IndMoneyService.totalReturnInr
    readonly property real totalReturnPct: IndMoneyService.totalReturnPct
    readonly property real dayInr: IndMoneyService.oneDayChangeInr
    readonly property real dayPct: IndMoneyService.oneDayChangePct
    readonly property bool isDayGain: dayPct >= 0
    readonly property bool isTotalGain: totalReturnInr >= 0

    // Theme-resilient contrast tokens using dynamic IrisStyle palette
    readonly property color fgMain: IrisStyle.text
    readonly property color fgMuted: IrisStyle.subtext
    readonly property color rowBg: IrisStyle.fillSecondary
    readonly property color rowBgHover: IrisStyle.fillHover

    // Dynamic asset class color mapping using IrisStyle.identity tokens
    function getAssetColor(assetName: string): color {
        const name = (assetName || "").toLowerCase()
        if (name.includes("mutual") || name === "mf") return IrisStyle.identity.indigo
        if (name.includes("us") || name === "us_eq") return IrisStyle.identity.teal
        if (name.includes("indian") || name === "in_eq" || name.includes("stock") || name.includes("equity")) return IrisStyle.identity.sky
        if (name.includes("fixed") || name.includes("fd") || name.includes("deposit") || name.includes("gold") || name === "gold") return IrisStyle.identity.yellow
        if (name.includes("epf") || name.includes("retirement") || name.includes("other")) return IrisStyle.identity.orange
        return IrisStyle.identity.teal
    }

    property int activeTab: 0 // 0: Top Movers, 1: Holdings, 2: SIPs, 3: Buckets (optional)
    property string holdingFilter: "ALL" // "ALL", "MF", "IN_EQ", "US_EQ"
    property string topMoversSort: "PCT" // "PCT" or "INR"
    property var hoveredAlloc: null
    property var hoveredBucket: null

    // Idle / OLED Care: subtle opacity dimming on user inactivity
    readonly property bool isUserIdle: (typeof ScreenTime !== "undefined" && ScreenTime?.userIdle) || false
    opacity: isUserIdle ? 0.75 : 1.0
    Behavior on opacity {
        NumberAnimation {
            duration: IrisStyle.duration(240)
            easing.type: IrisStyle.feedbackEasing
        }
    }

    spacing: Math.round(10 * root.d)
    Layout.fillWidth: true
    focus: true

    onVisibleChanged: {
        if (visible) {
            root.forceActiveFocus()
        }
    }

    Component.onCompleted: {
        if (visible) {
            root.forceActiveFocus()
        }
    }

    TapHandler {
        onTapped: root.forceActiveFocus()
    }

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
        } else if (event.key === Qt.Key_4 && IndMoneyService.bucketsEnabled) {
            root.activeTab = 3
            event.accepted = true
        } else if (event.key === Qt.Key_Tab && root.activeTab === 1) {
            const filters = ["ALL", "MF", "IN_EQ", "US_EQ"]
            const idx = filters.indexOf(root.holdingFilter)
            const nextIdx = (idx + 1) % filters.length
            root.holdingFilter = filters[nextIdx]
            event.accepted = true
        } else if (event.key === Qt.Key_S && root.activeTab === 0) {
            root.topMoversSort = (root.topMoversSort === "PCT" ? "INR" : "PCT")
            event.accepted = true
        } else if (event.key === Qt.Key_Q) {
            IndMoneyService.toggleQuietMode()
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
        const raw = IndMoneyService.topMovers && IndMoneyService.topMovers.length > 0
            ? IndMoneyService.topMovers
            : (IndMoneyService.holdings || []).slice().sort((a, b) => Math.abs(b.one_day_change_pct ?? b.day_pct ?? 0) - Math.abs(a.one_day_change_pct ?? a.day_pct ?? 0)).slice(0, 5)
        const list = raw.slice()
        if (root.topMoversSort === "INR") {
            return list.sort((a, b) => Math.abs(b.one_day_change_inr ?? b.day_change_inr ?? 0) - Math.abs(a.one_day_change_inr ?? a.day_change_inr ?? 0))
        } else {
            return list.sort((a, b) => Math.abs(b.one_day_change_pct ?? b.day_pct ?? 0) - Math.abs(a.one_day_change_pct ?? a.day_pct ?? 0))
        }
    }

    // Filtered Holdings
    readonly property var filteredHoldings: {
        const list = IndMoneyService.holdings || []
        if (root.holdingFilter === "ALL") return list
        return list.filter(h => {
            const a = (h.asset || h.class_id || "").toUpperCase()
            if (root.holdingFilter === "MF") return a === "MF"
            if (root.holdingFilter === "IN_EQ") return a === "IN_EQ" || a === "STOCK" || a === "EQUITY"
            if (root.holdingFilter === "US_EQ") return a === "US_EQ" || a === "US_STOCK"
            return true
        })
    }

    // Helper for 90-day Sparkline Polyline
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

        const padTop = h * 0.15
        const padBottom = h * 0.10
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

    // Freshness Badge Color Mapping
    readonly property color freshnessColor: {
        const f = IndMoneyService.freshness
        if (f === "fresh") return IrisStyle.identity.teal
        if (f === "aging") return IrisStyle.subtext
        if (f === "stale") return IrisStyle.identity.yellow
        if (f === "partial") return IrisStyle.identity.orange
        if (f === "auth_required") return IrisStyle.identity.red
        return IrisStyle.identity.teal
    }

    // --- Header ---
    CardHeader {
        glyph: "account_balance_wallet"
        tint: IrisStyle.identity.teal
        title: Translation.tr("Portfolio")
        detail: IndMoneyService.navAsOf
            ? Translation.tr("NAV as of %1").arg(IndMoneyService.navAsOf)
            : Translation.tr("Live Net Worth")

        // Freshness Badge Chip
        Rectangle {
            implicitHeight: Math.round(18 * root.d)
            implicitWidth: freshnessText.implicitWidth + Math.round(10 * root.d)
            radius: IrisStyle.radiusChip
            color: IrisStyle.trackOf(root.freshnessColor)
            border.color: root.freshnessColor
            border.width: 1
            Layout.alignment: Qt.AlignVCenter

            IrisText {
                id: freshnessText
                anchors.centerIn: parent
                text: IndMoneyService.freshness.toUpperCase()
                font.pixelSize: Math.round(9 * root.d)
                font.weight: IrisStyle.weight(Font.DemiBold)
                color: root.freshnessColor
            }
        }

        // Action Buttons: Quiet Mode, Privacy Mode, Sync Refresh
        IrisIconButton {
            materialIcon: IndMoneyService.quietMode ? "visibility_off" : "visibility"
            iconSize: Math.round(15 * root.d)
            Accessible.name: Translation.tr("Quiet Mode (Q)")
            onClicked: IndMoneyService.toggleQuietMode()
        }

        IrisIconButton {
            materialIcon: IndMoneyService.privacyMode ? "visibility_off" : "lock_open"
            iconSize: Math.round(15 * root.d)
            Accessible.name: Translation.tr("Privacy Mode (P)")
            onClicked: IndMoneyService.togglePrivacy()
        }

        IrisIconButton {
            id: refreshBtn
            materialIcon: "refresh"
            iconSize: Math.round(15 * root.d)
            Accessible.name: Translation.tr("Refresh (R)")
            onClicked: IndMoneyService.refresh()

            RotationAnimation on rotation {
                running: IndMoneyService.syncing
                loops: Animation.Infinite
                from: 0
                to: 360
                duration: 900
            }
        }
    }

    // --- Hero Platter with 90-Day Sparkline ---
    Rectangle {
        id: heroPlatter
        Layout.fillWidth: true
        implicitHeight: Math.round(110 * root.d)
        radius: IrisStyle.radiusPlate
        color: IrisStyle.readingPlate
        border.color: heroHover.hovered ? IrisStyle.hairlineStrong : IrisStyle.hairline
        border.width: 1
        clip: true

        HoverHandler {
            id: heroHover
        }

        // 90-Day Daily Sparkline Shape
        Shape {
            id: sparklineShape
            anchors.fill: parent
            anchors.bottomMargin: Math.round(2 * root.d)
            opacity: IndMoneyService.privacyMode ? 0.0 : (heroHover.hovered ? 0.85 : 0.55)
            visible: opacity > 0.01

            Behavior on opacity {
                NumberAnimation {
                    duration: IrisStyle.duration(160)
                    easing.type: IrisStyle.feedbackEasing
                }
            }

            readonly property var pts: root.generateSparklinePoints(IndMoneyService.sparkline90d, width, height)

            ShapePath {
                strokeColor: Qt.rgba(IrisStyle.identity.teal.r, IrisStyle.identity.teal.g, IrisStyle.identity.teal.b, 0.20)
                strokeWidth: 0
                fillGradient: LinearGradient {
                    x1: 0; y1: 0; x2: 0; y2: sparklineShape.height
                    GradientStop {
                        position: 0.0
                        color: Qt.rgba(IrisStyle.identity.teal.r, IrisStyle.identity.teal.g, IrisStyle.identity.teal.b, 0.15)
                    }
                    GradientStop {
                        position: 1.0
                        color: Qt.rgba(IrisStyle.identity.teal.r, IrisStyle.identity.teal.g, IrisStyle.identity.teal.b, 0.0)
                    }
                }
                PathPolyline {
                    path: sparklineShape.pts.fill
                }
            }

            ShapePath {
                strokeColor: IrisStyle.identity.teal
                strokeWidth: Math.max(1, Math.round(1.5 * root.d))
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathPolyline {
                    path: sparklineShape.pts.line
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Math.round(14 * root.d)
            spacing: Math.round(4 * root.d)

            RowLayout {
                Layout.fillWidth: true
                spacing: Math.round(8 * root.d)

                // Primary Hero Figure with Privacy Crossfade
                Item {
                    implicitWidth: Math.max(heroNumber.implicitWidth, heroMask.implicitWidth)
                    implicitHeight: Math.max(heroNumber.implicitHeight, heroMask.implicitHeight)
                    Layout.alignment: Qt.AlignVCenter

                    IrisNumber {
                        id: heroNumber
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: IndMoneyService.formatInrFull(root.investedVal, false)
                        family: IrisStyle.fontNumbers
                        pixelSize: IrisStyle.typeTitleLarge
                        weight: IrisStyle.weight(Font.Bold)
                        color: IrisStyle.text
                        opacity: IndMoneyService.privacyMode ? 0.0 : 1.0
                        visible: opacity > 0.01

                        Behavior on opacity {
                            NumberAnimation {
                                duration: IrisStyle.duration(120)
                                easing.type: IrisStyle.feedbackEasing
                            }
                        }
                    }

                    IrisText {
                        id: heroMask
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: IndMoneyService.staticMask
                        font.family: IrisStyle.fontNumbers
                        font.pixelSize: IrisStyle.typeTitleLarge
                        font.weight: IrisStyle.weight(Font.Bold)
                        font.features: ({ "tnum": 1 })
                        color: IrisStyle.subtext
                        opacity: IndMoneyService.privacyMode ? 1.0 : 0.0
                        visible: opacity > 0.01

                        Behavior on opacity {
                            NumberAnimation {
                                duration: IrisStyle.duration(120)
                                easing.type: IrisStyle.feedbackEasing
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // 1D Return Chip (F3: Quiet Mode gating)
                Rectangle {
                    implicitHeight: Math.round(22 * root.d)
                    implicitWidth: chipRow.implicitWidth + Math.round(12 * root.d)
                    radius: IrisStyle.radiusChip
                    color: IrisStyle.trackOf(root.isDayGain ? IrisStyle.identity.green : IrisStyle.identity.red)
                    opacity: (!IndMoneyService.quietMode || heroHover.hovered) ? 1.0 : 0.20
                    visible: opacity > 0.05
                    Layout.alignment: Qt.AlignVCenter

                    Behavior on opacity {
                        NumberAnimation {
                            duration: IrisStyle.duration(140)
                            easing.type: IrisStyle.feedbackEasing
                        }
                    }

                    RowLayout {
                        id: chipRow
                        anchors.centerIn: parent
                        spacing: Math.round(4 * root.d)

                        MaterialSymbol {
                            text: root.isDayGain ? "trending_up" : "trending_down"
                            iconSize: Math.round(13 * root.d)
                            color: root.isDayGain ? IrisStyle.identity.green : IrisStyle.identity.red
                        }

                        IrisText {
                            text: IndMoneyService.formatPct(root.dayPct)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(11 * root.d)
                            font.weight: IrisStyle.weight(Font.DemiBold)
                            font.features: ({ "tnum": 1 })
                            color: root.isDayGain ? IrisStyle.identity.green : IrisStyle.identity.red
                        }
                    }
                }
            }

            // Secondary Captions (Dual Basis Transparency)
            IrisText {
                text: Translation.tr("Net Worth: %1 (Bank %2 · EPF %3)")
                    .arg(IndMoneyService.formatInrCompact(root.networthVal, IndMoneyService.privacyMode))
                    .arg(IndMoneyService.formatInrCompact(root.bankVal, IndMoneyService.privacyMode))
                    .arg(IndMoneyService.formatInrCompact(root.epfVal, IndMoneyService.privacyMode))
                font.pixelSize: IrisStyle.typeFootnote
                color: root.fgMuted
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            IrisText {
                text: Translation.tr("Invested: %1 · Total Return: %2 (%3)")
                    .arg(IndMoneyService.formatInrCompact(root.investedVal, IndMoneyService.privacyMode))
                    .arg(IndMoneyService.formatPct(root.totalReturnPct))
                    .arg(IndMoneyService.formatInrCompact(root.totalReturnInr, IndMoneyService.privacyMode))
                font.pixelSize: IrisStyle.typeFootnote
                color: root.isTotalGain ? IrisStyle.identity.teal : root.fgMuted
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }

    // --- Proportional Asset Allocation Bar ---
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(4 * root.d)
        visible: (IndMoneyService.allocation || []).length > 0

        RowLayout {
            Layout.fillWidth: true

            IrisText {
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
                model: IndMoneyService.allocation || []

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
        options: {
            const base = [
                { value: 0, label: Translation.tr("Top Movers") },
                { value: 1, label: Translation.tr("Holdings (%1)").arg((IndMoneyService.holdings || []).length) },
                { value: 2, label: Translation.tr("SIPs (%1)").arg(IndMoneyService.sips.active_count ?? 0) }
            ]
            if (IndMoneyService.bucketsEnabled) {
                base.push({ value: 3, label: Translation.tr("Buckets & Drift") })
            }
            return base
        }
        current: root.activeTab
        onPicked: val => root.activeTab = val
    }

    // =========================================================================
    // TAB 0: Top Movers (Daily Leaders with Rupee Impact Attribution)
    // =========================================================================
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(5 * root.d)
        visible: root.activeTab === 0

        // Header Row with Sort Attribution Pill
        RowLayout {
            Layout.fillWidth: true
            spacing: Math.round(6 * root.d)

            IrisText {
                text: Translation.tr("Daily Leaders")
                font.pixelSize: IrisStyle.typeMeta
                color: root.fgMuted
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                implicitWidth: sortRow.implicitWidth + Math.round(12 * root.d)
                implicitHeight: Math.round(22 * root.d)
                radius: height / 2
                color: sortMouse.containsMouse ? IrisStyle.fillHover : root.rowBg

                RowLayout {
                    id: sortRow
                    anchors.centerIn: parent
                    spacing: Math.round(4 * root.d)

                    MaterialSymbol {
                        text: "sort"
                        iconSize: Math.round(12 * root.d)
                        color: IrisStyle.identity.teal
                    }

                    IrisText {
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

            delegate: Rectangle {
                id: moverRow
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: Math.round(40 * root.d)
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

                    // Asset type accent stripe
                    Rectangle {
                        implicitWidth: Math.round(3 * root.d)
                        implicitHeight: Math.round(22 * root.d)
                        radius: 1.5
                        color: root.getAssetColor(moverRow.modelData.asset || moverRow.modelData.class_id)
                        Layout.alignment: Qt.AlignVCenter
                    }

                    ColumnLayout {
                        spacing: 1
                        Layout.fillWidth: true

                        IrisText {
                            text: moverRow.modelData.name
                            font.pixelSize: IrisStyle.typeLabel
                            font.weight: IrisStyle.weight(Font.Medium)
                            color: root.fgMain
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        IrisText {
                            text: (moverRow.modelData.asset || moverRow.modelData.class_id || "").toUpperCase() + " · " + IndMoneyService.formatInrCompact(moverRow.modelData.value_inr ?? moverRow.modelData.current_value_inr, IndMoneyService.privacyMode)
                            font.pixelSize: IrisStyle.typeFootnote
                            color: root.fgMuted
                        }
                    }

                    // Attribution Chip with Rupee Impact + Percentage Change
                    Rectangle {
                        readonly property real dayVal: moverRow.modelData.day_change_inr ?? moverRow.modelData.one_day_change_inr ?? 0
                        readonly property real dayPctVal: moverRow.modelData.day_pct ?? moverRow.modelData.one_day_change_pct ?? 0
                        implicitWidth: moverBadgeText.implicitWidth + Math.round(12 * root.d)
                        implicitHeight: Math.round(22 * root.d)
                        radius: 4
                        color: dayPctVal >= 0 ? Qt.alpha(IrisStyle.identity.green, 0.15) : Qt.alpha(IrisStyle.identity.red, 0.15)

                        IrisText {
                            id: moverBadgeText
                            anchors.centerIn: parent
                            text: (parent.dayVal >= 0 ? "+" : "") + IndMoneyService.formatInrCompact(parent.dayVal, IndMoneyService.privacyMode) + " · " + IndMoneyService.formatPct(parent.dayPctVal)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(9.5 * root.d)
                            font.weight: IrisStyle.weight(Font.Bold)
                            font.features: ({ "tnum": 1 })
                            color: parent.dayPctVal >= 0 ? IrisStyle.identity.green : IrisStyle.identity.red
                        }
                    }
                }
            }
        }
    }

    // =========================================================================
    // TAB 1: Holdings with High-Character Category Filtering & Badges
    // =========================================================================
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(6 * root.d)
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
                    implicitWidth: filterText.implicitWidth + Math.round(14 * root.d)
                    implicitHeight: Math.round(22 * root.d)
                    radius: height / 2
                    color: root.holdingFilter === modelData.filter ? IrisStyle.identity.teal : root.rowBg

                    IrisText {
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
            id: holdingsListView
            Layout.fillWidth: true
            implicitHeight: Math.min(Math.round(260 * root.d), contentHeight)
            clip: true
            spacing: Math.round(4 * root.d)

            model: root.filteredHoldings

            delegate: Rectangle {
                id: hRow
                required property var modelData
                width: ListView.view.width
                implicitHeight: Math.round(42 * root.d)
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

                    // Category Accent Color Stripe (Character & Visual Polish)
                    Rectangle {
                        implicitWidth: Math.round(3 * root.d)
                        implicitHeight: Math.round(24 * root.d)
                        radius: 1.5
                        color: root.getAssetColor(hRow.modelData.asset || hRow.modelData.class_id)
                        Layout.alignment: Qt.AlignVCenter
                    }

                    ColumnLayout {
                        spacing: 1
                        Layout.fillWidth: true

                        IrisText {
                            text: hRow.modelData.name
                            font.pixelSize: IrisStyle.typeLabel
                            font.weight: IrisStyle.weight(Font.Medium)
                            color: root.fgMain
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        IrisText {
                            text: Translation.tr("Invested: %1 · %2")
                                .arg(IndMoneyService.formatInrCompact(hRow.modelData.invested_inr ?? hRow.modelData.invested_value_inr, IndMoneyService.privacyMode))
                                .arg((hRow.modelData.asset || hRow.modelData.class_id || "").toUpperCase())
                            font.pixelSize: IrisStyle.typeFootnote
                            color: root.fgMuted
                        }
                    }

                    ColumnLayout {
                        spacing: 1
                        Layout.alignment: Qt.AlignRight

                        IrisText {
                            text: IndMoneyService.formatInrCompact(hRow.modelData.value_inr ?? hRow.modelData.current_value_inr, IndMoneyService.privacyMode)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(11 * root.d)
                            font.weight: IrisStyle.weight(Font.Bold)
                            font.features: ({ "tnum": 1 })
                            color: root.fgMain
                            Layout.alignment: Qt.AlignRight
                        }

                        // Gain / Loss Chip Badge
                        Rectangle {
                            readonly property real returnPct: hRow.modelData.total_pct ?? hRow.modelData.total_return_pct ?? hRow.modelData.one_day_change_pct ?? 0
                            implicitWidth: badgeText.implicitWidth + Math.round(8 * root.d)
                            implicitHeight: Math.round(16 * root.d)
                            radius: 3
                            color: returnPct >= 0 ? Qt.alpha(IrisStyle.identity.green, 0.15) : Qt.alpha(IrisStyle.identity.red, 0.15)
                            Layout.alignment: Qt.AlignRight

                            IrisText {
                                id: badgeText
                                anchors.centerIn: parent
                                text: IndMoneyService.formatPct(parent.returnPct)
                                font.family: IrisStyle.fontNumbers
                                font.pixelSize: Math.round(9 * root.d)
                                font.weight: IrisStyle.weight(Font.Bold)
                                font.features: ({ "tnum": 1 })
                                color: parent.returnPct >= 0 ? IrisStyle.identity.green : IrisStyle.identity.red
                            }
                        }
                    }
                }
            }
        }
    }

    // =========================================================================
    // TAB 2: SIP Schedule & Liquidity
    // =========================================================================
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(6 * root.d)
        visible: root.activeTab === 2

        // Monthly Commitment Card with Liquidity Coverage Badge
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.round(50 * root.d)
            radius: IrisStyle.radiusTile
            color: root.rowBg

            RowLayout {
                anchors.fill: parent
                anchors.margins: Math.round(10 * root.d)

                ColumnLayout {
                    spacing: 0
                    IrisText {
                        text: Translation.tr("Monthly Commitment")
                        font.pixelSize: IrisStyle.typeFootnote
                        color: root.fgMuted
                    }
                    IrisText {
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

                    IrisText {
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

                            IrisText {
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
            implicitHeight: Math.min(Math.round(200 * root.d), contentHeight)
            clip: true
            spacing: Math.round(4 * root.d)

            model: IndMoneyService.sips.upcoming ?? []

            delegate: Rectangle {
                id: sipRow
                required property var modelData
                width: ListView.view.width
                implicitHeight: Math.round(38 * root.d)
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
                        implicitWidth: Math.round(44 * root.d)
                        implicitHeight: Math.round(20 * root.d)
                        radius: 4
                        color: IrisStyle.fillHover

                        IrisText {
                            anchors.centerIn: parent
                            text: String(sipRow.modelData.next_date ?? "").slice(0, 5)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(9.5 * root.d)
                            font.features: ({ "tnum": 1 })
                            color: root.fgMain
                        }
                    }

                    // Scheme / Stock Name
                    IrisText {
                        text: sipRow.modelData.name
                        font.pixelSize: IrisStyle.typeLabel
                        color: root.fgMain
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    // Amount
                    IrisText {
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

    // =========================================================================
    // TAB 3: Buckets & Drift (Optional: Enabled when buckets.enabled = true)
    // =========================================================================
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(8 * root.d)
        visible: root.activeTab === 3 && IndMoneyService.bucketsEnabled

        RowLayout {
            Layout.fillWidth: true
            IrisText {
                text: Translation.tr("Asset Allocation & Target Drift")
                font.weight: IrisStyle.weight(Font.DemiBold)
                font.pixelSize: IrisStyle.typeFootnote
                color: root.fgMuted
            }
            Item { Layout.fillWidth: true }
            IrisText {
                text: root.hoveredBucket
                    ? Translation.tr("%1: %2 · Target %3% · Drift %4%")
                        .arg(root.hoveredBucket.label)
                        .arg(IndMoneyService.formatInrCompact(root.hoveredBucket.current_value_inr, IndMoneyService.privacyMode))
                        .arg(root.hoveredBucket.target_pct)
                        .arg(root.hoveredBucket.drift_pct > 0 ? "+" + root.hoveredBucket.drift_pct : root.hoveredBucket.drift_pct)
                    : Translation.tr("Tolerance ±2.5%")
                font.pixelSize: Math.round(10 * root.d)
                color: root.hoveredBucket && !root.hoveredBucket.in_band ? IrisStyle.identity.orange : root.fgMuted
            }
        }

        Repeater {
            model: IndMoneyService.buckets

            delegate: Rectangle {
                id: bucketRow
                required property var modelData
                required property int index

                Layout.fillWidth: true
                implicitHeight: Math.round(36 * root.d)
                radius: IrisStyle.radiusTile
                color: bMouse.containsMouse ? root.rowBgHover : root.rowBg

                readonly property bool inBand: modelData.in_band
                readonly property color baseColor: IrisStyle.identity[modelData.palette_key] ?? IrisStyle.identity.blue
                readonly property color barColor: inBand ? baseColor : IrisStyle.identity.orange

                MouseArea {
                    id: bMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: root.hoveredBucket = bucketRow.modelData
                    onExited: {
                        if (root.hoveredBucket === bucketRow.modelData) root.hoveredBucket = null
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Math.round(10 * root.d)
                    anchors.rightMargin: Math.round(10 * root.d)
                    spacing: Math.round(8 * root.d)

                    IrisText {
                        text: bucketRow.modelData.label
                        font.pixelSize: Math.round(11 * root.d)
                        font.weight: IrisStyle.weight(Font.Medium)
                        color: bucketRow.barColor
                        Layout.preferredWidth: Math.round(95 * root.d)
                        elide: Text.ElideRight
                    }

                    // Bullet Bar Track
                    Rectangle {
                        id: barTrack
                        Layout.fillWidth: true
                        implicitHeight: Math.round(8 * root.d)
                        radius: 4
                        color: IrisStyle.fillHover

                        // Target Tolerance Band
                        Rectangle {
                            readonly property real tgt: bucketRow.modelData.target_pct
                            readonly property real minPct: Math.max(0, tgt - 2.5)
                            readonly property real maxPct: Math.min(100, tgt + 2.5)
                            x: (minPct / 100.0) * barTrack.width
                            width: Math.max(2, ((maxPct - minPct) / 100.0) * barTrack.width)
                            height: parent.height
                            radius: 4
                            color: Qt.rgba(bucketRow.baseColor.r, bucketRow.baseColor.g, bucketRow.baseColor.b, 0.20)
                        }

                        // Actual Value Bar
                        Rectangle {
                            height: parent.height
                            radius: 4
                            color: bucketRow.barColor
                            width: Math.min(barTrack.width, Math.max(0, (bucketRow.modelData.actual_pct / 100.0) * barTrack.width))
                        }

                        // Target Tick Marker
                        Rectangle {
                            x: Math.min(barTrack.width - 2, Math.max(0, (bucketRow.modelData.target_pct / 100.0) * barTrack.width - 1))
                            y: -Math.round(2 * root.d)
                            width: 2
                            height: parent.height + Math.round(4 * root.d)
                            color: IrisStyle.text
                            radius: 1
                        }
                    }

                    IrisText {
                        text: bucketRow.modelData.actual_pct.toFixed(1) + "%"
                        font.family: IrisStyle.fontNumbers
                        font.pixelSize: Math.round(10 * root.d)
                        font.weight: IrisStyle.weight(Font.DemiBold)
                        font.features: ({ "tnum": 1 })
                        color: bucketRow.barColor
                        Layout.preferredWidth: Math.round(38 * root.d)
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }
}
