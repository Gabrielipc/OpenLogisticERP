"""Security administration workflow view model."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ....application.auth import AuthModuleService
from ....application.rbac import RbacPermissionService
from ....application.rbac.permissions import PRIMARY_RESOURCES, RESOURCES
from ...qt import Property, QmlNamedElement, QmlUncreatable, Signal, Slot
from ...viewmodels.runtime_session_view_model import RuntimeSessionViewModel
from ..common import WorkflowDescriptor, WorkflowModuleViewModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0

DOMAIN_ORDER = ("Planificacion", "Operacion", "Tesoreria")


def _role_to_map(role: Any, permission_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    permissions = [
        {"resource": cell.resource, "action": cell.action, "granted": bool(cell.granted)}
        for cell in getattr(role, "permissions", [])
    ]
    role_map: dict[str, Any] = {"name": str(role.name), "permissions": permissions}
    if permission_rows is not None:
        role_map["permission_rows"] = permission_rows
    return role_map


def _permission_to_map(permission: Any) -> dict[str, str]:
    resource = str(permission.resource)
    return {
        "resource": resource,
        "action": str(permission.action),
        "domain": str(RESOURCES.get(resource, "")),
        "resource_label": _format_resource_label(resource),
    }


def _permission_key(resource: str, action: str) -> str:
    return f"{resource}:{action}"


def _format_resource_label(resource: str) -> str:
    return " ".join(part.capitalize() for part in str(resource or "").split("_") if part)


def _group_available_permissions(permissions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for permission in permissions:
        resource = str(permission.get("resource", ""))
        action = str(permission.get("action", ""))
        if not resource or not action or resource not in PRIMARY_RESOURCES:
            continue
        row = rows.setdefault(
            resource,
            {
                "resource": resource,
                "domain": str(permission.get("domain", "")),
                "resource_label": str(permission.get("resource_label", "")) or _format_resource_label(resource),
                "permissions": [],
            },
        )
        row["permissions"].append(
            {
                "resource": resource,
                "action": action,
                "key": _permission_key(resource, action),
            }
        )
    return sorted(
        rows.values(),
        key=lambda row: (
            DOMAIN_ORDER.index(row["domain"]) if row["domain"] in DOMAIN_ORDER else len(DOMAIN_ORDER),
            row["resource_label"],
            row["resource"],
        ),
    )


def _role_permission_rows(
    available_permissions: Sequence[Mapping[str, Any]],
    granted_permissions: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    granted_keys = {
        _permission_key(str(permission.get("resource", "")), str(permission.get("action", "")))
        for permission in granted_permissions
        if bool(permission.get("granted", True))
    }
    rows = _group_available_permissions(available_permissions)
    for row in rows:
        row_permissions = []
        for permission in row["permissions"]:
            granted = permission["key"] in granted_keys
            row_permissions.append(
                {
                    **permission,
                    "granted": granted,
                    "visual_state": "GRANTED" if granted else "NONE",
                }
            )
        row["permissions"] = row_permissions
    return rows


def _user_permission_rows(
    available_permissions: Sequence[Mapping[str, Any]],
    role_permissions: Iterable[Mapping[str, Any]],
    overrides: Mapping[str, bool],
    *,
    is_superuser: bool = False,
) -> list[dict[str, Any]]:
    inherited_keys = {
        _permission_key(str(permission.get("resource", "")), str(permission.get("action", "")))
        for permission in role_permissions
        if bool(permission.get("granted", True))
    }
    rows = _group_available_permissions(available_permissions)
    for row in rows:
        row_permissions = []
        for permission in row["permissions"]:
            key = permission["key"]
            override_value = overrides.get(key)
            inherited = key in inherited_keys
            if override_value is True:
                effective = True
                override = "grant"
                visual_state = "ALLOW_OVERRIDE"
            elif override_value is False:
                effective = False
                override = "deny"
                visual_state = "DENY"
            elif is_superuser:
                effective = True
                override = "inherit"
                visual_state = "EFFECTIVE_ROLE"
            elif inherited:
                effective = True
                override = "inherit"
                visual_state = "EFFECTIVE_ROLE"
            else:
                effective = False
                override = "inherit"
                visual_state = "NONE"
            row_permissions.append(
                {
                    **permission,
                    "effective": effective,
                    "inherited": inherited,
                    "override": override,
                    "visual_state": visual_state,
                }
            )
        row["permissions"] = row_permissions
    return rows


@QmlNamedElement("SecurityAdminViewModel")
@QmlUncreatable("SecurityAdminViewModel instances are created in Python and injected into QML.")
class SecurityAdminViewModel(WorkflowModuleViewModel):
    usersChanged = Signal()
    rolesChanged = Signal()
    availablePermissionsChanged = Signal()
    selectedUserProfileChanged = Signal()
    selectedRoleProfileChanged = Signal()
    newRoleProfileChanged = Signal()
    activePageChanged = Signal(str)
    canManageSecurityChanged = Signal(bool)
    errorMessageChanged = Signal(str)
    operationCompleted = Signal(str)

    def __init__(
        self,
        auth_service: AuthModuleService,
        rbac_service: RbacPermissionService,
        runtime_session: RuntimeSessionViewModel,
    ) -> None:
        super().__init__(
            WorkflowDescriptor(
                module_id="seguridad",
                title="Seguridad",
                domain_title="Administracion",
                summary="Administra usuarios, roles y permisos del sistema.",
                qml_component="SecurityAdminPage.qml",
            )
        )
        self._auth = auth_service
        self._rbac = rbac_service
        self._runtime_session = runtime_session
        self._users: list[dict[str, Any]] = []
        self._roles: list[dict[str, Any]] = []
        self._available_permissions: list[dict[str, str]] = []
        self._selected_user_profile: dict[str, Any] = {}
        self._selected_role_profile: dict[str, Any] = {}
        self._new_role_profile: dict[str, Any] = {}
        self._active_page = "users"
        self._error_message = ""
        self._runtime_session.superuserChanged.connect(self._handle_superuser_changed)

    @Property("QVariantList", notify=usersChanged)
    def users(self) -> list[dict[str, Any]]:
        return [dict(user) for user in self._users]

    @Property("QVariantList", notify=rolesChanged)
    def roles(self) -> list[dict[str, Any]]:
        return [dict(role) for role in self._roles]

    @Property("QVariantList", notify=availablePermissionsChanged)
    def available_permissions(self) -> list[dict[str, str]]:
        return [dict(permission) for permission in self._available_permissions]

    @Property("QVariantMap", notify=selectedUserProfileChanged)
    def selected_user_profile(self) -> dict[str, Any]:
        return dict(self._selected_user_profile)

    @Property("QVariantMap", notify=selectedRoleProfileChanged)
    def selected_role_profile(self) -> dict[str, Any]:
        return dict(self._selected_role_profile)

    @Property("QVariantMap", notify=newRoleProfileChanged)
    def new_role_profile(self) -> dict[str, Any]:
        return dict(self._new_role_profile)

    @Property(str, notify=activePageChanged)
    def active_page(self) -> str:
        return self._active_page

    @Property(bool, notify=canManageSecurityChanged)
    def can_manage_security(self) -> bool:
        return bool(self._runtime_session.is_authenticated and self._runtime_session.is_superuser)
        
    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Slot()
    def initialize(self) -> None:
        if not self._require_superuser():
            self._replace_loaded_data(users=[], roles=[], permissions=[])
            return
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        if not self._require_superuser():
            return
        self.is_busy = True
        try:
            users = [
                {
                    "id": user.id,
                    "username": user.username,
                    "is_superuser": bool(user.is_superuser),
                    "roles": list(user.roles),
                }
                for user in self._auth.list_users()
            ]
            roles = [_role_to_map(role) for role in self._rbac.list_roles()]
            permissions = [_permission_to_map(permission) for permission in self._rbac.list_available_permissions()]
            self._replace_loaded_data(users=users, roles=roles, permissions=permissions)
            self._set_error_message("")
        except Exception as exc:
            self._set_error_message(str(exc))
        finally:
            self.is_busy = False

    @Slot(str)
    def set_active_page(self, active_page: str) -> None:
        normalized = str(active_page or "").strip()
        if normalized not in {"users", "roles", "new_user", "user_detail", "new_role", "role_detail"}:
            return
        self._set_active_page(normalized)

    @Slot(str, str, bool, "QVariantList")
    def create_user(self, username: str, password: str, is_superuser: bool, roles: Iterable[str]) -> None:
        if not self._require_superuser():
            return
        try:
            normalized_roles = [str(role) for role in roles if str(role).strip()]
            user = self._auth.create_user(
                username=str(username or "").strip(),
                password=str(password or ""),
                is_superuser=bool(is_superuser),
                roles=normalized_roles,
            )
            self.refresh()
            self.select_user(user.username)
            self.operationCompleted.emit(user.username)
        except Exception as exc:
            self._set_error_message(str(exc))

    @Slot(str)
    def select_user(self, username: str) -> None:
        if not self._require_superuser():
            return
        try:
            profile = self._rbac.read_profile(str(username or "").strip())
            role_names = {str(role_name) for role_name in profile.get("roles", [])}
            role_permissions: list[dict[str, Any]] = []
            for role in self._rbac.list_roles():
                if role.name not in role_names:
                    continue
                role_permissions.extend(_role_to_map(role)["permissions"])
            user_map = dict(profile.get("user", {}))
            profile = {
                **dict(profile),
                "permission_rows": _user_permission_rows(
                    self._available_permissions,
                    role_permissions,
                    profile.get("overrides", {}),
                    is_superuser=bool(user_map.get("is_superuser", False)),
                ),
            }
            self._selected_user_profile = dict(profile)
            self.selectedUserProfileChanged.emit()
            self._set_active_page("user_detail")
            self._set_error_message("")
        except Exception as exc:
            self._set_error_message(str(exc))

    @Slot(str, "QVariantList")
    def save_user_roles(self, username: str, roles: Iterable[str]) -> None:
        if not self._require_superuser():
            return
        try:
            normalized_roles = [str(role) for role in roles if str(role).strip()]
            self._auth.update_user_roles(str(username or "").strip(), normalized_roles)
            self.refresh()
            self.select_user(username)
            self.operationCompleted.emit(str(username or ""))
        except Exception as exc:
            self._set_error_message(str(exc))

    @Slot(str, bool)
    def save_user_superuser(self, username: str, is_superuser: bool) -> None:
        if not self._require_superuser():
            return
        try:
            self._auth.set_user_superuser(str(username or "").strip(), bool(is_superuser))
            self.refresh()
            self.select_user(username)
            self.operationCompleted.emit(str(username or ""))
        except Exception as exc:
            self._set_error_message(str(exc))

    @Slot(str, "QVariantMap")
    def save_user_overrides(self, username: str, overrides: Mapping[str, Mapping[str, str]]) -> None:
        if not self._require_superuser():
            return
        try:
            self._rbac.update_user_override_states(str(username or "").strip(), overrides)
            self.select_user(username)
            self.operationCompleted.emit(str(username or ""))
        except Exception as exc:
            self._set_error_message(str(exc))

    @Slot(str)
    def create_role(self, name: str) -> None:
        if not self._require_superuser():
            return
        try:
            role = self._rbac.create_role(str(name or "").strip())
            self.refresh()
            self.select_role(role.name)
            self.operationCompleted.emit(role.name)
        except Exception as exc:
            self._set_error_message(str(exc))

    @Slot()
    def begin_create_role(self) -> None:
        if not self._require_superuser():
            return
        self._new_role_profile = self._empty_role_profile()
        self.newRoleProfileChanged.emit()
        self._set_active_page("new_role")
        self._set_error_message("")

    @Slot(str, "QVariantMap")
    def create_role_with_permissions(self, name: str, permissions: Mapping[str, Iterable[str]]) -> None:
        if not self._require_superuser():
            return
        normalized_name = str(name or "").strip()
        try:
            role = self._rbac.create_role(normalized_name)
            self._rbac.save_role_permissions(role.name, permissions)
            self.refresh()
            self.select_role(role.name)
            self.operationCompleted.emit(role.name)
        except Exception as exc:
            self._set_error_message(str(exc))

    @Slot(str)
    def select_role(self, name: str) -> None:
        if not self._require_superuser():
            return
        normalized = str(name or "").strip()
        role = next((role for role in self._rbac.list_roles() if role.name == normalized), None)
        if role is None:
            self._set_error_message(f"Rol '{normalized}' no existe")
            return
        role_map = _role_to_map(role)
        self._selected_role_profile = _role_to_map(
            role,
            _role_permission_rows(self._available_permissions, role_map["permissions"]),
        )
        self.selectedRoleProfileChanged.emit()
        self._set_active_page("role_detail")
        self._set_error_message("")

    @Slot(str, "QVariantMap")
    def save_role_permissions(self, name: str, permissions: Mapping[str, Iterable[str]]) -> None:
        if not self._require_superuser():
            return
        try:
            self._rbac.save_role_permissions(str(name or "").strip(), permissions)
            self.refresh()
            self.select_role(name)
            self.operationCompleted.emit(str(name or ""))
        except Exception as exc:
            self._set_error_message(str(exc))

    @Slot(str)
    def delete_role(self, name: str) -> None:
        if not self._require_superuser():
            return
        try:
            self._rbac.delete_role(str(name or "").strip())
            self._selected_role_profile = {}
            self.selectedRoleProfileChanged.emit()
            self.refresh()
            self._set_active_page("roles")
            self.operationCompleted.emit(str(name or ""))
        except Exception as exc:
            self._set_error_message(str(exc))

    @Slot()
    def dispose(self) -> None:
        try:
            self._runtime_session.superuserChanged.disconnect(self._handle_superuser_changed)
        except TypeError:
            pass
        super().dispose()

    def _replace_loaded_data(
        self,
        *,
        users: list[dict[str, Any]],
        roles: list[dict[str, Any]],
        permissions: list[dict[str, str]],
    ) -> None:
        self._users = users
        self._roles = roles
        self._available_permissions = permissions
        self.usersChanged.emit()
        self.rolesChanged.emit()
        self.availablePermissionsChanged.emit()

    def _empty_role_profile(self) -> dict[str, Any]:
        return {
            "name": "",
            "permissions": [],
            "permission_rows": _role_permission_rows(self._available_permissions, []),
        }

    def _require_superuser(self) -> bool:
        if self.can_manage_security:
            return True
        self._set_error_message("Se requiere usuario superuser para administrar seguridad.")
        return False

    def _set_active_page(self, value: str) -> None:
        if self._active_page != value:
            self._active_page = value
            self.activePageChanged.emit(value)

    def _set_error_message(self, value: str) -> None:
        normalized = str(value or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)

    def _handle_superuser_changed(self, value: bool) -> None:
        self.canManageSecurityChanged.emit(bool(value))
        if not value:
            self._replace_loaded_data(users=[], roles=[], permissions=[])
            self._selected_user_profile = {}
            self._selected_role_profile = {}
            self._new_role_profile = {}
            self.selectedUserProfileChanged.emit()
            self.selectedRoleProfileChanged.emit()
            self.newRoleProfileChanged.emit()
