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

    # Supabase JWT'sini doğrulamak için: Supabase Dashboard → Project Settings
    # → API → JWT Settings. İki türden biri olabilir, hangisi varsa o kopyalanır:
    # eski/legacy "JWT Secret" (düz metin, HS256) ya da yeni "Signing Keys"
    # özelliğinin PEM formatlı genel anahtarı ("-----BEGIN PUBLIC KEY-----" ile
    # başlar, ES256/RS256) — app/core/auth.py bu önekten otomatik ayırt eder.
    # Ayarlanmazsa her istek misafir sayılır; backend auth'tan habersiz kalır.
    supabase_jwt_secret: SecretStr | None = None

    # Virgülle ayrılmış izinli CORS origin listesi (prod'da frontend'in
    # gerçek adresiyle değiştirilir). Dev'de Vite proxy sunucu-sunucu
    # çalıştığı için bu ayar devreye girmez.
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
