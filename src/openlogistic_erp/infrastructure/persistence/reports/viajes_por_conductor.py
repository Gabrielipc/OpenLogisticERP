"""SQLAlchemy reader for the viajes por conductor report."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from openlogistic_erp.domain.reports import ReportColumn, ReportPayload, ReportTable
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import (
    Conductor,
    Descarga,
    DetalleOperacion,
    EstadoViaje,
    Ruta,
    Viaje,
)

from .base import ReportReaderBase


class ViajesPorConductorReportReader(ReportReaderBase):
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def generate(self, params: dict[str, Any]) -> ReportPayload:
        start_dt, end_dt = self.parse_date_range(params.get("rango_fechas"))
        if start_dt is None or end_dt is None:
            raise ValueError("Debes indicar un rango de fechas valido.")
        conductor_id = self.parse_int(params.get("conductor_id"))
        cliente_id = self.parse_int(params.get("cliente_id"))
        estado = _parse_estado_viaje(params.get("estado_viaje"))
        incluir_detalle = bool(params.get("incluir_detalle"))

        with self._session_factory() as session:
            query = session.query(Viaje).options(
                joinedload(Viaje.conductor),
                joinedload(Viaje.cliente),
                joinedload(Viaje._ruta).joinedload(Ruta.origen),
                joinedload(Viaje._ruta).joinedload(Ruta.destino),
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.descarga),
            )
            if conductor_id is not None:
                query = query.filter(Viaje.conductor_id == conductor_id)
            if cliente_id is not None:
                query = query.filter(Viaje.cliente_id == cliente_id)
            if estado is not None:
                query = query.filter(Viaje.estado == estado)
            query = _apply_overlap_prefilter(query, start_dt, end_dt)

            viajes = [viaje for viaje in query.all() if _overlaps(viaje, start_dt, end_dt)]

        resumen = defaultdict(_empty_summary)
        detalle_rows: list[dict[str, Any]] = []
        for viaje in viajes:
            conductor = viaje.conductor
            if conductor is None:
                continue
            row = resumen[int(conductor.id)]
            row["conductor"] = self.nombre_completo(conductor.nombre, conductor.apellido)
            row["total_viajes"] += 1
            row["dias_ocupado"] += _occupied_days(viaje, start_dt, end_dt)
            first_date = _interval_start(viaje)
            if first_date is not None:
                if row["primer_viaje"] is None or first_date < row["primer_viaje"]:
                    row["primer_viaje"] = first_date
                if row["ultimo_viaje"] is None or first_date > row["ultimo_viaje"]:
                    row["ultimo_viaje"] = first_date

            if incluir_detalle:
                detalle_rows.append(
                    {
                        "conductor": row["conductor"],
                        "referencia": viaje.referencia or "-",
                        "fecha": viaje.fecha_posicionamiento,
                        "fecha_finalizacion": _fecha_descarga(viaje),
                        "ruta": _ruta_label(viaje._ruta),
                        "cliente": viaje.cliente.nombre if viaje.cliente else "Sin cliente",
                        "estado": viaje.estado.value if viaje.estado else "",
                        "tipo": viaje.tipo_viaje.value if viaje.tipo_viaje else "",
                    }
                )

        resumen_rows = list(resumen.values())
        for row in resumen_rows:
            total_viajes = int(row["total_viajes"] or 0)
            dias_ocupado = int(row["dias_ocupado"] or 0)
            row["promedio_diario"] = round(dias_ocupado / total_viajes, 2) if total_viajes else 0.0
        resumen_rows.sort(key=lambda row: str(row["conductor"]).lower())

        tables = [
            ReportTable(
                key="resumen_conductor",
                title="Resumen por conductor",
                columns=(
                    ReportColumn("conductor", "Conductor"),
                    ReportColumn("total_viajes", "No. de viajes", "int"),
                    ReportColumn("dias_ocupado", "No. dias ocupado", "int"),
                    ReportColumn("promedio_diario", "Promedio de dias por viaje", "float"),
                    ReportColumn("primer_viaje", "Primer viaje", "datetime"),
                    ReportColumn("ultimo_viaje", "Ultimo viaje", "datetime"),
                ),
                rows=tuple(resumen_rows),
            )
        ]

        if incluir_detalle and detalle_rows:
            detalle_rows.sort(key=lambda row: (str(row["conductor"]).lower(), row["fecha"] or datetime.min))
            tables.append(
                ReportTable(
                    key="detalle_viajes",
                    title="Detalle de viajes",
                    columns=(
                        ReportColumn("conductor", "Conductor"),
                        ReportColumn("referencia", "Referencia"),
                        ReportColumn("fecha", "Fecha", "datetime"),
                        ReportColumn("fecha_finalizacion", "Fecha finalizacion", "datetime"),
                        ReportColumn("ruta", "Ruta"),
                        ReportColumn("cliente", "Cliente"),
                        ReportColumn("estado", "Estado"),
                        ReportColumn("tipo", "Tipo"),
                    ),
                    rows=tuple(detalle_rows),
                )
            )

        return ReportPayload(
            title="Viajes por conductor",
            generated_at=datetime.now(),
            message="" if resumen_rows else "Sin datos para el periodo seleccionado.",
            tables=tuple(tables),
        )


def _empty_summary() -> dict[str, Any]:
    return {
        "conductor": "",
        "total_viajes": 0,
        "dias_ocupado": 0,
        "promedio_diario": 0.0,
        "primer_viaje": None,
        "ultimo_viaje": None,
    }


def _parse_estado_viaje(value: Any) -> EstadoViaje | None:
    if value in (None, ""):
        return None
    if isinstance(value, EstadoViaje):
        return value
    return EstadoViaje(str(value))


def _apply_overlap_prefilter(query, start_dt: datetime | None, end_dt: datetime | None):
    if start_dt is None and end_dt is None:
        return query

    query = query.outerjoin(Viaje.detalle_operacion).outerjoin(DetalleOperacion.descarga)
    if start_dt is not None:
        query = query.filter(
            or_(
                Descarga.fecha_descarga >= start_dt,
                Descarga.fecha_descarga.is_(None),
            )
        )
    if end_dt is not None:
        query = query.filter(
            or_(
                Viaje.fecha_posicionamiento <= end_dt,
                Viaje.fecha_posicionamiento.is_(None) & (Descarga.fecha_descarga <= end_dt),
            )
        )
    return query


def _interval_start(viaje: Viaje) -> datetime | None:
    return viaje.fecha_posicionamiento or _fecha_descarga(viaje)


def _interval_end(viaje: Viaje, fallback_end: datetime | None = None) -> datetime | None:
    return _fecha_descarga(viaje) or fallback_end or datetime.now()


def _fecha_descarga(viaje: Viaje) -> datetime | None:
    detalle = viaje.detalle_operacion
    descarga: Descarga | None = detalle.descarga if detalle is not None else None
    return descarga.fecha_descarga if descarga is not None else None


def _overlaps(viaje: Viaje, start_dt: datetime | None, end_dt: datetime | None) -> bool:
    interval_start = _interval_start(viaje)
    if interval_start is None:
        return False
    interval_end = _interval_end(viaje, end_dt)
    if start_dt is not None and interval_end < start_dt:
        return False
    if end_dt is not None and interval_start > end_dt:
        return False
    return True


def _occupied_days(viaje: Viaje, start_dt: datetime | None, end_dt: datetime | None) -> int:
    interval_start = _interval_start(viaje)
    if interval_start is None:
        return 0
    interval_end = _interval_end(viaje, end_dt)
    effective_start = max(interval_start, start_dt) if start_dt is not None else interval_start
    effective_end = min(interval_end, end_dt) if end_dt is not None else interval_end
    if effective_end < effective_start:
        return 0
    return (effective_end.date() - effective_start.date()).days + 1


def _ruta_label(ruta: Ruta | None) -> str:
    if ruta is None:
        return ""
    origen = getattr(getattr(ruta, "origen", None), "descripcion", "") or str(ruta.origen_id)
    destino = getattr(getattr(ruta, "destino", None), "descripcion", "") or str(ruta.destino_id)
    return f"{origen} - {destino}"
