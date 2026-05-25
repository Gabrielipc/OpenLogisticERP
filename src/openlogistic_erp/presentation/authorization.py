"""Presentation authorization helpers for RBAC-aware view models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..application.rbac import RbacPermissionService

_ACTION_LABELS = {
    "crear": "crear",
    "leer": "leer",
    "modificar": "modificar",
    "eliminar": "eliminar",
}

_UI_TO_RBAC_ACTIONS = {
    "read": "leer",
    "list": "leer",
    "detail": "leer",
    "open": "leer",
    "create": "crear",
    "edit": "modificar",
    "update": "modificar",
    "save": "modificar",
    "close": "modificar",
    "reopen": "modificar",
    "delete": "eliminar",
}


class PresentationAuthorizationService:
    """Caches the authenticated user's effective permissions for presentation code."""

    def __init__(self, rbac_service: RbacPermissionService | None = None) -> None:
        self._rbac_service = rbac_service
        self._username = ""
        self._is_superuser = False
        self._permissions: dict[str, set[str]] = {}

    @property
    def username(self) -> str:
        return self._username

    @property
    def is_superuser(self) -> bool:
        return self._is_superuser

    def authenticate(self, username: str) -> None:
        if self._rbac_service is None:
            self.clear()
            return
        normalized_username = str(username or "").strip()
        if not normalized_username:
            self.clear()
            return

        profile = self._rbac_service.read_profile(normalized_username)
        self._username = normalized_username
        self._is_superuser = bool(profile.get("user", {}).get("is_superuser", False))
        self._permissions = self._compile_profile_permissions(profile)

    def clear(self) -> None:
        self._username = ""
        self._is_superuser = False
        self._permissions = {}

    def can(self, resource: str, action: str) -> bool:
        normalized_resource = self._normalize_resource(resource)
        normalized_action = self._normalize_action(action)
        if not normalized_resource or not normalized_action:
            return False
        if self._is_superuser:
            return True
        return normalized_action in self._permissions.get(normalized_resource, set())

    def require(self, resource: str, action: str) -> None:
        if self.can(resource, action):
            return
        normalized_resource = self._normalize_resource(resource)
        normalized_action = self._normalize_action(action)
        action_label = _ACTION_LABELS.get(normalized_action, normalized_action or str(action or ""))
        raise PermissionError(f"No tienes permiso para {action_label} {normalized_resource}")

    def resource_permissions(self, resource: str) -> dict[str, bool]:
        return {
            "read": self.can(resource, "read"),
            "create": self.can(resource, "create"),
            "edit": self.can(resource, "edit"),
            "delete": self.can(resource, "delete"),
        }

    def _compile_profile_permissions(self, profile: Mapping[str, Any]) -> dict[str, set[str]]:
        permissions: dict[str, set[str]] = {}
        role_names = {str(role_name) for role_name in profile.get("roles", []) if str(role_name or "").strip()}
        if role_names and self._rbac_service is not None:
            for role in self._rbac_service.list_roles():
                if role.name not in role_names:
                    continue
                for cell in role.permissions:
                    if cell.granted:
                        permissions.setdefault(self._normalize_resource(cell.resource), set()).add(
                            self._normalize_action(cell.action)
                        )

        overrides = profile.get("overrides", {})
        if isinstance(overrides, Mapping):
            for key, granted in overrides.items():
                resource, action = self._split_permission_key(str(key))
                if not resource or not action:
                    continue
                actions = permissions.setdefault(resource, set())
                if bool(granted):
                    actions.add(action)
                else:
                    actions.discard(action)
        return {resource: actions for resource, actions in permissions.items() if actions}

    @staticmethod
    def _split_permission_key(key: str) -> tuple[str, str]:
        if ":" not in key:
            return "", ""
        resource, action = key.split(":", 1)
        return (
            PresentationAuthorizationService._normalize_resource(resource),
            PresentationAuthorizationService._normalize_action(action),
        )

    @staticmethod
    def _normalize_resource(resource: str) -> str:
        return str(resource or "").strip().lower()

    @staticmethod
    def _normalize_action(action: str) -> str:
        normalized = str(action or "").strip().lower()
        return _UI_TO_RBAC_ACTIONS.get(normalized, normalized)
