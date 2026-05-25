pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import "../shared/controls"
import "../shared/surfaces"
import "../shared/theme"

SurfaceCard {
    id: tableCard

    property var screenViewModel: null
    property real wheelStep: theme.spacing6
    property string searchText: ""
    property string pageJumpText: "1"
    property var columnsSnapshot: []
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

    signal searchTextEdited(string text)
    signal searchRequested(string text)
    signal searchCleared()
    signal recordSelected(int recordId)
    signal editRecordRequested(int recordId)
    signal deleteRecordRequested(int recordId)
    signal viewRecordRequested(int recordId)
    signal exportRecordRequested(int recordId)

    property bool showViewAction: false
    property bool showExportAction: false
    property bool showDeleteAction: true
    property bool exportSelectionMode: false
    property string viewActionText: qsTr("Ver detalles")

    tone: "raised"
    padding: theme.spacing5

    Theme {
        id: theme
    }

    onScreenViewModelChanged: {
        tableCard.syncPageJumpText()
        tableCard.syncColumnsSnapshot()
    }

    Connections {
        target: tableCard.screenViewModel

        function onSelectedRowIndexChanged(rowIndex) {
            tableCard.ensureSelectedRowVisible(rowIndex)
        }

        function onSelectedExportRecordIdsChanged() {
            if (bodyTable) {
                bodyTable.forceLayout()
            }
        }
    }

    function columnsModel() {
        return tableCard.columnsSnapshot
    }

    function syncColumnsSnapshot() {
        tableCard.clearCellRangeSelection()
        tableCard.columnsSnapshot = tableCard.screenViewModel ? tableCard.screenViewModel.columns : []
        tableCard.pendingColumnWidths = ({})
        tableCard.refreshColumnMetrics()
    }

    function columnMeta(columnIndex) {
        const columns = tableCard.columnsModel()
        if (columnIndex < 0 || columnIndex >= columns.length) {
            return null
        }
        return columns[columnIndex]
    }

    function isDataColumn(columnIndex) {
        const meta = tableCard.columnMeta(columnIndex)
        return !!(meta && meta.kind === "data")
    }

    function resolvedBaseColumnWidth(columnIndex) {
        const meta = tableCard.columnMeta(columnIndex)
        if (!meta) {
            return 0
        }
        const pendingWidth = tableCard.pendingColumnWidths[meta.key]
        if (pendingWidth !== undefined) {
            return Number(pendingWidth)
        }
        return Number(meta.width || 0)
    }

    function columnWidth(columnIndex) {
        const meta = tableCard.columnMeta(columnIndex)
        if (!meta) {
            return 0
        }

        const baseWidth = tableCard.resolvedBaseColumnWidth(columnIndex)
        const stretchColumn = tableCard.stretchColumnIndex
        const viewportWidth = tableCard.availableTableWidth()
        const totalBaseWidth = tableCard.baseWidthTotal

        if (meta.kind !== "data" || columnIndex !== stretchColumn || viewportWidth <= totalBaseWidth) {
            return baseWidth
        }

        return baseWidth + (viewportWidth - totalBaseWidth)
    }

    function refreshColumnMetrics() {
        const columns = tableCard.columnsModel()
        let total = 0
        let stretchColumn = -1
        for (let i = 0; i < columns.length; ++i) {
            total += tableCard.resolvedBaseColumnWidth(i)
            if (columns[i].kind === "data") {
                stretchColumn = i
            }
        }
        tableCard.baseWidthTotal = total
        tableCard.stretchColumnIndex = stretchColumn
    }

    function requestTableLayout() {
        if (tableCard.layoutRefreshPending) {
            return
        }
        tableCard.layoutRefreshPending = true
        Qt.callLater(function() {
            tableCard.layoutRefreshPending = false
            if (bodyTable) {
                bodyTable.forceLayout()
            }
            if (headerView) {
                headerView.forceLayout()
            }
        })
    }

    function previewColumnWidth(columnIndex, width) {
        const meta = tableCard.columnMeta(columnIndex)
        if (!meta || !meta.resizable) {
            return
        }
        const minWidth = Number(meta.minWidth || 96)
        const normalizedWidth = Math.max(minWidth, Math.round(Number(width)))
        if (!Number.isFinite(normalizedWidth)) {
            return
        }
        const next = Object.assign({}, tableCard.pendingColumnWidths)
        if (next[meta.key] === normalizedWidth) {
            return
        }
        next[meta.key] = normalizedWidth
        tableCard.pendingColumnWidths = next
        tableCard.refreshColumnMetrics()
        tableCard.requestTableLayout()
    }

    function clearPendingColumnWidth(columnKey) {
        if (columnKey === undefined) {
            if (Object.keys(tableCard.pendingColumnWidths).length === 0) {
                return
            }
            tableCard.pendingColumnWidths = ({})
            tableCard.refreshColumnMetrics()
            tableCard.requestTableLayout()
            return
        }
        if (tableCard.pendingColumnWidths[columnKey] === undefined) {
            return
        }
        const next = Object.assign({}, tableCard.pendingColumnWidths)
        delete next[columnKey]
        tableCard.pendingColumnWidths = next
        tableCard.refreshColumnMetrics()
        tableCard.requestTableLayout()
    }

    function commitColumnWidth(columnIndex) {
        const meta = tableCard.columnMeta(columnIndex)
        if (!meta || !tableCard.screenViewModel) {
            return
        }
        const pendingWidth = tableCard.pendingColumnWidths[meta.key]
        if (pendingWidth === undefined) {
            return
        }
        tableCard.screenViewModel.set_column_width(meta.key, pendingWidth)
        tableCard.clearPendingColumnWidth(meta.key)
    }

    function availableTableWidth() {
        const bodyWidth = bodyTable ? bodyTable.width : 0
        const verticalBarWidth = bodyVerticalBar && bodyVerticalBar.visible ? bodyVerticalBar.width : 0
        const headerWidth = headerView ? headerView.width : 0
        return Math.max(0, Math.max(bodyWidth - verticalBarWidth, headerWidth))
    }

    function preserveViewport(callback) {
        const previousX = bodyTable ? bodyTable.contentX : 0
        const previousY = bodyTable ? bodyTable.contentY : 0
        callback()
        Qt.callLater(function() {
            if (!bodyTable) {
                return
            }
            const maxX = tableCard.maxTableContentX()
            const maxY = tableCard.maxTableContentY()
            bodyTable.contentX = Math.max(0, Math.min(previousX, maxX))
            bodyTable.contentY = Math.max(0, Math.min(previousY, maxY))
        })
    }

    function maxTableContentY() {
        if (!bodyTable) {
            return 0
        }
        return Math.max(0, tableCard.rowCount() * 50 - bodyTable.height)
    }

    function maxTableContentX() {
        if (!bodyTable) {
            return 0
        }
        return Math.max(0, tableCard.tableContentWidthFromColumns() - bodyTable.width)
    }

    function tableContentWidthFromColumns() {
        const columns = tableCard.columnsModel()
        let total = 0
        for (let columnIndex = 0; columnIndex < columns.length; ++columnIndex) {
            total += tableCard.columnWidth(columnIndex)
        }
        return total
    }

    function normalizedWheelDelta(event) {
        if (event.pixelDelta.y !== 0) {
            return event.pixelDelta.y
        }
        if (event.angleDelta.y !== 0) {
            return (event.angleDelta.y / 120) * tableCard.wheelStep
        }
        return 0
    }

    function rowCount() {
        if (!tableCard.screenViewModel || !tableCard.screenViewModel.table_model) {
            return 0
        }
        return tableCard.screenViewModel.table_model.rowCount()
    }

    function totalPages() {
        if (!tableCard.screenViewModel) {
            return 1
        }
        const totalCount = Number(tableCard.screenViewModel.total_count || 0)
        const pageSize = Math.max(1, Number(tableCard.screenViewModel.page_size || 1))
        return Math.max(1, Math.ceil(totalCount / pageSize))
    }

    function pageStartRecord() {
        if (!tableCard.screenViewModel || tableCard.screenViewModel.total_count <= 0) {
            return 0
        }
        return tableCard.screenViewModel.current_page * tableCard.screenViewModel.page_size + 1
    }

    function pageEndRecord() {
        if (!tableCard.screenViewModel || tableCard.screenViewModel.total_count <= 0) {
            return 0
        }
        return Math.min(
            tableCard.screenViewModel.total_count,
            (tableCard.screenViewModel.current_page + 1) * tableCard.screenViewModel.page_size
        )
    }

    function syncPageJumpText() {
        tableCard.pageJumpText = String(tableCard.screenViewModel ? tableCard.screenViewModel.current_page + 1 : 1)
    }

    function applyPageJump() {
        if (!tableCard.screenViewModel || tableCard.screenViewModel.total_count <= 0) {
            tableCard.syncPageJumpText()
            return
        }

        const requestedPage = Number(tableCard.pageJumpText)
        if (!Number.isFinite(requestedPage)) {
            tableCard.syncPageJumpText()
            return
        }

        const normalizedPage = Math.max(1, Math.min(tableCard.totalPages(), Math.floor(requestedPage)))
        tableCard.pageJumpText = String(normalizedPage)
        tableCard.screenViewModel.set_page_index(normalizedPage - 1)
    }

    function recordIdForRow(rowIndex) {
        if (!tableCard.screenViewModel) {
            return null
        }
        const recordId = tableCard.screenViewModel.record_id_at_row(rowIndex)
        if (recordId === undefined || recordId === null) {
            return null
        }
        const normalizedId = Number(recordId)
        if (!Number.isFinite(normalizedId) || normalizedId < 0) {
            return null
        }
        return normalizedId
    }

    function isSelectedRow(rowIndex) {
        return tableCard.screenViewModel
            && tableCard.screenViewModel.selected_row_index === rowIndex
    }

    function selectRow(rowIndex) {
        const recordId = tableCard.recordIdForRow(rowIndex)
        if (recordId === null) {
            return
        }
        tableCard.screenViewModel.select_record_by_id(recordId)
        tableCard.recordSelected(recordId)
    }

    function clearCellRangeSelection() {
        tableCard.hasCellRangeSelection = false
        tableCard.cellRangeSelectionActive = false
        tableCard.cellRangeStartRow = -1
        tableCard.cellRangeStartColumn = -1
        tableCard.cellRangeEndRow = -1
        tableCard.cellRangeEndColumn = -1
        tableCard.cellRangeDragPointX = 0
        tableCard.cellRangeDragPointY = 0
    }

    function startCellRangeSelection(rowIndex, columnIndex) {
        if (rowIndex < 0 || columnIndex < 0 || !tableCard.isDataColumn(columnIndex)) {
            tableCard.clearCellRangeSelection()
            return
        }
        tableCard.cellRangeSelectionActive = true
        tableCard.hasCellRangeSelection = true
        tableCard.cellRangeStartRow = rowIndex
        tableCard.cellRangeStartColumn = columnIndex
        tableCard.cellRangeEndRow = rowIndex
        tableCard.cellRangeEndColumn = columnIndex
    }

    function updateCellRangeSelection(rowIndex, columnIndex) {
        if (!tableCard.cellRangeSelectionActive || rowIndex < 0 || columnIndex < 0 || !tableCard.isDataColumn(columnIndex)) {
            return
        }
        tableCard.cellRangeEndRow = rowIndex
        tableCard.cellRangeEndColumn = columnIndex
    }

    function rowIndexAtTablePoint(point) {
        if (!bodyTable) {
            return -1
        }
        const contentY = Math.max(0, Number(bodyTable.contentY || 0) + Number(point.y || 0))
        const rowHeight = 50
        const rowIndex = Math.floor(contentY / rowHeight)
        return rowIndex >= 0 && rowIndex < tableCard.rowCount() ? rowIndex : -1
    }

    function columnIndexAtTablePoint(point) {
        if (!bodyTable) {
            return -1
        }
        const contentX = Math.max(0, Number(bodyTable.contentX || 0) + Number(point.x || 0))
        const columns = tableCard.columnsModel()
        let cursorX = 0
        for (let columnIndex = 0; columnIndex < columns.length; ++columnIndex) {
            const width = tableCard.columnWidth(columnIndex)
            if (contentX >= cursorX && contentX < cursorX + width) {
                return columnIndex
            }
            cursorX += width
        }
        return -1
    }

    function updateCellRangeSelectionFromPoint(point) {
        const rowIndex = tableCard.rowIndexAtTablePoint(point)
        const columnIndex = tableCard.columnIndexAtTablePoint(point)
        tableCard.updateCellRangeSelection(rowIndex, columnIndex)
    }

    function updateCellRangeDragPoint(point) {
        tableCard.cellRangeDragPointX = Number(point.x || 0)
        tableCard.cellRangeDragPointY = Number(point.y || 0)
        tableCard.updateCellRangeSelectionFromPoint(point)
    }

    function autoScrollCellRangeSelection() {
        if (!tableCard.cellRangeSelectionActive || !bodyTable) {
            return
        }

        let nextContentX = Number(bodyTable.contentX || 0)
        let nextContentY = Number(bodyTable.contentY || 0)
        const margin = tableCard.cellRangeAutoScrollMargin
        const step = tableCard.cellRangeAutoScrollStep

        if (tableCard.cellRangeDragPointY < margin) {
            nextContentY -= step
        } else if (tableCard.cellRangeDragPointY > bodyTable.height - margin) {
            nextContentY += step
        }

        if (tableCard.cellRangeDragPointX < margin) {
            nextContentX -= step
        } else if (tableCard.cellRangeDragPointX > bodyTable.width - margin) {
            nextContentX += step
        }

        nextContentX = Math.max(0, Math.min(tableCard.maxTableContentX(), nextContentX))
        nextContentY = Math.max(0, Math.min(tableCard.maxTableContentY(), nextContentY))

        if (nextContentX !== bodyTable.contentX) {
            bodyTable.contentX = nextContentX
        }
        if (nextContentY !== bodyTable.contentY) {
            bodyTable.contentY = nextContentY
        }

        tableCard.updateCellRangeSelectionFromPoint(Qt.point(
            tableCard.cellRangeDragPointX,
            tableCard.cellRangeDragPointY
        ))
    }

    function isPointInsideBodyTable(point) {
        if (!bodyTable) {
            return false
        }
        const bodyPoint = tableCard.mapToItem(bodyTable, point.x, point.y)
        return bodyPoint.x >= 0
            && bodyPoint.x <= bodyTable.width
            && bodyPoint.y >= 0
            && bodyPoint.y <= bodyTable.height
    }

    function clearCellRangeSelectionIfOutsideBodyTable(point) {
        if (tableCard.isPointInsideBodyTable(point)) {
            return
        }
        if (tableCard.hasCellRangeSelection) {
            tableCard.clearCellRangeSelection()
        }
        if (tableCard.screenViewModel && tableCard.screenViewModel.selected_row_index >= 0) {
            tableCard.screenViewModel.select_row_index(-1)
        }
    }

    function clearSelectionIfOutsideBodyTable(point, sourceItem) {
        if (!sourceItem) {
            tableCard.clearCellRangeSelectionIfOutsideBodyTable(point)
            return
        }
        const tablePoint = sourceItem.mapToItem(tableCard, point.x, point.y)
        tableCard.clearCellRangeSelectionIfOutsideBodyTable(tablePoint)
    }

    function normalizedCellRange() {
        if (!tableCard.hasCellRangeSelection) {
            return null
        }
        return {
            "firstRow": Math.min(tableCard.cellRangeStartRow, tableCard.cellRangeEndRow),
            "lastRow": Math.max(tableCard.cellRangeStartRow, tableCard.cellRangeEndRow),
            "firstColumn": Math.min(tableCard.cellRangeStartColumn, tableCard.cellRangeEndColumn),
            "lastColumn": Math.max(tableCard.cellRangeStartColumn, tableCard.cellRangeEndColumn)
        }
    }

    function isCellRangeSelected(rowIndex, columnIndex) {
        const range = tableCard.normalizedCellRange()
        return !!(range
            && rowIndex >= range.firstRow
            && rowIndex <= range.lastRow
            && columnIndex >= range.firstColumn
            && columnIndex <= range.lastColumn
            && tableCard.isDataColumn(columnIndex))
    }

    function copyCellRangeSelection() {
        if (!tableCard.hasCellRangeSelection || !tableCard.screenViewModel || !tableCard.screenViewModel.table_model) {
            return false
        }
        return tableCard.screenViewModel.table_model.copy_display_range_to_clipboard(
            tableCard.cellRangeStartRow,
            tableCard.cellRangeStartColumn,
            tableCard.cellRangeEndRow,
            tableCard.cellRangeEndColumn
        )
    }

    function ensureSelectedRowVisible(rowIndex) {
        if (!bodyTable || rowIndex === undefined || rowIndex === null || rowIndex < 0) {
            return
        }
        Qt.callLater(function() {
            if (!bodyTable || rowIndex < 0 || rowIndex >= tableCard.rowCount()) {
                return
            }
            bodyTable.positionViewAtRow(rowIndex, TableView.AlignVCenter)
            bodyTable.forceActiveFocus()
        })
    }

    function openMenu(menu, x, y, rowIndex) {
        tableCard.clearCellRangeSelection()
        tableCard.selectRow(rowIndex)
        menu.x = x
        menu.y = y
        menu.open()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: theme.spacing4

        Shortcut {
            sequences: [StandardKey.Copy]
            enabled: tableCard.hasCellRangeSelection
            onActivated: tableCard.copyCellRangeSelection()
        }

        Timer {
            id: cellRangeAutoScrollTimer

            interval: 40
            repeat: true
            running: tableCard.cellRangeSelectionActive
            onTriggered: tableCard.autoScrollCellRangeSelection()
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
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

                    HorizontalHeaderView {
                        id: headerView

                        resizableColumns: false
                        Layout.fillWidth: true
                        Layout.preferredHeight: 46
                        syncView: bodyTable
                        clip: true
                        model: tableCard.screenViewModel ? tableCard.screenViewModel.table_model : null
                        columnWidthProvider: function(column) {
                            return tableCard.columnWidth(column)
                        }
                        onWidthChanged: forceLayout()
                        Component.onCompleted: forceLayout()

                        delegate: Rectangle {
                            id: headerCell
                            required property int column

                            implicitWidth: tableCard.columnWidth(column)
                            implicitHeight: 46
                            color: theme.surfaceLow
                            border.width: 0

                            property var columnMeta: tableCard.columnMeta(column)
                            property real dragStartX: 0
                            property int dragStartWidth: 0

                            MouseArea {
                                anchors.fill: parent
                                anchors.rightMargin: headerCell.columnMeta && headerCell.columnMeta.resizable ? 10 : 0
                                enabled: !!(headerCell.columnMeta && headerCell.columnMeta.sortable)
                                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (enabled && tableCard.screenViewModel) {
                                        tableCard.screenViewModel.toggle_sort(headerCell.columnMeta.key)
                                    }
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: theme.spacing3
                                anchors.rightMargin: theme.spacing3
                                spacing: theme.spacing2

                                Label {
                                    Layout.fillWidth: true
                                    text: headerCell.columnMeta ? headerCell.columnMeta.header : ""
                                    color: theme.textSecondary
                                    font.family: theme.bodyFontFamily
                                    font.pixelSize: theme.captionSize
                                    font.bold: true
                                    elide: Text.ElideRight
                                }

                                Label {
                                    visible: !!(headerCell.columnMeta
                                        && headerCell.columnMeta.sortable
                                        && tableCard.screenViewModel
                                        && tableCard.screenViewModel.sort_field === headerCell.columnMeta.key)
                                    text: tableCard.screenViewModel
                                        && tableCard.screenViewModel.sort_direction === "desc" ? "\u2193" : "\u2191"
                                    color: theme.primary
                                    font.family: theme.bodyFontFamily
                                    font.pixelSize: theme.bodySize
                                    font.bold: true
                                }
                            }

                            Rectangle {
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.right: parent.right
                                width: 10
                                visible: !!(headerCell.columnMeta && headerCell.columnMeta.resizable)
                                color: resizeHandle.containsMouse || resizeHandle.pressed ? theme.surfaceMid : "transparent"

                                MouseArea {
                                    id: resizeHandle

                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.SizeHorCursor
                                    acceptedButtons: Qt.LeftButton
                                    preventStealing: true

                                    onPressed: function(mouse) {
                                        const point = resizeHandle.mapToItem(tableCard, mouse.x, mouse.y)
                                        headerCell.dragStartX = point.x
                                        headerCell.dragStartWidth = tableCard.columnWidth(headerCell.column)
                                    }

                                    onPositionChanged: function(mouse) {
                                        if (!(mouse.buttons & Qt.LeftButton) || !headerCell.columnMeta || !tableCard.screenViewModel) {
                                            return
                                        }
                                        const point = resizeHandle.mapToItem(tableCard, mouse.x, mouse.y)
                                        const delta = point.x - headerCell.dragStartX
                                        tableCard.previewColumnWidth(headerCell.column, headerCell.dragStartWidth + delta)
                                    }

                                    onReleased: tableCard.commitColumnWidth(headerCell.column)
                                    onCanceled: tableCard.clearPendingColumnWidth(headerCell.columnMeta ? headerCell.columnMeta.key : undefined)
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
                        boundsBehavior: Flickable.StopAtBounds
                        columnSpacing: 0
                        rowSpacing: 0
                        model: tableCard.screenViewModel ? tableCard.screenViewModel.table_model : null
                        columnWidthProvider: function(column) {
                            return tableCard.columnWidth(column)
                        }
                        rowHeightProvider: function() {
                            return 50
                        }
                        onWidthChanged: forceLayout()
                        Component.onCompleted: forceLayout()
                        z: 2

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.NoButton
                            propagateComposedEvents: true

                            onWheel: function(event) {
                                const deltaY = tableCard.normalizedWheelDelta(event)
                                if (deltaY === 0) {
                                    return
                                }

                                const nextContentY = Math.max(
                                    0,
                                    Math.min(tableCard.maxTableContentY(), bodyTable.contentY - deltaY)
                                )
                                if (nextContentY === bodyTable.contentY) {
                                    return
                                }

                                bodyTable.contentY = nextContentY
                                event.accepted = true
                            }
                        }

                        delegate: Rectangle {
                            id: bodyCell
                            required property int row
                            required property int column
                            required property var display
                            required property var columnKind
                            required property var rowData

                            implicitWidth: tableCard.columnWidth(column)
                            implicitHeight: 50
                            color: tableCard.isCellRangeSelected(bodyCell.row, bodyCell.column)
                                ? theme.primaryFixed
                                : !tableCard.hasCellRangeSelection && tableCard.isSelectedRow(row)
                                ? theme.primaryFixed
                                : row % 2 === 0 ? theme.surfaceRaised : theme.surfaceLow
                            border.width: 0

                            readonly property var columnMeta: tableCard.columnMeta(column)
                            readonly property var recordId: tableCard.recordIdForRow(row)

                            Menu {
                                id: rowMenu

                                MenuItem {
                                    text: tableCard.viewActionText
                                    visible: tableCard.showViewAction
                                    height: visible ? implicitHeight : 0
                                    enabled: bodyCell.recordId !== null
                                    onTriggered: tableCard.viewRecordRequested(bodyCell.recordId)
                                }

                                MenuItem {
                                    text: qsTr("Exportar Excel")
                                    visible: tableCard.showExportAction
                                    height: visible ? implicitHeight : 0
                                    enabled: bodyCell.recordId !== null
                                    onTriggered: tableCard.exportRecordRequested(bodyCell.recordId)
                                }

                                MenuItem {
                                    text: qsTr("Editar")
                                    visible: bodyCell.recordId !== null
                                        && (tableCard.screenViewModel ? tableCard.screenViewModel.can_edit : false)
                                    height: visible ? implicitHeight : 0
                                    enabled: bodyCell.recordId !== null
                                        && (tableCard.screenViewModel ? tableCard.screenViewModel.can_edit : false)
                                    onTriggered: tableCard.editRecordRequested(bodyCell.recordId)
                                }

                                MenuItem {
                                    text: qsTr("Borrar")
                                    visible: bodyCell.recordId !== null
                                        && tableCard.showDeleteAction
                                        && (tableCard.screenViewModel ? tableCard.screenViewModel.can_delete : false)
                                    height: visible ? implicitHeight : 0
                                    enabled: bodyCell.recordId !== null
                                        && tableCard.showDeleteAction
                                        && (tableCard.screenViewModel ? tableCard.screenViewModel.can_delete : false)
                                    onTriggered: tableCard.deleteRecordRequested(bodyCell.recordId)
                                }
                            }

                            MouseArea {
                                id: bodyCellMouseArea

                                anchors.fill: parent
                                enabled: !!(bodyCell.columnMeta && bodyCell.columnMeta.kind === "data")
                                    && bodyCell.recordId !== null
                                    && !(tableCard.exportSelectionMode && bodyCell.column === 0)
                                acceptedButtons: Qt.LeftButton
                                preventStealing: true
                                z: 20
                                onPressed: function(mouse) {
                                    bodyTable.forceActiveFocus()
                                    tableCard.startCellRangeSelection(bodyCell.row, bodyCell.column)
                                    const point = bodyCellMouseArea.mapToItem(bodyTable, mouse.x, mouse.y)
                                    tableCard.updateCellRangeDragPoint(point)
                                }
                                onPositionChanged: function(mouse) {
                                    if (!(mouse.buttons & Qt.LeftButton)) {
                                        return
                                    }
                                    const point = bodyCellMouseArea.mapToItem(bodyTable, mouse.x, mouse.y)
                                    tableCard.updateCellRangeDragPoint(point)
                                }
                                onReleased: {
                                    tableCard.cellRangeSelectionActive = false
                                }
                                onCanceled: {
                                    tableCard.cellRangeSelectionActive = false
                                }
                            }

                            TapHandler {
                                acceptedButtons: Qt.RightButton
                                enabled: !!(bodyCell.columnMeta && bodyCell.columnMeta.kind === "data")
                                    && bodyCell.recordId !== null
                                onTapped: function(eventPoint) {
                                    const point = eventPoint.position
                                    tableCard.openMenu(rowMenu, point.x, point.y, bodyCell.row)
                                }
                            }

                            TextInput {
                                id: catalogSelectableCellText

                                anchors.fill: parent
                                anchors.leftMargin: tableCard.exportSelectionMode && bodyCell.column === 0
                                    ? exportSelectionCheckbox.x + exportSelectionCheckbox.implicitWidth + theme.spacing2
                                    : theme.spacing3
                                anchors.rightMargin: theme.spacing3
                                visible: bodyCell.columnKind === "data"
                                verticalAlignment: Text.AlignVCenter
                                text: bodyCell.display !== undefined ? bodyCell.display : ""
                                readOnly: true
                                selectByMouse: true
                                clip: true
                                color: theme.textPrimary
                                selectedTextColor: theme.surfaceRaised
                                selectionColor: theme.primary
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.bodySize
                            }
                            CheckBox {
                                id: exportSelectionCheckbox

                                anchors.left: parent.left
                                anchors.leftMargin: theme.spacing2
                                anchors.verticalCenter: parent.verticalCenter
                                visible: tableCard.exportSelectionMode
                                    && bodyCell.columnKind === "data"
                                    && bodyCell.column === 0
                                    && bodyCell.recordId !== null
                                checked: tableCard.screenViewModel
                                    ? tableCard.screenViewModel.is_record_selected_for_export(bodyCell.recordId)
                                    : false
                                onToggled: {
                                    if (tableCard.screenViewModel && bodyCell.recordId !== null) {
                                        tableCard.screenViewModel.toggle_export_record_id(bodyCell.recordId, checked ? 1 : 0)
                                    }
                                }
                            }
                            Item {
                                anchors.fill: parent
                                visible: bodyCell.columnKind === "actions"

                                AppIconButton {
                                    id: actionButton

                                    anchors.centerIn: parent

                                    buttonSize: theme.controlHeightCompact
                                    iconSize: 16
                                    source: "qrc:/actions/control/vertical_3_dots"
                                    tintColor: theme.textPrimary
                                    disabledTintColor: theme.disabledText
                                    tooltipText: qsTr("Acciones")
                                    enabled: bodyCell.recordId !== null
                                        && !!(tableCard.screenViewModel
                                        && (tableCard.showViewAction
                                        || tableCard.showExportAction
                                        || tableCard.screenViewModel.can_edit
                                        || (tableCard.showDeleteAction && tableCard.screenViewModel.can_delete)))
                                    onClicked: tableCard.openMenu(
                                        rowMenu,
                                        actionButton.x,
                                        actionButton.y + actionButton.height,
                                        bodyCell.row
                                    )
                                }
                            }
                        }

                        ScrollBar.vertical: ScrollBar {
                            id: bodyVerticalBar
                        }
                        ScrollBar.horizontal: ScrollBar {}
                    }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing4

            Label {
                Layout.fillWidth: true
                text: tableCard.screenViewModel && tableCard.screenViewModel.total_count > 0
                    ? qsTr("Mostrando %1-%2 de %3 registros")
                        .arg(tableCard.pageStartRecord())
                        .arg(tableCard.pageEndRecord())
                        .arg(tableCard.screenViewModel.total_count)
                    : qsTr("Sin registros para mostrar")
                color: theme.textSecondary
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.captionSize
                elide: Text.ElideRight
            }

            RowLayout {
                spacing: theme.spacing2

                AppIconButton {
                    objectName: "paginationFirstButton"
                    buttonSize: theme.controlHeightCompact
                    iconSize: 16
                    source: "qrc:/actions/control/double_arrow_left"
                    tintColor: theme.textPrimary
                    disabledTintColor: theme.disabledText
                    tooltipText: qsTr("Primera pagina")
                    enabled: tableCard.screenViewModel
                        && !tableCard.screenViewModel.is_busy
                        && tableCard.screenViewModel.has_prev_page
                    onClicked: tableCard.screenViewModel.set_page_index(0)
                }

                AppIconButton {
                    objectName: "paginationPrevButton"
                    buttonSize: theme.controlHeightCompact
                    iconSize: 16
                    source: "qrc:/actions/control/chevron_left"
                    tintColor: theme.textPrimary
                    disabledTintColor: theme.disabledText
                    tooltipText: qsTr("Pagina anterior")
                    enabled: tableCard.screenViewModel
                        && !tableCard.screenViewModel.is_busy
                        && tableCard.screenViewModel.has_prev_page
                    onClicked: tableCard.screenViewModel.prev_page_slot()
                }

                Label {
                    text: qsTr("Pagina")
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                }

                AppTextField {
                    objectName: "paginationPageField"
                    Layout.preferredWidth: 72
                    Layout.minimumWidth: 72
                    Layout.maximumWidth: 72
                    enabled: tableCard.screenViewModel
                        && !tableCard.screenViewModel.is_busy
                        && tableCard.screenViewModel.total_count > 0
                    text: tableCard.pageJumpText
                    horizontalAlignment: Text.AlignHCenter
                    selectByMouse: true
                    inputMethodHints: Qt.ImhDigitsOnly
                    validator: IntValidator {
                        bottom: 1
                        top: tableCard.totalPages()
                    }
                    onTextEdited: tableCard.pageJumpText = text
                    onAccepted: tableCard.applyPageJump()
                    onEditingFinished: tableCard.applyPageJump()
                }

                Label {
                    objectName: "paginationTotalPagesLabel"
                    text: qsTr("de %1").arg(tableCard.totalPages())
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                }

                AppButton {
                    objectName: "paginationGoButton"
                    compact: true
                    variant: "secondary"
                    text: qsTr("Ir")
                    enabled: tableCard.screenViewModel
                        && !tableCard.screenViewModel.is_busy
                        && tableCard.screenViewModel.total_count > 0
                    onClicked: tableCard.applyPageJump()
                }

                AppIconButton {
                    objectName: "paginationNextButton"
                    buttonSize: theme.controlHeightCompact
                    iconSize: 16
                    source: "qrc:/actions/control/chevron_right"
                    tintColor: theme.textPrimary
                    disabledTintColor: theme.disabledText
                    tooltipText: qsTr("Pagina siguiente")
                    enabled: tableCard.screenViewModel
                        && !tableCard.screenViewModel.is_busy
                        && tableCard.screenViewModel.has_next_page
                    onClicked: tableCard.screenViewModel.next_page_slot()
                }

                AppIconButton {
                    objectName: "paginationLastButton"
                    buttonSize: theme.controlHeightCompact
                    iconSize: 16
                    source: "qrc:/actions/control/double_arrow_right"
                    tintColor: theme.textPrimary
                    disabledTintColor: theme.disabledText
                    tooltipText: qsTr("Ultima pagina")
                    enabled: tableCard.screenViewModel
                        && !tableCard.screenViewModel.is_busy
                        && tableCard.screenViewModel.has_next_page
                    onClicked: tableCard.screenViewModel.set_page_index(tableCard.totalPages() - 1)
                }
            }
        }
    }

    Connections {
        target: tableCard.screenViewModel

        function onColumnsChanged() {
            tableCard.syncColumnsSnapshot()
            tableCard.preserveViewport(function() {
                bodyTable.forceLayout()
                headerView.forceLayout()
            })
        }

        function onCurrentPageChanged() {
            tableCard.clearCellRangeSelection()
            tableCard.syncPageJumpText()
        }

        function onTotalCountChanged() {
            tableCard.syncPageJumpText()
        }

        function onPageSizeChanged() {
            tableCard.syncPageJumpText()
        }
    }

    Component.onCompleted: {
        tableCard.syncPageJumpText()
        tableCard.syncColumnsSnapshot()
    }

}
