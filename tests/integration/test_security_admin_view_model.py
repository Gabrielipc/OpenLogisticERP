from __future__ import annotations

from openlogistic_erp.infrastructure.persistence.session_identity import clear_authenticated_user_id
from openlogistic_erp.presentation import RuntimeSessionViewModel, SecurityAdminViewModel
from tests.builders.security_seed import create_permission, create_role, unique_value


def _login_superuser(auth_service) -> RuntimeSessionViewModel:
    username = unique_value("admin")
    password = "secret123"
    auth_service.create_user(username=username, password=password, is_superuser=True)
    runtime = RuntimeSessionViewModel(auth_service)
    runtime.login(username, password)
    clear_authenticated_user_id()
    return runtime


def test_security_admin_initialize_loads_users_roles_and_permissions(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)
    username = unique_value("managed")

    with session_factory() as session:
        role = create_role(session, name=unique_value("ops"))
        permission = create_permission(session, "viaje", "leer")
        session.commit()

    auth_service.create_user(username=username, password="abc12345", roles=[role.name])
    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)

    view_model.initialize()

    assert view_model.can_manage_security is True
    assert username in [user["username"] for user in view_model.users]
    assert role.name in [item["name"] for item in view_model.roles]
    assert {
        "resource": permission.resource,
        "action": permission.action,
        "domain": "Operacion",
        "resource_label": "Viaje",
    } in view_model.available_permissions


def test_security_admin_create_user_refreshes_list(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)
    username = unique_value("created_from_vm")

    with session_factory() as session:
        role = create_role(session, name=unique_value("viewer"))
        session.commit()

    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)
    view_model.initialize()

    view_model.create_user(username, "abc12345", False, [role.name])

    assert username in [user["username"] for user in view_model.users]
    assert rbac_service.read_profile(username)["roles"] == [role.name]
    assert view_model.active_page == "user_detail"
    assert view_model.selected_user_profile["user"]["username"] == username
    assert view_model.error_message == ""


def test_security_admin_select_user_exposes_profile_for_detail(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)
    username = unique_value("detail_vm")

    with session_factory() as session:
        role = create_role(session, name=unique_value("detail_role"))
        create_permission(session, "viaje", "leer")
        session.commit()

    auth_service.create_user(username=username, password="abc12345", roles=[role.name])
    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)
    view_model.initialize()

    view_model.select_user(username)

    assert view_model.active_page == "user_detail"
    assert view_model.selected_user_profile["user"]["username"] == username
    assert view_model.selected_user_profile["roles"] == [role.name]
    assert view_model.error_message == ""


def test_security_admin_select_user_exposes_effective_permission_rows(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)
    username = unique_value("matrix_vm")

    with session_factory() as session:
        viaje_read = create_permission(session, "viaje", "leer")
        create_permission(session, "viaje", "modificar")
        create_permission(session, "viaje", "eliminar")
        create_permission(session, "factura", "leer")
        role = create_role(session, name=unique_value("matrix_role"), permissions=[viaje_read])
        session.commit()

    auth_service.create_user(username=username, password="abc12345", roles=[role.name])
    rbac_service.update_user_override_states(
        username,
        {
            "viaje": {"modificar": "grant", "eliminar": "deny"},
            "factura": {"leer": "deny"},
        },
    )
    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)
    view_model.initialize()

    view_model.select_user(username)

    rows = {
        row["resource"]: {permission["action"]: permission for permission in row["permissions"]}
        for row in view_model.selected_user_profile["permission_rows"]
    }
    assert rows["viaje"]["leer"]["visual_state"] == "EFFECTIVE_ROLE"
    assert rows["viaje"]["leer"]["effective"] is True
    assert rows["viaje"]["modificar"]["visual_state"] == "ALLOW_OVERRIDE"
    assert rows["viaje"]["modificar"]["override"] == "grant"
    assert rows["viaje"]["eliminar"]["visual_state"] == "DENY"
    assert rows["viaje"]["eliminar"]["effective"] is False
    assert rows["factura"]["leer"]["visual_state"] == "DENY"


def test_security_admin_create_and_select_role_exposes_detail(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)
    role_name = unique_value("created_role")

    with session_factory() as session:
        permission = create_permission(session, "viaje", "leer")
        session.commit()

    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)
    view_model.initialize()

    view_model.create_role(role_name)
    view_model.save_role_permissions(role_name, {"viaje": ["leer"]})

    assert role_name in [role["name"] for role in view_model.roles]
    assert view_model.active_page == "role_detail"
    assert view_model.selected_role_profile["name"] == role_name
    assert {
        "resource": permission.resource,
        "action": permission.action,
        "granted": True,
    } in view_model.selected_role_profile["permissions"]
    assert view_model.error_message == ""


