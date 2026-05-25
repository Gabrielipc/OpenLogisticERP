from __future__ import annotations

from openlogistic_erp.infrastructure.persistence.session_identity import (
    clear_authenticated_user_id,
    get_authenticated_user_id,
)
from openlogistic_erp.presentation import PresentationAuthorizationService, RuntimeSessionViewModel
from tests.builders.security_seed import create_permission, create_role, unique_value


def test_runtime_session_view_model_sets_authenticated_user_context(auth_service, session_factory):
    username = unique_value("runtime")
    password = "secret123"

    with session_factory() as session:
        role = create_role(session, name=unique_value("role"))
        session.commit()

    created = auth_service.create_user(username=username, password=password, roles=[role.name])
    view_model = RuntimeSessionViewModel(auth_service)

    try:
        view_model.login(username, password)

        assert view_model.is_authenticated is True
        assert view_model.current_username == username
        assert view_model.roles == [role.name]
        assert get_authenticated_user_id() == created.id
        assert view_model.error_message == ""
    finally:
        clear_authenticated_user_id()


def test_runtime_session_view_model_refreshes_authorization_on_login(
    auth_service,
    rbac_service,
    session_factory,
):
    username = unique_value("runtime_authz")
    password = "secret123"

    with session_factory() as session:
        viaje_read = create_permission(session, "viaje", "leer")
        role = create_role(session, name=unique_value("role"), permissions=[viaje_read])
        session.commit()

    auth_service.create_user(username=username, password=password, roles=[role.name])
    authorization = PresentationAuthorizationService(rbac_service)
    view_model = RuntimeSessionViewModel(auth_service, authorization_service=authorization)

    try:
        view_model.login(username, password)

        assert authorization.can("viaje", "read") is True
        assert authorization.username == username
    finally:
        clear_authenticated_user_id()


def test_runtime_session_view_model_logout_clears_session_context(auth_service):
    username = unique_value("runtime")
    password = "secret123"
    created = auth_service.create_user(username=username, password=password)
    view_model = RuntimeSessionViewModel(auth_service)

    try:
        view_model.login(username, password)
        assert get_authenticated_user_id() == created.id

        view_model.logout()

        assert view_model.is_authenticated is False
        assert view_model.current_username == ""
        assert get_authenticated_user_id() is None
    finally:
        clear_authenticated_user_id()


def test_runtime_session_view_model_logout_clears_authorization(auth_service, rbac_service):
    username = unique_value("runtime_clear")
    password = "secret123"
    auth_service.create_user(username=username, password=password, is_superuser=True)
    authorization = PresentationAuthorizationService(rbac_service)
    view_model = RuntimeSessionViewModel(auth_service, authorization_service=authorization)

    try:
        view_model.login(username, password)
        assert authorization.can("viaje", "delete") is True

        view_model.logout()

        assert authorization.username == ""
        assert authorization.can("viaje", "delete") is False
    finally:
        clear_authenticated_user_id()
