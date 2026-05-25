"""Use case for assigning roles to users."""

from collections.abc import Iterable

from ....domain.rbac.repositories.authorization_store import AuthorizationStore


class AssignRolesUseCase:
    def __init__(self, authorization_store: AuthorizationStore):
        self._authorization_store = authorization_store

    def execute(self, username: str, role_names: Iterable[str], replace: bool = True) -> None:
        self._authorization_store.assign_roles_to_user(
            username=username,
            role_names=list(role_names),
            replace=replace,
        )
