pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../shared/controls"
import "../../shared/theme"

ColumnLayout {
    id: root

    required property var host
    required property var moduleViewModel
    
    Theme {id: theme}

    Layout.fillWidth: true
    Layout.minimumWidth: 0
    spacing: theme.spacing3

    function resetForm() {
        newUsername.text = ""
        newPassword.text = ""
        newSuperuser.checked = false
    }

    Label {
        text: qsTr("Nuevo usuario")
        color: theme.textPrimary
        font.pixelSize: theme.titleSize
        font.bold: true
    }

    AppTextField {
        id: newUsername
        Layout.fillWidth: true
        placeholderText: qsTr("Username")
    }

    AppTextField {
        id: newPassword
        Layout.fillWidth: true
        placeholderText: qsTr("Password inicial")
        echoMode: TextInput.Password
    }

    CheckBox {
        id: newSuperuser
        text: qsTr("Superuser")
    }

    Label {
        text: qsTr("Roles")
        color: theme.textSecondary
    }

    Repeater {
        model: root.moduleViewModel.roles

        delegate: CheckBox {
            required property var modelData

            text: modelData.name
            checked: root.host.selectedCreateRoles.indexOf(modelData.name) >= 0
            onToggled: root.host.selectedCreateRoles = root.host.toggleValue(root.host.selectedCreateRoles, modelData.name, checked)
        }
    }

    RowLayout {
        Layout.fillWidth: true

        Item {
            Layout.fillWidth: true
        }

        AppButton {
            text: qsTr("Cancelar")
            variant: "ghost"
            onClicked: root.moduleViewModel.set_active_page("users")
        }

        AppButton {
            text: qsTr("Crear")
            variant: "contrast"
            onClicked: root.moduleViewModel.create_user(newUsername.text, newPassword.text, newSuperuser.checked, root.host.selectedCreateRoles)
        }
    }
}
