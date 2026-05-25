pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../../../shared/surfaces"
import "../../../shared/theme"

AutoHeightSurfaceCard {
    id: root

    heightSource: content
    required property var viajeIda
    required property var viajeVuelta
    property bool canAddReturnTrip: false
    signal addReturnTripRequested()
    signal openTripDetailRequested(var viajeId)

    Layout.fillWidth: true
    Layout.minimumWidth: 0
    padding: theme.spacing5
    Theme { id: theme }

    RowLayout {
        id: content
        anchors.fill: parent
        spacing: theme.spacing4

        TripReadOnlyBlock {
            Layout.fillWidth: true
            title: qsTr("Viaje de ida")
            viaje: root.viajeIda
            existingActionVisible: root.viajeIda && root.viajeIda.id !== undefined
            onExistingActionRequested: root.openTripDetailRequested(root.viajeIda.id)
        }

        TripReadOnlyBlock {
            Layout.fillWidth: true
            title: qsTr("Viaje de vuelta")
            viaje: root.viajeVuelta
            emptyActionVisible: root.canAddReturnTrip
            onAddRequested: root.addReturnTripRequested()
            existingActionVisible: root.viajeVuelta && root.viajeVuelta.id !== undefined
            onExistingActionRequested: root.openTripDetailRequested(root.viajeVuelta.id)
        }
    }
}
