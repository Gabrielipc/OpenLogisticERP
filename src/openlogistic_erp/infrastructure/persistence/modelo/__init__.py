"""Persistence exports for legacy `Modelo` module."""

from .context import ModeloDataContext
from .models import Base
from .repositories import SqlAlchemyModeloRepository

__all__ = [
    "ModeloDataContext",
    "Base",
    "SqlAlchemyModeloRepository",
]
