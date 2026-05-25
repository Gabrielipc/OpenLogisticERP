"""Use case for updating user overrides."""

from collections.abc import Iterable, Mapping

from ....domain.rbac.entities.permission_cell import PermissionCell
from ....domain.rbac.repositories.authorization_store import AuthorizationStore


class UpdateUserOverridesUseCase:
    def __init__(self, authorization_store: AuthorizationStore):
        self._authorization_store = authorization_store

    def execute(self, username: str, compiled_selection: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
        cells = [
            PermissionCell(resource=resource, action=action, granted=True)
            for resource, actions in compiled_selection.items()
            for action in actions
        ]
        self._authorization_store.set_user_permissions(username=username, permissions=cells)
        return {resource: sorted(actions) for resource, actions in compiled_selection.items()}
