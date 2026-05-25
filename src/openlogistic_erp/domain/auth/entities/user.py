"""Auth user entity."""

from dataclasses import dataclass, field


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    is_superuser: bool = False
    roles: list[str] = field(default_factory=list)
