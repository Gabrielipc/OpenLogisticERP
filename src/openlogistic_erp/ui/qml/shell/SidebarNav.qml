pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import OpenLogistic.Models 1.0
import "../shared/controls"
import "../shared/surfaces"
import "../shell"

SurfaceCard {
    id: root

    required property AppShellViewModel appShellViewModel
    required property RuntimeSessionViewModel runtimeSessionViewModel
    required property var theme
    property bool collapsed: false
    signal collapseToggleRequested()

    tone: "low"
    padding: root.collapsed ? root.theme.spacing4 : root.theme.spacing6
    property real wheelStep: root.theme.spacing6

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

    function moduleBadge(title) {
        const parts = String(title || "").trim().split(/\s+/)
        if (parts.length === 0 || parts[0] === "") {
            return "OL"
        }
        if (parts.length === 1) {
            return parts[0].slice(0, 2).toUpperCase()
        }
        return (parts[0][0] + parts[1][0]).toUpperCase()
    }

    function resetHorizontalScroll() {
        const flickable = navScroll ? navScroll.contentItem : null
        if (flickable) {
            flickable["contentX"] = 0
        }
    }

    onCollapsedChanged: root.resetHorizontalScroll()

    ColumnLayout {
        anchors.fill: parent
        spacing: root.theme.spacing5

        SidebarBrandCard {
            id: brandCard

            theme: root.theme
            badgeText: "OL"
            title: qsTr("OpenLogisticERP")
            collapsed: root.collapsed

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor

                onClicked: {
                    if (root.appShellViewModel) {
                        root.appShellViewModel.go_home()
                    }
                }
            }
        }

        ScrollView {
            id: navScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            onWidthChanged: root.resetHorizontalScroll()

            Column {
                width: navScroll.availableWidth
                spacing: root.theme.spacing5

                Repeater {
                    model: root.appShellViewModel ? root.appShellViewModel.module_groups : []

                    delegate: Column {
                        id: sidebarButton
                        required property var modelData

                        width: parent.width
                        spacing: root.theme.spacing2

                        Label {
                            visible: !root.collapsed
                            width: parent.width
                            text: sidebarButton.modelData.title
                            color: root.theme.textSecondary
                            font.family: root.theme.bodyFontFamily
                            font.pixelSize: root.theme.captionSize
                            font.bold: true
                        }

                        Repeater {
                            model: sidebarButton.modelData.modules

                            delegate: SidebarNavButton {
                                required property var modelData

                                width: parent.width
                                checkable: true
                                enabled: modelData.enabled
                                checked: root.appShellViewModel
                                    && root.appShellViewModel.current_view === "module"
                                    && root.appShellViewModel.current_module_id === modelData.module_id
                                text: modelData.title
                                badgeText: modelData.monogram || root.moduleBadge(modelData.title)
                                iconSource: modelData.iconSource || ""
                                subtitle: root.collapsed ? "" : qsTr(" ")
                                collapsed: root.collapsed
                                onClicked: {
                                    if (root.appShellViewModel) {
                                        root.appShellViewModel.select_module(modelData.module_id)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        MouseArea {
            parent: navScroll
            anchors.fill: parent
            z: 1
            acceptedButtons: Qt.NoButton
            propagateComposedEvents: true

            onWheel: function(event) {
                const flickable = navScroll.contentItem
                if (!flickable) {
                    return
                }

                const deltaY = root.normalizedWheelDelta(event)
                if (deltaY === 0) {
                    return
                }

                const currentContentY = Number(flickable["contentY"] || 0)
                const nextContentY = Math.max(0, Math.min(root.maxScrollY(navScroll), currentContentY - deltaY))
                if (nextContentY === currentContentY) {
                    return
                }

                flickable["contentY"] = nextContentY
                event.accepted = true
            }
        }

        AutoHeightSurfaceCard {
            visible: root.runtimeSessionViewModel ? root.runtimeSessionViewModel.is_authenticated : false
            tone: "raised"
            padding: root.theme.spacing5
            Layout.fillWidth: true
            heightSource: sessionContent

            ColumnLayout {
                anchors.fill: parent
                spacing: root.theme.spacing3
                id: sessionContent

                Label {
                    Layout.fillWidth: true
                    visible: !root.collapsed && root.runtimeSessionViewModel
                        ? root.runtimeSessionViewModel.roles.length > 0
                        : false
                    text: root.runtimeSessionViewModel
                        ? qsTr("Roles: ") + root.runtimeSessionViewModel.roles.join(", ")
                        : ""
                    wrapMode: Text.WordWrap
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFontFamily
                    font.pixelSize: root.theme.captionSize
                }

                AppButton {
                    Layout.fillWidth: true
                    visible: !root.collapsed
                    text: qsTr("Cerrar sesion")
                    variant: "secondary"
                    onClicked: {
                        if (root.runtimeSessionViewModel) {
                            root.runtimeSessionViewModel.logout()
                        }
                    }
                }

                AppIconButton{
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    buttonSize: 36
                    iconSize: 20
                    ToolTip.delay: 550
                    ToolTip.visible: root.collapsed && hovered
                    ToolTip.text: qsTr("Cerrar sesion")
                    visible: root.collapsed
                    backgroundColor: root.theme.surfaceHigh

                    source: "qrc:/actions/control/logout"
                    tintColor: root.theme.textPrimary
                    hoverBackgroundColor: root.theme.surfaceMid

                    onClicked: {
                        if (root.runtimeSessionViewModel) {
                            root.runtimeSessionViewModel.logout()
                        }
                    }

                }
            }
        }
    }
}
