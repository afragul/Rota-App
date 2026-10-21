import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
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
    stops: Mapped[list] = mapped_column(JSONB)
    legs: Mapped[list] = mapped_column(JSONB)
    routes_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class _PlaceMixin:
    """favorite_places ve visited_places'in ortak mekan alanları."""

    place_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text, default=None)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    rating: Mapped[float | None] = mapped_column(Float, default=None)
    user_rating_count: Mapped[int | None] = mapped_column(Integer, default=None)
    types: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")


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
