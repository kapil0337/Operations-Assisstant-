"""FastAPI dependency that resolves an authenticated Principal from the request.

Accepts either:
  - Authorization: Bearer <jwt>       — user-facing sessions
  - X-Api-Key: <key>                  — machine-to-machine (workers, evals, CI)

The dependency raises 401 if neither is present or both fail validation.
Anonymous access is not permitted.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.auth.jwt_utils import Principal, decode_access_token
from app.config import get_settings

_ANON_TENANT = "default"
_ANON_USER = "anonymous"


def _api_key_principal(key: str) -> Principal:
    settings = get_settings()
    if key not in settings.api_key_set:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
    # API keys get full access under the default tenant
    return Principal(user_id="api", tenant_id=_ANON_TENANT, scopes=["chat", "admin"])


async def get_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Principal:
    """FastAPI dependency.  Inject with `Depends(get_principal)`."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
        try:
            return decode_access_token(token)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if x_api_key:
        return _api_key_principal(x_api_key)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="provide Authorization: Bearer <token> or X-Api-Key: <key>",
    )


async def get_principal_optional(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Principal:
    """Like get_principal but returns a default anon principal when no auth header is present.
    Used in dev/eval mode when AUTH_REQUIRED=false."""
    try:
        return await get_principal(authorization=authorization, x_api_key=x_api_key)
    except HTTPException:
        return Principal(user_id=_ANON_USER, tenant_id=_ANON_TENANT, scopes=["chat"])
