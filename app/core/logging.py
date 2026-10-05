from logging.config import dictConfig

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logger(level: str = "INFO") -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,  # uvicorn loglarini susturma
            "formatters": {
                "default": {
                    "format": LOG_FORMAT,
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
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
