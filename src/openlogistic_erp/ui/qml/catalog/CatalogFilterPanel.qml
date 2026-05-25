pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../shared/controls"
import "../shared/surfaces"
import "../shared/theme"

AutoHeightSurfaceCard {
    id: panel

    property var screenViewModel: null
    property string searchText: ""
    property var globalFiltersModel: []
    property string filterEditorField: ""
    property string filterEditorOperator: ""
    property string filterEditorValue: ""
    property string filterEditorValueTo: ""
    property string referenceSearchText: ""
    property var filterEditorSelections: []
    property var referenceLookupOptions: []
    property string periodEditorMode: "all"
    property string periodEditorMonth: ""

    signal searchTextEdited(string text)
    signal searchRequested(string text)
    signal searchCleared()
    signal globalFilterEditRequested(string key)
    signal globalFilterResetRequested(string key)
    signal periodFilterApplied(string mode, string month)

    tone: "raised"
    padding: theme.spacing4
    heightSource: controlsLayout

    Theme {
        id: theme
    }

    function filterFieldsModel() {
        return panel.screenViewModel ? panel.screenViewModel.available_filter_fields : []
    }

    function activeFiltersModel() {
        return panel.screenViewModel ? panel.screenViewModel.active_filters : []
    }

    function hasActiveFilters() {
        return panel.activeFiltersModel().length > 0 || panel.globalFiltersModel.length > 0
    }

    function filterCountText() {
        const count = panel.activeFiltersModel().length + panel.globalFiltersModel.length
        if (count <= 0) {
            return qsTr("Filtros")
        }
        return qsTr("Filtros (%1)").arg(count)
    }

    function filterFieldMeta(fieldName) {
        const fields = panel.filterFieldsModel()
        for (let index = 0; index < fields.length; ++index) {
            if (fields[index].name === fieldName) {
                return fields[index]
            }
        }
        return null
    }

    function selectedFilterFieldMeta() {
        return panel.filterFieldMeta(panel.filterEditorField)
    }

    function openFiltersPopup() {
        filterStack.clear()
        filterStack.push(filterListPage)
        filtersPopup.open()
    }

    function openFilterEditor(filterState) {
        const fields = panel.filterFieldsModel()
        if (!fields.length) {
            return
        }

        const currentField = filterState && filterState.field ? filterState.field : fields[0].name
        const meta = panel.filterFieldMeta(currentField) || fields[0]
        panel.filterEditorField = meta.name
        panel.filterEditorOperator = filterState && filterState.operator
            ? filterState.operator
            : (meta.operators.length ? meta.operators[0].value : "eq")
        panel.filterEditorValue = ""
        panel.filterEditorValueTo = ""
        panel.filterEditorSelections = []
        panel.referenceSearchText = ""
        panel.referenceLookupOptions = []

        if (filterState) {
            if (filterState.value instanceof Array) {
                panel.filterEditorSelections = filterState.value.slice()
            } else if (filterState.value !== undefined && filterState.value !== null && filterState.value !== "") {
                if (meta.kind === "reference") {
                    if (typeof filterState.value === "object" || !isNaN(Number(filterState.value))) {
                        panel.filterEditorSelections = [filterState.value]
                    } else {
                        panel.referenceSearchText = String(filterState.value)
                    }
                } else if (meta.multiValue) {
                    panel.filterEditorSelections = [filterState.value]
                } else {
                    panel.filterEditorValue = String(filterState.value)
                }
            }
            if (filterState.valueTo !== undefined && filterState.valueTo !== null) {
                panel.filterEditorValueTo = String(filterState.valueTo)
            }
        }

        if (meta.kind === "bool" && !filterState) {
            panel.filterEditorValue = ""
        }
        panel.loadReferenceOptions()
        filterStack.push(filterEditorPage)
    }

    function openGlobalEditor(filterState) {
        if (!filterState) {
            return
        }
        if (filterState.key === "period") {
            panel.periodEditorMode = filterState.value || "all"
            panel.periodEditorMonth = filterState.month || ""
            filterStack.push(periodEditorPage)
            return
        }
        panel.globalFilterEditRequested(filterState.key)
    }

    function applyFieldDefaults() {
        const meta = panel.selectedFilterFieldMeta()
        if (!meta) {
            return
        }
        panel.filterEditorOperator = meta.operators.length ? meta.operators[0].value : "eq"
        panel.filterEditorValue = ""
        panel.filterEditorValueTo = ""
        panel.filterEditorSelections = []
        panel.referenceSearchText = ""
        panel.referenceLookupOptions = []
        panel.loadReferenceOptions()
    }

    function toggleSelection(optionValue, optionLabel) {
        const next = []
        let removed = false
        for (let index = 0; index < panel.filterEditorSelections.length; ++index) {
            const entry = panel.filterEditorSelections[index]
            const entryValue = typeof entry === "object" ? entry.id ?? entry.value : entry
            if (entryValue === optionValue) {
                removed = true
                continue
            }
            next.push(entry)
        }
        if (!removed) {
            next.push({"id": optionValue, "label": optionLabel, "value": optionValue})
        }
        panel.filterEditorSelections = next
    }

    function selectionContains(optionValue) {
        for (let index = 0; index < panel.filterEditorSelections.length; ++index) {
            const entry = panel.filterEditorSelections[index]
            const entryValue = typeof entry === "object" ? entry.id ?? entry.value : entry
            if (entryValue === optionValue) {
                return true
            }
        }
        return false
    }

    function referenceSelectionPayload() {
        if (panel.filterEditorSelections.length) {
            return panel.filterEditorSelections
        }
        return panel.referenceSearchText
    }

    function buildFilterPayload() {
        const meta = panel.selectedFilterFieldMeta()
        if (!meta) {
            return null
        }
        const payload = {
            "field": meta.name,
            "operator": panel.filterEditorOperator
        }

        if (meta.kind === "reference") {
            payload.value = panel.referenceSelectionPayload()
            return payload
        }
        if (meta.kind === "enum") {
            payload.value = panel.filterEditorSelections.map(function(entry) {
                return typeof entry === "object" ? (entry.value ?? entry.id) : entry
            })
            return payload
        }
        if (meta.kind === "bool") {
            payload.value = panel.filterEditorValue === "" ? null : panel.filterEditorValue === "true"
            return payload
        }
        payload.value = panel.filterEditorValue
        if (panel.filterEditorOperator === "between") {
            payload.valueTo = panel.filterEditorValueTo
        }
        return payload
    }

    function applyFilterEditor() {
        if (!panel.screenViewModel) {
            return
        }
        const payload = panel.buildFilterPayload()
        if (!payload) {
            return
        }
        if (panel.screenViewModel.apply_filter_payload(payload)) {
            filterStack.pop()
        }
    }

    function removeFilter(fieldName) {
        if (panel.screenViewModel) {
            panel.screenViewModel.remove_filter(fieldName)
        }
    }

    function resetGlobalFilter(key) {
        if (key === "period") {
            panel.periodFilterApplied("all", panel.periodEditorMonth)
            return
        }
        panel.globalFilterResetRequested(key)
    }

    function loadReferenceOptions() {
        const meta = panel.selectedFilterFieldMeta()
        if (!meta || meta.kind !== "reference" || !panel.screenViewModel) {
            panel.referenceLookupOptions = []
            return
        }
        panel.referenceLookupOptions = panel.screenViewModel.reference_options(meta.name, panel.referenceSearchText)
    }

    function modelIndexByKey(model, key, value) {
        for (let index = 0; index < model.length; ++index) {
            if (model[index][key] === value) {
                return index
            }
        }
        return 0
    }

    RowLayout {
        id: controlsLayout

        anchors.fill: parent
        spacing: theme.spacing3

        AppTextField {
            Layout.fillWidth: true
            placeholderText: panel.screenViewModel ? panel.screenViewModel.search_placeholder : ""
            text: panel.searchText
            onTextEdited: panel.searchTextEdited(text)
            onAccepted: panel.searchRequested(text)
        }

        AppComboBox {
            id: sortSelector

            objectName: "catalogSortSelector"
            Layout.preferredWidth: 190
            Layout.minimumWidth: 160
            model: panel.screenViewModel ? panel.screenViewModel.sort_options : []
            textRole: "label"
            currentIndex: panel.modelIndexByKey(
                panel.screenViewModel ? panel.screenViewModel.sort_options : [],
                "label",
                panel.screenViewModel ? panel.screenViewModel.sort_label : ""
            )
            enabled: panel.screenViewModel && !panel.screenViewModel.is_busy
            contentItem: Text {
                leftPadding: theme.spacing4
                rightPadding: theme.spacing8
                text: panel.screenViewModel ? panel.screenViewModel.sort_label : ""
                font: sortSelector.font
                color: sortSelector.enabled ? theme.textPrimary : theme.disabledText
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
            onActivated: function(index) {
                if (!panel.screenViewModel) {
                    return
                }
                const option = panel.screenViewModel.sort_options[index]
                if (option) {
                    panel.screenViewModel.apply_sort_payload(option)
                }
            }
        }

        AppButton {
            id: filtersButton
            iconSource: "qrc:/actions/control/filter"
            variant: panel.hasActiveFilters() ? "secondary" : "ghost"
            text: panel.filterCountText()
            onClicked: panel.openFiltersPopup()
        }

        AppButton {
            variant: "secondary"
            iconSource: "qrc:/actions/control/search"
            text: qsTr("Buscar")
            onClicked: panel.searchRequested(panel.searchText)
        }

        AppButton {
            variant: "ghost"
            iconSource: "qrc:/actions/control/clear_all"
            text: qsTr("Limpiar")
            onClicked: panel.searchCleared()
        }
    }

    Popup {
        id: filtersPopup

        x: Math.max(
            theme.spacing2,
            Math.min(filtersButton.x + filtersButton.width - width, panel.width - width - theme.spacing2)
        )
        y: filtersButton.y + filtersButton.height + theme.spacing2
        width: Math.min(panel.width - theme.spacing6, 560)
        height: Math.min(620, panel.Window.window ? panel.Window.window.height - 120 : 620)
        modal: false
        focus: true
        padding: theme.spacing5
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent

        background: Rectangle {
            radius: theme.radiusLarge
            color: theme.surfaceRaised
            border.width: 1
            border.color: theme.alpha(theme.outlineVariant, 0.5)
        }

        contentItem: StackView {
            id: filterStack

            implicitWidth: 520
            implicitHeight: 520
            initialItem: filterListPage
            pushEnter: Transition {}
            pushExit: Transition {}
            popEnter: Transition {}
            popExit: Transition {}
        }
    }

    Component {
        id: filterListPage

        ColumnLayout {
            spacing: theme.spacing4

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing3

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Filtros")
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.sectionTitleSize
                    font.bold: true
                }

                AppButton {
                    compact: true
                    variant: "secondary"
                    text: "+"
                    enabled: panel.filterFieldsModel().length > 0
                    onClicked: panel.openFilterEditor(null)
                }
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                Column {
                    width: parent.width
                    spacing: theme.spacing2

                    Label {
                        width: parent.width
                        visible: !panel.hasActiveFilters()
                        text: qsTr("No hay filtros activos.")
                        color: theme.textSecondary
                        font.family: theme.bodyFontFamily
                        font.pixelSize: theme.bodySize
                    }

                    Repeater {
                        model: panel.globalFiltersModel

                        Rectangle {
                            id: globalFilterItem

                            required property var modelData

                            width: parent.width
                            height: globalFilterRow.implicitHeight + theme.spacing3
                            radius: theme.radiusMedium
                            color: theme.surfaceLow
                            border.width: 1
                            border.color: theme.alpha(theme.outlineVariant, 0.45)

                            RowLayout {
                                id: globalFilterRow

                                anchors.fill: parent
                                anchors.margins: theme.spacing2
                                spacing: theme.spacing3

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0

                                    Label {
                                        Layout.fillWidth: true
                                        text: globalFilterItem.modelData.label
                                        color: theme.textPrimary
                                        font.family: theme.bodyFontFamily
                                        font.pixelSize: theme.bodySize
                                        font.bold: true
                                        elide: Text.ElideRight
                                    }

                                    Label {
                                        Layout.fillWidth: true
                                        text: globalFilterItem.modelData.displayValue
                                        color: theme.textSecondary
                                        font.family: theme.bodyFontFamily
                                        font.pixelSize: theme.captionSize
                                        elide: Text.ElideRight
                                    }
                                }

                                AppIconButton {
                                    buttonSize: theme.controlHeightCompact
                                    iconSize: 16
                                    source: "qrc:/actions/control/filter"
                                    tooltipText: qsTr("Editar filtro")
                                    tintColor: theme.textPrimary
                                    onClicked: panel.openGlobalEditor(globalFilterItem.modelData)
                                }

                                AppIconButton {
                                    buttonSize: theme.controlHeightCompact
                                    iconSize: 16
                                    source: "qrc:/actions/control/close"
                                    tooltipText: qsTr("Restablecer filtro")
                                    tintColor: theme.textPrimary
                                    enabled: globalFilterItem.modelData.resettable === undefined || globalFilterItem.modelData.resettable
                                    onClicked: panel.resetGlobalFilter(globalFilterItem.modelData.key)
                                }
                            }
                        }
                    }

                    Repeater {
                        model: panel.activeFiltersModel()

                        Rectangle {
                            id: tableFilterItem

                            required property var modelData

                            width: parent.width
                            height: tableFilterRow.implicitHeight + theme.spacing3
                            radius: theme.radiusMedium
                            color: theme.surfaceLow
                            border.width: 1
                            border.color: theme.alpha(theme.outlineVariant, 0.45)

                            RowLayout {
                                id: tableFilterRow

                                anchors.fill: parent
                                anchors.margins: theme.spacing2
                                spacing: theme.spacing3

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0

                                    Label {
                                        Layout.fillWidth: true
                                        text: tableFilterItem.modelData.label
                                        color: theme.textPrimary
                                        font.family: theme.bodyFontFamily
                                        font.pixelSize: theme.bodySize
                                        font.bold: true
                                        elide: Text.ElideRight
                                    }

                                    Label {
                                        Layout.fillWidth: true
                                        text: tableFilterItem.modelData.operatorLabel + ": " + tableFilterItem.modelData.displayValue
                                        color: theme.textSecondary
                                        font.family: theme.bodyFontFamily
                                        font.pixelSize: theme.captionSize
                                        elide: Text.ElideRight
                                    }
                                }

                                AppIconButton {
                                    buttonSize: theme.controlHeightCompact
                                    iconSize: 16
                                    source: "qrc:/actions/control/filter"
                                    tooltipText: qsTr("Editar filtro")
                                    tintColor: theme.textPrimary
                                    onClicked: panel.openFilterEditor(tableFilterItem.modelData)
                                }

                                AppIconButton {
                                    buttonSize: theme.controlHeightCompact
                                    iconSize: 16
                                    source: "qrc:/actions/control/close"
                                    tooltipText: qsTr("Quitar filtro")
                                    tintColor: theme.textPrimary
                                    onClicked: panel.removeFilter(tableFilterItem.modelData.field)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: periodEditorPage

        ColumnLayout {
            spacing: theme.spacing4

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing3

                AppButton {
                    compact: true
                    variant: "ghost"
                    text: "<"
                    onClicked: filterStack.pop()
                }

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Periodo")
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.sectionTitleSize
                    font.bold: true
                }
            }

            AppComboBox {
                Layout.fillWidth: true
                textRole: "label"
                valueRole: "value"
                model: [
                    {"label": qsTr("Historico"), "value": "all"},
                    {"label": qsTr("Ultima semana"), "value": "last_week"},
                    {"label": qsTr("Ultimo mes"), "value": "last_month"},
                    {"label": qsTr("Seleccionar mes"), "value": "selected_month"}
                ]
                currentIndex: panel.modelIndexByKey(model, "value", panel.periodEditorMode)
                onActivated: function(index) {
                    const option = model[index]
                    panel.periodEditorMode = option ? option.value : "all"
                }
            }

            AppTextField {
                Layout.fillWidth: true
                visible: panel.periodEditorMode === "selected_month"
                placeholderText: qsTr("AAAA-MM")
                text: panel.periodEditorMonth
                inputMask: "9999-99"
                horizontalAlignment: Text.AlignHCenter
                onTextEdited: panel.periodEditorMonth = text
            }

            Item {
                Layout.fillHeight: true
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: theme.spacing3

                AppButton {
                    variant: "ghost"
                    text: qsTr("Cancelar")
                    onClicked: filterStack.pop()
                }

                AppButton {
                    variant: "secondary"
                    text: qsTr("Guardar")
                    onClicked: {
                        panel.periodFilterApplied(panel.periodEditorMode, panel.periodEditorMonth)
                        filterStack.pop()
                    }
                }
            }
        }
    }

    Component {
        id: filterEditorPage

        ColumnLayout {
            spacing: theme.spacing4

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing3

                AppButton {
                    compact: true
                    variant: "ghost"
                    text: "<"
                    onClicked: filterStack.pop()
                }

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Configurar filtro")
                    color: theme.textPrimary
                    font.family: theme.headlineFontFamily
                    font.pixelSize: theme.sectionTitleSize
                    font.bold: true
                }
            }

            AppComboBox {
                Layout.fillWidth: true
                model: panel.filterFieldsModel()
                textRole: "label"
                valueRole: "name"
                currentIndex: panel.modelIndexByKey(panel.filterFieldsModel(), "name", panel.filterEditorField)
                onActivated: function(index) {
                    const field = panel.filterFieldsModel()[index]
                    if (!field) {
                        return
                    }
                    panel.filterEditorField = field.name
                    panel.applyFieldDefaults()
                }
            }

            AppComboBox {
                Layout.fillWidth: true
                model: panel.selectedFilterFieldMeta() ? panel.selectedFilterFieldMeta().operators : []
                textRole: "label"
                valueRole: "value"
                currentIndex: panel.modelIndexByKey(
                    panel.selectedFilterFieldMeta() ? panel.selectedFilterFieldMeta().operators : [],
                    "value",
                    panel.filterEditorOperator
                )
                onActivated: function(index) {
                    const option = (panel.selectedFilterFieldMeta() ? panel.selectedFilterFieldMeta().operators : [])[index]
                    if (option) {
                        panel.filterEditorOperator = option.value
                    }
                }
            }

            AppComboBox {
                Layout.fillWidth: true
                visible: panel.selectedFilterFieldMeta() && panel.selectedFilterFieldMeta().kind === "bool"
                model: [
                    {"label": qsTr("Todos"), "value": ""},
                    {"label": qsTr("Si"), "value": "true"},
                    {"label": qsTr("No"), "value": "false"}
                ]
                textRole: "label"
                valueRole: "value"
                currentIndex: panel.modelIndexByKey(model, "value", panel.filterEditorValue)
                onActivated: function(index) {
                    const option = model[index]
                    panel.filterEditorValue = option ? option.value : ""
                }
            }

            AppTextField {
                Layout.fillWidth: true
                visible: panel.selectedFilterFieldMeta()
                    && panel.selectedFilterFieldMeta().kind !== "enum"
                    && panel.selectedFilterFieldMeta().kind !== "reference"
                    && panel.selectedFilterFieldMeta().kind !== "bool"
                placeholderText: qsTr("Valor")
                text: panel.filterEditorValue
                onTextEdited: panel.filterEditorValue = text
            }

            AppTextField {
                Layout.fillWidth: true
                visible: panel.selectedFilterFieldMeta()
                    && panel.selectedFilterFieldMeta().kind !== "enum"
                    && panel.selectedFilterFieldMeta().kind !== "reference"
                    && panel.selectedFilterFieldMeta().kind !== "bool"
                    && panel.filterEditorOperator === "between"
                placeholderText: qsTr("Valor final")
                text: panel.filterEditorValueTo
                onTextEdited: panel.filterEditorValueTo = text
            }

            ColumnLayout {
                Layout.fillWidth: true
                visible: panel.selectedFilterFieldMeta() && panel.selectedFilterFieldMeta().kind === "enum"
                spacing: theme.spacing2

                Label {
                    text: qsTr("Selecciona uno o varios valores")
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    Column {
                        width: parent.width
                        spacing: theme.spacing2

                        CheckBox {
                            text: qsTr("Todos")
                            checked: panel.filterEditorSelections.length === 0
                            onToggled: {
                                if (checked) {
                                    panel.filterEditorSelections = []
                                }
                            }
                        }

                        Repeater {
                            model: panel.selectedFilterFieldMeta() ? panel.selectedFilterFieldMeta().options : []

                            CheckBox {
                                required property var modelData

                                text: modelData.label
                                checked: panel.selectionContains(modelData.value)
                                onToggled: panel.toggleSelection(modelData.value, modelData.label)
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                visible: panel.selectedFilterFieldMeta() && panel.selectedFilterFieldMeta().kind === "reference"
                spacing: theme.spacing2

                RowLayout {
                    Layout.fillWidth: true
                    spacing: theme.spacing2

                    AppTextField {
                        Layout.fillWidth: true
                        placeholderText: qsTr("Buscar referencia")
                        text: panel.referenceSearchText
                        onTextEdited: {
                            panel.referenceSearchText = text
                            panel.loadReferenceOptions()
                        }
                    }

                    AppButton {
                        compact: true
                        variant: "secondary"
                        text: qsTr("Buscar")
                        onClicked: panel.loadReferenceOptions()
                    }
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 180
                    clip: true

                    Column {
                        width: parent.width
                        spacing: theme.spacing2

                        Repeater {
                            model: panel.referenceLookupOptions

                            CheckBox {
                                required property var modelData

                                text: modelData.label
                                checked: panel.selectionContains(modelData.id)
                                onToggled: panel.toggleSelection(modelData.id, modelData.label)
                            }
                        }
                    }
                }

                Label {
                    visible: panel.referenceLookupOptions.length === 0 && panel.referenceSearchText.length > 0
                    text: qsTr("No hay coincidencias.")
                    color: theme.textSecondary
                    font.family: theme.bodyFontFamily
                    font.pixelSize: theme.captionSize
                }
            }

            Item {
                Layout.fillHeight: true
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: theme.spacing3

                AppButton {
                    variant: "ghost"
                    text: qsTr("Cancelar")
                    onClicked: filterStack.pop()
                }

                AppButton {
                    variant: "secondary"
                    text: qsTr("Guardar")
                    onClicked: panel.applyFilterEditor()
                }
            }
        }
    }
}
