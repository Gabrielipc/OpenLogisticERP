pragma ComponentBehavior: Bound

import QtQuick
import "../theme"

Rectangle {
    id: root

    property string tone: "raised"
    property bool subtleBorder: false
    property int padding: theme.spacing6
    property Item sizeSource: null

    default property alias contentData: contentItem.data

    Theme {
        id: theme
    }

    implicitWidth: (root.sizeSource ? root.sizeSource.implicitWidth : contentItem.implicitWidth) + root.padding * 2
    implicitHeight: (root.sizeSource ? root.sizeSource.implicitHeight : contentItem.implicitHeight) + root.padding * 2

    radius: theme.radiusLarge
    clip: true
    color: {
        switch (root.tone) {
        case "low":
            return theme.surface
        case "mid":
            return theme.surfaceLow
        case "high":
            return theme.surfaceMid
        case "primary":
            return theme.primary
        default:
            return theme.surfaceRaised
        }
    }
    border.width: root.subtleBorder ? 1 : 0
    border.color: theme.alpha(theme.outlineVariant, 0.35)

    Item {
        id: contentItem

        anchors.fill: parent
        anchors.margins: root.padding
        implicitWidth: childrenRect.width
        implicitHeight: childrenRect.height
    }
}
