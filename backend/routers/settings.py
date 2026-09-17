"""The driver's alert switches, shared between the phone and the detector.

The app writes them and the detector polls them every few seconds, which is why
they live here rather than in SharedPreferences on the phone: the detector runs
on the laptop and has no way to read the phone's own storage.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Settings, utcnow
from schemas import SettingsIn, SettingsOut
from security import require_key

router = APIRouter(prefix="/settings", tags=["settings"],
                   dependencies=[Depends(require_key)])


def _row(db: Session) -> Settings:
    """The single settings row, created with its defaults on first use."""
    row = db.get(Settings, 1)
    if row is None:
        db.add(Settings(id=1))
        try:
            db.commit()
        except IntegrityError:
            # Two readers raced to create it. The other one won, which is all
            # we needed; carry on with theirs.
            db.rollback()
        row = db.get(Settings, 1)
    return row


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)):
    """Polled by the detector, and read by the app when the page opens.

    The app reads rather than trusting its own cache so the switches show what
    is actually in force -- otherwise a second phone, or a reinstall, would
    display its local defaults and silently push them on the next save.
    """
    return _row(db)


@router.put("", response_model=SettingsOut)
def write_settings(body: SettingsIn, db: Session = Depends(get_db)):
    """The app's Save button. The detector picks this up within ~5 seconds."""
    row = _row(db)
    row.buzzer_on = body.buzzer_on
    row.voice_alert_on = body.voice_alert_on
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    return row
