from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Integer, Table
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Moneda(StrEnum):
    USD = "USD"
    NIO = "NIO"


class EstadoCamion(StrEnum):
    ACTIVO = "Activo"
    MANTENIMIENTO = "Mantenimiento"
    BAJA = "De baja"
    ENVIAJE = "En viaje"
    VENDIDO = "Vendido"
    AGREGADO = "Agregado"


class EstadoConductor(StrEnum):
    VIAJE = "En un viaje"
    DISPONIBLE = "Disponible"
    INSTRUCCIONES = "Esperando instrucciones"
    BAJA = "De baja"
    AGREGADO = "Agregado"


class TipoCarga(StrEnum):
    SECA = "Carga seca"
    REFRIG = "Carga refrigerada"
    FRESCA = "Carga fresca"


class TipoViaje(StrEnum):
    EXPOR = "Exportacion"
    IMPOR = "Importacion"
    VACIO = "Vacio"


class EstadoViaje(StrEnum):
    PENDIENTE = "Pendiente"
    ENCURSO = "En curso"
    FINALIZADO = "Finalizado"


class EstadoFacturacion(StrEnum):
    REGISTRADO = "Registrado"
    FACTURADO = "Facturado"
    SIN_FACTURA = "Sin factura"


class TipoDetalle(StrEnum):
    VIAJE = "Viaje"
    GASTO = "Gasto"


class TipoImpuesto(StrEnum):
    IVA = "IVA"
    RETENCION = "Retencion"
    OTRO = "Otro"


class EstadoFactura(StrEnum):
    ATRASADA = "Atrasada"
    PAGADA = "Pagada"
    ANULADA = "Anulada"
    PAGADAPAR = "Parcialmente pagada"
    PENDIENTE = "Pendiente"
    PROXIMA_A_VENCER = "Proxima a vencerse"


class TipoGasto(StrEnum):
    ESTADIA = "Estadia"
    COMIDA = "Comida"
    OTRO = "Otro"


class EstadoRecibo(StrEnum):
    ACTIVO = "Activo"
    ANULADO = "Anulado"


class EstadoDetalle(StrEnum):
    CERRADO = "Cerrado"
    ABIERTO = "Abierto"


class TipoReferencia(StrEnum):
    BASE = "BASE"
    TRIANGULADO = "TRIANGULADO"
    POR_PESO = "POR_PESO"


class Gasolinera(StrEnum):
    NEDICSA = "NEDICSA"
    MOVIL = "MOVIL"
    SV = "El Salvador"


class TipoOrdenCombustible(StrEnum):
    CAMION = "CAMION"
    THERMO = "THERMO"


class EstadoCircuito(StrEnum):
    ENPROGRESO = "En progreso"
    FINALIZADO = "Finalizado"


def _decimal_or_zero(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def q2(value) -> Decimal:
    return _decimal_or_zero(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def q4(value) -> Decimal:
    return _decimal_or_zero(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def parse_money(value) -> Decimal:
    return q2(value)


def parse_percent(value) -> Decimal:
    return q4(value)


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


factura_impuesto = Table(
    "factura_impuesto",
    Base.metadata,
    Column("factura_id", Integer, ForeignKey("factura.id"), primary_key=True),
    Column("impuesto_id", Integer, ForeignKey("impuesto.id"), primary_key=True),
)

camion_criterio_association = Table(
    "camion_criterio_consumo",
    Base.metadata,
    Column("camion_id", Integer, ForeignKey("camion.id"), primary_key=True),
    Column("criterio_id", Integer, ForeignKey("referencia_consumo_combustible.id"), primary_key=True),
)
