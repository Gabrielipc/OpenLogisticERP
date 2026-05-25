pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../../catalog"
import "../../../shared/surfaces"
import "../../../shared/theme"
import "../../common"
import "../../viaje"

AutoHeightSurfaceCard {
    id: root

    required property var detailViewModel
    required property var summary
    property var visibleSections: []
    property bool saveConfirmationOpen: false
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    padding: theme.spacing5
    heightSource: content

    Theme { id: theme }

    ColumnLayout {
        id: content
        anchors.fill: parent
        spacing: theme.spacing4

        TabBar {
            Layout.fillWidth: true
            Repeater {
                model: root.visibleSections
                delegate: TabButton {
                    required property string modelData
                    text: modelData === "gasto_real_camion" ? qsTr("Consumo camion") : qsTr("Movimientos adicionales")
                    checked: root.detailViewModel && root.detailViewModel.active_tab === modelData
                    onClicked: {
                        if (root.detailViewModel) {
                            root.detailViewModel.set_active_tab(modelData)
                        }
                    }
                }
            }
        }

        Loader {
            Layout.fillWidth: true
            active: !!root.detailViewModel
            sourceComponent: {
                if (!root.detailViewModel) {
                    return undefined
                }
                if (root.detailViewModel.active_tab === "movimientos_adicionales") {
                    return movimientosComponent
                }
                return gastoComponent
            }
        }
    }

    BaseConfirmDialog {
        anchors.fill: parent
        open: root.saveConfirmationOpen
        title: qsTr("Cambios guardados")
        message: qsTr("Se guardaron los cambios correctamente.")
        buttons: [
            {
                role: "accept",
                text: qsTr("Aceptar"),
                variant: "secondary"
            }
        ]
        onDismissed: root.saveConfirmationOpen = false
        onActionRequested: root.saveConfirmationOpen = false
    }

    Component {
        id: gastoComponent

        ColumnLayout {
            width: parent.width
            spacing: theme.spacing4

            ConsumoAnalysisCards {
                Layout.fillWidth: true
                analysis: root.summary.consumo_camion_analysis || ({})
                analysisType: "CAMION"
                availableWidth: parent.width
            }

            OperationalDetailSectionForm {
                Layout.fillWidth: true
                formViewModel: root.detailViewModel ? root.detailViewModel.gasto_real_camion_form : null
                onSaveSucceeded: root.saveConfirmationOpen = true
            }
        }
    }

    Component {
        id: movimientosComponent

        CircuitoMovimientosSection {
            width: parent.width
            formViewModel: root.detailViewModel ? root.detailViewModel.movimientos_adicionales_form : null
            onSaveSucceeded: root.saveConfirmationOpen = true
        }
    }
}
