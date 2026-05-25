pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import "../shared/controls"
import "../shared/surfaces"
import "../shared/theme"
import "../workflows/common"

Item {
    id: root

    property var appShellViewModel: null
    required property var moduleViewModel
    property var currentParams: ({})
    property int selectedReportIndex: -1
    property string activeSubpage: "selection"
    property int filterPanelRevision: 0

    Theme {
        id: theme
    }

    function reportTitle() {
        return root.moduleViewModel && root.moduleViewModel.selected_report.title
            ? root.moduleViewModel.selected_report.title
            : qsTr("Reporte")
    }

    function reportSummary() {
        return root.moduleViewModel && root.moduleViewModel.selected_report.summary
            ? root.moduleViewModel.selected_report.summary
            : qsTr("Configura filtros y genera una vista previa antes de exportar.")
    }

    function tableAt(index) {
        const tables = root.moduleViewModel ? root.moduleViewModel.tables : []
        if (index < 0 || index >= tables.length) {
            return ({})
        }
        return tables[index]
    }

    function selectReport(index, reportKey) {
        root.selectedReportIndex = index
        root.currentParams = ({})
        root.filterPanelRevision += 1
        if (root.moduleViewModel) {
            root.moduleViewModel.select_report(String(reportKey || ""))
        }
        root.activeSubpage = "filters"
    }

    function generateReport() {
        if (!root.moduleViewModel || root.moduleViewModel.selected_report_key === "") {
            return
        }
        if (root.moduleViewModel.generate(root.currentParams)) {
            root.activeSubpage = "results"
        }
    }

    function closeSubpage() {
        if (root.activeSubpage === "results") {
            root.activeSubpage = "filters"
            return
        }
        root.activeSubpage = "selection"
    }

    function goDashboard() {
        if (root.appShellViewModel) {
            root.appShellViewModel.go_home()
        }
    }

    function urlToPath(url) {
        const value = String(url || "")
        if (value.startsWith("file:///")) {
            return decodeURIComponent(value.substring(8))
        }
        if (value.startsWith("file://")) {
            return decodeURIComponent(value.substring(7))
        }
        return value
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacing5

        Rectangle {
            Layout.fillWidth: true
            visible: root.moduleViewModel ? root.moduleViewModel.error_message !== "" : false
            radius: theme.radiusMedium
            color: theme.dangerContainer
            implicitHeight: errorLabel.implicitHeight + theme.spacing4

            Label {
                id: errorLabel

                anchors.fill: parent
                anchors.margins: theme.spacing3
                text: root.moduleViewModel ? root.moduleViewModel.error_message : ""
                color: theme.danger
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.bodySize
                wrapMode: Text.WordWrap
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.activeSubpage === "selection"

            ColumnLayout {
                anchors.fill: parent
                spacing: theme.spacing5

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.spacing3

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.spacing2

                        ToolButton {
                            id: reportsHomeBreadcrumbButton

                            text: qsTr("Inicio")
                            onClicked: root.goDashboard()

                            background: Item {}
                            padding: 0

                            contentItem: Label {
                                text: reportsHomeBreadcrumbButton.text
                                color: reportsHomeBreadcrumbButton.hovered ? theme.textSecondary : theme.textPrimary
                                font.family: theme.headlineFontFamily
                                font.pixelSize: theme.titleSize
                                font.bold: true
                                elide: Text.ElideRight
                            }
                        }

                        Label {
                            text: ">"
                            color: theme.textSecondary
                            font.family: theme.bodyFontFamily
                            font.pixelSize: theme.bodySize
                            font.bold: true
                        }

                        Label {
                            Layout.fillWidth: true
                            text: qsTr("Reportes")
                            color: theme.textPrimary
                            font.family: theme.headlineFontFamily
                            font.pixelSize: theme.titleSize
                            font.bold: true
                            elide: Text.ElideRight
                        }
                    }

                    AppButton {
                        text: qsTr("Volver al dashboard")
                        variant: "ghost"
                        onClicked: root.goDashboard()
                    }
                }

                GridView {
                    id: reportsGrid

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    cellWidth: Math.max(260, Math.floor(width / Math.max(1, Math.floor(width / 320))))
                    cellHeight: 132
                    model: root.moduleViewModel ? root.moduleViewModel.reports : []

                    delegate: ItemDelegate {
                        id: reportDelegate

                        required property int index
                        required property var modelData

                        width: reportsGrid.cellWidth - theme.spacing3
                        height: reportsGrid.cellHeight - theme.spacing3
                        highlighted: root.selectedReportIndex === index
                        onClicked: root.selectReport(index, modelData.key)

                        background: SurfaceCard {
                            tone: reportDelegate.highlighted || reportDelegate.hovered ? "raised" : "flat"
                            padding: theme.spacing4
                        }

                        contentItem: ColumnLayout {
                            spacing: theme.spacing2

                            Label {
                                Layout.fillWidth: true
                                text: String(reportDelegate.modelData.title || "")
                                color: theme.textPrimary
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.bodySize
                                font.bold: true
                                elide: Text.ElideRight
                            }

                            Label {
                                Layout.fillWidth: true
                                text: String(reportDelegate.modelData.summary || "")
                                color: theme.textSecondary
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.captionSize
                                wrapMode: Text.WordWrap
                                maximumLineCount: 3
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.activeSubpage === "filters"

            ColumnLayout {
                anchors.fill: parent
                spacing: theme.spacing4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.spacing4

                    WorkflowSubpageHeader {
                        Layout.fillWidth: true
                        baseTitle: qsTr("Inicio")
                        currentTitle: root.reportTitle()
                        subtitle: root.reportSummary()
                        showClose: true
                        closeText: qsTr("Atrás")
                        onNavigateBackRequested: root.goDashboard()
                        onCloseRequested: root.closeSubpage()
                    }

                    AppButton {
                        Layout.alignment: Qt.AlignTop
                        text: qsTr("Volver al dashboard")
                        variant: "ghost"
                        onClicked: root.goDashboard()
                    }

                    AppButton {
                        Layout.alignment: Qt.AlignTop
                        text: qsTr("Generar")
                        variant: "contrast"
                        enabled: root.moduleViewModel && root.moduleViewModel.selected_report_key !== ""
                        onClicked: root.generateReport()
                    }
                }

                SurfaceCard {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    tone: "raised"
                    padding: theme.spacing5

                    ScrollView {
                        anchors.fill: parent
                        clip: true

                        Loader {
                            id: filterPanelLoader

                            width: parent.width
                            sourceComponent: reportFilterPanelComponent
                            property int revision: root.filterPanelRevision
                            onRevisionChanged: {
                                sourceComponent = null
                                sourceComponent = reportFilterPanelComponent
                            }
                        }
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.activeSubpage === "results"

            ColumnLayout {
                anchors.fill: parent
                spacing: theme.spacing4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.spacing4

                    WorkflowSubpageHeader {
                        Layout.fillWidth: true
                        baseTitle: qsTr("Inicio")
                        currentTitle: qsTr("Resultados")
                        showClose: true
                        closeText: qsTr("Cerrar")
                        onNavigateBackRequested: root.goDashboard()
                        onCloseRequested: root.closeSubpage()
                    }

                    AppButton {
                        text: qsTr("Volver al dashboard")
                        variant: "ghost"
                        onClicked: root.goDashboard()
                    }

                    AppButton {
                        text: qsTr("PDF")
                        variant: "contrast"
                        enabled: root.moduleViewModel && root.moduleViewModel.tables.length > 0
                        onClicked: pdfDialog.open()
                    }

                    AppButton {
                        text: qsTr("Excel")
                        variant: "contrast"
                        enabled: root.moduleViewModel && root.moduleViewModel.tables.length > 0
                        onClicked: xlsxDialog.open()
                    }
                }

                SurfaceCard {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    tone: "raised"
                    padding: theme.spacing5

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: theme.spacing4

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: theme.spacing3

                            AppComboBox {
                                id: tableSelector

                                Layout.preferredWidth: 260
                                textRole: "title"
                                valueRole: "key"
                                model: root.moduleViewModel ? root.moduleViewModel.tables : []
                                enabled: model.length > 0
                                onActivated: root.moduleViewModel.select_table(currentIndex)
                            }

                            AppComboBox {
                                id: currencySelector

                                Layout.preferredWidth: 160
                                textRole: "label"
                                valueRole: "key"
                                model: root.moduleViewModel ? root.moduleViewModel.currencies : []
                                visible: model.length > 0
                                enabled: visible
                                onActivated: root.moduleViewModel.select_currency(currentValue || "")
                            }

                            Item {
                                Layout.fillWidth: true
                            }

                            BusyIndicator {
                                running: root.moduleViewModel ? root.moduleViewModel.busy : false
                                visible: running
                            }
                        }

                        ReportPreviewTable {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            tableMeta: root.tableAt(root.moduleViewModel ? root.moduleViewModel.active_table_index : -1)
                            tableModel: root.moduleViewModel ? root.moduleViewModel.active_table_model : null
                        }
                    }
                }
            }
        }
    }

    FileDialog {
        id: pdfDialog

        title: qsTr("Exportar PDF")
        fileMode: FileDialog.SaveFile
        nameFilters: [qsTr("PDF (*.pdf)")]
        onAccepted: root.moduleViewModel.export_pdf(root.urlToPath(selectedFile))
    }

    Component {
        id: reportFilterPanelComponent

        ReportFilterPanel {
            width: filterPanelLoader.width
            moduleViewModel: root.moduleViewModel
            filters: root.moduleViewModel ? root.moduleViewModel.filters : []
            onParamsChanged: root.currentParams = params
        }
    }

    FileDialog {
        id: xlsxDialog

        title: qsTr("Exportar Excel")
        fileMode: FileDialog.SaveFile
        nameFilters: [qsTr("Excel (*.xlsx)")]
        onAccepted: root.moduleViewModel.export_xlsx(root.urlToPath(selectedFile))
    }
}
