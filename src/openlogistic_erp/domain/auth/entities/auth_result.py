"""Authentication result object."""

from dataclasses import dataclass

from .user import User


@dataclass(frozen=True)
class AuthResult:
    user: User | None
    message: str = ""
