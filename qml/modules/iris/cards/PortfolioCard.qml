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

    property bool drillDownOpen: false
    property string drillDownTab: "holdings" // "holdings", "sips"
    property string holdingFilter: "ALL" // "ALL", "core", "satellite", "gold_silver", "liquid", "legacy"
    property var hoveredBucket: null

    // Idle / OLED Care (M9): subtle opacity dimming on user inactivity
    readonly property bool isUserIdle: (typeof ScreenTime !== "undefined" && ScreenTime?.userIdle) || false
    opacity: isUserIdle ? 0.70 : 1.0
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

    // --- Keyboard Navigation (M7) ---
    Keys.onPressed: event => {
        if (event.key === Qt.Key_D) {
            root.drillDownOpen = !root.drillDownOpen
            event.accepted = true
        } else if (event.key === Qt.Key_1) {
            root.drillDownOpen = true
            root.drillDownTab = "holdings"
            event.accepted = true
        } else if (event.key === Qt.Key_2) {
            root.drillDownOpen = true
            root.drillDownTab = "sips"
            event.accepted = true
        } else if (event.key === Qt.Key_3) {
            root.drillDownOpen = !root.drillDownOpen
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
        } else if (event.key === Qt.Key_Tab && root.drillDownOpen) {
            if (root.drillDownTab === "holdings") {
                const filters = ["ALL", "core", "satellite", "gold_silver", "liquid"]
                const idx = filters.indexOf(root.holdingFilter)
                const nextIdx = (idx + 1) % filters.length
                root.holdingFilter = filters[nextIdx]
            } else {
                root.drillDownTab = "holdings"
            }
            event.accepted = true
        }
    }

    // Helper for 90-day Sparkline Polyline (C11)
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

    // --- Hero Platter with 90-Day Sparkline (M1, C8, C11, F3, M9) ---
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

        // 90-Day Daily Sparkline Shape (C11)
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

                // Primary Hero Figure: Basis Consistency with Pill (C8) + Privacy Crossfade (M8, V5)
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
                color: IrisStyle.subtext
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            IrisText {
                text: Translation.tr("Invested: %1 · Total Return: %2 (%3)")
                    .arg(IndMoneyService.formatInrCompact(root.investedVal, IndMoneyService.privacyMode))
                    .arg(IndMoneyService.formatPct(root.totalReturnPct))
                    .arg(IndMoneyService.formatInrCompact(root.totalReturnInr, IndMoneyService.privacyMode))
                font.pixelSize: IrisStyle.typeFootnote
                color: root.isTotalGain ? IrisStyle.identity.teal : IrisStyle.subtext
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }

    // --- Bento Grid Container ---
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(10 * root.d)

        // Tile 1 — Bucket Drift Strip (F1, M3, M4, V2)
        Rectangle {
            id: tile1
            Layout.fillWidth: true
            implicitHeight: bucketColumn.implicitHeight + Math.round(20 * root.d)
            radius: IrisStyle.radiusCard
            color: IrisStyle.surfaceHigh
            border.color: IrisStyle.hairline
            border.width: 1

            // Staggered Entrance (M4): 0ms delay on entrance, OutCubic; faster InCubic exit
            opacity: root.visible ? 1.0 : 0.0
            Behavior on opacity {
                SequentialAnimation {
                    PauseAnimation { duration: (root.visible && IrisStyle.motionEnabled) ? 0 : 0 }
                    NumberAnimation {
                        duration: IrisStyle.duration(root.visible ? 160 : 90)
                        easing.type: root.visible ? Easing.OutCubic : Easing.InCubic
                    }
                }
            }

            ColumnLayout {
                id: bucketColumn
                anchors.fill: parent
                anchors.margins: Math.round(12 * root.d)
                spacing: Math.round(8 * root.d)

                RowLayout {
                    Layout.fillWidth: true
                    IrisText {
                        text: Translation.tr("Asset Allocation & Target Drift")
                        font.weight: IrisStyle.weight(Font.DemiBold)
                        font.pixelSize: IrisStyle.typeFootnote
                        color: IrisStyle.subtext
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
                        color: root.hoveredBucket && !root.hoveredBucket.in_band ? IrisStyle.identity.orange : IrisStyle.muted
                    }
                }

                Repeater {
                    model: IndMoneyService.buckets

                    delegate: Item {
                        id: bucketRow
                        required property var modelData
                        required property int index

                        Layout.fillWidth: true
                        implicitHeight: Math.round(20 * root.d)

                        readonly property bool inBand: modelData.in_band
                        readonly property color baseColor: IrisStyle.identity[modelData.palette_key] ?? IrisStyle.identity.blue
                        readonly property color barColor: inBand ? baseColor : IrisStyle.identity.orange

                        HoverHandler {
                            onHoveredChanged: {
                                if (hovered) root.hoveredBucket = bucketRow.modelData
                                else if (root.hoveredBucket === bucketRow.modelData) root.hoveredBucket = null
                            }
                        }

                        RowLayout {
                            anchors.fill: parent
                            spacing: Math.round(8 * root.d)

                            IrisText {
                                text: bucketRow.modelData.label
                                font.pixelSize: Math.round(11 * root.d)
                                font.weight: IrisStyle.weight(Font.Medium)
                                color: bucketRow.barColor
                                Layout.preferredWidth: Math.round(95 * root.d)
                                elide: Text.ElideRight
                            }

                            // Bullet Bar Track with Tolerance Shading
                            Rectangle {
                                id: barTrack
                                Layout.fillWidth: true
                                implicitHeight: Math.round(8 * root.d)
                                radius: IrisStyle.radiusMicro
                                color: IrisStyle.fillQuiet

                                // Target Tolerance Band (±2.5%) Shading
                                Rectangle {
                                    readonly property real tgt: bucketRow.modelData.target_pct
                                    readonly property real minPct: Math.max(0, tgt - 2.5)
                                    readonly property real maxPct: Math.min(100, tgt + 2.5)
                                    x: (minPct / 100.0) * barTrack.width
                                    width: Math.max(2, ((maxPct - minPct) / 100.0) * barTrack.width)
                                    height: parent.height
                                    radius: IrisStyle.radiusMicro
                                    color: Qt.rgba(bucketRow.baseColor.r, bucketRow.baseColor.g, bucketRow.baseColor.b, 0.15)
                                }

                                // Actual Value Bar animated via IrisSpring (M3)
                                Rectangle {
                                    id: fillBar
                                    height: parent.height
                                    radius: IrisStyle.radiusMicro
                                    color: bucketRow.barColor
                                    width: Math.min(barTrack.width, Math.max(0, barSpring.value))

                                    IrisSpring {
                                        id: barSpring
                                        property var springSpec: IrisStyle.springFor("standard", "card")
                                        surface: "cards"
                                        intent: "move"
                                        animate: IrisStyle.motionEnabled && root.visible
                                        to: (bucketRow.modelData.actual_pct / 100.0) * barTrack.width
                                    }
                                }

                                // 2px Target Tick Marker Line
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

        // Tile 2 — Attention Feed (F2, C6, M4)
        Rectangle {
            id: tile2
            Layout.fillWidth: true
            implicitHeight: attentionColumn.implicitHeight + Math.round(20 * root.d)
            radius: IrisStyle.radiusCard
            color: IrisStyle.surfaceHigh
            border.color: IrisStyle.hairline
            border.width: 1

            // Staggered Entrance (M4): 40ms delay on entrance, OutCubic; faster InCubic exit
            opacity: root.visible ? 1.0 : 0.0
            Behavior on opacity {
                SequentialAnimation {
                    PauseAnimation { duration: (root.visible && IrisStyle.motionEnabled) ? 40 : 0 }
                    NumberAnimation {
                        duration: IrisStyle.duration(root.visible ? 160 : 90)
                        easing.type: root.visible ? Easing.OutCubic : Easing.InCubic
                    }
                }
            }

            ColumnLayout {
                id: attentionColumn
                anchors.fill: parent
                anchors.margins: Math.round(12 * root.d)
                spacing: Math.round(6 * root.d)

                RowLayout {
                    Layout.fillWidth: true
                    IrisText {
                        text: Translation.tr("Attention Feed")
                        font.weight: IrisStyle.weight(Font.DemiBold)
                        font.pixelSize: IrisStyle.typeFootnote
                        color: IrisStyle.subtext
                    }
                    Item { Layout.fillWidth: true }
                    IrisText {
                        text: Translation.tr("%1 Active").arg(IndMoneyService.attentionItems.length)
                        font.pixelSize: Math.round(10 * root.d)
                        color: IndMoneyService.attentionItems.length > 0 ? IrisStyle.identity.orange : IrisStyle.identity.teal
                    }
                }

                // Calm Empty State (Zero active alerts)
                RowLayout {
                    Layout.fillWidth: true
                    visible: IndMoneyService.attentionItems.length === 0
                    spacing: Math.round(6 * root.d)

                    MaterialSymbol {
                        text: "check_circle"
                        iconSize: Math.round(14 * root.d)
                        color: IrisStyle.identity.teal
                    }

                    IrisText {
                        text: Translation.tr("All buckets in band · Nothing needs you")
                        font.pixelSize: Math.round(11 * root.d)
                        color: IrisStyle.subtext
                    }
                }

                // Alert Items List
                Repeater {
                    model: IndMoneyService.attentionItems

                    delegate: RowLayout {
                        id: alertRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Math.round(8 * root.d)

                        readonly property color alertColor: IrisStyle.identity[modelData.palette_key] ?? IrisStyle.identity.orange

                        Rectangle {
                            implicitWidth: Math.round(6 * root.d)
                            implicitHeight: Math.round(6 * root.d)
                            radius: width / 2
                            color: alertRow.alertColor
                            Layout.alignment: Qt.AlignVCenter
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1

                            IrisText {
                                text: alertRow.modelData.title
                                font.pixelSize: Math.round(11 * root.d)
                                font.weight: IrisStyle.weight(Font.DemiBold)
                                color: alertRow.alertColor
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            IrisText {
                                text: alertRow.modelData.message
                                font.pixelSize: Math.round(10 * root.d)
                                color: IrisStyle.subtext
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }

        // Tile 3 — Next SIP & Cash Buffer (F4, C1, C7, M4)
        Rectangle {
            id: tile3
            Layout.fillWidth: true
            implicitHeight: sipColumn.implicitHeight + Math.round(20 * root.d)
            radius: IrisStyle.radiusCard
            color: IrisStyle.surfaceHigh
            border.color: IrisStyle.hairline
            border.width: 1

            // Staggered Entrance (M4): 80ms delay on entrance, OutCubic; faster InCubic exit
            opacity: root.visible ? 1.0 : 0.0
            Behavior on opacity {
                SequentialAnimation {
                    PauseAnimation { duration: (root.visible && IrisStyle.motionEnabled) ? 80 : 0 }
                    NumberAnimation {
                        duration: IrisStyle.duration(root.visible ? 160 : 90)
                        easing.type: root.visible ? Easing.OutCubic : Easing.InCubic
                    }
                }
            }

            ColumnLayout {
                id: sipColumn
                anchors.fill: parent
                anchors.margins: Math.round(12 * root.d)
                spacing: Math.round(8 * root.d)

                RowLayout {
                    Layout.fillWidth: true

                    IrisText {
                        text: Translation.tr("Upcoming SIPs & Liquidity")
                        font.weight: IrisStyle.weight(Font.DemiBold)
                        font.pixelSize: IrisStyle.typeFootnote
                        color: IrisStyle.subtext
                    }

                    Item { Layout.fillWidth: true }

                    // Liquidity Coverage Badge
                    Rectangle {
                        implicitHeight: Math.round(18 * root.d)
                        implicitWidth: coverageText.implicitWidth + Math.round(10 * root.d)
                        radius: IrisStyle.radiusChip
                        color: IrisStyle.trackOf(IndMoneyService.sips.sip_coverage_ok ? IrisStyle.identity.teal : IrisStyle.identity.orange)
                        border.color: IndMoneyService.sips.sip_coverage_ok ? IrisStyle.identity.teal : IrisStyle.identity.orange
                        border.width: 1

                        IrisText {
                            id: coverageText
                            anchors.centerIn: parent
                            text: Translation.tr("%1x Coverage")
                                .arg(IndMoneyService.sips.sip_coverage_ratio ?? 0)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(9 * root.d)
                            font.weight: IrisStyle.weight(Font.DemiBold)
                            color: IndMoneyService.sips.sip_coverage_ok ? IrisStyle.identity.teal : IrisStyle.identity.orange
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Math.round(12 * root.d)

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        IrisText {
                            text: IndMoneyService.sips.upcoming && IndMoneyService.sips.upcoming.length > 0
                                ? IndMoneyService.sips.upcoming[0].name
                                : Translation.tr("No Upcoming SIPs")
                            font.pixelSize: Math.round(11 * root.d)
                            font.weight: IrisStyle.weight(Font.Medium)
                            color: IrisStyle.text
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        IrisText {
                            text: IndMoneyService.sips.upcoming && IndMoneyService.sips.upcoming.length > 0
                                ? Translation.tr("Next: %1 · %2")
                                    .arg(IndMoneyService.sips.upcoming[0].next_date)
                                    .arg(IndMoneyService.formatInrCompact(IndMoneyService.sips.upcoming[0].amount_inr, IndMoneyService.privacyMode))
                                : Translation.tr("Monthly commitment: %1")
                                    .arg(IndMoneyService.formatInrCompact(IndMoneyService.sips.monthly_total_inr, IndMoneyService.privacyMode))
                            font.pixelSize: Math.round(10 * root.d)
                            color: IrisStyle.subtext
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    ColumnLayout {
                        spacing: 2
                        IrisText {
                            text: IndMoneyService.formatInrCompact(IndMoneyService.sips.next_7d_sip_inr, IndMoneyService.privacyMode)
                            font.family: IrisStyle.fontNumbers
                            font.pixelSize: Math.round(12 * root.d)
                            font.weight: IrisStyle.weight(Font.Bold)
                            color: IrisStyle.identity.teal
                            Layout.alignment: Qt.AlignRight
                        }

                        IrisText {
                            text: Translation.tr("Next 7 Days")
                            font.pixelSize: Math.round(9 * root.d)
                            color: IrisStyle.muted
                            Layout.alignment: Qt.AlignRight
                        }
                    }
                }
            }
        }
    }

    // --- Lazy-Loaded Drill-Down Drawer (V1, M8) ---
    IrisButton {
        Layout.fillWidth: true
        text: root.drillDownOpen
            ? Translation.tr("Hide Details & Schedule (D)")
            : Translation.tr("View Holdings & Schedule (D)")
        buttonRadius: IrisStyle.radiusTile
        quiet: true
        onClicked: root.drillDownOpen = !root.drillDownOpen
    }

    Loader {
        id: drillDownDrawer
        Layout.fillWidth: true
        active: root.visible && root.drillDownOpen
        visible: active

        sourceComponent: Component {
            Rectangle {
                implicitHeight: drawerLayout.implicitHeight + Math.round(16 * root.d)
                radius: IrisStyle.radiusPlate
                color: IrisStyle.readingPlate
                border.color: IrisStyle.hairline
                border.width: 1

                ColumnLayout {
                    id: drawerLayout
                    anchors.fill: parent
                    anchors.margins: Math.round(12 * root.d)
                    spacing: Math.round(10 * root.d)

                    // Tab selector between Holdings and SIP Schedule
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Math.round(6 * root.d)

                        IrisButton {
                            text: Translation.tr("Holdings (%1) [1]").arg((IndMoneyService.holdings || []).length)
                            quiet: root.drillDownTab !== "holdings"
                            buttonRadius: IrisStyle.radiusChip
                            onClicked: root.drillDownTab = "holdings"
                        }

                        IrisButton {
                            text: Translation.tr("SIP Schedule (%1) [2]").arg((IndMoneyService.sips.upcoming || []).length)
                            quiet: root.drillDownTab !== "sips"
                            buttonRadius: IrisStyle.radiusChip
                            onClicked: root.drillDownTab = "sips"
                        }

                        Item { Layout.fillWidth: true }
                    }

                    // --- VIEW 1: Holdings with Bucket Filters ---
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.drillDownTab === "holdings"
                        spacing: Math.round(8 * root.d)

                        // Bucket Filter Chips (Tab keyboard navigation)
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Math.round(6 * root.d)

                            Repeater {
                                model: ["ALL", "core", "satellite", "gold_silver", "liquid"]

                                delegate: IrisButton {
                                    required property string modelData
                                    text: modelData === "ALL" ? "ALL" : modelData.toUpperCase()
                                    quiet: root.holdingFilter !== modelData
                                    buttonRadius: IrisStyle.radiusChip
                                    onClicked: root.holdingFilter = modelData
                                }
                            }
                        }

                        // Holdings List
                        ListView {
                            id: holdingsList
                            Layout.fillWidth: true
                            implicitHeight: Math.min(Math.round(220 * root.d), contentHeight)
                            clip: true
                            spacing: Math.round(4 * root.d)

                            model: {
                                const raw = IndMoneyService.holdings || []
                                if (root.holdingFilter === "ALL") return raw
                                return raw.filter(h => h.bucket_id === root.holdingFilter)
                            }

                            delegate: Rectangle {
                                id: holdingRow
                                required property var modelData
                                width: holdingsList.width
                                implicitHeight: Math.round(38 * root.d)
                                radius: IrisStyle.radiusRow
                                color: holdingHover.hovered ? IrisStyle.fillHover : IrisStyle.fillQuiet

                                HoverHandler { id: holdingHover }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: Math.round(8 * root.d)
                                    spacing: Math.round(8 * root.d)

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 1

                                        IrisText {
                                            text: holdingRow.modelData.name
                                            font.pixelSize: Math.round(11 * root.d)
                                            font.weight: IrisStyle.weight(Font.Medium)
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }

                                        IrisText {
                                            text: (holdingRow.modelData.symbol ?? "") + " · " + (holdingRow.modelData.bucket_id ?? "").toUpperCase()
                                            font.pixelSize: Math.round(9 * root.d)
                                            color: IrisStyle.muted
                                        }
                                    }

                                    ColumnLayout {
                                        spacing: 1

                                        IrisText {
                                            text: IndMoneyService.formatInrCompact(holdingRow.modelData.current_value_inr, IndMoneyService.privacyMode)
                                            font.family: IrisStyle.fontNumbers
                                            font.pixelSize: Math.round(11 * root.d)
                                            font.weight: IrisStyle.weight(Font.Bold)
                                            Layout.alignment: Qt.AlignRight
                                        }

                                        IrisText {
                                            text: IndMoneyService.formatPct(holdingRow.modelData.one_day_change_pct)
                                            font.family: IrisStyle.fontNumbers
                                            font.pixelSize: Math.round(9 * root.d)
                                            font.weight: IrisStyle.weight(Font.DemiBold)
                                            color: (holdingRow.modelData.one_day_change_pct ?? 0) >= 0 ? IrisStyle.identity.green : IrisStyle.identity.red
                                            Layout.alignment: Qt.AlignRight
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // --- VIEW 2: Upcoming SIPs Schedule ---
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: root.drillDownTab === "sips"
                        spacing: Math.round(8 * root.d)

                        ListView {
                            id: sipsList
                            Layout.fillWidth: true
                            implicitHeight: Math.min(Math.round(220 * root.d), contentHeight)
                            clip: true
                            spacing: Math.round(4 * root.d)

                            model: IndMoneyService.sips.upcoming || []

                            delegate: Rectangle {
                                id: sipRow
                                required property var modelData
                                width: sipsList.width
                                implicitHeight: Math.round(38 * root.d)
                                radius: IrisStyle.radiusRow
                                color: sipHover.hovered ? IrisStyle.fillHover : IrisStyle.fillQuiet

                                HoverHandler { id: sipHover }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: Math.round(8 * root.d)
                                    spacing: Math.round(8 * root.d)

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 1

                                        IrisText {
                                            text: sipRow.modelData.name
                                            font.pixelSize: Math.round(11 * root.d)
                                            font.weight: IrisStyle.weight(Font.Medium)
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }

                                        IrisText {
                                            text: (sipRow.modelData.next_date ?? "") + " · " + (sipRow.modelData.frequency ?? "").toUpperCase() + " · " + (sipRow.modelData.class_id ?? "").toUpperCase()
                                            font.pixelSize: Math.round(9 * root.d)
                                            color: IrisStyle.muted
                                        }
                                    }

                                    ColumnLayout {
                                        spacing: 1

                                        IrisText {
                                            text: IndMoneyService.formatInrCompact(sipRow.modelData.amount_inr, IndMoneyService.privacyMode)
                                            font.family: IrisStyle.fontNumbers
                                            font.pixelSize: Math.round(11 * root.d)
                                            font.weight: IrisStyle.weight(Font.Bold)
                                            Layout.alignment: Qt.AlignRight
                                        }

                                        IrisText {
                                            text: sipRow.modelData.amount_usd ? ("$" + sipRow.modelData.amount_usd.toFixed(2)) : Translation.tr("Auto-Debit")
                                            font.pixelSize: Math.round(9 * root.d)
                                            color: IrisStyle.subtext
                                            Layout.alignment: Qt.AlignRight
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
