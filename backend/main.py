"""VigiWatch API -- the relay between the detector and the phone app.

The detector stays on the laptop (it needs the webcam and dlib); this service
only holds what it reports, so the app can read it from any network.

On Railway: point the service's Root Directory at `backend/`, attach the
Postgres addon, and set the variables listed in .env.example.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect, text

from database import Base, engine
from routers import events, login, settings, status

# Columns added to a model after its table already exists. create_all() makes
# missing tables and nothing else, so on a database that already has a
# settings row these would never appear, and every read of the table would
# fail with "column does not exist" -- taking the app down rather than
# degrading. Checked against the live schema on each boot and skipped when
# present, which is what makes them safe to leave here permanently.
_ADDED_COLUMNS = {
    "settings": {
        "notify_contact_on": "BOOLEAN DEFAULT FALSE",
        "contact_name": "VARCHAR(80) DEFAULT ''",
        "contact_number": "VARCHAR(40) DEFAULT ''",
        "head_drop_ratio": "FLOAT DEFAULT 0.72",
        "no_face_alert_seconds": "FLOAT DEFAULT 20.0",
        "no_face_contact_seconds": "FLOAT DEFAULT 30.0",
    },
}


def _add_missing_columns():
    """Bring an existing table up to the shape the models expect."""
    inspector = inspect(engine)
    for table, columns in _ADDED_COLUMNS.items():
        if not inspector.has_table(table):
            continue            # create_all built it complete already
        present = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name in present:
                continue
            # One transaction each: on Postgres a failed statement poisons the
            # whole transaction, so a shared one would lose every later column.
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE {} ADD COLUMN {} {}".format(table, name, ddl)))
            print("migrated: added {}.{}".format(table, name), flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # A bad DATABASE_URL used to raise here, which killed the process before it
    # could bind a port -- Railway then showed a bare 502 with the real cause
    # buried. Log it and start anyway: /health still answers, and the DB routes
    # return a readable 500.
    try:
        Base.metadata.create_all(engine)
        _add_missing_columns()
    except Exception as exc:
        print(f"WARNING: could not reach the database: {exc}", flush=True)
    yield


app = FastAPI(title="Sentra API", lifespan=lifespan)

# The Android build does not need CORS; the Flutter web build does.
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(login.router)
app.include_router(events.router)
app.include_router(status.router)
app.include_router(settings.router)


@app.get("/health")
def health():
    """Unauthenticated ping, for checking a deploy came up."""
    return {"ok": True}
