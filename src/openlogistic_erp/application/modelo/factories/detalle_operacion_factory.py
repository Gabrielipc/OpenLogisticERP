"""Factories for DetalleOperacion aggregate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....infrastructure.persistence.modelo.workflow_orm import (
    ActividadThermo,
    Descarga,
    DetalleOperacion,
    EstadoDetalle,
    GastoRealThermo,
    MovimientoCombustible,
    OrdenCombustible,
)


class DetalleOperacionFactory:
    def create(self, viaje, data: Mapping[str, Any] | None = None) -> DetalleOperacion:
        data = dict(data or {})

        detalle = DetalleOperacion(
            viaje=viaje,
            estado=data.pop("estado", EstadoDetalle.ABIERTO),
        )

        for detalle_data in data.pop("ordenes_combustible", []) or []:
            if isinstance(detalle_data, dict):
                detalle.ordenes_combustible.append(OrdenCombustible(**detalle_data))

        for detalle_data in data.pop("movimientos_combustible", []) or []:
            if isinstance(detalle_data, dict):
                detalle.movimientos_combustible.append(MovimientoCombustible(**detalle_data))

        actividad_data = data.pop("actividad_thermo", None)
        if isinstance(actividad_data, dict):
            detalle.actividad_thermo = ActividadThermo(**actividad_data)

        descarga_data = data.pop("descarga", None)
        if isinstance(descarga_data, dict):
            detalle.descarga = Descarga(**descarga_data)

        gasto_thermo_data = data.pop("gasto_real_thermo", None)
        if isinstance(gasto_thermo_data, dict):
            detalle.gasto_real_thermo = GastoRealThermo(**gasto_thermo_data)

        for key, value in data.items():
            if value is not None:
                setattr(detalle, key, value)

        return detalle
