from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def as_utc(value: datetime) -> datetime:
    """Stamp UTC on a naive datetime.

    SQLite drops the offset on the way in and hands back naive values;
    Postgres keeps it. Serialised naive, an event timestamp reaches the phone
    with no zone and `DateTime.parse` reads it as local time -- eight hours
    off in Manila. Normalising here keeps the two backends telling the app
    the same thing.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(as_utc)]

# Both columns are String(20). Unbounded input was stored oversized on SQLite
# and would raise on Postgres; the detector's longest word is "FATIGUE WARNING".
Label = Annotated[str, Field(min_length=1, max_length=20)]


class LoginRequest(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


class LoginResponse(BaseModel):
    driver_name: str


class EventIn(BaseModel):
    seconds: float = Field(ge=0)
    kind: Label = "DROWSY"


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_at: UtcDatetime
    seconds: float
    kind: str


class StatusIn(BaseModel):
    state: Label
    perclos: float = Field(default=0.0, ge=0.0, le=1.0)   # PERCLOS is a fraction


class StatusOut(BaseModel):
    state: str
    perclos: float
    updated_at: UtcDatetime
    online: bool


class SettingsIn(BaseModel):
    """A full replacement, not a patch -- the app always sends both switches,
    so there is no way to read one back stale and write it over the other."""
    buzzer_on: bool
    voice_alert_on: bool


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    buzzer_on: bool
    voice_alert_on: bool
    updated_at: UtcDatetime
