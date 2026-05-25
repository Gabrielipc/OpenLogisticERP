pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../controls"
import "../surfaces"
import "../feedback"
import "../theme"

AutoHeightSurfaceCard {
    id: root

    heightSource: contentLayout

    property string eyebrow: ""
    property string value: ""
    property string caption: ""
    property string badgeText: ""
    property string accentTone: "primary"
    property string monogram: ""
    property string iconSource: ""

    Theme {
        id: theme
    }

    tone: accentTone === "soft" ? "low" : "raised"
    padding: theme.spacing6

    ColumnLayout {
        id: contentLayout

        anchors.fill: parent
        spacing: theme.spacing5

        RowLayout {
            Layout.fillWidth: true

            Rectangle {
                Layout.preferredWidth: 42
                Layout.preferredHeight: 42
                radius: 21
                color: root.accentTone === "warning" ? theme.warningContainer
                    : root.accentTone === "success" ? theme.successContainer
                    : theme.primaryFixed

                Label {
                    anchors.centerIn: parent
                    visible: root.iconSource === ""
                    text: root.monogram
                    color: root.accentTone === "warning" ? theme.warning
                        : root.accentTone === "success" ? theme.success
                        : theme.primary
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
                    tintColor: root.accentTone === "warning" ? theme.warning
                        : root.accentTone === "success" ? theme.success
                        : theme.primary
                }
            }

            Item {
                Layout.fillWidth: true
            }

            StatusBadge {
                visible: root.badgeText !== ""
                text: root.badgeText
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Label {
                text: root.eyebrow
                color: theme.textSecondary
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.captionSize
                wrapMode: Text.WordWrap
                font.bold: true
            }

            Label {
                text: root.value
                color: theme.textPrimary
                font.family: theme.headlineFontFamily
                font.pixelSize: theme.titleSize
                wrapMode: Text.WordWrap
                font.bold: true
            }

            Label {
                visible: root.caption !== ""
                text: root.caption
                color: theme.textSecondary
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.captionSize
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
    }
}
