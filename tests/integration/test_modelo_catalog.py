from __future__ import annotations

import pytest
from uuid import uuid4

from openlogistic_erp.application.modelo.contracts import (
    InvalidIdentifierError,
    InvalidPayloadError,
    WorkflowRequiredError,
)


def test_catalog_list_models_includes_known_entities(modelo_workflow):
    models = modelo_workflow.catalog.list_models()

    assert "cliente" in models
    assert "viaje" in models
    assert "factura" in models



def test_catalog_cliente_crud(modelo_workflow):
    created = modelo_workflow.catalog.create(
        "cliente",
        {
            "nombre": "Cliente Catálogo",
            "ruc": "J031000000001",
            "direccion": "Managua",
            "facturable": True,
        },
    )

    assert created["id"] > 0

    fetched = modelo_workflow.catalog.get("cliente", created["id"])
    assert fetched["nombre"] == "Cliente Catálogo"

    listed = modelo_workflow.catalog.list("cliente", {"ruc": "J031000000001"})
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]

    updated = modelo_workflow.catalog.update(
        "cliente",
        created["id"],
        {
            "direccion": "Leon",
            "facturable": False,
        },
    )
    assert updated["direccion"] == "Leon"
    assert updated["facturable"] is False

    deleted = modelo_workflow.catalog.delete("cliente", created["id"])
    assert deleted is True
    assert modelo_workflow.catalog.get("cliente", created["id"]) is None



def test_catalog_rejects_protected_models(modelo_workflow):
    with pytest.raises(WorkflowRequiredError):
        modelo_workflow.catalog.create("viaje", {"descripcion": "no permitido"})



def test_catalog_rejects_invalid_identifier(modelo_workflow):
    with pytest.raises(InvalidIdentifierError):
        modelo_workflow.catalog.get("cliente", 0)



def test_catalog_rejects_invalid_payload(modelo_workflow):
    with pytest.raises(InvalidPayloadError):
        modelo_workflow.catalog.create("cliente", ["dato-invalido"])


def test_catalog_service_accepts_typed_strings_for_integer_and_percent_fields(modelo_workflow):
    token = uuid4().hex[:8].upper()

    camion = modelo_workflow.catalog.create(
        "camion",
        {
            "placa": f"M{token}",
            "marca": "Freightliner",
            "color": "Blanco",
            "motor": f"MOTOR-{token}",
            "chasis": f"CHASIS-{token}",
            "anio": "2026",
            "estado": "Activo",
        },
    )
    impuesto = modelo_workflow.catalog.create(
        "impuesto",
        {
            "codigo": f"IMP-{token}",
            "tipo": "IVA",
            "porcentaje": "15.25",
        },
    )

    assert camion["anio"] == 2026
    assert str(impuesto["porcentaje"]).startswith("15.25")
