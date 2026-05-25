from __future__ import annotations

import pytest

from tests.builders.security_seed import create_permission, create_role, unique_value


def test_create_user_hashes_password_and_authenticates(auth_service, session_factory):
    username = unique_value("user")
    password = "Sup3rSecret!"

    with session_factory() as session:
        role = create_role(session, name=unique_value("role"))
        session.commit()

    created = auth_service.create_user(username=username, password=password, roles=[role.name])

    assert created.username == username
    assert created.roles == [role.name]
    assert created.password_hash != password

    auth_result = auth_service.authenticate(username, password)

    assert auth_result.user is not None
    assert auth_result.user.username == username
    assert auth_result.message == "OK"

    wrong_password = auth_service.authenticate(username, "clave-incorrecta")

    assert wrong_password.user is None
    assert wrong_password.message == "Clave incorrecta"

    listed_usernames = [user.username for user in auth_service.list_users()]
    assert username in listed_usernames


def test_create_user_rejects_duplicate_username(auth_service):
    username = unique_value("duplicate")
    auth_service.create_user(username=username, password="abc12345")

    with pytest.raises(ValueError, match="ya existe"):
        auth_service.create_user(username=username, password="abc12345")


def test_authenticate_unknown_user_returns_expected_message(auth_service):
    result = auth_service.authenticate(unique_value("missing"), "irrelevant")

    assert result.user is None
    assert result.message == "Usuario no encontrado"


def test_update_user_roles_replaces_existing_assignments(auth_service, rbac_service, session_factory):
    username = unique_value("roles_update")

    with session_factory() as session:
        first = create_role(session, name=unique_value("first"))
        second = create_role(session, name=unique_value("second"))
        session.commit()

    auth_service.create_user(username=username, password="abc12345", roles=[first.name])

    auth_service.update_user_roles(username, [second.name])

    profile = rbac_service.read_profile(username)
    assert profile["roles"] == [second.name]


def test_setting_superuser_clears_user_permission_overrides(auth_service, rbac_service, session_factory):
    username = unique_value("superuser_update")

    with session_factory() as session:
        create_permission(session, "viaje", "leer")
        session.commit()

    auth_service.create_user(username=username, password="abc12345")
    rbac_service.update_user_override_states(username, {"viaje": {"leer": "grant"}})

    auth_service.set_user_superuser(username, True)

    profile = rbac_service.read_profile(username)
    assert profile["user"]["is_superuser"] is True
    assert profile["overrides"] == {}
