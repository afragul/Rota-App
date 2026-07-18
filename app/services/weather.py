import httpx

from app.schemas.weather import CurrentWeather

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "açık",
    1: "az bulutlu",
    2: "parçalı bulutlu",
    3: "kapalı",
    45: "sisli",
    48: "kırağılı sis",
    51: "hafif çisenti",
    53: "çisenti",
    55: "yoğun çisenti",
    61: "hafif yağmurlu",
    63: "yağmurlu",
    65: "kuvvetli yağmurlu",
    71: "hafif karlı",
    73: "karlı",
    75: "yoğun karlı",
    80: "sağanak yağışlı",
    81: "sağanak yağışlı",
    82: "kuvvetli sağanak",
    95: "gök gürültülü fırtına",
}

async def _fetch_raw(latitude: float, longitude: float) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code",
        "timezone": "auto",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(OPEN_METEO_URL, params=params)
        response.raise_for_status()
        return response.json()

async def get_current_weather(latitude: float, longitude: float) -> CurrentWeather:
    data = await _fetch_raw(latitude, longitude)
    current = data["current"]
    code = current["weather_code"]

    return CurrentWeather(
        latitude=data["latitude"],
        longitude=data["longitude"],
        time=current["time"],
        temperature=current["temperature_2m"],
        condition=WEATHER_CODES.get(code, "bilinmiyor"),
        code=code,
    )