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

    # Who to tell, and whether to tell them at all.
    #
    # Here rather than on the phone because the detector is what sends the
    # message and the detector runs on the laptop: a number typed into the app
    # and left in SharedPreferences could never reach it, which is exactly the
    # gap this closes. The app used to promise it would message this person
    # while the detector messaged a number compiled into its source.
    #
    # Off by default, unlike the two switches above. They decide whether this
    # driver gets a louder warning; this one decides whether somebody else is
    # told where the driver is up to. That is not a default anyone should get
    # without choosing it.
    notify_contact_on: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_name: Mapped[str] = mapped_column(String(80), default="")
    contact_number: Mapped[str] = mapped_column(String(40), default="")

    # Tuning the driver can reach without editing the detector's source.
    #
    # head_drop_ratio especially: a webcam on top of a monitor and one clipped
    # to a dashboard do not want the same number, because the baseline it is
    # measured against depends on where the lens sits relative to the eyes.
    # Leaving it compiled in meant a false alarm every few seconds was only
    # fixable by someone willing to edit Python.
    head_drop_ratio: Mapped[float] = mapped_column(Float, default=0.72)
    no_face_alert_seconds: Mapped[float] = mapped_column(Float, default=20.0)
    no_face_contact_seconds: Mapped[float] = mapped_column(Float, default=30.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
