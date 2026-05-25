pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQml
import "../controls"
import "../theme"

ColumnLayout {
    id: root

    required property var field
    required property var formViewModel
    property bool readOnly: false
    property var optionsOverride: null
    property var editableOverride: null
    property bool useReferenceSetter: true

    Theme {
        id: theme
    }

    function currentValue() {
        const values = root.formViewModel ? root.formViewModel.values : {}
        const value = values[root.field.name]
        if (value === undefined || value === null) {
            return ""
        }
        return value
    }

    function stringValue() {
        return String(root.currentValue())
    }

    function fieldOptions() {
        let options = []
        if (root.optionsOverride !== null && root.optionsOverride !== undefined) {
            options = root.optionsOverride
        } else {
            options = root.field && root.field.options ? root.field.options : []
        }
        if (root.field && (root.field.kind === "enum" || root.field.kind === "reference")) {
            const firstOption = options.length > 0 ? options[0] : null
            if (!firstOption || firstOption.value !== "") {
                return [{ "value": "", "label": "" }].concat(options)
            }
        }
        return options
    }

    function fieldError() {
        if (!root.formViewModel || !root.field || !root.field.name) {
            return ""
        }
        if (root.formViewModel.field_error) {
            return root.formViewModel.field_error(root.field.name)
        }
        const errors = root.formViewModel.field_errors || {}
        return errors[root.field.name] || ""
    }

    function optionIndex() {
        if (!root.field) {
            return -1
        }
        const options = root.fieldOptions()
        for (let i = 0; i < options.length; ++i) {
            if (options[i].value === root.currentValue()) {
                return i
            }
        }
        return -1
    }

    function editable() {
        const fieldEditable = Boolean(root.field && root.field.editable)
        if (root.editableOverride !== null && root.editableOverride !== undefined) {
            return fieldEditable && Boolean(root.editableOverride) && !root.readOnly
        }
        return fieldEditable && !root.readOnly
    }

    function setReferenceValue(option) {
        if (!option || !root.formViewModel) {
            return
        }
        if (root.useReferenceSetter && root.formViewModel.set_reference_field_value) {
            root.formViewModel.set_reference_field_value(root.field.name, option.value, option.label)
            return
        }
        root.formViewModel.set_field_value(root.field.name, option.value)
    }

    Layout.fillWidth: true
    spacing: theme.spacing2

    Label {
        Layout.fillWidth: true
        text: root.field.label + (root.field.required ? " *" : "")
        color: theme.textSecondary
        font.family: theme.bodyFontFamily
        font.pixelSize: theme.captionSize
        font.bold: true
    }

    Loader {
        Layout.fillWidth: true
        sourceComponent: {
            if (root.field.kind === "bool") {
                return boolField
            }
            if (root.field.kind === "enum") {
                return enumField
            }
            if (root.field.kind === "reference") {
                return referenceField
            }
            if (root.field.kind === "multiline") {
                return multilineField
            }
            if (root.field.kind === "integer") {
                return integerField
            }
            if (root.field.kind === "number" || root.field.kind === "money" || root.field.kind === "percent") {
                return numberField
            }
            if (root.field.kind === "date") {
                return dateField
            }
            if (root.field.kind === "datetime") {
                return dateTimeField
            }
            return textField
        }
    }

    Label {
        Layout.fillWidth: true
        visible: root.fieldError() !== ""
        text: root.fieldError()
        color: theme.danger
        font.family: theme.bodyFontFamily
        font.pixelSize: theme.captionSize
        wrapMode: Text.WordWrap
    }

    Component {
        id: textField

        AppTextField {
            enabled: root.editable()
            invalid: root.fieldError() !== ""
            text: root.stringValue()
            inputMethodHints: Qt.ImhNone
            onTextEdited: root.formViewModel.set_field_value(root.field.name, text)
        }
    }

    Component {
        id: integerField

        AppTextField {
            enabled: root.editable()
            invalid: root.fieldError() !== ""
            text: root.stringValue()
            inputMethodHints: Qt.ImhDigitsOnly
            validator: IntValidator {}
            onTextEdited: root.formViewModel.set_field_value(root.field.name, text)
        }
    }

    Component {
        id: numberField

        AppTextField {
            enabled: root.editable()
            invalid: root.fieldError() !== ""
            text: root.stringValue()
            inputMethodHints: Qt.ImhFormattedNumbersOnly
            validator: DoubleValidator {
                notation: DoubleValidator.StandardNotation
                locale: "C"
                decimals: root.field.precision === null || root.field.precision === undefined ? 8 : root.field.precision
            }
            onTextEdited: root.formViewModel.set_field_value(root.field.name, text)
        }
    }

    Component {
        id: multilineField

        AppTextArea {
            Layout.fillWidth: true
            enabled: root.editable()
            invalid: root.fieldError() !== ""
            text: root.stringValue()
            implicitHeight: 132
            onTextChanged: {
                if (activeFocus) {
                    root.formViewModel.set_field_value(root.field.name, text)
                }
            }
        }
    }

    Component {
        id: enumField

        AppComboBox {
            enabled: root.editable()
            invalid: root.fieldError() !== ""
            model: root.fieldOptions()
            textRole: "label"
            valueRole: "value"
            currentIndex: root.optionIndex()
            onActivated: root.formViewModel.set_field_value(root.field.name, currentValue)
        }
    }

    Component {
        id: dateField

        AppDateField {
            enabled: root.editable()
            invalid: root.fieldError() !== ""
            text: root.stringValue()
            placeholderText: root.field.display_format || qsTr("DD/MM/YYYY")
            onTextEdited: root.formViewModel.set_field_value(root.field.name, text)
        }
    }

    Component {
        id: referenceField

        AppSearchComboBox {
            id: referenceCombo

            enabled: root.editable()
            invalid: root.fieldError() !== ""
            model: root.fieldOptions()
            textRole: "label"
            valueRole: "value"

            Binding {
                target: referenceCombo
                property: "currentIndex"
                when: !referenceCombo.activeFocus
                value: root.optionIndex()
            }

            Component.onCompleted: {
                if (root.formViewModel && root.field && root.field.name) {
                    root.formViewModel.prime_reference_field(root.field.name)
                }
            }

            onActivated: function(index) {
                referenceSearchDebounce.stop()
                root.setReferenceValue(root.fieldOptions()[index])
            }

            onUserTextEdited: {
                if (activeFocus) {
                    referenceSearchDebounce.restart()
                }
            }

            Timer {
                id: referenceSearchDebounce

                interval: 250
                onTriggered: {
                    if (root.formViewModel && root.field && root.field.name) {
                        root.formViewModel.search_reference_options(root.field.name, referenceCombo.editText)
                    }
                }
            }
        }
    }

    Component {
        id: dateTimeField

        AppDateTimeField {
            enabled: root.editable()
            invalid: root.fieldError() !== ""
            text: root.stringValue()
            placeholderText: root.field.display_format || qsTr("DD/MM/YYYY HH:MM")
            onTextEdited: root.formViewModel.set_field_value(root.field.name, text)
        }
    }

    Component {
        id: boolField

        Rectangle {
            implicitHeight: 54
            radius: theme.radiusMedium
            color: theme.surfaceRaised
            border.width: toggle.activeFocus ? 2 : 1
            border.color: root.fieldError() !== "" ? theme.danger : (toggle.activeFocus ? theme.primary : theme.outlineVariant)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: theme.spacing4
                anchors.rightMargin: theme.spacing4
                spacing: theme.spacing3

                Switch {
                    id: toggle

                    enabled: root.editable()
                    checked: Boolean(root.currentValue())
                    onToggled: root.formViewModel.set_field_value(root.field.name, checked)
                }

                Label {
                    Layout.fillWidth: true
                    text: toggle.checked ? qsTr("Si") : qsTr("No")
                    color: theme.textPrimary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.bodySize
                }
            }
        }
    }
}
