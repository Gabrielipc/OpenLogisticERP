pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../theme"

ComboBox {
    id: control
    property bool invalid: false

    Theme {
        id: theme
    }

    implicitHeight: theme.controlHeightLarge
    leftPadding: theme.spacing4
    rightPadding: theme.spacing8
    font.family: theme.bodyFontFamily
    font.pixelSize: theme.bodySize

    contentItem: Text {
        leftPadding: theme.spacing4
        rightPadding: theme.spacing8
        text: control.displayText
        font: control.font
        color: control.enabled ? theme.textPrimary : theme.disabledText
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: AppIcon {
        size: 24
        tintColor: control.enabled ? theme.textPrimary : theme.disabledText
        x: control.width - width - theme.spacing4
        y: (control.height - height) / 2
        source: "qrc:/actions/control/drop_down"
    }

    background: Rectangle {
        radius: theme.radiusMedium
        color: control.enabled ? theme.surfaceRaised : theme.disabledContainer
        border.width: control.enabled && control.activeFocus ? 2 : 1
        border.color: !control.enabled
            ? theme.disabledOutline
            : (control.invalid ? theme.danger : (control.activeFocus ? theme.primary : theme.outlineVariant))
    }

    popup: Popup {
        y: control.height + 6
        width: control.width
        padding: 6

        background: Rectangle {
            radius: theme.radiusMedium
            color: theme.surfaceRaised
            border.width: 1
            border.color: theme.alpha(theme.outlineVariant, 0.5)
        }

        contentItem: ListView {
            implicitHeight: Math.min(contentHeight, 240)
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            clip: true
        }
    }

    delegate: ItemDelegate {
        required property var model
        required property int index

        width: control.width - 12
        highlighted: control.highlightedIndex === index
        text: {
            if (typeof model === "object" && model !== null) {
                const roleName = control.textRole || "text"
                if (model[roleName] !== undefined) {
                    return String(model[roleName])
                }
            }
            return String(model)
        }
        onClicked: {
            control.currentIndex = index
            control.activated(index)
            control.popup.close()
        }
    }
}
