"""Catalog of available permissions."""

from collections.abc import Sequence
from typing import Protocol

from ..entities.permission_rule import PermissionRule


class PermissionCatalog(Protocol):
    def available_permissions(self) -> Sequence[PermissionRule]: ...
