from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression

from openlogistic_erp.presentation.qt import QCoreApplication, QObject, QUrl


ROOT = Path(__file__).resolve().parents[2]
CONTROLS_DIR = (ROOT / "src" / "openlogistic_erp" / "ui" / "qml" / "shared" / "controls").as_uri()
FORMS_DIR = (ROOT / "src" / "openlogistic_erp" / "ui" / "qml" / "shared" / "forms").as_uri()


@dataclass
class _ComboHarness:
    engine: QQmlEngine
    component: QQmlComponent
    root: QObject
    combo: QObject

    def dispose(self) -> None:
        self.root.deleteLater()
        self.engine.collectGarbage()
        self.engine.deleteLater()
        for _ in range(5):
            QCoreApplication.sendPostedEvents(None, 0)
            QCoreApplication.processEvents()


_COMBO_HARNESSES: list[_ComboHarness] = []


@pytest.fixture(autouse=True)
def cleanup_combo_harnesses():
    yield
    while _COMBO_HARNESSES:
        _COMBO_HARNESSES.pop().dispose()


def _create_combo(model: str, control_type: str = "AppSearchComboBox") -> _ComboHarness:
    qml = f"""
import QtQuick
import QtQuick.Controls
import "{CONTROLS_DIR}" as Controls

Item {{
    width: 300
    height: 100

    Controls.{control_type} {{
        id: combo
        objectName: "combo"
        model: {model}
        textRole: "label"
        valueRole: "value"
        property int activatedIndex: -99
        onActivated: function(index) {{ activatedIndex = index }}
    }}
}}
"""
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(qml.encode("utf-8"), QUrl())
    root = component.create()
    assert root is not None, "\n".join(error.toString() for error in component.errors())
    root._engine = engine  # keep the QML engine alive for the object lifetime
    combo = root.findChild(QObject, "combo")
    assert combo is not None
    harness = _ComboHarness(engine=engine, component=component, root=root, combo=combo)
    _COMBO_HARNESSES.append(harness)
    return harness


def _dispose_qml_root(engine: QQmlEngine, root: QObject) -> None:
    root.deleteLater()
    engine.collectGarbage()
    engine.deleteLater()
    for _ in range(5):
        QCoreApplication.sendPostedEvents(None, 0)
        QCoreApplication.processEvents()


def _evaluate(combo: QObject, expression: str):
    result, is_undefined = QQmlExpression(QQmlEngine.contextForObject(combo), combo, expression).evaluate()
    assert not is_undefined
    return result


def test_app_search_combo_commits_exact_label_match(qapp):
    del qapp
    harness = _create_combo('[{"value": 1, "label": "Alpha"}, {"value": 2, "label": "Beta"}]')
    combo = harness.combo
    combo.setProperty("currentIndex", -1)
    combo.setProperty("editText", " beta ")
    combo.setProperty("textEditedSinceFocus", True)

    assert _evaluate(combo, "commitEditedText()") is True

    assert combo.property("currentIndex") == 1
    assert combo.property("activatedIndex") == 1


def test_app_search_combo_does_not_commit_on_focus_loss_without_text_edit(qapp):
    del qapp
    harness = _create_combo('[{"value": 1, "label": "Alpha"}, {"value": 2, "label": "Beta"}]')
    combo = harness.combo
    combo.setProperty("currentIndex", 0)

    assert _evaluate(combo, "commitEditedText()") is False

    assert combo.property("currentIndex") == 0
    assert combo.property("activatedIndex") == -99


def test_app_search_combo_does_not_commit_partial_or_ambiguous_text(qapp):
    del qapp
    partial_harness = _create_combo('[{"value": 1, "label": "Alpha"}, {"value": 2, "label": "Beta"}]')
    partial_combo = partial_harness.combo
    partial_combo.setProperty("currentIndex", -1)
    partial_combo.setProperty("editText", "bet")

    assert _evaluate(partial_combo, "commitVisibleOption()") is False
    assert partial_combo.property("currentIndex") == -1
    assert partial_combo.property("activatedIndex") == -99

    duplicate_harness = _create_combo('[{"value": 1, "label": "Alpha"}, {"value": 2, "label": "alpha"}]')
    duplicate_combo = duplicate_harness.combo
    duplicate_combo.setProperty("currentIndex", -1)
    duplicate_combo.setProperty("editText", "Alpha")

    assert _evaluate(duplicate_combo, "commitVisibleOption()") is False
    assert duplicate_combo.property("currentIndex") == -1
    assert duplicate_combo.property("activatedIndex") == -99


def test_app_search_combo_tab_commits_single_visible_match(qapp):
    del qapp
    harness = _create_combo('[{"value": 2, "label": "Beta"}]')
    combo = harness.combo
    combo.setProperty("currentIndex", -1)
    combo.setProperty("editText", "Be")
    combo.setProperty("textEditedSinceFocus", True)

    assert _evaluate(combo, "handleTabPressed()") is True

    assert combo.property("currentIndex") == 0
    assert combo.property("currentValue") == 2
    assert combo.property("activatedIndex") == 0


def test_app_search_combo_keeps_user_text_when_model_refreshes_while_editing(qapp):
    del qapp
    harness = _create_combo('[{"value": 1, "label": "Alpha"}]')
    combo = harness.combo

    _evaluate(combo, 'beginUserEdit("Be")')
    combo.setProperty("model", [{"value": 2, "label": "Beta"}])

    assert combo.property("editText") == "Be"
    assert combo.property("currentIndex") == -1


def test_app_search_combo_keeps_qt_first_option_default(qapp):
    del qapp
    harness = _create_combo('[{"value": 1, "label": "Alpha"}]')

    assert harness.combo.property("currentIndex") == 0
    assert harness.combo.property("currentValue") == 1


def test_app_combo_keeps_qt_first_option_default(qapp):
    del qapp
    harness = _create_combo('[{"value": "USD", "label": "USD"}]', "AppComboBox")

    assert harness.combo.property("currentIndex") == 0
    assert harness.combo.property("currentValue") == "USD"


def test_form_field_renderer_prepends_empty_option_for_combos(qapp):
    del qapp
    qml = f"""
import QtQuick
import QtQuick.Controls
import "{FORMS_DIR}" as Forms

Item {{
    width: 300
    height: 100

    Forms.FormFieldRenderer {{
        id: renderer
        objectName: "renderer"
        field: {{
            "name": "thermo_id",
            "label": "Thermo",
            "kind": "reference",
            "required": true,
            "editable": true
        }}
        formViewModel: {{
            "values": {{"thermo_id": ""}},
            "field_error": function(fieldName) {{ return "" }},
            "prime_reference_field": function(fieldName) {{}},
            "search_reference_options": function(fieldName, term) {{}},
            "set_field_value": function(fieldName, value) {{}}
        }}
        optionsOverride: [{{"value": 1, "label": "Thermo Demo"}}]
    }}
}}
"""
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(qml.encode("utf-8"), QUrl())
    root = component.create()
    assert root is not None, "\n".join(error.toString() for error in component.errors())
    root._engine = engine
    try:
        renderer = root.findChild(QObject, "renderer")
        assert renderer is not None

        option_count = _evaluate(renderer, "fieldOptions().length")
        first_value = _evaluate(renderer, "fieldOptions()[0].value")
        second_value = _evaluate(renderer, "fieldOptions()[1].value")
        selected_index = _evaluate(renderer, "optionIndex()")

        assert option_count == 2
        assert first_value == ""
        assert second_value == 1
        assert selected_index == 0
    finally:
        _dispose_qml_root(engine, root)
