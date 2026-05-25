"""Registry used to resolve concrete forms for a catalog screen."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .definitions import FormDefinition
from .types import FormMode


class FormRegistry:
    def __init__(self, definitions: tuple[FormDefinition, ...] = ()) -> None:
        self._definitions = list(definitions)

    @property
    def definitions(self) -> tuple[FormDefinition, ...]:
        return tuple(sorted(self._definitions, key=lambda item: item.priority, reverse=True))

    def register(self, definition: FormDefinition) -> None:
        self._definitions.append(definition)

    def resolve(
        self,
        catalog_name: str,
        *,
        mode: FormMode,
        preferred_form_id: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> FormDefinition:
        safe_context = dict(context or {})

        if preferred_form_id is not None:
            for definition in self.definitions:
                if definition.form_id == preferred_form_id and definition.supports(mode):
                    return definition

        for definition in self.definitions:
            if definition.supports(mode) and definition.matches(catalog_name, safe_context):
                return definition

        raise LookupError(f"No hay formulario registrado para Catálogo={catalog_name!r} modo={mode.value!r}")
