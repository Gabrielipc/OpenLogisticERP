# OpenLogisticERP

OpenLogisticERP is a desktop ERP application for logistics operations, built with Python, PySide6/QML, SQLAlchemy, Alembic, and PostgreSQL. It focuses on operational workflows such as trips, circuits, billing, receipts, role-based access control, dashboards, and reports.

> Current UI language: the application interface is currently available only in Spanish. English documentation is provided for public project visibility, but the desktop UI has not been localized yet.

This repository was published as a clean initial public release from a previously private development history.

## Features

- Desktop application built with PySide6 and QML.
- PostgreSQL persistence through SQLAlchemy.
- Alembic migrations for schema management.
- Authentication and role-based access control.
- Logistics workflow modules for trips, circuits, billing, receipts, and operational details.
- Dashboard and reporting services with PDF/XLSX export support.
- Integration tests covering application services, presentation view models, reports, and database workflows.

## Tech Stack

- Python 3.10+
- PySide6 / QML
- SQLAlchemy
- Alembic
- PostgreSQL
- pytest
- uv or pip for dependency management

## Setup

Clone the repository:

```bash
git clone https://github.com/Gabrielipc/openlogistic-erp.git
cd openlogistic-erp
```

Create an environment file:

```bash
cp .env.example .env
```

Edit `.env` and set `OPENLOGISTIC_DATABASE_URL` to a PostgreSQL database URL:

```env
OPENLOGISTIC_ENV=development
OPENLOGISTIC_DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/openlogistic
OPENLOGISTIC_RLS_ENFORCED=true
```

Install dependencies with uv:

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

On Windows Git Bash, activate the virtual environment with:

```bash
source .venv/Scripts/activate
```

## Database

Run Alembic migrations after configuring the database URL:

```bash
alembic upgrade head
```

If your local setup does not include `alembic.ini`, create one for your environment or provide the database URL through `OPENLOGISTIC_DATABASE_URL`.

## Running The Application

With the package installed:

```bash
openlogistic-erp
```

Or directly through Python:

```bash
python -m openlogistic_erp.main
```

## Generated Assets

QML type metadata is generated and should not be committed:

```bash
olerp-qmltypes
```

Qt resources can be compiled with:

```bash
olerp-compile-assets
```

## Tests

Run the test suite:

```bash
pytest
```

Some integration tests expect a configured PostgreSQL database and the environment variables from `.env`.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

---

# OpenLogisticERP

OpenLogisticERP es una aplicacion  ERP de escritorio para operaciones logisticas, construido con Python, PySide6/QML, SQLAlchemy, Alembic y PostgreSQL. Esta enfocado en flujos operativos como viajes, circuitos, facturacion, recibos, control de acceso por roles, dashboards y reportes.

> Idioma actual de la UI: la interfaz de la aplicacion actualmente esta disponible solo en español. La documentacion en ingles se incluye para visibilidad publica del proyecto, pero la UI de escritorio todavia no esta localizada.

Este repositorio fue publicado como una version publica inicial limpia a partir de un historial de desarrollo previamente privado.

## Funcionalidades

- Aplicacion de escritorio construida con PySide6 y QML.
- Persistencia en PostgreSQL mediante SQLAlchemy.
- Migraciones de esquema con Alembic.
- Autenticacion y control de acceso por roles.
- Modulos de flujo logistico para viajes, circuitos, facturacion, recibos y detalles operativos.
- Servicios de dashboard y reportes con soporte de exportacion PDF/XLSX.
- Pruebas de integracion para servicios de aplicacion, view models de presentacion, reportes y flujos de base de datos.

## Stack Tecnico

- Python 3.10+
- PySide6 / QML
- SQLAlchemy
- Alembic
- PostgreSQL
- pytest
- uv o pip para gestion de dependencias

## Configuracion

Clona el repositorio:

```bash
git clone https://github.com/your-user/openlogistic-erp.git
cd openlogistic-erp
```

Crea un archivo de entorno:

```bash
cp .env.example .env
```

Edita `.env` y define `OPENLOGISTIC_DATABASE_URL` con una URL de PostgreSQL:

```env
OPENLOGISTIC_ENV=development
OPENLOGISTIC_DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/openlogistic
OPENLOGISTIC_RLS_ENFORCED=true
```

Instala dependencias con uv:

```bash
uv sync
```

O con pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

En Windows Git Bash, activa el entorno virtual con:

```bash
source .venv/Scripts/activate
```

## Base De Datos

Ejecuta las migraciones de Alembic despues de configurar la URL de base de datos:

```bash
alembic upgrade head
```

Si tu entorno local no incluye `alembic.ini`, crea uno para tu ambiente o proporciona la URL de base de datos mediante `OPENLOGISTIC_DATABASE_URL`.

## Ejecutar La Aplicacion

Con el paquete instalado:

```bash
openlogistic-erp
```

O directamente con Python:

```bash
python -m openlogistic_erp.main
```

## Archivos Generados

La metadata de tipos QML se genera automaticamente y no deberia versionarse:

```bash
olerp-qmltypes
```

Los recursos Qt pueden compilarse con:

```bash
olerp-compile-assets
```

## Pruebas

Ejecuta la suite de pruebas:

```bash
pytest
```

Algunas pruebas de integracion esperan una base de datos PostgreSQL configurada y las variables de entorno de `.env`.


## Licencia

Este proyecto esta licenciado bajo la licencia MIT. Ver [LICENSE](LICENSE).
