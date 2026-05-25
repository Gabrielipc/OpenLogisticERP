pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../shared/controls"
import "../shared/theme"

ColumnLayout {
    id: root

    required property var filterDef
    property var options: []
    property var params: ({})
    signal paramEdited(string key, var value)

    Layout.fillWidth: true
    spacing: theme.spacing2

    Theme {
        id: theme
    }

    function filterKey() {
        return String(root.filterDef.key || "")
    }

    function defaultStringValue() {
        if (root.filterDef.default === undefined || root.filterDef.default === null) {
            return ""
        }
        return String(root.filterDef.default || "")
    }

    function allowsAllOption() {
        return !Boolean(root.filterDef.required)
    }

    function optionModel() {
        const baseOptions = root.options || []
        if (!root.allowsAllOption()) {
            return baseOptions
        }
        return [{ value: "", label: qsTr("Todos") }].concat(baseOptions)
    }

    function isoFromDisplay(text) {
        const normalized = String(text || "").trim()
        const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(normalized)
        if (!match) {
            return normalized
        }
        return `${match[3]}-${match[2]}-${match[1]}`
    }

    function defaultOptionIndex() {
        const defaultValue = root.defaultStringValue()
        if (defaultValue === "") {
            return 0
        }
        const model = root.optionModel()
        for (let i = 0; i < model.length; ++i) {
            if (String(model[i].value || "") === defaultValue) {
                return i
            }
        }
        return 0
    }

    Label {
        Layout.fillWidth: true
        text: String(root.filterDef.label || "")
        color: theme.textSecondary
        font.family: theme.bodyFontFamily
        font.pixelSize: theme.captionSize
        font.bold: true
        elide: Text.ElideRight
    }

    Loader {
        Layout.fillWidth: true
        sourceComponent: {
            const type = String(root.filterDef.type || "")
            if (type === "date") {
                return dateComponent
            }
            if (type === "date_range") {
                return dateRangeComponent
            }
            if (type === "select") {
                return selectComponent
            }
            if (type === "checkbox") {
                return checkboxComponent
            }
            return textComponent
        }
    }

    Component {
        id: dateComponent

        AppDateField {
            Layout.fillWidth: true
            onTextEdited: function(text) {
                root.paramEdited(root.filterKey(), root.isoFromDisplay(text))
            }
        }
    }

    Component {
        id: dateRangeComponent

        RowLayout {
            spacing: theme.spacing3

            AppDateField {
                Layout.fillWidth: true
                placeholderText: qsTr("Desde")
                onTextEdited: function(text) {
                    const key = root.filterKey()
                    const current = root.params[key] || ["", ""]

                    root.paramEdited(
                        key,
                        [root.isoFromDisplay(text), current[1] || ""]
                    )
                }
            }

            AppDateField {
                Layout.fillWidth: true
                placeholderText: qsTr("Hasta")
                onTextEdited: function(text) {
                    const key = root.filterKey()
                    const current = root.params[key] || ["", ""]

                    root.paramEdited(
                        key,
                        [current[0] || "", root.isoFromDisplay(text)]
                    )
                }
            }
        }
    }

    Component {
        id: selectComponent

        AppComboBox {
            id: combo

            Layout.fillWidth: true
            textRole: "label"
            valueRole: "value"
            model: root.optionModel()
            currentIndex: root.defaultOptionIndex()
            onActivated: root.paramEdited(root.filterKey(), currentValue || "")
            Component.onCompleted: {
                const defaultValue = root.defaultStringValue()
                if (defaultValue !== "") {
                    root.paramEdited(root.filterKey(), defaultValue)
                } else if (!root.allowsAllOption() && currentValue !== undefined && currentValue !== null) {
                    root.paramEdited(root.filterKey(), currentValue)
                }
            }
        }
    }

    Component {
        id: checkboxComponent

        CheckBox {
            id: checkbox

            checked: Boolean(root.filterDef.default)
            text: checked ? qsTr("Si") : qsTr("No")
            font.family: theme.bodyFontFamily
            font.pixelSize: theme.bodySize
            onToggled: {
                text = checked ? qsTr("Si") : qsTr("No")
                root.paramEdited(root.filterKey(), checked)
            }
            Component.onCompleted: root.paramEdited(root.filterKey(), checked)
        }
    }

    Component {
        id: textComponent

        AppTextField {
            Layout.fillWidth: true
            onTextEdited: root.paramEdited(root.filterKey(), text)
        }
    }
}
