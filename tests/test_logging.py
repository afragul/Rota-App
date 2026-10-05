import logging

from app.core.logging import setup_logger


def test_httpx_istek_url_loglanmaz():
    # Geocoding key'i URL'de gittiği için httpx INFO logları sızıntıya yol açar
    setup_logger()

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
