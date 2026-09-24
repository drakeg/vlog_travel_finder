from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote_plus

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


class PageView(Base):
    __tablename__ = "page_view"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False, default="GET")
    status_code: Mapped[int] = mapped_column(nullable=False, default=200)
    referrer: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


class SavedPlace(Base):
    __tablename__ = "saved_place"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("place.id"), primary_key=True)
    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


class Trip(Base):
    __tablename__ = "trip"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


class TripPlace(Base):
    __tablename__ = "trip_place"

    trip_id: Mapped[int] = mapped_column(ForeignKey("trip.id"), primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("place.id"), primary_key=True)
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


class AccessRule(Base):
    __tablename__ = "access_rule"

    feature: Mapped[str] = mapped_column(String, primary_key=True)
    anonymous_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class Place(Base):
    __tablename__ = "place"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"), nullable=True)

    address: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    zipcode: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)

    venue_website_url: Mapped[str | None] = mapped_column(String, nullable=True)
    venue_youtube_url: Mapped[str | None] = mapped_column(String, nullable=True)
    venue_tiktok_url: Mapped[str | None] = mapped_column(String, nullable=True)
    venue_instagram_url: Mapped[str | None] = mapped_column(String, nullable=True)
    venue_facebook_url: Mapped[str | None] = mapped_column(String, nullable=True)

    vlog_youtube_url: Mapped[str | None] = mapped_column(String, nullable=True)
    vlog_tiktok_url: Mapped[str | None] = mapped_column(String, nullable=True)
    vlog_instagram_url: Mapped[str | None] = mapped_column(String, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    updated_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    category: Mapped[Category | None] = relationship("Category")

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category is not None else None

    @property
    def google_maps_url(self) -> str | None:
        if self.latitude is not None and self.longitude is not None:
            query = f"{self.latitude},{self.longitude}"
        else:
            parts = [self.address, self.city, self.state, self.zipcode]
            query = ", ".join(part.strip() for part in parts if part and part.strip())

        if not query:
            return None

        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


class SiteSetting(Base):
    __tablename__ = "site_setting"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(String, nullable=True)


class BlogPost(Base):
    __tablename__ = "blog_post"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    publish_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    updated_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


class ContactMessage(Base):
    __tablename__ = "contact_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    answered_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
