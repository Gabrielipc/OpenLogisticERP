pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "../../shared/controls"
import "../../shared/feedback"
import "../../shared/surfaces"
import "../../shared/theme"

Item {
    id: page

    property var appShellViewModel: null
    required property SecurityAdminViewModel moduleViewModel
    property real wheelStep: theme.spacing6
    property var selectedCreateRoles: []
    property var selectedUserRoles: []
    property var rolePermissionDraft: ({})
    property var userOverrideDraft: ({})
    property string activePage: page.moduleViewModel ? page.moduleViewModel.active_page : "users"

    Theme { id: theme }

    function normalizedWheelDelta(event) {
        if (event.pixelDelta.y !== 0) {
            return event.pixelDelta.y
        }
        if (event.angleDelta.y !== 0) {
            return (event.angleDelta.y / 120) * page.wheelStep
        }
        return 0
    }

    function permissionActions() {
        return ["crear", "leer", "modificar", "eliminar"]
    }

    function showDomainHeader(rows, index) {
        if (index <= 0) {
            return true
        }
        const current = rows[index] || {}
        const previous = rows[index - 1] || {}
        return String(current.domain || "") !== String(previous.domain || "")
    }

    function toggleValue(listValue, value, checked) {
        const copy = Array.from(listValue || [])
        const index = copy.indexOf(value)
        if (checked && index < 0) {
            copy.push(value)
        } else if (!checked && index >= 0) {
            copy.splice(index, 1)
        }
        return copy
    }

    function setPermissionState(target, resource, action, state) {
        const copy = Object.assign({}, target || {})
        const resourceMap = Object.assign({}, copy[resource] || {})
        if (state === "inherit") {
            delete resourceMap[action]
        } else {
            resourceMap[action] = state
        }
        copy[resource] = resourceMap
        return copy
    }

    function permissionState(target, resource, action, fallback) {
        if (!target || !target[resource] || target[resource][action] === undefined) {
            return fallback
        }
        return target[resource][action]
    }

    function roleSelectionFromProfile(profile) {
        const selection = {}
        const rows = profile && profile.permission_rows ? profile.permission_rows : []
        for (let i = 0; i < rows.length; i++) {
            const permissions = rows[i].permissions || []
            for (let j = 0; j < permissions.length; j++) {
                const permission = permissions[j]
                selection[permission.resource] = selection[permission.resource] || {}
                selection[permission.resource][permission.action] = Boolean(permission.granted)
            }
        }
        return selection
    }

    function rolePermissionPayload() {
        const payload = {}
        const draft = page.rolePermissionDraft || {}
        for (const resource in draft) {
            const actions = []
            for (const action in draft[resource]) {
                if (draft[resource][action] === true) {
                    actions.push(action)
                }
            }
            if (actions.length > 0) {
                payload[resource] = actions
            }
        }
        return payload
    }

    function syncSelectedUserDrafts() {
        const profile = page.moduleViewModel ? page.moduleViewModel.selected_user_profile : ({})
        page.selectedUserRoles = Array.from(profile && profile.roles ? profile.roles : [])

        const overrides = profile && profile.overrides ? profile.overrides : ({})
        const draft = {}
        for (const key in overrides) {
            const parts = String(key).split(":")
            if (parts.length !== 2) {
                continue
            }
            const state = overrides[key] === true ? "grant" : "deny"
            draft[parts[0]] = draft[parts[0]] || {}
            draft[parts[0]][parts[1]] = state
        }
        page.userOverrideDraft = draft
    }

    function syncSelectedRoleDraft() {
        page.rolePermissionDraft = page.roleSelectionFromProfile(
            page.moduleViewModel ? page.moduleViewModel.selected_role_profile : ({})
        )
    }

    function syncNewRoleDraft() {
        page.rolePermissionDraft = page.roleSelectionFromProfile(
            page.moduleViewModel ? page.moduleViewModel.new_role_profile : ({})
        )
    }

    function openNewUserForm() {
        page.selectedCreateRoles = []
        newUserForm.resetForm()
        page.moduleViewModel.set_active_page("new_user")
    }

    function openNewRoleForm() {
        page.rolePermissionDraft = {}
        page.moduleViewModel.begin_create_role()
    }

    function goDashboard() {
        if (page.appShellViewModel) {
            page.appShellViewModel.go_home()
        }
    }

    function overridePayload() {
        return Object.assign({}, page.userOverrideDraft || {})
    }

    function syncActivePage() {
        page.activePage = page.moduleViewModel ? page.moduleViewModel.active_page : "users"
    }

    function nextOverrideState(current) {
        if (current === "grant") {
            return "deny"
        }
        if (current === "deny") {
            return "inherit"
        }
        return "grant"
    }

    function userPermissionVisualState(permission) {
        const resourceMap = page.userOverrideDraft[permission.resource] || {}
        const current = resourceMap[permission.action] || "inherit"
        if (current === "grant") {
            return "ALLOW_OVERRIDE"
        }
        if (current === "deny") {
            return "DENY"
        }
        return permission.visual_state || "NONE"
    }

    function userPermissionLabel(permission) {
        const resourceMap = page.userOverrideDraft[permission.resource] || {}
        const current = resourceMap[permission.action] || "inherit"
        if (current === "grant") {
            return permission.action
        }
        if (current === "deny") {
            return permission.action
        }
        return permission.action
    }

    function rolePermissionVisualState(permission) {
        const checked = Boolean(page.permissionState(page.rolePermissionDraft, permission.resource, permission.action, permission.granted))
        return checked ? "GRANTED" : "NONE"
    }

    function rolePermissionLabel(permission) {
        return permission.action
    }

    function permissionFill(visualState) {
        if (visualState === "ALLOW_OVERRIDE" || visualState === "GRANTED") {
            return theme.success
        }
        if (visualState === "EFFECTIVE_ROLE") {
            return theme.successContainer
        }
        if (visualState === "DENY") {
            return theme.danger
        }
        return theme.surfaceRaised
    }

    function permissionBorder(visualState) {
        if (visualState === "ALLOW_OVERRIDE" || visualState === "GRANTED") {
            return theme.success
        }
        if (visualState === "EFFECTIVE_ROLE") {
            return theme.success
        }
        if (visualState === "DENY") {
            return theme.danger
        }
        return theme.outlineVariant
    }

    function permissionTextColor(visualState) {
        if (visualState === "ALLOW_OVERRIDE" || visualState === "GRANTED" || visualState === "DENY") {
            return theme.textOnPrimary
        }
        if (visualState === "EFFECTIVE_ROLE") {
            return theme.success
        }
        return theme.textSecondary
    }

    Component.onCompleted: {
        if (page.moduleViewModel) {
            page.syncActivePage()
            page.moduleViewModel.initialize()
        }
    }

    onModuleViewModelChanged: page.syncActivePage()

    Connections {
        target: page.moduleViewModel

        function onActivePageChanged(activePage) {
            page.activePage = activePage
        }

        function onSelectedUserProfileChanged() {
            page.syncSelectedUserDrafts()
        }

        function onSelectedRoleProfileChanged() {
            page.syncSelectedRoleDraft()
        }

        function onNewRoleProfileChanged() {
            page.syncNewRoleDraft()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacing4

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing3

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing2

                ToolButton {
                    id: securityHomeBreadcrumbButton

                    text: qsTr("Inicio")
                    onClicked: page.goDashboard()

                    background: Item {}
                    padding: 0

                    contentItem: Label {
                        text: securityHomeBreadcrumbButton.text
                        color: securityHomeBreadcrumbButton.hovered ? theme.textSecondary : theme.textPrimary
                        font.family: theme.headlineFontFamily
                        font.pixelSize: theme.titleSize
                        font.bold: true
                        elide: Text.ElideRight
                    }
                }

                Label {
                    text: ">"
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.bodySize
                    font.bold: true
                }

                Label {
                    Layout.fillWidth: true
                    text: page.moduleViewModel ? page.moduleViewModel.title : ""
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.titleSize
                    font.bold: true
                    elide: Text.ElideRight
                }
            }

            AppButton {
                text: qsTr("Volver al dashboard")
                variant: "ghost"
                onClicked: page.goDashboard()
            }

            AppButton {
                iconSource: "qrc:/actions/control/refresh"
                text: qsTr("Refrescar")
                variant: "secondary"
                onClicked: page.moduleViewModel.refresh()
            }
        }

        CatalogScreenErrorBanner {
            Layout.fillWidth: true
            message: page.moduleViewModel ? page.moduleViewModel.error_message : ""
        }

        AutoHeightSurfaceCard {
            Layout.fillWidth: true
            padding: theme.spacing3
            heightSource: navBar

            RowLayout {
                id: navBar
                spacing: theme.spacing2

                AppButton { text: qsTr("Usuarios"); variant: ["users", "new_user", "user_detail"].indexOf(page.activePage) >= 0 ? "contrast" : "ghost"; onClicked: page.moduleViewModel.set_active_page("users") }
                AppButton { text: qsTr("Roles"); variant: ["roles", "new_role", "role_detail"].indexOf(page.activePage) >= 0 ? "contrast" : "ghost"; onClicked: page.moduleViewModel.set_active_page("roles") }
                Item { Layout.fillWidth: true }
            }
        }

        SurfaceCard{

            Layout.fillWidth: true
            Layout.fillHeight: true
            tone: "raised"

            ScrollView {
                id: securityScrollView
                anchors.fill: parent
                clip: true

                ColumnLayout {
                    id: securityContent
                    width: securityScrollView.width
                    spacing: theme.spacing4

                    AutoHeightSurfaceCard {
                        Layout.fillWidth: true
                        visible: !page.moduleViewModel.can_manage_security
                        tone: "raised"
                        heightSource: label

                        Label {
                            id: label
                            text: qsTr("Se requiere usuario superuser para administrar seguridad.")
                            wrapMode: Text.WordWrap
                            color: theme.textSecondary
                            font.family: theme.bodyFontFamily
                            font.pixelSize: theme.bodySize
                        }
                    }

                    SecurityUsersList {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        visible: page.moduleViewModel.can_manage_security && page.activePage === "users"
                        host: page
                        moduleViewModel: page.moduleViewModel                        
                    }

                    SecurityNewUserForm {
                        id: newUserForm
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        visible: page.moduleViewModel.can_manage_security && page.activePage === "new_user"
                        host: page
                        moduleViewModel: page.moduleViewModel
                    }
                    
                    SecurityUserDetail {
                        visible: page.moduleViewModel.can_manage_security && page.activePage === "user_detail"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        host: page
                        moduleViewModel: page.moduleViewModel                       
                    }
                
                    SecurityRolesList {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        visible: page.moduleViewModel.can_manage_security && page.activePage === "roles"
                        host: page
                        moduleViewModel: page.moduleViewModel
                    }

                    SecurityRoleForm {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        visible: page.moduleViewModel.can_manage_security && page.activePage === "new_role"
                        host: page
                        moduleViewModel: page.moduleViewModel
                    }

                    SecurityRoleDetail {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        visible: page.moduleViewModel.can_manage_security && page.activePage === "role_detail"
                        host: page
                        moduleViewModel: page.moduleViewModel                       
                    }
                }
            }
        }
    }
    CatalogScreenBusyOverlay {
        anchors.fill: parent
        active: page.moduleViewModel ? page.moduleViewModel.is_busy : false
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true
        onWheel: function(event) {
            page.normalizedWheelDelta(event)
            event.accepted = false
        }
    }
}
