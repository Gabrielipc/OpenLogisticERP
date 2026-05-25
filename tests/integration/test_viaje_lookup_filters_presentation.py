from __future__ import annotations

from typing import Any

from openlogistic_erp.application.modelo.reference_service import ReferenceLookupService
from openlogistic_erp.domain.modelo.dtos import ReferenceOptionDTO
from openlogistic_erp.presentation.workflows.viaje.forms import ViajeFormViewModel


class _CapturingReferenceLookupRepository:
    def __init__(self) -> None:
        self.search_calls: list[dict[str, Any]] = []
        self.resolve_calls: list[dict[str, Any]] = []
        self.search_results: dict[str, tuple[ReferenceOptionDTO, ...]] = {}
        self.resolve_results: dict[str, dict[int, ReferenceOptionDTO]] = {}

    def search(self, lookup_key: str, term: str, limit: int = 20, context: dict[str, Any] | None = None):
        self.search_calls.append(
            {
                "lookup_key": lookup_key,
                "term": term,
                "limit": limit,
                "context": context,
            }
        )
        if lookup_key in self.search_results:
            return self.search_results[lookup_key]
        return (ReferenceOptionDTO(value=101, label="Demo"),)

    def resolve_ids(self, lookup_key: str, ids):
        self.resolve_calls.append({"lookup_key": lookup_key, "ids": tuple(ids)})
        if lookup_key in self.resolve_results:
            return {
                key: option
                for key, option in self.resolve_results[lookup_key].items()
                if key in {int(item) if str(item).isdigit() else item for item in ids}
            }
        return {101: ReferenceOptionDTO(value=101, label="Persistido")}


def test_viaje_form_starts_without_agregados_and_passes_lookup_context(modelo_workflow):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)

    assert form.include_agregados is False

    form.search_reference_options("conductor_id", "Ju")

    assert repository.search_calls[-1]["lookup_key"] == "viaje.conductor_id"
    assert repository.search_calls[-1]["context"] == {
        "trip_type": "Exportacion",
        "include_agregados": False,
    }

    form.set_include_agregados(True)

    assert form.include_agregados is True
    assert form.reference_options.get("conductor_id") == []

    form.search_reference_options("camion_id", "MA")

    assert repository.search_calls[-1]["lookup_key"] == "viaje.camion_id"
    assert repository.search_calls[-1]["context"] == {"include_agregados": True}


def test_viaje_form_passes_trip_type_for_conductor_lookup_when_switching_to_importacion(modelo_workflow):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    form.set_trip_type("Importacion")
    form.set_include_agregados(True)

    form.search_reference_options("conductor_id", "Ju")

    assert repository.search_calls[-1] == {
        "lookup_key": "viaje.conductor_id",
        "term": "Ju",
        "limit": 20,
        "context": {"trip_type": "Importacion", "include_agregados": True},
    }


def test_viaje_form_passes_driver_and_truck_context_for_viaje_ida_lookup(modelo_workflow):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    form.set_trip_type("Importacion")
    form.set_field_value("conductor_id", 301)
    form.set_field_value("camion_id", 402)

    form.search_reference_options("viaje_ida_id", "EXP-")

    assert repository.search_calls[-1] == {
        "lookup_key": "viaje.viaje_ida_id",
        "term": "EXP-",
        "limit": 20,
        "context": {"conductor_id": 301, "camion_id": 402},
    }


def test_viaje_form_resolves_circuito_from_selected_viaje_ida(modelo_workflow, monkeypatch):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )
    monkeypatch.setattr(
        modelo_workflow.viaje,
        "resolve_viaje_ida_circuito",
        lambda viaje_ida_id: 777 if int(viaje_ida_id) == 501 else None,
    )

    form.load(None)
    form.set_trip_type("Importacion")
    form.set_field_value("viaje_ida_id", 501)

    assert form.values["viaje_ida_id"] == 501
    assert form.values["_circuito_id"] == 777


