pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../theme"

ComboBox {
    id: control

    property bool invalid: false
    property bool textEditedSinceFocus: false
    property string userEditText: ""
    signal userTextEdited(string text)

    editable: true
    implicitHeight: theme.controlHeightLarge
    leftPadding: theme.spacing4
    rightPadding: theme.spacing8
    font.family: theme.bodyFontFamily
    font.pixelSize: theme.bodySize

    Theme {
        id: theme
    }

    function optionAt(index) {
        if (index < 0 || index >= control.count) {
            return null
        }
        return control.model[index]
    }

    function optionLabel(option) {
        if (typeof option === "object" && option !== null) {
            const roleName = control.textRole || "text"
            if (option[roleName] !== undefined) {
                return String(option[roleName])
            }
        }
        return String(option)
    }

    function exactTextIndex() {
        const needle = String(control.editText || "").trim().toLocaleLowerCase()
        if (needle === "") {
            return -1
        }

        let foundIndex = -1
        for (let index = 0; index < control.count; ++index) {
            const option = control.optionAt(index)
            const label = control.optionLabel(option).trim().toLocaleLowerCase()
            if (label !== needle) {
                continue
            }
            if (foundIndex !== -1) {
                return -1
            }
            foundIndex = index
        }
        return foundIndex
    }

    function commitVisibleOption() {
        let index = control.highlightedIndex
        if (index < 0 || index >= control.count) {
            index = control.exactTextIndex()
        }
        if (index < 0 || index >= control.count) {
            return false
        }

        control.currentIndex = index
        control.textEditedSinceFocus = false
        control.userEditText = ""
        control.activated(index)
        control.popup.close()
        return true
    }

    function commitEditedText() {
        if (!control.textEditedSinceFocus) {
            return false
        }
        control.textEditedSinceFocus = false
        return control.commitVisibleOption()
    }

    function restoreUserEditText() {
        if (!control.textEditedSinceFocus) {
            return
        }
        control.currentIndex = -1
        control.editText = control.userEditText
    }

    function beginUserEdit(text) {
        control.userEditText = String(text)
        control.textEditedSinceFocus = true
        control.restoreUserEditText()
        control.userTextEdited(control.userEditText)
        return true
    }

    function handleTabPressed() {
        if (control.commitVisibleOption()) {
            return true
        }
        if (control.textEditedSinceFocus && String(control.editText || "").trim() !== "" && control.count === 1) {
            control.currentIndex = 0
            control.textEditedSinceFocus = false
            control.userEditText = ""
            control.activated(0)
            control.popup.close()
            return true
        }
        return false
    }

    onActiveFocusChanged: {
        if (activeFocus) {
            control.textEditedSinceFocus = false
            control.userEditText = ""
        } else {
            Qt.callLater(control.commitEditedText)
        }
    }

    onModelChanged: {
        if (control.textEditedSinceFocus) {
            control.restoreUserEditText()
        }
    }

    contentItem: TextField {
        leftPadding: theme.spacing4
        rightPadding: theme.spacing8
        topPadding: theme.spacing3
        bottomPadding: theme.spacing3
        text: control.editText
        font: control.font
        color: control.enabled ? theme.textPrimary : theme.disabledText
        enabled: control.enabled
        readOnly: !control.editable
        selectionColor: theme.primaryFixed
        selectedTextColor: theme.primary
        placeholderTextColor: control.enabled ? theme.textSecondary : theme.disabledPlaceholderText
        background: null

        onTextEdited: {
            control.beginUserEdit(text)
        }

        Keys.onReturnPressed: function(event) {
            event.accepted = control.commitVisibleOption()
        }

        Keys.onEnterPressed: function(event) {
            event.accepted = control.commitVisibleOption()
        }

        Keys.onTabPressed: function(event) {
            event.accepted = control.handleTabPressed()
        }
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
            control.textEditedSinceFocus = false
            control.userEditText = ""
            control.activated(index)
            control.popup.close()
        }
    }
}
