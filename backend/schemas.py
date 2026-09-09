from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    driver_name: str


class EventIn(BaseModel):
    seconds: float = Field(ge=0)
    kind: str = "DROWSY"


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_at: datetime
    seconds: float
    kind: str


class StatusIn(BaseModel):
    state: str
    perclos: float = 0.0


class StatusOut(BaseModel):
    state: str
    perclos: float
    updated_at: datetime
    online: bool
