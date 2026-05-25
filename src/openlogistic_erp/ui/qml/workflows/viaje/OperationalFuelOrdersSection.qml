pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import "../../shared/controls"
import "../../shared/tables"
import "../../shared/theme"

Item {
    id: root

    required property var formViewModel
    readonly property bool readOnly: formViewModel ? formViewModel.is_read_only : true
    property int selectedRow: -1

    signal saveSucceeded()

    width: parent ? parent.width : implicitWidth

    Theme {
        id: theme
    }

    function rowValue(index, fieldName) {
        const rows = root.formViewModel ? root.formViewModel.rows : []
        if (index < 0 || index >= rows.length) {
            return ""
        }
        const value = rows[index][fieldName]
        if (value === undefined || value === null) {
            return ""
        }
        return value
    }

    function optionsFor(fieldName) {
        const fields = root.formViewModel ? root.formViewModel.row_fields : []
        for (let index = 0; index < fields.length; ++index) {
            if (fields[index].name === fieldName) {
                return fields[index].options || []
            }
        }
        return []
    }

    function optionIndex(fieldName, value) {
        const options = root.optionsFor(fieldName)
        for (let index = 0; index < options.length; ++index) {
            if (options[index].value === value) {
                return index
            }
        }
        return -1
    }

    function cellValue(row, column) {
        if (!root.formViewModel || !root.formViewModel.table_model) {
            return ""
        }
        const field = root.formViewModel.table_model.column_field(column)
        return root.rowValue(row, field.name || "")
    }

    function columnWidth(column) {
        const available = root.tableContentWidth
        if (column === 0 || column === 3) {
            return Math.max(190, available * 0.22)
        }
        if (column === 2) {
            return Math.max(150, available * 0.18)
        }
        return Math.max(240, available - (root.columnWidth(0) + root.columnWidth(2) + root.columnWidth(3)))
    }

    readonly property real tableContentWidth: Math.max(760, width - 2)
    readonly property int tableColumnCount: root.formViewModel ? root.formViewModel.row_fields.length : 0
    implicitHeight: contentLayout.implicitHeight

    ColumnLayout {
        id: contentLayout
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: theme.spacing4

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
                wrapMode: Text.WordWrap
                text: root.formViewModel ? root.formViewModel.error_message : ""
                color: theme.danger
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.bodySize
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.formViewModel && (root.formViewModel.field_errors["ordenes_combustible"] || "") !== ""
            text: root.formViewModel ? root.formViewModel.field_errors["ordenes_combustible"] || "" : ""
            color: theme.danger
            font.family: theme.bodyFontFamily
            font.pixelSize: theme.captionSize
            wrapMode: Text.WordWrap
        }

        DetailEditableTable {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(156, Math.min(360, 45 + (root.formViewModel ? root.formViewModel.rows.length * 52 : 52)))
            tableModel: root.formViewModel ? root.formViewModel.table_model : null
            headerModel: root.formViewModel ? root.formViewModel.row_fields : []
            rowCount: root.formViewModel ? root.formViewModel.rows.length : 0
            columnWidthProvider: function(column) { return root.columnWidth(column) }
            emptyText: qsTr("Sin ordenes")
            cellDelegate: Component {
                Rectangle {
                    id: tableCell

                    required property int tableRow
                    required property int tableColumn
                    required property var tableRowData
                    required property int tableRowIndex

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

                    function safeRowValue() {
                        if (!cellReady || fieldName === "")
                            return ""
                        return root.rowValue(tableRowIndex, fieldName)
                    }

                    function safeRowError() {
                        if (!cellReady || fieldName === "")
                            return ""
                        return root.formViewModel.row_error(tableRowIndex, fieldName)
                    }

                    color: root.selectedRow === tableRowIndex
                        ? theme.primaryFixed
                        : tableRowIndex % 2 === 0 ? theme.surfaceRaised : theme.surfaceLow

                    border.width: safeRowError() !== "" ? 1 : 0
                    border.color: border.width > 0 ? theme.danger : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        enabled: tableCell.cellReady
                        onPressed: root.selectedRow = tableCell.tableRowIndex
                    }

                    AppTextField {
                        anchors.fill: parent
                        anchors.margins: theme.spacing2
                        visible: tableCell.cellReady && tableCell.field.kind !== "enum"
                        text: tableCell.cellReady ? String(tableCell.safeRowValue()) : ""
                        enabled: tableCell.cellReady && !root.readOnly
                        invalid: tableCell.safeRowError() !== ""
                        validator: tableCell.fieldName === "galones_autorizados" ? galonesValidator : null

                        onActiveFocusChanged: {
                            if (activeFocus && tableCell.cellReady)
                                root.selectedRow = tableCell.tableRowIndex
                        }

                        onTextEdited: {
                            if (!tableCell.cellReady)
                                return

                            root.formViewModel.table_model.set_cell_value(
                                tableCell.tableRowIndex,
                                tableCell.tableColumn,
                                text
                            )
                        }
                    }

                    AppComboBox {
                        anchors.fill: parent
                        anchors.margins: theme.spacing2
                        visible: tableCell.cellReady && tableCell.field.kind === "enum"
                        model: tableCell.cellReady ? (tableCell.field.options || []) : []
                        enabled: tableCell.cellReady && !root.readOnly
                        textRole: "label"
                        valueRole: "value"
                        currentIndex: tableCell.cellReady
                            ? root.optionIndex(tableCell.fieldName, tableCell.safeRowValue())
                            : -1
                        invalid: tableCell.safeRowError() !== ""

                        onActiveFocusChanged: {
                            if (activeFocus && tableCell.cellReady)
                                root.selectedRow = tableCell.tableRowIndex
                        }

                        onActivated: function(optionIndexValue) {
                            if (!tableCell.cellReady)
                                return

                            const options = tableCell.field.options || []
                            const option = options[optionIndexValue]

                            if (option) {
                                root.formViewModel.table_model.set_cell_value(
                                    tableCell.tableRowIndex,
                                    tableCell.tableColumn,
                                    option.value
                                )
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            visible: !root.readOnly
            spacing: theme.spacing3

            AppButton {
                variant: "ghost"
                text: qsTr("Agregar orden")
                enabled: root.formViewModel ? !root.readOnly : false
                onClicked: root.formViewModel.add_row()
            }

            AppButton {
                variant: "ghost"
                text: qsTr("Quitar orden")
                enabled: root.formViewModel && root.selectedRow >= 0 && !root.readOnly
                onClicked: {
                    root.formViewModel.remove_row(root.selectedRow)
                    root.selectedRow = Math.min(root.selectedRow, root.formViewModel.rows.length - 1)
                }
            }

            AppButton {
                variant: "ghost"
                text: qsTr("Restablecer seccion")
                enabled: root.formViewModel ? root.formViewModel.is_dirty && !root.readOnly : false
                onClicked: root.formViewModel.reset_section()
            }

            AppButton {
                variant: "secondary"
                text: qsTr("Guardar seccion")
                enabled: root.formViewModel ? !root.formViewModel.is_busy && !root.readOnly : false
                onClicked: {
                    if (root.formViewModel.save_section()) {
                        root.saveSucceeded()
                    }
                }
            }
        }
    }

    DoubleValidator {
        id: galonesValidator
        notation: DoubleValidator.StandardNotation
        locale: "C"
        decimals: 2
    }
}
