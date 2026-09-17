"""VigiWatch API -- the relay between the detector and the phone app.

The detector stays on the laptop (it needs the webcam and dlib); this service
only holds what it reports, so the app can read it from any network.

On Railway: point the service's Root Directory at `backend/`, attach the
Postgres addon, and set the variables listed in .env.example.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers import events, login, settings, status


@asynccontextmanager
async def lifespan(app: FastAPI):
    # A bad DATABASE_URL used to raise here, which killed the process before it
    # could bind a port -- Railway then showed a bare 502 with the real cause
    # buried. Log it and start anyway: /health still answers, and the DB routes
    # return a readable 500.
    try:
        Base.metadata.create_all(engine)
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
