"""Read-side helpers for the circuito catalog."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import String, cast, exists, func, literal, or_, select
from sqlalchemy.orm import aliased

from ..catalog_schema import row_to_record
from ..model_entities.base import TipoViaje
from ..model_entities.operacion.circuito import Circuito
from ..model_entities.operacion.viaje import Viaje
from ..model_entities.planificacion.conductor import Conductor
from ..model_entities.planificacion.ruta import Ruta
from ..model_entities.planificacion.ubicacion import Ubicacion


def select_circuito_viajes(viajes: Sequence[Viaje]) -> tuple[Viaje | None, Viaje | None]:
    ordered = sorted(viajes, key=lambda viaje: int(viaje.id or 0))
    viaje_ida = next((viaje for viaje in ordered if viaje.tipo_viaje == TipoViaje.EXPOR), None)
    if viaje_ida is None and ordered:
        viaje_ida = ordered[0]
    viaje_vuelta = next(
        (
            viaje
            for viaje in ordered
            if viaje is not viaje_ida and viaje.tipo_viaje in {TipoViaje.IMPOR, TipoViaje.VACIO}
        ),
        None,
    )
    return viaje_ida, viaje_vuelta


def serialize_circuito_catalog_row(circuito: Circuito) -> dict[str, Any]:
    viaje_ida, viaje_vuelta = select_circuito_viajes(circuito.viajes or ())
    return {
        **dict(row_to_record("circuito", circuito).values),
        "conductor_label": _conductor_label(viaje_ida),
        "ruta_ida_label": _ruta_label(getattr(viaje_ida, "_ruta", None)),
        "ruta_vuelta_label": _ruta_label(getattr(viaje_vuelta, "_ruta", None)),
    }


def circuito_synthetic_search_clause(field_name: str, search_text: str):
    normalized = str(field_name or "").strip()
    if normalized == "conductor_label":
        viaje_ida = aliased(Viaje)
        conductor = aliased(Conductor)
        label = func.trim(func.concat(conductor.nombre, literal(" "), conductor.apellido))
        return exists(
            select(literal(1))
            .select_from(viaje_ida)
            .join(conductor, conductor.id == viaje_ida.conductor_id)
            .where(
                viaje_ida._circuito_id == Circuito.id,
                viaje_ida.tipo_viaje == TipoViaje.EXPOR,
                or_(
                    conductor.nombre.ilike(f"%{search_text}%"),
                    conductor.apellido.ilike(f"%{search_text}%"),
                    cast(label, String).ilike(f"%{search_text}%"),
                ),
            )
        )
    if normalized in {"ruta_ida_label", "ruta_vuelta_label"}:
        viaje = aliased(Viaje)
        ruta = aliased(Ruta)
        origen = aliased(Ubicacion)
        destino = aliased(Ubicacion)
        route_text = func.concat(origen.descripcion, literal(" -> "), destino.descripcion)
        viaje_types = (
            (TipoViaje.EXPOR,)
            if normalized == "ruta_ida_label"
            else (TipoViaje.IMPOR, TipoViaje.VACIO)
        )
        return exists(
            select(literal(1))
            .select_from(viaje)
            .join(ruta, ruta.id == viaje._ruta_id)
            .join(origen, origen.id == ruta.origen_id)
            .join(destino, destino.id == ruta.destino_id)
            .where(
                viaje._circuito_id == Circuito.id,
                viaje.tipo_viaje.in_(viaje_types),
                or_(
                    origen.descripcion.ilike(f"%{search_text}%"),
                    destino.descripcion.ilike(f"%{search_text}%"),
                    cast(route_text, String).ilike(f"%{search_text}%"),
                ),
            )
        )
    return None


def _conductor_label(viaje: Viaje | None) -> str:
    if viaje is None:
        return ""
    conductor = getattr(viaje, "conductor", None)
    nombre = str(getattr(conductor, "nombre", "") or "")
    apellido = str(getattr(conductor, "apellido", "") or "")
    return f"{nombre} {apellido}".strip() or str(getattr(viaje, "conductor_id", "") or "")


def _ruta_label(ruta: Ruta | None) -> str:
    if ruta is None:
        return ""
    origen = str(getattr(getattr(ruta, "origen", None), "descripcion", "") or "")
    destino = str(getattr(getattr(ruta, "destino", None), "descripcion", "") or "")
    if origen and destino:
        return f"{origen} -> {destino}"
    return str(getattr(ruta, "id", "") or "")
