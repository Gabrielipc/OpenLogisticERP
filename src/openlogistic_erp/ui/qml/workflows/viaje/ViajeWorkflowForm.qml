pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml
import OpenLogistic.Models 1.0
import "../../shared/controls"
import "../../shared/surfaces"
import "../../shared/forms"
import "../../shared/theme"

Item {
    id: root
    width: parent ? parent.width : implicitWidth
    height: parent ? parent.height : implicitHeight

    required property ViajeFormViewModel formViewModel
    signal cancelRequested()
    signal saveRequested()

    Theme {
        id: theme
    }

    readonly property bool exportacion: formViewModel && formViewModel.fixed_trip_type === "Exportacion"
    readonly property bool vacio: formViewModel && formViewModel.fixed_trip_type === "Vacio"
    readonly property bool routeSelectionLocked: formViewModel && formViewModel.mode === "edit"
    readonly property int renderedHeaderLayoutItemCount: formViewModel ? formViewModel.header_layout_items.length : 0
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
            return (event.angleDelta.y / 120) * root.wheelStep
        }
        return 0
    }

    function fieldValue(fieldName) {
        const values = root.formViewModel ? root.formViewModel.values : {}
        return values && values[fieldName] !== undefined ? values[fieldName] : ""
    }

    function fieldError(fieldName) {
        return root.formViewModel ? root.formViewModel.field_error(fieldName) : ""
    }

    function referenceOptions(fieldName) {
        const options = root.formViewModel ? root.formViewModel.reference_options : {}
        return options && options[fieldName] ? options[fieldName] : []
    }

    function orderField(index, fieldName) {
        const orders = root.formViewModel ? root.formViewModel.fuel_orders : []
        if (index < 0 || index >= orders.length) {
            return ""
        }
        return orders[index][fieldName] !== undefined ? orders[index][fieldName] : ""
    }

    function fieldSpan(fields, fieldName, columns) {
        for (let index = 0; index < fields.length; ++index) {
            if (fields[index].name === fieldName) {
                return Math.min(Number(fields[index].span || 1), columns)
            }
        }
        return 1
    }

    function headerFieldVisible(fieldName) {
        if (fieldName === "temperatura") {
            return root.exportacion
        }
        if (fieldName === "viaje_ida_id") {
            return !root.exportacion
        }
        if (fieldName === "_circuito_id") {
            return false
        }
        return true
    }

    function hasVisibleHeaderFields(fields) {
        for (let index = 0; index < fields.length; ++index) {
            if (root.headerFieldVisible(fields[index].name)) {
                return true
            }
        }
        return false
    }

    function headerFieldEnabled(fieldName) {
        if (!root.formViewModel || root.formViewModel.is_busy) {
            return false
        }
        const lockedFields = root.formViewModel.locked_fields || []
        if (lockedFields.indexOf(fieldName) !== -1) {
            return false
        }
        if (fieldName === "cliente_id") {
            return !root.routeSelectionLocked
        }
        if (fieldName === "origen_id" || fieldName === "destino_id") {
            return !root.routeSelectionLocked && !root.vacio && root.fieldValue("cliente_id") !== ""
        }
        return true
    }

    function headerFieldOptions(field) {
        if (!field) {
            return []
        }
        if (field.kind === "reference") {
            return root.referenceOptions(field.name)
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

    ScrollView {
        id: formScroll
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: formScroll.availableWidth
            spacing: theme.spacing5

            Rectangle {
                Layout.fillWidth: true
                visible: root.formViewModel && root.formViewModel.error_message !== ""
                radius: theme.radiusMedium
                color: theme.dangerContainer
                implicitHeight: errorLabel.implicitHeight + theme.spacing5

                Label {
                    id: errorLabel

                    anchors.fill: parent
                    anchors.margins: theme.spacing4
                    text: root.formViewModel ? root.formViewModel.error_message : ""
                    wrapMode: Text.WordWrap
                    color: theme.danger
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.bodySize
                }
            }

            AutoHeightSurfaceCard {
                Layout.fillWidth: true
                tone: "raised"
                padding: theme.spacing5
                heightSource: headerLayoutContent

                ColumnLayout {
                    id: headerLayoutContent
                    anchors.fill: parent
                    spacing: theme.spacing4

                    RowLayout {
                        Layout.fillWidth: true
                        visible: root.formViewModel ? root.formViewModel.show_trip_type_selector : false
                        spacing: theme.spacing3
                        Item { Layout.fillWidth: true }

                        AppButton {
                            text: qsTr("Exportación")
                            variant: root.exportacion ? "contrast" : "ghost"
                            enabled: root.formViewModel ? !root.formViewModel.trip_type_locked : false
                            onClicked: root.formViewModel.set_trip_type("Exportacion")
                        }

                        AppButton {
                            text: qsTr("Importación")
                            variant: !root.exportacion && !root.vacio ? "contrast" : "ghost"
                            enabled: root.formViewModel ? !root.formViewModel.trip_type_locked : false
                            onClicked: root.formViewModel.set_trip_type("Importacion")
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacing3

                        Label {
                            text: qsTr("Incluir agregados")
                            color: theme.textPrimary
                            font.bold: true
                        }

                        Switch {
                            checked: root.formViewModel ? root.formViewModel.include_agregados : false
                            enabled: root.formViewModel ? !root.formViewModel.is_busy : false
                            onToggled: root.formViewModel.set_include_agregados(checked)
                        }

                        Item { Layout.fillWidth: true }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacing5

                        Repeater {
                            id: headerLayoutRepeater
                            model: root.formViewModel ? root.headerSectionGroups(root.formViewModel.header_layout_items) : []

                            delegate: AutoHeightSurfaceCard {
                                id: sectionContainer
                                Layout.fillWidth: true
                                tone: "low"
                                padding: theme.spacing5
                                heightSource: sectionContent
                                required property var modelData

                                ColumnLayout {
                                    id: sectionContent
                                    anchors.fill: parent
                                    spacing: theme.spacing4

                                    Label {
                                        Layout.fillWidth: true
                                        visible: sectionContainer.modelData.title !== ""
                                        text: sectionContainer.modelData.title || ""
                                        color: theme.textPrimary
                                        font.family: theme.headlineFontFamily
                                        font.pixelSize: theme.sectionTitleSize
                                        font.bold: true
                                    }

                                    Repeater {
                                        model: sectionContainer.modelData.rows || []

                                        delegate: GridLayout {
                                            id: formGridLayout

                                            Layout.fillWidth: true
                                            required property var modelData
                                            visible: root.hasVisibleHeaderFields(formGridLayout.modelData.fields)
                                            columns: width > 850 ? 2 : 1
                                            columnSpacing: theme.spacing4
                                            rowSpacing: theme.spacing3

                                            Repeater {
                                                model: formGridLayout.modelData.fields || []

                                                delegate: ColumnLayout {
                                                    id: fieldContainer

                                                    Layout.fillWidth: true
                                                    Layout.minimumWidth: 0
                                                    Layout.preferredWidth: 1
                                                    required property var modelData
                                                    Layout.columnSpan: Math.min(Number(fieldContainer.modelData.span || 1), formGridLayout.columns)
                                                    visible: root.headerFieldVisible(fieldContainer.modelData.name)

                                                    FormFieldRenderer {
                                                        Layout.fillWidth: true
                                                        Layout.minimumWidth: 0
                                                        Layout.preferredWidth: 1
                                                        field: fieldContainer.modelData
                                                        formViewModel: root.formViewModel
                                                        optionsOverride: root.headerFieldOptions(fieldContainer.modelData)
                                                        editableOverride: root.headerFieldEnabled(fieldContainer.modelData.name)
                                                        useReferenceSetter: false
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

            AutoHeightSurfaceCard {
                Layout.fillWidth: true
                visible: root.exportacion
                tone: "low"
                padding: theme.spacing5
                heightSource: combustibleContent

                GridLayout {
                    id: combustibleContent
                    anchors.fill: parent
                    columns: width > 1120 ? 3 : (width > 760 ? 2 : 1)
                    columnSpacing: theme.spacing4
                    rowSpacing: theme.spacing3

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 1
                        spacing: theme.spacing2

                        Label {
                            text: qsTr("Combustible base thermo")
                            color: theme.textPrimary
                            font.bold: true
                        }

                        AppTextField {
                            Layout.fillWidth: true
                            text: String(root.fieldValue("combustible_base_thermo"))
                            invalid: root.fieldError("combustible_base_thermo") !== ""
                            onTextEdited: root.formViewModel.set_field_value("combustible_base_thermo", text)
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 1
                        spacing: theme.spacing2

                        Label {
                            text: qsTr("Combustible base camión")
                            color: theme.textPrimary
                            font.bold: true
                        }

                        AppTextField {
                            Layout.fillWidth: true
                            text: String(root.fieldValue("combustible_base_camion"))
                            invalid: root.fieldError("combustible_base_camion") !== ""
                            onTextEdited: root.formViewModel.set_field_value("combustible_base_camion", text)
                        }
                    }
                }
            }

            AutoHeightSurfaceCard {
                Layout.fillWidth: true
                visible: root.formViewModel ? root.formViewModel.show_fuel_orders : false
                tone: "raised"
                padding: theme.spacing5
                heightSource: orderLayoutContent

                ColumnLayout {
                    id: orderLayoutContent
                    anchors.fill: parent
                    spacing: theme.spacing4

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacing3

                        Label {
                            Layout.fillWidth: true
                            text: qsTr("Órdenes de combustible")
                            color: theme.textPrimary
                            font.family: theme.headlineFontFamily
                            font.pixelSize: theme.sectionTitleSize
                            font.bold: true
                        }

                        AppButton {
                            text: qsTr("Agregar orden")
                            variant: "secondary"
                            onClicked: root.formViewModel.add_fuel_order()
                        }
                    }

                    Label {
                        visible: root.fieldError("ordenes_combustible") !== ""
                        text: root.fieldError("ordenes_combustible")
                        color: theme.danger
                        font.pixelSize: theme.captionSize
                    }

                    Repeater {
                        model: root.formViewModel ? root.formViewModel.fuel_orders : []

                        delegate: AutoHeightSurfaceCard {
                            id: orderCard

                            required property int index

                            Layout.fillWidth: true
                            tone: "low"
                            padding: theme.spacing4
                            heightSource: orderCardContent

                            GridLayout {
                                id: orderCardContent
                                anchors.fill: parent
                                columns: width > 1280 ? 5 : (width > 860 ? 3 : (width > 620 ? 2 : 1))
                                columnSpacing: theme.spacing3
                                rowSpacing: theme.spacing2

                                AppComboBox {
                                    Layout.fillWidth: true
                                    Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.fuel_order_fields : [], "gasolinera", orderCardContent.columns)
                                    model: [
                                        { "value": "NEDICSA", "label": "NEDICSA" },
                                        { "value": "MOVIL", "label": "MOVIL" },
                                        { "value": "El Salvador", "label": qsTr("El Salvador") }
                                    ]
                                    textRole: "label"
                                    valueRole: "value"
                                    currentIndex: {
                                        const options = model
                                        for (let index = 0; index < options.length; ++index) {
                                            if (options[index].value === root.orderField(orderCard.index, "gasolinera")) {
                                                return index
                                            }
                                        }
                                        return -1
                                    }
                                    onActivated: function(index) {
                                        const option = model[index]
                                        if (option) {
                                            root.formViewModel.set_fuel_order_field(orderCard.index, "gasolinera", option.value)
                                        }
                                    }
                                }

                                AppTextField {
                                    Layout.fillWidth: true
                                    placeholderText: qsTr("Número orden")
                                    Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.fuel_order_fields : [], "numero_orden", orderCardContent.columns)
                                    text: String(root.orderField(orderCard.index, "numero_orden"))
                                    invalid: root.formViewModel ? root.formViewModel.fuel_order_error(orderCard.index, "numero_orden") !== "" : false
                                    onTextEdited: root.formViewModel.set_fuel_order_field(orderCard.index, "numero_orden", text)
                                }

                                AppTextField {
                                    Layout.fillWidth: true
                                    placeholderText: qsTr("Galones")
                                    Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.fuel_order_fields : [], "galones_autorizados", orderCardContent.columns)
                                    text: String(root.orderField(orderCard.index, "galones_autorizados"))
                                    invalid: root.formViewModel ? root.formViewModel.fuel_order_error(orderCard.index, "galones_autorizados") !== "" : false
                                    onTextEdited: root.formViewModel.set_fuel_order_field(orderCard.index, "galones_autorizados", text)
                                }

                                AppComboBox {
                                    Layout.fillWidth: true
                                    model: [
                                        { "value": "CAMION", "label": qsTr("Camión") },
                                        { "value": "THERMO", "label": "Thermo" }
                                    ]
                                    textRole: "label"
                                    valueRole: "value"
                                    Layout.columnSpan: root.fieldSpan(root.formViewModel ? root.formViewModel.fuel_order_fields : [], "tipo", orderCardContent.columns)
                                    currentIndex: root.orderField(orderCard.index, "tipo") === "THERMO" ? 1 : 0
                                    onActivated: function(index) {
                                        const option = model[index]
                                        if (option) {
                                            root.formViewModel.set_fuel_order_field(orderCard.index, "tipo", option.value)
                                        }
                                    }
                                }

                                AppButton {
                                    Layout.fillWidth: true
                                    text: qsTr("Eliminar")
                                    variant: "ghost"
                                    onClicked: root.formViewModel.remove_fuel_order(orderCard.index)
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing3

                Item {
                    Layout.fillWidth: true
                }

                AppButton {
                    text: qsTr("Cancelar")
                    variant: "ghost"
                    onClicked: root.cancelRequested()
                }

                AppButton {
                    text: root.formViewModel && root.formViewModel.mode === "edit"
                        ? qsTr("Guardar cambios")
                        : qsTr("Crear viaje")
                    variant: "contrast"
                    enabled: root.formViewModel ? !root.formViewModel.is_busy && root.formViewModel.is_valid : false
                    onClicked: root.saveRequested()
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
            const flickable = formScroll.contentItem as Flickable
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
}

