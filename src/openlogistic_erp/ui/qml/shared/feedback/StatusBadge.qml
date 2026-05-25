pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../theme"

Rectangle {
    id: root

    property string text: ""

    Theme {
        id: theme
    }

    readonly property string normalizedText: root.text.toLowerCase()

    implicitWidth: badgeLabel.implicitWidth + 18
    implicitHeight: 28
    radius: theme.radiusPill
    color: {
        if (normalizedText.indexOf("activo") >= 0 || normalizedText.indexOf("active") >= 0 || normalizedText.indexOf("entregado") >= 0 || normalizedText.indexOf("delivered") >= 0) {
            return theme.successContainer
        }
        if (normalizedText.indexOf("hold") >= 0 || normalizedText.indexOf("pend") >= 0 || normalizedText.indexOf("warning") >= 0) {
            return theme.warningContainer
        }
        if (normalizedText.indexOf("error") >= 0 || normalizedText.indexOf("critical") >= 0 || normalizedText.indexOf("inactivo") >= 0) {
            return theme.dangerContainer
        }
        return theme.neutralContainer
    }

    Label {
        id: badgeLabel

        anchors.centerIn: parent
        text: root.text
        color: {
            if (root.color === theme.successContainer) {
                return theme.success
            }
            if (root.color === theme.warningContainer) {
                return theme.warning
            }
            if (root.color === theme.dangerContainer) {
                return theme.danger
            }
            return theme.textSecondary
        }
        font.family: theme.bodyFontFamily
        font.pixelSize: theme.captionSize
        font.bold: true
    }
}
