from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import SecretStr

from app.core import auth

SECRET = "test-supabase-jwt-secret-en-az-32-bayt-olmali"


def _token(sub: str = "user-1", aud: str = "authenticated", secret: str = SECRET) -> str:
    return jwt.encode({"sub": sub, "aud": aud, "role": "authenticated"}, secret, algorithm="HS256")


@pytest.fixture
def secret_ayarli(monkeypatch):
    """supabase_jwt_secret ayarlıymış gibi davran (varsayılan None)."""
    monkeypatch.setattr(
        auth, "get_settings", lambda: SimpleNamespace(supabase_jwt_secret=SecretStr(SECRET))
    )


async def test_secret_ayarli_degilse_misafir_sayilir():
    # Varsayılan ayar: supabase_jwt_secret=None -> her zaman None (misafir).
    assert await auth.get_optional_user_id(authorization=f"Bearer {_token()}") is None


async def test_header_yoksa_misafir_sayilir(secret_ayarli):
    assert await auth.get_optional_user_id(authorization=None) is None


async def test_bearer_degilse_misafir_sayilir(secret_ayarli):
    assert await auth.get_optional_user_id(authorization=_token()) is None


async def test_gecerli_token_kullanici_id_doner(secret_ayarli):
    user_id = await auth.get_optional_user_id(authorization=f"Bearer {_token(sub='user-42')}")
    assert user_id == "user-42"


async def test_yanlis_secretle_imzali_token_reddedilir(secret_ayarli):
    bad = _token(secret="baska-bir-secret")
    assert await auth.get_optional_user_id(authorization=f"Bearer {bad}") is None


async def test_yanlis_audience_reddedilir(secret_ayarli):
    bad = _token(aud="baska-audience")
    assert await auth.get_optional_user_id(authorization=f"Bearer {bad}") is None


async def test_bozuk_token_reddedilir(secret_ayarli):
    assert await auth.get_optional_user_id(authorization="Bearer not-a-jwt") is None


# --- Supabase "Signing Keys" (ES256, asimetrik genel anahtar) desteği ---
# Yeni Supabase projelerinde legacy HS256 secret yerine/yanında bu kullanılıyor;
# SUPABASE_JWT_SECRET'teki değer "-----BEGIN" ile başlıyorsa ES256/RS256 denenir.

_EC_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
_EC_PUBLIC_PEM = _EC_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()


def _es256_token(sub: str = "user-1", aud: str = "authenticated") -> str:
    claims = {"sub": sub, "aud": aud, "role": "authenticated"}
    return jwt.encode(claims, _EC_PRIVATE_KEY, algorithm="ES256")


@pytest.fixture
def ec_public_key_ayarli(monkeypatch):
    """supabase_jwt_secret, PEM formatlı bir ES256 genel anahtarıymış gibi davran."""
    monkeypatch.setattr(
        auth, "get_settings", lambda: SimpleNamespace(supabase_jwt_secret=SecretStr(_EC_PUBLIC_PEM))
    )


async def test_es256_gecerli_token_kullanici_id_doner(ec_public_key_ayarli):
    user_id = await auth.get_optional_user_id(authorization=f"Bearer {_es256_token(sub='user-99')}")
    assert user_id == "user-99"


async def test_es256_yanlis_anahtarla_imzali_token_reddedilir(ec_public_key_ayarli):
    other_key = ec.generate_private_key(ec.SECP256R1())
    bad = jwt.encode({"sub": "user-1", "aud": "authenticated"}, other_key, algorithm="ES256")
    assert await auth.get_optional_user_id(authorization=f"Bearer {bad}") is None
