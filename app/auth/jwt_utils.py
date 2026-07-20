"""JWT encode/decode helpers.  Uses python-jose with HS256."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import get_settings


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    scopes: list[str] = field(default_factory=list)

    def can(self, scope: str) -> bool:
        return scope in self.scopes or "admin" in self.scopes


def create_access_token(user_id: str, tenant_id: str, scopes: list[str] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": user_id,
        "tenant": tenant_id,
        "scopes": scopes or ["chat"],
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Principal:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError(f"invalid token: {exc}") from exc
    return Principal(
        user_id=payload["sub"],
        tenant_id=payload["tenant"],
        scopes=payload.get("scopes", []),
    )
