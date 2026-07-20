"""Auth unit tests — no network or DB needed."""
from __future__ import annotations

import pytest

from app.auth.jwt_utils import Principal, create_access_token, decode_access_token
from app.auth.middleware import get_principal, get_principal_optional


def test_round_trip_jwt():
    token = create_access_token("user1", "tenant-a", ["chat"])
    p = decode_access_token(token)
    assert p.user_id == "user1"
    assert p.tenant_id == "tenant-a"
    assert "chat" in p.scopes


def test_invalid_token_raises():
    with pytest.raises(ValueError, match="invalid token"):
        decode_access_token("not-a-jwt")


def test_principal_can_scope():
    p = Principal(user_id="u", tenant_id="t", scopes=["chat"])
    assert p.can("chat") is True
    assert p.can("admin") is False


def test_principal_admin_can_all():
    p = Principal(user_id="u", tenant_id="t", scopes=["admin"])
    assert p.can("chat") is True
    assert p.can("admin") is True


@pytest.mark.asyncio
async def test_get_principal_bearer():
    token = create_access_token("u2", "tenant-b", ["chat"])
    p = await get_principal(authorization=f"Bearer {token}", x_api_key=None)
    assert p.user_id == "u2"


@pytest.mark.asyncio
async def test_get_principal_api_key(monkeypatch):
    monkeypatch.setenv("API_KEYS", "my-secret-key")
    from app.config import get_settings
    get_settings.cache_clear()
    p = await get_principal(authorization=None, x_api_key="my-secret-key")
    assert p.user_id == "api"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_get_principal_missing_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_principal(authorization=None, x_api_key=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_principal_optional_falls_back():
    p = await get_principal_optional(authorization=None, x_api_key=None)
    assert p.user_id == "anonymous"
