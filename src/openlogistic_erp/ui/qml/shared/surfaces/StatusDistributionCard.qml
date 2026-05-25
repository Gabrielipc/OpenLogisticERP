pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../controls"
import "../theme"

AutoHeightSurfaceCard {
    id: root

    signal clicked(var route)

    property string title: ""
    property var model: []
    property var visibilityOptions: []
    property var dashboardViewModel: null
    property string visibilityGroup: ""
    property string settingsIconSource: ""
    property string moduleId: ""
    property string target: "list"
    property int hoveredSliceIndex: -1

    heightSource: contentLayout
    padding: theme.spacing4
    tone: "raised"
    subtleBorder: true

    Theme {
        id: theme
    }

    function metricValue(item) {
        return Math.max(0, Number(item && item.value !== undefined ? item.value : 0))
    }

    function totalValue() {
        let total = 0
        const rows = root.model || []
        for (let index = 0; index < rows.length; index += 1) {
            total += root.metricValue(rows[index])
        }
        return total
    }

    function toneColor(tone) {
        switch (String(tone || "")) {
        case "warning":
            return theme.warning
        case "success":
            return theme.success
        case "danger":
            return theme.danger
        case "soft":
            return theme.outline
        default:
            return theme.primary
        }
    }

    function routeForIndex(index) {
        const rows = root.model || []
        if (index < 0 || index >= rows.length) {
            return null
        }
        const item = rows[index]
        return {
            "module_id": String(item.moduleId || root.moduleId),
            "target": String(item.target || root.target),
            "filters": item.filters || []
        }
    }

    function sliceIndexForPoint(localX, localY) {
        const centerX = pieChart.width / 2
        const centerY = pieChart.height / 2
        const dx = localX - centerX
        const dy = localY - centerY
        const distance = Math.sqrt(dx * dx + dy * dy)
        const radius = Math.min(pieChart.width, pieChart.height) / 2 - 4
        const innerRadius = radius * 0.56
        if (distance < innerRadius || distance > radius || root.totalValue() <= 0) {
            return -1
        }
        let angle = Math.atan2(dy, dx) + Math.PI / 2
        if (angle < 0) {
            angle += Math.PI * 2
        }
        let cursor = 0
        const rows = root.model || []
        const total = root.totalValue()
        for (let index = 0; index < rows.length; index += 1) {
            const value = root.metricValue(rows[index])
            if (value <= 0) {
                continue
            }
            const slice = Math.PI * 2 * value / total
            if (angle >= cursor && angle <= cursor + slice) {
                return index
            }
            cursor += slice
        }
        return -1
    }

    function routeForPoint(localX, localY) {
        return root.routeForIndex(root.sliceIndexForPoint(localX, localY))
    }

    onModelChanged: pieChart.requestPaint()

    ColumnLayout {
        id: contentLayout

        anchors.fill: parent
        spacing: theme.spacing3

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing3

            Label {
                Layout.fillWidth: true
                text: root.title
                color: theme.textPrimary
                font.family: theme.headlineFontFamily
                font.pixelSize: theme.titleSize
                font.bold: true
                elide: Text.ElideRight
            }

            AppIconButton {
                id: statusSettingsButton

                Layout.preferredWidth: theme.controlHeightCompact
                Layout.preferredHeight: theme.controlHeightCompact
                buttonSize: theme.controlHeightCompact
                iconSize: 18
                visible: root.dashboardViewModel !== null && (root.visibilityOptions || []).length > 0
                source: root.settingsIconSource !== "" ? root.settingsIconSource : "qrc:/actions/general/settings"
                tintColor: theme.textPrimary
                hoverBackgroundColor: theme.surfaceLow
                pressedBackgroundColor: theme.surfaceMid
                borderWidth: 1
                borderColor: theme.alpha(theme.outlineVariant, 0.8)
                radius: theme.radiusSmall
                tooltipText: qsTr("Configurar estados")
                onClicked: statusOptionsDialog.open()
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 132

            Canvas {
                id: pieChart

                anchors.centerIn: parent
                width: 122
                height: 122

                onPaint: {
                    const ctx = getContext("2d")
                    ctx.reset()

                    const rows = root.model || []
                    const total = root.totalValue()
                    const centerX = width / 2
                    const centerY = height / 2
                    const radius = Math.min(width, height) / 2 - 4
                    const innerRadius = radius * 0.56

                    if (total <= 0) {
                        ctx.beginPath()
                        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2, false)
                        ctx.lineTo(centerX, centerY)
                        ctx.fillStyle = theme.neutralContainer
                        ctx.fill()
                    } else {
                        let startAngle = -Math.PI / 2
                        for (let index = 0; index < rows.length; index += 1) {
                            const value = root.metricValue(rows[index])
                            if (value <= 0) {
                                continue
                            }
                            const endAngle = startAngle + (Math.PI * 2 * value / total)
                            ctx.beginPath()
                            ctx.moveTo(centerX, centerY)
                            ctx.arc(centerX, centerY, radius, startAngle, endAngle, false)
                            ctx.closePath()
                            ctx.fillStyle = root.toneColor(rows[index].accentTone)
                            ctx.fill()
                            if (index === root.hoveredSliceIndex) {
                                ctx.lineWidth = 3
                                ctx.strokeStyle = theme.surfaceRaised
                                ctx.stroke()
                            }
                            startAngle = endAngle
                        }
                    }

                    ctx.beginPath()
                    ctx.arc(centerX, centerY, innerRadius, 0, Math.PI * 2, false)
                    ctx.fillStyle = theme.surfaceRaised
                    ctx.fill()
                }
            }

            HoverHandler {
                target: pieChart
                cursorShape: root.hoveredSliceIndex >= 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                onPointChanged: {
                    const localPoint = pieChart.mapFromItem(
                        pieChart.parent,
                        point.position.x,
                        point.position.y
                    )
                    root.hoveredSliceIndex = root.sliceIndexForPoint(
                        localPoint.x,
                        localPoint.y
                    )
                    pieChart.requestPaint()
                }
                onHoveredChanged: {
                    if (!hovered) {
                        root.hoveredSliceIndex = -1
                        pieChart.requestPaint()
                    }
                }
            }

            TapHandler {
                target: pieChart
                onTapped: function(eventPoint) {
                    const localPoint = pieChart.mapFromItem(
                        pieChart.parent,
                        eventPoint.position.x,
                        eventPoint.position.y
                    )
                    const route = root.routeForPoint(localPoint.x, localPoint.y)
                    if (route) {
                        root.clicked(route)
                    }
                }
            }

            ColumnLayout {
                anchors.centerIn: pieChart
                width: pieChart.width * 0.52
                spacing: 0

                Label {
                    Layout.fillWidth: true
                    text: String(root.totalValue())
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.titleSize
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                }

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Total")
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: theme.spacing2

            Repeater {
                model: root.model || []

                delegate: Rectangle {
                    id: legendItem

                    required property int index
                    required property var modelData

                    implicitWidth: legendRow.implicitWidth + theme.spacing2
                    implicitHeight: legendRow.implicitHeight + theme.spacing2
                    width: implicitWidth
                    height: implicitHeight
                    radius: theme.radiusSmall
                    color: root.hoveredSliceIndex === legendItem.index ? theme.surfaceLow : "transparent"

                    Row {
                        id: legendRow

                        anchors.centerIn: parent
                        spacing: 4

                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            anchors.verticalCenter: parent.verticalCenter
                            color: root.toneColor(legendItem.modelData.accentTone)
                        }

                        Label {
                            text: String(legendItem.modelData.title || "") + " " + String(root.metricValue(legendItem.modelData))
                            color: theme.textSecondary
                            font.family: theme.bodyFontFamily
                            font.pixelSize: theme.captionSize
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: {
                            root.hoveredSliceIndex = legendItem.index
                            pieChart.requestPaint()
                        }
                        onExited: {
                            root.hoveredSliceIndex = -1
                            pieChart.requestPaint()
                        }
                        onClicked: {
                            const route = root.routeForIndex(legendItem.index)
                            if (route) {
                                root.clicked(route)
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: statusOptionsDialog

        modal: true
        title: qsTr("Estados de %1").arg(root.title)
        standardButtons: Dialog.Close
        anchors.centerIn: Overlay.overlay
        width: 340

        ColumnLayout {
            width: parent ? parent.width : 0
            spacing: theme.spacing3

            Repeater {
                model: root.visibilityOptions || []

                delegate: CheckBox {
                    required property var modelData

                    Layout.fillWidth: true
                    text: String(modelData.title || "")
                    checked: Boolean(modelData.visible)
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.bodySize
                    onToggled: {
                        if (root.dashboardViewModel) {
                            root.dashboardViewModel.setStatusMetricVisible(
                                root.visibilityGroup,
                                String(modelData.key || ""),
                                checked
                            )
                        }
                    }
                }
            }
        }
    }
}
