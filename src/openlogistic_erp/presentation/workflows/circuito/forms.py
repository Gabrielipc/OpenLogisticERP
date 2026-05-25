"""Limited edit form for Circuito workflow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....application.modelo.services import ModeloWorkflowService
from ....domain.modelo.dtos import FieldKind
from ....infrastructure.persistence.modelo.workflow_orm import EstadoCircuito
from ...catalog.definitions import FormFieldOption, GenericFormFieldDefinition
from ...catalog.forms import GenericCatalogFormViewModel
from ...qt import QmlNamedElement, QmlUncreatable

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


class _CircuitoCatalogAdapter:
    def __init__(self, workflow_service: ModeloWorkflowService) -> None:
        self._workflow_service = workflow_service

    def get(self, _catalog_name: str, record_id: int):
        return self._workflow_service.circuito.get(int(record_id))

    def update(self, _catalog_name: str, record_id: int, payload: Mapping[str, Any]):
        allowed = {"fecha_inicio", "fecha_fin", "estado"}
        data = {key: value for key, value in dict(payload).items() if key in allowed}
        return self._workflow_service.circuito.update(int(record_id), data)

    def create(self, _catalog_name: str, _payload: Mapping[str, Any]):
        raise ValueError("Los circuitos se crean desde el workflow de viajes.")


def _circuito_fields() -> tuple[GenericFormFieldDefinition, ...]:
    return (
        GenericFormFieldDefinition(
            name="fecha_inicio",
            label="Fecha inicio",
            kind=FieldKind.DATETIME.value,
            required=True,
            nullable=False,
        ),
        GenericFormFieldDefinition(
            name="fecha_fin",
            label="Fecha final",
            kind=FieldKind.DATETIME.value,
            required=False,
            nullable=True,
        ),
        GenericFormFieldDefinition(
            name="estado",
            label="Estado",
            kind=FieldKind.ENUM.value,
            required=True,
            nullable=False,
            options=tuple(FormFieldOption(value=str(member.value), label=str(member.value)) for member in EstadoCircuito),
        ),
    )


@QmlNamedElement("CircuitoBasicFormViewModel")
@QmlUncreatable("CircuitoBasicFormViewModel instances are created in Python and injected into QML.")
class CircuitoBasicFormViewModel(GenericCatalogFormViewModel):
    def __init__(self, *, workflow_service: ModeloWorkflowService) -> None:
        super().__init__(
            catalog_name="circuito",
            fields=_circuito_fields(),
            catalog_service=_CircuitoCatalogAdapter(workflow_service),
            title="Circuito",
        )
