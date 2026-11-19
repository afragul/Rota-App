from pydantic import BaseModel


class Place(BaseModel):
    """Google Places'ten dönen bir mekânın sadeleştirilmiş hâli."""

    place_id: str  # sonraki adımlarda rota için lazım olacak
    name: str
    address: str | None = None
    latitude: float
    longitude: float
    rating: float | None = None  # her mekânın puanı olmayabilir
    user_rating_count: int | None = None
    types: list[str] = []  # "cafe", "museum", "park" ...


class PlaceLocation(BaseModel):
    """Yalnızca konum — Google ToS'un favori/ziyaret mekanlarında enlem/boylamın en
    fazla 30 gün önbelleklenmesine izin vermesi yüzünden hiç saklamıyoruz, kullanım
    anında (`GET /places/{place_id}/location`) anlık çekiyoruz."""

    latitude: float
    longitude: float
