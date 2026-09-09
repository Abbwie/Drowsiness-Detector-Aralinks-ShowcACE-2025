from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Event, utcnow
from schemas import EventIn, EventOut
from security import require_key

router = APIRouter(prefix="/events", tags=["events"], dependencies=[Depends(require_key)])


@router.post("", response_model=EventOut)
def report_event(body: EventIn, db: Session = Depends(get_db)):
    """The detector calls this each time an episode fires."""
    event = Event(occurred_at=utcnow(), seconds=body.seconds, kind=body.kind)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("", response_model=list[EventOut])
def list_events(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db)):
    """History for the app. A week by default, matching the home page chart."""
    since = utcnow() - timedelta(days=days)
    stmt = select(Event).where(Event.occurred_at >= since).order_by(Event.occurred_at.desc())
    return db.scalars(stmt).all()
