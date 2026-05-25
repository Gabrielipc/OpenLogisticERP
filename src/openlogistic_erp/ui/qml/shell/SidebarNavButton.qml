pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../shared/controls"
import "../shared/theme"

Button {
    id: control

    property string badgeText: ""
    property string subtitle: ""
    property string iconSource: ""
    property bool collapsed: false

    Theme {
        id: theme
    }

    implicitHeight: control.collapsed ? 46 : (subtitle !== "" ? 62 : 54)
    leftPadding: control.collapsed ? 0 : theme.spacing3
    rightPadding: control.collapsed ? 0 : theme.spacing3
    topPadding: control.collapsed ? 0 : theme.spacing3
    bottomPadding: control.collapsed ? 0 : theme.spacing3
    ToolTip.delay: 550
    ToolTip.visible: control.collapsed && control.hovered && control.text !== ""
    ToolTip.text: control.text

    contentItem: RowLayout {
        spacing: control.collapsed ? 0 : theme.spacing3

        Rectangle {
            Layout.preferredWidth: 34
            Layout.preferredHeight: 34
            Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
            radius: 17
            color: control.checked ? theme.surfaceRaised : theme.primaryFixed

            Label {
                anchors.centerIn: parent
                visible: control.iconSource === ""
                text: control.badgeText
                color: control.checked ? theme.primary : theme.textPrimary
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.captionSize
                font.bold: true
            }

            AppIcon {
                anchors.centerIn: parent
                width: 18
                height: 18
                size: 18
                visible: control.iconSource !== ""
                source: control.iconSource
                tintColor: control.checked ? theme.primary : theme.textPrimary
            }
        }

        ColumnLayout {
            visible: !control.collapsed
            Layout.fillWidth: true
            spacing: 1

            Label {
                Layout.fillWidth: true
                text: control.text
                elide: Text.ElideRight
                color: control.checked ? theme.textOnPrimary : theme.textPrimary
                font.family: theme.headlineFontFamily
                font.pixelSize: theme.bodySize
                font.bold: true
            }

            Label {
                visible: control.subtitle !== ""
                Layout.fillWidth: true
                text: control.subtitle
                elide: Text.ElideRight
                color: control.checked ? theme.textOnPrimaryMuted : theme.textSecondary
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.captionSize
            }
        }
    }

    background: Rectangle {
        radius: theme.radiusPill
        color: control.checked ? theme.primary : control.hovered ? theme.surfaceMid : "transparent"
    }
}
