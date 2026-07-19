from fastapi import APIRouter

from app.api.routes import health, places, plan, weather

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(weather.router)
api_router.include_router(places.router)
api_router.include_router(plan.router)
