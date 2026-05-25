from __future__ import annotations

import pytest
from sqlalchemy import select

from openlogistic_erp.infrastructure.persistence.security.models import UserPermission
from tests.builders.security_seed import create_permission, create_role, unique_value


def test_list_available_permissions_reads_from_database(rbac_service, session_factory):
    with session_factory() as session:
        permission = create_permission(session, resource=unique_value("resource"), action="leer")
        session.commit()

    available = rbac_service.list_available_permissions()
    keys = {(item.resource, item.action) for item in available}

    assert (permission.resource, permission.action) in keys


def test_save_role_permissions_compiles_dependencies_and_shadow_tables(rbac_service, rbac_repository, session_factory):
    with session_factory() as session:
        role = create_role(session, name=unique_value("ops"))
        for resource, action in (
            ("viaje", "crear"),
            ("viaje", "leer"),
            ("circuito", "leer"),
            ("detalle_operacion", "crear"),
            ("detalle_operacion", "leer"),
            ("descarga", "crear"),
            ("descarga", "leer"),
        ):
            create_permission(session, resource=resource, action=action)
        session.commit()

    effective = rbac_service.save_role_permissions(role.name, {"viaje": ["crear"]})

    assert effective == {
        "viaje": ["crear", "leer"],
        "circuito": ["leer"],
        "detalle_operacion": ["crear", "leer"],
        "descarga": ["crear", "leer"],
    }

    saved = {(cell.resource, cell.action) for cell in rbac_repository.get_role_permissions(role.name)}

    assert saved == {
        ("viaje", "crear"),
        ("viaje", "leer"),
        ("circuito", "leer"),
        ("detalle_operacion", "crear"),
        ("detalle_operacion", "leer"),
        ("descarga", "crear"),
        ("descarga", "leer"),
    }


def test_assign_roles_and_user_overrides_are_reflected_in_profile(
    auth_service,
    rbac_service,
    session_factory,
):
    username = unique_value("rbac_user")

    with session_factory() as session:
        cliente_read = create_permission(session, resource="cliente", action="leer")
        for resource, action in (
            ("factura", "leer"),
            ("viaje", "leer"),
            ("impuesto", "leer"),
            ("detalle_factura", "leer"),
            ("factura_impuesto", "leer"),
            ("gasto", "leer"),
        ):
            create_permission(session, resource=resource, action=action)
        role = create_role(session, name=unique_value("accounting"), permissions=[cliente_read])
        session.commit()

    auth_service.create_user(username=username, password="abc12345")
    rbac_service.assign_roles(username, [role.name])
    overrides = rbac_service.update_user_overrides(username, {"factura": {"leer": True}})
    profile = rbac_service.read_profile(username)

    assert role.name in profile["roles"]
    assert profile["user"]["username"] == username
    assert overrides == {
        "circuito": ["leer"],
        "descarga": ["leer"],
        "detalle_operacion": ["leer"],
        "factura": ["leer"],
        "viaje": ["leer"],
        "impuesto": ["leer"],
        "detalle_factura": ["leer"],
        "factura_impuesto": ["leer"],
        "gasto": ["leer"],
    }
    assert profile["overrides"] == {
        "circuito:leer": True,
        "descarga:leer": True,
        "detalle_operacion:leer": True,
        "factura:leer": True,
        "viaje:leer": True,
        "impuesto:leer": True,
        "detalle_factura:leer": True,
        "factura_impuesto:leer": True,
        "gasto:leer": True,
    }


def test_create_and_delete_role_rejects_roles_assigned_to_users(
    auth_service,
    rbac_service,
):
    role_name = unique_value("security_admin")
    username = unique_value("role_user")

    created = rbac_service.create_role(role_name)

    assert created.name == role_name
    assert role_name in [role.name for role in rbac_service.list_roles()]

    auth_service.create_user(username=username, password="abc12345", roles=[role_name])

    with pytest.raises(ValueError, match="asignado"):
        rbac_service.delete_role(role_name)


def test_delete_role_removes_unassigned_role(rbac_service):
    role_name = unique_value("unused_role")
    rbac_service.create_role(role_name)

    assert role_name in [role.name for role in rbac_service.list_roles()]

    rbac_service.delete_role(role_name)

    assert role_name not in [role.name for role in rbac_service.list_roles()]


def test_user_override_states_persist_grants_denies_and_skip_inherit(
    auth_service,
    rbac_service,
    session_factory,
):
    username = unique_value("override_states")

    with session_factory() as session:
        for resource, action in (
            ("viaje", "leer"),
            ("viaje", "modificar"),
            ("cliente", "leer"),
        ):
            create_permission(session, resource, action)
        session.commit()

    auth_service.create_user(username=username, password="abc12345")

    saved = rbac_service.update_user_override_states(
        username,
        {
            "viaje": {"leer": "grant", "modificar": "deny"},
            "cliente": {"leer": "inherit"},
        },
    )

    assert saved == {
        "viaje": {"leer": "grant", "modificar": "deny"},
    }

    profile = rbac_service.read_profile(username)
    assert profile["overrides"] == {
        "viaje:leer": True,
        "viaje:modificar": False,
    }

    with session_factory() as session:
        persisted = session.execute(select(UserPermission)).scalars().all()
        states = {
            (row.permission.resource, row.permission.action): row.grant_or_deny
            for row in persisted
            if str(row.user.username) == username
        }

    assert states == {
        ("viaje", "leer"): True,
        ("viaje", "modificar"): False,
    }
