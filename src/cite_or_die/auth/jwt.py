from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cite_or_die.core.config import Settings, get_settings
from cite_or_die.core.models import AuthContext, Role

bearer = HTTPBearer(auto_error=False)


def issue_token(
    tenant_id: str,
    subject: str,
    roles: list[Role],
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": [role.value for role in roles],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.auth_secret.get_secret_value(), algorithm="HS256")


def decode_token(token: str, settings: Settings | None = None) -> AuthContext:
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid bearer token") from exc

    roles = [Role(role) for role in payload.get("roles", [Role.analyst.value])]
    return AuthContext(
        tenant_id=str(payload["tenant_id"]),
        subject=str(payload["sub"]),
        roles=roles,
    )


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    if credentials is None:
        if settings.app_env == "dev":
            return AuthContext(tenant_id="dev", subject="dev-user", roles=[Role.admin])
        raise HTTPException(status_code=401, detail="missing bearer token")
    return decode_token(credentials.credentials, settings)
