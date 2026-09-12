
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DATABASE_URL

# Railway hands out postgresql:// URLs; psycopg 3's dialect is postgresql+psycopg://.
_url = DATABASE_URL

for prefix in ("postgresql://", "postgres://"):
    if _url.startswith(prefix):
        _url = "postgresql+psycopg://" + _url[len(prefix):]
        break

connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}

# pool_pre_ping because Railway recycles idle Postgres connections, and a dead
# one would otherwise show up as a 500 on the first request after a quiet spell.
engine = create_engine(_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
