import pytest
from fastapi import HTTPException

from cite_or_die.auth.authorizer import Authorizer
from cite_or_die.core.models import AuthContext, Role
from cite_or_die.security.walls import MatterMismatchError


def test_casbin_abac_allows_role_with_matching_tenant_and_matter() -> None:
    authorizer = Authorizer()
    ctx = AuthContext(
        tenant_id="tenant-a",
        matter_id="matter-a",
        subject="alice",
        roles=[Role.analyst],
    )

    authorizer.require(ctx, "upload", "tenant-a", "matter-a")


def test_casbin_abac_rejects_role_without_policy() -> None:
    authorizer = Authorizer()
    ctx = AuthContext(
        tenant_id="tenant-a",
        matter_id="matter-a",
        subject="alice",
        roles=[Role.viewer],
    )

    with pytest.raises(HTTPException):
        authorizer.require(ctx, "upload", "tenant-a", "matter-a")


def test_casbin_abac_rejects_cross_matter() -> None:
    authorizer = Authorizer()
    ctx = AuthContext(
        tenant_id="tenant-a",
        matter_id="matter-a",
        subject="alice",
        roles=[Role.admin],
    )

    with pytest.raises(MatterMismatchError):
        authorizer.require(ctx, "chat", "tenant-a", "matter-b")
