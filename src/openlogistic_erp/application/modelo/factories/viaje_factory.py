"""Factories for domain creation of Viaje entities."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from ....infrastructure.persistence.modelo.workflow_orm import (
    EstadoFacturacion,
    EstadoViaje,
    TipoViaje,
    Viaje,
    ViajeExportacion,
    ViajeImportacion,
    ViajeVacio,
)


class ViajeFactory:
    _viaje_class_map = {
        TipoViaje.EXPOR: ViajeExportacion,
        TipoViaje.IMPOR: ViajeImportacion,
        TipoViaje.VACIO: ViajeVacio,
    }

    @staticmethod
    def _normalize_tipo(tipo: Any) -> TipoViaje:
        if isinstance(tipo, TipoViaje):
            return tipo
        return TipoViaje(tipo)

    def _create_base(self, data: Mapping[str, Any]) -> Viaje:
        data = dict(data)

        tipo = self._normalize_tipo(data.get("tipo_viaje"))
        data["tipo_viaje"] = tipo

        required_fields = {
            TipoViaje.EXPOR: ["conductor_id", "furgon_id", "camion_id", "thermo_id", "_ruta_id", "fecha_posicionamiento", "_circuito_id"],
            TipoViaje.IMPOR: ["conductor_id", "furgon_id", "camion_id", "thermo_id", "_ruta_id", "fecha_posicionamiento", "_circuito_id"],
            TipoViaje.VACIO: ["conductor_id", "furgon_id", "camion_id", "thermo_id", "_ruta_id", "fecha_posicionamiento", "_circuito_id"],
        }[tipo]

        if tipo in (TipoViaje.EXPOR, TipoViaje.IMPOR) and data.get("cliente_id") is None:
            raise ValueError("cliente_id es obligatorio para viajes de exportacion e importacion")
        if tipo == TipoViaje.VACIO and data.get("cliente_id") is not None:
            raise ValueError("Un viaje vacio no debe tener cliente")

        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValueError(f"Factory error: Campos requeridos faltantes: {missing}")

        data.setdefault("estado", EstadoViaje.PENDIENTE)
        data.setdefault("_estado_facturacion", EstadoFacturacion.REGISTRADO)

        viaje_cls = self._viaje_class_map.get(tipo)
        if not viaje_cls:
            raise ValueError(f"Factory error: Tipo de viaje no soportado: {tipo!r}")

        return viaje_cls(**data)

    def create_expor(self, data: Mapping[str, Any], circuito_id: int, **kwargs) -> Viaje:
        payload = dict(data)
        payload["tipo_viaje"] = TipoViaje.EXPOR
        payload["_circuito_id"] = circuito_id
        payload.setdefault("estado", EstadoViaje.PENDIENTE)
        payload.setdefault("fecha_posicionamiento", datetime.now())
        payload.update(kwargs)
        return self._create_base(payload)

    def create_impor(self, data: Mapping[str, Any], circuito_id: int, **kwargs) -> Viaje:
        payload = dict(data)
        payload["tipo_viaje"] = TipoViaje.IMPOR
        payload["_circuito_id"] = circuito_id
        payload.setdefault("estado", EstadoViaje.PENDIENTE)
        payload.setdefault("fecha_posicionamiento", datetime.now())
        payload.update(kwargs)
        return self._create_base(payload)

    def create_vacio(self, viaje_ida: Viaje, circuito_id: int, **kwargs) -> Viaje:
        payload = {
            "cliente_id": None,
            "referencia": None,
            "descripcion": None,
            "conductor_id": viaje_ida.conductor_id,
            "furgon_id": viaje_ida.furgon_id,
            "camion_id": viaje_ida.camion_id,
            "thermo_id": viaje_ida.thermo_id,
            "_ruta_id": kwargs.pop("_ruta_id", getattr(viaje_ida, "_ruta_id", None)),
            "tipo_viaje": TipoViaje.VACIO,
            "_circuito_id": circuito_id,
            "estado": EstadoViaje.PENDIENTE,
            "fecha_posicionamiento": kwargs.pop("fecha_posicionamiento", datetime.now()),
            "_estado_facturacion": EstadoFacturacion.SIN_FACTURA,
        }
        payload.update(kwargs)
        return self._create_base(payload)
