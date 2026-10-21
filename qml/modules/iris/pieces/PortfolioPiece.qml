pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.iris.style
import qs.modules.iris.components

Item {
    id: root

    property string kind: "portfolio"
    property string screenName: ""
    property bool plated: true
    property bool lane: true
    property bool hovered: false
    property bool pressed: false

    signal activated()

    readonly property real d: IrisStyle.density
    readonly property real investedVal: IndMoneyService.investedValue
    readonly property real dayPct: IndMoneyService.oneDayChangePct
    readonly property bool isGain: dayPct >= 0
    readonly property bool showDayPct: root.lane && ((hoverHandler.hovered || root.hovered) || !IndMoneyService.quietMode)

    // Attention / Status alert states (M6: calm status, no infinite loop at rest)
    readonly property bool hasAttention: IndMoneyService.attentionItems.length > 0
    readonly property bool isPartial: IndMoneyService.status === "partial"
    readonly property bool isStale: IndMoneyService.freshness === "stale"
    readonly property bool isAuthReq: IndMoneyService.status === "auth_required"
    readonly property bool isSyncing: IndMoneyService.syncing
    readonly property bool showStatusDot: root.hasAttention || root.isPartial || root.isStale || root.isAuthReq || root.isSyncing

    readonly property color statusDotColor: {
        if (root.isAuthReq) return IrisStyle.identity.red
        if (root.isPartial) return IrisStyle.identity.orange
        if (root.hasAttention || root.isStale) return IrisStyle.identity.yellow
        if (root.isSyncing) return IrisStyle.identity.sky
        return IrisStyle.identity.teal
    }

    // Fit seamlessly into iRiS Island bar geometry
    implicitWidth: root.lane
        ? Math.max(contentRow.implicitWidth + Math.round(12 * root.d), Math.round(36 * root.d))
        : Math.round(28 * root.d)
    implicitHeight: Math.round(28 * root.d)

    RowLayout {
        id: contentRow
        anchors.centerIn: parent
        spacing: Math.round(5 * root.d)

        // Native iRiS Material Symbol Glyph
        MaterialSymbol {
            text: "account_balance_wallet"
            iconSize: Math.round(15 * root.d)
            fill: root.hovered ? 1 : 0
            color: root.isAuthReq
                ? IrisStyle.danger
                : (root.hovered ? IrisStyle.accent : IrisStyle.identity.teal)
            Layout.alignment: Qt.AlignVCenter
            Behavior on color {
                ColorAnimation {
                    duration: IrisStyle.duration(120)
                    easing.type: IrisStyle.feedbackEasing
                }
            }
        }

        // Networth Amount: slot-rolling IrisNumber with zero-leak opacity crossfade (M2, M8, V5)
        Item {
            id: amountContainer
            visible: root.lane
            implicitWidth: Math.max(liveNumber.implicitWidth, maskText.implicitWidth)
            implicitHeight: Math.max(liveNumber.implicitHeight, maskText.implicitHeight)
            Layout.alignment: Qt.AlignVCenter

            // Live rolling figures (M2)
            IrisNumber {
                id: liveNumber
                anchors.centerIn: parent
                text: IndMoneyService.formatInrCompact(root.investedVal, false)
                family: IrisStyle.fontNumbers
                pixelSize: Math.round(11 * root.d)
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

            // Fixed-length mask (V5) - zero digit leak, opacity crossfade (M8)
            IrisText {
                id: maskText
                anchors.centerIn: parent
                text: IndMoneyService.staticMask
                font.family: IrisStyle.fontNumbers
                font.pixelSize: Math.round(11 * root.d)
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

        // 1D Return Chip (F3: hidden at rest in quietMode, smoothly revealed on hover)
        Item {
            id: dayChipContainer
            implicitWidth: dayText.implicitWidth
            implicitHeight: dayText.implicitHeight
            Layout.alignment: Qt.AlignVCenter
            opacity: root.showDayPct ? 1.0 : 0.0
            visible: root.lane && opacity > 0.01

            Behavior on opacity {
                NumberAnimation {
                    duration: IrisStyle.duration(140)
                    easing.type: IrisStyle.feedbackEasing
                }
            }

            IrisText {
                id: dayText
                anchors.centerIn: parent
                text: IndMoneyService.formatPct(root.dayPct)
                font.family: IrisStyle.fontNumbers
                font.pixelSize: Math.round(10 * root.d)
                font.weight: IrisStyle.weight(Font.Medium)
                font.features: ({ "tnum": 1 })
                color: root.isGain ? IrisStyle.identity.green : IrisStyle.identity.red
            }
        }

        // Calm Alert / Sync Indicator Dot (M6: calm status, no infinite loop at rest)
        Rectangle {
            id: statusDot
            implicitWidth: Math.round(5 * root.d)
            implicitHeight: Math.round(5 * root.d)
            radius: width / 2
            Layout.alignment: Qt.AlignVCenter
            visible: root.showStatusDot
            color: root.statusDotColor

            // Gentle pulse ONLY during active network sync, zero pulsing at rest
            SequentialAnimation on opacity {
                running: root.isSyncing && root.visible
                loops: Animation.Infinite
                NumberAnimation { to: 0.35; duration: 600; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 600; easing.type: Easing.InOutSine }
            }
        }
    }

    HoverHandler {
        id: hoverHandler
        onHoveredChanged: root.hovered = hovered
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        hoverEnabled: true

        onEntered: root.hovered = true
        onExited: root.hovered = false
        onPressed: mouse => { root.pressed = true }
        onReleased: mouse => { root.pressed = false }

        onClicked: mouse => {
            if (mouse.button === Qt.LeftButton) {
                root.activated()
            } else if (mouse.button === Qt.MiddleButton) {
                IndMoneyService.togglePrivacy()
            } else if (mouse.button === Qt.RightButton) {
                IndMoneyService.refresh()
            }
        }
    }
}
