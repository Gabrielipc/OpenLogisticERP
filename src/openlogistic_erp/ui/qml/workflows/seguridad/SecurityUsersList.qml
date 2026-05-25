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
    
    Theme { id: theme }

    Layout.fillWidth: true
    Layout.minimumWidth: 0
    spacing: theme.spacing3

    RowLayout {
        Layout.fillWidth: true

        Label {
            Layout.fillWidth: true
            text: qsTr("Usuarios")
            color: theme.textPrimary
            font.family: theme.headlineFontFamily
            font.pixelSize: theme.titleSize
            font.bold: true
        }

        AppButton {
            text: qsTr("Nuevo usuario")
            variant: "contrast"
            onClicked: root.host.openNewUserForm()
        }
    }

    Repeater {
        model: root.moduleViewModel.users

        delegate: AutoHeightSurfaceCard {
            id: userCard

            required property var modelData

            Layout.fillWidth: true
            tone: "low"
            padding: theme.spacing4
            heightSource: cardContent

            RowLayout {
                id: cardContent

                width: parent.width
                spacing: theme.spacing3

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0

                    TextInput {
                        id: securityUserSelectableText

                        Layout.fillWidth: true
                        text: userCard.modelData.username
                        color: theme.textPrimary
                        font.bold: true
                        readOnly: true
                        selectByMouse: true
                        selectedTextColor: theme.surfaceRaised
                        selectionColor: theme.primary
                        clip: true
                    }

                    TextInput {
                        Layout.fillWidth: true
                        text: (userCard.modelData.is_superuser ? qsTr("Superuser") : qsTr("Usuario")) + (userCard.modelData.roles.length > 0 ? " | " + userCard.modelData.roles.join(", ") : "")
                        color: theme.textSecondary
                        readOnly: true
                        selectByMouse: true
                        selectedTextColor: theme.surfaceRaised
                        selectionColor: theme.primary
                        clip: true
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                AppButton {
                    text: qsTr("Abrir")
                    variant: "secondary"
                    onClicked: root.moduleViewModel.select_user(userCard.modelData.username)
                }
            }
        }
    }
}
