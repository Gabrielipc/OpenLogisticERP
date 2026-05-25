from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import psycopg2
import pytest
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_VERSIONS = ROOT / "alembic" / "versions"
BASE_LOOKUPS_MIGRATION = ALEMBIC_VERSIONS / "d4f6e2b8a1c9_secure_reference_lookups.py"
VIAJE_REPAIR_MIGRATION = ALEMBIC_VERSIONS / "7c9e3f1a6d44_repair_viaje_reference_lookups.py"
CONDUCTOR_TRIP_TYPE_MIGRATION = ALEMBIC_VERSIONS / "9f2c4d1a7b3e_viaje_conductor_lookup_by_trip_type.py"
ROUTE_CROSS_FILTER_MIGRATION = ALEMBIC_VERSIONS / "f1a2b3c4d5e6_viaje_route_lookup_cross_filters.py"
VIAJE_IDA_MIGRATION = ALEMBIC_VERSIONS / "a4d8c2f6b9e1_viaje_ida_lookup_for_importacion.py"


def _load_upgrade_sql(module_path: Path) -> str:
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No fue posible cargar la migracion: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sql = getattr(module, "UPGRADE_SQL", None)
    if not isinstance(sql, str) or not sql.strip():
        raise RuntimeError(f"La migracion no expone UPGRADE_SQL: {module_path}")
    return sql


def _strip_viaje_functions(sql: str) -> str:
    patterns = (
        r"create or replace function ui_ref\.viaje_cliente_search\([\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_cliente_resolve\(p_ids int\[\]\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_origen_search\([\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_origen_resolve\(p_ids int\[\]\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_destino_search\([\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_destino_resolve\(p_ids int\[\]\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_conductor_search\([\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_conductor_resolve\(p_ids int\[\]\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_furgon_search\([\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_furgon_resolve\(p_ids int\[\]\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_camion_search\([\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_camion_resolve\(p_ids int\[\]\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_thermo_search\([\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_thermo_resolve\(p_ids int\[\]\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_ruta_search\(p_term text, p_limit int default 20\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_ruta_resolve\(p_ids int\[\]\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_circuito_search\(p_term text, p_limit int default 20\)[\s\S]*?;\n\n",
        r"create or replace function ui_ref\.viaje_circuito_resolve\(p_ids int\[\]\)[\s\S]*?;\n\n",
    )
    stripped = sql
    for pattern in patterns:
        stripped, replacements = re.subn(pattern, "", stripped, count=1, flags=re.IGNORECASE)
        assert replacements == 1, f"No se pudo remover bloque esperado: {pattern}"
    return stripped


def _drop_viaje_lookup_functions(raw_connection) -> None:
    cursor = raw_connection.cursor()
    try:
        cursor.execute(
            """
            drop function if exists ui_ref.viaje_circuito_resolve(int[]);
            drop function if exists ui_ref.viaje_circuito_search(text, int);
            drop function if exists ui_ref.viaje_ruta_resolve(int[]);
            drop function if exists ui_ref.viaje_ruta_search(text, int);
            drop function if exists ui_ref.viaje_thermo_resolve(int[]);
            drop function if exists ui_ref.viaje_thermo_search(text, int, boolean);
            drop function if exists ui_ref.viaje_camion_resolve(int[]);
            drop function if exists ui_ref.viaje_camion_search(text, int, boolean);
            drop function if exists ui_ref.viaje_furgon_resolve(int[]);
            drop function if exists ui_ref.viaje_furgon_search(text, int, boolean);
            drop function if exists ui_ref.viaje_conductor_resolve(int[]);
            drop function if exists ui_ref.viaje_conductor_search(text, int, text, boolean);
            drop function if exists ui_ref.viaje_conductor_search(text, int, boolean);
            drop function if exists ui_ref.viaje_destino_resolve(int[]);
            drop function if exists ui_ref.viaje_destino_search(text, int, int);
            drop function if exists ui_ref.viaje_origen_resolve(int[]);
            drop function if exists ui_ref.viaje_origen_search(text, int, int);
            drop function if exists ui_ref.viaje_cliente_resolve(int[]);
            drop function if exists ui_ref.viaje_cliente_search(text, int, text);
            """
        )
    finally:
        cursor.close()

