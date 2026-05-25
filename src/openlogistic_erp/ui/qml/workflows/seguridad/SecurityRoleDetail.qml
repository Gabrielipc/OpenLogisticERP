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

    readonly property string roleName: String(moduleViewModel.selected_role_profile.name || "")

    Theme { id: theme }

    Layout.fillWidth: true
    Layout.minimumWidth: 0
    spacing: theme.spacing3

    RowLayout {
        Layout.fillWidth: true

        Label {
            Layout.fillWidth: true
            text: qsTr("Rol: ") + root.roleName
            color: theme.textPrimary
            font.pixelSize: theme.titleSize
            font.bold: true
        }

        AppButton {
            text: qsTr("Eliminar")
            variant: "danger"
            onClicked: root.moduleViewModel.delete_role(root.roleName)
        }

        AppButton {
            text: qsTr("Cerrar")
            variant: "ghost"
            onClicked: root.moduleViewModel.set_active_page("roles")
        }
    }

    SecurityPermissionTable {
        Layout.fillWidth: true
        host: root.host
        rows: root.moduleViewModel.selected_role_profile.permission_rows || []
        visualStateResolver: permission => root.host.rolePermissionVisualState(permission)
        labelResolver: permission => root.host.rolePermissionLabel(permission)
        onPermissionClicked: permission => {
            const checked = root.host.rolePermissionVisualState(permission) === "GRANTED"
            root.host.rolePermissionDraft = root.host.setPermissionState(
                root.host.rolePermissionDraft,
                permission.resource,
                permission.action,
                !checked
            )
        }
    }

    AppButton {
        text: qsTr("Guardar permisos del rol")
        onClicked: root.moduleViewModel.save_role_permissions(root.roleName, root.host.rolePermissionPayload())
    }
}
