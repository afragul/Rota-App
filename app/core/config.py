from functools import lru_cache

from pydantic import SecretStr, field_validator
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
    geocoding_api_key: SecretStr
    google_geocoding_base_url: str = "https://maps.googleapis.com/maps/api/geocode/json"

    # Duraklar arası rota/mesafe/süre (Google Routes API); ayrı key, ayrı kısıtlama
    routes_api_key: SecretStr
    google_routes_base_url: str = "https://routes.googleapis.com/directions/v2:computeRoutes"

    # --- LLM ---
    groq_api_key: SecretStr
    groq_model: str = "openai/gpt-oss-120b"

    # Tüm dış çağrılar için ortak zaman aşımı (saniye)
    http_timeout: float = 10.0

    # --- Güvenlik ---
    # IP bazlı rate limiting (slowapi); testlerde kapatılır (bkz. conftest.py).
    rate_limit_enabled: bool = True

    # Giriş yapmamış (misafir) kullanıcıların günlük plan üretme kotası.
    # frontend/src/guestLimit.ts::GUEST_PLAN_LIMIT ile aynı değerde tutulmalı.
    guest_daily_plan_limit: int = 3

    # Giriş yapmamış kullanıcıların günlük /route/legs (durak sil/sırala/ekle)
    # çağrı kotası. Bu, plan üretmekten çok daha sık tetiklenen bir aksiyon
    # olduğu için guest_daily_plan_limit'ten kasıtlı olarak daha yüksek.
    guest_daily_legs_limit: int = 20

    # Kendi ürettiğimiz erişim token'larını (JWT, HS256) imzalamak için gizli anahtar.
    # Varsayılanı yok: eksikse uygulama açılışta patlar. En az 32 karakter,
    # rastgele olmalı (ör. `openssl rand -hex 32`); sızarsa herkes herhangi
    # bir kullanıcı adına token üretebilir.
    jwt_secret: SecretStr

    # Erişim token'ının ömrü (dakika).
    jwt_expire_minutes: int = 60

    # --- Veritabanı ---
    # PostgreSQL bağlantı adresi (asyncpg sürücüsü). Hesap/favori verisi
    # Supabase'ten buraya taşınırken kullanılacak; şimdilik opsiyonel.
    database_url: SecretStr | None = None

    # Virgülle ayrılmış izinli CORS origin listesi (prod'da frontend'in
    # gerçek adresiyle değiştirilir). Dev'de Vite proxy sunucu-sunucu
    # çalıştığı için bu ayar devreye girmez.
    cors_origins: str = "http://localhost:5173"

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_yeterince_uzun(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET en az 32 karakter olmalı")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
