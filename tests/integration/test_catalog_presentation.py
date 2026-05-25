from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from typing import cast
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.infrastructure.persistence.session_identity import authenticated_user
from openlogistic_erp.application.modelo.services import ModeloCatalogService
from openlogistic_erp.domain.modelo.catalog_queries import (
    CatalogFilter,
    CatalogFilterOperator,
    CatalogSort,
    CatalogSortDirection,
)
from openlogistic_erp.domain.modelo.dtos import ReferenceFieldDTO
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
from openlogistic_erp.infrastructure.persistence.modelo.repositories.integrity_errors import translate_integrity_error
from openlogistic_erp.presentation.catalog import (
    BaseFormViewModel,
    CatalogColumnDefinition,
    CatalogScreenViewModel,
    CatalogViewDefinition,
    FormLayoutDefinition,
    FormLayoutFieldItem,
    FormLayoutSectionItem,
    InMemoryCatalogTablePreferencesStore,
    FormDefinition,
    FormHostViewModel,
    FormMode,
    FormRegistry,
    GenericCatalogFormViewModel,
    GenericFormFieldDefinition,
)
from openlogistic_erp.presentation.catalog.column_overrides import (
    CatalogColumnOverride,
    apply_catalog_column_overrides,
)
from tests.builders.modelo_seed import build_factura_payload, create_camion, create_cliente, create_conductor, create_furgon, create_ruta, create_thermo, create_ubicacion
from tests.builders.security_seed import create_permission, create_role
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import Moneda
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.tarifa_flete import TarifaFlete
from openlogistic_erp.presentation.qt import QSettings, Qt
from openlogistic_erp.presentation.catalog.table_preferences import QSettingsCatalogTablePreferencesStore
from openlogistic_erp.shared.errors import PersistenceConstraintError
from tests.integration.catalog_test_support import run_action_and_wait_for_applied_load, run_action_and_wait_for_request


def _column_keys(view_definition: CatalogViewDefinition) -> tuple[str, ...]:
    return tuple(column.key for column in view_definition.columns)


def test_catalog_column_overrides_leave_catalog_without_override_unchanged():
    view_definition = CatalogViewDefinition(
        catalog_name="cliente",
        columns=(
            CatalogColumnDefinition("id", width=80, min_width=72),
            CatalogColumnDefinition("nombre", width=200, min_width=120),
        ),
    )

    resolved = apply_catalog_column_overrides(view_definition, overrides={})

    assert resolved is view_definition
    assert _column_keys(resolved) == ("id", "nombre")


def test_catalog_column_overrides_include_filters_and_orders_columns():
    view_definition = CatalogViewDefinition(
        catalog_name="cliente",
        columns=(
            CatalogColumnDefinition("id"),
            CatalogColumnDefinition("nombre"),
            CatalogColumnDefinition("ruc"),
            CatalogColumnDefinition("telefono"),
        ),
    )

    resolved = apply_catalog_column_overrides(
        view_definition,
        overrides={
            "cliente": CatalogColumnOverride(
                include=("nombre", "ruc"),
            )
        },
    )

    assert _column_keys(resolved) == ("nombre", "ruc")


def test_catalog_column_overrides_exclude_and_order_preserve_unmentioned_columns():
    view_definition = CatalogViewDefinition(
        catalog_name="viaje",
        columns=(
            CatalogColumnDefinition("id"),
            CatalogColumnDefinition("referencia"),
            CatalogColumnDefinition("descripcion"),
            CatalogColumnDefinition("estado"),
            CatalogColumnDefinition("cliente_label"),
        ),
    )

    resolved = apply_catalog_column_overrides(
        view_definition,
        overrides={
            "viaje": CatalogColumnOverride(
                exclude=("descripcion",),
                order=("referencia", "cliente_label"),
            )
        },
    )

    assert _column_keys(resolved) == ("referencia", "cliente_label", "id", "estado")


def test_catalog_column_overrides_apply_column_properties():
    view_definition = CatalogViewDefinition(
        catalog_name="cliente",
        columns=(
            CatalogColumnDefinition("nombre", header="Nombre", width=200, min_width=120),
            CatalogColumnDefinition("ruc", header="Ruc", width=140, min_width=90),
        ),
    )

    resolved = apply_catalog_column_overrides(
        view_definition,
        overrides={
            "cliente": CatalogColumnOverride(
                headers={"ruc": "RUC"},
                widths={"nombre": 260},
                min_widths={"nombre": 180},
                sortable={"ruc": False},
                resizable={"nombre": False},
            )
        },
    )

    by_key = {column.key: column for column in resolved.columns}
    assert by_key["ruc"].header == "RUC"
    assert by_key["ruc"].sortable is False
    assert by_key["nombre"].width == 260
    assert by_key["nombre"].min_width == 180
    assert by_key["nombre"].resizable is False


def test_catalog_column_overrides_reject_unknown_columns():
    view_definition = CatalogViewDefinition(
        catalog_name="cliente",
        columns=(CatalogColumnDefinition("nombre"),),
    )

    try:
        apply_catalog_column_overrides(
            view_definition,
            overrides={"cliente": CatalogColumnOverride(include=("nombre", "ruc"))},
        )
    except ValueError as exc:
        assert "cliente" in str(exc)
        assert "ruc" in str(exc)
    else:
        raise AssertionError("Expected unknown column override to raise ValueError")


