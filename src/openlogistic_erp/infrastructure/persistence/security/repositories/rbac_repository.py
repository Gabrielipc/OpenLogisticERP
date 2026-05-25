"""RBAC repository implementation."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Sequence

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from .....domain.rbac import AuthorizationStore, PermissionCatalog, PermissionCell, PermissionRule
from .....domain.rbac import Role as DomainRole
from ..models import Permission, Role, User, UserPermission


class SqlAlchemyRbacRepository(AuthorizationStore, PermissionCatalog):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def _new_session(self) -> Session:
        return self._session_factory()

    def list_roles(self) -> list[DomainRole]:
        with self._new_session() as session:
            rows = session.execute(select(Role).order_by(Role.name.asc())).scalars().all()
            return [
                DomainRole(
                    name=row.name,
                    permissions=[PermissionCell(resource=p.resource, action=p.action, granted=True) for p in row.permissions],
                )
                for row in rows
            ]

    def create_role(self, role_name: str) -> DomainRole:
        normalized = str(role_name or "").strip()
        if not normalized:
            raise ValueError("El nombre del rol es requerido")
        with self._new_session() as session:
            existing = session.get(Role, normalized)
            if existing is not None:
                raise ValueError(f"Rol '{normalized}' ya existe")
            role = Role(name=normalized)
            session.add(role)
            session.commit()
            return DomainRole(name=role.name, permissions=[])

    def delete_role(self, role_name: str) -> None:
        normalized = str(role_name or "").strip()
        if not normalized:
            raise ValueError("El nombre del rol es requerido")
        with self._new_session() as session:
            role = session.get(Role, normalized)
            if role is None:
                raise ValueError(f"Rol '{normalized}' no existe")
            assigned_count = session.scalar(
                select(func.count()).select_from(User).join(User.roles).where(Role.name == normalized)
            )
            if int(assigned_count or 0) > 0:
                raise ValueError(f"El rol '{normalized}' esta asignado a usuarios")
            session.delete(role)
            session.commit()

    def get_role_permissions(self, role_name: str) -> list[PermissionCell]:
        with self._new_session() as session:
            role = session.execute(select(Role).where(Role.name == role_name)).scalar_one()
            return [PermissionCell(resource=p.resource, action=p.action, granted=True) for p in role.permissions]

    def set_role_permissions(self, role_name: str, permissions: Sequence[PermissionCell]) -> None:
        with self._new_session() as session:
            role = session.execute(select(Role).where(Role.name == role_name)).scalar_one()
            normalized = self._normalize_permission_cells(permissions)
            resolved = self._load_permission_lookup(session, normalized)
            role.permissions = [resolved[pair] for pair in normalized]
            session.commit()

    def assign_roles_to_user(self, username: str, role_names: Iterable[str], replace: bool = True) -> None:
        role_names = list(role_names)
        with self._new_session() as session:
            user = session.execute(select(User).where(User.username == username)).scalar_one()
            roles = self._load_roles(session, role_names)

            if replace:
                user.roles.clear()

            existing_names = {role.name for role in user.roles}
            for name, role in roles.items():
                if name not in existing_names:
                    user.roles.append(role)
            session.commit()

    def set_user_permissions(self, username: str, permissions: list[PermissionCell]) -> None:
        with self._new_session() as session:
            user = session.execute(select(User).where(User.username == username)).scalar_one()
            normalized = self._normalize_permission_cells(permissions)
            resolved = self._load_permission_lookup(session, normalized)

            user.user_permissions = []
            session.flush()
            user.user_permissions = [
                UserPermission(user=user, permission=resolved[pair], grant_or_deny=granted)
                for pair, granted in normalized.items()
            ]
            session.commit()

    def set_user_permission_states(self, username: str, permission_states: Sequence[PermissionCell]) -> None:
        with self._new_session() as session:
            user = session.execute(select(User).where(User.username == username)).scalar_one()
            normalized = self._normalize_permission_cells(permission_states)
            resolved = self._load_permission_lookup(session, normalized)
            user.user_permissions = []
            session.flush()
            user.user_permissions = [
                UserPermission(user=user, permission=resolved[pair], grant_or_deny=granted)
                for pair, granted in normalized.items()
            ]
            session.commit()

    def read_profile(self, username: str) -> dict:
        with self._new_session() as session:
            user = session.execute(select(User).where(User.username == username)).scalar_one()
            overrides = {
                f"{up.permission.resource}:{up.permission.action}": up.grant_or_deny
                for up in user.user_permissions
            }
            return {
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "is_superuser": user.is_superuser,
                },
                "roles": [role.name for role in user.roles],
                "overrides": overrides,
            }

    def available_permissions(self) -> list[PermissionRule]:
        with self._new_session() as session:
            permissions = session.execute(
                select(Permission).order_by(Permission.resource.asc(), Permission.action.asc())
            ).scalars().all()
            return [PermissionRule(resource=row.resource, action=row.action) for row in permissions]

    def _normalize_permission_cells(self, permissions: Sequence[PermissionCell]) -> OrderedDict[tuple[str, str], bool]:
        normalized: OrderedDict[tuple[str, str], bool] = OrderedDict()
        for cell in permissions:
            key = (cell.resource, cell.action)
            if not cell.resource or not cell.action:
                raise ValueError("Permiso inv�lido: recurso y acci�n son obligatorios")
            normalized[key] = bool(cell.granted)
        return normalized

    def _load_permission_lookup(
        self,
        session: Session,
        cells: dict[tuple[str, str], bool],
    ) -> OrderedDict[tuple[str, str], Permission]:
        pairs = list(cells.keys())
        if not pairs:
            return OrderedDict()

        found = self._load_permissions(session, pairs)
        missing = [pair for pair in pairs if pair not in found]
        if missing:
            raise ValueError(f"Permiso faltante: {missing}")

        return OrderedDict((pair, found[pair]) for pair in pairs)

    def _load_permissions(self, session: Session, pairs: Sequence[tuple[str, str]]) -> dict[tuple[str, str], Permission]:
        loaded = session.execute(select(Permission).where(tuple_(Permission.resource, Permission.action).in_(pairs))).scalars().all()
        return {(permission.resource, permission.action): permission for permission in loaded}

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
