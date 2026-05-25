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

    Theme { id: theme }

    Layout.fillWidth: true
    Layout.minimumWidth: 0
    spacing: theme.spacing3

    RowLayout {
        Layout.fillWidth: true

        Label {
            Layout.fillWidth: true
            text: qsTr("Nuevo rol")
            color: theme.textPrimary
            font.pixelSize: theme.titleSize
            font.bold: true
        }

        AppButton {
            text: qsTr("Cancelar")
            variant: "ghost"
            onClicked: root.moduleViewModel.set_active_page("roles")
        }
    }

    AppTextField {
        id: roleName

        Layout.fillWidth: true
        placeholderText: qsTr("Nombre del rol")
    }

    SecurityPermissionTable {
        Layout.fillWidth: true
        host: root.host
        rows: root.moduleViewModel.new_role_profile.permission_rows || []
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
        text: qsTr("Crear rol")
        variant: "contrast"
        onClicked: root.moduleViewModel.create_role_with_permissions(roleName.text, root.host.rolePermissionPayload())
    }
}
