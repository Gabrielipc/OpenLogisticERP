from __future__ import annotations

import importlib.util
import gc
import os
import sys
import time
from uuid import uuid4
from pathlib import Path

import pytest
from dotenv import load_dotenv
from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import openlogistic_erp.infrastructure.persistence.modelo.models  # noqa: E402, F401
import openlogistic_erp.infrastructure.persistence.security.models  # noqa: E402, F401
from openlogistic_erp.application.auth import build_auth_module  # noqa: E402
from openlogistic_erp.application.modelo.factories import build_modelo_module  # noqa: E402
from openlogistic_erp.application.modelo.reference_service import ReferenceLookupService  # noqa: E402
from openlogistic_erp.application.rbac import build_rbac_module  # noqa: E402
from openlogistic_erp.presentation.catalog import screen_view_model as catalog_screen_module  # noqa: E402
from openlogistic_erp.presentation.catalog.async_load import execute_catalog_load  # noqa: E402
from openlogistic_erp.infrastructure.persistence.database import (  # noqa: E402
    build_postgres_connect_args,
    create_engine_and_factory,
    with_session_auth_context,
)
from openlogistic_erp.infrastructure.persistence.modelo.repositories.sqlalchemy_modelo_repository import (  # noqa: E402
    SqlAlchemyModeloRepository,
)
from openlogistic_erp.infrastructure.persistence.modelo.repositories.sqlalchemy_reference_lookup_repository import (  # noqa: E402
    SqlAlchemyReferenceLookupRepository,
)
from openlogistic_erp.infrastructure.persistence.security.repositories.auth_repository import (  # noqa: E402
    SqlAlchemyAuthRepository,
)
from openlogistic_erp.infrastructure.persistence.security.repositories.rbac_repository import (  # noqa: E402
    SqlAlchemyRbacRepository,
)
from openlogistic_erp.presentation.qt import QApplication  # noqa: E402
from openlogistic_erp.presentation.viewmodels.base_view_model import BaseViewModel  # noqa: E402

REQUIRED_TABLES = {
    "users",
    "roles",
    "permissions",
    "user_roles",
    "role_permissions",
    "cliente",
    "viaje",
    "factura",
    "recibo",
    "circuito",
    "detalle_operacion",
}


def _git_worktree_checkout_root(root: Path) -> Path | None:
    git_pointer = root / ".git"
    if not git_pointer.is_file():
        return None
    try:
        content = git_pointer.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "gitdir:"
    if not content.lower().startswith(prefix):
        return None
    gitdir_value = content[len(prefix) :].strip()
    if not gitdir_value:
        return None
    gitdir_path = Path(gitdir_value)
    if not gitdir_path.is_absolute():
        gitdir_path = (root / gitdir_path).resolve()
    else:
        gitdir_path = gitdir_path.resolve()
    try:
        if gitdir_path.parent.name != "worktrees" or gitdir_path.parents[1].name != ".git":
            return None
        return gitdir_path.parents[2]
    except IndexError:
        return None


def _candidate_repo_roots() -> tuple[Path, ...]:
    candidates: list[Path] = [ROOT]
    checkout_root = _git_worktree_checkout_root(ROOT)
    if checkout_root is not None and checkout_root not in candidates:
        candidates.append(checkout_root)
    return tuple(candidates)


def _load_module_sql(module_path: Path, attribute: str = "UPGRADE_SQL") -> str:
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No fue posible cargar la migracion: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value = getattr(module, attribute, None)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"La migracion no expone {attribute}: {module_path}")
    return value


def _load_reference_lookup_sql() -> str:
    searched: list[str] = []
    for candidate_root in _candidate_repo_roots():
        legacy_path = candidate_root / "supabase" / "migrations" / "20260408170000_secure_reference_lookups.sql"
        searched.append(str(legacy_path))
        if legacy_path.exists():
            return legacy_path.read_text(encoding="utf-8")

        migration_paths = (
            candidate_root / "alembic" / "versions" / "d4f6e2b8a1c9_secure_reference_lookups.py",
            candidate_root / "alembic" / "versions" / "e6a6290a7f4c_conductor_reference_lookups.py",
            candidate_root / "alembic" / "versions" / "4b1816e0a2b9_repair_viaje_thermo_lookup.py",
            candidate_root / "alembic" / "versions" / "7c9e3f1a6d44_repair_viaje_reference_lookups.py",
            candidate_root / "alembic" / "versions" / "9f2c4d1a7b3e_viaje_conductor_lookup_by_trip_type.py",
            candidate_root / "alembic" / "versions" / "c3d4e5f6a7b8_fix_factura_recibo_cliente_lookup_permissions.py",
            candidate_root / "alembic" / "versions" / "f1a2b3c4d5e6_viaje_route_lookup_cross_filters.py",
            candidate_root / "alembic" / "versions" / "a4d8c2f6b9e1_viaje_ida_lookup_for_importacion.py",
        )
        searched.extend(str(path) for path in migration_paths)
        if all(path.exists() for path in migration_paths):
            return "\n\n".join(_load_module_sql(path) for path in migration_paths)

    raise FileNotFoundError(
        "No se encontro el SQL legacy ni las migraciones Alembic de reference lookups en ninguno de los roots candidatos: "
        + ", ".join(searched)
    )


