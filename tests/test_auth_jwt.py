from datetime import UTC, datetime, timedelta

import jwt

from app.core import auth
from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token


def _secret() -> str:
    return get_settings().jwt_secret.get_secret_value()


def _token(sub: str = "user-1", secret: str | None = None, **overrides) -> str:
    now = datetime.now(UTC)
    claims = {"sub": sub, "iss": "rota-app", "iat": now, "exp": now + timedelta(minutes=5)}
    claims.update(overrides)
    return jwt.encode(claims, secret or _secret(), algorithm="HS256")


def test_olusturulan_token_dogrulanir():
    token, expires_in = create_access_token("user-7")
    assert expires_in == get_settings().jwt_expire_minutes * 60
    assert decode_access_token(token) == "user-7"


def test_yanlis_secretle_imzali_token_reddedilir():
    assert decode_access_token(_token(secret="baska-bir-secret-en-az-32-karakter-uzun")) is None


def test_suresi_dolmus_token_reddedilir():
    expired = _token(exp=datetime.now(UTC) - timedelta(seconds=1))
    assert decode_access_token(expired) is None


def test_yanlis_issuer_reddedilir():
    assert decode_access_token(_token(iss="baska-uygulama")) is None


def test_exp_olmayan_token_reddedilir():
    claims = {"sub": "user-1", "iss": "rota-app"}
    assert decode_access_token(jwt.encode(claims, _secret(), algorithm="HS256")) is None


def test_none_algoritmali_token_reddedilir():
    claims = {"sub": "user-1", "iss": "rota-app", "exp": datetime.now(UTC) + timedelta(minutes=5)}
    assert decode_access_token(jwt.encode(claims, None, algorithm="none")) is None


def test_bozuk_token_reddedilir():
    assert decode_access_token("not-a-jwt") is None


async def test_header_yoksa_misafir_sayilir():
    assert await auth.get_optional_user_id(authorization=None) is None


async def test_bearer_degilse_misafir_sayilir():
    assert await auth.get_optional_user_id(authorization=_token()) is None


async def test_gecerli_token_kullanici_id_doner():
    user_id = await auth.get_optional_user_id(authorization=f"Bearer {_token(sub='user-42')}")
    assert user_id == "user-42"


async def test_gecersiz_token_misafir_sayilir():
    assert await auth.get_optional_user_id(authorization="Bearer not-a-jwt") is None
