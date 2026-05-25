pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../../shared/theme"

Item {
    id: root

    required property var detailViewModel
    property real wheelStep: theme.spacing6
    property string activeContentMode: "trips"
    signal addReturnTripRequested()
    signal openTripDetailRequested(var viajeId)

    Theme { id: theme }

    function safeObject(value) {
        return value === undefined || value === null ? ({}) : value
    }

    function safeList(value) {
        return value === undefined || value === null ? [] : value
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
            id: detailContent

            width: detailScroll.availableWidth
            spacing: theme.spacing4

            readonly property var circuito: root.safeObject(root.detailViewModel ? root.detailViewModel.circuito_summary : null)
            readonly property var summary: root.safeObject(root.detailViewModel ? root.detailViewModel.summary : null)
            readonly property var ida: root.safeObject(root.detailViewModel ? root.detailViewModel.viaje_ida : null)
            readonly property var vuelta: root.safeObject(root.detailViewModel ? root.detailViewModel.viaje_vuelta : null)
            readonly property var sections: root.safeList(root.detailViewModel ? root.detailViewModel.visible_sections : null)

            CircuitoHeaderPanel {
                Layout.fillWidth: true
                circuito: parent.circuito
                formViewModel: root.detailViewModel ? root.detailViewModel.circuito_form : null
                editable: root.detailViewModel ? root.detailViewModel.can_edit_circuito : false
                onSaved: {
                    if (root.detailViewModel) {
                        root.detailViewModel.reload()
                    }
                }
            }

            TabBar {
                id: tabBar
                Layout.fillWidth: true
                background: Rectangle {
                    radius: theme.radiusLarge
                }
                
                TabButton {
                    text: qsTr("Viajes")
                    checked: root.activeContentMode === "trips"
                    onClicked: root.activeContentMode = "trips"
                }

                TabButton {
                    text: qsTr("Detalles")
                    checked: root.activeContentMode === "details"
                    onClicked: root.activeContentMode = "details"
                }
            }

            Loader {
                id: activeContentLoader

                Layout.fillWidth: true
                sourceComponent: root.activeContentMode === "trips" ? tripsComponent : detailsComponent
            }
        }
    }

    Component {
        id: tripsComponent

        CircuitoTripsPanel {
            width: activeContentLoader.width
            viajeIda: detailContent.ida
            viajeVuelta: detailContent.vuelta
            canAddReturnTrip: root.detailViewModel ? root.detailViewModel.can_add_return_trip : false
            onAddReturnTripRequested: root.addReturnTripRequested()
            onOpenTripDetailRequested: viajeId => root.openTripDetailRequested(viajeId)
        }
    }

    Component {
        id: detailsComponent

        CircuitoSectionsPanel {
            width: activeContentLoader.width
            detailViewModel: root.detailViewModel
            summary: detailContent.summary
            visibleSections: detailContent.sections
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
