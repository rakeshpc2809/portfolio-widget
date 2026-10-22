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

    // Calm Status Indicator: only visible when something needs attention or is actively syncing
    readonly property bool hasAttention: IndMoneyService.attentionItems.length > 0
    readonly property bool isPartial: IndMoneyService.status === "partial"
    readonly property bool isStale: IndMoneyService.freshness === "stale"
    readonly property bool isAuthReq: IndMoneyService.status === "auth_required"
    readonly property bool isSyncing: IndMoneyService.syncing
    readonly property bool showStatusDot: root.hasAttention || root.isPartial || root.isStale || root.isAuthReq || root.isSyncing

    readonly property color statusDotColor: {
        if (root.isAuthReq) return IrisStyle.identity.red
        if (root.isPartial || root.hasAttention) return IrisStyle.identity.orange
        if (root.isStale) return IrisStyle.identity.yellow
        if (root.isSyncing) return IrisStyle.identity.sky
        return IrisStyle.identity.teal
    }

    implicitWidth: root.lane
        ? Math.max(contentRow.implicitWidth + Math.round(12 * root.d), Math.round(36 * root.d))
        : Math.round(28 * root.d)
    implicitHeight: Math.round(28 * root.d)

    RowLayout {
        id: contentRow
        anchors.centerIn: parent
        spacing: Math.round(5 * root.d)

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

        Item {
            id: amountContainer
            visible: root.lane
            implicitWidth: Math.max(liveNumber.implicitWidth, maskText.implicitWidth)
            implicitHeight: Math.max(liveNumber.implicitHeight, maskText.implicitHeight)
            Layout.alignment: Qt.AlignVCenter

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

        Rectangle {
            id: statusDot
            implicitWidth: Math.round(5 * root.d)
            implicitHeight: Math.round(5 * root.d)
            radius: width / 2
            Layout.alignment: Qt.AlignVCenter
            visible: root.showStatusDot
            color: root.statusDotColor

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
        acceptedButtons: Qt.MiddleButton | Qt.RightButton

        onClicked: mouse => {
            if (mouse.button === Qt.MiddleButton) {
                IndMoneyService.togglePrivacy()
            } else if (mouse.button === Qt.RightButton) {
                IndMoneyService.refresh()
            }
        }
    }
}
