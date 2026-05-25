from __future__ import annotations

import pytest

from openlogistic_erp.presentation.authorization import PresentationAuthorizationService
from tests.builders.security_seed import create_permission, create_role, unique_value


def test_presentation_authorization_denies_without_session(rbac_service):
    authorization = PresentationAuthorizationService(rbac_service)

    assert authorization.can("viaje", "read") is False
    assert authorization.resource_permissions("viaje") == {
        "read": False,
        "create": False,
        "edit": False,
        "delete": False,
    }


def test_presentation_authorization_maps_crud_permissions_from_profile(
    auth_service,
    rbac_service,
    session_factory,
):
    username = unique_value("presenter")
    with session_factory() as session:
        viaje_read = create_permission(session, "viaje", "leer")
        viaje_modify = create_permission(session, "viaje", "modificar")
        role = create_role(session, name=unique_value("ops"), permissions=[viaje_read, viaje_modify])
        session.commit()

    auth_service.create_user(username=username, password="abc12345", roles=[role.name])
    authorization = PresentationAuthorizationService(rbac_service)

    authorization.authenticate(username)

    assert authorization.can("viaje", "read") is True
    assert authorization.can("viaje", "detail") is True
    assert authorization.can("viaje", "edit") is True
    assert authorization.can("viaje", "save") is True
    assert authorization.can("viaje", "create") is False
    assert authorization.can("viaje", "delete") is False
    assert authorization.resource_permissions("viaje") == {
        "read": True,
        "create": False,
        "edit": True,
        "delete": False,
    }


def test_presentation_authorization_honors_user_denies(
    auth_service,
    rbac_service,
    session_factory,
):
    username = unique_value("denied")
    with session_factory() as session:
        viaje_read = create_permission(session, "viaje", "leer")
        viaje_modify = create_permission(session, "viaje", "modificar")
        role = create_role(session, name=unique_value("ops"), permissions=[viaje_read, viaje_modify])
        session.commit()

    auth_service.create_user(username=username, password="abc12345", roles=[role.name])
    rbac_service.update_user_override_states(username, {"viaje": {"modificar": "deny"}})
    authorization = PresentationAuthorizationService(rbac_service)

    authorization.authenticate(username)

    assert authorization.can("viaje", "read") is True
    assert authorization.can("viaje", "edit") is False


def test_presentation_authorization_superuser_allows_all(auth_service, rbac_service):
    username = unique_value("super")
    auth_service.create_user(username=username, password="abc12345", is_superuser=True)
    authorization = PresentationAuthorizationService(rbac_service)

    authorization.authenticate(username)

    assert authorization.can("anything", "read") is True
    assert authorization.can("viaje", "delete") is True


def test_presentation_authorization_require_raises_clear_message(rbac_service):
    authorization = PresentationAuthorizationService(rbac_service)

    with pytest.raises(PermissionError, match="No tienes permiso para modificar viaje"):
        authorization.require("viaje", "edit")
