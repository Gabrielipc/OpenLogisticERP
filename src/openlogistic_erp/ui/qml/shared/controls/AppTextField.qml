pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../theme"

TextField {
    id: control
    property bool invalid: false

    Theme {
        id: theme
    }

    implicitHeight: theme.controlHeightLarge
    leftPadding: theme.spacing4
    rightPadding: theme.spacing4
    topPadding: theme.spacing3
    bottomPadding: theme.spacing3
    font.family: theme.bodyFontFamily
    font.pixelSize: theme.bodySize
    color: control.enabled ? theme.textPrimary : theme.disabledText
    selectionColor: theme.primaryFixed
    selectedTextColor: theme.primary
    placeholderTextColor: control.enabled ? theme.textSecondary : theme.disabledPlaceholderText

    background: Rectangle {
        radius: theme.radiusMedium
        color: control.enabled ? theme.surfaceRaised : theme.disabledContainer
        border.width: control.enabled && control.activeFocus ? 2 : 1
        border.color: !control.enabled
            ? theme.disabledOutline
            : (control.invalid ? theme.danger : (control.activeFocus ? theme.primary : theme.outlineVariant))
    }
}
