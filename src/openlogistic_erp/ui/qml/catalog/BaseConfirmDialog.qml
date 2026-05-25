pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../shared/controls"
import "../shared/surfaces"
import "../shared/theme"

Item {
    id: root

    property bool open: false
    property string title: ""
    property string message: ""
    property var buttons: []
    property bool closeOnOverlayClick: true

    signal actionRequested(string role)
    signal dismissed()

    visible: open
    z: 50

    Theme {
        id: theme
    }

    Rectangle {
        anchors.fill: parent
        color: theme.alpha(theme.textPrimary, 0.22)

        MouseArea {
            anchors.fill: parent
            onClicked: {
                if (root.closeOnOverlayClick) {
                    root.dismissed()
                }
            }
        }
    }

    SurfaceCard {
        anchors.centerIn: parent
        width: Math.min(460, root.width - theme.spacing8)
        height: Math.max(180, dialogLayout.implicitHeight + theme.spacing12)
        padding: theme.spacing6
        subtleBorder: true
        tone: "raised"

        ColumnLayout {
            id: dialogLayout

            anchors.fill: parent
            spacing: theme.spacing4

            Label {
                Layout.fillWidth: true
                text: root.title
                color: theme.textPrimary
                font.family: theme.headlineFontFamily
                font.pixelSize: theme.sectionTitleSize
                font.bold: true
                wrapMode: Text.WordWrap
            }

            Label {
                Layout.fillWidth: true
                text: root.message
                color: theme.textSecondary
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.bodySize
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing3

                Item {
                    Layout.fillWidth: true
                }

                Repeater {
                    model: root.buttons

                    delegate: AppButton {
                        id: buttonDelegate

                        required property var modelData

                        visible: buttonDelegate.modelData.visible === undefined ? true : Boolean(buttonDelegate.modelData.visible)
                        variant: buttonDelegate.modelData.variant || "secondary"
                        text: buttonDelegate.modelData.text || ""
                        enabled: buttonDelegate.modelData.enabled === undefined ? true : Boolean(buttonDelegate.modelData.enabled)
                        onClicked: root.actionRequested(String(buttonDelegate.modelData.role || ""))
                    }
                }
            }
        }
    }
}
