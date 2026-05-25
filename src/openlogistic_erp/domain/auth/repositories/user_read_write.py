"""Auth repository contracts for identity and credential operations."""

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from ..entities.user import User


@runtime_checkable
class UserRepository(Protocol):
    def list_users(self) -> list[User]: ...
    def find_user(self, username: str) -> User | None: ...
    def find_user_by_id(self, user_id: str) -> User | None: ...
    def create_user(
        self,
        username: str,
        password_hash: str,
        is_superuser: bool = False,
        roles: Iterable[str] | None = None,
    ) -> User: ...
    def set_user_roles(self, username: str, roles: Iterable[str]) -> None: ...
    def set_user_superuser(self, username: str, is_superuser: bool) -> None: ...
