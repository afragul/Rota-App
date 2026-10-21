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

    jwt_expire_minutes: int = 15

    # Refresh token (httpOnly cookie, veritabanında hash'li) ömrü ve cookie ayarları.
    # Erişim token'ı kısa ömürlü, oturumu refresh token sürdürür.
    refresh_token_expire_days: int = 30
    # Cookie yalnızca HTTPS üzerinden gider; yerel http geliştirmede COOKIE_SECURE=false.
    cookie_secure: bool = True
    # Cookie'nin yolu, tarayıcının gördüğü adresle eşleşmeli: frontend API'ye /api
    # önekiyle gidiyor (bkz. vite.config.ts proxy), yani /api/auth/*.
    refresh_cookie_path: str = "/api/auth"
    # Aynı refresh token'ın bu süre içindeki ikinci kullanımı "çalıntı" sayılmaz
    # (iki sekmenin aynı anda yenilemesi); süre dışı tekrar kullanım tüm zinciri kapatır.
    refresh_reuse_grace_seconds: int = 10

    # Bir kullanıcının kaydedebileceği en fazla plan sayısı (depolama şişmesin).
    max_saved_plans_per_user: int = 100

    # Giriş yapmış kullanıcıların günlük kotası (hesap açmak ücretsiz olduğundan,
    # ücretli Google/Groq çağrılarını yapan uçlarda hesap başına da üst sınır var).
    # Gün, Türkiye saatine göre (UTC+3) başlar/biter. Sayaç veritabanında tutulur.
    user_daily_plan_limit: int = 30
    user_daily_legs_limit: int = 300

    # Kullanıcı başına favori / ziyaret edilen farklı mekan sayısı üst sınırları.
    max_favorites_per_user: int = 200
    max_visited_places_per_user: int = 500

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
