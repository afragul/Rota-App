import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Postgres'te JSONB, testlerde (SQLite) düz JSON.
JsonType = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    """Hesap. Supabase'teki `auth.users` + `profiles` tablolarının birleşimi."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # E-posta küçük harfe çevrilerek saklanır; büyük/küçük harf farkıyla çift hesap açılmasın.
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50))
    # argon2 hash'i; düz şifre asla saklanmaz.
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# Kullanıcı adı büyük/küçük harf farkı gözetmeden benzersiz ("Ada" ile "ada" aynı sayılır).
Index("uq_users_username_lower", func.lower(User.username), unique=True)


class SavedPlan(Base):
    """Kaydedilen/favorilenen rotalar; id ile link paylaşımı (`/shared/{id}`)."""

    __tablename__ = "saved_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    theme: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    stops: Mapped[list] = mapped_column(JsonType)
    legs: Mapped[list] = mapped_column(JsonType)
    routes_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class _PlaceMixin:
    """favorite_places ve visited_places'in ortak mekan alanları.

    Enlem/boylam BİLEREK yok: Google Maps Platform ToS'u (Places/Routes API Service
    Specific Terms 14.3/19.3) koordinatın en fazla 30 gün önbelleklenmesine izin
    veriyor, süresiz saklamaya değil. Bu yüzden hiç saklamıyoruz — bir mekan gerçekten
    kullanılacağı an (`app/api/routes/places.py::get_location`) anlık çekiliyor. Ad/adres
    gibi diğer alanlar bu maddenin kapsamında değil, süresiz saklanabilir."""

    place_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text, default=None)
    rating: Mapped[float | None] = mapped_column(Float, default=None)
    user_rating_count: Mapped[int | None] = mapped_column(Integer, default=None)
    types: Mapped[list] = mapped_column(JsonType, default=list, server_default="[]")


class FavoritePlace(_PlaceMixin, Base):
    """Tekil mekan favorisi; tamamen özel, paylaşım yok."""

    __tablename__ = "favorite_places"
    __table_args__ = (UniqueConstraint("user_id", "place_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VisitedPlace(_PlaceMixin, Base):
    """"Ulaşıldı" işaretlerinden türeyen ziyaret sayacı ("Sık Gidilen Yerlerin")."""

    __tablename__ = "visited_places"
    __table_args__ = (UniqueConstraint("user_id", "place_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    visit_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    last_visited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RefreshToken(Base):
    """Oturum yenileme token'ı. Ham değer yalnızca istemcinin httpOnly cookie'sinde;
    veritabanında SHA-256 özeti durur (sızarsa kullanılamaz). Her yenilemede dönüşür
    (eski satır iptal edilir, aynı `family_id` ile yenisi açılır); iptal edilmiş bir
    token yeniden gelirse çalınmış sayılıp ailenin tamamı kapatılır."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class DailyUsage(Base):
    """Giriş yapmış kullanıcının o günkü (Türkiye saatiyle) ücretli uç çağrı sayaçları.
    Veritabanında tutulur: süreç yeniden başlayınca sıfırlanmaz, çoklu worker'da paylaşılır."""

    __tablename__ = "daily_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    plans: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    legs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    searches: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class PasswordResetToken(Base):
    """Şifre sıfırlama bağlantısındaki tek kullanımlık token. Ham değer yalnızca e-postadaki
    bağlantıda; veritabanında SHA-256 özeti (sızarsa kullanılamaz)."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
