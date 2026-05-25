"""Declarative layout metadata for generic catalog forms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FormLayoutFieldItem:
    field_name: str
    span: int = 1
    full_width: bool = False

    def __post_init__(self) -> None:
        normalized_name = str(self.field_name or "").strip()
        if not normalized_name:
            raise ValueError("field_name es requerido para layout items de campo")
        object.__setattr__(self, "field_name", normalized_name)
        normalized_span = 2 if self.full_width else max(1, int(self.span or 1))
        object.__setattr__(self, "span", min(2, normalized_span))
        if normalized_span >= 2:
            object.__setattr__(self, "full_width", True)


@dataclass(frozen=True)
class FormLayoutSectionItem:
    title: str
    item_type: Literal["section"] = "section"

    def __post_init__(self) -> None:
        normalized_title = str(self.title or "").strip()
        if not normalized_title:
            raise ValueError("title es requerido para layout items de seccion")
        object.__setattr__(self, "title", normalized_title)


FormLayoutItem = FormLayoutFieldItem | FormLayoutSectionItem


@dataclass(frozen=True)
class FormLayoutDefinition:
    items: tuple[FormLayoutItem, ...] = ()
