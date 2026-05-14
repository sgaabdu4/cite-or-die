import casbin  # type: ignore[import-untyped]
from casbin.persist.adapters import StringAdapter  # type: ignore[import-untyped]
from fastapi import HTTPException

from cite_or_die.core.models import AuthContext
from cite_or_die.security.walls import MatterMismatchError

CASBIN_MODEL = """
[request_definition]
r = sub_tenant, sub_matter, roles, tenant, matter, act

[policy_definition]
p = role, act

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = r.sub_tenant == r.tenant && r.sub_matter == r.matter && r.act == p.act \
&& role_in(r.roles, p.role)
"""

CASBIN_POLICY = """
p, admin, upload
p, analyst, upload
p, admin, chat
p, analyst, chat
p, viewer, chat
p, admin, read
p, analyst, read
p, viewer, read
p, admin, admin
"""


class Authorizer:
    """Casbin-backed ABAC layer for tenant, matter, role, and action checks."""

    def __init__(self) -> None:
        # Source: https://github.com/pycasbin/fastapi-authz is the brief's Casbin ABAC reference.
        model = casbin.Model()
        model.load_model_from_text(CASBIN_MODEL)
        self.enforcer = casbin.Enforcer(model, StringAdapter(CASBIN_POLICY))
        self.enforcer.add_function("role_in", self._role_in)

    def require(
        self, ctx: AuthContext, action: str, tenant_id: str, matter_id: str | None = None
    ) -> None:
        effective_matter = matter_id or ctx.matter_id
        allowed = self.enforcer.enforce(
            ctx.tenant_id,
            ctx.matter_id,
            [role.value for role in ctx.roles],
            tenant_id,
            effective_matter,
            action,
        )
        if ctx.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="tenant boundary violation")
        if ctx.matter_id != effective_matter:
            raise MatterMismatchError()
        if not allowed:
            raise HTTPException(status_code=403, detail="role not permitted")

    @staticmethod
    def _role_in(roles: list[str], role: str) -> bool:
        return role in roles
