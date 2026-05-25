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
    property string value: "0"
    property string monogram: ""
    property string iconSource: ""
    property string accentTone: "primary"
    property string moduleId: ""
    property string target: "list"
    property var routeData: ({})

    heightSource: contentLayout
    padding: theme.spacing4
    tone: "raised"
    subtleBorder: true

    Theme {
        id: theme
    }
    
    HoverHandler {
        cursorShape: Qt.PointingHandCursor
        target: root
    }

    TapHandler {
        onTapped: {
            const route = Object.assign({
                "module_id": root.moduleId,
                "target": root.target
            }, root.routeData || {})
            root.clicked(route)
        }
    }

    function toneColor() {
        switch (root.accentTone) {
        case "warning":
            return theme.warning
        case "success":
            return theme.success
        case "danger":
            return theme.danger
        default:
            return theme.primary
        }
    }

    function toneContainer() {
        switch (root.accentTone) {
        case "warning":
            return theme.warningContainer
        case "success":
            return theme.successContainer
        case "danger":
            return theme.dangerContainer
        default:
            return theme.primaryFixed
        }
    }

    ColumnLayout {
        id: contentLayout
        anchors.fill: parent
        
        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing3

            Rectangle {
                Layout.preferredWidth: 38
                Layout.preferredHeight: 38
                radius: 19
                color: root.toneContainer()

                Label {
                    anchors.centerIn: parent
                    visible: root.iconSource === ""
                    text: root.monogram
                    color: root.toneColor()
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                    font.bold: true
                }

                AppIcon {
                    anchors.centerIn: parent
                    width: 20
                    height: 20
                    size: 20
                    visible: root.iconSource !== ""
                    source: root.iconSource
                    tintColor: root.toneColor()
                }
            }

            Label {
                Layout.fillWidth: true
                text: root.title
                color: theme.textSecondary
                font.family: theme.bodyFontFamily
                font.pixelSize: theme.bodySize
                font.bold: true
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }

        Label {
            Layout.alignment: Qt.AlignCenter
            text: root.value
            color: theme.textPrimary
            font.family: theme.headlineFontFamily
            font.pixelSize: theme.displaySize
            font.bold: true
            elide: Text.Center
        }

        Item {
            Layout.preferredHeight: theme.spacing5
            Layout.fillWidth: true
        }
    }
}
