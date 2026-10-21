import re
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.db.models import PasswordResetToken
from app.services import email as email_service

SIFRE = "uzun-bir-sifre-1"
YENI = "yepyeni-sifre-9"
KAYIT = {"email": "ada@example.com", "username": "ada", "password": SIFRE}


@pytest.fixture
def gonderilenler(monkeypatch) -> list[dict]:
    """SMTP açık gibi davran ve e-postaları gerçekten göndermeden yakala."""
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "Rota <no-reply@rota.test>")
    monkeypatch.setattr(settings, "password_reset_cooldown_seconds", 0)
    kutu: list[dict] = []

    async def sahte(to: str, subject: str, body: str) -> None:
        kutu.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(email_service, "send_email", sahte)
    return kutu


def _token(mail: dict) -> str:
    return re.search(r"#reset=(\S+)", mail["body"]).group(1)


async def _kayit(client) -> None:
    assert (await client.post("/auth/register", json=KAYIT)).status_code == 201


async def _forgot(client, email: str = "ada@example.com"):
    return await client.post("/auth/forgot", json={"email": email})


async def _sifirla(client, token: str, sifre: str = YENI) -> int:
    r = await client.post("/auth/reset", json={"token": token, "new_password": sifre})
    return r.status_code


# --- yetenek ve yapılandırma ---


async def test_smtp_yoksa_ozellik_kapali(client):
    assert (await client.get("/auth/capabilities")).json() == {"password_reset": False}
    r = await _forgot(client)
    assert r.status_code == 503  # hesap var mı yok mu fark etmeksizin


async def test_smtp_varsa_ozellik_acik(client, gonderilenler):
    assert (await client.get("/auth/capabilities")).json() == {"password_reset": True}


# --- istek: hesap var/yok sızmamalı ---


async def test_kayitli_hesaba_baglanti_gonderilir(client, gonderilenler):
    await _kayit(client)
    r = await _forgot(client)
    assert r.status_code == 202
    assert len(gonderilenler) == 1
    mail = gonderilenler[0]
    assert mail["to"] == "ada@example.com"
    assert "#reset=" in mail["body"]  # token fragment'te: sunucu log'una/Referer'a gitmez
    assert "?reset=" not in mail["body"]
    assert "geçerli" in mail["body"] and "yapmadıysan" in mail["body"]


async def test_kayitsiz_ve_kayitli_ayni_cevabi_alir_kayitsiza_mail_gitmez(client, gonderilenler):
    await _kayit(client)
    var = await _forgot(client, "ada@example.com")
    yok = await _forgot(client, "yok@example.com")
    assert (var.status_code, var.json()) == (yok.status_code, yok.json())
    assert [m["to"] for m in gonderilenler] == ["ada@example.com"]


async def test_e_posta_buyuk_kucuk_harf_duyarsiz(client, gonderilenler):
    await _kayit(client)
    assert (await _forgot(client, "ADA@Example.COM")).status_code == 202
    assert len(gonderilenler) == 1


async def test_ayni_hesap_icin_bekleme_suresi_mail_bombardimanini_keser(
    client, gonderilenler, monkeypatch
):
    monkeypatch.setattr(get_settings(), "password_reset_cooldown_seconds", 60)
    await _kayit(client)
    for _ in range(3):
        assert (await _forgot(client)).status_code == 202  # cevap hep aynı
    assert len(gonderilenler) == 1


async def test_token_veritabaninda_ozet_olarak_saklanir(client, gonderilenler):
    await _kayit(client)
    await _forgot(client)
    ham = _token(gonderilenler[0])
    async with client.session_factory() as session:
        satir = await session.scalar(select(PasswordResetToken))
    assert satir.token_hash != ham and len(satir.token_hash) == 64


async def test_eposta_gonderimi_basarisiz_olsa_da_cevap_ayni(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "no-reply@rota.test")
    monkeypatch.setattr(settings, "password_reset_cooldown_seconds", 0)

    async def patlayan(to: str, subject: str, body: str) -> None:
        raise ConnectionRefusedError("smtp kapalı")

    monkeypatch.setattr(email_service, "send_email", patlayan)
    await _kayit(client)
    assert (await _forgot(client)).status_code == 202  # hata kullanıcıya yansımaz


# --- sıfırlama ---


async def test_baglantiyla_sifre_degisir(client, gonderilenler):
    await _kayit(client)
    await _forgot(client)
    token = _token(gonderilenler[0])

    r = await client.post("/auth/reset", json={"token": token, "new_password": YENI})
    assert r.status_code == 204
    eski = await client.post("/auth/login", json={"email": KAYIT["email"], "password": SIFRE})
    yeni = await client.post("/auth/login", json={"email": KAYIT["email"], "password": YENI})
    assert (eski.status_code, yeni.status_code) == (401, 200)


async def test_token_tek_kullanimliktir(client, gonderilenler):
    await _kayit(client)
    await _forgot(client)
    token = _token(gonderilenler[0])
    assert await _sifirla(client, token) == 204
    assert await _sifirla(client, token, "baska-sifre-77") == 400
    # İkinci denemenin şifresi uygulanmadı.
    giris = await client.post("/auth/login", json={"email": KAYIT["email"], "password": YENI})
    assert giris.status_code == 200


