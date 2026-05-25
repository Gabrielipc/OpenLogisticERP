"""Persistence helpers for DB-first access."""

from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .session_identity import get_authenticated_user_id

_ENGINE_CACHE: dict[tuple[str, tuple[tuple[str, str], ...]], Engine] = {}
_SESSION_FACTORY_CACHE: dict[tuple[str, tuple[tuple[str, str], ...]], sessionmaker] = {}
_LOCK = threading.Lock()
_NON_SSL_ENVS = {"development", "dev", "staging", "test", "testing", "local"}
_SESSION_IDENTITY_INSTALLED = False
_SESSION_AUTH_CONTEXT_FLAG = "openlogistic_apply_auth_context"
_SESSION_AUTH_ROLE_FLAG = "openlogistic_apply_authenticated_role"


def build_postgres_connect_args(env: str | None = None) -> dict[str, Any]:
    normalized_env = (env or "").strip().lower()
    connect_args: dict[str, Any] = {
        "keepalives_interval": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_count": 3,
        "options": "-c idle_in_transaction_session_timeout=60000 -c statement_timeout=30000",
    }
    if normalized_env not in _NON_SSL_ENVS:
        connect_args["sslmode"] = "require"
    return connect_args


def _install_session_identity_hook() -> None:
    global _SESSION_IDENTITY_INSTALLED
    if _SESSION_IDENTITY_INSTALLED:
        return

    @event.listens_for(Session, "after_begin")
    def _apply_request_context(session, transaction, connection) -> None:
        del transaction
        if not session.info.get(_SESSION_AUTH_CONTEXT_FLAG, False):
            return
        if connection.dialect.name != "postgresql":
            return
        user_id = get_authenticated_user_id()
        if not user_id:
            return
        connection.execute(
            text(
                "select set_config('request.jwt.claim.sub', :user_id, true), "
                "set_config('request.jwt.claim.role', 'authenticated', true)"
            ),
            {"user_id": user_id},
        )
        if session.info.get(_SESSION_AUTH_ROLE_FLAG, False):
            connection.execute(text("set local role authenticated"))

    _SESSION_IDENTITY_INSTALLED = True


def _normalize_options(options: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    normalized = dict(options)
    if "connect_args" in normalized and isinstance(normalized["connect_args"], dict):
        connect_args = normalized["connect_args"]
        normalized["connect_args"] = tuple(sorted((str(k), str(v)) for k, v in connect_args.items()))
    return tuple(sorted((str(k), str(v)) for k, v in normalized.items()))


def _get_or_create_engine(
    database_url: str,
    *,
    echo: bool = False,
    pool_pre_ping: bool = True,
    pool_size: int = 10,
    max_overflow: int = 20,
    connect_args: dict[str, Any] | None = None,
    **engine_kwargs: Any,
) -> Engine:
    normalized = dict(engine_kwargs)
    normalized["pool_pre_ping"] = pool_pre_ping
    normalized["pool_size"] = pool_size
    normalized["max_overflow"] = max_overflow
    if connect_args is not None:
        normalized["connect_args"] = tuple(sorted((str(k), str(v)) for k, v in connect_args.items()))

    options_key = _normalize_options(normalized)
    cache_key = (database_url, options_key)
    if cache_key in _ENGINE_CACHE:
        return _ENGINE_CACHE[cache_key]

    with _LOCK:
        if cache_key in _ENGINE_CACHE:
            return _ENGINE_CACHE[cache_key]

        normalized_kwargs = dict(engine_kwargs)
        normalized_kwargs.setdefault("pool_recycle", 3600)
        normalized_kwargs.setdefault("pool_timeout", 30)
        normalized_kwargs.setdefault("pool_use_lifo", True)
        if connect_args is not None:
            normalized_kwargs["connect_args"] = connect_args

        engine = create_engine(
            database_url,
            echo=echo,
            pool_pre_ping=pool_pre_ping,
            pool_size=pool_size,
            max_overflow=max_overflow,
            **normalized_kwargs,
        )
        _ENGINE_CACHE[cache_key] = engine
        return engine


def _get_or_create_session_factory(database_url: str, **engine_kwargs: Any) -> sessionmaker:
    _install_session_identity_hook()
    options_key = _normalize_options(dict(engine_kwargs))
    cache_key = (database_url, options_key)

    if cache_key in _SESSION_FACTORY_CACHE:
        return _SESSION_FACTORY_CACHE[cache_key]

    with _LOCK:
        if cache_key in _SESSION_FACTORY_CACHE:
            return _SESSION_FACTORY_CACHE[cache_key]

        engine = _get_or_create_engine(database_url, **engine_kwargs)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        _SESSION_FACTORY_CACHE[cache_key] = factory
        return factory


def create_engine_and_factory(
    database_url: str,
    *,
    echo: bool = False,
    pool_pre_ping: bool = True,
    pool_size: int = 10,
    max_overflow: int = 20,
    connect_args: dict[str, Any] | None = None,
    **engine_kwargs: Any,
):
    engine_kwargs = dict(engine_kwargs)
    if connect_args is not None:
        engine_kwargs["connect_args"] = connect_args

    engine = _get_or_create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=pool_pre_ping,
        pool_size=pool_size,
        max_overflow=max_overflow,
        **engine_kwargs,
    )
    session_factory = _get_or_create_session_factory(
        database_url,
        echo=echo,
        pool_pre_ping=pool_pre_ping,
        pool_size=pool_size,
        max_overflow=max_overflow,
        **engine_kwargs,
    )
    return engine, session_factory


def with_session_auth_context(
    session_factory,
    *,
    apply_authenticated_role: bool = False,
):
    """Wrap a session factory so sessions propagate auth context into PostgreSQL."""

    def factory():
        session = session_factory()
        session.info[_SESSION_AUTH_CONTEXT_FLAG] = True
        session.info[_SESSION_AUTH_ROLE_FLAG] = bool(apply_authenticated_role)
        return session

    return factory


_install_session_identity_hook()
