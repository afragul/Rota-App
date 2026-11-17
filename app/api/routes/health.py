import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/health")
@limiter.exempt
def health_check() -> dict[str, str]:
    """Canlılık: süreç ayakta mı. Bağımlılıklara dokunmaz, hep hızlı döner."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check() -> JSONResponse:
    """Hazırlık: veritabanı gerçekten cevap veriyor mu. Dış API anahtarları tanımsızsa uygulama
    zaten açılmadığı için burada ayrıca sorulmaz. Dışarıya ayrıntı verilmez (yalnızca ok/hata);
    sebep log'a yazılır. DATABASE_URL tanımlı değilse DB'siz çalışma modudur ve hazır sayılır."""
    if get_settings().database_url is not None:
        try:
            async with get_engine().connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:
            # str(exc) bağlantı adresini (şifre dahil) taşıyabilir: yalnızca tür yazılır.
            logger.error("Hazırlık kontrolü: veritabanına ulaşılamadı (%s)", type(exc).__name__)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "unavailable"}
            )
    return JSONResponse(content={"status": "ok"})
