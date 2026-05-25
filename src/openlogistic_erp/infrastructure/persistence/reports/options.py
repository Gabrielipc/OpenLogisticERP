"""Report filter options backed by current persistence models."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openlogistic_erp.domain.reports import ReportFilterOption
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import (
    Cliente,
    Conductor,
    EstadoFactura,
    EstadoViaje,
)


class ReportOptionsReader:
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def conductores(self) -> list[ReportFilterOption]:
        try:
            with self._session_factory() as session:
                records = session.query(Conductor).order_by(Conductor.nombre).all()
                return [
                    ReportFilterOption(value=record.id, label=_nombre_completo(record.nombre, record.apellido))
                    for record in records
                ]
        except Exception:
            return []

    def clientes(self) -> list[ReportFilterOption]:
        try:
            with self._session_factory() as session:
                records = session.query(Cliente).order_by(Cliente.nombre).all()
                return [ReportFilterOption(value=record.id, label=record.nombre) for record in records]
        except Exception:
            return []

    def estado_viaje(self) -> list[ReportFilterOption]:
        return [ReportFilterOption(value=estado.value, label=estado.value) for estado in EstadoViaje]

    def estado_factura(self) -> list[ReportFilterOption]:
        return [ReportFilterOption(value=estado.value, label=estado.value) for estado in EstadoFactura]

    def bucket_scheme(self) -> list[ReportFilterOption]:
        return [ReportFilterOption(value="30_60_90", label="0-30 / 31-60 / 61-90 / 91+ dias")]


def _nombre_completo(nombre: Any, apellido: Any) -> str:
    parts = [str(part).strip() for part in (nombre, apellido) if part not in (None, "")]
    label = " ".join(part for part in parts if part)
    return label or "(Sin nombre)"