def test_schema_generated_catalog_hides_id_column_but_preserves_row_identity(
    session_factory,
    modelo_workflow,
    auth_service,
):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    token = uuid4().hex[:8].upper()
    created = modelo_workflow.catalog.create(
        "cliente",
        {
            "nombre": f"Cliente Hidden Id {token}",
            "ruc": f"HIDDEN-ID-{token}",
            "direccion": f"Managua {token}",
            "facturable": True,
        },
    )
    view_definition = CatalogViewDefinition.from_schema(query_service.get_schema("cliente"))
    screen = CatalogScreenViewModel(
        view_definition=view_definition,
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(FormRegistry()),
    )

    visible_column_keys = [
        str(column["key"])
        for column in screen.columns
        if str(column.get("kind", "data")) == "data"
    ]

    assert "id" not in _column_keys(view_definition)
    assert "id" not in visible_column_keys
    assert screen.sort_field == "id"
    assert screen.sort_direction == CatalogSortDirection.DESC.value

    run_action_and_wait_for_request(
        screen,
        lambda: screen.set_filters(
            (
                CatalogFilter(field="id", operator=CatalogFilterOperator.EQ, value=int(created["id"])),
            )
        ),
    )

    assert screen.table_model.rowCount() == 1
    assert screen.record_id_at_row(0) == created["id"]
    assert screen.row_data_at(0)["id"] == created["id"]
    assert screen.table_model.row_data(0)["id"] == created["id"]


def test_catalog_screen_exposes_semantic_id_sort_options_without_visible_id_label():
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="cliente",
            columns=(CatalogColumnDefinition("nombre"), CatalogColumnDefinition("ruc")),
            default_sort=CatalogSort(field="id", direction=CatalogSortDirection.DESC),
        ),
        query_service=cast(ModeloCatalogQueryService, object()),
        catalog_service=cast(ModeloCatalogService, object()),
        form_host=FormHostViewModel(FormRegistry()),
    )

    assert screen.sort_label == "Más recientes"
    assert screen.sort_options == [
        {"label": "Más recientes", "field": "id", "direction": "desc"},
        {"label": "Más antiguos", "field": "id", "direction": "asc"},
    ]
    assert all("ID" not in option["label"] for option in screen.sort_options)


def test_default_viaje_column_override_hides_operational_detail_columns():
    view_definition = CatalogViewDefinition(
        catalog_name="viaje",
        columns=(
            CatalogColumnDefinition("referencia"),
            CatalogColumnDefinition("circuito_label"),
            CatalogColumnDefinition("temperatura"),
            CatalogColumnDefinition("viaticos_monto"),
            CatalogColumnDefinition("viaticos_moneda"),
            CatalogColumnDefinition("estado"),
        ),
    )

    resolved = apply_catalog_column_overrides(view_definition)

    assert _column_keys(resolved) == ("referencia", "estado")


class ClienteSpecializedFormViewModel(BaseFormViewModel):
    def __init__(self):
        super().__init__(title="Cliente especializado")
        self.load_calls: list[int | None] = []

    def load(self, record_id: int | None) -> None:
        self.load_calls.append(record_id)
        self._set_mode(FormMode.EDIT if record_id is not None else FormMode.CREATE)
        self._set_record_id(record_id)

    def reset(self) -> None:
        self._set_mode(FormMode.CREATE)
        self._set_record_id(None)

    def submit(self) -> Mapping[str, Any] | None:
        payload = {"id": self.record_id, "source": "specialized"}
        self.saved.emit(payload)
        return payload


class CapturingCatalogService:
    def __init__(self) -> None:
        self.created_payload: dict[str, Any] | None = None
        self.updated_payload: dict[str, Any] | None = None

    def create(self, catalog_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.created_payload = dict(payload)
        return {"id": 1, **payload}

    def update(self, catalog_name: str, record_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.updated_payload = dict(payload)
        return {"id": record_id, **payload}

    def get(self, catalog_name: str, record_id: int) -> dict[str, Any] | None:
        return None


class CapturingInvoiceExportHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[int, ...], str]] = []

    def __call__(self, record_ids, target_path: str) -> str:
        normalized_ids = tuple(int(record_id) for record_id in record_ids)
        self.calls.append((normalized_ids, str(target_path)))
        return str(target_path)


