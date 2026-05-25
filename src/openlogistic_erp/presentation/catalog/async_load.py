"""Background loading pipeline for catalog table snapshots."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextvars import Context, copy_context
from dataclasses import dataclass
from typing import Any, Protocol, cast

from ...application.modelo.query_service import ModeloCatalogQueryService
from ...domain.modelo.catalog_queries import CatalogQueryRequest
from ..qt import QObject, QRunnable, QThreadPool, Signal
from .serialization import display_catalog_value, serialize_catalog_value


@dataclass(frozen=True)
class CatalogLoadRequest:
    request_id: int
    query: CatalogQueryRequest
    column_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogLoadResult:
    request_id: int
    rows: tuple[dict[str, Any], ...]
    display_rows: tuple[tuple[str, ...], ...]
    column_keys: tuple[str, ...]
    total_count: int
    page: int
    page_size: int


@dataclass(frozen=True)
class CatalogLoadFailure:
    request_id: int
    message: str


class CatalogLoadRunner(Protocol):
    def submit(
        self,
        request: CatalogLoadRequest,
        on_success: Callable[[CatalogLoadResult], None],
        on_failure: Callable[[CatalogLoadFailure], None],
    ) -> None:
        ...


def execute_catalog_load(
    query_service: ModeloCatalogQueryService,
    request: CatalogLoadRequest,
) -> CatalogLoadResult:
    page = query_service.query_page(request.query)
    rows = tuple(_serialize_row(row) for row in page.rows)
    column_keys = _resolve_column_keys(rows, request.column_keys)
    display_rows = tuple(
        tuple(display_catalog_value(row.get(column_key)) for column_key in column_keys)
        for row in rows
    )
    return CatalogLoadResult(
        request_id=request.request_id,
        rows=rows,
        display_rows=display_rows,
        column_keys=column_keys,
        total_count=page.total_count,
        page=page.page,
        page_size=page.page_size,
    )


class _CatalogLoadWorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)


class _CatalogLoadWorker(QRunnable):
    def __init__(
        self,
        query_service: ModeloCatalogQueryService,
        request: CatalogLoadRequest,
        signals: _CatalogLoadWorkerSignals,
        context: Context,
    ) -> None:
        super().__init__()
        self._query_service = query_service
        self._request = request
        self._signals = signals
        self._context = context

    def run(self) -> None:
        try:
            result = self._context.run(execute_catalog_load, self._query_service, self._request)
        except Exception as exc:
            self._signals.failed.emit(
                CatalogLoadFailure(
                    request_id=self._request.request_id,
                    message=str(exc),
                )
            )
            return
        self._signals.succeeded.emit(result)


class QtThreadPoolCatalogLoadRunner:
    """Qt-backed async loader that executes catalog reads off the UI thread."""

    def __init__(
        self,
        query_service: ModeloCatalogQueryService,
        *,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        self._query_service = query_service
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._inflight: dict[int, tuple[_CatalogLoadWorkerSignals, _CatalogLoadWorker]] = {}

    def submit(
        self,
        request: CatalogLoadRequest,
        on_success: Callable[[CatalogLoadResult], None],
        on_failure: Callable[[CatalogLoadFailure], None],
    ) -> None:
        signals = _CatalogLoadWorkerSignals()
        worker = _CatalogLoadWorker(self._query_service, request, signals, copy_context())

        def _clear_inflight() -> None:
            self._inflight.pop(request.request_id, None)

        def _handle_success(result: object) -> None:
            _clear_inflight()
            on_success(cast(CatalogLoadResult, result))

        def _handle_failure(failure: object) -> None:
            _clear_inflight()
            if isinstance(failure, CatalogLoadFailure):
                on_failure(failure)
                return
            on_failure(CatalogLoadFailure(request_id=request.request_id, message=str(failure)))

        signals.succeeded.connect(_handle_success)
        signals.failed.connect(_handle_failure)
        self._inflight[request.request_id] = (signals, worker)
        self._thread_pool.start(worker)


def _serialize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): serialize_catalog_value(value) for key, value in row.items()}


def _resolve_column_keys(
    rows: tuple[dict[str, Any], ...],
    requested_column_keys: tuple[str, ...],
) -> tuple[str, ...]:
    if requested_column_keys:
        return tuple(str(column_key) for column_key in requested_column_keys)
    if not rows:
        return ()
    return tuple(rows[0].keys())