async def test_suresi_dolmus_token_reddedilir(client, gonderilenler):
    await _kayit(client)
    await _forgot(client)
    token = _token(gonderilenler[0])
    async with client.session_factory() as session:
        await session.execute(
            update(PasswordResetToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    r = await client.post("/auth/reset", json={"token": token, "new_password": YENI})
    assert r.status_code == 400
    assert "süresi dolmuş" in r.json()["detail"]


async def test_uydurma_token_reddedilir(client):
    assert await _sifirla(client, "uydurma-token-degeri") == 400


async def test_yeni_istek_eski_baglantiyi_gecersiz_kilar(client, gonderilenler):
    await _kayit(client)
    await _forgot(client)
    await _forgot(client)
    ilk, ikinci = (_token(m) for m in gonderilenler)
    assert await _sifirla(client, ilk) == 400
    assert await _sifirla(client, ikinci) == 204


async def test_kisa_yeni_sifre_reddedilir_ve_token_tuketilmez(client, gonderilenler):
    await _kayit(client)
    await _forgot(client)
    token = _token(gonderilenler[0])
    assert await _sifirla(client, token, "kisa") == 422
    assert await _sifirla(client, token) == 204


async def test_sifirlama_tum_oturumlari_kapatir(client, gonderilenler):
    await _kayit(client)
    ham = client.cookies.get("rota_refresh")  # saldırganın ele geçirmiş olabileceği oturum
    await _forgot(client)
    token = _token(gonderilenler[0])
    await client.post("/auth/reset", json={"token": token, "new_password": YENI})

    client.cookies.clear()
    yenile = await client.post("/auth/refresh", headers={"cookie": f"rota_refresh={ham}"})
    assert yenile.status_code == 401


async def test_hesap_silinince_sifirlama_tokenlari_da_gider(client, gonderilenler):
    await _kayit(client)
    await _forgot(client)
    giris = await client.post("/auth/login", json={"email": KAYIT["email"], "password": SIFRE})
    h = {"Authorization": f"Bearer {giris.json()['access_token']}"}
    await client.request("DELETE", "/me", json={"password": SIFRE}, headers=h)
    async with client.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PasswordResetToken)) == 0


# --- SMTP: smtplib çağrı sırası (gerçek sunucuya gitmeden) ---


class _SahteSMTP:
    olaylar: list[str]

    def __init__(self, host, port, timeout=None, context=None):
        type(self).olaylar = [f"baglan:{host}:{port}"]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        type(self).olaylar.append("kapat")

    def starttls(self, context=None):
        type(self).olaylar.append("starttls")

    def login(self, user, password):
        type(self).olaylar.append(f"login:{user}:{password}")

    def send_message(self, message):
        type(self).olaylar.append(f"gonder:{message['To']}:{message['Subject']}")


@pytest.fixture
def sahte_smtp(monkeypatch):
    class SahteSSL(_SahteSMTP):
        pass

    monkeypatch.setattr("app.services.email.smtplib.SMTP", _SahteSMTP)
    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", SahteSSL)
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_from", "no-reply@rota.test")
    monkeypatch.setattr(settings, "smtp_username", "kullanici")
    monkeypatch.setattr(settings, "smtp_password", SecretStr("gizli"))
    return SahteSSL


async def test_starttls_once_sifreler_sonra_giris_sonra_gonderir(sahte_smtp, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_security", "starttls")
    await email_service.send_email("a@b.com", "Konu", "Gövde")
    assert _SahteSMTP.olaylar == [
        "baglan:smtp.test:587",
        "starttls",  # kimlik bilgisi gitmeden ÖNCE kanal şifrelenir
        "login:kullanici:gizli",
        "gonder:a@b.com:Konu",
        "kapat",
    ]


async def test_ssl_modunda_starttls_yok(sahte_smtp, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_security", "ssl")
    await email_service.send_email("a@b.com", "Konu", "Gövde")
    assert "starttls" not in sahte_smtp.olaylar and "login:kullanici:gizli" in sahte_smtp.olaylar


async def test_kimlik_bilgisi_yoksa_login_denenmez(sahte_smtp, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_security", "none")
    monkeypatch.setattr(get_settings(), "smtp_username", None)
    await email_service.send_email("a@b.com", "Konu", "Gövde")
    assert all(not o.startswith("login") and o != "starttls" for o in _SahteSMTP.olaylar)


async def test_smtp_yapilandirilmamissa_gonderim_hata_verir():
    with pytest.raises(email_service.EmailNotConfiguredError):
        await email_service.send_email("a@b.com", "Konu", "Gövde")


def test_tls_baglami_sertifika_ve_ad_dogrular_ve_certifi_kullanir():
    import ssl

    import certifi

    context = email_service._ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    # Sistem deposuna bağımlı olmamalı: certifi paketindeki kökler yüklü.
    assert len(context.get_ca_certs()) > 0
    assert certifi.where().endswith("cacert.pem")
