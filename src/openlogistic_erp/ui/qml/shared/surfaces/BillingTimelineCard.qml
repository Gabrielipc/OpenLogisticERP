pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../controls"
import "../theme"

AutoHeightSurfaceCard {
    id: root

    property var rows: []
    property var currencies: []
    property string selectedCurrency: ""
    property bool showReceipts: false
    property bool canCompareReceipts: true

    heightSource: content

    signal currencySelected(string currencyKey)
    signal receiptsVisibleChanged(bool visible)

    tone: "raised"
    padding: theme.spacing5

    Theme {
        id: theme
    }

    function currencyKeys() {
        const keys = []
        for (let i = 0; i < root.rows.length; ++i) {
            const key = String(root.rows[i].moneda || "")
            if (key !== "" && keys.indexOf(key) === -1) {
                keys.push(key)
            }
        }
        return keys
    }

    function rowsForCurrency(currencyKey) {
        const filtered = []
        for (let i = 0; i < root.rows.length; ++i) {
            if (String(root.rows[i].moneda || "") === String(currencyKey || "")) {
                filtered.push(root.rows[i])
            }
        }
        return filtered
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        spacing: theme.spacing4

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing3

            Label {
                Layout.fillWidth: true
                text: qsTr("Facturacion mensual")
                color: theme.textPrimary
                font.family: theme.headlineFontFamily
                font.pixelSize: theme.titleSize
                font.bold: true
                elide: Text.ElideRight
            }

            AppComboBox {
                id: currencySelector

                Layout.preferredWidth: 140
                model: root.currencies
                textRole: "label"
                valueRole: "key"
                enabled: root.currencies.length > 1
                currentIndex: {
                    for (let i = 0; i < root.currencies.length; ++i) {
                        if (String(root.currencies[i].key || "") === root.selectedCurrency) {
                            return i
                        }
                    }
                    return 0
                }
                onActivated: function(index) {
                    const option = root.currencies[index]
                    if (option) {
                        root.currencySelected(String(option.key || ""))
                    }
                }
            }

            CheckBox {
                id: receiptsToggle

                visible: root.canCompareReceipts
                enabled: root.canCompareReceipts
                text: qsTr("Recibos")
                checked: root.canCompareReceipts && root.showReceipts
                onToggled: root.receiptsVisibleChanged(checked)
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.rows.length === 0
            text: qsTr("Sin facturacion ni recibos en los ultimos 12 meses.")
            color: theme.textSecondary
            font.family: theme.bodyFontFamily
            font.pixelSize: theme.bodySize
            wrapMode: Text.WordWrap
        }

        Repeater {
            model: root.currencyKeys()

            delegate: ColumnLayout {
                id: currencySection

                required property string modelData
                readonly property var currencyRows: root.rowsForCurrency(currencySection.modelData)

                Layout.fillWidth: true
                spacing: theme.spacing3

                Label {
                    Layout.fillWidth: true
                    text: currencySection.modelData
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                    font.bold: true
                }

                Canvas {
                    id: chartCanvas

                    Layout.fillWidth: true
                    Layout.preferredHeight: 84

                    readonly property real chartPadding: 10

                    function maxValue() {
                        let value = 1
                        for (let i = 0; i < currencySection.currencyRows.length; ++i) {
                            value = Math.max(value, Number(currencySection.currencyRows[i].max_value || 0))
                        }
                        return value
                    }

                    function pointX(index, count) {
                        if (count <= 1) {
                            return chartCanvas.width / 2
                        }
                        const usableWidth = Math.max(1, chartCanvas.width - chartCanvas.chartPadding * 2)
                        return chartCanvas.chartPadding + usableWidth * index / (count - 1)
                    }

                    function pointY(value, maxValue) {
                        const usableHeight = Math.max(1, chartCanvas.height - chartCanvas.chartPadding * 2)
                        const ratio = Math.max(0, Math.min(1, Number(value || 0) / Math.max(1, maxValue)))
                        return chartCanvas.chartPadding + usableHeight * (1 - ratio)
                    }

                    function drawSeries(ctx, valueRole, strokeColor) {
                        const rows = currencySection.currencyRows
                        const peak = chartCanvas.maxValue()

                        if (rows.length === 0) {
                            return
                        }

                        ctx.lineWidth = 2
                        ctx.strokeStyle = strokeColor
                        ctx.fillStyle = strokeColor
                        ctx.beginPath()

                        for (let i = 0; i < rows.length; ++i) {
                            const x = chartCanvas.pointX(i, rows.length)
                            const y = chartCanvas.pointY(Number(rows[i][valueRole] || 0), peak)
                            if (i === 0) {
                                ctx.moveTo(x, y)
                            } else {
                                ctx.lineTo(x, y)
                            }
                        }

                        ctx.stroke()

                        for (let pointIndex = 0; pointIndex < rows.length; ++pointIndex) {
                            const pointX = chartCanvas.pointX(pointIndex, rows.length)
                            const pointY = chartCanvas.pointY(Number(rows[pointIndex][valueRole] || 0), peak)
                            ctx.beginPath()
                            ctx.arc(pointX, pointY, 4, 0, Math.PI * 2)
                            ctx.fill()
                        }
                    }

                    onPaint: {
                        const ctx = chartCanvas.getContext("2d")
                        ctx.reset()
                        ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height)
                        chartCanvas.drawSeries(ctx, "facturado", theme.primary)
                        if (root.showReceipts) {
                            chartCanvas.drawSeries(ctx, "pagado", theme.success)
                        }
                    }

                    onWidthChanged: chartCanvas.requestPaint()
                    onHeightChanged: chartCanvas.requestPaint()

                    Connections {
                        target: root

                        function onRowsChanged() {
                            chartCanvas.requestPaint()
                        }

                        function onShowReceiptsChanged() {
                            chartCanvas.requestPaint()
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.spacing2

                    Repeater {
                        model: currencySection.currencyRows

                        delegate: ColumnLayout {
                            id: monthLabelColumn

                            required property var modelData

                            Layout.fillWidth: true
                            Layout.minimumWidth: 48
                            spacing: theme.spacing2

                            Label {
                                Layout.fillWidth: true
                                text: String(monthLabelColumn.modelData.period_label || "")
                                color: theme.textSecondary
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.captionSize
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                            }

                            Label {
                                Layout.fillWidth: true
                                text: String(monthLabelColumn.modelData.facturado_display || "")
                                color: theme.textPrimary
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.captionSize
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                            }

                            Label {
                                Layout.fillWidth: true
                                visible: root.showReceipts
                                text: String(monthLabelColumn.modelData.pagado_display || "")
                                color: theme.success
                                font.family: theme.bodyFontFamily
                                font.pixelSize: theme.captionSize
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }
        }
    }
}
