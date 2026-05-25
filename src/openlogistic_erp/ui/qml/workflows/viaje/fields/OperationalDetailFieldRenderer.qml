pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../../../shared/forms"

FormFieldRenderer {
    id: root

    property int columnSpan: 1

    Layout.fillWidth: true
    Layout.minimumWidth: 0
    Layout.preferredWidth: 1
    Layout.columnSpan: root.columnSpan
    readOnly: true
}
