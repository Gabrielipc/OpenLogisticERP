from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression

from openlogistic_erp.presentation.qt import QCoreApplication, QObject, QUrl


ROOT = Path(__file__).resolve().parents[2]
CONTROLS_DIR = (ROOT / "src" / "openlogistic_erp" / "ui" / "qml" / "shared" / "controls").as_uri()


@dataclass
class _DateHarness:
    engine: QQmlEngine
    component: QQmlComponent
    root: QObject
    field: QObject

    def dispose(self) -> None:
        self.root.deleteLater()
        self.engine.collectGarbage()
        self.engine.deleteLater()
        for _ in range(5):
            QCoreApplication.sendPostedEvents(None, 0)
            QCoreApplication.processEvents()


_DATE_HARNESSES: list[_DateHarness] = []


@pytest.fixture(autouse=True)
def cleanup_date_harnesses():
    yield
    while _DATE_HARNESSES:
        _DATE_HARNESSES.pop().dispose()


def _create_date_field(control_type: str) -> _DateHarness:
    qml = f"""
import QtQuick
import "{CONTROLS_DIR}" as Controls

Item {{
    width: 360
    height: 120

    function selectUtcCalendarDate() {{
        field.selectCalendarDate(new Date(Date.UTC(2026, 4, 2)))
    }}

    Controls.{control_type} {{
        id: field
        objectName: "field"
    }}
}}
"""
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(qml.encode("utf-8"), QUrl())
    root = component.create()
    assert root is not None, "\n".join(error.toString() for error in component.errors())
    root._engine = engine
    field = root.findChild(QObject, "field")
    assert field is not None
    harness = _DateHarness(engine=engine, component=component, root=root, field=field)
    _DATE_HARNESSES.append(harness)
    return harness


def _evaluate(target: QObject, expression: str):
    result, is_undefined = QQmlExpression(QQmlEngine.contextForObject(target), target, expression).evaluate()
    assert not is_undefined
    return result


def test_app_date_field_reads_month_grid_dates_without_timezone_shift(qapp):
    del qapp
    harness = _create_date_field("AppDateField")

    _evaluate(harness.root, "selectUtcCalendarDate(); true")

    assert harness.field.property("selectedDay") == 2
    assert harness.field.property("selectedMonth") == 5
    assert harness.field.property("selectedYear") == 2026


def test_app_date_time_field_reads_month_grid_dates_without_timezone_shift(qapp):
    del qapp
    harness = _create_date_field("AppDateTimeField")

    _evaluate(harness.root, "selectUtcCalendarDate(); true")

    assert harness.field.property("selectedDay") == 2
    assert harness.field.property("selectedMonth") == 5
    assert harness.field.property("selectedYear") == 2026
