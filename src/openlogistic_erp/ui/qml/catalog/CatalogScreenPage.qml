pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import OpenLogistic.Models 1.0
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
    id: page

    required property CatalogScreenViewModel screenViewModel
    property var formHost: page.screenViewModel ? page.screenViewModel.form_host : null
    property string searchDraft: page.screenViewModel ? page.screenViewModel.search_term : ""
    property int pendingDeleteRecordId: -1
    property int pendingExportRecordId: -1
    readonly property bool showFormAsPage: page.formHost
        && page.formHost.is_open
        && page.formHost.presentation_mode === "page"

    Theme {
        id: theme
    }

    function requestDelete(recordId) {
        if (!page.screenViewModel) {
            return
        }
        page.pendingDeleteRecordId = recordId
    }

    function cancelDeleteRequest() {
        page.pendingDeleteRecordId = -1
    }

    function confirmDeleteRequest() {
        if (!page.screenViewModel || page.pendingDeleteRecordId < 0) {
            page.cancelDeleteRequest()
            return
        }
        page.screenViewModel.delete_record_by_id(page.pendingDeleteRecordId)
        page.cancelDeleteRequest()
    }

    function urlToPath(url) {
        const value = String(url || "")
        if (value.startsWith("file:///")) {
            return decodeURIComponent(value.substring(8))
        }
        if (value.startsWith("file://")) {
            return decodeURIComponent(value.substring(7))
        }
        return value
    }

    function requestSingleExport(recordId) {
        page.pendingExportRecordId = recordId
        singleExportDialog.open()
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

    onScreenViewModelChanged: page.searchDraft = page.screenViewModel ? page.screenViewModel.search_term : ""

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacing5

        CatalogScreenHeader {
            Layout.fillWidth: true
            visible: !page.showFormAsPage
            title: page.screenViewModel ? page.screenViewModel.title : ""
            canCreate: page.screenViewModel ? page.screenViewModel.can_create : false
            canExport: page.screenViewModel ? page.screenViewModel.can_export : false
            exportSelectionMode: page.screenViewModel ? page.screenViewModel.export_selection_mode : false
            selectedExportCount: page.screenViewModel ? page.screenViewModel.selected_export_count : 0
            onCreateRequested: {
                if (page.screenViewModel) {
                    page.screenViewModel.open_create_form()
                }
            }
            onExportSelectionRequested: {
                if (page.screenViewModel) {
                    page.screenViewModel.begin_export_selection_slot()
                }
            }
            onExportSelectedRequested: multiExportDialog.open()
            onExportSelectionCancelled: {
                if (page.screenViewModel) {
                    page.screenViewModel.cancel_export_selection_slot()
                }
            }
            onRefreshRequested: {
                if (page.screenViewModel) {
                    page.screenViewModel.refresh_data()
                }
            }
        }

        CatalogScreenErrorBanner {
            Layout.fillWidth: true
            message: page.screenViewModel ? page.screenViewModel.error_message : ""
        }

        CatalogFilterPanel {
            Layout.fillWidth: true
            visible: !page.showFormAsPage
            screenViewModel: page.screenViewModel
            searchText: page.searchDraft
            onSearchTextEdited: text => page.searchDraft = text
            onSearchRequested: text => {
                if (page.screenViewModel) {
                    page.screenViewModel.apply_search(text)
                }
            }
            onSearchCleared: {
                page.searchDraft = ""
                if (page.screenViewModel) {
                    page.screenViewModel.clear_search()
                }
            }
        }

        CatalogScreenTableCard {
            id: catalogTableCard

            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 0
            Layout.minimumWidth: 0
            visible: !page.showFormAsPage
            screenViewModel: page.screenViewModel
            searchText: page.searchDraft
            showViewAction: page.screenViewModel
                && (page.screenViewModel.catalog_name === "factura"
                    || page.screenViewModel.catalog_name === "recibo")
            showExportAction: page.screenViewModel ? page.screenViewModel.can_export : false
            exportSelectionMode: page.screenViewModel ? page.screenViewModel.export_selection_mode : false
            onRecordSelected: recordId => {
                if (page.screenViewModel) {
                    page.screenViewModel.select_record_by_id(recordId)
                }
            }
            onViewRecordRequested: recordId => {
                if (page.screenViewModel) {
                    page.screenViewModel.open_record_detail(recordId)
                }
            }
            onEditRecordRequested: recordId => {
                if (page.screenViewModel) {
                    page.screenViewModel.open_record_form(recordId)
                }
            }
            onExportRecordRequested: recordId => page.requestSingleExport(recordId)
            onDeleteRecordRequested: recordId => {
                page.requestDelete(recordId)
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 0
            Layout.minimumWidth: 0
            visible: page.showFormAsPage

            ColumnLayout {
                anchors.fill: parent
                spacing: theme.spacing4

                WorkflowSubpageHeader {
                    Layout.fillWidth: true
                    baseTitle: page.formHost ? page.formHost.navigation_title : ""
                    currentTitle: page.formHost && page.formHost.active_form ? page.formHost.active_form.title : ""
                    showCancel: true
                    onNavigateBackRequested: {
                        if (page.screenViewModel) {
                            page.screenViewModel.close_active_form()
                        }
                    }
                    onCancelRequested: {
                        if (page.screenViewModel) {
                            page.screenViewModel.close_active_form()
                        }
                    }
                    onCloseRequested: {
                        if (page.screenViewModel) {
                            page.screenViewModel.close_active_form()
                        }
                    }
                }

                Loader {
                    id: formLoader
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 0
                    Layout.minimumWidth: 0
                    active: page.showFormAsPage

                    function syncForm() {
                        const host = page.formHost
                        if (!host || !host.is_open || host.active_component === "" || !host.active_form) {
                            source = ""
                            return
                        }

                        const resolvedSource = page.formComponentUrl(host.active_component)
                        if (source === resolvedSource && item && item.formViewModel === host.active_form) {
                            return
                        }

                        setSource(resolvedSource, {
                            formViewModel: host.active_form
                        })
                    }

                    Component.onCompleted: syncForm()
                }
            }
        }
    }

    MouseArea {
        id: catalogScreenSelectionClearArea

        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        enabled: !page.showFormAsPage
            && page.pendingDeleteRecordId < 0
            && !(page.screenViewModel ? page.screenViewModel.is_busy : false)
        propagateComposedEvents: true
        z: 1

        onPressed: function(mouse) {
            catalogTableCard.clearSelectionIfOutsideBodyTable(Qt.point(mouse.x, mouse.y), catalogScreenSelectionClearArea)
            mouse.accepted = false
        }
    }

    CatalogScreenBusyOverlay {
        anchors.fill: parent
        active: page.screenViewModel ? page.screenViewModel.is_busy : false
    }

    CatalogScreenFormOverlay {
        anchors.fill: parent
        visible: !page.showFormAsPage
        formHost: page.formHost
        onCloseRequested: {
            if (page.screenViewModel) {
                page.screenViewModel.close_active_form()
            }
        }
    }

    CatalogScreenConfirmDialog {
        anchors.fill: parent
        open: page.pendingDeleteRecordId >= 0
        title: qsTr("Confirmar eliminacion")
        message: qsTr("Deseas eliminar el registro seleccionado? Esta accion no se puede deshacer.")
        confirmEnabled: !(page.screenViewModel ? page.screenViewModel.is_busy : false)
        onCancelRequested: page.cancelDeleteRequest()
        onConfirmRequested: page.confirmDeleteRequest()
    }

    FileDialog {
        id: multiExportDialog

        title: qsTr("Exportar facturas")
        fileMode: FileDialog.SaveFile
        nameFilters: [qsTr("Excel (*.xlsx)")]
        onAccepted: {
            if (page.screenViewModel) {
                page.screenViewModel.export_selected_records(page.urlToPath(selectedFile))
            }
        }
    }

    FileDialog {
        id: singleExportDialog

        title: qsTr("Exportar factura")
        fileMode: FileDialog.SaveFile
        nameFilters: [qsTr("Excel (*.xlsx)")]
        onAccepted: {
            if (page.screenViewModel && page.pendingExportRecordId >= 0) {
                page.screenViewModel.export_record_by_id(page.pendingExportRecordId, page.urlToPath(selectedFile))
            }
            page.pendingExportRecordId = -1
        }
        onRejected: page.pendingExportRecordId = -1
    }

    Connections {
        target: page.screenViewModel

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
}
