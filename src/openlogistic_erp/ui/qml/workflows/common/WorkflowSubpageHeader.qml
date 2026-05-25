pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../shared/controls"
import "../../shared/theme"

Item {
    id: root

    property string baseTitle: ""
    property string currentTitle: ""
    property string subtitle: ""
    property bool showCancel: false
    property bool showDangerAction: false
    property bool showClose: true
    property string closeText: qsTr("Cerrar")
    property string dangerActionText: qsTr("Eliminar")

    signal navigateBackRequested()
    signal cancelRequested()
    signal closeRequested()
    signal dangerActionRequested()

    implicitHeight: content.implicitHeight

    Theme {
        id: theme
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        spacing: theme.spacing3

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing3

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing2

                ToolButton {
                    text: root.baseTitle
                    visible: root.baseTitle !== ""
                    onClicked: root.navigateBackRequested()

                    background: Item {}
                    padding: 0

                    contentItem: Label {
                        text: parent.text
                        color: parent.hovered ? theme.textSecondary : theme.textPrimary
                        font.family: theme.headlineFontFamily
                        font.pixelSize: theme.titleSize
                        font.bold: true
                        elide: Text.ElideRight
                    }
                }

                Label {
                    text: root.baseTitle !== "" && root.currentTitle !== "" ? ">" : ""
                    visible: text !== ""
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.bodySize
                    font.bold: true
                }

                Label {
                    Layout.fillWidth: true
                    text: root.currentTitle
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.titleSize
                    font.bold: true
                    wrapMode: Text.WordWrap
                }
            }

            AppButton {
                visible: root.showDangerAction
                variant: "danger"
                text: root.dangerActionText
                onClicked: root.dangerActionRequested()
            }

            AppButton {
                visible: root.showClose
                variant: "secondary"
                text: root.closeText
                onClicked: root.closeRequested()
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.subtitle !== ""
            text: root.subtitle
            color: theme.textSecondary
            font.family: theme.bodyFontFamily
            font.pixelSize: theme.bodySize
            wrapMode: Text.WordWrap
        }
    }
}
