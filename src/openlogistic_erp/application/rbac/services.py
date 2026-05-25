"""RBAC module service orchestrating permission compilation and authorization operations."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ...domain.rbac.entities.permission_cell import PermissionCell
from ...domain.rbac.repositories.authorization_store import AuthorizationStore
from ...domain.rbac.repositories.permission_catalog import PermissionCatalog
from .permissions import PermissionConfig, compile_permissions
from .use_cases.assign_roles import AssignRolesUseCase
from .use_cases.save_role_permissions import SaveRolePermissionsUseCase
from .use_cases.seed_permissions import SeedPermissionsUseCase
from .use_cases.update_user_overrides import UpdateUserOverridesUseCase


@dataclass(frozen=True)
class RbacPermissionService:
    authorization_store: AuthorizationStore
    permission_catalog: PermissionCatalog
    config: PermissionConfig | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "_assign_roles", AssignRolesUseCase(self.authorization_store))
        object.__setattr__(self, "_seed_permissions", SeedPermissionsUseCase(self.permission_catalog))
        object.__setattr__(self, "_save_role_permissions_uc", SaveRolePermissionsUseCase(self.authorization_store))
        object.__setattr__(self, "_update_user_overrides_uc", UpdateUserOverridesUseCase(self.authorization_store))

    def _effective(self, selection: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
        compiled = compile_permissions(selection, self.config)
        return {resource: sorted(actions) for resource, actions in compiled.items()}

    def compile_effective_permissions(self, selection: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
        return self._effective(selection)

    def list_available_permissions(self):
        return self._seed_permissions.execute()

    def assign_roles(self, username: str, role_names: Iterable[str], replace: bool = True) -> None:
        self._assign_roles.execute(username=username, role_names=role_names, replace=replace)

    def save_role_permissions(
        self,
        role_name: str,
        canonical_selection: Mapping[str, Iterable[str]] | dict[str, dict[str, bool]],
    ) -> dict[str, list[str]]:
        effective = self._normalize_and_compile(canonical_selection)
        return self._save_role_permissions_uc.execute(role_name=role_name, permissions=effective)

    def update_user_overrides(
        self,
        username: str,
        canonical_selection: Mapping[str, Iterable[str]] | dict[str, dict[str, bool]],
    ) -> dict[str, list[str]]:
        effective = self._normalize_and_compile(canonical_selection)
        return self._update_user_overrides_uc.execute(username=username, compiled_selection=effective)

    def update_user_override_states(
        self,
        username: str,
        override_states: Mapping[str, Mapping[str, str]],
    ) -> dict[str, dict[str, str]]:
        normalized: dict[str, dict[str, str]] = {}
        cells: list[PermissionCell] = []
        for resource, actions in override_states.items():
            resource_name = str(resource or "").strip()
            if not resource_name:
                continue
            for action, state in actions.items():
                action_name = str(action or "").strip()
                normalized_state = str(state or "inherit").strip().lower()
                if not action_name or normalized_state == "inherit":
                    continue
                if normalized_state not in {"grant", "deny"}:
                    raise ValueError(f"Estado de override invalido: {normalized_state}")
                normalized.setdefault(resource_name, {})[action_name] = normalized_state
                cells.append(
                    PermissionCell(
                        resource=resource_name,
                        action=action_name,
                        granted=normalized_state == "grant",
                    )
                )
        self.authorization_store.set_user_permission_states(username=username, permission_states=cells)
        return normalized

    def read_profile(self, username: str) -> dict:
        return self.authorization_store.read_profile(username)

    def _normalize_and_compile(
        self,
        selection: Mapping[str, Iterable[str]] | dict[str, dict[str, bool]],
    ) -> dict[str, list[str]]:
        normalized: dict[str, set[str]] = {}
        for resource, actions in selection.items():
            if isinstance(actions, dict):
                normalized[resource] = {action for action, granted in actions.items() if bool(granted)}
            else:
                normalized[resource] = {str(action) for action in actions if action}
        return self._effective(normalized)

    def list_roles(self):
        return self.authorization_store.list_roles()

    def create_role(self, role_name: str):
        return self.authorization_store.create_role(role_name)

    def delete_role(self, role_name: str) -> None:
        self.authorization_store.delete_role(role_name)
