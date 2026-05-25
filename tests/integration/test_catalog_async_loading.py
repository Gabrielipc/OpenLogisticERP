from __future__ import annotations

from typing import Any, cast

from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.domain.modelo.catalog_queries import CatalogQueryRequest
from openlogistic_erp.domain.modelo.dtos import CatalogPageDTO, CatalogRecordDTO
from openlogistic_erp.application.modelo.services import ModeloCatalogService
from openlogistic_erp.presentation.catalog import (
    CatalogColumnDefinition,
    CatalogScreenViewModel,
    CatalogViewDefinition,
    FormHostViewModel,
    FormRegistry,
)
from openlogistic_erp.presentation.catalog.async_load import (
    CatalogLoadFailure,
    CatalogLoadRequest,
    CatalogLoadResult,
    execute_catalog_load,
)
from openlogistic_erp.presentation.catalog.serialization import display_catalog_value
from openlogistic_erp.presentation.qt import Qt


class ControlledLoadRunner:
    def __init__(self) -> None:
        self.requests: dict[int, CatalogLoadRequest] = {}
        self._success_callbacks: dict[int, object] = {}
        self._failure_callbacks: dict[int, object] = {}

    def submit(self, request, on_success, on_failure) -> None:
        self.requests[request.request_id] = request
        self._success_callbacks[request.request_id] = on_success
        self._failure_callbacks[request.request_id] = on_failure

    def succeed(self, request_id: int, rows: list[dict[str, Any]], *, total_count: int | None = None) -> None:
        request = self.requests[request_id]
        result = CatalogLoadResult(
            request_id=request_id,
            rows=tuple(dict(row) for row in rows),
            display_rows=tuple(
                tuple(display_catalog_value(row.get(column_key)) for column_key in request.column_keys)
                for row in rows
            ),
            column_keys=request.column_keys,
            total_count=int(total_count if total_count is not None else len(rows)),
            page=request.query.page,
            page_size=request.query.page_size,
        )
        callback = self._success_callbacks.pop(request_id)
        self._failure_callbacks.pop(request_id, None)
        callback(result)

    def fail(self, request_id: int, message: str) -> None:
        callback = self._failure_callbacks.pop(request_id)
        self._success_callbacks.pop(request_id, None)
        callback(CatalogLoadFailure(request_id=request_id, message=message))


class _StubQueryService:
    def __init__(self, page: CatalogPageDTO) -> None:
        self._page = page
        self.seen_requests: list[CatalogQueryRequest] = []

    def query_page(self, request: CatalogQueryRequest) -> CatalogPageDTO:
        self.seen_requests.append(request)
        return self._page


def _build_screen(load_runner: ControlledLoadRunner) -> CatalogScreenViewModel:
    return CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="cliente",
            columns=(
                CatalogColumnDefinition("id", width=80, min_width=72),
                CatalogColumnDefinition("nombre", width=180, min_width=120),
            ),
        ),
        query_service=cast(ModeloCatalogQueryService, object()),
        catalog_service=cast(ModeloCatalogService, object()),
        form_host=FormHostViewModel(FormRegistry()),
        load_runner=load_runner,
    )


def test_catalog_table_model_reads_precomputed_display_snapshot():
    screen = _build_screen(ControlledLoadRunner())
    model = screen.table_model

    model.set_table(
        rows=[{"id": 1, "nombre": "raw"}],
        columns=[
            {"key": "id", "header": "Id", "kind": "data"},
            {"key": "nombre", "header": "Nombre", "kind": "data"},
        ],
        display_rows=[("1", "precomputed")],
        display_column_keys=("id", "nombre"),
    )

    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "precomputed"
    assert model.display_data(0, 1) == "precomputed"


def test_catalog_table_model_builds_tsv_for_display_range():
    screen = _build_screen(ControlledLoadRunner())
    model = screen.table_model

    model.set_table(
        rows=[
            {"id": 1, "nombre": "raw 1", "estado": "activo"},
            {"id": 2, "nombre": "raw 2", "estado": "inactivo"},
        ],
        columns=[
            {"key": "id", "header": "Id", "kind": "data"},
            {"key": "nombre", "header": "Nombre", "kind": "data"},
            {"key": "estado", "header": "Estado", "kind": "data"},
            {"key": "__actions__", "header": "", "kind": "actions"},
        ],
        display_rows=[
            ("1", "Cliente\tUno", "Activo"),
            ("2", "Cliente\nDos", "Inactivo"),
        ],
        display_column_keys=("id", "nombre", "estado"),
    )

    assert model.display_range_as_tsv(1, 2, 0, 1) == "Cliente Uno\tActivo\nCliente Dos\tInactivo"


