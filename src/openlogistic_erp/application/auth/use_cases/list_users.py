"""List users use case."""

from ....domain.auth.entities.user import User
from ....domain.auth.repositories.user_read_write import UserRepository


class ListUsersUseCase:
    def __init__(self, repository: UserRepository):
        self._repository = repository

    def execute(self) -> list[User]:
        return self._repository.list_users()
