from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database import get_db
from models import Event, utcnow
from schemas import DeleteResult, EventIn, EventOut
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


@router.delete("", response_model=DeleteResult)
def clear_events(days: int | None = Query(None, ge=1, le=90),
                 db: Session = Depends(get_db)):
    """Delete recorded episodes. There is no undo -- the app confirms first.

    With no `days`, everything goes. With `days`, only episodes newer than that
    cutoff are removed, which mirrors the filter the list endpoint already takes
    rather than inventing a second way of naming a date range.
    """
    stmt = delete(Event)
    if days is not None:
        stmt = stmt.where(Event.occurred_at >= utcnow() - timedelta(days=days))
    removed = db.execute(stmt).rowcount
    db.commit()
    return DeleteResult(deleted=removed or 0)


@router.delete("/{event_id}", response_model=DeleteResult)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    """Remove one episode -- what a swipe on a single row in the app does.

    A missing row is reported as 0 deleted rather than 404: two swipes on the
    same entry, or a swipe against a list the relay has already been cleared
    behind, is not an error worth interrupting the driver for.
    """
    row = db.get(Event, event_id)
    if row is None:
        return DeleteResult(deleted=0)
    db.delete(row)
    db.commit()
    return DeleteResult(deleted=1)
