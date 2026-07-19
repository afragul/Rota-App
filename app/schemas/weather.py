from pydantic import BaseModel


class CurrentWeather(BaseModel):
    latitude: float
    longitude: float
    time: str
    temperature: float
    condition: str
    code: int
