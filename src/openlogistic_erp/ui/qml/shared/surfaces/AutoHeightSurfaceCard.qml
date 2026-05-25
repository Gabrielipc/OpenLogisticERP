pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../surfaces"

SurfaceCard {
    id: root

    required property Item heightSource
    property Item widthSource: root.heightSource

    implicitWidth: (root.widthSource ? root.widthSource.implicitWidth : 0) + root.padding * 2
    implicitHeight: (root.heightSource ? root.heightSource.implicitHeight : 0) + root.padding * 2
    // When the card participates in a fill-width layout, keep its content
    // implicit width from becoming the layout's preferred width.
    Layout.preferredWidth: Layout.fillWidth ? 0 : implicitWidth
    Layout.minimumWidth: 0
    Layout.preferredHeight: implicitHeight
}
