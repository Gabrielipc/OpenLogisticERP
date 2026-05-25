pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../shared/controls"
import "../shared/surfaces"
import "../shared/feedback"
import "../shared/forms"
import "../shared/theme"
import "../shell"
import "../catalog"
import "../workflows/common"
import "../workflows/viaje"
import "../workflows/factura"
import "../workflows/recibo"

Item {
    id: overlay

    property var formHost: null
    readonly property bool showFormAsDrawer: overlay.formHost
        && overlay.formHost.is_open
        && overlay.formHost.presentation_mode !== "page"

    signal closeRequested()

    Theme {
        id: theme
    }

    function formComponentUrl(componentName) {
        switch (componentName) {
            case "GenericCatalogForm.qml":
                return Qt.resolvedUrl("../shared/forms/GenericCatalogForm.qml")
            case "FacturaWorkflowForm.qml":
                return Qt.resolvedUrl("../workflows/factura/FacturaWorkflowForm.qml")
            case "ReciboWorkflowForm.qml":
                return Qt.resolvedUrl("../workflows/recibo/ReciboWorkflowForm.qml")
            case "ViajeWorkflowForm.qml":
                return Qt.resolvedUrl("../workflows/viaje/ViajeWorkflowForm.qml")
            default:
                return Qt.resolvedUrl(componentName)
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: overlay.showFormAsDrawer
        color: theme.alpha(theme.textPrimary, 0.18)
        z: 20

        MouseArea {
            anchors.fill: parent
            onClicked: overlay.closeRequested()
        }
    }

    Rectangle {
        id: drawer

        anchors.top: parent.top
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: overlay.showFormAsDrawer ? Math.min(540, overlay.width * 0.42) : 0
        clip: true
        color: theme.surfaceRaised
        z: 30

        Behavior on width {
            NumberAnimation {
                duration: 180
                easing.type: Easing.OutCubic
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: theme.spacing5
            spacing: theme.spacing4

            RowLayout {
                Layout.fillWidth: true

                Label {
                    Layout.fillWidth: true
                    text: overlay.formHost && overlay.formHost.active_form ? overlay.formHost.active_form.title : ""
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.titleSize
                    font.bold: true
                    wrapMode: Text.WordWrap
                }

                AppButton {
                    compact: true
                    variant: "ghost"
                    text: qsTr("Cerrar")
                    onClicked: overlay.closeRequested()
                }
            }

            Loader {
                id: formLoader

                Layout.fillWidth: true
                Layout.fillHeight: true
                active: overlay.showFormAsDrawer

                function syncForm() {
                    const host = overlay.formHost
                    if (!overlay.showFormAsDrawer || !host || host.active_component === "" || !host.active_form) {
                        source = ""
                        return
                    }

                    const resolvedSource = overlay.formComponentUrl(host.active_component)
                    if (source === resolvedSource && item && item.formViewModel === host.active_form) {
                        return
                    }

                    setSource(resolvedSource, {
                        formViewModel: host.active_form
                    })
                }

                Component.onCompleted: syncForm()

                Connections {
                    target: overlay.formHost

                    function onActiveFormChanged() {
                        formLoader.syncForm()
                    }

                    function onActiveComponentChanged() {
                        formLoader.syncForm()
                    }

                    function onIsOpenChanged() {
                        formLoader.syncForm()
                    }
                }
            }
        }
    }
}
