pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../../shared/surfaces"
import "../../shared/theme"

GridLayout {
    id: root

    required property var analysis
    property string analysisType: ""
    property real availableWidth: width

    Layout.fillWidth: true
    columns: root.analysisType === "THERMO"
        ? (root.availableWidth > 500 ? 5 : root.availableWidth > 300 ? 2 : 1)
        : (root.availableWidth > 500 ? 3 : root.availableWidth > 300 ? 2 : 1)
    columnSpacing: theme.spacing4
    rowSpacing: theme.spacing4
    visible: root.analysis && root.analysis.type !== undefined && root.analysis.type !== ""

    Theme {
        id: theme
    }

    MetricCard {
        Layout.fillWidth: true
        visible: root.analysisType === "THERMO"
        eyebrow: qsTr("Horas")
        value: String(root.analysis.horas || "")
        caption: qsTr("Thermo")
        badgeText: String(root.analysis.status || "")
        monogram: "HR"
    }

    MetricCard {
        Layout.fillWidth: true
        eyebrow: qsTr("Consumo real")
        value: String(root.analysis.consumo_real || "")
        caption: qsTr("Galones")
        badgeText: root.analysisType === "CAMION" ? String(root.analysis.status || "") : ""
        monogram: "CR"
    }

    MetricCard {
        Layout.fillWidth: true
        visible: root.analysisType === "THERMO"
        eyebrow: qsTr("Rendimiento")
        value: String(root.analysis.rendimiento || "")
        caption: qsTr("Horas por galon")
        monogram: "RD"
    }

    MetricCard {
        Layout.fillWidth: true
        eyebrow: qsTr("Estimado")
        value: String(root.analysis.consumo_estimado || "")
        caption: " "
        monogram: "ES"
    }

    MetricCard {
        Layout.fillWidth: true
        eyebrow: qsTr("Diferencia")
        value: String(root.analysis.diferencia || "")
        caption: qsTr("Real - estimado")
        accentTone: Number(root.analysis.diferencia || 0) > 0 ? "warning" : "success"
        monogram: "DF"
    }

}
