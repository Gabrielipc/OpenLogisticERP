pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../../shared/theme"

Item {
    id: root

    required property var detailViewModel
    property real wheelStep: theme.spacing6

    Theme {
        id: theme
    }

    function safeObject(value) {
        return value === undefined || value === null ? ({}) : value
    }

    function safeList(value) {
        return value === undefined || value === null ? [] : value
    }

    function safeString(value) {
        return value === undefined || value === null ? "" : String(value)
    }

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
            return (event.angleDelta.y / 120) * root.wheelStep
        }
        return 0
    }

    ScrollView {
        id: detailScroll

        anchors.fill: parent
        clip: true

        ColumnLayout {
            id: detailLayout

            width: detailScroll.availableWidth
            spacing: theme.spacing4

            readonly property var summary: root.safeObject(root.detailViewModel ? root.detailViewModel.summary : null)
            readonly property var viaje: root.safeObject(root.detailViewModel ? root.detailViewModel.viaje_summary : null)
            readonly property var visibleSections: root.safeList(root.detailViewModel ? root.detailViewModel.visible_sections : null)
            readonly property string errorMessage: root.safeString(root.detailViewModel ? root.detailViewModel.error_message : null)

           GridLayout {
                id: responsiveGrid

                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                columns: detailLayout.width > 600 ? 2 : 1
                columnSpacing: theme.spacing4
                rowSpacing: theme.spacing4

                ViajeDetailSummaryPanel {
                    viaje: detailLayout.viaje

                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    Layout.maximumWidth: responsiveGrid.columns === 2 ? 450 : -1
                }
                
                ViajeDetailOperationsPanel {
                    detailViewModel: root.detailViewModel
                    summary: detailLayout.summary
                    visibleSections: detailLayout.visibleSections
                    errorMessage: detailLayout.errorMessage
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                }
            }
            Item {
            Layout.fillHeight: true
            }   
        }
    }

    MouseArea {
        parent: detailScroll
        anchors.fill: parent
        z: 1
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true

        onWheel: function(event) {
            const flickable = detailScroll.contentItem
            if (!flickable) {
                return
            }

            const deltaY = root.normalizedWheelDelta(event)
            if (deltaY === 0) {
                return
            }

            const currentContentY = Number(flickable["contentY"] || 0)
            const nextContentY = Math.max(0, Math.min(root.maxScrollY(detailScroll), currentContentY - deltaY))
            if (nextContentY === currentContentY) {
                return
            }

            flickable["contentY"] = nextContentY
            event.accepted = true
        }
    }
}
