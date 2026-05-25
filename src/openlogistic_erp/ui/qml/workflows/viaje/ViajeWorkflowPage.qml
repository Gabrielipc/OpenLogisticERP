pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "../../shared/controls"
import "../../shared/feedback"
import "../../shared/surfaces"
import "../../shared/theme"
import "../../catalog"
import "../common"
import "../viaje/detail"

Item {
    id: page

    required property AppShellViewModel appShellViewModel
    required property ViajeWorkflowViewModel moduleViewModel
    property var listScreen: page.moduleViewModel ? page.moduleViewModel.list_screen : null
    property var formHost: page.listScreen ? page.listScreen.form_host : null
    property string searchDraft: page.listScreen ? page.listScreen.search_term : ""
    property int pendingDeleteRecordId: -1

    Theme {
        id: theme
    }
    property real wheelStep: theme.spacing6

    function maxScrollY(scrollView) {
        const flickable = scrollView ? scrollView.contentItem : null
        if (!flickable) {
            return 0
        }
        return Math.max(0, Number(flickable["contentHeight"] || 0) - Number(flickable.height || 0))
    }

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
            return
        }
        if (page.moduleViewModel.active_page === "unbilled_trips") {
            page.moduleViewModel.close_subpage()
        }
    }

    function requestDelete(recordId) {
        if (recordId === undefined || recordId === null) {
            return
        }
        page.pendingDeleteRecordId = Number(recordId)
    }

    function cancelDeleteRequest() {
        page.pendingDeleteRecordId = -1
    }

    function confirmDeleteRequest() {
        if (!page.moduleViewModel || page.pendingDeleteRecordId < 0) {
            page.cancelDeleteRequest()
            return
        }
        page.moduleViewModel.delete_viaje(page.pendingDeleteRecordId)
        page.cancelDeleteRequest()
    }

    function globalFiltersModel() {
        return page.moduleViewModel && page.moduleViewModel.global_filters
                ? page.moduleViewModel.global_filters: [] 
    }

    Component.onCompleted: {
        if (page.moduleViewModel) {
            page.moduleViewModel.initialize()
        }
    }

    onModuleViewModelChanged: {
        page.searchDraft = page.listScreen ? page.listScreen.search_term : ""
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacing5

        CatalogScreenHeader {
            Layout.fillWidth: true
            visible: !page.moduleViewModel || page.moduleViewModel.active_page === "list"
            title: page.moduleViewModel ? page.moduleViewModel.title : ""
            subtitle: page.moduleViewModel ? page.moduleViewModel.summary : ""
            canCreate: page.moduleViewModel ? page.moduleViewModel.can_create_viaje : false
            onCreateRequested: {
                if (page.moduleViewModel) {
                    page.moduleViewModel.open_create()
                }
            }
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
            globalFiltersModel: page.globalFiltersModel()
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
            onPeriodFilterApplied: (mode, month) => {
                if (page.moduleViewModel) {
                    page.moduleViewModel.apply_date_filter(mode, month)
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
            showDeleteAction: true
            viewActionText: qsTr("Ver detalle")
            onRecordSelected: recordId => {
                if (page.moduleViewModel) {
                    page.moduleViewModel.select_record_by_id(recordId)
                }
            }
            onEditRecordRequested: recordId => {
                if (page.moduleViewModel) {
                    page.moduleViewModel.open_record_form(recordId)
                }
            }
            onViewRecordRequested: recordId => {
                if (page.moduleViewModel) {
                    page.moduleViewModel.open_detalle(recordId)
                }
            }
            onDeleteRecordRequested: recordId => {
                page.requestDelete(recordId)
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
                    showClose: !(page.moduleViewModel
                        && page.moduleViewModel.active_page === "detail"
                        && page.moduleViewModel.detail_view_model
                        && page.moduleViewModel.detail_view_model.is_closed)
                    showDangerAction: page.moduleViewModel
                        && page.moduleViewModel.active_page === "detail"
                        && page.moduleViewModel.active_detail_record_id !== null
                        && page.moduleViewModel.detail_view_model
                        && page.moduleViewModel.can_delete_selected_viaje
                        && !page.moduleViewModel.detail_view_model.is_closed
                    dangerActionText: qsTr("Eliminar viaje")
                    onNavigateBackRequested: page.closeSubpage()
                    onCancelRequested: page.closeSubpage()
                    onDangerActionRequested: {
                        if (page.moduleViewModel) {
                            page.requestDelete(page.moduleViewModel.active_detail_record_id)
                        }
                    }
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

                        const resolvedSource = Qt.resolvedUrl(host.active_component)
                        if (source === resolvedSource && item && item.formViewModel === host.active_form) {
                            return
                        }

                        setSource(resolvedSource, {
                            formViewModel: host.active_form
                        })
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
                    id: detailLoader

                    Layout.alignment: Qt.AlignTop
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: page.moduleViewModel && page.moduleViewModel.active_page === "detail"
                    visible: active
                    sourceComponent: detailPageComponent
                }

                Loader {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    active: page.moduleViewModel && page.moduleViewModel.active_page === "unbilled_trips"
                    visible: active
                    sourceComponent: unbilledTripsPageComponent
                }
            }
        }
    }

    Component {
        id: detailPageComponent

        ViajeDetailPage {
            detailViewModel: page.moduleViewModel ? page.moduleViewModel.detail_view_model : null
            wheelStep: page.wheelStep
        }
    }

    Component {
        id: unbilledTripsPageComponent

        SurfaceCard {
    
            ColumnLayout {
                anchors.fill: parent
                spacing: theme.spacing3

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Viajes finalizados pendientes de factura")
                    font.bold: true
                    font.pointSize: theme.titleSize
                    color: theme.textPrimary
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: theme.spacing2
                    model: page.moduleViewModel ? page.moduleViewModel.unbilled_trips : []

                    delegate: AutoHeightSurfaceCard {

                        required property var modelData
                        readonly property var clientRow: modelData
                        property bool expanded: false
                        id: clientCard
                        width: ListView.view.width
                        tone: "low"
                        padding: theme.spacing4
                        heightSource: tripsLayout

                        ColumnLayout{
                            id: tripsLayout
                            anchors.fill: parent
                            spacing: theme.spacing2

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: clientHeaderLayout.implicitHeight
                                color: "transparent"

                                RowLayout{
                                    id: clientHeaderLayout
                                    anchors.fill: parent
                                    spacing: theme.spacing2

                                    AppIcon {
                                        size: 24
                                        tintColor: theme.textPrimary
                                        source: clientCard.expanded ? "qrc:/actions/control/drop_down" : "qrc:/actions/control/drop_right" 
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        text: String(clientCard.modelData.cliente_label || "")
                                        font.bold: true
                                    }
                                    Label {
                                        text: qsTr("Viajes sin facturar: %1").arg(String(clientCard.modelData.cantidad_viajes || "0"))
                                        font.bold: true
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: clientCard.expanded = !clientCard.expanded
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: theme.spacing2
                                visible: clientCard.expanded

                                Repeater{
                                    model: clientCard.clientRow.viajes || []
                                    
                                    delegate: AutoHeightSurfaceCard {
                                        id: rowCard
                                        required property var modelData
                                        Layout.fillWidth: true
                                        tone: "raised"
                                        padding: theme.spacing3
                                        heightSource: rowLayout

                                        RowLayout {
                                            id: rowLayout
                                            anchors.fill: parent
                                            spacing: theme.spacing3

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                Label { text: String(rowCard.modelData.referencia || ""); font.bold: true }
                                                Label { text: String(rowCard.modelData.conductor_label || ""); color: theme.textSecondary }
                                                Label { text: String(rowCard.modelData.descripcion || ""); color: theme.textSecondary }
                                                Label { text: qsTr("Fecha posicionamiento: %1").arg(String(rowCard.modelData.fecha_posicionamiento || "")); color: theme.textSecondary}
                                            }

                                            AppButton {
                                                variant: "secondary"
                                                text: qsTr("Crear factura")
                                                onClicked: {
                                                    page.appShellViewModel.navigate_to({
                                                        "module_id": "factura",
                                                        "target": "create_form_with_context",
                                                        "workflow_context": {
                                                            "cliente_id": rowCard.modelData.cliente_id,
                                                            "cliente_label": rowCard.modelData.cliente_label,
                                                            "viaje_id": rowCard.modelData.id,
                                                            "search_term": rowCard.modelData.referencia
                                                        }
                                                    })
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }                      
                }
            }
        }
    }

    CatalogScreenBusyOverlay {
        anchors.fill: parent
        active: page.moduleViewModel ? page.moduleViewModel.is_busy : false
    }

    CatalogScreenConfirmDialog {
        anchors.fill: parent
        open: page.pendingDeleteRecordId >= 0
        title: qsTr("Confirmar eliminacion")
        message: qsTr("Deseas eliminar el viaje seleccionado? Esta accion no se puede deshacer.")
        confirmEnabled: !(page.moduleViewModel ? page.moduleViewModel.is_busy : false)
        onCancelRequested: page.cancelDeleteRequest()
        onConfirmRequested: page.confirmDeleteRequest()
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
}
