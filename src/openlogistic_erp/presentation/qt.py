"""Typed PySide6 facade used across presentation, bootstrap and tests.

PySide6's runtime works well for QML decorators and Qt metaobject helpers,
but some shipped stubs are too narrow for static analyzers like Pylance.
This module exposes the subset we use with typing-friendly wrappers.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar, cast  # noqa: UP035

from PySide6 import __file__ as PYSIDE6_FILE
from PySide6.QtCore import (
    Property as _Property,
)
from PySide6.QtCore import (
    QCoreApplication,
    QAbstractListModel,
    QAbstractTableModel,
    QEventLoop,
    QModelIndex,
    QObject,
    QRunnable,
    QSettings,
    QThreadPool,
    QTimer,
    Qt,
    QUrl,
)
from PySide6.QtCore import (
    Signal as _Signal,
)
from PySide6.QtCore import (
    Slot as _Slot,
)
from PySide6.QtQml import (
    QmlNamedElement as _QmlNamedElement,
)
from PySide6.QtQml import (
    QmlUncreatable as _QmlUncreatable,
)
from PySide6.QtQml import (
    QQmlDebuggingEnabler,
)
from PySide6.QtQml import (
    QQmlApplicationEngine,
)
from PySide6.QtQml import (
    qmlTypeId as _qmlTypeId,
)
from PySide6.QtWidgets import QApplication

F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T", bound=type)


def Signal(*types: object, name: str | None = None, arguments: list[str] | None = None) -> Any:
    signal_factory = cast(Any, _Signal)
    if name is None and arguments is None:
        return signal_factory(*types)
    if name is None:
        return signal_factory(*types, arguments=arguments)
    if arguments is None:
        return signal_factory(*types, name=name)
    return signal_factory(*types, name=name, arguments=arguments)


def Slot(*types: object, name: str | None = None, result: object | None = None) -> Callable[[F], F]:
    slot_factory = cast(Any, _Slot)
    if name is None and result is None:
        return cast(Callable[[F], F], slot_factory(*types))
    if name is None:
        return cast(Callable[[F], F], slot_factory(*types, result=result))
    if result is None:
        return cast(Callable[[F], F], slot_factory(*types, name=name))
    return cast(Callable[[F], F], slot_factory(*types, name=name, result=result))


def Property(type_: object, /, *args: object, **kwargs: Any) -> Any:
    return cast(Any, _Property)(type_, *args, **kwargs)


def QmlNamedElement(name: str) -> Callable[[T], T]:
    decorator_factory = cast(Any, _QmlNamedElement)
    return cast(Callable[[T], T], decorator_factory(name))


def QmlUncreatable(reason: str) -> Callable[[T], T]:
    decorator_factory = cast(Any, _QmlUncreatable)
    return cast(Callable[[T], T], decorator_factory(reason))


def qmlTypeId(uri: str | bytes, major: int, minor: int, qml_name: str | bytes) -> int:
    # PySide6 accepts str here at runtime even though the stub narrows to bytes-like.
    return int(cast(Any, _qmlTypeId)(uri, major, minor, qml_name))


__all__ = [
    "PYSIDE6_FILE",
    "Property",
    "QAbstractListModel",
    "QAbstractTableModel",
    "QApplication",
    "QCoreApplication",
    "QEventLoop",
    "QModelIndex",
    "QObject",
    "QQmlApplicationEngine",
    "QQmlDebuggingEnabler",
    "QRunnable",
    "QSettings",
    "QThreadPool",
    "QTimer",
    "QUrl",
    "QmlNamedElement",
    "QmlUncreatable",
    "Qt",
    "Signal",
    "Slot",
    "qmlTypeId",
]
