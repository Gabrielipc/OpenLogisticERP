pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../shared/surfaces"

AutoHeightSurfaceCard {
    id: root

    required property var theme
    heightSource: contentLayout

    property string eyebrow: ""
    property string title: ""
    property string description: ""

    Layout.fillWidth: true
    tone: "raised"
    padding: root.theme.spacing5

    ColumnLayout {
        id: contentLayout

        anchors.fill: parent
        spacing: root.theme.spacing2

        Label {
            Layout.fillWidth: true
            text: root.eyebrow
            color: root.theme.textSecondary
            font.family: root.theme.bodyFontFamily
            font.pixelSize: root.theme.captionSize
            font.bold: true
        }

        Label {
            Layout.fillWidth: true
            text: root.title
            color: root.theme.textPrimary
            font.family: root.theme.headlineFontFamily
            font.pixelSize: root.theme.bodySize
            font.bold: true
        }

        Label {
            visible: root.description !== ""
            Layout.fillWidth: true
            text: root.description
            color: root.theme.textSecondary
            font.family: root.theme.bodyFontFamily
            font.pixelSize: root.theme.captionSize
            wrapMode: Text.WordWrap
        }
    }
}
