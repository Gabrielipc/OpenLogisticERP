from __future__ import annotations

from pathlib import Path

from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.movimiento_adicional import (
    MovimientoAdicional,
)


def test_movimiento_adicional_exposes_es_triangulado_column():
    column = MovimientoAdicional.__table__.columns.get("es_triangulado")

    assert column is not None
    assert column.default is not None
    assert column.nullable is False


def test_es_triangulado_migration_documents_legacy_backfill():
    versions_dir = Path("alembic/versions")
    matching = [
        path
        for path in versions_dir.glob("*es_triangulado*movimiento_adicional*.py")
        if path.is_file()
    ]

    assert matching
    content = matching[0].read_text(encoding="utf-8")
    assert "movimiento_adicional" in content
    assert "es_triangulado" in content
    assert "triangulado" in content.lower()
    assert "descripcion" in content
