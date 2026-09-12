from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Status, utcnow
from schemas import StatusIn, StatusOut, as_utc
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
        db.add(Status(id=1))
        try:
            db.commit()
        except IntegrityError:
            # Two heartbeats raced to create the single row. The other one won,
            # which is all we needed; carry on and update it.
            db.rollback()
        row = db.get(Status, 1)

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
    updated = as_utc(row.updated_at)
    online = utcnow() - updated < STALE_AFTER

    # A stale reading is reported as OFFLINE rather than as the last thing the
    # detector said, so the app never shows a reassuring ALERT from an hour ago.
    return StatusOut(state=row.state if online else "OFFLINE", perclos=row.perclos,
                     updated_at=updated, online=online)
