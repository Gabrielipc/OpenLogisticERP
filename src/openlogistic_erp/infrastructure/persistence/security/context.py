"""Database session primitives for security contexts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...persistence.database import create_engine_and_factory


@dataclass(frozen=True)
class SecurityDataContext:
    engine_url: str
    engine_kwargs: dict[str, Any] | None = None

    def session_factory(self):
        engine_kwargs = dict(self.engine_kwargs or {})
        engine_kwargs.setdefault("pool_pre_ping", True)
        _, session_factory = create_engine_and_factory(self.engine_url, **engine_kwargs)
        return session_factory
