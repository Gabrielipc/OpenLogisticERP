"""Compile UI assets into a PySide6 Qt resource module."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def ui_root() -> Path:
    return Path(__file__).resolve().parent


def resolve_rcc() -> str:
    executable = shutil.which("pyside6-rcc")
    if executable:
        return executable
    candidate = project_root() / ".venv" / "Scripts" / "pyside6-rcc.exe"
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("pyside6-rcc no esta disponible. Instala PySide6 o ejecuta dentro del .venv del proyecto.")


def compile_resources(qrc_path: Path, output_path: Path) -> None:
    command = [resolve_rcc(), str(qrc_path), "-o", str(output_path)]
    subprocess.run(command, cwd=project_root(), check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    qrc_path = ui_root() / "assets.qrc"
    output_path = ui_root() / "resources_rc.py"
    if not qrc_path.is_file():
        raise FileNotFoundError(f"No se encontro el archivo QRC fuente: {qrc_path}")

    compile_resources(qrc_path, output_path)

    print(f"QRC fuente: {qrc_path}")
    print(f"Modulo generado: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
