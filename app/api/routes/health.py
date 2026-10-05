from fastapi import APIRouter

from app.core.rate_limit import limiter

router = APIRouter(tags=["system"])


@router.get("/health")
@limiter.exempt
def health_check() -> dict[str, str]:
    return {"status": "ok"}
