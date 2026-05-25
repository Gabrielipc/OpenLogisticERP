"""Helpers to generate QML type metadata from PySide6-decorated classes."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from .qml_module import QML_IMPORT_MAJOR_VERSION, QML_IMPORT_MINOR_VERSION, QML_IMPORT_NAME
from .qt import PYSIDE6_FILE

REPO_ROOT = Path(__file__).resolve().parents[3]
QML_SOURCE_ROOT = REPO_ROOT / "src" / "openlogistic_erp" / "ui" / "qml"
QML_MODULE_DIR = QML_SOURCE_ROOT / "OpenLogistic" / "Models"

DECORATED_PYTHON_FILES: tuple[Path, ...] = (
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "viewmodels" / "base_view_model.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "viewmodels" / "runtime_session_view_model.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "dashboard.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "catalog" / "forms.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "app_shell.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "common.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "factura" / "forms.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "recibo" / "forms.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "circuito" / "forms.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "circuito" / "detail.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "circuito" / "viewmodels.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "viaje" / "forms.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "viaje" / "detail.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "viaje" / "viewmodels.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "workflows" / "seguridad" / "viewmodels.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "catalog" / "form_host_view_model.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "catalog" / "screen_view_model.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "catalog" / "table_model.py",
    REPO_ROOT / "src" / "openlogistic_erp" / "presentation" / "catalog" / "workbench_view_model.py",
)

QML_FILES: tuple[Path, ...] = (
    QML_SOURCE_ROOT / "Main.qml",
    QML_SOURCE_ROOT / "DashboardPage.qml",
    QML_SOURCE_ROOT / "catalog" / "CatalogFilterPanel.qml",
    QML_SOURCE_ROOT / "catalog" / "CatalogScreenPage.qml",
    QML_SOURCE_ROOT / "shared" / "forms" / "GenericCatalogForm.qml",
    QML_SOURCE_ROOT / "workflows" / "common" / "WorkflowPlaceholderPage.qml",
    QML_SOURCE_ROOT / "workflows" / "factura" / "FacturaWorkflowForm.qml",
    QML_SOURCE_ROOT / "workflows" / "recibo" / "ReciboWorkflowForm.qml",
    QML_SOURCE_ROOT / "workflows" / "seguridad" / "SecurityAdminPage.qml",
    QML_SOURCE_ROOT / "workflows" / "circuito" / "CircuitoWorkflowPage.qml",
    QML_SOURCE_ROOT / "workflows" / "circuito" / "detail" / "CircuitoDetailPage.qml",
    QML_SOURCE_ROOT / "workflows" / "circuito" / "detail" / "CircuitoHeaderPanel.qml",
    QML_SOURCE_ROOT / "workflows" / "circuito" / "detail" / "CircuitoMovimientosSection.qml",
    QML_SOURCE_ROOT / "workflows" / "circuito" / "detail" / "CircuitoSectionsPanel.qml",
    QML_SOURCE_ROOT / "workflows" / "circuito" / "detail" / "CircuitoTripsPanel.qml",
    QML_SOURCE_ROOT / "workflows" / "circuito" / "detail" / "TripReadOnlyBlock.qml",
    QML_SOURCE_ROOT / "workflows" / "viaje" / "detail" / "ViajeDetailOperationsPanel.qml",
    QML_SOURCE_ROOT / "workflows" / "viaje" / "detail" / "ViajeDetailPage.qml",
    QML_SOURCE_ROOT / "workflows" / "viaje" / "detail" / "ViajeDetailSummaryPanel.qml",
    QML_SOURCE_ROOT / "workflows" / "viaje" / "fields" / "OperationalDetailFieldRenderer.qml",
    QML_SOURCE_ROOT / "workflows" / "viaje" / "OperationalDetailSectionForm.qml",
    QML_SOURCE_ROOT / "workflows" / "viaje" / "OperationalFuelOrdersSection.qml",
    QML_SOURCE_ROOT / "workflows" / "viaje" / "ViajeWorkflowPage.qml",
    QML_SOURCE_ROOT / "workflows" / "viaje" / "ViajeWorkflowForm.qml",
)


def _tool_path(tool_name: str) -> Path:
    scripts_dir = Path(sys.executable).resolve().parent
    suffix = ".exe" if sys.platform.startswith("win") else ""
    tool = scripts_dir / f"{tool_name}{suffix}"
    if not tool.exists():
        raise FileNotFoundError(f"No se encontro {tool_name!r} en {scripts_dir}")
    return tool


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def generate_qmltypes(output_dir: Path | None = None) -> Path:
    """Generate a single qmltypes contract and qmldir for the OpenLogistic.Models module."""

    module_dir = output_dir or QML_MODULE_DIR
    module_dir.mkdir(parents=True, exist_ok=True)
    build_dir = module_dir / ".typegen"
    build_dir.mkdir(parents=True, exist_ok=True)

    metaobjectdump = _tool_path("pyside6-metaobjectdump")
    qmltyperegistrar = _tool_path("pyside6-qmltyperegistrar")
    metatypes_dir = Path(PYSIDE6_FILE).resolve().parent / "metatypes"

    combined_metatypes = build_dir / "OpenLogisticModels.metatypes.json"
    combined_qmltypes = module_dir / "OpenLogisticModels.qmltypes"
    combined_cpp = build_dir / "OpenLogisticModels_qmltyperegistrations.cpp"

    _run(
        [str(metaobjectdump), "-o", str(combined_metatypes), *[str(path) for path in DECORATED_PYTHON_FILES]]
    )
    _run(
        [
            str(qmltyperegistrar),
            "--generate-qmltypes",
            str(combined_qmltypes),
            "-o",
            str(combined_cpp),
            str(combined_metatypes),
            "--import-name",
            QML_IMPORT_NAME,
            "--major-version",
            str(QML_IMPORT_MAJOR_VERSION),
            "--minor-version",
            str(QML_IMPORT_MINOR_VERSION),
            f"--foreign-types={metatypes_dir / 'qt6core_metatypes.json'},{metatypes_dir / 'qt6qml_metatypes.json'}",
        ]
    )

    (module_dir / "qmldir").write_text(
        f"module {QML_IMPORT_NAME}\n"
        f"typeinfo {combined_qmltypes.name}\n",
        encoding="utf-8",
    )

    return module_dir


def run_qmllint(module_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run qmllint against the current QML surface using a generated module directory."""

    qmllint = _tool_path("pyside6-qmllint")
    return subprocess.run(
        [str(qmllint), "-i", str(module_dir / "qmldir"), *[str(path) for path in QML_FILES]],
        check=False,
        capture_output=True,
        text=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for regenerating QML type metadata."""

    parser = argparse.ArgumentParser(description="Generate OpenLogistic QML type metadata.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional target directory for the generated OpenLogistic.Models module.",
    )
    parser.add_argument(
        "--lint",
        action="store_true",
        help="Run qmllint after generating the module metadata.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print the output module directory when generation succeeds.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    module_dir = generate_qmltypes(args.output_dir)
    if not args.quiet:
        print(module_dir)

    if not args.lint:
        return 0

    result = run_qmllint(module_dir)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
