"""Unit-of-work helpers for single-transaction application use-cases."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


def run_in_transaction(session_factory: Callable[[], Any], fn: Callable[[Any], T]) -> T:
    """Execute ``fn`` in a new session and commit/rollback safely."""
    with SQLAlchemyUnitOfWork(session_factory=session_factory) as uow:
        return uow.execute(fn)


@dataclass
class SQLAlchemyUnitOfWork:
    """Thin UoW wrapper around a SQLAlchemy session factory."""

    session_factory: Callable[[], Any]
    _session: Any | None = None

    def __enter__(self):
        self._session = self.session_factory()
        return self

    def __exit__(self, exc_type, exc, tb):
        session = self._session
        try:
            if exc_type is not None:
                if session is not None:
                    session.rollback()
            else:
                if session is not None:
                    session.commit()
        finally:
            if session is not None:
                session.close()
            self._session = None

    @contextmanager
    def begin(self):
        with self as uow:
            yield uow.session

    def execute(self, fn):
        return self.run_in_transaction(fn)

    def run_in_transaction(self, fn):
        with self as uow:
            if uow.session is None:
                raise RuntimeError("No active session in UnitOfWork.")
            return fn(uow.session)

    @property
    def session(self):
        if self._session is None:
            raise RuntimeError("No active session. Use with-block or run_in_transaction.")
        return self._session

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
