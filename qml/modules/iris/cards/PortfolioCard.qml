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
    readonly property bool isTotalGain: totalReturnInr >= 0

    readonly property color fgMain: IrisStyle.text
    readonly property color fgMuted: IrisStyle.subtext
    readonly property color rowBg: IrisStyle.fillQuiet
    readonly property color rowBgHover: IrisStyle.fillHover

    // Interactive UI State
    property string expandedBucketId: ""
    property bool sipsExpanded: false
    property var hoveredBucket: null
    property int scrubbedSparkIdx: -1

    // Visible buckets (hide 0-target buckets when their value is 0, e.g. empty legacy)
    readonly property var visibleBuckets: {
        const list = IndMoneyService.buckets || []
        return list.filter(b => (b.target_pct > 0) || (b.current_value_inr > 0))
    }

    // Holdings grouped by bucket_id
    function holdingsForBucket(bId: string): var {
        const list = IndMoneyService.holdings || []
        return list.filter(h => (h.bucket_id || "core") === bId)
    }

    // Next upcoming SIP summary
    readonly property var nextSip: {
        const up = IndMoneyService.sips?.upcoming || []
        return up.length > 0 ? up[0] : null
    }

    // Top Attention Item (if any)
    readonly property var topAttention: {
        const items = IndMoneyService.attentionItems || []
        return items.length > 0 ? items[0] : null
    }

    // Freshness Status Color (dot is only visible when not fresh)
    readonly property bool isFresh: IndMoneyService.freshness === "fresh" && IndMoneyService.status === "ok"
    readonly property color freshnessColor: {
        const f = IndMoneyService.freshness
        if (f === "auth_required" || IndMoneyService.status === "auth_required") return IrisStyle.identity.red
        if (f === "partial" || IndMoneyService.status === "partial") return IrisStyle.identity.orange
        if (f === "stale") return IrisStyle.identity.yellow
        if (f === "aging") return IrisStyle.subtext
        return IrisStyle.identity.teal
    }

    // Idle / OLED Care
    readonly property bool isUserIdle: (typeof ScreenTime !== "undefined" && ScreenTime?.userIdle) || false
    opacity: isUserIdle ? 0.75 : 1.0
    Behavior on opacity {
        NumberAnimation {
            duration: IrisStyle.duration(240)
            easing.type: IrisStyle.feedbackEasing
        }
    }

    spacing: Math.round(8 * root.d)
    Layout.fillWidth: true
    focus: true

    onVisibleChanged: {
        if (visible) root.forceActiveFocus()
        else root.scrubbedSparkIdx = -1
    }

    Component.onCompleted: {
        if (visible) root.forceActiveFocus()
    }

    TapHandler {
        onTapped: root.forceActiveFocus()
    }

    // --- Keyboard-First Navigation ---
    Keys.onPressed: event => {
        const bList = root.visibleBuckets
        if (event.key >= Qt.Key_1 && event.key <= Qt.Key_5) {
            const idx = event.key - Qt.Key_1
            if (idx < bList.length) {
                const targetId = bList[idx].bucket_id
                root.expandedBucketId = (root.expandedBucketId === targetId ? "" : targetId)
                event.accepted = true
            }
        } else if (event.key === Qt.Key_S) {
            root.sipsExpanded = !root.sipsExpanded
            event.accepted = true
        } else if (event.key === Qt.Key_Escape) {
            root.expandedBucketId = ""
            root.sipsExpanded = false
            event.accepted = true
        } else if (event.key === Qt.Key_P) {
            IndMoneyService.togglePrivacy()
            event.accepted = true
        } else if (event.key === Qt.Key_R) {
            IndMoneyService.refresh()
            event.accepted = true
        }
    }

    // Sparkline coordinate generator (uses wealth_index when present to strip SIP deposit jumps)
    function generateSparklinePoints(pts: var, w: real, h: real): var {
        if (!pts || pts.length < 2 || w <= 0 || h <= 0) return { line: [], fill: [] }
        const metric = pt => (pt.wealth_index !== undefined && pt.wealth_index !== null) ? pt.wealth_index : pt.v
        let minVal = metric(pts[0])
        let maxVal = metric(pts[0])
        for (let i = 1; i < pts.length; i++) {
            const val = metric(pts[i])
            if (val < minVal) minVal = val
            if (val > maxVal) maxVal = val
        }
        let range = maxVal - minVal
        if (range <= 0.0001) range = 1.0

        const padTop = h * 0.18
        const padBottom = h * 0.12
        const availH = h - padTop - padBottom

        const linePoints = []
        const fillPoints = []
        const stepX = w / (pts.length - 1)

        fillPoints.push(Qt.point(0, h))
        for (let i = 0; i < pts.length; i++) {
            const x = i * stepX
            const normalized = (metric(pts[i]) - minVal) / range
            const y = padTop + availH * (1.0 - normalized)
            const pt = Qt.point(x, y)
            linePoints.push(pt)
            fillPoints.push(pt)
        }
        fillPoints.push(Qt.point(w, h))
        return { line: linePoints, fill: fillPoints }
    }

    // =========================================================================
    // 1. HEADER: Title + Subtle Freshness Dot + Privacy & Refresh
    // =========================================================================
    CardHeader {
        glyph: "account_balance_wallet"
        tint: IrisStyle.identity.teal
        title: Translation.tr("Portfolio")
        detail: IndMoneyService.navAsOf
            ? Translation.tr("NAV · %1").arg(IndMoneyService.navAsOf)
            : Translation.tr("Rules-Based Allocation")

        Rectangle {
            visible: !root.isFresh
            implicitWidth: Math.round(7 * root.d)
            implicitHeight: Math.round(7 * root.d)
            radius: width / 2
            color: root.freshnessColor
            Layout.alignment: Qt.AlignVCenter
        }

        IrisIconButton {
            materialIcon: IndMoneyService.privacyMode ? "visibility_off" : "lock_open"
            iconSize: Math.round(15 * root.d)
            Accessible.name: Translation.tr("Privacy Mode (P)")
            onClicked: IndMoneyService.togglePrivacy()
        }

        IrisIconButton {
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

    // =========================================================================
    // 2. HERO PLATTER: Big Invested Figure + 1-Line Subtitle + Interactive Scrub
    // =========================================================================
    Rectangle {
        id: heroPlatter
        Layout.fillWidth: true
        implicitHeight: Math.round(92 * root.d)
        radius: IrisStyle.radiusPlate
        color: IrisStyle.readingPlate
        border.color: heroMouse.containsMouse ? IrisStyle.hairlineStrong : IrisStyle.hairline
        border.width: 1
        clip: true

        readonly property var sparkData: IndMoneyService.sparkline90d || []
        readonly property bool isScrubbing: root.scrubbedSparkIdx >= 0 && root.scrubbedSparkIdx < sparkData.length
        readonly property var scrubbedPoint: isScrubbing ? sparkData[root.scrubbedSparkIdx] : null
        readonly property double displayVal: scrubbedPoint ? scrubbedPoint.v : root.investedVal
        readonly property string displayDate: scrubbedPoint ? scrubbedPoint.date : ""

        // Background 90-Day Sparkline
        Shape {
            id: sparklineShape
            anchors.fill: parent
            opacity: IndMoneyService.privacyMode ? 0.0 : (heroMouse.containsMouse ? 0.65 : 0.28)
            visible: opacity > 0.01

            Behavior on opacity {
                NumberAnimation {
                    duration: IrisStyle.duration(160)
                    easing.type: IrisStyle.feedbackEasing
                }
            }

            readonly property var pts: root.generateSparklinePoints(heroPlatter.sparkData, width, height)

            ShapePath {
                strokeColor: "transparent"
                strokeWidth: 0
                fillGradient: LinearGradient {
                    x1: 0; y1: 0; x2: 0; y2: sparklineShape.height
                    GradientStop {
                        position: 0.0
                        color: Qt.rgba(IrisStyle.identity.teal.r, IrisStyle.identity.teal.g, IrisStyle.identity.teal.b, 0.18)
                    }
                    GradientStop {
                        position: 1.0
                        color: Qt.rgba(IrisStyle.identity.teal.r, IrisStyle.identity.teal.g, IrisStyle.identity.teal.b, 0.0)
                    }
                }
                PathPolyline { path: sparklineShape.pts.fill }
            }

            ShapePath {
                strokeColor: IrisStyle.identity.teal
                strokeWidth: Math.max(1, Math.round(1.5 * root.d))
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathPolyline { path: sparklineShape.pts.line }
            }
        }

        // Interactive Scrubbing Crosshair & Node
        Rectangle {
            visible: heroPlatter.isScrubbing && !IndMoneyService.privacyMode && sparklineShape.pts.line.length > root.scrubbedSparkIdx
            x: visible ? sparklineShape.pts.line[root.scrubbedSparkIdx].x - 0.5 : 0
            y: 0
            width: 1
            height: parent.height
            color: Qt.rgba(IrisStyle.identity.teal.r, IrisStyle.identity.teal.g, IrisStyle.identity.teal.b, 0.45)

            Rectangle {
                width: Math.round(7 * root.d)
                height: width
                radius: width / 2
                x: -width / 2 + 0.5
                y: parent.visible ? sparklineShape.pts.line[root.scrubbedSparkIdx].y - height / 2 : 0
                color: IrisStyle.identity.teal
                border.color: IrisStyle.surfaceOpaque
                border.width: 1.5
            }
        }

        MouseArea {
            id: heroMouse
            anchors.fill: parent
            hoverEnabled: true
            onPositionChanged: mouse => {
                const count = heroPlatter.sparkData.length
                if (count > 1 && width > 0) {
                    const ratio = Math.max(0, Math.min(1, mouse.x / width))
                    root.scrubbedSparkIdx = Math.round(ratio * (count - 1))
                }
            }
            onExited: root.scrubbedSparkIdx = -1
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Math.round(14 * root.d)
            spacing: Math.round(4 * root.d)

            RowLayout {
                Layout.fillWidth: true
                spacing: Math.round(8 * root.d)

                Item {
                    implicitWidth: Math.max(heroNumber.implicitWidth, heroMask.implicitWidth)
                    implicitHeight: Math.max(heroNumber.implicitHeight, heroMask.implicitHeight)
                    Layout.alignment: Qt.AlignVCenter

                    IrisNumber {
                        id: heroNumber
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: IndMoneyService.formatInrFull(heroPlatter.displayVal, false)
                        family: IrisStyle.fontNumbers
                        pixelSize: IrisStyle.typeTitleLarge
                        weight: IrisStyle.weight(Font.Bold)
                        color: IrisStyle.text
                        opacity: IndMoneyService.privacyMode ? 0.0 : 1.0
                        visible: opacity > 0.01

                        Behavior on opacity {
                            NumberAnimation { duration: IrisStyle.duration(120); easing.type: IrisStyle.feedbackEasing }
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
                            NumberAnimation { duration: IrisStyle.duration(120); easing.type: IrisStyle.feedbackEasing }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // Total Return / Scrub Date Pill
                Rectangle {
                    implicitHeight: Math.round(20 * root.d)
                    implicitWidth: retPillText.implicitWidth + Math.round(10 * root.d)
                    radius: IrisStyle.radiusChip
                    color: heroPlatter.isScrubbing
                        ? IrisStyle.fillHover
                        : IrisStyle.trackOf(root.isTotalGain ? IrisStyle.identity.teal : IrisStyle.identity.orange)

                    IrisText {
                        id: retPillText
                        anchors.centerIn: parent
                        text: heroPlatter.isScrubbing
                            ? (heroPlatter.displayDate + (heroPlatter.scrubbedPoint?.return_pct !== undefined
                                ? " · " + IndMoneyService.formatPct(heroPlatter.scrubbedPoint.return_pct)
                                : ""))
                            : (IndMoneyService.formatPct(root.totalReturnPct)
                                + (IndMoneyService.portfolioOs?.xirr_pct
                                    ? " · XIRR " + Number(IndMoneyService.portfolioOs.xirr_pct).toFixed(1) + "%"
                                    : ""))
                        font.family: IrisStyle.fontNumbers
                        font.pixelSize: Math.round(10 * root.d)
                        font.weight: IrisStyle.weight(Font.DemiBold)
                        font.features: ({ "tnum": 1 })
                        color: heroPlatter.isScrubbing
                            ? root.fgMain
                            : (root.isTotalGain ? IrisStyle.identity.teal : IrisStyle.identity.orange)
                    }
                }
            }

            // Single Unified Muted Line
            IrisText {
                text: Translation.tr("Invested %1 · Gains %2 · Net Worth %3")
                    .arg(IndMoneyService.formatInrCompact(IndMoneyService.investedPortfolio?.invested_value_inr ?? 0, IndMoneyService.privacyMode))
                    .arg(IndMoneyService.formatInrCompact(root.totalReturnInr, IndMoneyService.privacyMode))
                    .arg(IndMoneyService.formatInrCompact(root.networthVal, IndMoneyService.privacyMode))
                font.pixelSize: IrisStyle.typeFootnote
                color: root.fgMuted
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }

    // =========================================================================
    // 3. BUCKET ROWS (THE BODY): Bullet Bars + Per-Bucket Band + Expandable Funds
    // =========================================================================
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(5 * root.d)

        RowLayout {
            Layout.fillWidth: true
            IrisText {
                text: Translation.tr("Strategic Buckets")
                font.weight: IrisStyle.weight(Font.DemiBold)
                font.pixelSize: IrisStyle.typeFootnote
                color: root.fgMuted
            }
            Item { Layout.fillWidth: true }
            IrisText {
                readonly property var hb: root.hoveredBucket
                readonly property real rebInr: hb
                    ? (hb.rebalance_inr ?? (((hb.target_pct - hb.actual_pct) / 100.0) * root.investedVal))
                    : 0
                text: hb
                    ? (hb.target_pct > 0
                        ? Translation.tr("%1 · Target %2% (±%3%) · %4 %5")
                            .arg(IndMoneyService.formatInrCompact(hb.current_value_inr, IndMoneyService.privacyMode))
                            .arg(hb.target_pct)
                            .arg(hb.band_pct ?? 2.5)
                            .arg(rebInr >= 0 ? Translation.tr("Buy") : Translation.tr("Trim"))
                            .arg(IndMoneyService.formatInrCompact(Math.abs(rebInr), IndMoneyService.privacyMode))
                        : Translation.tr("%1 · Unallocated / Legacy").arg(IndMoneyService.formatInrCompact(hb.current_value_inr, IndMoneyService.privacyMode)))
                    : Translation.tr("Click row or 1–5 to inspect funds")
                font.pixelSize: Math.round(9.5 * root.d)
                font.family: IrisStyle.fontNumbers
                font.features: ({ "tnum": 1 })
                color: hb && !hb.in_band ? IrisStyle.identity.orange : root.fgMuted
            }
        }

        Repeater {
            model: root.visibleBuckets

            delegate: ColumnLayout {
                id: bucketGroup
                required property var modelData
                required property int index

                Layout.fillWidth: true
                spacing: Math.round(3 * root.d)

                readonly property bool isExpanded: root.expandedBucketId === modelData.bucket_id
                readonly property bool inBand: modelData.in_band
                readonly property color baseColor: IrisStyle.identity[modelData.palette_key] ?? IrisStyle.identity.blue
                readonly property color barColor: inBand ? baseColor : IrisStyle.identity.orange
                readonly property var bucketHoldings: root.holdingsForBucket(modelData.bucket_id)

                // Primary Bucket Row
                Rectangle {
                    id: bucketRow
                    Layout.fillWidth: true
                    implicitHeight: Math.round(36 * root.d)
                    radius: IrisStyle.radiusRow
                    color: bMouse.containsMouse || bucketGroup.isExpanded ? root.rowBgHover : root.rowBg
                    border.color: bucketGroup.isExpanded
                        ? Qt.rgba(bucketGroup.barColor.r, bucketGroup.barColor.g, bucketGroup.barColor.b, 0.45)
                        : "transparent"
                    border.width: 1

                    MouseArea {
                        id: bMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: root.hoveredBucket = bucketGroup.modelData
                        onExited: {
                            if (root.hoveredBucket === bucketGroup.modelData) root.hoveredBucket = null
                        }
                        onClicked: {
                            const bId = bucketGroup.modelData.bucket_id
                            root.expandedBucketId = (root.expandedBucketId === bId ? "" : bId)
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Math.round(10 * root.d)
                        anchors.rightMargin: Math.round(10 * root.d)
                        spacing: Math.round(8 * root.d)

                        // Smoothly Rotating Chevron Indicator
                        MaterialSymbol {
                            text: "expand_more"
                            iconSize: Math.round(14 * root.d)
                            color: bucketGroup.barColor
                            rotation: bucketGroup.isExpanded ? 180 : 0
                            Behavior on rotation {
                                enabled: IrisStyle.motionEnabled
                                NumberAnimation {
                                    duration: IrisStyle.duration(180)
                                    easing.type: Easing.OutCubic
                                }
                            }
                        }

                        // Bucket Label
                        IrisText {
                            text: bucketGroup.modelData.label
                            font.pixelSize: Math.round(11 * root.d)
                            font.weight: IrisStyle.weight(Font.Medium)
                            color: root.fgMain
                            Layout.preferredWidth: Math.round(98 * root.d)
                            elide: Text.ElideRight
                        }

                        // Bullet Bar Track with Per-Bucket Band
                        Rectangle {
                            id: barTrack
                            Layout.fillWidth: true
                            implicitHeight: Math.round(8 * root.d)
                            radius: 4
                            color: IrisStyle.fill

                            // Dynamic Target Tolerance Band from modelData.band_pct
                            Rectangle {
                                readonly property real tgt: bucketGroup.modelData.target_pct
                                readonly property real band: bucketGroup.modelData.band_pct ?? 2.5
                                readonly property real minPct: Math.max(0, tgt - band)
                                readonly property real maxPct: Math.min(100, tgt + band)
                                visible: tgt > 0
                                x: (minPct / 100.0) * barTrack.width
                                width: Math.max(2, ((maxPct - minPct) / 100.0) * barTrack.width)
                                height: parent.height
                                radius: 4
                                color: Qt.rgba(bucketGroup.baseColor.r, bucketGroup.baseColor.g, bucketGroup.baseColor.b, 0.24)
                            }

                            // Actual Value Fill Bar
                            Rectangle {
                                height: parent.height
                                radius: 4
                                color: bucketGroup.barColor
                                width: Math.min(barTrack.width, Math.max(0, (bucketGroup.modelData.actual_pct / 100.0) * barTrack.width))

                                Behavior on width {
                                    enabled: IrisStyle.motionEnabled
                                    NumberAnimation {
                                        duration: IrisStyle.duration(220)
                                        easing.type: Easing.OutCubic
                                    }
                                }
                            }

                            // Target Tick Marker
                            Rectangle {
                                visible: bucketGroup.modelData.target_pct > 0
                                x: Math.min(barTrack.width - 2, Math.max(0, (bucketGroup.modelData.target_pct / 100.0) * barTrack.width - 1))
                                y: -Math.round(2 * root.d)
                                width: 2
                                height: parent.height + Math.round(4 * root.d)
                                color: IrisStyle.text
                                radius: 1
                            }
                        }

                        // Actual % + Out-of-Band Drift Badge
                        RowLayout {
                            spacing: Math.round(4 * root.d)
                            Layout.preferredWidth: Math.round(74 * root.d)

                            Item { Layout.fillWidth: true }

                            Rectangle {
                                visible: !bucketGroup.inBand
                                implicitHeight: Math.round(16 * root.d)
                                implicitWidth: driftTxt.implicitWidth + Math.round(6 * root.d)
                                radius: 3
                                color: Qt.alpha(IrisStyle.identity.orange, 0.16)

                                IrisText {
                                    id: driftTxt
                                    anchors.centerIn: parent
                                    readonly property real dp: bucketGroup.modelData.drift_pct
                                    text: (dp > 0 ? "+" : "") + dp.toFixed(1) + "%"
                                    font.family: IrisStyle.fontNumbers
                                    font.pixelSize: Math.round(8.5 * root.d)
                                    font.weight: IrisStyle.weight(Font.Bold)
                                    font.features: ({ "tnum": 1 })
                                    color: IrisStyle.identity.orange
                                }
                            }

                            IrisText {
                                text: bucketGroup.modelData.actual_pct.toFixed(1) + "%"
                                font.family: IrisStyle.fontNumbers
                                font.pixelSize: Math.round(10.5 * root.d)
                                font.weight: IrisStyle.weight(Font.DemiBold)
                                font.features: ({ "tnum": 1 })
                                color: bucketGroup.inBand ? root.fgMain : IrisStyle.identity.orange
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }
                }

                // Smooth Accordion Wrapper for Inline Funds Drawer
                Item {
                    Layout.fillWidth: true
                    Layout.leftMargin: Math.round(14 * root.d)
                    clip: true
                    implicitHeight: bucketGroup.isExpanded ? drawerCol.implicitHeight : 0
                    opacity: bucketGroup.isExpanded ? 1.0 : 0.0
                    visible: implicitHeight > 0.5

                    Behavior on implicitHeight {
                        enabled: IrisStyle.motionEnabled
                        NumberAnimation {
                            duration: IrisStyle.duration(200)
                            easing.type: Easing.OutCubic
                        }
                    }
                    Behavior on opacity {
                        enabled: IrisStyle.motionEnabled
                        NumberAnimation {
                            duration: IrisStyle.duration(160)
                            easing.type: Easing.OutCubic
                        }
                    }

                    ColumnLayout {
                        id: drawerCol
                        width: parent.width
                        spacing: Math.round(3 * root.d)

                        // Empty bucket placeholder when 0 holdings are mapped
                        Rectangle {
                            visible: bucketGroup.bucketHoldings.length === 0
                            Layout.fillWidth: true
                            implicitHeight: Math.round(30 * root.d)
                            radius: IrisStyle.radiusChip
                            color: IrisStyle.surfaceHigh

                            IrisText {
                                anchors.centerIn: parent
                                text: Translation.tr("No holdings mapped to this bucket")
                                font.pixelSize: IrisStyle.typeFootnote
                                color: root.fgMuted
                            }
                        }

                        Repeater {
                            model: bucketGroup.bucketHoldings

                            delegate: Rectangle {
                                id: fundRow
                                required property var modelData
                                Layout.fillWidth: true
                                implicitHeight: Math.round(34 * root.d)
                                radius: IrisStyle.radiusChip
                                color: IrisStyle.surfaceHigh
                                clip: true

                                // Subtle Intra-Bucket Share Progress Fill
                                Rectangle {
                                    width: bucketGroup.modelData.current_value_inr > 0
                                        ? parent.width * Math.min(1.0, fundRow.modelData.current_value_inr / bucketGroup.modelData.current_value_inr)
                                        : 0
                                    height: parent.height
                                    color: Qt.rgba(bucketGroup.baseColor.r, bucketGroup.baseColor.g, bucketGroup.baseColor.b, 0.08)
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Math.round(10 * root.d)
                                    anchors.rightMargin: Math.round(10 * root.d)
                                    spacing: Math.round(8 * root.d)

                                    IrisText {
                                        text: fundRow.modelData.name
                                        font.pixelSize: IrisStyle.typeFootnote
                                        font.weight: IrisStyle.weight(Font.Medium)
                                        color: root.fgMain
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }

                                    IrisText {
                                        text: IndMoneyService.formatInrCompact(fundRow.modelData.current_value_inr, IndMoneyService.privacyMode)
                                        font.family: IrisStyle.fontNumbers
                                        font.pixelSize: Math.round(10 * root.d)
                                        font.weight: IrisStyle.weight(Font.DemiBold)
                                        font.features: ({ "tnum": 1 })
                                        color: root.fgMain
                                    }

                                    Rectangle {
                                        readonly property real rPct: fundRow.modelData.total_return_pct ?? 0
                                        implicitWidth: fRetText.implicitWidth + Math.round(8 * root.d)
                                        implicitHeight: Math.round(16 * root.d)
                                        radius: 3
                                        color: rPct >= 0 ? Qt.alpha(IrisStyle.identity.green, 0.14) : Qt.alpha(IrisStyle.identity.red, 0.14)

                                        IrisText {
                                            id: fRetText
                                            anchors.centerIn: parent
                                            text: IndMoneyService.formatPct(parent.rPct)
                                            font.family: IrisStyle.fontNumbers
                                            font.pixelSize: Math.round(8.5 * root.d)
                                            font.weight: IrisStyle.weight(Font.Bold)
                                            font.features: ({ "tnum": 1 })
                                            color: parent.rPct >= 0 ? IrisStyle.identity.green : IrisStyle.identity.red
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

    // =========================================================================
    // 4. FOOTER STRIP: Calm Band Status / Attention + Next SIP Expander
    // =========================================================================
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Math.round(4 * root.d)

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.round(32 * root.d)
            radius: IrisStyle.radiusRow
            color: footerMouse.containsMouse || root.sipsExpanded ? root.rowBgHover : root.rowBg

            MouseArea {
                id: footerMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.sipsExpanded = !root.sipsExpanded
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Math.round(10 * root.d)
                anchors.rightMargin: Math.round(10 * root.d)
                spacing: Math.round(6 * root.d)

                MaterialSymbol {
                    text: root.topAttention ? "warning" : "verified"
                    iconSize: Math.round(13 * root.d)
                    color: root.topAttention ? IrisStyle.identity.orange : IrisStyle.identity.teal
                }

                IrisText {
                    text: root.topAttention
                        ? root.topAttention.title
                        : (IndMoneyService.portfolioOs?.rebalance_action
                            ? IndMoneyService.portfolioOs.rebalance_action
                            : Translation.tr("All buckets in band"))
                    font.pixelSize: IrisStyle.typeFootnote
                    font.weight: IrisStyle.weight(Font.Medium)
                    color: root.topAttention ? IrisStyle.identity.orange : root.fgMuted
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // Next SIP Summary Pill
                IrisText {
                    visible: root.nextSip !== null
                    text: root.nextSip
                        ? Translation.tr("Next SIP %1 · %2")
                            .arg(IndMoneyService.formatInrCompact(root.nextSip.amount_inr, IndMoneyService.privacyMode))
                            .arg(String(root.nextSip.next_date ?? "").slice(5))
                        : ""
                    font.family: IrisStyle.fontNumbers
                    font.pixelSize: IrisStyle.typeFootnote
                    font.features: ({ "tnum": 1 })
                    color: (IndMoneyService.sips?.sip_coverage_ok ?? true) ? IrisStyle.identity.teal : IrisStyle.identity.orange
                }

                MaterialSymbol {
                    text: "keyboard_arrow_down"
                    iconSize: Math.round(14 * root.d)
                    color: root.fgMuted
                    rotation: root.sipsExpanded ? 180 : 0
                    Behavior on rotation {
                        enabled: IrisStyle.motionEnabled
                        NumberAnimation {
                            duration: IrisStyle.duration(180)
                            easing.type: Easing.OutCubic
                        }
                    }
                }
            }
        }

        // Smooth Accordion Wrapper for Expandable SIP Schedule Drawer
        Item {
            Layout.fillWidth: true
            clip: true
            implicitHeight: root.sipsExpanded ? sipsDrawerCol.implicitHeight : 0
            opacity: root.sipsExpanded ? 1.0 : 0.0
            visible: implicitHeight > 0.5

            Behavior on implicitHeight {
                enabled: IrisStyle.motionEnabled
                NumberAnimation {
                    duration: IrisStyle.duration(200)
                    easing.type: Easing.OutCubic
                }
            }
            Behavior on opacity {
                enabled: IrisStyle.motionEnabled
                NumberAnimation {
                    duration: IrisStyle.duration(160)
                    easing.type: Easing.OutCubic
                }
            }

            ColumnLayout {
                id: sipsDrawerCol
                width: parent.width
                spacing: Math.round(3 * root.d)

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: Math.round(6 * root.d)
                    Layout.rightMargin: Math.round(6 * root.d)

                    IrisText {
                        text: Translation.tr("Monthly SIPs: %1 (%2 active)")
                            .arg(IndMoneyService.formatInrCompact(IndMoneyService.sips?.monthly_total_inr ?? 0, IndMoneyService.privacyMode))
                            .arg(IndMoneyService.sips?.active_count ?? 0)
                        font.pixelSize: Math.round(9.5 * root.d)
                        color: root.fgMuted
                    }

                    Item { Layout.fillWidth: true }

                    IrisText {
                        readonly property bool covOk: IndMoneyService.sips?.sip_coverage_ok ?? true
                        text: covOk
                            ? Translation.tr("Bank Buffer: %1 (%2x 7D SIPs)")
                                .arg(IndMoneyService.formatInrCompact(root.bankVal, IndMoneyService.privacyMode))
                                .arg(IndMoneyService.sips?.sip_coverage_ratio ?? 0)
                            : Translation.tr("Low Bank Buffer: %1").arg(IndMoneyService.formatInrCompact(root.bankVal, IndMoneyService.privacyMode))
                        font.pixelSize: Math.round(9.5 * root.d)
                        color: covOk ? IrisStyle.identity.teal : IrisStyle.identity.orange
                    }
                }

                Repeater {
                    model: IndMoneyService.sips?.upcoming ?? []

                    delegate: Rectangle {
                        id: sipDelegate
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: Math.round(30 * root.d)
                        radius: IrisStyle.radiusChip
                        color: IrisStyle.surfaceHigh

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Math.round(10 * root.d)
                            anchors.rightMargin: Math.round(10 * root.d)
                            spacing: Math.round(8 * root.d)

                            IrisText {
                                text: String(sipDelegate.modelData.next_date ?? "").slice(5)
                                font.family: IrisStyle.fontNumbers
                                font.pixelSize: Math.round(9.5 * root.d)
                                font.features: ({ "tnum": 1 })
                                color: IrisStyle.identity.teal
                                Layout.preferredWidth: Math.round(38 * root.d)
                            }

                            IrisText {
                                text: sipDelegate.modelData.name
                                font.pixelSize: IrisStyle.typeFootnote
                                color: root.fgMain
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            IrisText {
                                text: IndMoneyService.formatInrCompact(sipDelegate.modelData.amount_inr, IndMoneyService.privacyMode)
                                font.family: IrisStyle.fontNumbers
                                font.pixelSize: Math.round(10 * root.d)
                                font.weight: IrisStyle.weight(Font.DemiBold)
                                font.features: ({ "tnum": 1 })
                                color: root.fgMain
                            }
                        }
                    }
                }
            }
        }
    }
}
