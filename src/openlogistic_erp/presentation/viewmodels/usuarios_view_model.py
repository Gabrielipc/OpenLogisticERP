"""ViewModel for new auth/rbac-based user management flows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ...application.auth import AuthModuleService
from ...application.rbac import RbacPermissionService
from ...infrastructure.persistence.session_identity import clear_authenticated_user_id, set_authenticated_user_id
from ..qt import Signal, Slot
from ..viewmodels.base_view_model import BaseViewModel


class UsuariosViewModel(BaseViewModel):
    usersLoaded = Signal(list)
    authCompleted = Signal(dict)
    profileLoaded = Signal(dict)
    operationCompleted = Signal(str)
    error = Signal(str)

    def __init__(self, auth_service: AuthModuleService, rbac_service: RbacPermissionService):
        super().__init__()
        self._auth = auth_service
        self._rbac = rbac_service

    @Slot()
    def list_users(self) -> None:
        try:
            users = self._auth.list_users()
            self.usersLoaded.emit([u.username for u in users])
        except Exception as exc:
            self.error.emit(str(exc))

    @Slot(str, str)
    def login(self, username: str, password: str) -> None:
        try:
            result = self._auth.authenticate(username=username, password=password)
            if result.user is not None:
                set_authenticated_user_id(result.user.id)
            else:
                clear_authenticated_user_id()
            self.authCompleted.emit(
                {
                    "ok": result.user is not None,
                    "message": result.message,
                    "user": result.user.username if result.user else None,
                }
            )
        except Exception as exc:
            self.error.emit(str(exc))

    @Slot(str, str, bool, "QVariantList")
    def create_user(self, username: str, password: str, is_superuser: bool = False, roles: Iterable[str] = ()) -> None:
        try:
            user = self._auth.create_user(
                username=username,
                password=password,
                is_superuser=is_superuser,
                roles=[str(role) for role in roles],
            )
            self.operationCompleted.emit(user.username)
        except Exception as exc:
            self.error.emit(str(exc))

    @Slot(str, "QVariantMap")
    def update_permissions(self, username: str, selection: Mapping[str, Iterable[str]]) -> None:
        try:
            normalized_selection = {
                str(model_name): [str(permission) for permission in permissions]
                for model_name, permissions in selection.items()
            }
            profile = self._rbac.update_user_overrides(
                username=username,
                canonical_selection=normalized_selection,
            )
            self.profileLoaded.emit({"username": username, "models": profile})
        except Exception as exc:
            self.error.emit(str(exc))
