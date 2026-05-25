pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../../shared/forms"
import "../../../shared/surfaces"
import "../../../shared/theme"

AutoHeightSurfaceCard {
    id: root

    required property var viaje

    Layout.fillWidth: true
    Layout.alignment: Qt.AlignTop
    tone: "raised"
    padding: theme.spacing5
    heightSource: summaryFields

    Theme {
        id: theme
    }

    ReadOnlySummaryFields {
        id: summaryFields

        anchors.fill: parent
        Layout.fillWidth: true
        title: root.viaje.referencia || (`Viaje #${root.viaje.id || ""}`)
        description: root.viaje.descripcion || ""
        fields: [
            { label: qsTr("Tipo"), value: root.viaje.tipo_viaje },
            { label: qsTr("Estado"), value: root.viaje.estado },
            { label: qsTr("Cliente"), value: root.viaje.cliente_label },
            { label: qsTr("Conductor"), value: root.viaje.conductor_label },
            { label: qsTr("Ruta"), value: root.viaje.ruta_label },
            { label: qsTr("Camion"), value: root.viaje.camion_label },
            { label: qsTr("Furgon"), value: root.viaje.furgon_label },
            { label: qsTr("Thermo"), value: root.viaje.thermo_label },
            { label: qsTr("Posicionamiento"), value: root.viaje.fecha_posicionamiento },
            { label: qsTr("Descarga"), value: root.viaje.fecha_descarga }
        ]
    }
}
