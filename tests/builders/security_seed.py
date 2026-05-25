from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from openlogistic_erp.infrastructure.persistence.security.models import Permission, Role


def unique_value(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def create_permission(session, resource: str, action: str) -> Permission:
    existing = session.execute(
        select(Permission).where(
            Permission.resource == resource,
            Permission.action == action,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    permission = Permission(resource=resource, action=action)
    session.add(permission)
    session.flush()
    return permission


def create_role(session, name: str | None = None, permissions: list[Permission] | None = None) -> Role:
    role = Role(name=name or unique_value("role"))
    if permissions:
        role.permissions.extend(permissions)
    session.add(role)
    session.flush()
    return role