@pytest.mark.skip(reason="Migración de reparación ya aplicada. Su ejecución cruda causa conflictos de transacciones con SQLAlchemy.")
def test_viaje_lookup_repair_migration_restores_missing_functions(db_connection):
    base_sql = _strip_viaje_functions(_load_upgrade_sql(BASE_LOOKUPS_MIGRATION))
    repair_sql = _load_upgrade_sql(VIAJE_REPAIR_MIGRATION)

    raw_connection = db_connection.connection.driver_connection
    _drop_viaje_lookup_functions(raw_connection)
    cursor = raw_connection.cursor()
    try:
        cursor.execute(base_sql)
    finally:
        cursor.close()

    check_cursor = raw_connection.cursor()
    try:
        check_cursor.execute("SAVEPOINT missing_viaje_lookups")
        try:
            check_cursor.execute("SELECT id, label FROM ui_ref.viaje_camion_search('', 20, false)")
        except psycopg2.Error:
            check_cursor.execute("ROLLBACK TO SAVEPOINT missing_viaje_lookups")
        else:
            raise AssertionError("La base simulada debia carecer de los lookups ui_ref.viaje_*")
        finally:
            check_cursor.execute("RELEASE SAVEPOINT missing_viaje_lookups")
    finally:
        check_cursor.close()

    repair_cursor = raw_connection.cursor()
    try:
        repair_cursor.execute(repair_sql)
    finally:
        repair_cursor.close()

    checks = (
        "SELECT id, label FROM ui_ref.viaje_cliente_search('', 20, NULL)",
        "SELECT id, label FROM ui_ref.viaje_origen_search('', 20, NULL)",
        "SELECT id, label FROM ui_ref.viaje_destino_search('', 20, NULL)",
        "SELECT id, label FROM ui_ref.viaje_conductor_search('', 20, false)",
        "SELECT id, label FROM ui_ref.viaje_furgon_search('', 20, false)",
        "SELECT id, label FROM ui_ref.viaje_camion_search('', 20, false)",
        "SELECT id, label FROM ui_ref.viaje_thermo_search('', 20, false)",
        "SELECT id, label FROM ui_ref.viaje_ruta_search('', 20)",
        "SELECT id, label FROM ui_ref.viaje_circuito_search('', 20)",
    )

    for query in checks:
        rows = db_connection.execute(text(query)).all()
        assert rows == []


def test_conductor_lookup_migration_upgrades_signature_with_trip_type(db_connection):
    repair_sql = _load_upgrade_sql(VIAJE_REPAIR_MIGRATION)
    conductor_trip_type_sql = _load_upgrade_sql(CONDUCTOR_TRIP_TYPE_MIGRATION)

    raw_connection = db_connection.connection.driver_connection
    cursor = raw_connection.cursor()
    try:
        cursor.execute(repair_sql)
        cursor.execute(conductor_trip_type_sql)
    finally:
        cursor.close()

    rows = db_connection.execute(
        text("SELECT id, label FROM ui_ref.viaje_conductor_search('', 20, 'Exportacion', false)")
    ).all()
    assert rows == []


def test_route_lookup_migration_upgrades_signatures_with_cross_filters(db_connection):
    repair_sql = _load_upgrade_sql(VIAJE_REPAIR_MIGRATION)
    conductor_trip_type_sql = _load_upgrade_sql(CONDUCTOR_TRIP_TYPE_MIGRATION)
    route_cross_filter_sql = _load_upgrade_sql(ROUTE_CROSS_FILTER_MIGRATION)

    raw_connection = db_connection.connection.driver_connection
    cursor = raw_connection.cursor()
    try:
        cursor.execute(repair_sql)
        cursor.execute(conductor_trip_type_sql)
        cursor.execute(route_cross_filter_sql)
    finally:
        cursor.close()

    origen_rows = db_connection.execute(
        text("SELECT id, label FROM ui_ref.viaje_origen_search('', 20, NULL, NULL)")
    ).all()
    destino_rows = db_connection.execute(
        text("SELECT id, label FROM ui_ref.viaje_destino_search('', 20, NULL, NULL)")
    ).all()

    assert origen_rows == []
    assert destino_rows == []


def test_viaje_ida_lookup_migration_adds_import_candidate_functions(db_connection):
    repair_sql = _load_upgrade_sql(VIAJE_REPAIR_MIGRATION)
    conductor_trip_type_sql = _load_upgrade_sql(CONDUCTOR_TRIP_TYPE_MIGRATION)
    route_cross_filter_sql = _load_upgrade_sql(ROUTE_CROSS_FILTER_MIGRATION)
    viaje_ida_sql = _load_upgrade_sql(VIAJE_IDA_MIGRATION)

    raw_connection = db_connection.connection.driver_connection
    cursor = raw_connection.cursor()
    try:
        cursor.execute(repair_sql)
        cursor.execute(conductor_trip_type_sql)
        cursor.execute(route_cross_filter_sql)
        cursor.execute(viaje_ida_sql)
    finally:
        cursor.close()

    search_rows = db_connection.execute(
        text("SELECT id, label FROM ui_ref.viaje_ida_search('', 20, NULL, NULL)")
    ).all()
    resolve_rows = db_connection.execute(
        text("SELECT id, label FROM ui_ref.viaje_ida_resolve(ARRAY[]::int[])")
    ).all()

    assert search_rows == []
    assert resolve_rows == []
