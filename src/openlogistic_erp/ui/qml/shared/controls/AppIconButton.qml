pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../theme"

Item {
    id: root

    property string source: ""
    property int buttonSize: theme.controlHeightCompact
    property int iconSize: 18
    property color tintColor: theme.textPrimary
    property color hoverTintColor: root.tintColor
    property color disabledTintColor: theme.disabledText
    property color backgroundColor: "transparent"
    property color hoverBackgroundColor: theme.surfaceMid
    property color pressedBackgroundColor: theme.surfaceLow
    property color borderColor: "transparent"
    property int borderWidth: 0
    property int radius: theme.radiusMedium
    property string tooltipText: ""
    readonly property bool hovered: hoverHandler.hovered
    readonly property bool pressed: tapHandler.pressed

    signal clicked()

    implicitWidth: root.buttonSize
    implicitHeight: root.buttonSize
    opacity: root.enabled ? 1.0 : 0.64

    Theme {
        id: theme
    }

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: root.pressed
            ? root.pressedBackgroundColor
            : root.hovered && root.enabled ? root.hoverBackgroundColor : root.backgroundColor
        border.width: root.borderWidth
        border.color: root.borderColor
    }

    AppIcon {
        anchors.centerIn: parent
        size: root.iconSize
        source: root.source
        tintColor: !root.enabled
            ? root.disabledTintColor
            : root.hovered ? root.hoverTintColor : root.tintColor
    }

    HoverHandler {
        id: hoverHandler
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
        id: tapHandler
        enabled: root.enabled
        acceptedButtons: Qt.LeftButton
        onTapped: root.clicked()
    }

    ToolTip.delay: 550
    ToolTip.visible: root.enabled && root.hovered && root.tooltipText !== ""
    ToolTip.text: root.tooltipText
}
