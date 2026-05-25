pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "../../../shared/controls"
import "../../../shared/forms"
import "../../../shared/surfaces"
import "../../../shared/theme"

AutoHeightSurfaceCard {
    id: root

    required property var circuito
    required property GenericCatalogFormViewModel formViewModel
    property bool editable: false
    signal saved()

    padding: theme.spacing5

    Layout.fillWidth: true
    Layout.minimumWidth: 0
    heightSource: content
    Theme { id: theme }

    ColumnLayout {
        id: content

        anchors.fill: parent
        spacing: theme.spacing4

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing3

            Label {
                Layout.fillWidth: true
                text: qsTr("Circuito #%1").arg(root.circuito.id || "")
                color: theme.textPrimary
                font.family: theme.headlineFontFamily
                font.pixelSize: theme.titleSize
                font.bold: true
                elide: Text.ElideRight
            }

            Label {
                visible: !root.editable
                text: root.circuito.estado || ""
                color: theme.textSecondary
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.bodySize
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: root.width > 720 ? 3 : 1
            columnSpacing: theme.spacing4
            rowSpacing: theme.spacing4

            Repeater {
                model: root.formViewModel ? root.formViewModel.fields : []

                delegate: FormFieldRenderer {
                    required property var modelData

                    Layout.fillWidth: true
                    field: modelData
                    formViewModel: root.formViewModel
                    readOnly: !root.editable
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: root.editable
            spacing: theme.spacing3

            Item {
                Layout.fillWidth: true
            }

            AppButton {
                text: qsTr("Guardar cambios")
                enabled: root.formViewModel ? root.formViewModel.is_dirty && !root.formViewModel.is_busy : false
                onClicked: {
                    if (root.formViewModel.submit_form()) {
                        root.saved()
                    }
                }
            }
        }
    }
}
