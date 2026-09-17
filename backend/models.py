from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Event(Base):
    """One episode the detector reported -- what the app's history page lists."""
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    seconds: Mapped[float] = mapped_column(Float)      
    kind: Mapped[str] = mapped_column(String(20))      


class Status(Base):
    __tablename__ = "status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    state: Mapped[str] = mapped_column(String(20), default="OFFLINE")
    perclos: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Settings(Base):
    """The app's alert switches, so the detector can read them from anywhere.

    One row, id=1, the same shape as Status. Both default ON: a driver who has
    never opened the Settings page should still get every alert the hardware
    can give them, and a safety feature that defaults to silent is the wrong
    way round.
    """
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    buzzer_on: Mapped[bool] = mapped_column(Boolean, default=True)
    voice_alert_on: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
