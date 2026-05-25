"""Helpers to translate SQLAlchemy integrity errors into UI-safe messages."""

from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError

from .....shared.errors import PersistenceConstraintError

_UNIQUE_VIOLATION = "23505"
_FOREIGN_KEY_VIOLATION = "23503"
_NOT_NULL_VIOLATION = "23502"

_KEY_DETAIL_RE = re.compile(r"Key \((?P<fields>[^)]+)\)=\((?P<values>.*?)\)")
_NOT_NULL_RE = re.compile(r'null value in column "(?P<field>[^"]+)" violates not-null constraint', re.IGNORECASE)


def translate_integrity_error(model_name: str, error: IntegrityError) -> PersistenceConstraintError:
    """Convert a database integrity error into a presentation-safe exception."""

    detail = _error_detail(error)
    primary = _error_primary_message(error)
    code = _error_code(error)

    if code == _UNIQUE_VIOLATION or "duplicate key value" in primary.lower():
        fields = _fields_from_key_detail(detail)
        return _build_unique_error(fields)

    if code == _FOREIGN_KEY_VIOLATION or "violates foreign key constraint" in primary.lower():
        fields = _fields_from_key_detail(detail)
        return _build_foreign_key_error(fields)

    if code == _NOT_NULL_VIOLATION or "not-null constraint" in primary.lower():
        field_name = _field_from_not_null(primary)
        return _build_not_null_error(field_name)

    return PersistenceConstraintError(
        "No se pudo guardar el registro por una restriccion de datos.",
        error_code="integrity",
    )


def _build_unique_error(fields: tuple[str, ...]) -> PersistenceConstraintError:
    if len(fields) == 1:
        field_name = fields[0]
        return PersistenceConstraintError(
            f"El campo '{field_name}' debe ser unico. Ya existe otro registro con ese valor.",
            field_errors={field_name: "Ya existe otro registro con este valor."},
            error_code="unique",
            fields=fields,
        )

    if fields:
        return PersistenceConstraintError(
            "Ya existe otro registro con esa combinacion de valores.",
            field_errors={field_name: "Esta combinacion ya existe en otro registro." for field_name in fields},
            error_code="unique",
            fields=fields,
        )

    return PersistenceConstraintError(
        "Ya existe otro registro con un valor que debe ser unico.",
        error_code="unique",
    )


def _build_foreign_key_error(fields: tuple[str, ...]) -> PersistenceConstraintError:
    if len(fields) == 1:
        field_name = fields[0]
        return PersistenceConstraintError(
            f"El campo '{field_name}' debe referenciar un registro valido.",
            field_errors={field_name: "Selecciona un registro valido."},
            error_code="foreign_key",
            fields=fields,
        )

    if fields:
        return PersistenceConstraintError(
            "Uno o mas campos referencian registros que no existen.",
            field_errors={field_name: "Selecciona un registro valido." for field_name in fields},
            error_code="foreign_key",
            fields=fields,
        )

    return PersistenceConstraintError(
        "No se pudo guardar el registro porque una referencia no existe.",
        error_code="foreign_key",
    )


def _build_not_null_error(field_name: str | None) -> PersistenceConstraintError:
    if field_name:
        return PersistenceConstraintError(
            f"El campo '{field_name}' es obligatorio.",
            field_errors={field_name: "Este campo es obligatorio."},
            error_code="not_null",
            fields=(field_name,),
        )

    return PersistenceConstraintError(
        "Falta un campo obligatorio para guardar el registro.",
        error_code="not_null",
    )


def _fields_from_key_detail(detail: str) -> tuple[str, ...]:
    match = _KEY_DETAIL_RE.search(detail)
    if match is None:
        return ()
    fields = [
        field_name.strip().strip('"')
        for field_name in match.group("fields").split(",")
        if field_name.strip()
    ]
    return tuple(dict.fromkeys(fields))


def _field_from_not_null(message: str) -> str | None:
    match = _NOT_NULL_RE.search(message)
    if match is None:
        return None
    field_name = match.group("field").strip()
    return field_name or None


def _error_code(error: IntegrityError) -> str:
    original = getattr(error, "orig", None)
    return str(getattr(original, "pgcode", "") or getattr(original, "sqlstate", "") or "").strip()


def _error_detail(error: IntegrityError) -> str:
    original = getattr(error, "orig", None)
    diag = getattr(original, "diag", None)
    candidates = (
        getattr(diag, "message_detail", None),
        getattr(diag, "detail", None),
        _error_primary_message(error),
        str(original) if original is not None else "",
        str(error),
    )
    return _first_text(candidates)


def _error_primary_message(error: IntegrityError) -> str:
    original = getattr(error, "orig", None)
    diag = getattr(original, "diag", None)
    candidates = (
        getattr(diag, "message_primary", None),
        getattr(diag, "message_detail", None),
        str(original) if original is not None else "",
        str(error),
    )
    return _first_text(candidates)


def _first_text(candidates: tuple[object, ...]) -> str:
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return ""
