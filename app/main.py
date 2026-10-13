from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logger
from app.core.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # uygulama açılırken çalışacaklar buraya gelecek (şimdilik boş)
    yield
    # uygulama kapanırken çalışacaklar buraya gelecek


def create_app() -> FastAPI:
    setup_logger()  # her seyden once
    settings = get_settings()
    # Prod'da (debug=False) API dokümantasyonu dışarıya açık kalmasın.
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    register_exception_handlers(app)

    app.include_router(api_router)
    return app


app = create_app()
