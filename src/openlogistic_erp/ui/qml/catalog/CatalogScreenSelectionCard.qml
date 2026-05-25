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

SurfaceCard {
    id: selectionCard

    property var screenViewModel: null
    property var selectedRow: null

    signal editRequested()

    tone: "low"
    padding: theme.spacing4

    Theme {
        id: theme
    }

    function displayValue(value) {
        if (value === true) {
            return qsTr("Si")
        }
        if (value === false) {
            return qsTr("No")
        }
        if (value === undefined || value === null) {
            return ""
        }
        return String(value)
    }

    function rowValue(key) {
        if (!selectionCard.selectedRow
                || selectionCard.selectedRow[key] === undefined
                || selectionCard.selectedRow[key] === null) {
            return ""
        }
        return selectionCard.selectedRow[key]
    }

    function previewColumns() {
        if (!selectionCard.screenViewModel) {
            return []
        }
        return selectionCard.screenViewModel.columns.filter(function(column) {
            return column.kind === "data" && column.key !== "id"
        }).slice(0, 3)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacing3

        Label {
            text: qsTr("Seleccion")
            color: theme.textPrimary
            font.family: theme.headlineFontFamily
            font.pixelSize: theme.sectionTitleSize
            font.bold: true
        }

        Label {
            Layout.fillWidth: true
            text: selectionCard.selectedRow
                ? qsTr("Registro #%1").arg(selectionCard.selectedRow.id)
                : qsTr("Sin seleccion")
            color: theme.textPrimary
            font.family: theme.bodyFontFamily
            font.pixelSize: theme.bodySize
            font.bold: true
            wrapMode: Text.WordWrap
        }

        Repeater {
            model: selectionCard.previewColumns()

            delegate: ColumnLayout {
                required property var modelData

                Layout.fillWidth: true
                spacing: 2

                Label {
                    Layout.fillWidth: true
                    text: modelData.header
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                    font.bold: true
                    elide: Text.ElideRight
                }

                Label {
                    Layout.fillWidth: true
                    text: selectionCard.selectedRow
                        ? selectionCard.displayValue(selectionCard.rowValue(modelData.key))
                        : ""
                    color: theme.textPrimary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.bodySize
                    wrapMode: Text.WordWrap
                }
            }
        }

        Item {
            Layout.fillHeight: true
        }

        AppButton {
            Layout.fillWidth: true
            compact: true
            variant: "secondary"
            text: qsTr("Editar seleccion")
            enabled: selectionCard.screenViewModel ? selectionCard.screenViewModel.selected_row_index >= 0 : false
            onClicked: selectionCard.editRequested()
        }
    }
}
