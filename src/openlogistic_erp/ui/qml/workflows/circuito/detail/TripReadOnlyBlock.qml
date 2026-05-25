pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../../shared/forms"
import "../../../shared/theme"

Rectangle {
    id: root

    required property string title
    required property var viaje
    property bool emptyActionVisible: false
    property bool existingActionVisible: false
    property string existingActionText: qsTr("Ver detalle operativo")
    signal addRequested()
    signal existingActionRequested()

    radius: theme.radiusMedium
    color: theme.surface
    border.color: theme.outlineVariant
    implicitHeight: content.implicitHeight + theme.spacing4 * 2

    Theme { id: theme }

    ReadOnlySummaryFields {
        id: content

        anchors.fill: parent
        anchors.margins: theme.spacing4
        title: root.viaje && root.viaje.id !== undefined ? (root.viaje.referencia || root.title) : root.title
        description: root.viaje ? (root.viaje.descripcion || "") : ""
        empty: !root.viaje || root.viaje.id === undefined
        emptyText: qsTr("Sin viaje registrado")
        actionVisible: root.emptyActionVisible && (!root.viaje || root.viaje.id === undefined)
        actionText: qsTr("Agregar viaje de vuelta")
        secondaryActionVisible: root.existingActionVisible && root.viaje && root.viaje.id !== undefined
        secondaryActionText: root.existingActionText
        fields: [
            { label: qsTr("Tipo"), value: root.viaje ? root.viaje.tipo_viaje : "" },
            { label: qsTr("Estado"), value: root.viaje ? root.viaje.estado : "" },
            { label: qsTr("Cliente"), value: root.viaje ? root.viaje.cliente_label : "" },
            { label: qsTr("Conductor"), value: root.viaje ? root.viaje.conductor_label : "" },
            { label: qsTr("Ruta"), value: root.viaje ? root.viaje.ruta_label : "" },
            { label: qsTr("Camion"), value: root.viaje ? root.viaje.camion_label : "" },
            { label: qsTr("Furgon"), value: root.viaje ? root.viaje.furgon_label : "" },
            { label: qsTr("Thermo"), value: root.viaje ? root.viaje.thermo_label : "" },
            { label: qsTr("Posicionamiento"), value: root.viaje ? root.viaje.fecha_posicionamiento : "" },
            { label: qsTr("Descarga"), value: root.viaje ? root.viaje.fecha_descarga : "" }
        ]
        onActionRequested: root.addRequested()
        onSecondaryActionRequested: root.existingActionRequested()
    }
}
