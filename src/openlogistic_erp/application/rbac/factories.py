"""RBAC composition helper."""

from .services import RbacPermissionService


def build_rbac_module(authorization_store, permission_catalog) -> RbacPermissionService:
    return RbacPermissionService(
        authorization_store=authorization_store,
        permission_catalog=permission_catalog,
    )
