"""Auth module service orchestrating authentication + user flows."""

from dataclasses import dataclass

from ...domain.auth.entities.auth_result import AuthResult
from ...domain.auth.repositories.user_read_write import UserRepository
from .use_cases.authenticate_user import AuthenticateUserUseCase, LoginInput
from .use_cases.create_user import CreateUserUseCase
from .use_cases.list_users import ListUsersUseCase


@dataclass(frozen=True)
class AuthModuleService:
    repository: UserRepository

    def __post_init__(self) -> None:
        object.__setattr__(self, "_authenticate", AuthenticateUserUseCase(self.repository))
        object.__setattr__(self, "_list_users", ListUsersUseCase(self.repository))
        object.__setattr__(self, "_create_user", CreateUserUseCase(self.repository))

    def authenticate(self, username: str, password: str) -> AuthResult:
        return self._authenticate.execute(LoginInput(username=username, password=password))

    def list_users(self) -> list:
        return self._list_users.execute()

    def create_user(
        self,
        username: str,
        password: str,
        is_superuser: bool = False,
        roles: list[str] | None = None,
    ):
        return self._create_user.execute(
            username=username,
            password=password,
            is_superuser=is_superuser,
            roles=list(roles or []),
        )

    def update_user_roles(self, username: str, roles: list[str] | None = None) -> None:
        self.repository.set_user_roles(username=username, roles=list(roles or []))

    def set_user_superuser(self, username: str, is_superuser: bool) -> None:
        self.repository.set_user_superuser(username=username, is_superuser=is_superuser)

    def read_user_profile(self, username: str) -> dict:
        user = self.repository.find_user(username)
        if user is None:
            raise ValueError(f"Usuario '{username}' no existe")
        return {
            "id": user.id,
            "username": user.username,
            "is_superuser": user.is_superuser,
            "roles": list(user.roles),
        }
