from fastapi import APIRouter

from app.api.routes import (
    auth,
    favorites,
    geocoding,
    health,
    me,
    places,
    plan,
    plans,
    route,
    visits,
    weather,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(weather.router)
api_router.include_router(places.router)
api_router.include_router(geocoding.router)
api_router.include_router(plan.router)
api_router.include_router(route.router)
api_router.include_router(plans.router)
api_router.include_router(plans.shared_router)
api_router.include_router(favorites.router)
api_router.include_router(visits.router)
api_router.include_router(me.router)
