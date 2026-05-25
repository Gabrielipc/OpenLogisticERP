pragma ComponentBehavior: Bound

import QtQuick
import QtQml
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "shared/controls"
import "shared/surfaces"
import "shared/theme"
import "shell"
import "catalog"
import "workflows/common"
import "workflows/viaje"
import "workflows/circuito"
import "workflows/factura"
import "workflows/recibo"
import "reports"
import "workflows/seguridad"

ApplicationWindow {
    id: window

    required property AppShellViewModel appShellViewModel
    required property RuntimeSessionViewModel runtimeSessionViewModel
    property bool launchVisible: false

    width: 1520
    height: 920
    minimumWidth: 960
    minimumHeight: 640
    visible: launchVisible
    flags: Qt.FramelessWindowHint | Qt.Window
    title: window.appShellViewModel ? window.appShellViewModel.title : ""
    color: theme.surfaceHigh

    Theme {
        id: theme
    }

    readonly property var currentModule: window.appShellViewModel ? window.appShellViewModel.current_module : null
    readonly property string currentModuleType: currentModule && currentModule.module_type
        ? String(currentModule.module_type)
        : ""
    readonly property string currentView: window.appShellViewModel && window.appShellViewModel.current_view
        ? String(window.appShellViewModel.current_view)
        : "dashboard"
    readonly property bool isAuthenticated: window.runtimeSessionViewModel
        ? window.runtimeSessionViewModel.is_authenticated
        : false
    property bool sidebarCollapsed: false
    property int resizeHandleSize: 6

    Component.onCompleted: {
        if (window.appShellViewModel && window.isAuthenticated) {
            window.appShellViewModel.initialize()
        }
    }

    function submitLogin() {
        if (window.runtimeSessionViewModel) {
            window.runtimeSessionViewModel.login(usernameField.text, passwordField.text)
        }
    }

    function beginSystemResize(edges) {
        if (window.visibility === Window.Windowed) {
            window.startSystemResize(edges)
        }
    }


    Component {
        id: catalogScreenComponent

        CatalogScreenPage {
            screenViewModel: window.appShellViewModel ? window.appShellViewModel.current_catalog_screen : null
        }
    }

    Component {
        id: clientDebtScreenComponent

        ClientDebtPage {
            appShellViewModel: window.appShellViewModel
        }
    }

    Component {
        id: dashboardScreenComponent

        DashboardPage {
            appShellViewModel: window.appShellViewModel
            runtimeSessionViewModel: window.runtimeSessionViewModel
        }
    }

    Component {
        id: workflowScreenHostComponent

        Item {
            id: workflowScreenHost

            Loader {
                id: workflowPageLoader

                anchors.fill: parent
                active: window.visible
                    && !!window.appShellViewModel
                    && window.currentView === "module"
                    && window.currentModuleType === "workflow"
                property var loadedWorkflowViewModel: null

                function syncWorkflow() {
                    const workflowViewModel = window.appShellViewModel
                        ? window.appShellViewModel.current_workflow_module
                        : null
                    const workflowSource = window.appShellViewModel
                        ? window.appShellViewModel.current_workflow_source
                        : ""
                    if (!workflowViewModel || workflowSource === "") {
                        source = ""
                        loadedWorkflowViewModel = null
                        return
                    }

                    const resolvedSource = Qt.resolvedUrl(workflowSource)
                    if (resolvedSource === "") {
                        source = ""
                        loadedWorkflowViewModel = null
                        return
                    }

                    if (source === resolvedSource && loadedWorkflowViewModel === workflowViewModel) {
                        return
                    }

                    loadedWorkflowViewModel = workflowViewModel
                    const workflowModuleId = window.currentModule && window.currentModule.module_id
                        ? String(window.currentModule.module_id)
                        : ""
                    let initialProperties = {
                        moduleViewModel: workflowViewModel
                    }
                    if (workflowModuleId === "reportes"
                            || workflowModuleId === "seguridad"
                            || workflowModuleId === "viaje"
                            || workflowModuleId === "circuito") {
                        initialProperties.appShellViewModel = window.appShellViewModel
                    }
                    setSource(resolvedSource, initialProperties)
                }

                Component.onCompleted: syncWorkflow()
                onActiveChanged: syncWorkflow()
            }

            Connections {
                target: window.appShellViewModel

                function onCurrentWorkflowModuleChanged() {
                    workflowPageLoader.syncWorkflow()
                }

                function onCurrentWorkflowComponentChanged() {
                    workflowPageLoader.syncWorkflow()
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: shellTopBar

            Layout.fillWidth: true
            Layout.preferredHeight: 48
            color: theme.surfaceHigh
            z: 30

            MouseArea {
                id: shellDragArea

                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                onPressed: {
                    if (window.visibility !== Window.FullScreen) {
                        window.startSystemMove()
                    }
                }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: theme.spacing3
                anchors.rightMargin: theme.spacing2
                spacing: theme.spacing2

                AppIconButton {
                    id: sidebarCollapseButton

                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 36
                    buttonSize: 36
                    iconSize: 20
                    tooltipText: window.sidebarCollapsed ? qsTr("Expandir menu") : qsTr("Colapsar menu")
                    source: window.sidebarCollapsed
                        ? "qrc:/actions/control/left_panel_open"
                        : "qrc:/actions/control/left_panel_close"
                    tintColor: theme.textPrimary
                    hoverBackgroundColor: theme.surfaceMid
                    onClicked: window.sidebarCollapsed = !window.sidebarCollapsed
                }

                Label {
                    Layout.fillWidth: true
                    text: window.appShellViewModel ? window.appShellViewModel.title : qsTr("OpenLogisticERP")
                    elide: Text.ElideRight
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.bodySize
                    font.bold: true
                }

                AppIconButton {
                    id: minimizeWindowButton

                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 36
                    buttonSize: 36
                    iconSize: 20
                    tooltipText: qsTr("Minimizar")
                    source: "qrc:/actions/control/minimize"
                    tintColor: theme.textPrimary
                    hoverBackgroundColor: theme.surfaceMid
                    onClicked: window.showMinimized()
                }

                AppIconButton {
                    id: maximizeWindowButton

                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 36
                    buttonSize: 36
                    iconSize: 20
                    tooltipText: window.visibility === Window.Maximized ? qsTr("Restaurar") : qsTr("Maximizar")
                    source: window.visibility === Window.Maximized
                        ? "qrc:/actions/control/select_window"
                        : "qrc:/actions/control/fullscreen"
                    tintColor: theme.textPrimary
                    hoverBackgroundColor: theme.surfaceMid
                    onClicked: {
                        if (window.visibility === Window.Maximized) {
                            window.showNormal()
                        } else {
                            window.showMaximized()
                        }
                    }
                }

                AppIconButton {
                    id: closeWindowButton

                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 36
                    buttonSize: 36
                    iconSize: 20
                    tooltipText: qsTr("Cerrar")
                    source: "qrc:/actions/control/close"
                    tintColor: theme.textPrimary
                    hoverTintColor: theme.danger
                    hoverBackgroundColor: theme.dangerContainer
                    onClicked: window.close()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: theme.spacing4
            spacing: theme.spacing4

            SidebarNav {
                Layout.fillHeight: true
                Layout.preferredWidth: window.sidebarCollapsed ? 104 : (window.width < 1280 ? 260 : 320)
                Layout.maximumWidth: window.sidebarCollapsed ? 104 : 320
                Layout.minimumWidth: window.sidebarCollapsed ? 104 : 260
                appShellViewModel: window.appShellViewModel
                runtimeSessionViewModel: window.runtimeSessionViewModel
                theme: theme
                collapsed: window.sidebarCollapsed
                onCollapseToggleRequested: window.sidebarCollapsed = !window.sidebarCollapsed
            }

            SurfaceCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                tone: "low"
                padding: theme.spacing6

                ColumnLayout {
                    anchors.fill: parent
                    spacing: theme.spacing5

                    Rectangle {
                        Layout.fillWidth: true
                        visible: window.appShellViewModel ? window.appShellViewModel.error_message !== "" : false
                        radius: theme.radiusMedium
                        color: theme.dangerContainer
                        implicitHeight: shellError.implicitHeight + theme.spacing5

                        Label {
                            id: shellError

                            anchors.fill: parent
                            anchors.margins: theme.spacing4
                            text: window.appShellViewModel ? window.appShellViewModel.error_message : ""
                            wrapMode: Text.WordWrap
                            color: theme.danger
                            font.family: theme.bodyFontFamily
                            font.pixelSize: theme.bodySize
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        Loader {
                            id: moduleLoader

                            anchors.fill: parent
                            active: window.visible && !!window.appShellViewModel && window.isAuthenticated
                            sourceComponent: {
                                if (!window.isAuthenticated) {
                                    return null
                                }
                                if (window.currentView === "dashboard") {
                                    return dashboardScreenComponent
                                }
                                if (window.currentModuleType !== "workflow") {
                                    if (window.appShellViewModel && window.appShellViewModel.current_catalog_subpage === "client_debt") {
                                        return clientDebtScreenComponent
                                    }
                                    return catalogScreenComponent
                                }
                                return workflowScreenHostComponent
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: window.appShellViewModel
            ? window.appShellViewModel.is_busy && window.currentView === "module" && window.currentModuleType !== "catalog"
            : false
        color: theme.alpha(theme.textPrimary, 0.08)
        z: 20

        BusyIndicator {
            anchors.centerIn: parent
            running: parent.visible
        }
    }

    MouseArea {
        id: resizeHandleTop

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: window.resizeHandleSize
        z: 80
        enabled: window.visibility === Window.Windowed
        cursorShape: Qt.SizeVerCursor
        onPressed: window.beginSystemResize(Qt.TopEdge)
    }

    MouseArea {
        id: resizeHandleBottom

        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: window.resizeHandleSize
        z: 80
        enabled: window.visibility === Window.Windowed
        cursorShape: Qt.SizeVerCursor
        onPressed: window.beginSystemResize(Qt.BottomEdge)
    }

    MouseArea {
        id: resizeHandleLeft

        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        width: window.resizeHandleSize
        z: 80
        enabled: window.visibility === Window.Windowed
        cursorShape: Qt.SizeHorCursor
        onPressed: window.beginSystemResize(Qt.LeftEdge)
    }

    MouseArea {
        id: resizeHandleRight

        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: window.resizeHandleSize
        z: 80
        enabled: window.visibility === Window.Windowed
        cursorShape: Qt.SizeHorCursor
        onPressed: window.beginSystemResize(Qt.RightEdge)
    }

    MouseArea {
        id: resizeHandleTopLeft

        anchors.top: parent.top
        anchors.left: parent.left
        width: window.resizeHandleSize * 2
        height: window.resizeHandleSize * 2
        z: 90
        enabled: window.visibility === Window.Windowed
        cursorShape: Qt.SizeFDiagCursor
        onPressed: window.beginSystemResize(Qt.TopEdge | Qt.LeftEdge)
    }

    MouseArea {
        id: resizeHandleTopRight

        anchors.top: parent.top
        anchors.right: parent.right
        width: window.resizeHandleSize * 2
        height: window.resizeHandleSize * 2
        z: 90
        enabled: window.visibility === Window.Windowed
        cursorShape: Qt.SizeBDiagCursor
        onPressed: window.beginSystemResize(Qt.TopEdge | Qt.RightEdge)
    }

    MouseArea {
        id: resizeHandleBottomLeft

        anchors.bottom: parent.bottom
        anchors.left: parent.left
        width: window.resizeHandleSize * 2
        height: window.resizeHandleSize * 2
        z: 90
        enabled: window.visibility === Window.Windowed
        cursorShape: Qt.SizeBDiagCursor
        onPressed: window.beginSystemResize(Qt.BottomEdge | Qt.LeftEdge)
    }

    MouseArea {
        id: resizeHandleBottomRight

        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: window.resizeHandleSize * 2
        height: window.resizeHandleSize * 2
        z: 90
        enabled: window.visibility === Window.Windowed
        cursorShape: Qt.SizeFDiagCursor
        onPressed: window.beginSystemResize(Qt.BottomEdge | Qt.RightEdge)
    }

    Rectangle {
        anchors.fill: parent
        visible: window.runtimeSessionViewModel ? !window.runtimeSessionViewModel.is_authenticated : true
        color: theme.alpha(theme.textPrimary, 0.38)
        z: 40
        onVisibleChanged: {
            if (visible) {
                usernameField.forceActiveFocus()
            }
        }

        Connections {
            target: window.runtimeSessionViewModel

            function onAuthenticatedChanged(authenticated) {
                if (authenticated) {
                    passwordField.text = ""
                    return
                }
                passwordField.text = ""
                usernameField.forceActiveFocus()
            }
        }

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: theme.alpha(theme.primaryFixed, 0.92) }
                GradientStop { position: 1.0; color: theme.alpha(theme.surface, 0.98) }
            }
        }

        MouseArea {
            id: loginEventBlocker

            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            hoverEnabled: true
            preventStealing: true
            scrollGestureEnabled: true
            onWheel: wheel => { wheel.accepted = true }
        }

        SurfaceCard {
            anchors.centerIn: parent
            width: Math.min(460, window.width - theme.spacing8 * 2)
            height: 600
            tone: "raised"
            padding: theme.spacing8
            z: 1

            ColumnLayout {
                anchors.fill: parent
                spacing: theme.spacing5

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: theme.spacing2


                    Label {
                        Layout.fillWidth: true
                        text: qsTr("Iniciar Sesión")
                        wrapMode: Text.WordWrap
                        color: theme.textPrimary
                        font.family: theme.headlineFontFamily
                        font.pixelSize: theme.titleSize
                        font.bold: true
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: theme.spacing3

                    Label {
                        text: qsTr("Usuario")
                        color: theme.textPrimary
                        font.family: theme.bodyFontFamily
                        font.pixelSize: theme.bodySize
                        font.bold: true
                    }

                    AppTextField {
                        id: usernameField
                        Layout.fillWidth: true
                        enabled: window.runtimeSessionViewModel ? !window.runtimeSessionViewModel.is_busy : true
                        placeholderText: qsTr("Ingresa el username")
                        onAccepted: window.submitLogin()
                    }

                    Label {
                        text: qsTr("Clave")
                        color: theme.textPrimary
                        font.family: theme.bodyFontFamily
                        font.pixelSize: theme.bodySize
                        font.bold: true
                    }

                    AppTextField {
                        id: passwordField
                        Layout.fillWidth: true
                        enabled: window.runtimeSessionViewModel ? !window.runtimeSessionViewModel.is_busy : true
                        echoMode: TextInput.Password
                        placeholderText: qsTr("Ingresa la clave")
                        onAccepted: window.submitLogin()
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    visible: window.runtimeSessionViewModel
                        ? window.runtimeSessionViewModel.error_message !== ""
                            || window.runtimeSessionViewModel.status_message !== ""
                        : false
                    radius: theme.radiusMedium
                    color: window.runtimeSessionViewModel && window.runtimeSessionViewModel.error_message !== ""
                        ? theme.dangerContainer
                        : theme.neutralContainer
                    implicitHeight: runtimeSessionMessage.implicitHeight + theme.spacing4

                    Label {
                        id: runtimeSessionMessage
                        anchors.fill: parent
                        anchors.margins: theme.spacing3
                        wrapMode: Text.WordWrap
                        text: window.runtimeSessionViewModel && window.runtimeSessionViewModel.error_message !== ""
                            ? window.runtimeSessionViewModel.error_message
                            : (window.runtimeSessionViewModel ? window.runtimeSessionViewModel.status_message : "")
                        color: window.runtimeSessionViewModel && window.runtimeSessionViewModel.error_message !== ""
                            ? theme.danger
                            : theme.textSecondary
                        font.family: theme.bodyFontFamily
                        font.pixelSize: theme.bodySize
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.spacing3

                    Item {
                        Layout.fillWidth: true
                    }

                    BusyIndicator {
                        visible: window.runtimeSessionViewModel ? window.runtimeSessionViewModel.is_busy : false
                        running: visible
                    }

                    AppButton {
                        id: loginButton
                        text: window.runtimeSessionViewModel && window.runtimeSessionViewModel.is_busy
                            ? qsTr("Validando...")
                            : qsTr("Iniciar sesion")
                        enabled: window.runtimeSessionViewModel
                            ? !window.runtimeSessionViewModel.is_busy
                            : false
                        onClicked: window.submitLogin()
                    }
                }
            }
        }
    }
}
