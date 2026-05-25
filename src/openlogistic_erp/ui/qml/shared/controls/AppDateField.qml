pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../controls"
import "../theme"

Item {
    id: root

    property alias text: input.text
    property alias placeholderText: input.placeholderText
    property bool invalid: false
    property bool enabled: true
    property int selectedDay: 1
    property int selectedMonth: 1
    property int selectedYear: 2000
    signal textEdited(string text)

    Theme {
        id: theme
    }

    implicitWidth: row.implicitWidth
    implicitHeight: row.implicitHeight

    function parseTextValue() {
        const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec((input.text || "").trim())
        if (match) {
            return {
                day: Number(match[1]),
                month: Number(match[2]),
                year: Number(match[3]),
            }
        }
        const today = new Date()
        return {
            day: today.getDate(),
            month: today.getMonth() + 1,
            year: today.getFullYear(),
        }
    }

    function syncPopupState() {
        const parts = parseTextValue()
        root.selectedDay = parts.day
        root.selectedMonth = parts.month
        root.selectedYear = parts.year
        monthGrid.month = parts.month - 1
        monthGrid.year = parts.year
    }

    function formattedDate() {
        return `${String(root.selectedDay).padStart(2, "0")}/${String(root.selectedMonth).padStart(2, "0")}/${root.selectedYear}`
    }

    function selectDate(date) {
        root.selectedDay = date.getDate()
        root.selectedMonth = date.getMonth() + 1
        root.selectedYear = date.getFullYear()
        monthGrid.month = date.getMonth()
        monthGrid.year = date.getFullYear()
    }

    function selectCalendarDate(date) {
        root.selectedDay = date.getUTCDate()
        root.selectedMonth = date.getUTCMonth() + 1
        root.selectedYear = date.getUTCFullYear()
        monthGrid.month = date.getUTCMonth()
        monthGrid.year = date.getUTCFullYear()
    }

    function moveMonth(delta) {
        const visibleDate = new Date(monthGrid.year, monthGrid.month + delta, 1)
        monthGrid.month = visibleDate.getMonth()
        monthGrid.year = visibleDate.getFullYear()
    }

    RowLayout {
        id: row

        anchors.fill: parent
        spacing: theme.spacing2

        AppTextField {
            id: input

            Layout.fillWidth: true
            enabled: root.enabled
            invalid: root.invalid
            placeholderText: qsTr("DD/MM/YYYY")
            onTextEdited: root.textEdited(text)
        }

        AppIconButton {
            id: pickerButton

            Layout.preferredWidth: theme.controlHeightDefault
            Layout.preferredHeight: theme.controlHeightDefault
            buttonSize: theme.controlHeightDefault
            iconSize: 20
            enabled: root.enabled
            source: "qrc:/actions/control/calendar"
            tintColor: theme.textPrimary
            tooltipText: qsTr("Abrir calendario")

            onClicked: {
                root.syncPopupState()
                picker.open()
            }
        }
    }
    Popup {
        id: picker

        y: root.height + theme.spacing2
        width: 340
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent

        background: Rectangle {
            radius: theme.radiusLarge
            color: theme.surfaceRaised
            border.width: 1
            border.color: theme.outlineVariant
        }

        contentItem: ColumnLayout {
            spacing: theme.spacing4

            Label {
                text: monthGrid.title
                color: theme.textPrimary
                font.family: theme.headlineFontFamily
                font.pixelSize: theme.sectionTitleSize
                font.bold: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing2

                AppIconButton {
                    buttonSize: theme.controlHeightCompact
                    iconSize: 16
                    source: "qrc:/actions/control/chevron_left"
                    tintColor: theme.textPrimary
                    tooltipText: qsTr("Mes anterior")
                    onClicked: root.moveMonth(-1)
                }

                DayOfWeekRow {
                    Layout.fillWidth: true
                    locale: Qt.locale()
                }

                AppIconButton {
                    buttonSize: theme.controlHeightCompact
                    iconSize: 16
                    source: "qrc:/actions/control/chevron_right"
                    tintColor: theme.textPrimary
                    tooltipText: qsTr("Mes siguiente")
                    onClicked: root.moveMonth(1)
                }
            }

            MonthGrid {
                id: monthGrid

                Layout.fillWidth: true
                locale: Qt.locale()
                month: (new Date()).getMonth()
                year: (new Date()).getFullYear()
                onClicked: function(date) {
                    root.selectCalendarDate(date)
                }

                delegate: Rectangle {
                    required property var model

                    readonly property bool isCurrentMonth: model.month === monthGrid.month
                    readonly property bool isSelected: model.day === root.selectedDay
                        && model.month === root.selectedMonth - 1
                        && model.year === root.selectedYear
                    readonly property bool isToday: model.today

                    implicitWidth: 40
                    implicitHeight: 32
                    radius: theme.radiusSmall
                    color: isSelected ? theme.primary : "transparent"
                    border.width: isToday && !isSelected ? 1 : 0
                    border.color: theme.primary

                    Label {
                        anchors.centerIn: parent
                        text: parent.model.day
                        color: parent.isSelected ? theme.textOnPrimary
                            : parent.isCurrentMonth ? theme.textPrimary
                            : theme.disabledText
                        font.pixelSize: theme.bodySize
                        font.bold: parent.isSelected || parent.isToday
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing3

                AppButton {
                    compact: true
                    text: qsTr("Hoy")
                    variant: "ghost"
                    onClicked: {
                        const today = new Date()
                        root.selectDate(today)
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                AppButton {
                    compact: true
                    text: qsTr("Limpiar")
                    variant: "ghost"
                    onClicked: {
                        root.text = ""
                        root.textEdited(root.text)
                        picker.close()
                    }
                }

                AppButton {
                    compact: true
                    text: qsTr("Aplicar")
                    variant: "contrast"
                    onClicked: {
                        root.text = root.formattedDate()
                        root.textEdited(root.text)
                        picker.close()
                    }
                }
            }
        }
    }
}
