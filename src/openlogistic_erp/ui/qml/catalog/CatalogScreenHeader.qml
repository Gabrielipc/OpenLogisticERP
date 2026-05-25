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

Item {
    id: header

    property string title: ""
    property string subtitle: ""
    property bool canCreate: false
    property bool canExport: false
    property bool exportSelectionMode: false
    property int selectedExportCount: 0

    signal createRequested()
    signal refreshRequested()
    signal exportSelectionRequested()
    signal exportSelectedRequested()
    signal exportSelectionCancelled()

    implicitHeight: contentLayout.implicitHeight

    Theme {
        id: theme
    }

    RowLayout {
        id: contentLayout

        anchors.fill: parent
        spacing: theme.spacing4

        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 0
            Layout.minimumWidth: 0
            spacing: 2

            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: header.title
                color: theme.textPrimary
                font.family: theme.headlineFontFamily
                font.pixelSize: theme.displaySize
                font.bold: true
                elide: Text.ElideRight
            }

            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: header.subtitle
                color: theme.textSecondary
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.bodySize
                wrapMode: Text.WordWrap
            }
        }

        AppButton {
            variant: "contrast"
            visible: header.canCreate
            text: qsTr("Nuevo")
            onClicked: header.createRequested()
        }

        AppButton {
            variant: header.exportSelectionMode ? "contrast" : "secondary"
            visible: header.canExport
            text: header.exportSelectionMode
                ? qsTr("Exportar (%1)").arg(header.selectedExportCount)
                : qsTr("Exportar Excel")
            enabled: !header.exportSelectionMode || header.selectedExportCount > 0
            onClicked: {
                if (header.exportSelectionMode) {
                    header.exportSelectedRequested()
                } else {
                    header.exportSelectionRequested()
                }
            }
        }

        AppButton {
            variant: "ghost"
            visible: header.canExport && header.exportSelectionMode
            text: qsTr("Cancelar")
            onClicked: header.exportSelectionCancelled()
        }

        AppButton {
            variant: "secondary"
            iconSource: "qrc:/actions/control/refresh"
            text: qsTr("Refrescar")
            onClicked: header.refreshRequested()
        }
    }
}
