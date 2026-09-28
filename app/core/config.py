from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Uygulama ---
    app_name: str = "Rota App"
    debug: bool = False

    # --- Dış servisler ---
    # Varsayılanı yok: key eksikse uygulama açılışta patlar (bilinçli tercih)
    places_api_key: SecretStr

    # Google Places (New) taban adresi
    google_places_base_url: str = "https://places.googleapis.com/v1"

    # Şehir/adres -> koordinat çözümleme (Google Geocoding)
    maps_api_key: SecretStr
    google_geocoding_base_url: str = "https://maps.googleapis.com/maps/api/geocode/json"

    # --- LLM ---
    groq_api_key: SecretStr
    groq_model: str = "llama-3.3-70b-versatile"

    # Tüm dış çağrılar için ortak zaman aşımı (saniye)
    http_timeout: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
