"""Base QML-aware ViewModel contract."""

from __future__ import annotations

from weakref import WeakSet

import shiboken6

from ..qt import Property, QmlNamedElement, QmlUncreatable, QObject, Signal, Slot

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@QmlNamedElement("BaseViewModel")
@QmlUncreatable("BaseViewModel is only exposed through concrete subclasses.")
class BaseViewModel(QObject):
    """Base class for all MVVM view models in the new architecture."""

    busyChanged = Signal(bool)
    _live_instances: WeakSet = WeakSet()

    def __init__(self) -> None:
        super().__init__()
        self._is_busy = False
        self._disposed = False
        self._live_instances.add(self)

    @Property(bool, notify=busyChanged)
    def is_busy(self) -> bool: # type: ignore
        return self._is_busy

    @is_busy.setter
    def is_busy(self, value: bool) -> None:
        if self._is_busy != value:
            self._is_busy = value
            self.busyChanged.emit(value)

    @Slot()
    def dispose(self) -> None:
        if self._disposed:
            return
        self.is_busy = False
        self._disposed = True

    @classmethod
    def dispose_live_instances(cls) -> None:
        def priority(instance: BaseViewModel) -> int:
            class_name = instance.__class__.__name__
            if class_name == "AppShellViewModel":
                return 0
            if class_name.endswith("WorkflowViewModel"):
                return 1
            if class_name == "CatalogScreenViewModel":
                return 2
            return 3

        for instance in sorted(list(cls._live_instances), key=priority):
            if not shiboken6.isValid(instance):
                cls._live_instances.discard(instance)
                continue
            if getattr(instance, "_disposed", False):
                continue
            instance.dispose()
            if shiboken6.isValid(instance):
                instance.deleteLater()
