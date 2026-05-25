"""RBAC module entry points."""

from .factories import build_rbac_module
from .permissions import PermissionConfig, compile_permissions
from .services import RbacPermissionService
from .use_cases.assign_roles import AssignRolesUseCase
from .use_cases.save_role_permissions import SaveRolePermissionsUseCase
from .use_cases.seed_permissions import SeedPermissionsUseCase
from .use_cases.update_user_overrides import UpdateUserOverridesUseCase

__all__ = [
    "PermissionConfig",
    "compile_permissions",
    "RbacPermissionService",
    "AssignRolesUseCase",
    "SaveRolePermissionsUseCase",
    "SeedPermissionsUseCase",
    "UpdateUserOverridesUseCase",
    "build_rbac_module",
]