def test_execute_catalog_load_uses_real_label_columns_for_display():
    request = CatalogLoadRequest(
        request_id=7,
        query=CatalogQueryRequest(catalog_name="ruta"),
        column_keys=("id", "origen_label"),
    )
    query_service = _StubQueryService(
        CatalogPageDTO(
            rows=(
                CatalogRecordDTO(
                    catalog_name="ruta",
                    values={
                        "id": 1,
                        "origen_id": 99,
                        "origen_label": "Managua",
                    },
                ),
            ),
            total_count=1,
            page=0,
            page_size=20,
        )
    )

    result = execute_catalog_load(cast(ModeloCatalogQueryService, query_service), request)

    assert result.rows == ({"id": 1, "origen_id": 99, "origen_label": "Managua"},)
    assert result.display_rows == (("1", "Managua"),)


def test_execute_catalog_load_infers_dynamic_columns_from_serialized_rows():
    request = CatalogLoadRequest(
        request_id=8,
        query=CatalogQueryRequest(catalog_name="ruta"),
    )
    query_service = _StubQueryService(
        CatalogPageDTO(
            rows=(
                CatalogRecordDTO(
                    catalog_name="ruta",
                    values={
                        "id": 4,
                        "origen_id": 42,
                        "origen_label": "Leon",
                    },
                ),
            ),
            total_count=1,
            page=0,
            page_size=20,
        )
    )

    result = execute_catalog_load(cast(ModeloCatalogQueryService, query_service), request)

    assert result.column_keys == ("id", "origen_id", "origen_label")
    assert result.display_rows == (("4", "42", "Leon"),)


def test_catalog_screen_latest_request_wins_and_discards_stale_results():
    runner = ControlledLoadRunner()
    screen = _build_screen(runner)
    finished_events: list[tuple[int, bool]] = []
    screen.loadFinished.connect(lambda request_id, applied: finished_events.append((int(request_id), bool(applied))))

    first_request_id = screen.load()
    second_request_id = screen.refresh()

    assert screen.is_busy is True
    assert screen.table_model.rowCount() == 0

    runner.succeed(first_request_id, [{"id": 1, "nombre": "Viejo"}], total_count=1)

    assert screen.table_model.rowCount() == 0
    assert screen.is_busy is True

    runner.succeed(second_request_id, [{"id": 2, "nombre": "Nuevo"}], total_count=1)

    assert screen.is_busy is False
    assert screen.table_model.rowCount() == 1
    assert screen.table_model.row_data(0)["id"] == 2
    assert screen.table_model.display_data(0, 1) == "Nuevo"
    assert finished_events == [
        (first_request_id, False),
        (second_request_id, True),
    ]


def test_catalog_screen_keeps_previous_rows_during_refresh_after_first_load():
    runner = ControlledLoadRunner()
    screen = _build_screen(runner)

    first_request_id = screen.load()
    assert screen.table_model.rowCount() == 0

    runner.succeed(first_request_id, [{"id": 1, "nombre": "Inicial"}], total_count=1)

    assert screen.table_model.rowCount() == 1
    assert screen.table_model.display_data(0, 1) == "Inicial"

    refresh_request_id = screen.refresh()

    assert screen.is_busy is True
    assert screen.table_model.rowCount() == 1
    assert screen.table_model.display_data(0, 1) == "Inicial"

    runner.succeed(refresh_request_id, [{"id": 1, "nombre": "Actualizado"}], total_count=1)

    assert screen.is_busy is False
    assert screen.table_model.rowCount() == 1
    assert screen.table_model.display_data(0, 1) == "Actualizado"


def test_catalog_screen_surfaces_latest_error_without_clearing_existing_rows():
    runner = ControlledLoadRunner()
    screen = _build_screen(runner)

    first_request_id = screen.load()
    runner.succeed(first_request_id, [{"id": 1, "nombre": "Base"}], total_count=1)

    refresh_request_id = screen.refresh()
    runner.fail(refresh_request_id, "fallo controlado")

    assert screen.is_busy is False
    assert screen.error_message == "fallo controlado"
    assert screen.table_model.rowCount() == 1
    assert screen.table_model.row_data(0)["id"] == 1


def test_catalog_screen_preserves_selection_when_record_survives_refresh():
    runner = ControlledLoadRunner()
    screen = _build_screen(runner)

    first_request_id = screen.load()
    runner.succeed(
        first_request_id,
        [
            {"id": 1, "nombre": "Uno"},
            {"id": 2, "nombre": "Dos"},
        ],
        total_count=2,
    )
    screen.select_record_by_id(2)

    refresh_request_id = screen.refresh()
    runner.succeed(
        refresh_request_id,
        [
            {"id": 2, "nombre": "Dos"},
            {"id": 3, "nombre": "Tres"},
        ],
        total_count=2,
    )

    assert screen.selected_record_id == 2
    assert screen.selected_row_data["id"] == 2

    final_request_id = screen.refresh()
    runner.succeed(final_request_id, [{"id": 3, "nombre": "Tres"}], total_count=1)

    assert screen.selected_record_id is None
    assert screen.selected_row_data == {}
