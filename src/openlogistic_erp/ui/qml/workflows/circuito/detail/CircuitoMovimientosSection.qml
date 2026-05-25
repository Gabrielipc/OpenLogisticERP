pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../../shared/controls"
import "../../../shared/tables"
import "../../../shared/theme"

Item {
    id: root

    required property var formViewModel
    readonly property bool readOnly: root.formViewModel ? root.formViewModel.is_read_only : true
    readonly property real tableContentWidth: Math.max(720, width - 2)
    readonly property int fieldColumnCount: root.formViewModel ? root.formViewModel.row_fields.length : 0
    implicitHeight: contentLayout.implicitHeight
    signal saveSucceeded()

    Theme { id: theme }

    function rowValue(rowData, fieldName) {
        if (!rowData || rowData[fieldName] === undefined || rowData[fieldName] === null) {
            return ""
        }
        return rowData[fieldName]
    }

    function displayValue(rowData, fieldName) {
        if (fieldName === "ruta_id") {
            return root.rowValue(rowData, "ruta_label") || root.rowValue(rowData, "ruta_id") || qsTr("Sin ruta")
        }
        return root.rowValue(rowData, fieldName)
    }

    function lookupOptions(fieldName) {
        const options = root.formViewModel && root.formViewModel.lookup_options_map
            ? root.formViewModel.lookup_options_map[fieldName]
            : []
        if (!options || options.length === 0) {
            return []
        }
        return options
    }

    function routeOptionIndex(rowData) {
        const current = String(root.rowValue(rowData, "ruta_id"))
        const options = root.lookupOptions("ruta_id")
        for (let index = 0; index < options.length; ++index) {
            if (String(options[index].value) === current) {
                return index
            }
        }
        return -1
    }

    function headerFields() {
        const fields = []
        const sourceFields = root.formViewModel ? root.formViewModel.row_fields : []
        for (let index = 0; index < sourceFields.length; ++index) {
            fields.push(sourceFields[index])
        }
        fields.push({ "label": qsTr("Acciones") })
        return fields
    }

    function columnWidth(column) {
        const available = root.tableContentWidth
        if (column === 0) {
            return Math.max(170, available * 0.24)
        }
        if (column === 1) {
            return Math.max(160, available * 0.22)
        }
        if (column === 3) {
            return 132
        }
        if (column === root.fieldColumnCount) {
            return 120
        }
        return Math.max(210, available - (root.columnWidth(0) + root.columnWidth(1) + root.columnWidth(3) + root.columnWidth(root.fieldColumnCount)))
    }

    ColumnLayout {
        id: contentLayout
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: theme.spacing3

        DetailEditableTable {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(144, Math.min(360, 45 + (root.formViewModel ? root.formViewModel.rows.length * 54 : 54)))
            tableModel: root.formViewModel ? root.formViewModel.table_model : null
            headerModel: root.headerFields()
            rowCount: root.formViewModel ? root.formViewModel.rows.length : 0
            columnWidthProvider: function(column) { return root.columnWidth(column) }
            rowHeight: 54
            emptyText: qsTr("Sin movimientos adicionales")
            cellDelegate: Component {
                Rectangle {
                    id: tableCell

                    required property int tableRow
                    required property int tableRowIndex
                    required property int tableColumn
                    required property var tableRowData

                    readonly property bool cellReady: (
                        root.formViewModel
                        && root.formViewModel.table_model
                        && tableRowIndex >= 0
                        && tableColumn >= 0
                    )

                    readonly property var field: cellReady
                        ? root.formViewModel.table_model.column_field(tableColumn)
                        : ({})

                    readonly property string fieldName: field && field.name ? field.name : ""

                    function safeRowValue(name) {
                        if (!cellReady || !name)
                            return ""

                        if (tableRowData !== null && tableRowData !== undefined)
                            return root.rowValue(tableRowData, name)

                        return root.formViewModel.rows[tableRowIndex]
                            ? root.rowValue(root.formViewModel.rows[tableRowIndex], name)
                            : ""
                    }

                    color: tableRowIndex % 2 === 0 ? theme.surfaceRaised : theme.surfaceLow

                    AppSearchComboBox {
                        id: routeCombo
                        anchors.fill: parent
                        anchors.margins: theme.spacing2
                        visible: tableCell.cellReady && tableCell.fieldName === "ruta_id"
                        model: tableCell.cellReady ? root.lookupOptions("ruta_id") : []
                        textRole: "label"
                        valueRole: "value"
                        currentIndex: tableCell.cellReady ? root.routeOptionIndex(tableRowData) : -1
                        enabled: tableCell.cellReady && !root.readOnly

                        Component.onCompleted: {
                            if (root.formViewModel)
                                root.formViewModel.prime_lookup_field("ruta_id")
                        }

                        onActivated: function(index) {
                            if (!tableCell.cellReady)
                                return

                            routeSearchDebounce.stop()

                            const options = root.lookupOptions("ruta_id")
                            const option = options[index]

                            if (option) {
                                root.formViewModel.set_lookup_field_value(
                                    tableCell.tableRowIndex,
                                    "ruta_id",
                                    option.value,
                                    option.label
                                )
                            }
                        }

                        onUserTextEdited: {
                            if (activeFocus && tableCell.cellReady)
                                routeSearchDebounce.restart()
                        }

                        Timer {
                            id: routeSearchDebounce
                            interval: 250
                            onTriggered: {
                                if (root.formViewModel && tableCell.cellReady)
                                    root.formViewModel.search_lookup_options("ruta_id", routeCombo.editText)
                            }
                        }
                    }

                    AppDateTimeField {
                        anchors.fill: parent
                        anchors.margins: theme.spacing2
                        visible: tableCell.cellReady && tableCell.fieldName === "fecha_movimiento"
                        enabled: tableCell.cellReady && !root.readOnly
                        text: tableCell.safeRowValue(tableCell.fieldName)

                        onTextEdited: {
                            if (!tableCell.cellReady || tableCell.fieldName === "")
                                return

                            root.formViewModel.set_row_field(
                                tableCell.tableRowIndex,
                                tableCell.fieldName,
                                text
                            )
                        }
                    }

                    AppTextField {
                        anchors.fill: parent
                        anchors.margins: theme.spacing2
                        visible: tableCell.cellReady && tableCell.fieldName === "descripcion"
                        enabled: tableCell.cellReady && !root.readOnly
                        text: tableCell.safeRowValue(tableCell.fieldName)

                        onTextEdited: {
                            if (!tableCell.cellReady || tableCell.fieldName === "")
                                return

                            root.formViewModel.set_row_field(
                                tableCell.tableRowIndex,
                                tableCell.fieldName,
                                text
                            )
                        }
                    }

                    CheckBox {
                        anchors.centerIn: parent
                        visible: tableCell.cellReady && tableCell.fieldName === "es_triangulado"
                        enabled: tableCell.cellReady && !root.readOnly

                        checked: tableCell.safeRowValue("es_triangulado") === true
                            || tableCell.safeRowValue("es_triangulado") === "true"

                        onToggled: {
                            if (!tableCell.cellReady)
                                return

                            root.formViewModel.set_row_field(
                                tableCell.tableRowIndex,
                                "es_triangulado",
                                checked
                            )
                        }
                    }

                    TextInput {
                        id: circuitoMovementSelectableCellText

                        anchors.fill: parent
                        anchors.leftMargin: theme.spacing3
                        anchors.rightMargin: theme.spacing3

                        visible: tableCell.cellReady
                            && tableCell.fieldName !== "ruta_id"
                            && tableCell.fieldName !== "fecha_movimiento"
                            && tableCell.fieldName !== "descripcion"
                            && tableCell.fieldName !== "es_triangulado"
                            && tableCell.fieldName !== "__actions__"

                        verticalAlignment: Text.AlignVCenter
                        text: tableCell.cellReady
                            ? root.displayValue(tableCell.tableRowData, tableCell.fieldName)
                            : ""
                        readOnly: true
                        selectByMouse: true
                        clip: true

                        color: tableCell.fieldName === "fecha_movimiento"
                            ? theme.textSecondary
                            : theme.textPrimary
                        selectedTextColor: theme.surfaceRaised
                        selectionColor: theme.primary

                        font.family: theme.bodyFontFamily
                        font.pixelSize: theme.bodySize
                    }

                    AppButton {
                        anchors.centerIn: parent
                        compact: true
                        text: qsTr("Quitar")
                        variant: "ghost"

                        visible: tableCell.cellReady
                            && tableCell.fieldName === "__actions__"
                            && !root.readOnly

                        onClicked: {
                            if (!tableCell.cellReady)
                                return

                            root.formViewModel.remove_row(tableCell.tableRowIndex)
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing3

            AppButton {
                variant: "ghost"
                text: qsTr("Agregar movimiento")
                visible: !root.readOnly
                enabled: !!root.formViewModel && !root.readOnly
                onClicked: root.formViewModel.add_row()
            }

            AppButton {
                variant: "secondary"
                text: qsTr("Guardar seccion")
                visible: !root.readOnly
                enabled: root.formViewModel ? root.formViewModel.is_valid && !root.readOnly : false
                onClicked: {
                    if (root.formViewModel.save_section()) {
                        root.saveSucceeded()
                    }
                }
            }
        }
    }
}
