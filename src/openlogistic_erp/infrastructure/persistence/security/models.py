"""ORM models for users, roles, and permissions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))

    roles: Mapped[list[Role]] = relationship("Role", secondary="user_roles", back_populates="users")
    user_permissions: Mapped[list[UserPermission]] = relationship(
        "UserPermission",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Role(Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    users: Mapped[list[User]] = relationship("User", secondary="user_roles", back_populates="roles")
    permissions: Mapped[list[Permission]] = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (UniqueConstraint("resource", "action"),)
    roles: Mapped[list[Role]] = relationship("Role", secondary="role_permissions", back_populates="permissions")
    user_permissions: Mapped[list[UserPermission]] = relationship(
        "UserPermission",
        back_populates="permission",
        cascade="all, delete-orphan",
    )


class UserPermission(Base):
    __tablename__ = "user_permissions"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id"), primary_key=True)
    grant_or_deny: Mapped[bool] = mapped_column(Boolean, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="user_permissions")
    permission: Mapped[Permission] = relationship("Permission", back_populates="user_permissions")


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("role_name", String, ForeignKey("roles.name"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_name", String, ForeignKey("roles.name"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
)
