pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "../controls"
import "../forms"
import "../theme"

Item {
    id: formPage

    required property GenericCatalogFormViewModel formViewModel
    readonly property int renderedLayoutItemCount: layoutRepeater.count

    Theme {
        id: theme
    }

    readonly property bool twoColumnLayout: width > 820
    property real wheelStep: theme.spacing6

    function maxScrollY(scrollView) {
        const flickable = scrollView ? scrollView.contentItem : null
        if (!flickable) {
            return 0
        }
        return Math.max(0, Number(flickable["contentHeight"] || 0) - Number(flickable.height || 0))
    }

    function normalizedWheelDelta(event) {
        if (event.pixelDelta.y !== 0) {
            return event.pixelDelta.y
        }
        if (event.angleDelta.y !== 0) {
            return (event.angleDelta.y / 120) * formPage.wheelStep
        }
        return 0
    }

    ScrollView {
        id: formScroll

        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: formScroll.availableWidth
            spacing: theme.spacing5

            Rectangle {
                Layout.fillWidth: true
                visible: formPage.formViewModel.error_message !== ""
                radius: theme.radiusMedium
                color: theme.dangerContainer
                implicitHeight: errorLabel.implicitHeight + theme.spacing5

                Label {
                    id: errorLabel

                    anchors.fill: parent
                    anchors.margins: theme.spacing4
                    text: formPage.formViewModel.error_message
                    wrapMode: Text.WordWrap
                    color: theme.danger
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.bodySize
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: theme.spacing4

                Repeater {
                    id: layoutRepeater
                    model: formPage.formViewModel.layout_items

                    delegate: ColumnLayout {
                        Layout.fillWidth: true
                        required property var modelData
                        spacing: theme.spacing2

                        Label {
                            objectName: "layoutSectionLabel"
                            Layout.fillWidth: true
                            visible: modelData.type === "section"
                            text: modelData.title || ""
                            color: theme.textPrimary
                            font.family: theme.headlineFontFamily
                            font.pixelSize: theme.sectionTitleSize
                            font.bold: true
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            visible: modelData.type === "section"
                            implicitHeight: 1
                            color: theme.outlineVariant
                            opacity: 0.65
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            visible: modelData.type === "row"
                            columns: formPage.twoColumnLayout ? 2 : 1
                            columnSpacing: theme.spacing4
                            rowSpacing: theme.spacing4

                            Repeater {
                                model: modelData.type === "row" ? modelData.fields : []

                                delegate: FormFieldRenderer {
                                    objectName: "layoutFieldRenderer"
                                    required property var modelData

                                    field: modelData
                                    formViewModel: formPage.formViewModel
                                    Layout.fillWidth: true
                                    Layout.columnSpan: formPage.twoColumnLayout ? Number(modelData.span || 1) : 1
                                }
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
                    text: qsTr("Cancelar")
                    onClicked: formPage.formViewModel.cancel_form()
                }

                AppButton {
                    variant: "secondary"
                    text: formPage.formViewModel.mode === "edit" ? qsTr("Guardar cambios") : qsTr("Crear")
                    enabled: !formPage.formViewModel.is_busy
                    onClicked: formPage.formViewModel.submit_form()
                }
            }
        }
    }

    MouseArea {
        parent: formScroll
        anchors.fill: parent
        z: 1
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true

        onWheel: function(event) {
            const flickable = formScroll.contentItem
            if (!flickable) {
                return
            }

            const deltaY = formPage.normalizedWheelDelta(event)
            if (deltaY === 0) {
                return
            }

            const currentContentY = Number(flickable["contentY"] || 0)
            const nextContentY = Math.max(0, Math.min(formPage.maxScrollY(formScroll), currentContentY - deltaY))
            if (nextContentY === currentContentY) {
                return
            }

            flickable["contentY"] = nextContentY
            event.accepted = true
        }
    }
}
