pragma ComponentBehavior: Bound

import QtQuick

BaseConfirmDialog {
    id: dialog

    property string confirmText: qsTr("Eliminar")
    property string cancelText: qsTr("Cancelar")
    property bool confirmEnabled: true
    property string confirmVariant: "danger"
    property string cancelVariant: "ghost"
    property bool showCancelButton: true
    property bool showConfirmButton: true

    title: qsTr("Confirmar eliminacion")
    message: qsTr("Deseas eliminar este registro? Esta accion no se puede deshacer.")
    buttons: [
        {
            role: "cancel",
            text: dialog.cancelText,
            variant: dialog.cancelVariant,
            visible: dialog.showCancelButton
        },
        {
            role: "confirm",
            text: dialog.confirmText,
            variant: dialog.confirmVariant,
            visible: dialog.showConfirmButton,
            enabled: dialog.confirmEnabled
        }
    ]

    signal confirmRequested()
    signal cancelRequested()

    onDismissed: dialog.cancelRequested()
    onActionRequested: function(role) {
        if (role === "confirm") {
            dialog.confirmRequested()
            return
        }
        dialog.cancelRequested()
    }
}
