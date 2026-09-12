"""One shared key, sent as X-API-Key by both the detector and the app.

Without it the Railway URL is a public write endpoint that anyone who finds it
could post fake events to.
"""
import secrets

from fastapi import Header, HTTPException, status

from config import API_KEY


def matches(supplied: str, expected: str) -> bool:
    """Constant-time compare that survives non-ASCII input.

    `secrets.compare_digest` raises TypeError on str arguments holding any
    character above U+007F, which turned a mistyped accent in a username or
    key into a 500 instead of a 401. Bytes have no such restriction.
    """
    return secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


def require_key(x_api_key: str = Header(default="")) -> None:
    if not API_KEY or not matches(x_api_key, API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad API key")
