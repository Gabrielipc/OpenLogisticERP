"""Use case for seeding available permissions."""

from collections.abc import Sequence

from ....domain.rbac.entities.permission_rule import PermissionRule
from ....domain.rbac.repositories.permission_catalog import PermissionCatalog


class SeedPermissionsUseCase:
    def __init__(self, permission_catalog: PermissionCatalog):
        self._permission_catalog = permission_catalog

    def execute(self) -> Sequence[PermissionRule]:
        return self._permission_catalog.available_permissions()