def test_viaje_form_prime_reference_field_keeps_resolve_without_filter_context(modelo_workflow):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    form.set_field_value("conductor_id", 101)
    form.set_include_agregados(True)
    form.prime_reference_field("conductor_id")

    assert repository.resolve_calls[-1] == {
        "lookup_key": "viaje.conductor_id",
        "ids": (101,),
    }
    assert form.reference_options["conductor_id"] == [{"value": 101, "label": "Persistido"}]


def test_viaje_form_prime_reference_field_loads_initial_options_for_empty_fk(modelo_workflow):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    form.prime_reference_field("cliente_id")

    assert repository.search_calls[-1] == {
        "lookup_key": "viaje.cliente_id",
        "term": "",
        "limit": 20,
        "context": {"trip_type": "Exportacion"},
    }
    assert form.reference_options["cliente_id"] == [{"value": 101, "label": "Demo"}]


def test_viaje_form_selecting_cliente_reloads_route_options_with_cliente_context(modelo_workflow):
    repository = _CapturingReferenceLookupRepository()
    repository.search_results = {
        "viaje.cliente_id": (ReferenceOptionDTO(value=501, label="Cliente Demo"),),
        "viaje.origen_id": (ReferenceOptionDTO(value=601, label="Origen Demo"),),
        "viaje.destino_id": (ReferenceOptionDTO(value=701, label="Destino Demo"),),
    }
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    form.set_field_value("cliente_id", 501)

    assert form.values["origen_id"] == ""
    assert form.values["destino_id"] == ""
    assert form.reference_options["origen_id"] == [{"value": 601, "label": "Origen Demo"}]
    assert form.reference_options["destino_id"] == [{"value": 701, "label": "Destino Demo"}]
    assert repository.search_calls[-2]["lookup_key"] == "viaje.origen_id"
    assert repository.search_calls[-2]["context"] == {"cliente_id": 501, "destino_id": None}
    assert repository.search_calls[-1]["lookup_key"] == "viaje.destino_id"
    assert repository.search_calls[-1]["context"] == {"cliente_id": 501, "origen_id": None}


def test_viaje_form_passes_cross_route_context_to_route_lookups(modelo_workflow):
    repository = _CapturingReferenceLookupRepository()
    repository.search_results = {
        "viaje.origen_id": (ReferenceOptionDTO(value=601, label="Origen Demo"),),
        "viaje.destino_id": (ReferenceOptionDTO(value=701, label="Destino Demo"),),
    }
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    form.set_field_value("cliente_id", 501)
    form.set_field_value("origen_id", 601)

    form.search_reference_options("destino_id", "Dest")

    assert repository.search_calls[-1]["lookup_key"] == "viaje.destino_id"
    assert repository.search_calls[-1]["context"] == {"cliente_id": 501, "origen_id": 601}

    form.set_field_value("destino_id", 701)

    form.search_reference_options("origen_id", "Orig")

    assert repository.search_calls[-1]["lookup_key"] == "viaje.origen_id"
    assert repository.search_calls[-1]["context"] == {"cliente_id": 501, "destino_id": 701}


def test_viaje_form_load_create_preloads_filtered_reference_options(modelo_workflow):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)

    search_calls = {
        (call["lookup_key"], tuple(sorted((call["context"] or {}).items())))
        for call in repository.search_calls
    }

    assert ("viaje.cliente_id", (("trip_type", "Exportacion"),)) in search_calls
    assert (
        "viaje.conductor_id",
        (("include_agregados", False), ("trip_type", "Exportacion")),
    ) in search_calls
    assert ("viaje.furgon_id", (("include_agregados", False),)) in search_calls
    assert ("viaje.camion_id", (("include_agregados", False),)) in search_calls
    assert ("viaje.thermo_id", (("include_agregados", False),)) in search_calls

    assert form.reference_options["conductor_id"] == [{"value": 101, "label": "Demo"}]
    assert form.reference_options["furgon_id"] == [{"value": 101, "label": "Demo"}]
    assert form.reference_options["camion_id"] == [{"value": 101, "label": "Demo"}]
    assert form.reference_options["thermo_id"] == [{"value": 101, "label": "Demo"}]


