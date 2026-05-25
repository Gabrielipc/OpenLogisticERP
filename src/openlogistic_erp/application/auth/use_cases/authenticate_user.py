"""Use cases for authentication operations."""

from dataclasses import dataclass

from passlib.hash import bcrypt

from ....domain.auth.entities.auth_result import AuthResult
from ....domain.auth.repositories.user_read_write import UserRepository


@dataclass(frozen=True)
class LoginInput:
    username: str
    password: str


class AuthenticateUserUseCase:
    def __init__(self, repository: UserRepository):
        self._repository = repository

    def execute(self, input_data: LoginInput) -> AuthResult:
        user = self._repository.find_user(input_data.username)
        if not user:
            return AuthResult(user=None, message="Usuario no encontrado")
        ok = bcrypt.verify(input_data.password, user.password_hash)
        return AuthResult(user=user if ok else None, message="OK" if ok else "Clave incorrecta")
