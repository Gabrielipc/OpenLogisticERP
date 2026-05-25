"""Auth composition helpers."""

from ...domain.auth.repositories.user_read_write import UserRepository as AuthUserRepository
from .services import AuthModuleService


def build_auth_module(user_repository: AuthUserRepository) -> AuthModuleService:
    return AuthModuleService(user_repository)
