pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "../shared/controls"
import "../shared/surfaces"
import "../shared/theme"
import "../workflows/common"

Item {
    id: page

    required property AppShellViewModel appShellViewModel
    readonly property var dashboardViewModel: page.appShellViewModel ? page.appShellViewModel.dashboard_view_model : null

    Theme { id: theme }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacing4

        WorkflowSubpageHeader {
            Layout.fillWidth: true
            baseTitle: qsTr("Clientes")
            currentTitle: qsTr("Cuentas por cobrar por cliente")
            onNavigateBackRequested: page.appShellViewModel.navigate_to({"module_id": "cliente", "target": "list"})
            onCloseRequested: page.appShellViewModel.navigate_to({"module_id": "cliente", "target": "list"})
        }

        SurfaceCard {
            Layout.fillWidth: true
            Layout.fillHeight: true
            tone: "raised"

            ListView {
                anchors.fill: parent
                clip: true
                spacing: theme.spacing3
                model: page.dashboardViewModel ? page.dashboardViewModel.clientDebtRows : []

                delegate: AutoHeightSurfaceCard {
                    required property var modelData
                    readonly property var clientRow: modelData
                    readonly property bool hasMultipleCurrencies: (clientRow.saldos_por_moneda || []).length > 1
                    property bool expanded: false
                    id: debtCard
                    width: ListView.view.width
                    tone: "low"
                    padding: theme.spacing4
                    heightSource: debtLayout

                    ColumnLayout {
                        id: debtLayout
                        anchors.fill: parent
                        spacing: theme.spacing2

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: debtHeaderLayout.implicitHeight
                        color: "transparent"

                        TapHandler {
                            acceptedButtons: Qt.LeftButton
                            onTapped: debtCard.expanded = !debtCard.expanded
                        }

                            RowLayout {
                                id: debtHeaderLayout
                                anchors.fill: parent
                                spacing: theme.spacing2

                                AppIcon {
                                    size: 24
                                    tintColor: theme.textPrimary
                                    source: debtCard.expanded ? "qrc:/actions/control/drop_down" : "qrc:/actions/control/drop_right" 
                                }
                                TextInput {
                                id: clientDebtSelectableText

                                    Layout.fillWidth: true
                                    text: String(debtCard.modelData.cliente_label || "")
                                    font.bold: true
                                readOnly: true
                                selectByMouse: true
                                selectedTextColor: theme.surfaceRaised
                                selectionColor: theme.primary
                                color: theme.textPrimary
                                }
                                Label {
                                    text: qsTr("%1 %2")
                                        .arg(debtCard.hasMultipleCurrencies ? qsTr("Saldos:") : qsTr("Saldo:"))
                                        .arg(String(debtCard.modelData.saldo_total_display || debtCard.modelData.saldo_total || "0.00"))
                                    font.bold: true
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: debtCard.expanded = !debtCard.expanded
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: theme.spacing2
                            visible: debtCard.expanded

                            Repeater {
                                model: debtCard.clientRow.facturas || []
                                delegate: AutoHeightSurfaceCard {
                                    id: rowCard
                                    required property var modelData
                                    readonly property var invoiceRow: modelData
                                    Layout.fillWidth: true
                                    tone: "default"
                                    padding: theme.spacing3
                                    heightSource: invoiceLayout

                                    RowLayout {
                                        id: invoiceLayout
                                        anchors.fill: parent
                                        spacing: theme.spacing3

                                    TextInput {
                                        Layout.preferredWidth: 180
                                        text: String(rowCard.modelData.numero_factura || "")
                                        font.bold: true
                                        readOnly: true
                                        selectByMouse: true
                                        selectedTextColor: theme.surfaceRaised
                                        selectionColor: theme.primary
                                        color: theme.textPrimary
                                    }

                                    TextInput {
                                        Layout.preferredWidth: 120
                                        text: String(rowCard.modelData.estado || "")
                                        color: theme.textSecondary
                                        readOnly: true
                                        selectByMouse: true
                                        selectedTextColor: theme.surfaceRaised
                                        selectionColor: theme.primary
                                    }

                                    TextInput {
                                        Layout.fillWidth: true
                                        text: qsTr("Saldo: %1").arg(String(rowCard.modelData.saldo_display || "0.00"))
                                        color: theme.textSecondary
                                        readOnly: true
                                        selectByMouse: true
                                        selectedTextColor: theme.surfaceRaised
                                        selectionColor: theme.primary
                                    }

                                        AppButton {
                                            variant: "secondary"
                                            text: qsTr("Crear recibo")
                                            onClicked: {
                                                page.appShellViewModel.navigate_to({
                                                    "module_id": "recibo",
                                                    "target": "create_form_with_context",
                                                    "workflow_context": {
                                                        "cliente_id": debtCard.clientRow.cliente_id,
                                                        "cliente_label": debtCard.clientRow.cliente_label,
                                                        "factura_id": rowCard.invoiceRow.id,
                                                        "numero_factura": rowCard.invoiceRow.numero_factura,
                                                        "search_term": rowCard.invoiceRow.numero_factura
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
