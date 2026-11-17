import json
import logging
import re
from contextvars import ContextVar
from logging.config import dictConfig

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s"

# İstek başına bir numara: aynı isteğin bütün log satırlarında görünür (bkz. request_id.py).
# İstek dışında (açılış, test) "-" kalır.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_KONTROL_KARAKTERLERI = re.compile(r"[\x00-\x1f\x7f-\x9f  ]+")


def clean_log(value: object, max_length: int = 80) -> str:
    """Kullanıcı metnini log'a yazmadan önce temizler: satır sonu/kontrol karakterleri
    boşluğa çevrilir (log injection: sahte bir log satırı eklenemesin) ve uzunluk kesilir."""
    text = _KONTROL_KARAKTERLERI.sub(" ", str(value)).strip()
    return text if len(text) <= max_length else text[:max_length] + "…"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Canlıda log toplayıcıların okuyabileceği, satır başına bir JSON nesnesi."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "-"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            # Yalnızca hata türü: traceback/mesaj httpx hatalarında URL'yi (key dahil) taşıyabilir.
            entry["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(entry, ensure_ascii=False)


def setup_logger(level: str = "INFO", log_format: str = "text") -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,  # uvicorn loglarini susturma
            "filters": {"request_id": {"()": RequestIdFilter}},
            "formatters": {
                "default": {
                    "format": LOG_FORMAT,
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "json": {"()": JsonFormatter},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json" if log_format == "json" else "default",
                    "filters": ["request_id"],
                },
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
            # httpx INFO'da istek URL'sini loglar; Geocoding key'i query string'de gittiği
            # için key log'a düşer. Sadece uyarı/hata seviyesi loglansın.
            "loggers": {
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
            },
        }
    )
