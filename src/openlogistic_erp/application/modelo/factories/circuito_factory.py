"""Factories for Circuito aggregates."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from ....infrastructure.persistence.modelo.workflow_orm import (
    Circuito,
    EstadoCircuito,
    GastoRealCamion,
    MovimientoAdicional,
)


class CircuitoFactory:
    def create(self, data: Mapping[str, Any] | None = None) -> Circuito:
        data = dict(data or {})

        fecha_inicio = data.pop("fecha_inicio", data.pop("fechaInicio", None)) or datetime.now()
        fecha_fin = data.pop("fecha_fin", data.pop("fechaFin", None))
        estado = data.pop("estado", EstadoCircuito.ENPROGRESO)

        circuito = Circuito(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            estado=estado,
        )

        gasto_data = data.pop("gasto_real_camion", None)
        if isinstance(gasto_data, dict):
            defaults = {
                "combustible_base_camion": gasto_data.pop("combustible_base_camion", 60.0),
                "retorno_camion": gasto_data.pop("retorno_camion", 0.0),
                "_consumo_camion": gasto_data.pop("_consumo_camion", 0.0),
            }
            defaults.update(gasto_data)
            circuito.gasto_real_camion = GastoRealCamion(**defaults)

        for movimiento_data in data.pop("movimientos_adicionales", []) or []:
            if not isinstance(movimiento_data, dict):
                continue
            defaults = {"fecha_movimiento": datetime.now()}
            defaults.update(movimiento_data)
            circuito.movimientos_adicionales.append(MovimientoAdicional(**defaults))

        if data:
            extra = {k: v for k, v in data.items() if v is not None}
            for key, value in extra.items():
                setattr(circuito, key, value)

        return circuito
