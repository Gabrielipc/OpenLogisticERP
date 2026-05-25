pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "../../shared/controls"
import "../../shared/surfaces"
import "../../shared/feedback"
import "../../shared/theme"

Item {
    id: page

    required property WorkflowPlaceholderViewModel moduleViewModel

    Theme {
        id: theme
    }
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
            return (event.angleDelta.y / 120) * page.wheelStep
        }
        return 0
    }

    ScrollView {
        id: pageScroll

        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: pageScroll.availableWidth
            spacing: theme.spacing6

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing5

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Label {
                        Layout.fillWidth: true
                        text: page.moduleViewModel ? page.moduleViewModel.title : ""
                        color: theme.textPrimary
                        font.family: theme.headlineFontFamily
                        font.pixelSize: theme.displaySize
                        font.bold: true
                        elide: Text.ElideRight
                    }

                    Label {
                        Layout.fillWidth: true
                        text: page.moduleViewModel ? page.moduleViewModel.summary : ""
                        color: theme.textSecondary
                        font.family: theme.bodyFontFamily
                        font.pixelSize: theme.bodySize
                        wrapMode: Text.WordWrap
                    }
                }

                StatusBadge {
                    text: qsTr("Proximamente")
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: width > 1080 ? 3 : 1
                columnSpacing: theme.spacing4
                rowSpacing: theme.spacing4

                MetricCard {
                    Layout.fillWidth: true
                    eyebrow: qsTr("Dominio")
                    value: page.moduleViewModel ? page.moduleViewModel.domain_title : ""
                    caption: qsTr("Modulo especializado fuera del CRUD generico.")
                    monogram: "DM"
                    accentTone: "soft"
                }

                MetricCard {
                    Layout.fillWidth: true
                    eyebrow: qsTr("Contrato actual")
                    value: qsTr("Pantalla raiz dedicada")
                    caption: qsTr("Este modulo tendra su propio view model y formularios por flujo.")
                    monogram: "VM"
                }

                MetricCard {
                    Layout.fillWidth: true
                    eyebrow: qsTr("Estado")
                    value: qsTr("Especializacion pendiente")
                    caption: qsTr("La navegacion ya distingue este workflow del Catálogo generico.")
                    monogram: "WF"
                    accentTone: "success"
                }
            }

            GridLayout {
                id: detailsGrid

                Layout.fillWidth: true
                columns: width > 1260 ? 2 : 1
                columnSpacing: theme.spacing4
                rowSpacing: theme.spacing4

                AutoHeightSurfaceCard {
                    heightSource: actionsContent
                    Layout.fillWidth: true
                    tone: "raised"
                    padding: theme.spacing6

                    ColumnLayout {
                        id: actionsContent

                        anchors.fill: parent
                        spacing: theme.spacing4

                        Label {
                            text: qsTr("Acciones previstas")
                            color: theme.textPrimary
                            font.family: theme.headlineFontFamily
                            font.pixelSize: theme.sectionTitleSize
                            font.bold: true
                        }

                        Repeater {
                            model: page.moduleViewModel ? page.moduleViewModel.planned_actions : []

                            delegate: AutoHeightSurfaceCard {
                                id: actionCard

                                required property int index
                                required property string modelData
                                readonly property int actionIndex: actionCard.index

                                heightSource: actionContent
                                Layout.fillWidth: true
                                tone: "low"
                                padding: theme.spacing4

                                RowLayout {
                                    id: actionContent

                                    width: parent.width
                                    spacing: theme.spacing3

                                    Rectangle {
                                        id: actionBadge

                                        Layout.preferredWidth: 28
                                        Layout.preferredHeight: 28
                                        Layout.alignment: Qt.AlignTop
                                        radius: 14
                                        color: theme.primaryFixed

                                        Label {
                                            anchors.centerIn: parent
                                            text: String(actionCard.actionIndex + 1)
                                            color: theme.primary
                                            font.family: theme.bodyFontFamily
                                            font.pixelSize: theme.captionSize
                                            font.bold: true
                                        }
                                    }

                                    Label {
                                        id: actionLabel

                                        Layout.fillWidth: true
                                        Layout.alignment: Qt.AlignTop
                                        text: actionCard.modelData
                                        color: theme.textPrimary
                                        font.family: theme.bodyFontFamily
                                        font.pixelSize: theme.bodySize
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }
                }

                AutoHeightSurfaceCard {
                    heightSource: architectureContent
                    Layout.fillWidth: true
                    tone: "primary"
                    padding: theme.spacing6

                    ColumnLayout {
                        id: architectureContent

                        anchors.fill: parent
                        spacing: theme.spacing4

                        Label {
                            text: qsTr("Decision de arquitectura")
                            color: theme.textOnPrimaryMuted
                            font.family: theme.bodyFontFamily
                            font.pixelSize: theme.captionSize
                            font.bold: true
                        }

                        Label {
                            Layout.fillWidth: true
                            text: qsTr("Los workflows complejos no comparten el formulario generico.")
                            color: theme.textOnPrimary
                            font.family: theme.headlineFontFamily
                            font.pixelSize: theme.sectionTitleSize
                            font.bold: true
                            wrapMode: Text.WordWrap
                        }

                        Label {
                            Layout.fillWidth: true
                            text: qsTr("La shell ya reserva su espacio de navegacion y evita mezclar comandos especializados como viajes, facturas o recibos con la infraestructura CRUD simple.")
                            color: theme.textOnPrimaryMuted
                            font.family: theme.bodyFontFamily
                            font.pixelSize: theme.bodySize
                            wrapMode: Text.WordWrap
                        }

                        AppButton {
                            Layout.fillWidth: true
                            variant: "secondary"
                            text: qsTr("Modulo especializado en construccion")
                        }
                    }
                }
            }
        }
    }

    MouseArea {
        parent: pageScroll
        anchors.fill: parent
        z: 1
        acceptedButtons: Qt.NoButton
        propagateComposedEvents: true

        onWheel: function(event) {
            const flickable = pageScroll.contentItem
            if (!flickable) {
                return
            }

            const deltaY = page.normalizedWheelDelta(event)
            if (deltaY === 0) {
                return
            }

            const currentContentY = Number(flickable["contentY"] || 0)
            const nextContentY = Math.max(0, Math.min(page.maxScrollY(pageScroll), currentContentY - deltaY))
            if (nextContentY === currentContentY) {
                return
            }

            flickable["contentY"] = nextContentY
            event.accepted = true
        }
    }
}
