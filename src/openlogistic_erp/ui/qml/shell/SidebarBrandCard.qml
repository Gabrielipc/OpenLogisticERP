pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../shared/surfaces"

AutoHeightSurfaceCard {
    id: root

    required property var theme
    heightSource: contentLayout

    property string badgeText: "OL"
    property string title: ""
    property string subtitle: ""
    property bool collapsed: false

    Layout.fillWidth: true
    tone: "raised"
    padding: root.collapsed ? root.theme.spacing3 : root.theme.spacing5

    ColumnLayout {
        id: contentLayout

        anchors.fill: parent
        spacing: root.theme.spacing3

        RowLayout {
            spacing: root.theme.spacing3

            Rectangle {
                Layout.preferredWidth: root.collapsed ? 38 : 44
                Layout.preferredHeight: root.collapsed ? 38 : 44
                Layout.alignment: Qt.AlignHCenter
                radius: width / 2
                gradient: Gradient {
                    GradientStop { position: 0.0; color: root.theme.primary }
                    GradientStop { position: 1.0; color: root.theme.primaryContainer }
                }

                Label {
                    anchors.centerIn: parent
                    text: root.badgeText
                    color: root.theme.textOnPrimary
                    font.family: root.theme.bodyFontFamily
                    font.pixelSize: root.theme.captionSize
                    font.bold: true
                }
            }

            ColumnLayout {
                visible: !root.collapsed
                Layout.fillWidth: true
                spacing: 1

                Label {
                    Layout.fillWidth: true
                    text: root.title
                    color: root.theme.textPrimary
                    font.family: root.theme.headlineFontFamily
                    font.pixelSize: root.theme.sectionTitleSize
                    font.bold: true
                    elide: Text.ElideRight
                }

                Label {
                    visible: root.subtitle !== ""
                    Layout.fillWidth: true
                    text: root.subtitle
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFontFamily
                    font.pixelSize: root.theme.captionSize
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
