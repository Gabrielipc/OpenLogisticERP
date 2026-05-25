pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../shared/theme"

Rectangle {
    id: root

    required property var host
    property var rows: []
    property var visualStateResolver: permission => "NONE"
    property var labelResolver: permission => permission.action

    signal permissionClicked(var permission)

    Theme { id: theme }

    implicitHeight: permissionTable.implicitHeight
    color: theme.surfaceRaised
    border.color: theme.outlineVariant
    radius: theme.radiusSmall
    clip: true

    ColumnLayout {
        id: permissionTable

        width: parent.width
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: theme.spacing3

            Label {
                Layout.preferredWidth: 180
                text: qsTr("Recurso")
                color: theme.textSecondary
                font.bold: true
            }

            Label {
                Layout.fillWidth: true
                text: qsTr("Permisos")
                color: theme.textSecondary
                font.bold: true
            }
        }

        Repeater {
            model: root.rows

            delegate: ColumnLayout {
                id: permissionRow

                required property var modelData
                required property int index

                Layout.fillWidth: true
                spacing: 0

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: root.host.showDomainHeader(root.rows, permissionRow.index) ? 34 : 0
                    visible: implicitHeight > 0
                    color: theme.surface
                    border.color: theme.outlineVariant
                    border.width: 1

                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: theme.spacing3
                        text: permissionRow.modelData.domain || qsTr("General")
                        color: theme.textSecondary
                        font.family: theme.bodyFontFamily
                        font.pixelSize: theme.captionSize
                        font.bold: true
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: theme.spacing3
                    Layout.rightMargin: theme.spacing3
                    Layout.topMargin: theme.spacing2
                    Layout.bottomMargin: theme.spacing2
                    spacing: theme.spacing3

                    TextInput {
                        id: permissionResourceSelectableText

                        Layout.preferredWidth: 180
                        text: permissionRow.modelData.resource_label || permissionRow.modelData.resource
                        color: theme.textPrimary
                        font.family: theme.bodyFontFamily
                        font.pixelSize: theme.bodySize
                        font.bold: true
                        readOnly: true
                        selectByMouse: true
                        selectedTextColor: theme.surfaceRaised
                        selectionColor: theme.primary
                        clip: true
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: theme.spacing2

                        Repeater {
                            model: permissionRow.modelData.permissions || []

                            delegate: Rectangle {
                                id: permissionPill

                                required property var modelData
                                readonly property string visualState: root.visualStateResolver(permissionPill.modelData)

                                width: Math.max(76, permissionPillLabel.implicitWidth + theme.spacing6)
                                height: theme.controlHeightCompact
                                radius: theme.radiusPill
                                color: root.host.permissionFill(visualState)
                                border.color: root.host.permissionBorder(visualState)
                                border.width: 1

                                Label {
                                    id: permissionPillLabel

                                    anchors.centerIn: parent
                                    text: root.labelResolver(permissionPill.modelData)
                                    color: root.host.permissionTextColor(permissionPill.visualState)
                                    font.family: theme.bodyFontFamily
                                    font.pixelSize: theme.bodySize
                                    font.bold: permissionPill.visualState !== "NONE"
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.permissionClicked(permissionPill.modelData)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
