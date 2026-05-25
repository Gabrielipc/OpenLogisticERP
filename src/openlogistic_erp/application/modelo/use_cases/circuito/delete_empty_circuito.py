"""Reusable rule to delete circuitos that no longer contain viajes."""

from __future__ import annotations

from sqlalchemy import func, select

from .....infrastructure.persistence.modelo.workflow_orm import Circuito, Viaje


class DeleteEmptyCircuitoRule:
    """Delete a circuito only when it no longer has associated viajes."""

    def delete_if_empty(self, session, circuito_id: int | None) -> bool:
        if circuito_id is None:
            return False

        remaining_viajes = session.execute(
            select(func.count()).select_from(Viaje).where(Viaje._circuito_id == int(circuito_id))
        ).scalar() or 0
        if remaining_viajes > 0:
            return False

        circuito = session.get(Circuito, int(circuito_id))
        if circuito is None:
            return False

        session.delete(circuito)
        return True