class PersistenceErroringCatalogService:
    def __init__(self) -> None:
        self.create_calls = 0

    def create(self, catalog_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.create_calls += 1
        raise PersistenceConstraintError(
            "El campo 'ruc' debe ser unico. Ya existe otro registro con ese valor.",
            field_errors={"ruc": "Ya existe otro registro con este valor."},
            error_code="unique",
            fields=("ruc",),
        )

    def update(self, catalog_name: str, record_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def get(self, catalog_name: str, record_id: int) -> dict[str, Any] | None:
        return None


class _FakeDiag:
    def __init__(self, *, message_primary: str, message_detail: str) -> None:
        self.message_primary = message_primary
        self.message_detail = message_detail


class _FakeDBAPIIntegrityError(Exception):
    def __init__(self, *, pgcode: str, message_primary: str, message_detail: str) -> None:
        super().__init__(message_primary)
        self.pgcode = pgcode
        self.diag = _FakeDiag(message_primary=message_primary, message_detail=message_detail)


def test_catalog_screen_uses_generic_form_and_refreshes_after_save(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    fields = (
        GenericFormFieldDefinition(name="nombre", required=True),
        GenericFormFieldDefinition(name="ruc", required=True),
        GenericFormFieldDefinition(name="direccion", required=True),
        GenericFormFieldDefinition(name="facturable", field_type="bool", default=True),
    )
    registry = FormRegistry(
        (
            FormDefinition(
                form_id="generic-catalog",
                qml_component="GenericCatalogForm.qml",
                view_model_factory=lambda catalog_name, mode, context: GenericCatalogFormViewModel(
                    catalog_name=catalog_name,
                    fields=context["view_definition"].generic_form_fields,
                    catalog_service=modelo_workflow.catalog,
                ),
                priority=0,
            ),
        )
    )
    form_host = FormHostViewModel(registry)
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="cliente",
            columns=(CatalogColumnDefinition("nombre"), CatalogColumnDefinition("ruc")),
            form_id="generic-catalog",
            generic_form_fields=fields,
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=form_host,
    )

    run_action_and_wait_for_request(screen, screen.load)
    baseline = screen.total_count
    token = uuid4().hex[:8].upper()

    form = screen.open_create()
    assert isinstance(form, GenericCatalogFormViewModel)
    form.set_field_value("nombre", f"Cliente VM {token}")
    form.set_field_value("ruc", f"TEST-VM-{token}")
    form.set_field_value("direccion", f"Masaya {token}")
    saved_holder: dict[str, Mapping[str, Any] | None] = {"value": None}

    def submit_form() -> Mapping[str, Any] | None:
        saved_holder["value"] = form.submit()
        return saved_holder["value"]

    run_action_and_wait_for_applied_load(screen, submit_form)
    saved = saved_holder["value"]

    assert saved is not None

    assert form_host.is_open is False
    assert screen.total_count == baseline + 1

    run_action_and_wait_for_request(
        screen,
        lambda: screen.set_filters(
            (
                CatalogFilter(field="ruc", operator=CatalogFilterOperator.EQ, value=saved["ruc"]),
            )
        ),
    )
    assert screen.table_model.row_data(0)["nombre"] == f"Cliente VM {token}"
    assert screen.table_model.headerData(0, Qt.Orientation.Horizontal) == "Nombre"
    assert screen.columns[-1]["key"] == "__actions__"


def test_catalog_screen_can_swap_to_specialized_form(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    registry = FormRegistry(
        (
            FormDefinition(
                form_id="cliente-special",
                qml_component="ClienteSpecial.qml",
                view_model_factory=lambda catalog_name, mode, context: ClienteSpecializedFormViewModel(),
                catalog_names=("cliente",),
                priority=10,
            ),
            FormDefinition(
                form_id="generic-catalog",
                qml_component="GenericCatalogForm.qml",
                view_model_factory=lambda catalog_name, mode, context: GenericCatalogFormViewModel(
                    catalog_name=catalog_name,
                    fields=context["view_definition"].generic_form_fields,
                    catalog_service=modelo_workflow.catalog,
                ),
                priority=0,
            ),
        )
    )
    form_host = FormHostViewModel(registry)
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="cliente",
            columns=(CatalogColumnDefinition("nombre"),),
            generic_form_fields=(GenericFormFieldDefinition(name="nombre", required=True),),
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=form_host,
    )

    form = screen.open_create()

    assert isinstance(form, ClienteSpecializedFormViewModel)
    assert form_host.active_form_id == "cliente-special"


def test_catalog_screen_exports_selected_records_with_injected_handler(tmp_path):
    export_handler = CapturingInvoiceExportHandler()
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="factura"),
        query_service=cast(ModeloCatalogQueryService, object()),
        catalog_service=cast(ModeloCatalogService, object()),
        form_host=FormHostViewModel(FormRegistry()),
        export_handler=export_handler,
    )
    target = tmp_path / "facturas.xlsx"

    assert screen.can_export is True
    assert screen.export_selection_mode is False

    screen.begin_export_selection()
    screen.toggle_export_record_id(11, 1)
    screen.toggle_export_record_id(12, 1)

    assert screen.export_selection_mode is True
    assert screen.selected_export_record_ids == [11, 12]
    assert screen.selected_export_count == 2

    assert screen.export_selected_records(str(target)) is True

    assert export_handler.calls == [((11, 12), str(target))]
    assert screen.export_selection_mode is False
    assert screen.selected_export_record_ids == []


def test_catalog_screen_exports_single_record_by_id_with_injected_handler(tmp_path):
    export_handler = CapturingInvoiceExportHandler()
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="factura"),
        query_service=cast(ModeloCatalogQueryService, object()),
        catalog_service=cast(ModeloCatalogService, object()),
        form_host=FormHostViewModel(FormRegistry()),
        export_handler=export_handler,
    )
    target = tmp_path / "factura.xlsx"

    assert screen.export_record_by_id(44, str(target)) is True

    assert export_handler.calls == [((44,), str(target))]