def test_viaje_form_replaces_equipment_when_conductor_changes(modelo_workflow, monkeypatch):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    form.set_field_value("furgon_id", 11)
    form.set_field_value("camion_id", 22)
    form.set_field_value("thermo_id", 33)

    monkeypatch.setattr(
        modelo_workflow.viaje,
        "resolve_conductor_equipment_defaults",
        lambda conductor_id: {
            "furgon_id": 401,
            "camion_id": 402,
            "thermo_id": 403,
        },
    )

    form.set_field_value("conductor_id", 101)

    assert form.values["furgon_id"] == 401
    assert form.values["camion_id"] == 402
    assert form.values["thermo_id"] == 403


def test_viaje_form_keeps_equipment_lookup_options_when_conductor_autofills(modelo_workflow, monkeypatch):
    repository = _CapturingReferenceLookupRepository()
    repository.search_results = {
        "viaje.furgon_id": (
            ReferenceOptionDTO(value=401, label="Furgon asignado"),
            ReferenceOptionDTO(value=411, label="Furgon alterno"),
        ),
        "viaje.camion_id": (
            ReferenceOptionDTO(value=402, label="Camion asignado"),
            ReferenceOptionDTO(value=412, label="Camion alterno"),
        ),
        "viaje.thermo_id": (
            ReferenceOptionDTO(value=403, label="Thermo asignado"),
            ReferenceOptionDTO(value=413, label="Thermo alterno"),
        ),
    }
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    monkeypatch.setattr(
        modelo_workflow.viaje,
        "resolve_conductor_equipment_defaults",
        lambda conductor_id: {
            "furgon_id": 401,
            "camion_id": 402,
            "thermo_id": 403,
        },
    )

    form.set_field_value("conductor_id", 101)

    assert form.values["furgon_id"] == 401
    assert form.values["camion_id"] == 402
    assert form.values["thermo_id"] == 403
    assert form.reference_options["furgon_id"] == [
        {"value": 401, "label": "Furgon asignado"},
        {"value": 411, "label": "Furgon alterno"},
    ]
    assert form.reference_options["camion_id"] == [
        {"value": 402, "label": "Camion asignado"},
        {"value": 412, "label": "Camion alterno"},
    ]
    assert form.reference_options["thermo_id"] == [
        {"value": 403, "label": "Thermo asignado"},
        {"value": 413, "label": "Thermo alterno"},
    ]


def test_viaje_form_keeps_injected_equipment_ids_even_when_lookup_cannot_resolve(
    modelo_workflow,
    monkeypatch,
):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    monkeypatch.setattr(
        modelo_workflow.viaje,
        "resolve_conductor_equipment_defaults",
        lambda conductor_id: {
            "furgon_id": 901,
            "camion_id": 902,
            "thermo_id": 903,
        },
    )

    form.set_field_value("conductor_id", 101)

    assert form.values["furgon_id"] == 901
    assert form.values["camion_id"] == 902
    assert form.values["thermo_id"] == 903
    assert form.reference_options["furgon_id"][0] == {"value": 901, "label": "901"}
    assert form.reference_options["camion_id"][0] == {"value": 902, "label": "902"}
    assert form.reference_options["thermo_id"][0] == {"value": 903, "label": "903"}


def test_viaje_form_search_keeps_selected_reference_even_if_not_returned(modelo_workflow):
    repository = _CapturingReferenceLookupRepository()
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=ReferenceLookupService(repository=repository),
    )

    form.load(None)
    form.set_field_value("conductor_id", 901)
    form.search_reference_options("conductor_id", "zz")

    assert form.reference_options["conductor_id"][0] == {"value": 901, "label": "901"}
