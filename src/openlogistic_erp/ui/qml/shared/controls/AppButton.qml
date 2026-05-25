pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../theme"

Button {
    id: control

    property string variant: "primary"
    property bool compact: false
    property string iconSource: ""
    readonly property int iconVisualSize: control.compact ? 16 : 18

    Theme {
        id: theme
    }

    implicitHeight: control.compact ? theme.controlHeightCompact : theme.controlHeightDefault
    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    padding: control.compact ? theme.spacing3 : theme.spacing4
    font.family: theme.bodyFontFamily
    font.pixelSize: control.compact ? theme.captionSize : theme.bodySize
    font.bold: true

    contentItem: Item {
        implicitWidth: contentRow.implicitWidth
        implicitHeight: Math.max(contentLabel.implicitHeight, control.iconVisualSize)

        Row {
            id: contentRow

            anchors.centerIn: parent
            spacing: control.text !== "" && control.iconSource !== "" ? theme.spacing2 : 0

            AppIcon {
                width: control.iconVisualSize
                height: control.iconVisualSize
                size: control.iconVisualSize
                anchors.verticalCenter: parent.verticalCenter
                visible: control.iconSource !== ""
                source: control.iconSource
                tintColor: contentLabel.color
            }

            Label {
                id: contentLabel

                visible: control.text !== ""
                text: control.text
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                color: {
                    switch (control.variant) {
                    case "primary":
                        return theme.textOnPrimary
                    case "contrast":
                        return theme.textOnPrimary
                    case "danger":
                        return theme.danger
                    default:
                        return theme.textPrimary
                    }
                }
                font: control.font
            }
        }
    }

    background: Rectangle {
        radius: theme.radiusPill
        border.width: control.variant === "ghost" ? 1 : 0
        border.color: theme.alpha(theme.outlineVariant, 0.6)
        color: {
            switch (control.variant) {
            case "primary":
                return "transparent"
            case "secondary":
                return control.down ? theme.surfaceMid : theme.surfaceHigh
            case "contrast":
                return control.down ? theme.surfaceMid : theme.primary
            case "danger":
                return control.down ? Qt.darker(theme.dangerContainer, 1.05) : theme.dangerContainer
            default:
                return control.hovered ? theme.surfaceMid : "transparent"
            }
        }
        gradient: control.variant === "primary" ? primaryGradient : null
    }

    Gradient {
        id: primaryGradient

        GradientStop { position: 0.0; color: Qt.lighter(theme.primary, control.hovered ? 1.05 : 1.0) }
        GradientStop { position: 1.0; color: Qt.lighter(theme.primaryContainer, control.hovered ? 1.05 : 1.0) }
    }
}
