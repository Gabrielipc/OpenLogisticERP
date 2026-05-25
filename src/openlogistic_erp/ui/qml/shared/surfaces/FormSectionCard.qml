pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../controls"
import "../surfaces"
import "../theme"

AutoHeightSurfaceCard {
    id: root

    width: parent ? parent.width : implicitWidth
    height: parent ? parent.height : implicitHeight
    heightSource: contentLayout

    property string title: ""
    property string subtitle: ""
    property string monogram: ""
    property string iconSource: ""

    default property alias sectionContent: sectionBody.data

    Theme {
        id: theme
    }

    tone: "raised"
    padding: theme.spacing8

    ColumnLayout {
        id: contentLayout

        anchors.fill: parent
        spacing: theme.spacing6

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing4

            Rectangle {
                Layout.preferredWidth: 42
                Layout.preferredHeight: 42
                radius: 21
                color: theme.primaryFixed

                Label {
                    anchors.centerIn: parent
                    visible: root.iconSource === ""
                    text: root.monogram
                    color: theme.primary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                    font.bold: true
                }

                AppIcon {
                    anchors.centerIn: parent
                    width: 22
                    height: 22
                    size: 22
                    visible: root.iconSource !== ""
                    source: root.iconSource
                    tintColor: theme.primary
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Label {
                    Layout.fillWidth: true
                    text: root.title
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.sectionTitleSize
                    font.bold: true
                    elide: Text.ElideRight
                }

                Label {
                    visible: root.subtitle !== ""
                    Layout.fillWidth: true
                    text: root.subtitle
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                    wrapMode: Text.WordWrap
                }
            }
        }

        Item {
            id: sectionBody

            Layout.fillWidth: true
            implicitHeight: childrenRect.height
        }
    }
}
