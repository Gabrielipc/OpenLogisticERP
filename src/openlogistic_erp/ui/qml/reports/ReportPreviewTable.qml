pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import "../shared/theme"

Item {
    id: root

    property var tableMeta: ({})
    property var tableModel: null
    property var pendingColumnWidths: ({})
    property real baseWidthTotal: 0
    property int stretchColumnIndex: -1
    property bool layoutRefreshPending: false
    property bool hasCellRangeSelection: false
    property bool cellRangeSelectionActive: false
    property int cellRangeStartRow: -1
    property int cellRangeStartColumn: -1
    property int cellRangeEndRow: -1
    property int cellRangeEndColumn: -1
    property real cellRangeDragPointX: 0
    property real cellRangeDragPointY: 0
    property int cellRangeAutoScrollMargin: 32
    property int cellRangeAutoScrollStep: 22

    Theme {
        id: theme
    }

    onTableMetaChanged: {
        root.pendingColumnWidths = ({})
        root.refreshColumnMetrics()
        root.requestTableLayout()
    }
    onTableModelChanged: {
        root.clearCellRangeSelection()
        root.refreshColumnMetrics()
        root.requestTableLayout()
    }

    function columnsModel() {
        return root.tableMeta && root.tableMeta.columns ? root.tableMeta.columns : []
    }

    function columnMeta(columnIndex) {
        const columns = root.columnsModel()
        if (columnIndex < 0 || columnIndex >= columns.length) {
            return null
        }
        return columns[columnIndex]
    }

    function defaultColumnWidth(meta) {
        if (!meta) {
            return 160
        }
        const explicitWidth = Number(meta.width || 0)
        if (explicitWidth > 0) {
            return explicitWidth
        }
        const format = String(meta.format || "")
        if (format === "currency" || format === "decimal") {
            return 150
        }
        if (format === "int") {
            return 120
        }
        return 190
    }

    function resolvedBaseColumnWidth(columnIndex) {
        const meta = root.columnMeta(columnIndex)
        if (!meta) {
            return 0
        }
        const key = String(meta.key || columnIndex)
        const pendingWidth = root.pendingColumnWidths[key]
        if (pendingWidth !== undefined) {
            return Number(pendingWidth)
        }
        return root.defaultColumnWidth(meta)
    }

    function columnWidth(columnIndex) {
        const meta = root.columnMeta(columnIndex)
        if (!meta) {
            return 0
        }

        const baseWidth = root.resolvedBaseColumnWidth(columnIndex)
        const stretchColumn = root.stretchColumnIndex
        const viewportWidth = root.availableTableWidth()
        const totalBaseWidth = root.baseWidthTotal

        if (columnIndex !== stretchColumn || viewportWidth <= totalBaseWidth) {
            return baseWidth
        }

        return baseWidth + (viewportWidth - totalBaseWidth)
    }

    function refreshColumnMetrics() {
        const columns = root.columnsModel()
        let total = 0
        let stretchColumn = -1
        for (let i = 0; i < columns.length; ++i) {
            total += root.resolvedBaseColumnWidth(i)
            stretchColumn = i
        }
        root.baseWidthTotal = total
        root.stretchColumnIndex = stretchColumn
    }

    function availableTableWidth() {
        const bodyWidth = bodyTable ? bodyTable.width : 0
        const verticalBarWidth = bodyVerticalBar && bodyVerticalBar.visible ? bodyVerticalBar.width : 0
        const headerWidth = headerView ? headerView.width : 0
        return Math.max(0, Math.max(bodyWidth - verticalBarWidth, headerWidth))
    }

    function minColumnWidth(columnIndex) {
        const meta = root.columnMeta(columnIndex)
        return Math.max(80, Number(meta && meta.minWidth ? meta.minWidth : 96))
    }

    function requestTableLayout() {
        if (root.layoutRefreshPending) {
            return
        }
        root.layoutRefreshPending = true
        Qt.callLater(function() {
            root.layoutRefreshPending = false
            if (bodyTable) {
                bodyTable.forceLayout()
            }
            if (headerView) {
                headerView.forceLayout()
            }
        })
    }

    function rowCount() {
        return root.tableModel ? root.tableModel.rowCount() : 0
    }

    function maxTableContentX() {
        if (!bodyTable) {
            return 0
        }
        return Math.max(0, root.tableContentWidthFromColumns() - bodyTable.width)
    }

    function maxTableContentY() {
        if (!bodyTable) {
            return 0
        }
        return Math.max(0, root.rowCount() * 38 - bodyTable.height)
    }

    function tableContentWidthFromColumns() {
        const columns = root.columnsModel()
        let total = 0
        for (let columnIndex = 0; columnIndex < columns.length; ++columnIndex) {
            total += root.columnWidth(columnIndex)
        }
        return total
    }

    function clearCellRangeSelection() {
        root.hasCellRangeSelection = false
        root.cellRangeSelectionActive = false
        root.cellRangeStartRow = -1
        root.cellRangeStartColumn = -1
        root.cellRangeEndRow = -1
        root.cellRangeEndColumn = -1
        root.cellRangeDragPointX = 0
        root.cellRangeDragPointY = 0
    }

    function startCellRangeSelection(rowIndex, columnIndex) {
        if (rowIndex < 0 || columnIndex < 0) {
            root.clearCellRangeSelection()
            return
        }
        root.cellRangeSelectionActive = true
        root.hasCellRangeSelection = true
        root.cellRangeStartRow = rowIndex
        root.cellRangeStartColumn = columnIndex
        root.cellRangeEndRow = rowIndex
        root.cellRangeEndColumn = columnIndex
    }

    function updateCellRangeSelection(rowIndex, columnIndex) {
        if (!root.cellRangeSelectionActive || rowIndex < 0 || columnIndex < 0) {
            return
        }
        root.cellRangeEndRow = rowIndex
        root.cellRangeEndColumn = columnIndex
    }

    function rowIndexAtTablePoint(point) {
        if (!bodyTable) {
            return -1
        }
        const contentY = Math.max(0, Number(bodyTable.contentY || 0) + Number(point.y || 0))
        const rowIndex = Math.floor(contentY / 38)
        return rowIndex >= 0 && rowIndex < root.rowCount() ? rowIndex : -1
    }

    function columnIndexAtTablePoint(point) {
        if (!bodyTable) {
            return -1
        }
        const contentX = Math.max(0, Number(bodyTable.contentX || 0) + Number(point.x || 0))
        const columns = root.columnsModel()
        let cursorX = 0
        for (let columnIndex = 0; columnIndex < columns.length; ++columnIndex) {
            const width = root.columnWidth(columnIndex)
            if (contentX >= cursorX && contentX < cursorX + width) {
                return columnIndex
            }
            cursorX += width
        }
        return -1
    }

    function updateCellRangeSelectionFromPoint(point) {
        root.updateCellRangeSelection(root.rowIndexAtTablePoint(point), root.columnIndexAtTablePoint(point))
    }

    function updateCellRangeDragPoint(point) {
        root.cellRangeDragPointX = Number(point.x || 0)
        root.cellRangeDragPointY = Number(point.y || 0)
        root.updateCellRangeSelectionFromPoint(point)
    }

    function autoScrollCellRangeSelection() {
        if (!root.cellRangeSelectionActive || !bodyTable) {
            return
        }
        let nextContentX = Number(bodyTable.contentX || 0)
        let nextContentY = Number(bodyTable.contentY || 0)
        const margin = root.cellRangeAutoScrollMargin
        const step = root.cellRangeAutoScrollStep

        if (root.cellRangeDragPointY < margin) {
            nextContentY -= step
        } else if (root.cellRangeDragPointY > bodyTable.height - margin) {
            nextContentY += step
        }
        if (root.cellRangeDragPointX < margin) {
            nextContentX -= step
        } else if (root.cellRangeDragPointX > bodyTable.width - margin) {
            nextContentX += step
        }

        bodyTable.contentX = Math.max(0, Math.min(root.maxTableContentX(), nextContentX))
        bodyTable.contentY = Math.max(0, Math.min(root.maxTableContentY(), nextContentY))
        root.updateCellRangeSelectionFromPoint(Qt.point(root.cellRangeDragPointX, root.cellRangeDragPointY))
    }

    function isPointInsideBodyTable(point) {
        if (!bodyTable) {
            return false
        }
        const bodyPoint = root.mapToItem(bodyTable, point.x, point.y)
        return bodyPoint.x >= 0
            && bodyPoint.x <= bodyTable.width
            && bodyPoint.y >= 0
            && bodyPoint.y <= bodyTable.height
    }

    function clearCellRangeSelectionIfOutsideBodyTable(point) {
        if (root.hasCellRangeSelection && !root.isPointInsideBodyTable(point)) {
            root.clearCellRangeSelection()
        }
    }

    function normalizedCellRange() {
        if (!root.hasCellRangeSelection) {
            return null
        }
        return {
            "firstRow": Math.min(root.cellRangeStartRow, root.cellRangeEndRow),
            "lastRow": Math.max(root.cellRangeStartRow, root.cellRangeEndRow),
            "firstColumn": Math.min(root.cellRangeStartColumn, root.cellRangeEndColumn),
            "lastColumn": Math.max(root.cellRangeStartColumn, root.cellRangeEndColumn)
        }
    }

    function isCellRangeSelected(rowIndex, columnIndex) {
        const range = root.normalizedCellRange()
        return !!(range
            && rowIndex >= range.firstRow
            && rowIndex <= range.lastRow
            && columnIndex >= range.firstColumn
            && columnIndex <= range.lastColumn)
    }

    function copyCellRangeSelection() {
        if (!root.hasCellRangeSelection || !root.tableModel) {
            return false
        }
        return root.tableModel.copy_display_range_to_clipboard(
            root.cellRangeStartRow,
            root.cellRangeStartColumn,
            root.cellRangeEndRow,
            root.cellRangeEndColumn
        )
    }

    function previewColumnWidth(columnIndex, width) {
        const meta = root.columnMeta(columnIndex)
        if (!meta) {
            return
        }
        const normalizedWidth = Math.max(root.minColumnWidth(columnIndex), Math.round(Number(width)))
        if (!Number.isFinite(normalizedWidth)) {
            return
        }
        const key = String(meta.key || columnIndex)
        if (root.pendingColumnWidths[key] === normalizedWidth) {
            return
        }
        const next = Object.assign({}, root.pendingColumnWidths)
        next[key] = normalizedWidth
        root.pendingColumnWidths = next
        root.refreshColumnMetrics()
        root.requestTableLayout()
    }

    function commitColumnWidth(columnIndex) {
        const meta = root.columnMeta(columnIndex)
        if (!meta) {
            return
        }
        const key = String(meta.key || columnIndex)
        const pendingWidth = root.pendingColumnWidths[key]
        if (pendingWidth === undefined) {
            return
        }
        const next = Object.assign({}, root.pendingColumnWidths)
        next[key] = Math.max(root.minColumnWidth(columnIndex), Math.round(Number(pendingWidth)))
        root.pendingColumnWidths = next
        root.refreshColumnMetrics()
        root.requestTableLayout()
    }

    Rectangle {
        anchors.fill: parent
        radius: theme.radiusMedium
        color: theme.surfaceRaised
        border.width: 1
        border.color: theme.alpha(theme.outlineVariant, 0.45)

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: Math.max(0, theme.radiusMedium - 1)
            color: "transparent"

            Item {
                id: maskedViewport

                anchors.fill: parent
                layer.enabled: true
                layer.smooth: true
                layer.effect: OpacityMask {
                    maskSource: Rectangle {
                        width: maskedViewport.width
                        height: maskedViewport.height
                        radius: Math.max(0, theme.radiusMedium - 1)
                        color: "black"
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    color: theme.surfaceRaised
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Shortcut {
                        sequences: [StandardKey.Copy]
                        enabled: root.hasCellRangeSelection
                        onActivated: root.copyCellRangeSelection()
                    }

                    Timer {
                        id: cellRangeAutoScrollTimer

                        interval: 40
                        repeat: true
                        running: root.cellRangeSelectionActive
                        onTriggered: root.autoScrollCellRangeSelection()
                    }

                    HorizontalHeaderView {
                        id: headerView

                        resizableColumns: false
                        Layout.fillWidth: true
                        Layout.preferredHeight: 42
                        syncView: bodyTable
                        clip: true
                        model: root.tableModel
                        columnWidthProvider: function(column) {
                            return root.columnWidth(column)
                        }
                        onWidthChanged: forceLayout()
                        Component.onCompleted: forceLayout()

                        delegate: Rectangle {
                            id: headerCell

                            required property int column

                            implicitWidth: root.columnWidth(column)
                            implicitHeight: 42
                            color: theme.surfaceHigh

                            property var columnMeta: root.columnMeta(column)
                            property real dragStartX: 0
                            property int dragStartWidth: 0

                            MouseArea {
                                anchors.fill: parent
                                anchors.rightMargin: 10
                                enabled: !!(headerCell.columnMeta && root.tableModel)
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (enabled) {
                                        root.tableModel.toggle_sort(headerCell.columnMeta.key)
                                    }
                                }
                            }

                            Label {
                                anchors.fill: parent
                                anchors.leftMargin: theme.spacing4
                                anchors.rightMargin: sortIndicator.visible ? theme.spacing8 : theme.spacing5
                                text: headerCell.columnMeta ? String(headerCell.columnMeta.label || "") : ""
                                color: theme.textSecondary
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.captionSize
                                font.bold: true
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }

                            Label {
                                id: sortIndicator

                                anchors.right: parent.right
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                visible: !!(headerCell.columnMeta
                                    && root.tableModel
                                    && root.tableModel.sort_field === headerCell.columnMeta.key)
                                text: root.tableModel
                                    && root.tableModel.sort_direction === "desc" ? "\u2193" : "\u2191"
                                color: theme.primary
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.bodySize
                                font.bold: true
                            }

                            Rectangle {
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.right: parent.right
                                width: 10
                                color: resizeHandle.containsMouse || resizeHandle.pressed
                                    ? theme.surfaceMid
                                    : "transparent"

                                MouseArea {
                                    id: resizeHandle

                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.SizeHorCursor
                                    acceptedButtons: Qt.LeftButton
                                    preventStealing: true

                                    onPressed: function(mouse) {
                                        const point = resizeHandle.mapToItem(root, mouse.x, mouse.y)
                                        headerCell.dragStartX = point.x
                                        headerCell.dragStartWidth = root.columnWidth(headerCell.column)
                                    }

                                    onPositionChanged: function(mouse) {
                                        if (!(mouse.buttons & Qt.LeftButton)) {
                                            return
                                        }
                                        const point = resizeHandle.mapToItem(root, mouse.x, mouse.y)
                                        const delta = point.x - headerCell.dragStartX
                                        root.previewColumnWidth(headerCell.column, headerCell.dragStartWidth + delta)
                                    }

                                    onReleased: root.commitColumnWidth(headerCell.column)
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: theme.alpha(theme.outlineVariant, 0.45)
                    }

                    TableView {
                        id: bodyTable

                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.tableModel
                        boundsBehavior: Flickable.StopAtBounds
                        columnSpacing: 0
                        rowSpacing: 0
                        columnWidthProvider: function(column) {
                            return root.columnWidth(column)
                        }
                        rowHeightProvider: function() {
                            return 38
                        }
                        onWidthChanged: forceLayout()
                        Component.onCompleted: {
                            root.refreshColumnMetrics()
                            forceLayout()
                        }

                        delegate: Rectangle {
                            id: reportCell

                            required property string display
                            required property int row
                            required property int column

                            implicitWidth: root.columnWidth(column)
                            implicitHeight: 38
                            color: root.isCellRangeSelected(reportCell.row, reportCell.column)
                                ? theme.primaryFixed
                                : row % 2 === 0 ? theme.surfaceRaised : theme.surfaceLow

                            MouseArea {
                                id: reportCellMouseArea

                                anchors.fill: parent
                                acceptedButtons: Qt.LeftButton
                                preventStealing: true
                                z: 20

                                onPressed: function(mouse) {
                                    bodyTable.forceActiveFocus()
                                    root.startCellRangeSelection(reportCell.row, reportCell.column)
                                    const point = reportCellMouseArea.mapToItem(bodyTable, mouse.x, mouse.y)
                                    root.updateCellRangeDragPoint(point)
                                }

                                onPositionChanged: function(mouse) {
                                    if (!(mouse.buttons & Qt.LeftButton)) {
                                        return
                                    }
                                    const point = reportCellMouseArea.mapToItem(bodyTable, mouse.x, mouse.y)
                                    root.updateCellRangeDragPoint(point)
                                }

                                onReleased: {
                                    root.cellRangeSelectionActive = false
                                }

                                onCanceled: {
                                    root.cellRangeSelectionActive = false
                                }
                            }

                            TextInput {
                                id: reportSelectableCellText

                                anchors.fill: parent
                                anchors.leftMargin: theme.spacing4
                                anchors.rightMargin: theme.spacing4
                                text: parent.display
                                color: theme.textPrimary
                                selectedTextColor: theme.surfaceRaised
                                selectionColor: theme.primary
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.bodySize
                                readOnly: true
                                selectByMouse: true
                                clip: true
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        ScrollBar.horizontal: ScrollBar {}
                        ScrollBar.vertical: ScrollBar {
                            id: bodyVerticalBar
                        }
                    }
                }
            }
        }
    }

    Label {
        anchors.centerIn: parent
        visible: !root.tableModel || root.tableModel.rowCount() === 0
        text: qsTr("Sin filas para mostrar")
        color: theme.textSecondary
        font.family: theme.bodyFontFamily
        font.pixelSize: theme.bodySize
    }

        Component.onCompleted: root.refreshColumnMetrics()

    MouseArea {
        id: outsideTableSelectionClearArea

        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        propagateComposedEvents: true
        z: 1000

        onPressed: function(mouse) {
            root.clearCellRangeSelectionIfOutsideBodyTable(Qt.point(mouse.x, mouse.y))
            mouse.accepted = false
        }
    }
}
