pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import "../theme"

Item {
    id: root

    required property var tableModel
    required property var headerModel
    required property int rowCount
    required property var columnWidthProvider
    required property Component cellDelegate
    property string emptyText: ""
    property int headerHeight: 44
    property int rowHeight: 52
    readonly property real tableContentWidth: Math.max(0, bodyTable.contentWidth)

    Theme { id: theme }

    implicitHeight: tableContainer.implicitHeight

    Rectangle {
        id: tableContainer
        anchors.fill: parent
        implicitHeight: Math.max(144, Math.min(360, root.headerHeight + 1 + Math.max(root.rowHeight, root.rowCount * root.rowHeight)))
        radius: theme.radiusMedium
        color: theme.surfaceRaised
        border.width: 1
        border.color: theme.outlineVariant
        clip: true

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: Math.max(0, tableContainer.radius - 1)
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
                        radius: Math.max(0, tableContainer.radius - 1)
                        color: "black"
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    color: tableContainer.color
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    HorizontalHeaderView {
                        id: headerView
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.headerHeight
                        syncView: bodyTable
                        clip: true
                        columnWidthProvider: root.columnWidthProvider

                        delegate: Rectangle {
                            id: header
                            required property int column

                            implicitWidth: root.columnWidthProvider(column)
                            implicitHeight: root.headerHeight
                            color: theme.surfaceLow

                            readonly property var headerField: (
                                root.headerModel
                                && column >= 0
                                && column < root.headerModel.length
                            ) ? root.headerModel[column] : ({})

                            Label {
                                anchors.fill: parent
                                anchors.leftMargin: theme.spacing3
                                anchors.rightMargin: theme.spacing3
                                verticalAlignment: Text.AlignVCenter
                                text: header.headerField.label || ""
                                color: theme.textSecondary
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.captionSize
                                font.bold: true
                                elide: Text.ElideRight
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
                        model: root.tableModel
                        columnWidthProvider: root.columnWidthProvider
                        rowHeightProvider: function() { return root.rowHeight }
                        onWidthChanged: forceLayout()
                        Component.onCompleted: forceLayout()

                        delegate: Item {
                            id: cellHost

                            required property int row
                            required property int column
                            required property var rowData
                            required property int rowIndex

                            property Item cellItem: null

                            width: root.columnWidthProvider(column)
                            height: root.rowHeight

                            function createCell() {
                                if (cellItem || !root.cellDelegate)
                                    return

                                cellItem = root.cellDelegate.createObject(cellHost, {
                                    "tableRow": cellHost.row,
                                    "tableColumn": cellHost.column,
                                    "tableRowData": cellHost.rowData,
                                    "tableRowIndex": cellHost.rowIndex
                                })

                                if (!cellItem) {
                                    console.warn("No se pudo crear cellDelegate")
                                    return
                                }

                                syncCell()
                            }

                            function syncCell() {
                                if (!cellItem)
                                    return

                                cellItem.width = cellHost.width
                                cellItem.height = cellHost.height

                                cellItem.tableRow = cellHost.row
                                cellItem.tableColumn = cellHost.column
                                cellItem.tableRowData = cellHost.rowData
                                cellItem.tableRowIndex = cellHost.rowIndex
                            }

                            Component.onCompleted: createCell()

                            onRowChanged: syncCell()
                            onColumnChanged: syncCell()
                            onRowDataChanged: syncCell()
                            onRowIndexChanged: syncCell()
                            onWidthChanged: syncCell()
                            onHeightChanged: syncCell()

                            Component.onDestruction: {
                                if (cellItem)
                                    cellItem.destroy()
                            }
                        }
                    }
                }
                Label {
                    anchors.fill: parent
                    visible: root.rowCount === 0
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: root.emptyText
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.bodySize
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: tableContainer.radius
            color: "transparent"
            border.width: tableContainer.border.width
            border.color: tableContainer.border.color
            z: 10
        }
    }
}
