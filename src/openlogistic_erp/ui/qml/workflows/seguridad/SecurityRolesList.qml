pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../shared/controls"
import "../../shared/surfaces"
import "../../shared/theme"

ColumnLayout {
    id: root

    required property var host
    required property var moduleViewModel

    Layout.fillWidth: true
    Layout.minimumWidth: 0

    Theme { id: theme }

    spacing: theme.spacing3


    RowLayout {
        Layout.fillWidth: true

        Label {
            Layout.fillWidth: true
            text: qsTr("Roles")
            color: theme.textPrimary
            font.family: theme.headlineFontFamily
            font.pixelSize: theme.titleSize
            font.bold: true
        }

        AppButton {
            text: qsTr("Nuevo rol")
            variant: "contrast"
            onClicked: root.host.openNewRoleForm()
        }
    }

    Repeater {
        model: root.moduleViewModel.roles

        delegate: SurfaceCard {
            id: roleCard

            required property var modelData

            Layout.fillWidth: true
            tone: "low"
            padding: theme.spacing4

            RowLayout {
                id: roleCardContent

                TextInput {
                    id: securityRoleSelectableText

                    Layout.fillWidth: true
                    text: roleCard.modelData.name
                    color: theme.textPrimary
                    font.bold: true
                    readOnly: true
                    selectByMouse: true
                    selectedTextColor: theme.surfaceRaised
                    selectionColor: theme.primary
                    clip: true
                }

                Item { Layout.fillWidth: true }

                TextInput {
                    text: qsTr("%1 permisos").arg(roleCard.modelData.permissions.length)
                    color: theme.textSecondary
                    readOnly: true
                    selectByMouse: true
                    selectedTextColor: theme.surfaceRaised
                    selectionColor: theme.primary
                }

                AppButton {
                    text: qsTr("Editar")
                    variant: "secondary"
                    onClicked: root.moduleViewModel.select_role(roleCard.modelData.name)
                }
            }
        }
    }
}