REFERENCE_LOOKUP_SQL = _load_reference_lookup_sql()


def pytest_ignore_collect(collection_path, config):
    del config
    name = collection_path.name
    return name.startswith(("tmp-pytest", ".tmp-pytest", "pytest_basetemp", "pytest_cache"))


@pytest.fixture
def tmp_path(request):
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in request.node.name)[:80]
    path = ROOT / "pytest_tmp" / f"{safe_name}_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _database_url() -> str:
    load_dotenv()
    candidates = (
        os.getenv("OPENLOGISTIC_DATABASE_URL", "").strip(),
        os.getenv("SUPABASE_CONNECTION_STRING", "").strip(),
    )
    for candidate in candidates:
        if candidate:
            return candidate
    pytest.skip(
        "Se requiere OPENLOGISTIC_DATABASE_URL o SUPABASE_CONNECTION_STRING para ejecutar integraciones contra staging.",  # noqa: E501
    )


def _environment_name() -> str:
    load_dotenv()
    return os.getenv("OPENLOGISTIC_ENV", "development").strip() or "development"


def _connect_args(database_url: str) -> dict[str, object]:
    if not database_url.startswith("postgresql"):
        pytest.fail("La suite de integración requiere PostgreSQL real; SQLite ya no está soportado en tests.")
    return build_postgres_connect_args(_environment_name())


@pytest.fixture(scope="session")
def staging_database_url() -> str:
    return _database_url()


@pytest.fixture(scope="session")
def engine(staging_database_url):
    engine, _ = create_engine_and_factory(
        staging_database_url,
        connect_args=_connect_args(staging_database_url),
    )
    return engine


@pytest.fixture(scope="session", autouse=True)
def verify_required_tables(engine) -> None:
    inspector = inspect(engine)
    available = set(inspector.get_table_names())
    missing = sorted(REQUIRED_TABLES - available)
    if missing:
        pytest.skip(f"El schema de staging no contiene las tablas requeridas: {', '.join(missing)}")


@pytest.fixture
def db_connection(engine):
    connection = engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def session_factory(db_connection):
    base_factory = sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    return with_session_auth_context(base_factory, apply_authenticated_role=True)


@pytest.fixture
def install_reference_lookup_schema(db_connection):
    raw_connection = db_connection.connection.driver_connection
    cursor = raw_connection.cursor()
    try:
        cursor.execute(REFERENCE_LOOKUP_SQL)
    finally:
        cursor.close()
    return True



@pytest.fixture(scope="session", autouse=True)
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _SynchronousCatalogLoadRunner:
    def __init__(self, query_service, **_kwargs):
        self._query_service = query_service

    def submit(self, request, on_success, on_failure) -> None:
        try:
            on_success(execute_catalog_load(self._query_service, request))
        except Exception as exc:
            from openlogistic_erp.presentation.catalog.async_load import CatalogLoadFailure

            on_failure(CatalogLoadFailure(request_id=request.request_id, message=str(exc)))


@pytest.fixture(autouse=True)
def use_synchronous_catalog_loads(monkeypatch):
    monkeypatch.setattr(
        catalog_screen_module,
        "QtThreadPoolCatalogLoadRunner",
        _SynchronousCatalogLoadRunner,
    )


@pytest.fixture
def repository(session_factory):
    return SqlAlchemyModeloRepository(session_factory)


@pytest.fixture
def auth_repository(session_factory):
    return SqlAlchemyAuthRepository(session_factory)


@pytest.fixture
def rbac_repository(session_factory):
    return SqlAlchemyRbacRepository(session_factory)


@pytest.fixture
def modelo_workflow(repository, session_factory):
    return build_modelo_module(repository=repository, session_factory=session_factory)


@pytest.fixture
def reference_lookup_service(session_factory):
    repository = SqlAlchemyReferenceLookupRepository(session_factory)
    return ReferenceLookupService(repository=repository)


@pytest.fixture
def auth_service(auth_repository):
    return build_auth_module(auth_repository)


@pytest.fixture
def rbac_service(rbac_repository):
    return build_rbac_module(rbac_repository, rbac_repository)

@pytest.fixture(autouse=True)
def wait_for_qt_threads_to_finish():
    yield
    
    thread_pool = QThreadPool.globalInstance()
    timeout = time.time() + 5.0  # Máximo 5 segundos de espera para no colgar el test
    
    # Mientras haya hilos trabajando, mantenemos respirando al hilo principal
    while thread_pool.activeThreadCount() > 0 and time.time() < timeout:
        # Esto permite que '_handle_success' y '_handle_failure' se ejecuten correctamente
        QCoreApplication.processEvents()
        time.sleep(0.01)
        
    # Limpieza final de seguridad
    if thread_pool.activeThreadCount() > 0:
        thread_pool.waitForDone(1000)
        QCoreApplication.processEvents()


@pytest.fixture(autouse=True)
def cleanup_qt_objects_after_test():
    yield

    BaseViewModel.dispose_live_instances()
    gc.collect()

    app = QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        for window in app.topLevelWindows():
            window.close()
            window.deleteLater()

    for _ in range(5):
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        if app is not None:
            app.processEvents()
        else:
            QCoreApplication.processEvents()
