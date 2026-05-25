pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml
import OpenLogistic.Models 1.0
import "../../shared/controls"
import "../../shared/surfaces"
import "../../shared/forms"
import "../../shared/feedback"
import "../../shared/theme"

Item {
    id: root
    width: parent ? parent.width : implicitWidth
    height: parent ? parent.height : implicitHeight

    required property FacturaFormViewModel formViewModel

    Theme { id: theme }
    property real wheelStep: theme.spacing6
    property var selectedDetailIndexes: []
    property var collapsedDetailKeys: ({})
    property var pendingViajeCandidateColumnWidths: ({})
    readonly property bool readOnly: root.formViewModel && root.formViewModel.mode === "view"

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
            return (event.angleDelta.y / 120) * root.wheelStep
        }
        return 0
    }

    function value(name) {
        const values = root.formViewModel ? root.formViewModel.values : {}
        return values && values[name] !== undefined ? values[name] : ""
    }

    function fieldError(name) {
        const errors = root.formViewModel ? root.formViewModel.field_errors : {}
        return errors && errors[name] !== undefined ? errors[name] : ""
    }

    function headerFieldOptions(field) {
        if (!field || !root.formViewModel) {
            return []
        }
        if (field.kind === "reference") {
            return root.formViewModel.lookup_options(field.name)
        }
        return field.options || []
    }

    function headerSectionGroups(layoutItems) {
        const groups = []
        let currentGroup = null

        for (let index = 0; index < layoutItems.length; ++index) {
            const item = layoutItems[index]
            if (!item) {
                continue
            }
            if (item.type === "section") {
                currentGroup = {
                    "title": item.title || "",
                    "rows": []
                }
                groups.push(currentGroup)
                continue
            }
            if (item.type !== "row") {
                continue
            }
            if (!currentGroup) {
                currentGroup = {
                    "title": "",
                    "rows": []
                }
                groups.push(currentGroup)
            }
            currentGroup.rows.push(item)
        }

        return groups
    }

    function fieldSpan(fields, fieldName, columns) {
        for (let i = 0; i < fields.length; ++i) {
            if (fields[i].name === fieldName) {
                return Math.min(Number(fields[i].span || 1), columns)
            }
        }
        return 1
    }

    function viajeCandidateColumnWidth(column, tableWidth) {
        const metadata = root.viajeCandidateColumnData(column)
        const pendingWidth = metadata.key ? root.pendingViajeCandidateColumnWidths[metadata.key] : undefined
        if (pendingWidth !== undefined) {
            return Number(pendingWidth)
        }
        if (metadata.key === "ruta_label") {
            const columns = root.formViewModel ? root.formViewModel.viaje_candidate_columns : []
            let fixed = 6 * theme.spacing2
            for (let i = 0; i < columns.length; ++i) {
                if (columns[i].key !== "ruta_label") {
                    fixed += Number(root.pendingViajeCandidateColumnWidths[columns[i].key] || columns[i].width || 120)
                }
            }
            return Math.max(180, tableWidth - fixed)
        }
        return Number(metadata.width || 120)
    }

    function previewViajeCandidateColumnWidth(columnIndex, width) {
        const metadata = root.viajeCandidateColumnData(columnIndex)
        if (!metadata || !metadata.key || !metadata.resizable) {
            return
        }
        const minWidth = Number(metadata.minWidth || 40)
        const normalizedWidth = Math.max(minWidth, Math.round(Number(width)))
        if (!Number.isFinite(normalizedWidth)) {
            return
        }
        const next = Object.assign({}, root.pendingViajeCandidateColumnWidths)
        next[metadata.key] = normalizedWidth
        root.pendingViajeCandidateColumnWidths = next
        if (viajeCandidateTable) {
            viajeCandidateTable.forceLayout()
        }
    }

    function clearPendingViajeCandidateColumnWidth(columnKey) {
        if (!columnKey || root.pendingViajeCandidateColumnWidths[columnKey] === undefined) {
            return
        }
        const next = Object.assign({}, root.pendingViajeCandidateColumnWidths)
        delete next[columnKey]
        root.pendingViajeCandidateColumnWidths = next
        if (viajeCandidateTable) {
            viajeCandidateTable.forceLayout()
        }
    }

    function commitViajeCandidateColumnWidth(columnIndex) {
        const metadata = root.viajeCandidateColumnData(columnIndex)
        if (!metadata || !metadata.key || !root.formViewModel) {
            return
        }
        const pendingWidth = root.pendingViajeCandidateColumnWidths[metadata.key]
        if (pendingWidth === undefined) {
            return
        }
        root.formViewModel.set_viaje_candidate_column_width(metadata.key, pendingWidth)
        root.clearPendingViajeCandidateColumnWidth(metadata.key)
    }

    function viajeCandidateColumnData(column) {
        const columns = root.formViewModel ? root.formViewModel.viaje_candidate_columns : []
        if (column >= 0 && column < columns.length) {
            return columns[column]
        }
        return {}
    }

    function modelIndex(model, key, value) {
        for (let i = 0; i < model.length; ++i) {
            if (model[i][key] === value) {
                return i
            }
        }
        return -1
    }

    function detailIndexSelected(index) {
        return root.selectedDetailIndexes.indexOf(index) !== -1
    }

    function setDetailIndexSelected(index, selected) {
        const next = root.selectedDetailIndexes.slice()
        const current = next.indexOf(index)
        if (selected && current === -1) {
            next.push(index)
        } else if (!selected && current !== -1) {
            next.splice(current, 1)
        }
        root.selectedDetailIndexes = next
    }

    function detailCollapseKey(detail, index) {
        if (!detail) {
            return "index:" + index
        }
        if (detail.id !== undefined && detail.id !== null && detail.id !== "") {
            return "id:" + detail.id
        }
        if (detail.viaje_id !== undefined && detail.viaje_id !== null && detail.viaje_id !== "") {
            return "viaje:" + detail.viaje_id
        }
        if (detail.gasto_id !== undefined && detail.gasto_id !== null && detail.gasto_id !== "") {
            return "gasto:" + detail.gasto_id
        }
        return "index:" + index
    }

    function detailCollapsed(detail, index) {
        return root.collapsedDetailKeys[root.detailCollapseKey(detail, index)] === true
    }

    function setDetailCollapsed(detail, index, collapsed) {
        const key = root.detailCollapseKey(detail, index)
        const next = Object.assign({}, root.collapsedDetailKeys)
        if (collapsed) {
            next[key] = true
        } else {
            delete next[key]
        }
        root.collapsedDetailKeys = next
    }

    function allDetailsCollapsed() {
        const details = root.formViewModel ? root.formViewModel.details : []
        if (!details || details.length === 0) {
            return false
        }
        for (let i = 0; i < details.length; ++i) {
            if (!root.detailCollapsed(details[i], i)) {
                return false
            }
        }
        return true
    }

    function setAllDetailsCollapsed(collapsed) {
        const next = ({})
        const details = root.formViewModel ? root.formViewModel.details : []
        if (collapsed && details) {
            for (let i = 0; i < details.length; ++i) {
                next[root.detailCollapseKey(details[i], i)] = true
            }
        }
        root.collapsedDetailKeys = next
    }

    function removeSelectedViajeDetails() {
        const indexes = root.selectedDetailIndexes.slice().sort(function(a, b) { return b - a })
        for (let i = 0; i < indexes.length; ++i) {
            const detail = root.formViewModel && root.formViewModel.details[indexes[i]]
                ? root.formViewModel.details[indexes[i]]
                : null
            if (detail && detail.tipo === "Viaje") {
                root.formViewModel.remove_detail(indexes[i])
            }
        }
        root.selectedDetailIndexes = []
    }

    Connections {
        target: root.formViewModel

        function onDetailsChanged() {
            root.selectedDetailIndexes = []
            const details = root.formViewModel ? root.formViewModel.details : []
            const next = ({})
            for (let i = 0; details && i < details.length; ++i) {
                const key = root.detailCollapseKey(details[i], i)
                if (root.collapsedDetailKeys[key] === true) {
                    next[key] = true
                }
            }
            root.collapsedDetailKeys = next
        }

        function onPendingTarifaChanged() {
            if (root.formViewModel && root.formViewModel.pending_tarifa && root.formViewModel.pending_tarifa.viaje_id) {
                tarifaPopup.open()
            }
        }

        function onPendingTarifaChoicesChanged() {
            if (root.formViewModel && root.formViewModel.pending_tarifa_choices.length > 0) {
                tarifaChoicePopup.open()
            } else if (tarifaChoicePopup.opened) {
                tarifaChoicePopup.close()
            }
        }

        function onViajeCandidateColumnsChanged() {
            root.pendingViajeCandidateColumnWidths = ({})
            if (viajeCandidateTable) {
                viajeCandidateTable.forceLayout()
            }
        }
    }

    ScrollView {
        id: formScroll
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: formScroll.availableWidth
            spacing: theme.spacing4

            CatalogScreenErrorBanner {
                Layout.fillWidth: true
                message: root.formViewModel ? root.formViewModel.error_message : ""
            }

                ColumnLayout {
                    id: facturaFieldsLayout
                    spacing: theme.spacing5

                Repeater {
                    model: root.formViewModel ? root.headerSectionGroups(root.formViewModel.header_layout_items) : []

                    delegate: AutoHeightSurfaceCard {
                        id: headerSectionContainer
                        Layout.fillWidth: true
                        tone: "raised"
                        padding: theme.spacing5
                        heightSource: headerSectionContent
                        required property var modelData

                        ColumnLayout {
                            id: headerSectionContent
                            anchors.fill: parent
                            spacing: theme.spacing4

                            Label {
                                Layout.fillWidth: true
                                visible: headerSectionContainer.modelData.title !== ""
                                text: headerSectionContainer.modelData.title || ""
                                color: theme.textPrimary
                                font.family: theme.headlineFontFamily
                                font.pixelSize: theme.sectionTitleSize
                                font.bold: true
                            }

                            Repeater {
                                model: headerSectionContainer.modelData.rows || []

                                delegate: GridLayout {
                                    id: headerRowGrid
                                    Layout.fillWidth: true
                                    required property var modelData
                                    columns: width > 850 ? 2 : 1
                                    columnSpacing: theme.spacing4
                                    rowSpacing: theme.spacing3

                                    Repeater {
                                        model: headerRowGrid.modelData.fields || []

                                        delegate: ColumnLayout {
                                            id: headerFieldContainer
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            Layout.preferredWidth: 1
                                            required property var modelData
                                            Layout.columnSpan: Math.min(Number(headerFieldContainer.modelData.span || 1), headerRowGrid.columns)

                                            FormFieldRenderer {
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 0
                                                Layout.preferredWidth: 1
                                                field: headerFieldContainer.modelData
                                                formViewModel: root.formViewModel
                                                readOnly: root.readOnly
                                                optionsOverride: root.headerFieldOptions(headerFieldContainer.modelData)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            AutoHeightSurfaceCard {
                Layout.fillWidth: true
                tone: "raised"
                padding: theme.spacing5
                heightSource: facturaDetailsLayout

                ColumnLayout {
                    id: facturaDetailsLayout
                    anchors.fill: parent
                    spacing: theme.spacing3
                    RowLayout {
                        Layout.fillWidth: true
                        Label { Layout.fillWidth: true; text: qsTr("Detalles"); font.bold: true }
                        AppButton {
                            compact: true
                            variant: "ghost"
                            text: root.allDetailsCollapsed() ? qsTr("Expandir") : qsTr("Contraer")
                            enabled: root.formViewModel ? root.formViewModel.details.length > 0 : false
                            onClicked: root.setAllDetailsCollapsed(!root.allDetailsCollapsed())
                        }
                        AppButton { compact: true; variant: "secondary"; text: "+"; visible: !root.readOnly; onClicked: root.formViewModel.open_viaje_selector() }
                        AppButton { compact: true; variant: "ghost"; text: "-"; visible: !root.readOnly; enabled: root.selectedDetailIndexes.length > 0; onClicked: root.removeSelectedViajeDetails() }
                        AppButton { compact: true; variant: "ghost"; text: qsTr("Gasto"); visible: !root.readOnly; onClicked: root.formViewModel.add_gasto_detail() }
                    }
                    Repeater {
                        model: root.formViewModel ? root.formViewModel.details : []
                        AutoHeightSurfaceCard {
                            id: containerDetail
                            required property var modelData
                            required property int index

                            Layout.fillWidth: true
                            tone: "low"
                            padding: theme.spacing3
                            heightSource: detailCol
                            ColumnLayout {
                                id: detailCol
                                anchors.fill: parent
                                spacing: theme.spacing3
                                RowLayout {
                                    Layout.fillWidth: true
                                    CheckBox {
                                        visible: !root.readOnly && containerDetail.modelData.tipo === "Viaje"
                                        checked: root.detailIndexSelected(containerDetail.index)
                                        onToggled: root.setDetailIndexSelected(containerDetail.index, checked)
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        text: containerDetail.modelData.tipo + " - " + containerDetail.modelData.label
                                        font.bold: true
                                        elide: Text.ElideRight
                                    }
                                    Label {
                                        text: containerDetail.modelData.costo_display || containerDetail.modelData.costo || "0.00"
                                        font.bold: true
                                        color: theme.textPrimary
                                    }
                                    AppButton {
                                        objectName: "facturaDetailCollapseButton"
                                        compact: true
                                        variant: "ghost"
                                        text: root.detailCollapsed(containerDetail.modelData, containerDetail.index) ? qsTr("Expandir") : qsTr("Contraer")
                                        onClicked: root.setDetailCollapsed(
                                            containerDetail.modelData,
                                            containerDetail.index,
                                            !root.detailCollapsed(containerDetail.modelData, containerDetail.index)
                                        )
                                    }
                                    AppButton { compact: true; variant: "ghost"; text: qsTr("Quitar"); visible: !root.readOnly; onClicked: root.formViewModel.remove_detail(containerDetail.index) }
                                }
                                GridLayout {
                                    id: detailFieldsGrid
                                    Layout.fillWidth: true
                                    visible: !root.detailCollapsed(containerDetail.modelData, containerDetail.index)
                                    columns: width > 1040 ? 4 : (width > 760 ? 2 : 1)
                                    columnSpacing: theme.spacing3
                                    rowSpacing: theme.spacing2

                                    AppTextField {
                                        Layout.fillWidth: true;
                                        Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.detail_fields : [], "conductor", detailFieldsGrid.columns);
                                        enabled: false;
                                        visible: containerDetail.modelData.tipo !== "Gasto" 
                                        text: String(containerDetail.modelData.conductor_label || ""); 
                                        placeholderText: qsTr("Conductor");
                                    }

                                    AppTextField {
                                        Layout.fillWidth: true;
                                        Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.detail_fields : [], "ruta", detailFieldsGrid.columns);
                                        enabled: false;
                                        visible: containerDetail.modelData.tipo !== "Gasto" 
                                        text: String(containerDetail.modelData.ruta_label || ""); 
                                        placeholderText: qsTr("Ruta");
                                    }

                                    AppTextField { 
                                        Layout.fillWidth: true; 
                                        Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.detail_fields : [], "descripcion", detailFieldsGrid.columns); 
                                        enabled: !root.readOnly && containerDetail.modelData.tipo === "Gasto"; 
                                        text: String(containerDetail.modelData.descripcion || ""); 
                                        placeholderText: qsTr("Descripcion"); 
                                        onTextEdited: root.formViewModel.set_detail_field(containerDetail.index, "descripcion", text) 
                                        }

                                    AppTextField { 
                                        Layout.fillWidth: true; 
                                        Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.detail_fields : [], "source_costo", detailFieldsGrid.columns); 
                                        enabled: !root.readOnly && containerDetail.modelData.tipo === "Gasto"; 
                                        text: String(containerDetail.modelData.source_costo || ""); 
                                        placeholderText: qsTr("Costo"); 
                                        onTextEdited: root.formViewModel.set_detail_field(containerDetail.index, "source_costo", text) 
                                        }


                                    AppComboBox {
                                        Layout.fillWidth: true
                                        Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.detail_fields : [], "source_moneda", detailFieldsGrid.columns)
                                        enabled: !root.readOnly && containerDetail.modelData.tipo === "Gasto"
                                        model: [{ "value": "NIO", "label": "NIO" }, { "value": "USD", "label": "USD" }]
                                        textRole: "label"
                                        valueRole: "value"
                                        currentIndex: containerDetail.modelData.source_moneda === "USD" ? 1 : 0
                                        onActivated: function(comboIndex) { const option = model[comboIndex]; if (option) root.formViewModel.set_detail_field(containerDetail.index, "source_moneda", option.value) }
                                    }
                                    
                                    Label {
                                        Layout.topMargin: theme.spacing4
                                        Layout.bottomMargin: theme.spacing4
                                        Layout.fillWidth: true; 
                                        Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.detail_fields : [], "costo", detailFieldsGrid.columns); 
                                        text: containerDetail.modelData.costo_display || containerDetail.modelData.costo || "0.00"; 
                                        font.bold: true 
                                        font.pixelSize: theme.sectionTitleSize
                                        }
                                }
                            }
                        }
                    }
                    Label { visible: root.fieldError("details") !== ""; text: root.fieldError("details"); color: theme.danger }
                }
            }

            AutoHeightSurfaceCard {
                Layout.fillWidth: true
                tone: "raised"
                padding: theme.spacing5
                heightSource: facturaTaxesLayout

                ColumnLayout {
                    id: facturaTaxesLayout
                    width: parent.width
                    spacing: theme.spacing3

                    RowLayout {
                        Layout.fillWidth: true
                        Label { Layout.fillWidth: true; text: qsTr("Impuestos"); font.bold: true }
                        AppComboBox {
                            id: taxCombo
                            Layout.fillWidth: true
                            visible: !root.readOnly
                            model: root.formViewModel ? root.formViewModel.tax_options : []
                            textRole: "label"
                            valueRole: "id"
                        }
                        AppButton {
                            variant: "secondary"
                            text: qsTr("Agregar")
                            visible: !root.readOnly
                            onClicked: {
                                const option = taxCombo.model[taxCombo.currentIndex]
                                if (option) {
                                    root.formViewModel.add_tax(option.id)
                                }
                            }
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: theme.spacing2
                        Repeater {
                            model: root.formViewModel ? root.formViewModel.selected_taxes : []
                            Rectangle {
                                id: taxesPillsContainer
                                required property var modelData
                                required property int index

                                radius: theme.radiusPill
                                color: theme.primaryFixed
                                implicitHeight: chipRow.implicitHeight + theme.spacing2
                                implicitWidth: chipRow.implicitWidth + theme.spacing4
                                RowLayout {
                                    id: chipRow
                                    anchors.centerIn: parent
                                    spacing: theme.spacing2
                                    Label { text: taxesPillsContainer.modelData.codigo + " " + taxesPillsContainer.modelData.porcentaje + "%"; font.bold: true; color: theme.primary }
                                    AppIconButton {
                                        buttonSize: theme.controlHeightCompact
                                        iconSize: 16
                                        source: "qrc:/actions/control/close"
                                        tintColor: theme.primary
                                        hoverTintColor: theme.danger
                                        hoverBackgroundColor: theme.dangerContainer
                                        tooltipText: qsTr("Quitar retencion")
                                        visible: !root.readOnly
                                        onClicked: root.formViewModel.remove_tax(taxesPillsContainer.modelData.id)
                                    }
                                }
                            }
                        }
                    }

                    Label { text: qsTr("Subtotal: %1").arg(root.formViewModel ? root.formViewModel.summary.subtotal_display : "0.00") }
                    Label { text: qsTr("Retenciones: %1").arg(root.formViewModel ? root.formViewModel.summary.retenciones_display : "0.00") }
                    Label { text: qsTr("Total: %1").arg(root.formViewModel ? root.formViewModel.summary.total_display : "0.00"); font.bold: true }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing3

                Item {
                    Layout.fillWidth: true
                }

                AppButton {
                    variant: "ghost"
                    text: qsTr("Cancelar")
                    onClicked: root.formViewModel.cancel_form()
                }

                AppButton {
                    variant: "secondary"
                    text: root.formViewModel && root.formViewModel.mode === "edit" ? qsTr("Guardar cambios") : qsTr("Crear factura")
                    visible: !root.readOnly
                    enabled: root.formViewModel ? !root.formViewModel.is_busy : false
                    onClicked: root.formViewModel.submit_form()
                }
            }
        }
    }

    MouseArea {
        parent: formScroll
        anchors.fill: parent
        z: 1
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true

        onWheel: function(event) {
            const flickable = formScroll.contentItem
            if (!flickable) {
                return
            }

            const deltaY = root.normalizedWheelDelta(event)
            if (deltaY === 0) {
                return
            }

            const currentContentY = Number(flickable["contentY"] || 0)
            const nextContentY = Math.max(0, Math.min(root.maxScrollY(formScroll), currentContentY - deltaY))
            if (nextContentY === currentContentY) {
                return
            }

            flickable["contentY"] = nextContentY
            event.accepted = true
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: root.formViewModel ? root.formViewModel.viaje_selector_open : false
        color: theme.alpha(theme.textPrimary, 0.18)
        z: 20

        MouseArea {
            anchors.fill: parent
            onClicked: root.formViewModel.close_viaje_selector()
        }
    }

    Rectangle {
        id: viajeDrawer

        anchors.top: parent.top
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: root.formViewModel && root.formViewModel.viaje_selector_open ? Math.min(900, root.width * 0.72) : 0
        clip: true
        color: theme.surfaceRaised
        z: 30

        Behavior on width {
            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: theme.spacing5
            spacing: theme.spacing4

            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Seleccionar viajes")
                    font.bold: true
                    font.pixelSize: theme.titleSize
                    color: theme.textPrimary
                }
                AppButton { compact: true; variant: "ghost"; text: qsTr("Cerrar"); onClicked: root.formViewModel.close_viaje_selector() }
            }

            RowLayout {
                Layout.fillWidth: true
                AppTextField {
                    id: drawerTripSearch
                    Layout.fillWidth: true
                    placeholderText: qsTr("Referencia o descripcion")
                    enabled: root.value("cliente_id") !== ""
                    onAccepted: root.formViewModel.search_viaje_candidates(text)
                }
                AppButton {
                    compact: true
                    variant: "secondary"
                    text: qsTr("Buscar")
                    enabled: root.value("cliente_id") !== ""
                    onClicked: root.formViewModel.search_viaje_candidates(drawerTripSearch.text)
                }
            }

            CheckBox {
                text: qsTr("Incluir no finalizados")
                checked: root.formViewModel ? root.formViewModel.include_non_finalized : false
                onToggled: root.formViewModel.set_include_non_finalized(checked ? 1 : 0)
            }

            Label {
                Layout.fillWidth: true
                visible: root.value("cliente_id") === ""
                text: qsTr("Selecciona un cliente para buscar viajes.")
                color: theme.textSecondary
                wrapMode: Text.WordWrap
            }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: theme.surfaceLow
                        radius: theme.radiusMedium
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: theme.spacing3
                    spacing: theme.spacing2

                    Item {
                        id: viajeCandidateHeaderClip
                        Layout.fillWidth: true
                        implicitHeight: 28
                        clip: true
                        visible: root.value("cliente_id") !== ""

                        Row {
                            id: viajeCandidateHeaderRow
                            x: -(viajeCandidateTable ? viajeCandidateTable.contentX : 0)
                            height: parent.height
                            spacing: theme.spacing2

                            Repeater {
                                model: root.formViewModel ? root.formViewModel.viaje_candidate_columns : []
                                Rectangle {
                                    id: viajeCandidateHeaderCell
                                    required property var modelData
                                    required property int index

                                    width: root.viajeCandidateColumnWidth(viajeCandidateHeaderCell.index, viajeCandidateTable ? viajeCandidateTable.width : 0)
                                    height: viajeCandidateHeaderRow.height
                                    color: "transparent"

                                    property real dragStartX: 0
                                    property int dragStartWidth: 0

                                    Label {
                                        anchors.fill: parent
                                        anchors.leftMargin: theme.spacing2
                                        anchors.rightMargin: viajeCandidateHeaderCell.modelData.resizable ? theme.spacing4 : theme.spacing2
                                        text: viajeCandidateHeaderCell.modelData.label || ""
                                        font.bold: true
                                        horizontalAlignment: viajeCandidateHeaderCell.modelData.alignment === "right" ? Text.AlignRight : Text.AlignLeft
                                        elide: Text.ElideRight
                                        verticalAlignment: Text.AlignVCenter
                                    }

                                    Rectangle {
                                        anchors.top: parent.top
                                        anchors.bottom: parent.bottom
                                        anchors.right: parent.right
                                        width: 10
                                        visible: !!viajeCandidateHeaderCell.modelData.resizable
                                        color: viajeCandidateResizeHandle.containsMouse || viajeCandidateResizeHandle.pressed ? theme.surfaceMid : "transparent"

                                        MouseArea {
                                            id: viajeCandidateResizeHandle

                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.SizeHorCursor
                                            acceptedButtons: Qt.LeftButton
                                            preventStealing: true

                                            onPressed: function(mouse) {
                                                const point = viajeCandidateResizeHandle.mapToItem(root, mouse.x, mouse.y)
                                                viajeCandidateHeaderCell.dragStartX = point.x
                                                viajeCandidateHeaderCell.dragStartWidth = root.viajeCandidateColumnWidth(viajeCandidateHeaderCell.index, viajeCandidateTable ? viajeCandidateTable.width : 0)
                                            }

                                            onPositionChanged: function(mouse) {
                                                if (!(mouse.buttons & Qt.LeftButton)) {
                                                    return
                                                }
                                                const point = viajeCandidateResizeHandle.mapToItem(root, mouse.x, mouse.y)
                                                root.previewViajeCandidateColumnWidth(viajeCandidateHeaderCell.index, viajeCandidateHeaderCell.dragStartWidth + point.x - viajeCandidateHeaderCell.dragStartX)
                                            }

                                            onReleased: root.commitViajeCandidateColumnWidth(viajeCandidateHeaderCell.index)
                                            onCanceled: root.clearPendingViajeCandidateColumnWidth(viajeCandidateHeaderCell.modelData.key)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    TableView {
                        id: viajeCandidateTable
                        objectName: "viajeCandidateTable"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        visible: root.value("cliente_id") !== ""
                        model: null
                        rowSpacing: theme.spacing2
                        columnSpacing: theme.spacing2
                        columnWidthProvider: function(column) { return root.viajeCandidateColumnWidth(column, viajeCandidateTable.width) }
                        rowHeightProvider: function(row) { return 40 }
                        ScrollBar.horizontal: ScrollBar {
                            policy: ScrollBar.AsNeeded
                            active: true
                        }
                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                            active: true
                        }
                        Component.onCompleted: viajeCandidateModelAttach.start()

                        Timer {
                            id: viajeCandidateModelAttach
                            interval: 0
                            repeat: false
                            onTriggered: {
                                viajeCandidateTable.model = root.formViewModel ? root.formViewModel.viaje_candidate_model : null
                                viajeCandidateTable.forceLayout()
                            }
                        }

                        delegate: Rectangle {
                            id: viajeDetailContainer
                            required property int row
                            required property int column
                            required property var rowData
                            required property bool selected
                            required property var cellValue

                            implicitWidth: root.viajeCandidateColumnWidth(column, viajeCandidateTable.width)
                            implicitHeight: 40
                            radius: theme.radiusSmall
                            color: row % 2 === 0 ? theme.surfaceRaised : theme.surface

                            CheckBox {
                                anchors.centerIn: parent
                                visible: viajeDetailContainer.column === 0
                                checked: viajeDetailContainer.selected
                                onToggled: {
                                    root.formViewModel.toggle_viaje_candidate_selection(viajeDetailContainer.rowData.value, checked ? 1 : 0)
                                }
                            }

                            TextInput {
                                id: viajeCandidateSelectableCellText

                                anchors.fill: parent
                                anchors.leftMargin: theme.spacing2
                                anchors.rightMargin: theme.spacing2
                                visible: viajeDetailContainer.column !== 0
                                text: String(viajeDetailContainer.cellValue || "")
                                readOnly: true
                                selectByMouse: true
                                clip: true
                                selectedTextColor: theme.surfaceRaised
                                selectionColor: theme.primary
                                verticalAlignment: Text.AlignVCenter
                                horizontalAlignment: {
                                    const metadata = root.viajeCandidateColumnData(viajeDetailContainer.column)
                                    return metadata.alignment === "right" ? Text.AlignRight : Text.AlignLeft
                                }
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: root.value("cliente_id") !== "" && root.formViewModel && root.formViewModel.viaje_candidates.length === 0
                        text: qsTr("Sin viajes para mostrar.")
                        color: theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton { variant: "ghost"; text: qsTr("Cancelar"); onClicked: root.formViewModel.close_viaje_selector() }
                AppButton {
                    variant: "secondary"
                    text: qsTr("Agregar seleccionados")
                    enabled: root.value("cliente_id") !== ""
                    onClicked: {
                        if (root.formViewModel.add_selected_viajes()) {
                            root.formViewModel.close_viaje_selector()
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: tarifaChoicePopup
        modal: true
        focus: true
        width: Math.min(root.width - theme.spacing6, 720)
        x: Math.max(0, (root.width - width) / 2)
        y: theme.spacing6
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        onClosed: root.formViewModel.cancel_pending_tarifa_choices()

        background: Rectangle {
            radius: theme.radiusLarge
            color: theme.surfaceRaised
            border.width: 1
            border.color: theme.alpha(theme.outlineVariant, 0.5)
        }

        contentItem: ColumnLayout {
            spacing: theme.spacing3

            Label { text: qsTr("Seleccionar tarifas"); font.bold: true }
            Repeater {
                model: root.formViewModel ? root.formViewModel.pending_tarifa_choices : []
                RowLayout {
                    id: tarifasLayout
                    required property var modelData

                    Layout.fillWidth: true
                    spacing: theme.spacing3
                    Label {
                        Layout.fillWidth: true
                        text: tarifasLayout.modelData.referencia + (tarifasLayout.modelData.ruta_label ? " - " + tarifasLayout.modelData.ruta_label : "")
                        wrapMode: Text.WordWrap
                    }
                    AppComboBox {
                        Layout.preferredWidth: 220
                        model: tarifasLayout.modelData.tarifas || []
                        textRole: "label"
                        valueRole: "id"
                        currentIndex: root.modelIndex(model, "id", tarifasLayout.modelData.selected_tarifa_id)
                        onActivated: function(index) {
                            const option = model[index]
                            if (option) {
                                root.formViewModel.set_pending_tarifa_selection(tarifasLayout.modelData.viaje_id, option.id)
                            }
                        }
                    }
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                AppButton { variant: "ghost"; text: qsTr("Cancelar"); onClicked: { root.formViewModel.cancel_pending_tarifa_choices(); tarifaChoicePopup.close() } }
                AppButton { variant: "secondary"; text: qsTr("Agregar"); onClicked: { if (root.formViewModel.confirm_pending_tarifa_choices()) tarifaChoicePopup.close() } }
            }
        }
    }

    Popup {
        id: tarifaPopup
        modal: true
        focus: true
        width: Math.min(root.width - theme.spacing6, 420)
        x: Math.max(0, (root.width - width) / 2)
        y: theme.spacing6
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        onClosed: root.formViewModel.cancel_pending_tarifa()

        background: Rectangle {
            radius: theme.radiusLarge
            color: theme.surfaceRaised
            border.width: 1
            border.color: theme.alpha(theme.outlineVariant, 0.5)
        }

        contentItem: ColumnLayout {
            spacing: theme.spacing3

            Label { text: qsTr("Crear tarifa"); font.bold: true }
            Label { text: root.formViewModel ? String(root.formViewModel.pending_tarifa.ruta_label || "") : ""; wrapMode: Text.WordWrap; color: theme.textSecondary }
            AppTextField { Layout.fillWidth: true; placeholderText: qsTr("Costo"); text: root.formViewModel ? String(root.formViewModel.pending_tarifa.costo || "") : ""; onTextEdited: root.formViewModel.set_pending_tarifa_field("costo", text) }
            AppComboBox {
                Layout.fillWidth: true
                model: [{ "value": "NIO", "label": "NIO" }, { "value": "USD", "label": "USD" }]
                textRole: "label"
                valueRole: "value"
                currentIndex: root.formViewModel && root.formViewModel.pending_tarifa.moneda === "USD" ? 1 : 0
                onActivated: function(index) { const option = model[index]; if (option) root.formViewModel.set_pending_tarifa_field("moneda", option.value) }
            }
            AppTextField { Layout.fillWidth: true; placeholderText: qsTr("Descripcion"); text: root.formViewModel ? String(root.formViewModel.pending_tarifa.descripcion || "") : ""; onTextEdited: root.formViewModel.set_pending_tarifa_field("descripcion", text) }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                AppButton { variant: "ghost"; text: qsTr("Cancelar"); onClicked: { root.formViewModel.cancel_pending_tarifa(); tarifaPopup.close() } }
                AppButton { variant: "secondary"; text: qsTr("Guardar"); onClicked: { if (root.formViewModel.create_tarifa_and_add_pending_viaje()) tarifaPopup.close() } }
            }
        }
    }
}
