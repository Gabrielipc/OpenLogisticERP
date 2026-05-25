pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../../shared/controls"
import "../../../shared/surfaces"
import "../../../shared/theme"
import "../../../catalog"
import "../../common"
import ".."

AutoHeightSurfaceCard {
    id: root

    required property var detailViewModel
    required property var summary
    required property var visibleSections
    property string errorMessage: ""
    property bool reopenConfirmationOpen: false
    property bool saveConfirmationOpen: false
    readonly property bool detailClosed: root.detailViewModel ? root.detailViewModel.is_closed : false
    readonly property var sectionRegistry: ({
        "descarga": descargaSectionComponent,
        "combustible_thermo": thermoSectionComponent,
        "ordenes_combustible": ordersSectionComponent
    })

    Layout.fillWidth: true
    Layout.alignment: Qt.AlignTop
    tone: "raised"
    padding: theme.spacing5
    heightSource: operationsLayout

    Theme {
        id: theme
    }

    function tabLabel(sectionKey) {
        if (!root.detailViewModel) {
            return sectionKey
        }
        const state = root.detailViewModel.section_state(sectionKey)
        let label = state.title || sectionKey
        if (state.valid === false) {
            label += " !"
        } else if (state.dirty === true) {
            label += " *"
        }
        return label
    }

    function tabIndexForKey(sectionKey) {
        if (!root.detailViewModel || !root.visibleSections) {
            return 0
        }
        for (let index = 0; index < root.visibleSections.length; ++index) {
            if (root.visibleSections[index] === sectionKey) {
                return index
            }
        }
        return 0
    }

    function activeSectionKey() {
        return root.detailViewModel ? root.detailViewModel.active_tab : ""
    }

    function hasVisibleSection(sectionKey) {
        if (!root.visibleSections) {
            return false
        }
        for (let index = 0; index < root.visibleSections.length; ++index) {
            if (root.visibleSections[index] === sectionKey) {
                return true
            }
        }
        return false
    }

    function componentForSection(sectionKey) {
        if (!root.hasVisibleSection(sectionKey)) {
            return null
        }
        return root.sectionRegistry[sectionKey] || null
    }

    ColumnLayout {
        id: operationsLayout
        anchors.fill: parent
        spacing: theme.spacing4

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing3

            ColumnLayout {
                Layout.fillWidth: true
                spacing: theme.spacing2

                Label {
                    text: qsTr("Detalle operativo")
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.titleSize
                    font.bold: true
                }

                Label {
                    text: (root.summary.detalle_operacion || {}).estado || qsTr("Sin detalle")
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.bodySize
                }
            }

            AppButton {
                variant: "secondary"
                text: qsTr("Guardar todo")
                visible: !root.detailClosed
                enabled: root.detailViewModel ? !root.detailViewModel.is_busy && root.detailViewModel.can_save_all : false
                onClicked: {
                    if (root.detailViewModel.save_all()) {
                        root.saveConfirmationOpen = true
                    }
                }
            }

            AppButton {
                variant: "danger"
                text: qsTr("Cerrar detalle")
                visible: !root.detailClosed
                enabled: root.detailViewModel ? !root.detailViewModel.is_busy && root.detailViewModel.can_save_all : false
                onClicked: root.detailViewModel.close_detail()
            }

            AppButton {
                variant: "secondary"
                text: qsTr("Reabrir")
                visible: root.detailClosed
                enabled: root.detailViewModel ? !root.detailViewModel.is_busy : false
                onClicked: root.reopenConfirmationOpen = true
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.errorMessage !== ""
            text: root.errorMessage
            color: theme.danger
            wrapMode: Text.WordWrap
            font.family: theme.bodyFontFamily
            font.pixelSize: theme.captionSize
        }

        TabBar {
            id: detailTabs

            Layout.fillWidth: true
            visible: root.visibleSections.length > 0
            currentIndex: root.tabIndexForKey(root.detailViewModel ? root.detailViewModel.active_tab : "")

            onCurrentIndexChanged: {
                if (!root.detailViewModel || currentIndex < 0 || currentIndex >= root.visibleSections.length) {
                    return
                }
                root.detailViewModel.set_active_tab(root.visibleSections[currentIndex])
            }

            Repeater {
                model: root.visibleSections

                delegate: TabButton {
                    id: tabButton

                    required property var modelData

                    text: root.tabLabel(modelData)
                    width: implicitWidth
                    implicitWidth: tabText.implicitWidth + leftPadding + rightPadding
                    leftPadding: theme.spacing4
                    rightPadding: theme.spacing4

                    contentItem: Label {
                        id: tabText

                        text: tabButton.text
                        color: tabButton.checked ? theme.primary : theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.family: theme.bodyFontFamily
                        font.pixelSize: theme.bodySize
                        font.bold: tabButton.checked
                    }
                }
            }
        }

        Loader {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            active: root.detailViewModel !== null
            sourceComponent: root.componentForSection(root.activeSectionKey())
        }
    }

    CatalogScreenConfirmDialog {
        anchors.fill: parent
        open: root.reopenConfirmationOpen
        title: qsTr("Confirmar reapertura")
        message: qsTr("Reabrir este viaje solo es recomendable si se cometio algun error grabando la informacion.")
        confirmText: qsTr("Reabrir")
        cancelText: qsTr("Cancelar")
        confirmEnabled: root.detailViewModel ? !root.detailViewModel.is_busy : false
        onCancelRequested: root.reopenConfirmationOpen = false
        onConfirmRequested: {
            if (root.detailViewModel) {
                root.detailViewModel.reopen_detail()
            }
            root.reopenConfirmationOpen = false
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
        id: descargaSectionComponent

        OperationalDetailSectionForm {
            width: parent.width
            formViewModel: root.detailViewModel ? root.detailViewModel.descarga_form : null
            onSaveSucceeded: root.saveConfirmationOpen = true
        }
    }

    Component {
        id: thermoSectionComponent

        ColumnLayout {
            width: parent.width
            spacing: theme.spacing4

            ConsumoAnalysisCards {
                Layout.fillWidth: true
                analysis: root.summary.consumo_thermo_analysis || ({})
                analysisType: "THERMO"
                availableWidth: parent.width
            }

            OperationalDetailSectionForm {
                Layout.fillWidth: true
                formViewModel: root.detailViewModel ? root.detailViewModel.combustible_thermo_form : null
                onSaveSucceeded: root.saveConfirmationOpen = true
            }
        }
    }

    Component {
        id: ordersSectionComponent

        OperationalFuelOrdersSection {
            width: parent.width
            formViewModel: root.detailViewModel ? root.detailViewModel.ordenes_combustible_form : null
            onSaveSucceeded: root.saveConfirmationOpen = true
        }
    }
}
