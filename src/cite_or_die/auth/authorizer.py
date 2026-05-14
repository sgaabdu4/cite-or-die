from fastapi import HTTPException

from cite_or_die.core.models import AuthContext, Role


class Authorizer:
    """Small ABAC layer: tenant match first, then role/action."""

    def require(self, ctx: AuthContext, action: str, tenant_id: str) -> None:
        if ctx.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="tenant boundary violation")

        allowed: dict[str, set[Role]] = {
            "upload": {Role.admin, Role.analyst},
            "chat": {Role.admin, Role.analyst, Role.viewer},
            "read": {Role.admin, Role.analyst, Role.viewer},
            "admin": {Role.admin},
        }
        if not set(ctx.roles).intersection(allowed.get(action, set())):
            raise HTTPException(status_code=403, detail="role not permitted")