def test_generic_form_supports_secure_reference_search_for_ruta(
    session_factory,
    modelo_workflow,
    auth_service,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    with session_factory() as session:
        origen = create_ubicacion(session, descripcion=f"Origen Ref {uuid4().hex[:6]}")
        destino = create_ubicacion(session, descripcion=f"Destino Ref {uuid4().hex[:6]}")
        ruta = create_ruta(session, origen=origen, destino=destino)
        ruta_create = create_permission(session, "ruta", "crear")
        ruta_read = create_permission(session, "ruta", "leer")
        role = create_role(session, name=uuid4().hex[:10], permissions=[ruta_create, ruta_read])
        session.commit()

    user = auth_service.create_user(
        username=f"ruta_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    schema = query_service.get_schema("ruta")
    fields = tuple(GenericFormFieldDefinition.from_schema(field) for field in schema.form_fields)
    form = GenericCatalogFormViewModel(
        catalog_name="ruta",
        fields=fields,
        catalog_service=modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
    )

    with authenticated_user(user.id):
        form.load(int(ruta.id))
        loaded_fields = {field["name"]: field for field in form.fields}

        assert loaded_fields["origen_id"]["field_type"] == "reference"
        assert loaded_fields["origen_id"]["options"][0]["label"] == origen.descripcion

        form.search_reference_options("origen_id", origen.descripcion[:6])
        searched_fields = {field["name"]: field for field in form.fields}
        assert any(option["value"] == origen.id for option in searched_fields["origen_id"]["options"])


def test_generic_form_primes_reference_options_for_empty_fk(
    session_factory,
    modelo_workflow,
    auth_service,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    with session_factory() as session:
        create_ubicacion(session, descripcion=f"Origen Prime {uuid4().hex[:6]}")
        create_ubicacion(session, descripcion=f"Destino Prime {uuid4().hex[:6]}")
        ruta_create = create_permission(session, "ruta", "crear")
        ruta_read = create_permission(session, "ruta", "leer")
        ubicacion_read = create_permission(session, "ubicacion", "leer")
        role = create_role(session, name=uuid4().hex[:10], permissions=[ruta_create, ruta_read, ubicacion_read])
        session.commit()

    user = auth_service.create_user(
        username=f"ruta_prime_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    schema = query_service.get_schema("ruta")
    fields = tuple(GenericFormFieldDefinition.from_schema(field) for field in schema.form_fields)
    form = GenericCatalogFormViewModel(
        catalog_name="ruta",
        fields=fields,
        catalog_service=modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
    )

    with authenticated_user(user.id):
        form.reset()
        form.prime_reference_field("origen_id")
        loaded_fields = {field["name"]: field for field in form.fields}

        assert loaded_fields["origen_id"]["options"]


def test_generic_form_uses_schema_display_field_for_reference_labels_on_edit(
    session_factory,
    modelo_workflow,
    auth_service,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    with session_factory() as session:
        origen = create_ubicacion(session, descripcion=f"Origen Edit {uuid4().hex[:6]}")
        destino = create_ubicacion(session, descripcion=f"Destino Edit {uuid4().hex[:6]}")
        ruta = create_ruta(session, origen=origen, destino=destino)
        ruta_read = create_permission(session, "ruta", "leer")
        ubicacion_read = create_permission(session, "ubicacion", "leer")
        role = create_role(session, name=uuid4().hex[:10], permissions=[ruta_read, ubicacion_read])
        session.commit()

    user = auth_service.create_user(
        username=f"ruta_edit_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    schema = query_service.get_schema("ruta")
    fields = tuple(GenericFormFieldDefinition.from_schema(field) for field in schema.form_fields)
    form = GenericCatalogFormViewModel(
        catalog_name="ruta",
        fields=fields,
        catalog_service=modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
    )

    with authenticated_user(user.id):
        form.load(int(ruta.id))
        loaded_fields = {field["name"]: field for field in form.fields}

        assert loaded_fields["origen_id"]["display_field_key"] == "origen_label"
        assert loaded_fields["origen_id"]["options"][0]["value"] == origen.id
        assert loaded_fields["origen_id"]["options"][0]["label"] == origen.descripcion


def test_generic_form_set_reference_field_value_persists_id_and_exposes_label():
    service = CapturingCatalogService()
    form = GenericCatalogFormViewModel(
        catalog_name="factura",
        fields=(
            GenericFormFieldDefinition(
                name="cliente_id",
                kind="reference",
                required=True,
                nullable=False,
                reference=ReferenceFieldDTO(lookup_key="factura.cliente_id"),
                display_field_key="cliente_label",
            ),
        ),
        catalog_service=cast(ModeloCatalogService, service),
    )

    form.set_reference_field_value("cliente_id", 42, "Cliente Demo")
    serialized_fields = cast(list[dict[str, object]], form.fields)
    saved = form.submit()

    assert saved is not None
    assert service.created_payload == {"cliente_id": 42}
    assert serialized_fields[0]["display_field_key"] == "cliente_label"
    assert cast(list[dict[str, object]], serialized_fields[0]["options"])[0]["label"] == "Cliente Demo"


def test_catalog_screen_persists_column_widths_per_catalog(tmp_path):
    settings = QSettings(str(tmp_path / "table-prefs.ini"), QSettings.Format.IniFormat)
    store = QSettingsCatalogTablePreferencesStore(settings)
    fake_query_service = cast(ModeloCatalogQueryService, object())
    fake_catalog_service = cast(ModeloCatalogService, object())

    store.save_column_width("cliente", "nombre", 244)

    restored = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="cliente",
            columns=(CatalogColumnDefinition("nombre", width=180, min_width=120),),
        ),
        query_service=fake_query_service,
        catalog_service=fake_catalog_service,
        form_host=FormHostViewModel(FormRegistry()),
        table_preferences_store=store,
    )

    other_catalog = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="impuesto",
            columns=(CatalogColumnDefinition("nombre", width=180, min_width=120),),
        ),
        query_service=fake_query_service,
        catalog_service=fake_catalog_service,
        form_host=FormHostViewModel(FormRegistry()),
        table_preferences_store=store,
    )

    assert restored.columns[0]["width"] == 244
    assert other_catalog.columns[0]["width"] == 180


def test_catalog_screen_can_update_column_width_and_selected_row_data(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="cliente",
            columns=(
                CatalogColumnDefinition("id", width=80, min_width=72),
                CatalogColumnDefinition("nombre", width=180, min_width=120),
            ),
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(FormRegistry()),
        table_preferences_store=InMemoryCatalogTablePreferencesStore(),
    )

    run_action_and_wait_for_request(screen, screen.load)
    screen.set_column_width("nombre", 260)
    screen.select_row_index(0)

    assert screen.columns[1]["width"] == 260
    assert screen.selected_row_data is not None
    assert "id" in screen.selected_row_data


def test_catalog_screen_normalizes_enum_values_when_opening_edit_form(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    registry = FormRegistry(
        (
            FormDefinition(
                form_id="generic-catalog",
                qml_component="GenericCatalogForm.qml",
                view_model_factory=lambda catalog_name, mode, context: GenericCatalogFormViewModel(
                    catalog_name=catalog_name,
                    fields=context["view_definition"].generic_form_fields,
                    catalog_service=modelo_workflow.catalog,
                ),
                priority=0,
            ),
        )
    )
    view_definition = CatalogViewDefinition.from_schema(
        query_service.get_schema("impuesto"),
        form_id="generic-catalog",
    )
    form_host = FormHostViewModel(registry)
    screen = CatalogScreenViewModel(
        view_definition=view_definition,
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=form_host,
    )

    run_action_and_wait_for_request(screen, screen.load)
    record_id = screen.record_id_at_row(0)

    assert isinstance(record_id, int)

    form = screen.open_edit(record_id)

    assert isinstance(form, GenericCatalogFormViewModel)
    assert form.values["tipo"] == screen.row_data_at(0)["tipo"]
    assert isinstance(form.values["tipo"], str)


def test_generic_catalog_form_exposes_typed_metadata_and_field_errors():
    form = GenericCatalogFormViewModel(
        catalog_name="impuesto",
        fields=(
            GenericFormFieldDefinition(name="anio", kind="integer", nullable=True),
            GenericFormFieldDefinition(name="porcentaje", kind="percent", required=True, nullable=False),
            GenericFormFieldDefinition(name="fecha_emision", kind="date", nullable=True),
        ),
        catalog_service=cast(ModeloCatalogService, CapturingCatalogService()),
    )

    serialized_fields = cast(list[dict[str, object]], form.fields)
    anio_field = next(field for field in serialized_fields if field["name"] == "anio")
    porcentaje_field = next(field for field in serialized_fields if field["name"] == "porcentaje")
    fecha_field = next(field for field in serialized_fields if field["name"] == "fecha_emision")

    assert anio_field["kind"] == "integer"
    assert anio_field["nullable"] is True
    assert porcentaje_field["precision"] == 4
    assert fecha_field["display_format"] == "DD/MM/YYYY"
    assert form.field_errors["porcentaje"] == "Este campo es obligatorio."
    assert form.is_valid is False

    form.set_field_value("anio", "abc")

    assert form.field_errors["anio"] == "Debe ser un numero entero."

    form.set_field_value("anio", "2026")

    assert "anio" not in form.field_errors


def test_generic_catalog_form_normalizes_typed_payloads_before_submit():
    service = CapturingCatalogService()
    form = GenericCatalogFormViewModel(
        catalog_name="evento",
        fields=(
            GenericFormFieldDefinition(name="anio", kind="integer", required=True, nullable=False),
            GenericFormFieldDefinition(name="monto", kind="money", required=True, nullable=False),
            GenericFormFieldDefinition(name="porcentaje", kind="percent", required=True, nullable=False),
            GenericFormFieldDefinition(name="fecha", kind="date", required=True, nullable=False),
            GenericFormFieldDefinition(name="inicio", kind="datetime", required=True, nullable=False),
        ),
        catalog_service=cast(ModeloCatalogService, service),
    )

    form.set_field_value("anio", "2026")
    form.set_field_value("monto", "125.5")
    form.set_field_value("porcentaje", "15")
    form.set_field_value("fecha", "08/04/2026")
    form.set_field_value("inicio", "08/04/2026 14:30")

    saved = form.submit()

    assert saved is not None
    assert service.created_payload == {
        "anio": 2026,
        "monto": "125.50",
        "porcentaje": "15.0000",
        "fecha": "2026-04-08",
        "inicio": "2026-04-08T14:30",
    }
    assert form.field_errors == {}
    assert form.is_valid is True


def test_generic_catalog_form_exposes_default_layout_items_in_field_order():
    form = GenericCatalogFormViewModel(
        catalog_name="cliente",
        fields=(
            GenericFormFieldDefinition(name="nombre", required=True),
            GenericFormFieldDefinition(name="ruc", required=True),
            GenericFormFieldDefinition(name="direccion"),
        ),
        catalog_service=cast(ModeloCatalogService, CapturingCatalogService()),
    )

    layout_items = cast(list[dict[str, object]], form.layout_items)

    assert [item["type"] for item in layout_items] == ["row", "row"]
    assert [field["name"] for field in cast(list[dict[str, object]], layout_items[0]["fields"])] == ["nombre", "ruc"]
    assert [field["name"] for field in cast(list[dict[str, object]], layout_items[1]["fields"])] == ["direccion"]


def test_generic_catalog_form_resolves_custom_layout_sections_rows_and_omitted_fields():
    fields = (
        GenericFormFieldDefinition(name="nombre", required=True),
        GenericFormFieldDefinition(name="ruc", required=True),
        GenericFormFieldDefinition(name="direccion"),
        GenericFormFieldDefinition(name="facturable", field_type="bool", default=True),
    )
    form = GenericCatalogFormViewModel(
        catalog_name="cliente",
        fields=fields,
        form_layout=FormLayoutDefinition(
            items=(
                FormLayoutSectionItem(title="Encabezado"),
                FormLayoutFieldItem(field_name="nombre"),
                FormLayoutFieldItem(field_name="ruc"),
                FormLayoutFieldItem(field_name="direccion", full_width=True),
            )
        ),
        catalog_service=cast(ModeloCatalogService, CapturingCatalogService()),
    )

    layout_items = cast(list[dict[str, object]], form.layout_items)

    assert [item["type"] for item in layout_items] == ["section", "row", "row", "row"]
    assert layout_items[0]["title"] == "Encabezado"
    assert [field["name"] for field in cast(list[dict[str, object]], layout_items[1]["fields"])] == ["nombre", "ruc"]
    full_width_row = cast(list[dict[str, object]], layout_items[2]["fields"])
    assert [field["name"] for field in full_width_row] == ["direccion"]
    assert full_width_row[0]["full_width"] is True
    assert [field["name"] for field in cast(list[dict[str, object]], layout_items[3]["fields"])] == ["facturable"]


def test_generic_catalog_form_ignores_unknown_layout_fields_without_breaking_submit():
    service = CapturingCatalogService()
    form = GenericCatalogFormViewModel(
        catalog_name="cliente",
        fields=(
            GenericFormFieldDefinition(name="nombre", required=True),
            GenericFormFieldDefinition(name="ruc", required=True),
        ),
        form_layout=FormLayoutDefinition(
            items=(
                FormLayoutFieldItem(field_name="nombre"),
                FormLayoutFieldItem(field_name="inexistente"),
            )
        ),
        catalog_service=cast(ModeloCatalogService, service),
    )

    layout_items = cast(list[dict[str, object]], form.layout_items)
    form.set_field_value("nombre", "Cliente Demo")
    form.set_field_value("ruc", "RUC-001")

    saved = form.submit()

    assert saved is not None
    assert [field["name"] for field in cast(list[dict[str, object]], layout_items[0]["fields"])] == ["nombre", "ruc"]
    assert service.created_payload == {"nombre": "Cliente Demo", "ruc": "RUC-001"}


def test_generic_catalog_form_surfaces_duplicate_unique_errors_without_closing(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    fields = (
        GenericFormFieldDefinition(name="nombre", required=True),
        GenericFormFieldDefinition(name="ruc", required=True),
        GenericFormFieldDefinition(name="direccion", required=True),
        GenericFormFieldDefinition(name="facturable", field_type="bool", default=True),
    )
    registry = FormRegistry(
        (
            FormDefinition(
                form_id="generic-catalog",
                qml_component="GenericCatalogForm.qml",
                view_model_factory=lambda catalog_name, mode, context: GenericCatalogFormViewModel(
                    catalog_name=catalog_name,
                    fields=context["view_definition"].generic_form_fields,
                    catalog_service=modelo_workflow.catalog,
                ),
                priority=0,
            ),
        )
    )
    form_host = FormHostViewModel(registry)
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="cliente",
            columns=(CatalogColumnDefinition("nombre"), CatalogColumnDefinition("ruc")),
            form_id="generic-catalog",
            generic_form_fields=fields,
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=form_host,
    )

    token = uuid4().hex[:8].upper()
    duplicate_ruc = f"DUP-{token}"
    modelo_workflow.catalog.create(
        "cliente",
        {
            "nombre": f"Cliente Base {token}",
            "ruc": duplicate_ruc,
            "direccion": f"Managua {token}",
            "facturable": True,
        },
    )

    form = screen.open_create()

    assert isinstance(form, GenericCatalogFormViewModel)

    form.set_field_value("nombre", f"Cliente Duplicado {token}")
    form.set_field_value("ruc", duplicate_ruc)
    form.set_field_value("direccion", f"Masaya {token}")
    form.set_field_value("facturable", True)

    result = form.submit()

    assert result is None
    assert form_host.is_open is True
    assert form_host.active_form is form
    assert form.error_message == "El campo 'ruc' debe ser unico. Ya existe otro registro con ese valor."
    assert form.field_errors["ruc"] == "Ya existe otro registro con este valor."
    assert "INSERT INTO" not in form.error_message
    assert "cliente_ruc_key" not in form.error_message
    assert form.is_valid is False


def test_generic_catalog_form_merges_local_and_persistence_field_errors():
    service = PersistenceErroringCatalogService()
    form = GenericCatalogFormViewModel(
        catalog_name="cliente",
        fields=(
            GenericFormFieldDefinition(name="nombre", required=True),
            GenericFormFieldDefinition(name="ruc", required=True),
        ),
        catalog_service=cast(ModeloCatalogService, service),
    )

    form.set_field_value("nombre", "Cliente Demo")
    form.set_field_value("ruc", "RUC-001")

    assert form.submit() is None
    assert form.field_errors["ruc"] == "Ya existe otro registro con este valor."

    form.set_field_value("nombre", "")

    assert form.field_errors["ruc"] == "Ya existe otro registro con este valor."
    assert form.field_errors["nombre"] == "Este campo es obligatorio."
    assert form.is_valid is False


def test_generic_catalog_form_clears_persistence_field_error_when_user_edits_field():
    service = PersistenceErroringCatalogService()
    form = GenericCatalogFormViewModel(
        catalog_name="cliente",
        fields=(
            GenericFormFieldDefinition(name="nombre", required=True),
            GenericFormFieldDefinition(name="ruc", required=True),
        ),
        catalog_service=cast(ModeloCatalogService, service),
    )

    form.set_field_value("nombre", "Cliente Demo")
    form.set_field_value("ruc", "RUC-001")

    assert form.submit() is None
    assert form.error_message == "El campo 'ruc' debe ser unico. Ya existe otro registro con ese valor."
    assert form.field_errors["ruc"] == "Ya existe otro registro con este valor."

    form.set_field_value("ruc", "RUC-002")

    assert "ruc" not in form.field_errors
    assert form.error_message == ""
    assert form.is_valid is True


def test_translate_integrity_error_maps_foreign_key_to_field_error():
    error = IntegrityError(
        "INSERT INTO factura (cliente_id) VALUES (%(cliente_id)s)",
        {"cliente_id": 999},
        _FakeDBAPIIntegrityError(
            pgcode="23503",
            message_primary='insert or update on table "factura" violates foreign key constraint "factura_cliente_id_fkey"',
            message_detail='Key (cliente_id)=(999) is not present in table "cliente".',
        ),
    )

    translated = translate_integrity_error("factura", error)

    assert translated.error_code == "foreign_key"
    assert translated.fields == ("cliente_id",)
    assert translated.summary_message == "El campo 'cliente_id' debe referenciar un registro valido."
    assert translated.field_errors == {"cliente_id": "Selecciona un registro valido."}


def test_catalog_screen_displays_reference_label_columns_but_preserves_canonical_ids(
    session_factory,
    modelo_workflow,
    auth_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    with session_factory() as session:
        origen = create_ubicacion(session, descripcion=f"Origen Label {uuid4().hex[:6]}")
        destino = create_ubicacion(session, descripcion=f"Destino Label {uuid4().hex[:6]}")
        ruta = create_ruta(session, origen=origen, destino=destino)
        ruta_read = create_permission(session, "ruta", "leer")
        ubicacion_read = create_permission(session, "ubicacion", "leer")
        role = create_role(session, name=uuid4().hex[:10], permissions=[ruta_read, ubicacion_read])
        session.commit()

    user = auth_service.create_user(
        username=f"ruta_grid_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )

    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(query_service.get_schema("ruta")),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(FormRegistry()),
    )

    with authenticated_user(user.id):
        run_action_and_wait_for_request(screen, screen.load)
        run_action_and_wait_for_request(
            screen,
            lambda: screen.set_filters(
                (
                    CatalogFilter(field="id", operator=CatalogFilterOperator.EQ, value=int(ruta.id)),
                )
            ),
        )

        assert screen.table_model.rowCount() == 1

        column_positions = {
            str(column["key"]): index
            for index, column in enumerate(screen.columns)
            if str(column.get("kind", "data")) == "data"
        }

        assert "origen_id" not in column_positions
        assert "destino_id" not in column_positions
        assert screen.table_model.display_data(0, column_positions["origen_label"]) == origen.descripcion
        assert screen.table_model.display_data(0, column_positions["destino_label"]) == destino.descripcion

        row_data = screen.row_data_at(0)
        assert row_data["id"] == ruta.id
        assert row_data["origen_id"] == origen.id
        assert row_data["destino_id"] == destino.id
        assert row_data["origen_label"] == origen.descripcion
        assert row_data["destino_label"] == destino.descripcion

        screen.select_row_index(0)

        assert screen.selected_row_data["origen_id"] == origen.id
        assert screen.selected_row_data["destino_id"] == destino.id


def test_catalog_screen_displays_reference_labels_for_conductor_catalog(
    session_factory,
    modelo_workflow,
    auth_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    with session_factory() as session:
        camion = create_camion(session, placa=f"TC-{uuid4().hex[:6].upper()}")
        furgon = create_furgon(session, placa=f"TF-{uuid4().hex[:6].upper()}")
        thermo = create_thermo(session, codigo=f"TH-{uuid4().hex[:6].upper()}")
        conductor = create_conductor(
            session,
            nombre="Ana",
            apellido=f"Label {uuid4().hex[:4]}",
            camion_id=int(camion.id),
            furgon_id=int(furgon.id),
            thermo_id=int(thermo.id),
        )
        conductor_read = create_permission(session, "conductor", "leer")
        role = create_role(session, name=uuid4().hex[:10], permissions=[conductor_read])
        session.commit()

    user = auth_service.create_user(
        username=f"conductor_grid_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )

    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(query_service.get_schema("conductor")),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(FormRegistry()),
    )

    with authenticated_user(user.id):
        run_action_and_wait_for_request(screen, screen.load)
        run_action_and_wait_for_request(
            screen,
            lambda: screen.set_filters(
                (
                    CatalogFilter(field="id", operator=CatalogFilterOperator.EQ, value=int(conductor.id)),
                )
            ),
        )

        assert screen.table_model.rowCount() == 1

        column_positions = {
            str(column["key"]): index
            for index, column in enumerate(screen.columns)
            if str(column.get("kind", "data")) == "data"
        }

        assert "camion_id" not in column_positions
        assert "furgon_id" not in column_positions
        assert "thermo_id" not in column_positions
        assert screen.table_model.display_data(0, column_positions["camion_label"]) == camion.placa
        assert screen.table_model.display_data(0, column_positions["furgon_label"]) == furgon.placa
        assert screen.table_model.display_data(0, column_positions["thermo_label"]) == thermo.codigo

        row_data = screen.row_data_at(0)
        assert row_data["camion_id"] == camion.id
        assert row_data["furgon_id"] == furgon.id
        assert row_data["thermo_id"] == thermo.id
        assert row_data["camion_label"] == camion.placa
        assert row_data["furgon_label"] == furgon.placa
        assert row_data["thermo_label"] == thermo.codigo


def test_catalog_screen_formats_money_with_currency_symbol_and_hides_currency_column(
    session_factory,
    modelo_workflow,
    auth_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente Tarifa {uuid4().hex[:6]}")
        ruta = create_ruta(session)
        tarifa = TarifaFlete(
            cliente_id=cliente.id,
            ruta_id=ruta.id,
            costo="1000.00",
            moneda=Moneda.USD,
        )
        session.add(tarifa)
        tarifa_read = create_permission(session, "tarifa_flete", "leer")
        role = create_role(session, name=uuid4().hex[:10], permissions=[tarifa_read])
        session.commit()

    user = auth_service.create_user(
        username=f"tarifa_grid_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(query_service.get_schema("tarifa_flete")),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(FormRegistry()),
    )

    with authenticated_user(user.id):
        run_action_and_wait_for_request(screen, screen.load)
        run_action_and_wait_for_request(
            screen,
            lambda: screen.set_filters(
                (
                    CatalogFilter(field="id", operator=CatalogFilterOperator.EQ, value=int(tarifa.id)),
                )
            ),
        )

        column_positions = {
            str(column["key"]): index
            for index, column in enumerate(screen.columns)
            if str(column.get("kind", "data")) == "data"
        }

        assert "moneda" not in column_positions
        assert screen.table_model.display_data(0, column_positions["costo"]) == "$ 1,000.00"
        assert screen.row_data_at(0)["costo"] == "1000.00"
        assert screen.row_data_at(0)["moneda"] == "USD"


def test_factura_catalog_formats_subtotal_and_total_with_currency_symbol(
    session_factory,
    modelo_workflow,
    auth_service,
):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente Factura {token}", ruc=f"FAC-{token}")
        factura_read = create_permission(session, "factura", "leer")
        role = create_role(session, name=uuid4().hex[:10], permissions=[factura_read])
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-FMT-{token}"
    factura_payload["factura"]["moneda"] = Moneda.USD
    factura = modelo_workflow.factura.create(factura_payload)

    user = auth_service.create_user(
        username=f"factura_grid_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(query_service.get_schema("factura")),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(FormRegistry()),
    )

    with authenticated_user(user.id):
        run_action_and_wait_for_request(screen, screen.load)
        run_action_and_wait_for_request(
            screen,
            lambda: screen.set_filters(
                (
                    CatalogFilter(field="id", operator=CatalogFilterOperator.EQ, value=int(factura["id"])),
                )
            ),
        )

        column_positions = {
            str(column["key"]): index
            for index, column in enumerate(screen.columns)
            if str(column.get("kind", "data")) == "data"
        }

        assert "moneda" not in column_positions
        assert screen.table_model.display_data(0, column_positions["_subtotal"]) == "$ 150.00"
        assert screen.table_model.display_data(0, column_positions["_total"]) == "$ 150.00"
        assert screen.row_data_at(0)["_subtotal"] == "150.00"
        assert screen.row_data_at(0)["_total"] == "150.00"
        assert screen.row_data_at(0)["moneda"] == "USD"
