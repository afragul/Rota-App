import logging

from app.core.logging import setup_logger


def test_httpx_istek_url_loglanmaz():
    # Geocoding key'i URL'de gittiği için httpx INFO logları sızıntıya yol açar
    setup_logger()

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING


def test_clean_log_satir_sonu_ve_kontrol_karakterlerini_temizler():
    from app.core.logging import clean_log

    # Sahte bir log satırı eklenememeli (log injection)
    assert clean_log("İstanbul\nERROR | sahte satır\r\x00") == "İstanbul ERROR | sahte satır"
    assert "\n" not in clean_log("a b")


def test_clean_log_uzun_metni_keser():
    from app.core.logging import clean_log

    assert clean_log("a" * 500, max_length=10) == "a" * 10 + "…"


def test_json_bicimi_gecerli_json_ve_istek_numarasi_yazar():
    import json

    from app.core.logging import JsonFormatter, request_id_var

    token = request_id_var.set("abc12345")
    try:
        record = logging.LogRecord(
            "x", logging.WARNING, __file__, 1, "merhaba %s", ("dünya",), None
        )
        record.request_id = request_id_var.get()
        out = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert out["message"] == "merhaba dünya"
    assert out["level"] == "WARNING"
    assert out["request_id"] == "abc12345"


def test_json_bicimi_istisnada_yalnizca_tur_yazar():
    from app.core.logging import JsonFormatter

    try:
        raise RuntimeError("GIZLI-ANAHTAR")
    except RuntimeError:
        import sys

        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "hata", (), sys.exc_info())
    out = JsonFormatter().format(record)

    assert "RuntimeError" in out
    assert "GIZLI-ANAHTAR" not in out
