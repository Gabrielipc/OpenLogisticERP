pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../theme"

Rectangle {
    id: banner

    property string message: ""

    visible: message !== ""
    radius: theme.radiusMedium
    color: theme.dangerContainer
    implicitHeight: errorLabel.implicitHeight + theme.spacing4

    Theme {
        id: theme
    }

    Label {
        id: errorLabel

        anchors.fill: parent
        anchors.margins: theme.spacing3
        text: banner.message
        color: theme.danger
        font.family: theme.bodyFontFamily
        font.pixelSize: theme.bodySize
        wrapMode: Text.WordWrap
    }
}
