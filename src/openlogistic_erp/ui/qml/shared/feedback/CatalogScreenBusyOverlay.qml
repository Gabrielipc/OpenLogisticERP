pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../theme"

Rectangle {
    id: overlay

    property bool active: false

    visible: active
    color: theme.alpha(theme.textPrimary, 0.08)
    z: 10

    Theme {
        id: theme
    }

    BusyIndicator {
        anchors.centerIn: parent
        running: overlay.visible
    }
}
