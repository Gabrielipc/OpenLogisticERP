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

    required property ReciboFormViewModel formViewModel
    Theme { id: theme }
    property real wheelStep: theme.spacing6
    property var collapsedFacturaKeys: ({})
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

    function facturaCandidateColumnWidth(column, tableWidth) {
        const metadata = root.facturaCandidateColumnData(column)
        if (metadata.key === "label") {
            const fixed = 40 + 150 + 120 + (3 * theme.spacing2)
            return Math.max(180, tableWidth - fixed)
        }
        return Number(metadata.width || 120)
    }

    function facturaCandidateColumnData(column) {
        const columns = root.formViewModel ? root.formViewModel.factura_candidate_columns : []
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

    function invoiceBalanceText(item) {
        if (!item) {
            return ""
        }
        return item.saldo_context_display || item.saldo_restante_display || item.saldo_restante || "0.00"
    }

    function invoiceAppliedText(item) {
        if (!item) {
            return "0.00"
        }
        return item.applied_context_display || item.applied_amount_display || item.applied_amount || "0.00"
    }

    function facturaCollapseKey(factura, index) {
        if (!factura) {
            return "index:" + index
        }
        if (factura.id !== undefined && factura.id !== null && factura.id !== "") {
            return "id:" + factura.id
        }
        if (factura.value !== undefined && factura.value !== null && factura.value !== "") {
            return "value:" + factura.value
        }
        return "index:" + index
    }

    function facturaCollapsed(factura, index) {
        return root.collapsedFacturaKeys[root.facturaCollapseKey(factura, index)] === true
    }

    function setFacturaCollapsed(factura, index, collapsed) {
        const key = root.facturaCollapseKey(factura, index)
        const next = Object.assign({}, root.collapsedFacturaKeys)
        if (collapsed) {
            next[key] = true
        } else {
            delete next[key]
        }
        root.collapsedFacturaKeys = next
    }

    function allFacturasCollapsed() {
        const facturas = root.formViewModel ? root.formViewModel.selected_facturas : []
        if (!facturas || facturas.length === 0) {
            return false
        }
        for (let i = 0; i < facturas.length; ++i) {
            if (!root.facturaCollapsed(facturas[i], i)) {
                return false
            }
        }
        return true
    }

    function setAllFacturasCollapsed(collapsed) {
        const next = ({})
        const facturas = root.formViewModel ? root.formViewModel.selected_facturas : []
        if (collapsed && facturas) {
            for (let i = 0; i < facturas.length; ++i) {
                next[root.facturaCollapseKey(facturas[i], i)] = true
            }
        }
        root.collapsedFacturaKeys = next
    }

    function facturaFieldText(factura, fieldName) {
        if (!factura) {
            return ""
        }
        if (fieldName === "applied_amount") {
            return root.invoiceAppliedText(factura)
        }
        if (fieldName === "saldo_restante") {
            return root.invoiceBalanceText(factura)
        }
        const displayKey = fieldName + "_display"
        if (factura[displayKey] !== undefined && factura[displayKey] !== null && factura[displayKey] !== "") {
            return factura[displayKey]
        }
        return factura[fieldName] !== undefined && factura[fieldName] !== null ? String(factura[fieldName]) : ""
    }

    function facturaFieldLabel(field) {
        const name = field ? String(field.name || "") : ""
        if (name === "saldo_restante") {
            return qsTr("Saldo restante")
        }
        if (name === "subtotal") {
            return qsTr("Subtotal")
        }
        if (name === "retenciones") {
            return qsTr("Retenciones")
        }
        if (name === "total") {
            return qsTr("Total")
        }
        if (name === "estado") {
            return qsTr("Estado")
        }
        if (name === "moneda") {
            return qsTr("Moneda")
        }
        return field ? String(field.label || "") : ""
    }

    Connections {
        target: root.formViewModel

        function onAllocationEditorOpenChanged(open) {
            if (open && !allocationPopup.opened) {
                allocationPopup.open()
            } else if (allocationPopup.opened) {
                allocationPopup.close()
            }
        }

        function onSelectedFacturasChanged() {
            const facturas = root.formViewModel ? root.formViewModel.selected_facturas : []
            const next = ({})
            for (let i = 0; facturas && i < facturas.length; ++i) {
                const key = root.facturaCollapseKey(facturas[i], i)
                if (root.collapsedFacturaKeys[key] === true) {
                    next[key] = true
                }
            }
            root.collapsedFacturaKeys = next
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

            AutoHeightSurfaceCard {
                Layout.fillWidth: true
                tone: "raised"
                padding: theme.spacing5
                heightSource: reciboFieldsLayout

                ColumnLayout {
                    id: reciboFieldsLayout
                    anchors.fill: parent
                    spacing: theme.spacing5

                    Repeater {
                        model: root.formViewModel ? root.headerSectionGroups(root.formViewModel.header_layout_items) : []

                        delegate: AutoHeightSurfaceCard {
                            id: headerSectionContainer
                            Layout.fillWidth: true
                            tone: "low"
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
                                                    objectName: headerFieldContainer.modelData.name === "tasa_cambio" ? "reciboTasaCambioField" : ""
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
            }

            AutoHeightSurfaceCard {
                Layout.fillWidth: true
                tone: "raised"
                padding: theme.spacing5
                heightSource: facturaSearchLayout

                ColumnLayout {
                    id: facturaSearchLayout
                    width: parent.width
                    spacing: theme.spacing3

                    RowLayout {
                        Layout.fillWidth: true
                        Label { Layout.fillWidth: true; text: qsTr("Facturas"); font.bold: true }
                        Label {
                            text: root.formViewModel ? qsTr("%1 seleccionadas").arg(root.formViewModel.selected_facturas.length) : qsTr("0 seleccionadas")
                            color: theme.textSecondary
                        }
                        AppButton {
                            variant: "secondary"
                            text: qsTr("Seleccionar facturas")
                            visible: !root.readOnly
                            enabled: root.value("cliente_id") !== ""
                            onClicked: root.formViewModel.open_factura_selector()
                        }
                    }
                }
            }

            AutoHeightSurfaceCard {
                Layout.fillWidth: true
                tone: "raised"
                padding: theme.spacing5
                heightSource: aplicacionesLayout

                ColumnLayout {
                    id: aplicacionesLayout
                    width: parent.width
                    spacing: theme.spacing3

                    RowLayout {
                        Layout.fillWidth: true
                        Label { Layout.fillWidth: true; text: qsTr("Aplicaciones"); font.bold: true }
                        AppButton {
                            compact: true
                            variant: "ghost"
                            text: root.allFacturasCollapsed() ? qsTr("Expandir") : qsTr("Contraer")
                            enabled: root.formViewModel ? root.formViewModel.selected_facturas.length > 0 : false
                            onClicked: root.setAllFacturasCollapsed(!root.allFacturasCollapsed())
                        }
                        AppButton {
                            id: allocationButton
                            variant: "ghost"
                            text: qsTr("Asignar manualmente")
                            visible: !root.readOnly
                            enabled: root.formViewModel ? root.formViewModel.selected_facturas.length > 0 : false
                            onClicked: root.formViewModel.open_allocation_editor()
                        }
                    }

                    Repeater {
                        model: root.formViewModel ? root.formViewModel.selected_facturas : []
                        AutoHeightSurfaceCard {
                            id: facturaLineCard
                            required property var modelData
                            required property int index

                            Layout.fillWidth: true
                            tone: "low"
                            padding: theme.spacing3
                            heightSource: lineColumn
                            ColumnLayout {
                                id: lineColumn
                                anchors.fill: parent
                                spacing: theme.spacing3

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: theme.spacing3

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: theme.spacing2

                                        Label {
                                            Layout.fillWidth: true
                                            text: facturaLineCard.modelData.label + " (" + root.invoiceBalanceText(facturaLineCard.modelData) + ")"
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        Label {
                                            Layout.fillWidth: true
                                            text: qsTr("Estado: %1 / Moneda: %2")
                                                .arg(String(facturaLineCard.modelData.estado || ""))
                                                .arg(String(facturaLineCard.modelData.moneda || ""))
                                            color: theme.textSecondary
                                            font.pixelSize: theme.captionSize
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Label {
                                        text: root.invoiceAppliedText(facturaLineCard.modelData)
                                        font.bold: true
                                        color: theme.textPrimary
                                    }

                                    AppButton {
                                        objectName: "reciboFacturaCollapseButton"
                                        compact: true
                                        variant: "ghost"
                                        text: root.facturaCollapsed(facturaLineCard.modelData, facturaLineCard.index) ? qsTr("Expandir") : qsTr("Contraer")
                                        onClicked: root.setFacturaCollapsed(
                                            facturaLineCard.modelData,
                                            facturaLineCard.index,
                                            !root.facturaCollapsed(facturaLineCard.modelData, facturaLineCard.index)
                                        )
                                    }
                                    AppButton { compact: true; variant: "ghost"; text: qsTr("Quitar"); visible: !root.readOnly; onClicked: root.formViewModel.remove_factura(facturaLineCard.index) }
                                }

                                GridLayout {
                                    id: facturaFieldsGrid
                                    Layout.fillWidth: true
                                    visible: !root.facturaCollapsed(facturaLineCard.modelData, facturaLineCard.index)
                                    columns: width > 880 ? 4 : (width > 620 ? 2 : 1)
                                    columnSpacing: theme.spacing3
                                    rowSpacing: theme.spacing2

                                    Repeater {
                                        model: root.formViewModel ? root.formViewModel.selected_factura_fields.slice(2) : []

                                        delegate: ColumnLayout {
                                            id: facturaFieldBlock
                                            required property var modelData

                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            spacing: theme.spacing2

                                            Label {
                                                Layout.fillWidth: true
                                                text: root.facturaFieldLabel(facturaFieldBlock.modelData)
                                                color: theme.textSecondary
                                                font.pixelSize: theme.captionSize
                                                elide: Text.ElideRight
                                            }
                                            Label {
                                                Layout.fillWidth: true
                                                text: root.facturaFieldText(facturaLineCard.modelData, facturaFieldBlock.modelData.name)
                                                color: theme.textPrimary
                                                wrapMode: Text.WordWrap
                                            }
                                        }
                                    }
                                }

                                Label {
                                    Layout.fillWidth: true
                                    visible: !root.facturaCollapsed(facturaLineCard.modelData, facturaLineCard.index) && Boolean(facturaLineCard.modelData.currency_context_display)
                                    text: facturaLineCard.modelData.currency_context_display || ""
                                    color: theme.textSecondary
                                    font.pixelSize: theme.captionSize
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                    Label { visible: root.fieldError("facturas") !== ""; text: root.fieldError("facturas"); color: theme.danger }
                }
            }

            AutoHeightSurfaceCard {
                Layout.fillWidth: true
                tone: "raised"
                padding: theme.spacing5
                heightSource: reciboSummaryLayout
                                ColumnLayout {
                    id: reciboSummaryLayout
                    width: parent.width
                    spacing: theme.spacing3

                    GridLayout {
                        Layout.fillWidth: true
                        columns: width > 720 ? 2 : 1
                        columnSpacing: theme.spacing6
                        rowSpacing: theme.spacing4

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: theme.spacing2

                            Label {
                                Layout.fillWidth: true
                                text: qsTr("Facturas")
                                color: theme.textPrimary
                                font.bold: true
                            }
                            Label { Layout.fillWidth: true; text: qsTr("Subtotal") + ": " + (root.formViewModel ? root.formViewModel.summary.subtotal_facturas_display : "0.00") }
                            Label { Layout.fillWidth: true; text: qsTr("Retenciones") + ": " + (root.formViewModel ? root.formViewModel.summary.retenciones_display : "0.00") }
                            Label { Layout.fillWidth: true; text: qsTr("Total facturas") + ": " + (root.formViewModel ? root.formViewModel.summary.total_facturas_display : "0.00") }
                            Label { Layout.fillWidth: true; text: qsTr("Saldo restante") + ": " + (root.formViewModel ? root.formViewModel.summary.saldo_restante_facturas_display : "0.00") }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: theme.spacing2

                            Label {
                                Layout.fillWidth: true
                                text: qsTr("Recibo")
                                color: theme.textPrimary
                                font.bold: true
                            }
                            Label { Layout.fillWidth: true; text: qsTr("Total aplicado") + ": " + (root.formViewModel ? root.formViewModel.summary.total_aplicado_display : "0.00") }
                            Label { Layout.fillWidth: true; text: qsTr("Saldo disponible") + ": " + (root.formViewModel ? root.formViewModel.summary.saldo_disponible_display : "0.00") }
                            Label {
                                Layout.fillWidth: true
                                text: qsTr("Faltante") + ": " + (root.formViewModel ? root.formViewModel.summary.faltante_display : "0.00")
                                color: (root.formViewModel && root.formViewModel.summary.faltante !== "0.00") ? theme.danger : theme.textPrimary
                            }
                        }
                    }

                    Label { Layout.fillWidth: true; visible: root.formViewModel && Boolean(root.formViewModel.summary.currency_context_display); text: root.formViewModel ? root.formViewModel.summary.currency_context_display : ""; color: theme.textSecondary; font.pixelSize: theme.captionSize; wrapMode: Text.WordWrap }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing3
                Item { Layout.fillWidth: true }
                AppButton { variant: "ghost"; text: qsTr("Cancelar"); onClicked: root.formViewModel.cancel_form() }
                AppButton { variant: "secondary"; text: root.formViewModel && root.formViewModel.mode === "edit" ? qsTr("Guardar cambios") : qsTr("Crear recibo"); visible: !root.readOnly; enabled: root.formViewModel ? !root.formViewModel.is_busy : false; onClicked: root.formViewModel.submit_form() }
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
        visible: root.formViewModel ? root.formViewModel.factura_selector_open : false
        color: theme.alpha(theme.textPrimary, 0.18)
        z: 20

        MouseArea {
            anchors.fill: parent
            onClicked: root.formViewModel.close_factura_selector()
        }
    }

    Rectangle {
        id: facturaDrawer

        anchors.top: parent.top
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: root.formViewModel && root.formViewModel.factura_selector_open ? Math.min(820, root.width * 0.68) : 0
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
                    text: qsTr("Seleccionar facturas")
                    font.bold: true
                    font.pixelSize: theme.titleSize
                    color: theme.textPrimary
                }
                AppButton { compact: true; variant: "ghost"; text: qsTr("Cerrar"); onClicked: root.formViewModel.close_factura_selector() }
            }

            RowLayout {
                Layout.fillWidth: true
                AppTextField {
                    id: drawerFacturaSearch
                    Layout.fillWidth: true
                    placeholderText: qsTr("Numero factura")
                    enabled: root.value("cliente_id") !== ""
                    onAccepted: root.formViewModel.search_factura_candidates(text)
                }
                AppButton {
                    compact: true
                    variant: "secondary"
                    text: qsTr("Buscar")
                    enabled: root.value("cliente_id") !== ""
                    onClicked: root.formViewModel.search_factura_candidates(drawerFacturaSearch.text)
                }
            }

            Label {
                Layout.fillWidth: true
                visible: root.value("cliente_id") === ""
                text: qsTr("Selecciona un cliente para buscar facturas.")
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

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 4
                        columnSpacing: theme.spacing2
                        visible: root.value("cliente_id") !== ""

                        Repeater {
                            model: root.formViewModel ? root.formViewModel.factura_candidate_columns : []
                            Label {
                                required property var modelData
                                text: modelData.label || ""
                                font.bold: true
                                Layout.preferredWidth: Number(modelData.width || 120)
                                Layout.fillWidth: modelData.key === "label"
                                horizontalAlignment: modelData.alignment === "right" ? Text.AlignRight : Text.AlignLeft
                                elide: Text.ElideRight
                            }
                        }
                    }

                    TableView {
                        id: facturaCandidateTable
                        objectName: "facturaCandidateTable"

                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        visible: root.value("cliente_id") !== ""
                        model: null
                        rowSpacing: theme.spacing2
                        columnSpacing: theme.spacing2
                        columnWidthProvider: function(column) { return root.facturaCandidateColumnWidth(column, facturaCandidateTable.width) }
                        rowHeightProvider: function(row) { return 40 }
                        Component.onCompleted: facturaCandidateModelAttach.start()

                        Timer {
                            id: facturaCandidateModelAttach
                            interval: 0
                            repeat: false
                            onTriggered: {
                                facturaCandidateTable.model = root.formViewModel ? root.formViewModel.factura_candidate_model : null
                                facturaCandidateTable.forceLayout()
                            }
                        }

                        delegate: Rectangle {
                            id: facturaCandidateCell
                            required property var rowData
                            required property int row
                            required property int column
                            required property bool selected
                            required property var cellValue

                            implicitWidth: root.facturaCandidateColumnWidth(facturaCandidateCell.column, facturaCandidateTable.width)
                            implicitHeight: 40
                            radius: theme.radiusSmall
                            color: facturaCandidateCell.row % 2 === 0 ? theme.surfaceRaised : theme.surface

                            CheckBox {
                                anchors.centerIn: parent
                                visible: facturaCandidateCell.column === 0
                                checked: facturaCandidateCell.selected
                                onToggled: root.formViewModel.toggle_factura_candidate_selection(facturaCandidateCell.rowData.value, checked ? 1 : 0)
                            }

                            TextInput {
                                id: facturaCandidateSelectableCellText

                                anchors.fill: parent
                                anchors.leftMargin: theme.spacing2
                                anchors.rightMargin: theme.spacing2
                                visible: facturaCandidateCell.column !== 0
                                text: String(facturaCandidateCell.cellValue || "")
                                readOnly: true
                                selectByMouse: true
                                clip: true
                                selectedTextColor: theme.surfaceRaised
                                selectionColor: theme.primary
                                verticalAlignment: Text.AlignVCenter
                                horizontalAlignment: {
                                    const metadata = root.facturaCandidateColumnData(facturaCandidateCell.column)
                                    return metadata.alignment === "right" ? Text.AlignRight : Text.AlignLeft
                                }
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: root.value("cliente_id") !== "" && root.formViewModel && root.formViewModel.factura_candidates.length === 0
                        text: qsTr("Sin facturas para mostrar.")
                        color: theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton { variant: "ghost"; text: qsTr("Cancelar"); onClicked: root.formViewModel.close_factura_selector() }
                AppButton {
                    variant: "secondary"
                    text: qsTr("Agregar seleccionadas")
                    enabled: root.value("cliente_id") !== ""
                    onClicked: {
                        if (root.formViewModel.add_selected_facturas()) {
                            root.formViewModel.close_factura_selector()
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: allocationPopup

        modal: false
        focus: true
        padding: theme.spacing5
        width: Math.min(root.width - theme.spacing6, 560)
        x: Math.max(
            theme.spacing2,
            Math.min(
                allocationButton.mapToItem(root, allocationButton.width - width, 0).x,
                root.width - width - theme.spacing2
            )
        )
        y: allocationButton.mapToItem(root, 0, allocationButton.height + theme.spacing2).y
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        onClosed: {
            if (root.formViewModel && root.formViewModel.allocation_editor_open) {
                root.formViewModel.close_allocation_editor()
            }
        }

        background: Rectangle {
            radius: theme.radiusLarge
            color: theme.surfaceRaised
            border.width: 1
            border.color: theme.alpha(theme.outlineVariant, 0.5)
        }

        contentItem: ColumnLayout {
            spacing: theme.spacing3
            Label { text: qsTr("Asignacion manual"); font.bold: true }
            Repeater {
                model: root.formViewModel ? root.formViewModel.allocation_draft_facturas : []
                RowLayout {
                    id: allocationRow
                    required property var modelData
                    required property int index

                    Layout.fillWidth: true
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacing2
                        Label { Layout.fillWidth: true; text: allocationRow.modelData.label + " (" + root.invoiceBalanceText(allocationRow.modelData) + ")"; wrapMode: Text.WordWrap }
                        Label { Layout.fillWidth: true; visible: Boolean(allocationRow.modelData.currency_context_display); text: allocationRow.modelData.currency_context_display || ""; color: theme.textSecondary; font.pixelSize: theme.captionSize; wrapMode: Text.WordWrap }
                    }
                    AppTextField { Layout.preferredWidth: 120; text: String(allocationRow.modelData.applied_amount || "0.00"); onTextEdited: root.formViewModel.set_factura_applied_amount(allocationRow.index, text) }
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                AppButton {
                    variant: "secondary"
                    text: qsTr("Aplicar")
                    onClicked: {
                        if (root.formViewModel.apply_allocation_editor()) {
                            allocationPopup.close()
                        }
                    }
                }
                AppButton { variant: "ghost"; text: qsTr("Cerrar"); onClicked: { root.formViewModel.close_allocation_editor(); allocationPopup.close() } }
            }
        }
    }
}
