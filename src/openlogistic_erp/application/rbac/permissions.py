"""Permission rules used by the RBAC module."""

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

ACCIONES = ("crear", "leer", "modificar", "eliminar")

RESOURCES = {
    "camion": "Planificacion",
    "conductor": "Planificacion",
    "thermo": "Planificacion",
    "furgon": "Planificacion",
    "ubicacion": "Planificacion",
    "ruta": "Planificacion",
    "viaje": "Operacion",
    "circuito": "Operacion",
    "tarifa_flete": "Operacion",
    "factura": "Tesoreria",
    "recibo": "Tesoreria",
    "impuesto": "Tesoreria",
    "cliente": "Tesoreria",
    "deuda_por_cliente": "Tesoreria",
}

PRIMARY_RESOURCES = tuple(RESOURCES)

DEPENDENCIAS_LECTURA = {
    "viaje": ["circuito"],
    "circuito": ["viaje"],
    "factura": ["viaje", "impuesto"],
    "recibo": ["factura"],
}

SHADOW_TABLES = {
    "factura": {
        "detalle_factura": "mirror",
        "factura_impuesto": "mirror",
        "gasto": "mirror",
    },
    "recibo": {
        "recibo_factura": "mirror",
    },
    "viaje": {
        "detalle_operacion": "mirror",
        "descarga": "mirror",
    },
}


@dataclass(frozen=True)
class PermissionConfig:
    acciones: tuple[str, ...] = field(default_factory=lambda: ACCIONES)
    resources: Mapping[str, str] = field(default_factory=lambda: RESOURCES)
    read_dependencies: Mapping[str, Iterable[str]] = field(default_factory=lambda: DEPENDENCIAS_LECTURA)
    shadow_tables: Mapping[str, Mapping[str, object]] = field(default_factory=lambda: SHADOW_TABLES)


def imply_read(perms: dict[str, set[str]]) -> dict[str, set[str]]:
    out = {resource: set(actions) for resource, actions in perms.items()}
    for actions in out.values():
        if {"crear", "modificar", "eliminar"} & actions:
            actions.add("leer")
    return out


def apply_read_dependencies(perms: dict[str, set[str]], dependencies: Mapping[str, Iterable[str]]) -> dict[str, set[str]]:
    out = {resource: set(actions) for resource, actions in perms.items()}
    queue = deque([resource for resource, actions in out.items() if "leer" in actions])
    seen = set(queue)
    while queue:
        resource = queue.popleft()
        for dep in dependencies.get(resource, []):
            dep_actions = out.setdefault(dep, set())
            if "leer" not in dep_actions:
                dep_actions.add("leer")
            if dep not in seen:
                seen.add(dep)
                queue.append(dep)
    return out


def expand_shadow_tables(perms: dict[str, set[str]], shadows: Mapping[str, Mapping[str, object]]) -> dict[str, set[str]]:
    out = {resource: set(actions) for resource, actions in perms.items()}
    for resource, actions in perms.items():
        for table_name, rule in shadows.get(resource, {}).items():
            if rule == "mirror":
                grant = set(actions)
            elif isinstance(rule, Iterable) and not isinstance(rule, (str, bytes)):
                grant = {str(item) for item in rule}
            else:
                continue
            out.setdefault(table_name, set()).update(grant)
    return out


def compile_permissions(user_selection: Mapping[str, Iterable[str]], cfg: PermissionConfig | None = None) -> dict[str, set[str]]:
    cfg = cfg or PermissionConfig()
    permisos = {
        resource: set(actions) & set(cfg.acciones)
        for resource, actions in user_selection.items()
        if actions
    }
    permisos = imply_read(permisos)
    permisos = apply_read_dependencies(permisos, cfg.read_dependencies)
    permisos = expand_shadow_tables(permisos, cfg.shadow_tables)
    return permisos
