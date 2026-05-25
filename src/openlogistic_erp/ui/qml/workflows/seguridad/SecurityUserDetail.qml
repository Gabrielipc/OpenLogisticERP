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

    readonly property var profile: moduleViewModel.selected_user_profile || ({})
    readonly property var userMap: profile.user || ({})
    readonly property string username: String(userMap.username || "")

    Theme { id: theme }

    Layout.fillWidth: true
    Layout.minimumWidth: 0
    spacing: theme.spacing3

    RowLayout {
        Layout.fillWidth: true

        Label {
            Layout.fillWidth: true
            text: qsTr("Usuario: ") + root.username
            color: theme.textPrimary
            font.pixelSize: theme.titleSize
            font.bold: true
        }

        AppButton {
            text: qsTr("Cerrar")
            variant: "ghost"
            onClicked: root.moduleViewModel.set_active_page("users")
        }
    }

    CheckBox {
        text: qsTr("Superuser")
        checked: Boolean(root.userMap.is_superuser)
        onToggled: root.moduleViewModel.save_user_superuser(root.username, checked)
    }

    Label {
        text: qsTr("Roles asignados")
        color: theme.textSecondary
    }

    Repeater {
        model: root.moduleViewModel.roles

        delegate: CheckBox {
            required property var modelData

            text: modelData.name
            checked: root.host.selectedUserRoles.indexOf(modelData.name) >= 0
            onToggled: root.host.selectedUserRoles = root.host.toggleValue(root.host.selectedUserRoles, modelData.name, checked)
        }
    }

    AppButton {
        text: qsTr("Guardar roles")
        variant: "secondary"
        onClicked: root.moduleViewModel.save_user_roles(root.username, root.host.selectedUserRoles)
    }

    Label {
        text: qsTr("Permisos efectivos")
        color: theme.textPrimary
        font.bold: true
    }

    SecurityPermissionTable {
        Layout.fillWidth: true
        host: root.host
        rows: root.profile.permission_rows || []
        visualStateResolver: permission => root.host.userPermissionVisualState(permission)
        labelResolver: permission => root.host.userPermissionLabel(permission)
        onPermissionClicked: permission => {
            const current = root.host.permissionState(
                root.host.userOverrideDraft,
                permission.resource,
                permission.action,
                permission.override || "inherit"
            )
            root.host.userOverrideDraft = root.host.setPermissionState(
                root.host.userOverrideDraft,
                permission.resource,
                permission.action,
                root.host.nextOverrideState(current)
            )
        }
    }

    AppButton {
        text: qsTr("Guardar overrides")
        onClicked: root.moduleViewModel.save_user_overrides(root.username, root.host.overridePayload())
    }
}
