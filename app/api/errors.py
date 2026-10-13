import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.geocoding import GeocodingServiceError
from app.services.places import PlacesServiceError
from app.services.planner import PlannerServiceError
from app.services.routes import RoutesServiceError
from app.services.weather import WeatherServiceError

logger = logging.getLogger(__name__)

# Dış servis hataları: route'lar tek tek try/except yazmak yerine bunlara güvenir.
SERVICE_ERRORS = (
    GeocodingServiceError,
    PlacesServiceError,
    PlannerServiceError,
    RoutesServiceError,
    WeatherServiceError,
)


async def _service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Servis hata mesajları istemciye gösterilmek üzere yazılmış (URL/key taşımaz)
    logger.warning("%s %s -> %s: %s", request.method, request.url.path, type(exc).__name__, exc)
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Beklenmeyen hata: ayrıntı istemciye gitmez. str(exc) bilerek loglanmıyor; httpx
    # hataları URL'yi (query string'deki key dahil) taşıyabilir. Yalnızca tür ve yol.
    logger.error(
        "%s %s -> beklenmeyen hata: %s", request.method, request.url.path, type(exc).__name__
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Beklenmeyen bir hata oluştu"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    for error_type in SERVICE_ERRORS:
        app.add_exception_handler(error_type, _service_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
