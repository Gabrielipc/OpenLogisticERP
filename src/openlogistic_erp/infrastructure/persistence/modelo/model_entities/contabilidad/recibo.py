"""Recibos."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship, validates

from ..base import Base, EstadoRecibo, Moneda, _to_decimal, parse_money, q2, q4


class Recibo(Base):
    __tablename__ = "recibo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referencia = Column(String, nullable=False)
    fecha_emision = Column(DateTime, default=datetime.now, nullable=False)
    cliente_id = Column(Integer, ForeignKey("cliente.id"), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)
    estado = Column(Enum(EstadoRecibo), default=EstadoRecibo.ACTIVO, nullable=False)
    moneda = Column(Enum(Moneda), default=Moneda.USD, nullable=False)
    tasa_cambio = Column(Numeric(10, 4), nullable=False, default=Decimal("1.0000"))

    cliente = relationship("Cliente", back_populates="recibos")
    recibos_facturas = relationship("ReciboFactura", back_populates="recibo", cascade="all, delete-orphan")
    facturas = relationship("Factura", secondary="recibo_factura", back_populates="recibos", viewonly=True)

    @property
    def saldo_disponible(self) -> Decimal:
        monto_utilizado = sum(
            self.convert_to_recibo_currency(rf.monto_pagado, getattr(rf.factura, "moneda", self.moneda))
            for rf in self.recibos_facturas
        )
        monto_total = _to_decimal(self.monto) or Decimal("0")
        saldo = monto_total - monto_utilizado
        if saldo < 0:
            saldo = Decimal("0")
        return q2(saldo)

    def convert_to_recibo_currency(self, amount, source_currency) -> Decimal:
        value = parse_money(amount)
        recibo_currency = self._currency_value(self.moneda)
        normalized_source = self._currency_value(source_currency)
        rate = q4(self.tasa_cambio)
        if rate <= Decimal("0"):
            raise ValueError("La tasa de cambio debe ser mayor que cero.")
        if normalized_source == recibo_currency:
            return q2(value)
        if normalized_source == Moneda.USD.value and recibo_currency == Moneda.NIO.value:
            return q2(value * rate)
        if normalized_source == Moneda.NIO.value and recibo_currency == Moneda.USD.value:
            return q2(value / rate)
        return q2(value)

    def convert_from_recibo_currency(self, amount, target_currency) -> Decimal:
        value = parse_money(amount)
        recibo_currency = self._currency_value(self.moneda)
        normalized_target = self._currency_value(target_currency)
        rate = q4(self.tasa_cambio)
        if rate <= Decimal("0"):
            raise ValueError("La tasa de cambio debe ser mayor que cero.")
        if normalized_target == recibo_currency:
            return q2(value)
        if recibo_currency == Moneda.USD.value and normalized_target == Moneda.NIO.value:
            return q2(value * rate)
        if recibo_currency == Moneda.NIO.value and normalized_target == Moneda.USD.value:
            return q2(value / rate)
        return q2(value)

    @staticmethod
    def _currency_value(value) -> str:
        if isinstance(value, Moneda):
            return value.value
        return str(value or Moneda.NIO.value)

    @validates("monto")
    def validate_monto(self, _, value):
        return parse_money(value)

    @validates("tasa_cambio")
    def validate_exchange_rate(self, _, value):
        normalized = q4(value)
        if normalized <= Decimal("0"):
            raise ValueError("La tasa de cambio debe ser mayor que cero.")
        return normalized


