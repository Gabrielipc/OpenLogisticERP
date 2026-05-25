pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "../../catalog"
import "../../shared/controls"
import "../../shared/feedback"
import "../../shared/theme"
import "../common"
import "../circuito/detail"

Item {
    id: page

    required property CircuitoWorkflowViewModel moduleViewModel
    required property AppShellViewModel appShellViewModel
    property var listScreen: page.moduleViewModel ? page.moduleViewModel.list_screen : null
    property var formHost: page.listScreen ? page.listScreen.form_host : null
    property string searchDraft: page.listScreen ? page.listScreen.search_term : ""
    property real wheelStep: theme.spacing6

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

    function closeSubpage() {
        if (!page.moduleViewModel) {
            return
        }
        if (page.moduleViewModel.active_page === "form" && page.listScreen) {
            page.listScreen.close_active_form()
            return
        }
        if (page.moduleViewModel.active_page === "detail") {
            page.moduleViewModel.close_detalle()
        }
    }

    Component.onCompleted: {
        if (page.moduleViewModel) {
            page.moduleViewModel.initialize()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacing5

        CatalogScreenHeader {
            Layout.fillWidth: true
            visible: !page.moduleViewModel || page.moduleViewModel.active_page === "list"
            title: page.moduleViewModel ? page.moduleViewModel.title : ""
            subtitle: page.moduleViewModel ? page.moduleViewModel.summary : ""
            canCreate: false
            onRefreshRequested: {
                if (page.listScreen) {
                    page.listScreen.refresh_data()
                }
            }
        }

        CatalogScreenErrorBanner {
            Layout.fillWidth: true
            message: page.moduleViewModel ? page.moduleViewModel.error_message : ""
        }

        CatalogFilterPanel {
            Layout.fillWidth: true
            visible: !page.moduleViewModel || page.moduleViewModel.active_page === "list"
            screenViewModel: page.listScreen
            searchText: page.searchDraft
            onSearchTextEdited: text => page.searchDraft = text
            onSearchRequested: text => {
                page.searchDraft = text
                if (page.listScreen) {
                    page.listScreen.apply_search(text)
                }
            }
            onSearchCleared: {
                page.searchDraft = ""
                if (page.listScreen) {
                    page.listScreen.clear_search()
                }
            }
        }

        CatalogScreenTableCard {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !page.moduleViewModel || page.moduleViewModel.active_page === "list"
            screenViewModel: page.listScreen
            searchText: page.searchDraft
            showViewAction: true
            showDeleteAction: false
            viewActionText: qsTr("Ver detalle")
            onRecordSelected: recordId => {
                if (page.moduleViewModel) {
                    page.moduleViewModel.select_record_by_id(recordId)
                }
            }
            onEditRecordRequested: recordId => {
                if (page.moduleViewModel) {
                    page.moduleViewModel.open_detalle(recordId)
                }
            }
            onViewRecordRequested: recordId => {
                if (page.moduleViewModel) {
                    page.moduleViewModel.open_detalle(recordId)
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: page.moduleViewModel && page.moduleViewModel.active_page !== "list"

            ColumnLayout {
                anchors.fill: parent
                spacing: theme.spacing4

                WorkflowSubpageHeader {
                    Layout.fillWidth: true
                    baseTitle: page.formHost ? page.formHost.navigation_title : ""
                    currentTitle: page.moduleViewModel ? page.moduleViewModel.active_subpage_title : ""
                    showCancel: page.moduleViewModel && page.moduleViewModel.active_page === "form"
                    showClose: true
                    showDangerAction: false
                    onNavigateBackRequested: page.closeSubpage()
                    onCancelRequested: page.closeSubpage()
                    onCloseRequested: page.closeSubpage()
                }

                Loader {
                    id: formLoader
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: page.moduleViewModel && page.moduleViewModel.active_page === "form" && page.formHost
                    visible: active

                    function syncForm() {
                        const host = page.formHost
                        if (!host || !host.is_open || host.active_component === "" || !host.active_form) {
                            source = ""
                            return
                        }
                        let resolvedSource = ""
                        if (host.active_component === "ViajeWorkflowForm.qml") {
                            resolvedSource = Qt.resolvedUrl("../viaje/" + host.active_component)
                        } else {
                            resolvedSource = Qt.resolvedUrl("../../shared/forms/" + host.active_component)
                        }
                        if (source === resolvedSource && item && item.formViewModel === host.active_form) {
                            return
                        }
                        setSource(resolvedSource, { formViewModel: host.active_form })
                    }

                    Component.onCompleted: syncForm()

                    Connections {
                        target: formLoader.item
                        ignoreUnknownSignals: true

                        function onSaveRequested() {
                            if (page.moduleViewModel) {
                                page.moduleViewModel.save_form()
                            }
                        }

                        function onCancelRequested() {
                            page.closeSubpage()
                        }
                    }
                }

                Loader {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: page.moduleViewModel && page.moduleViewModel.active_page === "detail"
                    visible: active
                    sourceComponent: detailPageComponent
                }
            }
        }
    }

    Component {
        id: detailPageComponent

        CircuitoDetailPage {
            detailViewModel: page.moduleViewModel ? page.moduleViewModel.detail_view_model : null
            wheelStep: page.wheelStep
            onAddReturnTripRequested: returnTripDialog.open()
            onOpenTripDetailRequested: viajeId => {
                if (page.appShellViewModel) {
                    page.appShellViewModel.navigate_to({
                        "module_id": "viaje",
                        "target": "detail",
                        "record_id": viajeId
                    })
                }
            }
        }
    }

    Dialog {
        id: returnTripDialog
        modal: true
        anchors.centerIn: Overlay.overlay
        title: qsTr("Viaje de vuelta")
        font.bold: true


        ColumnLayout {
            spacing: theme.spacing3

            AppButton {
                text: qsTr("Importacion")
                variant: "secondary"
                onClicked: {
                    returnTripDialog.close()
                    page.moduleViewModel.open_return_trip_form("Importacion")
                }
            }

            AppButton {
                text: qsTr("Vacio")
                variant: "secondary"
                onClicked: {
                    returnTripDialog.close()
                    page.moduleViewModel.open_return_trip_form("Vacio")
                }
            }
        }
    }

    CatalogScreenBusyOverlay {
        anchors.fill: parent
        active: page.moduleViewModel ? page.moduleViewModel.is_busy : false
    }

    Connections {
        target: page.listScreen

        function onSearchTermChanged(term) {
            page.searchDraft = term
        }
    }

    Connections {
        target: page.formHost

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
