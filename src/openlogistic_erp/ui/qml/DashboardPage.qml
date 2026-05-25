pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "shared/controls"
import "shared/surfaces"
import "shared/theme"

Item {
    id: root

    required property AppShellViewModel appShellViewModel
    required property RuntimeSessionViewModel runtimeSessionViewModel
    readonly property DashboardViewModel dashboardViewModel: root.appShellViewModel
        ? root.appShellViewModel.dashboard_view_model
        : null
    property real wheelStep: theme.spacing6

    Theme {
        id: theme
    }

    function maxScrollY(flickable) {
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

    function navigate(route) {
        if (!root.appShellViewModel) {
            return
        }
        root.appShellViewModel.navigate_to(route)
    }

    function refreshDashboardMetrics() {
        if (!root.runtimeSessionViewModel || !root.runtimeSessionViewModel.is_authenticated) {
            return
        }
        if (root.dashboardViewModel) {
            root.dashboardViewModel.refresh()
        }
    }

    Component.onCompleted: root.refreshDashboardMetrics()

    Connections {
        target: root.appShellViewModel

        function onCurrentViewChanged(currentView) {
            if (String(currentView) === "dashboard") {
                root.refreshDashboardMetrics()
            }
        }
    }

    Flickable {
        id: dashboardFlick

        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: dashboardContent.height

        ColumnLayout {
            id: dashboardContent

            height: Math.max(dashboardFlick.height, implicitHeight)
            width: dashboardFlick.width
            spacing: theme.spacing6

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing2

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Inicio")
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.displaySize
                    font.bold: true
                }

                Item {
                    Layout.fillWidth: true
                }

                Repeater {
                    model: root.appShellViewModel ? root.appShellViewModel.dashboard_modules: []

                    delegate: AppButton {
                        id: moduleAccessButton
                        variant: "contrast"
                        required property var modelData
                        text: moduleAccessButton.modelData.title
                        iconSource: String(moduleAccessButton.modelData.iconSource || "")
                        onClicked: root.appShellViewModel.select_module(moduleAccessButton.modelData.module_id)
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: theme.spacing3

                Label {
                    text: qsTr("Metricas")
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.titleSize
                    font.bold: true
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: theme.spacing4

                    GridLayout {
                        id: statusCardsLayout

                        Layout.fillWidth: true
                        Layout.minimumWidth: 0

                        columns: root.width >= 1000 ? 2 : 1
                        columnSpacing: theme.spacing4
                        rowSpacing: theme.spacing4

                        StatusDistributionCard {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0

                            title: qsTr("Camiones")
                            model: root.dashboardViewModel ? root.dashboardViewModel.fleetStatusMetrics : []
                            visibilityOptions: root.dashboardViewModel ? root.dashboardViewModel.fleetStatusVisibilityOptions : []
                            visibilityGroup: "fleet"
                            settingsIconSource: "qrc:/actions/general/settings"
                            dashboardViewModel: root.dashboardViewModel
                            moduleId: "camion"
                            target: "list"

                            onClicked: function(route) {
                                root.navigate(route)
                            }
                        }

                        StatusDistributionCard {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0

                            title: qsTr("Conductores")
                            model: root.dashboardViewModel ? root.dashboardViewModel.driverStatusMetrics : []
                            visibilityOptions: root.dashboardViewModel ? root.dashboardViewModel.driverStatusVisibilityOptions : []
                            visibilityGroup: "driver"
                            settingsIconSource: "qrc:/actions/general/settings"
                            dashboardViewModel: root.dashboardViewModel
                            moduleId: "conductor"
                            target: "list"

                            onClicked: function(route) {
                                root.navigate(route)
                            }
                        }
                    }

                    GridLayout {
                        id: summaryMetricsLayout

                        Layout.fillWidth: true
                        Layout.minimumWidth: 0

                        columns: root.width >= 760 ? 2 : 1
                        columnSpacing: theme.spacing4
                        rowSpacing: theme.spacing4

                        Repeater {
                            model: root.dashboardViewModel ? root.dashboardViewModel.summaryMetrics : []

                            delegate: CompactMetricTile {
                                required property var modelData

                                Layout.fillWidth: true
                                Layout.minimumWidth: 0

                                title: String(modelData.title || "")
                                value: String(modelData.value || "0")
                                monogram: String(modelData.monogram || "")
                                iconSource: String(modelData.iconSource || "")
                                accentTone: String(modelData.accentTone || "primary")
                                moduleId: String(modelData.moduleId || "")
                                target: String(modelData.target || "list")
                                routeData: {
                                    "filters": modelData.filters || [],
                                    "subpage": modelData.subpage || "",
                                    "subpage_context": modelData.subpageContext || ({})
                                }

                                onClicked: function(route) {
                                    root.navigate(route)
                                }
                            }
                        }
                    }

                    BillingTimelineCard {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        visible: root.dashboardViewModel ? root.dashboardViewModel.canViewBillingTimeline : true

                        rows: root.dashboardViewModel ? root.dashboardViewModel.billingTimelineRows : []
                        currencies: root.dashboardViewModel ? root.dashboardViewModel.billingTimelineCurrencies : []
                        selectedCurrency: root.dashboardViewModel ? root.dashboardViewModel.selectedBillingTimelineCurrency : ""
                        showReceipts: root.dashboardViewModel ? root.dashboardViewModel.showBillingTimelineReceipts : false
                        canCompareReceipts: root.dashboardViewModel ? root.dashboardViewModel.canCompareBillingTimelineReceipts : true

                        onCurrencySelected: function(currencyKey) {
                            if (root.dashboardViewModel) {
                                root.dashboardViewModel.selectBillingTimelineCurrency(currencyKey)
                            }
                        }

                        onReceiptsVisibleChanged: function(visible) {
                            if (root.dashboardViewModel) {
                                root.dashboardViewModel.setBillingTimelineReceiptsVisible(visible)
                            }
                        }
                    }

                    GridLayout {
                        id: financeMetricsLayout

                        Layout.fillWidth: true
                        Layout.minimumWidth: 0

                        columns: root.width >= 760 ? 3 : 1
                        columnSpacing: theme.spacing4
                        rowSpacing: theme.spacing4

                        Repeater {
                            model: root.dashboardViewModel ? root.dashboardViewModel.financeMetrics : []

                            delegate: CompactMetricTile {
                                required property var modelData

                                Layout.fillWidth: true
                                Layout.minimumWidth: 0

                                title: String(modelData.title || "")
                                value: String(modelData.value || "0")
                                monogram: String(modelData.monogram || "")
                                iconSource: String(modelData.iconSource || "")
                                accentTone: String(modelData.accentTone || "primary")
                                moduleId: String(modelData.moduleId || "")
                                target: String(modelData.target || "list")
                                routeData: {
                                    "filters": modelData.filters || [],
                                    "subpage": modelData.subpage || "",
                                    "subpage_context": modelData.subpageContext || ({})
                                }

                                onClicked: function(route) {
                                    root.navigate(route)
                                }
                            }
                        }
                    }

                    AutoHeightSurfaceCard {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0

                        visible: root.dashboardViewModel
                            ? root.dashboardViewModel.error_message !== ""
                            : false

                        tone: "low"
                        padding: theme.spacing5
                        heightSource: dashboardError

                        Label {
                            id: dashboardError

                            anchors.fill: parent
                            text: root.dashboardViewModel ? root.dashboardViewModel.error_message : ""
                            color: theme.danger
                            font.family: theme.bodyFontFamily
                            font.pixelSize: theme.bodySize
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }

            Item {
                Layout.fillHeight: true
                Layout.fillWidth: true
            }         
        }
    }

    WheelHandler {
        target: dashboardFlick
        onWheel: function(event) {
            const flickable = dashboardFlick
            if (!flickable) {
                return
            }

            const deltaY = root.normalizedWheelDelta(event)
            if (deltaY === 0) {
                return
            }

            const currentContentY = Number(flickable["contentY"] || 0)
            const nextContentY = Math.max(0, Math.min(root.maxScrollY(dashboardFlick), currentContentY - deltaY))
            if (nextContentY === currentContentY) {
                return
            }

            flickable["contentY"] = nextContentY
            event.accepted = true
        }
    }
}
