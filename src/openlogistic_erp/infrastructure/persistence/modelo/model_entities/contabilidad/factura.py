"""Facturas y contabilidad."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship, validates

from ..base import Base, EstadoFactura, Moneda, TipoImpuesto, _to_decimal, factura_impuesto, parse_money, q2, q4


class Factura(Base):
    __tablename__ = "factura"

    id = Column(Integer, primary_key=True, autoincrement=True)
    numero_factura = Column(String, nullable=False)
    fecha_emision = Column(DateTime, nullable=False)
    cliente_id = Column(Integer, ForeignKey("cliente.id"), nullable=False)
    dias_credito = Column(Integer, nullable=False, default=10)
    moneda = Column(Enum(Moneda), nullable=False, default=Moneda.NIO)
    _subtotal = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    _total = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tasa_cambio = Column(Numeric(10, 4), nullable=False, default=Decimal("1.0000"))
    estado = Column(Enum(EstadoFactura), default=EstadoFactura.PENDIENTE, nullable=False)

    cliente = relationship("Cliente", back_populates="facturas")
    detalles = relationship("DetalleFactura", back_populates="factura", cascade="all, delete-orphan")
    recibos_facturas = relationship("ReciboFactura", back_populates="factura", cascade="all, delete-orphan")
    impuestos = relationship("Impuesto", secondary=factura_impuesto, back_populates="facturas")
    recibos = relationship("Recibo", secondary="recibo_factura", back_populates="facturas", viewonly=True)

    @property
    def saldo_restante(self) -> Decimal:
        return self.get_saldo_restante()

    @property
    def dias_restantes(self) -> int:
        fecha_vencimiento = self.fecha_emision + timedelta(days=cast(int, self.dias_credito))
        dias_faltantes = int((fecha_vencimiento - datetime.now()).days)
        return max(dias_faltantes, 0)

    @property
    def monto_retenido(self) -> Decimal:
        porcentaje_base = Decimal("100")
        return q2(
            sum(
                (_to_decimal(self._subtotal) or Decimal("0")) * ((_to_decimal(impuesto.porcentaje) or Decimal("0")) / porcentaje_base)
                for impuesto in self.impuestos
                if impuesto.tipo == TipoImpuesto.RETENCION
            )
        )

    def get_saldo_restante(self, exclude_recibo_id: int | None = None) -> Decimal:
        pagos = sum((_to_decimal(rf.monto_pagado) or Decimal("0")) for rf in self.recibos_facturas if rf.recibo_id != exclude_recibo_id)
        total = _to_decimal(self._total) or Decimal("0")
        saldo = total - pagos
        if saldo < 0:
            saldo = Decimal("0")
        return q2(saldo)

    @validates("_subtotal", "_total")
    def validate_money(self, key, value):
        return parse_money(value)

    @validates("tasa_cambio")
    def validate_exchange_rate(self, _, value):
        return q4(value)
