"""Lightweight fuel consumption analysis for workflow detail pages."""

from __future__ import annotations

from typing import Any
from unicodedata import normalize

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ...infrastructure.persistence.modelo.model_entities.base import TipoReferencia
from ...infrastructure.persistence.modelo.model_entities.combustible.criterios_consumo import (
    CriteriosConsumoCombustible,
)
from ...infrastructure.persistence.modelo.model_entities.combustible.modelo_consumo_thermo import (
    ModeloConsumoThermo,
)
from ...infrastructure.persistence.modelo.workflow_orm import (
    Camion,
    Circuito,
    Descarga,
    DetalleOperacion,
    MovimientoAdicional,
    OrdenCombustible,
    Ruta,
    TipoOrdenCombustible,
    TipoViaje,
    Viaje,
)


POR_PESO_DESTINO_CODES = frozenset({"CIUDAD_HIDALGO", "HIDALGO"})
POR_PESO_DESTINO_ALIASES = frozenset({"ciudad hidalgo", "hidalgo"})


class ConsumoAnalysisService:
    """Builds lightweight fuel-consumption analysis dictionaries for UI details."""

    def analyze_camion(self, session, circuito_id: int) -> dict[str, Any]:
        circuito = self._load_circuito(session, circuito_id)
        if circuito is None:
            return self._missing_camion("No se encontro el circuito seleccionado.")

        viaje_ida = self._viaje_ida(circuito)
        if viaje_ida is None:
            return self._missing_camion("El circuito no tiene viaje de ida para analizar.")

        viaje_vuelta = self._viaje_vuelta(circuito, viaje_ida)
        detalle_ida = getattr(viaje_ida, "detalle_operacion", None)
        detalle_vuelta = getattr(viaje_vuelta, "detalle_operacion", None) if viaje_vuelta is not None else None
        gasto = getattr(circuito, "gasto_real_camion", None)

        combustible_base = _sum_orders(detalle_ida, TipoOrdenCombustible.CAMION)
        combustible_importacion = _sum_orders(detalle_vuelta, TipoOrdenCombustible.CAMION)
        retorno = float(getattr(gasto, "retorno_camion", 0) or 0)
        consumo_real = combustible_base + combustible_importacion - retorno

        criteria = self._build_camion_criteria(circuito, viaje_ida, viaje_vuelta)
        consumo_estimado = self._lookup_camion_estimate(session, viaje_ida, criteria)
        if consumo_estimado is None:
            consumo_estimado = combustible_base

        return {
            "status": "ok",
            "type": str(criteria["tipo_referencia"]),
            "consumo_real": _fmt(consumo_real),
            "consumo_estimado": _fmt(consumo_estimado),
            "diferencia": _fmt(consumo_real - consumo_estimado),
            "metrics": {
                "combustible_base": _fmt(combustible_base),
                "combustible_importacion": _fmt(combustible_importacion),
                "retorno_camion": _fmt(retorno),
            },
            "criteria": dict(criteria),
            "messages": [],
        }

    def analyze_thermo(self, session, viaje_id: int) -> dict[str, Any]:
        viaje = self._load_viaje(session, viaje_id)
        if viaje is None:
            return self._missing_thermo("No se encontro el viaje seleccionado.")

        detalle = getattr(viaje, "detalle_operacion", None)
        gasto = getattr(detalle, "gasto_real_thermo", None) if detalle is not None else None
        actividad = getattr(detalle, "actividad_thermo", None) if detalle is not None else None

        horas = float(getattr(actividad, "_duracion_horas", 0) or 0)
        combustible_base = float(getattr(gasto, "combustible_base_thermo", 0) or 0)
        restante = float(getattr(gasto, "restante_thermo", 0) or 0)
        ordenes_thermo = _sum_orders(detalle, TipoOrdenCombustible.THERMO)
        movimientos = _sum_movimientos(detalle)
        consumo_real = combustible_base + ordenes_thermo + movimientos - restante
        rendimiento = horas / consumo_real if consumo_real > 0 else None

        base_result = {
            "type": "THERMO",
            "horas": _fmt(horas),
            "consumo_real": _fmt(consumo_real),
            "rendimiento": _fmt(rendimiento),
            "metrics": {
                "combustible_base_thermo": _fmt(combustible_base),
                "ordenes_thermo": _fmt(ordenes_thermo),
                "movimientos_transferidos": _fmt(movimientos),
                "restante_thermo": _fmt(restante),
            },
        }

        modelo = session.execute(
            select(ModeloConsumoThermo).where(ModeloConsumoThermo.thermo_id == int(viaje.thermo_id))
        ).scalar_one_or_none()
        if modelo is None:
            return {
                **base_result,
                "status": "missing_model",
                "consumo_estimado": "",
                "diferencia": "",
                "messages": ["No hay modelo de consumo para el thermo seleccionado."],
            }

        try:
            consumo_estimado = float(modelo.calcular_gasto_combustible(getattr(viaje, "temperatura", 0) or 0, horas))
        except ValueError as exc:
            return {
                **base_result,
                "status": "missing_model",
                "consumo_estimado": "",
                "diferencia": "",
                "messages": [str(exc)],
            }

        return {
            **base_result,
            "status": "ok",
            "consumo_estimado": _fmt(consumo_estimado),
            "diferencia": _fmt(consumo_real - consumo_estimado),
            "messages": [],
        }

    def _build_camion_criteria(
        self,
        circuito: Circuito,
        viaje_ida: Viaje,
        viaje_vuelta: Viaje | None,
    ) -> dict[str, Any]:
        refs: dict[str, Any] = {
            "tipo_referencia": TipoReferencia.BASE.value,
            "destino_id": None,
            "cliente_id": None,
            "lugar_carga_id": None,
            "ruta_movimiento_id": None,
            "peso_min": None,
            "peso_max": None,
            "camion_id": int(viaje_ida.camion_id),
        }

        movimiento_triangulado = next(
            (
                movimiento
                for movimiento in sorted(circuito.movimientos_adicionales or [], key=lambda item: int(item.id or 0))
                if bool(getattr(movimiento, "es_triangulado", False))
            ),
            None,
        )
        if movimiento_triangulado is not None:
            self._apply_triangulado_criteria(refs, movimiento_triangulado, viaje_ida, viaje_vuelta)
            return self._public_criteria(refs)

        ruta_ida = getattr(viaje_ida, "_ruta", None)
        destino = getattr(ruta_ida, "destino", None)
        if destino is not None:
            refs["destino_id"] = int(destino.id)

        if _destino_usa_referencia_por_peso(destino):
            refs["tipo_referencia"] = TipoReferencia.POR_PESO.value
            descarga = self._descarga(viaje_vuelta)
            peso = getattr(descarga, "peso", None)
            refs["peso_min"] = str(peso) if peso not in (None, "") else None
            refs["peso_max"] = str(peso) if peso not in (None, "") else None
            return self._public_criteria(refs)

        refs["tipo_referencia"] = TipoReferencia.BASE.value
        if refs["destino_id"] == 1:
            refs["cliente_id"] = int(viaje_ida.cliente_id) if viaje_ida.cliente_id is not None else None
            refs["lugar_carga_id"] = self._lugar_carga_id(viaje_vuelta)
        elif refs["destino_id"] == 4:
            refs["lugar_carga_id"] = self._lugar_carga_id(viaje_vuelta)
        return self._public_criteria(refs)

    def _apply_triangulado_criteria(
        self,
        refs: dict[str, Any],
        movimiento: MovimientoAdicional,
        viaje_ida: Viaje,
        viaje_vuelta: Viaje | None,
    ) -> None:
        refs["tipo_referencia"] = TipoReferencia.TRIANGULADO.value
        refs["ruta_movimiento_id"] = int(movimiento.ruta_id) if movimiento.ruta_id is not None else None
        nuevo_destino = getattr(getattr(movimiento, "ruta", None), "destino", None)
        if nuevo_destino is not None:
            refs["destino_id"] = int(nuevo_destino.id)
        nuevo_destino_id = refs.get("destino_id")
        if nuevo_destino_id == 4:
            if refs["ruta_movimiento_id"] == 21:
                refs["cliente_id"] = int(viaje_ida.cliente_id) if viaje_ida.cliente_id is not None else None
            else:
                refs["lugar_carga_id"] = self._lugar_carga_id(viaje_vuelta)
        elif nuevo_destino_id == 1:
            refs["lugar_carga_id"] = self._lugar_carga_id(viaje_vuelta)

    def _lookup_camion_estimate(self, session, viaje_ida: Viaje, criteria: dict[str, Any]) -> float | None:
        query = (
            session.query(CriteriosConsumoCombustible)
            .join(CriteriosConsumoCombustible.camiones)
            .filter(Camion.id == int(viaje_ida.camion_id))
            .filter(CriteriosConsumoCombustible.tipo_referencia == TipoReferencia(criteria["tipo_referencia"]))
        )
        mapping = {
            "destino_id": CriteriosConsumoCombustible.destino_id,
            "cliente_id": CriteriosConsumoCombustible.cliente_id,
            "lugar_carga_id": CriteriosConsumoCombustible.lugar_carga_id,
            "ruta_movimiento_id": CriteriosConsumoCombustible.ruta_movimiento_id,
            "peso_min": CriteriosConsumoCombustible.peso_min,
            "peso_max": CriteriosConsumoCombustible.peso_max,
        }
        for key, column in mapping.items():
            value = criteria.get(key)
            if value in (None, ""):
                continue
            if key in {"peso_min", "peso_max"}:
                numeric_value = _float_or_none(value)
                if numeric_value is None:
                    continue
                value = numeric_value
            query = query.filter(column == value)
        criterio = query.first()
        return float(criterio.consumo_galones) if criterio is not None else None

    @staticmethod
    def _public_criteria(refs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tipo_referencia": refs.get("tipo_referencia"),
            "destino_id": refs.get("destino_id"),
            "cliente_id": refs.get("cliente_id"),
            "lugar_carga_id": refs.get("lugar_carga_id"),
            "ruta_movimiento_id": refs.get("ruta_movimiento_id"),
            "peso_min": refs.get("peso_min"),
            "peso_max": refs.get("peso_max"),
            "camion_id": refs.get("camion_id"),
        }

    @staticmethod
    def _load_circuito(session, circuito_id: int) -> Circuito | None:
        return session.execute(
            select(Circuito)
            .options(
                joinedload(Circuito.gasto_real_camion),
                joinedload(Circuito.movimientos_adicionales).joinedload(MovimientoAdicional.ruta).joinedload(Ruta.destino),
                joinedload(Circuito.viajes).joinedload(Viaje._ruta).joinedload(Ruta.destino),
                joinedload(Circuito.viajes).joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.ordenes_combustible),
                joinedload(Circuito.viajes).joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.descarga),
            )
            .where(Circuito.id == int(circuito_id))
        ).unique().scalar_one_or_none()

    @staticmethod
    def _load_viaje(session, viaje_id: int) -> Viaje | None:
        return session.execute(
            select(Viaje)
            .options(
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.ordenes_combustible),
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.movimientos_combustible),
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.actividad_thermo),
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.gasto_real_thermo),
            )
            .where(Viaje.id == int(viaje_id))
        ).unique().scalar_one_or_none()

    @staticmethod
    def _viaje_ida(circuito: Circuito) -> Viaje | None:
        viajes = sorted(list(circuito.viajes or []), key=lambda viaje: int(viaje.id or 0))
        return next((viaje for viaje in viajes if viaje.tipo_viaje == TipoViaje.EXPOR), viajes[0] if viajes else None)

    @staticmethod
    def _viaje_vuelta(circuito: Circuito, viaje_ida: Viaje) -> Viaje | None:
        return next(
            (
                viaje
                for viaje in sorted(list(circuito.viajes or []), key=lambda item: int(item.id or 0))
                if viaje is not viaje_ida and viaje.tipo_viaje in {TipoViaje.IMPOR, TipoViaje.VACIO}
            ),
            None,
        )

    @staticmethod
    def _descarga(viaje: Viaje | None) -> Descarga | None:
        detalle = getattr(viaje, "detalle_operacion", None) if viaje is not None else None
        return getattr(detalle, "descarga", None) if detalle is not None else None

    def _lugar_carga_id(self, viaje: Viaje | None) -> int | None:
        descarga = self._descarga(viaje)
        value = getattr(descarga, "_lugar_carga_id", None)
        return int(value) if value is not None else None

    @staticmethod
    def _missing_camion(message: str) -> dict[str, Any]:
        return {
            "status": "missing_data",
            "type": "",
            "consumo_real": "",
            "consumo_estimado": "",
            "diferencia": "",
            "metrics": {},
            "criteria": {},
            "messages": [message],
        }

    @staticmethod
    def _missing_thermo(message: str) -> dict[str, Any]:
        return {
            "status": "missing_data",
            "type": "THERMO",
            "horas": "",
            "consumo_real": "",
            "rendimiento": "",
            "consumo_estimado": "",
            "diferencia": "",
            "metrics": {},
            "messages": [message],
        }


