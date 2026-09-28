from pydantic import BaseModel


class GeocodeResult(BaseModel):
    """Şehir/adres aramasının sonucu."""

    formatted_address: str
    latitude: float
    longitude: float
