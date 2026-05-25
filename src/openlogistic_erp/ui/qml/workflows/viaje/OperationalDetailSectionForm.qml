pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../shared/controls"
import "../../shared/theme"
import "../viaje/fields"

Item {
    id: root

    required property var formViewModel
    readonly property bool twoColumnLayout: width > 760
    readonly property bool readOnly: formViewModel ? formViewModel.is_read_only : true
    property var layoutItems: []

    signal saveSucceeded()

    Theme {
        id: theme
    }

    implicitHeight: contentLayout.implicitHeight

    function refreshLayoutItems() {
        root.layoutItems = root.formViewModel ? root.formViewModel.layout_items : []
    }

    Component.onCompleted: root.refreshLayoutItems()

    onFormViewModelChanged: root.refreshLayoutItems()

    Connections {
        target: root.formViewModel

        function onLayoutItemsChanged() {
            root.refreshLayoutItems()
        }
    }

    ColumnLayout {
        id: contentLayout
        anchors.fill: parent
        spacing: theme.spacing4

        Rectangle {
            Layout.fillWidth: true
            visible: root.formViewModel ? root.formViewModel.error_message !== "" : false
            radius: theme.radiusMedium
            color: theme.dangerContainer
            implicitHeight: formErrorLabel.implicitHeight + theme.spacing5

            Label {
                id: formErrorLabel
                anchors.fill: parent
                anchors.margins: theme.spacing4
                wrapMode: Text.WordWrap
                text: root.formViewModel ? root.formViewModel.error_message : ""
                color: theme.danger
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.bodySize
            }
        }

        Repeater {
            model: root.layoutItems

            delegate: ColumnLayout {
                id: sectionContainer

                Layout.fillWidth: true
                required property var modelData
                spacing: theme.spacing2

                Label {
                    Layout.fillWidth: true
                    visible: sectionContainer.modelData.type === "section"
                    text: sectionContainer.modelData.title || ""
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.sectionTitleSize
                    font.bold: true
                }

                Rectangle {
                    Layout.fillWidth: true
                    visible: sectionContainer.modelData.type === "section"
                    implicitHeight: 1
                    color: theme.outlineVariant
                    opacity: 0.65
                }

                GridLayout {
                    Layout.fillWidth: true
                    visible: sectionContainer.modelData.type === "row"
                    columns: root.twoColumnLayout ? 2 : 1
                    columnSpacing: theme.spacing4
                    rowSpacing: theme.spacing4

                    Repeater {
                        model: sectionContainer.modelData.type === "row" ? sectionContainer.modelData.fields : []

                        delegate: OperationalDetailFieldRenderer {
                            required property var modelData

                            formViewModel: root.formViewModel
                            field: modelData
                            readOnly: root.readOnly
                            columnSpan: root.twoColumnLayout ? Number(modelData.span || 1) : 1
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
                text: qsTr("Restablecer sección")
                enabled: root.formViewModel ? root.formViewModel.is_dirty && !root.readOnly : false
                onClicked: root.formViewModel.reset_section()
            }

            AppButton {
                variant: "secondary"
                text: qsTr("Guardar sección")
                enabled: root.formViewModel ? !root.formViewModel.is_busy && !root.readOnly : false
                onClicked: {
                    if (root.formViewModel.save_section()) {
                        root.saveSucceeded()
                    }
                }
            }
        }
    }
}
