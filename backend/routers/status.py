from datetime import timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Status, utcnow
from schemas import StatusIn, StatusOut
from security import require_key

router = APIRouter(prefix="/status", tags=["status"], dependencies=[Depends(require_key)])

# With no heartbeat for this long, the app should stop trusting the reading.
# Generous next to the detector's ~1 s posting rate, so a couple of dropped
# requests on bad wifi do not flicker the phone to OFFLINE mid-demo.
STALE_AFTER = timedelta(seconds=15)


@router.post("", response_model=StatusOut)
def push_status(body: StatusIn, db: Session = Depends(get_db)):
    """Heartbeat from the detector, about once a second."""
    row = db.get(Status, 1)
    if row is None:
        row = Status(id=1)
        db.add(row)

    row.state = body.state
    row.perclos = body.perclos
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return _out(row)


@router.get("", response_model=StatusOut)
def read_status(db: Session = Depends(get_db)):
    row = db.get(Status, 1)
    if row is None:      # detector has never checked in -- not an error
        return StatusOut(state="OFFLINE", perclos=0.0, updated_at=utcnow(), online=False)
    return _out(row)


def _out(row: Status) -> StatusOut:
    updated = row.updated_at
    if updated.tzinfo is None:     # SQLite returns naive datetimes, Postgres does not
        updated = updated.replace(tzinfo=timezone.utc)

    online = utcnow() - updated < STALE_AFTER
    
    return StatusOut(state=row.state if online else "OFFLINE", perclos=row.perclos,
                     updated_at=updated, online=online)
