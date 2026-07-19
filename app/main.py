from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # uygulama açılırken çalışacaklar buraya gelecek (şimdilik boş)
    yield
    # uygulama kapanırken çalışacaklar buraya gelecek


def create_app() -> FastAPI:
    setup_logger()  # her seyden once
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(api_router)
    return app


app = create_app()
