pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.iris.style

Item {
    id: root

    property string kind: "portfolio"
    property string screenName: ""
    property bool plated: true
    property bool hovered: false
    property bool pressed: false

    signal activated()

    readonly property real d: IrisStyle.density
    readonly property var summary: IndMoneyService.summary
    readonly property real networth: summary.total_portfolio_inr ?? summary.total_networth_inr ?? 0
    readonly property real dayPct: summary.day_change_pct ?? 0
    readonly property real dayInr: summary.day_change_inr ?? 0
    readonly property bool isGain: dayPct >= 0

    // Fit seamlessly into iRiS Island width and height
    implicitWidth: Math.max(contentRow.implicitWidth + Math.round(12 * root.d), Math.round(36 * root.d))
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
            color: IndMoneyService.status === "auth_required"
                ? IrisStyle.danger
                : (root.hovered ? IrisStyle.accent : IrisStyle.identity.teal)
            Layout.alignment: Qt.AlignVCenter
            Behavior on color { ColorAnimation { duration: IrisStyle.duration(120); easing.type: IrisStyle.feedbackEasing } }
        }

        // Networth Amount formatted with iRiS numbers font & Gaussian blur privacy
        Item {
            implicitWidth: networthText.implicitWidth
            implicitHeight: networthText.implicitHeight
            Layout.alignment: Qt.AlignVCenter

            Text {
                id: networthText
                anchors.centerIn: parent
                text: IndMoneyService.formatInrCompact(root.networth, false)
                font.family: IrisStyle.fontNumbers
                font.pixelSize: Math.round(11 * root.d)
                font.weight: IrisStyle.weight(Font.Bold)
                font.features: ({ "tnum": 1 })
                color: IrisStyle.text
                visible: !IndMoneyService.privacyMode
            }

            Text {
                anchors.centerIn: parent
                text: "₹••.••L"
                font.family: IrisStyle.fontNumbers
                font.pixelSize: Math.round(11 * root.d)
                font.weight: IrisStyle.weight(Font.Bold)
                font.features: ({ "tnum": 1 })
                color: IrisStyle.subtext
                visible: IndMoneyService.privacyMode
            }

            MultiEffect {
                source: networthText
                anchors.fill: networthText
                blurEnabled: true
                blur: IndMoneyService.privacyMode ? 1.0 : 0.0
                opacity: IndMoneyService.privacyMode ? 0.25 : 1.0
                visible: IndMoneyService.privacyMode
                Behavior on blur { NumberAnimation { duration: 180; easing.type: Easing.InOutCubic } }
                Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.InOutCubic } }
            }
        }

        // 1D Return Chip (subtle, no heavy border)
        Text {
            text: IndMoneyService.formatPct(root.dayPct)
            font.family: IrisStyle.fontNumbers
            font.pixelSize: Math.round(10 * root.d)
            font.weight: IrisStyle.weight(Font.Medium)
            font.features: ({ "tnum": 1 })
            color: root.isGain ? IrisStyle.identity.green : IrisStyle.identity.red
            Layout.alignment: Qt.AlignVCenter
        }

        // Ambient Market Status Indicator Dot
        Rectangle {
            id: statusDot
            implicitWidth: Math.round(5 * root.d)
            implicitHeight: Math.round(5 * root.d)
            radius: width / 2
            Layout.alignment: Qt.AlignVCenter

            readonly property bool isOpen: IndMoneyService.marketState === "IN_OPEN" || IndMoneyService.marketState === "US_OPEN"
            readonly property bool isAuthReq: IndMoneyService.status === "auth_required"
            readonly property bool isSync: IndMoneyService.syncing

            color: isAuthReq
                ? IrisStyle.identity.orange
                : (isSync
                    ? IrisStyle.identity.sky
                    : (isOpen ? IrisStyle.identity.green : IrisStyle.subtext))

            SequentialAnimation on opacity {
                running: statusDot.isOpen || statusDot.isSync
                loops: Animation.Infinite
                NumberAnimation { to: 0.35; duration: 900; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutSine }
            }
        }
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