def _sum_orders(detalle: DetalleOperacion | None, tipo: TipoOrdenCombustible) -> float:
    if detalle is None:
        return 0.0
    total = 0.0
    for order in detalle.ordenes_combustible or []:
        if _order_type(order) == tipo:
            total += float(order.galones_autorizados or 0)
    return total


def _order_type(order: OrdenCombustible) -> TipoOrdenCombustible:
    value = getattr(order, "tipo", None)
    if isinstance(value, TipoOrdenCombustible):
        return value
    try:
        return TipoOrdenCombustible(value)
    except ValueError:
        return TipoOrdenCombustible.CAMION


def _sum_movimientos(detalle: DetalleOperacion | None) -> float:
    if detalle is None:
        return 0.0
    return sum(float(movimiento.galones_transferidos or 0) for movimiento in detalle.movimientos_combustible or [])


def _destino_usa_referencia_por_peso(destino: object) -> bool:
    if destino is None:
        return False
    codigo = _code_token(getattr(destino, "codigo", ""))
    descripcion = _text_token(getattr(destino, "descripcion", ""))
    return codigo in POR_PESO_DESTINO_CODES or descripcion in POR_PESO_DESTINO_ALIASES


def _text_token(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    ascii_text = normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.casefold().split())


def _code_token(value: object) -> str:
    return _text_token(value).replace(" ", "_").upper()


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: object) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)
