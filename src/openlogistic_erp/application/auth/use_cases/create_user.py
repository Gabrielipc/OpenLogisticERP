"""Create user use case."""

from collections.abc import Iterable

from passlib.hash import bcrypt

from ....domain.auth.entities.user import User
from ....domain.auth.repositories.user_read_write import UserRepository


class CreateUserUseCase:
    def __init__(self, repository: UserRepository):
        self._repository = repository

    def execute(
        self,
        username: str,
        password: str,
        is_superuser: bool = False,
        roles: Iterable[str] | None = None,
    ) -> User:
        hashed = bcrypt.hash(password)
        return self._repository.create_user(
            username=username,
            password_hash=hashed,
            is_superuser=is_superuser,
            roles=list(roles or []),
        )