def test_security_admin_create_role_with_permissions_opens_detail(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)
    role_name = unique_value("created_role_permissions")

    with session_factory() as session:
        permission = create_permission(session, "viaje", "leer")
        create_permission(session, "viaje", "modificar")
        session.commit()

    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)
    view_model.initialize()
    view_model.begin_create_role()

    assert view_model.active_page == "new_role"
    rows = {
        row["resource"]: {permission["action"]: permission for permission in row["permissions"]}
        for row in view_model.new_role_profile["permission_rows"]
    }
    assert rows["viaje"]["leer"]["granted"] is False

    view_model.create_role_with_permissions(role_name, {"viaje": ["leer"]})

    assert role_name in [role["name"] for role in view_model.roles]
    assert view_model.active_page == "role_detail"
    assert view_model.selected_role_profile["name"] == role_name
    assert {
        "resource": permission.resource,
        "action": permission.action,
        "granted": True,
    } in view_model.selected_role_profile["permissions"]
    assert view_model.error_message == ""


def test_security_admin_select_role_exposes_permission_rows_for_all_available_permissions(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)

    with session_factory() as session:
        viaje_read = create_permission(session, "viaje", "leer")
        create_permission(session, "viaje", "modificar")
        role = create_role(session, name=unique_value("role_matrix"), permissions=[viaje_read])
        session.commit()

    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)
    view_model.initialize()

    view_model.select_role(role.name)

    rows = {
        row["resource"]: {permission["action"]: permission for permission in row["permissions"]}
        for row in view_model.selected_role_profile["permission_rows"]
    }
    assert rows["viaje"]["leer"]["granted"] is True
    assert rows["viaje"]["leer"]["visual_state"] == "GRANTED"
    assert rows["viaje"]["modificar"]["granted"] is False
    assert rows["viaje"]["modificar"]["visual_state"] == "NONE"


def test_security_admin_permission_rows_only_show_primary_resources_with_domain_and_label(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)

    with session_factory() as session:
        viaje_create = create_permission(session, "viaje", "crear")
        create_permission(session, "detalle_operacion", "crear")
        create_permission(session, "descarga", "crear")
        create_permission(session, "factura", "leer")
        create_permission(session, "factura_recibo", "leer")
        create_permission(session, "recibo_factura", "leer")
        role = create_role(session, name=unique_value("primary_matrix"), permissions=[viaje_create])
        session.commit()

    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)
    view_model.initialize()

    view_model.select_role(role.name)

    rows = view_model.selected_role_profile["permission_rows"]
    row_by_resource = {row["resource"]: row for row in rows}
    assert "viaje" in row_by_resource
    assert "factura" in row_by_resource
    assert "detalle_operacion" not in row_by_resource
    assert "descarga" not in row_by_resource
    assert "factura_recibo" not in row_by_resource
    assert "recibo_factura" not in row_by_resource
    assert row_by_resource["viaje"]["domain"] == "Operacion"
    assert row_by_resource["viaje"]["resource_label"] == "Viaje"
    assert row_by_resource["factura"]["domain"] == "Tesoreria"
    assert row_by_resource["factura"]["resource_label"] == "Factura"


def test_security_admin_permission_rows_are_grouped_by_domain_then_resource_label(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)

    with session_factory() as session:
        for resource in ["factura", "camion", "recibo", "viaje", "conductor", "tarifa_flete"]:
            create_permission(session, resource, "leer")
        role = create_role(session, name=unique_value("domain_order"))
        session.commit()

    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)
    view_model.initialize()

    view_model.select_role(role.name)

    rows = [
        (row["domain"], row["resource_label"])
        for row in view_model.selected_role_profile["permission_rows"]
        if row["resource"] in {"factura", "camion", "recibo", "viaje", "conductor", "tarifa_flete"}
    ]
    assert rows == [
        ("Planificacion", "Camion"),
        ("Planificacion", "Conductor"),
        ("Operacion", "Tarifa Flete"),
        ("Operacion", "Viaje"),
        ("Tesoreria", "Factura"),
        ("Tesoreria", "Recibo"),
    ]


def test_security_admin_save_user_overrides_preserves_grants_and_denies(
    auth_service,
    rbac_service,
    session_factory,
):
    runtime = _login_superuser(auth_service)
    username = unique_value("override_vm")

    with session_factory() as session:
        create_permission(session, "viaje", "leer")
        create_permission(session, "viaje", "modificar")
        session.commit()

    auth_service.create_user(username=username, password="abc12345")
    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)
    view_model.initialize()

    view_model.save_user_overrides(
        username,
        {"viaje": {"leer": "grant", "modificar": "deny"}},
    )

    assert view_model.selected_user_profile["overrides"] == {
        "viaje:leer": True,
        "viaje:modificar": False,
    }


def test_security_admin_blocks_non_superuser_operations(auth_service, rbac_service):
    username = unique_value("regular")
    password = "secret123"
    auth_service.create_user(username=username, password=password)
    runtime = RuntimeSessionViewModel(auth_service)
    runtime.login(username, password)
    clear_authenticated_user_id()
    view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime)

    view_model.initialize()
    view_model.create_role(unique_value("blocked_role"))

    assert view_model.can_manage_security is False
    assert view_model.users == []
    assert "superuser" in view_model.error_message.lower()
