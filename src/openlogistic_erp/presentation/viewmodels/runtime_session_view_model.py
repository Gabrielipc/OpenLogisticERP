"""Runtime session view model for lightweight login/logout flows."""

from __future__ import annotations

from ...application.auth import AuthModuleService
from ...infrastructure.persistence.session_identity import clear_authenticated_user_id, set_authenticated_user_id
from ..authorization import PresentationAuthorizationService
from ..qt import Property, QmlNamedElement, QmlUncreatable, Signal, Slot
from .base_view_model import BaseViewModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@QmlNamedElement("RuntimeSessionViewModel")
@QmlUncreatable("RuntimeSessionViewModel instances are created in Python and injected into QML.")
class RuntimeSessionViewModel(BaseViewModel):
    authenticatedChanged = Signal(bool)
    currentUsernameChanged = Signal(str)
    rolesChanged = Signal()
    superuserChanged = Signal(bool)
    statusMessageChanged = Signal(str)
    errorMessageChanged = Signal(str)

    def __init__(
        self,
        auth_service: AuthModuleService,
        *,
        authorization_service: PresentationAuthorizationService | None = None,
    ) -> None:
        super().__init__()
        self._auth = auth_service
        self._authorization = authorization_service
        self._is_authenticated = False
        self._current_username = ""
        self._roles: list[str] = []
        self._is_superuser = False
        self._status_message = ""
        self._error_message = ""

    @Property(bool, notify=authenticatedChanged)
    def is_authenticated(self) -> bool:
        return self._is_authenticated

    @Property(str, notify=currentUsernameChanged)
    def current_username(self) -> str:
        return self._current_username

    @Property("QVariantList", notify=rolesChanged)
    def roles(self) -> list[str]:
        return list(self._roles)

    @Property(bool, notify=superuserChanged)
    def is_superuser(self) -> bool:
        return self._is_superuser

    @Property(str, notify=statusMessageChanged)
    def status_message(self) -> str:
        return self._status_message

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Slot(str, str)
    def login(self, username: str, password: str) -> None:
        normalized_username = str(username or "").strip()
        if not normalized_username or not str(password or ""):
            self._set_error_message("Usuario y clave son requeridos.")
            return

        was_authenticated = self._is_authenticated
        self.is_busy = True
        self._set_error_message("")
        clear_authenticated_user_id()
        try:
            result = self._auth.authenticate(username=normalized_username, password=password)
        except Exception as exc:
            clear_authenticated_user_id()
            self._clear_session_state()
            self._set_error_message(str(exc))
            self.is_busy = False
            return

        self.is_busy = False
        if result.user is None:
            clear_authenticated_user_id()
            self._clear_session_state()
            self._set_status_message(result.message or "No fue posible iniciar sesion.")
            self._set_error_message(result.message or "Credenciales invalidas.")
            return

        if self._authorization is not None:
            self._authorization.authenticate(result.user.username)
        set_authenticated_user_id(result.user.id)
        self._set_current_username(result.user.username)
        self._set_roles(result.user.roles)
        self._set_superuser(result.user.is_superuser)
        self._set_authenticated(True)
        if was_authenticated:
            self.authenticatedChanged.emit(True)
        self._set_status_message(result.message or f"Sesion iniciada como {result.user.username}.")
        self._set_error_message("")

    @Slot()
    def logout(self) -> None:
        clear_authenticated_user_id()
        if self._authorization is not None:
            self._authorization.clear()
        self._clear_session_state()
        self._set_status_message("Sesion cerrada.")
        self._set_error_message("")

    def _clear_session_state(self) -> None:
        if self._authorization is not None:
            self._authorization.clear()
        self._set_authenticated(False)
        self._set_current_username("")
        self._set_roles([])
        self._set_superuser(False)

    def _set_authenticated(self, value: bool) -> None:
        normalized = bool(value)
        if self._is_authenticated != normalized:
            self._is_authenticated = normalized
            self.authenticatedChanged.emit(normalized)

    def _set_current_username(self, value: str) -> None:
        normalized = str(value or "")
        if self._current_username != normalized:
            self._current_username = normalized
            self.currentUsernameChanged.emit(normalized)

    def _set_roles(self, roles: list[str]) -> None:
        normalized = [str(role) for role in roles if str(role).strip()]
        if self._roles != normalized:
            self._roles = normalized
            self.rolesChanged.emit()

    def _set_superuser(self, value: bool) -> None:
        normalized = bool(value)
        if self._is_superuser != normalized:
            self._is_superuser = normalized
            self.superuserChanged.emit(normalized)

    def _set_status_message(self, value: str) -> None:
        normalized = str(value or "")
        if self._status_message != normalized:
            self._status_message = normalized
            self.statusMessageChanged.emit(normalized)

    def _set_error_message(self, value: str) -> None:
        normalized = str(value or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)
