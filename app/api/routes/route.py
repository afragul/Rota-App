from fastapi import APIRouter, HTTPException, status

from app.schemas.plan import ApproachRequest, ApproachRoute
from app.services.routes import RoutesServiceError, get_approach_route

router = APIRouter(
    prefix="/route",
    tags=["route"],
)


@router.post("/approach", response_model=ApproachRoute)
async def approach(request: ApproachRequest) -> ApproachRoute:
    """Kullanıcının konumundan verilen noktaya (ilk durak) rota döndürür."""
    try:
        return await get_approach_route(
            origin=(request.origin_latitude, request.origin_longitude),
            destination=(request.destination_latitude, request.destination_longitude),
            mode=request.travel_mode,
        )
    except RoutesServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
