"""Auth-specific repository implementation."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .....domain.auth.entities.user import User as DomainUser
from .....domain.auth.repositories.user_read_write import UserRepository
from ..models import Role, User


class SqlAlchemyAuthRepository(UserRepository):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def _new_session(self) -> Session:
        return self._session_factory()

    def list_users(self) -> list[DomainUser]:
        with self._new_session() as session:
            rows = session.execute(select(User).order_by(User.username.asc())).scalars().all()
            return [self._to_domain_user(row) for row in rows]

    def find_user(self, username: str) -> DomainUser | None:
        with self._new_session() as session:
            row = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
            return self._to_domain_user(row) if row else None

    def find_user_by_id(self, user_id: str) -> DomainUser | None:
        with self._new_session() as session:
            row = session.get(User, user_id)
            return self._to_domain_user(row) if row else None

    def create_user(
        self,
        username: str,
        password_hash: str,
        is_superuser: bool = False,
        roles: Iterable[str] | None = None,
    ) -> DomainUser:
        with self._new_session() as session:
            existing = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
            if existing is not None:
                raise ValueError(f"Usuario '{username}' ya existe")

            user = User(username=username, password_hash=password_hash, is_superuser=is_superuser)
            role_names = list(roles or [])
            if role_names:
                user.roles = list(self._load_roles(session, role_names).values())

            session.add(user)
            session.commit()
            return self._to_domain_user(user)

    def set_user_roles(self, username: str, roles: Iterable[str]) -> None:
        with self._new_session() as session:
            user = session.execute(select(User).where(User.username == username)).scalar_one()
            user.roles = list(self._load_roles(session, roles).values())
            session.commit()

    def set_user_superuser(self, username: str, is_superuser: bool) -> None:
        with self._new_session() as session:
            user = session.execute(select(User).where(User.username == username)).scalar_one()
            user.is_superuser = bool(is_superuser)
            if is_superuser:
                user.user_permissions.clear()
            session.commit()

    def _to_domain_user(self, row: User) -> DomainUser:
        return DomainUser(
            id=str(row.id),
            username=row.username,
            password_hash=row.password_hash,
            is_superuser=row.is_superuser,
            roles=[role.name for role in row.roles],
        )

    def _load_roles(self, session: Session, role_names: Iterable[str]) -> OrderedDict[str, Role]:
        names = list(dict.fromkeys([name for name in role_names if name]))
        if not names:
            return OrderedDict()

        rows = session.execute(select(Role).where(Role.name.in_(names))).scalars().all()
        roles = OrderedDict((role.name, role) for role in rows)

        missing = [name for name in names if name not in roles]
        if missing:
            raise ValueError(f"Role(s) no existen: {missing}")
        return roles
