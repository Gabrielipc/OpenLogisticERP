"""Use case for saving role-level permissions."""

from collections.abc import Iterable, Mapping

from ....domain.rbac.entities.permission_cell import PermissionCell
from ....domain.rbac.repositories.authorization_store import AuthorizationStore


class SaveRolePermissionsUseCase:
    def __init__(self, authorization_store: AuthorizationStore):
        self._authorization_store = authorization_store

    def execute(
        self,
        role_name: str,
        permissions: Mapping[str, Iterable[str]],
    ) -> dict[str, list[str]]:
        normalized = {
            resource: sorted(set(actions))
            for resource, actions in permissions.items()
        }
        cells = [
            PermissionCell(resource=resource, action=action, granted=True)
            for resource, actions in normalized.items()
            for action in actions
        ]
        self._authorization_store.set_role_permissions(role_name, cells)
        return normalized
