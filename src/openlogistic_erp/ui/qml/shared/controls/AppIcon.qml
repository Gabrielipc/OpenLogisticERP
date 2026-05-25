pragma ComponentBehavior: Bound

import QtQuick
import Qt5Compat.GraphicalEffects

Item {
    id: root

    property string source: ""
    property int size: 20
    property bool tinted: true
    property color tintColor: "transparent"

    implicitWidth: root.size
    implicitHeight: root.size
    visible: root.source !== ""

    Image {
        id: sourceImage

        anchors.fill: parent
        visible: root.source !== "" && !root.tinted
        source: root.source
        fillMode: Image.PreserveAspectFit
        smooth: true
    }

    Image {
        id: maskImage

        anchors.fill: parent
        visible: false
        source: root.source
        fillMode: Image.PreserveAspectFit
        smooth: true
    }

    ColorOverlay {
        anchors.fill: maskImage
        visible: root.source !== "" && root.tinted
        source: maskImage
        color: root.tintColor
    }
}
