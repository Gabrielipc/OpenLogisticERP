"""Workflow command DTOs for Modelo services."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CreateViajeCommand:
    payload: Mapping[str, object]

    def to_payload(self) -> dict[str, object]:
        return dict(self.payload)


@dataclass(frozen=True)
class UpdateViajeCommand:
    payload: Mapping[str, object]
    record_id: int | None = None

    def to_payload(self) -> dict[str, object]:
        if self.record_id is None:
            return dict(self.payload)
        return {"id": self.record_id, **dict(self.payload)}


@dataclass(frozen=True)
class CreateFacturaCommand:
    payload: Mapping[str, object]

    def to_payload(self) -> dict[str, object]:
        return dict(self.payload)


@dataclass(frozen=True)
class UpdateFacturaCommand:
    payload: Mapping[str, object]
    record_id: int | None = None

    def to_payload(self) -> dict[str, object]:
        if self.record_id is None:
            return dict(self.payload)
        return {"id": self.record_id, **dict(self.payload)}


@dataclass(frozen=True)
class CreateReciboCommand:
    payload: Mapping[str, object]

    def to_payload(self) -> dict[str, object]:
        return dict(self.payload)


@dataclass(frozen=True)
class UpdateReciboCommand:
    payload: Mapping[str, object]
    record_id: int | None = None

    def to_payload(self) -> dict[str, object]:
        if self.record_id is None:
            return dict(self.payload)
        return {"id": self.record_id, **dict(self.payload)}


@dataclass(frozen=True)
class CloseCircuitoCommand:
    circuito: object

    def to_payload(self) -> object:
        return self.circuito


@dataclass(frozen=True)
class UpdateCircuitoSectionsCommand:
    circuito: object
    secciones_data: Mapping[str, Any] | None = None

    def to_payload(self) -> object:
        if self.secciones_data is None:
            return self.circuito
        return {"circuito": self.circuito, "secciones_data": dict(self.secciones_data)}
