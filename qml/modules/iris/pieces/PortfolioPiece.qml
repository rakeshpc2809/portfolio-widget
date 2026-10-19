pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell
import qs.services
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
    readonly property real networth: summary.total_networth_inr ?? 0
    readonly property real dayPct: summary.day_change_pct ?? 0
    readonly property real dayInr: summary.day_change_inr ?? 0
    readonly property bool isGain: dayPct >= 0

    implicitWidth: pillRow.implicitWidth + Math.round(16 * root.d)
    implicitHeight: Math.round(28 * root.d)

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: height / 2
        color: root.pressed
            ? IrisStyle.fillPressed
            : (root.hovered ? IrisStyle.fillHover : (root.plated ? IrisStyle.fillSecondary : "transparent"))
        border.width: 1
        border.color: root.hovered ? IrisStyle.outline : IrisStyle.outlineVariant
        Behavior on color { ColorAnimation { duration: IrisStyle.duration(120); easing.type: IrisStyle.feedbackEasing } }
        Behavior on border.color { ColorAnimation { duration: IrisStyle.duration(120); easing.type: IrisStyle.feedbackEasing } }
    }

    RowLayout {
        id: pillRow
        anchors.centerIn: parent
        spacing: Math.round(6 * root.d)

        // Glyph / Icon
        Text {
            text: "◈"
            font.pixelSize: Math.round(12 * root.d)
            font.family: "JetBrains Mono Nerd Font"
            color: IrisStyle.accent
            Layout.alignment: Qt.AlignVCenter
        }

        // Networth Amount with Gaussian Blur Privacy Effect
        Item {
            id: networthContainer
            implicitWidth: rawNetworthText.implicitWidth
            implicitHeight: rawNetworthText.implicitHeight
            Layout.alignment: Qt.AlignVCenter

            Text {
                id: rawNetworthText
                anchors.centerIn: parent
                text: IndMoneyService.formatInrCompact(root.networth, false)
                font.family: "JetBrains Mono Nerd Font"
                font.pixelSize: Math.round(11 * root.d)
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
                color: IrisStyle.text
                visible: !IndMoneyService.privacyMode
            }

            Text {
                id: maskedNetworthText
                anchors.centerIn: parent
                text: "₹••.••L"
                font.family: "JetBrains Mono Nerd Font"
                font.pixelSize: Math.round(11 * root.d)
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
                color: IrisStyle.muted
                visible: IndMoneyService.privacyMode
            }

            MultiEffect {
                source: rawNetworthText
                anchors.fill: rawNetworthText
                blurEnabled: true
                blur: IndMoneyService.privacyMode ? 1.0 : 0.0
                opacity: IndMoneyService.privacyMode ? 0.3 : 1.0
                visible: IndMoneyService.privacyMode
                Behavior on blur {
                    NumberAnimation {
                        duration: 180
                        easing.type: Easing.InOutCubic
                    }
                }
                Behavior on opacity {
                    NumberAnimation {
                        duration: 180
                        easing.type: Easing.InOutCubic
                    }
                }
            }
        }

        // 1D Return Badge
        RowLayout {
            spacing: Math.round(2 * root.d)
            Layout.alignment: Qt.AlignVCenter

            Text {
                text: root.isGain ? "▲" : "▼"
                font.pixelSize: Math.round(8 * root.d)
                color: root.isGain ? "#10b981" : "#f43f5e"
            }

            Text {
                text: IndMoneyService.formatPct(root.dayPct)
                font.family: "JetBrains Mono Nerd Font"
                font.pixelSize: Math.round(10 * root.d)
                font.weight: Font.Medium
                font.features: { "tnum": 1 }
                color: root.isGain ? "#10b981" : "#f43f5e"
            }
        }

        // Ambient Market Status Indicator Dot
        Rectangle {
            id: statusDot
            implicitWidth: Math.round(6 * root.d)
            implicitHeight: Math.round(6 * root.d)
            radius: width / 2
            Layout.alignment: Qt.AlignVCenter

            readonly property bool isOpen: IndMoneyService.marketState === "IN_OPEN" || IndMoneyService.marketState === "US_OPEN"
            readonly property bool isAuthReq: IndMoneyService.status === "auth_required"
            readonly property bool isSync: IndMoneyService.syncing

            color: isAuthReq
                ? "#f59e0b" // Amber
                : (isSync
                    ? "#38bdf8" // Sky
                    : (isOpen ? "#10b981" : "#64748b")) // Emerald or Dimmed

            // Ambient pulsing animation when open or syncing
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
