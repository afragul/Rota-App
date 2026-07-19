from pydantic import BaseModel


class Place(BaseModel):
    """Google Places'ten dönen bir mekânın sadeleştirilmiş hâli."""

    place_id: str          # sonraki adımlarda rota için lazım olacak
    name: str
    address: str | None = None
    latitude: float
    longitude: float
    rating: float | None = None        # her mekânın puanı olmayabilir
    user_rating_count: int | None = None
    types: list[str] = []              # "cafe", "museum", "park" ...