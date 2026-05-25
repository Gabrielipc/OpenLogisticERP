"""Compiled permission matrix for convenience lookups."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CompiledPermissionMatrix:
    grants: dict[str, set[str]]

    def resource_actions(self, resource: str) -> set[str]:
        return set(self.grants.get(resource, set()))
