from __future__ import annotations

from pathlib import Path


def test_application_and_presentation_do_not_import_model_entities_directly():
    root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp"
    forbidden = "infrastructure.persistence.modelo.model_entities"
    targets = (root / "application", root / "presentation")
    legacy_exceptions = {
        root / "application" / "modelo" / "consumo_analysis_service.py",
    }

    offenders: list[str] = []
    for base in targets:
        for path in base.rglob("*.py"):
            if path in legacy_exceptions:
                continue
            source = path.read_text(encoding="utf-8")
            if forbidden in source:
                offenders.append(str(path))

    assert offenders == []


def test_reports_application_and_presentation_do_not_import_sqlalchemy_or_model_entities_directly():
    root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp"
    targets = (root / "application" / "reports", root / "presentation" / "reports")
    forbidden_patterns = (
        "from sqlalchemy",
        "import sqlalchemy",
        "infrastructure.persistence.modelo.model_entities",
    )

    offenders: list[str] = []
    for base in targets:
        for path in base.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(pattern in source for pattern in forbidden_patterns):
                offenders.append(str(path))

    assert offenders == []


def test_workflow_presentation_does_not_use_sqlalchemy_or_unit_of_work_directly():
    root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "presentation" / "workflows"
    forbidden_patterns = {
        "factura": ("from sqlalchemy", "import sqlalchemy", "unit_of_work.run_in_transaction"),
        "recibo": ("from sqlalchemy", "import sqlalchemy", "unit_of_work.run_in_transaction"),
    }

    offenders: list[str] = []
    for workflow_name, patterns in forbidden_patterns.items():
        workflow_root = root / workflow_name
        for path in workflow_root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(pattern in source for pattern in patterns):
                offenders.append(str(path))

    assert offenders == []


def test_viaje_workflow_presentation_does_not_depend_on_query_service():
    workflow_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "presentation" / "workflows" / "viaje"

    offenders: list[str] = []
    for path in workflow_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "ModeloCatalogQueryService" in source:
            offenders.append(str(path))

    assert offenders == []
