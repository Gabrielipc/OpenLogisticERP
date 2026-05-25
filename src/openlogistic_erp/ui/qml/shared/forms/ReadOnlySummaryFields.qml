pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../controls"
import "../theme"

ColumnLayout {
    id: root

    required property string title
    property string description: ""
    property var fields: []
    property bool empty: false
    property string emptyText: qsTr("Sin datos para mostrar.")
    property bool actionVisible: false
    property string actionText: ""
    property bool secondaryActionVisible: false
    property string secondaryActionText: ""
    signal actionRequested()
    signal secondaryActionRequested()

    spacing: theme.spacing4

    Theme { id: theme }

    function displayValue(value) {
        const normalized = value === undefined || value === null ? "" : String(value).trim()
        return normalized === "" ? "-" : normalized
    }

    RowLayout {
        Layout.fillWidth: true

        Label {
            Layout.fillWidth: true
            text: root.title
            color: theme.textPrimary
            font.family: theme.headlineFontFamily
            font.pixelSize: theme.titleSize
            font.bold: true
            elide: Text.ElideRight
        }

        AppButton {
            Layout.alignment: Qt.AlignCenter
            visible: root.secondaryActionVisible
            variant: "secondary"
            text: root.secondaryActionText
            onClicked: root.secondaryActionRequested()
        }
    }

    Label {
        Layout.fillWidth: true
        visible: root.description.length > 0
        text: root.description
        wrapMode: Text.WordWrap
        color: theme.textSecondary
        font.family: theme.bodyFontFamily
        font.pixelSize: theme.bodySize
    }

    Label {
        Layout.fillWidth: true
        visible: root.empty
        text: root.emptyText
        color: theme.textSecondary
        font.family: theme.bodyFontFamily
        font.pixelSize: theme.bodySize
        wrapMode: Text.WordWrap
    }

    GridLayout {
        Layout.fillWidth: true
        visible: !root.empty
        columns: root.width > 520 ? 2 : 1
        columnSpacing: theme.spacing3
        rowSpacing: theme.spacing3

        Repeater {
            model: root.fields

            delegate: ColumnLayout {
                id: summaryField

                required property var modelData

                Layout.fillWidth: true
                spacing: theme.spacing2

                Label {
                    Layout.fillWidth: true
                    text: summaryField.modelData.label
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                    font.bold: true
                }

                AppTextField {
                    Layout.fillWidth: true
                    enabled: false
                    text: root.displayValue(summaryField.modelData.value)
                }
            }
        }
    }

    AppButton {
        Layout.alignment: Qt.AlignCenter
        visible: root.actionVisible
        variant: "contrast"
        text: root.actionText
        onClicked: root.actionRequested()
    }

}
