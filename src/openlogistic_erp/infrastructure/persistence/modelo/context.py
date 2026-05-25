"""Model module database context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..database import create_engine_and_factory, with_session_auth_context


@dataclass(frozen=True)
class ModeloDataContext:
    engine_url: str
    engine_kwargs: dict[str, Any] | None = None

    def session_factory(self):
        """Create a SQLAlchemy session factory for legacy Modelo entities."""
        engine_kwargs = dict(self.engine_kwargs or {})
        engine_kwargs.setdefault("pool_pre_ping", True)
        _, session_factory = create_engine_and_factory(self.engine_url, **engine_kwargs)
        return with_session_auth_context(session_factory, apply_authenticated_role=True)
