pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../shared/theme"

ColumnLayout {
    id: root

    required property var moduleViewModel
    property var filters: []
    property var params: ({})

    spacing: theme.spacing4

    Theme {
        id: theme
    }

    function updateParam(key, value) {
        const next = Object.assign({}, root.params)
        next[key] = value
        root.params = next
    }

    Repeater {
        model: root.filters

        delegate: ReportFilterField {
            required property var modelData

            Layout.fillWidth: true
            filterDef: modelData || ({})
            params: root.params
            onParamEdited: function(key, value) {
                root.updateParam(key, value)
            }
            options: modelData && modelData.options ? modelData.options : []
        }
    }
}
