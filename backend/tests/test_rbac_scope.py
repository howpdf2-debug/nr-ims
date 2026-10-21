"""RBAC matrix + data-scope SQL clause. Pure unit tests (no DB): the matrix is the security contract."""

import pytest

from app.models.user import User
from app.security.rbac import ROLE_PERMISSIONS, Permission, Role
from app.security.scope import is_unrestricted, scope_stations, station_clause


def _user(role: str, scopes: list[str]) -> User:
    return User(email=f"{role}@t.local", hashed_password="x", role=role, scopes=scopes, is_active=True)


def _sql(clause) -> str:
    return str(clause.compile(compile_kwargs={"literal_binds": True}))


def test_every_role_has_a_permission_set():
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_irca_admin_has_every_permission():
    assert ROLE_PERMISSIONS[Role.IRCA_ADMIN] == set(Permission)


@pytest.mark.parametrize("perm", [Permission.USER_MANAGE, Permission.DISCOVERY_MANAGE])
def test_only_irca_admin_manages_users_and_discovery(perm):
    holders = {r for r, perms in ROLE_PERMISSIONS.items() if perm in perms}
    assert holders == {Role.IRCA_ADMIN}


def test_operator_is_read_only():
    perms = ROLE_PERMISSIONS[Role.OPERATOR]
    assert perms == {Permission.DEVICE_READ, Permission.ALARM_READ}


def test_tier1_cannot_manage_stations_or_read_audit():
    perms = ROLE_PERMISSIONS[Role.TIER1_INCHARGE]
    assert Permission.STATION_MANAGE not in perms and Permission.AUDIT_READ not in perms
    assert Permission.ALARM_ACK in perms and Permission.DEVICE_WRITE in perms


def test_divisional_admin_can_manage_stations_and_read_audit():
    perms = ROLE_PERMISSIONS[Role.DIVISIONAL_ADMIN]
    assert {Permission.STATION_MANAGE, Permission.AUDIT_READ} <= perms
    assert Permission.USER_MANAGE not in perms


def test_unrestricted_users():
    assert is_unrestricted(_user("irca_admin", []))
    assert is_unrestricted(_user("operator", ["*"]))
    assert not is_unrestricted(_user("operator", ["BSB"]))


def test_unrestricted_has_no_clause():
    assert station_clause(_user("irca_admin", [])) is None


def test_empty_scopes_see_nothing():
    assert "false" in _sql(station_clause(_user("operator", []))).lower()


def test_scope_matches_division_code_and_parent():
    sql = _sql(station_clause(_user("tier1_incharge", ["BSB"])))
    assert "stations.division IN ('BSB')" in sql
    assert "stations.code IN ('BSB')" in sql
    assert "stations.parent_station_code IN ('BSB')" in sql


def test_scope_stations_passthrough_for_admin():
    from sqlalchemy import select

    from app.models.station import Station

    q = select(Station)
    assert scope_stations(q, _user("irca_admin", ["*"])) is q
