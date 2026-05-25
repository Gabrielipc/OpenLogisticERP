"""Application-side identity context propagated to PostgreSQL sessions."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator  # noqa: UP035

_CURRENT_USER_ID: ContextVar[str | None] = ContextVar("openlogistic_current_user_id", default=None)


def get_authenticated_user_id() -> str | None:
    return _CURRENT_USER_ID.get()


def set_authenticated_user_id(user_id: str | None) -> Token[str | None]:
    normalized = str(user_id).strip() if user_id is not None else None
    return _CURRENT_USER_ID.set(normalized or None)


def clear_authenticated_user_id() -> None:
    _CURRENT_USER_ID.set(None)


@contextmanager
def authenticated_user(user_id: str | None) -> Iterator[None]:
    token = set_authenticated_user_id(user_id)
    try:
        yield
    finally:
        _CURRENT_USER_ID.reset(token)
