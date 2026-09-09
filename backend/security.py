"""One shared key, sent as X-API-Key by both the detector and the app.

Without it the Railway URL is a public write endpoint that anyone who finds it
could post fake events to.
"""
import os
import secrets

from fastapi import Header, HTTPException, status

API_KEY = os.environ.get("API_KEY", "")


def require_key(x_api_key: str = Header(default="")) -> None:
    if not API_KEY or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad API key")
